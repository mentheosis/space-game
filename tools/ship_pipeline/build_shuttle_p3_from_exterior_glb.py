#!/usr/bin/env python3
"""Build shuttle_p3 milestone-one evidence from the accepted exterior GLB skin."""

from __future__ import annotations

import argparse
import heapq
import json
import math
import shutil
import struct
import zlib
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_GLB = ROOT / "assets/models/ship/prototype_shuttle/prototype_shuttle_exterior.glb"
OUT_MODEL_DIR = ROOT / "assets/models/ship/shuttle_p3"
OUT_SOURCE_DIR = ROOT / "assets/source/blender/ships/shuttle_p3"
OUT_REPORT_DIR = ROOT / "reports/ship_pipeline/shuttle_p3_voxel_fit"
OUT_GLB = OUT_MODEL_DIR / "shuttle_p3_exterior.glb"
CONFIG_PATH = OUT_SOURCE_DIR / "shuttle_p3_voxel_config.json"
MANIFEST_PATH = OUT_SOURCE_DIR / "shuttle_p3_source_manifest.json"
REPORT_JSON = OUT_REPORT_DIR / "shuttle_p3_voxel_report.json"
REPORT_MD = OUT_REPORT_DIR / "shuttle_p3_voxel_report.md"
EXTERIOR_PNG = OUT_REPORT_DIR / "shuttle_p3_exterior_skin_projection_current.png"
VOXEL_PNG = OUT_REPORT_DIR / "shuttle_p3_voxel_free_space_projection_current.png"
SEMANTIC_PNG = OUT_REPORT_DIR / "shuttle_p3_semantic_regions_projection_current.png"
TRAVERSAL_PNG = OUT_REPORT_DIR / "shuttle_p3_voxel_traversal_projection_current.png"

DEFAULT_CONFIG = {
    "schema_version": 1,
    "ship_id": "shuttle_p3",
    "source_skin": "assets/models/ship/prototype_shuttle/prototype_shuttle_exterior.glb",
    "voxel_size": 0.25,
    "local_refine_voxel_size": 0.125,
    "player_capsule_radius": 0.42,
    "standing_height": 1.82,
    "clearance_margin": 0.18,
    "shell_margin": 0.22,
    "central_x_quantiles": [0.34, 0.66],
    "central_y_quantiles": [0.18, 0.82],
    "traversal": {
        "max_step_height": 0.38,
        "max_neighbor_distance": 0.38,
        "vertical_cost_scale": 2.0,
    },
    "semantic_region_hint": {
        "cargo_z_fraction": [0.44, 0.82],
        "cockpit_z_fraction": [0.10, 0.42],
        "transition_z_fraction": [0.34, 0.56],
        "ramp_threshold_z_fraction": [0.30, 0.48],
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-glb", type=Path, default=SOURCE_GLB)
    return parser.parse_args()


def load_config() -> dict:
    OUT_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        config = json.loads(json.dumps(DEFAULT_CONFIG))
        loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        for key, value in loaded.items():
            if isinstance(value, dict) and isinstance(config.get(key), dict):
                config[key].update(value)
            else:
                config[key] = value
        return config
    CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
    return dict(DEFAULT_CONFIG)


def read_glb(path: Path) -> tuple[dict, bytes]:
    data = path.read_bytes()
    if len(data) < 20 or data[:4] != b"glTF":
        raise ValueError(f"Not a GLB file: {path}")
    version, total_length = struct.unpack_from("<II", data, 4)
    if version != 2:
        raise ValueError(f"Unsupported GLB version {version}: {path}")
    offset = 12
    json_chunk = None
    bin_chunk = b""
    while offset < total_length:
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        chunk = data[offset : offset + chunk_length]
        offset += chunk_length
        if chunk_type == 0x4E4F534A:
            json_chunk = chunk
        elif chunk_type == 0x004E4942:
            bin_chunk = chunk
    if json_chunk is None:
        raise ValueError(f"GLB has no JSON chunk: {path}")
    return json.loads(json_chunk.decode("utf-8")), bin_chunk


def matrix_identity() -> list[list[float]]:
    return [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]


def matrix_multiply(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[row][k] * b[k][col] for k in range(4)) for col in range(4)] for row in range(4)]


def matrix_from_flat(values: list[float]) -> list[list[float]]:
    # glTF matrices are column-major.
    return [[float(values[col * 4 + row]) for col in range(4)] for row in range(4)]


