#!/usr/bin/env python3
"""Audit Ship.tscn nodes by package/Godot ownership and migration recommendation."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCENE = ROOT / "scenes/ship/Ship.tscn"
DEFAULT_JSON = ROOT / "reports/ship_pipeline/shuttle_a_godot_node_audit.json"
DEFAULT_MD = ROOT / "reports/ship_pipeline/shuttle_a_godot_node_audit.md"

NODE_RE = re.compile(r'^\[node name="(?P<name>[^"]+)"(?: type="(?P<type>[^"]+)")?(?: parent="(?P<parent>[^"]+)")?(?: instance=ExtResource\("(?P<instance>[^"]+)"\))?\]$')
EXT_RESOURCE_RE = re.compile(r'^\[ext_resource type="(?P<type>[^"]+)" path="(?P<path>[^"]+)" id="(?P<id>[^"]+)"\]$')
SUB_RESOURCE_RE = re.compile(r'^\[sub_resource type="(?P<type>[^"]+)" id="(?P<id>[^"]+)"\]$')

PACKAGE_MARKERS = {
    "InteriorSpawn",
    "ExteriorExit",
    "SeatAnchor",
    "PilotEye",
    "SeatExit",
    "CanopyTarget",
    "HatchCenter",
    "RampStart",
    "RampEnd",
}

INTERACTION_ROOTS = {"ExteriorHatch", "InteriorHatch", "PilotSeat"}
GAMEPLAY_SCRIPT_IDS = {"1_hatch", "2_seat", "4_interior_volume", "5_ship_controller", "6_material_overrides"}
PACKAGE_INSTANCE_IDS = {"36_blender_interior"}
EXTERIOR_REFERENCE_INSTANCE_IDS = {"12_placeholder_visual", "13_oga_shuttle"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, default=DEFAULT_SCENE)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MD)
    return parser.parse_args()


def parse_scene(scene_path: Path) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]], list[dict[str, object]]]:
    ext_resources: dict[str, dict[str, str]] = {}
    sub_resources: dict[str, dict[str, str]] = {}
    nodes: list[dict[str, object]] = []
    current_node: dict[str, object] | None = None

    for line_no, line in enumerate(scene_path.read_text(encoding="utf-8").splitlines(), start=1):
        ext_match = EXT_RESOURCE_RE.match(line)
        if ext_match:
            ext_resources[ext_match.group("id")] = {
                "type": ext_match.group("type"),
                "path": ext_match.group("path"),
            }
            continue

        sub_match = SUB_RESOURCE_RE.match(line)
        if sub_match:
            sub_resources[sub_match.group("id")] = {"type": sub_match.group("type")}
            continue

        node_match = NODE_RE.match(line)
        if node_match:
            if current_node is not None:
                nodes.append(current_node)
            name = node_match.group("name")
            parent = node_match.group("parent") or "."
            current_node = {
                "name": name,
                "type": node_match.group("type") or "Instance",
                "parent": parent,
                "path": name if parent == "." else f"{parent}/{name}",
                "instance": node_match.group("instance"),
                "line": line_no,
                "properties": {},
            }
            continue

        if current_node is not None and " = " in line:
            key, value = line.split(" = ", 1)
            current_node["properties"][key] = value

    if current_node is not None:
        nodes.append(current_node)
    return ext_resources, sub_resources, nodes


def resource_id(value: str | None) -> str | None:
    if value is None:
        return None
    match = re.match(r'ExtResource\("(?P<id>[^"]+)"\)', value)
    if match:
        return match.group("id")
    match = re.match(r'SubResource\("(?P<id>[^"]+)"\)', value)
    if match:
        return match.group("id")
    return None


def nearest_interaction_root(path: str) -> str | None:
    parts = path.split("/")
    for root in INTERACTION_ROOTS:
        if root in parts:
            return root
    return None


def classify_node(node: dict[str, object]) -> tuple[str, str]:
    name = str(node["name"])
    node_type = str(node["type"])
    path = str(node["path"])
    parent = str(node["parent"])
    props = node["properties"]
    assert isinstance(props, dict)
    script_id = resource_id(props.get("script"))
    mesh_id = resource_id(props.get("mesh"))
    shape_id = resource_id(props.get("shape"))
    instance_id = node.get("instance")

    if instance_id in PACKAGE_INSTANCE_IDS:
        return "package_driven_now", "Blender/package interior GLB instance."
    if node_type == "Marker3D" and parent == "Markers" and name in PACKAGE_MARKERS:
        return "package_driven_now", "Marker position is contract validated."
    if node_type in {"OmniLight3D", "SpotLight3D"}:
        return "package_driven_now", "Light node is contract validated."

    if script_id in GAMEPLAY_SCRIPT_IDS:
        return "godot_authored_keep", "Gameplay script/controller node."
    if path == "Ship":
        return "godot_authored_keep", "Ship physics root and runtime controller host."
    if path == "ShipCamera":
        return "godot_authored_keep", "Runtime ship camera."
    if node_type == "Area3D" and name in INTERACTION_ROOTS:
        return "godot_authored_keep", "Gameplay interaction area."
    if path == "Interior/InteriorVolume" or path == "Interior/InteriorVolume/CollisionShape3D":
        return "godot_authored_keep", "Runtime interior gravity/attachment volume."
    if nearest_interaction_root(path) and node_type == "CollisionShape3D":
        return "godot_authored_keep", "Interaction collision shape tied to gameplay area."

    if instance_id in EXTERIOR_REFERENCE_INSTANCE_IDS:
        return "godot_authored_should_migrate", "Exterior/reference visual instance should be package-owned or replaced by package exterior."
    if node_type == "CollisionShape3D" and path not in {"Interior/InteriorVolume/CollisionShape3D"}:
        return "godot_authored_should_migrate", "Physical collision should become package-authored collision data."
    if node_type == "MeshInstance3D" and mesh_id:
        if nearest_interaction_root(path):
            return "godot_authored_should_migrate", "Interaction visual fixture should migrate to package art while gameplay parent remains."
        return "godot_authored_should_migrate", "Manual mesh visual should migrate to Blender/package art."
    if shape_id and node_type == "CollisionShape3D":
        return "godot_authored_should_migrate", "Manual shape resource should migrate to package collision."

    if node_type == "Node3D" and path in {"Interior", "Interior/Floor", "Interior/LeftWall", "Interior/RightWall", "Interior/Ribs", "Interior/Cockpit", "ExteriorHatchUndersideLights", "Markers"}:
        return "ambiguous", "Container node; ownership depends on child migration boundary."
    if node_type == "Node3D" and nearest_interaction_root(path):
        return "ambiguous", "Interaction visual container; gameplay root should stay but visual children can migrate."
    if node_type == "Node":
        return "godot_authored_keep", "Runtime helper node."

    return "ambiguous", "No explicit migration rule matched."


def enrich_node(
    node: dict[str, object],
    ext_resources: dict[str, dict[str, str]],
    sub_resources: dict[str, dict[str, str]],
) -> dict[str, object]:
    props = node["properties"]
    assert isinstance(props, dict)
    category, recommendation = classify_node(node)
    resources = {}
    for property_name in ["script", "mesh", "shape", "material_override"]:
        rid = resource_id(props.get(property_name))
        if rid is None:
            continue
        resources[property_name] = {
            "id": rid,
            "external": ext_resources.get(rid),
            "sub_resource": sub_resources.get(rid),
        }
    instance_id = node.get("instance")
    if instance_id:
        resources["instance"] = {
            "id": instance_id,
            "external": ext_resources.get(str(instance_id)),
        }
    return {
        "path": node["path"],
        "name": node["name"],
        "type": node["type"],
        "parent": node["parent"],
        "line": node["line"],
        "category": category,
        "recommendation": recommendation,
        "resources": resources,
    }


def write_json(path: Path, records: list[dict[str, object]]) -> None:
    counts = Counter(str(record["category"]) for record in records)
    by_type = Counter(str(record["type"]) for record in records)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "scene": str(DEFAULT_SCENE.relative_to(ROOT)),
                "node_count": len(records),
                "category_counts": dict(sorted(counts.items())),
                "type_counts": dict(sorted(by_type.items())),
                "nodes": records,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def write_markdown(path: Path, records: list[dict[str, object]]) -> None:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in records:
        grouped[str(record["category"])].append(record)

    lines = [
        "# ShuttleA Godot Node Audit",
        "",
        "This report classifies `scenes/ship/Ship.tscn` nodes by ownership and migration recommendation.",
        "",
        "## Summary",
        "",
    ]
    for category, items in sorted(grouped.items()):
        lines.append(f"- `{category}`: {len(items)} node(s)")
    lines.append("")

    labels = {
        "package_driven_now": "Package-Driven Now",
        "godot_authored_keep": "Godot-Authored Keep",
        "godot_authored_should_migrate": "Godot-Authored Should Migrate",
        "ambiguous": "Ambiguous",
    }
    for category in ["package_driven_now", "godot_authored_keep", "godot_authored_should_migrate", "ambiguous"]:
        items = grouped.get(category, [])
        lines.extend([f"## {labels[category]}", ""])
        if not items:
            lines.extend(["None.", ""])
            continue
        for record in items:
            lines.append(f"- `{record['path']}` `{record['type']}`: {record['recommendation']}")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    ext_resources, sub_resources, nodes = parse_scene(args.scene)
    records = [enrich_node(node, ext_resources, sub_resources) for node in nodes]
    write_json(args.json, records)
    write_markdown(args.markdown, records)
    counts = Counter(str(record["category"]) for record in records)
    print(f"Wrote {args.json}")
    print(f"Wrote {args.markdown}")
    print(
        "Node audit: "
        + ", ".join(f"{category}={count}" for category, count in sorted(counts.items()))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
