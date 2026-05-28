#!/usr/bin/env python3
"""Export the ShuttleA Blender source scene to Godot-ready artifacts."""

from __future__ import annotations

import json
import os
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(os.environ.get("SPACE_GAME_ROOT", Path.cwd())).resolve()
SOURCE_BLEND = ROOT / "assets/source/blender/ships/shuttle_a/shuttle_a_interior.blend"
OUT_DIR = ROOT / "assets/models/ship/shuttle_a"
REPORT_DIR = ROOT / "reports/ship_modeling"
INTERIOR_GLB = OUT_DIR / "shuttle_a_interior.glb"
COLLISION_GLB = OUT_DIR / "shuttle_a_collision.glb"
MARKERS_JSON = OUT_DIR / "shuttle_a_markers.json"
ASSET_REPORT_JSON = OUT_DIR / "shuttle_a_asset_report.json"
MATERIAL_REPORT_JSON = OUT_DIR / "shuttle_a_material_report.json"
LIGHT_REPORT_JSON = OUT_DIR / "shuttle_a_light_report.json"
SCALE_PROXY_REPORT_JSON = OUT_DIR / "shuttle_a_scale_proxy_report.json"
EXPORT_LOG = REPORT_DIR / "shuttle_a_export_report.json"
MARKER_CONTRACT = ROOT / "assets/source/blender/ships/shuttle_a/shuttle_a_marker_contract.json"
LIGHT_CONTRACT = ROOT / "assets/source/blender/ships/shuttle_a/shuttle_a_light_contract.json"
SCALE_PROXY_CONTRACT = ROOT / "assets/source/blender/ships/shuttle_a/shuttle_a_scale_proxy_contract.json"

STANDARD_COLLECTIONS = {
    "Exterior": {
        "aliases": ["Exterior", "Reference_Exterior"],
        "required": True,
    },
    "Interior": {
        "aliases": ["Interior", "Interior_Render", "Interior_Glass"],
        "required": True,
    },
    "Collision": {
        "aliases": ["Collision", "Collision_Proxy"],
        "required": True,
    },
    "Markers": {
        "aliases": ["Markers"],
        "required": True,
    },
    "Lights": {
        "aliases": ["Lights"],
        "required": False,
    },
    "ReviewCameras": {
        "aliases": ["ReviewCameras", "Review_Cameras"],
        "required": False,
    },
    "ScaleProxies": {
        "aliases": ["ScaleProxies", "Scale_Proxies"],
        "required": False,
    },
    "Disabled_Source": {
        "aliases": ["Disabled_Source"],
        "required": False,
    },
}


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


def resolve_standard_collections() -> dict[str, dict[str, object]]:
    ensure_contract_backed_collections()
    resolved = {}
    missing_required = []
    for standard_name, config in STANDARD_COLLECTIONS.items():
        found = [
            bpy.data.collections[name]
            for name in config["aliases"]
            if bpy.data.collections.get(name) is not None
        ]
        if config["required"] and not found:
            missing_required.append(f"{standard_name} ({', '.join(config['aliases'])})")
        resolved[standard_name] = {
            "required": bool(config["required"]),
            "aliases": list(config["aliases"]),
            "found": [collection.name for collection in found],
            "collections": found,
        }
    if missing_required:
        fail(f"Missing required collection(s): {', '.join(missing_required)}")
    return resolved


def ensure_contract_backed_collections() -> None:
    if LIGHT_CONTRACT.exists() and bpy.data.collections.get("Lights") is None:
        bpy.context.scene.collection.children.link(bpy.data.collections.new("Lights"))
    if SCALE_PROXY_CONTRACT.exists() and bpy.data.collections.get("ScaleProxies") is None:
        bpy.context.scene.collection.children.link(bpy.data.collections.new("ScaleProxies"))


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


def blender_to_godot_triplet(values: list[float]) -> list[float]:
    return [round(values[0], 5), round(values[2], 5), round(-values[1], 5)]


def object_report(obj: bpy.types.Object) -> dict[str, object]:
    bounds = object_bounds(obj)
    return {
        "name": obj.name,
        "type": obj.type,
        "triangle_count": mesh_triangle_count(obj),
        "material_slots": [
            slot.material.name if slot.material is not None else "<empty>"
            for slot in getattr(obj, "material_slots", [])
        ],
        "bounds": None
        if bounds is None
        else {
            "blender_min": bounds[0],
            "blender_max": bounds[1],
            "godot_min": blender_to_godot_triplet(bounds[0]),
            "godot_max": blender_to_godot_triplet(bounds[1]),
        },
    }


