#!/usr/bin/env python3
"""Generate a colocated Godot review scene for MX01 collision artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SHIP_DIR = ROOT / "ships" / "MX01"
DEFAULT_CONFIG = SHIP_DIR / "config" / "mx01_collision_generation.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def res(path: str) -> str:
    return "res://" + path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resolve_config_path(config: dict, section: str, key: str) -> Path:
    return ROOT / config[section][key]


def resolve_root_path(path: str) -> Path:
    return ROOT / path


def load_ship_contract(config: dict) -> dict:
    contract_path = config.get("ship_contract")
    if not contract_path:
        return {"ship_id": config["ship_id"], "schema_version": 1, "hatches": []}
    return load_json(resolve_root_path(contract_path))


def fmt(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def connector_group_id(name: str) -> str | None:
    prefix = "COL_MX01_"
    if not name.startswith(prefix):
        return None
    core = name[len(prefix) :]
    for suffix in ("_lower_landing", "_upper_landing"):
        if core.endswith(suffix):
            return core[: -len(suffix)]
    marker = "_stair_tread_"
    if marker in core:
        return core.split(marker, 1)[0]
    return None


def stair_transition_support_aprons(collision: dict, config: dict) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for obj in collision["objects"]:
        if obj["role"] not in {"player_connector_landing", "player_connector_stair_tread"}:
            continue
        group_id = connector_group_id(obj["name"])
        if group_id is not None:
            groups.setdefault(group_id, []).append(obj)

    extension = float(config["player_capsule_radius"]) + 0.4
    aprons = []
    for group_id, objects in sorted(groups.items()):
        treads = [obj for obj in objects if obj["role"] == "player_connector_stair_tread"]
        landings = [obj for obj in objects if obj["role"] == "player_connector_landing"]
        if not treads or not landings:
            continue

        top_tread = max(treads, key=lambda obj: (float(obj["center"][1]) + float(obj["size"][1]) * 0.5, obj["name"]))
        lower_landing = min(landings, key=lambda obj: (float(obj["center"][1]) + float(obj["size"][1]) * 0.5, obj["name"]))
        upper_landing = max(landings, key=lambda obj: (float(obj["center"][1]) + float(obj["size"][1]) * 0.5, obj["name"]))
        top_center = [float(value) for value in top_tread["center"]]
        lower_center = [float(value) for value in lower_landing["center"]]
        upper_center = [float(value) for value in upper_landing["center"]]
        size = [float(value) for value in top_tread["size"]]

        dx = upper_center[0] - top_center[0]
        dz = upper_center[2] - top_center[2]
        if abs(dx) < 0.001 and abs(dz) < 0.001:
            dx = top_center[0] - lower_center[0]
            dz = top_center[2] - lower_center[2]
        if abs(dx) > abs(dz):
            axis = 0
            sign = 1.0 if dx >= 0.0 else -1.0
        else:
            axis = 2
            sign = 1.0 if dz >= 0.0 else -1.0

        center = top_center[:]
        center[axis] += sign * extension * 0.5
        size[axis] += extension
        aprons.append(
            {
                "name": f"COL_MX01_{group_id}_top_transition_support_apron",
                "center": [round(value, 6) for value in center],
                "size": [round(value, 6) for value in size],
                "source_tread": top_tread["name"],
            }
        )
    return aprons


def box_bounds(obj: dict) -> tuple[float, float, float, float, float, float]:
    cx, cy, cz = [float(value) for value in obj["center"]]
    sx, sy, sz = [float(value) for value in obj["size"]]
    return (cx - sx * 0.5, cx + sx * 0.5, cy - sy * 0.5, cy + sy * 0.5, cz - sz * 0.5, cz + sz * 0.5)


def overlaps_stair_transition_keepout(obj: dict, aprons: list[dict]) -> bool:
    if obj["role"] not in {"player_walkable_floor", "player_connector_landing"}:
        return False
    obj_x0, obj_x1, _obj_y0, obj_y1, obj_z0, obj_z1 = box_bounds(obj)
    for apron in aprons:
        apron_x0, apron_x1, _apron_y0, apron_y1, apron_z0, apron_z1 = box_bounds(apron)
        if abs(obj_y1 - apron_y1) > 0.18:
            continue
        overlap_x = min(obj_x1, apron_x1) - max(obj_x0, apron_x0)
        overlap_z = min(obj_z1, apron_z1) - max(obj_z0, apron_z0)
        if overlap_x > 0.04 and overlap_z > 0.04:
            return True
    return False


def split_floor_for_transition_keepouts(obj: dict, aprons: list[dict]) -> list[dict]:
    if obj["role"] != "player_walkable_floor":
        return [obj]

    obj_x0, obj_x1, obj_y0, obj_y1, obj_z0, obj_z1 = box_bounds(obj)
    rects = [(obj_x0, obj_x1, obj_z0, obj_z1)]
    min_thickness = 0.05
    for apron in aprons:
        apron_x0, apron_x1, _apron_y0, apron_y1, apron_z0, apron_z1 = box_bounds(apron)
        if abs(obj_y1 - apron_y1) > 0.18:
            continue
        next_rects = []
        for x0, x1, z0, z1 in rects:
            ix0 = max(x0, apron_x0)
            ix1 = min(x1, apron_x1)
            iz0 = max(z0, apron_z0)
            iz1 = min(z1, apron_z1)
            if ix1 - ix0 <= 0.04 or iz1 - iz0 <= 0.04:
                next_rects.append((x0, x1, z0, z1))
                continue
            pieces = [
                (x0, ix0, z0, z1),
                (ix1, x1, z0, z1),
                (ix0, ix1, z0, iz0),
                (ix0, ix1, iz1, z1),
            ]
            next_rects.extend(piece for piece in pieces if piece[1] - piece[0] >= min_thickness and piece[3] - piece[2] >= min_thickness)
        rects = next_rects

    if len(rects) == 1 and rects[0] == (obj_x0, obj_x1, obj_z0, obj_z1):
        return [obj]

    pieces = []
    cy = (obj_y0 + obj_y1) * 0.5
    sy = obj_y1 - obj_y0
    for index, (x0, x1, z0, z1) in enumerate(rects, start=1):
        pieces.append(
            {
                "name": f"{obj['name']}_transition_piece_{index:02d}",
                "role": obj["role"],
                "center": [round((x0 + x1) * 0.5, 6), round(cy, 6), round((z0 + z1) * 0.5, 6)],
                "size": [round(x1 - x0, 6), round(sy, 6), round(z1 - z0, 6)],
                "split_from": obj["name"],
            }
        )
    return pieces


def primary_collision_scene_objects(collision: dict, aprons: list[dict]) -> list[dict]:
    objects = []
    for obj in collision["objects"]:
        if obj["role"] == "player_connector_stair_tread":
            continue
        if obj["role"] == "player_connector_landing" and overlaps_stair_transition_keepout(obj, aprons):
            continue
        if obj["role"] == "player_walkable_floor":
            objects.extend(split_floor_for_transition_keepouts(obj, aprons))
            continue
        objects.append(obj)
    return objects


def hatch_ramp_supports(contract: dict) -> list[dict]:
    ramps = []
    for hatch in contract.get("hatches", []):
        ramp = hatch.get("ramp")
        if not ramp:
            continue
        aperture = hatch["aperture"]
        center = [float(value) for value in aperture["center"]]
        size = [float(value) for value in aperture["size"]]
        axis = ramp["axis"]
        direction = float(ramp["direction"])
        width = float(ramp["width"])
        length = float(ramp["length"])
        drop = float(ramp["drop"])
        thickness = float(ramp["thickness"])
        threshold_overlap = float(ramp.get("threshold_overlap", 0.0))
        start_y = center[1] - size[1] * 0.5 + 0.15
        angle = math.atan2(drop, length)
        if axis == "z":
            ramp_center = [center[0], start_y - drop * 0.5 - thickness * 0.5, center[2] + direction * (size[2] * 0.5 + length * 0.5 - threshold_overlap)]
            ramp_size = [width, thickness, length]
            rotation = [direction * angle, 0.0, 0.0]
        elif axis == "x":
            ramp_center = [center[0] + direction * (size[0] * 0.5 + length * 0.5 - threshold_overlap), start_y - drop * 0.5 - thickness * 0.5, center[2]]
            ramp_size = [length, thickness, width]
            rotation = [0.0, 0.0, -direction * angle]
        else:
            raise ValueError(f"Unsupported ramp axis for hatch {hatch['id']}: {axis}")
        ramps.append(
            {
                "name": f"COL_MX01_{hatch['id']}_ramp_support",
                "center": [round(value, 6) for value in ramp_center],
                "size": [round(value, 6) for value in ramp_size],
                "rotation": [round(value, 6) for value in rotation],
                "threshold_overlap": round(threshold_overlap, 6),
            }
        )
    return ramps


def write_scene(path: Path, config: dict) -> None:
    normalized = config["normalization_outputs"]["normalized_obj"]
    boundary = config["simplification_outputs"]["simplified_obj"]
    interior = config["interior_collision_outputs"]["collision_obj"]
    enclosure = config["interior_enclosure_outputs"]["enclosure_obj"]
    dynamic = config["dynamic_collision_outputs"]["collision_obj"]
    lines = [
        '[gd_scene load_steps=6 format=3]',
        '',
        f'[ext_resource type="ArrayMesh" path="{res(normalized)}" id="1_skin"]',
        f'[ext_resource type="ArrayMesh" path="{res(boundary)}" id="2_boundary"]',
        f'[ext_resource type="ArrayMesh" path="{res(interior)}" id="3_interior"]',
        f'[ext_resource type="ArrayMesh" path="{res(enclosure)}" id="4_enclosure"]',
        f'[ext_resource type="ArrayMesh" path="{res(dynamic)}" id="5_dynamic"]',
        '',
        '[node name="MX01CollisionReview" type="Node3D"]',
        '',
        '[node name="VisualSkin_Normalized" type="MeshInstance3D" parent="."]',
        'mesh = ExtResource("1_skin")',
        '',
        '[node name="BoundarySurface_Simplified" type="MeshInstance3D" parent="."]',
        'visible = false',
        'mesh = ExtResource("2_boundary")',
        '',
        '[node name="InteriorCollision_FirstPass" type="MeshInstance3D" parent="."]',
        'mesh = ExtResource("3_interior")',
        '',
        '[node name="InteriorEnclosure_SkinFitted" type="MeshInstance3D" parent="."]',
        'mesh = ExtResource("4_enclosure")',
        '',
        '[node name="DynamicCollision_FirstPass" type="MeshInstance3D" parent="."]',
        'visible = false',
        'mesh = ExtResource("5_dynamic")',
        '',
        '[node name="Camera3D" type="Camera3D" parent="."]',
        'transform = Transform3D(1, 0, 0, 0, 0.707107, 0.707107, 0, -0.707107, 0.707107, 0, 55, 125)',
        'current = true',
        '',
        '[node name="DirectionalLight3D" type="DirectionalLight3D" parent="."]',
        'transform = Transform3D(0.707107, -0.408248, 0.57735, 0, 0.816497, 0.57735, -0.707107, -0.408248, 0.57735, 0, 20, 0)',
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_playable_scene(path: Path, config: dict, collision: dict, enclosure: dict) -> None:
    normalized = config["normalization_outputs"]["normalized_obj"]
    interior = config["interior_collision_outputs"]["collision_obj"]
    enclosure_obj = config["interior_enclosure_outputs"]["enclosure_obj"]
    enclosure_collider_obj = config["interior_enclosure_outputs"]["collider_obj"]
    dynamic = config["dynamic_collision_outputs"]["collision_obj"]
    ship_world_y = 205.0
    # Keep the player clear of the lower-to-mid connector footprint.
    player_spawn = [8.0, ship_world_y - 3.45, -36.5]
    enclosure_primitives = enclosure.get("collision_primitives", [])
    ship_contract = load_ship_contract(config)
    ramp_supports = hatch_ramp_supports(ship_contract)
    stair_support_objects = [obj for obj in collision["objects"] if obj["role"] in {"player_connector_landing", "player_connector_stair_tread"}]
    stair_support_aprons = stair_transition_support_aprons(collision, config)
    primary_objects = primary_collision_scene_objects(collision, stair_support_aprons)
    split_primary_objects = [obj for obj in primary_objects if "split_from" in obj]
    stair_transition_floor_keepout_count = sum(
        1 for obj in collision["objects"] if overlaps_stair_transition_keepout(obj, stair_support_aprons)
    )
    lines = [
        f'[gd_scene load_steps={12 + len(collision["objects"]) + len(split_primary_objects) + len(stair_support_aprons) + (len(ramp_supports) * 2) + len(enclosure_primitives)} format=3]',
        '',
        '[ext_resource type="PackedScene" path="res://scenes/planets/PlanetBody.tscn" id="1_planet"]',
        '[ext_resource type="PackedScene" path="res://scenes/player/Player.tscn" id="2_player"]',
        '[ext_resource type="PackedScene" path="res://scenes/ui/GravityDebugOverlay.tscn" id="3_overlay"]',
        f'[ext_resource type="ArrayMesh" path="{res(normalized)}" id="4_skin"]',
        f'[ext_resource type="ArrayMesh" path="{res(interior)}" id="5_interior_mesh"]',
        f'[ext_resource type="ArrayMesh" path="{res(enclosure_obj)}" id="6_enclosure_mesh"]',
        f'[ext_resource type="ArrayMesh" path="{res(dynamic)}" id="7_dynamic_mesh"]',
        f'[ext_resource type="ArrayMesh" path="{res(enclosure_collider_obj)}" id="8_enclosure_collider_mesh"]',
        '',
        '[sub_resource type="StandardMaterial3D" id="StandardMaterial3D_enclosure_collider"]',
        'transparency = 1',
        'albedo_color = Color(0.16, 0.82, 1, 0.72)',
        'roughness = 0.8',
        '',
        '[sub_resource type="StandardMaterial3D" id="StandardMaterial3D_hatch_ramp"]',
        'albedo_color = Color(0.86, 0.78, 0.58, 1)',
        'roughness = 0.72',
        '',
        '[sub_resource type="ProceduralSkyMaterial" id="ProceduralSkyMaterial_space"]',
        'sky_top_color = Color(0.004, 0.008, 0.02, 1)',
        'sky_horizon_color = Color(0.02, 0.025, 0.04, 1)',
        'ground_bottom_color = Color(0.004, 0.008, 0.02, 1)',
        'ground_horizon_color = Color(0.02, 0.025, 0.04, 1)',
        'sun_angle_max = 2.0',
        '',
        '[sub_resource type="Sky" id="Sky_space"]',
        'sky_material = SubResource("ProceduralSkyMaterial_space")',
        '',
        '[sub_resource type="Environment" id="Environment_space"]',
        'background_mode = 2',
        'sky = SubResource("Sky_space")',
        'ambient_light_source = 3',
        'ambient_light_color = Color(0.45, 0.52, 0.62, 1)',
        'ambient_light_energy = 0.8',
        'tonemap_mode = 2',
        '',
    ]
    for index, obj in enumerate(collision["objects"], start=1):
        sx, sy, sz = obj["size"]
        lines.extend(
            [
                f'[sub_resource type="BoxShape3D" id="BoxShape3D_mx01_{index}"]',
                f'size = Vector3({sx}, {sy}, {sz})',
                '',
            ]
        )
    for index, obj in enumerate(enclosure_primitives, start=1):
        sx, sy, sz = obj["size"]
        lines.extend(
            [
                f'[sub_resource type="BoxShape3D" id="BoxShape3D_mx01_enclosure_{index}"]',
                f'size = Vector3({sx}, {sy}, {sz})',
                '',
            ]
        )
    for index, obj in enumerate(stair_support_aprons, start=1):
        sx, sy, sz = obj["size"]
        lines.extend(
            [
                f'[sub_resource type="BoxShape3D" id="BoxShape3D_mx01_stair_support_apron_{index}"]',
                f'size = Vector3({sx}, {sy}, {sz})',
                '',
            ]
        )
    for index, obj in enumerate(ramp_supports, start=1):
        sx, sy, sz = obj["size"]
        lines.extend(
            [
                f'[sub_resource type="BoxShape3D" id="BoxShape3D_mx01_hatch_ramp_support_{index}"]',
                f'size = Vector3({sx}, {sy}, {sz})',
                '',
            ]
        )
    for index, obj in enumerate(ramp_supports, start=1):
        sx, sy, sz = obj["size"]
        lines.extend(
            [
                f'[sub_resource type="BoxMesh" id="BoxMesh_mx01_hatch_ramp_visual_{index}"]',
                f'size = Vector3({sx}, {sy}, {sz})',
                '',
            ]
        )
    for index, obj in enumerate(split_primary_objects, start=1):
        sx, sy, sz = obj["size"]
        lines.extend(
            [
                f'[sub_resource type="BoxShape3D" id="BoxShape3D_mx01_primary_split_{index}"]',
                f'size = Vector3({sx}, {sy}, {sz})',
                '',
            ]
        )
    lines.extend(
        [
            '[node name="MX01PlayableInspection" type="Node3D"]',
            '',
            '[node name="PlanetBody" parent="." instance=ExtResource("1_planet")]',
            '',
            '[node name="ShipRoot" type="Node3D" parent="."]',
            f'position = Vector3(0, {ship_world_y}, 0)',
            '',
            '[node name="VisualSkin" type="MeshInstance3D" parent="ShipRoot"]',
            'mesh = ExtResource("4_skin")',
            '',
            '[node name="InteriorCollisionVisual" type="MeshInstance3D" parent="ShipRoot"]',
            'mesh = ExtResource("5_interior_mesh")',
            '',
            '[node name="InteriorEnclosureVisual" type="MeshInstance3D" parent="ShipRoot"]',
            'visible = false',
            'mesh = ExtResource("6_enclosure_mesh")',
            '',
            '[node name="InteriorEnclosureColliderVisual" type="MeshInstance3D" parent="ShipRoot"]',
            'transparency = 0.18',
            'mesh = ExtResource("8_enclosure_collider_mesh")',
            'material_override = SubResource("StandardMaterial3D_enclosure_collider")',
            '',
            '[node name="DynamicCollisionVisual" type="MeshInstance3D" parent="ShipRoot"]',
            'visible = false',
            'mesh = ExtResource("7_dynamic_mesh")',
            '',
            '[node name="HatchRampVisuals" type="Node3D" parent="ShipRoot"]',
            '',
            '[node name="InteriorCollisionBody" type="StaticBody3D" parent="ShipRoot"]',
            'collision_layer = 1',
            'collision_mask = 1',
            '',
        ]
    )
    for index, obj in enumerate(ramp_supports, start=1):
        cx, cy, cz = obj["center"]
        rx, ry, rz = obj["rotation"]
        visual_name = obj["name"].replace("COL_MX01_", "VIS_MX01_")
        lines.extend(
            [
                f'[node name="{visual_name}" type="MeshInstance3D" parent="ShipRoot/HatchRampVisuals"]',
                f'position = Vector3({cx}, {cy}, {cz})',
                f'rotation = Vector3({rx}, {ry}, {rz})',
                f'mesh = SubResource("BoxMesh_mx01_hatch_ramp_visual_{index}")',
                'material_override = SubResource("StandardMaterial3D_hatch_ramp")',
                '',
            ]
        )
    original_shape_index_by_name = {obj["name"]: index for index, obj in enumerate(collision["objects"], start=1)}
    split_shape_index_by_name = {obj["name"]: index for index, obj in enumerate(split_primary_objects, start=1)}
    for obj in primary_objects:
        cx, cy, cz = obj["center"]
        if "split_from" in obj:
            shape_id = f'BoxShape3D_mx01_primary_split_{split_shape_index_by_name[obj["name"]]}'
        else:
            shape_id = f'BoxShape3D_mx01_{original_shape_index_by_name[obj["name"]]}'
        lines.extend(
            [
                f'[node name="{obj["name"]}" type="CollisionShape3D" parent="ShipRoot/InteriorCollisionBody"]',
                f'position = Vector3({cx}, {cy}, {cz})',
                f'shape = SubResource("{shape_id}")',
                '',
            ]
        )
    lines.extend(
        [
            '[node name="WalkableSupportSurfaces" type="StaticBody3D" parent="ShipRoot"]',
            'collision_layer = 128',
            'collision_mask = 0',
            '',
        ]
    )
    for index, obj in enumerate(collision["objects"], start=1):
        if obj["role"] not in {"player_connector_landing", "player_connector_stair_tread"}:
            continue
        cx, cy, cz = obj["center"]
        suffix = "_support" if obj["role"] == "player_connector_stair_tread" else "_landing_support"
        lines.extend(
            [
                f'[node name="{obj["name"]}{suffix}" type="CollisionShape3D" parent="ShipRoot/WalkableSupportSurfaces"]',
                f'position = Vector3({cx}, {cy}, {cz})',
                f'shape = SubResource("BoxShape3D_mx01_{index}")',
                '',
            ]
        )
    for index, obj in enumerate(stair_support_aprons, start=1):
        cx, cy, cz = obj["center"]
        lines.extend(
            [
                f'[node name="{obj["name"]}" type="CollisionShape3D" parent="ShipRoot/WalkableSupportSurfaces"]',
                f'position = Vector3({cx}, {cy}, {cz})',
                f'shape = SubResource("BoxShape3D_mx01_stair_support_apron_{index}")',
                '',
            ]
        )
    for index, obj in enumerate(ramp_supports, start=1):
        cx, cy, cz = obj["center"]
        rx, ry, rz = obj["rotation"]
        lines.extend(
            [
                f'[node name="{obj["name"]}" type="CollisionShape3D" parent="ShipRoot/WalkableSupportSurfaces"]',
                f'position = Vector3({cx}, {cy}, {cz})',
                f'rotation = Vector3({rx}, {ry}, {rz})',
                f'shape = SubResource("BoxShape3D_mx01_hatch_ramp_support_{index}")',
                '',
            ]
        )
    lines.extend(
        [
            '[node name="InteriorEnclosureBody" type="StaticBody3D" parent="ShipRoot"]',
            'collision_layer = 1',
            'collision_mask = 1',
            '',
        ]
    )
    for index, obj in enumerate(enclosure_primitives, start=1):
        cx, cy, cz = obj["center"]
        rotation_y = float(obj.get("rotation_y", 0.0))
        lines.extend(
            [
                f'[node name="{obj["name"]}" type="CollisionShape3D" parent="ShipRoot/InteriorEnclosureBody"]',
                f'position = Vector3({cx}, {cy}, {cz})',
                f'rotation = Vector3(0, {rotation_y}, 0)',
                f'shape = SubResource("BoxShape3D_mx01_enclosure_{index}")',
                '',
            ]
        )
    lines.extend(
        [
            '[node name="Player" parent="." instance=ExtResource("2_player")]',
            f'position = Vector3({player_spawn[0]}, {player_spawn[1]}, {player_spawn[2]})',
            '',
            '[node name="DirectionalLight3D" type="DirectionalLight3D" parent="."]',
            'transform = Transform3D(0.866025, -0.353553, 0.353553, 0, 0.707107, 0.707107, -0.5, -0.612372, 0.612372, 0, 120, 0)',
            'light_energy = 3.2',
            'shadow_enabled = true',
            '',
            '[node name="FillLight" type="OmniLight3D" parent="."]',
            'position = Vector3(0, 215, -20)',
            'light_energy = 2.2',
            'omni_range = 90.0',
            '',
            '[node name="WorldEnvironment" type="WorldEnvironment" parent="."]',
            'environment = SubResource("Environment_space")',
            '',
            '[node name="GravityDebugOverlay" parent="." instance=ExtResource("3_overlay")]',
            'visible = false',
            'PlayerPath = NodePath("../Player")',
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_markdown(path: Path, report: dict) -> None:
    lines = [
        "# MX01 Scene Report",
        "",
        f"- Review scene: `{report['outputs']['review_scene']}`",
        f"- Playable scene: `{report['outputs']['playable_scene']}`",
        f"- Status: `{report['status']}`",
        f"- Stair walkable support shapes: `{report.get('counts', {}).get('stair_walkable_support_shapes', 0)}`",
        f"- Stair transition support aprons: `{report.get('counts', {}).get('stair_transition_support_aprons', 0)}`",
        f"- Hatch ramp support shapes: `{report.get('counts', {}).get('hatch_ramp_support_shapes', 0)}`",
        f"- Visible hatch ramp meshes: `{report.get('counts', {}).get('visible_hatch_ramp_meshes', 0)}`",
        f"- Stair transition floor keepout shapes: `{report.get('counts', {}).get('stair_transition_floor_keepout_shapes', 0)}`",
        "",
        "## Referenced Artifacts",
        "",
    ]
    for item in report["referenced_artifacts"]:
        lines.append(f"- `{item['path']}` sha256=`{item['sha256']}`")
    lines.extend(["", "## Notes", "", report["notes"]])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    config_path = args.config.resolve()
    config = load_json(config_path)
    scene_path = resolve_config_path(config, "scene_outputs", "review_scene")
    playable_scene_path = resolve_config_path(config, "scene_outputs", "playable_scene")
    report_json = resolve_config_path(config, "scene_outputs", "report_json")
    report_md = resolve_config_path(config, "scene_outputs", "report_md")
    manifest_json = resolve_config_path(config, "scene_outputs", "manifest_json")

    write_scene(scene_path, config)
    collision_path = resolve_config_path(config, "interior_collision_outputs", "collision_json")
    enclosure_path = resolve_config_path(config, "interior_enclosure_outputs", "enclosure_json")
    collision = load_json(collision_path)
    enclosure = load_json(enclosure_path)
    write_playable_scene(playable_scene_path, config, collision, enclosure)
    ship_contract = load_ship_contract(config)
    stair_support_count = sum(1 for obj in collision["objects"] if obj["role"] in {"player_connector_landing", "player_connector_stair_tread"})
    stair_support_apron_count = len(stair_transition_support_aprons(collision, config))
    hatch_ramp_support_count = len(hatch_ramp_supports(ship_contract))
    primary_objects = primary_collision_scene_objects(collision, stair_transition_support_aprons(collision, config))
    stair_transition_floor_keepout_count = sum(
        1 for obj in collision["objects"] if overlaps_stair_transition_keepout(obj, stair_transition_support_aprons(collision, config))
    )
    referenced = [
        ROOT / config["normalization_outputs"]["normalized_obj"],
        ROOT / config["simplification_outputs"]["simplified_obj"],
        ROOT / config["interior_collision_outputs"]["collision_obj"],
        ROOT / config["interior_enclosure_outputs"]["enclosure_obj"],
        ROOT / config["dynamic_collision_outputs"]["collision_obj"],
        collision_path,
        enclosure_path,
    ]
    report = {
        "ship_id": config["ship_id"],
        "method": "godot_collision_review_scene_v1",
        "status": "PASS",
        "counts": {
            "stair_walkable_support_shapes": stair_support_count,
            "stair_transition_support_aprons": stair_support_apron_count,
            "hatch_ramp_support_shapes": hatch_ramp_support_count,
            "visible_hatch_ramp_meshes": hatch_ramp_support_count,
            "stair_transition_floor_keepout_shapes": stair_transition_floor_keepout_count,
            "split_primary_floor_shapes": sum(1 for obj in primary_objects if "split_from" in obj),
        },
        "referenced_artifacts": [{"path": rel(path), "sha256": sha256(path)} for path in referenced],
        "config": {"path": rel(config_path), "sha256": sha256(config_path), "effective_values": config},
        "tools": {
            "generate_mx01_review_scene.py": {"path": rel(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())}
        },
        "outputs": {"review_scene": rel(scene_path), "playable_scene": rel(playable_scene_path), "report_json": rel(report_json), "report_md": rel(report_md)},
        "notes": "The review scene references generated OBJ assets. The playable scene instances the real Player scene, Stage 7A StaticBody3D box collision from MX01 interior collision JSON, Stage 7A stair treads as nonblocking walkable support surfaces on physics layer 128, and Stage 7B controller-safe BoxShape3D enclosure primitives from MX01 interior enclosure JSON.",
    }
    write_json(report_json, report)
    write_markdown(report_md, report)
    write_json(
        manifest_json,
        {
            "ship_id": config["ship_id"],
            "stage": "review_scene_generation",
            "config": report["config"],
            "outputs": {
                "review_scene": rel(scene_path),
                "review_scene_sha256": sha256(scene_path),
                "playable_scene": rel(playable_scene_path),
                "playable_scene_sha256": sha256(playable_scene_path),
                "report_json": rel(report_json),
                "report_md": rel(report_md),
            },
            "referenced_artifacts": report["referenced_artifacts"],
            "tools": report["tools"],
        },
    )
    print(f"Wrote {rel(scene_path)}")
    print(f"Wrote {rel(playable_scene_path)}")
    print(f"Wrote {rel(report_json)}")
    print(f"Wrote {rel(report_md)}")
    print(f"Wrote {rel(manifest_json)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
