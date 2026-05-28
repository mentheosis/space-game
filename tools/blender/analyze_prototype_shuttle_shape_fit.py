#!/usr/bin/env python3
"""Measure prototype shuttle silhouette fit against the ShuttleA OBJ reference.

This tool is intentionally deterministic: it reads the actual ShuttleA OBJ
vertices and the current prototype Blender exterior mesh, projects both to
side/top/front views, normalizes them by length, and writes numeric fit reports
plus raster overlay images.
"""

from __future__ import annotations

import json
import math
import os
import struct
import zlib
from pathlib import Path

import bpy


ROOT = Path(os.environ.get("SPACE_GAME_ROOT", Path.cwd())).resolve()
SOURCE_BLEND = ROOT / "assets/source/blender/ships/prototype_shuttle/prototype_shuttle.blend"
SHUTTLE_OBJ = ROOT / "assets/models/ship/placeholders/oga_3d_space_ship_pack/ShuttleA.obj"
OUT_DIR = ROOT / "reports/prototype_shuttle_shape_fit"
REPORT_JSON = OUT_DIR / "shape_fit_report.json"
REPORT_MD = OUT_DIR / "shape_fit_report.md"
CONTACT_SHEET = OUT_DIR / "shape_fit_overlay_current.png"

# Match the runtime ShuttleA visual transform documented in
# tools/blender/bootstrap_shuttle_a_scene.py.
EXTERIOR_VISUAL_POSITION = (0.0, 2.12, 0.69)
EXTERIOR_VISUAL_SCALE = (1.27, 0.92, 0.92)

VIEW_SPECS = {
    "side": {"u": "z", "v": "y", "label": "Side: length vs height"},
    "top": {"u": "z", "v": "x", "label": "Top: length vs width"},
    "front": {"u": "x", "v": "y", "label": "Front: width vs height"},
}


def transform_obj_vertex_to_ship_space(vertex: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = vertex
    px, py, pz = EXTERIOR_VISUAL_POSITION
    sx, sy, sz = EXTERIOR_VISUAL_SCALE
    return (px + x * sx, py + y * sy, pz - z * sz)


def blender_to_ship_space(loc) -> tuple[float, float, float]:
    return (float(loc.x), float(loc.z), float(-loc.y))


def read_shuttle_a_vertices() -> tuple[list[tuple[float, float, float]], dict[str, list[tuple[float, float, float]]]]:
    raw: list[tuple[float, float, float] | None] = [None]
    current_material = "<none>"
    by_material: dict[str, list[tuple[float, float, float]]] = {}
    all_vertices: list[tuple[float, float, float]] = []

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
            index = int(part.split("/")[0])
            vertex = raw[index]
            if vertex is None:
                continue
            point = transform_obj_vertex_to_ship_space(vertex)
            all_vertices.append(point)
            by_material.setdefault(current_material, []).append(point)

    if not all_vertices:
        raise RuntimeError(f"No vertices found in {SHUTTLE_OBJ}")
    return all_vertices, by_material


def collect_prototype_vertices() -> list[tuple[float, float, float]]:
    if not SOURCE_BLEND.exists():
        raise RuntimeError(f"Missing prototype source blend: {SOURCE_BLEND}")
    if Path(bpy.data.filepath).resolve() != SOURCE_BLEND:
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE_BLEND))

    collection = bpy.data.collections.get("Exterior")
    if collection is None:
        raise RuntimeError("Prototype blend is missing Exterior collection")

    vertices: list[tuple[float, float, float]] = []

    def visit(coll: bpy.types.Collection) -> None:
        for obj in coll.objects:
            if obj.type != "MESH" or obj.data is None:
                continue
            for vertex in obj.data.vertices:
                vertices.append(blender_to_ship_space(obj.matrix_world @ vertex.co))
        for child in coll.children:
            visit(child)

    visit(collection)
    if not vertices:
        raise RuntimeError("No prototype exterior vertices found")
    return vertices


