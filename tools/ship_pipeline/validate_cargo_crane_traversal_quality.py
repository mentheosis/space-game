#!/usr/bin/env python3
"""Static QC for CargoCrane traversal surface candidates."""

from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "assets/source/blender/ships/cargo_crane/cargo_crane_interior_layout_contract.json"
SURFACES_PATH = ROOT / "assets/models/ship/cargo_crane/cargo_crane_traversal_surfaces.json"
SURFACE_REPORT_PATH = ROOT / "reports/ship_pipeline/cargo_crane_voxel_fit/cargo_crane_traversal_surfaces_report.json"
VOXEL_REPORT_PATH = ROOT / "reports/ship_pipeline/cargo_crane_voxel_fit/cargo_crane_voxel_report.json"
REPORT_JSON = ROOT / "reports/ship_pipeline/cargo_crane_voxel_fit/cargo_crane_traversal_quality_report.json"
REPORT_MD = ROOT / "reports/ship_pipeline/cargo_crane_voxel_fit/cargo_crane_traversal_quality_report.md"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((a[index] - b[index]) ** 2 for index in range(3)))


def point_segment_distance(point: list[float], start: list[float], end: list[float]) -> float:
    ab = [end[index] - start[index] for index in range(3)]
    ap = [point[index] - start[index] for index in range(3)]
    denom = max(0.0001, sum(value * value for value in ab))
    t = max(0.0, min(1.0, sum(ap[index] * ab[index] for index in range(3)) / denom))
    closest = [start[index] + ab[index] * t for index in range(3)]
    return distance(point, closest)


def point_supported_by_surface(point: list[float], surface: dict, tolerance: float) -> bool:
    if surface["type"] == "floor_box":
        center = surface["center"]
        size = surface["size"]
        return (
            abs(point[0] - center[0]) <= size[0] * 0.5 + tolerance
            and abs(point[2] - center[2]) <= size[2] * 0.5 + tolerance
            and abs(point[1] - center[1]) <= 1.6
        )
    if surface["type"] == "ramp":
        return point_segment_distance(point, surface["start"], surface["end"]) <= surface["width"] * 0.5 + tolerance
    if surface["type"] == "stair_path":
        return any(
            point_segment_distance(point, start, end) <= surface["width"] * 0.5 + tolerance
            for start, end in zip(surface["points"], surface["points"][1:])
        )
    return False


def segment_grade(start: list[float], end: list[float]) -> float:
    horizontal = math.sqrt((end[0] - start[0]) ** 2 + (end[2] - start[2]) ** 2)
    if horizontal <= 0.0001:
        return float("inf")
    return abs(end[1] - start[1]) / horizontal


