#!/usr/bin/env python3
"""Voxel flood-fill leak audit for CargoCrane enclosure.

This treats generated traversal/enclosure bands as solid blockers, seeds the
known playable interior with "water", and reports every connected escape to the
outside review boundary except the four approved side entry paths.
"""

from __future__ import annotations

import json
import math
from collections import deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "assets/source/blender/ships/cargo_crane/cargo_crane_interior_layout_contract.json"
TRAVERSAL_PATH = ROOT / "assets/models/ship/cargo_crane/cargo_crane_traversal_surfaces.json"
ENCLOSURE_PATH = ROOT / "assets/models/ship/cargo_crane/cargo_crane_enclosure_bands.json"
REPORT_DIR = ROOT / "reports/ship_pipeline/cargo_crane_enclosure_leak_audit"
REPORT_JSON = REPORT_DIR / "cargo_crane_enclosure_leak_audit.json"
REPORT_MD = REPORT_DIR / "cargo_crane_enclosure_leak_audit.md"
REPORT_SVG = REPORT_DIR / "cargo_crane_enclosure_leak_audit_current.svg"

VOXEL = 0.5
BOUNDS_MIN = (-18.0, -12.0, -68.0)
BOUNDS_MAX = (18.0, 10.0, 76.0)
FLOOD_NEIGHBORS = (
    ((1, 0, 0), "+x"),
    ((-1, 0, 0), "-x"),
    ((0, 1, 0), "+y"),
    ((0, -1, 0), "-y"),
    ((0, 0, 1), "+z"),
    ((0, 0, -1), "-z"),
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dims() -> tuple[int, int, int]:
    return tuple(int(round((BOUNDS_MAX[i] - BOUNDS_MIN[i]) / VOXEL)) + 1 for i in range(3))  # type: ignore[return-value]


def to_index(point: tuple[float, float, float] | list[float]) -> tuple[int, int, int]:
    return tuple(int(round((point[i] - BOUNDS_MIN[i]) / VOXEL)) for i in range(3))  # type: ignore[return-value]


def to_world(index: tuple[int, int, int]) -> tuple[float, float, float]:
    return tuple(BOUNDS_MIN[i] + index[i] * VOXEL for i in range(3))  # type: ignore[return-value]


def in_bounds(index: tuple[int, int, int], d: tuple[int, int, int]) -> bool:
    return all(0 <= index[i] < d[i] for i in range(3))


def box_bounds(center: list[float], size: list[float], pad: float = 0.0) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    bmin = [center[i] - size[i] * 0.5 - pad for i in range(3)]
    bmax = [center[i] + size[i] * 0.5 + pad for i in range(3)]
    return to_index(bmin), to_index(bmax)


def rotated_aabb_size(size: list[float], rotation_degrees: list[float] | None) -> list[float]:
    if not rotation_degrees:
        return size

    rx = math.radians(float(rotation_degrees[0]))
    ry = math.radians(float(rotation_degrees[1])) if len(rotation_degrees) > 1 else 0.0
    rz = math.radians(float(rotation_degrees[2])) if len(rotation_degrees) > 2 else 0.0
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    matrix = (
        (cy * cz, cz * sx * sy - cx * sz, sx * sz + cx * cz * sy),
        (cy * sz, cx * cz + sx * sy * sz, cx * sy * sz - cz * sx),
        (-sy, cy * sx, cx * cy),
    )
    return [
        abs(matrix[axis][0]) * size[0] + abs(matrix[axis][1]) * size[1] + abs(matrix[axis][2]) * size[2]
        for axis in range(3)
    ]


def add_solid_box(solid: set[tuple[int, int, int]], center: list[float], size: list[float], pad: float = 0.0) -> None:
    imin, imax = box_bounds(center, size, pad)
    d = dims()
    for ix in range(max(0, imin[0]), min(d[0], imax[0] + 1)):
        for iy in range(max(0, imin[1]), min(d[1], imax[1] + 1)):
            for iz in range(max(0, imin[2]), min(d[2], imax[2] + 1)):
                solid.add((ix, iy, iz))


def add_segment_box(
    solid: set[tuple[int, int, int]],
    start: list[float],
    end: list[float],
    width: float,
    thickness: float,
    samples_per_meter: float = 4.0,
) -> None:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dz = end[2] - start[2]
    length = max(0.001, (dx * dx + dy * dy + dz * dz) ** 0.5)
    count = max(2, int(length * samples_per_meter))
    # Conservative AABB splats along the segment. This is deliberately slightly
    # thick so flood fill does not leak through diagonal sample cracks.
    for index in range(count + 1):
        t = index / count
        center = [start[axis] + (end[axis] - start[axis]) * t for axis in range(3)]
        add_solid_box(solid, center, [width, thickness + 0.35, width], pad=0.05)


def build_solid(traversal: dict, enclosure: dict) -> set[tuple[int, int, int]]:
    solid: set[tuple[int, int, int]] = set()
    for surface in traversal.get("surfaces", []):
        kind = surface.get("type")
        if kind in {"floor_box", "objective_floor_patch"}:
            add_solid_box(solid, surface["center"], surface["size"], pad=0.05)
        elif kind == "ramp":
            add_segment_box(solid, surface["start"], surface["end"], float(surface.get("width", 1.0)), float(surface.get("thickness", 0.24)))
        elif kind == "stair_path":
            points = surface.get("points", [])
            for start, end in zip(points, points[1:]):
                add_segment_box(solid, start, end, float(surface.get("width", 1.0)), float(surface.get("thickness", 0.24)))

    for band in enclosure.get("bands", []):
        add_solid_box(solid, band["center"], rotated_aabb_size(band["size"], band.get("rotation_degrees")), pad=0.05)
    return solid


def seed_points(traversal: dict) -> list[list[float]]:
    route = traversal.get("primary_route", [])
    seeds = []
    for point in route:
        seeds.append([point[0], point[1] + 1.1, point[2]])
    # Add off-center seeds so side rooms/edges participate in the same fill.
    for surface in traversal.get("surfaces", []):
        if surface.get("role") in {"entry_ramp", "entry_hatch_path"}:
            continue
        if surface.get("type") in {"floor_box", "objective_floor_patch"}:
            center = surface["center"]
            size = surface["size"]
            for sx in (-0.35, 0.0, 0.35):
                for sz in (-0.35, 0.0, 0.35):
                    seeds.append([center[0] + size[0] * sx, center[1] + 1.1, center[2] + size[2] * sz])
    return seeds


def is_boundary(index: tuple[int, int, int], d: tuple[int, int, int]) -> bool:
    return any(index[i] == 0 or index[i] == d[i] - 1 for i in range(3))


def approved_entry_escape(point: tuple[float, float, float], direction: str, contract: dict) -> bool:
    x, y, z = point
    if direction not in {"+x", "-x"}:
        return False
    for entrance in contract.get("entrance_hatches", []):
        cx, _cy, cz = entrance["cut_center"]
        side = -1.0 if entrance["side"] == "port" else 1.0
        if side * x < 6.2:
            continue
        if abs(z - cz) <= 1.85 and -2.9 <= y <= 2.5:
            return True
    return False


def approved_internal_transition(point: tuple[float, float, float], direction: str, traversal: dict) -> bool:
    x, y, z = point
    if direction == "+y" and -3.6 <= x <= 3.6 and -3.35 <= y <= -2.65 and 64.0 <= z <= 72.6:
        return True
    for surface in traversal.get("surfaces", []):
        if surface.get("type") != "stair_path":
            continue
        points = surface.get("points", [])
        if direction in {"+x", "-x", "+z", "-z", "+y", "-y"} and inside_stairwell_transition(point, points, float(surface.get("width", 1.0))):
            return True
    if direction not in {"+z", "-z", "+y", "-y"}:
        return False
    for surface in traversal.get("surfaces", []):
        if surface.get("type") != "ramp" or surface.get("role") != "edge_to_edge_inter_region_connector":
            continue
        if direction in {"+z", "-z", "+y"} and inside_segment_domain(point, surface["start"], surface["end"], float(surface.get("width", 1.0))):
            return True
    return False


def flood_leaks(contract: dict, traversal: dict, solid: set[tuple[int, int, int]]) -> dict:
    d = dims()
    queue: deque[tuple[int, int, int]] = deque()
    visited: set[tuple[int, int, int]] = set()
    for seed in seed_points(traversal):
        index = to_index(seed)
        if in_bounds(index, d) and index not in solid and inside_interior_domain(to_world(index), contract, traversal):
            queue.append(index)
            visited.add(index)

    leak_cells = []
    approved_cells = []
    internal_transition_cells = []
    while queue:
        cell = queue.popleft()
        for delta, direction in FLOOD_NEIGHBORS:
            nxt = (cell[0] + delta[0], cell[1] + delta[1], cell[2] + delta[2])
            if not in_bounds(nxt, d):
                point = to_world(cell)
                if approved_entry_escape(point, direction, contract):
                    approved_cells.append(point)
                elif approved_internal_transition(point, direction, traversal):
                    internal_transition_cells.append(point)
                else:
                    leak_cells.append({"cell": cell, "point": point, "direction": direction})
                continue
            if nxt in visited or nxt in solid:
                continue
            world = to_world(nxt)
            if not inside_interior_domain(world, contract, traversal):
                point = to_world(cell)
                if approved_entry_escape(point, direction, contract):
                    approved_cells.append(world)
                elif approved_internal_transition(point, direction, traversal):
                    internal_transition_cells.append(point)
                else:
                    leak_cells.append({"cell": cell, "point": point, "direction": direction})
                continue
            visited.add(nxt)
            queue.append(nxt)

    return {
        "visited_count": len(visited),
        "raw_leak_count": len(leak_cells),
        "approved_escape_count": len(approved_cells),
        "approved_internal_transition_count": len(internal_transition_cells),
        "leak_clusters": cluster_leaks(leak_cells),
    }


def cluster_leaks(leaks: list[dict]) -> list[dict]:
    if not leaks:
        return []
    by_cell_direction: dict[tuple[tuple[int, int, int], str], tuple[float, float, float]] = {}
    cells_by_direction: dict[str, set[tuple[int, int, int]]] = {}
    for leak in leaks:
        cell = tuple(leak["cell"])
        direction = leak["direction"]
        by_cell_direction[(cell, direction)] = leak["point"]
        cells_by_direction.setdefault(direction, set()).add(cell)

    clusters = []
    for direction, cells in cells_by_direction.items():
        remaining = set(cells)
        while remaining:
            start = remaining.pop()
            stack = [start]
            component = [start]
            while stack:
                cell = stack.pop()
                for delta, _name in FLOOD_NEIGHBORS:
                    nxt = (cell[0] + delta[0], cell[1] + delta[1], cell[2] + delta[2])
                    if nxt in remaining:
                        remaining.remove(nxt)
                        stack.append(nxt)
                        component.append(nxt)
            items = [by_cell_direction[(cell, direction)] for cell in component]
            xs = [p[0] for p in items]
            ys = [p[1] for p in items]
            zs = [p[2] for p in items]
            clusters.append(
                {
                    "count": len(items),
                    "direction": direction,
                    "classification": classify_leak(direction, xs, ys, zs),
                    "center": [round(sum(xs) / len(xs), 3), round(sum(ys) / len(ys), 3), round(sum(zs) / len(zs), 3)],
                    "bounds": {
                        "min": [round(min(xs), 3), round(min(ys), 3), round(min(zs), 3)],
                        "max": [round(max(xs), 3), round(max(ys), 3), round(max(zs), 3)],
                    },
                }
            )
    return sorted(clusters, key=lambda c: c["count"], reverse=True)


def classify_leak(direction: str, xs: list[float], ys: list[float], zs: list[float]) -> str:
    center = (sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs))
    if direction == "+y":
        return "missing_ceiling_or_upper_cap"
    if direction == "-y":
        return "floor_void_or_lower_opening"
    if direction in {"+x", "-x"}:
        if -24.0 <= center[2] <= 22.0:
            return "side_wall_or_hatch_opening"
        return "side_wall_gap"
    if direction in {"+z", "-z"}:
        return "end_cap_or_connector_seam"
    return "unknown"


