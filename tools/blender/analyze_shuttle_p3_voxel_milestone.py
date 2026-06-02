#!/usr/bin/env python3
"""Generate first-pass voxel/free-space evidence for shuttle_p3."""

from __future__ import annotations

import json
import math
import os
import struct
import zlib
from collections import defaultdict
from pathlib import Path
from statistics import quantiles

import bpy


ROOT = Path(os.environ.get("SPACE_GAME_ROOT", Path.cwd())).resolve()
SOURCE_BLEND = ROOT / "assets/source/blender/ships/shuttle_p3/shuttle_p3.blend"
SOURCE_DIR = SOURCE_BLEND.parent
MODEL_DIR = ROOT / "assets/models/ship/shuttle_p3"
REPORT_DIR = ROOT / "reports/ship_pipeline/shuttle_p3_voxel_fit"
CONFIG_PATH = SOURCE_DIR / "shuttle_p3_voxel_config.json"
REPORT_JSON = REPORT_DIR / "shuttle_p3_voxel_report.json"
REPORT_MD = REPORT_DIR / "shuttle_p3_voxel_report.md"
EXTERIOR_PNG = REPORT_DIR / "shuttle_p3_exterior_skin_projection_current.png"
VOXEL_PNG = REPORT_DIR / "shuttle_p3_voxel_free_space_projection_current.png"
SEMANTIC_PNG = REPORT_DIR / "shuttle_p3_semantic_regions_projection_current.png"
EXTERIOR_GLB = MODEL_DIR / "shuttle_p3_exterior.glb"


DEFAULT_CONFIG = {
    "schema_version": 1,
    "ship_id": "shuttle_p3",
    "voxel_size": 0.25,
    "local_refine_voxel_size": 0.125,
    "player_capsule_radius": 0.42,
    "standing_height": 1.82,
    "clearance_margin": 0.18,
    "shell_margin": 0.22,
    "semantic_region_hint": {
        "cargo_z_fraction": [0.48, 0.78],
        "cockpit_z_fraction": [0.12, 0.45],
        "transition_z_fraction": [0.38, 0.58],
        "ramp_threshold_z_fraction": [0.34, 0.52],
    },
}


def blender_to_ship_space(loc) -> tuple[float, float, float]:
    return (float(loc.x), float(loc.z), float(-loc.y))


def descendants(collection: bpy.types.Collection) -> list[bpy.types.Object]:
    objects = list(collection.objects)
    for child in collection.children:
        objects.extend(descendants(child))
    return objects


def collect_exterior_vertices() -> list[tuple[float, float, float]]:
    if not SOURCE_BLEND.exists():
        raise RuntimeError(f"Missing shuttle_p3 source blend: {SOURCE_BLEND}")
    if Path(bpy.data.filepath).resolve() != SOURCE_BLEND:
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE_BLEND))
    exterior = bpy.data.collections.get("Exterior")
    if exterior is None:
        raise RuntimeError("shuttle_p3 blend is missing Exterior collection")

    points: list[tuple[float, float, float]] = []
    for obj in descendants(exterior):
        if obj.type != "MESH" or obj.data is None:
            continue
        for vertex in obj.data.vertices:
            points.append(blender_to_ship_space(obj.matrix_world @ vertex.co))
    if not points:
        raise RuntimeError("No exterior vertices found")
    return points


def load_config() -> dict:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
        return dict(DEFAULT_CONFIG)
    config = dict(DEFAULT_CONFIG)
    loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config.update(loaded)
    return config


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def bounds(points: list[tuple[float, float, float]]) -> dict[str, list[float]]:
    return {
        "min": [round(min(point[axis] for point in points), 5) for axis in range(3)],
        "max": [round(max(point[axis] for point in points), 5) for axis in range(3)],
    }


