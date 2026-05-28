#!/usr/bin/env python3
"""Validate or apply exported ship marker positions to the Godot ship scene."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "assets/source/blender/ships/shuttle_a/shuttle_a_marker_contract.json"
DEFAULT_EXPORTED_MARKERS = ROOT / "assets/models/ship/shuttle_a/shuttle_a_markers.json"
DEFAULT_SCENE = ROOT / "scenes/ship/Ship.tscn"
DEFAULT_REPORT = ROOT / "reports/ship_pipeline/shuttle_a_marker_sync_report.json"

NODE_RE = re.compile(r'^\[node name="(?P<name>[^"]+)" type="(?P<type>[^"]+)" parent="(?P<parent>[^"]+)"\]$')
POSITION_RE = re.compile(r"^position = Vector3\(([^)]*)\)$")


@dataclass(frozen=True)
class Marker:
    id: str
    godot_node: str
    position: tuple[float, float, float]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--markers-json", type=Path, default=DEFAULT_EXPORTED_MARKERS)
    parser.add_argument("--scene", type=Path, default=DEFAULT_SCENE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--tolerance", type=float, default=0.001)
    parser.add_argument("--apply", action="store_true", help="Update scene marker positions from marker data.")
    parser.add_argument("--check", action="store_true", help="Fail if scene markers drift from marker data.")
    parser.add_argument(
        "--source",
        choices=("contract", "exported"),
        default="exported",
        help="Marker data to use. Use contract before export, exported after Blender export.",
    )
    return parser.parse_args()


def finite_vector(values: object, marker_name: str) -> tuple[float, float, float]:
    if not isinstance(values, list) or len(values) != 3:
        raise ValueError(f"{marker_name}: position must be a 3-number list")
    parsed = tuple(float(value) for value in values)
    if any(not math.isfinite(value) for value in parsed):
        raise ValueError(f"{marker_name}: position contains a non-finite value")
    return parsed


def load_contract(path: Path) -> list[Marker]:
    data = json.loads(path.read_text(encoding="utf-8"))
    markers = []
    seen_nodes = set()
    for item in data.get("markers", []):
        marker_id = str(item["id"])
        godot_node = str(item["godot_node"])
        if godot_node in seen_nodes:
            raise ValueError(f"Duplicate marker node in contract: {godot_node}")
        seen_nodes.add(godot_node)
        markers.append(Marker(marker_id, godot_node, finite_vector(item["position"], godot_node)))
    if not markers:
        raise ValueError(f"No markers found in {path}")
    return markers


def load_exported(path: Path, contract: list[Marker]) -> list[Marker]:
    data = json.loads(path.read_text(encoding="utf-8"))
    by_node = {marker.godot_node: marker for marker in contract}
    markers = []
    for godot_node, contract_marker in by_node.items():
        if godot_node not in data:
            raise ValueError(f"Exported marker JSON is missing required marker: {godot_node}")
        markers.append(Marker(contract_marker.id, godot_node, finite_vector(data[godot_node], godot_node)))
    return markers


def load_scene_markers(scene_path: Path) -> dict[str, tuple[float, float, float]]:
    lines = scene_path.read_text(encoding="utf-8").splitlines()
    markers: dict[str, tuple[float, float, float]] = {}
    current_marker: str | None = None
    for line in lines:
        node_match = NODE_RE.match(line)
        if node_match:
            current_marker = None
            if node_match.group("type") == "Marker3D" and node_match.group("parent") == "Markers":
                current_marker = node_match.group("name")
            continue
        if current_marker is None:
            continue
        position_match = POSITION_RE.match(line)
        if position_match:
            markers[current_marker] = parse_vector3(position_match.group(1))
            current_marker = None
    return markers


def parse_vector3(value: str) -> tuple[float, float, float]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 3:
        raise ValueError(f"Invalid Vector3 value: {value}")
    return tuple(float(part) for part in parts)


def format_float(value: float) -> str:
    text = f"{value:.5f}".rstrip("0").rstrip(".")
    return text if text != "-0" else "0"


def format_vector3(position: tuple[float, float, float]) -> str:
    return f"Vector3({format_float(position[0])}, {format_float(position[1])}, {format_float(position[2])})"


def compare(markers: list[Marker], scene_markers: dict[str, tuple[float, float, float]], tolerance: float) -> list[dict[str, object]]:
    drift = []
    for marker in markers:
        actual = scene_markers.get(marker.godot_node)
        if actual is None:
            drift.append(
                {
                    "marker": marker.godot_node,
                    "status": "missing_in_scene",
                    "expected": list(marker.position),
                    "actual": None,
                }
            )
            continue
        delta = max(abs(expected - seen) for expected, seen in zip(marker.position, actual))
        if delta > tolerance:
            drift.append(
                {
                    "marker": marker.godot_node,
                    "status": "drift",
                    "expected": list(marker.position),
                    "actual": list(actual),
                    "max_axis_delta": round(delta, 6),
                }
            )
    return drift


def apply_markers(scene_path: Path, markers: list[Marker]) -> None:
    lines = scene_path.read_text(encoding="utf-8").splitlines()
    marker_by_node = {marker.godot_node: marker for marker in markers}
    seen = set()
    output = []
    current_marker: str | None = None
    current_is_known = False
    for line in lines:
        node_match = NODE_RE.match(line)
        if node_match:
            current_marker = None
            current_is_known = False
            if node_match.group("type") == "Marker3D" and node_match.group("parent") == "Markers":
                current_marker = node_match.group("name")
                current_is_known = current_marker in marker_by_node
            output.append(line)
            continue
        if current_marker is not None and current_is_known and POSITION_RE.match(line):
            marker = marker_by_node[current_marker]
            output.append(f"position = {format_vector3(marker.position)}")
            seen.add(current_marker)
            current_marker = None
            current_is_known = False
            continue
        output.append(line)

    missing = [marker for marker in markers if marker.godot_node not in seen]
    if missing:
        insert_at = find_marker_insert_index(output)
        additions = []
        for marker in missing:
            additions.extend(
                [
                    "",
                    f'[node name="{marker.godot_node}" type="Marker3D" parent="Markers"]',
                    f"position = {format_vector3(marker.position)}",
                ]
            )
        output[insert_at:insert_at] = additions

    scene_path.write_text("\n".join(output) + "\n", encoding="utf-8")


def find_marker_insert_index(lines: list[str]) -> int:
    last_marker_header = -1
    for index, line in enumerate(lines):
        match = NODE_RE.match(line)
        if match and match.group("type") == "Marker3D" and match.group("parent") == "Markers":
            last_marker_header = index
    if last_marker_header == -1:
        raise ValueError("Could not find any Marker3D nodes under parent Markers")
    index = last_marker_header + 1
    while index < len(lines) and not lines[index].startswith("[node "):
        index += 1
    return index


def write_report(path: Path, source: str, markers: list[Marker], drift: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "source": source,
                "marker_count": len(markers),
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
    if not args.apply and not args.check:
        args.check = True

    contract = load_contract(args.contract)
    markers = contract if args.source == "contract" else load_exported(args.markers_json, contract)

    if args.apply:
        apply_markers(args.scene, markers)

    scene_markers = load_scene_markers(args.scene)
    drift = compare(markers, scene_markers, args.tolerance)
    write_report(args.report, args.source, markers, drift)

    if drift:
        print(f"ERROR: {len(drift)} ship marker issue(s) detected. See {args.report}")
        for item in drift:
            print(f"- {item['marker']}: {item['status']} expected={item['expected']} actual={item['actual']}")
        return 1 if args.check else 0

    print(f"PASS: {len(markers)} ship markers match {args.scene}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
