#!/usr/bin/env python3
"""Validate prototype shuttle exterior collision contract."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "assets/source/blender/ships/prototype_shuttle/prototype_shuttle_exterior_collision_contract.json"
REPORT_JSON = ROOT / "reports/ship_pipeline/prototype_shuttle_exterior_collision_validation_report.json"
REPORT_MD = ROOT / "reports/ship_pipeline/prototype_shuttle_exterior_collision_validation_report.md"


def bounds(center: list[float], size: list[float]) -> dict[str, list[float]]:
    return {
        "min": [round(center[i] - size[i] * 0.5, 5) for i in range(3)],
        "max": [round(center[i] + size[i] * 0.5, 5) for i in range(3)],
    }


def overlaps_1d(a_min: float, a_max: float, b_min: float, b_max: float) -> bool:
    return a_min <= b_max and b_min <= a_max


def main() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    validation_targets = contract.get("initial_validation_targets", {})
    ramp_x = validation_targets.get("must_not_block_ramp_center_x_range", [-1.65, 1.65])
    ramp_z = validation_targets.get("must_not_block_ramp_z_range", [-3.8, 0.4])
    contact_bottom_y = float(validation_targets.get("ship_world_contact_bottom_y", -3.65))

    checks: list[dict[str, object]] = []
    regions_report: list[dict[str, object]] = []
    ship_world_regions = []

    for region in contract.get("regions", []):
        region_bounds = bounds(region["center"], region["size"])
        role = region.get("role")
        kind = region.get("kind")
        region_report = {
            "id": region.get("id"),
            "kind": kind,
            "role": role,
            "walkable": bool(region.get("walkable", False)),
            "center": region["center"],
            "size": region["size"],
            "bounds": region_bounds,
        }
        regions_report.append(region_report)

        if role == "ship_world_physics":
            ship_world_regions.append(region_report)
            blocks_ramp = (
                overlaps_1d(region_bounds["min"][0], region_bounds["max"][0], ramp_x[0], ramp_x[1])
                and overlaps_1d(region_bounds["min"][2], region_bounds["max"][2], ramp_z[0], ramp_z[1])
            )
            checks.append({
                "id": f"{region['id']}_does_not_cross_ramp_center",
                "pass": not blocks_ramp,
                "details": {
                    "region_bounds": region_bounds,
                    "ramp_center_x_range": ramp_x,
                    "ramp_z_range": ramp_z,
                },
            })

    checks.append({
        "id": "has_ship_world_physics_regions",
        "pass": len(ship_world_regions) >= 2,
        "details": {"count": len(ship_world_regions)},
    })

    lowest_bottom = min((region["bounds"]["min"][1] for region in ship_world_regions), default=None)
    checks.append({
        "id": "ship_world_contact_bottom_reaches_expected_support_height",
        "pass": lowest_bottom is not None and abs(float(lowest_bottom) - contact_bottom_y) <= 0.12,
        "details": {
            "expected_bottom_y": contact_bottom_y,
            "actual_lowest_bottom_y": lowest_bottom,
            "tolerance": 0.12,
        },
    })

    duplicate_ids = sorted({
        region["id"]
        for region in regions_report
        if [item["id"] for item in regions_report].count(region["id"]) > 1
    })
    checks.append({
        "id": "region_ids_are_unique",
        "pass": not duplicate_ids,
        "details": {"duplicates": duplicate_ids},
    })

    report = {
        "schema_version": 1,
        "source": str(CONTRACT_PATH.relative_to(ROOT)),
        "pass": all(bool(check["pass"]) for check in checks),
        "region_count": len(regions_report),
        "ship_world_physics_region_count": len(ship_world_regions),
        "regions": regions_report,
        "checks": checks,
    }

    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Prototype Shuttle Exterior Collision Validation",
        "",
        f"Source: `{report['source']}`",
        f"Status: {'PASS' if report['pass'] else 'FAIL'}",
        "",
        "## Regions",
        "",
    ]
    for region in regions_report:
        lines.append(
            f"- `{region['id']}`: `{region['role']}` `{region['kind']}` center={region['center']} size={region['size']}"
        )
    lines.extend(["", "## Checks", ""])
    for check in checks:
        lines.append(f"- {'PASS' if check['pass'] else 'FAIL'} `{check['id']}`")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Exterior collision validation: {'PASS' if report['pass'] else 'FAIL'}")
    print(f"Report: {REPORT_JSON.relative_to(ROOT)}")
    if not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
