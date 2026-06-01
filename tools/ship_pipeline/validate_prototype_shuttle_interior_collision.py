#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "assets/source/blender/ships/prototype_shuttle/prototype_shuttle_interior_collision_contract.json"
REPORT_JSON = ROOT / "reports/ship_pipeline/prototype_shuttle_interior_collision_validation_report.json"
REPORT_MD = ROOT / "reports/ship_pipeline/prototype_shuttle_interior_collision_validation_report.md"


@dataclass(frozen=True)
class Box:
    box_id: str
    center: tuple[float, float, float]
    size: tuple[float, float, float]

    @property
    def mins(self) -> tuple[float, float, float]:
        return tuple(c - s * 0.5 for c, s in zip(self.center, self.size))

    @property
    def maxs(self) -> tuple[float, float, float]:
        return tuple(c + s * 0.5 for c, s in zip(self.center, self.size))


PROTECTED_SPACES: dict[str, Box] = {
    "ramp_center_path": Box("ramp_center_path", (0.0, -2.05, -1.45), (2.4, 2.9, 4.7)),
    "cargo_walkway": Box("cargo_walkway", (0.0, 0.2, 7.15), (3.1, 2.0, 12.5)),
    "left_stair_lane": Box("left_stair_lane", (-2.165, 0.3, -0.2), (1.17, 2.2, 4.4)),
    "right_stair_lane": Box("right_stair_lane", (2.165, 0.3, -0.2), (1.17, 2.2, 4.4)),
    "cockpit_walkway": Box("cockpit_walkway", (0.0, 1.8, -8.5), (2.7, 1.6, 10.6)),
}


def main() -> int:
    contract = json.loads(CONTRACT.read_text())
    checks: list[dict[str, object]] = []
    regions = contract.get("regions", [])

    ids: set[str] = set()
    for region in regions:
        region_id = region.get("id", "")
        add_check(checks, bool(region_id), f"{region_id or '<missing>'}_has_id")
        add_check(checks, region_id not in ids, f"{region_id}_id_is_unique")
        ids.add(region_id)
        add_check(checks, region.get("role") == "player_enclosure", f"{region_id}_role_is_player_enclosure")
        add_check(checks, region.get("kind") == "box", f"{region_id}_kind_is_box")
        add_check(checks, valid_vector(region.get("center")), f"{region_id}_has_center_vector")
        add_check(checks, valid_vector(region.get("size")), f"{region_id}_has_size_vector")
        if valid_vector(region.get("size")):
            add_check(checks, all(value > 0.0 for value in region["size"]), f"{region_id}_size_is_positive")

    add_check(checks, len(regions) >= 20, "has_expected_enclosure_region_count")

    for region in regions:
        if not valid_vector(region.get("center")) or not valid_vector(region.get("size")):
            continue

        box = Box(region["id"], tuple(region["center"]), tuple(region["size"]))
        for space_id, protected in PROTECTED_SPACES.items():
            volume = overlap_volume(box, protected)
            add_check(checks, volume <= 0.0, f"{box.box_id}_does_not_overlap_{space_id}", {"overlap_volume": round(volume, 5)})

    passed = all(check["pass"] for check in checks)
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": 1,
        "source": str(CONTRACT.relative_to(ROOT)),
        "pass": passed,
        "checks": checks,
        "regions": regions,
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n")
    REPORT_MD.write_text(render_markdown(report))

    print(f"Interior collision validation: {'PASS' if passed else 'FAIL'}")
    print(f"Report: {REPORT_JSON.relative_to(ROOT)}")
    return 0 if passed else 1


def valid_vector(value: object) -> bool:
    return isinstance(value, list) and len(value) == 3 and all(isinstance(item, (int, float)) for item in value)


def overlap_volume(a: Box, b: Box) -> float:
    a_min = a.mins
    a_max = a.maxs
    b_min = b.mins
    b_max = b.maxs
    overlap = [
        max(0.0, min(a_max[i], b_max[i]) - max(a_min[i], b_min[i]))
        for i in range(3)
    ]
    return overlap[0] * overlap[1] * overlap[2]


def add_check(checks: list[dict[str, object]], passed: bool, check_id: str, data: dict[str, object] | None = None) -> None:
    check = {"id": check_id, "pass": passed}
    if data:
        check.update(data)
    checks.append(check)


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Prototype Shuttle Interior Collision Validation",
        "",
        f"Source: `{report['source']}`",
        f"Status: {'PASS' if report['pass'] else 'FAIL'}",
        "",
        "## Checks",
        "",
    ]
    for check in report["checks"]:
        status = "PASS" if check["pass"] else "FAIL"
        suffix = ""
        if "overlap_volume" in check:
            suffix = f" overlap={check['overlap_volume']}"
        lines.append(f"- {status} `{check['id']}`{suffix}")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