def write_package_reports(
    collection_report: dict[str, dict[str, object]],
    exterior_objects: list[bpy.types.Object],
    interior_objects: list[bpy.types.Object],
    collision_objects: list[bpy.types.Object],
    markers: dict[str, list[float]],
) -> dict[str, object]:
    lights = load_json_contract(LIGHT_CONTRACT, "lights")
    scale_proxies = load_json_contract(SCALE_PROXY_CONTRACT, "proxies")
    object_groups = {
        "exterior": exterior_objects,
        "interior": interior_objects,
        "collision": collision_objects,
    }
    warnings = []
    missing_optional = [
        name
        for name, report in collection_report.items()
        if not report["required"] and not report["found"]
    ]
    for name in missing_optional:
        warnings.append(f"Optional standard collection is not present yet: {name}")

    material_usage: dict[str, dict[str, object]] = {}
    for group_name, objects in object_groups.items():
        for obj in objects:
            for slot in getattr(obj, "material_slots", []):
                material_name = slot.material.name if slot.material is not None else "<empty>"
                entry = material_usage.setdefault(material_name, {"object_count": 0, "groups": set()})
                entry["object_count"] += 1
                entry["groups"].add(group_name)
            if obj.type == "MESH" and not getattr(obj, "material_slots", []):
                warnings.append(f"Mesh has no material slots: {obj.name}")

    material_report = {
        "ship_id": "shuttle_a",
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
        "ship_id": "shuttle_a",
        "source_contract": str(LIGHT_CONTRACT.relative_to(ROOT)),
        "light_count": len(lights),
        "lights": lights,
    }
    scale_proxy_report = {
        "schema_version": 1,
        "ship_id": "shuttle_a",
        "source_contract": str(SCALE_PROXY_CONTRACT.relative_to(ROOT)),
        "proxy_count": len(scale_proxies),
        "proxies": scale_proxies,
    }
    asset_report = {
        "schema_version": 1,
        "ship_id": "shuttle_a",
        "source_blend": str(SOURCE_BLEND.relative_to(ROOT)),
        "exports": {
            "interior_glb": str(INTERIOR_GLB.relative_to(ROOT)),
            "collision_glb": str(COLLISION_GLB.relative_to(ROOT)),
            "markers_json": str(MARKERS_JSON.relative_to(ROOT)),
            "asset_report": str(ASSET_REPORT_JSON.relative_to(ROOT)),
            "material_report": str(MATERIAL_REPORT_JSON.relative_to(ROOT)),
            "light_report": str(LIGHT_REPORT_JSON.relative_to(ROOT)),
            "scale_proxy_report": str(SCALE_PROXY_REPORT_JSON.relative_to(ROOT)),
        },
        "standard_collections": {
            name: {
                "required": report["required"],
                "aliases": report["aliases"],
                "found": report["found"],
            }
            for name, report in collection_report.items()
        },
        "groups": {
            name: {
                "object_count": len(objects),
                "mesh_count": sum(1 for obj in objects if obj.type == "MESH"),
                "triangle_count": sum(mesh_triangle_count(obj) for obj in objects),
                "bounds": combine_bounds(objects),
                "objects": [object_report(obj) for obj in objects],
            }
            for name, objects in object_groups.items()
        },
        "marker_count": len(markers),
        "markers": markers,
        "light_count": len(lights),
        "scale_proxy_count": len(scale_proxies),
        "warnings": sorted(set(warnings)),
    }
    ASSET_REPORT_JSON.write_text(json.dumps(asset_report, indent=2) + "\n", encoding="utf-8")
    MATERIAL_REPORT_JSON.write_text(json.dumps(material_report, indent=2) + "\n", encoding="utf-8")
    LIGHT_REPORT_JSON.write_text(json.dumps(light_report, indent=2) + "\n", encoding="utf-8")
    SCALE_PROXY_REPORT_JSON.write_text(json.dumps(scale_proxy_report, indent=2) + "\n", encoding="utf-8")
    return {
        "asset_report": asset_report,
        "material_report": material_report,
        "light_report": light_report,
        "scale_proxy_report": scale_proxy_report,
    }