def inside_interior_domain(point: tuple[float, float, float], contract: dict, traversal: dict) -> bool:
    x, y, z = point
    for region in contract.get("semantic_regions", []):
        bmin = region["bounds"]["min"]
        bmax = region["bounds"]["max"]
        if bmin[0] - 0.35 <= x <= bmax[0] + 0.35 and bmin[1] - 0.25 <= y <= bmax[1] + 0.35 and bmin[2] - 0.35 <= z <= bmax[2] + 0.35:
            return True
    for surface in traversal.get("surfaces", []):
        if inside_surface_domain(point, surface):
            return True
    return False


def inside_surface_domain(point: tuple[float, float, float], surface: dict) -> bool:
    x, y, z = point
    if surface.get("role") in {"entry_ramp", "entry_hatch_path"}:
        return False
    kind = surface.get("type")
    if kind in {"floor_box", "objective_floor_patch"}:
        center = surface["center"]
        size = surface["size"]
        return (
            center[0] - size[0] * 0.5 - 0.35 <= x <= center[0] + size[0] * 0.5 + 0.35
            and center[1] - 0.35 <= y <= center[1] + 3.0
            and center[2] - size[2] * 0.5 - 0.35 <= z <= center[2] + size[2] * 0.5 + 0.35
        )
    if kind == "ramp":
        return inside_segment_domain(point, surface["start"], surface["end"], float(surface.get("width", 1.0)))
    if kind == "stair_path":
        points = surface.get("points", [])
        return inside_stairwell_domain(point, points, float(surface.get("width", 1.0)))
    return False