def transform_point(matrix: list[list[float]], point: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = point
    return (
        matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z + matrix[0][3],
        matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z + matrix[1][3],
        matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z + matrix[2][3],
    )


def node_matrix(node: dict) -> list[list[float]]:
    if "matrix" in node:
        return matrix_from_flat(node["matrix"])
    # Minimal TRS support. Rotation is ignored unless matrix is present because
    # current exported ship nodes are matrix/identity-oriented.
    translation = node.get("translation", [0.0, 0.0, 0.0])
    scale = node.get("scale", [1.0, 1.0, 1.0])
    return [
        [scale[0], 0.0, 0.0, translation[0]],
        [0.0, scale[1], 0.0, translation[1]],
        [0.0, 0.0, scale[2], translation[2]],
        [0.0, 0.0, 0.0, 1.0],
    ]


def accessor_vec3(gltf: dict, bin_chunk: bytes, accessor_index: int) -> list[tuple[float, float, float]]:
    accessor = gltf["accessors"][accessor_index]
    if accessor.get("componentType") != 5126 or accessor.get("type") != "VEC3":
        raise ValueError("Only FLOAT VEC3 accessors are supported for positions")
    view = gltf["bufferViews"][accessor["bufferView"]]
    count = accessor["count"]
    offset = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    stride = view.get("byteStride", 12)
    points = []
    for index in range(count):
        base = offset + index * stride
        points.append(struct.unpack_from("<fff", bin_chunk, base))
    return points


def collect_vertices(gltf: dict, bin_chunk: bytes) -> list[tuple[float, float, float]]:
    nodes = gltf.get("nodes", [])
    meshes = gltf.get("meshes", [])
    scene_index = gltf.get("scene", 0)
    root_nodes = gltf.get("scenes", [{}])[scene_index].get("nodes", list(range(len(nodes))))
    vertices: list[tuple[float, float, float]] = []

    def visit(node_index: int, parent_matrix: list[list[float]]) -> None:
        node = nodes[node_index]
        world = matrix_multiply(parent_matrix, node_matrix(node))
        if "mesh" in node:
            mesh = meshes[node["mesh"]]
            for primitive in mesh.get("primitives", []):
                position_index = primitive.get("attributes", {}).get("POSITION")
                if position_index is None:
                    continue
                for point in accessor_vec3(gltf, bin_chunk, position_index):
                    vertices.append(transform_point(world, point))
        for child in node.get("children", []):
            visit(child, world)

    for node_index in root_nodes:
        visit(node_index, matrix_identity())
    if not vertices:
        raise ValueError("No POSITION vertices found in GLB")
    return vertices


def bounds(points: list[tuple[float, float, float]]) -> dict:
    return {
        "min": [round(min(p[i] for p in points), 5) for i in range(3)],
        "max": [round(max(p[i] for p in points), 5) for i in range(3)],
    }


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def sample_profiles(points: list[tuple[float, float, float]], config: dict) -> list[dict]:
    voxel_size = float(config["voxel_size"])
    shell_margin = float(config["shell_margin"])
    x_quantiles = config.get("central_x_quantiles", [0.34, 0.66])
    y_quantiles = config.get("central_y_quantiles", [0.18, 0.82])
    z_min = min(p[2] for p in points)
    z_max = max(p[2] for p in points)
    bin_count = max(18, int(math.ceil((z_max - z_min) / max(0.001, voxel_size))))
    bins: dict[int, list[tuple[float, float, float]]] = defaultdict(list)
    for point in points:
        index = max(0, min(bin_count - 1, int((point[2] - z_min) / max(0.001, z_max - z_min) * bin_count)))
        bins[index].append(point)

    profiles = []
    last = None
    for index in range(bin_count):
        z0 = z_min + (z_max - z_min) * index / bin_count
        z1 = z_min + (z_max - z_min) * (index + 1) / bin_count
        z = (z0 + z1) * 0.5
        slice_points = bins.get(index, [])
        if len(slice_points) < 8 and last:
            profile = dict(last)
            profile["z"] = round(z, 5)
            profile["source"] = "interpolated"
            profiles.append(profile)
            continue
        if len(slice_points) < 8:
            continue
        xs = [p[0] for p in slice_points]
        ys = [p[1] for p in slice_points]
        profile = {
            "z": round(z, 5),
            "x_min": round(percentile(xs, float(x_quantiles[0])) + shell_margin, 5),
            "x_max": round(percentile(xs, float(x_quantiles[1])) - shell_margin, 5),
            "y_min": round(percentile(ys, float(y_quantiles[0])) + shell_margin, 5),
            "y_max": round(percentile(ys, float(y_quantiles[1])) - shell_margin, 5),
            "source": "sampled",
            "source_point_count": len(slice_points),
        }
        if profile["x_max"] > profile["x_min"] and profile["y_max"] > profile["y_min"]:
            profiles.append(profile)
            last = profile
    return profiles


def generate_voxels(profiles: list[dict], config: dict) -> list[dict]:
    voxel_size = float(config["voxel_size"])
    radius = float(config["player_capsule_radius"])
    standing_height = float(config["standing_height"])
    clearance = float(config["clearance_margin"])
    voxels = []
    for profile in profiles:
        x_min = profile["x_min"] + radius
        x_max = profile["x_max"] - radius
        y_min = profile["y_min"] + radius
        y_max = profile["y_max"] - clearance
        if x_max < x_min or y_max < y_min:
            continue
        x_count = max(1, int((x_max - x_min) / voxel_size) + 1)
        y_count = max(1, int((y_max - y_min) / voxel_size) + 1)
        for xi in range(x_count):
            for yi in range(y_count):
                center = [x_min + xi * voxel_size, y_min + yi * voxel_size, profile["z"]]
                head_clearance = profile["y_max"] - center[1]
                voxels.append(
                    {
                        "center": [round(v, 5) for v in center],
                        "can_stand": head_clearance >= standing_height,
                        "head_clearance": round(head_clearance, 5),
                    }
                )
    return voxels


def voxel_key(center: list[float]) -> tuple[int, int, int]:
    return (int(round(center[0] * 1000)), int(round(center[1] * 1000)), int(round(center[2] * 1000)))


def build_walkable_nodes(voxels: list[dict]) -> dict[tuple[int, int, int], dict]:
    by_xz: dict[tuple[int, int], dict] = {}
    for voxel in voxels:
        if not voxel["can_stand"]:
            continue
        center = voxel["center"]
        xz_key = (int(round(center[0] * 1000)), int(round(center[2] * 1000)))
        current = by_xz.get(xz_key)
        if current is None or center[1] < current["center"][1]:
            by_xz[xz_key] = voxel

    nodes: dict[tuple[int, int, int], dict] = {}
    for voxel in by_xz.values():
        key = voxel_key(voxel["center"])
        nodes[key] = {
            "key": key,
            "center": voxel["center"],
            "can_stand": voxel["can_stand"],
            "head_clearance": voxel["head_clearance"],
        }
    return nodes


def nearest_node(nodes: dict[tuple[int, int, int], dict], target: list[float], region: dict | None = None) -> tuple[int, int, int] | None:
    candidates = list(nodes.values())
    if region is not None:
        region_ids = {region["id"]}
        filtered = []
        for node in candidates:
            ids = voxel_region_ids({"center": node["center"]}, [region])
            if region["id"] in ids:
                filtered.append(node)
        if filtered:
            candidates = filtered
    if not candidates:
        return None
    best = min(candidates, key=lambda node: (node["center"][0] - target[0]) ** 2 + (node["center"][2] - target[2]) ** 2 + (node["center"][1] - target[1]) ** 2)
    return best["key"]


def region_target(region: dict, preference: str) -> list[float]:
    center = list(region["center"])
    bmin = region["bounds"]["min"]
    bmax = region["bounds"]["max"]
    if preference == "front":
        center[2] = bmin[2]
    elif preference == "aft":
        center[2] = bmax[2]
    elif preference == "center":
        pass
    center[0] = (bmin[0] + bmax[0]) * 0.5
    center[1] = bmin[1]
    return center


def find_path(
    nodes: dict[tuple[int, int, int], dict],
    start_key: tuple[int, int, int],
    goal_key: tuple[int, int, int],
    config: dict,
    max_step_override: float | None = None,
    max_dist_override: float | None = None,
) -> list[dict]:
    traversal = config.get("traversal", {})
    voxel_size = float(config["voxel_size"])
    max_step = float(max_step_override if max_step_override is not None else traversal.get("max_step_height", 0.38))
    max_dist = float(max_dist_override if max_dist_override is not None else traversal.get("max_neighbor_distance", voxel_size * 1.6))
    vertical_cost = float(traversal.get("vertical_cost_scale", 2.0))
    centers = {key: node["center"] for key, node in nodes.items()}
    bucket_size = max(voxel_size, max_dist)
    buckets: dict[tuple[int, int], list[tuple[int, int, int]]] = defaultdict(list)
    for key, center in centers.items():
        buckets[(math.floor(center[0] / bucket_size), math.floor(center[2] / bucket_size))].append(key)
    bucket_radius = max(1, int(math.ceil(max_dist / bucket_size)))
    open_set: list[tuple[float, tuple[int, int, int]]] = [(0.0, start_key)]
    came_from: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    g_score: dict[tuple[int, int, int], float] = {start_key: 0.0}
    closed: set[tuple[int, int, int]] = set()

    def heuristic(a_key: tuple[int, int, int], b_key: tuple[int, int, int]) -> float:
        a = centers[a_key]
        b = centers[b_key]
        return math.dist((a[0], a[2]), (b[0], b[2]))

    while open_set:
        _, current = heapq.heappop(open_set)
        if current in closed:
            continue
        closed.add(current)
        if current == goal_key:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return [nodes[key] for key in path]

        cx, cy, cz = centers[current]
        current_bucket = (math.floor(cx / bucket_size), math.floor(cz / bucket_size))
        neighbor_keys = []
        for bx in range(current_bucket[0] - bucket_radius, current_bucket[0] + bucket_radius + 1):
            for bz in range(current_bucket[1] - bucket_radius, current_bucket[1] + bucket_radius + 1):
                neighbor_keys.extend(buckets.get((bx, bz), []))
        for key in neighbor_keys:
            if key == current:
                continue
            node = nodes[key]
            nx, ny, nz = node["center"]
            horizontal = math.dist((cx, cz), (nx, nz))
            if horizontal <= 0.001 or horizontal > max_dist:
                continue
            vertical = abs(ny - cy)
            if vertical > max_step:
                continue
            candidate = g_score[current] + horizontal + vertical * vertical_cost
            if candidate < g_score.get(key, float("inf")):
                came_from[key] = current
                g_score[key] = candidate
                heapq.heappush(open_set, (candidate + heuristic(key, goal_key), key))
    return []


def discover_traversal(voxels: list[dict], regions: list[dict], config: dict) -> dict:
    nodes = build_walkable_nodes(voxels)
    traversal_config = config.get("traversal", {})
    max_step = float(traversal_config.get("max_step_height", 0.38))
    connector_max_step = float(traversal_config.get("connector_max_step_height", 6.0))
    connector_max_dist = float(traversal_config.get("connector_max_neighbor_distance", 5.0))
    ramp = region_by_id(regions, "ramp_threshold")
    cargo = region_by_id(regions, "cargo")
    transition = region_by_id(regions, "transition")
    cockpit = region_by_id(regions, "cockpit")
    required = [ramp, cargo, transition, cockpit]
    if any(region is None for region in required):
        return {"status": "FAIL", "reason": "missing required semantic region", "node_count": len(nodes), "path": []}

    route_specs = [
        (ramp, "center"),
        (cargo, "center"),
        (transition, "center"),
        (cockpit, "center"),
    ]
    route_keys = []
    for region, preference in route_specs:
        target = region_target(region, preference)
        key = nearest_node(nodes, target, region)
        if key is None:
            return {"status": "FAIL", "reason": f"no walkable node in {region['id']}", "node_count": len(nodes), "path": []}
        route_keys.append(key)

    full_path: list[dict] = []
    segment_reports = []
    connector_segments = []
    for start, goal in zip(route_keys, route_keys[1:]):
        segment = find_path(nodes, start, goal, config)
        requires_connector = False
        if not segment:
            segment = find_path(nodes, start, goal, config, connector_max_step, connector_max_dist)
            requires_connector = bool(segment)
            if not segment:
                return {
                    "status": "FAIL",
                    "reason": "no connected path between route waypoints",
                    "node_count": len(nodes),
                    "route_keys": route_keys,
                    "segments": segment_reports,
                    "path": full_path,
                }
        measured_segment = segment
        full_path.extend(segment)
        max_vertical_delta = 0.0
        max_horizontal_delta = 0.0
        for a, b in zip(measured_segment, measured_segment[1:]):
            max_vertical_delta = max(max_vertical_delta, abs(b["center"][1] - a["center"][1]))
            max_horizontal_delta = max(
                max_horizontal_delta,
                math.dist((a["center"][0], a["center"][2]), (b["center"][0], b["center"][2])),
            )
        if full_path and len(full_path) > len(segment):
            full_path = full_path[:-len(segment)] + segment[1:]
            display_node_count = max(0, len(segment) - 1)
        else:
            display_node_count = len(segment)
        if max_vertical_delta > max_step or max_horizontal_delta > float(traversal_config.get("max_neighbor_distance", 0.38)):
            requires_connector = True
        if requires_connector:
            connector_segments.append(
                {
                    "start": nodes[start]["center"],
                    "goal": nodes[goal]["center"],
                    "max_vertical_delta": round(max_vertical_delta, 5),
                    "max_horizontal_delta": round(max_horizontal_delta, 5),
                    "recommendation": "generate ramp/stair connector before playable collision",
                }
            )
        segment_reports.append(
            {
                "start": nodes[start]["center"],
                "goal": nodes[goal]["center"],
                "node_count": display_node_count,
                "raw_node_count": len(measured_segment),
                "requires_connector": requires_connector,
                "max_vertical_delta": round(max_vertical_delta, 5),
                "max_horizontal_delta": round(max_horizontal_delta, 5),
            }
        )
    return {
        "status": "PASS_WITH_CONNECTORS" if connector_segments else "PASS",
        "node_count": len(nodes),
        "route_keys": route_keys,
        "segments": segment_reports,
        "connector_segments": connector_segments,
        "path_node_count": len(full_path),
        "path": [node["center"] for node in full_path],
    }


def region_from_voxels(name: str, voxels: list[dict], fractions: list[float], all_bounds: dict) -> dict | None:
    z_min, z_max = all_bounds["min"][2], all_bounds["max"][2]
    rz0 = z_min + (z_max - z_min) * fractions[0]
    rz1 = z_min + (z_max - z_min) * fractions[1]
    selected = [v for v in voxels if rz0 <= v["center"][2] <= rz1]
    if not selected:
        return None
    mins = [min(v["center"][i] for v in selected) for i in range(3)]
    maxs = [max(v["center"][i] for v in selected) for i in range(3)]
    by_z: dict[float, list[dict]] = defaultdict(list)
    for voxel in selected:
        by_z[voxel["center"][2]].append(voxel)
    sections = []
    for z, section_voxels in sorted(by_z.items()):
        sx_min = min(v["center"][0] for v in section_voxels)
        sx_max = max(v["center"][0] for v in section_voxels)
        sy_min = min(v["center"][1] for v in section_voxels)
        sy_max = max(v["center"][1] for v in section_voxels)
        sections.append(
            {
                "z": round(z, 5),
                "x_min": round(sx_min, 5),
                "x_max": round(sx_max, 5),
                "y_min": round(sy_min, 5),
                "y_max": round(sy_max, 5),
                "voxel_count": len(section_voxels),
            }
        )
    return {
        "id": name,
        "voxel_count": len(selected),
        "standing_voxel_count": sum(1 for v in selected if v["can_stand"]),
        "representation": "prismatic_voxel_sections",
        "section_count": len(sections),
        "section_z_step": round(min(
            (abs(sections[index + 1]["z"] - sections[index]["z"]) for index in range(len(sections) - 1)),
            default=0.25,
        ), 5),
        "center": [round((mins[i] + maxs[i]) * 0.5, 5) for i in range(3)],
        "size": [round(maxs[i] - mins[i], 5) for i in range(3)],
        "bounds": {"min": [round(v, 5) for v in mins], "max": [round(v, 5) for v in maxs]},
        "sections": sections,
    }


def region_by_id(regions: list[dict], region_id: str) -> dict | None:
    return next((region for region in regions if region["id"] == region_id), None)


def regions_overlap(a: dict | None, b: dict | None) -> bool:
    if a is None or b is None:
        return False
    amin = a["bounds"]["min"]
    amax = a["bounds"]["max"]
    bmin = b["bounds"]["min"]
    bmax = b["bounds"]["max"]
    overlaps = []
    for axis in range(3):
        overlaps.append(min(amax[axis], bmax[axis]) - max(amin[axis], bmin[axis]))
    # For planning regions, x/y should overlap and z should touch or overlap.
    return overlaps[0] > 0.25 and overlaps[1] > 0.25 and overlaps[2] > -0.25


class ImageCanvas:
    def __init__(self, width: int, height: int, color: tuple[int, int, int]):
        self.width = width
        self.height = height
        self.pixels = bytearray(color * width * height)

    def set_pixel(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            offset = (y * self.width + x) * 3
            self.pixels[offset : offset + 3] = bytes(color)

    def rect(self, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int], fill: bool = False) -> None:
        left, right = sorted((max(0, x0), min(self.width - 1, x1)))
        top, bottom = sorted((max(0, y0), min(self.height - 1, y1)))
        if fill:
            for y in range(top, bottom + 1):
                start = (y * self.width + left) * 3
                self.pixels[start : start + (right - left + 1) * 3] = bytes(color) * (right - left + 1)
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
            rows.extend(self.pixels[y * stride : (y + 1) * stride])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
            + chunk(b"IEND", b"")
        )