def bounds(points: list[tuple[float, float, float]]) -> dict[str, object]:
    mins = [min(point[index] for point in points) for index in range(3)]
    maxs = [max(point[index] for point in points) for index in range(3)]
    size = [maxs[index] - mins[index] for index in range(3)]
    center = [(mins[index] + maxs[index]) * 0.5 for index in range(3)]
    return {
        "min": [round(value, 5) for value in mins],
        "max": [round(value, 5) for value in maxs],
        "size": [round(value, 5) for value in size],
        "center": [round(value, 5) for value in center],
    }


def axis_value(point: tuple[float, float, float], axis: str) -> float:
    return {"x": point[0], "y": point[1], "z": point[2]}[axis]


def normalized_points(points: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    b = bounds(points)
    mins = b["min"]
    size = b["size"]
    length = float(size[2]) if float(size[2]) > 0.0001 else 1.0
    scale = 1.0 / length
    center = b["center"]
    return [
        (
            (point[0] - float(center[0])) * scale,
            (point[1] - float(center[1])) * scale,
            (point[2] - float(center[2])) * scale,
        )
        for point in points
    ]


def profile(points: list[tuple[float, float, float]], u_axis: str, v_axis: str, bins: int = 96) -> list[dict[str, float | None]]:
    u_values = [axis_value(point, u_axis) for point in points]
    u_min = min(u_values)
    u_max = max(u_values)
    span = max(u_max - u_min, 0.0001)
    buckets: list[list[float]] = [[] for _ in range(bins)]
    for point in points:
        u = axis_value(point, u_axis)
        v = axis_value(point, v_axis)
        index = min(bins - 1, max(0, int(((u - u_min) / span) * bins)))
        buckets[index].append(v)
    result: list[dict[str, float | None]] = []
    for index, bucket in enumerate(buckets):
        u = u_min + (index + 0.5) * span / bins
        if bucket:
            result.append({"u": u, "min": min(bucket), "max": max(bucket)})
        else:
            result.append({"u": u, "min": None, "max": None})
    return result


def profile_delta(reference: list[dict[str, float | None]], prototype: list[dict[str, float | None]]) -> dict[str, float]:
    deltas: list[float] = []
    for ref, proto in zip(reference, prototype):
        if ref["min"] is None or ref["max"] is None or proto["min"] is None or proto["max"] is None:
            continue
        deltas.append(abs(float(ref["min"]) - float(proto["min"])))
        deltas.append(abs(float(ref["max"]) - float(proto["max"])))
    if not deltas:
        return {"mean": 999.0, "rms": 999.0, "max": 999.0}
    mean = sum(deltas) / len(deltas)
    rms = math.sqrt(sum(delta * delta for delta in deltas) / len(deltas))
    return {"mean": round(mean, 5), "rms": round(rms, 5), "max": round(max(deltas), 5)}


def png_write(path: Path, width: int, height: int, pixels: bytearray) -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    rows = bytearray()
    stride = width * 3
    for y in range(height):
        rows.append(0)
        rows.extend(pixels[y * stride : (y + 1) * stride])
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + chunk(b"IEND", b"")
    )


def draw_line(pixels: bytearray, width: int, height: int, a: tuple[int, int], b: tuple[int, int], color: tuple[int, int, int]) -> None:
    x0, y0 = a
    x1, y1 = b
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        if 0 <= x0 < width and 0 <= y0 < height:
            offset = (y0 * width + x0) * 3
            pixels[offset : offset + 3] = bytes(color)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def draw_profile(
    pixels: bytearray,
    width: int,
    height: int,
    origin_x: int,
    origin_y: int,
    panel_w: int,
    panel_h: int,
    prof: list[dict[str, float | None]],
    color: tuple[int, int, int],
    scale: float,
) -> None:
    points_min: list[tuple[int, int]] = []
    points_max: list[tuple[int, int]] = []
    for index, item in enumerate(prof):
        if item["min"] is None or item["max"] is None:
            continue
        x = origin_x + int((index / max(1, len(prof) - 1)) * (panel_w - 1))
        y_min = origin_y + panel_h // 2 - int(float(item["min"]) * scale)
        y_max = origin_y + panel_h // 2 - int(float(item["max"]) * scale)
        points_min.append((x, y_min))
        points_max.append((x, y_max))
    for seq in (points_min, points_max):
        for a, b in zip(seq, seq[1:]):
            draw_line(pixels, width, height, a, b, color)