def inside_segment_domain(point: tuple[float, float, float], start: list[float], end: list[float], width: float) -> bool:
    x, y, z = point
    ax, ay, az = start
    bx, by, bz = end
    dx, dy, dz = bx - ax, by - ay, bz - az
    horizontal_len = max(0.0001, (dx * dx + dz * dz) ** 0.5)
    ux, uz = dx / horizontal_len, dz / horizontal_len
    along = (x - ax) * ux + (z - az) * uz
    lateral = abs((x - ax) * -uz + (z - az) * ux)
    t = max(0.0, min(1.0, along / horizontal_len))
    cy = ay + dy * t
    return (
        -0.45 <= along <= horizontal_len + 0.45
        and lateral <= width * 0.5 + 0.45
        and cy - 0.35 <= y <= cy + 3.0
    )


def inside_stairwell_domain(point: tuple[float, float, float], points: list[list[float]], width: float) -> bool:
    if len(points) < 2:
        return False
    x, y, z = point
    for start, end in zip(points, points[1:]):
        ax, _ay, az = start
        bx, _by, bz = end
        dx, dz = bx - ax, bz - az
        horizontal_len = max(0.0001, (dx * dx + dz * dz) ** 0.5)
        ux, uz = dx / horizontal_len, dz / horizontal_len
        along = (x - ax) * ux + (z - az) * uz
        lateral = abs((x - ax) * -uz + (z - az) * ux)
        t = max(0.0, min(1.0, along / horizontal_len))
        cy = start[1] + (end[1] - start[1]) * t
        if (
            -0.45 <= along <= horizontal_len + 0.45
            and lateral <= width * 0.5 + 0.45
            and cy - 0.35 <= y <= cy + 4.8
        ):
            return True
    return False