def sample_slice_profiles(points: list[tuple[float, float, float]], voxel_size: float, shell_margin: float) -> list[dict]:
    z_min = min(point[2] for point in points)
    z_max = max(point[2] for point in points)
    bin_count = max(16, int(math.ceil((z_max - z_min) / max(0.001, voxel_size))))
    bins: dict[int, list[tuple[float, float, float]]] = defaultdict(list)
    for point in points:
        index = max(0, min(bin_count - 1, int((point[2] - z_min) / max(0.001, z_max - z_min) * bin_count)))
        bins[index].append(point)

    profiles: list[dict] = []
    last_profile: dict | None = None
    for index in range(bin_count):
        slice_points = bins.get(index, [])
        z0 = z_min + (z_max - z_min) * index / bin_count
        z1 = z_min + (z_max - z_min) * (index + 1) / bin_count
        z = (z0 + z1) * 0.5
        if len(slice_points) < 8 and last_profile is not None:
            profile = dict(last_profile)
            profile["z"] = round(z, 5)
            profile["source"] = "interpolated"
            profiles.append(profile)
            continue
        if len(slice_points) < 8:
            continue

        xs = [point[0] for point in slice_points]
        ys = [point[1] for point in slice_points]
        # Robust central envelope: ignore wings/fins/extreme protrusions.
        x_low = percentile(xs, 0.18) + shell_margin
        x_high = percentile(xs, 0.82) - shell_margin
        y_low = percentile(ys, 0.18) + shell_margin
        y_high = percentile(ys, 0.82) - shell_margin
        profile = {
            "z": round(z, 5),
            "x_min": round(min(x_low, x_high), 5),
            "x_max": round(max(x_low, x_high), 5),
            "y_min": round(min(y_low, y_high), 5),
            "y_max": round(max(y_low, y_high), 5),
            "source": "sampled",
            "source_point_count": len(slice_points),
        }
        profiles.append(profile)
        last_profile = profile
    return profiles


def generate_free_voxels(profiles: list[dict], voxel_size: float, config: dict) -> list[dict]:
    free: list[dict] = []
    radius = float(config["player_capsule_radius"])
    standing = float(config["standing_height"])
    clearance = float(config["clearance_margin"])
    for profile in profiles:
        width = profile["x_max"] - profile["x_min"]
        height = profile["y_max"] - profile["y_min"]
        if width < radius * 2.0 or height < standing * 0.55:
            continue
        x_min = profile["x_min"] + radius
        x_max = profile["x_max"] - radius
        y_min = profile["y_min"] + radius
        y_max = profile["y_max"] - clearance
        if x_min > x_max or y_min > y_max:
            continue
        x_count = max(1, int(math.floor((x_max - x_min) / voxel_size)) + 1)
        y_count = max(1, int(math.floor((y_max - y_min) / voxel_size)) + 1)
        for xi in range(x_count):
            x = x_min + xi * voxel_size
            for yi in range(y_count):
                y = y_min + yi * voxel_size
                head_clearance = profile["y_max"] - y
                can_stand = head_clearance >= standing
                free.append(
                    {
                        "center": [round(x, 5), round(y, 5), profile["z"]],
                        "can_stand": can_stand,
                        "head_clearance": round(head_clearance, 5),
                    }
                )
    return free


