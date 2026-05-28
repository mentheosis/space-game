#!/usr/bin/env python3
"""Extract current Godot-authored ship lights into a package light contract."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCENE = ROOT / "scenes/ship/Ship.tscn"
DEFAULT_OUTPUT = ROOT / "assets/source/blender/ships/shuttle_a/shuttle_a_light_contract.json"

NODE_RE = re.compile(r'^\[node name="(?P<name>[^"]+)" type="(?P<type>[^"]+)" parent="(?P<parent>[^"]+)"\]$')
VECTOR_RE = re.compile(r"Vector3\(([^)]*)\)")
COLOR_RE = re.compile(r"Color\(([^)]*)\)")
LIGHT_TYPES = {"OmniLight3D", "SpotLight3D"}


def parse_numbers(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",")]


def parse_value(raw: str):
    vector_match = VECTOR_RE.match(raw)
    if vector_match:
        return parse_numbers(vector_match.group(1))
    color_match = COLOR_RE.match(raw)
    if color_match:
        return parse_numbers(color_match.group(1))
    try:
        return float(raw)
    except ValueError:
        return raw


def light_id(name: str) -> str:
    result = []
    for index, char in enumerate(name):
        if char.isupper() and index > 0:
            result.append("_")
        result.append(char.lower())
    return "".join(result)


def extract(scene_path: Path) -> list[dict[str, object]]:
    lights = []
    current = None
    for line in scene_path.read_text(encoding="utf-8").splitlines():
        node_match = NODE_RE.match(line)
        if node_match:
            if current is not None:
                lights.append(current)
            current = None
            node_type = node_match.group("type")
            if node_type in LIGHT_TYPES:
                name = node_match.group("name")
                current = {
                    "id": light_id(name),
                    "godot_node": name,
                    "godot_type": node_type,
                    "parent": node_match.group("parent"),
                    "position": [0.0, 0.0, 0.0],
                    "properties": {},
                }
            continue
        if current is None or " = " not in line:
            continue
        key, raw_value = line.split(" = ", 1)
        parsed = parse_value(raw_value)
        if key == "position":
            current["position"] = parsed
        elif key == "rotation":
            current["rotation"] = parsed
        elif key.startswith("light_") or key.startswith("omni_") or key.startswith("spot_"):
            current["properties"][key] = parsed
    if current is not None:
        lights.append(current)
    return lights


def main() -> int:
    lights = extract(DEFAULT_SCENE)
    if not lights:
        print(f"ERROR: no lights found in {DEFAULT_SCENE}", file=sys.stderr)
        return 1
    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "ship_id": "shuttle_a",
                "coordinate_space": "godot_ship_local",
                "source": str(DEFAULT_SCENE.relative_to(ROOT)),
                "lights": lights,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {DEFAULT_OUTPUT} ({len(lights)} lights)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