def voxel_region_ids(voxel: dict, regions: list[dict]) -> list[str]:
    x, y, z = voxel["center"]
    found = []
    for region in regions:
        section = nearest_region_section(region, z)
        if section is None:
            continue
        z_step = region.get("section_z_step", 0.25)
        if abs(z - section["z"]) > z_step * 0.55:
            continue
        if section["x_min"] <= x <= section["x_max"] and section["y_min"] <= y <= section["y_max"]:
            found.append(region["id"])
    return found


def nearest_region_section(region: dict, z: float) -> dict | None:
    sections = region.get("sections", [])
    if not sections:
        return None
    return min(sections, key=lambda section: abs(section["z"] - z))


def draw_prism_outline(canvas: ImageCanvas, region: dict, axes: tuple[int, int], map_point, color: tuple[int, int, int]) -> None:
    sections = region.get("sections", [])
    if len(sections) < 2:
        return
    if axes == (2, 1):
        lower = [(section["z"], section["y_min"]) for section in sections]
        upper = [(section["z"], section["y_max"]) for section in reversed(sections)]
    elif axes == (2, 0):
        lower = [(section["z"], section["x_min"]) for section in sections]
        upper = [(section["z"], section["x_max"]) for section in reversed(sections)]
    elif axes == (0, 1):
        widest = max(sections, key=lambda section: (section["x_max"] - section["x_min"]) * (section["y_max"] - section["y_min"]))
        lower = [
            (widest["x_min"], widest["y_min"]),
            (widest["x_max"], widest["y_min"]),
        ]
        upper = [
            (widest["x_max"], widest["y_max"]),
            (widest["x_min"], widest["y_max"]),
        ]
    else:
        return

    poly = lower + upper
    mapped = [map_point(x, y) for x, y in poly]
    for index in range(len(mapped)):
        x0, y0 = mapped[index]
        x1, y1 = mapped[(index + 1) % len(mapped)]
        canvas.line(x0, y0, x1, y1, color)
        canvas.line(x0 + 1, y0, x1 + 1, y1, color)