def validate() -> dict:
    contract = load_json(CONTRACT_PATH)
    traversal = load_json(SURFACES_PATH)
    surface_report = load_json(SURFACE_REPORT_PATH)
    voxel_report = load_json(VOXEL_REPORT_PATH)
    capsule = contract["player_capsule"]
    min_clear_width = capsule["radius"] * 2.0 + 0.45
    errors = []
    warnings = []

    if surface_report.get("status") != "PASS":
        errors.append({"check": "surface_feature_coverage", "status": surface_report.get("status")})
    if voxel_report.get("status") != "PASS":
        errors.append({"check": "voxel_semantic_connectivity", "status": voxel_report.get("status")})

    for surface in traversal["surfaces"]:
        surface_type = surface["type"]
        name = surface["name"]
        if surface_type == "floor_box":
            width = min(surface["size"][0], surface["size"][2])
            if width < min_clear_width:
                errors.append({"check": "floor_clear_width", "surface": name, "width": width, "required": min_clear_width})
        elif surface_type == "ramp":
            if surface["width"] < min_clear_width:
                errors.append({"check": "ramp_clear_width", "surface": name, "width": surface["width"], "required": min_clear_width})
            grade = segment_grade(surface["start"], surface["end"])
            if grade > 0.65:
                warnings.append({"check": "steep_ramp_grade", "surface": name, "grade": round(grade, 4)})
        elif surface_type == "stair_path":
            if surface["width"] < min_clear_width:
                errors.append({"check": "stair_clear_width", "surface": name, "width": surface["width"], "required": min_clear_width})
            for index, (start, end) in enumerate(zip(surface["points"], surface["points"][1:])):
                grade = segment_grade(start, end)
                if grade > 1.35:
                    warnings.append({"check": "steep_stair_segment", "surface": name, "segment": index, "grade": round(grade, 4)})

    checkpoint_reports = []
    for checkpoint in contract["player_traversal_validation"]["checkpoints"]:
        point = checkpoint["local_origin"]
        supported = any(point_supported_by_surface(point, surface, tolerance=1.6) for surface in traversal["surfaces"])
        checkpoint_reports.append({"name": checkpoint["name"], "local_origin": point, "supported": supported})
        if not supported:
            errors.append({"check": "checkpoint_support", "checkpoint": checkpoint["name"], "local_origin": point})

    route = traversal["primary_route"]
    route_segment_reports = []
    for index, (start, end) in enumerate(zip(route, route[1:])):
        supported_start = any(point_supported_by_surface(start, surface, tolerance=1.8) for surface in traversal["surfaces"])
        supported_end = any(point_supported_by_surface(end, surface, tolerance=1.8) for surface in traversal["surfaces"])
        gap = distance(start, end)
        route_segment_reports.append(
            {
                "index": index,
                "start": start,
                "end": end,
                "distance": round(gap, 4),
                "start_supported": supported_start,
                "end_supported": supported_end,
            }
        )
        if not supported_start or not supported_end:
            errors.append({"check": "route_endpoint_support", "segment": index, "start_supported": supported_start, "end_supported": supported_end})

    hatch_reports = []
    surfaces_by_name = {surface["name"]: surface for surface in traversal["surfaces"]}
    for entrance in contract.get("entrance_hatches", []):
        side_sign = -1.0 if entrance["side"] == "port" else 1.0
        cx, _cy, cz = entrance["cut_center"]
        threshold = [cx - side_sign * 0.35, entrance["entry_floor_y"], cz]
        interior = [side_sign * 4.2, entrance["entry_floor_y"], cz]
        expected_names = [
            f"{entrance['name']}_exterior_ramp",
            f"{entrance['name']}_hatch_to_corridor",
        ]
        missing = [name for name in expected_names if name not in surfaces_by_name]
        threshold_supported = any(point_supported_by_surface(threshold, surface, tolerance=1.0) for surface in traversal["surfaces"])
        interior_supported = any(point_supported_by_surface(interior, surface, tolerance=1.0) for surface in traversal["surfaces"])
        hatch_reports.append(
            {
                "name": entrance["name"],
                "threshold": threshold,
                "interior": interior,
                "missing_surfaces": missing,
                "threshold_supported": threshold_supported,
                "interior_supported": interior_supported,
            }
        )
        if missing or not threshold_supported or not interior_supported:
            errors.append(
                {
                    "check": "entrance_hatch_traversal",
                    "hatch": entrance["name"],
                    "missing_surfaces": missing,
                    "threshold_supported": threshold_supported,
                    "interior_supported": interior_supported,
                }
            )

    return {
        "schema_version": 1,
        "ship_id": "cargo_crane",
        "status": "PASS" if not errors else "FAIL",
        "error_count": len(errors),
        "warning_count": len(warnings),
        "minimum_clear_width": round(min_clear_width, 4),
        "errors": errors,
        "warnings": warnings,
        "checkpoint_reports": checkpoint_reports,
        "route_segment_reports": route_segment_reports,
        "hatch_reports": hatch_reports,
    }


def write_report(report: dict) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# CargoCrane Traversal Quality Report",
        "",
        f"Status: **{report['status']}**",
        "",
        f"- Errors: `{report['error_count']}`",
        f"- Warnings: `{report['warning_count']}`",
        f"- Minimum clear width: `{report['minimum_clear_width']}m`",
        "",
        "## Checkpoints",
        "",
    ]
    for checkpoint in report["checkpoint_reports"]:
        lines.append(f"- `{checkpoint['name']}` supported={checkpoint['supported']} origin={checkpoint['local_origin']}")
    lines += ["", "## Entrance Hatches", ""]
    for hatch in report["hatch_reports"]:
        lines.append(
            f"- `{hatch['name']}` threshold_supported={hatch['threshold_supported']} "
            f"interior_supported={hatch['interior_supported']} missing={hatch['missing_surfaces']}"
        )
    lines += ["", "## Warnings", ""]
    if report["warnings"]:
        for warning in report["warnings"]:
            lines.append(f"- `{warning['check']}` {warning}")
    else:
        lines.append("- None")
    lines += ["", "## Errors", ""]
    if report["errors"]:
        for error in report["errors"]:
            lines.append(f"- `{error['check']}` {error}")
    else:
        lines.append("- None")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    report = validate()
    write_report(report)
    print(f"{report['status']}: {report['error_count']} error(s), {report['warning_count']} warning(s)")
    print(f"Wrote {REPORT_MD.relative_to(ROOT)}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
