#!/usr/bin/env python3
"""Static quality checks for CargoCrane enclosure bands."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "assets/source/blender/ships/cargo_crane/cargo_crane_interior_layout_contract.json"
ENCLOSURE_PATH = ROOT / "assets/models/ship/cargo_crane/cargo_crane_enclosure_bands.json"
TRAVERSAL_PATH = ROOT / "assets/models/ship/cargo_crane/cargo_crane_traversal_surfaces.json"
VOXEL_REPORT_PATH = ROOT / "reports/ship_pipeline/cargo_crane_voxel_fit/cargo_crane_voxel_report.json"
REPORT_JSON = ROOT / "reports/ship_pipeline/cargo_crane_voxel_fit/cargo_crane_enclosure_quality_report.json"
REPORT_MD = ROOT / "reports/ship_pipeline/cargo_crane_voxel_fit/cargo_crane_enclosure_quality_report.md"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def point_inside_box(point: list[float], center: list[float], size: list[float], padding: float = 0.0) -> bool:
    return all(abs(point[index] - center[index]) <= size[index] * 0.5 + padding for index in range(3))


def band_bounds(band: dict) -> tuple[list[float], list[float]]:
    center = band["center"]
    size = band["size"]
    return (
        [center[index] - size[index] * 0.5 for index in range(3)],
        [center[index] + size[index] * 0.5 for index in range(3)],
    )


def validate() -> dict:
    contract = load_json(CONTRACT_PATH)
    enclosure = load_json(ENCLOSURE_PATH)
    traversal = load_json(TRAVERSAL_PATH)
    voxel_report = load_json(VOXEL_REPORT_PATH)
    radius = float(contract["player_capsule"]["radius"])
    errors = []
    warnings = []

    expected_regions = {region["id"] for region in contract["semantic_regions"]}
    by_region: dict[str, list[dict]] = {}
    for band in enclosure.get("bands", []):
        by_region.setdefault(band["region"], []).append(band)
        if any(value <= 0.0 for value in band["size"]):
            errors.append({"check": "positive_band_size", "band": band["name"], "size": band["size"]})

    for region_id in sorted(expected_regions):
        types = {band["type"] for band in by_region.get(region_id, [])}
        required_types = {"side_wall", "ceiling"}
        if region_id == "cockpit_lower":
            required_types.remove("ceiling")
        for required in required_types:
            if required not in types:
                errors.append({"check": "region_band_completeness", "region": region_id, "missing": required})

    exterior_bounds = voxel_report["exterior_bounds"]
    for band in enclosure.get("bands", []):
        bmin, bmax = band_bounds(band)
        for axis, axis_name in enumerate(["x", "y", "z"]):
            if bmin[axis] < exterior_bounds["min"][axis] - 2.5 or bmax[axis] > exterior_bounds["max"][axis] + 2.5:
                warnings.append(
                    {
                        "check": "band_near_exterior_envelope",
                        "band": band["name"],
                        "axis": axis_name,
                        "band_min": round(bmin[axis], 4),
                        "band_max": round(bmax[axis], 4),
                        "exterior_min": exterior_bounds["min"][axis],
                        "exterior_max": exterior_bounds["max"][axis],
                    }
                )

    route_clearance_failures = []
    for point in traversal["primary_route"]:
        for band in enclosure.get("bands", []):
            if point_inside_box(point, band["center"], band["size"], padding=radius):
                route_clearance_failures.append({"point": point, "band": band["name"]})
                break
    if route_clearance_failures:
        errors.append({"check": "route_clearance", "failures": route_clearance_failures})

    stair_ramp_clearance_failures = []
    for surface in traversal["surfaces"]:
        sample_points = []
        if surface["type"] == "ramp":
            sample_points = [surface["start"], surface["end"]]
        elif surface["type"] == "stair_path":
            sample_points = surface["points"]
        for point in sample_points:
            for band in enclosure.get("bands", []):
                if point_inside_box(point, band["center"], band["size"], padding=radius):
                    stair_ramp_clearance_failures.append({"surface": surface["name"], "point": point, "band": band["name"]})
                    break
    if stair_ramp_clearance_failures:
        errors.append({"check": "stair_ramp_corridor_clearance", "failures": stair_ramp_clearance_failures})

    return {
        "schema_version": 1,
        "ship_id": "cargo_crane",
        "status": "PASS" if not errors else "FAIL",
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "band_count": len(enclosure.get("bands", [])),
        "region_count": len(expected_regions),
    }


def write_report(report: dict) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# CargoCrane Enclosure Quality Report",
        "",
        f"Status: **{report['status']}**",
        "",
        f"- Bands: `{report['band_count']}`",
        f"- Regions: `{report['region_count']}`",
        f"- Errors: `{report['error_count']}`",
        f"- Warnings: `{report['warning_count']}`",
        "",
        "## Errors",
        "",
    ]
    if report["errors"]:
        for error in report["errors"]:
            lines.append(f"- `{error['check']}` {error}")
    else:
        lines.append("- None")
    lines += ["", "## Warnings", ""]
    if report["warnings"]:
        for warning in report["warnings"]:
            lines.append(f"- `{warning['check']}` {warning}")
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
