#!/usr/bin/env python3
"""Generate a colocated Godot review scene for MX01 collision artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
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


def write_scene(path: Path, config: dict) -> None:
    normalized = config["normalization_outputs"]["normalized_obj"]
    boundary = config["simplification_outputs"]["simplified_obj"]
    interior = config["interior_collision_outputs"]["collision_obj"]
    dynamic = config["dynamic_collision_outputs"]["collision_obj"]
    lines = [
        '[gd_scene load_steps=5 format=3]',
        '',
        f'[ext_resource type="ArrayMesh" path="{res(normalized)}" id="1_skin"]',
        f'[ext_resource type="ArrayMesh" path="{res(boundary)}" id="2_boundary"]',
        f'[ext_resource type="ArrayMesh" path="{res(interior)}" id="3_interior"]',
        f'[ext_resource type="ArrayMesh" path="{res(dynamic)}" id="4_dynamic"]',
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
        '[node name="DynamicCollision_FirstPass" type="MeshInstance3D" parent="."]',
        'visible = false',
        'mesh = ExtResource("4_dynamic")',
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


def write_playable_scene(path: Path, config: dict, collision: dict) -> None:
    normalized = config["normalization_outputs"]["normalized_obj"]
    interior = config["interior_collision_outputs"]["collision_obj"]
    dynamic = config["dynamic_collision_outputs"]["collision_obj"]
    ship_world_y = 205.0
    # Keep the player clear of the lower-to-mid connector footprint.
    player_spawn = [8.0, ship_world_y - 3.45, -36.5]
    lines = [
        f'[gd_scene load_steps={8 + len(collision["objects"])} format=3]',
        '',
        '[ext_resource type="PackedScene" path="res://scenes/planets/PlanetBody.tscn" id="1_planet"]',
        '[ext_resource type="PackedScene" path="res://scenes/player/Player.tscn" id="2_player"]',
        '[ext_resource type="PackedScene" path="res://scenes/ui/GravityDebugOverlay.tscn" id="3_overlay"]',
        f'[ext_resource type="ArrayMesh" path="{res(normalized)}" id="4_skin"]',
        f'[ext_resource type="ArrayMesh" path="{res(interior)}" id="5_interior_mesh"]',
        f'[ext_resource type="ArrayMesh" path="{res(dynamic)}" id="6_dynamic_mesh"]',
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
            '[node name="DynamicCollisionVisual" type="MeshInstance3D" parent="ShipRoot"]',
            'visible = false',
            'mesh = ExtResource("6_dynamic_mesh")',
            '',
            '[node name="InteriorCollisionBody" type="StaticBody3D" parent="ShipRoot"]',
            '',
        ]
    )
    for index, obj in enumerate(collision["objects"], start=1):
        cx, cy, cz = obj["center"]
        lines.extend(
            [
                f'[node name="{obj["name"]}" type="CollisionShape3D" parent="ShipRoot/InteriorCollisionBody"]',
                f'position = Vector3({cx}, {cy}, {cz})',
                f'shape = SubResource("BoxShape3D_mx01_{index}")',
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
    collision = load_json(collision_path)
    write_playable_scene(playable_scene_path, config, collision)
    referenced = [
        ROOT / config["normalization_outputs"]["normalized_obj"],
        ROOT / config["simplification_outputs"]["simplified_obj"],
        ROOT / config["interior_collision_outputs"]["collision_obj"],
        ROOT / config["dynamic_collision_outputs"]["collision_obj"],
        collision_path,
    ]
    report = {
        "ship_id": config["ship_id"],
        "method": "godot_collision_review_scene_v1",
        "status": "PASS",
        "referenced_artifacts": [{"path": rel(path), "sha256": sha256(path)} for path in referenced],
        "config": {"path": rel(config_path), "sha256": sha256(config_path), "effective_values": config},
        "tools": {
            "generate_mx01_review_scene.py": {"path": rel(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())}
        },
        "outputs": {"review_scene": rel(scene_path), "playable_scene": rel(playable_scene_path), "report_json": rel(report_json), "report_md": rel(report_md)},
        "notes": "The review scene references generated OBJ assets. The playable scene instances the real Player scene and generated StaticBody3D box collision from MX01 interior collision JSON.",
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
