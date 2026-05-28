#!/usr/bin/env python3
"""Extract deterministic interior volume proxy candidates from exterior mesh slices."""

from __future__ import annotations

import importlib.util
import json
import os
import struct
import zlib
from pathlib import Path

import bpy


ROOT = Path(os.environ.get("SPACE_GAME_ROOT", Path.cwd())).resolve()
SOURCE_BLEND = ROOT / "assets/source/blender/ships/prototype_shuttle/prototype_shuttle.blend"
BOOTSTRAP = ROOT / "tools/blender/bootstrap_prototype_shuttle_scene.py"
OUT_DIR = ROOT / "reports/prototype_shuttle_volume_fit"
REPORT_JSON = OUT_DIR / "interior_volume_report.json"
REPORT_MD = OUT_DIR / "interior_volume_report.md"
REPORT_PNG = OUT_DIR / "interior_volume_projection_current.png"


def load_bootstrap_module():
    spec = importlib.util.spec_from_file_location("prototype_shuttle_bootstrap", BOOTSTRAP)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load bootstrap module: {BOOTSTRAP}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def blender_to_ship_space(loc) -> tuple[float, float, float]:
    return (float(loc.x), float(loc.z), float(-loc.y))


def collect_exterior_vertices() -> list[tuple[float, float, float]]:
    if Path(bpy.data.filepath).resolve() != SOURCE_BLEND:
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE_BLEND))
    collection = bpy.data.collections.get("Exterior")
    if collection is None:
        raise RuntimeError("Prototype blend is missing Exterior collection")
    points: list[tuple[float, float, float]] = []

    def visit(coll: bpy.types.Collection) -> None:
        for obj in coll.objects:
            if obj.type != "MESH" or obj.data is None:
                continue
            for vertex in obj.data.vertices:
                points.append(blender_to_ship_space(obj.matrix_world @ vertex.co))
        for child in coll.children:
            visit(child)

    visit(collection)
    if not points:
        raise RuntimeError("No exterior mesh vertices found for volume extraction")
    return points


def tuple_payload(value):
    if isinstance(value, tuple):
        return [round(float(item), 5) for item in value]
    if isinstance(value, list):
        return [tuple_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: tuple_payload(item) for key, item in value.items()}
    if isinstance(value, float):
        return round(value, 5)
    return value


class ImageCanvas:
    def __init__(self, width: int, height: int, color: tuple[int, int, int]):
        self.width = width
        self.height = height
        self.pixels = bytearray(color * (width * height))

    def set_pixel(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            offset = (y * self.width + x) * 3
            self.pixels[offset : offset + 3] = bytes(color)

    def rect(self, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int], fill: bool = False) -> None:
        left, right = sorted((max(0, x0), min(self.width - 1, x1)))
        top, bottom = sorted((max(0, y0), min(self.height - 1, y1)))
        if fill:
            for y in range(top, bottom + 1):
                row = (y * self.width + left) * 3
                self.pixels[row : row + (right - left + 1) * 3] = bytes(color) * (right - left + 1)
            return
        for x in range(left, right + 1):
            self.set_pixel(x, top, color)
            self.set_pixel(x, bottom, color)
        for y in range(top, bottom + 1):
            self.set_pixel(left, y, color)
            self.set_pixel(right, y, color)

    def line(self, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
        dx = abs(x1 - x0)
        sx = 1 if x0 < x1 else -1
        dy = -abs(y1 - y0)
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set_pixel(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def write_png(self, path: Path) -> None:
        def chunk(kind: bytes, data: bytes) -> bytes:
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

        rows = bytearray()
        stride = self.width * 3
        for y in range(self.height):
            rows.append(0)
            start = y * stride
            rows.extend(self.pixels[start : start + stride])
        data = b"".join(
            [
                b"\x89PNG\r\n\x1a\n",
                chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)),
                chunk(b"IDAT", zlib.compress(bytes(rows), 9)),
                chunk(b"IEND", b""),
            ]
        )
        path.write_bytes(data)


def box_corners_2d(box, axes: tuple[int, int]) -> tuple[float, float, float, float]:
    position = box["position"]
    size = box["size"]
    x_axis, y_axis = axes
    min_x = position[x_axis] - size[x_axis] * 0.5
    max_x = position[x_axis] + size[x_axis] * 0.5
    min_y = position[y_axis] - size[y_axis] * 0.5
    max_y = position[y_axis] + size[y_axis] * 0.5
    return (min_x, min_y, max_x, max_y)


