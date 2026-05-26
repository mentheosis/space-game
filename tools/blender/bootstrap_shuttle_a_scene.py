#!/usr/bin/env python3
"""Create the initial ShuttleA Blender source scene.

Run with Blender:

    blender --background --python tools/blender/bootstrap_shuttle_a_scene.py

This is not final art. It creates the source-file structure, imports the chosen
ShuttleA exterior as locked reference geometry, and builds the first authored
interior modeling scaffold in Blender so future polish happens in a real DCC
workflow instead of procedural OBJ text generation.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(os.environ.get("SPACE_GAME_ROOT", Path.cwd())).resolve()
SOURCE_BLEND = ROOT / "assets/source/blender/ships/shuttle_a/shuttle_a_interior.blend"
SHUTTLE_OBJ = ROOT / "assets/models/ship/placeholders/oga_3d_space_ship_pack/ShuttleA.obj"
MARKERS_JSON = ROOT / "assets/models/ship/shuttle_a/shuttle_a_markers.json"
REFERENCE_FIT_JSON = ROOT / "reports/ship_modeling/shuttle_a_reference_fit.json"

# Match scenes/ship/OpenGameArtShuttleVisual.tscn. The imported OBJ is rotated
# 180 degrees around Godot Y, then scaled and offset as the visible exterior.
EXTERIOR_VISUAL_POSITION = (0.0, 2.12, 0.69)
EXTERIOR_VISUAL_SCALE = (1.27, 0.92, 0.92)


def to_blender_loc(godot_loc: tuple[float, float, float]) -> tuple[float, float, float]:
    """Convert project/Godot coordinates (Y-up, -Z forward) to Blender Z-up."""
    x, y, z = godot_loc
    return (x, -z, y)


def to_blender_dims(godot_dims: tuple[float, float, float]) -> tuple[float, float, float]:
    sx, sy, sz = godot_dims
    return (sx, sz, sy)


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


def material(name: str, color: tuple[float, float, float, float], roughness: float = 0.75, metallic: float = 0.0) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if color[3] < 1.0:
            bsdf.inputs["Alpha"].default_value = color[3]
            mat.blend_method = "BLEND"
            mat.use_screen_refraction = True
    return mat


def transform_obj_vertex_to_ship_space(vertex: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = vertex
    px, py, pz = EXTERIOR_VISUAL_POSITION
    sx, sy, sz = EXTERIOR_VISUAL_SCALE
    return (px + x * sx, py + y * sy, pz - z * sz)


def read_material_bounds(material_name: str, object_prefix: str = "AttackShuttle.LOD1") -> dict[str, tuple[float, float, float]]:
    verts: list[tuple[float, float, float] | None] = [None]
    current_object = ""
    current_material = ""
    selected: list[tuple[float, float, float]] = []

    for line in SHUTTLE_OBJ.read_text(encoding="utf-8").splitlines():
        if line.startswith("v "):
            _, x, y, z, *_ = line.split()
            verts.append((float(x), float(y), float(z)))
            continue

        if line.startswith("o "):
            current_object = line[2:].strip()
            continue

        if line.startswith("usemtl "):
            current_material = line.split(None, 1)[1]
            continue

        if not line.startswith("f "):
            continue

        if not current_object.startswith(object_prefix) or current_material != material_name:
            continue

        for part in line.split()[1:]:
            vertex_index = int(part.split("/")[0])
            vertex = verts[vertex_index]
            if vertex is not None:
                selected.append(transform_obj_vertex_to_ship_space(vertex))

    if not selected:
        raise ValueError(f"No vertices found for material {material_name!r} in {object_prefix!r}")

    xs = [point[0] for point in selected]
    ys = [point[1] for point in selected]
    zs = [point[2] for point in selected]
    return {
        "min": (min(xs), min(ys), min(zs)),
        "max": (max(xs), max(ys), max(zs)),
        "center": (
            (min(xs) + max(xs)) * 0.5,
            (min(ys) + max(ys)) * 0.5,
            (min(zs) + max(zs)) * 0.5,
        ),
        "size": (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)),
    }


def write_reference_fit_report(cockpit_bounds: dict[str, tuple[float, float, float]]) -> None:
    REFERENCE_FIT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REFERENCE_FIT_JSON.write_text(
        json.dumps(
            {
                "source_obj": str(SHUTTLE_OBJ.relative_to(ROOT)),
                "visual_transform_source": "scenes/ship/OpenGameArtShuttleVisual.tscn",
                "exterior_visual_position": list(EXTERIOR_VISUAL_POSITION),
                "exterior_visual_scale": list(EXTERIOR_VISUAL_SCALE),
                "cockpit_material_bounds_ship_space": {
                    key: list(value) for key, value in cockpit_bounds.items()
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def emissive_material(name: str, color: tuple[float, float, float, float], energy: float = 1.0) -> bpy.types.Material:
    mat = material(name, color, 0.25, 0.0)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Emission Color"].default_value = color
        bsdf.inputs["Emission Strength"].default_value = energy
    return mat


def add_beveled_cube(
    name: str,
    loc: tuple[float, float, float],
    scale: tuple[float, float, float],
    mat: bpy.types.Material,
    target: bpy.types.Collection,
    bevel: float = 0.04,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=to_blender_loc(loc))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = to_blender_dims(scale)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel > 0.0:
        modifier = obj.modifiers.new("small bevels", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
        modifier.affect = "EDGES"
        obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    link_to_collection(obj, target)
    return obj


def create_loft_mesh(
    name: str,
    sections: list[tuple[float, list[tuple[float, float]]]],
    mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> bpy.types.Object:
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []
    for z, profile in sections:
        for x, y in profile:
            verts.append(to_blender_loc((x, y, z)))

    points_per_ring = len(sections[0][1])
    for ring_index in range(len(sections) - 1):
        base = ring_index * points_per_ring
        nxt = (ring_index + 1) * points_per_ring
        for point_index in range(points_per_ring - 1):
            faces.append((
                base + point_index,
                nxt + point_index,
                nxt + point_index + 1,
                base + point_index + 1,
            ))

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(mat)
    target.objects.link(obj)
    obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    return obj


def create_panel_patch(
    name: str,
    corners: list[tuple[float, float, float]],
    mat: bpy.types.Material,
    target: bpy.types.Collection,
    thickness: float = 0.035,
) -> bpy.types.Object:
    """Create a slightly raised quad panel in project/Godot coordinates."""
    if len(corners) != 4:
        raise ValueError("panel patch requires four corners")
    points = [Vector(to_blender_loc(corner)) for corner in corners]
    center = sum(points, Vector()) / 4.0
    normal = (points[1] - points[0]).cross(points[2] - points[0]).normalized()
    raised = [point + normal * thickness for point in points]
    verts = [tuple(point) for point in points + raised]
    faces = [
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (3, 7, 4, 0),
    ]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(mat)
    target.objects.link(obj)
    bevel = obj.modifiers.new("soft panel bevel", "BEVEL")
    bevel.width = 0.025
    bevel.segments = 2
    obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    return obj


def create_raised_panel_grid(
    prefix: str,
    side: float,
    z_values: list[float],
    wall_x: float,
    mat: bpy.types.Material,
    accent_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    label = "L" if side < 0 else "R"
    for index, z in enumerate(z_values):
        lower_x = wall_x
        upper_x = wall_x * 0.93
        create_panel_patch(
            f"{prefix}_lower_panel_{label}_{index}",
            [
                (side * lower_x, 0.54, z - 0.36),
                (side * lower_x, 0.54, z + 0.36),
                (side * lower_x * 0.96, 0.96, z + 0.32),
                (side * lower_x * 0.96, 0.96, z - 0.32),
            ],
            mat,
            target,
            0.018,
        )
        create_panel_patch(
            f"{prefix}_upper_panel_{label}_{index}",
            [
                (side * upper_x, 1.20, z - 0.29),
                (side * upper_x, 1.20, z + 0.29),
                (side * upper_x * 0.96, 1.52, z + 0.25),
                (side * upper_x * 0.96, 1.52, z - 0.25),
            ],
            mat,
            target,
            0.016,
        )
        create_panel_patch(
            f"{prefix}_dark_inner_recess_{label}_{index}",
            [
                (side * wall_x * 0.99, 0.67, z - 0.22),
                (side * wall_x * 0.99, 0.67, z + 0.22),
                (side * wall_x * 0.96, 0.84, z + 0.20),
                (side * wall_x * 0.96, 0.84, z - 0.20),
            ],
            accent_mat,
            target,
            0.010,
        )
        add_cylinder_between(
            f"{prefix}_pin_rail_top_{label}_{index}",
            (side * (wall_x * 0.93), 1.58, z - 0.26),
            (side * (wall_x * 0.93), 1.58, z + 0.26),
            0.009,
            accent_mat,
            target,
            8,
        )
        add_cylinder_between(
            f"{prefix}_pin_rail_bottom_{label}_{index}",
            (side * (wall_x * 0.92), 0.48, z - 0.28),
            (side * (wall_x * 0.92), 0.48, z + 0.28),
            0.009,
            accent_mat,
            target,
            8,
        )


def create_side_liner_segment(
    prefix: str,
    side: float,
    z0: float,
    z1: float,
    x0: float,
    x1: float,
    lower_y0: float,
    lower_y1: float,
    upper_y0: float,
    upper_y1: float,
    wall_mat: bpy.types.Material,
    recess_mat: bpy.types.Material,
    trim_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Create a continuous fitted side wall panel behind smaller detail parts."""
    label = "L" if side < 0 else "R"
    create_panel_patch(
        f"{prefix}_main_liner_{label}_{z0:.1f}_{z1:.1f}",
        [
            (side * x0, lower_y0, z0),
            (side * x1, lower_y1, z1),
            (side * x1 * 0.96, upper_y1, z1),
            (side * x0 * 0.96, upper_y0, z0),
        ],
        wall_mat,
        target,
        0.030,
    )
    create_panel_patch(
        f"{prefix}_lower_cove_{label}_{z0:.1f}_{z1:.1f}",
        [
            (side * (x0 * 0.70), 0.34, z0),
            (side * (x1 * 0.72), 0.34, z1),
            (side * x1, lower_y1 + 0.08, z1),
            (side * x0, lower_y0 + 0.08, z0),
        ],
        recess_mat,
        target,
        0.026,
    )
    add_cylinder_between(
        f"{prefix}_upper_integrated_trim_{label}_{z0:.1f}_{z1:.1f}",
        (side * x0 * 0.93, upper_y0 - 0.08, z0),
        (side * x1 * 0.93, upper_y1 - 0.08, z1),
        0.026,
        trim_mat,
        target,
        12,
    )
    add_cylinder_between(
        f"{prefix}_lower_integrated_trim_{label}_{z0:.1f}_{z1:.1f}",
        (side * x0 * 0.82, lower_y0 + 0.14, z0),
        (side * x1 * 0.82, lower_y1 + 0.14, z1),
        0.024,
        trim_mat,
        target,
        12,
    )


