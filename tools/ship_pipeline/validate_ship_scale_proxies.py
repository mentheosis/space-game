#!/usr/bin/env python3
"""Validate ship scale proxy contract against marker contract assumptions."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROXY_CONTRACT = ROOT / "assets/source/blender/ships/shuttle_a/shuttle_a_scale_proxy_contract.json"
DEFAULT_MARKER_CONTRACT = ROOT / "assets/source/blender/ships/shuttle_a/shuttle_a_marker_contract.json"
DEFAULT_REPORT = ROOT / "reports/ship_pipeline/shuttle_a_scale_proxy_validation_report.json"

REQUIRED_PROXIES = {
    "standing_player_capsule",
    "seated_pilot_capsule",
    "pilot_eye_to_canopy",
    "rear_ramp_path",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proxy-contract", type=Path, default=DEFAULT_PROXY_CONTRACT)
    parser.add_argument("--marker-contract", type=Path, default=DEFAULT_MARKER_CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def finite_vector(value: object, size: int = 3) -> bool:
    return (
        isinstance(value, list)
        and len(value) == size
        and all(isinstance(item, (int, float)) and math.isfinite(float(item)) for item in value)
    )


def distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((float(a[index]) - float(b[index])) ** 2 for index in range(3)))


def horizontal_distance(a: list[float], b: list[float]) -> float:
    return math.sqrt((float(a[0]) - float(b[0])) ** 2 + (float(a[2]) - float(b[2])) ** 2)


def markers_by_node(marker_contract: dict) -> dict[str, list[float]]:
    markers = {}
    for marker in marker_contract.get("markers", []):
        node = marker.get("godot_node")
        position = marker.get("position")
        if isinstance(node, str) and finite_vector(position):
            markers[node] = position
    return markers


def validate_capsule(proxy: dict, markers: dict[str, list[float]], errors: list[dict[str, object]]) -> None:
    proxy_id = proxy.get("id")
    position = proxy.get("position")
    radius = proxy.get("radius")
    height = proxy.get("height")
    if not finite_vector(position):
        errors.append({"proxy": proxy_id, "status": "invalid_position", "value": position})
        return
    if not isinstance(radius, (int, float)) or not 0.15 <= float(radius) <= 0.75:
        errors.append({"proxy": proxy_id, "status": "implausible_radius", "value": radius})
    if not isinstance(height, (int, float)) or not 0.8 <= float(height) <= 2.4:
        errors.append({"proxy": proxy_id, "status": "implausible_height", "value": height})
    if isinstance(radius, (int, float)) and isinstance(height, (int, float)) and float(height) <= float(radius) * 2.0:
        errors.append({"proxy": proxy_id, "status": "height_not_larger_than_capsule_diameter"})

    if proxy_id == "standing_player_capsule":
        spawn = markers.get("InteriorSpawn")
        if spawn is None:
            errors.append({"proxy": proxy_id, "status": "missing_reference_marker", "marker": "InteriorSpawn"})
        elif horizontal_distance(position, spawn) > 0.25:
            errors.append(
                {
                    "proxy": proxy_id,
                    "status": "too_far_from_interior_spawn",
                    "distance": round(horizontal_distance(position, spawn), 4),
                }
            )
    elif proxy_id == "seated_pilot_capsule":
        seat_anchor = markers.get("SeatAnchor")
        pilot_eye = markers.get("PilotEye")
        if seat_anchor is None or pilot_eye is None:
            errors.append({"proxy": proxy_id, "status": "missing_seat_or_eye_marker"})
        else:
            if horizontal_distance(position, seat_anchor) > 0.5:
                errors.append(
                    {
                        "proxy": proxy_id,
                        "status": "too_far_from_seat_anchor",
                        "distance": round(horizontal_distance(position, seat_anchor), 4),
                    }
                )
            if float(position[1]) >= float(pilot_eye[1]):
                errors.append({"proxy": proxy_id, "status": "seated_proxy_not_below_pilot_eye"})


def validate_marker_segment(proxy: dict, markers: dict[str, list[float]], errors: list[dict[str, object]]) -> None:
    proxy_id = proxy.get("id")
    start_marker = proxy.get("start_marker")
    end_marker = proxy.get("end_marker")
    if not isinstance(start_marker, str) or not isinstance(end_marker, str):
        errors.append({"proxy": proxy_id, "status": "invalid_marker_references"})
        return
    start = markers.get(start_marker)
    end = markers.get(end_marker)
    if start is None or end is None:
        errors.append(
            {
                "proxy": proxy_id,
                "status": "missing_marker_reference",
                "start_marker": start_marker,
                "end_marker": end_marker,
            }
        )
        return
    length = distance(start, end)
    if proxy.get("type") == "ray":
        if not 0.2 <= length <= 3.0:
            errors.append({"proxy": proxy_id, "status": "implausible_ray_length", "length": round(length, 4)})
    elif proxy.get("type") == "segment":
        if not 0.5 <= length <= 4.0:
            errors.append({"proxy": proxy_id, "status": "implausible_segment_length", "length": round(length, 4)})
        if proxy_id == "rear_ramp_path":
            if float(end[1]) >= float(start[1]):
                errors.append({"proxy": proxy_id, "status": "ramp_end_not_below_start"})
            if float(end[2]) <= float(start[2]):
                errors.append({"proxy": proxy_id, "status": "ramp_end_not_aft_of_start"})


def validate(proxy_contract: dict, marker_contract: dict) -> list[dict[str, object]]:
    errors: list[dict[str, object]] = []
    proxies = proxy_contract.get("proxies", [])
    if not isinstance(proxies, list):
        return [{"proxy": None, "status": "proxies_field_not_list"}]

    ids = {proxy.get("id") for proxy in proxies}
    for required_id in sorted(REQUIRED_PROXIES - ids):
        errors.append({"proxy": required_id, "status": "missing_required_proxy"})

    markers = markers_by_node(marker_contract)
    for proxy in proxies:
        proxy_id = proxy.get("id")
        proxy_type = proxy.get("type")
        if not isinstance(proxy_id, str):
            errors.append({"proxy": proxy_id, "status": "invalid_id"})
            continue
        if proxy_type == "capsule":
            validate_capsule(proxy, markers, errors)
        elif proxy_type in {"ray", "segment"}:
            validate_marker_segment(proxy, markers, errors)
        else:
            errors.append({"proxy": proxy_id, "status": "unsupported_proxy_type", "type": proxy_type})
    return errors


def write_report(path: Path, proxy_contract: dict, marker_contract: dict, errors: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "proxy_count": len(proxy_contract.get("proxies", [])),
                "marker_count": len(marker_contract.get("markers", [])),
                "error_count": len(errors),
                "errors": errors,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    proxy_contract = load_json(args.proxy_contract)
    marker_contract = load_json(args.marker_contract)
    errors = validate(proxy_contract, marker_contract)
    write_report(args.report, proxy_contract, marker_contract, errors)
    if errors:
        print(f"ERROR: {len(errors)} scale proxy issue(s) detected. See {args.report}")
        for error in errors:
            print(f"- {error.get('proxy')}: {error.get('status')}")
        return 1
    print(f"PASS: {len(proxy_contract.get('proxies', []))} ship scale proxies are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
