#!/usr/bin/env python3
"""Validate Godot ship light nodes against the package light contract."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from extract_ship_scene_lights import extract


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "assets/source/blender/ships/shuttle_a/shuttle_a_light_contract.json"
DEFAULT_SCENE = ROOT / "scenes/ship/Ship.tscn"
DEFAULT_REPORT = ROOT / "reports/ship_pipeline/shuttle_a_light_sync_report.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--scene", type=Path, default=DEFAULT_SCENE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--tolerance", type=float, default=0.001)
    parser.add_argument("--check", action="store_true", help="Fail on drift. Default when no action is supplied.")
    return parser.parse_args()


def load_contract(path: Path) -> list[dict[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    lights = data.get("lights", [])
    if not lights:
        raise ValueError(f"No lights found in {path}")
    return lights


def light_key(light: dict[str, object]) -> str:
    return str(light.get("godot_node", ""))


def compare_number(expected: float, actual: object, tolerance: float) -> bool:
    if not isinstance(actual, (int, float)):
        return False
    return math.isfinite(float(actual)) and abs(float(expected) - float(actual)) <= tolerance


def compare_value(expected: object, actual: object, tolerance: float) -> bool:
    if isinstance(expected, (int, float)):
        return compare_number(float(expected), actual, tolerance)
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            return False
        return all(compare_value(item, actual[index], tolerance) for index, item in enumerate(expected))
    return expected == actual


def compare_lights(
    expected_lights: list[dict[str, object]],
    actual_lights: list[dict[str, object]],
    tolerance: float,
) -> list[dict[str, object]]:
    drift = []
    expected_by_node = {light_key(light): light for light in expected_lights}
    actual_by_node = {light_key(light): light for light in actual_lights}

    for node_name, expected in expected_by_node.items():
        actual = actual_by_node.get(node_name)
        if actual is None:
            drift.append({"light": node_name, "status": "missing_in_scene", "expected": expected, "actual": None})
            continue

        for field in ["id", "godot_type", "parent", "position", "rotation"]:
            if field not in expected and field not in actual:
                continue
            if field not in expected or field not in actual:
                drift.append(
                    {
                        "light": node_name,
                        "status": "field_presence_drift",
                        "field": field,
                        "expected": expected.get(field),
                        "actual": actual.get(field),
                    }
                )
                continue
            if not compare_value(expected[field], actual[field], tolerance):
                drift.append(
                    {
                        "light": node_name,
                        "status": "field_value_drift",
                        "field": field,
                        "expected": expected[field],
                        "actual": actual[field],
                    }
                )

        expected_props = expected.get("properties", {})
        actual_props = actual.get("properties", {})
        if not isinstance(expected_props, dict) or not isinstance(actual_props, dict):
            drift.append(
                {
                    "light": node_name,
                    "status": "invalid_properties",
                    "expected": expected_props,
                    "actual": actual_props,
                }
            )
            continue

        for property_name in sorted(set(expected_props.keys()) | set(actual_props.keys())):
            if property_name not in expected_props or property_name not in actual_props:
                drift.append(
                    {
                        "light": node_name,
                        "status": "property_presence_drift",
                        "field": property_name,
                        "expected": expected_props.get(property_name),
                        "actual": actual_props.get(property_name),
                    }
                )
                continue
            if not compare_value(expected_props[property_name], actual_props[property_name], tolerance):
                drift.append(
                    {
                        "light": node_name,
                        "status": "property_value_drift",
                        "field": property_name,
                        "expected": expected_props[property_name],
                        "actual": actual_props[property_name],
                    }
                )

    for node_name, actual in actual_by_node.items():
        if node_name not in expected_by_node:
            drift.append({"light": node_name, "status": "extra_scene_light", "expected": None, "actual": actual})
    return drift


def write_report(path: Path, expected_count: int, actual_count: int, drift: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "expected_light_count": expected_count,
                "actual_light_count": actual_count,
                "drift_count": len(drift),
                "drift": drift,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    if not args.check:
        args.check = True

    expected = load_contract(args.contract)
    actual = extract(args.scene)
    drift = compare_lights(expected, actual, args.tolerance)
    write_report(args.report, len(expected), len(actual), drift)

    if drift:
        print(f"ERROR: {len(drift)} ship light issue(s) detected. See {args.report}")
        for item in drift[:20]:
            suffix = f" field={item['field']}" if "field" in item else ""
            print(f"- {item['light']}: {item['status']}{suffix}")
        if len(drift) > 20:
            print(f"... {len(drift) - 20} more issue(s)")
        return 1 if args.check else 0

    print(f"PASS: {len(expected)} ship lights match {args.scene}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
