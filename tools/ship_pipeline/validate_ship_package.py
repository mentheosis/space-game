#!/usr/bin/env python3
"""Validate ShuttleA exported package reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ASSET_REPORT = ROOT / "assets/models/ship/shuttle_a/shuttle_a_asset_report.json"
DEFAULT_MATERIAL_REPORT = ROOT / "assets/models/ship/shuttle_a/shuttle_a_material_report.json"
DEFAULT_LIGHT_REPORT = ROOT / "assets/models/ship/shuttle_a/shuttle_a_light_report.json"
DEFAULT_SCALE_PROXY_REPORT = ROOT / "assets/models/ship/shuttle_a/shuttle_a_scale_proxy_report.json"

REQUIRED_COLLECTIONS = ["Exterior", "Interior", "Collision", "Markers"]
REQUIRED_GROUPS = ["exterior", "interior", "collision"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-report", type=Path, default=DEFAULT_ASSET_REPORT)
    parser.add_argument("--material-report", type=Path, default=DEFAULT_MATERIAL_REPORT)
    parser.add_argument("--light-report", type=Path, default=DEFAULT_LIGHT_REPORT)
    parser.add_argument("--scale-proxy-report", type=Path, default=DEFAULT_SCALE_PROXY_REPORT)
    return parser.parse_args()


def load_json(path: Path) -> dict:
    if not path.exists() or path.stat().st_size == 0:
        raise ValueError(f"Missing or empty JSON report: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_asset_report(report: dict) -> list[str]:
    errors = []
    collections = report.get("standard_collections", {})
    for name in REQUIRED_COLLECTIONS:
        item = collections.get(name)
        if not item:
            errors.append(f"Missing standard collection report: {name}")
        elif not item.get("found"):
            errors.append(f"Required standard collection has no matching Blender collection: {name}")

    groups = report.get("groups", {})
    for name in REQUIRED_GROUPS:
        group = groups.get(name)
        if not group:
            errors.append(f"Missing object group report: {name}")
            continue
        if group.get("mesh_count", 0) <= 0:
            errors.append(f"Object group has no meshes: {name}")
        if group.get("triangle_count", 0) <= 0:
            errors.append(f"Object group has no triangles: {name}")
        if group.get("bounds") is None:
            errors.append(f"Object group has no bounds: {name}")

    if report.get("marker_count", 0) <= 0:
        errors.append("Asset report has no markers")
    return errors


def validate_material_report(report: dict) -> list[str]:
    errors = []
    if report.get("material_count", 0) <= 0:
        errors.append("Material report has no materials")
    return errors


def validate_light_report(report: dict) -> list[str]:
    errors = []
    if report.get("light_count", 0) <= 0:
        errors.append("Light report has no lights")
    for light in report.get("lights", []):
        for key in ["id", "godot_node", "godot_type", "parent", "position", "properties"]:
            if key not in light:
                errors.append(f"Light is missing required field {key}: {light}")
                break
    return errors


def validate_scale_proxy_report(report: dict) -> list[str]:
    errors = []
    if report.get("proxy_count", 0) <= 0:
        errors.append("Scale proxy report has no proxies")
    proxy_ids = {proxy.get("id") for proxy in report.get("proxies", [])}
    for required_id in ["standing_player_capsule", "seated_pilot_capsule", "pilot_eye_to_canopy", "rear_ramp_path"]:
        if required_id not in proxy_ids:
            errors.append(f"Scale proxy report is missing required proxy: {required_id}")
    return errors


def main() -> int:
    args = parse_args()
    asset_report = load_json(args.asset_report)
    material_report = load_json(args.material_report)
    light_report = load_json(args.light_report)
    scale_proxy_report = load_json(args.scale_proxy_report)
    errors = (
        validate_asset_report(asset_report)
        + validate_material_report(material_report)
        + validate_light_report(light_report)
        + validate_scale_proxy_report(scale_proxy_report)
    )
    if errors:
        print("ERROR: Ship package validation failed")
        for error in errors:
            print(f"- {error}")
        return 1
    warnings = asset_report.get("warnings", [])
    print(
        "PASS: ship package reports are valid "
        f"({asset_report.get('marker_count', 0)} markers, "
        f"{material_report.get('material_count', 0)} materials, "
        f"{light_report.get('light_count', 0)} lights, "
        f"{scale_proxy_report.get('proxy_count', 0)} scale proxies, "
        f"{len(warnings)} warning(s))."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
