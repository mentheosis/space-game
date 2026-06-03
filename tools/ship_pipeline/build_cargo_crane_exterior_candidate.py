#!/usr/bin/env python3
"""Build CargoCrane exterior-only candidate and review evidence from OGA OBJ."""

from __future__ import annotations

import argparse
import json
import math
import struct
import zlib
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / "assets/models/ship/placeholders/oga_3d_space_ship_pack"
SOURCE_OBJ = SOURCE_DIR / "CargoCrane.obj"
OUT_MODEL_DIR = ROOT / "assets/models/ship/cargo_crane"
OUT_SOURCE_DIR = ROOT / "assets/source/blender/ships/cargo_crane"
OUT_REPORT_DIR = ROOT / "reports/ship_pipeline/cargo_crane_voxel_fit"
OUT_GLB = OUT_MODEL_DIR / "cargo_crane_exterior.glb"
MANIFEST_PATH = OUT_SOURCE_DIR / "cargo_crane_source_manifest.json"
REPORT_JSON = OUT_REPORT_DIR / "cargo_crane_exterior_candidate_report.json"
REPORT_MD = OUT_REPORT_DIR / "cargo_crane_exterior_candidate_report.md"
PROJECTION_PNG = OUT_REPORT_DIR / "cargo_crane_exterior_reference_projection_current.png"

PROVISIONAL_SCALE = 1.4
MATERIAL_COLORS = {
    "Hull": [0.74, 0.76, 0.78, 1.0],
    "Accent": [0.12, 0.13, 0.15, 1.0],
    "Cockpit": [0.03, 0.09, 0.15, 0.92],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-obj", type=Path, default=SOURCE_OBJ)
    parser.add_argument("--scale", type=float, default=PROVISIONAL_SCALE)
    return parser.parse_args()


def parse_mtl(path: Path) -> dict[str, dict[str, object]]:
    materials: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    if not path.exists():
        return materials
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0] == "newmtl" and len(parts) >= 2:
            current = {"name": parts[1]}
            materials[parts[1]] = current
        elif current is not None and parts[0] == "Kd" and len(parts) >= 4:
            current["base_color"] = [float(parts[1]), float(parts[2]), float(parts[3]), 1.0]
        elif current is not None and parts[0] == "d" and len(parts) >= 2:
            color = current.setdefault("base_color", [1.0, 1.0, 1.0, 1.0])
            color[3] = float(parts[1])
    for name, color in MATERIAL_COLORS.items():
        materials.setdefault(name, {"name": name})["base_color"] = color
    return materials


def parse_obj(path: Path) -> tuple[list[tuple[float, float, float]], dict[str, list[list[tuple[int, int | None]]]], Path | None]:
    vertices: list[tuple[float, float, float]] = []
    normals: list[tuple[float, float, float]] = []
    groups: dict[str, list[list[tuple[int, int | None]]]] = defaultdict(list)
    material = "Default"
    mtl_path: Path | None = None

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0] == "mtllib" and len(parts) >= 2:
            mtl_path = path.parent / parts[1]
        elif parts[0] == "v" and len(parts) >= 4:
            vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif parts[0] == "vn" and len(parts) >= 4:
            normals.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif parts[0] == "usemtl" and len(parts) >= 2:
            material = parts[1]
        elif parts[0] == "f" and len(parts) >= 4:
            face = []
            for token in parts[1:]:
                fields = token.split("/")
                vi = int(fields[0])
                if vi < 0:
                    vi = len(vertices) + vi + 1
                ni = None
                if len(fields) >= 3 and fields[2]:
                    ni = int(fields[2])
                    if ni < 0:
                        ni = len(normals) + ni + 1
                face.append((vi - 1, ni - 1 if ni is not None else None))
            groups[material].append(face)
    if normals:
        setattr(parse_obj, "normals", normals)
    else:
        setattr(parse_obj, "normals", [])
    return vertices, groups, mtl_path


def bounds(points: list[tuple[float, float, float]]) -> dict[str, list[float]]:
    return {
        "min": [min(point[index] for point in points) for index in range(3)],
        "max": [max(point[index] for point in points) for index in range(3)],
    }


def transformed(point: tuple[float, float, float], source_center: list[float], scale: float) -> tuple[float, float, float]:
    return (
        (point[0] - source_center[0]) * scale,
        (point[1] - source_center[1]) * scale,
        (point[2] - source_center[2]) * scale,
    )


