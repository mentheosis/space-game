#!/usr/bin/env python3
"""Create the prototype shuttle exterior silhouette and gross-volume scene."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import bpy


ROOT = Path(os.environ.get("SPACE_GAME_ROOT", Path.cwd())).resolve()
SOURCE_DIR = ROOT / "assets/source/blender/ships/prototype_shuttle"
SOURCE_BLEND = SOURCE_DIR / "prototype_shuttle.blend"
MODEL_DIR = ROOT / "assets/models/ship/prototype_shuttle"
ACTIVE_FLOORPLAN_CANDIDATE = MODEL_DIR / "active_floorplan_candidate.json"
REPORT_DIR = ROOT / "reports/prototype_shuttle"
SHUTTLE_OBJ = ROOT / "assets/models/ship/placeholders/oga_3d_space_ship_pack/ShuttleA.obj"
MARKER_CONTRACT = SOURCE_DIR / "prototype_shuttle_marker_contract.json"
LIGHT_CONTRACT = SOURCE_DIR / "prototype_shuttle_light_contract.json"
SCALE_PROXY_CONTRACT = SOURCE_DIR / "prototype_shuttle_scale_proxy_contract.json"
COLLISION_LAYOUT_CONTRACT = SOURCE_DIR / "prototype_shuttle_collision_layout_contract.json"
BRIEF = ROOT / "plans/0.3 roadmap to AAA/0.3.2 references/reference-brief.md"

# Runtime ShuttleA visual transform from scenes/ship/OpenGameArtShuttleVisual.tscn.
EXTERIOR_VISUAL_POSITION = (0.0, 2.12, 0.69)
EXTERIOR_VISUAL_SCALE = (1.27, 0.92, 0.92)
PROTOTYPE_UNIFORM_SCALE = 1.75
BELLY_DELTA_Z_MIN = -2.2
BELLY_DELTA_Z_MAX = 4.8
BELLY_LOWER_Y_MAX = 1.65
BELLY_EXTRA_DEPTH = 0.42
BELLY_EXTRA_WIDTH_FACTOR = 0.08
DEFAULT_FLOORPLAN_CANDIDATE = {
    "id": "default_human_approved_like",
    "ramp_floor_edge_z_offset": 1.25,
    "ramp_hinge_y_offset": -0.06,
    "ramp_tip_y_delta": -1.98,
    "ramp_tip_z_delta": -3.95,
    "ramp_aperture_z_min_delta": -1.45,
    "ramp_aperture_z_max_from_original_floor": 0.80,
    "cargo_forward_floor_trim": 1.25,
    "stair_count": 10,
    "stair_depth_scale": 1.08,
    "stair_width": 1.0,
    "stair_lane_gap": 0.18,
    "cockpit_entry_depth": 3.2,
    "cockpit_entry_z_bias": -0.42,
    "disable_walkable_floorplan": False,
}


def load_floorplan_candidate() -> dict[str, object]:
    candidate = dict(DEFAULT_FLOORPLAN_CANDIDATE)
    candidate_path = os.environ.get("PROTOTYPE_SHUTTLE_FLOORPLAN_CANDIDATE")
    if not candidate_path and ACTIVE_FLOORPLAN_CANDIDATE.exists():
        candidate_path = str(ACTIVE_FLOORPLAN_CANDIDATE)
    if candidate_path:
        payload = json.loads(Path(candidate_path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Floorplan candidate must be a JSON object: {candidate_path}")
        candidate.update(payload)
    if os.environ.get("PROTOTYPE_SHUTTLE_SAVE_ACTIVE_FLOORPLAN") == "1":
        ACTIVE_FLOORPLAN_CANDIDATE.parent.mkdir(parents=True, exist_ok=True)
        ACTIVE_FLOORPLAN_CANDIDATE.write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8")
    return candidate


def to_blender_loc(godot_loc: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = godot_loc
    return (x, -z, y)


def to_blender_dims(godot_dims: tuple[float, float, float]) -> tuple[float, float, float]:
    sx, sy, sz = godot_dims
    return (sx, sz, sy)


def transform_obj_vertex_to_ship_space(vertex: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = vertex
    px, py, pz = EXTERIOR_VISUAL_POSITION
    sx, sy, sz = EXTERIOR_VISUAL_SCALE
    return (px + x * sx, py + y * sy, pz - z * sz)


def apply_design_delta(point: tuple[float, float, float], center: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = point
    cx, cy, cz = center
    x = cx + (x - cx) * PROTOTYPE_UNIFORM_SCALE
    y = cy + (y - cy) * PROTOTYPE_UNIFORM_SCALE
    z = cz + (z - cz) * PROTOTYPE_UNIFORM_SCALE

    belly_min = cz + (BELLY_DELTA_Z_MIN - cz) * PROTOTYPE_UNIFORM_SCALE
    belly_max = cz + (BELLY_DELTA_Z_MAX - cz) * PROTOTYPE_UNIFORM_SCALE
    lower_y = cy + (BELLY_LOWER_Y_MAX - cy) * PROTOTYPE_UNIFORM_SCALE
    if belly_min <= z <= belly_max and y <= lower_y:
        t = (z - belly_min) / max(0.001, belly_max - belly_min)
        z_weight = math.sin(math.pi * t)
        y_weight = min(1.0, max(0.0, (lower_y - y) / 1.8))
        weight = z_weight * y_weight
        y -= BELLY_EXTRA_DEPTH * weight
        x = cx + (x - cx) * (1.0 + BELLY_EXTRA_WIDTH_FACTOR * weight)
    return (x, y, z)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def collection(name: str) -> bpy.types.Collection:
    existing = bpy.data.collections.get(name)
    if existing is not None:
        return existing
    created = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(created)
    return created


def link_to_collection(obj: bpy.types.Object, target: bpy.types.Collection) -> None:
    for existing in list(obj.users_collection):
        existing.objects.unlink(obj)
    target.objects.link(obj)


def material(
    name: str,
    color: tuple[float, float, float, float],
    roughness: float = 0.75,
    metallic: float = 0.0,
    alpha: float | None = None,
    emission: tuple[float, float, float, float] | None = None,
    emission_strength: float = 0.0,
) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if alpha is not None or color[3] < 1.0:
            bsdf.inputs["Alpha"].default_value = color[3] if alpha is None else alpha
            mat.blend_method = "BLEND"
            mat.use_screen_refraction = True
        if emission is not None:
            bsdf.inputs["Emission Color"].default_value = emission
            bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat


def add_cube(
    name: str,
    loc: tuple[float, float, float],
    dims: tuple[float, float, float],
    mat: bpy.types.Material,
    target: bpy.types.Collection,
    bevel: float = 0.04,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=to_blender_loc(loc))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = to_blender_dims(dims)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel > 0.0:
        modifier = obj.modifiers.new("blockout bevel", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
        obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    link_to_collection(obj, target)
    return obj


def add_sloped_panel(
    name: str,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    width: float,
    thickness: float,
    mat: bpy.types.Material,
    target: bpy.types.Collection,
    bevel: float = 0.03,
) -> bpy.types.Object:
    sx, sy, sz = start
    ex, ey, ez = end
    center = ((sx + ex) * 0.5, (sy + ey) * 0.5, (sz + ez) * 0.5)
    length = math.sqrt((ez - sz) ** 2 + (ey - sy) ** 2)
    obj = add_cube(name, center, (width, thickness, length), mat, target, bevel)
    obj.rotation_euler[0] = math.atan2(ey - sy, ez - sz)
    return obj


def add_open_ramp_panel(
    name: str,
    hinge: tuple[float, float, float],
    tip: tuple[float, float, float],
    width: float,
    thickness: float,
    mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> bpy.types.Object:
    half_width = width * 0.5
    hx, hy, hz = hinge
    tx, ty, tz = tip
    bottom_offset = thickness
    verts_godot = [
        (hx - half_width, hy, hz),
        (hx + half_width, hy, hz),
        (tx + half_width, ty, tz),
        (tx - half_width, ty, tz),
        (hx - half_width, hy - bottom_offset, hz),
        (hx + half_width, hy - bottom_offset, hz),
        (tx + half_width, ty - bottom_offset, tz),
        (tx - half_width, ty - bottom_offset, tz),
    ]
    verts = [to_blender_loc(point) for point in verts_godot]
    faces = [
        (0, 1, 2, 3),
        (7, 6, 5, 4),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (3, 7, 4, 0),
    ]
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(mat)
    target.objects.link(obj)
    bevel = obj.modifiers.new("ramp panel bevel", "BEVEL")
    bevel.width = 0.025
    bevel.segments = 1
    obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    return obj


def add_floor_collision_plane(
    name: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> bpy.types.Object:
    cx, cy, cz = center
    sx, _, sz = size
    half_x = sx * 0.5
    half_z = sz * 0.5
    verts_godot = [
        (cx - half_x, cy, cz - half_z),
        (cx + half_x, cy, cz - half_z),
        (cx + half_x, cy, cz + half_z),
        (cx - half_x, cy, cz + half_z),
    ]
    verts = [to_blender_loc(point) for point in verts_godot]
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(verts, [], [(0, 1, 2, 3), (3, 2, 1, 0)])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(mat)
    target.objects.link(obj)
    return obj


def add_ellipsoid(
    name: str,
    loc: tuple[float, float, float],
    dims: tuple[float, float, float],
    mat: bpy.types.Material,
    target: bpy.types.Collection,
    segments: int = 32,
    rings: int = 12,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=0.5, location=to_blender_loc(loc))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = to_blender_dims(dims)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    obj.modifiers.new("canopy weighted normals", "WEIGHTED_NORMAL")
    link_to_collection(obj, target)
    return obj


def add_flat_prism(
    name: str,
    points_xz: list[tuple[float, float]],
    y_center: float,
    thickness: float,
    mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> bpy.types.Object:
    top_y = y_center + thickness * 0.5
    bottom_y = y_center - thickness * 0.5
    verts_godot = [(x, top_y, z) for x, z in points_xz] + [(x, bottom_y, z) for x, z in points_xz]
    verts = [to_blender_loc(point) for point in verts_godot]
    count = len(points_xz)
    faces: list[tuple[int, ...]] = [tuple(range(count)), tuple(range(count * 2 - 1, count - 1, -1))]
    for index in range(count):
        faces.append((index, (index + 1) % count, count + (index + 1) % count, count + index))
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(mat)
    target.objects.link(obj)
    bevel = obj.modifiers.new("silhouette edge bevel", "BEVEL")
    bevel.width = 0.035
    bevel.segments = 1
    obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    return obj


def add_vertical_prism(
    name: str,
    points_zy: list[tuple[float, float]],
    x_center: float,
    thickness: float,
    mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> bpy.types.Object:
    left_x = x_center - thickness * 0.5
    right_x = x_center + thickness * 0.5
    verts_godot = [(left_x, y, z) for z, y in points_zy] + [(right_x, y, z) for z, y in points_zy]
    verts = [to_blender_loc(point) for point in verts_godot]
    count = len(points_zy)
    faces: list[tuple[int, ...]] = [tuple(range(count)), tuple(range(count * 2 - 1, count - 1, -1))]
    for index in range(count):
        faces.append((index, (index + 1) % count, count + (index + 1) % count, count + index))
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(mat)
    target.objects.link(obj)
    bevel = obj.modifiers.new("fin edge bevel", "BEVEL")
    bevel.width = 0.045
    bevel.segments = 1
    obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    return obj


def add_cargo_section_prism(
    name: str,
    sections: list[dict[str, float]],
    mat: bpy.types.Material,
    target: bpy.types.Collection,
    x_offset: float = 0.0,
    width_scale: float = 1.0,
) -> bpy.types.Object:
    if len(sections) < 2:
        raise ValueError("Cargo section prism needs at least two sections")
    verts_godot: list[tuple[float, float, float]] = []
    for section in sections:
        z = section["z"]
        lower = section["lower_half_width"]
        upper = section["upper_half_width"]
        bottom = section["bottom"]
        mid = section["mid"]
        top = section["top"]
        lower *= width_scale
        upper *= width_scale
        verts_godot.extend(
            [
                (x_offset - lower, bottom, z),
                (x_offset + lower, bottom, z),
                (x_offset + lower, mid, z),
                (x_offset + upper, top, z),
                (x_offset - upper, top, z),
                (x_offset - lower, mid, z),
            ]
        )
    verts = [to_blender_loc(point) for point in verts_godot]
    ring_count = len(sections)
    ring_size = 6
    faces: list[tuple[int, ...]] = [tuple(range(ring_size - 1, -1, -1))]
    last = (ring_count - 1) * ring_size
    faces.append(tuple(last + index for index in range(ring_size)))
    for ring_index in range(ring_count - 1):
        base = ring_index * ring_size
        nxt = (ring_index + 1) * ring_size
        for index in range(ring_size):
            faces.append((base + index, base + (index + 1) % ring_size, nxt + (index + 1) % ring_size, nxt + index))
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(mat)
    target.objects.link(obj)
    bevel = obj.modifiers.new("cargo prism bevel", "BEVEL")
    bevel.width = 0.045
    bevel.segments = 1
    obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    return obj


def read_shuttle_a_points_by_material() -> tuple[list[tuple[float, float, float]], dict[str, list[tuple[float, float, float]]]]:
    raw: list[tuple[float, float, float] | None] = [None]
    current_material = "<none>"
    all_points: list[tuple[float, float, float]] = []
    by_material: dict[str, list[tuple[float, float, float]]] = {}
    for line in SHUTTLE_OBJ.read_text(encoding="utf-8").splitlines():
        if line.startswith("v "):
            _, x, y, z, *_ = line.split()
            raw.append((float(x), float(y), float(z)))
            continue
        if line.startswith("usemtl "):
            current_material = line.split(None, 1)[1].strip()
            continue
        if not line.startswith("f "):
            continue
        for part in line.split()[1:]:
            vertex = raw[int(part.split("/")[0])]
            if vertex is None:
                continue
            point = transform_obj_vertex_to_ship_space(vertex)
            all_points.append(point)
            by_material.setdefault(current_material, []).append(point)
    if not all_points:
        raise RuntimeError(f"No vertices found in {SHUTTLE_OBJ}")
    return all_points, by_material


def point_bounds(points: list[tuple[float, float, float]]) -> dict[str, tuple[float, float, float]]:
    mins = tuple(min(point[index] for point in points) for index in range(3))
    maxs = tuple(max(point[index] for point in points) for index in range(3))
    center = tuple((mins[index] + maxs[index]) * 0.5 for index in range(3))
    size = tuple(maxs[index] - mins[index] for index in range(3))
    return {"min": mins, "max": maxs, "center": center, "size": size}


def derive_cargo_prism_sections(volume_boxes: dict[str, dict[str, tuple[float, float, float]]]) -> list[dict[str, float]]:
    section_names = ["forward", "mid", "aft"]
    sections: list[dict[str, float]] = []
    for name in section_names:
        lower = volume_boxes.get(f"cargo_{name}_lower")
        upper = volume_boxes.get(f"cargo_{name}_upper")
        if lower is None:
            continue
        lower_pos = lower["position"]
        lower_size = lower["size"]
        upper_pos = upper["position"] if upper else lower_pos
        upper_size = upper["size"] if upper else lower_size
        lower_bottom = lower_pos[1] - lower_size[1] * 0.5
        lower_top = lower_pos[1] + lower_size[1] * 0.5
        upper_bottom = upper_pos[1] - upper_size[1] * 0.5
        upper_top = upper_pos[1] + upper_size[1] * 0.5
        sections.append(
            {
                "z": lower_pos[2],
                "bottom": lower_bottom,
                "mid": max(lower_top, upper_bottom),
                "top": upper_top,
                "lower_half_width": lower_size[0] * 0.5,
                "upper_half_width": upper_size[0] * 0.5,
            }
        )
    if len(sections) < 2 and "cargo" in volume_boxes:
        cargo = volume_boxes["cargo"]
        pos = cargo["position"]
        size = cargo["size"]
        for z_offset in [-0.5, 0.0, 0.5]:
            sections.append(
                {
                    "z": pos[2] + size[2] * z_offset,
                    "bottom": pos[1] - size[1] * 0.5,
                    "mid": pos[1],
                    "top": pos[1] + size[1] * 0.5,
                    "lower_half_width": size[0] * 0.5,
                    "upper_half_width": size[0] * 0.38,
                }
            )
    return sorted(sections, key=lambda item: item["z"])


def derive_transition_prism_sections(
    volume_boxes: dict[str, dict[str, tuple[float, float, float]]],
    cargo_sections: list[dict[str, float]],
) -> list[dict[str, float]]:
    cockpit = volume_boxes.get("cockpit")
    if cockpit is None or not cargo_sections:
        return []
    cockpit_pos = cockpit["position"]
    cockpit_size = cockpit["size"]
    cockpit_aft_z = cockpit_pos[2] + cockpit_size[2] * 0.5
    cockpit_bottom = cockpit_pos[1] - cockpit_size[1] * 0.5
    cockpit_top = cockpit_pos[1] + cockpit_size[1] * 0.5
    cockpit_half_width = cockpit_size[0] * 0.42

    cargo_forward = min(cargo_sections, key=lambda item: item["z"])
    cargo_z = cargo_forward["z"]
    transition_start_z = cockpit_aft_z - 0.35
    transition_end_z = cargo_z + 0.35
    if transition_end_z <= transition_start_z:
        transition_end_z = transition_start_z + 1.2
    mid_t = 0.55
    transition_mid_z = transition_start_z + (transition_end_z - transition_start_z) * mid_t

    cargo_bottom = cargo_forward["bottom"]
    cargo_mid = cargo_forward["mid"]
    cargo_lower = cargo_forward["lower_half_width"]
    cargo_upper = cargo_forward["upper_half_width"]

    return [
        {
            "z": transition_start_z,
            "bottom": cockpit_bottom - 0.05,
            "mid": (cockpit_bottom + cockpit_top) * 0.5,
            "top": cockpit_top + 0.05,
            "lower_half_width": max(0.75, cockpit_half_width),
            "upper_half_width": max(0.65, cockpit_half_width * 0.82),
        },
        {
            "z": transition_mid_z,
            "bottom": cockpit_bottom * (1.0 - mid_t) + cargo_bottom * mid_t,
            "mid": ((cockpit_bottom + cockpit_top) * 0.5) * (1.0 - mid_t) + cargo_mid * mid_t,
            "top": cockpit_top * (1.0 - mid_t) + (cargo_mid + 0.42) * mid_t,
            "lower_half_width": cockpit_half_width * (1.0 - mid_t) + cargo_lower * 0.52 * mid_t,
            "upper_half_width": cockpit_half_width * 0.82 * (1.0 - mid_t) + cargo_upper * 0.58 * mid_t,
        },
        {
            "z": transition_end_z,
            "bottom": cargo_bottom,
            "mid": cargo_mid,
            "top": cargo_mid + 0.42,
            "lower_half_width": max(1.05, cargo_lower * 0.52),
            "upper_half_width": max(0.85, cargo_upper * 0.58),
        },
    ]


def derive_forward_ramp_contract(
    volume_boxes: dict[str, dict[str, tuple[float, float, float]]],
    cargo_sections: list[dict[str, float]],
    floorplan_candidate: dict[str, object],
) -> dict[str, object]:
    cargo_forward_lower = volume_boxes.get("cargo_forward_lower")
    cargo_forward_floor_z = (
        cargo_forward_lower["position"][2] - cargo_forward_lower["size"][2] * 0.5
        if cargo_forward_lower is not None
        else volume_boxes["ramp"]["position"][2] + volume_boxes["ramp"]["size"][2] * 0.5
    )
    cargo_forward_floor_y = min(section["bottom"] for section in cargo_sections) if cargo_sections else volume_boxes["ramp"]["position"][1]
    width = max(3.1, volume_boxes["ramp"]["size"][0] * 1.08)
    # Keep the open ramp deterministic: its top edge is the trimmed cargo
    # floor edge, lowered slightly so the player never catches on an upward lip.
    cargo_floor_edge_z = cargo_forward_floor_z + float(floorplan_candidate["ramp_floor_edge_z_offset"])
    hinge = (0.0, cargo_forward_floor_y + float(floorplan_candidate["ramp_hinge_y_offset"]), cargo_floor_edge_z)
    tip = (
        0.0,
        cargo_forward_floor_y + float(floorplan_candidate["ramp_tip_y_delta"]),
        cargo_floor_edge_z + float(floorplan_candidate["ramp_tip_z_delta"]),
    )
    return {
        "width": width,
        "hinge": hinge,
        "tip": tip,
        "aperture": {
            "x_min": -width * 0.62,
            "x_max": width * 0.62,
            "y_min": cargo_forward_floor_y - 0.30,
            "y_max": cargo_forward_floor_y + 2.35,
            "z_min": cargo_floor_edge_z + float(floorplan_candidate["ramp_aperture_z_min_delta"]),
            "z_max": cargo_forward_floor_z + float(floorplan_candidate["ramp_aperture_z_max_from_original_floor"]),
        },
    }


def derive_interior_volume_boxes(points: list[tuple[float, float, float]]) -> dict[str, dict[str, tuple[float, float, float]]]:
    def percentile(values: list[float], fraction: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
        return ordered[index]

    def smooth_profile(values: list[float], passes: int = 2) -> list[float]:
        smoothed = values[:]
        for _ in range(passes):
            next_values = smoothed[:]
            for idx in range(1, len(smoothed) - 1):
                next_values[idx] = smoothed[idx - 1] * 0.25 + smoothed[idx] * 0.5 + smoothed[idx + 1] * 0.25
            smoothed = next_values
        return smoothed

    z_min = min(point[2] for point in points)
    z_max = max(point[2] for point in points)
    span = max(z_max - z_min, 0.0001)
    bins = 96
    buckets: list[list[tuple[float, float, float]]] = [[] for _ in range(bins)]
    for point in points:
        index = min(bins - 1, max(0, int(((point[2] - z_min) / span) * bins)))
        buckets[index].append(point)

    for index, bucket in enumerate(buckets):
        if bucket:
            continue
        left = next((buckets[i] for i in range(index - 1, -1, -1) if buckets[i]), None)
        right = next((buckets[i] for i in range(index + 1, bins) if buckets[i]), None)
        buckets[index] = left or right or []

    z_values: list[float] = []
    x_min_values: list[float] = []
    x_max_values: list[float] = []
    y_min_values: list[float] = []
    y_max_values: list[float] = []
    for index, bucket in enumerate(buckets):
        if not bucket:
            continue
        xs = [point[0] for point in bucket]
        ys = [point[1] for point in bucket]
        z_values.append(z_min + (index + 0.5) * span / bins)
        # Use a central fuselage quantile band; full min/max is dominated by
        # wings, fins, and small exterior details that are not interior room.
        x_min_values.append(percentile(xs, 0.14))
        x_max_values.append(percentile(xs, 0.86))
        y_min_values.append(percentile(ys, 0.06))
        y_max_values.append(percentile(ys, 0.94))

    x_min_values = smooth_profile(x_min_values)
    x_max_values = smooth_profile(x_max_values)
    y_min_values = smooth_profile(y_min_values)
    y_max_values = smooth_profile(y_max_values)

    slices: list[dict[str, float]] = []
    for index, z in enumerate(z_values):
        center_x = (x_min_values[index] + x_max_values[index]) * 0.5
        center_y = (y_min_values[index] + y_max_values[index]) * 0.5
        radius_x = max((x_max_values[index] - x_min_values[index]) * 0.5 - 0.22, 0.05)
        radius_y = max((y_max_values[index] - y_min_values[index]) * 0.5 - 0.22, 0.05)
        slices.append(
            {
                "z": z,
                "cx": center_x,
                "cy": center_y,
                "rx": radius_x,
                "ry": radius_y,
                "left": center_x - radius_x,
                "right": center_x + radius_x,
                "bottom": center_y - radius_y,
                "top": center_y + radius_y,
                "width": radius_x * 2.0,
                "height": radius_y * 2.0,
            }
        )

    def slice_at(z: float) -> dict[str, float]:
        index = min(len(slices) - 1, max(0, round(((z - z_min) / span) * (len(slices) - 1))))
        return slices[index]

    def point_inside_slice(x: float, y: float, profile: dict[str, float], clearance: float = 0.0) -> bool:
        rx = max(profile["rx"] - clearance, 0.001)
        ry = max(profile["ry"] - clearance, 0.001)
        nx = abs(x - profile["cx"]) / rx
        ny = abs(y - profile["cy"]) / ry
        # Superellipse approximates the rounded rectangular fuselage envelope
        # better than a circular ellipse while remaining deterministic.
        return nx**2.8 + ny**2.2 <= 1.0

    usable_points: list[tuple[float, float, float]] = []
    x_samples = 34
    y_samples = 32
    wall_clearance = 0.18
    for profile in slices:
        for xi in range(x_samples):
            x = profile["left"] + (profile["right"] - profile["left"]) * (xi + 0.5) / x_samples
            for yi in range(y_samples):
                y = profile["bottom"] + (profile["top"] - profile["bottom"]) * (yi + 0.5) / y_samples
                if point_inside_slice(x, y, profile, wall_clearance):
                    usable_points.append((x, y, profile["z"]))

    if not usable_points:
        return {
            "cargo": {"position": (0.0, 1.2, 0.4), "size": (3.2, 1.6, 5.0)},
            "cockpit": {"position": (0.0, 2.6, -7.1), "size": (2.2, 1.1, 2.6)},
            "ramp": {"position": (0.0, 0.55, -3.2), "size": (2.8, 0.85, 1.7)},
            "left_ascent": {"position": (-1.1, 2.0, -4.1), "size": (0.62, 1.0, 2.6)},
            "right_ascent": {"position": (1.1, 2.0, -4.1), "size": (0.62, 1.0, 2.6)},
            "pilot_seat": {"position": (-0.55, 2.5, -7.1), "size": (0.54, 0.78, 0.68)},
            "copilot_seat": {"position": (0.55, 2.5, -7.1), "size": (0.54, 0.78, 0.68)},
        }

    def box_from_points(
        region_points: list[tuple[float, float, float]],
        x_fit: tuple[float, float] = (0.04, 0.96),
        y_fit: tuple[float, float] = (0.04, 0.96),
        z_fit: tuple[float, float] = (0.02, 0.98),
        min_size: tuple[float, float, float] = (0.2, 0.2, 0.6),
    ) -> dict[str, tuple[float, float, float]]:
        xs = [point[0] for point in region_points]
        ys = [point[1] for point in region_points]
        zs = [point[2] for point in region_points]
        x0 = percentile(xs, x_fit[0])
        x1 = percentile(xs, x_fit[1])
        y0 = percentile(ys, y_fit[0])
        y1 = percentile(ys, y_fit[1])
        z0 = percentile(zs, z_fit[0])
        z1 = percentile(zs, z_fit[1])
        size = (max(min_size[0], x1 - x0), max(min_size[1], y1 - y0), max(min_size[2], z1 - z0))
        return {
            "position": ((x0 + x1) * 0.5, (y0 + y1) * 0.5, (z0 + z1) * 0.5),
            "size": size,
        }

    # Semantic split is intentionally broad: the voxel field decides available
    # volume, while these cut planes express the two-level shuttle concept.
    cockpit_cut_z = z_min + span * 0.50
    cargo_start_z = z_min + span * 0.52
    cargo_points = [
        point
        for point in usable_points
        if point[2] >= cargo_start_z
        and point[1] <= slice_at(point[2])["cy"] + 0.62
    ]
    cockpit_points = [
        point
        for point in usable_points
        if point[2] <= cockpit_cut_z
        and point[1] >= slice_at(point[2])["cy"] - 0.60
    ]

    cargo = box_from_points(cargo_points, (0.03, 0.97), (0.08, 0.72), (0.01, 0.99), (2.4, 1.2, 4.0))
    cockpit = box_from_points(cockpit_points, (0.06, 0.94), (0.08, 0.92), (0.01, 0.99), (1.4, 1.2, 2.4))

    cargo_z0 = cargo["position"][2] - cargo["size"][2] * 0.5
    cargo_z1 = cargo["position"][2] + cargo["size"][2] * 0.5
    cargo_segment_boxes: dict[str, dict[str, tuple[float, float, float]]] = {}
    cargo_segment_names = ["forward", "mid", "aft"]
    for segment_index, segment_name in enumerate(cargo_segment_names):
        segment_z0 = cargo_z0 + (cargo_z1 - cargo_z0) * segment_index / 3.0
        segment_z1 = cargo_z0 + (cargo_z1 - cargo_z0) * (segment_index + 1) / 3.0
        segment_points = [point for point in cargo_points if segment_z0 <= point[2] <= segment_z1]
        if segment_points:
            split_y = percentile([point[1] for point in segment_points], 0.58)
            lower_points = [point for point in segment_points if point[1] <= split_y]
            upper_points = [point for point in segment_points if point[1] > split_y]
            for vertical_name, vertical_points, x_fit, y_fit in [
                ("lower", lower_points, (0.03, 0.97), (0.06, 0.94)),
                ("upper", upper_points, (0.12, 0.88), (0.08, 0.92)),
            ]:
                if not vertical_points:
                    continue
                cargo_segment_boxes[f"cargo_{segment_name}_{vertical_name}"] = box_from_points(
                    vertical_points,
                    x_fit,
                    y_fit,
                    (0.01, 0.99),
                    (1.2, 0.45, max(1.0, (segment_z1 - segment_z0) * 0.65)),
                )
        else:
            cargo_segment_boxes[f"cargo_{segment_name}_lower"] = {
                "position": (cargo["position"][0], cargo["position"][1], (segment_z0 + segment_z1) * 0.5),
                "size": (cargo["size"][0], cargo["size"][1], segment_z1 - segment_z0),
            }

    cargo_pos = cargo["position"]
    cargo_size = cargo["size"]
    cockpit_pos = cockpit["position"]
    cockpit_size = cockpit["size"]
    cargo_front = cargo_pos[2] - cargo_size[2] * 0.5
    cockpit_aft = cockpit_pos[2] + cockpit_size[2] * 0.5
    ramp_z = cargo_front - 0.85
    ascent_z = (cargo_front + cockpit_aft) * 0.5
    ascent_depth = max(1.0, abs(cockpit_aft - cargo_front))

    return {
        "cargo": cargo,
        **cargo_segment_boxes,
        "cockpit": cockpit,
        "ramp": {
            "position": (0.0, max(0.35, cargo_pos[1] - cargo_size[1] * 0.45), ramp_z),
            "size": (min(2.8, cargo_size[0] * 0.65), 0.85, 1.7),
        },
        "left_ascent": {
            "position": (-min(1.1, cargo_size[0] * 0.24), (cargo_pos[1] + cockpit_pos[1]) * 0.5, ascent_z),
            "size": (0.62, max(0.8, abs(cockpit_pos[1] - cargo_pos[1]) + 0.25), ascent_depth),
        },
        "right_ascent": {
            "position": (min(1.1, cargo_size[0] * 0.24), (cargo_pos[1] + cockpit_pos[1]) * 0.5, ascent_z),
            "size": (0.62, max(0.8, abs(cockpit_pos[1] - cargo_pos[1]) + 0.25), ascent_depth),
        },
        "pilot_seat": {
            "position": (-min(0.55, cockpit_size[0] * 0.23), cockpit_pos[1] - cockpit_size[1] * 0.12, cockpit_pos[2] - cockpit_size[2] * 0.22),
            "size": (0.54, 0.78, 0.68),
        },
        "copilot_seat": {
            "position": (min(0.55, cockpit_size[0] * 0.23), cockpit_pos[1] - cockpit_size[1] * 0.12, cockpit_pos[2] - cockpit_size[2] * 0.22),
            "size": (0.54, 0.78, 0.68),
        },
    }


def smooth_values(values: list[float], passes: int = 2) -> list[float]:
    smoothed = values[:]
    for _ in range(passes):
        next_values = smoothed[:]
        for index in range(1, len(smoothed) - 1):
            next_values[index] = smoothed[index - 1] * 0.25 + smoothed[index] * 0.5 + smoothed[index + 1] * 0.25
        smoothed = next_values
    return smoothed


def create_reference_envelope_hull(
    points: list[tuple[float, float, float]],
    mat: bpy.types.Material,
    target: bpy.types.Collection,
    bins: int = 52,
    ring_segments: int = 18,
) -> bpy.types.Object:
    z_min = min(point[2] for point in points)
    z_max = max(point[2] for point in points)
    span = max(z_max - z_min, 0.0001)
    buckets: list[list[tuple[float, float, float]]] = [[] for _ in range(bins)]
    for point in points:
        index = min(bins - 1, max(0, int(((point[2] - z_min) / span) * bins)))
        buckets[index].append(point)

    # Fill any empty slice from the closest non-empty neighbor so the generated
    # hull remains continuous even if the source mesh has local gaps.
    for index, bucket in enumerate(buckets):
        if bucket:
            continue
        left = next((buckets[i] for i in range(index - 1, -1, -1) if buckets[i]), None)
        right = next((buckets[i] for i in range(index + 1, bins) if buckets[i]), None)
        buckets[index] = left or right or []

    x_min = [min(point[0] for point in bucket) for bucket in buckets]
    x_max = [max(point[0] for point in bucket) for bucket in buckets]
    y_min = [min(point[1] for point in bucket) for bucket in buckets]
    y_max = [max(point[1] for point in bucket) for bucket in buckets]
    x_min = smooth_values(x_min)
    x_max = smooth_values(x_max)
    y_min = smooth_values(y_min)
    y_max = smooth_values(y_max)

    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for index in range(bins):
        t = index / max(1, bins - 1)
        z = z_min + t * span
        cx = (x_min[index] + x_max[index]) * 0.5
        cy = (y_min[index] + y_max[index]) * 0.5
        rx = max((x_max[index] - x_min[index]) * 0.5, 0.04)
        ry = max((y_max[index] - y_min[index]) * 0.5, 0.04)
        for segment in range(ring_segments):
            angle = math.tau * segment / ring_segments
            # Superellipse-ish cross-section keeps broad ShuttleA wing/belly
            # envelopes without making every slice a perfect round tube.
            cos_v = math.cos(angle)
            sin_v = math.sin(angle)
            x = cx + math.copysign(abs(cos_v) ** 0.72, cos_v) * rx
            y = cy + math.copysign(abs(sin_v) ** 0.82, sin_v) * ry
            verts.append(to_blender_loc((x, y, z)))

    for ring_index in range(bins - 1):
        base = ring_index * ring_segments
        nxt = (ring_index + 1) * ring_segments
        for segment in range(ring_segments):
            faces.append((base + segment, base + (segment + 1) % ring_segments, nxt + (segment + 1) % ring_segments, nxt + segment))
    faces.append(tuple(range(ring_segments - 1, -1, -1)))
    last = (bins - 1) * ring_segments
    faces.append(tuple(last + segment for segment in range(ring_segments)))

    mesh = bpy.data.meshes.new("PrototypeShuttleReferenceEnvelopeHullMesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("ReferenceEnvelopeExteriorHull", mesh)
    obj.data.materials.append(mat)
    target.objects.link(obj)
    obj.modifiers.new("envelope weighted normals", "WEIGHTED_NORMAL")
    return obj


def create_reference_mesh_exterior(
    reference_by_material: dict[str, list[tuple[float, float, float]]],
    material_map: dict[str, bpy.types.Material],
    target: bpy.types.Collection,
    ramp_contract: dict[str, object] | None = None,
) -> bpy.types.Object:
    def point_inside_aperture(point: tuple[float, float, float], margin: float = 0.0) -> bool:
        if ramp_contract is None:
            return False
        aperture = ramp_contract["aperture"]
        assert isinstance(aperture, dict)
        return (
            float(aperture["x_min"]) - margin <= point[0] <= float(aperture["x_max"]) + margin
            and float(aperture["y_min"]) - margin <= point[1] <= float(aperture["y_max"]) + margin
            and float(aperture["z_min"]) - margin <= point[2] <= float(aperture["z_max"]) + margin
        )

    def face_crosses_aperture(face_indices: tuple[int, ...], raw_godot: list[tuple[float, float, float] | None]) -> bool:
        if ramp_contract is None:
            return False
        points = [raw_godot[index + 1] for index in face_indices if raw_godot[index + 1] is not None]
        if len(points) < 3:
            return False
        centroid = tuple(sum(point[axis] for point in points) / len(points) for axis in range(3))
        if point_inside_aperture(centroid, margin=0.08):
            return True
        if not any(point_inside_aperture(point, margin=0.16) for point in points):
            return False
        aperture = ramp_contract["aperture"]
        assert isinstance(aperture, dict)
        # Keep upper hull/canopy faces that merely share a wide triangle with
        # the cut area. The ramp aperture is a lower-belly operation.
        return centroid[1] <= float(aperture["y_max"]) + 0.2

    all_reference_points = [point for points in reference_by_material.values() for point in points]
    reference_center = point_bounds(all_reference_points)["center"]
    raw: list[tuple[float, float, float] | None] = [None]
    raw_godot: list[tuple[float, float, float] | None] = [None]
    faces: list[tuple[int, ...]] = []
    face_materials: list[str] = []
    current_material = "Hull"
    for line in SHUTTLE_OBJ.read_text(encoding="utf-8").splitlines():
        if line.startswith("v "):
            _, x, y, z, *_ = line.split()
            point = transform_obj_vertex_to_ship_space((float(x), float(y), float(z)))
            point = apply_design_delta(point, reference_center)
            raw.append(to_blender_loc(point))
            raw_godot.append(point)
            continue
        if line.startswith("usemtl "):
            current_material = line.split(None, 1)[1].strip()
            continue
        if not line.startswith("f "):
            continue
        face = tuple(int(part.split("/")[0]) - 1 for part in line.split()[1:])
        if len(face) >= 3:
            if face_crosses_aperture(face, raw_godot):
                continue
            faces.append(face)
            face_materials.append(current_material)

    verts = [point for point in raw[1:] if point is not None]
    mesh = bpy.data.meshes.new("PrototypeShuttleExactReferenceBlockoutMesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("ExactShuttleAReferenceBlockoutExterior", mesh)
    slot_by_material: dict[str, int] = {}
    for material_name in ("Hull", "Accent", "Cockpit"):
        slot_by_material[material_name] = len(obj.data.materials)
        obj.data.materials.append(material_map.get(material_name, material_map["Hull"]))
    for index, material_name in enumerate(face_materials):
        mesh.polygons[index].material_index = slot_by_material.get(material_name, slot_by_material["Hull"])
    target.objects.link(obj)
    obj.modifiers.new("reference weighted normals", "WEIGHTED_NORMAL")
    return obj


def add_marker(name: str, loc: tuple[float, float, float], target: bpy.types.Collection) -> None:
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = "SPHERE"
    empty.empty_display_size = 0.25
    empty.location = to_blender_loc(loc)
    empty["godot_position"] = list(loc)
    target.objects.link(empty)


def add_light_marker(light: dict[str, object], target: bpy.types.Collection) -> None:
    name = str(light["id"])
    position = light["position"]
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "SPHERE"
    obj.empty_display_size = 0.35
    obj.location = to_blender_loc(tuple(position))
    for key, value in light.items():
        obj[key] = json.dumps(value) if isinstance(value, (dict, list)) else value
    target.objects.link(obj)


def ring_points(width: float, low_y: float, high_y: float, belly_y: float) -> list[tuple[float, float]]:
    return [
        (-width * 0.18, high_y),
        (width * 0.18, high_y),
        (width * 0.48, high_y - 0.35),
        (width * 0.58, (high_y + belly_y) * 0.5),
        (width * 0.48, low_y + 0.15),
        (width * 0.20, belly_y),
        (-width * 0.20, belly_y),
        (-width * 0.48, low_y + 0.15),
        (-width * 0.58, (high_y + belly_y) * 0.5),
        (-width * 0.48, high_y - 0.35),
    ]


def create_hull(mat: bpy.types.Material, target: bpy.types.Collection) -> bpy.types.Object:
    sections = [
        (-11.0, 0.8, 1.55, 0.62, 0.72),
        (-9.5, 1.9, 2.55, 0.44, 0.72),
        (-7.4, 2.85, 3.15, 0.36, 0.78),
        (-5.0, 3.35, 3.05, 0.32, 0.92),
        (-2.0, 4.15, 2.85, 0.20, 1.20),
        (1.8, 4.75, 2.75, 0.12, 1.30),
        (5.2, 4.25, 2.65, 0.18, 1.22),
        (8.2, 2.55, 2.42, 0.45, 0.98),
        (10.2, 1.05, 2.05, 0.75, 0.85),
    ]
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    rings: list[list[tuple[float, float, float]]] = []
    for z, width, high_y, low_y, belly_y in sections:
        ring = [(x, y, z) for x, y in ring_points(width, low_y, high_y, belly_y)]
        rings.append(ring)
        verts.extend(to_blender_loc(point) for point in ring)

    per_ring = len(rings[0])
    for ring_index in range(len(rings) - 1):
        base = ring_index * per_ring
        nxt = (ring_index + 1) * per_ring
        for index in range(per_ring):
            faces.append((base + index, base + (index + 1) % per_ring, nxt + (index + 1) % per_ring, nxt + index))
    faces.append(tuple(range(per_ring - 1, -1, -1)))
    last = (len(rings) - 1) * per_ring
    faces.append(tuple(last + index for index in range(per_ring)))

    mesh = bpy.data.meshes.new("PrototypeShuttleExteriorHullBlockoutMesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("ExteriorHullBlockout", mesh)
    obj.data.materials.append(mat)
    target.objects.link(obj)
    bevel = obj.modifiers.new("hull soft edges", "BEVEL")
    bevel.width = 0.035
    bevel.segments = 2
    obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    return obj


def create_scene() -> None:
    clear_scene()
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    exterior = collection("Exterior")
    interior = collection("Interior")
    collision = collection("Collision")
    markers = collection("Markers")
    lights = collection("Lights")
    cameras = collection("ReviewCameras")
    proxies = collection("ScaleProxies")
    collection("Disabled_Source")

    hull_mat = material("proto_hull_warm_white_silhouette", (0.78, 0.8, 0.78, 0.86), 0.62, 0.05, alpha=0.86)
    wing_mat = material("proto_wing_dark_graphite_blockout", (0.16, 0.17, 0.17, 1), 0.7, 0.1)
    glass_mat = material("proto_canopy_smoked_glass_volume", (0.04, 0.16, 0.20, 0.40), 0.08, 0.0, alpha=0.40)
    cargo_mat = material("proto_cargo_volume_amber", (1.0, 0.56, 0.12, 0.34), 0.72, 0.0, alpha=0.34)
    cockpit_mat = material("proto_cockpit_volume_cyan", (0.12, 0.58, 1.0, 0.32), 0.6, 0.0, alpha=0.32)
    wall_mat = material("proto_transition_volume_green", (0.28, 0.85, 0.32, 0.28), 0.78, 0.0, alpha=0.28)
    ramp_mat = material("proto_belly_ramp_blockout", (0.30, 0.32, 0.31, 1), 0.8, 0.0)
    seat_mat = material("proto_seat_dark_fabric_blockout", (0.08, 0.085, 0.09, 1), 0.9, 0.0)
    proxy_mat = material("proto_scale_proxy_blue", (0.12, 0.45, 1.0, 0.32), 0.4, 0.0, alpha=0.32)
    light_mat = material(
        "proto_emissive_warm_strip",
        (1.0, 0.78, 0.42, 1),
        0.35,
        0.0,
        emission=(1.0, 0.68, 0.32, 1),
        emission_strength=1.8,
    )

    reference_points, reference_by_material = read_shuttle_a_points_by_material()
    reference_center = point_bounds(reference_points)["center"]
    prototype_exterior_points = [apply_design_delta(point, reference_center) for point in reference_points]
    volume_boxes = derive_interior_volume_boxes(prototype_exterior_points)
    floorplan_candidate = load_floorplan_candidate()
    cargo_prism_sections = derive_cargo_prism_sections(volume_boxes)
    transition_prism_sections = derive_transition_prism_sections(volume_boxes, cargo_prism_sections)
    ramp_contract = derive_forward_ramp_contract(volume_boxes, cargo_prism_sections, floorplan_candidate)
    create_reference_mesh_exterior(
        reference_by_material,
        {"Hull": hull_mat, "Accent": wing_mat, "Cockpit": glass_mat},
        exterior,
        ramp_contract,
    )

    cargo_segment_keys = [
        key
        for key in ["cargo_forward_lower", "cargo_forward_upper", "cargo_mid_lower", "cargo_mid_upper", "cargo_aft_lower", "cargo_aft_upper"]
        if key in volume_boxes
    ]
    if len(cargo_prism_sections) >= 2:
        add_cargo_section_prism("VOLUME_LowerBellyCargoPrismaticEnvelope", cargo_prism_sections, cargo_mat, interior)
    elif cargo_segment_keys:
        for key in cargo_segment_keys:
            add_cube(f"VOLUME_{key.title().replace('_', '')}Envelope", volume_boxes[key]["position"], volume_boxes[key]["size"], cargo_mat, interior, 0.035)
    else:
        add_cube("VOLUME_LowerBellyCargoDeckEnvelope", volume_boxes["cargo"]["position"], volume_boxes["cargo"]["size"], cargo_mat, interior, 0.035)
    add_cube("VOLUME_RaisedForwardCockpitDeckEnvelope", volume_boxes["cockpit"]["position"], volume_boxes["cockpit"]["size"], cockpit_mat, interior, 0.035)
    ramp_hinge = tuple(ramp_contract["hinge"])
    ramp_tip = tuple(ramp_contract["tip"])
    ramp_width = float(ramp_contract["width"])
    add_open_ramp_panel(
        "VOLUME_ForwardBellyRampOpenPanel",
        ramp_hinge,
        ramp_tip,
        ramp_width,
        0.12,
        ramp_mat,
        interior,
    )
    aperture = ramp_contract["aperture"]
    assert isinstance(aperture, dict)
    aperture_center_z = (float(aperture["z_min"]) + float(aperture["z_max"])) * 0.5
    aperture_depth = float(aperture["z_max"]) - float(aperture["z_min"])
    aperture_mid_y = (float(aperture["y_min"]) + float(aperture["y_max"])) * 0.5
    aperture_height = float(aperture["y_max"]) - float(aperture["y_min"])
    frame_width = ramp_width + 0.42
    add_cube("ForwardRampApertureLeftFrame", (-frame_width * 0.5, aperture_mid_y, aperture_center_z), (0.16, aperture_height, aperture_depth), wing_mat, interior, 0.03)
    add_cube("ForwardRampApertureRightFrame", (frame_width * 0.5, aperture_mid_y, aperture_center_z), (0.16, aperture_height, aperture_depth), wing_mat, interior, 0.03)
    if len(transition_prism_sections) >= 2:
        side_lane_half_width = 0.55
        side_lane_offset = ramp_width * 0.5 + side_lane_half_width + 0.18
        side_width_scale = min(
            0.42,
            side_lane_half_width / max(
                0.001,
                min(
                    min(section["lower_half_width"], section["upper_half_width"])
                    for section in transition_prism_sections
                ),
            ),
        )
        add_cargo_section_prism("VOLUME_LeftCargoToCockpitTransitionPrism", transition_prism_sections, wall_mat, interior, x_offset=-side_lane_offset, width_scale=side_width_scale)
        add_cargo_section_prism("VOLUME_RightCargoToCockpitTransitionPrism", transition_prism_sections, wall_mat, interior, x_offset=side_lane_offset, width_scale=side_width_scale)
    else:
        add_cube("VOLUME_LeftCargoToCockpitAscent", volume_boxes["left_ascent"]["position"], volume_boxes["left_ascent"]["size"], wall_mat, interior, 0.025).rotation_euler[0] = math.radians(-22)
        add_cube("VOLUME_RightCargoToCockpitAscent", volume_boxes["right_ascent"]["position"], volume_boxes["right_ascent"]["size"], wall_mat, interior, 0.025).rotation_euler[0] = math.radians(-22)
    add_cube("PilotSeatScaleBlockout", volume_boxes["pilot_seat"]["position"], volume_boxes["pilot_seat"]["size"], seat_mat, interior, 0.08)
    add_cube("CopilotSeatScaleBlockout", volume_boxes["copilot_seat"]["position"], volume_boxes["copilot_seat"]["size"], seat_mat, interior, 0.08)
    add_cube("CargoVolumeWarmReferenceStripLeft", (-2.18, 2.92, 0.6), (0.08, 0.08, 3.8), light_mat, interior, 0.02)
    add_cube("CargoVolumeWarmReferenceStripRight", (2.18, 2.92, 0.6), (0.08, 0.08, 3.8), light_mat, interior, 0.02)

    # Temporary export placeholders only. 0.3.2a does not accept traversal or
    # stair collision as a gate; real collision starts after shape lock.
    cargo_floor = volume_boxes["cargo"]["position"]
    cargo_floor_size = volume_boxes["cargo"]["size"]
    cockpit_floor = volume_boxes["cockpit"]["position"]
    cockpit_floor_size = volume_boxes["cockpit"]["size"]
    ramp_floor = volume_boxes["ramp"]["position"]
    ramp_floor_size = volume_boxes["ramp"]["size"]
    collision_layout_surfaces: list[dict[str, object]] = []
    cargo_floor_segment_keys = [key for key in cargo_segment_keys if key.endswith("_lower")]
    if cargo_floor_segment_keys:
        for key in cargo_floor_segment_keys:
            segment_pos = volume_boxes[key]["position"]
            segment_size = volume_boxes[key]["size"]
            floor_y = segment_pos[1] - segment_size[1] * 0.5
            if key == "cargo_forward_lower":
                original_min_z = segment_pos[2] - segment_size[2] * 0.5
                original_max_z = segment_pos[2] + segment_size[2] * 0.5
                adjusted_min_z = original_min_z + float(floorplan_candidate["cargo_forward_floor_trim"])
                adjusted_size_z = max(0.5, original_max_z - adjusted_min_z)
                adjusted_center_z = adjusted_min_z + adjusted_size_z * 0.5
                floor_center = (segment_pos[0], floor_y, adjusted_center_z)
                floor_size = (segment_size[0], 0.08, adjusted_size_z)
                add_cube(
                    f"COL_TEMP_{key.title().replace('_', '')}Floor",
                    floor_center,
                    floor_size,
                    cargo_mat,
                    collision,
                    0.0,
                )
                collision_layout_surfaces.append({"id": key, "kind": "floor_box", "center": floor_center, "size": floor_size})
            else:
                floor_center = (segment_pos[0], floor_y, segment_pos[2])
                floor_size = (segment_size[0], 0.08, segment_size[2])
                add_cube(
                    f"COL_TEMP_{key.title().replace('_', '')}Floor",
                    floor_center,
                    floor_size,
                    cargo_mat,
                    collision,
                    0.0,
                )
                collision_layout_surfaces.append({"id": key, "kind": "floor_box", "center": floor_center, "size": floor_size})
    else:
        add_cube("COL_TEMP_CargoVolumeFloor", (0.0, cargo_floor[1] - cargo_floor_size[1] * 0.5, cargo_floor[2]), (cargo_floor_size[0], 0.08, cargo_floor_size[2]), cargo_mat, collision, 0.0)
        collision_layout_surfaces.append({
            "id": "cargo",
            "kind": "floor_box",
            "center": (0.0, cargo_floor[1] - cargo_floor_size[1] * 0.5, cargo_floor[2]),
            "size": (cargo_floor_size[0], 0.08, cargo_floor_size[2]),
        })
    cockpit_floor_center = (0.0, cockpit_floor[1] - cockpit_floor_size[1] * 0.5, cockpit_floor[2])
    cockpit_floor_box_size = (cockpit_floor_size[0], 0.08, cockpit_floor_size[2])
    add_cube(
        "COL_TEMP_CockpitVolumeFloor",
        cockpit_floor_center,
        cockpit_floor_box_size,
        cockpit_mat,
        collision,
        0.0,
    )
    collision_layout_surfaces.append({"id": "cockpit_floor", "kind": "floor_box", "center": cockpit_floor_center, "size": cockpit_floor_box_size})
    add_open_ramp_panel(
        "COL_TEMP_ForwardBellyOpenRamp",
        ramp_hinge,
        ramp_tip,
        ramp_width,
        0.08,
        ramp_mat,
        collision,
    )
    collision_layout_surfaces.append({
        "id": "forward_belly_ramp",
        "kind": "ramp_panel",
        "hinge": ramp_hinge,
        "tip": ramp_tip,
        "width": ramp_width,
        "thickness": 0.08,
    })
    if len(transition_prism_sections) >= 2:
        transition_start = min(transition_prism_sections, key=lambda item: item["z"])
        transition_end = max(transition_prism_sections, key=lambda item: item["z"])
        start_floor = transition_start["bottom"]
        end_floor = transition_end["bottom"]
        start_z = transition_start["z"]
        end_z = transition_end["z"]
        transition_width = min(
            min(section["lower_half_width"], section["upper_half_width"]) * 2.0
            for section in transition_prism_sections
        )
        step_count = int(floorplan_candidate["stair_count"])
        step_depth = abs(end_z - start_z) / step_count * float(floorplan_candidate["stair_depth_scale"])
        step_width = float(floorplan_candidate["stair_width"])
        side_lane_offset = ramp_width * 0.5 + step_width * 0.5 + float(floorplan_candidate["stair_lane_gap"])
        cockpit_entry_floor_y = cockpit_floor[1] - cockpit_floor_size[1] * 0.5
        cockpit_entry_depth = float(floorplan_candidate["cockpit_entry_depth"])
        cockpit_entry_z_bias = float(floorplan_candidate["cockpit_entry_z_bias"])
        add_cube(
            "COL_TEMP_CockpitEntryLanding",
            (0.0, cockpit_entry_floor_y, start_z + cockpit_entry_depth * cockpit_entry_z_bias),
            (side_lane_offset * 2.0 + step_width, 0.08, cockpit_entry_depth),
            cockpit_mat,
            collision,
            0.0,
        )
        collision_layout_surfaces.append({
            "id": "cockpit_entry_landing",
            "kind": "floor_box",
            "center": (0.0, cockpit_entry_floor_y, start_z + cockpit_entry_depth * cockpit_entry_z_bias),
            "size": (side_lane_offset * 2.0 + step_width, 0.08, cockpit_entry_depth),
        })
        for side_name, x_offset in [("Left", -side_lane_offset), ("Right", side_lane_offset)]:
            for step_index in range(step_count):
                t0 = step_index / step_count
                t1 = (step_index + 1) / step_count
                t_mid = (t0 + t1) * 0.5
                z_mid = start_z * (1.0 - t_mid) + end_z * t_mid
                floor_y = start_floor * (1.0 - t_mid) + end_floor * t_mid
                step_center = (x_offset, floor_y, z_mid)
                step_box_size = (step_width, 0.10, step_depth)
                add_cube(
                    f"COL_TEMP_{side_name}CargoToCockpitTransitionStep{step_index:02d}",
                    step_center,
                    step_box_size,
                    wall_mat,
                    collision,
                    0.0,
                )
                collision_layout_surfaces.append({
                    "id": f"{side_name.lower()}_stair_{step_index:02d}",
                    "kind": "floor_box",
                    "side": side_name.lower(),
                    "step_index": step_index,
                    "center": step_center,
                    "size": step_box_size,
                })

    if bool(floorplan_candidate.get("disable_walkable_floorplan")):
        for obj in list(collision.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        add_cube(
            "COL_TEMP_DisabledFloorplanMarker",
            (0.0, -1000.0, 0.0),
            (0.1, 0.1, 0.1),
            wall_mat,
            collision,
            0.0,
        )
        collision_layout_surfaces = []

    cargo_pos = volume_boxes["cargo"]["position"]
    cargo_size = volume_boxes["cargo"]["size"]
    cockpit_pos = volume_boxes["cockpit"]["position"]
    cockpit_size = volume_boxes["cockpit"]["size"]
    ramp_pos = volume_boxes["ramp"]["position"]
    ramp_size = volume_boxes["ramp"]["size"]
    pilot_pos = volume_boxes["pilot_seat"]["position"]
    copilot_pos = volume_boxes["copilot_seat"]["position"]
    marker_positions = {
        "InteriorSpawn": (0.0, cargo_pos[1] - cargo_size[1] * 0.35, cargo_pos[2] - cargo_size[2] * 0.45),
        "ExteriorExit": ramp_tip,
        "SeatAnchor": pilot_pos,
        "PilotEye": (pilot_pos[0], pilot_pos[1] + 0.58, pilot_pos[2] - 0.62),
        "SeatExit": (0.0, cockpit_pos[1] - cockpit_size[1] * 0.20, cockpit_pos[2] + cockpit_size[2] * 0.18),
        "CanopyTarget": (0.0, cockpit_pos[1] + cockpit_size[1] * 0.20, cockpit_pos[2] - cockpit_size[2] * 0.55),
        "HatchCenter": ramp_pos,
        "RampStart": ramp_hinge,
        "RampEnd": ramp_tip,
        "CopilotSeatAnchor": copilot_pos,
        "CopilotEye": (copilot_pos[0], copilot_pos[1] + 0.58, copilot_pos[2] - 0.62),
        "CargoDeckCenter": cargo_pos,
        "CockpitDeckCenter": cockpit_pos,
    }
    for name, loc in marker_positions.items():
        add_marker(name, loc, markers)

    light_contract = {
        "schema_version": 1,
        "ship_id": "prototype_shuttle",
        "lights": [
            {
                "id": "cargo_warm_left",
                "godot_node": "CargoWarmLeft",
                "godot_type": "OmniLight3D",
                "parent": "Lights",
                "position": [-2.0, 2.9, 0.35],
                "properties": {"light_color": [1.0, 0.76, 0.46, 1.0], "light_energy": 0.9, "omni_range": 4.5},
            },
            {
                "id": "cargo_warm_right",
                "godot_node": "CargoWarmRight",
                "godot_type": "OmniLight3D",
                "parent": "Lights",
                "position": [2.0, 2.9, 0.35],
                "properties": {"light_color": [1.0, 0.76, 0.46, 1.0], "light_energy": 0.9, "omni_range": 4.5},
            },
            {
                "id": "cockpit_soft_key",
                "godot_node": "CockpitSoftKey",
                "godot_type": "OmniLight3D",
                "parent": "Lights",
                "position": [0.0, 4.0, -6.6],
                "properties": {"light_color": [0.72, 0.86, 1.0, 1.0], "light_energy": 0.65, "omni_range": 3.6},
            },
        ],
    }
    for light in light_contract["lights"]:
        add_light_marker(light, lights)

    marker_contract = {
        "schema_version": 1,
        "ship_id": "prototype_shuttle",
        "markers": [
            {"id": name, "godot_node": name, "position": [round(v, 5) for v in loc]}
            for name, loc in marker_positions.items()
        ],
    }
    scale_proxy_contract = {
        "schema_version": 1,
        "ship_id": "prototype_shuttle",
        "proxies": [
            {
                "id": "standing_player_capsule",
                "type": "capsule",
                "position": [round(v, 5) for v in marker_positions["InteriorSpawn"]],
                "radius": 0.38,
                "height": 1.78,
                "label": "standing player at cargo entry",
            },
            {
                "id": "standing_player_cockpit_capsule",
                "type": "capsule",
                "position": [round(v, 5) for v in marker_positions["CockpitDeckCenter"]],
                "radius": 0.38,
                "height": 1.78,
                "label": "standing player on raised cockpit deck",
            },
            {
                "id": "seated_pilot_capsule",
                "type": "capsule",
                "position": [round(v, 5) for v in marker_positions["SeatAnchor"]],
                "radius": 0.34,
                "height": 1.12,
                "label": "seated pilot",
            },
            {
                "id": "seated_copilot_capsule",
                "type": "capsule",
                "position": [round(v, 5) for v in marker_positions["CopilotSeatAnchor"]],
                "radius": 0.34,
                "height": 1.12,
                "label": "seated copilot",
            },
            {
                "id": "pilot_eye_to_canopy",
                "type": "ray",
                "start_marker": "PilotEye",
                "end_marker": "CanopyTarget",
                "label": "pilot eye to canopy",
            },
            {
                "id": "belly_ramp_path",
                "type": "segment",
                "start_marker": "RampStart",
                "end_marker": "RampEnd",
                "label": "forward-opening belly ramp path",
            },
        ],
    }
    for proxy in scale_proxy_contract["proxies"]:
        if proxy["type"] == "capsule":
            loc = tuple(proxy["position"])
            add_cube(f"PROXY_{proxy['id']}", loc, (proxy["radius"] * 2.0, proxy["height"], proxy["radius"] * 2.0), proxy_mat, proxies, 0.03)

    collision_layout_contract = {
        "schema_version": 1,
        "ship_id": "prototype_shuttle",
        "units": "meters",
        "floorplan_candidate": floorplan_candidate,
        "player": {
            "radius": 0.36,
            "max_step_height": 0.48,
            "minimum_landing_depth": 1.1,
            "minimum_overlap": 0.24,
        },
        "surfaces": [
            {
                key: ([round(v, 5) for v in value] if isinstance(value, tuple) else value)
                for key, value in surface.items()
            }
            for surface in collision_layout_surfaces
        ],
        "route": [
            "forward_belly_ramp",
            "cargo_forward_lower",
            "left_stair_09",
            "left_stair_00",
            "cockpit_entry_landing",
            "cockpit_floor",
        ],
        "notes": [
            "Static collision layout contract generated from deterministic prototype shuttle volumes.",
            "The route uses both side stair lanes; left is listed as representative and right is validated separately.",
        ],
    }

    MARKER_CONTRACT.write_text(json.dumps(marker_contract, indent=2) + "\n", encoding="utf-8")
    LIGHT_CONTRACT.write_text(json.dumps(light_contract, indent=2) + "\n", encoding="utf-8")
    SCALE_PROXY_CONTRACT.write_text(json.dumps(scale_proxy_contract, indent=2) + "\n", encoding="utf-8")
    COLLISION_LAYOUT_CONTRACT.write_text(json.dumps(collision_layout_contract, indent=2) + "\n", encoding="utf-8")

    camera_specs = {
        "ReviewExteriorFront": ((0.0, 5.2, -30.0), (0.0, 2.4, -1.0), 42),
        "ReviewExteriorLeft": ((-30.0, 4.8, 0.0), (0.0, 2.2, 0.0), 42),
        "ReviewExteriorTop": ((0.0, 38.0, 0.0), (0.0, 2.0, 0.0), 42),
        "ReviewCargoDeck": ((0.0, 1.55, -9.2), (0.0, 1.45, -1.8), 68),
        "ReviewCockpitDeck": ((0.0, 3.25, -3.0), (0.0, 3.2, -8.0), 68),
    }
    for name, (loc, target, fov) in camera_specs.items():
        cam_data = bpy.data.cameras.new(name)
        cam = bpy.data.objects.new(name, cam_data)
        cam.location = to_blender_loc(loc)
        direction = bpy.mathutils.Vector(to_blender_loc(target)) - cam.location if False else None
        cameras.objects.link(cam)
        cam["godot_position"] = list(loc)
        cam["godot_target"] = list(target)
        cam["fov"] = fov

    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE_BLEND))
    (REPORT_DIR / "prototype_shuttle_bootstrap_report.json").write_text(
        json.dumps(
            {
                "ship_id": "prototype_shuttle",
                "source_blend": str(SOURCE_BLEND.relative_to(ROOT)),
                "brief": str(BRIEF.relative_to(ROOT)),
                "concept": "deterministic ShuttleA OBJ mesh seed with measured prototype deltas for larger scale and modest lower-belly cargo expansion",
                "design_delta": {
                    "uniform_scale": PROTOTYPE_UNIFORM_SCALE,
                    "belly_delta_z_min": BELLY_DELTA_Z_MIN,
                    "belly_delta_z_max": BELLY_DELTA_Z_MAX,
                    "belly_lower_y_max": BELLY_LOWER_Y_MAX,
                    "belly_extra_depth": BELLY_EXTRA_DEPTH,
                    "belly_extra_width_factor": BELLY_EXTRA_WIDTH_FACTOR,
                },
                "marker_count": len(marker_positions),
                "light_count": len(light_contract["lights"]),
                "scale_proxy_count": len(scale_proxy_contract["proxies"]),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    create_scene()