def inside_stairwell_transition(point: tuple[float, float, float], points: list[list[float]], width: float) -> bool:
    if len(points) < 2:
        return False
    x, y, z = point
    if y < min(p[1] for p in points) - 0.35 or y > max(p[1] for p in points) + 1.0:
        return False
    for start, end in zip(points, points[1:]):
        ax, _ay, az = start
        bx, _by, bz = end
        dx, dz = bx - ax, bz - az
        horizontal_len = max(0.0001, (dx * dx + dz * dz) ** 0.5)
        ux, uz = dx / horizontal_len, dz / horizontal_len
        along = (x - ax) * ux + (z - az) * uz
        lateral = abs((x - ax) * -uz + (z - az) * ux)
        if -0.8 <= along <= horizontal_len + 1.4 and lateral <= width * 0.5 + 0.55:
            return True
    return False


def write_reports(report: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# CargoCrane Enclosure Leak Audit",
        "",
        f"Status: **{report['status']}**",
        "",
        f"- Visited water voxels: `{report['visited_count']}`",
        f"- Raw leak boundary cells: `{report['raw_leak_count']}`",
        f"- Approved entry escape cells: `{report['approved_escape_count']}`",
        f"- Approved internal transition cells: `{report['approved_internal_transition_count']}`",
        f"- Leak clusters: `{len(report['leak_clusters'])}`",
        f"- Projection: `{REPORT_SVG.relative_to(ROOT)}`",
        "",
        "## Leak Clusters",
        "",
    ]
    if report["leak_clusters"]:
        for cluster in report["leak_clusters"][:80]:
            lines.append(
                f"- count `{cluster['count']}` dir `{cluster['direction']}` "
                f"class `{cluster['classification']}` center `{cluster['center']}` bounds `{cluster['bounds']}`"
            )
    else:
        lines.append("- None")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_svg(report)


