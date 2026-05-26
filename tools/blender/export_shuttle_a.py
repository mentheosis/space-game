#!/usr/bin/env python3
"""Export the ShuttleA Blender source scene to Godot-ready artifacts."""

from __future__ import annotations

import json
import os
from pathlib import Path

import bpy


ROOT = Path(os.environ.get("SPACE_GAME_ROOT", Path.cwd())).resolve()
SOURCE_BLEND = ROOT / "assets/source/blender/ships/shuttle_a/shuttle_a_interior.blend"
OUT_DIR = ROOT / "assets/models/ship/shuttle_a"
REPORT_DIR = ROOT / "reports/ship_modeling"
INTERIOR_GLB = OUT_DIR / "shuttle_a_interior.glb"
COLLISION_GLB = OUT_DIR / "shuttle_a_collision.glb"
MARKERS_JSON = OUT_DIR / "shuttle_a_markers.json"
EXPORT_LOG = REPORT_DIR / "shuttle_a_export_report.json"

REQUIRED_COLLECTIONS = [
    "Reference_Exterior",
    "Interior_Render",
    "Interior_Glass",
    "Collision_Proxy",
    "Markers",
]

REQUIRED_MARKERS = [
    "InteriorSpawn",
    "SeatAnchor",
    "SeatExit",
    "PilotEye",
    "CanopyTarget",
    "HatchCenter",
]


def blender_to_godot(loc) -> list[float]:
    """Convert Blender Z-up coordinates back to project/Godot coordinates."""
    return [round(loc.x, 5), round(loc.z, 5), round(-loc.y, 5)]


def fail(message: str) -> None:
    raise RuntimeError(message)


def require_collection(name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.get(name)
    if collection is None:
        fail(f"Missing required collection: {name}")
    return collection


def descendants(collection: bpy.types.Collection) -> list[bpy.types.Object]:
    objects = list(collection.objects)
    for child in collection.children:
        objects.extend(descendants(child))
    return objects


def select_objects(objects: list[bpy.types.Object]) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    if objects:
        bpy.context.view_layer.objects.active = objects[0]


def export_glb(path: Path, objects: list[bpy.types.Object]) -> None:
    if not objects:
        fail(f"No objects selected for export: {path}")
    select_objects(objects)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_materials="EXPORT",
    )


def write_markers(markers_collection: bpy.types.Collection) -> dict[str, list[float]]:
    marker_objects = {obj.name: obj for obj in descendants(markers_collection)}
    missing = [name for name in REQUIRED_MARKERS if name not in marker_objects]
    if missing:
        fail(f"Missing required marker(s): {', '.join(missing)}")
    data = {
        name: list(marker_objects[name].get("godot_position", blender_to_godot(marker_objects[name].location)))
        for name in REQUIRED_MARKERS
    }
    MARKERS_JSON.parent.mkdir(parents=True, exist_ok=True)
    MARKERS_JSON.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def main() -> None:
    if not SOURCE_BLEND.exists():
        fail(f"Source blend is missing. Run scripts/bootstrap-shuttle-a-blender.sh first: {SOURCE_BLEND}")

    if Path(bpy.data.filepath).resolve() != SOURCE_BLEND:
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE_BLEND))

    collections = {name: require_collection(name) for name in REQUIRED_COLLECTIONS}
    render_objects = [
        obj
        for obj in descendants(collections["Interior_Render"]) + descendants(collections["Interior_Glass"])
        if obj.type in {"MESH", "EMPTY"}
    ]
    collision_objects = [
        obj
        for obj in descendants(collections["Collision_Proxy"])
        if obj.type == "MESH"
    ]

    export_glb(INTERIOR_GLB, render_objects)
    export_glb(COLLISION_GLB, collision_objects)
    markers = write_markers(collections["Markers"])

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_LOG.write_text(
        json.dumps(
            {
                "source_blend": str(SOURCE_BLEND.relative_to(ROOT)),
                "interior_glb": str(INTERIOR_GLB.relative_to(ROOT)),
                "collision_glb": str(COLLISION_GLB.relative_to(ROOT)),
                "markers_json": str(MARKERS_JSON.relative_to(ROOT)),
                "render_object_count": len(render_objects),
                "collision_object_count": len(collision_objects),
                "markers": markers,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {INTERIOR_GLB}")
    print(f"Wrote {COLLISION_GLB}")
    print(f"Wrote {MARKERS_JSON}")
    print(f"Wrote {EXPORT_LOG}")


if __name__ == "__main__":
    main()
