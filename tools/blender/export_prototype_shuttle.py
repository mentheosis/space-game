#!/usr/bin/env python3
"""Export the prototype shuttle Blender blockout package."""

from __future__ import annotations

import json
import os
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(os.environ.get("SPACE_GAME_ROOT", Path.cwd())).resolve()
SOURCE_BLEND = ROOT / "assets/source/blender/ships/prototype_shuttle/prototype_shuttle.blend"
SOURCE_DIR = SOURCE_BLEND.parent
OUT_DIR = ROOT / "assets/models/ship/prototype_shuttle"
REPORT_DIR = ROOT / "reports/ship_modeling"
EXTERIOR_GLB = OUT_DIR / "prototype_shuttle_exterior.glb"
INTERIOR_GLB = OUT_DIR / "prototype_shuttle_interior.glb"
COLLISION_GLB = OUT_DIR / "prototype_shuttle_collision.glb"
MARKERS_JSON = OUT_DIR / "prototype_shuttle_markers.json"
ASSET_REPORT_JSON = OUT_DIR / "prototype_shuttle_asset_report.json"
MATERIAL_REPORT_JSON = OUT_DIR / "prototype_shuttle_material_report.json"
LIGHT_REPORT_JSON = OUT_DIR / "prototype_shuttle_light_report.json"
SCALE_PROXY_REPORT_JSON = OUT_DIR / "prototype_shuttle_scale_proxy_report.json"
COLLISION_LAYOUT_REPORT_JSON = OUT_DIR / "prototype_shuttle_collision_layout_report.json"
EXPORT_LOG = REPORT_DIR / "prototype_shuttle_export_report.json"
MARKER_CONTRACT = SOURCE_DIR / "prototype_shuttle_marker_contract.json"
LIGHT_CONTRACT = SOURCE_DIR / "prototype_shuttle_light_contract.json"
SCALE_PROXY_CONTRACT = SOURCE_DIR / "prototype_shuttle_scale_proxy_contract.json"
COLLISION_LAYOUT_CONTRACT = SOURCE_DIR / "prototype_shuttle_collision_layout_contract.json"

STANDARD_COLLECTIONS = ["Exterior", "Interior", "Collision", "Markers", "Lights", "ReviewCameras", "ScaleProxies", "Disabled_Source"]


def fail(message: str) -> None:
    raise RuntimeError(message)


def blender_to_godot(loc) -> list[float]:
    return [round(loc.x, 5), round(loc.z, 5), round(-loc.y, 5)]


def blender_to_godot_triplet(values: list[float]) -> list[float]:
    return [round(values[0], 5), round(values[2], 5), round(-values[1], 5)]


def godot_to_blender(position: list[float]):
    return (position[0], -position[2], position[1])


def collection(name: str) -> bpy.types.Collection:
    found = bpy.data.collections.get(name)
    if found is None:
        fail(f"Missing required collection: {name}")
    return found


def descendants(source: bpy.types.Collection) -> list[bpy.types.Object]:
    objects = list(source.objects)
    for child in source.children:
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


def mesh_triangle_count(obj: bpy.types.Object) -> int:
    if obj.type != "MESH" or obj.data is None:
        return 0
    obj.data.calc_loop_triangles()
    return len(obj.data.loop_triangles)


def object_bounds(obj: bpy.types.Object) -> tuple[list[float], list[float]] | None:
    if obj.type != "MESH":
        return None
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    mins = [round(min(getattr(corner, axis) for corner in corners), 5) for axis in ("x", "y", "z")]
    maxs = [round(max(getattr(corner, axis) for corner in corners), 5) for axis in ("x", "y", "z")]
    return mins, maxs


def combine_bounds(objects: list[bpy.types.Object]) -> dict[str, list[float]] | None:
    bounds = [object_bounds(obj) for obj in objects]
    bounds = [item for item in bounds if item is not None]
    if not bounds:
        return None
    mins = [round(min(item[0][axis] for item in bounds), 5) for axis in range(3)]
    maxs = [round(max(item[1][axis] for item in bounds), 5) for axis in range(3)]
    return {
        "blender_min": mins,
        "blender_max": maxs,
        "godot_min": blender_to_godot_triplet(mins),
        "godot_max": blender_to_godot_triplet(maxs),
    }


