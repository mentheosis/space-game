#!/usr/bin/env python3
"""Create shuttle_p3 by preserving only the accepted prototype exterior skin."""

from __future__ import annotations

import json
import os
from pathlib import Path

import bpy


ROOT = Path(os.environ.get("SPACE_GAME_ROOT", Path.cwd())).resolve()
SOURCE_BLEND = ROOT / "assets/source/blender/ships/prototype_shuttle/prototype_shuttle.blend"
OUT_DIR = ROOT / "assets/source/blender/ships/shuttle_p3"
OUT_BLEND = OUT_DIR / "shuttle_p3.blend"
REPORT_DIR = ROOT / "reports/ship_pipeline/shuttle_p3_layout_review"
BOOTSTRAP_REPORT = REPORT_DIR / "shuttle_p3_bootstrap_report.json"

STANDARD_COLLECTIONS = [
    "Exterior",
    "Interior",
    "Collision",
    "Markers",
    "Lights",
    "ReviewCameras",
    "ScaleProxies",
    "Disabled_Source",
]


def descendants(collection: bpy.types.Collection) -> list[bpy.types.Object]:
    objects = list(collection.objects)
    for child in collection.children:
        objects.extend(descendants(child))
    return objects


def collection_tree_names(collection: bpy.types.Collection) -> set[str]:
    names = {collection.name}
    for child in collection.children:
        names.update(collection_tree_names(child))
    return names


def mesh_triangle_count(obj: bpy.types.Object) -> int:
    if obj.type != "MESH" or obj.data is None:
        return 0
    obj.data.calc_loop_triangles()
    return len(obj.data.loop_triangles)


def main() -> None:
    if not SOURCE_BLEND.exists():
        raise RuntimeError(f"Missing accepted prototype source blend: {SOURCE_BLEND}")

    bpy.ops.wm.open_mainfile(filepath=str(SOURCE_BLEND))
    exterior = bpy.data.collections.get("Exterior")
    if exterior is None:
        raise RuntimeError("Prototype source has no Exterior collection")

    exterior_tree = collection_tree_names(exterior)
    preserved_objects = [obj.name for obj in descendants(exterior) if obj.type == "MESH"]
    removed_objects: list[str] = []

    for obj in list(bpy.data.objects):
        users_in_exterior = any(collection.name in exterior_tree for collection in obj.users_collection)
        if not users_in_exterior:
            removed_objects.append(obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)

    for collection in list(bpy.data.collections):
        if collection.name not in exterior_tree and collection.name not in STANDARD_COLLECTIONS:
            bpy.data.collections.remove(collection)

    for name in STANDARD_COLLECTIONS:
        if bpy.data.collections.get(name) is None:
            bpy.context.scene.collection.children.link(bpy.data.collections.new(name))

    # Keep milestone-one source intentionally empty outside the preserved skin.
    for name in ["Interior", "Collision", "Markers", "Lights", "ReviewCameras", "ScaleProxies"]:
        coll = bpy.data.collections.get(name)
        if coll is None:
            continue
        for obj in list(descendants(coll)):
            removed_objects.append(obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)

    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.name = "shuttle_p3_skin_only"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))

    exterior_after = bpy.data.collections.get("Exterior")
    exterior_meshes = [obj for obj in descendants(exterior_after) if obj.type == "MESH"] if exterior_after else []
    report = {
        "schema_version": 1,
        "ship_id": "shuttle_p3",
        "source": str(SOURCE_BLEND.relative_to(ROOT)),
        "output_blend": str(OUT_BLEND.relative_to(ROOT)),
        "reuse_boundary": "Accepted prototype exterior skin only; all interior/collision/furniture/lighting discarded.",
        "preserved_mesh_count": len(exterior_meshes),
        "preserved_triangle_count": sum(mesh_triangle_count(obj) for obj in exterior_meshes),
        "preserved_objects": sorted(obj.name for obj in exterior_meshes),
        "removed_object_count": len(set(removed_objects)),
        "removed_objects": sorted(set(removed_objects)),
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    BOOTSTRAP_REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {OUT_BLEND}")
    print(f"Wrote {BOOTSTRAP_REPORT}")


if __name__ == "__main__":
    main()
