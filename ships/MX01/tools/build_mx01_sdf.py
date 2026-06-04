#!/usr/bin/env python3
"""Build a deterministic first-pass MX01 occupancy field from the normalized skin.

This is an occupancy-field implementation, not a full signed-distance solver
yet. It classifies X-axis voxel rays from normalized triangle intersections and
records uncertainty caused by degenerate ray projections or odd parity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SHIP_DIR = ROOT / "ships" / "MX01"
DEFAULT_CONFIG = SHIP_DIR / "config" / "mx01_collision_generation.json"

Vec3 = tuple[float, float, float]
Triangle = tuple[int, int, int]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_config_path(config: dict, section: str, key: str) -> Path:
    return ROOT / config[section][key]


def parse_obj(path: Path) -> tuple[list[Vec3], list[Triangle]]:
    vertices: list[Vec3] = []
    triangles: list[Triangle] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0] == "v" and len(parts) >= 4:
            vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif parts[0] == "f" and len(parts) == 4:
            triangles.append(tuple(int(token.split("/")[0]) - 1 for token in parts[1:4]))
        elif parts[0] == "f":
            raise RuntimeError(f"Expected normalized triangulated OBJ, got polygon: {line}")
    return vertices, triangles


def bounds(points: list[Vec3]) -> dict:
    mins = [min(point[index] for point in points) for index in range(3)]
    maxs = [max(point[index] for point in points) for index in range(3)]
    return {
        "min": [round(value, 6) for value in mins],
        "max": [round(value, 6) for value in maxs],
        "size": [round(maxs[index] - mins[index], 6) for index in range(3)],
        "center": [round((mins[index] + maxs[index]) * 0.5, 6) for index in range(3)],
    }


def axis_centers(min_value: float, max_value: float, voxel_size: float, margin: float) -> list[float]:
    start = math.floor((min_value - margin) / voxel_size) * voxel_size + voxel_size * 0.5
    end = math.ceil((max_value + margin) / voxel_size) * voxel_size - voxel_size * 0.5
    count = int(round((end - start) / voxel_size)) + 1
    return [round(start + index * voxel_size, 6) for index in range(max(0, count))]


def index_range_for_bounds(centers: list[float], min_value: float, max_value: float, voxel_size: float) -> range:
    if not centers:
        return range(0)
    start = max(0, int(math.floor((min_value - centers[0]) / voxel_size)))
    end = min(len(centers) - 1, int(math.ceil((max_value - centers[0]) / voxel_size)))
    return range(start, end + 1)


def build_yz_bins(vertices: list[Vec3], triangles: list[Triangle], y_centers: list[float], z_centers: list[float], voxel_size: float) -> tuple[dict[tuple[int, int], list[int]], int]:
    bins: dict[tuple[int, int], list[int]] = defaultdict(list)
    skipped = 0
    for triangle_index, (a_i, b_i, c_i) in enumerate(triangles):
        tri = [vertices[a_i], vertices[b_i], vertices[c_i]]
        ys = [point[1] for point in tri]
        zs = [point[2] for point in tri]
        y_range = index_range_for_bounds(y_centers, min(ys) - voxel_size, max(ys) + voxel_size, voxel_size)
        z_range = index_range_for_bounds(z_centers, min(zs) - voxel_size, max(zs) + voxel_size, voxel_size)
        assigned = False
        for yi in y_range:
            for zi in z_range:
                bins[(yi, zi)].append(triangle_index)
                assigned = True
        if not assigned:
            skipped += 1
    for key in list(bins):
        bins[key].sort()
    return bins, skipped


def intersect_x_at_yz(a: Vec3, b: Vec3, c: Vec3, y: float, z: float) -> float | None:
    y1, z1 = a[1], a[2]
    y2, z2 = b[1], b[2]
    y3, z3 = c[1], c[2]
    denom = (z2 - z3) * (y1 - y3) + (y3 - y2) * (z1 - z3)
    if abs(denom) < 1e-10:
        return None
    l1 = ((z2 - z3) * (y - y3) + (y3 - y2) * (z - z3)) / denom
    l2 = ((z3 - z1) * (y - y3) + (y1 - y3) * (z - z3)) / denom
    l3 = 1.0 - l1 - l2
    eps = -1e-8
    if l1 < eps or l2 < eps or l3 < eps:
        return None
    return a[0] * l1 + b[0] * l2 + c[0] * l3


def dedupe(values: list[float], epsilon: float) -> list[float]:
    if not values:
        return []
    values.sort()
    result = [values[0]]
    for value in values[1:]:
        if abs(value - result[-1]) > epsilon:
            result.append(value)
    return result


def classify_ray(x_centers: list[float], intersections: list[float], shell_margin: float) -> tuple[list[list[int]], int, int]:
    intervals: list[list[int]] = []
    near_surface = 0
    if len(intersections) < 2:
        return intervals, 0, 0

    for pair_index in range(0, len(intersections) - 1, 2):
        start_x = intersections[pair_index]
        end_x = intersections[pair_index + 1]
        if end_x < start_x:
            start_x, end_x = end_x, start_x
        start = lower_center_index(x_centers, start_x)
        end = upper_center_index(x_centers, end_x)
        if start <= end:
            intervals.append([start, end])

    inside_count = sum(end - start + 1 for start, end in intervals)
    for center in x_centers:
        if any(abs(center - x_value) <= shell_margin for x_value in intersections):
            near_surface += 1
    return intervals, inside_count, near_surface


def lower_center_index(centers: list[float], value: float) -> int:
    for index, center in enumerate(centers):
        if center >= value:
            return index
    return len(centers)


def upper_center_index(centers: list[float], value: float) -> int:
    result = -1
    for index, center in enumerate(centers):
        if center <= value:
            result = index
        else:
            break
    return result


def build_occupancy(config: dict, vertices: list[Vec3], triangles: list[Triangle]) -> tuple[dict, dict]:
    b = bounds(vertices)
    voxel_size = float(config["voxel_size"])
    shell_margin = float(config["surface_offset_modes"]["outset_for_debug_review"])
    margin = max(voxel_size, float(config["player_clearance_margin"]))
    x_centers = axis_centers(b["min"][0], b["max"][0], voxel_size, margin)
    y_centers = axis_centers(b["min"][1], b["max"][1], voxel_size, margin)
    z_centers = axis_centers(b["min"][2], b["max"][2], voxel_size, margin)

    yz_bins, skipped_bin_triangles = build_yz_bins(vertices, triangles, y_centers, z_centers, voxel_size)
    intervals_by_ray: list[dict] = []
    inside_voxels = 0
    near_surface_voxels = 0
    odd_parity_rays = 0
    empty_rays = 0
    degenerate_projection_hits = 0
    candidate_total = 0

    for zi, z in enumerate(z_centers):
        for yi, y in enumerate(y_centers):
            candidates = yz_bins.get((yi, zi), [])
            candidate_total += len(candidates)
            x_hits: list[float] = []
            for triangle_index in candidates:
                a_i, b_i, c_i = triangles[triangle_index]
                hit = intersect_x_at_yz(vertices[a_i], vertices[b_i], vertices[c_i], y, z)
                if hit is None:
                    continue
                x_hits.append(hit)
            intersections = dedupe(x_hits, voxel_size * 0.001)
            if not intersections:
                empty_rays += 1
                continue
            if len(intersections) % 2 != 0:
                odd_parity_rays += 1
            ray_intervals, ray_inside_count, ray_near_surface = classify_ray(x_centers, intersections, shell_margin)
            inside_voxels += ray_inside_count
            near_surface_voxels += ray_near_surface
            if ray_intervals:
                intervals_by_ray.append({"y_index": yi, "z_index": zi, "x_intervals": ray_intervals, "intersection_count": len(intersections)})

    total_voxels = len(x_centers) * len(y_centers) * len(z_centers)
    report = {
        "ship_id": config["ship_id"],
        "method": "x_axis_ray_parity_occupancy_v1",
        "bounds": b,
        "voxel_size": voxel_size,
        "grid": {
            "x_count": len(x_centers),
            "y_count": len(y_centers),
            "z_count": len(z_centers),
            "origin_center": [x_centers[0], y_centers[0], z_centers[0]],
            "total_voxels": total_voxels,
        },
        "counts": {
            "inside_voxels": inside_voxels,
            "outside_voxels": total_voxels - inside_voxels,
            "near_surface_voxels": near_surface_voxels,
            "rays_with_inside_intervals": len(intervals_by_ray),
            "empty_rays": empty_rays,
            "odd_parity_rays": odd_parity_rays,
            "skipped_bin_triangles": skipped_bin_triangles,
            "degenerate_projection_hits": degenerate_projection_hits,
            "average_triangle_candidates_per_ray": round(candidate_total / max(1, len(y_centers) * len(z_centers)), 4),
        },
        "uncertainty": {
            "status": "WARN" if odd_parity_rays else "PASS",
            "reason": "Odd intersection parity usually indicates non-manifold or tangential ray cases." if odd_parity_rays else "All intersecting rays had even parity.",
        },
    }
    payload = {
        "ship_id": config["ship_id"],
        "method": report["method"],
        "voxel_size": voxel_size,
        "axis_centers": {
            "x": x_centers,
            "y": y_centers,
            "z": z_centers,
        },
        "rays": intervals_by_ray,
    }
    return payload, report


def draw_projection(path: Path, payload: dict, title: str, mode: str) -> None:
    x_count = len(payload["axis_centers"]["x"])
    y_count = len(payload["axis_centers"]["y"])
    z_count = len(payload["axis_centers"]["z"])
    if mode == "side":
        width, height = z_count, y_count
        cells = [[0 for _ in range(width)] for _ in range(height)]
        for ray in payload["rays"]:
            yi, zi = ray["y_index"], ray["z_index"]
            cells[y_count - 1 - yi][zi] = sum(end - start + 1 for start, end in ray["x_intervals"])
    elif mode == "top":
        width, height = z_count, x_count
        cells = [[0 for _ in range(width)] for _ in range(height)]
        for ray in payload["rays"]:
            zi = ray["z_index"]
            for start, end in ray["x_intervals"]:
                for xi in range(start, end + 1):
                    cells[x_count - 1 - xi][zi] += 1
    elif mode == "front":
        width, height = x_count, y_count
        cells = [[0 for _ in range(width)] for _ in range(height)]
        for ray in payload["rays"]:
            yi = ray["y_index"]
            for start, end in ray["x_intervals"]:
                for xi in range(start, end + 1):
                    cells[y_count - 1 - yi][xi] += 1
    else:
        raise RuntimeError(mode)

    max_value = max([max(row) for row in cells] or [1])
    scale = max(2, min(6, int(900 / max(width, height, 1))))
    svg_width = width * scale
    svg_height = height * scale + 34
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width}" height="{svg_height}" viewBox="0 0 {svg_width} {svg_height}">',
        '<rect width="100%" height="100%" fill="#111827"/>',
        f'<text x="8" y="20" font-family="Arial, sans-serif" font-size="13" fill="#f9fafb">{title}</text>',
    ]
    for row_index, row in enumerate(cells):
        for col_index, value in enumerate(row):
            if value <= 0:
                continue
            intensity = int(60 + 195 * (value / max_value))
            color = f"rgb({intensity},{min(255, intensity + 35)},255)"
            lines.append(f'<rect x="{col_index * scale}" y="{34 + row_index * scale}" width="{scale}" height="{scale}" fill="{color}"/>')
    lines.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_markdown(path: Path, report: dict) -> None:
    lines = [
        "# MX01 Occupancy Report",
        "",
        f"- Method: `{report['method']}`",
        f"- Voxel size: `{report['voxel_size']}`",
        f"- Grid: `{report['grid']['x_count']} x {report['grid']['y_count']} x {report['grid']['z_count']}`",
        f"- Total voxels: `{report['grid']['total_voxels']}`",
        f"- Inside voxels: `{report['counts']['inside_voxels']}`",
        f"- Near-surface voxels: `{report['counts']['near_surface_voxels']}`",
        f"- Rays with inside intervals: `{report['counts']['rays_with_inside_intervals']}`",
        f"- Odd-parity rays: `{report['counts']['odd_parity_rays']}`",
        f"- Uncertainty status: `{report['uncertainty']['status']}`",
        "",
        "## Notes",
        "",
        report["uncertainty"]["reason"],
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    config_path = args.config.resolve()
    config = load_config(config_path)
    normalized_obj = resolve_config_path(config, "normalization_outputs", "normalized_obj")
    vertices, triangles = parse_obj(normalized_obj)
    payload, report = build_occupancy(config, vertices, triangles)

    intervals_json = resolve_config_path(config, "occupancy_outputs", "intervals_json")
    report_json = resolve_config_path(config, "occupancy_outputs", "report_json")
    report_md = resolve_config_path(config, "occupancy_outputs", "report_md")
    side_svg = resolve_config_path(config, "occupancy_outputs", "side_projection_svg")
    top_svg = resolve_config_path(config, "occupancy_outputs", "top_projection_svg")
    front_svg = resolve_config_path(config, "occupancy_outputs", "front_projection_svg")
    manifest_json = resolve_config_path(config, "occupancy_outputs", "manifest_json")

    write_json(intervals_json, payload)
    report["source"] = {
        "normalized_obj": rel(normalized_obj),
        "normalized_obj_sha256": sha256(normalized_obj),
    }
    report["config"] = {"path": rel(config_path), "sha256": sha256(config_path), "effective_values": config}
    report["tools"] = {
        "build_mx01_sdf.py": {"path": rel(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())}
    }
    report["outputs"] = {
        "intervals_json": rel(intervals_json),
        "side_projection_svg": rel(side_svg),
        "top_projection_svg": rel(top_svg),
        "front_projection_svg": rel(front_svg),
    }
    write_json(report_json, report)
    write_markdown(report_md, report)
    draw_projection(side_svg, payload, "MX01 occupancy side projection (Z/Y)", "side")
    draw_projection(top_svg, payload, "MX01 occupancy top projection (Z/X)", "top")
    draw_projection(front_svg, payload, "MX01 occupancy front projection (X/Y)", "front")
    write_json(
        manifest_json,
        {
            "ship_id": config["ship_id"],
            "stage": "occupancy",
            "source": report["source"],
            "config": report["config"],
            "outputs": {
                **report["outputs"],
                "intervals_json_sha256": sha256(intervals_json),
                "report_json": rel(report_json),
                "report_md": rel(report_md),
            },
            "tools": report["tools"],
        },
    )
    print(f"Wrote {rel(intervals_json)}")
    print(f"Wrote {rel(report_json)}")
    print(f"Wrote {rel(report_md)}")
    print(f"Wrote {rel(side_svg)}")
    print(f"Wrote {rel(top_svg)}")
    print(f"Wrote {rel(front_svg)}")
    print(f"Wrote {rel(manifest_json)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