def object_report(obj: bpy.types.Object) -> dict[str, object]:
    bounds = object_bounds(obj)
    return {
        "name": obj.name,
        "type": obj.type,
        "triangle_count": mesh_triangle_count(obj),
        "material_slots": [slot.material.name if slot.material is not None else "<empty>" for slot in getattr(obj, "material_slots", [])],
        "bounds": None if bounds is None else {
            "blender_min": bounds[0],
            "blender_max": bounds[1],
            "godot_min": blender_to_godot_triplet(bounds[0]),
            "godot_max": blender_to_godot_triplet(bounds[1]),
        },
    }


def load_json(path: Path, key: str) -> list[dict[str, object]]:
    if not path.exists():
        fail(f"Missing contract: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get(key, [])
    if not items:
        fail(f"Contract has no {key}: {path}")
    return items


def write_markers(markers_collection: bpy.types.Collection) -> dict[str, list[float]]:
    markers = load_json(MARKER_CONTRACT, "markers")
    marker_objects = {obj.name: obj for obj in descendants(markers_collection)}
    data: dict[str, list[float]] = {}
    for marker in markers:
        name = str(marker["godot_node"])
        position = [round(float(value), 5) for value in marker["position"]]
        data[name] = position
        obj = marker_objects.get(name)
        if obj is not None:
            obj.location = godot_to_blender(position)
            obj["godot_position"] = position
    MARKERS_JSON.parent.mkdir(parents=True, exist_ok=True)
    MARKERS_JSON.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def write_reports(exterior_objects: list[bpy.types.Object], interior_objects: list[bpy.types.Object], collision_objects: list[bpy.types.Object], markers: dict[str, list[float]]) -> None:
    lights = load_json(LIGHT_CONTRACT, "lights")
    scale_proxies = load_json(SCALE_PROXY_CONTRACT, "proxies")
    collision_layout = json.loads(COLLISION_LAYOUT_CONTRACT.read_text(encoding="utf-8")) if COLLISION_LAYOUT_CONTRACT.exists() else None
    groups = {
        "exterior": exterior_objects,
        "interior": interior_objects,
        "collision": collision_objects,
    }
    warnings = []
    material_usage: dict[str, dict[str, object]] = {}
    for group_name, objects in groups.items():
        for obj in objects:
            if obj.type == "MESH" and not getattr(obj, "material_slots", []):
                warnings.append(f"Mesh has no material slots: {obj.name}")
            for slot in getattr(obj, "material_slots", []):
                material_name = slot.material.name if slot.material is not None else "<empty>"
                entry = material_usage.setdefault(material_name, {"object_count": 0, "groups": set()})
                entry["object_count"] += 1
                entry["groups"].add(group_name)

    collection_report = {
        name: {
            "required": name not in {"Lights", "ReviewCameras", "ScaleProxies", "Disabled_Source"},
            "aliases": [name],
            "found": [name] if bpy.data.collections.get(name) else [],
        }
        for name in STANDARD_COLLECTIONS
    }
    asset_report = {
        "schema_version": 1,
        "ship_id": "prototype_shuttle",
        "source_blend": str(SOURCE_BLEND.relative_to(ROOT)),
        "exports": {
            "exterior_glb": str(EXTERIOR_GLB.relative_to(ROOT)),
            "interior_glb": str(INTERIOR_GLB.relative_to(ROOT)),
            "collision_glb": str(COLLISION_GLB.relative_to(ROOT)),
            "markers_json": str(MARKERS_JSON.relative_to(ROOT)),
            "asset_report": str(ASSET_REPORT_JSON.relative_to(ROOT)),
            "material_report": str(MATERIAL_REPORT_JSON.relative_to(ROOT)),
            "light_report": str(LIGHT_REPORT_JSON.relative_to(ROOT)),
            "scale_proxy_report": str(SCALE_PROXY_REPORT_JSON.relative_to(ROOT)),
            "collision_layout_report": str(COLLISION_LAYOUT_REPORT_JSON.relative_to(ROOT)),
        },
        "standard_collections": collection_report,
        "groups": {
            name: {
                "object_count": len(objects),
                "mesh_count": sum(1 for obj in objects if obj.type == "MESH"),
                "triangle_count": sum(mesh_triangle_count(obj) for obj in objects),
                "bounds": combine_bounds(objects),
                "objects": [object_report(obj) for obj in objects],
            }
            for name, objects in groups.items()
        },
        "marker_count": len(markers),
        "markers": markers,
        "light_count": len(lights),
        "scale_proxy_count": len(scale_proxies),
        "warnings": sorted(set(warnings)),
    }
    material_report = {
        "ship_id": "prototype_shuttle",
        "material_count": len(material_usage),
        "materials": {
            name: {
                "object_count": data["object_count"],
                "groups": sorted(data["groups"]),
            }
            for name, data in sorted(material_usage.items())
        },
        "warnings": sorted(set(warnings)),
    }
    light_report = {
        "schema_version": 1,
        "ship_id": "prototype_shuttle",
        "source_contract": str(LIGHT_CONTRACT.relative_to(ROOT)),
        "light_count": len(lights),
        "lights": lights,
    }
    scale_proxy_report = {
        "schema_version": 1,
        "ship_id": "prototype_shuttle",
        "source_contract": str(SCALE_PROXY_CONTRACT.relative_to(ROOT)),
        "proxy_count": len(scale_proxies),
        "proxies": scale_proxies,
    }
    ASSET_REPORT_JSON.write_text(json.dumps(asset_report, indent=2) + "\n", encoding="utf-8")
    MATERIAL_REPORT_JSON.write_text(json.dumps(material_report, indent=2) + "\n", encoding="utf-8")
    LIGHT_REPORT_JSON.write_text(json.dumps(light_report, indent=2) + "\n", encoding="utf-8")
    SCALE_PROXY_REPORT_JSON.write_text(json.dumps(scale_proxy_report, indent=2) + "\n", encoding="utf-8")
    if collision_layout is None:
        fail(f"Missing contract: {COLLISION_LAYOUT_CONTRACT}")
    COLLISION_LAYOUT_REPORT_JSON.write_text(json.dumps(collision_layout, indent=2) + "\n", encoding="utf-8")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_LOG.write_text(
        json.dumps(
            {
                "source_blend": str(SOURCE_BLEND.relative_to(ROOT)),
                "exports": asset_report["exports"],
                "marker_contract": str(MARKER_CONTRACT.relative_to(ROOT)),
                "light_contract": str(LIGHT_CONTRACT.relative_to(ROOT)),
                "scale_proxy_contract": str(SCALE_PROXY_CONTRACT.relative_to(ROOT)),
                "collision_layout_contract": str(COLLISION_LAYOUT_CONTRACT.relative_to(ROOT)),
                "standard_collections": collection_report,
                "warnings": sorted(set(warnings)),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    if not SOURCE_BLEND.exists():
        fail(f"Source blend is missing. Run scripts/bootstrap-prototype-shuttle-blender.sh first: {SOURCE_BLEND}")
    if Path(bpy.data.filepath).resolve() != SOURCE_BLEND:
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE_BLEND))

    for name in STANDARD_COLLECTIONS:
        collection(name)
    exterior_objects = [obj for obj in descendants(collection("Exterior")) if obj.type in {"MESH", "EMPTY"}]
    interior_objects = [obj for obj in descendants(collection("Interior")) if obj.type in {"MESH", "EMPTY"}]
    collision_objects = [obj for obj in descendants(collection("Collision")) if obj.type == "MESH"]

    export_glb(EXTERIOR_GLB, exterior_objects)
    export_glb(INTERIOR_GLB, interior_objects)
    export_glb(COLLISION_GLB, collision_objects)
    markers = write_markers(collection("Markers"))
    write_reports(exterior_objects, interior_objects, collision_objects, markers)

    print(f"Wrote {EXTERIOR_GLB}")
    print(f"Wrote {INTERIOR_GLB}")
    print(f"Wrote {COLLISION_GLB}")
    print(f"Wrote {MARKERS_JSON}")
    print(f"Wrote {ASSET_REPORT_JSON}")
    print(f"Wrote {MATERIAL_REPORT_JSON}")
    print(f"Wrote {LIGHT_REPORT_JSON}")
    print(f"Wrote {SCALE_PROXY_REPORT_JSON}")
    print(f"Wrote {COLLISION_LAYOUT_REPORT_JSON}")
    print(f"Wrote {EXPORT_LOG}")


if __name__ == "__main__":
    main()
