#!/usr/bin/env python3
"""Apply the first authored structural detail pass to the prototype shuttle."""

from __future__ import annotations

import math
import os
import json
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(os.environ.get("SPACE_GAME_ROOT", Path.cwd())).resolve()
SOURCE_BLEND = ROOT / "assets/source/blender/ships/prototype_shuttle/prototype_shuttle.blend"
COLLISION_LAYOUT_CONTRACT = SOURCE_BLEND.parent / "prototype_shuttle_collision_layout_contract.json"
PREFIX = "SDP1_"


def to_blender_loc(godot_loc: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = godot_loc
    return (x, -z, y)


def to_blender_dims(godot_dims: tuple[float, float, float]) -> tuple[float, float, float]:
    sx, sy, sz = godot_dims
    return (sx, sz, sy)


def collection(name: str) -> bpy.types.Collection:
    found = bpy.data.collections.get(name)
    if found is None:
        found = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(found)
    return found


def clear_previous() -> None:
    for obj in list(bpy.data.objects):
        if obj.name.startswith(PREFIX):
            bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.name.startswith(PREFIX) and mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def material(name: str, color: tuple[float, float, float, float], roughness: float = 0.72, metallic: float = 0.0, emission: tuple[float, float, float, float] | None = None, strength: float = 0.0) -> bpy.types.Material:
    found = bpy.data.materials.get(name)
    mat = found if found is not None else bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Emission Color"].default_value = emission or (0.0, 0.0, 0.0, 1.0)
        bsdf.inputs["Emission Strength"].default_value = strength
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.72
        if "Coat Weight" in bsdf.inputs and metallic > 0.2:
            bsdf.inputs["Coat Weight"].default_value = 0.18
        if "Coat Roughness" in bsdf.inputs and metallic > 0.2:
            bsdf.inputs["Coat Roughness"].default_value = max(0.18, roughness * 0.72)
    return mat


def add_cube(
    name: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    mat: bpy.types.Material,
    parent_collection: bpy.types.Collection,
    bevel: float = 0.025,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=to_blender_loc(center))
    obj = bpy.context.object
    obj.name = f"{PREFIX}{name}"
    obj.data.name = f"{PREFIX}{name}Mesh"
    obj.dimensions = to_blender_dims(size)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    for coll in list(obj.users_collection):
        coll.objects.unlink(obj)
    parent_collection.objects.link(obj)
    if bevel > 0:
        mod = obj.modifiers.new("manufactured bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 1
        obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    return obj


def add_tapered_box(
    name: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    mat: bpy.types.Material,
    parent_collection: bpy.types.Collection,
    top_scale: tuple[float, float] = (0.82, 0.82),
    bevel: float = 0.02,
) -> bpy.types.Object:
    cx, cy, cz = center
    sx, sy, sz = size
    bottom_x = sx * 0.5
    bottom_z = sz * 0.5
    top_x = bottom_x * top_scale[0]
    top_z = bottom_z * top_scale[1]
    bottom_y = cy - sy * 0.5
    top_y = cy + sy * 0.5
    godot_verts = [
        (cx - bottom_x, bottom_y, cz - bottom_z),
        (cx + bottom_x, bottom_y, cz - bottom_z),
        (cx + bottom_x, bottom_y, cz + bottom_z),
        (cx - bottom_x, bottom_y, cz + bottom_z),
        (cx - top_x, top_y, cz - top_z),
        (cx + top_x, top_y, cz - top_z),
        (cx + top_x, top_y, cz + top_z),
        (cx - top_x, top_y, cz + top_z),
    ]
    verts = [to_blender_loc(vertex) for vertex in godot_verts]
    faces = [
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (3, 7, 4, 0),
    ]
    mesh = bpy.data.meshes.new(f"{PREFIX}{name}Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(f"{PREFIX}{name}", mesh)
    obj.data.materials.append(mat)
    parent_collection.objects.link(obj)
    if bevel > 0:
        mod = obj.modifiers.new("manufactured bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 1
        obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    return obj


def add_cylinder_between(
    name: str,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    radius: float,
    mat: bpy.types.Material,
    parent_collection: bpy.types.Collection,
    vertices: int = 16,
) -> bpy.types.Object:
    start_b = Vector(to_blender_loc(start))
    end_b = Vector(to_blender_loc(end))
    delta = end_b - start_b
    length = delta.length
    if length <= 0.0001:
        raise ValueError(f"Cannot create zero-length cylinder {name}")

    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=length, location=start_b + delta * 0.5)
    obj = bpy.context.object
    obj.name = f"{PREFIX}{name}"
    obj.data.name = f"{PREFIX}{name}Mesh"
    obj.rotation_euler = delta.to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(mat)
    for coll in list(obj.users_collection):
        coll.objects.unlink(obj)
    parent_collection.objects.link(obj)
    try:
        for poly in obj.data.polygons:
            poly.use_smooth = True
    except Exception:
        pass
    obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    return obj


def add_ramp_cube(
    name: str,
    t: float,
    width: float,
    length: float,
    thickness: float,
    mat: bpy.types.Material,
    parent_collection: bpy.types.Collection,
    x_offset: float = 0.0,
    y_lift: float = 0.035,
    z_lift: float = 0.0,
    bevel: float = 0.02,
) -> bpy.types.Object:
    hinge = Vector((0.0, -1.79286, 0.2724))
    tip = Vector((0.0, -3.65286, -3.6776))
    along = (tip - hinge).normalized()
    across = Vector((1.0, 0.0, 0.0))
    normal = Vector((0.0, -along.z, along.y)).normalized()
    if normal.y < 0.0:
        normal = -normal

    center = hinge + (tip - hinge) * t + across * x_offset + normal * y_lift + Vector((0.0, 0.0, z_lift))
    half_width = width * 0.5
    half_length = length * 0.5
    half_thickness = thickness * 0.5

    godot_corners = []
    for n in (-1.0, 1.0):
        for l in (-1.0, 1.0):
            for w in (-1.0, 1.0):
                godot_corners.append(center + across * (w * half_width) + along * (l * half_length) + normal * (n * half_thickness))

    verts = [to_blender_loc((corner.x, corner.y, corner.z)) for corner in godot_corners]
    faces = [
        (0, 1, 3, 2),
        (4, 6, 7, 5),
        (0, 4, 5, 1),
        (2, 3, 7, 6),
        (0, 2, 6, 4),
        (1, 5, 7, 3),
    ]
    mesh = bpy.data.meshes.new(f"{PREFIX}{name}Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(f"{PREFIX}{name}", mesh)
    obj.data.materials.append(mat)
    parent_collection.objects.link(obj)
    if bevel > 0:
        mod = obj.modifiers.new("manufactured bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 1
        obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    return obj


def add_light(name: str, center: tuple[float, float, float], energy: float, size: float, color: tuple[float, float, float], parent_collection: bpy.types.Collection) -> None:
    light_data = bpy.data.lights.new(f"{PREFIX}{name}", "AREA")
    light_data.energy = energy
    light_data.size = size
    light_data.color = color
    obj = bpy.data.objects.new(f"{PREFIX}{name}", light_data)
    obj.location = to_blender_loc(center)
    parent_collection.objects.link(obj)


def add_indicator_strip(
    name: str,
    center: tuple[float, float, float],
    count: int,
    spacing: float,
    size: tuple[float, float, float],
    mat: bpy.types.Material,
    parent_collection: bpy.types.Collection,
    axis: str = "x",
) -> None:
    for index in range(count):
        offset = (index - (count - 1) * 0.5) * spacing
        x, y, z = center
        if axis == "x":
            x += offset
        elif axis == "y":
            y += offset
        else:
            z += offset
        add_cube(f"{name}_{index:02d}", (x, y, z), size, mat, parent_collection, 0.006)


def apply_structural_pass() -> None:
    interior = collection("Interior")
    collision = collection("Collision")
    lights = collection("Lights")

    trim = material("proto_structural_dark_trim", (0.050, 0.056, 0.060, 1), 0.26, 0.78)
    brushed = material("proto_structural_burnished_edge_metal", (0.21, 0.215, 0.205, 1), 0.18, 0.88)
    panel = material("proto_structural_warm_wall_panel", (0.50, 0.48, 0.43, 1), 0.74, 0.02)
    pale_panel = material("proto_structural_pale_insulated_panel", (0.66, 0.64, 0.58, 1), 0.82, 0.0)
    floor = material("proto_structural_floor_plate", (0.25, 0.255, 0.235, 1), 0.16, 0.70)
    worn_floor = material("proto_structural_worn_floor_insert", (0.40, 0.375, 0.315, 1), 0.22, 0.48)
    scratched = material("proto_structural_scratched_edge_metal", (0.32, 0.325, 0.300, 1), 0.16, 0.90)
    soot = material("proto_structural_sooty_recess", (0.022, 0.024, 0.023, 1), 0.88, 0.0)
    label_white = material("proto_structural_stenciled_label_white", (0.82, 0.80, 0.72, 1), 0.78, 0.0)
    warm_worn_path = material("proto_structural_warm_worn_walk_path", (0.47, 0.415, 0.310, 1), 0.18, 0.58)
    muted_service_green = material("proto_structural_muted_service_green", (0.25, 0.34, 0.29, 1), 0.76, 0.02)
    rubber = material("proto_structural_rubber_gasket", (0.012, 0.014, 0.016, 1), 0.93, 0.0)
    blue = material("proto_structural_blue_accent_panel", (0.055, 0.17, 0.24, 1), 0.62, 0.05)
    hazard = material("proto_structural_hazard_warm_yellow", (0.92, 0.63, 0.16, 1), 0.58, 0.0)
    dark_glass = material("proto_structural_dark_inset_glass", (0.015, 0.018, 0.02, 1), 0.42, 0.0)
    cargo_canvas = material("proto_structural_cargo_fabric_canvas", (0.19, 0.24, 0.20, 1), 0.84, 0.0)
    cargo_case = material("proto_structural_service_green_cargo_hard_case", (0.12, 0.14, 0.13, 1), 0.56, 0.08)
    warm_light = material("proto_structural_warm_light_fixture", (1.0, 0.82, 0.55, 1), 0.22, 0.0, (1.0, 0.72, 0.42, 1), 3.2)
    cool_light = material("proto_structural_cool_light_fixture", (0.58, 0.86, 1.0, 1), 0.18, 0.0, (0.36, 0.68, 1.0, 1), 2.6)
    seat = material("proto_structural_seat_fabric_dark", (0.080, 0.088, 0.092, 1), 0.90, 0.0)
    seat_stitch = material("proto_structural_seat_stitching", (0.34, 0.35, 0.33, 1), 0.86, 0.0)
    amber = material("proto_structural_amber_status_light", (1.0, 0.48, 0.12, 1), 0.30, 0.0, (1.0, 0.36, 0.08, 1), 2.6)
    cyan = material("proto_structural_cyan_status_light", (0.16, 0.80, 1.0, 1), 0.26, 0.0, (0.08, 0.60, 1.0, 1), 2.3)
    glass = material("proto_structural_smoked_glass", (0.08, 0.19, 0.22, 0.55), 0.28, 0.0)
    collision_floor = material("proto_structural_collision_walkable", (0.0, 0.9, 0.35, 0.45), 0.6, 0.0)

    # Ramp and hatch frame: thicker jambs/lintel/threshold with edge trims.
    add_cube("RampDoor_LeftRoundedJamb", (-1.82, -0.54, -0.13), (0.24, 2.85, 0.22), trim, interior, 0.05)
    add_cube("RampDoor_RightRoundedJamb", (1.82, -0.54, -0.13), (0.24, 2.85, 0.22), trim, interior, 0.05)
    add_cube("RampDoor_UpperLintel", (0.0, 0.74, -0.12), (3.9, 0.24, 0.24), trim, interior, 0.05)
    add_cube("RampDoor_LowerHingeMass", (0.0, -1.82, 0.24), (3.55, 0.20, 0.26), trim, interior, 0.04)
    add_cube("RampDoor_InnerRubberGasketTop", (0.0, 0.56, -0.03), (3.35, 0.08, 0.09), rubber, interior, 0.025)
    add_cube("RampDoor_InnerRubberGasketLeft", (-1.60, -0.55, -0.02), (0.08, 2.18, 0.09), rubber, interior, 0.025)
    add_cube("RampDoor_InnerRubberGasketRight", (1.60, -0.55, -0.02), (0.08, 2.18, 0.09), rubber, interior, 0.025)
    add_cube("RampDoor_SidePocketLeft", (-2.16, -0.40, -0.55), (0.26, 1.55, 0.72), panel, interior, 0.04)
    add_cube("RampDoor_SidePocketRight", (2.16, -0.40, -0.55), (0.26, 1.55, 0.72), panel, interior, 0.04)
    add_cube("RampDoor_OuterRoundedFrameTop", (0.0, 1.02, -1.34), (3.58, 0.18, 0.18), trim, interior, 0.045)
    add_cube("RampDoor_OuterRoundedFrameLeft", (-1.88, -0.62, -1.33), (0.18, 3.16, 0.18), trim, interior, 0.045)
    add_cube("RampDoor_OuterRoundedFrameRight", (1.88, -0.62, -1.33), (0.18, 3.16, 0.18), trim, interior, 0.045)
    add_cube("RampDoor_StatusClusterLeft", (-1.28, 0.76, -0.18), (0.32, 0.06, 0.12), amber, interior, 0.018)
    add_cube("RampDoor_StatusClusterRight", (1.28, 0.76, -0.18), (0.32, 0.06, 0.12), amber, interior, 0.018)
    for side, x in [("Left", -1.84), ("Right", 1.84)]:
        add_cube(f"RampDoor_{side}_InnerDoublerPlateUpper", (x, 0.34, -0.28), (0.10, 0.48, 0.28), panel, interior, 0.025)
        add_cube(f"RampDoor_{side}_InnerDoublerPlateLower", (x, -1.30, -0.22), (0.10, 0.52, 0.28), panel, interior, 0.025)
        add_cube(f"RampDoor_{side}_AmberIndicatorTop", (x * 0.88, 0.58, -0.06), (0.10, 0.045, 0.08), amber, interior, 0.008)
        add_cube(f"RampDoor_{side}_BlackLatchHousing", (x * 0.86, -0.84, -0.05), (0.12, 0.34, 0.12), dark_glass, interior, 0.016)
        add_cylinder_between(f"RampDoor_{side}_DiagonalLoadBraceA", (x * 0.93, 0.58, -0.12), (x * 0.88, -0.22, -0.92), 0.035, trim, interior)
        add_cylinder_between(f"RampDoor_{side}_DiagonalLoadBraceB", (x * 0.88, -0.22, -0.92), (x * 0.93, -1.26, -0.16), 0.035, trim, interior)
    add_cube("RampDoor_HeaderVentPanel", (0.0, 0.93, -0.54), (1.35, 0.075, 0.18), dark_glass, interior, 0.018)
    for x in [-0.48, -0.24, 0.0, 0.24, 0.48]:
        add_cube(f"RampDoor_HeaderVentSlat_{int((x + 0.48) * 100):02d}", (x, 0.985, -0.54), (0.055, 0.04, 0.20), trim, interior, 0.006)
    add_cylinder_between("RampDoor_LeftHydraulicRam_A", (-1.52, -1.52, -0.10), (-1.16, -2.82, -2.70), 0.035, trim, interior)
    add_cylinder_between("RampDoor_RightHydraulicRam_A", (1.52, -1.52, -0.10), (1.16, -2.82, -2.70), 0.035, trim, interior)
    add_cylinder_between("RampDoor_LeftHydraulicSleeve", (-1.66, -1.36, 0.02), (-1.43, -2.16, -1.62), 0.06, rubber, interior)
    add_cylinder_between("RampDoor_RightHydraulicSleeve", (1.66, -1.36, 0.02), (1.43, -2.16, -1.62), 0.06, rubber, interior)
    for side, x in [("Left", -1.18), ("Right", 1.18)]:
        add_cylinder_between(f"Iter2_RampDoor_{side}_MainHingeBar", (x, -1.86, 0.34), (x, -1.86, -0.58), 0.055, scratched, interior)
        add_cube(f"Iter2_RampDoor_{side}_HingeBracketUpper", (x, -1.74, 0.20), (0.34, 0.12, 0.14), brushed, interior, 0.018)
        add_cube(f"Iter2_RampDoor_{side}_HingeBracketLower", (x, -1.95, -0.42), (0.30, 0.12, 0.14), brushed, interior, 0.018)
        latch_x = -1.58 if side == "Left" else 1.58
        add_cube(f"Iter2_RampDoor_{side}_LatchWarningPlate", (latch_x, -0.84, -0.05), (0.11, 0.22, 0.18), hazard, interior, 0.006)
    add_cube("Iter2_RampDoor_SootedThresholdRecess", (0.0, -1.70, 0.08), (2.70, 0.045, 0.11), soot, interior, 0.008)

    add_ramp_cube("Ramp_MainSolidDeck", 0.52, 3.18, 4.05, 0.06, floor, interior, y_lift=0.025, bevel=0.02)
    add_ramp_cube("Ramp_LeftSideDeckPanel", 0.52, 0.46, 3.84, 0.04, panel, interior, x_offset=-1.36, y_lift=0.055, bevel=0.018)
    add_ramp_cube("Ramp_RightSideDeckPanel", 0.52, 0.46, 3.84, 0.04, panel, interior, x_offset=1.36, y_lift=0.055, bevel=0.018)
    add_ramp_cube("Ramp_CenterDarkGripPath", 0.52, 1.16, 3.72, 0.032, rubber, interior, y_lift=0.072, bevel=0.012)
    add_ramp_cube("Ramp_LeftRaisedRail", 0.52, 0.16, 3.5, 0.12, trim, interior, x_offset=-1.42, y_lift=0.12, bevel=0.035)
    add_ramp_cube("Ramp_RightRaisedRail", 0.52, 0.16, 3.5, 0.12, trim, interior, x_offset=1.42, y_lift=0.12, bevel=0.035)
    for idx, t in enumerate([0.16, 0.30, 0.44, 0.58, 0.72, 0.86]):
        add_ramp_cube(f"Ramp_TransverseTread_{idx:02d}", t, 2.35, 0.055, 0.055, rubber, interior, y_lift=0.14, bevel=0.015)
    for x in [-0.62, 0.62]:
        add_ramp_cube(f"Ramp_LongInsetRail_{'L' if x < 0 else 'R'}", 0.52, 0.08, 3.25, 0.04, floor, interior, x_offset=x, y_lift=0.15, bevel=0.012)
    for x in [-1.12, 0.0, 1.12]:
        add_ramp_cube(f"Ramp_RecessedWearPlate_{int((x + 1.12) * 10):02d}", 0.52, 0.55, 2.80, 0.026, panel, interior, x_offset=x, y_lift=0.108, bevel=0.018)
    for idx, t in enumerate([0.22, 0.39, 0.56, 0.73]):
        add_ramp_cube(f"Ramp_SideLatchPocketLeft_{idx:02d}", t, 0.18, 0.24, 0.04, dark_glass, interior, x_offset=-1.14, y_lift=0.16, bevel=0.012)
        add_ramp_cube(f"Ramp_SideLatchPocketRight_{idx:02d}", t, 0.18, 0.24, 0.04, dark_glass, interior, x_offset=1.14, y_lift=0.16, bevel=0.012)
    for idx, t in enumerate([0.28, 0.50, 0.72]):
        add_ramp_cube(f"Ramp_CenterAccessPlate_{idx:02d}", t, 0.84, 0.38, 0.018, floor, interior, y_lift=0.17, bevel=0.012)
    for idx, t in enumerate([0.18, 0.34, 0.50, 0.66, 0.82]):
        add_ramp_cube(f"Ramp_WornCenterScuff_{idx:02d}", t, 0.74, 0.18, 0.012, worn_floor, interior, y_lift=0.192, bevel=0.006)
        add_ramp_cube(f"Ramp_LeftAmberEdgeMarker_{idx:02d}", t, 0.10, 0.14, 0.018, amber, interior, x_offset=-1.03, y_lift=0.196, bevel=0.006)
        add_ramp_cube(f"Ramp_RightAmberEdgeMarker_{idx:02d}", t, 0.10, 0.14, 0.018, amber, interior, x_offset=1.03, y_lift=0.196, bevel=0.006)
    add_ramp_cube("Ramp_LeftCableChainHousing", 0.52, 0.18, 3.18, 0.10, brushed, interior, x_offset=-1.66, y_lift=0.20, bevel=0.026)
    add_ramp_cube("Ramp_RightCableChainHousing", 0.52, 0.18, 3.18, 0.10, brushed, interior, x_offset=1.66, y_lift=0.20, bevel=0.026)
    for idx, t in enumerate([0.24, 0.36, 0.48, 0.60, 0.72, 0.84]):
        add_ramp_cube(f"Ramp_LeftCableChainLink_{idx:02d}", t, 0.22, 0.06, 0.055, trim, interior, x_offset=-1.66, y_lift=0.285, bevel=0.012)
        add_ramp_cube(f"Ramp_RightCableChainLink_{idx:02d}", t, 0.22, 0.06, 0.055, trim, interior, x_offset=1.66, y_lift=0.285, bevel=0.012)
    for idx, t in enumerate([0.14, 0.26, 0.38, 0.50, 0.62, 0.74, 0.86]):
        add_ramp_cube(f"Iter2_Ramp_ScrapedLeadingEdge_{idx:02d}", t, 2.05, 0.030, 0.018, scratched, interior, y_lift=0.218, bevel=0.004)
    for idx, (x, t) in enumerate([(-0.52, 0.20), (0.48, 0.30), (-0.28, 0.46), (0.35, 0.61), (-0.64, 0.76), (0.62, 0.86)]):
        add_ramp_cube(f"Iter2_Ramp_OilScuff_{idx:02d}", t, 0.34, 0.10, 0.010, soot, interior, x_offset=x, y_lift=0.225, bevel=0.003)
    for side, x in [("Left", -1.78), ("Right", 1.78)]:
        add_ramp_cube(f"Iter2_Ramp_{side}_VisibleServiceConduit", 0.52, 0.055, 3.56, 0.055, scratched, interior, x_offset=x, y_lift=0.34, bevel=0.01)
        for idx, t in enumerate([0.18, 0.34, 0.50, 0.66, 0.82]):
            add_ramp_cube(f"Iter2_Ramp_{side}_CableClamp_{idx:02d}", t, 0.20, 0.040, 0.070, rubber, interior, x_offset=x, y_lift=0.395, bevel=0.006)
    add_ramp_cube("Iter3_Ramp_BroadWarmWearLane", 0.52, 0.86, 3.55, 0.016, warm_worn_path, interior, y_lift=0.236, bevel=0.006)
    for side, x in [("Left", -1.18), ("Right", 1.18)]:
        add_ramp_cube(f"Iter3_Ramp_{side}_ContinuousGuideLight", 0.52, 0.055, 3.36, 0.026, warm_light, interior, x_offset=x, y_lift=0.246, bevel=0.004)
        add_ramp_cube(f"Iter3_Ramp_{side}_DarkSideBumperFace", 0.52, 0.18, 3.70, 0.050, soot, interior, x_offset=x * 1.18, y_lift=0.185, bevel=0.010)

    # Lower cargo deck shell: manufactured panels, floor route, ceiling ribs,
    # and visible light housings inspired by the cargo ramp reference.
    add_cube("CargoFloor_SolidDeckBase", (0.0, -1.555, 4.92), (4.95, 0.075, 9.34), floor, interior, 0.035)
    add_cube("CargoFloor_SolidDeckCenterInsetBase", (0.0, -1.507, 4.92), (1.86, 0.028, 8.55), rubber, interior, 0.018)
    for idx, z in enumerate([1.05, 2.55, 4.05, 5.55, 7.05, 8.55]):
        add_cube(f"CargoFloor_CenterPanel_{idx:02d}", (0.0, -1.50, z), (1.55, 0.045, 1.05), floor, interior, 0.025)
        add_cube(f"CargoFloor_LeftSidePanel_{idx:02d}", (-2.30, -1.48, z), (1.10, 0.04, 1.0), panel, interior, 0.02)
        add_cube(f"CargoFloor_RightSidePanel_{idx:02d}", (2.30, -1.48, z), (1.10, 0.04, 1.0), panel, interior, 0.02)
        add_cube(f"CargoFloor_WornInsert_{idx:02d}", (0.0, -1.455, z + 0.18), (0.92, 0.018, 0.42), worn_floor, interior, 0.014)
    for x in [-0.92, 0.92]:
        add_cube(f"CargoFloor_LongDarkPathRail_{'L' if x < 0 else 'R'}", (x, -1.445, 4.80), (0.10, 0.05, 7.95), trim, interior, 0.018)
    for idx, z in enumerate([1.45, 2.95, 4.45, 5.95, 7.45, 8.95]):
        add_cube(f"CargoFloor_TieDownLeft_{idx:02d}", (-1.36, -1.425, z), (0.34, 0.04, 0.08), rubber, interior, 0.012)
        add_cube(f"CargoFloor_TieDownRight_{idx:02d}", (1.36, -1.425, z), (0.34, 0.04, 0.08), rubber, interior, 0.012)
        add_cube(f"CargoFloor_CenterLatch_{idx:02d}", (0.0, -1.415, z + 0.38), (0.22, 0.05, 0.12), trim, interior, 0.014)
        add_cube(f"Iter2_CargoFloor_LeftScrapedTieDownLip_{idx:02d}", (-1.36, -1.388, z + 0.10), (0.42, 0.014, 0.024), scratched, interior, 0.003)
        add_cube(f"Iter2_CargoFloor_RightScrapedTieDownLip_{idx:02d}", (1.36, -1.388, z + 0.10), (0.42, 0.014, 0.024), scratched, interior, 0.003)
    for idx, z in enumerate([1.15, 1.75, 2.35, 3.55, 4.15, 5.35, 6.55, 7.15, 8.35]):
        add_cube(f"Iter2_CargoFloor_DirectionalWearStripe_{idx:02d}", ((-0.34 if idx % 2 else 0.34), -1.398, z), (0.46, 0.012, 0.035), scratched, interior, 0.003)
    for x in [-1.72, 1.72]:
        add_cube(f"Iter2_CargoFloor_LongTieDownTrack_{'Left' if x < 0 else 'Right'}", (x, -1.392, 4.95), (0.105, 0.026, 8.10), scratched, interior, 0.008)
        for idx, z in enumerate([1.20, 2.00, 2.80, 3.60, 4.40, 5.20, 6.00, 6.80, 7.60, 8.40]):
            add_cube(f"Iter2_CargoFloor_TieDownSlot_{'Left' if x < 0 else 'Right'}_{idx:02d}", (x, -1.372, z), (0.070, 0.016, 0.16), soot, interior, 0.003)
    for idx, z in enumerate([1.55, 3.05, 4.55, 6.05, 7.55, 9.05]):
        add_cube(f"Iter3_CargoFloor_BroadWarmWalkPanel_{idx:02d}", (0.0, -1.382, z), (1.05, 0.016, 0.86), warm_worn_path, interior, 0.010)
        add_cube(f"Iter3_CargoFloor_DarkPanelGap_{idx:02d}", (0.0, -1.369, z + 0.52), (1.36, 0.012, 0.045), soot, interior, 0.002)
        add_cube(f"Iter9_CargoFloor_RouteEdgeLeft_{idx:02d}", (-0.66, -1.358, z), (0.045, 0.018, 0.72), scratched, interior, 0.004)
        add_cube(f"Iter9_CargoFloor_RouteEdgeRight_{idx:02d}", (0.66, -1.358, z), (0.045, 0.018, 0.72), scratched, interior, 0.004)
    for side, x in [("Left", -2.82), ("Right", 2.82)]:
        add_cube(f"Iter3_Cargo_{side}_ContinuousLowerBumperRail", (x, -1.05, 4.95), (0.20, 0.16, 8.52), rubber, interior, 0.024)
        add_cube(f"Iter3_Cargo_{side}_ScratchedUpperBumperLip", (x, -0.91, 4.95), (0.23, 0.035, 8.34), scratched, interior, 0.008)
    add_cube("Iter4_RampCargo_ThresholdWarmWearPlate", (0.0, -1.377, 0.58), (2.55, 0.018, 0.34), warm_worn_path, interior, 0.010)
    add_cube("Iter4_RampCargo_ThresholdDarkExpansionJoint", (0.0, -1.362, 0.31), (2.70, 0.012, 0.045), soot, interior, 0.002)
    for x in [-1.20, 1.20]:
        add_cube(f"Iter4_RampCargo_ThresholdGuideBeacon_{'L' if x < 0 else 'R'}", (x, -1.348, 0.58), (0.18, 0.026, 0.08), warm_light, interior, 0.005)
    for idx, x in enumerate([-0.72, -0.36, 0.36, 0.72]):
        add_cube(f"Iter5_RampCargo_ThresholdStenciledGuide_{idx:02d}", (x, -1.346, 0.76), (0.18, 0.010, 0.035), label_white, interior, 0.001)
    for side, x in [("Left", -2.58), ("Right", 2.58)]:
        add_cube(f"Iter6_Cargo_{side}_SubtleRouteArrowA", (x, -1.334, 1.45), (0.24, 0.010, 0.040), label_white, interior, 0.001)
        add_cube(f"Iter6_Cargo_{side}_SubtleRouteArrowB", (x, -1.334, 1.58), (0.14, 0.010, 0.040), label_white, interior, 0.001)
    for idx, x in enumerate([-1.52, -1.22, 1.22, 1.52]):
        for j, z in enumerate([0.30, 0.72, 1.14]):
            add_cube(f"Iter8_RampCargo_ThresholdBolt_{idx:02d}_{j:02d}", (x, -1.338, z), (0.045, 0.018, 0.045), scratched, interior, 0.004)
    for idx, z in enumerate([1.85, 3.35, 4.85, 6.35, 7.85]):
        add_cube(f"CargoWall_LeftVerticalRib_{idx:02d}", (-3.88, 0.42, z), (0.16, 3.05, 0.12), trim, interior, 0.04)
        add_cube(f"CargoWall_RightVerticalRib_{idx:02d}", (3.88, 0.42, z), (0.16, 3.05, 0.12), trim, interior, 0.04)
        add_cube(f"CargoWall_LeftInsetPanel_{idx:02d}", (-3.65, 0.60, z), (0.10, 1.52, 0.86), panel, interior, 0.035)
        add_cube(f"CargoWall_RightInsetPanel_{idx:02d}", (3.65, 0.60, z), (0.10, 1.52, 0.86), panel, interior, 0.035)
        add_cube(f"CargoWall_LeftPaddedInset_{idx:02d}", (-3.535, 0.64, z), (0.052, 0.88, 0.56), pale_panel, interior, 0.025)
        add_cube(f"CargoWall_RightPaddedInset_{idx:02d}", (3.535, 0.64, z), (0.052, 0.88, 0.56), pale_panel, interior, 0.025)
        add_cube(f"CargoWall_LeftBlueServicePanel_{idx:02d}", (-3.56, -0.12, z + 0.36), (0.08, 0.62, 0.32), blue, interior, 0.025)
        add_cube(f"CargoWall_RightBlueServicePanel_{idx:02d}", (3.56, -0.12, z + 0.36), (0.08, 0.62, 0.32), blue, interior, 0.025)
        add_cube(f"CargoWall_LeftLowerKickPanel_{idx:02d}", (-3.42, -1.18, z), (0.11, 0.36, 0.98), trim, interior, 0.022)
        add_cube(f"CargoWall_RightLowerKickPanel_{idx:02d}", (3.42, -1.18, z), (0.11, 0.36, 0.98), trim, interior, 0.022)
        add_cube(f"CargoWall_LeftUpperPad_{idx:02d}", (-3.34, 1.55, z), (0.10, 0.70, 0.92), panel, interior, 0.035)
        add_cube(f"CargoWall_RightUpperPad_{idx:02d}", (3.34, 1.55, z), (0.10, 0.70, 0.92), panel, interior, 0.035)
        add_cylinder_between(f"CargoWall_LeftConduit_{idx:02d}", (-3.18, 1.07, z - 0.48), (-3.18, 1.07, z + 0.48), 0.025, trim, interior, 12)
        add_cylinder_between(f"CargoWall_RightConduit_{idx:02d}", (3.18, 1.07, z - 0.48), (3.18, 1.07, z + 0.48), 0.025, trim, interior, 12)
        add_cylinder_between(f"CargoWall_LeftDiagonalBraceUp_{idx:02d}", (-3.26, -0.90, z - 0.44), (-3.20, 1.48, z + 0.44), 0.028, trim, interior, 10)
        add_cylinder_between(f"CargoWall_RightDiagonalBraceUp_{idx:02d}", (3.26, -0.90, z - 0.44), (3.20, 1.48, z + 0.44), 0.028, trim, interior, 10)
        add_cube(f"CargoWall_LeftInsetGlassSlot_{idx:02d}", (-3.53, 0.84, z - 0.26), (0.055, 0.22, 0.48), dark_glass, interior, 0.016)
        add_cube(f"CargoWall_RightInsetGlassSlot_{idx:02d}", (3.53, 0.84, z - 0.26), (0.055, 0.22, 0.48), dark_glass, interior, 0.016)
        add_cube(f"CargoWall_LeftHazardToeStrip_{idx:02d}", (-3.30, -1.02, z - 0.30), (0.075, 0.09, 0.28), hazard, interior, 0.006)
        add_cube(f"CargoWall_RightHazardToeStrip_{idx:02d}", (3.30, -1.02, z - 0.30), (0.075, 0.09, 0.28), hazard, interior, 0.006)
        add_indicator_strip(f"CargoWall_LeftStatusPinline_{idx:02d}", (-3.47, 1.18, z + 0.16), 3, 0.14, (0.04, 0.035, 0.045), cyan, interior, "z")
        add_indicator_strip(f"CargoWall_RightStatusPinline_{idx:02d}", (3.47, 1.18, z + 0.16), 3, 0.14, (0.04, 0.035, 0.045), cyan, interior, "z")
        add_cube(f"Iter2_CargoWall_LeftLowPracticalLens_{idx:02d}", (-3.29, -0.84, z + 0.34), (0.055, 0.12, 0.22), warm_light, interior, 0.008)
        add_cube(f"Iter2_CargoWall_RightLowPracticalLens_{idx:02d}", (3.29, -0.84, z + 0.34), (0.055, 0.12, 0.22), warm_light, interior, 0.008)
        add_cube(f"Iter2_CargoWall_LeftStenciledZoneLabel_{idx:02d}", (-3.305, -0.36, z - 0.38), (0.025, 0.055, 0.36), label_white, interior, 0.002)
        add_cube(f"Iter2_CargoWall_RightStenciledZoneLabel_{idx:02d}", (3.305, -0.36, z - 0.38), (0.025, 0.055, 0.36), label_white, interior, 0.002)
        add_cube(f"Iter3_CargoWall_LeftDeepEquipmentWell_{idx:02d}", (-3.49, 0.08, z - 0.12), (0.050, 0.50, 0.44), soot, interior, 0.014)
        add_cube(f"Iter3_CargoWall_RightDeepEquipmentWell_{idx:02d}", (3.49, 0.08, z - 0.12), (0.050, 0.50, 0.44), soot, interior, 0.014)
        add_cube(f"Iter3_CargoWall_LeftGreenRemovablePanel_{idx:02d}", (-3.515, 1.28, z - 0.28), (0.045, 0.42, 0.38), muted_service_green, interior, 0.016)
        add_cube(f"Iter3_CargoWall_RightGreenRemovablePanel_{idx:02d}", (3.515, 1.28, z - 0.28), (0.045, 0.42, 0.38), muted_service_green, interior, 0.016)

    # Cargo furnishings: anchored to tie-downs or wall ribs, with the central
    # walking route left clear.
    for side, sign in [("Left", -1), ("Right", 1)]:
        wall_x = 3.12 * sign
        case_x = 2.52 * sign
        seat_x = 3.10 * sign
        seat_face = sign * -1
        for case_idx, z in enumerate([2.35, 6.95]):
            add_cube(f"CargoFurnishing_{side}_FloorAnchorPad_{case_idx:02d}", (case_x, -1.365, z), (0.92, 0.025, 0.84), scratched, interior, 0.008)
            add_tapered_box(f"CargoFurnishing_{side}_HardCaseBody_{case_idx:02d}", (case_x, -1.08, z), (0.78, 0.48, 0.68), cargo_case, interior, (0.88, 0.92), 0.035)
            add_cube(f"CargoFurnishing_{side}_HardCaseLidSeam_{case_idx:02d}", (case_x, -0.80, z), (0.66, 0.035, 0.58), trim, interior, 0.008)
            add_cube(f"CargoFurnishing_{side}_HardCaseHandle_{case_idx:02d}", (case_x + 0.28 * seat_face, -0.79, z), (0.06, 0.08, 0.26), rubber, interior, 0.012)
            add_cube(f"CargoFurnishing_{side}_StrapAcrossCase_{case_idx:02d}", (case_x, -0.72, z), (0.88, 0.040, 0.070), rubber, interior, 0.006)
            add_cube(f"CargoFurnishing_{side}_StrapForeAftCase_{case_idx:02d}", (case_x, -0.71, z), (0.070, 0.045, 0.76), rubber, interior, 0.006)
            add_cube(f"CargoFurnishing_{side}_AmberCaseTag_{case_idx:02d}", (case_x + 0.34 * seat_face, -0.89, z - 0.20), (0.035, 0.12, 0.18), amber, interior, 0.004)

        for seat_idx, z in enumerate([3.65, 5.10, 8.20]):
            add_cube(f"CargoFurnishing_{side}_FoldSeatBackMount_{seat_idx:02d}", (wall_x, -0.26, z), (0.10, 0.72, 0.58), trim, interior, 0.018)
            add_cube(f"CargoFurnishing_{side}_FoldSeatBackPad_{seat_idx:02d}", (wall_x - 0.055 * sign, -0.22, z), (0.075, 0.54, 0.42), cargo_canvas, interior, 0.018)
            add_cube(f"CargoFurnishing_{side}_FoldSeatBottom_{seat_idx:02d}", (seat_x - 0.30 * sign, -0.92, z), (0.58, 0.10, 0.44), cargo_canvas, interior, 0.020)
            add_cylinder_between(
                f"CargoFurnishing_{side}_FoldSeatLeg_{seat_idx:02d}",
                (seat_x - 0.55 * sign, -1.34, z - 0.16),
                (seat_x - 0.30 * sign, -0.98, z - 0.10),
                0.018,
                trim,
                interior,
                8,
            )
            add_cube(f"CargoFurnishing_{side}_SeatBeltLatch_{seat_idx:02d}", (seat_x - 0.31 * sign, -0.82, z + 0.19), (0.16, 0.035, 0.055), hazard, interior, 0.004)

        for net_idx, z in enumerate([4.35, 7.45]):
            add_cube(f"CargoFurnishing_{side}_WallNetHeader_{net_idx:02d}", (wall_x, 0.92, z), (0.055, 0.075, 0.92), rubber, interior, 0.006)
            add_cube(f"CargoFurnishing_{side}_WallNetFooter_{net_idx:02d}", (wall_x, 0.18, z), (0.055, 0.065, 0.92), rubber, interior, 0.006)
            for strand, z_offset in enumerate([-0.30, 0.0, 0.30]):
                add_cylinder_between(
                    f"CargoFurnishing_{side}_WallNetVertical_{net_idx:02d}_{strand:02d}",
                    (wall_x - 0.03 * sign, 0.18, z + z_offset),
                    (wall_x - 0.03 * sign, 0.92, z + z_offset),
                    0.010,
                    rubber,
                    interior,
                    6,
                )
            for strand, y in enumerate([0.38, 0.58, 0.78]):
                add_cube(f"CargoFurnishing_{side}_WallNetHorizontal_{net_idx:02d}_{strand:02d}", (wall_x - 0.03 * sign, y, z), (0.035, 0.018, 0.82), rubber, interior, 0.002)
            add_tapered_box(f"CargoFurnishing_{side}_SoftBagUnderNet_{net_idx:02d}", (wall_x - 0.055 * sign, 0.48, z + 0.08), (0.20, 0.34, 0.42), cargo_canvas, interior, (0.78, 0.88), 0.025)

    add_cube("CargoFurnishing_CenterCeilingCargoHookBar", (0.0, 2.05, 5.0), (1.55, 0.06, 0.08), scratched, interior, 0.010)
    for hook_idx, x in enumerate([-0.54, 0.0, 0.54]):
        add_cylinder_between(f"CargoFurnishing_CenterCeilingTieLoop_{hook_idx:02d}", (x, 1.88, 5.0), (x, 2.05, 5.0), 0.018, rubber, interior, 8)

    # Larger lived-in cargo bay silhouettes: a compact side lounge module and
    # opposite cargo shelving. They are intentionally side-mounted so the cargo
    # route from ramp to cockpit remains open.
    add_cube("CargoLounge_LeftCouchFloorMount", (-2.68, -1.355, 5.35), (1.55, 0.030, 2.18), scratched, interior, 0.010)
    add_tapered_box("CargoLounge_LeftCouchSeatCushion", (-2.78, -1.05, 5.35), (1.08, 0.30, 1.88), cargo_canvas, interior, (0.88, 0.96), 0.060)
    add_tapered_box("CargoLounge_LeftCouchBackCushion", (-3.22, -0.60, 5.35), (0.24, 0.86, 1.94), cargo_canvas, interior, (0.82, 0.94), 0.055)
    add_tapered_box("CargoLounge_LeftCouchForwardArm", (-2.78, -0.82, 4.26), (0.96, 0.48, 0.18), cargo_canvas, interior, (0.84, 0.82), 0.045)
    add_tapered_box("CargoLounge_LeftCouchAftArm", (-2.78, -0.82, 6.44), (0.96, 0.48, 0.18), cargo_canvas, interior, (0.84, 0.82), 0.045)
    for rib_idx, z in enumerate([4.72, 5.35, 5.98]):
        add_cube(f"CargoLounge_LeftCouchSeatSeam_{rib_idx:02d}", (-2.22, -0.87, z), (0.035, 0.035, 0.038), trim, interior, 0.004)
        add_cube(f"CargoLounge_LeftCouchBackSeam_{rib_idx:02d}", (-3.05, -0.36, z), (0.045, 0.42, 0.035), rubber, interior, 0.004)
    add_cube("CargoLounge_TableFloorBase", (-1.66, -1.33, 5.35), (0.62, 0.040, 0.62), scratched, interior, 0.012)
    add_cylinder_between("CargoLounge_TablePedestal", (-1.66, -1.31, 5.35), (-1.66, -0.82, 5.35), 0.060, trim, interior, 14)
    add_tapered_box("CargoLounge_TableTop", (-1.66, -0.74, 5.35), (0.92, 0.10, 0.74), brushed, interior, (0.94, 0.88), 0.045)
    add_cube("CargoLounge_TableInsetDarkTray", (-1.66, -0.665, 5.35), (0.62, 0.025, 0.44), dark_glass, interior, 0.012)
    add_cube("CargoLounge_TableAmberStatusChip", (-1.36, -0.64, 5.06), (0.13, 0.020, 0.08), amber, interior, 0.004)

    for shelf_idx, z in enumerate([2.25, 3.65, 5.05, 6.45, 7.85]):
        add_cube(f"CargoShelves_RightBackFrame_{shelf_idx:02d}", (3.18, -0.18, z), (0.13, 1.82, 1.02), trim, interior, 0.024)
        add_cube(f"CargoShelves_RightDeckLower_{shelf_idx:02d}", (2.72, -0.78, z), (0.82, 0.08, 0.96), brushed, interior, 0.016)
        add_cube(f"CargoShelves_RightDeckUpper_{shelf_idx:02d}", (2.72, 0.12, z), (0.82, 0.08, 0.96), brushed, interior, 0.016)
        add_cube(f"CargoShelves_RightVerticalDividerA_{shelf_idx:02d}", (2.38, -0.33, z - 0.38), (0.08, 0.86, 0.08), trim, interior, 0.010)
        add_cube(f"CargoShelves_RightVerticalDividerB_{shelf_idx:02d}", (2.38, -0.33, z + 0.38), (0.08, 0.86, 0.08), trim, interior, 0.010)
        add_tapered_box(f"CargoShelves_RightCrateLower_{shelf_idx:02d}", (2.68, -0.48, z - 0.20), (0.52, 0.42, 0.34), cargo_case, interior, (0.88, 0.92), 0.025)
        add_tapered_box(f"CargoShelves_RightSoftRollUpper_{shelf_idx:02d}", (2.66, 0.29, z + 0.16), (0.46, 0.26, 0.52), cargo_canvas, interior, (0.84, 0.90), 0.035)
        add_cube(f"CargoShelves_RightRubberRetainerLower_{shelf_idx:02d}", (2.31, -0.28, z), (0.050, 0.06, 0.92), rubber, interior, 0.006)
        add_cube(f"CargoShelves_RightAmberInventoryTag_{shelf_idx:02d}", (2.28, -0.56, z + 0.34), (0.040, 0.12, 0.16), amber, interior, 0.004)

    for idx, z in enumerate([1.3, 2.9, 4.5, 6.1, 7.7, 9.3]):
        add_cube(f"CargoCeiling_CrossRib_{idx:02d}", (0.0, 2.92, z), (5.05, 0.16, 0.13), trim, interior, 0.04)
        add_cube(f"CargoCeiling_LightHousing_{idx:02d}", (0.0, 2.78, z), (0.36, 0.08, 0.84), warm_light, interior, 0.025)
        add_cube(f"CargoCeiling_BlackVentPanel_{idx:02d}", (0.0, 2.83, z + 0.50), (0.95, 0.055, 0.34), dark_glass, interior, 0.018)
        for slot, x in enumerate([-0.32, -0.16, 0.0, 0.16, 0.32]):
            add_cube(f"CargoCeiling_VentSlat_{idx:02d}_{slot:02d}", (x, 2.865, z + 0.50), (0.055, 0.035, 0.30), trim, interior, 0.004)
        add_light(f"CargoCeiling_AreaLight_{idx:02d}", (0.0, 2.65, z), 32.0, 0.7, (1.0, 0.82, 0.62), lights)
        add_cube(f"CargoCeiling_LeftWarmSideLight_{idx:02d}", (-2.62, 2.22, z + 0.24), (0.12, 0.08, 0.36), warm_light, interior, 0.016)
        add_cube(f"CargoCeiling_RightWarmSideLight_{idx:02d}", (2.62, 2.22, z + 0.24), (0.12, 0.08, 0.36), warm_light, interior, 0.016)
        add_cube(f"CargoCeiling_LeftCableTray_{idx:02d}", (-1.65, 2.70, z), (0.28, 0.08, 0.88), trim, interior, 0.018)
        add_cube(f"CargoCeiling_RightCableTray_{idx:02d}", (1.65, 2.70, z), (0.28, 0.08, 0.88), trim, interior, 0.018)
        add_cylinder_between(f"CargoCeiling_LeftRoundConduit_{idx:02d}", (-2.18, 2.62, z - 0.48), (-2.18, 2.62, z + 0.48), 0.035, trim, interior, 12)
        add_cylinder_between(f"CargoCeiling_RightRoundConduit_{idx:02d}", (2.18, 2.62, z - 0.48), (2.18, 2.62, z + 0.48), 0.035, trim, interior, 12)
        add_cube(f"Iter2_CargoCeiling_WarmDiffuserLeft_{idx:02d}", (-0.42, 2.695, z), (0.22, 0.030, 0.70), warm_light, interior, 0.008)
        add_cube(f"Iter2_CargoCeiling_WarmDiffuserRight_{idx:02d}", (0.42, 2.695, z), (0.22, 0.030, 0.70), warm_light, interior, 0.008)
        add_cube(f"Iter7_CargoCeiling_LinerPanelLeft_{idx:02d}", (-1.05, 2.755, z + 0.04), (0.62, 0.035, 0.92), pale_panel, interior, 0.014)
        add_cube(f"Iter7_CargoCeiling_LinerPanelRight_{idx:02d}", (1.05, 2.755, z + 0.04), (0.62, 0.035, 0.92), pale_panel, interior, 0.014)
        add_cube(f"Iter7_CargoCeiling_DarkServiceChannel_{idx:02d}", (0.0, 2.735, z - 0.54), (1.52, 0.030, 0.16), soot, interior, 0.006)
        add_cube(f"Iter7_CargoCeiling_BrushedRibCap_{idx:02d}", (0.0, 2.835, z - 0.06), (4.45, 0.050, 0.045), scratched, interior, 0.006)
        for bolt_idx, x in enumerate([-1.82, -0.92, 0.92, 1.82]):
            add_cube(f"Iter8_CargoCeiling_RibCapFastener_{idx:02d}_{bolt_idx:02d}", (x, 2.875, z - 0.06), (0.050, 0.020, 0.050), brushed, interior, 0.004)

    for side, x in [("Left", -3.05), ("Right", 3.05)]:
        rail_x = x + (-0.13 if x < 0 else 0.13)
        add_cylinder_between(f"Cargo_{side}_LongUpperRail", (rail_x, 1.62, 0.95), (rail_x, 1.62, 9.55), 0.055, trim, interior)
        add_cylinder_between(f"Cargo_{side}_LongMidRail", (rail_x, 0.18, 0.95), (rail_x, 0.18, 9.55), 0.04, trim, interior)
        add_cube(f"Cargo_{side}_ForwardEquipmentRack", (x * 0.96, -0.18, 1.05), (0.20, 1.18, 0.58), trim, interior, 0.035)
        add_cube(f"Cargo_{side}_AftEquipmentRack", (x * 0.96, -0.18, 8.90), (0.20, 1.18, 0.58), trim, interior, 0.035)
        add_cube(f"Cargo_{side}_AmberSwitchBankA", (x * 0.93, 0.18, 1.05), (0.06, 0.12, 0.28), amber, interior, 0.01)
        add_cube(f"Cargo_{side}_AmberSwitchBankB", (x * 0.93, 0.18, 8.90), (0.06, 0.12, 0.28), amber, interior, 0.01)
        for idx, z in enumerate([2.2, 3.8, 5.4, 7.0]):
            add_cube(f"Cargo_{side}_UtilityBox_{idx:02d}", (x * 0.94, -0.72, z), (0.18, 0.34, 0.46), trim, interior, 0.03)
            add_cube(f"Cargo_{side}_UtilityInset_{idx:02d}", (x * 0.91, -0.68, z), (0.045, 0.17, 0.26), dark_glass, interior, 0.01)
            add_cube(f"Cargo_{side}_UtilityAmberLED_{idx:02d}", (x * 0.905, -0.52, z + 0.17), (0.035, 0.045, 0.045), amber, interior, 0.006)

    # Cargo-to-cockpit ascent: keep stair lanes visually clear. Earlier passes
    # added rails, markers, panels, and truss here, but those read as obstacles
    # because traversal collision is intentionally simplified. Only visible
    # treads and the upper landing deck remain in the player route.
    for side, x in [("Left", -2.17), ("Right", 2.17)]:
        for idx, z in enumerate([1.55, 1.05, 0.55, 0.05, -0.45, -0.95, -1.45, -1.95]):
            y = -1.44 + idx * 0.27
            add_cube(f"Ascent_{side}_VisibleStep_{idx:02d}", (x, y, z), (1.00, 0.050, 0.34), floor, interior, 0.014)
        add_cube(f"Ascent_{side}_LandingDeckInset", (x, 0.91, -2.76), (0.86, 0.05, 0.62), floor, interior, 0.018)

    # Cockpit cleanup: early seat form and canopy/floor trim without blocking
    # the forward view.
    add_cube("CockpitFloor_SolidDeckBase", (0.0, 0.858, -10.70), (3.35, 0.062, 10.88), floor, interior, 0.03)
    add_cube("CockpitFloor_SolidDeckCenterInsetBase", (0.0, 0.894, -10.70), (1.42, 0.024, 10.18), rubber, interior, 0.014)
    for idx, z in enumerate([-6.25, -7.65, -9.05, -10.45, -11.85, -13.25, -14.65]):
        add_cube(f"CockpitFloor_CenterPlate_{idx:02d}", (0.0, 0.91, z), (1.18, 0.045, 1.02), floor, interior, 0.022)
        add_cube(f"CockpitFloor_LeftWingPlate_{idx:02d}", (-1.23, 0.90, z), (0.78, 0.04, 0.98), panel, interior, 0.02)
        add_cube(f"CockpitFloor_RightWingPlate_{idx:02d}", (1.23, 0.90, z), (0.78, 0.04, 0.98), panel, interior, 0.02)
        add_cube(f"CockpitFloor_CenterWornMat_{idx:02d}", (0.0, 0.944, z + 0.12), (0.78, 0.018, 0.36), worn_floor, interior, 0.012)
    add_cube("CockpitFloor_TransitionSolidDeck", (0.0, 0.858, -3.02), (4.18, 0.052, 4.26), floor, interior, 0.025)
    add_cube("CockpitFloor_TransitionSolidDeckDarkInset", (0.0, 0.892, -3.02), (1.42, 0.026, 3.82), rubber, interior, 0.014)
    for idx, z in enumerate([-1.78, -2.62, -3.46, -4.30]):
        add_cube(f"CockpitFloor_TransitionBridgeCenter_{idx:02d}", (0.0, 0.91, z), (1.34, 0.048, 0.72), floor, interior, 0.022)
        add_cube(f"CockpitFloor_TransitionBridgeLeft_{idx:02d}", (-1.18, 0.90, z), (0.72, 0.042, 0.68), panel, interior, 0.02)
        add_cube(f"CockpitFloor_TransitionBridgeRight_{idx:02d}", (1.18, 0.90, z), (0.72, 0.042, 0.68), panel, interior, 0.02)
    add_cube("CockpitFloor_TopLandingCrossPlate", (0.0, 0.92, -1.26), (3.22, 0.055, 0.48), trim, interior, 0.025)
    add_cube("CockpitFloor_TopLandingDarkInset", (0.0, 0.955, -1.64), (1.66, 0.025, 0.20), rubber, interior, 0.01)
    add_cylinder_between("Iter12_TopLanding_RampDropGuardRailLower", (-1.36, 1.24, -0.86), (1.36, 1.24, -0.86), 0.032, trim, interior, 14)
    add_cylinder_between("Iter12_TopLanding_RampDropGuardRailUpper", (-1.36, 1.58, -0.86), (1.36, 1.58, -0.86), 0.036, trim, interior, 14)
    for idx, x in enumerate([-1.36, -0.68, 0.0, 0.68, 1.36]):
        add_cylinder_between(f"Iter12_TopLanding_RampDropGuardPost_{idx:02d}", (x, 0.98, -0.86), (x, 1.62, -0.86), 0.030, trim, interior, 12)
    add_cube("Iter12_TopLanding_GuardRailToeKick", (0.0, 1.02, -0.86), (2.86, 0.10, 0.12), rubber, interior, 0.014)
    add_cube("CockpitFloor_TransitionLeftToeRail", (-1.88, 0.965, -3.02), (0.10, 0.06, 3.34), rubber, interior, 0.012)
    add_cube("CockpitFloor_TransitionRightToeRail", (1.88, 0.965, -3.02), (0.10, 0.06, 3.34), rubber, interior, 0.012)
    add_cube("CockpitFloor_LeftSeatRail", (-0.32, 0.96, -13.55), (0.06, 0.035, 1.18), rubber, interior, 0.012)
    add_cube("CockpitFloor_RightSeatRail", (0.32, 0.96, -13.55), (0.06, 0.035, 1.18), rubber, interior, 0.012)
    add_cube("CockpitFloor_AftThreshold", (0.0, 0.98, -5.15), (2.90, 0.08, 0.18), trim, interior, 0.022)
    add_cube("CockpitFloor_ForwardThreshold", (0.0, 0.98, -15.28), (2.45, 0.08, 0.18), trim, interior, 0.022)
    add_cube("Iter9_CockpitEntry_WarmThresholdBand", (0.0, 0.995, -5.00), (1.80, 0.026, 0.070), warm_light, interior, 0.004)
    add_cube("Iter9_CockpitEntry_PaleRouteFrameLeft", (-1.10, 1.04, -5.05), (0.12, 0.20, 0.16), pale_panel, interior, 0.010)
    add_cube("Iter9_CockpitEntry_PaleRouteFrameRight", (1.10, 1.04, -5.05), (0.12, 0.20, 0.16), pale_panel, interior, 0.010)
    for idx, z in enumerate([-5.92, -7.42, -8.92, -10.42]):
        add_cube(f"CockpitApproach_LeftMetalLightHousing_{idx:02d}", (-1.42, 1.18, z), (0.12, 0.13, 0.44), scratched, interior, 0.010)
        add_cube(f"CockpitApproach_RightMetalLightHousing_{idx:02d}", (1.42, 1.18, z), (0.12, 0.13, 0.44), scratched, interior, 0.010)
        add_cube(f"CockpitApproach_LeftWarmLensedSource_{idx:02d}", (-1.34, 1.16, z), (0.035, 0.040, 0.30), warm_light, interior, 0.004)
        add_cube(f"CockpitApproach_RightWarmLensedSource_{idx:02d}", (1.34, 1.16, z), (0.035, 0.040, 0.30), warm_light, interior, 0.004)
        add_cube(f"CockpitApproach_FloorSpecularCatchPlate_{idx:02d}", (0.0, 0.964, z + 0.22), (1.12, 0.018, 0.34), warm_worn_path, interior, 0.006)

    # Cockpit hallway avionics: side-mounted computers and navigation gear.
    # These stay tight to the metal side structure so they read as equipment,
    # not floating decoration, and keep the center route clear.
    for side, sign in [("Left", -1), ("Right", 1)]:
        wall_x = 1.63 * sign
        face_x = 1.565 * sign
        support_x = 1.50 * sign
        for idx, z in enumerate([-6.32, -7.82, -9.32]):
            add_cube(f"Iter11_CockpitApproach_{side}_AvionicsBackplate_{idx:02d}", (wall_x, 1.42, z), (0.095, 0.72, 0.86), brushed, interior, 0.020)
            add_cube(f"Iter11_CockpitApproach_{side}_RubberShockMount_{idx:02d}", (support_x, 1.42, z), (0.050, 0.62, 0.76), rubber, interior, 0.010)
            add_cube(f"Iter11_CockpitApproach_{side}_ComputerBezel_{idx:02d}", (face_x, 1.54, z - 0.13), (0.045, 0.34, 0.46), trim, interior, 0.018)
            add_cube(f"Iter11_CockpitApproach_{side}_ComputerScreen_{idx:02d}", (face_x - 0.020 * sign, 1.54, z - 0.13), (0.028, 0.23, 0.32), glass, interior, 0.008)
            add_cube(f"Iter11_CockpitApproach_{side}_NavMapGlow_{idx:02d}", (face_x - 0.038 * sign, 1.545, z - 0.13), (0.014, 0.15, 0.24), cyan, interior, 0.004)
            add_cube(f"Iter11_CockpitApproach_{side}_StatusModule_{idx:02d}", (face_x, 1.20, z + 0.25), (0.040, 0.22, 0.22), dark_glass, interior, 0.010)
            add_indicator_strip(f"Iter11_CockpitApproach_{side}_AmberStatusBank_{idx:02d}", (face_x - 0.030 * sign, 1.20, z + 0.25), 4, 0.055, (0.018, 0.026, 0.024), amber, interior, "z")
            add_indicator_strip(f"Iter11_CockpitApproach_{side}_CyanKeyBank_{idx:02d}", (face_x - 0.030 * sign, 1.32, z - 0.46), 5, 0.052, (0.018, 0.022, 0.022), cyan, interior, "z")
            add_cube(f"Iter11_CockpitApproach_{side}_LowerDataPlate_{idx:02d}", (face_x, 1.08, z - 0.02), (0.035, 0.10, 0.58), scratched, interior, 0.008)
            add_cube(f"Iter11_CockpitApproach_{side}_StenciledNavLabel_{idx:02d}", (face_x - 0.035 * sign, 1.09, z - 0.02), (0.012, 0.034, 0.38), label_white, interior, 0.001)
            add_cylinder_between(f"Iter11_CockpitApproach_{side}_UpperCableLoom_{idx:02d}", (support_x, 1.86, z - 0.42), (support_x, 1.86, z + 0.42), 0.018, rubber, interior, 10)
            add_cylinder_between(f"Iter11_CockpitApproach_{side}_LowerCableLoom_{idx:02d}", (support_x, 1.04, z - 0.38), (support_x, 1.04, z + 0.38), 0.014, rubber, interior, 10)
            add_cylinder_between(f"Iter11_CockpitApproach_{side}_DiagonalComputerBrace_{idx:02d}", (wall_x, 1.12, z - 0.42), (wall_x, 1.72, z + 0.42), 0.016, scratched, interior, 8)

    for side, sign in [("Left", -1), ("Right", 1)]:
        x = 1.54 * sign
        add_cube(f"Iter11_CockpitApproach_{side}_LongNavigationBusHousing", (x, 1.78, -8.04), (0.060, 0.16, 3.96), trim, interior, 0.016)
        for idx, z in enumerate([-6.82, -7.22, -8.62, -9.02]):
            add_cube(f"Iter11_CockpitApproach_{side}_RouteComputerMiniDisplay_{idx:02d}", (x - 0.020 * sign, 1.79, z), (0.022, 0.080, 0.20), cyan, interior, 0.004)
        add_cube(f"Iter11_CockpitApproach_{side}_FoldedChartSlot", (x - 0.015 * sign, 1.03, -8.04), (0.028, 0.22, 0.72), dark_glass, interior, 0.010)

    for side, x in [("Pilot", -0.55), ("Copilot", 0.55)]:
        add_tapered_box(f"Cockpit_{side}_SeatDeckMount", (x, 0.89, -13.46), (0.74, 0.10, 0.78), trim, interior, (0.76, 0.72), 0.035)
        add_cube(f"Cockpit_{side}_SeatSlideRailLeft", (x - 0.22, 0.96, -13.46), (0.06, 0.06, 0.96), rubber, interior, 0.012)
        add_cube(f"Cockpit_{side}_SeatSlideRailRight", (x + 0.22, 0.96, -13.46), (0.06, 0.06, 0.96), rubber, interior, 0.012)
        add_tapered_box(f"Cockpit_{side}_SeatBase", (x, 1.17, -13.56), (0.58, 0.18, 0.62), seat, interior, (0.86, 0.78), 0.055)
        add_tapered_box(f"Cockpit_{side}_SeatBackLower", (x, 1.43, -13.82), (0.52, 0.30, 0.13), seat, interior, (0.88, 0.86), 0.045)
        add_tapered_box(f"Cockpit_{side}_SeatBackUpper", (x, 1.70, -13.91), (0.42, 0.32, 0.12), seat, interior, (0.72, 0.78), 0.045)
        add_tapered_box(f"Cockpit_{side}_SeatHeadrest", (x, 1.95, -13.98), (0.30, 0.14, 0.12), seat, interior, (0.70, 0.72), 0.035)
        add_cylinder_between(f"Cockpit_{side}_SeatPost", (x, 0.90, -13.56), (x, 1.13, -13.56), 0.05, trim, interior)
        add_cube(f"Cockpit_{side}_SeatCenterFabricPanel", (x, 1.28, -13.44), (0.38, 0.028, 0.36), seat_stitch, interior, 0.012)
        add_cube(f"Cockpit_{side}_SeatBackFabricPanel", (x, 1.57, -13.725), (0.34, 0.20, 0.028), seat_stitch, interior, 0.012)
        add_tapered_box(f"Cockpit_{side}_SeatSideBolsterLeft", (x - 0.31, 1.25, -13.58), (0.08, 0.18, 0.42), seat, interior, (0.70, 0.80), 0.035)
        add_tapered_box(f"Cockpit_{side}_SeatSideBolsterRight", (x + 0.31, 1.25, -13.58), (0.08, 0.18, 0.42), seat, interior, (0.70, 0.80), 0.035)
        add_cube(f"Cockpit_{side}_ArmPanelLeft", (x - 0.42, 1.16, -13.26), (0.08, 0.07, 0.30), trim, interior, 0.02)
        add_cube(f"Cockpit_{side}_ArmPanelRight", (x + 0.42, 1.16, -13.26), (0.08, 0.07, 0.30), trim, interior, 0.02)
        add_cube(f"Cockpit_{side}_HarnessLeft", (x - 0.14, 1.66, -13.67), (0.055, 0.42, 0.035), rubber, interior, 0.01)
        add_cube(f"Cockpit_{side}_HarnessRight", (x + 0.14, 1.66, -13.67), (0.055, 0.42, 0.035), rubber, interior, 0.01)
        add_cube(f"Iter2_Cockpit_{side}_LapBeltLeft", (x - 0.13, 1.38, -13.39), (0.050, 0.028, 0.42), rubber, interior, 0.006)
        add_cube(f"Iter2_Cockpit_{side}_LapBeltRight", (x + 0.13, 1.38, -13.39), (0.050, 0.028, 0.42), rubber, interior, 0.006)
        add_cylinder_between(f"Iter2_Cockpit_{side}_ControlGrip", (x, 1.18, -13.02), (x, 1.42, -13.08), 0.035, rubber, interior, 10)
        add_cube(f"Iter2_Cockpit_{side}_ControlGripTop", (x, 1.445, -13.09), (0.18, 0.055, 0.08), rubber, interior, 0.012)
    add_cube("Cockpit_LowForwardConsole", (0.0, 1.08, -15.05), (2.02, 0.24, 0.30), brushed, interior, 0.04)
    add_cube("Cockpit_ConsoleGlassA", (-0.52, 1.32, -14.90), (0.62, 0.05, 0.22), glass, interior, 0.025)
    add_cube("Cockpit_ConsoleGlassB", (0.52, 1.32, -14.90), (0.62, 0.05, 0.22), glass, interior, 0.025)
    add_cube("Iter2_Cockpit_ConsoleScratchedLowerLip", (0.0, 1.335, -14.68), (1.62, 0.035, 0.055), scratched, interior, 0.006)
    add_cube("Iter2_Cockpit_ConsoleBlackShadowRecess", (0.0, 1.155, -14.56), (1.86, 0.08, 0.10), soot, interior, 0.008)
    add_indicator_strip("Cockpit_ConsoleAmberButtonsLeft", (-0.52, 1.355, -14.76), 5, 0.10, (0.055, 0.025, 0.035), amber, interior, "x")
    add_indicator_strip("Cockpit_ConsoleCyanButtonsRight", (0.52, 1.355, -14.76), 5, 0.10, (0.055, 0.025, 0.035), cyan, interior, "x")
    add_cube("Cockpit_CenterMFDGlow", (0.0, 1.36, -14.84), (0.34, 0.035, 0.18), cyan, interior, 0.014)
    add_cube("Iter2_Cockpit_LeftLargeMFDBezel", (-0.62, 1.385, -14.98), (0.74, 0.030, 0.34), scratched, interior, 0.010)
    add_cube("Iter2_Cockpit_RightLargeMFDBezel", (0.62, 1.385, -14.98), (0.74, 0.030, 0.34), scratched, interior, 0.010)
    add_cube("Iter2_Cockpit_CenterAmberWarningBank", (0.0, 1.395, -14.65), (0.44, 0.030, 0.10), amber, interior, 0.006)
    add_cube("Iter3_Cockpit_BroadLowDashboardTop", (0.0, 1.18, -14.18), (1.86, 0.08, 0.82), warm_worn_path, interior, 0.022)
    add_cube("Iter3_Cockpit_DashboardShadowUnderbite", (0.0, 1.08, -13.70), (2.08, 0.10, 0.20), soot, interior, 0.018)
    add_cube("Iter3_Cockpit_ClearCenterFootwell", (0.0, 0.992, -12.92), (0.80, 0.026, 0.84), rubber, interior, 0.012)
    add_cube("Iter4_Cockpit_LowConsoleWarmTopPlane", (0.0, 1.245, -14.05), (1.72, 0.040, 0.64), warm_worn_path, interior, 0.016)
    add_cube("Iter4_Cockpit_LowConsoleFrontPaleFace", (0.0, 1.135, -13.66), (1.84, 0.22, 0.040), pale_panel, interior, 0.014)
    add_cube("Iter4_Cockpit_LowConsoleBlackGasketLine", (0.0, 1.262, -13.72), (1.72, 0.030, 0.035), rubber, interior, 0.004)
    add_cube("Iter4_Cockpit_ForwardFootwellWarmLane", (0.0, 0.986, -13.58), (0.76, 0.020, 1.24), warm_worn_path, interior, 0.010)
    add_cube("Iter4_Cockpit_ForwardFootwellDarkCenterSlot", (0.0, 1.006, -13.58), (0.22, 0.018, 1.02), soot, interior, 0.004)
    add_cube("Iter4_Cockpit_DashboardAmberSourceLeft", (-0.64, 1.285, -13.80), (0.22, 0.030, 0.10), amber, interior, 0.005)
    add_cube("Iter4_Cockpit_DashboardAmberSourceRight", (0.64, 1.285, -13.80), (0.22, 0.030, 0.10), amber, interior, 0.005)
    add_cube("Iter5_Cockpit_ConsolePaleReadableFaceLeft", (-0.56, 1.135, -14.88), (0.56, 0.105, 0.055), pale_panel, interior, 0.010)
    add_cube("Iter5_Cockpit_ConsolePaleReadableFaceRight", (0.56, 1.135, -14.88), (0.56, 0.105, 0.055), pale_panel, interior, 0.010)
    add_cube("Iter5_Cockpit_ConsoleDarkLowerSlot", (0.0, 1.006, -14.88), (1.46, 0.045, 0.050), rubber, interior, 0.004)
    add_cube("Iter5_Cockpit_ConsoleCyanInstrumentStrip", (0.0, 1.235, -14.74), (0.86, 0.030, 0.055), cyan, interior, 0.004)
    add_cube("Iter5_Cockpit_ForwardDashboardEdgeHighlight", (0.0, 1.225, -15.20), (1.72, 0.028, 0.040), scratched, interior, 0.004)
    add_cube("Cockpit_EntryDeckTrimLeft", (-1.60, 0.94, -4.92), (1.55, 0.10, 0.16), trim, interior, 0.03)
    add_cube("Cockpit_EntryDeckTrimRight", (1.60, 0.94, -4.92), (1.55, 0.10, 0.16), trim, interior, 0.03)
    add_cube("Cockpit_AftToeTrimLeft", (-1.34, 1.00, -11.84), (0.42, 0.08, 0.12), trim, interior, 0.02)
    add_cube("Cockpit_AftToeTrimRight", (1.34, 1.00, -11.84), (0.42, 0.08, 0.12), trim, interior, 0.02)
    add_cube("Cockpit_CenterPedestal", (0.0, 1.02, -14.10), (0.30, 0.24, 1.20), trim, interior, 0.035)
    add_cube("Cockpit_PedestalStatusLight", (0.0, 1.19, -14.54), (0.16, 0.04, 0.22), amber, interior, 0.012)
    for side, x in [("Left", -1.45), ("Right", 1.45)]:
        add_cube(f"Cockpit_{side}_SideConsoleBase", (x, 1.00, -13.95), (0.22, 0.12, 1.20), trim, interior, 0.035)
        add_cube(f"Cockpit_{side}_SideConsoleInsetGlass", (x, 1.10, -14.08), (0.18, 0.025, 0.58), glass, interior, 0.014)
        add_cube(f"Cockpit_{side}_LowSideSill", (x, 1.01, -12.70), (0.16, 0.07, 0.76), panel, interior, 0.025)
        add_cube(f"Cockpit_{side}_ForwardSillPad", (x, 1.03, -15.20), (0.16, 0.07, 0.42), panel, interior, 0.02)
        add_cube(f"Cockpit_{side}_CanopySideBaseRail", (x, 1.64, -12.80), (0.10, 0.16, 3.65), brushed, interior, 0.025)
        add_cube(f"Cockpit_{side}_CanopyLowerRubberSeal", (x * 0.96, 1.53, -12.80), (0.055, 0.07, 3.45), rubber, interior, 0.012)
        add_cube(f"Cockpit_{side}_LowCyanSideIndicator", (x * 0.90, 1.20, -14.18), (0.035, 0.050, 0.18), cyan, interior, 0.006)
        add_cube(f"Iter2_Cockpit_{side}_AngledInstrumentPaddle", (x * 0.90, 1.22, -13.52), (0.10, 0.11, 0.54), scratched, interior, 0.018)
        add_indicator_strip(f"Iter2_Cockpit_{side}_SideConsoleButtonLadder", (x * 0.91, 1.285, -13.74), 4, 0.12, (0.034, 0.026, 0.046), amber, interior, "z")
        add_cylinder_between(f"Iter2_Cockpit_{side}_CanopySillConduit", (x * 0.94, 1.76, -14.98), (x * 0.98, 1.69, -11.08), 0.022, scratched, interior, 10)
        add_cube(f"Iter3_Cockpit_{side}_ConsoleReadableTopPlane", (x * 0.88, 1.16, -13.54), (0.42, 0.040, 0.86), warm_worn_path, interior, 0.014)
        add_cube(f"Iter3_Cockpit_{side}_DarkCanopyLowerShadowStrip", (x * 0.98, 1.60, -12.45), (0.050, 0.10, 1.35), soot, interior, 0.010)
        add_cube(f"Iter4_Cockpit_{side}_CanopyPaleInnerFrame", (x * 0.91, 1.88, -12.55), (0.075, 0.16, 2.40), pale_panel, interior, 0.018)
        add_cube(f"Iter4_Cockpit_{side}_CanopyBlackSealLower", (x * 0.82, 1.58, -12.55), (0.055, 0.060, 2.30), rubber, interior, 0.008)
        add_cube(f"Iter4_Cockpit_{side}_LargeReadableSideDisplay", (x * 0.92, 1.23, -14.18), (0.070, 0.20, 0.34), glass, interior, 0.010)
        add_cube(f"Iter5_Cockpit_{side}_SeatBackPaleBreakupPanel", (x, 1.60, -13.74), (0.30, 0.13, 0.020), seat_stitch, interior, 0.006)
        add_cube(f"Iter5_Cockpit_{side}_ArmrestScratchedTop", (x + (0.48 if x < 0 else -0.48), 1.205, -13.26), (0.095, 0.018, 0.34), scratched, interior, 0.006)
        add_cube(f"Iter5_Cockpit_{side}_SideGlowUnderConsole", (x * 0.88, 1.04, -13.26), (0.065, 0.030, 0.26), cool_light, interior, 0.004)
        add_cube(f"Iter6_Cockpit_{side}_LargeSideLinerPanelA", (x * 0.92, 1.42, -12.34), (0.070, 0.46, 0.88), pale_panel, interior, 0.018)
        add_cube(f"Iter6_Cockpit_{side}_LargeSideLinerPanelB", (x * 0.90, 1.30, -11.36), (0.065, 0.36, 0.66), panel, interior, 0.018)
        add_cube(f"Iter6_Cockpit_{side}_SideLinerDarkInset", (x * 0.86, 1.42, -12.34), (0.040, 0.24, 0.44), soot, interior, 0.008)
        add_cube(f"Iter6_Cockpit_{side}_SideDisplayGlow", (x * 0.82, 1.42, -12.34), (0.035, 0.18, 0.30), cyan, interior, 0.005)
        add_cube(f"Iter6_Cockpit_{side}_CanopyShoulderBrushedRail", (x * 0.88, 1.96, -12.34), (0.080, 0.075, 1.36), scratched, interior, 0.010)
        add_cube(f"Iter6_Cockpit_{side}_SeatShoulderSoftTrim", (x * 0.32, 1.72, -13.70), (0.18, 0.14, 0.030), seat_stitch, interior, 0.006)
        add_cube(f"Iter7_Cockpit_{side}_OverheadCanopyRibCap", (x * 0.42, 2.18, -12.80), (0.11, 0.075, 2.00), scratched, interior, 0.012)
        add_cube(f"Iter7_Cockpit_{side}_OverheadSoftLiner", (x * 0.26, 2.08, -13.15), (0.42, 0.050, 1.12), pale_panel, interior, 0.014)
        for idx, z in enumerate([-12.05, -12.75, -13.45, -14.15]):
            add_cube(f"Iter8_Cockpit_{side}_CanopyRailFastener_{idx:02d}", (x * 0.82, 1.985, z), (0.045, 0.022, 0.045), scratched, interior, 0.004)
        add_indicator_strip(f"Iter8_Cockpit_{side}_SideDisplayButtonBank", (x * 0.90, 1.42, -12.74), 5, 0.07, (0.030, 0.022, 0.030), amber, interior, "z")
    add_cube("Iter10_Cockpit_DashboardCoolSourceLeft", (-0.72, 1.285, -14.36), (0.32, 0.032, 0.08), cool_light, interior, 0.005)
    add_cube("Iter10_Cockpit_DashboardCoolSourceRight", (0.72, 1.285, -14.36), (0.32, 0.032, 0.08), cool_light, interior, 0.005)
    add_cube("Iter10_Cockpit_LowerBulkheadWarmPractical", (0.0, 1.18, -14.98), (0.52, 0.035, 0.10), warm_light, interior, 0.006)
    add_cube("Iter10_Cockpit_LeftMetalSidePractical", (-1.30, 1.20, -13.18), (0.050, 0.14, 0.28), cool_light, interior, 0.006)
    add_cube("Iter10_Cockpit_RightMetalSidePractical", (1.30, 1.20, -13.18), (0.050, 0.14, 0.28), cool_light, interior, 0.006)
    add_cube("Iter10_Cockpit_LeftPracticalBackerPlate", (-1.34, 1.20, -13.18), (0.035, 0.22, 0.42), brushed, interior, 0.010)
    add_cube("Iter10_Cockpit_RightPracticalBackerPlate", (1.34, 1.20, -13.18), (0.035, 0.22, 0.42), brushed, interior, 0.010)

    # Gameplay collision correction for the aft side of the upper landing:
    # the visual deck now extends over the ramp opening, so add matching
    # walkable collision there instead of leaving it as a visual-only shelf.
    add_cube("COL_CockpitEntryLandingAftExtension", (0.0, 0.86383, -1.34), (1.92, 0.08, 1.44), collision_floor, collision, 0.0)
    add_cube("COL_CockpitEntryLandingRampDropGuardRail", (0.0, 1.28, -0.86), (2.86, 0.76, 0.18), collision_floor, collision, 0.0)


def patch_collision_layout_contract() -> None:
    if not COLLISION_LAYOUT_CONTRACT.exists():
        return

    payload = json.loads(COLLISION_LAYOUT_CONTRACT.read_text(encoding="utf-8"))
    surfaces = payload.setdefault("surfaces", [])
    extension = {
        "id": "cockpit_entry_landing_aft_extension",
        "kind": "floor_box",
        "center": [0.0, 0.86383, -1.34],
        "size": [1.92, 0.08, 1.44],
        "notes": "Centered structural detail pass extension for the aft landing surface above the ramp opening; kept out of side stair lanes.",
    }
    guard_rail = {
        "id": "cockpit_entry_landing_ramp_drop_guard_rail",
        "kind": "barrier_box",
        "center": [0.0, 1.28, -0.86],
        "size": [2.86, 0.76, 0.18],
        "notes": "Top landing safety guard rail across the central drop toward the cargo ramp; leaves side stair landing paths open.",
    }
    surfaces[:] = [
        surface
        for surface in surfaces
        if surface.get("id") not in {extension["id"], guard_rail["id"]}
    ]
    surfaces.append(extension)
    surfaces.append(guard_rail)
    COLLISION_LAYOUT_CONTRACT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    clear_previous()
    apply_structural_pass()
    patch_collision_layout_contract()
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE_BLEND))
    print(f"Applied prototype shuttle structural detail pass and saved {SOURCE_BLEND}")


if __name__ == "__main__":
    main()