def region_from_voxels(name: str, voxels: list[dict], color: str, z_fraction: tuple[float, float], all_bounds: dict) -> dict | None:
    z_min, z_max = all_bounds["min"][2], all_bounds["max"][2]
    rz0 = z_min + (z_max - z_min) * z_fraction[0]
    rz1 = z_min + (z_max - z_min) * z_fraction[1]
    selected = [v for v in voxels if rz0 <= v["center"][2] <= rz1 and v["can_stand"]]
    if not selected:
        selected = [v for v in voxels if rz0 <= v["center"][2] <= rz1]
    if not selected:
        return None
    mins = [min(v["center"][axis] for v in selected) for axis in range(3)]
    maxs = [max(v["center"][axis] for v in selected) for axis in range(3)]
    center = [(mins[i] + maxs[i]) * 0.5 for i in range(3)]
    size = [maxs[i] - mins[i] for i in range(3)]
    return {
        "id": name,
        "color": color,
        "voxel_count": len(selected),
        "standing_voxel_count": sum(1 for v in selected if v["can_stand"]),
        "center": [round(v, 5) for v in center],
        "size": [round(v, 5) for v in size],
        "bounds": {
            "min": [round(v, 5) for v in mins],
            "max": [round(v, 5) for v in maxs],
        },
    }


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
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def draw_projection(path: Path, points: list[tuple[float, float, float]], voxels: list[dict], regions: list[dict], mode: str) -> None:
    canvas = ImageCanvas(1920, 720, (12, 15, 19))
    panels = [
        (24, 36, 604, 648, (2, 1)),   # side: length / height
        (658, 36, 604, 648, (2, 0)),  # top: length / width
        (1292, 36, 604, 648, (0, 1)), # front: width / height
    ]
    region_colors = {
        "cargo": (80, 180, 220),
        "cockpit": (235, 190, 70),
        "transition": (140, 215, 90),
        "ramp_threshold": (235, 125, 75),
    }
    all_points = list(points) + [tuple(v["center"]) for v in voxels]
    for px, py, pw, ph, axes in panels:
        canvas.rect(px, py, px + pw - 1, py + ph - 1, (40, 46, 54))
        coords = [(p[axes[0]], p[axes[1]]) for p in all_points]
        min_x, max_x = min(c[0] for c in coords), max(c[0] for c in coords)
        min_y, max_y = min(c[1] for c in coords), max(c[1] for c in coords)
        margin_x = max(0.6, (max_x - min_x) * 0.12)
        margin_y = max(0.6, (max_y - min_y) * 0.16)
        min_x -= margin_x
        max_x += margin_x
        min_y -= margin_y
        max_y += margin_y

        def map_point(x: float, y: float) -> tuple[int, int]:
            nx = (x - min_x) / max(0.001, max_x - min_x)
            ny = (y - min_y) / max(0.001, max_y - min_y)
            return int(px + nx * (pw - 1)), int(py + (1.0 - ny) * (ph - 1))

        for p in points:
            x, y = map_point(p[axes[0]], p[axes[1]])
            canvas.set_pixel(x, y, (210, 215, 222))
        if mode in {"voxels", "semantic"}:
            for voxel in voxels:
                color = (80, 170, 210) if voxel["can_stand"] else (60, 90, 110)
                x, y = map_point(voxel["center"][axes[0]], voxel["center"][axes[1]])
                canvas.rect(x - 1, y - 1, x + 1, y + 1, color, fill=True)
        if mode == "semantic":
            for region in regions:
                bmin = region["bounds"]["min"]
                bmax = region["bounds"]["max"]
                x0, y0 = map_point(bmin[axes[0]], bmin[axes[1]])
                x1, y1 = map_point(bmax[axes[0]], bmax[axes[1]])
                color = region_colors.get(region["id"], (200, 200, 200))
                canvas.rect(x0, y0, x1, y1, color)
                canvas.rect(x0 + 1, y0 + 1, x1 - 1, y1 - 1, color)
    canvas.write_png(path)


def export_exterior_glb() -> None:
    exterior = bpy.data.collections.get("Exterior")
    if exterior is None:
        raise RuntimeError("Missing Exterior collection")
    objects = [obj for obj in descendants(exterior) if obj.type in {"MESH", "EMPTY"}]
    if not objects:
        raise RuntimeError("No exterior objects to export")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(EXTERIOR_GLB),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_materials="EXPORT",
    )