def draw_projection(path: Path, points: list[tuple[float, float, float]], voxels: list[dict], regions: list[dict], mode: str, traversal_path: list[list[float]] | None = None) -> None:
    canvas = ImageCanvas(1920, 720, (12, 15, 19))
    panels = [(24, 36, 604, 648, (2, 1)), (658, 36, 604, 648, (2, 0)), (1292, 36, 604, 648, (0, 1))]
    all_points = list(points) + [tuple(v["center"]) for v in voxels]
    colors = {"cargo": (80, 180, 220), "cockpit": (235, 190, 70), "transition": (140, 215, 90), "ramp_threshold": (235, 125, 75)}
    for px, py, pw, ph, axes in panels:
        canvas.rect(px, py, px + pw - 1, py + ph - 1, (40, 46, 54))
        coords = [(p[axes[0]], p[axes[1]]) for p in all_points]
        min_x, max_x = min(c[0] for c in coords), max(c[0] for c in coords)
        min_y, max_y = min(c[1] for c in coords), max(c[1] for c in coords)
        min_x, max_x = min_x - 0.8, max_x + 0.8
        min_y, max_y = min_y - 0.8, max_y + 0.8

        def map_point(x: float, y: float) -> tuple[int, int]:
            sx = int(px + (x - min_x) / max(0.001, max_x - min_x) * (pw - 1))
            sy = int(py + (1.0 - (y - min_y) / max(0.001, max_y - min_y)) * (ph - 1))
            return sx, sy

        for point in points:
            sx, sy = map_point(point[axes[0]], point[axes[1]])
            canvas.set_pixel(sx, sy, (210, 215, 222))
        if mode in {"voxels", "semantic", "traversal"}:
            for voxel in voxels:
                sx, sy = map_point(voxel["center"][axes[0]], voxel["center"][axes[1]])
                color = (85, 175, 215) if voxel["can_stand"] else (55, 90, 115)
                if mode == "semantic":
                    ids = voxel_region_ids(voxel, regions)
                    if "cockpit" in ids:
                        color = colors["cockpit"]
                    elif "transition" in ids:
                        color = colors["transition"]
                    elif "ramp_threshold" in ids:
                        color = colors["ramp_threshold"]
                    elif "cargo" in ids:
                        color = colors["cargo"]
                canvas.rect(sx - 1, sy - 1, sx + 1, sy + 1, color, fill=True)
        if mode in {"semantic", "traversal"}:
            for region in regions:
                color = colors.get(region["id"], (200, 200, 200))
                draw_prism_outline(canvas, region, axes, map_point, color)
                if mode == "semantic" and axes in {(2, 1), (2, 0)}:
                    for section in region.get("sections", []):
                        if axes == (2, 1):
                            a0, b0 = map_point(section["z"], section["y_min"])
                            a1, b1 = map_point(section["z"], section["y_max"])
                        else:
                            a0, b0 = map_point(section["z"], section["x_min"])
                            a1, b1 = map_point(section["z"], section["x_max"])
                        canvas.line(a0, b0, a1, b1, color)
        if mode == "traversal" and traversal_path:
            mapped = []
            for point in traversal_path:
                if isinstance(point, dict):
                    if "center" in point:
                        values = point["center"]
                    else:
                        values = (point["x"], point["y"], point["z"])
                else:
                    values = point
                mapped.append(map_point(values[axes[0]], values[axes[1]]))
            for index in range(len(mapped) - 1):
                x0, y0 = mapped[index]
                x1, y1 = mapped[index + 1]
                canvas.line(x0, y0, x1, y1, (255, 235, 90))
                canvas.line(x0 + 1, y0, x1 + 1, y1, (255, 235, 90))
                canvas.line(x0, y0 + 1, x1, y1 + 1, (255, 235, 90))
    canvas.write_png(path)