def write_svg(report: dict) -> None:
    width = 900
    height = 1200
    x_min, x_max = BOUNDS_MIN[0], BOUNDS_MAX[0]
    z_min, z_max = BOUNDS_MIN[2], BOUNDS_MAX[2]

    def sx(x: float) -> float:
        return (x - x_min) / (x_max - x_min) * width

    def sz(z: float) -> float:
        return height - (z - z_min) / (z_max - z_min) * height

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#101318"/>',
        '<text x="18" y="30" fill="#f0f3f8" font-family="Arial" font-size="20">CargoCrane voxel water leak audit</text>',
        '<text x="18" y="56" fill="#ff4f4f" font-family="Arial" font-size="15">red = unapproved water escape cluster; label = escape direction</text>',
    ]
    for cluster in report["leak_clusters"]:
        x, _y, z = cluster["center"]
        radius = max(4.0, min(18.0, cluster["count"] ** 0.5 * 1.7))
        parts.append(f'<circle cx="{sx(x):.2f}" cy="{sz(z):.2f}" r="{radius:.2f}" fill="#ff3b30" fill-opacity="0.65" stroke="#ffffff" stroke-width="0.8"/>')
        parts.append(f'<text x="{sx(x) + radius + 2:.2f}" y="{sz(z) + 4:.2f}" fill="#ffffff" font-family="Arial" font-size="11">{cluster["direction"]}</text>')
    parts.append("</svg>")
    REPORT_SVG.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> int:
    contract = load_json(CONTRACT_PATH)
    traversal = load_json(TRAVERSAL_PATH)
    enclosure = load_json(ENCLOSURE_PATH)
    solid = build_solid(traversal, enclosure)
    report = flood_leaks(contract, traversal, solid)
    report.update(
        {
            "schema_version": 1,
            "ship_id": "cargo_crane",
            "voxel_size": VOXEL,
            "status": "PASS" if not report["leak_clusters"] else "FAIL",
            "solid_voxel_count": len(solid),
        }
    )
    write_reports(report)
    print(f"{report['status']}: {len(report['leak_clusters'])} leak cluster(s), {report['raw_leak_count']} raw leak cell(s)")
    print(f"Wrote {REPORT_MD.relative_to(ROOT)}")
    print(f"Wrote {REPORT_SVG.relative_to(ROOT)}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
