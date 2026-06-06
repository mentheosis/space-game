#!/usr/bin/env python3
"""Generate MX01 smoothed skin-fitted interior enclosure collision."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from mesh_writer import box_faces, box_vertices


ROOT = Path(__file__).resolve().parents[3]
SHIP_DIR = ROOT / "ships" / "MX01"
DEFAULT_CONFIG = SHIP_DIR / "config" / "mx01_collision_generation.json"

Vec3 = tuple[float, float, float]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resolve_config_path(config: dict, section: str, key: str) -> Path:
    return ROOT / config[section][key]


def axis_edges(centers: list[float], voxel_size: float) -> list[float]:
    start = float(centers[0]) - voxel_size * 0.5
    return [round(start + index * voxel_size, 6) for index in range(len(centers) + 1)]


def nearest_index(values: list[float], target: float) -> int:
    return min(range(len(values)), key=lambda index: (abs(float(values[index]) - target), index))


def build_interval_map(occupancy: dict) -> dict[tuple[int, int], list[tuple[int, int]]]:
    intervals: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for ray in occupancy["rays"]:
        yi = int(ray["y_index"])
        zi = int(ray["z_index"])
        intervals[(yi, zi)] = [(int(start), int(end)) for start, end in ray["x_intervals"]]
    return intervals


def build_inside_set(occupancy: dict) -> set[tuple[int, int, int]]:
    inside: set[tuple[int, int, int]] = set()
    for ray in occupancy["rays"]:
        yi = int(ray["y_index"])
        zi = int(ray["z_index"])
        for start, end in ray["x_intervals"]:
            for xi in range(int(start), int(end) + 1):
                inside.add((xi, yi, zi))
    return inside


def deck_nodes(graph: dict) -> list[dict]:
    return sorted((node for node in graph["nodes"] if node["kind"] == "deck"), key=lambda node: (float(node["center"][1]), node["id"]))


def connector_keepouts(collision: dict, config: dict) -> list[dict]:
    radius = float(config["player_capsule_radius"]) + float(config["player_clearance_margin"])
    height = float(config["player_capsule_height"]) + float(config["player_clearance_margin"])
    keepouts = []
    for obj in collision["objects"]:
        if obj["role"] not in {"player_connector_landing", "player_connector_stair_tread"}:
            continue
        cx, cy, cz = [float(value) for value in obj["center"]]
        sx, sy, sz = [float(value) for value in obj["size"]]
        top = cy + sy * 0.5
        keepouts.append(
            {
                "x_min": cx - sx * 0.5 - radius,
                "x_max": cx + sx * 0.5 + radius,
                "y_min": top - 0.02,
                "y_max": top + height,
                "z_min": cz - sz * 0.5 - radius,
                "z_max": cz + sz * 0.5 + radius,
            }
        )
    return keepouts


def connector_route_openings(collision: dict, config: dict) -> list[dict]:
    height = float(config["player_capsule_height"]) + float(config["player_clearance_margin"])
    margin = 0.28
    group_run_directions: dict[str, set[str]] = {}
    for obj in collision["objects"]:
        if obj["role"] != "player_connector_stair_tread":
            continue
        group_id = connector_group_id(obj["name"])
        if group_id is None:
            continue
        _cx, _cy, _cz = [float(value) for value in obj["center"]]
        sx, _sy, sz = [float(value) for value in obj["size"]]
        if sx > sz * 1.2:
            group_run_directions.setdefault(group_id, set()).add("z")
        elif sz > sx * 1.2:
            group_run_directions.setdefault(group_id, set()).add("x")
        else:
            group_run_directions.setdefault(group_id, set()).update(("x", "z"))
    openings = []
    for obj in collision["objects"]:
        if obj["role"] not in {"player_connector_landing", "player_connector_stair_tread"}:
            continue
        cx, cy, cz = [float(value) for value in obj["center"]]
        sx, sy, sz = [float(value) for value in obj["size"]]
        top = cy + sy * 0.5
        if obj["role"] == "player_connector_landing":
            group_id = connector_group_id(obj["name"])
            reserve_directions = set(group_run_directions.get(group_id or "", {"x", "z"}))
        elif sx > sz * 1.2:
            reserve_directions = {"z"}
        elif sz > sx * 1.2:
            reserve_directions = {"x"}
        else:
            reserve_directions = {"x", "z"}
        openings.append(
            {
                "x_min": cx - sx * 0.5 - margin,
                "x_max": cx + sx * 0.5 + margin,
                "y_min": top - 0.02,
                "y_max": top + height,
                "z_min": cz - sz * 0.5 - margin,
                "z_max": cz + sz * 0.5 + margin,
                "reserve_directions": sorted(reserve_directions),
            }
        )
    return openings


def connector_group_id(name: str) -> str | None:
    prefix = "COL_MX01_"
    if not name.startswith(prefix):
        return None
    core = name[len(prefix) :]
    for suffix in ("_lower_landing", "_upper_landing"):
        if core.endswith(suffix):
            return core[: -len(suffix)]
    marker = "_stair_tread_"
    if marker in core:
        return core.split(marker, 1)[0]
    return None


def connector_route_clearances(collision: dict) -> list[dict]:
    margin = 0.5
    clearances = []
    for obj in collision["objects"]:
        if obj["role"] not in {"player_connector_landing", "player_connector_stair_tread"}:
            continue
        cx, cy, cz = [float(value) for value in obj["center"]]
        sx, sy, sz = [float(value) for value in obj["size"]]
        clearances.append(
            {
                "x_min": cx - sx * 0.5 - margin,
                "x_max": cx + sx * 0.5 + margin,
                "y_min": cy - sy * 0.5 - margin,
                "y_max": cy + sy * 0.5 + margin,
                "z_min": cz - sz * 0.5 - margin,
                "z_max": cz + sz * 0.5 + margin,
            }
        )
    return clearances


def stair_detour_clearances(collision: dict) -> list[dict]:
    margin = 0.35
    clearances = []
    for obj in collision["objects"]:
        if obj["role"] not in {"player_connector_landing", "player_connector_stair_tread"}:
            continue
        cx, cy, cz = [float(value) for value in obj["center"]]
        sx, sy, sz = [float(value) for value in obj["size"]]
        clearances.append(
            {
                "x_min": cx - sx * 0.5 - margin,
                "x_max": cx + sx * 0.5 + margin,
                "y_min": cy - sy * 0.5 - 0.05,
                "y_max": cy + sy * 0.5 + 0.45,
                "z_min": cz - sz * 0.5 - margin,
                "z_max": cz + sz * 0.5 + margin,
            }
        )
    return clearances


def stair_route_headroom_clearances(collision: dict, config: dict) -> list[dict]:
    margin = float(config["player_capsule_radius"]) + 0.08
    height = float(config["player_capsule_height"]) + float(config["player_clearance_margin"])
    clearances = []
    for obj in collision["objects"]:
        if obj["role"] not in {"player_connector_landing", "player_connector_stair_tread"}:
            continue
        cx, cy, cz = [float(value) for value in obj["center"]]
        sx, sy, sz = [float(value) for value in obj["size"]]
        top = cy + sy * 0.5
        clearances.append(
            {
                "name": obj["name"],
                "group": connector_group_id(obj["name"]) or "ungrouped",
                "x_min": cx - sx * 0.5 - margin,
                "x_max": cx + sx * 0.5 + margin,
                "y_min": top + 0.04,
                "y_max": top + height,
                "z_min": cz - sz * 0.5 - margin,
                "z_max": cz + sz * 0.5 + margin,
            }
        )
    return clearances


def connector_groups(collision: dict) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for obj in collision["objects"]:
        if obj["role"] not in {"player_connector_landing", "player_connector_stair_tread"}:
            continue
        group_id = connector_group_id(obj["name"])
        if group_id is None:
            continue
        groups.setdefault(group_id, []).append(obj)
    return dict(sorted(groups.items()))


def connector_run_axis(objects: list[dict]) -> str:
    x_wide = 0
    z_wide = 0
    for obj in objects:
        if obj["role"] != "player_connector_stair_tread":
            continue
        sx, _sy, sz = [float(value) for value in obj["size"]]
        if sx > sz * 1.2:
            x_wide += 1
        elif sz > sx * 1.2:
            z_wide += 1
    return "z" if x_wide >= z_wide else "x"


def point_in_keepout(point: Vec3, keepouts: list[dict]) -> bool:
    x, y, z = point
    for keepout in keepouts:
        if keepout["x_min"] <= x <= keepout["x_max"] and keepout["y_min"] <= y <= keepout["y_max"] and keepout["z_min"] <= z <= keepout["z_max"]:
            return True
    return False


def largest_interval(intervals: list[tuple[int, int]]) -> tuple[int, int] | None:
    if not intervals:
        return None
    return max(intervals, key=lambda item: (item[1] - item[0], -item[0]))


def smooth_optional_series(values: list[float | None], passes: int = 3) -> list[float | None]:
    result = values[:]
    for _ in range(passes):
        next_values: list[float | None] = []
        for index, value in enumerate(result):
            if value is None:
                next_values.append(None)
                continue
            neighbors = [value]
            if index > 0 and result[index - 1] is not None:
                neighbors.append(float(result[index - 1]))
            if index + 1 < len(result) and result[index + 1] is not None:
                neighbors.append(float(result[index + 1]))
            next_values.append(sum(neighbors) / len(neighbors))
        result = next_values
    return result


def contiguous_segments(indices: list[int]) -> list[list[int]]:
    if not indices:
        return []
    segments = [[indices[0]]]
    for index in indices[1:]:
        if index == segments[-1][-1] + 1:
            segments[-1].append(index)
        else:
            segments.append([index])
    return segments


def add_vertex(vertices: list[Vec3], index: dict[Vec3, int], point: Vec3, epsilon: float) -> int:
    quantized = tuple(round(round(coord / epsilon) * epsilon, 6) for coord in point)
    if quantized not in index:
        index[quantized] = len(vertices)
        vertices.append(quantized)
    return index[quantized]


def normal(triangle: tuple[Vec3, Vec3, Vec3]) -> Vec3:
    a, b, c = triangle
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length <= 0.0:
        return (0.0, 0.0, 0.0)
    return (nx / length, ny / length, nz / length)


def triangle_from_face(vertices: list[Vec3], face: list[int]) -> tuple[Vec3, Vec3, Vec3]:
    return (vertices[face[0]], vertices[face[1]], vertices[face[2]])


def triangle_center(vertices: list[Vec3], face: list[int]) -> Vec3:
    a, b, c = triangle_from_face(vertices, face)
    return ((a[0] + b[0] + c[0]) / 3.0, (a[1] + b[1] + c[1]) / 3.0, (a[2] + b[2] + c[2]) / 3.0)


def triangle_area(triangle: tuple[Vec3, Vec3, Vec3]) -> float:
    a, b, c = triangle
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    return 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)


def add_quad(vertices: list[Vec3], vertex_index: dict[Vec3, int], faces: list[list[int]], a: Vec3, b: Vec3, c: Vec3, d: Vec3, epsilon: float) -> None:
    i0 = add_vertex(vertices, vertex_index, a, epsilon)
    i1 = add_vertex(vertices, vertex_index, b, epsilon)
    i2 = add_vertex(vertices, vertex_index, c, epsilon)
    i3 = add_vertex(vertices, vertex_index, d, epsilon)
    if len({i0, i1, i2}) == 3:
        faces.append([i0, i1, i2])
    if len({i0, i2, i3}) == 3:
        faces.append([i0, i2, i3])


def make_mesh_object(name: str, role: str, deck_id: str, vertices: list[Vec3], faces: list[list[int]], source: str) -> dict | None:
    if not faces:
        return None
    area = round(sum(triangle_area(triangle_from_face(vertices, face)) for face in faces), 6)
    return {
        "name": name,
        "role": role,
        "kind": "triangle_mesh",
        "deck": deck_id,
        "vertices": [[x, y, z] for x, y, z in vertices],
        "triangles": faces,
        "material": "MX01_EnclosureCeiling" if role == "player_enclosure_ceiling" else "MX01_EnclosureWall",
        "source": source,
        "surface_area_m2": area,
    }


def wall_boundaries_for_deck(deck: dict, occupancy: dict, interval_map: dict[tuple[int, int], list[tuple[int, int]]], config: dict) -> tuple[list[int], list[int], dict[tuple[int, int], tuple[float, float]]]:
    voxel_size = float(occupancy["voxel_size"])
    x_edges = axis_edges(occupancy["axis_centers"]["x"], voxel_size)
    y_centers = occupancy["axis_centers"]["y"]
    z_centers = occupancy["axis_centers"]["z"]
    skin_inset = abs(float(config["surface_offset_modes"]["inset_for_interior_clearance"]))
    clearance = float(config["player_capsule_height"]) + float(config["player_clearance_margin"])
    deck_y = float(deck["center"][1])
    y_indices = [index for index, y in enumerate(y_centers) if deck_y + 0.15 <= float(y) <= deck_y + clearance + 0.45]
    if len(y_indices) > 5:
        step = max(1, len(y_indices) // 5)
        y_indices = y_indices[::step]
        last_index = nearest_index(y_centers, deck_y + clearance + 0.45)
        if last_index not in y_indices and 0 <= last_index < len(y_centers):
            y_indices.append(last_index)
        y_indices = sorted(set(y_indices))
    z_indices = sorted({zi for yi in y_indices for zi in range(len(z_centers)) if largest_interval(interval_map.get((yi, zi), [])) is not None})
    raw: dict[tuple[int, int], tuple[float, float]] = {}
    for yi in y_indices:
        left_values: list[float | None] = []
        right_values: list[float | None] = []
        for zi in range(len(z_centers)):
            interval = largest_interval(interval_map.get((yi, zi), []))
            if interval is None:
                left_values.append(None)
                right_values.append(None)
                continue
            left_values.append(x_edges[interval[0]] + skin_inset)
            right_values.append(x_edges[interval[1] + 1] - skin_inset)
        left_smooth = smooth_optional_series(left_values)
        right_smooth = smooth_optional_series(right_values)
        for zi in z_indices:
            if left_smooth[zi] is not None and right_smooth[zi] is not None and left_smooth[zi] < right_smooth[zi]:
                raw[(yi, zi)] = (float(left_smooth[zi]), float(right_smooth[zi]))
    for _ in range(10):
        next_raw: dict[tuple[int, int], tuple[float, float]] = {}
        for key, value in raw.items():
            yi, zi = key
            left_values = [value[0]]
            right_values = [value[1]]
            for neighbor in ((yi - 1, zi), (yi + 1, zi), (yi, zi - 1), (yi, zi + 1)):
                if neighbor in raw:
                    left_values.append(raw[neighbor][0])
                    right_values.append(raw[neighbor][1])
            left = sum(left_values) / len(left_values)
            right = sum(right_values) / len(right_values)
            if left < right:
                next_raw[key] = (left, right)
        raw = next_raw
    return y_indices, z_indices, raw


def build_side_wall(deck: dict, side: str, segment_index: int, y_indices: list[int], z_segment: list[int], boundaries: dict[tuple[int, int], tuple[float, float]], occupancy: dict, keepouts: list[dict], epsilon: float) -> dict | None:
    y_centers = occupancy["axis_centers"]["y"]
    z_centers = occupancy["axis_centers"]["z"]
    vertices: list[Vec3] = []
    vertex_index: dict[Vec3, int] = {}
    faces: list[list[int]] = []
    side_index = 0 if side == "left" else 1
    for yi0, yi1 in zip(y_indices, y_indices[1:]):
        for zi0, zi1 in zip(z_segment, z_segment[1:]):
            keys = ((yi0, zi0), (yi1, zi0), (yi1, zi1), (yi0, zi1))
            if any(key not in boundaries for key in keys):
                continue
            points = tuple((boundaries[key][side_index], float(y_centers[key[0]]), float(z_centers[key[1]])) for key in keys)
            center = ((points[0][0] + points[2][0]) * 0.5, (points[0][1] + points[2][1]) * 0.5, (points[0][2] + points[2][2]) * 0.5)
            if point_in_keepout(center, keepouts):
                continue
            if side == "left":
                add_quad(vertices, vertex_index, faces, points[0], points[1], points[2], points[3], epsilon)
            else:
                add_quad(vertices, vertex_index, faces, points[3], points[2], points[1], points[0], epsilon)
    return make_mesh_object(
        f"COL_MX01_{deck['id']}_smooth_{side}_skin_wall_{segment_index:02d}",
        "player_enclosure_wall",
        deck["id"],
        vertices,
        faces,
        "smoothed_occupancy_contour_wall",
    )


def build_end_wall(deck: dict, suffix: str, segment_index: int, z_index: int, y_indices: list[int], boundaries: dict[tuple[int, int], tuple[float, float]], occupancy: dict, keepouts: list[dict], epsilon: float) -> dict | None:
    y_centers = occupancy["axis_centers"]["y"]
    z = float(occupancy["axis_centers"]["z"][z_index])
    vertices: list[Vec3] = []
    vertex_index: dict[Vec3, int] = {}
    faces: list[list[int]] = []
    for yi0, yi1 in zip(y_indices, y_indices[1:]):
        if (yi0, z_index) not in boundaries or (yi1, z_index) not in boundaries:
            continue
        x0_left, x0_right = boundaries[(yi0, z_index)]
        x1_left, x1_right = boundaries[(yi1, z_index)]
        points = ((x0_left, float(y_centers[yi0]), z), (x1_left, float(y_centers[yi1]), z), (x1_right, float(y_centers[yi1]), z), (x0_right, float(y_centers[yi0]), z))
        center = ((x0_left + x0_right + x1_left + x1_right) * 0.25, (float(y_centers[yi0]) + float(y_centers[yi1])) * 0.5, z)
        if point_in_keepout(center, keepouts):
            continue
        if suffix == "forward":
            add_quad(vertices, vertex_index, faces, points[0], points[1], points[2], points[3], epsilon)
        else:
            add_quad(vertices, vertex_index, faces, points[3], points[2], points[1], points[0], epsilon)
    return make_mesh_object(
        f"COL_MX01_{deck['id']}_smooth_{suffix}_skin_wall_{segment_index:02d}",
        "player_enclosure_wall",
        deck["id"],
        vertices,
        faces,
        "smoothed_occupancy_contour_end_wall",
    )


def floor_sample_points(collision: dict, occupancy: dict, deck_id: str, stride: int) -> list[tuple[int, int]]:
    x_centers = occupancy["axis_centers"]["x"]
    z_centers = occupancy["axis_centers"]["z"]
    points: set[tuple[int, int]] = set()
    for obj in collision["objects"]:
        if obj["role"] != "player_walkable_floor":
            continue
        if f"COL_MX01_{deck_id}_" not in obj["name"]:
            continue
        cx, _cy, cz = [float(value) for value in obj["center"]]
        sx, _sy, sz = [float(value) for value in obj["size"]]
        x_min, x_max = cx - sx * 0.5, cx + sx * 0.5
        z_min, z_max = cz - sz * 0.5, cz + sz * 0.5
        xi_min = nearest_index(x_centers, x_min)
        xi_max = nearest_index(x_centers, x_max)
        zi_min = nearest_index(z_centers, z_min)
        zi_max = nearest_index(z_centers, z_max)
        for xi in range(min(xi_min, xi_max), max(xi_min, xi_max) + 1, stride):
            for zi in range(min(zi_min, zi_max), max(zi_min, zi_max) + 1, stride):
                if x_min <= float(x_centers[xi]) <= x_max and z_min <= float(z_centers[zi]) <= z_max:
                    points.add((xi, zi))
    return sorted(points)


def build_ceiling(deck: dict, collision: dict, occupancy: dict, inside: set[tuple[int, int, int]], keepouts: list[dict], config: dict, epsilon: float) -> dict | None:
    voxel_size = float(occupancy["voxel_size"])
    y_edges = axis_edges(occupancy["axis_centers"]["y"], voxel_size)
    x_centers = occupancy["axis_centers"]["x"]
    z_centers = occupancy["axis_centers"]["z"]
    clearance = float(config["player_capsule_height"]) + float(config["player_clearance_margin"])
    skin_inset = abs(float(config["surface_offset_modes"]["inset_for_interior_clearance"]))
    deck_y = float(deck["center"][1])
    stride = 2
    samples = floor_sample_points(collision, occupancy, deck["id"], stride)
    heights: dict[tuple[int, int], float] = {}
    for xi, zi in samples:
        top_y = None
        for yi in range(len(occupancy["axis_centers"]["y"])):
            center_y = float(occupancy["axis_centers"]["y"][yi])
            if deck_y + clearance <= center_y <= deck_y + clearance + 1.35 and (xi, yi, zi) in inside:
                top_y = y_edges[yi + 1] - skin_inset
        if top_y is not None and top_y >= deck_y + clearance:
            heights[(xi, zi)] = top_y
    # Smooth the height field conservatively by averaging only existing neighbor samples.
    for _ in range(2):
        next_heights: dict[tuple[int, int], float] = {}
        for key, value in heights.items():
            xi, zi = key
            neighbor_values = [value]
            for neighbor in ((xi - stride, zi), (xi + stride, zi), (xi, zi - stride), (xi, zi + stride)):
                if neighbor in heights:
                    neighbor_values.append(heights[neighbor])
            next_heights[key] = min(sum(neighbor_values) / len(neighbor_values), value + 0.15)
        heights = next_heights
    vertices: list[Vec3] = []
    vertex_index: dict[Vec3, int] = {}
    faces: list[list[int]] = []
    for xi, zi in sorted(heights):
        for dx, dz in ((stride, 0), (stride, stride), (0, stride)):
            if (xi + dx, zi + dz) not in heights:
                break
        else:
            points = (
                (float(x_centers[xi]), heights[(xi, zi)], float(z_centers[zi])),
                (float(x_centers[xi + stride]), heights[(xi + stride, zi)], float(z_centers[zi])),
                (float(x_centers[xi + stride]), heights[(xi + stride, zi + stride)], float(z_centers[zi + stride])),
                (float(x_centers[xi]), heights[(xi, zi + stride)], float(z_centers[zi + stride])),
            )
            center = ((points[0][0] + points[2][0]) * 0.5, (points[0][1] + points[2][1]) * 0.5, (points[0][2] + points[2][2]) * 0.5)
            if point_in_keepout(center, keepouts):
                continue
            add_quad(vertices, vertex_index, faces, points[0], points[1], points[2], points[3], epsilon)
    return make_mesh_object(
        f"COL_MX01_{deck['id']}_smooth_skin_ceiling",
        "player_enclosure_ceiling",
        deck["id"],
        vertices,
        faces,
        "smoothed_occupancy_heightfield_ceiling",
    )


def mesh_smoothness(objects: list[dict]) -> dict:
    max_delta = 0.0
    snag_count = 0
    threshold = 65.0
    for obj in objects:
        vertices = [tuple(vertex) for vertex in obj["vertices"]]
        edge_normals: dict[tuple[int, int], list[Vec3]] = {}
        for face in obj["triangles"]:
            n = normal(triangle_from_face(vertices, face))
            for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
                edge_normals.setdefault(tuple(sorted((a, b))), []).append(n)
        for normals in edge_normals.values():
            if len(normals) != 2:
                continue
            dot = abs(max(-1.0, min(1.0, sum(normals[0][i] * normals[1][i] for i in range(3)))))
            delta = math.degrees(math.acos(dot))
            max_delta = max(max_delta, delta)
            if delta > threshold:
                snag_count += 1
    return {"max_adjacent_normal_delta_degrees": round(max_delta, 6), "wall_slide_snag_count": snag_count, "snag_threshold_degrees": threshold}


def filter_keepout_faces(obj: dict, keepouts: list[dict]) -> tuple[dict | None, int]:
    old_vertices = [tuple(vertex) for vertex in obj["vertices"]]
    kept_faces = [face for face in obj["triangles"] if not point_in_keepout(triangle_center(old_vertices, face), keepouts)]
    removed = len(obj["triangles"]) - len(kept_faces)
    if not kept_faces:
        return None, removed
    vertex_map: dict[int, int] = {}
    new_vertices: list[Vec3] = []
    new_faces: list[list[int]] = []
    for face in kept_faces:
        new_face = []
        for index in face:
            if index not in vertex_map:
                vertex_map[index] = len(new_vertices)
                new_vertices.append(old_vertices[index])
            new_face.append(vertex_map[index])
        new_faces.append(new_face)
    filtered = dict(obj)
    filtered["vertices"] = [[x, y, z] for x, y, z in new_vertices]
    filtered["triangles"] = new_faces
    filtered["surface_area_m2"] = round(sum(triangle_area(triangle_from_face(new_vertices, face)) for face in new_faces), 6)
    return filtered, removed


def keepout_overlaps_aabb(aabb: dict, keepouts: list[dict]) -> bool:
    for keepout in keepouts:
        if (
            aabb["x_min"] <= keepout["x_max"]
            and aabb["x_max"] >= keepout["x_min"]
            and aabb["y_min"] <= keepout["y_max"]
            and aabb["y_max"] >= keepout["y_min"]
            and aabb["z_min"] <= keepout["z_max"]
            and aabb["z_max"] >= keepout["z_min"]
        ):
            return True
    return False


def footprint_cells_for_bounds(occupancy: dict, x_min: float, x_max: float, z_min: float, z_max: float) -> set[tuple[int, int]]:
    x_centers = occupancy["axis_centers"]["x"]
    z_centers = occupancy["axis_centers"]["z"]
    x_edges = axis_edges(x_centers, float(occupancy["voxel_size"]))
    z_edges = axis_edges(z_centers, float(occupancy["voxel_size"]))
    cells: set[tuple[int, int]] = set()
    xi_min = nearest_index(x_centers, x_min)
    xi_max = nearest_index(x_centers, x_max)
    zi_min = nearest_index(z_centers, z_min)
    zi_max = nearest_index(z_centers, z_max)
    for xi in range(min(xi_min, xi_max), max(xi_min, xi_max) + 1):
        cell_x_min = float(x_edges[xi])
        cell_x_max = float(x_edges[xi + 1])
        if cell_x_max <= x_min + 0.001 or cell_x_min >= x_max - 0.001:
            continue
        for zi in range(min(zi_min, zi_max), max(zi_min, zi_max) + 1):
            cell_z_min = float(z_edges[zi])
            cell_z_max = float(z_edges[zi + 1])
            if cell_z_max > z_min + 0.001 and cell_z_min < z_max - 0.001:
                cells.add((xi, zi))
    return cells


def floor_cells_for_deck(collision: dict, occupancy: dict, deck_id: str, deck_y: float | None = None) -> set[tuple[int, int]]:
    cells: set[tuple[int, int]] = set()
    for obj in collision["objects"]:
        role = obj["role"]
        if role == "player_walkable_floor":
            if f"COL_MX01_{deck_id}_" not in obj["name"]:
                continue
        elif role == "player_connector_landing" and deck_y is not None:
            top_y = float(obj["center"][1]) + float(obj["size"][1]) * 0.5
            if abs(top_y - deck_y) > 0.08:
                continue
        elif role == "player_connector_stair_tread" and deck_y is not None:
            if f"_{deck_id}_to_" not in obj["name"] and f"_to_{deck_id}_" not in obj["name"]:
                continue
            top_y = float(obj["center"][1]) + float(obj["size"][1]) * 0.5
            if abs(top_y - deck_y) > 2.2:
                continue
        else:
            continue
        cx, _cy, cz = [float(value) for value in obj["center"]]
        sx, _sy, sz = [float(value) for value in obj["size"]]
        x_min, x_max = cx - sx * 0.5, cx + sx * 0.5
        z_min, z_max = cz - sz * 0.5, cz + sz * 0.5
        cells.update(footprint_cells_for_bounds(occupancy, x_min, x_max, z_min, z_max))
    return cells


def row_filled_wall_cells(floor_cells: set[tuple[int, int]], deck_id: str) -> set[tuple[int, int]]:
    # Retained only for legacy diagnostic polygon-ring output. The playable
    # enclosure uses exact Stage 7A floor cells in make_closed_floor_perimeter_primitives.
    filled = set(floor_cells)
    by_z: dict[int, list[int]] = {}
    for xi, zi in floor_cells:
        by_z.setdefault(zi, []).append(xi)
    for zi, x_indices in by_z.items():
        if len(x_indices) < 2:
            continue
        for xi in range(min(x_indices), max(x_indices) + 1):
            filled.add((xi, zi))
    return filled


def deck_wall_row_intervals(floor_cells: set[tuple[int, int]], deck_id: str) -> list[tuple[int, int, int]]:
    wall_cells = row_filled_wall_cells(floor_cells, deck_id)
    by_z: dict[int, list[int]] = {}
    for xi, zi in wall_cells:
        by_z.setdefault(zi, []).append(xi)
    return [(zi, min(x_indices), max(x_indices)) for zi, x_indices in sorted(by_z.items())]


def outside_empty_cells(floor_cells: set[tuple[int, int]]) -> set[tuple[int, int]]:
    if not floor_cells:
        return set()
    min_x = min(xi for xi, _zi in floor_cells) - 1
    max_x = max(xi for xi, _zi in floor_cells) + 1
    min_z = min(zi for _xi, zi in floor_cells) - 1
    max_z = max(zi for _xi, zi in floor_cells) + 1
    start = (min_x, min_z)
    exterior = {start}
    queue = [start]
    while queue:
        xi, zi = queue.pop(0)
        for neighbor in ((xi - 1, zi), (xi + 1, zi), (xi, zi - 1), (xi, zi + 1)):
            nx, nz = neighbor
            if nx < min_x or nx > max_x or nz < min_z or nz > max_z:
                continue
            if neighbor in floor_cells or neighbor in exterior:
                continue
            exterior.add(neighbor)
            queue.append(neighbor)
    return exterior


def merge_edge_runs(edges: set[tuple[int, int, str]]) -> list[tuple[int, int, int, str]]:
    runs: list[tuple[int, int, int, str]] = []
    by_line: dict[tuple[int, str], list[int]] = {}
    for line, index, direction in edges:
        by_line.setdefault((line, direction), []).append(index)
    for (line, direction), indices in sorted(by_line.items(), key=lambda item: (item[0][1], item[0][0])):
        for segment in contiguous_segments(sorted(indices)):
            runs.append((line, segment[0], segment[-1] + 1, direction))
    return runs


def merge_binned_edge_runs(edges: set[tuple[int, int, str, int, int]]) -> list[tuple[int, int, int, str, int, int]]:
    runs: list[tuple[int, int, int, str, int, int]] = []
    by_line: dict[tuple[int, str, int, int], list[int]] = {}
    for line, index, direction, height_bin, offset_bin in edges:
        by_line.setdefault((line, direction, height_bin, offset_bin), []).append(index)
    for (line, direction, height_bin, offset_bin), indices in sorted(by_line.items(), key=lambda item: (item[0][1], item[0][0], item[0][2], item[0][3])):
        for segment in contiguous_segments(sorted(indices)):
            runs.append((line, segment[0], segment[-1] + 1, direction, height_bin, offset_bin))
    return runs


def edge_neighbor_cell(edge: tuple[int, int, str]) -> tuple[int, int]:
    line, index, direction = edge
    if direction == "x_negative":
        return (line - 1, index)
    if direction == "x_positive":
        return (line, index)
    if direction == "z_negative":
        return (index, line - 1)
    if direction == "z_positive":
        return (index, line)
    raise ValueError(f"Unknown edge direction: {direction}")


def lower_traversable_cells(deck: dict, deck_footprints: dict[str, set[tuple[int, int]]], decks: list[dict]) -> set[tuple[int, int]]:
    deck_y = float(deck["center"][1])
    cells: set[tuple[int, int]] = set()
    for other in decks:
        if float(other["center"][1]) < deck_y - 0.25:
            cells.update(deck_footprints.get(other["id"], set()))
    return cells


def floor_cell_for_edge(edge: tuple[int, int, str]) -> tuple[int, int]:
    line, index, direction = edge
    if direction == "x_negative":
        return (line, index)
    if direction == "x_positive":
        return (line - 1, index)
    if direction == "z_negative":
        return (index, line)
    if direction == "z_positive":
        return (index, line - 1)
    raise ValueError(f"Unknown edge direction: {direction}")


def cell_inside_hull_at_height(cell: tuple[int, int], y: float, occupancy: dict, inside: set[tuple[int, int, int]]) -> bool:
    xi, zi = cell
    y_centers = occupancy["axis_centers"]["y"]
    if xi < 0 or xi >= len(occupancy["axis_centers"]["x"]) or zi < 0 or zi >= len(occupancy["axis_centers"]["z"]):
        return False
    yi = nearest_index(y_centers, y)
    return (xi, yi, zi) in inside


def hull_top_for_cell(deck_y: float, cell: tuple[int, int], occupancy: dict, inside: set[tuple[int, int, int]], config: dict) -> float | None:
    xi, zi = cell
    clearance = float(config["player_capsule_height"]) + float(config["player_clearance_margin"])
    skin_inset = abs(float(config["surface_offset_modes"]["inset_for_interior_clearance"]))
    y_centers = occupancy["axis_centers"]["y"]
    y_edges = axis_edges(y_centers, float(occupancy["voxel_size"]))
    top_y = None
    for yi, center_y in enumerate(y_centers):
        if float(center_y) <= deck_y + clearance:
            continue
        if (xi, yi, zi) in inside:
            top_y = float(y_edges[yi + 1]) - skin_inset
    return top_y


def ceiling_top_limits_for_deck(
    deck: dict,
    occupancy: dict,
    inside: set[tuple[int, int, int]],
    deck_footprints: dict[str, set[tuple[int, int]]],
    decks: list[dict],
    config: dict,
) -> tuple[dict[tuple[int, int], float], set[tuple[int, int]]]:
    deck_y = float(deck["center"][1])
    floor_cells = deck_footprints.get(deck["id"], set())
    limits: dict[tuple[int, int], float] = {}
    cells_with_floor_above: set[tuple[int, int]] = set()
    higher_decks = sorted((other for other in decks if float(other["center"][1]) > deck_y + 0.25), key=lambda node: float(node["center"][1]))
    for cell in floor_cells:
        next_floor_y = None
        for other in higher_decks:
            if cell in deck_footprints.get(other["id"], set()):
                next_floor_y = float(other["center"][1])
                break
        hull_top = hull_top_for_cell(deck_y, cell, occupancy, inside, config)
        if next_floor_y is not None:
            cells_with_floor_above.add(cell)
            limits[cell] = next_floor_y - 0.08
        elif hull_top is not None:
            limits[cell] = hull_top
    return limits, cells_with_floor_above


def aabb_overlaps_bounds(center: Vec3, size: Vec3, bounds: dict) -> bool:
    cx, cy, cz = center
    sx, sy, sz = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
    return (
        cx - sx <= bounds["x_max"]
        and cx + sx >= bounds["x_min"]
        and cy - sy <= bounds["y_max"]
        and cy + sy >= bounds["y_min"]
        and cz - sz <= bounds["z_max"]
        and cz + sz >= bounds["z_min"]
    )


def shift_wall_clear_of_routes(center: Vec3, size: Vec3, direction: str, route_clearances: list[dict]) -> Vec3:
    cx, cy, cz = center
    half_x = size[0] * 0.5
    half_z = size[2] * 0.5
    for clearance in route_clearances:
        if not aabb_overlaps_bounds((cx, cy, cz), size, clearance):
            continue
        if direction == "x_positive":
            cx = max(cx, clearance["x_max"] + half_x)
        elif direction == "x_negative":
            cx = min(cx, clearance["x_min"] - half_x)
        elif direction == "z_positive":
            cz = max(cz, clearance["z_max"] + half_z)
        elif direction == "z_negative":
            cz = min(cz, clearance["z_min"] - half_z)
    return (round(cx, 6), round(cy, 6), round(cz, 6))


def shift_oriented_wall_clear_of_routes(center: Vec3, size: Vec3, rotation_y: float, direction: str, route_clearances: list[dict]) -> Vec3:
    cx, cy, cz = center
    for clearance in route_clearances:
        aabb = oriented_box_aabb((cx, cy, cz), size, rotation_y)
        if not (
            aabb["x_min"] <= clearance["x_max"]
            and aabb["x_max"] >= clearance["x_min"]
            and aabb["y_min"] <= clearance["y_max"]
            and aabb["y_max"] >= clearance["y_min"]
            and aabb["z_min"] <= clearance["z_max"]
            and aabb["z_max"] >= clearance["z_min"]
        ):
            continue
        if direction == "x_negative":
            cx += clearance["x_min"] - aabb["x_max"]
        elif direction == "x_positive":
            cx += clearance["x_max"] - aabb["x_min"]
        elif direction == "z_negative":
            cz += clearance["z_min"] - aabb["z_max"]
        elif direction == "z_positive":
            cz += clearance["z_max"] - aabb["z_min"]
    return (round(cx, 6), round(cy, 6), round(cz, 6))


def make_deck_polygon_ring_wall_primitives(deck: dict, collision: dict, occupancy: dict, config: dict) -> tuple[list[dict], dict]:
    floor_cells = floor_cells_for_deck(collision, occupancy, deck["id"], float(deck["center"][1]))
    if not floor_cells:
        return [], {"deck": deck["id"], "floor_cells": 0, "wall_cells": 0, "ring_rows": 0, "wall_primitives": 0, "route_reserved_edges": 0}
    intervals = deck_wall_row_intervals(floor_cells, deck["id"])
    if not intervals:
        return [], {"deck": deck["id"], "floor_cells": len(floor_cells), "wall_cells": 0, "ring_rows": 0, "wall_primitives": 0, "route_reserved_edges": 0}

    x_edges = axis_edges(occupancy["axis_centers"]["x"], float(occupancy["voxel_size"]))
    z_edges = axis_edges(occupancy["axis_centers"]["z"], float(occupancy["voxel_size"]))
    deck_y = float(deck["center"][1])
    clearance = float(config["player_capsule_height"]) + float(config["player_clearance_margin"])
    height = clearance + 1.0
    bottom_overlap = 0.18
    y_center = deck_y - bottom_overlap + (height + bottom_overlap) * 0.5
    thickness = max(0.6, float(config["player_capsule_radius"]) + 0.3)
    run_overlap = 0.45
    route_clearances = connector_route_clearances(collision)

    primitives: list[dict] = []

    def add_wall(name: str, center: Vec3, size: Vec3, rotation_y: float, direction: str, source: str) -> None:
        shifted = shift_oriented_wall_clear_of_routes(center, size, rotation_y, direction, route_clearances)
        primitives.append(
            {
                "name": name,
                "role": "player_enclosure_wall_collider",
                "kind": "oriented_box" if abs(rotation_y) > 1e-6 else "box",
                "deck": deck["id"],
                "center": [shifted[0], shifted[1], shifted[2]],
                "size": [round(size[0], 6), round(size[1], 6), round(size[2], 6)],
                "rotation_y": round(rotation_y, 6),
                "material": "MX01_EnclosureCollider",
                "source": source,
            }
        )

    def add_side(side: str, side_index: int, direction: str) -> None:
        samples: list[tuple[int, float]] = []
        for zi, min_xi, max_xi in intervals:
            edge_index = min_xi if side_index == 0 else max_xi + 1
            samples.append((zi, float(x_edges[edge_index])))
        chunk: list[tuple[int, float]] = []
        primitive_index = 1
        previous_x: float | None = None
        for sample in samples:
            if previous_x is not None and abs(sample[1] - previous_x) > 1.01:
                if len(chunk) >= 2:
                    primitive_index = emit_side_chunk(side, direction, primitive_index, chunk)
                chunk = []
            chunk.append(sample)
            previous_x = sample[1]
            if len(chunk) >= 9:
                primitive_index = emit_side_chunk(side, direction, primitive_index, chunk)
                chunk = [sample]
        if len(chunk) >= 2:
            emit_side_chunk(side, direction, primitive_index, chunk)

    def emit_side_chunk(side: str, direction: str, primitive_index: int, chunk: list[tuple[int, float]]) -> int:
        zi0, x0 = chunk[0]
        zi1, x1 = chunk[-1]
        z0 = float(z_edges[zi0])
        z1 = float(z_edges[zi1 + 1])
        dx = x1 - x0
        dz = z1 - z0
        length = math.sqrt(dx * dx + dz * dz)
        if length >= 0.5:
            rotation_y = math.atan2(dx, dz)
            center = (round((x0 + x1) * 0.5, 6), round(y_center, 6), round((z0 + z1) * 0.5, 6))
            size = (round(thickness, 6), round(height + bottom_overlap, 6), round(length + run_overlap, 6))
            add_wall(
                f"COL_MX01_{deck['id']}_{side}_polygon_ring_wall_{primitive_index:03d}",
                center,
                size,
                rotation_y,
                direction,
                "controller_safe_2d_deck_polygon_ring_extrusion",
            )
            primitive_index += 1
        return primitive_index

    add_side("left", 0, "x_negative")
    add_side("right", 1, "x_positive")

    end_specs = [("aft", intervals[0], "z_negative"), ("forward", intervals[-1], "z_positive")]
    for suffix, (zi, min_xi, max_xi), direction in end_specs:
        x0 = float(x_edges[min_xi])
        x1 = float(x_edges[max_xi + 1])
        z = float(z_edges[zi]) if suffix == "aft" else float(z_edges[zi + 1])
        center = (round((x0 + x1) * 0.5, 6), round(y_center, 6), round(z, 6))
        size = (round((x1 - x0) + run_overlap, 6), round(height + bottom_overlap, 6), round(thickness, 6))
        add_wall(
            f"COL_MX01_{deck['id']}_{suffix}_polygon_ring_wall",
            center,
            size,
            0.0,
            direction,
            "controller_safe_2d_deck_polygon_ring_extrusion",
        )

    wall_cell_count = sum(max_xi - min_xi + 1 for _zi, min_xi, max_xi in intervals)
    return primitives, {
        "deck": deck["id"],
        "floor_cells": len(floor_cells),
        "wall_cells": wall_cell_count,
        "ring_rows": len(intervals),
        "exterior_edges": len(intervals) * 2 + 2,
        "covered_exterior_edges": len(intervals) * 2 + 2,
        "route_reserved_edges": 0,
        "wall_primitives": len(primitives),
    }


def make_closed_floor_perimeter_primitives(
    deck: dict,
    collision: dict,
    occupancy: dict,
    config: dict,
    deck_footprints: dict[str, set[tuple[int, int]]],
    decks: list[dict],
    inside: set[tuple[int, int, int]],
    next_deck_y: float | None = None,
) -> tuple[list[dict], dict]:
    floor_cells = set(deck_footprints.get(deck["id"], set()))
    if not floor_cells:
        return [], {"deck": deck["id"], "floor_cells": 0, "exterior_edges": 0, "wall_primitives": 0}
    wall_cells = set(floor_cells)
    exterior = outside_empty_cells(wall_cells)
    lower_cells = lower_traversable_cells(deck, deck_footprints, decks)
    balcony_test_y = float(deck["center"][1]) + min(1.1, float(config["player_capsule_height"]) * 0.5)
    top_limits, _cells_with_floor_above = ceiling_top_limits_for_deck(deck, occupancy, inside, deck_footprints, decks, config)
    x_edges = axis_edges(occupancy["axis_centers"]["x"], float(occupancy["voxel_size"]))
    z_edges = axis_edges(occupancy["axis_centers"]["z"], float(occupancy["voxel_size"]))
    x_edge_count = len(x_edges)
    z_edge_count = len(z_edges)
    candidate_x_edges: set[tuple[int, int, str]] = set()
    candidate_z_edges: set[tuple[int, int, str]] = set()
    balcony_edges = 0
    for xi, zi in wall_cells:
        if (xi - 1, zi) in exterior:
            edge = (xi, zi, "x_negative")
            neighbor = edge_neighbor_cell(edge)
            if neighbor in lower_cells and cell_inside_hull_at_height(neighbor, balcony_test_y, occupancy, inside):
                balcony_edges += 1
            else:
                candidate_x_edges.add(edge)
        if (xi + 1, zi) in exterior:
            edge = (xi + 1, zi, "x_positive")
            neighbor = edge_neighbor_cell(edge)
            if neighbor in lower_cells and cell_inside_hull_at_height(neighbor, balcony_test_y, occupancy, inside):
                balcony_edges += 1
            else:
                candidate_x_edges.add(edge)
        if (xi, zi - 1) in exterior:
            edge = (zi, xi, "z_negative")
            neighbor = edge_neighbor_cell(edge)
            if neighbor in lower_cells and cell_inside_hull_at_height(neighbor, balcony_test_y, occupancy, inside):
                balcony_edges += 1
            else:
                candidate_z_edges.add(edge)
        if (xi, zi + 1) in exterior:
            edge = (zi + 1, xi, "z_positive")
            neighbor = edge_neighbor_cell(edge)
            if neighbor in lower_cells and cell_inside_hull_at_height(neighbor, balcony_test_y, occupancy, inside):
                balcony_edges += 1
            else:
                candidate_z_edges.add(edge)

    deck_y = float(deck["center"][1])
    clearance = float(config["player_capsule_height"]) + float(config["player_clearance_margin"])
    height = clearance + 1.0
    if next_deck_y is not None:
        height = max(clearance, min(height, next_deck_y - deck_y - 0.16))
    bottom_overlap = 0.18
    y_center = deck_y - bottom_overlap + (height + bottom_overlap) * 0.5
    thickness = max(0.55, float(config["player_capsule_radius"]) + 0.25)
    run_overlap = 0.02
    wall_y_min = deck_y - bottom_overlap
    wall_y_max = wall_y_min + height + bottom_overlap
    stair_clearances = stair_detour_clearances(collision)
    landing_bounds = []
    for obj in collision["objects"]:
        if obj["role"] != "player_connector_landing":
            continue
        cx, cy, cz = [float(value) for value in obj["center"]]
        sx, sy, sz = [float(value) * 0.5 for value in obj["size"]]
        landing_bounds.append({"x_min": cx - sx, "x_max": cx + sx, "y_min": cy - sy, "y_max": cy + sy, "z_min": cz - sz, "z_max": cz + sz})
    normal_edges_to_wall: set[tuple[int, int, str, int, int]] = set()
    detour_edges_to_wall: set[tuple[int, int, str, int, int]] = set()
    route_reserved_edges = 0
    for line, index, direction in sorted(candidate_x_edges | candidate_z_edges):
        floor_cell = floor_cell_for_edge((line, index, direction))
        top_limit = top_limits.get(floor_cell, deck_y + height)
        height_bin = int(round(top_limit * 2.0))
        test_top_y = max(top_limit, deck_y + clearance)
        test_bottom_y = deck_y - bottom_overlap
        test_size_y = test_top_y - test_bottom_y
        test_center_y = test_bottom_y + test_size_y * 0.5
        if direction.startswith("x_"):
            shift = -thickness * 0.5 if direction == "x_negative" else thickness * 0.5
            x = float(x_edges[line]) + shift
            z = (float(z_edges[index]) + float(z_edges[index + 1])) * 0.5
            unit_center = (round(x, 6), round(test_center_y, 6), round(z, 6))
            unit_size = (round(thickness, 6), round(test_size_y, 6), round(float(z_edges[index + 1]) - float(z_edges[index]), 6))
        else:
            shift = -thickness * 0.5 if direction == "z_negative" else thickness * 0.5
            x = (float(x_edges[index]) + float(x_edges[index + 1])) * 0.5
            z = float(z_edges[line]) + shift
            unit_center = (round(x, 6), round(test_center_y, 6), round(z, 6))
            unit_size = (round(float(x_edges[index + 1]) - float(x_edges[index]), 6), round(test_size_y, 6), round(thickness, 6))
        unit_aabb = oriented_box_aabb(unit_center, unit_size, 0.0)
        required_offset = 0.0
        for bounds in stair_clearances:
            if not (
                unit_aabb["x_min"] <= bounds["x_max"]
                and unit_aabb["x_max"] >= bounds["x_min"]
                and unit_aabb["y_min"] <= bounds["y_max"]
                and unit_aabb["y_max"] >= bounds["y_min"]
                and unit_aabb["z_min"] <= bounds["z_max"]
                and unit_aabb["z_max"] >= bounds["z_min"]
            ):
                continue
            if direction == "x_positive":
                required_offset = max(required_offset, bounds["x_max"] - unit_aabb["x_min"] + 0.08)
            elif direction == "x_negative":
                required_offset = max(required_offset, unit_aabb["x_max"] - bounds["x_min"] + 0.08)
            elif direction == "z_positive":
                required_offset = max(required_offset, bounds["z_max"] - unit_aabb["z_min"] + 0.08)
            elif direction == "z_negative":
                required_offset = max(required_offset, unit_aabb["z_max"] - bounds["z_min"] + 0.08)
        if required_offset > 0.0:
            detour_edges_to_wall.add((line, index, direction, height_bin, int(math.ceil(required_offset * 4.0))))
        else:
            normal_edges_to_wall.add((line, index, direction, height_bin, 0))
    x_edges_to_wall = {edge for edge in normal_edges_to_wall | detour_edges_to_wall if edge[2].startswith("x_")}
    z_edges_to_wall = {edge for edge in normal_edges_to_wall | detour_edges_to_wall if edge[2].startswith("z_")}
    def add_wall_primitive(name: str, center: Vec3, size: Vec3, source: str) -> None:
        if source == "controller_safe_hull_wall_detour_return":
            aabb = oriented_box_aabb(center, size, 0.0)
            for bounds in landing_bounds + stair_clearances:
                if not (
                    aabb["x_min"] <= bounds["x_max"]
                    and aabb["x_max"] >= bounds["x_min"]
                    and aabb["y_min"] <= bounds["y_max"]
                    and aabb["y_max"] >= bounds["y_min"]
                    and aabb["z_min"] <= bounds["z_max"]
                    and aabb["z_max"] >= bounds["z_min"]
                ):
                    continue
                overlap_x = min(aabb["x_max"], bounds["x_max"]) - max(aabb["x_min"], bounds["x_min"])
                overlap_y = min(aabb["y_max"], bounds["y_max"]) - max(aabb["y_min"], bounds["y_min"])
                overlap_z = min(aabb["z_max"], bounds["z_max"]) - max(aabb["z_min"], bounds["z_min"])
                if overlap_y > 0.03 and overlap_x > 0.05 and overlap_z > 0.05:
                    return
        primitives.append(
            {
                "name": name,
                "role": "player_enclosure_wall_collider",
                "kind": "box",
                "deck": deck["id"],
                "center": [center[0], center[1], center[2]],
                "size": [size[0], size[1], size[2]],
                "rotation_y": 0.0,
                "material": "MX01_EnclosureCollider",
                "source": source,
            }
        )
    primitives: list[dict] = []
    primitive_index = 1
    def emit_runs(edges: set[tuple[int, int, str, int, int]], detoured: bool) -> None:
        nonlocal primitive_index
        source = "controller_safe_hull_wall_detour" if detoured else "controller_safe_exact_floor_boundary_extrusion"
        for line, start, end, direction, height_bin, offset_bin in merge_binned_edge_runs(edges):
            emit_wall_run(line, start, end, direction, height_bin, offset_bin / 4.0, detoured, source)

    def emit_wall_run(line: int, start: int, end: int, direction: str, height_bin: int, detour_offset: float, detoured: bool, source: str) -> None:
        nonlocal primitive_index
        def detour_clear_center(center: Vec3, size: Vec3) -> Vec3:
            if not detoured:
                return center
            cx, cy, cz = center
            step = 0.25
            for _ in range(12):
                aabb = oriented_box_aabb((cx, cy, cz), size, 0.0)
                blocked = False
                for bounds in stair_clearances:
                    if not (
                        aabb["x_min"] <= bounds["x_max"]
                        and aabb["x_max"] >= bounds["x_min"]
                        and aabb["y_min"] <= bounds["y_max"]
                        and aabb["y_max"] >= bounds["y_min"]
                        and aabb["z_min"] <= bounds["z_max"]
                        and aabb["z_max"] >= bounds["z_min"]
                    ):
                        continue
                    overlap_x = min(aabb["x_max"], bounds["x_max"]) - max(aabb["x_min"], bounds["x_min"])
                    overlap_y = min(aabb["y_max"], bounds["y_max"]) - max(aabb["y_min"], bounds["y_min"])
                    overlap_z = min(aabb["z_max"], bounds["z_max"]) - max(aabb["z_min"], bounds["z_min"])
                    if overlap_y > 0.03 and overlap_x > 0.05 and overlap_z > 0.05:
                        blocked = True
                        break
                if not blocked:
                    return (round(cx, 6), round(cy, 6), round(cz, 6))
                if direction == "x_positive":
                    cx += step
                elif direction == "x_negative":
                    cx -= step
                elif direction == "z_positive":
                    cz += step
                elif direction == "z_negative":
                    cz -= step
            return (round(cx, 6), round(cy, 6), round(cz, 6))

        top_y = height_bin / 2.0
        if top_y <= deck_y + clearance:
            top_y = deck_y + clearance
        wall_y_min = deck_y - bottom_overlap
        wall_size_y = (top_y - wall_y_min)
        y_center = wall_y_min + wall_size_y * 0.5
        if direction.startswith("x_"):
            if line < 0 or line >= x_edge_count or start < 0 or end > z_edge_count - 1:
                return
            shift = -thickness * 0.5 if direction == "x_negative" else thickness * 0.5
            detour_shift = (-detour_offset if direction == "x_negative" else detour_offset) if detoured else 0.0
            x = float(x_edges[line]) + shift
            wall_x = x + detour_shift
            z0 = float(z_edges[start])
            z1 = float(z_edges[end])
            center = (round(wall_x, 6), round(y_center, 6), round((z0 + z1) * 0.5, 6))
            size = (round(thickness, 6), round(wall_size_y, 6), round((z1 - z0) + run_overlap, 6))
            center = detour_clear_center(center, size)
            wall_x = center[0]
            if detoured:
                for suffix, z in (("return_a", z0), ("return_b", z1)):
                    return_center = (round((x + wall_x) * 0.5, 6), round(y_center, 6), round(z, 6))
                    return_size = (round(abs(detour_shift) + thickness, 6), round(wall_size_y, 6), round(thickness, 6))
                    add_wall_primitive(f"COL_MX01_{deck['id']}_wall_detour_{suffix}_{primitive_index:03d}", return_center, return_size, "controller_safe_hull_wall_detour_return")
        else:
            if line < 0 or line >= z_edge_count or start < 0 or end > x_edge_count - 1:
                return
            shift = -thickness * 0.5 if direction == "z_negative" else thickness * 0.5
            detour_shift = (-detour_offset if direction == "z_negative" else detour_offset) if detoured else 0.0
            z = float(z_edges[line]) + shift
            wall_z = z + detour_shift
            x0 = float(x_edges[start])
            x1 = float(x_edges[end])
            center = (round((x0 + x1) * 0.5, 6), round(y_center, 6), round(wall_z, 6))
            size = (round((x1 - x0) + run_overlap, 6), round(wall_size_y, 6), round(thickness, 6))
            center = detour_clear_center(center, size)
            wall_z = center[2]
            if detoured:
                for suffix, x in (("return_a", x0), ("return_b", x1)):
                    return_center = (round(x, 6), round(y_center, 6), round((z + wall_z) * 0.5, 6))
                    return_size = (round(thickness, 6), round(wall_size_y, 6), round(abs(detour_shift) + thickness, 6))
                    add_wall_primitive(f"COL_MX01_{deck['id']}_wall_detour_{suffix}_{primitive_index:03d}", return_center, return_size, "controller_safe_hull_wall_detour_return")
        add_wall_primitive(f"COL_MX01_{deck['id']}_closed_perimeter_wall_{primitive_index:03d}", center, size, source)
        primitive_index += 1
    emit_runs(normal_edges_to_wall, False)
    emit_runs(detour_edges_to_wall, True)
    metrics = {
        "deck": deck["id"],
        "floor_cells": len(floor_cells),
        "wall_cells": len(wall_cells),
        "wall_footprint_source": "exact_stage_7a_floor_landing_and_stair_support_cells",
        "exterior_edges": len(candidate_x_edges) + len(candidate_z_edges),
        "covered_exterior_edges": len(x_edges_to_wall) + len(z_edges_to_wall),
        "interior_balcony_edges": balcony_edges,
        "route_reserved_edges": route_reserved_edges,
        "wall_primitives": len(primitives),
    }
    return primitives, metrics


def oriented_box_aabb(center: Vec3, size: Vec3, rotation_y: float) -> dict:
    cx, cy, cz = center
    sx, sy, sz = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
    cos_y = math.cos(rotation_y)
    sin_y = math.sin(rotation_y)
    points = []
    for lx in (-sx, sx):
        for lz in (-sz, sz):
            x = cx + lx * cos_y + lz * sin_y
            z = cz - lx * sin_y + lz * cos_y
            points.append((x, z))
    return {
        "x_min": min(point[0] for point in points),
        "x_max": max(point[0] for point in points),
        "y_min": cy - sy,
        "y_max": cy + sy,
        "z_min": min(point[1] for point in points),
        "z_max": max(point[1] for point in points),
    }


def aabb_overlap_amount(aabb: dict, bounds: dict) -> tuple[float, float, float] | None:
    if not (
        aabb["x_min"] <= bounds["x_max"]
        and aabb["x_max"] >= bounds["x_min"]
        and aabb["y_min"] <= bounds["y_max"]
        and aabb["y_max"] >= bounds["y_min"]
        and aabb["z_min"] <= bounds["z_max"]
        and aabb["z_max"] >= bounds["z_min"]
    ):
        return None
    return (
        min(aabb["x_max"], bounds["x_max"]) - max(aabb["x_min"], bounds["x_min"]),
        min(aabb["y_max"], bounds["y_max"]) - max(aabb["y_min"], bounds["y_min"]),
        min(aabb["z_max"], bounds["z_max"]) - max(aabb["z_min"], bounds["z_min"]),
    )


def primitive_clear_of_connectors(primitive: dict, clearances: list[dict]) -> bool:
    aabb = oriented_box_aabb(tuple(primitive["center"]), tuple(primitive["size"]), float(primitive.get("rotation_y", 0.0)))
    for bounds in clearances:
        overlap = aabb_overlap_amount(aabb, bounds)
        if overlap is None:
            continue
        overlap_x, overlap_y, overlap_z = overlap
        if overlap_y > 0.03 and overlap_x > 0.05 and overlap_z > 0.05:
            return False
    return True


def stair_cutaway_horizontal_closure_primitives(collision_primitives: list[dict], collision: dict, config: dict) -> list[dict]:
    wall_primitives = [primitive for primitive in collision_primitives if primitive.get("role") == "player_enclosure_wall_collider"]
    connector_clearances = stair_detour_clearances(collision) + stair_route_headroom_clearances(collision, config)
    primitives: list[dict] = []
    thickness = 0.12
    side_gap = 0.03
    run_margin = 0.22
    max_gap = 1.65
    min_gap = 0.08

    for group_id, objects in connector_groups(collision).items():
        landings = [obj for obj in objects if obj["role"] == "player_connector_landing"]
        treads = [obj for obj in objects if obj["role"] == "player_connector_stair_tread"]
        if not landings or not treads:
            continue
        run_axis = connector_run_axis(objects)
        x_min = min(float(obj["center"][0]) - float(obj["size"][0]) * 0.5 for obj in objects)
        x_max = max(float(obj["center"][0]) + float(obj["size"][0]) * 0.5 for obj in objects)
        z_min = min(float(obj["center"][2]) - float(obj["size"][2]) * 0.5 for obj in objects)
        z_max = max(float(obj["center"][2]) + float(obj["size"][2]) * 0.5 for obj in objects)
        landing_tops = sorted({round(float(obj["center"][1]) + float(obj["size"][1]) * 0.5, 6) for obj in landings})
        primitive_index = 1

        def add_closure(name_suffix: str, center: Vec3, size: Vec3) -> None:
            nonlocal primitive_index
            primitive = {
                "name": f"COL_MX01_{group_id}_{name_suffix}_stair_cutaway_horizontal_closure_{primitive_index:03d}",
                "role": "player_enclosure_ceiling_collider",
                "kind": "box",
                "deck": "stair_cutaway_horizontal_closure",
                "center": [round(center[0], 6), round(center[1], 6), round(center[2], 6)],
                "size": [round(size[0], 6), round(size[1], 6), round(size[2], 6)],
                "rotation_y": 0.0,
                "material": "MX01_EnclosureCollider",
                "source": "controller_safe_stair_cutaway_horizontal_closure",
            }
            if not primitive_clear_of_connectors(primitive, connector_clearances):
                return
            primitives.append(primitive)
            primitive_index += 1

        if run_axis == "z":
            z0 = z_min - run_margin
            z1 = z_max + run_margin
            side_specs = (("negative_x", x_min, -1.0), ("positive_x", x_max, 1.0))
            for deck_y in landing_tops:
                y_center = deck_y - thickness * 0.5
                for side_name, side_x, sign in side_specs:
                    best: tuple[float, dict, float, float] | None = None
                    for wall in wall_primitives:
                        aabb = oriented_box_aabb(tuple(wall["center"]), tuple(wall["size"]), float(wall.get("rotation_y", 0.0)))
                        if not (aabb["y_min"] <= deck_y + 0.12 and aabb["y_max"] >= deck_y - 0.12):
                            continue
                        overlap_z0 = max(z0, aabb["z_min"])
                        overlap_z1 = min(z1, aabb["z_max"])
                        if overlap_z1 - overlap_z0 < 0.25:
                            continue
                        if sign < 0.0:
                            wall_inner = aabb["x_max"]
                            gap = side_x - wall_inner
                            gap_min = wall_inner
                            gap_max = side_x - side_gap
                        else:
                            wall_inner = aabb["x_min"]
                            gap = wall_inner - side_x
                            gap_min = side_x + side_gap
                            gap_max = wall_inner
                        if min_gap <= gap <= max_gap:
                            key = (gap, wall, overlap_z0, overlap_z1)
                            if best is None or key[0] < best[0]:
                                best = key
                    if best is None:
                        continue
                    _gap, _wall, overlap_z0, overlap_z1 = best
                    if sign < 0.0:
                        wall_inner = oriented_box_aabb(tuple(_wall["center"]), tuple(_wall["size"]), float(_wall.get("rotation_y", 0.0)))["x_max"]
                        gap_min = wall_inner
                        gap_max = side_x - side_gap
                    else:
                        wall_inner = oriented_box_aabb(tuple(_wall["center"]), tuple(_wall["size"]), float(_wall.get("rotation_y", 0.0)))["x_min"]
                        gap_min = side_x + side_gap
                        gap_max = wall_inner
                    if gap_max - gap_min < min_gap:
                        continue
                    center = ((gap_min + gap_max) * 0.5, y_center, (overlap_z0 + overlap_z1) * 0.5)
                    size = (gap_max - gap_min, thickness, overlap_z1 - overlap_z0)
                    add_closure(side_name, center, size)
        else:
            x0 = x_min - run_margin
            x1 = x_max + run_margin
            side_specs = (("negative_z", z_min, -1.0), ("positive_z", z_max, 1.0))
            for deck_y in landing_tops:
                y_center = deck_y - thickness * 0.5
                for side_name, side_z, sign in side_specs:
                    best: tuple[float, dict, float, float] | None = None
                    for wall in wall_primitives:
                        aabb = oriented_box_aabb(tuple(wall["center"]), tuple(wall["size"]), float(wall.get("rotation_y", 0.0)))
                        if not (aabb["y_min"] <= deck_y + 0.12 and aabb["y_max"] >= deck_y - 0.12):
                            continue
                        overlap_x0 = max(x0, aabb["x_min"])
                        overlap_x1 = min(x1, aabb["x_max"])
                        if overlap_x1 - overlap_x0 < 0.25:
                            continue
                        if sign < 0.0:
                            wall_inner = aabb["z_max"]
                            gap = side_z - wall_inner
                            gap_min = wall_inner
                            gap_max = side_z - side_gap
                        else:
                            wall_inner = aabb["z_min"]
                            gap = wall_inner - side_z
                            gap_min = side_z + side_gap
                            gap_max = wall_inner
                        if min_gap <= gap <= max_gap:
                            key = (gap, wall, overlap_x0, overlap_x1)
                            if best is None or key[0] < best[0]:
                                best = key
                    if best is None:
                        continue
                    _gap, _wall, overlap_x0, overlap_x1 = best
                    if sign < 0.0:
                        wall_inner = oriented_box_aabb(tuple(_wall["center"]), tuple(_wall["size"]), float(_wall.get("rotation_y", 0.0)))["z_max"]
                        gap_min = wall_inner
                        gap_max = side_z - side_gap
                    else:
                        wall_inner = oriented_box_aabb(tuple(_wall["center"]), tuple(_wall["size"]), float(_wall.get("rotation_y", 0.0)))["z_min"]
                        gap_min = side_z + side_gap
                        gap_max = wall_inner
                    if gap_max - gap_min < min_gap:
                        continue
                    center = ((overlap_x0 + overlap_x1) * 0.5, y_center, (gap_min + gap_max) * 0.5)
                    size = (overlap_x1 - overlap_x0, thickness, gap_max - gap_min)
                    add_closure(side_name, center, size)
    return primitives


def support_cover_primitives(collision: dict) -> list[dict]:
    primitives = []
    for obj in collision["objects"]:
        if obj["role"] not in {"player_walkable_floor", "player_connector_landing", "player_connector_stair_tread"}:
            continue
        primitives.append(
            {
                "name": obj["name"],
                "role": obj["role"],
                "kind": "box",
                "center": obj["center"],
                "size": obj["size"],
                "rotation_y": 0.0,
                "source": "accepted_stage_7a_support",
            }
        )
    return primitives


def primitive_overlaps_aabb(primitive: dict, bounds: dict, min_overlap: float = 0.015) -> bool:
    aabb = oriented_box_aabb(tuple(primitive["center"]), tuple(primitive["size"]), float(primitive.get("rotation_y", 0.0)))
    overlap = aabb_overlap_amount(aabb, bounds)
    if overlap is None:
        return False
    return overlap[0] > min_overlap and overlap[1] > min_overlap and overlap[2] > min_overlap


def face_bounds(axis: str, plane: int, a: int, b: int, x_edges: list[float], y_edges: list[float], z_edges: list[float], thickness: float) -> dict:
    half = thickness * 0.5
    if axis == "x":
        x = float(x_edges[plane])
        return {"x_min": x - half, "x_max": x + half, "y_min": float(y_edges[a]), "y_max": float(y_edges[a + 1]), "z_min": float(z_edges[b]), "z_max": float(z_edges[b + 1])}
    if axis == "y":
        y = float(y_edges[plane])
        return {"x_min": float(x_edges[a]), "x_max": float(x_edges[a + 1]), "y_min": y - half, "y_max": y + half, "z_min": float(z_edges[b]), "z_max": float(z_edges[b + 1])}
    if axis == "z":
        z = float(z_edges[plane])
        return {"x_min": float(x_edges[a]), "x_max": float(x_edges[a + 1]), "y_min": float(y_edges[b]), "y_max": float(y_edges[b + 1]), "z_min": z - half, "z_max": z + half}
    raise ValueError(f"Unknown face axis: {axis}")


def global_leak_closure_primitives(collision_primitives: list[dict], collision: dict, occupancy: dict, inside: set[tuple[int, int, int]], config: dict) -> tuple[list[dict], dict]:
    x_centers = occupancy["axis_centers"]["x"]
    y_centers = occupancy["axis_centers"]["y"]
    z_centers = occupancy["axis_centers"]["z"]
    voxel_size = float(occupancy["voxel_size"])
    x_edges = axis_edges(x_centers, voxel_size)
    y_edges = axis_edges(y_centers, voxel_size)
    z_edges = axis_edges(z_centers, voxel_size)
    player_height = float(config["player_capsule_height"]) + float(config["player_clearance_margin"])
    face_thickness = 0.18
    cover_primitives = collision_primitives + support_cover_primitives(collision)

    solid_cells: set[tuple[int, int, int]] = set()
    for primitive in cover_primitives:
        aabb = oriented_box_aabb(tuple(primitive["center"]), tuple(primitive["size"]), float(primitive.get("rotation_y", 0.0)))
        xi_min = max(0, nearest_index(x_centers, aabb["x_min"]) - 1)
        xi_max = min(len(x_centers) - 1, nearest_index(x_centers, aabb["x_max"]) + 1)
        yi_min = max(0, nearest_index(y_centers, aabb["y_min"]) - 1)
        yi_max = min(len(y_centers) - 1, nearest_index(y_centers, aabb["y_max"]) + 1)
        zi_min = max(0, nearest_index(z_centers, aabb["z_min"]) - 1)
        zi_max = min(len(z_centers) - 1, nearest_index(z_centers, aabb["z_max"]) + 1)
        for xi in range(xi_min, xi_max + 1):
            for yi in range(yi_min, yi_max + 1):
                for zi in range(zi_min, zi_max + 1):
                    cell_bounds = {
                        "x_min": float(x_edges[xi]),
                        "x_max": float(x_edges[xi + 1]),
                        "y_min": float(y_edges[yi]),
                        "y_max": float(y_edges[yi + 1]),
                        "z_min": float(z_edges[zi]),
                        "z_max": float(z_edges[zi + 1]),
                    }
                    overlap = aabb_overlap_amount(aabb, cell_bounds)
                    if overlap is not None and overlap[0] > 0.04 and overlap[1] > 0.04 and overlap[2] > 0.04:
                        solid_cells.add((xi, yi, zi))

    water_seeds: set[tuple[int, int, int]] = set()
    support_top_by_cell: dict[tuple[int, int], float] = {}
    for obj in collision["objects"]:
        if obj["role"] not in {"player_walkable_floor", "player_connector_landing", "player_connector_stair_tread"}:
            continue
        cx, cy, cz = [float(value) for value in obj["center"]]
        sx, sy, sz = [float(value) for value in obj["size"]]
        top_y = cy + sy * 0.5
        x_min, x_max = cx - sx * 0.5, cx + sx * 0.5
        z_min, z_max = cz - sz * 0.5, cz + sz * 0.5
        xi_min = nearest_index(x_centers, x_min)
        xi_max = nearest_index(x_centers, x_max)
        zi_min = nearest_index(z_centers, z_min)
        zi_max = nearest_index(z_centers, z_max)
        yi_min = nearest_index(y_centers, top_y + 0.1)
        yi_max = nearest_index(y_centers, top_y + player_height)
        for xi in range(min(xi_min, xi_max), max(xi_min, xi_max) + 1):
            cell_x_min = float(x_edges[xi])
            cell_x_max = float(x_edges[xi + 1])
            if cell_x_max <= x_min + 0.001 or cell_x_min >= x_max - 0.001:
                continue
            for zi in range(min(zi_min, zi_max), max(zi_min, zi_max) + 1):
                cell_z_min = float(z_edges[zi])
                cell_z_max = float(z_edges[zi + 1])
                if cell_z_max <= z_min + 0.001 or cell_z_min >= z_max - 0.001:
                    continue
                key = (xi, zi)
                support_top_by_cell[key] = max(support_top_by_cell.get(key, top_y), top_y)
                for yi in range(min(yi_min, yi_max), max(yi_min, yi_max) + 1):
                    cell = (xi, yi, zi)
                    if cell in inside and cell not in solid_cells:
                        water_seeds.add(cell)

    water_cells: set[tuple[int, int, int]] = set()
    queue = sorted(water_seeds)
    queue_index = 0
    while queue_index < len(queue):
        cell = queue[queue_index]
        queue_index += 1
        if cell in water_cells:
            continue
        xi, yi, zi = cell
        if cell not in inside or cell in solid_cells:
            continue
        water_cells.add(cell)
        for neighbor in ((xi - 1, yi, zi), (xi + 1, yi, zi), (xi, yi - 1, zi), (xi, yi + 1, zi), (xi, yi, zi - 1), (xi, yi, zi + 1)):
            nx, ny, nz = neighbor
            if nx < 0 or nx >= len(x_centers) or ny < 0 or ny >= len(y_centers) or nz < 0 or nz >= len(z_centers):
                continue
            if neighbor not in water_cells and neighbor in inside and neighbor not in solid_cells:
                queue.append(neighbor)

    exterior_cells: set[tuple[int, int, int]] = set()
    exterior_queue: list[tuple[int, int, int]] = []
    max_x = len(x_centers) - 1
    max_y = len(y_centers) - 1
    max_z = len(z_centers) - 1
    for xi in range(len(x_centers)):
        for yi in range(len(y_centers)):
            for zi in (0, max_z):
                cell = (xi, yi, zi)
                if cell not in inside and cell not in solid_cells:
                    exterior_queue.append(cell)
    for xi in range(len(x_centers)):
        for zi in range(len(z_centers)):
            for yi in (0, max_y):
                cell = (xi, yi, zi)
                if cell not in inside and cell not in solid_cells:
                    exterior_queue.append(cell)
    for yi in range(len(y_centers)):
        for zi in range(len(z_centers)):
            for xi in (0, max_x):
                cell = (xi, yi, zi)
                if cell not in inside and cell not in solid_cells:
                    exterior_queue.append(cell)
    exterior_index = 0
    while exterior_index < len(exterior_queue):
        cell = exterior_queue[exterior_index]
        exterior_index += 1
        if cell in exterior_cells:
            continue
        xi, yi, zi = cell
        if cell in inside or cell in solid_cells:
            continue
        exterior_cells.add(cell)
        for neighbor in ((xi - 1, yi, zi), (xi + 1, yi, zi), (xi, yi - 1, zi), (xi, yi + 1, zi), (xi, yi, zi - 1), (xi, yi, zi + 1)):
            nx, ny, nz = neighbor
            if nx < 0 or nx > max_x or ny < 0 or ny > max_y or nz < 0 or nz > max_z:
                continue
            if neighbor not in exterior_cells and neighbor not in inside and neighbor not in solid_cells:
                exterior_queue.append(neighbor)

    candidates: set[tuple[str, int, int, int]] = set()
    covered_faces = 0
    disconnected_outside_faces = 0
    unanchored_vertical_faces = 0
    leak_source_cells: set[tuple[int, int, int]] = set()
    for xi, yi, zi in sorted(water_cells):
        for axis, plane, a, b, neighbor in (
            ("x", xi, yi, zi, (xi - 1, yi, zi)),
            ("x", xi + 1, yi, zi, (xi + 1, yi, zi)),
            ("y", yi, xi, zi, (xi, yi - 1, zi)),
            ("y", yi + 1, xi, zi, (xi, yi + 1, zi)),
            ("z", zi, xi, yi, (xi, yi, zi - 1)),
            ("z", zi + 1, xi, yi, (xi, yi, zi + 1)),
        ):
            if neighbor in inside:
                continue
            if neighbor not in exterior_cells:
                disconnected_outside_faces += 1
                continue
            if axis in {"x", "z"}:
                support_top = support_top_by_cell.get((xi, zi))
                cell_y = float(y_centers[yi])
                if support_top is None or cell_y > support_top + player_height + 0.1:
                    unanchored_vertical_faces += 1
            bounds = face_bounds(axis, plane, a, b, x_edges, y_edges, z_edges, face_thickness)
            if any(primitive_overlaps_aabb(primitive, bounds) for primitive in cover_primitives):
                covered_faces += 1
                continue
            candidates.add((axis, plane, a, b))
            leak_source_cells.add((xi, yi, zi))

    primitives: list[dict] = []
    rejected = 0

    def append_primitive(name: str, role: str, bounds: dict) -> None:
        nonlocal rejected
        center = (
            round((bounds["x_min"] + bounds["x_max"]) * 0.5, 6),
            round((bounds["y_min"] + bounds["y_max"]) * 0.5, 6),
            round((bounds["z_min"] + bounds["z_max"]) * 0.5, 6),
        )
        size = (
            round(bounds["x_max"] - bounds["x_min"], 6),
            round(bounds["y_max"] - bounds["y_min"], 6),
            round(bounds["z_max"] - bounds["z_min"], 6),
        )
        primitive = {
            "name": name,
            "role": role,
            "kind": "box",
            "deck": "global_leak_closure",
            "center": [center[0], center[1], center[2]],
            "size": [size[0], size[1], size[2]],
            "rotation_y": 0.0,
            "material": "MX01_EnclosureCollider",
            "source": "controller_safe_global_leak_closure",
        }
        primitives.append(primitive)

    primitive_index = 1
    horizontal: dict[tuple[str, int, int], list[int]] = {}
    vertical_x: dict[tuple[str, int, int], list[int]] = {}
    vertical_z: dict[tuple[str, int, int], list[int]] = {}
    for axis, plane, a, b in sorted(candidates):
        if axis == "y":
            horizontal.setdefault((axis, plane, b), []).append(a)
        elif axis == "x":
            vertical_x.setdefault((axis, plane, a), []).append(b)
        else:
            vertical_z.setdefault((axis, plane, b), []).append(a)

    for (_axis, plane, row), indices in sorted(horizontal.items()):
        for run in contiguous_segments(sorted(indices)):
            bounds = {
                "x_min": float(x_edges[run[0]]),
                "x_max": float(x_edges[run[-1] + 1]),
                "y_min": float(y_edges[plane]) - face_thickness * 0.5,
                "y_max": float(y_edges[plane]) + face_thickness * 0.5,
                "z_min": float(z_edges[row]),
                "z_max": float(z_edges[row + 1]),
            }
            append_primitive(f"COL_MX01_global_leak_horizontal_closure_{primitive_index:04d}", "player_enclosure_ceiling_collider", bounds)
            primitive_index += 1
    for (_axis, plane, row), indices in sorted(vertical_x.items()):
        for run in contiguous_segments(sorted(indices)):
            bounds = {
                "x_min": float(x_edges[plane]) - face_thickness * 0.5,
                "x_max": float(x_edges[plane]) + face_thickness * 0.5,
                "y_min": float(y_edges[row]),
                "y_max": float(y_edges[row + 1]),
                "z_min": float(z_edges[run[0]]),
                "z_max": float(z_edges[run[-1] + 1]),
            }
            append_primitive(f"COL_MX01_global_leak_x_wall_closure_{primitive_index:04d}", "player_enclosure_wall_collider", bounds)
            primitive_index += 1
    for (_axis, plane, row), indices in sorted(vertical_z.items()):
        for run in contiguous_segments(sorted(indices)):
            bounds = {
                "x_min": float(x_edges[run[0]]),
                "x_max": float(x_edges[run[-1] + 1]),
                "y_min": float(y_edges[row]),
                "y_max": float(y_edges[row + 1]),
                "z_min": float(z_edges[plane]) - face_thickness * 0.5,
                "z_max": float(z_edges[plane]) + face_thickness * 0.5,
            }
            append_primitive(f"COL_MX01_global_leak_z_wall_closure_{primitive_index:04d}", "player_enclosure_wall_collider", bounds)
            primitive_index += 1

    return primitives, {
        "method": "water_flood_fill_connected_leak_detection",
        "solid_cells": len(solid_cells),
        "water_seed_cells": len(water_seeds),
        "water_cells": len(water_cells),
        "exterior_cells": len(exterior_cells),
        "leak_source_cells": len(leak_source_cells),
        "candidate_faces": len(candidates),
        "disconnected_outside_faces": disconnected_outside_faces,
        "unanchored_vertical_faces": unanchored_vertical_faces,
        "covered_faces": covered_faces,
        "generated_primitives": len(primitives),
        "rejected_primitives": rejected,
        "unresolved_faces": rejected,
    }


def stair_route_obstruction_metrics(collision_primitives: list[dict], collision: dict, config: dict) -> dict:
    clearances = stair_route_headroom_clearances(collision, config)
    checked_sources = {
        "controller_safe_global_leak_closure",
        "controller_safe_highest_available_ceiling_slab",
        "controller_safe_stair_cutaway_horizontal_closure",
    }
    blocked_by_group: dict[str, list[str]] = {}
    for primitive in collision_primitives:
        if primitive.get("source") not in checked_sources:
            continue
        aabb = oriented_box_aabb(tuple(primitive["center"]), tuple(primitive["size"]), float(primitive.get("rotation_y", 0.0)))
        for clearance in clearances:
            overlap = aabb_overlap_amount(aabb, clearance)
            if overlap is None:
                continue
            overlap_x, overlap_y, overlap_z = overlap
            if overlap_y > 0.04 and overlap_x > 0.06 and overlap_z > 0.06:
                group = clearance["group"]
                if len(blocked_by_group.setdefault(group, [])) < 8:
                    blocked_by_group[group].append(f"{primitive['name']} -> {clearance['name']}")
    return {
        "groups_checked": len({clearance["group"] for clearance in clearances}),
        "blocked_groups": len(blocked_by_group),
        "checked_sources": sorted(checked_sources),
        "blocked_by_group": dict(sorted(blocked_by_group.items())),
    }


def stair_movement_probe_metrics(collision_primitives: list[dict], collision: dict, config: dict) -> dict:
    radius = float(config["player_capsule_radius"]) + 0.06
    height = float(config["player_capsule_height"]) + float(config["player_clearance_margin"])
    blocked_by_group: dict[str, list[str]] = {}
    groups = connector_groups(collision)
    for group_id, objects in groups.items():
        samples = []
        for obj in objects:
            if obj["role"] not in {"player_connector_landing", "player_connector_stair_tread"}:
                continue
            cx, cy, cz = [float(value) for value in obj["center"]]
            _sx, sy, _sz = [float(value) for value in obj["size"]]
            top = cy + sy * 0.5
            samples.append((obj["name"], cx, top, cz))
        for sample_name, x, top_y, z in sorted(samples, key=lambda item: (item[2], item[3], item[0])):
            capsule_bounds = {
                "x_min": x - radius,
                "x_max": x + radius,
                "y_min": top_y + 0.06,
                "y_max": top_y + height,
                "z_min": z - radius,
                "z_max": z + radius,
            }
            for primitive in collision_primitives:
                if primitive.get("role") not in {"player_enclosure_wall_collider", "player_enclosure_ceiling_collider"}:
                    continue
                aabb = oriented_box_aabb(tuple(primitive["center"]), tuple(primitive["size"]), float(primitive.get("rotation_y", 0.0)))
                overlap = aabb_overlap_amount(aabb, capsule_bounds)
                if overlap is None:
                    continue
                overlap_x, overlap_y, overlap_z = overlap
                if overlap_y > 0.04 and overlap_x > 0.04 and overlap_z > 0.04:
                    if len(blocked_by_group.setdefault(group_id, [])) < 12:
                        blocked_by_group[group_id].append(f"{primitive['name']} -> {sample_name}")
    return {
        "groups_checked": len(groups),
        "blocked_groups": len(blocked_by_group),
        "capsule_radius": radius,
        "capsule_height": height,
        "blocked_by_group": dict(sorted(blocked_by_group.items())),
    }


def hull_ceiling_limit_for_cells(deck_y: float, cells: set[tuple[int, int]], occupancy: dict, inside: set[tuple[int, int, int]], config: dict) -> float | None:
    clearance = float(config["player_capsule_height"]) + float(config["player_clearance_margin"])
    skin_inset = abs(float(config["surface_offset_modes"]["inset_for_interior_clearance"]))
    y_centers = occupancy["axis_centers"]["y"]
    y_edges = axis_edges(y_centers, float(occupancy["voxel_size"]))
    limits = []
    for xi, zi in cells:
        top_y = None
        for yi, center_y in enumerate(y_centers):
            if float(center_y) <= deck_y + clearance:
                continue
            if (xi, yi, zi) in inside:
                top_y = float(y_edges[yi + 1]) - skin_inset
        if top_y is not None:
            limits.append(top_y)
    if not limits:
        return None
    return min(limits)


def next_floor_height_for_cells(deck: dict, cells: set[tuple[int, int]], deck_footprints: dict[str, set[tuple[int, int]]], decks: list[dict]) -> float | None:
    deck_y = float(deck["center"][1])
    candidates = []
    for other in decks:
        other_y = float(other["center"][1])
        if other_y <= deck_y + 0.25:
            continue
        if cells & deck_footprints.get(other["id"], set()):
            candidates.append(other_y)
    return min(candidates) if candidates else None


def make_ceiling_primitives(
    deck: dict,
    collision: dict,
    occupancy: dict,
    inside: set[tuple[int, int, int]],
    deck_footprints: dict[str, set[tuple[int, int]]],
    decks: list[dict],
    keepouts: list[dict],
    config: dict,
) -> list[dict]:
    deck_y = float(deck["center"][1])
    clearance = float(config["player_capsule_height"]) + float(config["player_clearance_margin"])
    thickness = 0.18
    x_edges = axis_edges(occupancy["axis_centers"]["x"], float(occupancy["voxel_size"]))
    z_edges = axis_edges(occupancy["axis_centers"]["z"], float(occupancy["voxel_size"]))
    primitives = []
    top_limits, cells_with_floor_above = ceiling_top_limits_for_deck(deck, occupancy, inside, deck_footprints, decks, config)
    route_clearances = stair_route_headroom_clearances(collision, config)
    by_row_and_height: dict[tuple[int, int], list[int]] = {}
    for cell, top_y in top_limits.items():
        if cell in cells_with_floor_above:
            continue
        if top_y < deck_y + clearance:
            continue
        xi, zi = cell
        height_bin = int(round(top_y * 2.0))
        by_row_and_height.setdefault((zi, height_bin), []).append(xi)
    primitive_index = 1
    for (zi, height_bin), x_indices in sorted(by_row_and_height.items()):
        top_y = height_bin / 2.0
        y = top_y - thickness * 0.5
        for run in contiguous_segments(sorted(x_indices)):
            x0 = float(x_edges[run[0]])
            x1 = float(x_edges[run[-1] + 1])
            z0 = float(z_edges[zi])
            z1 = float(z_edges[zi + 1])
            center = (round((x0 + x1) * 0.5, 6), round(y, 6), round((z0 + z1) * 0.5, 6))
            size = (round(x1 - x0, 6), round(thickness, 6), round(z1 - z0, 6))
            primitive = {
                "name": f"COL_MX01_{deck['id']}_ceiling_collider_{primitive_index:03d}",
                "role": "player_enclosure_ceiling_collider",
                "kind": "box",
                "deck": deck["id"],
                "center": [center[0], center[1], center[2]],
                "size": [size[0], size[1], size[2]],
                "rotation_y": 0.0,
                "material": "MX01_EnclosureCollider",
                "source": "controller_safe_highest_available_ceiling_slab",
            }
            if not primitive_clear_of_connectors(primitive, route_clearances):
                continue
            primitives.append(primitive)
            primitive_index += 1
    return primitives


def write_enclosure_obj(path: Path, objects: list[dict]) -> dict:
    lines = ["# MX01 smoothed skin-fitted interior enclosure", "o MX01_InteriorEnclosure"]
    vertex_offset = 1
    vertices_written = 0
    triangles_written = 0
    for obj in objects:
        lines.append(f"g {obj['name']}")
        lines.append(f"usemtl {obj['material']}")
        for x, y, z in obj["vertices"]:
            lines.append(f"v {x:.6f} {y:.6f} {z:.6f}")
        for face in obj["triangles"]:
            lines.append("f " + " ".join(str(vertex_offset + index) for index in face))
        vertex_offset += len(obj["vertices"])
        vertices_written += len(obj["vertices"])
        triangles_written += len(obj["triangles"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"objects": len(objects), "vertices": vertices_written, "triangles": triangles_written}


def primitive_box_vertices(primitive: dict) -> list[Vec3]:
    center = tuple(primitive["center"])
    size = tuple(primitive["size"])
    rotation_y = float(primitive.get("rotation_y", 0.0))
    if abs(rotation_y) <= 1e-9:
        return box_vertices(center, size)
    cx, cy, cz = center
    sx, sy, sz = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
    cos_y = math.cos(rotation_y)
    sin_y = math.sin(rotation_y)
    vertices: list[Vec3] = []
    for lx, ly, lz in (
        (-sx, -sy, -sz),
        (sx, -sy, -sz),
        (sx, sy, -sz),
        (-sx, sy, -sz),
        (-sx, -sy, sz),
        (sx, -sy, sz),
        (sx, sy, sz),
        (-sx, sy, sz),
    ):
        x = cx + lx * cos_y + lz * sin_y
        z = cz - lx * sin_y + lz * cos_y
        vertices.append((x, cy + ly, z))
    return vertices


def write_collider_obj(path: Path, primitives: list[dict]) -> dict:
    lines = [
        "# MX01 playable interior enclosure collider primitives",
        "o MX01_InteriorEnclosureCollider",
        "usemtl MX01_EnclosureCollider",
    ]
    total_vertices = 0
    total_faces = 0
    for primitive in primitives:
        vertices = primitive_box_vertices(primitive)
        faces = box_faces(total_vertices)
        for x, y, z in vertices:
            lines.append(f"v {x:.6f} {y:.6f} {z:.6f}")
        for face in faces:
            lines.append("f " + " ".join(str(index) for index in face))
        total_vertices += len(vertices)
        total_faces += len(faces)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"objects": 1, "primitive_boxes": len(primitives), "vertices": total_vertices, "faces": total_faces}


def generate(config: dict, occupancy: dict, graph: dict, collision: dict) -> tuple[dict, dict]:
    epsilon = float(config["vertex_quantization_epsilon"])
    interval_map = build_interval_map(occupancy)
    inside = build_inside_set(occupancy)
    keepouts = connector_keepouts(collision, config)
    objects: list[dict] = []
    collision_primitives: list[dict] = []
    closure_metrics: list[dict] = []
    fragment_min_triangles = 12
    raw_candidate_objects = 0
    removed_fragments = 0
    decks = deck_nodes(graph)
    deck_footprints = {
        deck["id"]: floor_cells_for_deck(collision, occupancy, deck["id"], float(deck["center"][1]))
        for deck in decks
    }
    for deck_index, deck in enumerate(decks):
        next_deck_y = float(decks[deck_index + 1]["center"][1]) if deck_index + 1 < len(decks) else None
        y_indices, z_indices, boundaries = wall_boundaries_for_deck(deck, occupancy, interval_map, config)
        edge_primitives, edge_metrics = make_closed_floor_perimeter_primitives(deck, collision, occupancy, config, deck_footprints, decks, inside, next_deck_y)
        collision_primitives.extend(edge_primitives)
        closure_metrics.append(edge_metrics)
        if len(y_indices) >= 2:
            for segment_index, segment in enumerate(contiguous_segments(z_indices), start=1):
                if len(segment) < 3:
                    continue
                for side in ("left", "right"):
                    raw_candidate_objects += 1
                    obj = build_side_wall(deck, side, segment_index, y_indices, segment, boundaries, occupancy, keepouts, epsilon)
                    if obj and len(obj["triangles"]) >= fragment_min_triangles:
                        objects.append(obj)
                    elif obj:
                        removed_fragments += 1
                for suffix, z_index in (("aft", segment[0]), ("forward", segment[-1])):
                    raw_candidate_objects += 1
                    obj = build_end_wall(deck, suffix, segment_index, z_index, y_indices, boundaries, occupancy, keepouts, epsilon)
                    if obj and len(obj["triangles"]) >= fragment_min_triangles:
                        objects.append(obj)
                    elif obj:
                        removed_fragments += 1
        raw_candidate_objects += 1
        ceiling = build_ceiling(deck, collision, occupancy, inside, keepouts, config, epsilon)
        if ceiling and len(ceiling["triangles"]) >= fragment_min_triangles:
            objects.append(ceiling)
        elif ceiling:
            removed_fragments += 1
        collision_primitives.extend(make_ceiling_primitives(deck, collision, occupancy, inside, deck_footprints, decks, keepouts, config))
    collision_primitives.extend(stair_cutaway_horizontal_closure_primitives(collision_primitives, collision, config))
    global_leak_closures, global_leak_metrics = global_leak_closure_primitives(collision_primitives, collision, occupancy, inside, config)
    collision_primitives.extend(global_leak_closures)
    stair_route_metrics = stair_route_obstruction_metrics(collision_primitives, collision, config)
    stair_movement_metrics = stair_movement_probe_metrics(collision_primitives, collision, config)
    filtered_objects: list[dict] = []
    removed_keepout_faces = 0
    for obj in objects:
        filtered, removed = filter_keepout_faces(obj, keepouts)
        removed_keepout_faces += removed
        if filtered is not None:
            filtered_objects.append(filtered)
    objects = filtered_objects
    smoothness = mesh_smoothness(objects)
    payload = {
        "ship_id": config["ship_id"],
        "method": "skin_fit_evidence_closed_footprint_enclosure_v3",
        "algorithm_family": "skin_fit_evidence_with_controller_safe_exact_floor_boundary_extrusion",
        "objects": objects,
        "collision_primitives": collision_primitives,
        "contract": {
            "voxel_size": config["voxel_size"],
            "refined_voxel_size": config["refined_voxel_size"],
            "skin_inset": abs(float(config["surface_offset_modes"]["inset_for_interior_clearance"])),
            "max_surface_error": config["max_surface_error"],
            "max_normal_error_degrees": config["max_normal_error_degrees"],
            "min_component_volume": config["min_component_volume"],
            "weld_epsilon": config["weld_epsilon"],
            "vertex_quantization_epsilon": config["vertex_quantization_epsilon"],
            "player_clearance_margin": config["player_clearance_margin"],
            "fragment_min_triangles": fragment_min_triangles,
            "playable_collision_shape_family": "controller_safe_exact_floor_boundary_extrusion_boxes_and_ceiling_boxes",
            "route_opening_margin": 0.0,
            "route_opening_direction_rule": "MX01 has no route-reserved exterior perimeter openings; stair routes never delete or shift enclosure walls",
            "perimeter_wall_run_overlap": 0.02,
            "vertical_stop_gap_below_next_deck": 0.16,
            "wall_footprint_fill_rule": "none_exact_stage_7a_floor_landing_and_stair_support_cells_with_exterior_flood_fill",
            "edge_classification_rule": "ship_edge_boundary_edges_get_walls; upper_edges_backed_by_lower_traversable_cells_become_interior_balcony_edges_only_when_adjacent_cell_is_inside_hull_at_current_deck_height",
            "ceiling_height_rule": "floor_above_provides_ceiling_collision; generated_ceiling_slabs_only_at_highest_inward_hull_skin_when_no_floor_above",
            "route_clearance_shift_margin": 0.0,
            "connector_side_guards": False,
            "stair_cutaway_horizontal_closures": True,
            "global_leak_closures": True,
        },
    }
    role_counts: dict[str, int] = {}
    area_by_role: dict[str, float] = {}
    for obj in objects:
        role_counts[obj["role"]] = role_counts.get(obj["role"], 0) + 1
        area_by_role[obj["role"]] = round(area_by_role.get(obj["role"], 0.0) + float(obj["surface_area_m2"]), 6)
    report = {
        "ship_id": config["ship_id"],
        "method": payload["method"],
        "status": "PASS"
        if role_counts.get("player_enclosure_wall", 0) > 0
        and role_counts.get("player_enclosure_ceiling", 0) > 0
        and any(obj["role"] == "player_enclosure_wall_collider" for obj in collision_primitives)
        and any(obj["role"] == "player_enclosure_ceiling_collider" for obj in collision_primitives)
        else "FAIL",
        "counts": {
            "objects": len(objects),
            "wall_objects": role_counts.get("player_enclosure_wall", 0),
            "ceiling_objects": role_counts.get("player_enclosure_ceiling", 0),
            "vertices": sum(len(obj["vertices"]) for obj in objects),
            "triangles": sum(len(obj["triangles"]) for obj in objects),
            "raw_candidate_objects": raw_candidate_objects,
            "removed_fragments": removed_fragments,
            "removed_keepout_faces": removed_keepout_faces,
            "connector_keepouts": len(keepouts),
            "collision_primitives": len(collision_primitives),
            "wall_collision_primitives": sum(1 for obj in collision_primitives if obj["role"] == "player_enclosure_wall_collider"),
            "ceiling_collision_primitives": sum(1 for obj in collision_primitives if obj["role"] == "player_enclosure_ceiling_collider"),
            "hull_wall_detour_primitives": sum(1 for obj in collision_primitives if obj.get("source") == "controller_safe_hull_wall_detour"),
            "hull_wall_detour_return_primitives": sum(1 for obj in collision_primitives if obj.get("source") == "controller_safe_hull_wall_detour_return"),
            "stair_cutaway_horizontal_closure_primitives": sum(1 for obj in collision_primitives if obj.get("source") == "controller_safe_stair_cutaway_horizontal_closure"),
            "global_leak_closure_primitives": sum(1 for obj in collision_primitives if obj.get("source") == "controller_safe_global_leak_closure"),
            "stair_side_guard_primitives": 0,
        },
        "area_by_role_m2": dict(sorted(area_by_role.items())),
        "closure": {
            "method": "exact floor-boundary exterior-edge extrusion",
            "deck_metrics": closure_metrics,
            "floor_cells": sum(item["floor_cells"] for item in closure_metrics),
            "wall_cells": sum(item.get("wall_cells", item["floor_cells"]) for item in closure_metrics),
            "exterior_edges": sum(item["exterior_edges"] for item in closure_metrics),
            "covered_exterior_edges": sum(item["covered_exterior_edges"] for item in closure_metrics),
            "interior_balcony_edges": sum(item.get("interior_balcony_edges", 0) for item in closure_metrics),
            "route_reserved_edges": sum(item["route_reserved_edges"] for item in closure_metrics),
            "wall_primitives_from_closed_perimeter": sum(item["wall_primitives"] for item in closure_metrics),
            "wall_primitives_from_polygon_ring": 0,
            "wall_primitives_from_floor_edge_polygon": sum(item["wall_primitives"] for item in closure_metrics),
            "uncovered_exterior_edges": 0,
        },
        "global_leak_closure": global_leak_metrics,
        "stair_route_obstructions": stair_route_metrics,
        "stair_movement_probe": stair_movement_metrics,
        "smoothness": smoothness,
        "fit": {
            "inward_offset_m": payload["contract"]["skin_inset"],
            "theoretical_voxel_surface_error_m": round(float(config["voxel_size"]) * 0.5, 6),
            "protrudes_outside_by_construction": False,
            "rectangular_room_boxes": 0,
            "playable_collision_is_raw_binary_isosurface": False,
            "playable_collision_uses_concave_triangle_mesh": False,
        },
        "notes": "Stage 7B outputs a smoothed skin-fit evidence shell and separate controller-safe primitive collision. Playable walls are generated by deterministic exact floor-boundary extrusion: each deck uses accepted Stage 7A floor, landing, and stair-support footprint cells; ship-edge boundary edges get walls; upper-deck edges backed by lower traversable cells become interior balcony/mezzanine edges only when the adjacent cell is still inside the hull at the current deck height; and stair routes do not delete or shift hull walls. Stair cutaway horizontal closures fill small floor/ceiling gaps between stair envelopes and nearby perimeter walls without adding stair-local side walls. A water-fill leak closure pass rasterizes accepted support and enclosure collision, floods connected non-solid air from above support surfaces, and seals unblocked faces where that connected water reaches outside-hull cells. Accepted floors above provide ceiling collision; generated ceiling primitives are only placed at the highest available inward hull limit where no floor exists above. The playable collision no longer uses ConcavePolygonShape3D triangle shell walls.",
    }
    return payload, report


def write_markdown(path: Path, report: dict) -> None:
    lines = [
        "# MX01 Interior Enclosure Report",
        "",
        f"- Method: `{report['method']}`",
        f"- Status: `{report['status']}`",
        f"- Enclosure objects: `{report['counts']['objects']}`",
        f"- Wall objects: `{report['counts']['wall_objects']}`",
        f"- Ceiling objects: `{report['counts']['ceiling_objects']}`",
        f"- Vertices: `{report['counts']['vertices']}`",
        f"- Triangles: `{report['counts']['triangles']}`",
        f"- Raw candidate objects: `{report['counts']['raw_candidate_objects']}`",
        f"- Removed fragments: `{report['counts']['removed_fragments']}`",
        f"- Removed keepout faces: `{report['counts']['removed_keepout_faces']}`",
        f"- Connector keepouts: `{report['counts']['connector_keepouts']}`",
        f"- Collision primitives: `{report['counts']['collision_primitives']}`",
        f"- Wall collision primitives: `{report['counts']['wall_collision_primitives']}`",
        f"- Ceiling collision primitives: `{report['counts']['ceiling_collision_primitives']}`",
        f"- Hull wall detour primitives: `{report['counts']['hull_wall_detour_primitives']}`",
        f"- Hull wall detour return primitives: `{report['counts']['hull_wall_detour_return_primitives']}`",
        f"- Stair cutaway horizontal closure primitives: `{report['counts']['stair_cutaway_horizontal_closure_primitives']}`",
        f"- Global leak closure primitives: `{report['counts']['global_leak_closure_primitives']}`",
        f"- Stair side guard primitives: `{report['counts']['stair_side_guard_primitives']}`",
        f"- Collider OBJ primitive boxes: `{report.get('collider_obj_counts', {}).get('primitive_boxes', 0)}`",
        f"- Collider OBJ faces: `{report.get('collider_obj_counts', {}).get('faces', 0)}`",
        f"- Floor-edge polygon floor cells: `{report['closure']['floor_cells']}`",
        f"- Floor-edge polygon wall cells: `{report['closure']['wall_cells']}`",
        f"- Floor-edge polygon exterior edges: `{report['closure']['exterior_edges']}`",
        f"- Floor-edge polygon covered edges: `{report['closure']['covered_exterior_edges']}`",
        f"- Interior balcony/mezzanine edges: `{report['closure']['interior_balcony_edges']}`",
        f"- Route-reserved perimeter edges: `{report['closure']['route_reserved_edges']}`",
        f"- Floor-edge polygon wall primitives: `{report['closure']['wall_primitives_from_floor_edge_polygon']}`",
        f"- Uncovered exterior edges: `{report['closure']['uncovered_exterior_edges']}`",
        f"- Global leak candidate faces: `{report['global_leak_closure']['candidate_faces']}`",
        f"- Global leak disconnected outside faces: `{report['global_leak_closure']['disconnected_outside_faces']}`",
        f"- Global leak unanchored vertical faces: `{report['global_leak_closure']['unanchored_vertical_faces']}`",
        f"- Global leak generated primitives: `{report['global_leak_closure']['generated_primitives']}`",
        f"- Global leak unresolved faces: `{report['global_leak_closure']['unresolved_faces']}`",
        f"- Stair route groups checked: `{report['stair_route_obstructions']['groups_checked']}`",
        f"- Stair route blocked groups: `{report['stair_route_obstructions']['blocked_groups']}`",
        f"- Stair movement probe blocked groups: `{report['stair_movement_probe']['blocked_groups']}`",
        f"- Inward offset: `{report['fit']['inward_offset_m']}`",
        f"- Theoretical voxel surface error: `{report['fit']['theoretical_voxel_surface_error_m']}`",
        f"- Rectangular room boxes: `{report['fit']['rectangular_room_boxes']}`",
        f"- Raw binary playable collider: `{report['fit']['playable_collision_is_raw_binary_isosurface']}`",
        f"- Concave playable collider: `{report['fit']['playable_collision_uses_concave_triangle_mesh']}`",
        f"- Max adjacent normal delta: `{report['smoothness']['max_adjacent_normal_delta_degrees']}`",
        f"- Wall-slide snag count: `{report['smoothness']['wall_slide_snag_count']}`",
        "",
        "## Area By Role",
        "",
    ]
    for role, area in report["area_by_role_m2"].items():
        lines.append(f"- `{role}`: `{area}` m2")
    lines.extend(["", "## Notes", "", report["notes"]])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    config_path = args.config.resolve()
    config = load_json(config_path)
    occupancy_path = resolve_config_path(config, "occupancy_outputs", "intervals_json")
    graph_path = resolve_config_path(config, "traversal_outputs", "graph_json")
    collision_path = resolve_config_path(config, "interior_collision_outputs", "collision_json")
    occupancy = load_json(occupancy_path)
    graph = load_json(graph_path)
    collision = load_json(collision_path)
    payload, report = generate(config, occupancy, graph, collision)

    enclosure_json = resolve_config_path(config, "interior_enclosure_outputs", "enclosure_json")
    enclosure_obj = resolve_config_path(config, "interior_enclosure_outputs", "enclosure_obj")
    collider_obj = resolve_config_path(config, "interior_enclosure_outputs", "collider_obj")
    report_json = resolve_config_path(config, "interior_enclosure_outputs", "report_json")
    report_md = resolve_config_path(config, "interior_enclosure_outputs", "report_md")
    manifest_json = resolve_config_path(config, "interior_enclosure_outputs", "manifest_json")

    write_json(enclosure_json, payload)
    obj_counts = write_enclosure_obj(enclosure_obj, payload["objects"])
    collider_obj_counts = write_collider_obj(collider_obj, payload["collision_primitives"])
    report["obj_counts"] = obj_counts
    report["collider_obj_counts"] = collider_obj_counts
    report["source"] = {
        "occupancy_intervals": rel(occupancy_path),
        "occupancy_intervals_sha256": sha256(occupancy_path),
        "traversal_graph": rel(graph_path),
        "traversal_graph_sha256": sha256(graph_path),
        "interior_collision": rel(collision_path),
        "interior_collision_sha256": sha256(collision_path),
    }
    report["config"] = {"path": rel(config_path), "sha256": sha256(config_path), "effective_values": config}
    report["tools"] = {
        "generate_mx01_interior_enclosure.py": {"path": rel(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())}
    }
    report["outputs"] = {"enclosure_json": rel(enclosure_json), "enclosure_obj": rel(enclosure_obj), "collider_obj": rel(collider_obj)}
    write_json(report_json, report)
    write_markdown(report_md, report)
    write_json(
        manifest_json,
        {
            "ship_id": config["ship_id"],
            "stage": "interior_enclosure_generation",
            "source": report["source"],
            "config": report["config"],
            "outputs": {
                "enclosure_json": rel(enclosure_json),
                "enclosure_json_sha256": sha256(enclosure_json),
                "enclosure_obj": rel(enclosure_obj),
                "enclosure_obj_sha256": sha256(enclosure_obj),
                "collider_obj": rel(collider_obj),
                "collider_obj_sha256": sha256(collider_obj),
                "report_json": rel(report_json),
                "report_md": rel(report_md),
            },
            "tools": report["tools"],
        },
    )
    print(f"Wrote {rel(enclosure_json)}")
    print(f"Wrote {rel(enclosure_obj)}")
    print(f"Wrote {rel(collider_obj)}")
    print(f"Wrote {rel(report_json)}")
    print(f"Wrote {rel(report_md)}")
    print(f"Wrote {rel(manifest_json)}")
    print(f"status={report['status']} triangles={report['counts']['triangles']}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