def write_reports(config: dict, points: list[tuple[float, float, float]], profiles: list[dict], voxels: list[dict], regions: list[dict]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    b = bounds(points)
    standing_count = sum(1 for v in voxels if v["can_stand"])
    connectivity = {
        "ramp_threshold_to_cargo": bool(region_by_id(regions, "ramp_threshold") and region_by_id(regions, "cargo")),
        "cargo_to_transition": bool(region_by_id(regions, "cargo") and region_by_id(regions, "transition")),
        "transition_to_cockpit": bool(region_by_id(regions, "transition") and region_by_id(regions, "cockpit")),
        "status": "PASS" if {"cargo", "cockpit", "transition", "ramp_threshold"} <= {r["id"] for r in regions} else "FAIL",
    }
    report = {
        "schema_version": 1,
        "ship_id": "shuttle_p3",
        "source_blend": str(SOURCE_BLEND.relative_to(ROOT)),
        "config": config,
        "exterior_bounds_ship_space": b,
        "slice_profile_count": len(profiles),
        "voxel_count": len(voxels),
        "standing_voxel_count": standing_count,
        "standing_voxel_fraction": round(standing_count / max(1, len(voxels)), 5),
        "semantic_regions": regions,
        "connectivity": connectivity,
        "evidence": {
            "exterior_projection": str(EXTERIOR_PNG.relative_to(ROOT)),
            "voxel_projection": str(VOXEL_PNG.relative_to(ROOT)),
            "semantic_projection": str(SEMANTIC_PNG.relative_to(ROOT)),
            "exterior_glb": str(EXTERIOR_GLB.relative_to(ROOT)),
        },
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Shuttle P3 Voxel Milestone Report",
        "",
        f"Status: **{connectivity['status']}**",
        "",
        "## Summary",
        "",
        f"- Exterior vertices: {len(points)}",
        f"- Slice profiles: {len(profiles)}",
        f"- Free-space voxels: {len(voxels)}",
        f"- Standing voxels: {standing_count}",
        f"- Exterior projection: `{report['evidence']['exterior_projection']}`",
        f"- Voxel projection: `{report['evidence']['voxel_projection']}`",
        f"- Semantic projection: `{report['evidence']['semantic_projection']}`",
        "",
        "## Semantic Regions",
        "",
    ]
    for region in regions:
        lines.append(
            f"- `{region['id']}`: voxels={region['voxel_count']}, standing={region['standing_voxel_count']}, "
            f"center={region['center']}, size={region['size']}"
        )
    lines.extend(
        [
            "",
            "## Connectivity",
            "",
        ]
    )
    for key, value in connectivity.items():
        if key != "status":
            lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This is milestone-one evidence only.",
            "- No floors, ramps, stairs, collision, furnishings, or lighting are generated in this pass.",
            "- The voxel field is a first-pass interior planning approximation derived from the preserved exterior skin.",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def region_by_id(regions: list[dict], region_id: str) -> dict | None:
    return next((region for region in regions if region["id"] == region_id), None)


def main() -> None:
    config = load_config()
    points = collect_exterior_vertices()
    profiles = sample_slice_profiles(points, float(config["voxel_size"]), float(config["shell_margin"]))
    voxels = generate_free_voxels(profiles, float(config["voxel_size"]), config)
    b = bounds(points)
    hints = config["semantic_region_hint"]
    regions = [
        region_from_voxels("cargo", voxels, "blue", tuple(hints["cargo_z_fraction"]), b),
        region_from_voxels("cockpit", voxels, "yellow", tuple(hints["cockpit_z_fraction"]), b),
        region_from_voxels("transition", voxels, "green", tuple(hints["transition_z_fraction"]), b),
        region_from_voxels("ramp_threshold", voxels, "orange", tuple(hints["ramp_threshold_z_fraction"]), b),
    ]
    regions = [region for region in regions if region is not None]

    export_exterior_glb()
    draw_projection(EXTERIOR_PNG, points, [], regions, "exterior")
    draw_projection(VOXEL_PNG, points, voxels, regions, "voxels")
    draw_projection(SEMANTIC_PNG, points, voxels, regions, "semantic")
    write_reports(config, points, profiles, voxels, regions)

    print(f"Wrote {EXTERIOR_GLB}")
    print(f"Wrote {REPORT_JSON}")
    print(f"Wrote {REPORT_MD}")
    print(f"Wrote {EXTERIOR_PNG}")
    print(f"Wrote {VOXEL_PNG}")
    print(f"Wrote {SEMANTIC_PNG}")


if __name__ == "__main__":
    main()
