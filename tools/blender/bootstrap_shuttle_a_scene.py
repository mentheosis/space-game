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


def create_cockpit_lighting_sprint_pass(
    trim_mat: bpy.types.Material,
    dark_mat: bpy.types.Material,
    rubber_mat: bpy.types.Material,
    screen_mat: bpy.types.Material,
    warning_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Add cockpit fixtures that make display glow and warm task light feel sourced."""
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        add_beveled_cube(
            f"CockpitLighting01_console_dark_lamp_well_{label}",
            (side * 0.50, 1.172, -9.36),
            (0.26, 0.040, 0.16),
            dark_mat,
            target,
            0.012,
        )
        add_beveled_cube(
            f"CockpitLighting01_console_warm_lens_{label}",
            (side * 0.50, 1.198, -9.36),
            (0.150, 0.018, 0.052),
            warning_mat,
            target,
            0.006,
        )
        add_beveled_cube(
            f"CockpitLighting01_side_task_warm_lens_{label}",
            (side * 0.74, 1.335, -8.64),
            (0.026, 0.070, 0.19),
            warning_mat,
            target,
            0.006,
        )
        add_beveled_cube(
            f"CockpitLighting01_side_task_dark_brow_{label}",
            (side * 0.762, 1.382, -8.64),
            (0.036, 0.034, 0.25),
            dark_mat,
            target,
            0.006,
        )
        add_cylinder_between(
            f"CockpitLighting01_screen_shadow_gasket_{label}",
            (side * 0.42, 1.075, -9.96),
            (side * 0.60, 1.095, -9.54),
            0.012,
            rubber_mat,
            target,
            8,
        )

    add_beveled_cube(
        "CockpitLighting01_footwell_dark_recess",
        (0.0, 0.835, -8.60),
        (0.64, 0.030, 0.18),
        dark_mat,
        target,
        0.010,
    )
    add_beveled_cube(
        "CockpitLighting01_footwell_warm_lens",
        (0.0, 0.858, -8.60),
        (0.42, 0.016, 0.048),
        warning_mat,
        target,
        0.006,
    )
    add_beveled_cube(
        "CockpitLighting01_cool_mfd_inner_glow",
        (0.0, 1.166, -10.02),
        (0.34, 0.012, 0.055),
        screen_mat,
        target,
        0.004,
    )
    add_beveled_cube(
        "CockpitLighting01_upper_console_brushed_trim_catch",
        (0.0, 1.235, -9.62),
        (1.08, 0.024, 0.035),
        trim_mat,
        target,
        0.006,
    )

    # Keep the canopy edge free of tiny floating lamps. Earlier rim fixtures
    # were too small to read as mounted hardware in the cockpit walkthrough.
    # No glowing fixture on the seat back; it read as an odd artifact and
    # competed with the canopy silhouette.


def create_cockpit_access_architecture(
    floor_mat: bpy.types.Material,
    wall_mat: bpy.types.Material,
    trim_mat: bpy.types.Material,
    rubber_mat: bpy.types.Material,
    screen_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Create the raised cockpit deck and enclosed approach path."""
    deck_sections = [
        (-5.58, [(-0.48, 0.30), (0.48, 0.30), (0.48, 0.45), (-0.48, 0.45)]),
        (-6.18, [(-0.56, 0.46), (0.56, 0.46), (0.56, 0.62), (-0.56, 0.62)]),
        (-6.78, [(-0.62, 0.62), (0.62, 0.62), (0.62, 0.80), (-0.62, 0.80)]),
        (-7.36, [(-0.72, 0.78), (0.72, 0.78), (0.72, 0.99), (-0.72, 0.99)]),
        (-8.18, [(-0.82, 0.96), (0.82, 0.96), (0.82, 1.18), (-0.82, 1.18)]),
        (-9.12, [(-0.78, 0.98), (0.78, 0.98), (0.78, 1.20), (-0.78, 1.20)]),
    ]
    deck = create_loft_mesh("Cockpit_access_raised_ramp_and_platform", deck_sections, floor_mat, target)
    bevel = deck.modifiers.new("access deck molded bevel", "BEVEL")
    bevel.width = 0.045
    bevel.segments = 4

    for index, (z, y, width) in enumerate([
        (-5.96, 0.56, 1.00),
        (-6.46, 0.70, 1.08),
        (-6.96, 0.86, 1.16),
        (-7.48, 1.04, 1.32),
    ]):
        add_beveled_cube(
            f"Cockpit_access_broad_anti_slip_tread_{index}",
            (0.0, y + 0.035, z),
            (width, 0.038, 0.18),
            rubber_mat,
            target,
            0.014,
        )

    add_beveled_cube("Cockpit_access_pilot_platform_insert", (0.0, 1.235, -8.32), (1.46, 0.085, 1.38), trim_mat, target, 0.040)
    add_beveled_cube("Cockpit_access_seat_plinth_integrated", (0.0, 1.36, -8.34), (0.82, 0.24, 0.78), trim_mat, target, 0.070)
    add_beveled_cube("Cockpit_access_front_heel_well", (0.0, 1.255, -8.98), (0.74, 0.045, 0.30), rubber_mat, target, 0.024)

    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        closeout_sections = []
        for z, inner_x, outer_x, lower_y, upper_y in [
            (-5.74, 0.50, 0.86, 0.42, 1.02),
            (-6.48, 0.62, 0.96, 0.62, 1.18),
            (-7.24, 0.76, 1.02, 0.86, 1.32),
            (-8.20, 0.86, 1.04, 1.02, 1.42),
            (-9.12, 0.80, 0.94, 1.02, 1.34),
        ]:
            closeout_sections.append((z, [
                (side * inner_x, lower_y),
                (side * outer_x, lower_y + 0.08),
                (side * outer_x, upper_y),
                (side * inner_x, upper_y - 0.10),
            ]))
        wall = create_loft_mesh(f"Cockpit_access_enclosed_side_closeout_{label}", closeout_sections, wall_mat, target)
        bevel = wall.modifiers.new("access side closeout bevel", "BEVEL")
        bevel.width = 0.025
        bevel.segments = 3
        add_cylinder_between(
            f"Cockpit_access_low_handrail_{label}",
            (side * 0.68, 0.98, -5.92),
            (side * 0.88, 1.18, -8.96),
            0.020,
            trim_mat,
            target,
            12,
        )
        add_cylinder_between(
            f"Cockpit_access_floor_seal_{label}",
            (side * 0.52, 0.50, -5.70),
            (side * 0.86, 1.10, -9.05),
            0.018,
            rubber_mat,
            target,
            10,
        )
        add_beveled_cube(
            f"Cockpit_access_integrated_step_light_{label}",
            (side * 0.44, 0.76, -6.70),
            (0.020, 0.030, 0.66),
            screen_mat,
            target,
            0.005,
        )
        console_sections = []
        for z, inner_x, outer_x, y in [
            (-6.00, 0.58, 0.92, 0.96),
            (-6.82, 0.72, 1.04, 1.12),
            (-7.72, 0.86, 1.10, 1.26),
            (-8.76, 0.84, 1.00, 1.26),
        ]:
            console_sections.append((z, [
                (side * inner_x, y - 0.05),
                (side * outer_x, y + 0.02),
                (side * (outer_x - 0.06), y + 0.14),
                (side * (inner_x - 0.04), y + 0.08),
            ]))
        console = create_loft_mesh(f"Cockpit_access_molded_side_console_{label}", console_sections, trim_mat, target)
        bevel = console.modifiers.new("access console soft bevel", "BEVEL")
        bevel.width = 0.030
        bevel.segments = 3
        add_beveled_cube(
            f"Cockpit_access_console_dark_inset_{label}",
            (side * 0.78, 1.23, -7.55),
            (0.030, 0.030, 0.78),
            rubber_mat,
            target,
            0.008,
        )


def create_forward_enclosure_infill(
    wall_mat: bpy.types.Material,
    floor_mat: bpy.types.Material,
    trim_mat: bpy.types.Material,
    rubber_mat: bpy.types.Material,
    screen_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Close the cockpit approach so it reads as a pressure shell, not loose panels."""
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        side_sections = []
        for z, inner_x, outer_x, lower_y, upper_y in [
            (-5.70, 0.86, 1.24, 0.54, 1.42),
            (-6.42, 0.94, 1.22, 0.72, 1.54),
            (-7.18, 1.02, 1.16, 0.96, 1.66),
            (-8.06, 1.00, 1.06, 1.12, 1.68),
            (-9.08, 0.84, 0.94, 1.08, 1.58),
        ]:
            side_sections.append((z, [
                (side * inner_x, lower_y),
                (side * outer_x, lower_y + 0.08),
                (side * outer_x, upper_y),
                (side * inner_x, upper_y - 0.14),
            ]))
        side_wall = create_loft_mesh(f"Cockpit_forward_enclosure_side_wall_{label}", side_sections, wall_mat, target)
        bevel = side_wall.modifiers.new("forward enclosure side bevel", "BEVEL")
        bevel.width = 0.022
        bevel.segments = 3

        deck_closeout = []
        for z, inner_x, outer_x, y in [
            (-5.78, 0.50, 0.92, 0.45),
            (-6.50, 0.62, 1.02, 0.66),
            (-7.26, 0.78, 1.08, 0.94),
            (-8.08, 0.84, 1.02, 1.15),
            (-8.96, 0.78, 0.92, 1.16),
        ]:
            deck_closeout.append((z, [
                (side * inner_x, y),
                (side * outer_x, y + 0.06),
                (side * outer_x, y + 0.18),
                (side * inner_x, y + 0.10),
            ]))
        closeout = create_loft_mesh(f"Cockpit_forward_enclosure_deck_closeout_{label}", deck_closeout, floor_mat, target)
        bevel = closeout.modifiers.new("forward deck closeout bevel", "BEVEL")
        bevel.width = 0.020
        bevel.segments = 2

        add_cylinder_between(
            f"Cockpit_forward_enclosure_lower_seal_{label}",
            (side * 0.72, 0.62, -5.80),
            (side * 0.82, 1.20, -9.02),
            0.024,
            trim_mat,
            target,
            12,
        )
    # Keep the forward cockpit ceiling dominated by glass. Earlier broad
    # opaque shoulders and overhead bridge enclosed the space, but made the
    # fighter-style canopy read like a square tunnel.

    add_beveled_cube("Cockpit_forward_enclosure_threshold_floor_fill", (0.0, 0.39, -5.88), (1.32, 0.055, 0.42), floor_mat, target, 0.025)
    add_beveled_cube("Cockpit_forward_enclosure_platform_floor_fill", (0.0, 1.265, -8.92), (1.34, 0.055, 0.58), floor_mat, target, 0.025)


def create_aft_enclosure_closeout(
    wall_mat: bpy.types.Material,
    floor_mat: bpy.types.Material,
    trim_mat: bpy.types.Material,
    rubber_mat: bpy.types.Material,
    screen_mat: bpy.types.Material,
    dark_panel_mat: bpy.types.Material,
    bolt_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Close the aft cabin with a pressure bulkhead and hatch structure."""
    # The rear of the current isolated review hides the legacy hatch geometry,
    # so the authored Blender model needs its own aft pressure wall. Keep a
    # readable central hatch, but close every surrounding wall/ceiling/floor gap.
    z = 3.72
    create_panel_patch(
        "Aft_pressure_bulkhead_left_wall_skin",
        [(-1.70, 0.30, z), (-0.78, 0.38, z), (-0.78, 2.02, z), (-1.44, 2.42, z)],
        wall_mat,
        target,
        0.055,
    )
    create_panel_patch(
        "Aft_pressure_bulkhead_right_wall_skin",
        [(0.78, 0.38, z), (1.70, 0.30, z), (1.44, 2.42, z), (0.78, 2.02, z)],
        wall_mat,
        target,
        0.055,
    )
    create_panel_patch(
        "Aft_pressure_bulkhead_overhead_skin",
        [(-1.34, 1.92, z), (1.34, 1.92, z), (1.02, 2.54, z), (-1.02, 2.54, z)],
        wall_mat,
        target,
        0.055,
    )
    create_panel_patch(
        "Aft_pressure_bulkhead_lower_sill_skin",
        [(-1.18, 0.25, z), (1.18, 0.25, z), (0.86, 0.54, z), (-0.86, 0.54, z)],
        floor_mat,
        target,
        0.060,
    )

    add_arch_tube("Aft_pressure_bulkhead_outer_welded_frame", z - 0.06, 1.66, 0.30, 2.48, 1.02, 0.050, trim_mat, target)
    add_arch_tube("Aft_pressure_bulkhead_hatch_frame", z - 0.13, 0.84, 0.52, 2.02, 0.98, 0.042, trim_mat, target)
    add_arch_tube("Aft_pressure_bulkhead_inner_seal", z - 0.18, 0.70, 0.64, 1.88, 1.02, 0.020, rubber_mat, target)

    # Volumetric blocker panels make the aft closure reliable in Godot even
    # from grazing reverse-walkthrough angles where thin quads can disappear.
    add_beveled_cube("Aft_pressure_bulkhead_left_blocking_panel", (-1.22, 1.22, z - 0.18), (0.74, 1.86, 0.16), wall_mat, target, 0.040)
    add_beveled_cube("Aft_pressure_bulkhead_right_blocking_panel", (1.22, 1.22, z - 0.18), (0.74, 1.86, 0.16), wall_mat, target, 0.040)
    add_beveled_cube("Aft_pressure_bulkhead_top_blocking_panel", (0.0, 2.18, z - 0.18), (2.55, 0.56, 0.16), wall_mat, target, 0.040)
    add_beveled_cube("Aft_pressure_bulkhead_bottom_blocking_panel", (0.0, 0.42, z - 0.18), (2.36, 0.34, 0.16), floor_mat, target, 0.032)

    add_beveled_cube("Aft_hatch_closed_inner_panel", (0.0, 1.22, z - 0.28), (1.16, 1.20, 0.100), trim_mat, target, 0.045)
    add_beveled_cube("Aft_hatch_center_recess", (0.0, 1.22, z - 0.35), (0.72, 0.72, 0.055), wall_mat, target, 0.030)
    add_beveled_cube("Aft_hatch_lower_kick_plate", (0.0, 0.70, z - 0.42), (0.92, 0.18, 0.045), dark_panel_mat, target, 0.014)
    add_beveled_cube("Aft_hatch_status_strip", (0.0, 1.86, z - 0.43), (0.42, 0.035, 0.030), screen_mat, target, 0.006)
    add_beveled_cube("Aft_hatch_pull_handle", (0.42, 1.16, z - 0.45), (0.055, 0.36, 0.050), rubber_mat, target, 0.012)

    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        add_cylinder_between(
            f"Aft_enclosure_upper_return_longeron_{label}",
            (side * 1.12, 2.02, 2.72),
            (side * 0.86, 2.15, 3.82),
            0.032,
            trim_mat,
            target,
            12,
        )
        add_cylinder_between(
            f"Aft_enclosure_lower_return_seal_{label}",
            (side * 1.45, 0.58, 2.72),
            (side * 0.96, 0.54, 3.74),
            0.026,
            rubber_mat,
            target,
            10,
        )
        add_beveled_cube(
            f"Aft_pressure_bulkhead_side_equipment_panel_{label}",
            (side * 1.08, 1.18, z - 0.26),
            (0.030, 0.72, 0.040),
            dark_panel_mat,
            target,
            0.008,
        )
        for index, y in enumerate([0.58, 1.88]):
            add_beveled_cube(
                f"Aft_pressure_bulkhead_visible_fastener_{label}_{index}",
                (side * 1.22, y, z - 0.34),
                (0.060, 0.060, 0.030),
                bolt_mat,
                target,
                0.010,
            )

    add_beveled_cube("Aft_floor_to_hatch_continuous_threshold", (0.0, 0.30, 3.58), (1.72, 0.080, 0.54), floor_mat, target, 0.024)
    add_beveled_cube("Aft_ceiling_to_hatch_return_panel", (0.0, 2.34, 3.48), (1.92, 0.080, 0.62), wall_mat, target, 0.024)


def create_overhead_enclosure_blockers(
    wall_mat: bpy.types.Material,
    trim_mat: bpy.types.Material,
    rubber_mat: bpy.types.Material,
    screen_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Add continuous upper pressure-shell panels visible from reverse views."""
    overhead_sections = [
        (-5.78, [(-1.02, 2.34), (-0.58, 2.76), (0.0, 2.90), (0.58, 2.76), (1.02, 2.34)]),
        (-4.60, [(-1.36, 2.22), (-0.78, 2.58), (0.0, 2.70), (0.78, 2.58), (1.36, 2.22)]),
        (-3.20, [(-1.70, 2.06), (-0.98, 2.42), (0.0, 2.56), (0.98, 2.42), (1.70, 2.06)]),
        (-1.40, [(-1.94, 1.96), (-1.12, 2.36), (0.0, 2.52), (1.12, 2.36), (1.94, 1.96)]),
        (0.60, [(-1.92, 1.94), (-1.10, 2.34), (0.0, 2.50), (1.10, 2.34), (1.92, 1.94)]),
        (2.40, [(-1.50, 1.96), (-0.88, 2.30), (0.0, 2.44), (0.88, 2.30), (1.50, 1.96)]),
        (3.62, [(-1.00, 2.00), (-0.58, 2.30), (0.0, 2.42), (0.58, 2.30), (1.00, 2.00)]),
    ]
    overhead = create_loft_mesh("Cabin_overhead_pressure_liner_unbroken", overhead_sections, wall_mat, target)
    bevel = overhead.modifiers.new("overhead pressure liner bevel", "BEVEL")
    bevel.width = 0.018
    bevel.segments = 2

    add_beveled_cube("Cabin_overhead_center_service_spine", (0.0, 2.48, -0.98), (0.40, 0.12, 8.90), trim_mat, target, 0.030)
    add_beveled_cube("Cabin_overhead_aft_hatch_return_cap", (0.0, 2.34, 3.30), (1.34, 0.16, 0.78), wall_mat, target, 0.030)
    add_beveled_cube("Cabin_overhead_cockpit_return_cap", (0.0, 2.55, -5.60), (1.12, 0.14, 0.62), wall_mat, target, 0.028)

    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        add_cylinder_between(
            f"Cabin_overhead_side_gasket_{label}",
            (side * 1.06, 2.22, -5.60),
            (side * 1.22, 2.06, 3.42),
            0.026,
            rubber_mat,
            target,
            12,
        )
        add_cylinder_between(
            f"Cabin_overhead_inner_light_strip_{label}",
            (side * 0.44, 2.44, -4.90),
            (side * 0.48, 2.28, 2.85),
            0.010,
            screen_mat,
            target,
            8,
        )
        for index, z in enumerate([-4.40, -2.40, -0.40, 1.60, 3.00]):
            add_beveled_cube(
                f"Cabin_overhead_fastener_plate_{label}_{index}",
                (side * 0.72, 2.36, z),
                (0.18, 0.030, 0.12),
                trim_mat,
                target,
                0.006,
            )


def create_enclosure_completion_skin(
    wall_mat: bpy.types.Material,
    floor_mat: bpy.types.Material,
    trim_mat: bpy.types.Material,
    rubber_mat: bpy.types.Material,
    dark_panel_mat: bpy.types.Material,
    screen_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Add broad closure surfaces for gaps exposed by round-trip walkthroughs."""
    # These are intentionally larger, continuous pressure-shell surfaces. The
    # fine rib layer can sit on top, but the player should never see space
    # through the cabin sides, lower wall coves, or overhead returns.
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"

        lower_cove_sections = []
        for z, inner_x, outer_x, floor_y, wall_y in [
            (-5.55, 0.70, 1.30, 0.30, 0.92),
            (-4.10, 0.84, 1.52, 0.27, 1.04),
            (-2.20, 1.02, 1.78, 0.25, 1.10),
            (-0.10, 1.16, 1.98, 0.25, 1.10),
            (1.95, 1.02, 1.78, 0.28, 1.02),
            (3.34, 0.76, 1.36, 0.34, 0.92),
        ]:
            lower_cove_sections.append((z, [
                (side * inner_x, floor_y),
                (side * outer_x, floor_y + 0.08),
                (side * outer_x, wall_y),
                (side * (inner_x + 0.12), wall_y - 0.10),
            ]))
        lower_cove = create_loft_mesh(f"Cabin_completion_unbroken_lower_cove_{label}", lower_cove_sections, floor_mat, target)
        bevel = lower_cove.modifiers.new("completion lower cove bevel", "BEVEL")
        bevel.width = 0.024
        bevel.segments = 3

        mid_wall_sections = []
        for z, inner_x, outer_x, lower_y, upper_y in [
            (-5.50, 1.00, 1.34, 0.78, 2.10),
            (-4.00, 1.18, 1.58, 0.86, 2.20),
            (-2.00, 1.44, 1.88, 0.90, 2.28),
            (0.10, 1.56, 2.02, 0.88, 2.24),
            (2.00, 1.34, 1.74, 0.84, 2.06),
            (3.42, 0.92, 1.34, 0.76, 1.82),
        ]:
            mid_wall_sections.append((z, [
                (side * inner_x, lower_y),
                (side * outer_x, lower_y + 0.05),
                (side * outer_x, upper_y),
                (side * inner_x, upper_y - 0.12),
            ]))
        mid_wall = create_loft_mesh(f"Cabin_completion_continuous_side_pressure_skin_{label}", mid_wall_sections, wall_mat, target)
        bevel = mid_wall.modifiers.new("completion side skin bevel", "BEVEL")
        bevel.width = 0.018
        bevel.segments = 2

        overhead_return_sections = []
        for z, inner_x, outer_x, inner_y, outer_y in [
            (-5.46, 0.58, 1.14, 2.62, 2.12),
            (-4.00, 0.78, 1.42, 2.54, 2.08),
            (-2.00, 1.02, 1.74, 2.54, 2.10),
            (0.10, 1.06, 1.86, 2.50, 2.06),
            (2.02, 0.92, 1.58, 2.42, 1.98),
            (3.36, 0.54, 1.10, 2.28, 1.84),
        ]:
            overhead_return_sections.append((z, [
                (side * inner_x, inner_y),
                (side * outer_x, outer_y),
                (side * (outer_x + 0.08), outer_y - 0.10),
                (side * (inner_x + 0.06), inner_y - 0.08),
            ]))
        overhead_return = create_loft_mesh(f"Cabin_completion_overhead_side_return_{label}", overhead_return_sections, wall_mat, target)
        bevel = overhead_return.modifiers.new("completion overhead return bevel", "BEVEL")
        bevel.width = 0.018
        bevel.segments = 2

        add_cylinder_between(
            f"Cabin_completion_floor_wall_pressure_seal_{label}",
            (side * 0.92, 0.42, -5.36),
            (side * 1.12, 0.40, 3.34),
            0.030,
            rubber_mat,
            target,
            12,
        )
        add_cylinder_between(
            f"Cabin_completion_overhead_pressure_seal_{label}",
            (side * 0.76, 2.42, -5.32),
            (side * 0.82, 2.24, 3.30),
            0.026,
            rubber_mat,
            target,
            12,
        )

        for index, z in enumerate([-4.55, -2.70, -0.70, 1.25, 2.82]):
            add_beveled_cube(
                f"Cabin_completion_dark_lower_service_cover_{label}_{index}",
                (side * 1.08, 0.67, z),
                (0.040, 0.22, 0.56),
                dark_panel_mat,
                target,
                0.012,
            )
            add_beveled_cube(
                f"Cabin_completion_small_marker_light_{label}_{index}",
                (side * 0.92, 1.56, z - 0.18),
                (0.020, 0.028, 0.16),
                screen_mat,
                target,
                0.004,
            )

    add_beveled_cube("Cabin_completion_forward_floor_wall_threshold_fill", (0.0, 0.32, -5.42), (1.74, 0.070, 0.52), floor_mat, target, 0.026)
    add_beveled_cube("Cabin_completion_aft_floor_wall_threshold_fill", (0.0, 0.30, 3.26), (2.10, 0.075, 0.58), floor_mat, target, 0.026)
    add_beveled_cube("Cabin_completion_aft_upper_corner_closeout", (0.0, 2.10, 3.32), (2.18, 0.32, 0.42), wall_mat, target, 0.030)
    add_beveled_cube("Cabin_completion_forward_upper_corner_closeout", (0.0, 2.44, -5.36), (1.48, 0.30, 0.42), wall_mat, target, 0.026)
    add_beveled_cube("Cabin_completion_center_floor_infill_aft", (0.0, 0.275, 2.68), (1.48, 0.040, 1.18), floor_mat, target, 0.022)
    add_beveled_cube("Cabin_completion_center_floor_infill_mid", (0.0, 0.270, -0.10), (1.72, 0.040, 3.80), floor_mat, target, 0.022)


def create_nose_tail_enclosure_finish(
    wall_mat: bpy.types.Material,
    floor_mat: bpy.types.Material,
    trim_mat: bpy.types.Material,
    rubber_mat: bpy.types.Material,
    dark_panel_mat: bpy.types.Material,
    screen_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Close the forward nose tub and aft hatch/tail returns exposed in review."""
    # Forward cockpit: keep the upper canopy visually open, but make the lower
    # nose, front corners, and side sills read as a sealed tub instead of a
    # platform floating inside the exterior shell.
    nose_floor_sections = [
        (-10.92, [(-0.34, 0.66), (0.34, 0.66), (0.52, 0.86), (-0.52, 0.86)]),
        (-10.30, [(-0.52, 0.62), (0.52, 0.62), (0.76, 0.88), (-0.76, 0.88)]),
        (-9.58, [(-0.68, 0.68), (0.68, 0.68), (0.92, 0.98), (-0.92, 0.98)]),
        (-8.82, [(-0.72, 0.94), (0.72, 0.94), (0.92, 1.14), (-0.92, 1.14)]),
    ]
    nose_floor = create_loft_mesh("Nose_completion_sealed_lower_tub_floor", nose_floor_sections, floor_mat, target)
    bevel = nose_floor.modifiers.new("nose lower tub bevel", "BEVEL")
    bevel.width = 0.026
    bevel.segments = 3

    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        cheek_sections = []
        for z, inner_x, outer_x, lower_y, upper_y in [
            (-10.94, 0.44, 0.70, 0.78, 1.30),
            (-10.28, 0.64, 0.92, 0.82, 1.40),
            (-9.50, 0.82, 1.08, 0.96, 1.52),
            (-8.64, 0.90, 1.06, 1.16, 1.58),
        ]:
            cheek_sections.append((z, [
                (side * inner_x, lower_y),
                (side * outer_x, lower_y + 0.08),
                (side * outer_x, upper_y),
                (side * inner_x, upper_y - 0.14),
            ]))
        cheek = create_loft_mesh(f"Nose_completion_forward_pressure_cheek_{label}", cheek_sections, wall_mat, target)
        bevel = cheek.modifiers.new("nose cheek bevel", "BEVEL")
        bevel.width = 0.020
        bevel.segments = 3

        add_cylinder_between(
            f"Nose_completion_floor_side_pressure_seal_{label}",
            (side * 0.48, 0.78, -10.82),
            (side * 0.78, 1.06, -8.74),
            0.024,
            trim_mat,
            target,
            12,
        )
        # Avoid equipment boxes above the cockpit sill; they read as random
        # opaque blocks inside the transparent exterior canopy.

    add_beveled_cube("Nose_completion_low_forward_pressure_bulkhead", (0.0, 1.02, -10.94), (0.92, 0.68, 0.085), wall_mat, target, 0.032)
    add_cylinder_between("Nose_completion_low_front_canopy_bow", (-0.42, 1.84, -10.92), (0.42, 1.84, -10.92), 0.020, trim_mat, target, 12)

    # Aft hatch/tail: close visible diagonal returns around the hatch so the
    # reverse walkthrough reads as a sealed rear pressure wall.
    aft_skin_sections = [
        (2.62, [(-1.50, 0.44), (-0.92, 0.38), (0.92, 0.38), (1.50, 0.44), (1.34, 2.00), (0.74, 2.30), (0.0, 2.42), (-0.74, 2.30), (-1.34, 2.00)]),
        (3.18, [(-1.28, 0.42), (-0.76, 0.36), (0.76, 0.36), (1.28, 0.42), (1.14, 1.88), (0.62, 2.18), (0.0, 2.30), (-0.62, 2.18), (-1.14, 1.88)]),
        (3.82, [(-0.94, 0.50), (-0.58, 0.44), (0.58, 0.44), (0.94, 0.50), (0.86, 1.70), (0.48, 1.98), (0.0, 2.10), (-0.48, 1.98), (-0.86, 1.70)]),
    ]
    aft_skin = create_loft_mesh("Tail_completion_tapered_pressure_endcap", aft_skin_sections, wall_mat, target)
    bevel = aft_skin.modifiers.new("tail pressure endcap bevel", "BEVEL")
    bevel.width = 0.018
    bevel.segments = 2

    add_beveled_cube("Tail_completion_hatch_floor_bridge", (0.0, 0.34, 3.64), (1.52, 0.11, 0.84), floor_mat, target, 0.028)
    add_beveled_cube("Tail_completion_hatch_overhead_bridge", (0.0, 2.18, 3.56), (1.56, 0.16, 0.78), wall_mat, target, 0.030)
    add_beveled_cube("Tail_completion_inner_hatch_dark_panel", (0.0, 1.22, 3.50), (0.90, 0.82, 0.060), dark_panel_mat, target, 0.026)
    add_beveled_cube("Tail_completion_hatch_status_window", (0.0, 1.76, 3.45), (0.42, 0.036, 0.030), screen_mat, target, 0.006)
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        add_cylinder_between(
            f"Tail_completion_side_pressure_weld_{label}",
            (side * 1.40, 0.72, 2.72),
            (side * 0.86, 1.62, 3.86),
            0.032,
            trim_mat,
            target,
            12,
        )
        add_cylinder_between(
            f"Tail_completion_overhead_corner_gasket_{label}",
            (side * 1.06, 1.96, 2.72),
            (side * 0.54, 2.06, 3.78),
            0.026,
            rubber_mat,
            target,
            12,
        )


def create_visible_canopy_and_tail_seals(
    glass_mat: bpy.types.Material,
    wall_mat: bpy.types.Material,
    trim_mat: bpy.types.Material,
    rubber_mat: bpy.types.Material,
    dark_panel_mat: bpy.types.Material,
    screen_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Add visible closure skins at the transparent canopy and aft hatch."""
    # The canopy must read as a sealed transparent dome during review. Keep the
    # panes segmented and lightly tinted to avoid the full-dome alpha streaking
    # that made earlier cockpit captures hard to read.
    create_panel_patch(
        "CanopyGlass_front_windscreen",
        [(-0.68, 1.58, -10.94), (0.68, 1.58, -10.94), (0.88, 2.58, -10.12), (-0.88, 2.58, -10.12)],
        glass_mat,
        target,
        0.014,
    )
    create_panel_patch(
        "CanopyGlass_overhead_dome",
        [(-0.86, 2.36, -10.16), (0.86, 2.36, -10.16), (1.04, 3.24, -7.00), (-1.04, 3.24, -7.00)],
        glass_mat,
        target,
        0.014,
    )
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        create_panel_patch(
            f"CanopyGlass_side_forward_{label}",
            [
                (side * 0.72, 1.42, -10.56),
                (side * 1.12, 1.82, -9.48),
                (side * 1.02, 2.72, -8.42),
                (side * 0.62, 2.36, -9.96),
            ],
            glass_mat,
            target,
            0.014,
        )
        create_panel_patch(
            f"CanopyGlass_side_aft_{label}",
            [
                (side * 1.12, 1.82, -9.48),
                (side * 1.18, 2.10, -6.92),
                (side * 1.04, 3.24, -7.00),
                (side * 1.02, 2.72, -8.42),
            ],
            glass_mat,
            target,
            0.014,
        )
        add_tube_polyline(
            f"Canopy_visible_outer_glass_full_length_seal_{label}",
            [
                (side * 0.58, 1.72, -10.78),
                (side * 1.10, 2.20, -7.02),
                (side * 1.16, 2.36, -5.52),
            ],
            0.018,
            rubber_mat,
            target,
            12,
        )

    add_cylinder_between("Canopy_visible_front_cross_seal", (-0.52, 1.82, -10.92), (0.52, 1.82, -10.92), 0.020, rubber_mat, target, 12)
    # No overhead center crown seal. The canopy should read as one clear dome
    # without a top-center structural rib.

    # Aft hatch: add an unmistakable inner pressure door and surrounding
    # closeout panels so the tail does not read as an open arch from reverse
    # review angles.
    create_panel_patch(
        "Tail_visible_full_pressure_bulkhead_skin",
        [(-1.30, 0.36, 3.36), (1.30, 0.36, 3.36), (1.02, 2.28, 3.36), (-1.02, 2.28, 3.36)],
        wall_mat,
        target,
        0.070,
    )
    add_beveled_cube("Tail_visible_solid_inner_hatch_door", (0.0, 1.22, 3.22), (1.04, 1.28, 0.16), trim_mat, target, 0.040)
    add_beveled_cube("Tail_visible_recessed_hatch_center_panel", (0.0, 1.20, 3.06), (0.68, 0.72, 0.045), dark_panel_mat, target, 0.018)
    add_beveled_cube("Tail_visible_hatch_lower_pressure_sill", (0.0, 0.52, 3.08), (1.36, 0.24, 0.18), trim_mat, target, 0.024)
    add_beveled_cube("Tail_visible_hatch_upper_pressure_sill", (0.0, 2.02, 3.08), (1.20, 0.20, 0.18), trim_mat, target, 0.024)
    add_beveled_cube("Tail_visible_hatch_status_light", (0.0, 1.84, 3.00), (0.42, 0.035, 0.030), screen_mat, target, 0.006)
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        add_beveled_cube(f"Tail_visible_side_closeout_block_{label}", (side * 0.92, 1.18, 3.12), (0.22, 1.36, 0.18), trim_mat, target, 0.030)
        add_cylinder_between(
            f"Tail_visible_inner_hatch_gasket_{label}",
            (side * 0.58, 0.58, 3.00),
            (side * 0.58, 1.90, 3.00),
            0.018,
            rubber_mat,
            target,
            10,
        )


def create_canopy_glass_readability_pass(
    fog_mat: bpy.types.Material,
    reflection_mat: bpy.types.Material,
    rubber_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Add restrained glass cues without turning the canopy into an opaque wall."""
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        add_cylinder_between(
            f"CanopyReflection_long_soft_arc_{label}",
            (side * 0.58, 2.30, -10.18),
            (side * 1.10, 2.54, -5.56),
            0.006,
            reflection_mat,
            target,
            8,
        )
        add_cylinder_between(
            f"CanopyReflection_lower_edge_catch_{label}",
            (side * 0.62, 1.62, -10.46),
            (side * 1.08, 1.72, -5.58),
            0.004,
            reflection_mat,
            target,
            8,
        )
        for index, (x, y, z, length) in enumerate([
            (0.76, 2.34, -9.96, 0.16),
            (0.90, 2.52, -8.98, 0.12),
            (0.82, 2.66, -8.14, 0.10),
        ]):
            add_beveled_cube(
                f"CanopyHaze_tiny_condensation_dash_{label}_{index}",
                (side * x, y, z),
                (0.006, 0.010, length),
                fog_mat,
                target,
                0.002,
            )

    add_cylinder_between("CanopyReflection_front_soft_header", (-0.46, 2.18, -10.62), (0.46, 2.18, -10.62), 0.005, reflection_mat, target, 10)
    # No top-center canopy bow: the exterior reads as a broad fighter canopy,
    # and the center line made the cockpit look busier and less transparent.


def create_interior_enclosure_polish_pass(
    wall_mat: bpy.types.Material,
    floor_mat: bpy.types.Material,
    trim_mat: bpy.types.Material,
    rubber_mat: bpy.types.Material,
    dark_panel_mat: bpy.types.Material,
    screen_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Add a final broad-surface enclosure pass over visible cabin gaps."""
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"

        # Continuous pressure skin behind the decorative rib layer. These
        # broad spans are deliberately less busy than the ribs so the cabin
        # reads as an enclosed shell instead of separate floating frames.
        upper_sections = []
        for z, inner_x, outer_x, lower_y, upper_y in [
            (-5.42, 0.98, 1.36, 1.06, 2.36),
            (-4.10, 1.18, 1.62, 1.00, 2.30),
            (-2.35, 1.44, 1.92, 0.96, 2.28),
            (-0.30, 1.60, 2.08, 0.92, 2.24),
            (1.72, 1.42, 1.86, 0.96, 2.16),
            (3.24, 1.02, 1.42, 1.02, 1.92),
        ]:
            upper_sections.append((z, [
                (side * inner_x, lower_y),
                (side * outer_x, lower_y + 0.06),
                (side * outer_x, upper_y),
                (side * inner_x, upper_y - 0.12),
            ]))
        upper_skin = create_loft_mesh(f"EnclosurePolish_continuous_upper_side_skin_{label}", upper_sections, wall_mat, target)
        bevel = upper_skin.modifiers.new("polish upper side skin bevel", "BEVEL")
        bevel.width = 0.014
        bevel.segments = 2

        lower_sections = []
        for z, inner_x, outer_x, floor_y, wall_y in [
            (-5.42, 0.70, 1.18, 0.28, 1.16),
            (-4.10, 0.84, 1.34, 0.25, 1.12),
            (-2.35, 1.06, 1.58, 0.23, 1.10),
            (-0.30, 1.20, 1.72, 0.23, 1.06),
            (1.72, 1.08, 1.56, 0.25, 1.06),
            (3.24, 0.76, 1.22, 0.32, 1.06),
        ]:
            lower_sections.append((z, [
                (side * inner_x, floor_y),
                (side * outer_x, floor_y + 0.08),
                (side * outer_x, wall_y),
                (side * (inner_x + 0.10), wall_y - 0.08),
            ]))
        lower_skin = create_loft_mesh(f"EnclosurePolish_unbroken_lower_cove_skin_{label}", lower_sections, floor_mat, target)
        bevel = lower_skin.modifiers.new("polish lower cove bevel", "BEVEL")
        bevel.width = 0.022
        bevel.segments = 3

        overhead_sections = []
        for z, inner_x, outer_x, inner_y, outer_y in [
            (-5.36, 0.52, 1.02, 2.66, 2.22),
            (-4.08, 0.72, 1.28, 2.56, 2.14),
            (-2.30, 0.98, 1.62, 2.54, 2.12),
            (-0.30, 1.10, 1.78, 2.50, 2.08),
            (1.74, 0.94, 1.50, 2.42, 2.02),
            (3.20, 0.54, 1.08, 2.26, 1.88),
        ]:
            overhead_sections.append((z, [
                (side * inner_x, inner_y),
                (side * outer_x, outer_y),
                (side * (outer_x + 0.06), outer_y - 0.10),
                (side * (inner_x + 0.05), inner_y - 0.08),
            ]))
        overhead_skin = create_loft_mesh(f"EnclosurePolish_overhead_return_skin_{label}", overhead_sections, wall_mat, target)
        bevel = overhead_skin.modifiers.new("polish overhead side return bevel", "BEVEL")
        bevel.width = 0.014
        bevel.segments = 2

        add_cylinder_between(
            f"EnclosurePolish_lower_corner_pressure_seal_{label}",
            (side * 0.88, 0.40, -5.36),
            (side * 1.02, 0.40, 3.22),
            0.034,
            rubber_mat,
            target,
            12,
        )
        add_cylinder_between(
            f"EnclosurePolish_upper_corner_pressure_seal_{label}",
            (side * 0.72, 2.42, -5.32),
            (side * 0.78, 2.20, 3.16),
            0.028,
            rubber_mat,
            target,
            12,
        )

        for index, z in enumerate([-4.72, -3.28, -1.62, 0.12, 1.72, 2.88]):
            add_beveled_cube(
                f"EnclosurePolish_floor_edge_infill_{label}_{index}",
                (side * 0.84, 0.30, z),
                (0.46, 0.040, 0.42),
                floor_mat,
                target,
                0.014,
            )

    add_beveled_cube("EnclosurePolish_center_floor_no_gap_mid_panel", (0.0, 0.292, -1.10), (1.68, 0.040, 5.80), floor_mat, target, 0.018)
    add_beveled_cube("EnclosurePolish_center_floor_no_gap_aft_panel", (0.0, 0.294, 2.56), (1.46, 0.040, 1.58), floor_mat, target, 0.018)
    add_beveled_cube("EnclosurePolish_aft_upper_return_block", (0.0, 2.16, 3.18), (2.08, 0.28, 0.64), wall_mat, target, 0.026)
    add_beveled_cube("EnclosurePolish_forward_threshold_return_block", (0.0, 2.48, -5.34), (1.34, 0.24, 0.58), wall_mat, target, 0.024)
    add_beveled_cube("EnclosurePolish_aft_floor_threshold_solid_fill", (0.0, 0.33, 3.24), (1.78, 0.070, 0.64), floor_mat, target, 0.022)
    add_beveled_cube("EnclosurePolish_forward_floor_threshold_solid_fill", (0.0, 0.36, -5.34), (1.26, 0.065, 0.54), floor_mat, target, 0.020)


def create_material_depth_detail_pass(
    trim_mat: bpy.types.Material,
    rubber_mat: bpy.types.Material,
    dark_panel_mat: bpy.types.Material,
    screen_mat: bpy.types.Material,
    warning_mat: bpy.types.Material,
    bolt_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Layer small material cues on top of broad enclosure surfaces."""
    # Floor wear and removable tread plates. These are intentionally shallow
    # overlays so they read as surface treatment, not new obstacles.
    for index, z in enumerate([-4.72, -3.46, -2.18, -0.92, 0.36, 1.62, 2.68]):
        add_beveled_cube(
            f"MaterialDepth_dark_scuffed_center_tread_{index}",
            (0.0, 0.333, z),
            (0.54, 0.022, 0.52),
            dark_panel_mat,
            target,
            0.012,
        )
        add_beveled_cube(
            f"MaterialDepth_trim_worn_left_floor_edge_{index}",
            (-0.62, 0.350, z),
            (0.060, 0.026, 0.62),
            bolt_mat,
            target,
            0.008,
        )
        add_beveled_cube(
            f"MaterialDepth_trim_worn_right_floor_edge_{index}",
            (0.62, 0.350, z),
            (0.060, 0.026, 0.62),
            bolt_mat,
            target,
            0.008,
        )
        add_beveled_cube(
            f"MaterialDepth_tiny_warning_floor_locator_{index}",
            (0.0, 0.358, z - 0.31),
            (0.22, 0.024, 0.040),
            warning_mat,
            target,
            0.004,
        )

    # Wall service panels and darker recesses break up the continuous gray shell
    # while staying flush enough to avoid visual/collision ambiguity.
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        for index, (z, y, height, width) in enumerate([
            (-4.48, 1.10, 0.34, 0.62),
            (-3.12, 1.46, 0.46, 0.56),
            (-1.54, 1.02, 0.30, 0.68),
            (0.10, 1.40, 0.44, 0.58),
            (1.78, 1.08, 0.32, 0.62),
            (2.92, 1.36, 0.40, 0.48),
        ]):
            add_beveled_cube(
                f"MaterialDepth_dark_flush_side_service_panel_{label}_{index}",
                (side * 1.025, y, z),
                (0.024, height, width),
                dark_panel_mat,
                target,
                0.006,
            )
            add_beveled_cube(
                f"MaterialDepth_trim_panel_upper_lip_{label}_{index}",
                (side * 1.000, y + height * 0.52, z),
                (0.026, 0.026, width + 0.08),
                trim_mat,
                target,
                0.004,
            )
            add_beveled_cube(
                f"MaterialDepth_trim_panel_lower_lip_{label}_{index}",
                (side * 1.000, y - height * 0.52, z),
                (0.026, 0.026, width + 0.08),
                trim_mat,
                target,
                0.004,
            )
            add_beveled_cube(
                f"MaterialDepth_small_cyan_service_status_light_{label}_{index}",
                (side * 0.990, y + height * 0.28, z - width * 0.36),
                (0.018, 0.040, 0.080),
                screen_mat,
                target,
                0.003,
            )

        add_cylinder_between(
            f"MaterialDepth_burnished_lower_handrail_{label}",
            (side * 0.94, 0.82, -5.00),
            (side * 1.10, 0.78, 3.16),
            0.015,
            bolt_mat,
            target,
            10,
        )
        add_cylinder_between(
            f"MaterialDepth_dark_upper_shadow_gasket_{label}",
            (side * 0.76, 2.16, -5.10),
            (side * 0.86, 2.00, 3.08),
            0.014,
            rubber_mat,
            target,
            10,
        )

    # Smaller practical light housings make the lighting feel sourced by
    # objects in the cabin instead of one invisible ambient fill.
    for index, z in enumerate([-4.18, -2.28, -0.32, 1.58, 2.82]):
        add_beveled_cube(
            f"MaterialDepth_overhead_dark_light_recess_{index}",
            (0.0, 2.405, z),
            (0.46, 0.040, 0.22),
            dark_panel_mat,
            target,
            0.010,
        )
        add_beveled_cube(
            f"MaterialDepth_overhead_cyan_light_lens_{index}",
            (0.0, 2.365, z),
            (0.30, 0.026, 0.060),
            screen_mat,
            target,
            0.004,
        )
        add_beveled_cube(
            f"MaterialDepth_overhead_warning_service_tab_{index}",
            (-0.31, 2.365, z),
            (0.070, 0.024, 0.060),
            warning_mat,
            target,
            0.003,
        )


def create_reference_guided_light_and_panel_pass(
    wall_mat: bpy.types.Material,
    floor_mat: bpy.types.Material,
    trim_mat: bpy.types.Material,
    rubber_mat: bpy.types.Material,
    dark_panel_mat: bpy.types.Material,
    screen_mat: bpy.types.Material,
    warning_mat: bpy.types.Material,
    bolt_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Add reference-guided material depth: sourced lights, inset modules, and darker cavities."""
    # The reference target has local pools of light, not a single ambient wash.
    # These lenses line up with the Godot practical lights in Ship.tscn.
    for index, (x, z, width, tint) in enumerate([
        (-0.48, 2.42, 0.34, "warm"),
        (0.52, -0.82, 0.38, "warm"),
        (-0.45, -4.42, 0.32, "cool"),
    ]):
        add_beveled_cube(
            f"ReferenceLighting_overhead_dark_practical_fixture_{index}",
            (x, 2.315, z),
            (width + 0.20, 0.090, 0.30),
            dark_panel_mat,
            target,
            0.020,
        )
        add_beveled_cube(
            f"ReferenceLighting_{tint}_practical_lens_{index}",
            (x, 2.260, z),
            (width, 0.030, 0.105),
            screen_mat if tint == "cool" else warning_mat,
            target,
            0.010,
        )
        for rail_x in [x - width * 0.62, x + width * 0.62]:
            add_cylinder_between(
                f"ReferenceLighting_fixture_retainer_rail_{index}_{rail_x:.2f}",
                (rail_x, 2.245, z - 0.14),
                (rail_x, 2.245, z + 0.14),
                0.010,
                trim_mat,
                target,
                8,
            )

    # Break the corridor into framed bays so the sides read as integrated
    # machinery instead of broad flat wall skins with floating rectangles.
    bay_centers = [-4.55, -3.28, -1.95, -0.62, 0.74, 2.05]
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        for index, z in enumerate(bay_centers):
            y = 1.18 if index % 2 == 0 else 1.36
            height = 0.58 if index % 2 == 0 else 0.72
            depth_x = side * 1.018
            add_beveled_cube(
                f"ReferencePanel_dark_recess_backplate_{label}_{index}",
                (depth_x, y, z),
                (0.030, height, 0.82),
                dark_panel_mat,
                target,
                0.012,
            )
            add_beveled_cube(
                f"ReferencePanel_trim_outer_vertical_front_{label}_{index}",
                (side * 0.986, y, z - 0.43),
                (0.034, height + 0.12, 0.040),
                trim_mat,
                target,
                0.008,
            )
            add_beveled_cube(
                f"ReferencePanel_trim_outer_vertical_rear_{label}_{index}",
                (side * 0.986, y, z + 0.43),
                (0.034, height + 0.12, 0.040),
                trim_mat,
                target,
                0.008,
            )
            add_beveled_cube(
                f"ReferencePanel_trim_outer_upper_{label}_{index}",
                (side * 0.986, y + height * 0.53, z),
                (0.034, 0.040, 0.88),
                trim_mat,
                target,
                0.008,
            )
            add_beveled_cube(
                f"ReferencePanel_trim_outer_lower_{label}_{index}",
                (side * 0.986, y - height * 0.53, z),
                (0.034, 0.040, 0.88),
                trim_mat,
                target,
                0.008,
            )
            for slat in range(4):
                slat_z = z - 0.28 + slat * 0.18
                add_beveled_cube(
                    f"ReferencePanel_rubber_vent_slat_{label}_{index}_{slat}",
                    (side * 0.964, y - 0.10, slat_z),
                    (0.026, 0.032, 0.105),
                    rubber_mat,
                    target,
                    0.004,
                )
            add_beveled_cube(
                f"ReferencePanel_tiny_cyan_embedded_status_{label}_{index}",
                (side * 0.956, y + height * 0.24, z + 0.30),
                (0.020, 0.050, 0.120),
                screen_mat,
                target,
                0.004,
            )
            add_beveled_cube(
                f"ReferencePanel_inner_midline_trim_{label}_{index}",
                (side * 0.952, y, z),
                (0.018, 0.026, 0.68),
                trim_mat,
                target,
                0.004,
            )
            add_beveled_cube(
                f"ReferencePanel_inner_vertical_split_{label}_{index}",
                (side * 0.950, y - height * 0.16, z - 0.10),
                (0.018, height * 0.42, 0.026),
                trim_mat,
                target,
                0.004,
            )
            for screw_z in [z - 0.32, z + 0.32]:
                for screw_y in [y - height * 0.36, y + height * 0.36]:
                    add_beveled_cube(
                        f"ReferencePanel_bolt_head_{label}_{index}_{screw_z:.1f}_{screw_y:.1f}",
                        (side * 0.942, screw_y, screw_z),
                        (0.018, 0.028, 0.028),
                        bolt_mat,
                        target,
                        0.004,
                    )
            if index % 2 == 1:
                add_cylinder_between(
                    f"ReferencePanel_diagonal_retainer_{label}_{index}",
                    (side * 0.946, y - height * 0.36, z - 0.34),
                    (side * 0.946, y + height * 0.34, z + 0.34),
                    0.009,
                    trim_mat,
                    target,
                    8,
                )
            else:
                for fine in range(3):
                    fine_y = y - 0.14 + fine * 0.12
                    add_beveled_cube(
                        f"ReferencePanel_fine_vent_line_{label}_{index}_{fine}",
                        (side * 0.942, fine_y, z - 0.20),
                        (0.018, 0.014, 0.28),
                        rubber_mat,
                        target,
                        0.003,
                    )

    # Replace plain walkway reading with a layered industrial tread similar to
    # the reference: darker removable panels, metal borders, and repeated grip.
    for index, z in enumerate([-4.70, -3.90, -3.10, -2.30, -1.50, -0.70, 0.10, 0.90, 1.70, 2.45]):
        add_beveled_cube(
            f"ReferenceFloor_inset_dark_removable_plate_{index}",
            (0.0, 0.366, z),
            (0.92, 0.018, 0.46),
            dark_panel_mat,
            target,
            0.012,
        )
        add_beveled_cube(
            f"ReferenceFloor_thin_front_trim_{index}",
            (0.0, 0.382, z - 0.25),
            (0.98, 0.018, 0.026),
            trim_mat,
            target,
            0.004,
        )
        add_beveled_cube(
            f"ReferenceFloor_thin_rear_trim_{index}",
            (0.0, 0.382, z + 0.25),
            (0.98, 0.018, 0.026),
            trim_mat,
            target,
            0.004,
        )
        for stripe in [-0.30, -0.10, 0.10, 0.30]:
            add_beveled_cube(
                f"ReferenceFloor_rubber_grip_strip_{index}_{stripe:.1f}",
                (stripe, 0.397, z),
                (0.030, 0.012, 0.36),
                rubber_mat,
                target,
                0.003,
            )

    # Larger, readable practical sconces. These correspond to OmniLight3D
    # nodes in Ship.tscn so visible fixtures and actual light pools agree.
    for index, (side, z, y, tint) in enumerate([
        (-1.0, 1.35, 1.74, "warm"),
        (1.0, -0.55, 1.74, "warm"),
        (-1.0, -3.22, 1.72, "cool"),
    ]):
        label = "L" if side < 0 else "R"
        add_beveled_cube(
            f"ReferenceLighting_side_sconce_dark_recess_{label}_{index}",
            (side * 0.970, y, z),
            (0.045, 0.34, 0.42),
            dark_panel_mat,
            target,
            0.014,
        )
        add_beveled_cube(
            f"ReferenceLighting_side_{tint}_practical_lens_{label}_{index}",
            (side * 0.938, y + 0.02, z),
            (0.026, 0.088, 0.155),
            screen_mat if tint == "cool" else warning_mat,
            target,
            0.010,
        )
        add_beveled_cube(
            f"ReferenceLighting_side_sconce_dark_inner_mask_{label}_{index}",
            (side * 0.926, y + 0.02, z),
            (0.018, 0.150, 0.255),
            dark_panel_mat,
            target,
            0.006,
        )
        add_beveled_cube(
            f"ReferenceLighting_side_sconce_small_visible_core_{label}_{index}",
            (side * 0.912, y + 0.02, z),
            (0.020, 0.070, 0.125),
            screen_mat if tint == "cool" else warning_mat,
            target,
            0.008,
        )
        add_beveled_cube(
            f"ReferenceLighting_side_sconce_upper_brow_{label}_{index}",
            (side * 0.930, y + 0.215, z),
            (0.040, 0.042, 0.48),
            trim_mat,
            target,
            0.006,
        )
        add_beveled_cube(
            f"ReferenceLighting_side_sconce_lower_brow_{label}_{index}",
            (side * 0.930, y - 0.215, z),
            (0.040, 0.042, 0.48),
            trim_mat,
            target,
            0.006,
        )

    # Readable bay-to-bay structural borders, sized deliberately larger than
    # bolt detail so they hold up in walkthrough review media.
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        for index, z in enumerate([-4.00, -2.65, -1.28, 0.08, 1.46, 2.74]):
            add_cylinder_between(
                f"ReferenceStructure_vertical_dark_wall_stanchion_{label}_{index}",
                (side * 0.936, 0.56, z),
                (side * 0.936, 2.08, z),
                0.018,
                trim_mat,
                target,
                10,
            )
            add_beveled_cube(
                f"ReferenceStructure_stanchion_shadow_groove_{label}_{index}",
                (side * 0.918, 1.28, z + 0.055),
                (0.018, 1.18, 0.026),
                rubber_mat,
                target,
                0.004,
            )


def create_lighting_sprint_practical_path_pass(
    floor_mat: bpy.types.Material,
    trim_mat: bpy.types.Material,
    rubber_mat: bpy.types.Material,
    dark_panel_mat: bpy.types.Material,
    screen_mat: bpy.types.Material,
    warning_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Add small visible fixtures that justify the low path-light pools in Godot."""
    path_zones = [
        (-4.72, "cool"),
        (-3.36, "warm"),
        (-2.02, "warm"),
        (-0.66, "cool"),
        (0.78, "warm"),
        (2.08, "warm"),
    ]

    for index, (z, tint) in enumerate(path_zones):
        lens_mat = screen_mat if tint == "cool" else warning_mat
        lens_token = "cool" if tint == "cool" else "warm"
        for side in [-1.0, 1.0]:
            label = "L" if side < 0 else "R"
            add_beveled_cube(
                f"LightingSprint01_low_path_dark_recess_{label}_{index}",
                (side * 0.71, 0.435, z),
                (0.22, 0.030, 0.20),
                dark_panel_mat,
                target,
                0.010,
            )
            add_beveled_cube(
                f"LightingSprint01_low_path_{lens_token}_lens_{label}_{index}",
                (side * 0.71, 0.460, z - 0.006),
                (0.130, 0.020, 0.050),
                lens_mat,
                target,
                0.006,
            )
            add_beveled_cube(
                f"LightingSprint01_low_path_rubber_gasket_{label}_{index}",
                (side * 0.71, 0.457, z + 0.058),
                (0.176, 0.016, 0.018),
                rubber_mat,
                target,
                0.003,
            )

        add_beveled_cube(
            f"LightingSprint01_floor_pool_soft_catch_panel_{index}",
            (0.0, 0.421, z + 0.11),
            (0.82, 0.010, 0.42),
            floor_mat,
            target,
            0.006,
        )
        add_beveled_cube(
            f"LightingSprint01_floor_shadow_break_trim_crossbar_{index}",
            (0.0, 0.438, z - 0.23),
            (1.28, 0.014, 0.024),
            trim_mat,
            target,
            0.004,
        )

    for index, z in enumerate([-4.35, -1.12, 2.32]):
        add_beveled_cube(
            f"LightingSprint01_overhead_source_mask_{index}",
            (0.0, 2.388, z),
            (0.62, 0.028, 0.31),
            dark_panel_mat,
            target,
            0.010,
        )
        add_beveled_cube(
            f"LightingSprint01_overhead_warm_lens_core_{index}",
            (0.0, 2.360, z),
            (0.31, 0.018, 0.070),
            warning_mat,
            target,
            0.006,
        )


def create_solo_falcon_reference_brightness_pass(
    bright_mat: bpy.types.Material,
    luminous_mat: bpy.types.Material,
    warm_luminous_mat: bpy.types.Material,
    gloss_mat: bpy.types.Material,
    trim_mat: bpy.types.Material,
    dark_mat: bpy.types.Material,
    warning_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Reference-inspired bright panels, glossy floor plates, and fixture housings."""
    # Broad white/gray wall cushions, named to keep their Blender material
    # instead of being caught by the Godot wall/panel material override.
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        for index, z in enumerate([-4.35, -2.70, -1.02, 0.68, 2.30]):
            wall_x = 1.28 if z < -2.0 else 1.62
            add_beveled_cube(
                f"SoloFalconWhiteCushionLower_{label}_{index}",
                (side * wall_x, 0.88, z),
                (0.050, 0.44, 0.72),
                bright_mat,
                target,
                0.035,
            )
            add_beveled_cube(
                f"SoloFalconWhiteCushionUpper_{label}_{index}",
                (side * (wall_x * 0.93), 1.46, z - 0.04),
                (0.045, 0.40, 0.62),
                bright_mat,
                target,
                0.032,
            )
            add_beveled_cube(
                f"SoloFalconBlackInsetModule_{label}_{index}",
                (side * (wall_x * 0.88), 1.05, z + 0.36),
                (0.030, 0.32, 0.18),
                dark_mat,
                target,
                0.010,
            )
            add_beveled_cube(
                f"SoloFalconAmberButtonBank_{label}_{index}",
                (side * (wall_x * 0.855), 1.05, z + 0.36),
                (0.020, 0.18, 0.046),
                warm_luminous_mat,
                target,
                0.004,
            )

        for index, z in enumerate([-4.90, -3.55, -2.18, -0.82, 0.56, 1.92, 3.02]):
            wall_x = 1.18 if z < -2.6 else 1.52
            add_beveled_cube(
                f"SoloFalconHorizontalWhiteBumper_{label}_{index}",
                (side * wall_x, 0.56, z),
                (0.070, 0.125, 0.82),
                bright_mat,
                target,
                0.030,
            )
            add_beveled_cube(
                f"SoloFalconUpperWhiteSoffitPad_{label}_{index}",
                (side * (wall_x * 0.86), 1.92, z),
                (0.058, 0.155, 0.70),
                bright_mat,
                target,
                0.026,
            )
            add_beveled_cube(
                f"SoloFalconNarrowBlackReveal_{label}_{index}",
                (side * (wall_x * 0.815), 1.72, z),
                (0.020, 0.055, 0.60),
                dark_mat,
                target,
                0.006,
            )

    # Bright ceiling boxes inspired by the reference's rectangular overhead
    # panels. These visibly justify the brighter cabin pass.
    for index, (x, z, sx) in enumerate([
        (-0.50, -4.20, 0.38),
        (0.50, -3.12, 0.38),
        (-0.48, -1.45, 0.44),
        (0.48, 0.35, 0.44),
        (-0.40, 2.10, 0.36),
    ]):
        add_beveled_cube(
            f"SoloFalconCeilingWhiteBox_{index}",
            (x, 2.355, z),
            (sx + 0.18, 0.055, 0.50),
            bright_mat,
            target,
            0.024,
        )
        add_beveled_cube(
            f"SoloFalconCeilingLuminousCore_{index}",
            (x, 2.318, z),
            (sx, 0.020, 0.16),
            luminous_mat,
            target,
            0.010,
        )
        add_beveled_cube(
            f"SoloFalconCeilingDarkVent_{index}",
            (x + 0.33, 2.318, z + 0.18),
            (0.18, 0.018, 0.11),
            dark_mat,
            target,
            0.006,
        )

    # Glossy black floor overlays and thin bright seams create the reference
    # floor read without requiring true screen-space reflections.
    for index, z in enumerate([-4.30, -3.08, -1.86, -0.62, 0.62, 1.84, 2.74]):
        add_beveled_cube(
            f"SoloFalconGlossDeckTile_{index}",
            (0.0, 0.432, z),
            (0.82, 0.012, 0.72),
            gloss_mat,
            target,
            0.010,
        )
        add_beveled_cube(
            f"SoloFalconBrightDeckSeamFront_{index}",
            (0.0, 0.445, z - 0.37),
            (1.12, 0.010, 0.026),
            bright_mat,
            target,
            0.004,
        )
        add_beveled_cube(
            f"SoloFalconSideGlowReflectionLeft_{index}",
            (-0.56, 0.448, z),
            (0.040, 0.010, 0.54),
            luminous_mat,
            target,
            0.004,
        )
        add_beveled_cube(
            f"SoloFalconSideGlowReflectionRight_{index}",
            (0.56, 0.448, z),
            (0.040, 0.010, 0.54),
            luminous_mat,
            target,
            0.004,
        )

    # A brighter forward arch collar echoes the reference's circular white ring
    # while keeping the current ShuttleA corridor/cockpit layout.
    for arch_index, (z, radius_x, radius_y, center_y) in enumerate([(-5.67, 0.88, 0.82, 1.58), (3.12, 1.16, 0.94, 1.42)]):
        for index, angle in enumerate([-72, -50, -28, -8, 8, 28, 50, 72]):
            x = math.sin(math.radians(angle)) * radius_x
            y = center_y + math.cos(math.radians(angle)) * radius_y
            add_beveled_cube(
                f"SoloFalconWhiteArchPad_{arch_index}_{index}",
                (x, y, z),
                (0.22, 0.18, 0.065),
                bright_mat,
                target,
                0.026,
            )
        add_beveled_cube(f"SoloFalconArchAmberStatus_{arch_index}", (0.0, center_y + radius_y + 0.08, z), (0.48, 0.040, 0.050), warm_luminous_mat, target, 0.006)

    # Bring the brighter reference language into the pilot volume. These parts
    # sit inside the canopy and console silhouette so the cockpit review no
    # longer reads as an almost black/cyan tunnel.
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        add_beveled_cube(
            f"SoloFalconCockpitBrightConsoleCheek_{label}",
            (side * 0.66, 1.105, -8.98),
            (0.034, 0.115, 0.62),
            bright_mat,
            target,
            0.018,
        )
        add_beveled_cube(
            f"SoloFalconCockpitBlackConsoleInset_{label}",
            (side * 0.632, 1.118, -9.02),
            (0.014, 0.070, 0.30),
            dark_mat,
            target,
            0.006,
        )
        add_beveled_cube(
            f"SoloFalconCockpitWarmSwitchRun_{label}",
            (side * 0.620, 1.126, -9.02),
            (0.008, 0.030, 0.22),
            warm_luminous_mat,
            target,
            0.004,
        )
        add_beveled_cube(
            f"SoloFalconCockpitCanopySideBulkheadPad_{label}",
            (side * 0.88, 1.650, -8.42),
            (0.035, 0.155, 0.62),
            dark_mat,
            target,
            0.014,
        )
        add_beveled_cube(
            f"SoloFalconCockpitCanopyDarkReveal_{label}",
            (side * 0.852, 1.650, -8.42),
            (0.012, 0.075, 0.48),
            trim_mat,
            target,
            0.005,
        )
        add_beveled_cube(
            f"SoloFalconCockpitCanopyWarmPractical_{label}",
            (side * 0.836, 1.672, -8.82),
            (0.008, 0.030, 0.16),
            warm_luminous_mat,
            target,
            0.004,
        )

    # Do not place white overhead fixtures above the pilot seat. In the cockpit
    # walkthrough they read as two flat square objects sitting on top of the
    # chair instead of as ceiling-mounted lighting.

    # Inboard bright pads are deliberately closer to the walking volume than
    # the outer shell pads so the first-person walkthrough reads the reference
    # language instead of seeing mostly dark rails.
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        for index, z in enumerate([-4.55, -3.10, -1.62, -0.12, 1.34, 2.62]):
            module_x = 1.04
            add_beveled_cube(
                f"SoloFalconVisibleModuleDarkBackplate_{label}_{index}",
                (side * (module_x + 0.030), 1.28, z),
                (0.045, 0.68, 0.66),
                dark_mat,
                target,
                0.020,
            )
            add_beveled_cube(
                f"SoloFalconVisibleWhiteWallSlab_{label}_{index}",
                (side * module_x, 1.30, z - 0.015),
                (0.046, 0.48, 0.42),
                bright_mat,
                target,
                0.035,
            )
            for trim_index, (trim_y, trim_z, trim_sy, trim_sz) in enumerate([
                (1.58, z - 0.015, 0.032, 0.52),
                (1.02, z - 0.015, 0.032, 0.52),
                (1.30, z - 0.255, 0.50, 0.026),
                (1.30, z + 0.225, 0.50, 0.026),
            ]):
                add_beveled_cube(
                    f"SoloFalconVisibleModuleTrim_{label}_{index}_{trim_index}",
                    (side * (module_x - 0.032), trim_y, trim_z),
                    (0.018, trim_sy, trim_sz),
                    trim_mat,
                    target,
                    0.005,
                )
            add_beveled_cube(
                f"SoloFalconVisibleModuleInsetLower_{label}_{index}",
                (side * (module_x - 0.050), 1.08, z - 0.010),
                (0.018, 0.120, 0.300),
                dark_mat,
                target,
                0.006,
            )
            add_beveled_cube(
                f"SoloFalconVisibleBlackControlInset_{label}_{index}",
                (side * (module_x - 0.062), 1.34, z + 0.165),
                (0.018, 0.220, 0.105),
                dark_mat,
                target,
                0.008,
            )
            add_beveled_cube(
                f"SoloFalconVisibleWarmButtonStack_{label}_{index}",
                (side * (module_x - 0.076), 1.34, z + 0.165),
                (0.010, 0.132, 0.028),
                warm_luminous_mat,
                target,
                0.004,
            )
            add_beveled_cube(
                f"SoloFalconVisibleCoolStatusChip_{label}_{index}",
                (side * (module_x - 0.078), 1.54, z - 0.205),
                (0.010, 0.065, 0.032),
                luminous_mat,
                target,
                0.003,
            )

    for index, z in enumerate([-4.10, -2.72, -1.28, 0.18, 1.62, 2.78]):
        add_beveled_cube(
            f"SoloFalconMirrorGlossCenterPane_{index}",
            (0.0, 0.456, z),
            (0.54, 0.010, 0.74),
            gloss_mat,
            target,
            0.008,
        )
        add_beveled_cube(
            f"SoloFalconWhiteFloorSpecularEdge_{index}",
            (0.37, 0.462, z),
            (0.032, 0.010, 0.64),
            bright_mat,
            target,
            0.003,
        )

    # Smaller layered pads fill the empty dark runs between major modules. The
    # reference has dense but orderly paneling, so these are intentionally
    # repeated and framed instead of large single slabs.
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        for index, z in enumerate([-4.95, -3.75, -2.38, -0.92, 0.48, 1.82, 2.92]):
            add_beveled_cube(
                f"SoloFalconCabinLayeredWhiteLowerPad_{label}_{index}",
                (side * 1.25, 0.74, z),
                (0.032, 0.135, 0.38),
                bright_mat,
                target,
                0.016,
            )
            add_beveled_cube(
                f"SoloFalconCabinLayeredBlackRevealLower_{label}_{index}",
                (side * 1.228, 0.74, z + 0.01),
                (0.012, 0.050, 0.28),
                dark_mat,
                target,
                0.004,
            )
            add_beveled_cube(
                f"SoloFalconCabinLayeredWhiteUpperPad_{label}_{index}",
                (side * 1.22, 1.78, z + 0.06),
                (0.030, 0.120, 0.34),
                bright_mat,
                target,
                0.014,
            )
            if index % 2 == 0:
                add_beveled_cube(
                    f"SoloFalconCabinWarmMicroCluster_{label}_{index}",
                    (side * 1.202, 1.005, z - 0.12),
                    (0.012, 0.040, 0.155),
                    warm_luminous_mat,
                    target,
                    0.003,
                )

    for index, z in enumerate([-4.72, -3.35, -1.96, -0.52, 0.92, 2.28]):
        add_beveled_cube(
            f"SoloFalconCeilingReferenceDarkHousing_{index}",
            (0.0, 2.300, z),
            (1.05, 0.032, 0.145),
            dark_mat,
            target,
            0.010,
        )
        add_beveled_cube(
            f"SoloFalconCeilingReferenceWhiteLiner_{index}",
            (0.0, 2.278, z),
            (0.82, 0.020, 0.102),
            bright_mat,
            target,
            0.010,
        )
        add_beveled_cube(
            f"SoloFalconCeilingReferenceWarmSlit_{index}",
            (0.0, 2.260, z),
            (0.58, 0.010, 0.024),
            warm_luminous_mat,
            target,
            0.004,
        )
        add_beveled_cube(
            f"SoloFalconWhiteFloorSpecularEdgeMirror_{index}",
            (-0.37, 0.462, z),
            (0.032, 0.010, 0.64),
            bright_mat,
            target,
            0.003,
        )


def create_cockpit_viewport_cleanup_pass(
    trim_mat: bpy.types.Material,
    rubber_mat: bpy.types.Material,
    dark_mat: bpy.types.Material,
    warm_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Organize the canopy into deliberate windshield frames and low-profile sills."""
    add_cylinder_between("CockpitClean_front_left_windscreen_post", (-0.56, 1.78, -10.86), (-0.82, 2.34, -9.88), 0.026, trim_mat, target, 12)
    add_cylinder_between("CockpitClean_front_right_windscreen_post", (0.56, 1.78, -10.86), (0.82, 2.34, -9.88), 0.026, trim_mat, target, 12)
    add_cylinder_between("CockpitClean_front_upper_header", (-0.80, 2.34, -9.88), (0.80, 2.34, -9.88), 0.028, trim_mat, target, 14)
    add_cylinder_between("CockpitClean_front_lower_gasket", (-0.50, 1.76, -10.86), (0.50, 1.76, -10.86), 0.022, rubber_mat, target, 12)

    add_beveled_cube("CockpitClean_low_dashboard_dark_cap", (0.0, 1.155, -9.78), (0.94, 0.032, 0.115), dark_mat, target, 0.014)
    add_beveled_cube("CockpitClean_low_dashboard_warm_status_left", (-0.26, 1.180, -9.77), (0.13, 0.010, 0.024), warm_mat, target, 0.003)
    add_beveled_cube("CockpitClean_low_dashboard_warm_status_right", (0.26, 1.180, -9.77), (0.13, 0.010, 0.024), warm_mat, target, 0.003)

    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        add_tube_polyline(
            f"CockpitClean_side_structural_full_canopy_bow_{label}",
            [
                (side * 0.78, 1.54, -10.30),
                (side * 1.05, 2.20, -7.05),
                (side * 1.16, 2.42, -5.52),
            ],
            0.026,
            trim_mat,
            target,
            14,
        )
        add_tube_polyline(
            f"CockpitClean_side_inner_full_canopy_gasket_{label}",
            [
                (side * 0.70, 1.66, -10.22),
                (side * 0.96, 2.14, -7.10),
                (side * 1.06, 2.32, -5.54),
            ],
            0.014,
            rubber_mat,
            target,
            12,
        )
        # Keep the side canopy below the bow visually open; broad dark panels
        # here made the cockpit read as an opaque tunnel.
        add_tube_polyline(
            f"CockpitClean_side_lower_full_canopy_return_{label}",
            [
                (side * 0.74, 1.50, -7.02),
                (side * 0.90, 1.56, -6.28),
                (side * 1.08, 1.66, -5.54),
            ],
            0.020,
            trim_mat,
            target,
            12,
        )
        add_beveled_cube(
            f"CockpitClean_rear_canopy_anchor_socket_upper_{label}",
            (side * 1.15, 2.38, -5.50),
            (0.22, 0.20, 0.20),
            trim_mat,
            target,
            0.030,
        )
        add_beveled_cube(
            f"CockpitClean_rear_canopy_anchor_socket_lower_{label}",
            (side * 1.08, 1.66, -5.50),
            (0.20, 0.18, 0.22),
            trim_mat,
            target,
            0.026,
        )
        add_cylinder_between(
            f"CockpitClean_rear_canopy_anchor_web_{label}",
            (side * 1.14, 2.30, -5.50),
            (side * 1.08, 1.72, -5.50),
            0.022,
            trim_mat,
            target,
            12,
        )


def create_cockpit_reference_detail_pass(
    trim_mat: bpy.types.Material,
    rubber_mat: bpy.types.Material,
    dark_mat: bpy.types.Material,
    bolt_mat: bpy.types.Material,
    warm_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Add compact reference-style cockpit detail around, not over, the viewport."""
    # This pass used to add tiny canopy bolts and a second layer of seat
    # hardware. In the cockpit walkthrough those pieces read as floating
    # artifacts and made the pilot seat look like a flat table. The current
    # canopy frame and PilotSeatV2 now own those silhouettes.


def create_subtle_surface_wear_pass(
    wear_mat: bpy.types.Material,
    polish_mat: bpy.types.Material,
    grime_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Add low-contrast wear cues that read as material use, not decoration."""
    for index, (x, z, sx, sz) in enumerate([
        (-0.28, -4.35, 0.24, 0.72),
        (0.32, -3.42, 0.18, 0.58),
        (-0.18, -2.35, 0.30, 0.64),
        (0.26, -1.20, 0.22, 0.54),
        (-0.34, 0.22, 0.24, 0.66),
        (0.30, 1.25, 0.20, 0.50),
        (-0.12, 2.22, 0.28, 0.46),
    ]):
        add_beveled_cube(
            f"SubtleWear_soft_floor_scuff_{index}",
            (x, 0.414, z),
            (sx, 0.010, sz),
            wear_mat,
            target,
            0.010,
        )
        add_beveled_cube(
            f"SubtleWear_thin_polished_traffic_edge_{index}",
            (-0.52 if index % 2 == 0 else 0.52, 0.418, z + 0.08),
            (0.038, 0.012, sz * 0.92),
            polish_mat,
            target,
            0.006,
        )

    for index, (x, z) in enumerate([(-0.48, 2.42), (0.52, -0.82), (-0.45, -4.42)]):
        add_beveled_cube(
            f"SubtleWear_warm_fixture_soot_halo_{index}",
            (x, 2.295, z + 0.17),
            (0.50, 0.012, 0.035),
            grime_mat,
            target,
            0.004,
        )
        add_beveled_cube(
            f"SubtleWear_fixture_lower_lip_polish_{index}",
            (x, 2.242, z - 0.16),
            (0.34, 0.014, 0.024),
            polish_mat,
            target,
            0.004,
        )


def create_closed_rear_loading_ramp(
    wall_mat: bpy.types.Material,
    trim_mat: bpy.types.Material,
    rubber_mat: bpy.types.Material,
    dark_panel_mat: bpy.types.Material,
    warning_mat: bpy.types.Material,
    bolt_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Create a C-130-like closed rear loading ramp for the aft hatch."""
    # This is deliberately authored as a distinct ramp/door assembly so a
    # future phase can replace it with an animated open/closed mechanism.
    ramp_z = 2.86
    ramp_face_z = ramp_z - 0.28
    ramp_back_z = ramp_z + 0.03
    slab_points = [
        (-1.24, 0.22, ramp_face_z),
        (1.24, 0.22, ramp_face_z),
        (1.00, 2.34, ramp_face_z),
        (-1.00, 2.34, ramp_face_z),
        (-1.24, 0.22, ramp_back_z),
        (1.24, 0.22, ramp_back_z),
        (1.00, 2.34, ramp_back_z),
        (-1.00, 2.34, ramp_back_z),
    ]
    slab_faces = [
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (3, 7, 4, 0),
    ]
    slab = create_box_from_godot_points("AftLoadingRamp_tapered_closed_pressure_slab", slab_points, slab_faces, wall_mat, target, 0.065)
    bevel = slab.modifiers.new("large ramp perimeter bevel", "BEVEL")
    bevel.width = 0.035
    bevel.segments = 4

    create_panel_patch(
        "AftLoadingRamp_inner_recessed_structural_skin",
        [(-0.92, 0.44, ramp_face_z - 0.018), (0.92, 0.44, ramp_face_z - 0.018), (0.78, 2.04, ramp_face_z - 0.018), (-0.78, 2.04, ramp_face_z - 0.018)],
        trim_mat,
        target,
        0.026,
    )
    create_panel_patch(
        "AftLoadingRamp_dark_recessed_access_panel",
        [(-0.56, 0.82, ramp_face_z - 0.048), (0.56, 0.82, ramp_face_z - 0.048), (0.48, 1.58, ramp_face_z - 0.048), (-0.48, 1.58, ramp_face_z - 0.048)],
        dark_panel_mat,
        target,
        0.018,
    )
    create_panel_patch(
        "AftLoadingRamp_upper_pressure_latch_panel",
        [(-0.54, 1.76, ramp_face_z - 0.050), (0.54, 1.76, ramp_face_z - 0.050), (0.46, 2.05, ramp_face_z - 0.050), (-0.46, 2.05, ramp_face_z - 0.050)],
        dark_panel_mat,
        target,
        0.016,
    )
    for index, (x0, x1, y0, y1) in enumerate([
        (-0.82, -0.08, 0.54, 1.04),
        (0.08, 0.82, 0.54, 1.04),
        (-0.70, -0.08, 1.32, 1.78),
        (0.08, 0.70, 1.32, 1.78),
    ]):
        create_panel_patch(
            f"AftLoadingRamp_pressed_skin_panel_{index}",
            [(x0, y0, ramp_face_z - 0.062), (x1, y0, ramp_face_z - 0.062), (x1 * 0.94, y1, ramp_face_z - 0.062), (x0 * 0.94, y1, ramp_face_z - 0.062)],
            wall_mat,
            target,
            0.012,
        )
    add_cylinder_between("AftLoadingRamp_left_tapered_gasket", (-1.08, 0.32, ramp_face_z - 0.055), (-0.90, 2.24, ramp_face_z - 0.055), 0.018, rubber_mat, target, 12)
    add_cylinder_between("AftLoadingRamp_right_tapered_gasket", (1.08, 0.32, ramp_face_z - 0.055), (0.90, 2.24, ramp_face_z - 0.055), 0.018, rubber_mat, target, 12)
    add_cylinder_between("AftLoadingRamp_top_tapered_gasket", (-0.86, 2.23, ramp_face_z - 0.055), (0.86, 2.23, ramp_face_z - 0.055), 0.018, rubber_mat, target, 12)
    add_cylinder_between("AftLoadingRamp_bottom_threshold_gasket", (-1.06, 0.33, ramp_face_z - 0.055), (1.06, 0.33, ramp_face_z - 0.055), 0.020, rubber_mat, target, 12)

    for x in [-0.52, 0.0, 0.52]:
        add_cylinder_between(f"AftLoadingRamp_recessed_vertical_panel_seam_{x:.1f}", (x, 0.54, ramp_face_z - 0.084), (x * 0.82, 1.92, ramp_face_z - 0.084), 0.006, rubber_mat, target, 8)
    for y, width in [(0.68, 1.62), (1.22, 1.42), (1.72, 1.18)]:
        add_cylinder_between(f"AftLoadingRamp_recessed_horizontal_panel_seam_{y:.1f}", (-width * 0.5, y, ramp_face_z - 0.086), (width * 0.5, y, ramp_face_z - 0.086), 0.006, rubber_mat, target, 8)

    for index, x in enumerate([-0.58, -0.18, 0.18, 0.58]):
        add_cylinder_between(
            f"AftLoadingRamp_floor_hinge_barrel_{index}",
            (x - 0.12, 0.24, ramp_face_z - 0.06),
            (x + 0.12, 0.24, ramp_face_z - 0.06),
            0.035,
            trim_mat,
            target,
            12,
        )
        add_beveled_cube(
            f"AftLoadingRamp_hinge_bolt_plate_{index}",
            (x, 0.36, ramp_face_z - 0.02),
            (0.22, 0.080, 0.040),
            bolt_mat,
            target,
            0.010,
        )
        add_beveled_cube(
            f"AftLoadingRamp_hinge_dark_recess_{index}",
            (x, 0.265, ramp_face_z - 0.085),
            (0.30, 0.045, 0.030),
            rubber_mat,
            target,
            0.006,
        )

    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        add_cylinder_between(
            f"AftLoadingRamp_hydraulic_body_{label}",
            (side * 1.04, 0.62, ramp_face_z - 0.07),
            (side * 0.86, 1.56, ramp_face_z - 0.07),
            0.022,
            dark_panel_mat,
            target,
            12,
        )
        add_cylinder_between(
            f"AftLoadingRamp_hydraulic_rod_{label}",
            (side * 0.86, 1.56, ramp_face_z - 0.09),
            (side * 0.76, 1.94, ramp_face_z - 0.09),
            0.012,
            bolt_mat,
            target,
            10,
        )
        add_beveled_cube(
            f"AftLoadingRamp_warning_edge_strip_{label}",
            (side * 0.66, 0.34, ramp_face_z - 0.08),
            (0.28, 0.052, 0.040),
            warning_mat,
            target,
            0.006,
        )
        add_beveled_cube(
            f"AftLoadingRamp_side_locking_lug_{label}_upper",
            (side * 0.86, 1.72, ramp_face_z - 0.06),
            (0.12, 0.18, 0.050),
            bolt_mat,
            target,
            0.010,
        )
        add_beveled_cube(
            f"AftLoadingRamp_side_locking_lug_{label}_lower",
            (side * 1.00, 0.74, ramp_face_z - 0.06),
            (0.12, 0.18, 0.050),
            bolt_mat,
            target,
            0.010,
        )
        add_beveled_cube(
            f"AftLoadingRamp_red_lock_indicator_{label}",
            (side * 0.80, 1.22, ramp_face_z - 0.10),
            (0.050, 0.18, 0.026),
            warning_mat,
            target,
            0.004,
        )

    add_beveled_cube("AftLoadingRamp_status_window_closed", (0.0, 2.02, ramp_face_z - 0.075), (0.34, 0.040, 0.032), warning_mat, target, 0.006)
    add_beveled_cube("AftLoadingRamp_warning_top_left", (-0.42, 2.08, ramp_face_z - 0.080), (0.26, 0.050, 0.038), warning_mat, target, 0.006)
    add_beveled_cube("AftLoadingRamp_warning_top_right", (0.42, 2.08, ramp_face_z - 0.080), (0.26, 0.050, 0.038), warning_mat, target, 0.006)
    add_beveled_cube("AftLoadingRamp_aft_floor_roller_left", (-0.40, 0.25, ramp_face_z - 0.10), (0.16, 0.040, 0.040), bolt_mat, target, 0.008)
    add_beveled_cube("AftLoadingRamp_aft_floor_roller_right", (0.40, 0.25, ramp_face_z - 0.10), (0.16, 0.040, 0.040), bolt_mat, target, 0.008)

    # Deep jamb and threshold parts make the ramp read as a heavy sealed
    # aircraft loading door instead of a flat panel pasted over an opening.
    add_beveled_cube("AftLoadingRamp_left_deep_receiver_jamb", (-1.22, 1.24, ramp_face_z - 0.02), (0.24, 2.04, 0.30), trim_mat, target, 0.045)
    add_beveled_cube("AftLoadingRamp_right_deep_receiver_jamb", (1.22, 1.24, ramp_face_z - 0.02), (0.24, 2.04, 0.30), trim_mat, target, 0.045)
    add_beveled_cube("AftLoadingRamp_overhead_pressure_header", (0.0, 2.34, ramp_face_z - 0.02), (2.34, 0.24, 0.30), trim_mat, target, 0.045)
    add_beveled_cube("AftLoadingRamp_floor_hinge_pressure_beam", (0.0, 0.23, ramp_face_z - 0.035), (2.52, 0.22, 0.34), trim_mat, target, 0.040)
    add_beveled_cube("AftLoadingRamp_threshold_black_shadow_gap", (0.0, 0.42, ramp_face_z - 0.125), (2.06, 0.060, 0.070), rubber_mat, target, 0.010)
    add_beveled_cube("AftLoadingRamp_top_black_shadow_gap", (0.0, 2.17, ramp_face_z - 0.125), (1.82, 0.052, 0.070), rubber_mat, target, 0.010)

    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        create_panel_patch(
            f"AftLoadingRamp_sloped_inner_jamb_face_{label}",
            [
                (side * 1.06, 0.42, ramp_face_z - 0.18),
                (side * 1.22, 0.26, ramp_face_z - 0.02),
                (side * 1.16, 2.28, ramp_face_z - 0.02),
                (side * 0.94, 2.08, ramp_face_z - 0.18),
            ],
            wall_mat,
            target,
            0.035,
        )
        add_beveled_cube(
            f"AftLoadingRamp_lower_side_lock_receiver_{label}",
            (side * 1.10, 0.78, ramp_face_z - 0.205),
            (0.16, 0.22, 0.10),
            dark_panel_mat,
            target,
            0.020,
        )
        add_beveled_cube(
            f"AftLoadingRamp_upper_side_lock_receiver_{label}",
            (side * 0.94, 1.74, ramp_face_z - 0.205),
            (0.16, 0.22, 0.10),
            dark_panel_mat,
            target,
            0.020,
        )
        add_cylinder_between(
            f"AftLoadingRamp_side_jamb_weld_bead_{label}",
            (side * 1.18, 0.36, ramp_face_z - 0.19),
            (side * 0.98, 2.22, ramp_face_z - 0.19),
            0.010,
            bolt_mat,
            target,
            8,
        )

    create_panel_patch(
        "AftLoadingRamp_overhead_sloped_header_face",
        [(-1.04, 2.10, ramp_face_z - 0.18), (1.04, 2.10, ramp_face_z - 0.18), (1.22, 2.36, ramp_face_z - 0.02), (-1.22, 2.36, ramp_face_z - 0.02)],
        wall_mat,
        target,
        0.035,
    )
    create_panel_patch(
        "AftLoadingRamp_lower_folded_ramp_lip",
        [(-1.12, 0.34, ramp_face_z - 0.18), (1.12, 0.34, ramp_face_z - 0.18), (1.26, 0.18, ramp_face_z - 0.02), (-1.26, 0.18, ramp_face_z - 0.02)],
        trim_mat,
        target,
        0.030,
    )
    for index, x in enumerate([-0.88, -0.44, 0.0, 0.44, 0.88]):
        add_beveled_cube(
            f"AftLoadingRamp_threshold_bolt_plate_{index}",
            (x, 0.42, ramp_face_z - 0.19),
            (0.17, 0.055, 0.044),
            bolt_mat,
            target,
            0.008,
        )

    create_panel_patch(
        "AftLoadingRamp_surround_left_bulkhead_fairing",
        [(-1.36, 0.22, ramp_z + 0.02), (-1.10, 0.34, ramp_z - 0.12), (-1.10, 2.22, ramp_z - 0.12), (-1.30, 2.42, ramp_z + 0.02)],
        trim_mat,
        target,
        0.030,
    )
    create_panel_patch(
        "AftLoadingRamp_surround_right_bulkhead_fairing",
        [(1.10, 0.34, ramp_z - 0.12), (1.36, 0.22, ramp_z + 0.02), (1.30, 2.42, ramp_z + 0.02), (1.10, 2.22, ramp_z - 0.12)],
        trim_mat,
        target,
        0.030,
    )
    create_panel_patch(
        "AftLoadingRamp_surround_overhead_fairing",
        [(-1.10, 2.12, ramp_z - 0.12), (1.10, 2.12, ramp_z - 0.12), (1.28, 2.46, ramp_z + 0.02), (-1.28, 2.46, ramp_z + 0.02)],
        trim_mat,
        target,
        0.030,
    )


def create_reclined_seat_shell(
    name: str,
    mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> bpy.types.Object:
    sections = [
        (-8.72, [(-0.44, 1.40), (0.44, 1.40), (0.38, 1.60), (-0.38, 1.60)]),
        (-8.34, [(-0.46, 1.45), (0.46, 1.45), (0.40, 1.68), (-0.40, 1.68)]),
        (-8.02, [(-0.34, 1.66), (0.34, 1.66), (0.28, 1.88), (-0.28, 1.88)]),
        (-7.88, [(-0.20, 1.84), (0.20, 1.84), (0.15, 1.96), (-0.15, 1.96)]),
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
    create_tapered_prism("PilotSeat_thin_base_cushion", (0.0, 1.58, -8.42), (0.70, 0.13, 0.58), (0.58, 0.10, 0.46), mat, target, 0.050)
    back = create_tapered_prism("PilotSeat_segmented_back_cushion_lower", (0.0, 1.77, -8.02), (0.50, 0.22, 0.10), (0.38, 0.17, 0.08), mat, target, 0.040)
    back.rotation_euler[0] = math.radians(-10.0)
    upper = create_tapered_prism("PilotSeat_segmented_back_cushion_upper", (0.0, 1.92, -7.92), (0.32, 0.11, 0.075), (0.23, 0.08, 0.055), mat, target, 0.030)
    upper.rotation_euler[0] = math.radians(-10.0)
    add_beveled_cube("PilotSeat_cushion_center_seam", (0.0, 1.78, -7.875), (0.026, 0.30, 0.016), dark_mat, target, 0.005)
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        add_beveled_cube(f"PilotSeat_side_crash_bolster_{label}", (side * 0.32, 1.75, -7.98), (0.075, 0.25, 0.10), dark_mat, target, 0.026)


def create_reference_pilot_seat_v2(
    seat_mat: bpy.types.Material,
    shell_mat: bpy.types.Material,
    trim_mat: bpy.types.Material,
    rubber_mat: bpy.types.Material,
    bolt_mat: bpy.types.Material,
    target: bpy.types.Collection,
) -> None:
    """Reference-inspired compact pilot seat with a fresh silhouette."""
    # Low pedestal and track assembly: visible hardware, but not tall enough to
    # block the forward canopy view from the walkthrough path.
    add_beveled_cube("PilotSeatV2_floor_track_left", (-0.24, 1.315, -8.38), (0.065, 0.055, 0.96), trim_mat, target, 0.014)
    add_beveled_cube("PilotSeatV2_floor_track_right", (0.24, 1.315, -8.38), (0.065, 0.055, 0.96), trim_mat, target, 0.014)
    add_beveled_cube("PilotSeatV2_low_pedestal_core", (0.0, 1.405, -8.34), (0.38, 0.16, 0.42), shell_mat, target, 0.030)
    add_beveled_cube("PilotSeatV2_swivel_plate", (0.0, 1.505, -8.34), (0.58, 0.060, 0.56), trim_mat, target, 0.026)

    seat_pan = create_tapered_prism("PilotSeatV2_bucket_seat_pan", (0.0, 1.585, -8.46), (0.74, 0.12, 0.62), (0.60, 0.10, 0.48), seat_mat, target, 0.050)
    seat_pan.rotation_euler[0] = math.radians(-3.0)
    add_beveled_cube("PilotSeatV2_front_cushion_lip", (0.0, 1.625, -8.77), (0.62, 0.070, 0.070), seat_mat, target, 0.020)
    add_beveled_cube("PilotSeatV2_center_cushion_recess", (0.0, 1.655, -8.46), (0.030, 0.030, 0.48), rubber_mat, target, 0.006)

    back_sections = [
        (-8.20, [(-0.36, 1.58), (0.36, 1.58), (0.32, 1.78), (-0.32, 1.78)]),
        (-8.02, [(-0.39, 1.64), (0.39, 1.64), (0.32, 1.96), (-0.32, 1.96)]),
        (-7.88, [(-0.34, 1.80), (0.34, 1.80), (0.27, 2.08), (-0.27, 2.08)]),
        (-7.80, [(-0.24, 1.98), (0.24, 1.98), (0.18, 2.12), (-0.18, 2.12)]),
    ]
    back = create_loft_mesh("PilotSeatV2_single_piece_reclined_back_shell", back_sections, shell_mat, target)
    bevel = back.modifiers.new("seat v2 shell bevel", "BEVEL")
    bevel.width = 0.040
    bevel.segments = 4

    lower_pad = create_tapered_prism("PilotSeatV2_lower_back_fabric_pad", (0.0, 1.78, -8.00), (0.48, 0.12, 0.075), (0.38, 0.09, 0.055), seat_mat, target, 0.030)
    lower_pad.rotation_euler[0] = math.radians(-12.0)
    upper_pad = create_tapered_prism("PilotSeatV2_upper_shoulder_pad", (0.0, 1.95, -7.89), (0.24, 0.075, 0.052), (0.18, 0.055, 0.038), seat_mat, target, 0.018)
    upper_pad.rotation_euler[0] = math.radians(-12.0)
    # Avoid a headrest block here. From the cockpit walkthrough it read as a
    # flat object sitting on the chair and obstructed the canopy view.

    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        add_beveled_cube(f"PilotSeatV2_side_bucket_bolster_{label}", (side * 0.35, 1.66, -8.32), (0.085, 0.26, 0.42), shell_mat, target, 0.030)
        add_beveled_cube(f"PilotSeatV2_shoulder_side_frame_{label}", (side * 0.28, 1.86, -7.93), (0.052, 0.32, 0.052), shell_mat, target, 0.018)
        add_cylinder_between(f"PilotSeatV2_rear_tubular_support_{label}", (side * 0.34, 1.42, -8.02), (side * 0.28, 1.92, -7.84), 0.020, trim_mat, target, 10)
        add_beveled_cube(f"PilotSeatV2_low_arm_pad_{label}", (side * 0.43, 1.62, -8.42), (0.10, 0.045, 0.36), rubber_mat, target, 0.020)
        add_beveled_cube(f"PilotSeatV2_harness_slot_{label}", (side * 0.15, 1.96, -7.82), (0.045, 0.018, 0.036), rubber_mat, target, 0.006)
        add_beveled_cube(f"PilotSeatV2_track_bolt_front_{label}", (side * 0.24, 1.355, -8.78), (0.045, 0.020, 0.045), bolt_mat, target, 0.006)
        add_beveled_cube(f"PilotSeatV2_track_bolt_rear_{label}", (side * 0.24, 1.355, -7.98), (0.045, 0.020, 0.045), bolt_mat, target, 0.006)


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
        "InteriorSpawn": (0.0, 1.12, 2.35),
        "ExteriorExit": (0.0, 1.18, 5.42),
        "SeatAnchor": (0.0, 2.04, -8.55),
        "SeatExit": (0.0, 1.82, -7.42),
        "PilotEye": (0.0, 2.18, -8.92),
        "CanopyTarget": (0.0, 2.75, -8.72),
        "HatchCenter": (0.0, 1.30, 4.35),
        "RampStart": (0.0, 1.12, 4.20),
        "RampEnd": (0.0, 0.52, 5.70),
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
    collection("Lights")
    collection("Review_Cameras")
    collection("ScaleProxies")
    collection("Disabled_Source")

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
    glass_mat = material("SG_canopy_glass", (0.070, 0.095, 0.105, 0.030), 0.018, 0.0)
    canopy_fog_mat = material("SG_canopy_soft_fogging", (0.58, 0.72, 0.74, 0.08), 0.70, 0.0)
    canopy_reflection_mat = emissive_material("SG_canopy_cool_reflection_catch", (0.42, 0.64, 0.68, 0.42), 0.10)
    seat_mat = material("SG_seat_deep_black_fabric", (0.030, 0.034, 0.036, 1.0), 0.82, 0.0)
    seat_shell_mat = material("SG_seat_molded_dark_shell", (0.028, 0.033, 0.036, 1.0), 0.70, 0.08)
    screen_mat = emissive_material("SG_screen_soft_teal", (0.018, 0.070, 0.075, 1.0), 0.20)
    lounge_bright_mat = material("SG_solo_falcon_soft_white_composite", (0.78, 0.79, 0.74, 1.0), 0.48, 0.0)
    lounge_luminous_mat = emissive_material("SG_solo_falcon_soft_white_practical", (0.86, 0.90, 0.86, 1.0), 0.66)
    lounge_warm_luminous_mat = emissive_material("SG_solo_falcon_warm_indicator", (1.0, 0.58, 0.22, 1.0), 0.95)
    lounge_gloss_mat = material("SG_solo_falcon_gloss_black_floor", (0.015, 0.017, 0.018, 1.0), 0.18, 0.34)
    wear_mat = material("SG_subtle_worn_composite", (0.072, 0.080, 0.078, 1.0), 0.94, 0.0)
    polish_mat = material("SG_subtle_polished_edge", (0.235, 0.245, 0.230, 1.0), 0.44, 0.18)
    grime_mat = material("SG_subtle_warm_grime", (0.105, 0.085, 0.058, 1.0), 0.88, 0.0)

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
    ceiling_liner_sections = [
        (-5.68, [(-1.06, 1.02), (-0.70, 2.52), (0.0, 2.92), (0.70, 2.52), (1.06, 1.02)]),
        (-3.65, [(-1.46, 0.92), (-0.92, 2.18), (0.0, 2.48), (0.92, 2.18), (1.46, 0.92)]),
        (-1.40, [(-1.92, 0.86), (-1.18, 2.22), (0.0, 2.54), (1.18, 2.22), (1.92, 0.86)]),
        (0.85, [(-2.04, 0.86), (-1.24, 2.18), (0.0, 2.50), (1.24, 2.18), (2.04, 0.86)]),
        (3.20, [(-1.52, 0.98), (-0.96, 1.95), (0.0, 2.25), (0.96, 1.95), (1.52, 0.98)]),
    ]
    ceiling_liner = create_loft_mesh("Cabin_enclosure_continuous_ceiling_liner", ceiling_liner_sections, wall_mat, interior)
    bevel = ceiling_liner.modifiers.new("enclosure ceiling soft bevel", "BEVEL")
    bevel.width = 0.012
    bevel.segments = 2

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
    add_beveled_cube("Floor_enclosure_unbroken_pressure_pan", (0.0, 0.145, -1.18), (3.18, 0.040, 8.72), floor_mat, interior, 0.025)
    add_beveled_cube("Floor_enclosure_forward_transition_pan", (0.0, 0.35, -5.45), (1.30, 0.050, 0.72), floor_mat, interior, 0.020)
    add_beveled_cube("Floor_enclosure_rear_threshold_pan", (0.0, 0.25, 3.22), (1.54, 0.050, 0.64), floor_mat, interior, 0.020)
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
    for side in [-1.0, 1.0]:
        label = "L" if side < 0 else "R"
        lower_wall_sections = []
        for z, inner_x, outer_x, lower_y, upper_y in [
            (-5.45, 1.06, 1.32, 0.34, 1.08),
            (-3.55, 1.22, 1.50, 0.30, 1.20),
            (-1.30, 1.48, 1.82, 0.26, 1.24),
            (0.92, 1.62, 1.96, 0.26, 1.20),
            (3.10, 1.22, 1.52, 0.34, 1.04),
        ]:
            lower_wall_sections.append((z, [
                (side * inner_x, lower_y),
                (side * outer_x, lower_y + 0.05),
                (side * outer_x, upper_y),
                (side * inner_x, upper_y - 0.08),
            ]))
        lower_wall = create_loft_mesh(f"Cabin_enclosure_lower_wall_continuous_{label}", lower_wall_sections, wall_mat, interior)
        bevel = lower_wall.modifiers.new("enclosure lower wall bevel", "BEVEL")
        bevel.width = 0.014
        bevel.segments = 2
        add_beveled_cube(
            f"Cabin_enclosure_floor_wall_cove_{label}",
            (side * 1.18, 0.36, -1.15),
            (0.090, 0.115, 8.50),
            trim_mat,
            interior,
            0.028,
        )
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
        add_cylinder_between(f"Side_upper_dark_service_rail_{label}", (side * 1.42, 1.78, -4.80), (side * 1.72, 1.60, 3.10), 0.010, trim_mat, interior, 8)
        for light_index, z in enumerate([-4.10, -1.30, 1.70]):
            add_beveled_cube(
                f"Side_upper_segmented_cool_indicator_{label}_{light_index}",
                (side * 1.49, 1.745, z),
                (0.020, 0.040, 0.16),
                screen_mat,
                interior,
                0.004,
            )
        add_cylinder_between(f"Side_floor_pressure_rail_{label}", (side * 1.10, 0.42, -5.00), (side * 1.62, 0.38, 3.25), 0.020, trim_mat, interior, 10)
        add_cylinder_between(f"Side_mid_structural_rail_{label}", (side * 1.24, 1.22, -4.80), (side * 1.62, 1.12, 3.15), 0.018, trim_mat, interior, 10)

    create_cockpit_tub("Cockpit_measured_pilot_tub", wall_mat, floor_mat, trim_mat, dark_panel_mat, screen_mat, interior)
    create_curved_instrument_panel("Cockpit_measured_instrument_panel", trim_mat, dark_panel_mat, rubber_mat, screen_mat, interior)
    create_cockpit_lighting_sprint_pass(trim_mat, dark_panel_mat, rubber_mat, screen_mat, warning_mat, interior)
    create_cockpit_access_architecture(floor_mat, wall_mat, trim_mat, rubber_mat, screen_mat, interior)
    create_forward_enclosure_infill(wall_mat, floor_mat, trim_mat, rubber_mat, screen_mat, interior)
    create_aft_enclosure_closeout(wall_mat, floor_mat, trim_mat, rubber_mat, screen_mat, dark_panel_mat, bolt_mat, interior)
    create_overhead_enclosure_blockers(wall_mat, trim_mat, rubber_mat, screen_mat, interior)
    create_enclosure_completion_skin(wall_mat, floor_mat, trim_mat, rubber_mat, dark_panel_mat, screen_mat, interior)
    create_nose_tail_enclosure_finish(wall_mat, floor_mat, trim_mat, rubber_mat, dark_panel_mat, screen_mat, interior)
    create_visible_canopy_and_tail_seals(glass_mat, wall_mat, trim_mat, rubber_mat, dark_panel_mat, screen_mat, interior)
    create_canopy_glass_readability_pass(canopy_fog_mat, canopy_reflection_mat, rubber_mat, interior)
    create_cockpit_viewport_cleanup_pass(trim_mat, rubber_mat, dark_panel_mat, lounge_warm_luminous_mat, interior)
    create_cockpit_reference_detail_pass(trim_mat, rubber_mat, dark_panel_mat, bolt_mat, lounge_warm_luminous_mat, interior)
    create_interior_enclosure_polish_pass(wall_mat, floor_mat, trim_mat, rubber_mat, dark_panel_mat, screen_mat, interior)
    create_material_depth_detail_pass(trim_mat, rubber_mat, dark_panel_mat, screen_mat, warning_mat, bolt_mat, interior)
    create_reference_guided_light_and_panel_pass(
        wall_mat,
        floor_mat,
        trim_mat,
        rubber_mat,
        dark_panel_mat,
        screen_mat,
        warning_mat,
        bolt_mat,
        interior,
    )
    create_lighting_sprint_practical_path_pass(
        floor_mat,
        trim_mat,
        rubber_mat,
        dark_panel_mat,
        screen_mat,
        warning_mat,
        interior,
    )
    create_solo_falcon_reference_brightness_pass(
        lounge_bright_mat,
        lounge_luminous_mat,
        lounge_warm_luminous_mat,
        lounge_gloss_mat,
        trim_mat,
        dark_panel_mat,
        warning_mat,
        interior,
    )
    create_subtle_surface_wear_pass(wear_mat, polish_mat, grime_mat, interior)
    create_closed_rear_loading_ramp(wall_mat, trim_mat, rubber_mat, dark_panel_mat, warning_mat, bolt_mat, interior)
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
            (side * 1.10, 1.70, -5.54),
            0.022,
            rubber_mat,
            interior,
            12,
        )
    create_molded_cockpit_detail_layer(wall_mat, trim_mat, dark_panel_mat, rubber_mat, screen_mat, bolt_mat, interior)
    add_beveled_cube("Canopy_low_inner_sill", (0.0, 1.44, -9.30), (1.42, 0.060, 0.15), trim_mat, interior, 0.024)
    add_beveled_cube("Canopy_black_inner_gasket", (0.0, 1.54, -9.70), (1.28, 0.034, 0.10), rubber_mat, interior, 0.016)
    # The viewport cleanup pass owns the primary windshield bows. Avoid extra
    # lower sill tubes in the cockpit because they crowd the transparent canopy.

    create_reference_pilot_seat_v2(seat_mat, seat_shell_mat, trim_mat, rubber_mat, bolt_mat, interior)

    add_beveled_cube("Collision_walkable_floor", (0.0, 0.22, -3.20), (3.20, 0.26, 13.60), trim_mat, collision, 0.0)
    add_beveled_cube("Collision_cockpit_access_platform", (0.0, 0.96, -7.45), (1.58, 0.32, 3.36), trim_mat, collision, 0.0)
    add_beveled_cube("Collision_chair_clearance", (0.0, 1.58, -8.35), (1.18, 0.86, 1.06), trim_mat, collision, 0.0)

    create_markers(markers)


def main() -> None:
    SOURCE_BLEND.parent.mkdir(parents=True, exist_ok=True)
    clear_scene()
    create_initial_interior()
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE_BLEND))
    print(f"Wrote {SOURCE_BLEND}")


if __name__ == "__main__":
    main()