def write_markers(markers_collection: bpy.types.Collection) -> dict[str, list[float]]:
    contract = load_marker_contract()
    marker_objects = {obj.name: obj for obj in descendants(markers_collection)}
    data = {}
    for marker in contract:
        name = marker["godot_node"]
        position = marker["position"]
        data[name] = position
        obj = marker_objects.get(name)
        if obj is not None:
            obj.location = godot_to_blender(position)
            obj["godot_position"] = list(position)
    MARKERS_JSON.parent.mkdir(parents=True, exist_ok=True)
    MARKERS_JSON.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def godot_to_blender(position: list[float]):
    """Convert project/Godot coordinates to Blender Z-up coordinates."""
    return (position[0], -position[2], position[1])


def load_marker_contract() -> list[dict[str, object]]:
    if not MARKER_CONTRACT.exists():
        fail(f"Missing marker contract: {MARKER_CONTRACT}")
    data = json.loads(MARKER_CONTRACT.read_text(encoding="utf-8"))
    markers = data.get("markers", [])
    if not markers:
        fail(f"Marker contract has no markers: {MARKER_CONTRACT}")
    seen = set()
    parsed = []
    for marker in markers:
        name = marker.get("godot_node")
        position = marker.get("position")
        if not name or name in seen:
            fail(f"Invalid or duplicate marker name in contract: {name}")
        if not isinstance(position, list) or len(position) != 3:
            fail(f"Marker {name} position must be a three-number list")
        seen.add(name)
        parsed.append(
            {
                "id": marker.get("id"),
                "godot_node": str(name),
                "position": [round(float(value), 5) for value in position],
            }
        )
    return parsed


def load_json_contract(path: Path, key: str) -> list[dict[str, object]]:
    if not path.exists():
        fail(f"Missing package contract: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get(key, [])
    if not items:
        fail(f"Package contract has no {key}: {path}")
    return items


def main() -> None:
    if not SOURCE_BLEND.exists():
        fail(f"Source blend is missing. Run scripts/bootstrap-shuttle-a-blender.sh first: {SOURCE_BLEND}")

    if Path(bpy.data.filepath).resolve() != SOURCE_BLEND:
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE_BLEND))

    collection_report = resolve_standard_collections()
    collections = {
        name: require_collection(name)
        for name in ["Reference_Exterior", "Interior_Render", "Interior_Glass", "Collision_Proxy", "Markers"]
    }
    exterior_objects = [
        obj
        for obj in descendants(collections["Reference_Exterior"])
        if obj.type in {"MESH", "EMPTY"}
    ]
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
    package_reports = write_package_reports(collection_report, exterior_objects, render_objects, collision_objects, markers)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_LOG.write_text(
        json.dumps(
            {
                "source_blend": str(SOURCE_BLEND.relative_to(ROOT)),
                "interior_glb": str(INTERIOR_GLB.relative_to(ROOT)),
                "collision_glb": str(COLLISION_GLB.relative_to(ROOT)),
                "markers_json": str(MARKERS_JSON.relative_to(ROOT)),
                "marker_contract": str(MARKER_CONTRACT.relative_to(ROOT)),
                "asset_report": str(ASSET_REPORT_JSON.relative_to(ROOT)),
                "material_report": str(MATERIAL_REPORT_JSON.relative_to(ROOT)),
                "light_contract": str(LIGHT_CONTRACT.relative_to(ROOT)),
                "light_report": str(LIGHT_REPORT_JSON.relative_to(ROOT)),
                "scale_proxy_contract": str(SCALE_PROXY_CONTRACT.relative_to(ROOT)),
                "scale_proxy_report": str(SCALE_PROXY_REPORT_JSON.relative_to(ROOT)),
                "render_object_count": len(render_objects),
                "collision_object_count": len(collision_objects),
                "exterior_reference_object_count": len(exterior_objects),
                "light_count": package_reports["light_report"]["light_count"],
                "scale_proxy_count": package_reports["scale_proxy_report"]["proxy_count"],
                "standard_collections": package_reports["asset_report"]["standard_collections"],
                "warnings": package_reports["asset_report"]["warnings"],
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
    print(f"Wrote {ASSET_REPORT_JSON}")
    print(f"Wrote {MATERIAL_REPORT_JSON}")
    print(f"Wrote {LIGHT_REPORT_JSON}")
    print(f"Wrote {SCALE_PROXY_REPORT_JSON}")
    print(f"Wrote {EXPORT_LOG}")


if __name__ == "__main__":
    main()