def draw_projection(canvas: ImageCanvas, panel, points, boxes, axes, label_color, cargo_prism_sections=None, transition_prism_sections=None) -> None:
    px, py, pw, ph = panel
    canvas.rect(px, py, px + pw - 1, py + ph - 1, (42, 48, 56))
    coords = [(point[axes[0]], point[axes[1]]) for point in points]
    min_x = min(coord[0] for coord in coords)
    max_x = max(coord[0] for coord in coords)
    min_y = min(coord[1] for coord in coords)
    max_y = max(coord[1] for coord in coords)
    margin_x = max(0.5, (max_x - min_x) * 0.12)
    margin_y = max(0.5, (max_y - min_y) * 0.18)
    min_x -= margin_x
    max_x += margin_x
    min_y -= margin_y
    max_y += margin_y

    def map_point(x: float, y: float) -> tuple[int, int]:
        nx = (x - min_x) / max(0.001, max_x - min_x)
        ny = (y - min_y) / max(0.001, max_y - min_y)
        return (int(px + nx * (pw - 1)), int(py + (1.0 - ny) * (ph - 1)))

    # Exterior silhouette cloud.
    for x, y in coords:
        sx, sy = map_point(x, y)
        canvas.set_pixel(sx, sy, (215, 220, 226))

    def draw_polyline(poly_points: list[tuple[float, float]], color: tuple[int, int, int]) -> None:
        if len(poly_points) < 2:
            return
        mapped = [map_point(x, y) for x, y in poly_points]
        for index in range(len(mapped)):
            x0, y0 = mapped[index]
            x1, y1 = mapped[(index + 1) % len(mapped)]
            canvas.line(x0, y0, x1, y1, color)
            canvas.line(x0 + 1, y0, x1 + 1, y1, color)

    def draw_prism_sections(sections, color):
        if not sections:
            return
        if axes == (2, 1):
            lower = [(section["z"], section["bottom"]) for section in sections]
            upper = [(section["z"], section["top"]) for section in reversed(sections)]
            draw_polyline(lower + upper, color)
        elif axes == (2, 0):
            left = [(section["z"], -max(section["lower_half_width"], section["upper_half_width"])) for section in sections]
            right = [(section["z"], max(section["lower_half_width"], section["upper_half_width"])) for section in reversed(sections)]
            draw_polyline(left + right, color)
        elif axes == (0, 1):
            widest = max(sections, key=lambda section: section["lower_half_width"] + section["upper_half_width"])
            lower = widest["lower_half_width"]
            upper = widest["upper_half_width"]
            draw_polyline(
                [
                    (-lower, widest["bottom"]),
                    (lower, widest["bottom"]),
                    (lower, widest["mid"]),
                    (upper, widest["top"]),
                    (-upper, widest["top"]),
                    (-lower, widest["mid"]),
                ],
                color,
            )

    if cargo_prism_sections:
        draw_prism_sections(cargo_prism_sections, (81, 190, 212))
    if transition_prism_sections:
        draw_prism_sections(transition_prism_sections, (148, 214, 91))

    colors = {
        "cargo": (81, 177, 201),
        "cargo_forward_lower": (55, 151, 184),
        "cargo_forward_upper": (91, 198, 219),
        "cargo_mid_lower": (63, 161, 190),
        "cargo_mid_upper": (99, 207, 226),
        "cargo_aft_lower": (70, 171, 198),
        "cargo_aft_upper": (112, 217, 235),
        "cockpit": (235, 193, 75),
        "ramp": (236, 120, 71),
        "left_ascent": (148, 214, 91),
        "right_ascent": (148, 214, 91),
        "pilot_seat": (185, 128, 233),
        "copilot_seat": (185, 128, 233),
    }
    has_piecewise_cargo = any(name.startswith("cargo_") for name in boxes)
    for name, box in boxes.items():
        if name == "cargo" and has_piecewise_cargo:
            continue
        if cargo_prism_sections and name.startswith("cargo_"):
            continue
        if transition_prism_sections and name in {"left_ascent", "right_ascent"}:
            continue
        min_bx, min_by, max_bx, max_by = box_corners_2d(box, axes)
        sx0, sy0 = map_point(min_bx, min_by)
        sx1, sy1 = map_point(max_bx, max_by)
        color = colors.get(name, (81, 177, 201) if name.startswith("cargo_") else label_color)
        canvas.rect(sx0, sy0, sx1, sy1, color)
        # Thicken outlines enough to remain legible in the artifact UI.
        canvas.rect(sx0 + 1, sy0 + 1, sx1 - 1, sy1 - 1, color)

    center_x = px + pw // 2
    center_y = py + ph // 2
    canvas.line(center_x, py + 8, center_x, py + ph - 8, (55, 63, 73))
    canvas.line(px + 8, center_y, px + pw - 8, center_y, (55, 63, 73))


def write_projection_png(points, boxes, cargo_prism_sections, transition_prism_sections) -> None:
    canvas = ImageCanvas(1920, 720, (12, 15, 19))
    panels = [
        (24, 36, 604, 648),   # side: length / height
        (658, 36, 604, 648),  # top: length / width
        (1292, 36, 604, 648), # front: width / height
    ]
    draw_projection(canvas, panels[0], points, boxes, (2, 1), (235, 193, 75), cargo_prism_sections, transition_prism_sections)
    draw_projection(canvas, panels[1], points, boxes, (2, 0), (81, 177, 201), cargo_prism_sections, transition_prism_sections)
    draw_projection(canvas, panels[2], points, boxes, (0, 1), (236, 120, 71), cargo_prism_sections, transition_prism_sections)
    canvas.write_png(REPORT_PNG)