def normal_for(a: tuple[float, float, float], b: tuple[float, float, float], c: tuple[float, float, float]) -> tuple[float, float, float]:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length <= 0.000001:
        return (0.0, 1.0, 0.0)
    return (nx / length, ny / length, nz / length)


def pad4(data: bytes, pad: bytes = b"\x00") -> bytes:
    return data + pad * ((4 - len(data) % 4) % 4)


def make_accessor(gltf: dict, blob: bytearray, data: bytes, component_type: int, count: int, type_name: str, mins=None, maxs=None) -> int:
    offset = len(blob)
    blob.extend(pad4(data))
    view_index = len(gltf["bufferViews"])
    gltf["bufferViews"].append({"buffer": 0, "byteOffset": offset, "byteLength": len(data)})
    accessor = {"bufferView": view_index, "componentType": component_type, "count": count, "type": type_name}
    if mins is not None:
        accessor["min"] = mins
    if maxs is not None:
        accessor["max"] = maxs
    gltf["accessors"].append(accessor)
    return len(gltf["accessors"]) - 1


def build_glb(
    out_path: Path,
    vertices: list[tuple[float, float, float]],
    groups: dict[str, list[list[tuple[int, int | None]]]],
    materials: dict[str, dict[str, object]],
    scale: float,
) -> dict[str, object]:
    source_bounds = bounds(vertices)
    source_center = [(source_bounds["min"][i] + source_bounds["max"][i]) * 0.5 for i in range(3)]
    normals = getattr(parse_obj, "normals", [])

    gltf = {
        "asset": {"version": "2.0", "generator": "build_cargo_crane_exterior_candidate.py"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": "cargo_crane_exterior", "mesh": 0}],
        "meshes": [{"name": "cargo_crane_exterior_mesh", "primitives": []}],
        "materials": [],
        "buffers": [{"byteLength": 0}],
        "bufferViews": [],
        "accessors": [],
    }
    material_indices = {}
    for name in sorted(groups):
        color = materials.get(name, {}).get("base_color", MATERIAL_COLORS.get(name, [0.8, 0.8, 0.8, 1.0]))
        material_indices[name] = len(gltf["materials"])
        gltf["materials"].append(
            {
                "name": name,
                "pbrMetallicRoughness": {"baseColorFactor": color, "metallicFactor": 0.0, "roughnessFactor": 0.62},
            }
        )

    blob = bytearray()
    all_points: list[tuple[float, float, float]] = []
    primitive_counts: dict[str, int] = {}
    for material_name, faces in sorted(groups.items()):
        positions: list[tuple[float, float, float]] = []
        out_normals: list[tuple[float, float, float]] = []
        for face in faces:
            for start in range(1, len(face) - 1):
                tri = [face[0], face[start], face[start + 1]]
                tri_positions = [transformed(vertices[vi], source_center, scale) for vi, _ in tri]
                fallback_normal = normal_for(*tri_positions)
                for (vi, ni), point in zip(tri, tri_positions):
                    positions.append(point)
                    if ni is not None and 0 <= ni < len(normals):
                        out_normals.append(normals[ni])
                    else:
                        out_normals.append(fallback_normal)
        if not positions:
            continue
        all_points.extend(positions)
        primitive_counts[material_name] = len(positions) // 3
        pos_bytes = b"".join(struct.pack("<fff", *point) for point in positions)
        norm_bytes = b"".join(struct.pack("<fff", *point) for point in out_normals)
        prim_bounds = bounds(positions)
        position_accessor = make_accessor(
            gltf,
            blob,
            pos_bytes,
            5126,
            len(positions),
            "VEC3",
            [round(value, 6) for value in prim_bounds["min"]],
            [round(value, 6) for value in prim_bounds["max"]],
        )
        normal_accessor = make_accessor(gltf, blob, norm_bytes, 5126, len(out_normals), "VEC3")
        gltf["meshes"][0]["primitives"].append(
            {
                "attributes": {"POSITION": position_accessor, "NORMAL": normal_accessor},
                "material": material_indices[material_name],
                "mode": 4,
            }
        )
    gltf["buffers"][0]["byteLength"] = len(blob)
    json_chunk = pad4(json.dumps(gltf, separators=(",", ":")).encode("utf-8"), b" ")
    bin_chunk = pad4(bytes(blob))
    total_length = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(
        b"glTF"
        + struct.pack("<II", 2, total_length)
        + struct.pack("<II", len(json_chunk), 0x4E4F534A)
        + json_chunk
        + struct.pack("<II", len(bin_chunk), 0x004E4942)
        + bin_chunk
    )
    candidate_bounds = bounds(all_points)
    return {
        "source_bounds": source_bounds,
        "source_center": source_center,
        "candidate_bounds": candidate_bounds,
        "source_dimensions": [source_bounds["max"][i] - source_bounds["min"][i] for i in range(3)],
        "candidate_dimensions_m": [candidate_bounds["max"][i] - candidate_bounds["min"][i] for i in range(3)],
        "triangle_count_by_material": primitive_counts,
        "triangle_count": sum(primitive_counts.values()),
    }


def write_png(path: Path, width: int, height: int, pixels: list[list[tuple[int, int, int]]]) -> None:
    raw = bytearray()
    for row in pixels:
        raw.append(0)
        for r, g, b in row:
            raw.extend((r, g, b))
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def draw_line(pixels: list[list[tuple[int, int, int]]], a: tuple[int, int], b: tuple[int, int], color: tuple[int, int, int]) -> None:
    x0, y0 = a
    x1, y1 = b
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        if 0 <= y0 < len(pixels) and 0 <= x0 < len(pixels[0]):
            pixels[y0][x0] = color
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def render_projection(
    path: Path,
    vertices: list[tuple[float, float, float]],
    groups: dict[str, list[list[tuple[int, int | None]]]],
    scale: float,
    stats: dict[str, object],
) -> None:
    width, height = 1600, 1100
    pixels = [[(250, 250, 248) for _ in range(width)] for _ in range(height)]
    source_center = stats["source_center"]
    transformed_vertices = [transformed(point, source_center, scale) for point in vertices]
    panel_specs = [
        ("Top X/Z", (80, 70, 700, 480), (0, 2)),
        ("Side Z/Y", (850, 70, 1520, 480), (2, 1)),
        ("Front X/Y", (420, 600, 1180, 1010), (0, 1)),
    ]
    bounds_data = bounds(transformed_vertices)
    dims = [bounds_data["max"][i] - bounds_data["min"][i] for i in range(3)]
    colors = {"Hull": (154, 160, 166), "Accent": (32, 35, 39), "Cockpit": (15, 82, 132)}

    def text(x: int, y: int, value: str, color=(20, 20, 20)) -> None:
        # Tiny block text substitute: draw readable labels as metadata bars.
        for offset, byte in enumerate(value.encode("ascii", errors="replace")[:90]):
            bits = byte
            for bit in range(7):
                if bits & (1 << bit):
                    px = x + offset * 5 + bit % 3
                    py = y + bit // 3
                    if 0 <= py < height and 0 <= px < width:
                        pixels[py][px] = color

    for title, rect, axes in panel_specs:
        x0, y0, x1, y1 = rect
        for x in range(x0, x1 + 1):
            pixels[y0][x] = (208, 208, 208)
            pixels[y1][x] = (208, 208, 208)
        for y in range(y0, y1 + 1):
            pixels[y][x0] = (208, 208, 208)
            pixels[y][x1] = (208, 208, 208)
        text(x0, y0 - 22, title)
        axis_min = [bounds_data["min"][axis] for axis in axes]
        axis_max = [bounds_data["max"][axis] for axis in axes]
        pad = 0.08
        span = max(axis_max[0] - axis_min[0], axis_max[1] - axis_min[1])
        cx = (axis_min[0] + axis_max[0]) * 0.5
        cy = (axis_min[1] + axis_max[1]) * 0.5
        axis_min = [cx - span * (0.5 + pad), cy - span * (0.5 + pad)]
        axis_max = [cx + span * (0.5 + pad), cy + span * (0.5 + pad)]

        def project(point: tuple[float, float, float]) -> tuple[int, int]:
            px = x0 + int((point[axes[0]] - axis_min[0]) / (axis_max[0] - axis_min[0]) * (x1 - x0))
            py = y1 - int((point[axes[1]] - axis_min[1]) / (axis_max[1] - axis_min[1]) * (y1 - y0))
            return px, py

        for material_name, faces in groups.items():
            color = colors.get(material_name, (94, 94, 94))
            for face in faces:
                points = [project(transformed_vertices[vi]) for vi, _ in face]
                for index, point in enumerate(points):
                    draw_line(pixels, point, points[(index + 1) % len(points)], color)

    text(80, 1035, f"CargoCrane exterior candidate scale={scale:.3f}; dims m x/y/z={dims[0]:.2f}/{dims[1]:.2f}/{dims[2]:.2f}; source +Z cockpit/forward evidence")
    write_png(path, width, height, pixels)


def write_reports(args: argparse.Namespace, stats: dict[str, object], materials: dict[str, dict[str, object]]) -> None:
    OUT_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "ship_id": "cargo_crane",
        "source": {
            "asset": "OpenGameArt 3D Space Ship Pack",
            "author": "anaxarch",
            "license": "CC0",
            "url": "https://opengameart.org/content/3d-space-ship-pack",
            "obj": str(args.source_obj.relative_to(ROOT)),
            "mtl": str((args.source_obj.parent / "CargoCrane.mtl").relative_to(ROOT)),
        },
        "candidate": {
            "glb": str(OUT_GLB.relative_to(ROOT)),
            "provisional_scale": args.scale,
            "transform": "center source bounds on ship local origin; preserve source axes; source +Z is cockpit/forward candidate",
            "status": "exterior-only review candidate; scale/orientation not locked until human approval",
        },
        "materials": sorted(materials),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    report = {
        "schema_version": 1,
        "ship_id": "cargo_crane",
        "status": "needs_human_exterior_approval",
        "source_obj": str(args.source_obj.relative_to(ROOT)),
        "output_glb": str(OUT_GLB.relative_to(ROOT)),
        "reference_projection": str(PROJECTION_PNG.relative_to(ROOT)),
        "provisional_scale": args.scale,
        **stats,
        "orientation_evidence": {
            "source_cockpit_material_z_span": "Cockpit material is concentrated near source +Z, so +Z is the forward candidate.",
            "up_candidate": "Source +Y is treated as up for the provisional GLB.",
        },
        "approval_questions": [
            "Approve or revise overall scale.",
            "Approve or revise forward/up orientation.",
            "Choose entry hatch/ramp location.",
            "Choose one or two levels.",
            "Choose cockpit seat count.",
            "Define cargo/living/corridor roles.",
            "Confirm whether hull cutting is acceptable and where.",
        ],
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    dims = stats["candidate_dimensions_m"]
    lines = [
        "# CargoCrane Exterior Candidate Report",
        "",
        "Status: exterior-only review candidate. Scale and orientation are not locked.",
        "",
        f"- Source OBJ: `{args.source_obj.relative_to(ROOT)}`",
        f"- Output GLB: `{OUT_GLB.relative_to(ROOT)}`",
        f"- Provisional scale: `{args.scale}`",
        f"- Candidate dimensions: `{dims[0]:.2f}m wide x {dims[1]:.2f}m tall x {dims[2]:.2f}m long`",
        f"- Triangle count: `{stats['triangle_count']}`",
        "- Provisional orientation: source `+Y` up, source `+Z` forward/cockpit end.",
        "",
        "Human approval required before interior layout contract:",
        "",
        "1. Overall scale.",
        "2. Intended forward/up orientation.",
        "3. Entry hatch/ramp location.",
        "4. One or two interior levels.",
        "5. Cockpit seat count.",
        "6. Cargo/living/corridor roles.",
        "7. Whether hull cutting is acceptable and where.",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    if not args.source_obj.exists():
        raise FileNotFoundError(args.source_obj)
    vertices, groups, mtl_path = parse_obj(args.source_obj)
    materials = parse_mtl(mtl_path) if mtl_path else {}
    stats = build_glb(OUT_GLB, vertices, groups, materials, args.scale)
    render_projection(PROJECTION_PNG, vertices, groups, args.scale, stats)
    write_reports(args, stats, materials)
    print(f"Wrote {OUT_GLB.relative_to(ROOT)}")
    print(f"Wrote {REPORT_MD.relative_to(ROOT)}")
    print(f"Wrote {PROJECTION_PNG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
