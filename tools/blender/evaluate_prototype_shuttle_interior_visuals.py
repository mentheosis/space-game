#!/usr/bin/env python3
"""Evaluate prototype shuttle interior visual coherence from the Blender source."""

from __future__ import annotations

import json
import math
import os
import struct
import zlib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector


ROOT = Path(os.environ.get("SPACE_GAME_ROOT", Path.cwd())).resolve()
SOURCE_BLEND = ROOT / "assets/source/blender/ships/prototype_shuttle/prototype_shuttle.blend"
LIGHT_REPORT = ROOT / "assets/models/ship/prototype_shuttle/prototype_shuttle_light_report.json"
MATERIAL_WALKTHROUGH_MANIFEST = ROOT / "reports/prototype_shuttle_material_walkthrough/manifest.json"
OUT_DIR = ROOT / "reports/prototype_shuttle_visual_eval"
REPORT_JSON = OUT_DIR / "interior_visual_eval_report.json"
REPORT_MD = OUT_DIR / "interior_visual_eval_report.md"
CONTACT_SHEET = OUT_DIR / "interior_visual_eval_contact_sheet_current.png"
ATTACHMENT_OVERLAY = OUT_DIR / "attachment_debug_overlay_current.png"
MATERIAL_SHEET = OUT_DIR / "material_id_contact_sheet_current.png"
REGION_ORBIT_SHEET = OUT_DIR / "interior_region_orbit_contact_sheet_current.png"


ROLE_KEYWORDS = [
    ("walkable_surface", ["floor", "deck", "walk", "landing", "step", "ramp_mainsoliddeck", "warmwalkpanel"]),
    ("wall_panel", ["wall", "sidepocket", "liner", "panel", "jamb", "lintel", "frame"]),
    ("ceiling_panel", ["ceiling", "overhead"]),
    ("structural_rib", ["rib", "brace", "stringer", "post", "truss", "cap"]),
    ("rail_or_handle", ["rail", "handle", "grab"]),
    ("light_fixture", ["light", "diffuser", "beacon", "glow", "source", "marker"]),
    ("emissive_lens", ["amber", "cyan", "warm_light", "cool_light", "displayglow", "indicator"]),
    ("display_or_control", ["display", "mfd", "console", "button", "control", "grip", "instrument", "switch", "computer", "screen", "nav", "statusmodule", "keybank", "dataplate"]),
    ("seat_component", ["seat", "harness", "belt", "headrest", "bolster", "armrest", "fabric"]),
    ("mechanical_component", ["hinge", "hydraulic", "conduit", "cable", "latch", "clamp", "utility", "equipment"]),
    ("cargo_fixture", ["cargo", "tiedown", "rack", "storage"]),
    ("trim_or_gasket", ["trim", "gasket", "seal", "threshold", "edge", "toe", "bumper", "rail", "scuff", "shadow", "slot", "underbite"]),
]

MATERIAL_FAMILY_RULES = [
    ("emissive", ["light", "emissive", "amber", "cyan", "glow"]),
    ("rubber_gasket", ["rubber", "gasket", "seal"]),
    ("dark_structural", ["dark_trim", "sooty", "dark_inset", "graphite"]),
    ("brushed_metal", ["burnished", "scratched", "metal"]),
    ("worn_floor", ["worn", "walk_path", "floor_plate", "floor"]),
    ("light_panel", ["pale", "wall_panel", "insulated", "warm_wall"]),
    ("glass", ["glass", "canopy"]),
    ("seat_fabric", ["seat_fabric", "stitching", "fabric"]),
    ("hazard_label", ["hazard", "stenciled", "label", "warning"]),
    ("service_panel", ["blue_accent", "service_green", "green", "accent_panel"]),
    ("blockout_volume", ["volume", "blockout"]),
]

DETAIL_ROLES = {
    "trim_or_gasket",
    "rail_or_handle",
    "light_fixture",
    "emissive_lens",
    "display_or_control",
    "seat_component",
    "mechanical_component",
    "cargo_fixture",
    "structural_rib",
}

PARENT_ROLES = {
    "walkable_surface",
    "wall_panel",
    "ceiling_panel",
    "structural_rib",
    "trim_or_gasket",
    "mechanical_component",
    "display_or_control",
    "seat_component",
    "light_fixture",
    "cargo_fixture",
}


