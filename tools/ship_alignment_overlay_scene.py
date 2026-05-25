#!/usr/bin/env python3
"""Generate a Godot overlay scene from measured ShuttleA alignment JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIT_TARGETS_JSON_PATH = ROOT / "reports/ship_fit_targets.json"
OVERLAY_SCENE_PATH = ROOT / "scenes/debug/generated/ShipAlignmentOverlay.tscn"

TARGET_COLORS = {
    "Cockpit / canopy": "Color(1, 0.45, 0.05, 0.18)",
    "Cabin interior envelope": "Color(0.05, 0.35, 1, 0.12)",
    "Floor / walk path": "Color(0.1, 0.85, 0.35, 0.18)",
    "Rear hatch zone": "Color(1, 0.05, 0.65, 0.18)",
}

ACTUAL_COLORS = {
    "Interior volume vs cabin": "Color(0.25, 0.55, 1, 0.22)",
    "Floor plate vs walk path": "Color(0.3, 1, 0.55, 0.24)",
    "Exterior hatch vs rear zone": "Color(1, 1, 1, 0.25)",
    "Interior hatch vs rear zone": "Color(0.85, 0.35, 1, 0.25)",
    "Pilot cushion vs cockpit": "Color(1, 0.85, 0.1, 0.28)",
    "Interior canopy glass vs cockpit": "Color(0, 0.9, 1, 0.24)",
}


def vec3(values: object) -> str:
    if not isinstance(values, list) or len(values) != 3:
        raise ValueError(f"Expected Vector3 list, got {values!r}")
    return f"Vector3({values[0]}, {values[1]}, {values[2]})"


def clean_name(value: str) -> str:
    return (
        value.replace("/", " ")
        .replace("-", " ")
        .replace("_", " ")
        .replace("  ", " ")
        .title()
        .replace(" ", "")
    )


def material_block(name: str, color: str) -> str:
    return (
        f'[sub_resource type="StandardMaterial3D" id="{name}"]\n'
        "transparency = 1\n"
        "shading_mode = 0\n"
        "no_depth_test = true\n"
        f"albedo_color = {color}\n"
    )


def box_mesh_block(mesh_id: str, size: object) -> str:
    return (
        f'[sub_resource type="BoxMesh" id="{mesh_id}"]\n'
        f"size = {vec3(size)}\n"
    )


def mesh_node(name: str, center: object, mesh_id: str, material_id: str, parent: str) -> str:
    return (
        f'[node name="{name}" type="MeshInstance3D" parent="{parent}"]\n'
        f"position = {vec3(center)}\n"
        f'mesh = SubResource("{mesh_id}")\n'
        f'material_override = SubResource("{material_id}")\n'
        "cast_shadow = 0\n"
    )


def label_node(name: str, text: str, center: object, parent: str) -> str:
    if not isinstance(center, list) or len(center) != 3:
        raise ValueError(center)
    label_position = [center[0], center[1] + 0.08, center[2]]
    safe_text = text.replace('"', "'")
    return (
        f'[node name="{name}Label" type="Label3D" parent="{parent}"]\n'
        f"text = \"{safe_text}\"\n"
        f"position = {vec3(label_position)}\n"
        "font_size = 22\n"
        "billboard = 1\n"
        "no_depth_test = true\n"
        "modulate = Color(1, 1, 1, 0.86)\n"
    )


def write_overlay(data: dict[str, object]) -> None:
    OVERLAY_SCENE_PATH.parent.mkdir(parents=True, exist_ok=True)

    material_ids: dict[str, str] = {}
    material_blocks: list[str] = []
    mesh_blocks: list[str] = []
    nodes: list[str] = []
    mesh_index = 1
    material_index = 1

    def material_id(key: str, color: str) -> str:
        nonlocal material_index
        if key not in material_ids:
            resource_id = f"OverlayMaterial{material_index}"
            material_index += 1
            material_ids[key] = resource_id
            material_blocks.append(material_block(resource_id, color))
        return material_ids[key]

    nodes.append('[node name="ShipAlignmentOverlay" type="Node3D"]\n')
    nodes.append('[node name="Targets" type="Node3D" parent="."]\n')
    nodes.append('[node name="Actuals" type="Node3D" parent="."]\n')

    targets = data.get("fit_targets", {})
    if isinstance(targets, dict):
        for target_name, bounds in targets.items():
            if not isinstance(bounds, dict):
                continue
            mesh_id = f"OverlayBox{mesh_index}"
            mesh_index += 1
            material = material_id(str(target_name), TARGET_COLORS.get(str(target_name), "Color(1, 1, 1, 0.16)"))
            node_name = clean_name(str(target_name))
            mesh_blocks.append(box_mesh_block(mesh_id, bounds["size"]))
            nodes.append(mesh_node(node_name, bounds["center"], mesh_id, material, "Targets"))
            nodes.append(label_node(node_name, str(target_name), bounds["center"], "Targets"))

    comparisons = data.get("fit_comparisons", [])
    if isinstance(comparisons, list):
        for comparison in comparisons:
            if not isinstance(comparison, dict):
                continue
            name = str(comparison.get("name", "Actual"))
            actual_bounds = comparison.get("actual_bounds")
            if not isinstance(actual_bounds, dict):
                continue
            mesh_id = f"OverlayBox{mesh_index}"
            mesh_index += 1
            material = material_id(name, ACTUAL_COLORS.get(name, "Color(1, 1, 1, 0.2)"))
            node_name = clean_name(name)
            mesh_blocks.append(box_mesh_block(mesh_id, actual_bounds["size"]))
            nodes.append(mesh_node(node_name, actual_bounds["center"], mesh_id, material, "Actuals"))
            nodes.append(label_node(node_name, name, actual_bounds["center"], "Actuals"))

    lines = ["[gd_scene load_steps=%d format=3]" % (1 + len(material_blocks) + len(mesh_blocks)), ""]
    for block in [*material_blocks, *mesh_blocks, *nodes]:
        lines.append(block.rstrip())
        lines.append("")
    OVERLAY_SCENE_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    check_mode = "--check" in sys.argv[1:]
    if not FIT_TARGETS_JSON_PATH.exists():
        print(f"FAIL: {FIT_TARGETS_JSON_PATH.relative_to(ROOT)} does not exist.", file=sys.stderr)
        return 1
    data = json.loads(FIT_TARGETS_JSON_PATH.read_text(encoding="utf-8"))
    write_overlay(data)
    print(f"Wrote {OVERLAY_SCENE_PATH.relative_to(ROOT)}")
    if check_mode and not OVERLAY_SCENE_PATH.exists():
        print("FAIL: overlay scene was not written.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