def validate_connectivity(boxes, cargo_prism_sections, transition_prism_sections):
    checks = []
    cockpit = boxes.get("cockpit")
    if cockpit and transition_prism_sections:
        cockpit_aft = cockpit["position"][2] + cockpit["size"][2] * 0.5
        transition_start = min(section["z"] for section in transition_prism_sections)
        checks.append(
            {
                "id": "transition_overlaps_cockpit",
                "pass": transition_start <= cockpit_aft + 0.25,
                "value": round(transition_start - cockpit_aft, 5),
                "description": "transition prism starts at or slightly inside cockpit aft extent",
            }
        )
    else:
        checks.append({"id": "transition_overlaps_cockpit", "pass": False, "value": None, "description": "missing cockpit or transition prism"})

    if cargo_prism_sections and transition_prism_sections:
        cargo_start = min(section["z"] for section in cargo_prism_sections)
        transition_end = max(section["z"] for section in transition_prism_sections)
        checks.append(
            {
                "id": "transition_overlaps_cargo",
                "pass": transition_end >= cargo_start - 0.25,
                "value": round(transition_end - cargo_start, 5),
                "description": "transition prism reaches the cargo prism forward section",
            }
        )
        minimum_width = min(min(section["lower_half_width"], section["upper_half_width"]) * 2.0 for section in transition_prism_sections)
        checks.append(
            {
                "id": "transition_minimum_width",
                "pass": minimum_width >= 1.2,
                "value": round(minimum_width, 5),
                "description": "transition prism remains wider than player width plus clearance",
            }
        )
        cargo_forward = min(cargo_prism_sections, key=lambda item: item["z"])
        transition_aft = max(transition_prism_sections, key=lambda item: item["z"])
        floor_delta = abs(transition_aft["bottom"] - cargo_forward["bottom"])
        checks.append(
            {
                "id": "cargo_floor_meets_transition",
                "pass": floor_delta <= 0.35,
                "value": round(floor_delta, 5),
                "description": "cargo forward floor and transition aft floor meet within tolerance",
            }
        )
    else:
        checks.append({"id": "transition_overlaps_cargo", "pass": False, "value": None, "description": "missing cargo or transition prism"})
        checks.append({"id": "transition_minimum_width", "pass": False, "value": None, "description": "missing cargo or transition prism"})
        checks.append({"id": "cargo_floor_meets_transition", "pass": False, "value": None, "description": "missing cargo or transition prism"})

    return {"pass": all(check["pass"] for check in checks), "checks": checks}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bootstrap = load_bootstrap_module()
    points = collect_exterior_vertices()
    boxes = bootstrap.derive_interior_volume_boxes(points)
    cargo_prism_sections = bootstrap.derive_cargo_prism_sections(boxes)
    transition_prism_sections = bootstrap.derive_transition_prism_sections(boxes, cargo_prism_sections)
    connectivity = validate_connectivity(boxes, cargo_prism_sections, transition_prism_sections)
    report = {
        "schema_version": 1,
        "source_blend": str(SOURCE_BLEND.relative_to(ROOT)),
        "method": "sample central fuselage clearance field, derive semantic interior proxies, generate prismatic cargo sections from fitted lower/upper cargo bands",
        "volume_boxes": tuple_payload(boxes),
        "cargo_prism_sections": tuple_payload(cargo_prism_sections),
        "transition_prism_sections": tuple_payload(transition_prism_sections),
        "connectivity": connectivity,
        "notes": [
            "These are planning proxies, not collision and not final interior art.",
            "Boxes are deterministic outputs from exterior shell slice data and threshold constants in bootstrap_prototype_shuttle_scene.py.",
        ],
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    write_projection_png(points, boxes, cargo_prism_sections, transition_prism_sections)
    lines = [
        "# Prototype Shuttle Interior Volume Extraction",
        "",
        "These boxes are deterministic planning proxies derived from exterior mesh slices.",
        "",
        "## Boxes",
        "",
    ]
    for name, box in boxes.items():
        lines.append(f"- {name}: position `{tuple_payload(box['position'])}`, size `{tuple_payload(box['size'])}`")
    lines.extend(["", "## Cargo Prism Sections", ""])
    for index, section in enumerate(cargo_prism_sections):
        lines.append(f"- section {index}: `{tuple_payload(section)}`")
    lines.extend(["", "## Transition Prism Sections", ""])
    for index, section in enumerate(transition_prism_sections):
        lines.append(f"- section {index}: `{tuple_payload(section)}`")
    lines.extend(["", "## Connectivity", "", f"Overall: `{'PASS' if connectivity['pass'] else 'FAIL'}`", ""])
    for check in connectivity["checks"]:
        status = "PASS" if check["pass"] else "FAIL"
        lines.append(f"- {status}: {check['id']} = `{check['value']}` - {check['description']}")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- `{REPORT_JSON.relative_to(ROOT)}`",
            f"- `{REPORT_PNG.relative_to(ROOT)}`",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT_JSON}")
    print(f"Wrote {REPORT_MD}")
    print(f"Wrote {REPORT_PNG}")


if __name__ == "__main__":
    main()