def descendants(source: bpy.types.Collection) -> list[bpy.types.Object]:
    objects = list(source.objects)
    for child in source.children:
        objects.extend(descendants(child))
    return objects


def blender_to_godot(vec: Vector) -> list[float]:
    return [round(float(vec.x), 5), round(float(vec.z), 5), round(float(-vec.y), 5)]


def object_bounds(obj: bpy.types.Object) -> tuple[Vector, Vector] | None:
    if obj.type != "MESH":
        return None
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    mins = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    maxs = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    return mins, maxs


def bbox_center(bounds: tuple[Vector, Vector]) -> Vector:
    return (bounds[0] + bounds[1]) * 0.5


def bbox_size(bounds: tuple[Vector, Vector]) -> Vector:
    return bounds[1] - bounds[0]


def bbox_distance(a: tuple[Vector, Vector], b: tuple[Vector, Vector]) -> float:
    total = 0.0
    for axis in range(3):
        if a[1][axis] < b[0][axis]:
            delta = b[0][axis] - a[1][axis]
        elif b[1][axis] < a[0][axis]:
            delta = a[0][axis] - b[1][axis]
        else:
            delta = 0.0
        total += delta * delta
    return math.sqrt(total)


def bbox_volume(bounds: tuple[Vector, Vector]) -> float:
    size = bbox_size(bounds)
    return max(0.000001, float(size.x * size.y * size.z))


def classify_role(name: str, materials: list[str]) -> str:
    text = f"{name} {' '.join(materials)}".lower()
    if name.startswith("VOLUME_"):
        return "review_volume"
    if "reference" in text or "blockout" in text and "exact" in text:
        return "review_volume"
    for role, keywords in ROLE_KEYWORDS:
        if any(keyword.lower() in text for keyword in keywords):
            return role
    return "decorative_or_unknown"


def material_family(material: str) -> str:
    text = material.lower()
    for family, keywords in MATERIAL_FAMILY_RULES:
        if any(keyword in text for keyword in keywords):
            return family
    return "unknown"


def region_for_object(name: str, center_godot: list[float]) -> str:
    lower = name.lower()
    x, y, z = center_godot
    if "ramp" in lower or "hatch" in lower or "door" in lower:
        return "ramp_entry"
    if "ascent" in lower or "stair" in lower or "landing" in lower:
        return "stairs_landing"
    if "cockpit" in lower or z < -4.8:
        return "cockpit"
    if "cargo" in lower or z > 0.4:
        return "cargo_bay"
    return "transition"


def object_record(obj: bpy.types.Object) -> dict[str, Any] | None:
    bounds = object_bounds(obj)
    if bounds is None:
        return None
    materials = [slot.material.name if slot.material is not None else "<empty>" for slot in obj.material_slots]
    center = bbox_center(bounds)
    size = bbox_size(bounds)
    center_godot = blender_to_godot(center)
    return {
        "name": obj.name,
        "materials": materials,
        "material_families": sorted({material_family(material) for material in materials}),
        "role": classify_role(obj.name, materials),
        "region": region_for_object(obj.name, center_godot),
        "center_blender": [round(float(center.x), 5), round(float(center.y), 5), round(float(center.z), 5)],
        "center_godot": center_godot,
        "size_blender": [round(float(size.x), 5), round(float(size.y), 5), round(float(size.z), 5)],
        "volume": round(bbox_volume(bounds), 6),
        "_bounds": bounds,
    }


def load_source() -> None:
    if not SOURCE_BLEND.exists():
        raise RuntimeError(f"Missing source blend: {SOURCE_BLEND}")
    if Path(bpy.data.filepath).resolve() != SOURCE_BLEND:
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE_BLEND))


def nearest_parent(record: dict[str, Any], candidates: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float]:
    best = None
    best_distance = 999999.0
    for candidate in candidates:
        if candidate["name"] == record["name"]:
            continue
        distance = bbox_distance(record["_bounds"], candidate["_bounds"])
        if distance < best_distance:
            best = candidate
            best_distance = distance
    return best, best_distance


