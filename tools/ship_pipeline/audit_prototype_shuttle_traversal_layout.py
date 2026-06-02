#!/usr/bin/env python3
"""Audit prototype shuttle traversal layout from exported collision contracts.

This is a static spatial audit. It is intentionally separate from the Godot
controller replay so it can identify route, clearance, and lip risks before a
human playtest or a runtime replay.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LAYOUT_PATH = ROOT / "assets/models/ship/prototype_shuttle/prototype_shuttle_collision_layout_report.json"
MARKERS_PATH = ROOT / "assets/models/ship/prototype_shuttle/prototype_shuttle_markers.json"
INTERIOR_CONTRACT_PATH = ROOT / "assets/source/blender/ships/prototype_shuttle/prototype_shuttle_interior_collision_contract.json"
REPORT_JSON_PATH = ROOT / "reports/ship_pipeline/prototype_shuttle_traversal_audit_report.json"
REPORT_MD_PATH = ROOT / "reports/ship_pipeline/prototype_shuttle_traversal_audit_report.md"
TOP_SVG_PATH = ROOT / "reports/ship_pipeline/prototype_shuttle_traversal_audit_top.svg"
SIDE_SVG_PATH = ROOT / "reports/ship_pipeline/prototype_shuttle_traversal_audit_side.svg"
LEFT_STAIR_WALKWAY_X_RANGE = (-2.75, -1.58)


@dataclass(frozen=True)
class Surface:
    id: str
    kind: str
    center: tuple[float, float, float] | None
    size: tuple[float, float, float] | None
    hinge: tuple[float, float, float] | None = None
    tip: tuple[float, float, float] | None = None
    width: float | None = None

    @property
    def x_min(self) -> float:
        if self.kind == "ramp_panel" and self.width is not None:
            x_center = self.center[0] if self.center is not None else 0.0
            return x_center - self.width * 0.5
        assert self.center is not None and self.size is not None
        return self.center[0] - self.size[0] * 0.5

    @property
    def x_max(self) -> float:
        if self.kind == "ramp_panel" and self.width is not None:
            x_center = self.center[0] if self.center is not None else 0.0
            return x_center + self.width * 0.5
        assert self.center is not None and self.size is not None
        return self.center[0] + self.size[0] * 0.5

    @property
    def z_min(self) -> float:
        if self.kind == "ramp_panel" and self.hinge is not None and self.tip is not None:
            return min(self.hinge[2], self.tip[2])
        assert self.center is not None and self.size is not None
        return self.center[2] - self.size[2] * 0.5

    @property
    def z_max(self) -> float:
        if self.kind == "ramp_panel" and self.hinge is not None and self.tip is not None:
            return max(self.hinge[2], self.tip[2])
        assert self.center is not None and self.size is not None
        return self.center[2] + self.size[2] * 0.5

    @property
    def y_top(self) -> float:
        if self.kind == "ramp_panel" and self.hinge is not None:
            return self.hinge[1]
        assert self.center is not None and self.size is not None
        return self.center[1] + self.size[1] * 0.5

    def y_at_z(self, z: float) -> float:
        if self.kind != "ramp_panel":
            return self.y_top
        assert self.hinge is not None and self.tip is not None
        dz = self.hinge[2] - self.tip[2]
        if abs(dz) < 0.0001:
            return self.hinge[1]
        t = (z - self.tip[2]) / dz
        t = max(0.0, min(1.0, t))
        return self.tip[1] + (self.hinge[1] - self.tip[1]) * t

    def sample_center(self) -> tuple[float, float, float]:
        if self.kind == "ramp_panel":
            assert self.hinge is not None and self.tip is not None
            z = (self.hinge[2] + self.tip[2]) * 0.5
            x = self.center[0] if self.center is not None else 0.0
            return (x, self.y_at_z(z), z)
        assert self.center is not None
        return (self.center[0], self.y_top, self.center[2])


@dataclass(frozen=True)
class Region:
    id: str
    surface: str
    center: tuple[float, float, float]
    size: tuple[float, float, float]

    @property
    def x_min(self) -> float:
        return self.center[0] - self.size[0] * 0.5

    @property
    def x_max(self) -> float:
        return self.center[0] + self.size[0] * 0.5

    @property
    def y_min(self) -> float:
        return self.center[1] - self.size[1] * 0.5

    @property
    def y_max(self) -> float:
        return self.center[1] + self.size[1] * 0.5

    @property
    def z_min(self) -> float:
        return self.center[2] - self.size[2] * 0.5

    @property
    def z_max(self) -> float:
        return self.center[2] + self.size[2] * 0.5


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def vec3(values: list[float] | tuple[float, ...]) -> tuple[float, float, float]:
    return (float(values[0]), float(values[1]), float(values[2]))


def load_surfaces(path: Path) -> dict[str, Surface]:
    data = read_json(path)
    surfaces: dict[str, Surface] = {}
    for item in data.get("surfaces", []):
        surface = Surface(
            id=item["id"],
            kind=item.get("kind", ""),
            center=vec3(item["center"]) if "center" in item else None,
            size=vec3(item["size"]) if "size" in item else None,
            hinge=vec3(item["hinge"]) if "hinge" in item else None,
            tip=vec3(item["tip"]) if "tip" in item else None,
            width=float(item["width"]) if "width" in item else None,
        )
        surfaces[surface.id] = surface
    return surfaces


def load_regions(path: Path) -> list[Region]:
    data = read_json(path)
    regions: list[Region] = []
    for item in data.get("regions", []):
        if item.get("role") != "player_enclosure":
            continue
        if item.get("kind") != "box":
            continue
        regions.append(
            Region(
                id=item["id"],
                surface=item.get("surface", ""),
                center=vec3(item["center"]),
                size=vec3(item["size"]),
            )
        )
    return regions


def expanded_route(surfaces: dict[str, Surface]) -> list[str]:
    route = [
        "forward_belly_ramp",
        "cargo_forward_lower",
    ]
    if "left_smooth_stair_lane_runtime" in surfaces:
        route.append("left_smooth_stair_lane_runtime")
    else:
        route.extend(f"left_stair_{index:02d}" for index in range(9, -1, -1))
    route.extend(
        [
            "cockpit_entry_landing",
            "cockpit_entry_landing_aft_extension",
            "cockpit_floor",
        ]
    )
    return [surface_id for surface_id in route if surface_id in surfaces]


def add_derived_runtime_surfaces(surfaces: dict[str, Surface]) -> None:
    bottom = surfaces.get("left_stair_09")
    top = surfaces.get("left_stair_00")
    landing = surfaces.get("cockpit_entry_landing")
    if bottom is None or top is None or bottom.center is None or top.center is None or bottom.size is None or top.size is None:
        return

    width = LEFT_STAIR_WALKWAY_X_RANGE[1] - LEFT_STAIR_WALKWAY_X_RANGE[0]
    x_center = (LEFT_STAIR_WALKWAY_X_RANGE[0] + LEFT_STAIR_WALKWAY_X_RANGE[1]) * 0.5
    bottom_z = bottom.center[2] + bottom.size[2] * 0.5
    top_z = top.center[2] - top.size[2] * 0.5
    bottom_y = bottom.y_top + 0.01
    top_y = top.y_top + 0.01
    if landing is not None and landing.center is not None and landing.size is not None:
        top_y = landing.y_top + 0.01
        top_z = landing.z_max - 0.05
    surfaces["left_smooth_stair_lane_runtime"] = Surface(
        id="left_smooth_stair_lane_runtime",
        kind="ramp_panel",
        center=(x_center, 0.0, 0.0),
        size=None,
        hinge=(x_center, top_y, top_z),
        tip=(x_center, bottom_y, bottom_z),
        width=width,
    )


def apply_uniform_runtime_stair_heights(surfaces: dict[str, Surface]) -> None:
    cargo = surfaces.get("cargo_forward_lower")
    landing = surfaces.get("cockpit_entry_landing")
    if (
        cargo is None
        or landing is None
        or cargo.center is None
        or cargo.size is None
        or landing.center is None
        or landing.size is None
    ):
        return

    cargo_top = cargo.y_top
    landing_top = landing.y_top
    step_count = 10
    for index in range(step_count):
        rank_from_bottom = step_count - index
        top_y = cargo_top + (landing_top - cargo_top) * rank_from_bottom / (step_count + 1)
        for side in ("left", "right"):
            surface_id = f"{side}_stair_{index:02d}"
            surface = surfaces.get(surface_id)
            if surface is None or surface.center is None or surface.size is None:
                continue

            center = (surface.center[0], top_y - surface.size[1] * 0.5, surface.center[2])
            surfaces[surface_id] = Surface(
                id=surface.id,
                kind=surface.kind,
                center=center,
                size=surface.size,
                hinge=surface.hinge,
                tip=surface.tip,
                width=surface.width,
            )

    extension = surfaces.get("cockpit_entry_landing_aft_extension")
    if extension is not None and extension.center is not None and extension.size is not None and landing.size is not None:
        surfaces["cockpit_entry_landing_aft_extension"] = Surface(
            id=extension.id,
            kind=extension.kind,
            center=(0.0, landing_top - extension.size[1] * 0.5, extension.center[2]),
            size=(min(landing.size[0], 3.1), extension.size[1], extension.size[2]),
            hinge=extension.hinge,
            tip=extension.tip,
            width=extension.width,
        )


def interval_overlap(a_min: float, a_max: float, b_min: float, b_max: float) -> float:
    return max(0.0, min(a_max, b_max) - max(a_min, b_min))


def transition_report(
    a: Surface,
    b: Surface,
    player_radius: float,
    max_step: float,
    helper_step: float,
    minimum_overlap: float,
) -> dict[str, Any]:
    x_overlap = interval_overlap(a.x_min, a.x_max, b.x_min, b.x_max)
    z_overlap = interval_overlap(a.z_min, a.z_max, b.z_min, b.z_max)
    z_gap = max(0.0, max(a.z_min, b.z_min) - min(a.z_max, b.z_max))
    seam_z = max(min(a.z_max, b.z_max), min(max(a.z_min, b.z_min), (a.z_max + b.z_min) * 0.5))
    a_y = a.y_at_z(seam_z)
    b_y = b.y_at_z(seam_z)
    vertical_delta = b_y - a_y
    helper_required = abs(vertical_delta) > max_step

    reasons: list[str] = []
    status = "PASS"
    if x_overlap < player_radius * 2.0 + minimum_overlap:
        status = "FAIL"
        reasons.append("insufficient lateral overlap for player capsule")
    is_stair_pair = "_stair_" in a.id and "_stair_" in b.id
    is_abutting_panel = z_gap <= 0.08
    if z_overlap < minimum_overlap and a.kind != "ramp_panel" and b.kind != "ramp_panel":
        if is_abutting_panel and abs(vertical_delta) <= 0.05:
            pass
        elif is_stair_pair or is_abutting_panel:
            status = "WARN" if status != "FAIL" else status
            reasons.append("low route-depth overlap; relies on stepable adjacency")
        else:
            status = "FAIL"
            reasons.append("insufficient route-depth overlap between adjacent surfaces")
    if abs(vertical_delta) > helper_step:
        status = "FAIL"
        reasons.append("vertical delta exceeds helper budget")
    elif abs(vertical_delta) > max_step:
        status = "WARN" if status != "FAIL" else status
        reasons.append("vertical helper expected")
    elif abs(vertical_delta) > max_step * 0.5:
        status = "WARN" if status != "FAIL" else status
        reasons.append("noticeable lip or step")

    return {
        "from": a.id,
        "to": b.id,
        "status": status,
        "x_overlap": round(x_overlap, 4),
        "z_overlap": round(z_overlap, 4),
        "z_gap": round(z_gap, 4),
        "vertical_delta": round(vertical_delta, 4),
        "helper_required": helper_required,
        "reasons": reasons,
    }


def ceiling_clearance(sample: tuple[float, float, float], regions: list[Region], player_height: float) -> dict[str, Any]:
    x, floor_y, z = sample
    candidates = [
        region
        for region in regions
        if region.surface in {"ceiling", "canopy", "bulkhead"}
        and region.x_min <= x <= region.x_max
        and region.z_min <= z <= region.z_max
        and region.y_min > floor_y
    ]
    if not candidates:
        return {
            "status": "WARN",
            "clearance": None,
            "ceiling": None,
            "reason": "no nearby ceiling/enclosure region found above sample",
        }
    ceiling = min(candidates, key=lambda region: region.y_min)
    clearance = ceiling.y_min - floor_y
    if clearance < player_height:
        status = "FAIL"
        reason = "head clearance below player capsule height"
    elif clearance < player_height + 0.25:
        status = "WARN"
        reason = "tight head clearance"
    else:
        status = "PASS"
        reason = ""
    return {
        "status": status,
        "clearance": round(clearance, 4),
        "ceiling": ceiling.id,
        "reason": reason,
    }


def lateral_clearance(sample: tuple[float, float, float], regions: list[Region], player_radius: float) -> dict[str, Any]:
    x, floor_y, z = sample
    blockers = [
        region
        for region in regions
        if region.surface in {"wall", "door_frame", "guard"}
        and region.z_min <= z <= region.z_max
        and region.y_min <= floor_y + 1.2 <= region.y_max
    ]
    left = [region for region in blockers if region.center[0] < x]
    right = [region for region in blockers if region.center[0] > x]
    if not left or not right:
        return {
            "status": "WARN",
            "clearance": None,
            "left": left[-1].id if left else None,
            "right": right[0].id if right else None,
            "reason": "no paired lateral enclosure found at sample",
        }
    left_wall = max(left, key=lambda region: region.x_max)
    right_wall = min(right, key=lambda region: region.x_min)
    width = right_wall.x_min - left_wall.x_max
    comfortable = player_radius * 2.0 + 0.35
    minimum = player_radius * 2.0 + 0.12
    if width < minimum:
        status = "FAIL"
        reason = "lateral corridor width below capsule clearance"
    elif width < comfortable:
        status = "WARN"
        reason = "narrow lateral clearance; likely playable but tight"
    elif width < comfortable + 0.35:
        status = "WARN"
        reason = "tight lateral clearance"
    else:
        status = "PASS"
        reason = ""
    return {
        "status": status,
        "clearance": round(width, 4),
        "left": left_wall.id,
        "right": right_wall.id,
        "reason": reason,
    }


def sample_surfaces(route: list[str], surfaces: dict[str, Surface], regions: list[Region], player_height: float, player_radius: float) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for surface_id in route:
        surface = surfaces[surface_id]
        points = []
        if surface.kind == "ramp_panel":
            assert surface.tip is not None and surface.hinge is not None
            x = surface.center[0] if surface.center is not None else 0.0
            for t in (0.15, 0.5, 0.85):
                z = surface.tip[2] + (surface.hinge[2] - surface.tip[2]) * t
                points.append((x, surface.y_at_z(z), z))
        else:
            points.append(surface.sample_center())
        for index, point in enumerate(points):
            head = ceiling_clearance(point, regions, player_height)
            lateral = lateral_clearance(point, regions, player_radius)
            support = support_width(surface, player_radius)
            statuses = [head["status"], lateral["status"], support["status"]]
            status = "FAIL" if "FAIL" in statuses else "WARN" if "WARN" in statuses else "PASS"
            samples.append(
                {
                    "surface": surface_id,
                    "sample": index,
                    "status": status,
                    "position": [round(point[0], 4), round(point[1], 4), round(point[2], 4)],
                    "head_clearance": head,
                    "lateral_clearance": lateral,
                    "support_width": support,
                }
            )
    return samples


def support_width(surface: Surface, player_radius: float) -> dict[str, Any]:
    width = surface.x_max - surface.x_min
    minimum = player_radius * 2.0 + 0.12
    comfortable = player_radius * 2.0 + 0.50
    if width < minimum:
        status = "FAIL"
        reason = "walkable support narrower than capsule minimum"
    elif width < comfortable:
        status = "WARN"
        reason = "walkable support is narrow for comfortable traversal"
    else:
        status = "PASS"
        reason = ""
    return {
        "status": status,
        "width": round(width, 4),
        "reason": reason,
    }


def status_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for item in items:
        counts[item.get("status", "WARN")] = counts.get(item.get("status", "WARN"), 0) + 1
    return counts


def overall_status(transitions: list[dict[str, Any]], samples: list[dict[str, Any]], missing: list[str]) -> str:
    if missing:
        return "FAIL"
    if any(item["status"] == "FAIL" for item in transitions + samples):
        return "FAIL"
    if any(item["status"] == "WARN" for item in transitions + samples):
        return "WARN"
    return "PASS"


def svg_scale(points: list[tuple[float, float]], width: int, height: int, padding: int = 24):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(0.001, max_x - min_x)
    span_y = max(0.001, max_y - min_y)

    def map_point(x: float, y: float) -> tuple[float, float]:
        px = padding + (x - min_x) / span_x * (width - padding * 2)
        py = height - padding - (y - min_y) / span_y * (height - padding * 2)
        return px, py

    return map_point


def color(status: str) -> str:
    return {"PASS": "#2fb344", "WARN": "#f59f00", "FAIL": "#e03131"}.get(status, "#868e96")


def write_top_svg(path: Path, route: list[str], surfaces: dict[str, Surface], samples: list[dict[str, Any]]) -> None:
    points: list[tuple[float, float]] = []
    for surface_id in route:
        s = surfaces[surface_id]
        points.extend([(s.x_min, s.z_min), (s.x_max, s.z_max)])
    for sample in samples:
        x, _, z = sample["position"]
        points.append((x, z))
    mapper = svg_scale(points, 1100, 760)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="760" viewBox="0 0 1100 760">']
    parts.append('<rect width="1100" height="760" fill="#101418"/>')
    parts.append('<text x="24" y="32" fill="#f8f9fa" font-family="monospace" font-size="18">Prototype Shuttle Traversal Audit: Top X/Z</text>')
    for surface_id in route:
        s = surfaces[surface_id]
        x1, y1 = mapper(s.x_min, s.z_min)
        x2, y2 = mapper(s.x_max, s.z_max)
        parts.append(f'<rect x="{min(x1,x2):.1f}" y="{min(y1,y2):.1f}" width="{abs(x2-x1):.1f}" height="{abs(y2-y1):.1f}" fill="#4dabf766" stroke="#74c0fc" stroke-width="1"/>')
        cx, cy = mapper((s.x_min + s.x_max) * 0.5, (s.z_min + s.z_max) * 0.5)
        parts.append(f'<text x="{cx+4:.1f}" y="{cy:.1f}" fill="#d0ebff" font-family="monospace" font-size="10">{surface_id}</text>')
    for sample in samples:
        x, _, z = sample["position"]
        px, py = mapper(x, z)
        parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="7" fill="{color(sample["status"])}" stroke="#ffffff" stroke-width="1"/>')
    parts.append("</svg>")
    path.write_text("\n".join(parts))


def write_side_svg(path: Path, route: list[str], surfaces: dict[str, Surface], samples: list[dict[str, Any]]) -> None:
    points: list[tuple[float, float]] = []
    for surface_id in route:
        s = surfaces[surface_id]
        points.extend([(s.z_min, s.y_at_z(s.z_min)), (s.z_max, s.y_at_z(s.z_max))])
    for sample in samples:
        _, y, z = sample["position"]
        points.append((z, y))
        clearance = sample["head_clearance"].get("clearance")
        if clearance is not None:
            points.append((z, y + clearance))
    mapper = svg_scale(points, 1100, 680)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="680" viewBox="0 0 1100 680">']
    parts.append('<rect width="1100" height="680" fill="#101418"/>')
    parts.append('<text x="24" y="32" fill="#f8f9fa" font-family="monospace" font-size="18">Prototype Shuttle Traversal Audit: Side Z/Y</text>')
    for surface_id in route:
        s = surfaces[surface_id]
        x1, y1 = mapper(s.z_min, s.y_at_z(s.z_min))
        x2, y2 = mapper(s.z_max, s.y_at_z(s.z_max))
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#74c0fc" stroke-width="5" stroke-linecap="round"/>')
    for sample in samples:
        _, y, z = sample["position"]
        px, py = mapper(z, y)
        parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="7" fill="{color(sample["status"])}" stroke="#ffffff" stroke-width="1"/>')
        clearance = sample["head_clearance"].get("clearance")
        if clearance is not None:
            hx, hy = mapper(z, y + clearance)
            parts.append(f'<line x1="{px:.1f}" y1="{py:.1f}" x2="{hx:.1f}" y2="{hy:.1f}" stroke="{color(sample["head_clearance"]["status"])}" stroke-width="2" stroke-dasharray="4 4"/>')
    parts.append("</svg>")
    path.write_text("\n".join(parts))


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Prototype Shuttle Traversal Layout Audit",
        "",
        f"Status: **{report['status']}**",
        "",
        "## Summary",
        "",
        f"- Route surfaces: {len(report['route'])}",
        f"- Missing required surfaces: {len(report['missing_surfaces'])}",
        f"- Transition counts: {report['transition_counts']}",
        f"- Sample counts: {report['sample_counts']}",
        f"- Helper-required transitions: {report['helper_required_count']}",
        "",
    ]
    if report["blocking_issues"]:
        lines.extend(["## Blocking Issues", ""])
        lines.extend(f"- {issue}" for issue in report["blocking_issues"])
        lines.append("")
    if report["warnings"]:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report["warnings"][:30])
        lines.append("")
    lines.extend(["## Route Transitions", ""])
    for item in report["transitions"]:
        reason = "; ".join(item["reasons"]) if item["reasons"] else "ok"
        lines.append(
            f"- **{item['status']}** `{item['from']}` -> `{item['to']}`: "
            f"delta={item['vertical_delta']}m, x_overlap={item['x_overlap']}m, z_overlap={item['z_overlap']}m, {reason}"
        )
    lines.extend(["", "## Route Samples", ""])
    for item in report["samples"]:
        head = item["head_clearance"]
        lateral = item["lateral_clearance"]
        support = item["support_width"]
        lines.append(
            f"- **{item['status']}** `{item['surface']}` sample {item['sample']} at {item['position']}: "
            f"head={head.get('clearance')} via {head.get('ceiling')}, lateral={lateral.get('clearance')}, support_width={support.get('width')}"
        )
    lines.append("")
    path.write_text("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--layout", type=Path, default=LAYOUT_PATH)
    parser.add_argument("--markers", type=Path, default=MARKERS_PATH)
    parser.add_argument("--interior-contract", type=Path, default=INTERIOR_CONTRACT_PATH)
    parser.add_argument("--report-json", type=Path, default=REPORT_JSON_PATH)
    parser.add_argument("--report-md", type=Path, default=REPORT_MD_PATH)
    parser.add_argument("--top-svg", type=Path, default=TOP_SVG_PATH)
    parser.add_argument("--side-svg", type=Path, default=SIDE_SVG_PATH)
    parser.add_argument("--player-height", type=float, default=1.8)
    parser.add_argument("--player-radius", type=float, default=0.35)
    parser.add_argument("--base-step-height", type=float, default=0.48)
    parser.add_argument("--helper-step-height", type=float, default=0.72)
    parser.add_argument("--minimum-overlap", type=float, default=0.24)
    args = parser.parse_args()

    surfaces = load_surfaces(args.layout)
    apply_uniform_runtime_stair_heights(surfaces)
    regions = load_regions(args.interior_contract)
    route = expanded_route(surfaces)
    required = [
        "forward_belly_ramp",
        "cargo_forward_lower",
        "left_stair_09",
        "left_stair_00",
        "cockpit_entry_landing",
        "cockpit_floor",
    ]
    missing = [surface_id for surface_id in required if surface_id not in surfaces]
    transitions = [
        transition_report(surfaces[a], surfaces[b], args.player_radius, args.base_step_height, args.helper_step_height, args.minimum_overlap)
        for a, b in zip(route, route[1:])
    ]
    samples = sample_surfaces(route, surfaces, regions, args.player_height, args.player_radius)

    blocking = []
    warnings = []
    for surface_id in missing:
        blocking.append(f"missing required route surface `{surface_id}`")
    for transition in transitions:
        text = f"{transition['from']} -> {transition['to']}: {', '.join(transition['reasons']) or 'ok'}"
        if transition["status"] == "FAIL":
            blocking.append(text)
        elif transition["status"] == "WARN":
            warnings.append(text)
    for sample in samples:
        text = f"{sample['surface']} sample {sample['sample']}: {sample['head_clearance'].get('reason') or sample['lateral_clearance'].get('reason') or sample['support_width'].get('reason')}"
        if sample["status"] == "FAIL":
            blocking.append(text)
        elif sample["status"] == "WARN":
            warnings.append(text)

    report = {
        "schema_version": 1,
        "status": overall_status(transitions, samples, missing),
        "layout_path": str(args.layout.relative_to(ROOT)),
        "interior_contract_path": str(args.interior_contract.relative_to(ROOT)),
        "route": route,
        "missing_surfaces": missing,
        "transition_counts": status_counts(transitions),
        "sample_counts": status_counts(samples),
        "helper_required_count": sum(1 for transition in transitions if transition["helper_required"]),
        "blocking_issues": blocking,
        "warnings": warnings,
        "transitions": transitions,
        "samples": samples,
        "evidence": {
            "top_svg": str(args.top_svg.relative_to(ROOT)),
            "side_svg": str(args.side_svg.relative_to(ROOT)),
        },
    }

    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.write_text(json.dumps(report, indent=2))
    write_markdown(args.report_md, report)
    write_top_svg(args.top_svg, route, surfaces, samples)
    write_side_svg(args.side_svg, route, surfaces, samples)

    print(f"Prototype shuttle traversal layout audit: {report['status']}")
    print(f"Report: {args.report_md}")
    print(f"Top evidence: {args.top_svg}")
    print(f"Side evidence: {args.side_svg}")
    return 0 if report["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
