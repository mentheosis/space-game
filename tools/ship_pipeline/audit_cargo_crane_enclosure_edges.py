#!/usr/bin/env python3
"""Audit CargoCrane exposed traversal edges against generated enclosure bands."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "assets/source/blender/ships/cargo_crane/cargo_crane_interior_layout_contract.json"
TRAVERSAL_PATH = ROOT / "assets/models/ship/cargo_crane/cargo_crane_traversal_surfaces.json"
ENCLOSURE_PATH = ROOT / "assets/models/ship/cargo_crane/cargo_crane_enclosure_bands.json"
REPORT_DIR = ROOT / "reports/ship_pipeline/cargo_crane_enclosure_edge_audit"
REPORT_JSON = REPORT_DIR / "cargo_crane_enclosure_edge_audit.json"
REPORT_MD = REPORT_DIR / "cargo_crane_enclosure_edge_audit.md"
REPORT_SVG = REPORT_DIR / "cargo_crane_enclosure_edge_audit_current.svg"

SAMPLE_STEP = 0.2
OUTWARD_PROBE = 0.65
WALL_NEAR_TOLERANCE = 0.18
CONNECT_Y_TOLERANCE = 0.9
WALL_VERTICAL_PADDING = 0.15
PLAYER_HEIGHT = 1.8
PLAYER_RADIUS = 0.42


@dataclass(frozen=True)
class Vec2:
    x: float
    z: float

    def __add__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x + other.x, self.z + other.z)

    def __sub__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x - other.x, self.z - other.z)

    def __mul__(self, scalar: float) -> "Vec2":
        return Vec2(self.x * scalar, self.z * scalar)

    def length(self) -> float:
        return math.hypot(self.x, self.z)

    def normalized(self) -> "Vec2":
        length = self.length()
        if length <= 1e-6:
            return Vec2(0.0, 1.0)
        return Vec2(self.x / length, self.z / length)


@dataclass(frozen=True)
class EdgeObligation:
    surface: str
    edge: str
    role: str
    start: Vec2
    end: Vec2
    normal: Vec2
    y: float
    source_type: str
    end_y: float | None = None


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def round4(value: float) -> float:
    return round(value, 4)


def surface_name(surface: dict) -> str:
    return str(surface.get("name", "surface"))


def floor_bounds(surface: dict) -> tuple[float, float, float, float, float] | None:
    if surface.get("type") not in {"floor_box", "objective_floor_patch"}:
        return None
    center = surface["center"]
    size = surface["size"]
    return (
        center[0] - size[0] * 0.5,
        center[0] + size[0] * 0.5,
        center[2] - size[2] * 0.5,
        center[2] + size[2] * 0.5,
        center[1],
    )


def ramp_corners(start: list[float], end: list[float], width: float) -> tuple[Vec2, Vec2, Vec2, Vec2]:
    a = Vec2(start[0], start[2])
    b = Vec2(end[0], end[2])
    forward = (b - a).normalized()
    right = Vec2(forward.z, -forward.x)
    half_width = width * 0.5
    return (
        a - right * half_width,
        a + right * half_width,
        b + right * half_width,
        b - right * half_width,
    )


def build_edges(traversal: dict) -> list[EdgeObligation]:
    edges: list[EdgeObligation] = []
    for surface in traversal.get("surfaces", []):
        name = surface_name(surface)
        kind = surface.get("type")
        role = str(surface.get("role", ""))
        if kind in {"floor_box", "objective_floor_patch"}:
            bounds = floor_bounds(surface)
            if bounds is None:
                continue
            x0, x1, z0, z1, y = bounds
            edges.extend(
                [
                    EdgeObligation(name, "port", role, Vec2(x0, z0), Vec2(x0, z1), Vec2(-1.0, 0.0), y, kind, y),
                    EdgeObligation(name, "starboard", role, Vec2(x1, z0), Vec2(x1, z1), Vec2(1.0, 0.0), y, kind, y),
                    EdgeObligation(name, "aft", role, Vec2(x0, z0), Vec2(x1, z0), Vec2(0.0, -1.0), y, kind, y),
                    EdgeObligation(name, "forward", role, Vec2(x0, z1), Vec2(x1, z1), Vec2(0.0, 1.0), y, kind, y),
                ]
            )
        elif kind == "ramp" and role not in {"entry_ramp", "entry_hatch_path"}:
            start = surface["start"]
            end = surface["end"]
            width = float(surface.get("width", 1.0))
            left_start, right_start, right_end, left_end = ramp_corners(start, end, width)
            forward = (Vec2(end[0], end[2]) - Vec2(start[0], start[2])).normalized()
            right = Vec2(forward.z, -forward.x)
            edges.extend(
                [
                    EdgeObligation(name, "left_guard", role, left_start, left_end, right * -1.0, start[1], kind, end[1]),
                    EdgeObligation(name, "right_guard", role, right_start, right_end, right, start[1], kind, end[1]),
                ]
            )
        elif kind == "stair_path":
            points = surface.get("points", [])
            width = float(surface.get("width", 1.0))
            for index in range(len(points) - 1):
                start = points[index]
                end = points[index + 1]
                left_start, right_start, right_end, left_end = ramp_corners(start, end, width)
                forward = (Vec2(end[0], end[2]) - Vec2(start[0], start[2])).normalized()
                right = Vec2(forward.z, -forward.x)
                edges.extend(
                    [
                        EdgeObligation(name, f"left_guard_{index:02d}", role, left_start, left_end, right * -1.0, start[1], kind, end[1]),
                        EdgeObligation(name, f"right_guard_{index:02d}", role, right_start, right_end, right, start[1], kind, end[1]),
                    ]
                )
    return edges


def sample_edge(edge: EdgeObligation) -> list[Vec2]:
    delta = edge.end - edge.start
    length = delta.length()
    count = max(2, math.ceil(length / SAMPLE_STEP) + 1)
    return [edge.start + delta * (index / (count - 1)) for index in range(count)]


def edge_sample_y(edge: EdgeObligation, point: Vec2) -> float:
    if edge.end_y is None or abs(edge.end_y - edge.y) <= 1e-6:
        return edge.y
    delta = edge.end - edge.start
    denom = max(1e-6, delta.x * delta.x + delta.z * delta.z)
    offset = point - edge.start
    t = max(0.0, min(1.0, (offset.x * delta.x + offset.z * delta.z) / denom))
    return edge.y + (edge.end_y - edge.y) * t


def point_in_floor(point: Vec2, y: float, surface: dict) -> bool:
    bounds = floor_bounds(surface)
    if bounds is None:
        return False
    x0, x1, z0, z1, sy = bounds
    if abs(y - sy) > CONNECT_Y_TOLERANCE:
        return False
    return x0 - 0.05 <= point.x <= x1 + 0.05 and z0 - 0.05 <= point.z <= z1 + 0.05


def point_in_oriented_surface(point: Vec2, y: float, surface: dict) -> bool:
    kind = surface.get("type")
    if kind == "ramp":
        start = surface["start"]
        end = surface["end"]
        if min(start[1], end[1]) - CONNECT_Y_TOLERANCE > y or max(start[1], end[1]) + CONNECT_Y_TOLERANCE < y:
            return False
        return point_in_poly(point, ramp_corners(start, end, float(surface.get("width", 1.0))))
    if kind == "stair_path":
        points = surface.get("points", [])
        for index in range(len(points) - 1):
            start = points[index]
            end = points[index + 1]
            if min(start[1], end[1]) - CONNECT_Y_TOLERANCE <= y <= max(start[1], end[1]) + CONNECT_Y_TOLERANCE:
                if point_in_poly(point, ramp_corners(start, end, float(surface.get("width", 1.0)))):
                    return True
    return False


def point_in_poly(point: Vec2, corners: tuple[Vec2, Vec2, Vec2, Vec2]) -> bool:
    sign = None
    for index, a in enumerate(corners):
        b = corners[(index + 1) % len(corners)]
        cross = (b.x - a.x) * (point.z - a.z) - (b.z - a.z) * (point.x - a.x)
        if abs(cross) < 1e-6:
            continue
        current = cross > 0
        if sign is None:
            sign = current
        elif sign != current:
            return False
    return True


def has_connected_traversal(point: Vec2, y: float, source_surface: str, traversal: dict) -> bool:
    for surface in traversal.get("surfaces", []):
        if surface_name(surface) == source_surface:
            continue
        if point_in_floor(point, y, surface) or point_in_oriented_surface(point, y, surface):
            return True
    return False


def approved_openings(contract: dict) -> list[dict]:
    openings = []
    for opening in contract.get("enclosure_generation", {}).get("side_wall_openings", []):
        openings.append(opening)
    return openings


def is_approved_opening(edge: EdgeObligation, point: Vec2, y: float, openings: list[dict]) -> bool:
    for opening in openings:
        side = opening.get("side")
        if side not in {"port", "starboard"} or edge.edge not in {"port", "starboard"}:
            continue
        if side != edge.edge:
            continue
        center_z = float(opening["center_z"])
        width_z = float(opening["width_z"])
        center_y = float(opening.get("center_y", y))
        height_y = float(opening.get("height_y", PLAYER_HEIGHT))
        if abs(point.z - center_z) <= width_z * 0.5 and abs(y - center_y) <= height_y * 0.5 + 0.7:
            return True
    return False


def is_internal_cockpit_stairwell_opening(edge: EdgeObligation, point: Vec2, y: float) -> bool:
    if not edge.surface.startswith("cockpit_"):
        return False
    if edge.source_type not in {"floor_box", "stair_path"}:
        return False
    return -4.25 <= point.x <= 4.25 and 59.3 <= point.z <= 68.6 and -9.4 <= y <= 0.6


def band_bounds(band: dict) -> tuple[float, float, float, float, float, float]:
    center = band["center"]
    size = rotated_aabb_size(band["size"], band.get("rotation_degrees"))
    return (
        center[0] - size[0] * 0.5,
        center[0] + size[0] * 0.5,
        center[1] - size[1] * 0.5,
        center[1] + size[1] * 0.5,
        center[2] - size[2] * 0.5,
        center[2] + size[2] * 0.5,
    )


def rotated_aabb_size(size: list[float], rotation_degrees: list[float] | None) -> list[float]:
    if not rotation_degrees:
        return size

    rx = math.radians(float(rotation_degrees[0]))
    ry = math.radians(float(rotation_degrees[1])) if len(rotation_degrees) > 1 else 0.0
    rz = math.radians(float(rotation_degrees[2])) if len(rotation_degrees) > 2 else 0.0

    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    # Godot Euler order is not needed exactly for the audit; a conservative AABB
    # keeps rotated enclosure bands visible to edge coverage checks.
    matrix = (
        (cy * cz, cz * sx * sy - cx * sz, sx * sz + cx * cz * sy),
        (cy * sz, cx * cz + sx * sy * sz, cx * sy * sz - cz * sx),
        (-sy, cy * sx, cx * cy),
    )
    return [
        abs(matrix[axis][0]) * size[0] + abs(matrix[axis][1]) * size[1] + abs(matrix[axis][2]) * size[2]
        for axis in range(3)
    ]


def band_covers_sample(edge: EdgeObligation, point: Vec2, y: float, enclosure: dict) -> str | None:
    expected_y_min = y - WALL_VERTICAL_PADDING
    expected_y_max = y + PLAYER_HEIGHT
    for band in enclosure.get("bands", []):
        if band.get("type") not in {"side_wall", "end_wall"}:
            continue
        x0, x1, y0, y1, z0, z1 = band_bounds(band)
        if y1 < expected_y_min or y0 > expected_y_max:
            continue
        near_x = x0 - WALL_NEAR_TOLERANCE <= point.x <= x1 + WALL_NEAR_TOLERANCE
        near_z = z0 - WALL_NEAR_TOLERANCE <= point.z <= z1 + WALL_NEAR_TOLERANCE
        capsule_x = x0 - PLAYER_RADIUS <= point.x <= x1 + PLAYER_RADIUS
        capsule_z = z0 - PLAYER_RADIUS <= point.z <= z1 + PLAYER_RADIUS
        if near_x and near_z:
            return str(band.get("name", "band"))
        if capsule_x and capsule_z:
            # Near enough to touch the capsule but not enough to be flush. This is
            # treated as uncovered so endpoint/corner seams do not get a free pass.
            continue
    return None


def audit() -> dict:
    contract = load_json(CONTRACT_PATH)
    traversal = load_json(TRAVERSAL_PATH)
    enclosure = load_json(ENCLOSURE_PATH)
    openings = approved_openings(contract)
    failures = []
    guarded = 0
    connected = 0
    approved = 0
    samples = 0

    for edge in build_edges(traversal):
        for point in sample_edge(edge):
            samples += 1
            sample_y = edge_sample_y(edge, point)
            outward = point + edge.normal.normalized() * OUTWARD_PROBE
            if has_connected_traversal(outward, sample_y, edge.surface, traversal):
                connected += 1
                continue
            if is_internal_cockpit_stairwell_opening(edge, point, sample_y):
                connected += 1
                continue
            covering_band = band_covers_sample(edge, point, sample_y, enclosure)
            if covering_band is not None:
                guarded += 1
                continue
            check = "approved_opening_without_connected_traversal" if is_approved_opening(edge, point, sample_y, openings) else "unguarded_exposed_edge"
            if check == "approved_opening_without_connected_traversal":
                approved += 1
            failures.append(
                {
                    "check": check,
                    "surface": edge.surface,
                    "edge": edge.edge,
                    "source_type": edge.source_type,
                    "local_point": [round4(point.x), round4(sample_y), round4(point.z)],
                    "outward_probe": [round4(outward.x), round4(sample_y), round4(outward.z)],
                }
            )

    suspicious_walls = audit_unanchored_walls(enclosure, traversal)
    intrusive_walls = audit_intrusive_walls(enclosure, traversal)
    status = "PASS" if not failures and not suspicious_walls else "FAIL"
    status = "FAIL" if intrusive_walls else status
    return {
        "schema_version": 1,
        "ship_id": "cargo_crane",
        "status": status,
        "sample_count": samples,
        "guarded_sample_count": guarded,
        "connected_sample_count": connected,
        "approved_opening_failure_count": approved,
        "failure_count": len(failures),
        "suspicious_wall_count": len(suspicious_walls),
        "intrusive_wall_count": len(intrusive_walls),
        "failures": failures,
        "suspicious_walls": suspicious_walls,
        "intrusive_walls": intrusive_walls,
    }


def audit_unanchored_walls(enclosure: dict, traversal: dict) -> list[dict]:
    suspicious = []
    floor_edges = build_edges(traversal)
    for band in enclosure.get("bands", []):
        if band.get("type") not in {"side_wall", "end_wall"}:
            continue
        if is_sloped_transition_bulkhead(band):
            continue
        x0, x1, _y0, _y1, z0, z1 = band_bounds(band)
        wall_samples = sample_wall_horizontal_span(x0, x1, z0, z1)
        unanchored_samples = []
        for wall_sample in wall_samples:
            if not wall_sample_near_any_edge(wall_sample, floor_edges):
                unanchored_samples.append(wall_sample)
        if unanchored_samples:
            suspicious.append(
                {
                    "check": "wall_samples_not_near_traversal_edge",
                    "band": band.get("name", "band"),
                    "type": band.get("type"),
                    "center": [round4(value) for value in band["center"]],
                    "size": [round4(value) for value in band["size"]],
                    "unanchored_sample_count": len(unanchored_samples),
                    "first_unanchored_samples": [[round4(p.x), round4(p.z)] for p in unanchored_samples[:8]],
                }
            )
    return suspicious


def sample_wall_horizontal_span(x0: float, x1: float, z0: float, z1: float) -> list[Vec2]:
    if x1 - x0 >= z1 - z0:
        length = x1 - x0
        count = max(2, math.ceil(length / SAMPLE_STEP) + 1)
        z = (z0 + z1) * 0.5
        return [Vec2(x0 + (x1 - x0) * index / (count - 1), z) for index in range(count)]
    length = z1 - z0
    count = max(2, math.ceil(length / SAMPLE_STEP) + 1)
    x = (x0 + x1) * 0.5
    return [Vec2(x, z0 + (z1 - z0) * index / (count - 1)) for index in range(count)]


def wall_sample_near_any_edge(wall_sample: Vec2, edges: list[EdgeObligation]) -> bool:
    for edge in edges:
        for point in sample_edge(edge)[:: max(1, int(0.9 / SAMPLE_STEP))]:
            if abs(point.x - wall_sample.x) <= 0.75 and abs(point.z - wall_sample.z) <= 0.75:
                return True
    return False


def audit_intrusive_walls(enclosure: dict, traversal: dict) -> list[dict]:
    intrusive = []
    edges = build_edges(traversal)
    for band in enclosure.get("bands", []):
        if band.get("type") not in {"side_wall", "end_wall"}:
            continue
        if is_sloped_transition_bulkhead(band):
            continue
        x0, x1, _y0, _y1, z0, z1 = band_bounds(band)
        bad_samples = []
        for wall_sample in sample_wall_horizontal_span(x0, x1, z0, z1):
            if wall_sample_near_any_edge(wall_sample, edges):
                continue
            for surface in traversal.get("surfaces", []):
                if point_inside_traversal_footprint(wall_sample, surface):
                    bad_samples.append([round4(wall_sample.x), round4(wall_sample.z), surface_name(surface)])
                    break
        if bad_samples:
            intrusive.append(
                {
                    "check": "wall_intrudes_into_traversable_free_space",
                    "band": band.get("name", "band"),
                    "type": band.get("type"),
                    "center": [round4(value) for value in band["center"]],
                    "size": [round4(value) for value in band["size"]],
                    "intrusive_sample_count": len(bad_samples),
                    "first_intrusive_samples": bad_samples[:8],
                }
            )
    return intrusive


def is_sloped_transition_bulkhead(band: dict) -> bool:
    return str(band.get("name", "")) == "cockpit_lower_sloped_aft_bulkhead"


def point_inside_traversal_footprint(point: Vec2, surface: dict) -> bool:
    bounds = floor_bounds(surface)
    if bounds is not None:
        x0, x1, z0, z1, _y = bounds
        return x0 + 0.35 <= point.x <= x1 - 0.35 and z0 + 0.35 <= point.z <= z1 - 0.35
    if surface.get("type") == "ramp":
        return point_in_poly(point, ramp_corners(surface["start"], surface["end"], float(surface.get("width", 1.0))))
    if surface.get("type") == "stair_path":
        points = surface.get("points", [])
        for index in range(len(points) - 1):
            if point_in_poly(point, ramp_corners(points[index], points[index + 1], float(surface.get("width", 1.0)))):
                return True
    return False


def write_reports(report: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# CargoCrane Enclosure Edge Audit",
        "",
        f"Status: **{report['status']}**",
        "",
        f"- Samples: `{report['sample_count']}`",
        f"- Guarded samples: `{report['guarded_sample_count']}`",
        f"- Connected traversal samples: `{report['connected_sample_count']}`",
        f"- Approved opening failures: `{report['approved_opening_failure_count']}`",
        f"- Unguarded edge failures: `{report['failure_count']}`",
        f"- Suspicious walls: `{report['suspicious_wall_count']}`",
        f"- Intrusive walls: `{report['intrusive_wall_count']}`",
        f"- Projection: `{REPORT_SVG.relative_to(ROOT)}`",
        "",
        "## Unguarded Edge Failures",
        "",
    ]
    for failure in report["failures"][:80]:
        lines.append(f"- `{failure['surface']}` `{failure['edge']}` at `{failure['local_point']}`")
    if len(report["failures"]) > 80:
        lines.append(f"- ... {len(report['failures']) - 80} more")
    if not report["failures"]:
        lines.append("- None")
    lines.extend(["", "## Suspicious Walls", ""])
    for wall in report["suspicious_walls"][:80]:
        lines.append(f"- `{wall['band']}` center `{wall['center']}` size `{wall['size']}`")
    if len(report["suspicious_walls"]) > 80:
        lines.append(f"- ... {len(report['suspicious_walls']) - 80} more")
    if not report["suspicious_walls"]:
        lines.append("- None")
    lines.extend(["", "## Intrusive Walls", ""])
    for wall in report["intrusive_walls"][:80]:
        lines.append(f"- `{wall['band']}` center `{wall['center']}` size `{wall['size']}` samples `{wall['first_intrusive_samples']}`")
    if len(report["intrusive_walls"]) > 80:
        lines.append(f"- ... {len(report['intrusive_walls']) - 80} more")
    if not report["intrusive_walls"]:
        lines.append("- None")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_svg(report)


def write_svg(report: dict) -> None:
    traversal = load_json(TRAVERSAL_PATH)
    enclosure = load_json(ENCLOSURE_PATH)
    width = 900
    height = 1200
    x_min, x_max = -16.0, 16.0
    z_min, z_max = -70.0, 76.0

    def sx(x: float) -> float:
        return (x - x_min) / (x_max - x_min) * width

    def sz(z: float) -> float:
        return height - (z - z_min) / (z_max - z_min) * height

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#101318"/>',
        '<g fill="none" stroke-linejoin="round">',
    ]
    for surface in traversal.get("surfaces", []):
        bounds = floor_bounds(surface)
        if bounds is None:
            continue
        x0, x1, z0, z1, _y = bounds
        parts.append(
            f'<rect x="{sx(x0):.2f}" y="{sz(z1):.2f}" width="{sx(x1)-sx(x0):.2f}" height="{sz(z0)-sz(z1):.2f}" fill="#d6a93a" fill-opacity="0.22" stroke="#d6a93a" stroke-width="1"/>'
        )
    for band in enclosure.get("bands", []):
        if band.get("type") not in {"side_wall", "end_wall"}:
            continue
        x0, x1, _y0, _y1, z0, z1 = band_bounds(band)
        parts.append(
            f'<rect x="{sx(x0):.2f}" y="{sz(z1):.2f}" width="{sx(x1)-sx(x0):.2f}" height="{sz(z0)-sz(z1):.2f}" fill="#5f8edb" fill-opacity="0.25" stroke="#8fb2ff" stroke-width="0.8"/>'
        )
    for failure in report["failures"]:
        x, _y, z = failure["local_point"]
        parts.append(f'<circle cx="{sx(x):.2f}" cy="{sz(z):.2f}" r="4.2" fill="#ff3b30" stroke="#ffffff" stroke-width="0.8"/>')
    for wall in report["suspicious_walls"]:
        x, _y, z = wall["center"]
        parts.append(f'<circle cx="{sx(x):.2f}" cy="{sz(z):.2f}" r="5.0" fill="none" stroke="#ffcc00" stroke-width="2.2"/>')
    parts.extend(
        [
            "</g>",
            '<text x="18" y="30" fill="#f0f3f8" font-family="Arial" font-size="20">CargoCrane enclosure edge audit</text>',
            '<text x="18" y="56" fill="#ff6b5f" font-family="Arial" font-size="15">red = unguarded exposed-edge sample</text>',
            '<text x="18" y="78" fill="#ffcc00" font-family="Arial" font-size="15">yellow ring = suspicious/unanchored wall band</text>',
            "</svg>",
        ]
    )
    REPORT_SVG.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> int:
    report = audit()
    write_reports(report)
    print(f"{report['status']}: {report['failure_count']} unguarded samples, {report['suspicious_wall_count']} suspicious walls")
    print(f"Wrote {REPORT_MD.relative_to(ROOT)}")
    print(f"Wrote {REPORT_SVG.relative_to(ROOT)}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