def attachment_checks(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    parents = [
        record
        for record in records
        if record["role"] in PARENT_ROLES and record["volume"] >= 0.002 and record["role"] != "review_volume"
    ]
    details = [
        record
        for record in records
        if record["role"] in DETAIL_ROLES and record["role"] != "review_volume"
    ]

    for record in details:
        parent, distance = nearest_parent(record, parents)
        threshold_fail = 0.08
        threshold_warn = 0.03
        if record["role"] in {"light_fixture", "emissive_lens", "display_or_control"}:
            threshold_fail = 0.20
            threshold_warn = 0.08
        if any(token in record["name"].lower() for token in ["bolt", "fastener"]):
            threshold_fail = max(threshold_fail, 0.26)
            threshold_warn = max(threshold_warn, 0.12)
        if parent is None:
            issues.append({
                "severity": "FAIL",
                "kind": "attachment",
                "object": record["name"],
                "role": record["role"],
                "reason": "No plausible parent surface or support was found.",
            })
            continue
        if distance > threshold_fail:
            severity = "FAIL"
        elif distance > threshold_warn:
            severity = "WARN"
        else:
            continue
        issues.append({
            "severity": severity,
            "kind": "attachment",
            "object": record["name"],
            "role": record["role"],
            "nearest_parent": parent["name"],
            "nearest_parent_role": parent["role"],
            "distance_m": round(distance, 4),
            "reason": f"Detail is {distance:.3f}m from nearest plausible support.",
        })
    return issues


def classification_checks(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues = []
    ignored_prefixes = ("VOLUME_", "ScaleBlockout", "ReferenceStrip")
    for record in records:
        if record["name"].startswith(ignored_prefixes):
            continue
        if record["role"] == "decorative_or_unknown":
            volume = float(record["volume"])
            severity = "FAIL" if volume > 0.01 else "WARN"
            issues.append({
                "severity": severity,
                "kind": "classification",
                "object": record["name"],
                "role": record["role"],
                "volume": volume,
                "reason": "Visible object has no classified design role from name/materials.",
            })
    return issues


def material_checks(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    issues = []
    by_region: dict[str, Counter[str]] = defaultdict(Counter)
    volume_by_region: dict[str, Counter[str]] = defaultdict(Counter)
    unknown = []
    for record in records:
        if record["role"] == "review_volume":
            continue
        family = record["material_families"][0] if record["material_families"] else "unknown"
        if len(record["material_families"]) > 1 and "unknown" in record["material_families"]:
            families = [item for item in record["material_families"] if item != "unknown"]
            family = families[0] if families else "unknown"
        by_region[record["region"]][family] += 1
        volume_by_region[record["region"]][family] += float(record["volume"])
        if family == "unknown":
            unknown.append(record["name"])

    for region, counts in by_region.items():
        total = sum(counts.values())
        if total <= 0:
            continue
        dominant, count = counts.most_common(1)[0]
        dominance = count / total
        if dominance > 0.42 and total >= 20:
            issues.append({
                "severity": "WARN",
                "kind": "material_family",
                "region": region,
                "dominant_family": dominant,
                "dominance": round(dominance, 3),
                "reason": "Region may read as visually one-note by object count.",
            })
    for name in unknown[:30]:
        issues.append({
            "severity": "WARN",
            "kind": "material_family",
            "object": name,
            "reason": "Object uses an unknown material family.",
        })

    summary = {
        "object_counts_by_region": {region: dict(counter) for region, counter in sorted(by_region.items())},
        "volume_by_region": {
            region: {family: round(float(value), 5) for family, value in counter.items()}
            for region, counter in sorted(volume_by_region.items())
        },
        "unknown_material_object_count": len(unknown),
    }
    return issues, summary


def light_checks(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues = []
    fixtures = [
        record for record in records
        if record["role"] in {"light_fixture", "emissive_lens"} or "emissive" in record["material_families"]
    ]
    actual_lights = []
    if LIGHT_REPORT.exists():
        actual_lights = json.loads(LIGHT_REPORT.read_text(encoding="utf-8")).get("lights", [])
    if len(actual_lights) < max(1, len(fixtures) // 25):
        issues.append({
            "severity": "WARN",
            "kind": "lighting",
            "actual_light_count": len(actual_lights),
            "visible_fixture_count": len(fixtures),
            "reason": "Many visible emissive fixtures are not represented by actual exported production lights.",
        })
    bad_cockpit_mount_tokens = ["seat", "canopy", "overhead"]
    for fixture in fixtures:
        name = fixture["name"].lower()
        if fixture["region"] != "cockpit":
            continue
        if any(token in name for token in bad_cockpit_mount_tokens):
            issues.append({
                "severity": "FAIL",
                "kind": "lighting",
                "object": fixture["name"],
                "reason": "Cockpit light fixtures must mount to dashboard, console, side-panel, or bulkhead metal surfaces, not seats, canopy, or overhead canopy structure.",
            })
    for light in actual_lights:
        pos = Vector((float(light["position"][0]), float(light["position"][1]), float(light["position"][2])))
        best = None
        best_dist = 999999.0
        for fixture in fixtures:
            center = Vector(fixture["center_godot"])
            distance = float((center - pos).length)
            if distance < best_dist:
                best = fixture
                best_dist = distance
        if best is None or best_dist > 0.75:
            issues.append({
                "severity": "FAIL",
                "kind": "lighting",
                "light": light.get("id", "<unknown>"),
                "distance_m": round(best_dist, 3),
                "nearest_fixture": None if best is None else best["name"],
                "reason": "Actual light has no visible fixture within 0.75m.",
            })
        elif best_dist > 0.30:
            issues.append({
                "severity": "WARN",
                "kind": "lighting",
                "light": light.get("id", "<unknown>"),
                "distance_m": round(best_dist, 3),
                "nearest_fixture": best["name"],
                "reason": "Actual light is not tightly colocated with visible fixture.",
            })
    return issues


def evidence_checks() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    issues = []
    summary: dict[str, Any] = {}
    if not MATERIAL_WALKTHROUGH_MANIFEST.exists():
        return ([{
            "severity": "WARN",
            "kind": "evidence",
            "reason": "Material walkthrough manifest is missing.",
        }], summary)
    manifest = json.loads(MATERIAL_WALKTHROUGH_MANIFEST.read_text(encoding="utf-8"))
    frames_dir = MATERIAL_WALKTHROUGH_MANIFEST.parent / str(manifest["frames_directory"])
    frames = sorted(frames_dir.glob("frame_*.rgb"))
    width = int(manifest["width"])
    height = int(manifest["height"])
    samples = sorted(set(max(0, min(len(frames) - 1, round((len(frames) - 1) * t))) for t in [0.08, 0.18, 0.32, 0.46, 0.62, 0.78, 0.90]))
    dark_fractions = []
    bright_fractions = []
    for index in samples:
        data = frames[index].read_bytes()
        pixels = len(data) // 3
        dark = 0
        bright = 0
        for offset in range(0, len(data), 3):
            lum = 0.2126 * data[offset] + 0.7152 * data[offset + 1] + 0.0722 * data[offset + 2]
            if lum < 22:
                dark += 1
            if lum > 230:
                bright += 1
        dark_fractions.append(dark / pixels)
        bright_fractions.append(bright / pixels)
    avg_dark = sum(dark_fractions) / max(1, len(dark_fractions))
    max_dark = max(dark_fractions) if dark_fractions else 0.0
    avg_bright = sum(bright_fractions) / max(1, len(bright_fractions))
    summary = {
        "sample_count": len(samples),
        "average_dark_fraction": round(avg_dark, 3),
        "max_dark_fraction": round(max_dark, 3),
        "average_bright_fraction": round(avg_bright, 3),
    }
    if max_dark > 0.62:
        issues.append({
            "severity": "WARN",
            "kind": "evidence",
            "max_dark_fraction": round(max_dark, 3),
            "reason": "At least one sampled walkthrough frame is dominated by unreadable darkness; refresh or relight before human art review.",
        })
    elif max_dark > 0.48:
        issues.append({
            "severity": "WARN",
            "kind": "evidence",
            "max_dark_fraction": round(max_dark, 3),
            "reason": "Some walkthrough frames are too dark for reliable visual review.",
        })
    if avg_bright > 0.12:
        issues.append({
            "severity": "WARN",
            "kind": "evidence",
            "average_bright_fraction": round(avg_bright, 3),
            "reason": "Walkthrough may contain over-bright emissive/light areas.",
        })
    return issues, summary


def strip_private(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean = []
    for record in records:
        item = {key: value for key, value in record.items() if not key.startswith("_")}
        clean.append(item)
    return clean


def godot_to_blender(vec: list[float]) -> Vector:
    return Vector((float(vec[0]), float(-vec[2]), float(vec[1])))


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def write_png(path: Path, width: int, height: int, pixels: bytes) -> None:
    rows = bytearray()
    stride = width * 3
    for y in range(height):
        rows.append(0)
        rows.extend(pixels[y * stride : (y + 1) * stride])
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(bytes(rows), 6))
        + png_chunk(b"IEND", b"")
    )


def blit_rgb(
    dest: bytearray,
    dest_width: int,
    dest_height: int,
    src: bytes,
    src_width: int,
    src_height: int,
    x: int,
    y: int,
) -> None:
    copy_width = min(src_width, dest_width - x)
    copy_height = min(src_height, dest_height - y)
    if copy_width <= 0 or copy_height <= 0:
        return
    for src_y in range(copy_height):
        dest_y = y + src_y
        if dest_y < 0 or dest_y >= dest_height:
            continue
        src_start = src_y * src_width * 3
        src_end = src_start + copy_width * 3
        dest_start = (dest_y * dest_width + x) * 3
        dest_end = dest_start + copy_width * 3
        if 0 <= x:
            dest[dest_start:dest_end] = src[src_start:src_end]


def image_to_rgb_bytes(image: bpy.types.Image, expected_width: int, expected_height: int) -> tuple[bytes, int, int]:
    # Blender pixels are bottom-up RGBA floats. The report images are top-down RGB bytes.
    width, height = int(image.size[0]), int(image.size[1])
    pixels = list(image.pixels)
    pixel_count = len(pixels) // 4
    if pixel_count <= 0:
        return bytes([22, 24, 28] * expected_width * expected_height), expected_width, expected_height
    if width <= 0 or height <= 0 or width * height != pixel_count:
        width, height = expected_width, expected_height
    if width * height != pixel_count:
        aspect = expected_width / max(1, expected_height)
        width = max(1, int(math.sqrt(pixel_count * aspect)))
        height = max(1, pixel_count // width)
    pixel_count = min(pixel_count, width * height)
    out = bytearray(width * height * 3)
    for y in range(min(height, pixel_count // width)):
        src_y = height - 1 - y
        for x in range(width):
            src_offset = (src_y * width + x) * 4
            if src_offset + 2 >= len(pixels):
                continue
            dst_offset = (y * width + x) * 3
            out[dst_offset] = max(0, min(255, int(pixels[src_offset] * 255)))
            out[dst_offset + 1] = max(0, min(255, int(pixels[src_offset + 1] * 255)))
            out[dst_offset + 2] = max(0, min(255, int(pixels[src_offset + 2] * 255)))
    return bytes(out), width, height


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def region_bounds(records: list[dict[str, Any]], region: str) -> tuple[Vector, Vector] | None:
    region_records = [
        record for record in records
        if record["region"] == region and record["role"] != "review_volume"
    ]
    if not region_records:
        return None
    mins = Vector((
        min(record["_bounds"][0].x for record in region_records),
        min(record["_bounds"][0].y for record in region_records),
        min(record["_bounds"][0].z for record in region_records),
    ))
    maxs = Vector((
        max(record["_bounds"][1].x for record in region_records),
        max(record["_bounds"][1].y for record in region_records),
        max(record["_bounds"][1].z for record in region_records),
    ))
    return mins, maxs


def render_region_orbit_sheet(records: list[dict[str, Any]]) -> None:
    scene = bpy.context.scene
    original_camera = scene.camera
    original_resolution = (scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage)
    original_engine = scene.render.engine
    original_hide_render: dict[str, bool] = {}

    for record in records:
        obj = bpy.data.objects.get(record["name"])
        if obj is None:
            continue
        original_hide_render[obj.name] = obj.hide_render
        if record["role"] == "review_volume":
            obj.hide_render = True

    width, height = 480, 300
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    if "BLENDER_WORKBENCH" in {item.identifier for item in scene.render.bl_rna.properties["engine"].enum_items}:
        scene.render.engine = "BLENDER_WORKBENCH"

    camera_data = bpy.data.cameras.new("InteriorVisualEval_Camera")
    camera = bpy.data.objects.new("InteriorVisualEval_Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    scene.camera = camera
    camera_data.lens = 22

    regions = ["ramp_entry", "cargo_bay", "stairs_landing", "cockpit"]
    view_offsets = [
        Vector((0.0, -5.8, 1.15)),
        Vector((3.4, -2.4, 1.45)),
        Vector((-3.4, -2.4, 1.45)),
        Vector((0.0, 3.8, 1.25)),
    ]
    margin = 18
    sheet_width = len(view_offsets) * width + (len(view_offsets) + 1) * margin
    sheet_height = len(regions) * height + (len(regions) + 1) * margin
    sheet = bytearray([10, 12, 15] * sheet_width * sheet_height)

    try:
        for row, region in enumerate(regions):
            bounds = region_bounds(records, region)
            if bounds is None:
                continue
            center = bbox_center(bounds)
            size = bbox_size(bounds)
            radius = max(2.2, float(max(size.x, size.y, size.z)) * 0.95)
            target = center + Vector((0.0, 0.0, min(0.4, max(0.0, float(size.z) * 0.1))))
            for col, base_offset in enumerate(view_offsets):
                offset = Vector((base_offset.x * radius / 4.0, base_offset.y * radius / 4.0, base_offset.z))
                camera.location = target + offset
                look_at(camera, target)
                bpy.ops.render.render(write_still=False)
                image = bpy.data.images.get("Render Result")
                if image is None:
                    continue
                rgb, render_width, render_height = image_to_rgb_bytes(image, width, height)
                blit_rgb(
                    sheet,
                    sheet_width,
                    sheet_height,
                    rgb,
                    render_width,
                    render_height,
                    margin + col * (width + margin),
                    margin + row * (height + margin),
                )
        write_png(REGION_ORBIT_SHEET, sheet_width, sheet_height, bytes(sheet))
    finally:
        scene.camera = original_camera
        scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = original_resolution
        scene.render.engine = original_engine
        bpy.data.objects.remove(camera, do_unlink=True)
        bpy.data.cameras.remove(camera_data, do_unlink=True)
        for name, hide_render in original_hide_render.items():
            obj = bpy.data.objects.get(name)
            if obj is not None:
                obj.hide_render = hide_render


def render_region_projection_sheet(records: list[dict[str, Any]]) -> None:
    width, height = 1400, 900
    pixels = bytearray([13, 15, 18] * width * height)
    region_order = ["ramp_entry", "cargo_bay", "stairs_landing", "cockpit"]
    region_colors = {
        "walkable_surface": (100, 190, 110),
        "wall_panel": (170, 160, 130),
        "ceiling_panel": (125, 150, 180),
        "structural_rib": (190, 125, 90),
        "trim_or_gasket": (70, 75, 82),
        "light_fixture": (245, 210, 100),
        "emissive_lens": (90, 190, 240),
        "display_or_control": (80, 135, 210),
        "seat_component": (135, 135, 145),
        "mechanical_component": (150, 115, 90),
        "cargo_fixture": (160, 145, 90),
        "decorative_or_unknown": (230, 60, 180),
    }
    cell_w = width // len(region_order)
    for index, region in enumerate(region_order):
        x0 = index * cell_w
        draw_rect(pixels, width, height, x0 + 1, 0, 2, height, (42, 48, 55))
        region_records = [record for record in records if record["region"] == region and record["role"] != "review_volume"]
        bounds = region_bounds(records, region)
        if bounds is None:
            continue
        mins, maxs = bounds
        span_x = max(0.001, float(maxs.x - mins.x))
        span_z = max(0.001, float(maxs.z - mins.z))
        for record in region_records:
            center = record["center_blender"]
            size = record["size_blender"]
            px = x0 + 32 + int((center[0] - mins.x) / span_x * (cell_w - 64))
            py = 820 - int((center[2] - mins.z) / span_z * 720)
            rw = max(3, min(44, int(abs(size[0]) * 9)))
            rh = max(3, min(44, int(abs(size[2]) * 9)))
            color = region_colors.get(record["role"], (180, 180, 180))
            draw_rect(pixels, width, height, px - rw // 2, py - rh // 2, rw, rh, color)
    write_png(REGION_ORBIT_SHEET, width, height, bytes(pixels))


def draw_rect(pixels: bytearray, width: int, height: int, x: int, y: int, w: int, h: int, color: tuple[int, int, int]) -> None:
    for yy in range(max(0, y), min(height, y + h)):
        for xx in range(max(0, x), min(width, x + w)):
            offset = (yy * width + xx) * 3
            pixels[offset : offset + 3] = bytes(color)


def render_diagnostic_images(records: list[dict[str, Any]], issues: list[dict[str, Any]], material_summary: dict[str, Any]) -> None:
    width, height = 1400, 900
    pixels = bytearray([18, 20, 24] * width * height)
    fail_count = sum(1 for issue in issues if issue["severity"] == "FAIL")
    warn_count = sum(1 for issue in issues if issue["severity"] == "WARN")
    draw_rect(pixels, width, height, 30, 30, min(620, fail_count * 20), 42, (190, 45, 45))
    draw_rect(pixels, width, height, 30, 88, min(620, warn_count * 8), 42, (210, 150, 45))
    role_counts = Counter(record["role"] for record in records)
    y = 170
    colors = [(80, 150, 210), (130, 190, 105), (180, 120, 210), (210, 120, 90), (190, 190, 90), (110, 180, 180)]
    for idx, (_role, count) in enumerate(role_counts.most_common(14)):
        draw_rect(pixels, width, height, 40, y, min(760, count * 3), 28, colors[idx % len(colors)])
        y += 42
    write_png(CONTACT_SHEET, width, height, bytes(pixels))

    overlay = bytearray([12, 12, 14] * width * height)
    region_x = {"ramp_entry": 120, "cargo_bay": 380, "stairs_landing": 650, "cockpit": 930, "transition": 1160}
    severity_color = {"FAIL": (220, 45, 45), "WARN": (230, 165, 40)}
    draw_rect(overlay, width, height, 0, 430, width, 2, (60, 65, 70))
    for region, x in region_x.items():
        draw_rect(overlay, width, height, x, 80, 4, 740, (55, 60, 68))
    for issue in issues[:220]:
        obj = issue.get("object")
        if not obj:
            continue
        record = next((item for item in records if item["name"] == obj), None)
        if record is None:
            continue
        x = region_x.get(record["region"], 1160) + int((record["center_godot"][0] + 4.5) * 18)
        y = 430 - int(record["center_godot"][2] * 20)
        draw_rect(overlay, width, height, x, y, 8, 8, severity_color.get(issue["severity"], (180, 180, 180)))
    write_png(ATTACHMENT_OVERLAY, width, height, bytes(overlay))

    material_pixels = bytearray([15, 17, 20] * width * height)
    family_colors = {
        "emissive": (255, 214, 96),
        "rubber_gasket": (20, 24, 28),
        "dark_structural": (45, 50, 56),
        "brushed_metal": (145, 150, 145),
        "worn_floor": (150, 125, 85),
        "light_panel": (190, 184, 164),
        "glass": (60, 125, 145),
        "seat_fabric": (90, 95, 95),
        "blockout_volume": (130, 100, 170),
        "unknown": (220, 50, 180),
    }
    x = 40
    y = 80
    for region, families in material_summary.get("object_counts_by_region", {}).items():
        total = max(1, sum(families.values()))
        cursor = x
        for family, count in sorted(families.items()):
            w = max(2, int(980 * count / total))
            draw_rect(material_pixels, width, height, cursor, y, w, 48, family_colors.get(family, (150, 150, 150)))
            cursor += w
        y += 85
    write_png(MATERIAL_SHEET, width, height, bytes(material_pixels))


def write_markdown(report: dict[str, Any]) -> None:
    status = report["status"]
    issues = report["issues"]
    fail_count = sum(1 for issue in issues if issue["severity"] == "FAIL")
    warn_count = sum(1 for issue in issues if issue["severity"] == "WARN")
    lines = [
        "# Prototype Shuttle Interior Visual Evaluation",
        "",
        f"Status: **{status}**",
        "",
        "## Summary",
        "",
        f"- Interior objects inventoried: {report['object_count']}",
        f"- Blocking failures: {fail_count}",
        f"- Warnings: {warn_count}",
        f"- Unknown-role objects: {report['role_counts'].get('decorative_or_unknown', 0)}",
        f"- Visible fixture/emissive objects: {report['visible_fixture_count']}",
        f"- Actual production lights: {report['actual_light_count']}",
        "",
        "## Blocking Issues",
        "",
    ]
    failures = [issue for issue in issues if issue["severity"] == "FAIL"]
    if not failures:
        lines.append("- None")
    else:
        for issue in failures[:40]:
            subject = issue.get("object") or issue.get("light") or issue.get("region") or issue.get("kind")
            lines.append(f"- `{issue['kind']}` `{subject}`: {issue['reason']}")
    lines.extend(["", "## Warnings", ""])
    warnings = [issue for issue in issues if issue["severity"] == "WARN"]
    if not warnings:
        lines.append("- None")
    else:
        for issue in warnings[:60]:
            subject = issue.get("object") or issue.get("light") or issue.get("region") or issue.get("kind")
            lines.append(f"- `{issue['kind']}` `{subject}`: {issue['reason']}")
    lines.extend([
        "",
        "## Role Counts",
        "",
    ])
    for role, count in sorted(report["role_counts"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- `{role}`: {count}")
    lines.extend([
        "",
        "## Material Families By Region",
        "",
    ])
    for region, families in report["material_summary"]["object_counts_by_region"].items():
        lines.append(f"### {region}")
        for family, count in sorted(families.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- `{family}`: {count}")
        lines.append("")
    if report.get("evidence_summary"):
        lines.extend([
            "## Evidence Brightness Summary",
            "",
        ])
        for key, value in report["evidence_summary"].items():
            lines.append(f"- `{key}`: {value}")
        lines.append("")
    lines.extend([
        "## Generated Artifacts",
        "",
        f"- `{CONTACT_SHEET.relative_to(ROOT)}`",
        f"- `{ATTACHMENT_OVERLAY.relative_to(ROOT)}`",
        f"- `{MATERIAL_SHEET.relative_to(ROOT)}`",
        f"- `{REGION_ORBIT_SHEET.relative_to(ROOT)}`",
    ])
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    load_source()
    interior_collection = bpy.data.collections.get("Interior")
    if interior_collection is None:
        raise RuntimeError("Missing Interior collection")
    records = [
        record
        for obj in descendants(interior_collection)
        if (record := object_record(obj)) is not None
    ]
    issues = []
    issues.extend(classification_checks(records))
    issues.extend(attachment_checks(records))
    material_issues, material_summary = material_checks(records)
    issues.extend(material_issues)
    issues.extend(light_checks(records))
    evidence_issues, evidence_summary = evidence_checks()
    issues.extend(evidence_issues)
    severity_order = {"FAIL": 0, "WARN": 1}
    issues.sort(key=lambda issue: (severity_order.get(issue["severity"], 9), issue["kind"], issue.get("object", "")))
    status = "FAIL" if any(issue["severity"] == "FAIL" for issue in issues) else "PASS"
    report = {
        "schema_version": 1,
        "ship_id": "prototype_shuttle",
        "source_blend": str(SOURCE_BLEND.relative_to(ROOT)),
        "status": status,
        "object_count": len(records),
        "role_counts": dict(Counter(record["role"] for record in records)),
        "region_counts": dict(Counter(record["region"] for record in records)),
        "visible_fixture_count": sum(1 for record in records if record["role"] in {"light_fixture", "emissive_lens"} or "emissive" in record["material_families"]),
        "actual_light_count": len(json.loads(LIGHT_REPORT.read_text(encoding="utf-8")).get("lights", [])) if LIGHT_REPORT.exists() else 0,
        "issues": issues,
        "material_summary": material_summary,
        "evidence_summary": evidence_summary,
        "objects": strip_private(records),
        "artifacts": {
            "markdown": str(REPORT_MD.relative_to(ROOT)),
            "contact_sheet": str(CONTACT_SHEET.relative_to(ROOT)),
            "attachment_overlay": str(ATTACHMENT_OVERLAY.relative_to(ROOT)),
            "material_sheet": str(MATERIAL_SHEET.relative_to(ROOT)),
            "region_orbit_sheet": str(REGION_ORBIT_SHEET.relative_to(ROOT)),
        },
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    render_diagnostic_images(records, issues, material_summary)
    if os.environ.get("VISUAL_EVAL_RENDER_REGIONS", "0") == "1":
        render_region_orbit_sheet(records)
    else:
        render_region_projection_sheet(records)
    write_markdown(report)
    print(f"Prototype shuttle interior visual evaluation status: {status}")
    print(f"Report: {REPORT_MD.relative_to(ROOT)}")
    print(f"JSON: {REPORT_JSON.relative_to(ROOT)}")
    print(f"Contact sheet: {CONTACT_SHEET.relative_to(ROOT)}")
    print(f"Attachment overlay: {ATTACHMENT_OVERLAY.relative_to(ROOT)}")
    print(f"Material sheet: {MATERIAL_SHEET.relative_to(ROOT)}")
    print(f"Region orbit sheet: {REGION_ORBIT_SHEET.relative_to(ROOT)}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