def write_outputs(source_glb: Path, gltf: dict, points: list[tuple[float, float, float]], profiles: list[dict], voxels: list[dict], regions: list[dict], traversal: dict, config: dict) -> None:
    OUT_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    OUT_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_glb, OUT_GLB)

    draw_projection(EXTERIOR_PNG, points, [], regions, "exterior")
    draw_projection(VOXEL_PNG, points, voxels, regions, "voxels")
    draw_projection(SEMANTIC_PNG, points, voxels, regions, "semantic")
    draw_projection(TRAVERSAL_PNG, points, voxels, regions, "traversal", traversal.get("path", []))

    region_ids = {region["id"] for region in regions}
    connectivity = {
        "ramp_threshold_to_cargo": regions_overlap(region_by_id(regions, "ramp_threshold"), region_by_id(regions, "cargo")),
        "cargo_to_transition": regions_overlap(region_by_id(regions, "cargo"), region_by_id(regions, "transition")),
        "transition_to_cockpit": regions_overlap(region_by_id(regions, "transition"), region_by_id(regions, "cockpit")),
    }
    connectivity["status"] = "PASS" if all(connectivity.values()) else "FAIL"
    report = {
        "schema_version": 1,
        "ship_id": "shuttle_p3",
        "source_glb": str(source_glb.relative_to(ROOT)),
        "output_exterior_glb": str(OUT_GLB.relative_to(ROOT)),
        "reuse_boundary": "Copied accepted prototype exterior skin GLB only; no prototype interior/collision/furnishing/lighting carried forward.",
        "config": config,
        "exterior_vertex_count": len(points),
        "exterior_bounds": bounds(points),
        "slice_profile_count": len(profiles),
        "voxel_count": len(voxels),
        "standing_voxel_count": sum(1 for v in voxels if v["can_stand"]),
        "semantic_regions": regions,
        "connectivity": connectivity,
        "traversal": traversal,
        "evidence": {
            "exterior_projection": str(EXTERIOR_PNG.relative_to(ROOT)),
            "voxel_projection": str(VOXEL_PNG.relative_to(ROOT)),
            "semantic_projection": str(SEMANTIC_PNG.relative_to(ROOT)),
            "traversal_projection": str(TRAVERSAL_PNG.relative_to(ROOT)),
        },
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "ship_id": "shuttle_p3",
                "status": "milestone_one_glb_skin_source",
                "accepted_skin_source_glb": str(source_glb.relative_to(ROOT)),
                "generated_exterior_glb": str(OUT_GLB.relative_to(ROOT)),
                "note": "Clean Blender source is pending host Blender/MCP profile availability; this milestone uses the accepted exterior GLB skin only.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
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
        f"- Standing voxels: {report['standing_voxel_count']}",
        f"- Exterior projection: `{report['evidence']['exterior_projection']}`",
        f"- Voxel projection: `{report['evidence']['voxel_projection']}`",
        f"- Semantic projection: `{report['evidence']['semantic_projection']}`",
        f"- Traversal projection: `{report['evidence']['traversal_projection']}`",
        f"- Traversal status: **{traversal.get('status', 'UNKNOWN')}**",
        f"- Traversal graph nodes: {traversal.get('node_count', 0)}",
        f"- Traversal path nodes: {traversal.get('path_node_count', 0)}",
        "",
        "## Semantic Regions",
        "",
    ]
    for region in regions:
        lines.append(f"- `{region['id']}`: center={region['center']}, size={region['size']}, standing={region['standing_voxel_count']}")
    lines += [
        "",
        "## Voxel Traversal",
        "",
        f"- Status: `{traversal.get('status', 'UNKNOWN')}`",
        f"- Reason: `{traversal.get('reason', 'n/a')}`",
        f"- Graph nodes: {traversal.get('node_count', 0)}",
        f"- Path nodes: {traversal.get('path_node_count', 0)}",
        "",
        "## Segment Reports",
        "",
    ]
    for segment in traversal.get("segments", []):
        lines.append(
            f"- start={segment['start']} goal={segment['goal']} nodes={segment['node_count']} "
            f"requires_connector={segment.get('requires_connector', False)} "
            f"max_vertical_delta={segment.get('max_vertical_delta', 0)} "
            f"max_horizontal_delta={segment.get('max_horizontal_delta', 0)}"
        )
    if traversal.get("connector_segments"):
        lines += [
            "",
            "## Connector Requirements",
            "",
        ]
        for connector in traversal["connector_segments"]:
            lines.append(
                f"- start={connector['start']} goal={connector['goal']} "
                f"max_vertical_delta={connector['max_vertical_delta']} "
                f"max_horizontal_delta={connector['max_horizontal_delta']} "
                f"recommendation={connector['recommendation']}"
            )
    lines += [
        "",
        "## Notes",
        "",
        "- This is milestone-one evidence only.",
        "- No floors, ramps, stairs, collision, furnishings, or lighting were carried forward or generated.",
        "- The clean `.blend` source copy is still pending host Blender profile availability.",
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    source_glb = args.source_glb.resolve()
    if not source_glb.exists():
        raise FileNotFoundError(source_glb)
    config = load_config()
    gltf, bin_chunk = read_glb(source_glb)
    points = collect_vertices(gltf, bin_chunk)
    profiles = sample_profiles(points, config)
    voxels = generate_voxels(profiles, config)
    b = bounds(points)
    hints = config["semantic_region_hint"]
    regions = [
        region_from_voxels("cargo", voxels, hints["cargo_z_fraction"], b),
        region_from_voxels("cockpit", voxels, hints["cockpit_z_fraction"], b),
        region_from_voxels("transition", voxels, hints["transition_z_fraction"], b),
        region_from_voxels("ramp_threshold", voxels, hints["ramp_threshold_z_fraction"], b),
    ]
    regions = [region for region in regions if region is not None]
    traversal = discover_traversal(voxels, regions, config)
    write_outputs(source_glb, gltf, points, profiles, voxels, regions, traversal, config)
    print(f"Wrote {OUT_GLB}")
    print(f"Wrote {REPORT_JSON}")
    print(f"Wrote {REPORT_MD}")
    print(f"Wrote {EXTERIOR_PNG}")
    print(f"Wrote {VOXEL_PNG}")
    print(f"Wrote {SEMANTIC_PNG}")
    print(f"Wrote {TRAVERSAL_PNG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