def render_contact_sheet(reference_profiles: dict[str, list[dict[str, float | None]]], prototype_profiles: dict[str, list[dict[str, float | None]]]) -> None:
    width = 1800
    height = 700
    pixels = bytearray([12, 15, 18] * width * height)
    panel_w = 560
    panel_h = 560
    margin_x = 30
    margin_y = 70
    for panel_index, view in enumerate(("side", "top", "front")):
        x0 = margin_x + panel_index * (panel_w + 30)
        y0 = margin_y
        for x in range(x0, x0 + panel_w):
            draw_line(pixels, width, height, (x, y0 + panel_h // 2), (x, y0 + panel_h // 2), (55, 65, 75))
        for y in range(y0, y0 + panel_h):
            draw_line(pixels, width, height, (x0 + panel_w // 2, y), (x0 + panel_w // 2, y), (55, 65, 75))
        draw_profile(pixels, width, height, x0, y0, panel_w, panel_h, reference_profiles[view], (70, 170, 255), 360)
        draw_profile(pixels, width, height, x0, y0, panel_w, panel_h, prototype_profiles[view], (255, 105, 80), 360)
    png_write(CONTACT_SHEET, width, height, pixels)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reference_points, by_material = read_shuttle_a_vertices()
    prototype_points = collect_prototype_vertices()
    ref_norm = normalized_points(reference_points)
    proto_norm = normalized_points(prototype_points)

    reference_profiles = {}
    prototype_profiles = {}
    deltas = {}
    for view, spec in VIEW_SPECS.items():
        reference_profiles[view] = profile(ref_norm, spec["u"], spec["v"])
        prototype_profiles[view] = profile(proto_norm, spec["u"], spec["v"])
        deltas[view] = profile_delta(reference_profiles[view], prototype_profiles[view])

    render_contact_sheet(reference_profiles, prototype_profiles)

    report = {
        "schema_version": 1,
        "reference_obj": str(SHUTTLE_OBJ.relative_to(ROOT)),
        "prototype_blend": str(SOURCE_BLEND.relative_to(ROOT)),
        "method": "normalized envelope profiles from actual mesh vertices; blue=ShuttleA reference, orange=prototype",
        "reference_bounds_ship_space": bounds(reference_points),
        "prototype_bounds_ship_space": bounds(prototype_points),
        "reference_material_bounds_ship_space": {
            name: bounds(points) for name, points in sorted(by_material.items()) if points
        },
        "normalized_profile_delta": deltas,
        "artifacts": {
            "contact_sheet": str(CONTACT_SHEET.relative_to(ROOT)),
        },
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Prototype Shuttle Shape Fit Report",
        "",
        "Blue is the ShuttleA OBJ reference. Orange is the current prototype exterior.",
        "",
        "## Normalized Profile Delta",
        "",
    ]
    for view in ("side", "top", "front"):
        delta = deltas[view]
        lines.append(f"- {view}: mean `{delta['mean']}`, rms `{delta['rms']}`, max `{delta['max']}`")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- `{CONTACT_SHEET.relative_to(ROOT)}`",
            f"- `{REPORT_JSON.relative_to(ROOT)}`",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT_JSON}")
    print(f"Wrote {REPORT_MD}")
    print(f"Wrote {CONTACT_SHEET}")


if __name__ == "__main__":
    main()