def create_cockpit_cheek(
    name: str,
    side: float,
    mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> bpy.types.Object:
    """Create a sloped side surface tying the corridor shell into the canopy."""
    sections: list[tuple[float, list[tuple[float, float]]]] = []
    for z, inner_x, outer_x, lower_y, upper_y in [
        (-10.45, 0.58, 0.86, 0.96, 1.46),
        (-9.35, 0.70, 1.02, 0.84, 1.58),
        (-8.00, 0.78, 1.08, 0.82, 1.68),
        (-6.60, 0.76, 0.98, 0.96, 1.78),
    ]:
        sections.append((z, [
            (side * inner_x, lower_y),
            (side * outer_x, lower_y + 0.18),
            (side * outer_x, upper_y),
            (side * inner_x, upper_y - 0.18),
        ]))
    obj = create_loft_mesh(name, sections, mat, target)
    bevel = obj.modifiers.new("soft cheek bevel", "BEVEL")
    bevel.width = 0.018
    bevel.segments = 2
    return obj


def create_box_from_godot_points(
    name: str,
    points: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    mat: bpy.types.Material,
    target: bpy.types.Collection,
    bevel_width: float = 0.02,
) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([to_blender_loc(point) for point in points], [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(mat)
    target.objects.link(obj)
    if bevel_width > 0.0:
        bevel = obj.modifiers.new("soft bevel", "BEVEL")
        bevel.width = bevel_width
        bevel.segments = 2
    obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    return obj


def create_tapered_prism(
    name: str,
    center: tuple[float, float, float],
    bottom_size: tuple[float, float, float],
    top_size: tuple[float, float, float],
    mat: bpy.types.Material,
    target: bpy.types.Collection,
    bevel_width: float = 0.03,
) -> bpy.types.Object:
    cx, cy, cz = center
    bx, by, bz = bottom_size
    tx, ty, tz = top_size
    y0 = cy - by * 0.5
    y1 = cy + ty * 0.5
    points = [
        (cx - bx * 0.5, y0, cz - bz * 0.5),
        (cx + bx * 0.5, y0, cz - bz * 0.5),
        (cx + bx * 0.5, y0, cz + bz * 0.5),
        (cx - bx * 0.5, y0, cz + bz * 0.5),
        (cx - tx * 0.5, y1, cz - tz * 0.5),
        (cx + tx * 0.5, y1, cz - tz * 0.5),
        (cx + tx * 0.5, y1, cz + tz * 0.5),
        (cx - tx * 0.5, y1, cz + tz * 0.5),
    ]
    faces = [
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (3, 7, 4, 0),
    ]
    return create_box_from_godot_points(name, points, faces, mat, target, bevel_width)


def create_sloped_console(
    name: str,
    mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> bpy.types.Object:
    points = [
        (-0.92, 0.56, -9.12),
        (0.92, 0.56, -9.12),
        (0.74, 0.56, -10.18),
        (-0.74, 0.56, -10.18),
        (-0.78, 1.02, -9.22),
        (0.78, 1.02, -9.22),
        (0.54, 1.30, -10.22),
        (-0.54, 1.30, -10.22),
    ]
    faces = [
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (3, 7, 4, 0),
    ]
    return create_box_from_godot_points(name, points, faces, mat, target, 0.035)


def create_seat_bucket(
    name: str,
    mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> bpy.types.Object:
    points = [
        (-0.52, 1.74, -8.78),
        (0.52, 1.74, -8.78),
        (0.46, 1.74, -7.92),
        (-0.46, 1.74, -7.92),
        (-0.42, 1.98, -8.68),
        (0.42, 1.98, -8.68),
        (0.34, 2.02, -8.02),
        (-0.34, 2.02, -8.02),
    ]
    faces = [
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (3, 7, 4, 0),
    ]
    return create_box_from_godot_points(name, points, faces, mat, target, 0.055)


def create_wraparound_console(
    name: str,
    mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> bpy.types.Object:
    points = [
        (-1.08, 0.72, -9.28),
        (1.08, 0.72, -9.28),
        (0.78, 0.72, -10.44),
        (-0.78, 0.72, -10.44),
        (-0.92, 1.10, -9.16),
        (0.92, 1.10, -9.16),
        (0.56, 1.40, -10.36),
        (-0.56, 1.40, -10.36),
    ]
    faces = [
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (3, 7, 4, 0),
    ]
    return create_box_from_godot_points(name, points, faces, mat, target, 0.060)


def create_cockpit_tub(
    name: str,
    wall_mat: bpy.types.Material,
    floor_mat: bpy.types.Material,
    trim_mat: bpy.types.Material,
    dark_mat: bpy.types.Material,
    screen_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Create a fitted pilot tub inside the measured exterior canopy volume."""
    floor_sections = [
        (-10.45, [(-0.46, 0.62), (0.46, 0.62), (0.62, 0.82), (-0.62, 0.82)]),
        (-9.35, [(-0.52, 0.54), (0.52, 0.54), (0.78, 0.78), (-0.78, 0.78)]),
        (-8.05, [(-0.58, 0.52), (0.58, 0.52), (0.88, 0.78), (-0.88, 0.78)]),
        (-6.62, [(-0.50, 0.62), (0.50, 0.62), (0.76, 0.86), (-0.76, 0.86)]),
    ]
    floor = create_loft_mesh(f"{name}_recessed_floor_pan", floor_sections, floor_mat, target)
    bevel = floor.modifiers.new("cockpit tub floor bevel", "BEVEL")
    bevel.width = 0.035
    bevel.segments = 3

    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        side_sections = []
        for z, inner_x, outer_x, lower_y, upper_y in [
            (-10.70, 0.54, 0.86, 0.74, 1.58),
            (-9.30, 0.72, 0.98, 0.70, 1.68),
            (-8.00, 0.80, 1.04, 0.72, 1.82),
            (-6.55, 0.68, 0.90, 0.88, 1.98),
        ]:
            side_sections.append((z, [
                (side * inner_x, lower_y),
                (side * outer_x, lower_y + 0.10),
                (side * outer_x, upper_y),
                (side * inner_x, upper_y - 0.16),
            ]))
        sidewall = create_loft_mesh(f"{name}_continuous_sidewall_{label}", side_sections, wall_mat, target)
        bevel = sidewall.modifiers.new("cockpit tub side bevel", "BEVEL")
        bevel.width = 0.018
        bevel.segments = 2

        add_cylinder_between(f"{name}_sill_rail_{label}", (side * 0.72, 1.70, -10.70), (side * 0.98, 2.02, -6.48), 0.034, trim_mat, target, 14)
        add_cylinder_between(f"{name}_lower_equipment_rail_{label}", (side * 0.58, 0.86, -10.20), (side * 0.76, 0.92, -6.78), 0.024, trim_mat, target, 12)
        add_beveled_cube(f"{name}_inset_side_display_{label}", (side * 0.68, 1.12, -8.80), (0.030, 0.055, 0.70), screen_mat, target, 0.008)
        add_beveled_cube(f"{name}_dark_elbow_recess_{label}", (side * 0.63, 0.96, -8.10), (0.028, 0.050, 1.08), dark_mat, target, 0.006)
        for index, z in enumerate([-9.72, -9.12, -8.52, -7.92]):
            add_beveled_cube(f"{name}_flush_switch_{label}_{index}", (side * 0.54, 0.96, z), (0.032, 0.030, 0.075), trim_mat, target, 0.006)


def create_curved_instrument_panel(
    name: str,
    trim_mat: bpy.types.Material,
    dark_mat: bpy.types.Material,
    rubber_mat: bpy.types.Material,
    screen_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Build a low curved dashboard that stays below the pilot's canopy view."""
    panel_sections = [
        (-10.48, [(-0.74, 0.76), (0.74, 0.76), (0.56, 1.06), (-0.56, 1.06)]),
        (-10.00, [(-0.90, 0.72), (0.90, 0.72), (0.70, 1.20), (-0.70, 1.20)]),
        (-9.42, [(-1.02, 0.76), (1.02, 0.76), (0.82, 1.30), (-0.82, 1.30)]),
        (-8.92, [(-0.92, 0.82), (0.92, 0.82), (0.76, 1.18), (-0.76, 1.18)]),
    ]
    body = create_loft_mesh(f"{name}_sculpted_body", panel_sections, trim_mat, target)
    bevel = body.modifiers.new("instrument body bevel", "BEVEL")
    bevel.width = 0.045
    bevel.segments = 4

    create_tapered_prism(f"{name}_low_padded_lip", (0.0, 1.34, -9.90), (1.38, 0.105, 0.34), (0.98, 0.070, 0.20), rubber_mat, target, 0.050)
    create_tapered_prism(f"{name}_center_recessed_mfd_well", (0.0, 1.11, -10.10), (0.72, 0.060, 0.42), (0.54, 0.038, 0.28), dark_mat, target, 0.028)
    add_beveled_cube(f"{name}_center_mfd_glass", (0.0, 1.145, -10.12), (0.50, 0.018, 0.24), screen_mat, target, 0.012)
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        create_tapered_prism(f"{name}_angled_aux_well_{label}", (side * 0.58, 1.04, -9.72), (0.34, 0.052, 0.24), (0.24, 0.034, 0.16), dark_mat, target, 0.022)
        add_beveled_cube(f"{name}_aux_screen_{label}", (side * 0.58, 1.070, -9.73), (0.21, 0.016, 0.13), screen_mat, target, 0.008)
        add_cylinder_between(f"{name}_integrated_grip_{label}", (side * 0.84, 0.96, -9.22), (side * 0.68, 1.08, -10.24), 0.026, rubber_mat, target, 12)
    for index, x in enumerate([-0.42, -0.28, -0.14, 0.14, 0.28, 0.42]):
        add_beveled_cube(f"{name}_flush_toggle_{index}", (x, 0.96, -9.24), (0.070, 0.040, 0.105), dark_mat, target, 0.014)


def create_molded_cockpit_detail_layer(
    wall_mat: bpy.types.Material,
    trim_mat: bpy.types.Material,
    dark_mat: bpy.types.Material,
    rubber_mat: bpy.types.Material,
    screen_mat: bpy.types.Material,
    bolt_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Add a more deliberate hard-surface detail layer around the pilot tub."""
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"

        create_tapered_prism(
            f"Cockpit_molded_side_panel_forward_{label}",
            (side * 0.91, 1.05, -9.60),
            (0.16, 0.26, 1.22),
            (0.10, 0.18, 0.92),
            wall_mat,
            target,
            0.050,
        )
        create_tapered_prism(
            f"Cockpit_molded_side_panel_aft_{label}",
            (side * 0.96, 1.08, -7.55),
            (0.18, 0.28, 1.48),
            (0.11, 0.18, 1.10),
            wall_mat,
            target,
            0.050,
        )
        create_tapered_prism(
            f"Cockpit_dark_recessed_equipment_bay_{label}",
            (side * 0.77, 1.18, -8.72),
            (0.050, 0.070, 0.92),
            (0.034, 0.045, 0.66),
            dark_mat,
            target,
            0.014,
        )
        add_beveled_cube(
            f"Cockpit_screen_status_strip_{label}",
            (side * 0.735, 1.245, -8.76),
            (0.024, 0.018, 0.52),
            screen_mat,
            target,
            0.006,
        )
        add_beveled_cube(
            f"Cockpit_rubber_elbow_pad_{label}",
            (side * 0.68, 1.02, -8.10),
            (0.055, 0.080, 0.76),
            rubber_mat,
            target,
            0.028,
        )
        add_cylinder_between(
            f"Cockpit_molded_lower_conduit_{label}",
            (side * 0.62, 0.82, -10.16),
            (side * 0.82, 0.86, -6.78),
            0.018,
            rubber_mat,
            target,
            12,
        )
        add_cylinder_between(
            f"Cockpit_molded_upper_trim_spline_{label}",
            (side * 0.82, 1.44, -10.26),
            (side * 1.02, 1.56, -6.68),
            0.018,
            trim_mat,
            target,
            12,
        )

        for index, z in enumerate([-9.88, -9.28, -8.34, -7.52]):
            add_beveled_cube(
                f"Cockpit_bolt_cluster_{label}_{index}_upper",
                (side * 0.846, 1.325, z),
                (0.030, 0.020, 0.040),
                bolt_mat,
                target,
                0.006,
            )
            add_beveled_cube(
                f"Cockpit_bolt_cluster_{label}_{index}_lower",
                (side * 0.640, 0.890, z + 0.08),
                (0.026, 0.018, 0.036),
                bolt_mat,
                target,
                0.005,
            )

    create_tapered_prism(
        "Cockpit_molded_center_console_bridge",
        (0.0, 1.02, -9.08),
        (0.92, 0.120, 0.28),
        (0.66, 0.075, 0.18),
        trim_mat,
        target,
        0.040,
    )
    add_beveled_cube(
        "Cockpit_dark_switch_recess_left",
        (-0.22, 1.105, -9.04),
        (0.24, 0.024, 0.12),
        dark_mat,
        target,
        0.010,
    )
    add_beveled_cube(
        "Cockpit_dark_switch_recess_right",
        (0.22, 1.105, -9.04),
        (0.24, 0.024, 0.12),
        dark_mat,
        target,
        0.010,
    )
    for index, x in enumerate([-0.30, -0.22, -0.14, 0.14, 0.22, 0.30]):
        add_beveled_cube(
            f"Cockpit_molded_toggle_cap_{index}",
            (x, 1.128, -9.04),
            (0.036, 0.022, 0.055),
            bolt_mat,
            target,
            0.006,
        )


def create_reclined_seat_shell(
    name: str,
    mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> bpy.types.Object:
    sections = [
        (-8.78, [(-0.62, 1.60), (0.62, 1.60), (0.54, 1.90), (-0.54, 1.90)]),
        (-8.36, [(-0.66, 1.70), (0.66, 1.70), (0.58, 2.04), (-0.58, 2.04)]),
        (-7.96, [(-0.54, 2.08), (0.54, 2.08), (0.46, 2.62), (-0.46, 2.62)]),
        (-7.78, [(-0.40, 2.58), (0.40, 2.58), (0.34, 2.92), (-0.34, 2.92)]),
    ]
    obj = create_loft_mesh(name, sections, mat, target)
    bevel = obj.modifiers.new("seat shell bevel", "BEVEL")
    bevel.width = 0.045
    bevel.segments = 4
    return obj


def create_seat_cushion_stack(
    mat: bpy.types.Material,
    dark_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    create_tapered_prism("PilotSeat_thick_base_cushion", (0.0, 1.90, -8.42), (1.00, 0.20, 0.86), (0.82, 0.16, 0.68), mat, target, 0.080)
    back = create_tapered_prism("PilotSeat_segmented_back_cushion_lower", (0.0, 2.30, -7.98), (0.78, 0.48, 0.16), (0.62, 0.40, 0.13), mat, target, 0.065)
    back.rotation_euler[0] = math.radians(-10.0)
    upper = create_tapered_prism("PilotSeat_segmented_back_cushion_upper", (0.0, 2.67, -7.88), (0.62, 0.34, 0.14), (0.46, 0.28, 0.11), mat, target, 0.055)
    upper.rotation_euler[0] = math.radians(-10.0)
    add_beveled_cube("PilotSeat_cushion_center_seam", (0.0, 2.30, -7.845), (0.040, 0.88, 0.026), dark_mat, target, 0.006)
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        add_beveled_cube(f"PilotSeat_side_crash_bolster_{label}", (side * 0.48, 2.24, -7.94), (0.14, 0.70, 0.18), dark_mat, target, 0.045)


def add_bolt_pair(
    prefix: str,
    center_x: float,
    y: float,
    z: float,
    spacing: float,
    mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    for side in [-1.0, 1.0]:
        add_beveled_cube(f"{prefix}_bolt_{'L' if side < 0 else 'R'}", (center_x + side * spacing, y, z), (0.045, 0.018, 0.045), mat, target, 0.010)


def add_warning_stripes(
    prefix: str,
    z_values: list[float],
    mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    for index, z in enumerate(z_values):
        left = add_beveled_cube(f"{prefix}_stripe_left_{index}", (-0.52, 0.315, z), (0.10, 0.022, 0.42), mat, target, 0.006)
        right = add_beveled_cube(f"{prefix}_stripe_right_{index}", (0.52, 0.315, z), (0.10, 0.022, 0.42), mat, target, 0.006)
        left.rotation_euler[1] = math.radians(18.0)
        right.rotation_euler[1] = math.radians(-18.0)


def create_ceiling_service_panel(
    name: str,
    z: float,
    half_width: float,
    mat: bpy.types.Material,
    trim: bpy.types.Material,
    accent: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    panel = add_beveled_cube(name, (0.0, 2.36, z), (half_width * 1.35, 0.065, 1.05), mat, target, 0.030)
    panel.rotation_euler[0] = math.radians(0.0)
    add_beveled_cube(f"{name}_left_track", (-half_width * 0.56, 2.315, z), (0.045, 0.045, 0.96), trim, target, 0.012)
    add_beveled_cube(f"{name}_right_track", (half_width * 0.56, 2.315, z), (0.045, 0.045, 0.96), trim, target, 0.012)
    add_beveled_cube(f"{name}_service_label", (0.0, 2.300, z - 0.22), (0.38, 0.026, 0.055), accent, target, 0.006)


def add_longitudinal_rib_skin(
    prefix: str,
    side: float,
    mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    label = "L" if side < 0 else "R"
    add_cylinder_between(f"{prefix}_upper_spine_{label}", (side * 1.10, 2.12, -5.40), (side * 1.92, 1.78, 3.45), 0.030, mat, target, 12)
    add_cylinder_between(f"{prefix}_mid_spine_{label}", (side * 1.28, 1.56, -5.20), (side * 2.06, 1.30, 3.25), 0.024, mat, target, 12)
    add_cylinder_between(f"{prefix}_lower_spine_{label}", (side * 1.18, 0.72, -5.10), (side * 1.80, 0.60, 3.15), 0.022, mat, target, 12)


def create_bulkhead_collar(
    name: str,
    z: float,
    outer_half_width: float,
    inner_half_width: float,
    floor_y: float,
    crown_y: float,
    side_y: float,
    mat: bpy.types.Material,
    accent: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    add_arch_tube(f"{name}_outer_pressure_frame", z, outer_half_width, floor_y, crown_y, side_y, 0.055, mat, target)
    add_arch_tube(f"{name}_inner_pressure_frame", z + 0.10, inner_half_width, floor_y + 0.16, crown_y - 0.24, side_y + 0.08, 0.028, mat, target)
    add_beveled_cube(f"{name}_left_kick_plate", (-outer_half_width * 0.72, floor_y + 0.18, z), (0.40, 0.18, 0.16), mat, target, 0.025)
    add_beveled_cube(f"{name}_right_kick_plate", (outer_half_width * 0.72, floor_y + 0.18, z), (0.40, 0.18, 0.16), mat, target, 0.025)
    add_beveled_cube(f"{name}_top_status_light", (0.0, crown_y - 0.16, z - 0.02), (0.42, 0.040, 0.050), accent, target, 0.008)


def create_cockpit_transition_fairing(
    name: str,
    mat: bpy.types.Material,
    trim: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Blend the pressure cabin into the forward canopy volume."""
    sections = [
        (-6.30, arch_profile(1.12, 0.42, 2.44, 1.00)),
        (-6.82, arch_profile(0.96, 0.58, 2.58, 1.08)),
        (-7.35, arch_profile(0.78, 0.84, 2.68, 1.22)),
    ]
    obj = create_loft_mesh(name, sections, mat, target)
    bevel = obj.modifiers.new("fairing soft bevel", "BEVEL")
    bevel.width = 0.018
    bevel.segments = 2
    add_arch_tube(f"{name}_aft_trim", -6.24, 1.12, 0.42, 2.44, 1.00, 0.022, trim, target)
    add_arch_tube(f"{name}_forward_trim", -7.42, 0.78, 0.84, 2.68, 1.22, 0.022, trim, target)


def add_cylinder_between(
    name: str,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    radius: float,
    mat: bpy.types.Material,
    target: bpy.types.Collection,
    vertices: int = 12,
) -> bpy.types.Object:
    """Create a cylinder between two project/Godot-space points."""
    start_v = Vector(to_blender_loc(start))
    end_v = Vector(to_blender_loc(end))
    midpoint = (start_v + end_v) * 0.5
    direction = end_v - start_v
    length = direction.length
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=length, location=midpoint)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(mat)
    obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    link_to_collection(obj, target)
    return obj


def add_tube_polyline(
    name: str,
    points: list[tuple[float, float, float]],
    radius: float,
    mat: bpy.types.Material,
    target: bpy.types.Collection,
    vertices: int = 12,
) -> None:
    for index, (start, end) in enumerate(zip(points, points[1:])):
        add_cylinder_between(f"{name}_{index:02d}", start, end, radius, mat, target, vertices)


def add_arch_tube(
    name: str,
    z: float,
    half_width: float,
    floor_y: float,
    crown_y: float,
    side_y: float,
    radius: float,
    mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    profile = arch_profile(half_width, floor_y, crown_y, side_y)
    points = [(x, y, z) for x, y in profile]
    add_tube_polyline(name, points, radius, mat, target, 14)


def arch_profile(half_width: float, floor_y: float, crown_y: float, side_y: float) -> list[tuple[float, float]]:
    return [
        (-half_width, floor_y),
        (-half_width * 1.02, side_y),
        (-half_width * 0.86, side_y + (crown_y - side_y) * 0.42),
        (-half_width * 0.45, crown_y - 0.12),
        (0.0, crown_y),
        (half_width * 0.45, crown_y - 0.12),
        (half_width * 0.86, side_y + (crown_y - side_y) * 0.42),
        (half_width * 1.02, side_y),
        (half_width, floor_y),
    ]


def import_reference(target: bpy.types.Collection) -> None:
    if not SHUTTLE_OBJ.exists():
        raise FileNotFoundError(SHUTTLE_OBJ)

    before = set(bpy.data.objects)
    if hasattr(bpy.ops.wm, "obj_import"):
        bpy.ops.wm.obj_import(filepath=str(SHUTTLE_OBJ))
    else:
        bpy.ops.import_scene.obj(filepath=str(SHUTTLE_OBJ))

    imported = [obj for obj in bpy.data.objects if obj not in before]
    for obj in imported:
        obj.name = f"REF_{obj.name}"
        obj.rotation_euler[0] = math.radians(90.0)
        obj.hide_render = True
        obj.hide_select = True
        obj.display_type = "WIRE"
        link_to_collection(obj, target)


def create_markers(target: bpy.types.Collection) -> None:
    marker_data = {
        "InteriorSpawn": (0.0, 1.35, 3.95),
        "SeatAnchor": (0.0, 2.04, -8.55),
        "SeatExit": (0.0, 1.22, -5.65),
        "PilotEye": (0.0, 2.18, -8.92),
        "CanopyTarget": (0.0, 2.75, -8.72),
        "HatchCenter": (0.0, 1.30, 4.35),
    }
    for name, loc in marker_data.items():
        empty = bpy.data.objects.new(name, None)
        empty.empty_display_type = "PLAIN_AXES"
        empty.empty_display_size = 0.25
        empty.location = to_blender_loc(loc)
        empty["godot_position"] = list(loc)
        target.objects.link(empty)

    MARKERS_JSON.parent.mkdir(parents=True, exist_ok=True)
    MARKERS_JSON.write_text(
        json.dumps({name: list(loc) for name, loc in marker_data.items()}, indent=2) + "\n",
        encoding="utf-8",
    )


def create_initial_interior() -> None:
    reference = collection("Reference_Exterior")
    interior = collection("Interior_Render")
    glass = collection("Interior_Glass")
    collision = collection("Collision_Proxy")
    markers = collection("Markers")
    collection("Review_Cameras")

    cockpit_bounds = read_material_bounds("Cockpit")
    write_reference_fit_report(cockpit_bounds)
    import_reference(reference)

    wall_mat = material("SG_wall_matte_warm_gray", (0.18, 0.205, 0.205, 1.0), 0.86, 0.02)
    panel_mat = material("SG_panel_soft_gray", (0.30, 0.34, 0.33, 1.0), 0.80, 0.04)
    floor_mat = material("SG_floor_dark_composite", (0.075, 0.085, 0.09, 1.0), 0.90, 0.0)
    trim_mat = material("SG_trim_dark_metal", (0.16, 0.18, 0.18, 1.0), 0.68, 0.14)
    rubber_mat = material("SG_black_rubber_gasket", (0.025, 0.028, 0.030, 1.0), 0.88, 0.0)
    bolt_mat = material("SG_bolt_worn_edges", (0.36, 0.38, 0.36, 1.0), 0.52, 0.42)
    warning_mat = material("SG_muted_safety_yellow", (0.92, 0.72, 0.18, 1.0), 0.70, 0.0)
    dark_panel_mat = material("SG_dark_recess_panel", (0.105, 0.125, 0.125, 1.0), 0.82, 0.08)
    glass_mat = material("SG_canopy_glass", (0.08, 0.55, 0.62, 0.05), 0.05, 0.0)
    seat_mat = material("SG_seat_orange_cushion", (0.62, 0.36, 0.16, 1.0), 0.82, 0.0)
    screen_mat = emissive_material("SG_screen_cyan", (0.02, 0.75, 0.85, 1.0), 1.35)

    # Keep the opaque pressure shell out of the forward canopy. Earlier
    # versions carried this shell to the nose and turned the cockpit view into
    # a wall-lined tunnel instead of a fighter-style transparent dome.
    shell_sections = [
        (-5.80, arch_profile(1.30, 0.18, 3.00, 0.96)),
        (-3.85, arch_profile(1.78, 0.05, 2.55, 0.84)),
        (-1.60, arch_profile(2.35, -0.02, 2.62, 0.78)),
        (0.80, arch_profile(2.48, -0.02, 2.58, 0.78)),
        (3.35, arch_profile(1.88, 0.12, 2.30, 0.90)),
    ]
    create_loft_mesh("InteriorShell_single_piece", shell_sections, wall_mat, interior)

    cockpit_min = cockpit_bounds["min"]
    cockpit_max = cockpit_bounds["max"]
    cockpit_size = cockpit_bounds["size"]
    canopy_front_z = cockpit_min[2]
    canopy_aft_z = cockpit_max[2]
    canopy_floor_y = cockpit_min[1]
    canopy_crown_y = cockpit_max[1]
    canopy_half_width = cockpit_size[0] * 0.5
    canopy_sections = [
        (canopy_front_z + 0.14, arch_profile(canopy_half_width * 0.36, canopy_floor_y - 0.04, canopy_floor_y + 0.30, canopy_floor_y + 0.06)),
        (canopy_front_z + 0.92, arch_profile(canopy_half_width * 0.66, canopy_floor_y - 0.10, canopy_floor_y + 0.82, canopy_floor_y + 0.02)),
        (canopy_front_z + 1.86, arch_profile(canopy_half_width * 0.92, canopy_floor_y - 0.14, canopy_floor_y + 1.32, canopy_floor_y + 0.02)),
        (canopy_front_z + 3.06, arch_profile(canopy_half_width * 1.00, canopy_floor_y - 0.06, canopy_crown_y - 0.08, canopy_floor_y + 0.10)),
        (canopy_aft_z - 0.92, arch_profile(canopy_half_width * 0.88, canopy_floor_y + 0.10, canopy_crown_y - 0.06, canopy_floor_y + 0.24)),
        (canopy_aft_z - 0.04, arch_profile(canopy_half_width * 0.54, canopy_floor_y + 0.36, canopy_crown_y - 0.30, canopy_floor_y + 0.48)),
    ]
    # Keep the measured canopy sections as the fit source for frames and
    # review reporting, but do not export a full transparent skin yet. In Godot
    # 4.6 the imported full-dome glass currently creates bright alpha-sorting
    # streaks in close cockpit captures, which is worse than an open canopy
    # represented by semantic glass highlights and structural rails.

    # The generic cabin floor stops at the cockpit threshold. The forward
    # cockpit is owned by the measured pilot tub below; overlapping both floor
    # systems caused visible z-fighting streaks in close cockpit review.
    add_beveled_cube("Floor_continuous_spine", (0.0, 0.18, -0.82), (1.18, 0.18, 8.85), floor_mat, interior, 0.06)
    for z, width in [(-4.7, 1.55), (-2.4, 2.12), (-0.2, 2.42), (2.0, 2.10)]:
        add_beveled_cube(f"Floor_side_plate_{z:.1f}_L", (-width * 0.45, 0.21, z), (width * 0.82, 0.075, 1.05), floor_mat, interior, 0.035)
        add_beveled_cube(f"Floor_side_plate_{z:.1f}_R", (width * 0.45, 0.21, z), (width * 0.82, 0.075, 1.05), floor_mat, interior, 0.035)
        add_beveled_cube(f"Floor_dark_tread_{z:.1f}", (0.0, 0.265, z), (0.74, 0.04, 0.56), trim_mat, interior, 0.025)
        add_beveled_cube(f"Floor_edge_left_{z:.1f}", (-width * 0.78, 0.33, z), (0.055, 0.14, 1.03), trim_mat, interior, 0.025)
        add_beveled_cube(f"Floor_edge_right_{z:.1f}", (width * 0.78, 0.33, z), (0.055, 0.14, 1.03), trim_mat, interior, 0.025)
        add_beveled_cube(f"Floor_recess_left_{z:.1f}", (-0.34, 0.292, z), (0.20, 0.025, 0.36), rubber_mat, interior, 0.012)
        add_beveled_cube(f"Floor_recess_right_{z:.1f}", (0.34, 0.292, z), (0.20, 0.025, 0.36), rubber_mat, interior, 0.012)
        add_bolt_pair(f"Floor_panel_{z:.1f}_front", 0.0, 0.323, z - 0.38, 0.45, bolt_mat, interior)
        add_bolt_pair(f"Floor_panel_{z:.1f}_rear", 0.0, 0.323, z + 0.38, 0.45, bolt_mat, interior)
    add_warning_stripes("Floor_threshold", [-5.45, 3.05], warning_mat, interior)
    for z, half_width in [(-3.10, 1.72), (-1.10, 2.02), (1.05, 1.92), (2.75, 1.55)]:
        add_arch_tube(f"Primary_pressure_hoop_{z:.1f}", z, half_width, 0.30, 2.38 if z > -2.0 else 2.52, 0.90, 0.034, trim_mat, interior)
        add_arch_tube(f"Inner_soft_panel_hoop_{z:.1f}", z + 0.12, half_width - 0.22, 0.42, 2.18 if z > -2.0 else 2.30, 0.98, 0.018, panel_mat, interior)
    for index, (z, width) in enumerate([(-4.45, 1.30), (-2.65, 1.70), (-0.85, 1.92), (1.05, 1.82), (2.55, 1.42)]):
        create_ceiling_service_panel(f"Ceiling_service_panel_{index}", z, width, dark_panel_mat, trim_mat, screen_mat, interior)
    create_bulkhead_collar("Rear_hatch_bulkhead_collar", 3.22, 1.72, 1.35, 0.26, 2.42, 1.02, trim_mat, screen_mat, interior)
    create_bulkhead_collar("Forward_cockpit_bulkhead_collar", -5.70, 1.22, 0.86, 0.42, 2.88, 1.08, trim_mat, screen_mat, interior)
    add_beveled_cube("Rear_threshold_black_sill", (0.0, 0.34, 3.08), (1.46, 0.055, 0.24), dark_panel_mat, interior, 0.018)
    add_beveled_cube("Cockpit_threshold_black_sill", (0.0, 0.34, -5.62), (1.20, 0.055, 0.24), dark_panel_mat, interior, 0.018)
    add_beveled_cube("Rear_threshold_floor_light", (0.0, 0.385, 2.91), (0.78, 0.020, 0.050), screen_mat, interior, 0.006)
    add_beveled_cube("Cockpit_threshold_floor_light", (0.0, 0.385, -5.45), (0.64, 0.020, 0.050), screen_mat, interior, 0.006)

    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        for segment in [
            (-5.28, -3.68, 1.18, 1.34, 0.54, 0.48, 1.90, 2.02),
            (-3.68, -1.48, 1.34, 1.66, 0.48, 0.42, 2.02, 2.06),
            (-1.48, 0.72, 1.66, 1.86, 0.42, 0.40, 2.06, 2.04),
            (0.72, 2.72, 1.86, 1.62, 0.40, 0.48, 2.04, 1.86),
            (2.72, 3.48, 1.62, 1.28, 0.48, 0.64, 1.86, 1.62),
        ]:
            create_side_liner_segment(
                "Cabin_continuous_side_skin",
                side,
                segment[0],
                segment[1],
                segment[2],
                segment[3],
                segment[4],
                segment[5],
                segment[6],
                segment[7],
                wall_mat,
                dark_panel_mat,
                trim_mat,
                interior,
            )
        add_longitudinal_rib_skin("Cabin_integrated_skin", side, trim_mat, interior)
        create_raised_panel_grid("Side_service", side, [-4.35, -2.65], 1.36, panel_mat, trim_mat, interior)
        create_raised_panel_grid("Side_cabin", side, [-0.85, 1.05, 2.65], 1.72, panel_mat, trim_mat, interior)
        for index, z in enumerate([-4.35, -2.65, -0.85, 1.05, 2.65]):
            wall_x = 1.36 if z < -2.0 else 1.72
            add_beveled_cube(f"Side_small_label_light_{label}_{index}", (side * (wall_x * 0.91), 1.08, z + 0.30), (0.020, 0.035, 0.18), screen_mat, interior, 0.006)
            add_beveled_cube(f"Side_dark_access_slot_{label}_{index}", (side * (wall_x * 0.90), 0.98, z - 0.28), (0.018, 0.030, 0.24), dark_panel_mat, interior, 0.004)
            add_beveled_cube(f"Side_tiny_latch_{label}_{index}", (side * (wall_x * 0.88), 0.62, z + 0.23), (0.024, 0.045, 0.08), bolt_mat, interior, 0.006)
        add_cylinder_between(f"Side_upper_light_rail_{label}", (side * 1.42, 1.78, -4.80), (side * 1.72, 1.60, 3.10), 0.010, screen_mat, interior, 8)
        add_cylinder_between(f"Side_floor_pressure_rail_{label}", (side * 1.10, 0.42, -5.00), (side * 1.62, 0.38, 3.25), 0.020, trim_mat, interior, 10)
        add_cylinder_between(f"Side_mid_structural_rail_{label}", (side * 1.24, 1.22, -4.80), (side * 1.62, 1.12, 3.15), 0.018, trim_mat, interior, 10)

    create_cockpit_tub("Cockpit_measured_pilot_tub", wall_mat, floor_mat, trim_mat, dark_panel_mat, screen_mat, interior)
    create_curved_instrument_panel("Cockpit_measured_instrument_panel", trim_mat, dark_panel_mat, rubber_mat, screen_mat, interior)
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        coaming = create_tapered_prism(
            f"Cockpit_clean_low_side_coaming_{label}",
            (side * 0.98, 1.18, -8.42),
            (0.18, 0.20, 2.45),
            (0.11, 0.13, 2.05),
            trim_mat,
            interior,
            0.035,
        )
        coaming.rotation_euler[2] = math.radians(-5.0 * side)
        add_cylinder_between(
            f"Cockpit_clean_upper_grab_rail_{label}",
            (side * 0.88, 1.42, -9.80),
            (side * 1.02, 1.62, -7.05),
            0.022,
            rubber_mat,
            interior,
            12,
        )
    create_molded_cockpit_detail_layer(wall_mat, trim_mat, dark_panel_mat, rubber_mat, screen_mat, bolt_mat, interior)
    add_beveled_cube("Canopy_low_inner_sill", (0.0, 1.44, -9.30), (1.42, 0.060, 0.15), trim_mat, interior, 0.024)
    add_beveled_cube("Canopy_black_inner_gasket", (0.0, 1.54, -9.70), (1.28, 0.034, 0.10), rubber_mat, interior, 0.016)
    # Transparent canopy panes are intentionally not exported in this pass.
    # The Godot 4.6 import/render path currently turns thin alpha panes into
    # bright streak artifacts in the cockpit review. Use stable rails, gaskets,
    # and small opaque fit indicators until the glass material path can be
    # solved without corrupting the pilot view.
    for index, z in enumerate([-9.25, -7.40]):
        width = [0.78, 0.72][index]
        y = [2.04, 2.36][index]
        add_cylinder_between(f"Canopy_fit_indicator_left_{index}", (-width, y, z), (-width * 0.82, y + 0.025, z + 0.16), 0.004, screen_mat, interior, 6)
        add_cylinder_between(f"Canopy_fit_indicator_right_{index}", (width, y, z), (width * 0.82, y + 0.025, z + 0.16), 0.004, screen_mat, interior, 6)
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        add_cylinder_between(f"Cockpit_canopy_side_longeron_{label}", (side * 0.74, 1.70, -10.65), (side * 1.12, 2.26, -6.35), 0.024, trim_mat, interior, 12)
        add_cylinder_between(f"Cockpit_lower_sill_rail_{label}", (side * 0.82, 1.24, -10.40), (side * 1.02, 1.52, -6.45), 0.030, trim_mat, interior, 12)
        add_cylinder_between(f"Cockpit_canopy_rubber_gasket_{label}", (side * 0.66, 1.82, -10.70), (side * 1.02, 2.34, -6.48), 0.014, rubber_mat, interior, 10)
        add_beveled_cube(f"Cockpit_warning_chip_{label}", (side * 0.72, 1.15, -7.65), (0.20, 0.052, 0.16), seat_mat, interior, 0.016)
    add_cylinder_between("Canopy_center_spine", (0.0, 3.42, -6.15), (0.0, 2.18, -11.20), 0.012, trim_mat, interior, 10)
    add_cylinder_between("Canopy_center_rubber_gasket", (0.0, 3.35, -6.20), (0.0, 2.14, -11.12), 0.008, rubber_mat, interior, 8)
    for index, z in enumerate([-10.55, -9.25, -7.85, -6.35]):
        half_width = [0.42, 0.84, 1.02, 0.64][index]
        crown_y = [2.40, 3.12, 3.42, 3.20][index]
        side_y = [1.92, 1.88, 2.02, 2.35][index]
        add_cylinder_between(f"Canopy_arch_{index}_left", (-half_width, side_y, z), (-half_width * 0.25, crown_y, z + 0.08), 0.010, trim_mat, interior, 10)
        add_cylinder_between(f"Canopy_arch_{index}_right", (half_width, side_y, z), (half_width * 0.25, crown_y, z + 0.08), 0.010, trim_mat, interior, 10)
        add_cylinder_between(f"Canopy_arch_{index}_crown", (-half_width * 0.25, crown_y, z + 0.08), (half_width * 0.25, crown_y, z + 0.08), 0.010, trim_mat, interior, 10)

    add_beveled_cube("PilotSeat_double_rail_left", (-0.28, 1.35, -8.30), (0.10, 0.18, 1.18), trim_mat, interior, 0.025)
    add_beveled_cube("PilotSeat_double_rail_right", (0.28, 1.35, -8.30), (0.10, 0.18, 1.18), trim_mat, interior, 0.025)
    add_beveled_cube("PilotSeat_central_actuator_column", (0.0, 1.54, -8.34), (0.34, 0.38, 0.42), trim_mat, interior, 0.060)
    create_reclined_seat_shell("PilotSeat_reclined_hard_shell", trim_mat, interior)
    create_seat_cushion_stack(seat_mat, dark_panel_mat, interior)
    create_tapered_prism("PilotSeat_integrated_headrest", (0.0, 2.88, -7.84), (0.58, 0.20, 0.16), (0.42, 0.16, 0.12), seat_mat, interior, 0.060)
    add_beveled_cube("PilotSeat_left_harness", (-0.23, 2.34, -7.82), (0.055, 0.72, 0.035), rubber_mat, interior, 0.012)
    add_beveled_cube("PilotSeat_right_harness", (0.23, 2.34, -7.82), (0.055, 0.72, 0.035), rubber_mat, interior, 0.012)
    add_beveled_cube("PilotSeat_center_harness_gap", (0.0, 2.29, -7.805), (0.09, 0.58, 0.025), dark_panel_mat, interior, 0.006)
    add_beveled_cube("PilotSeat_lap_buckle", (0.0, 2.03, -8.54), (0.22, 0.055, 0.10), trim_mat, interior, 0.014)
    add_cylinder_between("PilotSeat_left_armature", (-0.64, 1.78, -8.68), (-0.64, 1.92, -8.02), 0.055, trim_mat, interior, 10)
    add_cylinder_between("PilotSeat_right_armature", (0.64, 1.78, -8.68), (0.64, 1.92, -8.02), 0.055, trim_mat, interior, 10)
    add_beveled_cube("PilotSeat_left_arm_pad", (-0.64, 1.96, -8.36), (0.16, 0.08, 0.66), trim_mat, interior, 0.045)
    add_beveled_cube("PilotSeat_right_arm_pad", (0.64, 1.96, -8.36), (0.16, 0.08, 0.66), trim_mat, interior, 0.045)

    add_beveled_cube("Collision_walkable_floor", (0.0, 0.22, -3.20), (3.20, 0.26, 13.60), trim_mat, collision, 0.0)
    add_beveled_cube("Collision_chair_clearance", (0.0, 1.82, -8.35), (1.26, 1.36, 1.12), trim_mat, collision, 0.0)

    create_markers(markers)


def main() -> None:
    SOURCE_BLEND.parent.mkdir(parents=True, exist_ok=True)
    clear_scene()
    create_initial_interior()
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE_BLEND))
    print(f"Wrote {SOURCE_BLEND}")


if __name__ == "__main__":
    main()
