#!/usr/bin/env python3
"""Generate first-pass MX01 interior traversal collision meshes."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import deque
from pathlib import Path

from mesh_writer import write_box_obj


ROOT = Path(__file__).resolve().parents[3]
SHIP_DIR = ROOT / "ships" / "MX01"
DEFAULT_CONFIG = SHIP_DIR / "config" / "mx01_collision_generation.json"


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


def build_inside_set(occupancy: dict) -> set[tuple[int, int, int]]:
    inside: set[tuple[int, int, int]] = set()
    for ray in occupancy["rays"]:
        yi = int(ray["y_index"])
        zi = int(ray["z_index"])
        for start, end in ray["x_intervals"]:
            for xi in range(int(start), int(end) + 1):
                inside.add((xi, yi, zi))
    return inside


def connected_components(cells: set[tuple[int, int]]) -> list[set[tuple[int, int]]]:
    remaining = set(cells)
    components: list[set[tuple[int, int]]] = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        component = {start}
        queue: deque[tuple[int, int]] = deque([start])
        while queue:
            x, z = queue.popleft()
            for neighbor in ((x - 1, z), (x + 1, z), (x, z - 1), (x, z + 1)):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)
        components.append(component)
    components.sort(key=lambda c: (-len(c), min(c)))
    return components


def greedy_rectangles(cells: set[tuple[int, int]]) -> list[tuple[int, int, int, int]]:
    remaining = set(cells)
    rectangles: list[tuple[int, int, int, int]] = []
    while remaining:
        x0, z0 = min(remaining, key=lambda cell: (cell[1], cell[0]))
        width = 1
        while (x0 + width, z0) in remaining:
            width += 1
        depth = 1
        while True:
            next_z = z0 + depth
            row = {(x, next_z) for x in range(x0, x0 + width)}
            if not row.issubset(remaining):
                break
            depth += 1
        for x in range(x0, x0 + width):
            for z in range(z0, z0 + depth):
                remaining.remove((x, z))
        rectangles.append((x0, z0, x0 + width, z0 + depth))
    rectangles.sort(key=lambda rect: (rect[1], rect[0], rect[3], rect[2]))
    return rectangles


def axis_edges(centers: list[float], voxel_size: float) -> list[float]:
    start = centers[0] - voxel_size * 0.5
    return [round(start + index * voxel_size, 6) for index in range(len(centers) + 1)]


def walkable_cells_at_y(inside: set[tuple[int, int, int]], y_index: int, y_count: int, clearance_cells: int) -> set[tuple[int, int]]:
    if y_index + clearance_cells >= y_count:
        return set()
    cells: set[tuple[int, int]] = set()
    for xi, yi, zi in inside:
        if yi != y_index:
            continue
        clear = True
        for offset in range(1, clearance_cells + 1):
            if (xi, yi + offset, zi) not in inside:
                clear = False
                break
        if clear:
            cells.add((xi, zi))
    return cells


def rect_from_bounds(bounds: dict) -> dict:
    return {
        "x_min": float(bounds["min"][0]),
        "x_max": float(bounds["max"][0]),
        "z_min": float(bounds["min"][2]),
        "z_max": float(bounds["max"][2]),
    }


def clamp(value: float, low: float, high: float) -> float:
    if high < low:
        return value
    return max(low, min(high, value))


def remove_cutout_cells(cells: set[tuple[int, int]], x_centers: list[float], z_centers: list[float], cutouts: list[dict]) -> int:
    removed = 0
    for cell in list(cells):
        x = float(x_centers[cell[0]])
        z = float(z_centers[cell[1]])
        for cutout in cutouts:
            if float(cutout["x_min"]) <= x <= float(cutout["x_max"]) and float(cutout["z_min"]) <= z <= float(cutout["z_max"]):
                cells.remove(cell)
                removed += 1
                break
    return removed


def add_floor_tiles(
    objects: list[dict],
    deck: dict,
    occupancy: dict,
    inside: set[tuple[int, int, int]],
    config: dict,
    thickness: float,
    deck_cutouts: dict[str, list[dict]],
) -> dict:
    voxel_size = float(occupancy["voxel_size"])
    x_centers = occupancy["axis_centers"]["x"]
    z_centers = occupancy["axis_centers"]["z"]
    x_edges = axis_edges(occupancy["axis_centers"]["x"], voxel_size)
    z_edges = axis_edges(occupancy["axis_centers"]["z"], voxel_size)
    y_count = len(occupancy["axis_centers"]["y"])
    clearance = float(config["player_capsule_height"]) + float(config["player_clearance_margin"])
    clearance_cells = max(1, int(math.ceil(clearance / voxel_size)))
    deck_y = float(deck["center"][1])
    y_index = min(range(y_count), key=lambda index: (abs(float(occupancy["axis_centers"]["y"][index]) - deck_y), index))
    cells = walkable_cells_at_y(inside, y_index, y_count, clearance_cells)
    cutout_count = remove_cutout_cells(cells, x_centers, z_centers, deck_cutouts.get(deck["id"], []))
    components = connected_components(cells)
    if not components:
        return {"deck": deck["id"], "tile_count": 0, "source_cells": 0, "cutout_cells": cutout_count}
    largest = components[0]
    rectangles = greedy_rectangles(largest)
    y = deck_y
    for index, (x0, z0, x1, z1) in enumerate(rectangles, start=1):
        x_min, x_max = x_edges[x0], x_edges[x1]
        z_min, z_max = z_edges[z0], z_edges[z1]
        objects.append(
            {
                "name": f"COL_MX01_{deck['id']}_floor_tile_{index:03d}",
                "role": "player_walkable_floor",
                "kind": "box",
                "center": [round((x_min + x_max) * 0.5, 6), round(y - thickness * 0.5, 6), round((z_min + z_max) * 0.5, 6)],
                "size": [round(x_max - x_min, 6), thickness, round(z_max - z_min, 6)],
                "material": "MX01_PlayerFloor",
                "source": "occupancy_clipped_deck_component",
            }
        )
    return {
        "deck": deck["id"],
        "tile_count": len(rectangles),
        "source_cells": len(largest),
        "cutout_cells": cutout_count,
    }


def box_from_bounds(name: str, role: str, bounds: dict, y: float, thickness: float, material: str) -> dict:
    x_min, _y_min, z_min = bounds["min"]
    x_max, _y_max, z_max = bounds["max"]
    return {
        "name": name,
        "role": role,
        "kind": "box",
        "center": [round((x_min + x_max) * 0.5, 6), round(y - thickness * 0.5, 6), round((z_min + z_max) * 0.5, 6)],
        "size": [round(x_max - x_min, 6), thickness, round(z_max - z_min, 6)],
        "material": material,
        "source": "accepted_deck_bounds",
    }


def add_landing(objects: list[dict], name: str, y: float, x: float, z: float, width: float, depth: float) -> None:
    objects.append(
        {
            "name": name,
            "role": "player_connector_landing",
            "kind": "box",
            "center": [round(x, 6), round(y - 0.05, 6), round(z, 6)],
            "size": [round(width, 6), 0.1, round(depth, 6)],
            "material": "MX01_PlayerConnector",
            "source": "traversal_graph_connector",
        }
    )


def add_guard_rails(objects: list[dict], edge: dict, y_from: float, y_to: float, rail_span: float) -> None:
    center = edge["connector_center"]
    if not center:
        return
    x, _y, z = center
    y_center = (y_from + y_to) * 0.5
    height = abs(y_to - y_from)
    if height <= 0.0:
        return
    rail_t = 0.16
    rail_h = max(0.1, height)
    half = rail_span * 0.5
    specs = [
        ("port", [x - half, y_center, z], [rail_t, rail_h, rail_span]),
        ("starboard", [x + half, y_center, z], [rail_t, rail_h, rail_span]),
        ("aft", [x, y_center, z - half], [rail_span, rail_h, rail_t]),
        ("forward", [x, y_center, z + half], [rail_span, rail_h, rail_t]),
    ]
    for suffix, center_value, size in specs:
        objects.append(
            {
                "name": f"COL_MX01_{edge['id']}_{suffix}_guard_rail",
                "role": "player_connector_guard",
                "kind": "box",
                "center": [round(v, 6) for v in center_value],
                "size": [round(v, 6) for v in size],
                "material": "MX01_PlayerGuard",
                "source": "traversal_graph_connector",
            }
        )


def build_stair_spec(edge: dict, from_node: dict, to_node: dict, order_index: int) -> dict | None:
    overlap = edge.get("overlap") or {}
    center = edge.get("connector_center")
    if not overlap or not center:
        return None
    y_from = float(from_node["center"][1])
    y_to = float(to_node["center"][1])
    vertical_delta = y_to - y_from
    if vertical_delta <= 0.0:
        return None
    from_rect = rect_from_bounds(from_node["bounds"])
    to_rect = rect_from_bounds(to_node["bounds"])
    compact_cockpit_stair = "forward_cockpit" in from_node["id"] or "forward_cockpit" in to_node["id"]
    compact_aft_stair = edge["id"] == "lower_deck_candidate_to_mid_deck_candidate" or float(overlap["center"][1]) < -20.0
    tread_count = max(5, int(math.ceil(vertical_delta / 0.7)))
    tread_run = 0.42
    total_run = tread_count * tread_run
    if compact_aft_stair:
        stair_width = max(1.15, min(1.55, float(overlap["width"]) - 0.9))
        landing_depth = 0.75
    elif compact_cockpit_stair:
        stair_width = max(1.05, min(1.35, float(overlap["width"]) - 0.8))
        landing_depth = 0.9
    else:
        stair_width = max(1.3, min(2.2, float(overlap["width"]) - 0.8))
        landing_depth = 1.1
    x_low = max(from_rect["x_min"], to_rect["x_min"], float(overlap["x_min"])) + stair_width * 0.5 + 0.25
    x_high = min(from_rect["x_max"], to_rect["x_max"], float(overlap["x_max"])) - stair_width * 0.5 - 0.25
    if compact_aft_stair:
        x = clamp(float(center[0]), x_low, x_high)
    elif compact_cockpit_stair:
        x = x_low if order_index % 2 else x_high
    else:
        x = clamp(float(center[0]) + ((order_index % 3) - 1) * 0.25, x_low, x_high)

    candidates = []
    directions = (1.0,) if compact_aft_stair else (1.0, -1.0)
    for direction in directions:
        if direction > 0.0:
            if compact_aft_stair:
                low = float(overlap["z_min"]) + landing_depth * 0.5 + 0.15
                high = float(overlap["z_max"]) - landing_depth * 0.5 - 0.15 - total_run
            else:
                low = max(from_rect["z_min"] + landing_depth, float(overlap["z_min"]) + 0.35, to_rect["z_min"] - total_run + landing_depth)
                high = min(from_rect["z_max"] - landing_depth, float(overlap["z_max"]) - 0.35, to_rect["z_max"] - total_run - landing_depth)
        else:
            low = max(from_rect["z_min"] + landing_depth, float(overlap["z_min"]) + 0.35, to_rect["z_min"] + total_run + landing_depth)
            high = min(from_rect["z_max"] - landing_depth, float(overlap["z_max"]) - 0.35, to_rect["z_max"] + total_run - landing_depth)
        if low <= high:
            z_start = low if compact_aft_stair else clamp(float(center[2]), low, high)
            z_end = z_start + direction * total_run
            candidates.append((abs(z_start - float(center[2])), direction, z_start, z_end))
    if candidates:
        _score, direction, z_start, z_end = min(candidates, key=lambda item: (item[0], item[1]))
    else:
        direction = 1.0 if float(center[2]) < (from_rect["z_min"] + from_rect["z_max"]) * 0.5 else -1.0
        z_start = float(center[2]) - direction * total_run * 0.5
        z_end = z_start + direction * total_run

    cutout_padding_x = 0.15 if compact_cockpit_stair or compact_aft_stair else 0.3
    cutout_padding_z = 0.2 if compact_aft_stair else (0.25 if compact_cockpit_stair else 0.4)
    placement = "aft_compact_steep_overlap" if compact_aft_stair else ("cockpit_side_switchback" if compact_cockpit_stair else "lengthwise_centerline")
    cutout_z_min = min(z_start, z_end) - landing_depth - cutout_padding_z
    cutout_z_max = max(z_start, z_end) + landing_depth + cutout_padding_z
    if compact_aft_stair:
        cutout_z_min = max(float(overlap["z_min"]) + 0.05, min(z_start, z_end) - cutout_padding_z)
        cutout_z_max = min(float(overlap["z_max"]) - 0.05, max(z_start, z_end) + landing_depth + cutout_padding_z)
    return {
        "edge_id": edge["id"],
        "from_deck": from_node["id"],
        "to_deck": to_node["id"],
        "x": round(x, 6),
        "z_start": round(z_start, 6),
        "z_end": round(z_end, 6),
        "direction": int(direction),
        "y_from": round(y_from, 6),
        "y_to": round(y_to, 6),
        "vertical_delta": round(vertical_delta, 6),
        "tread_count": tread_count,
        "tread_run": round(tread_run, 6),
        "stair_width": round(stair_width, 6),
        "landing_depth": landing_depth,
        "placement": placement,
        "cutout": {
            "x_min": round(x - stair_width * 0.5 - cutout_padding_x, 6),
            "x_max": round(x + stair_width * 0.5 + cutout_padding_x, 6),
            "z_min": round(cutout_z_min, 6),
            "z_max": round(cutout_z_max, 6),
        },
    }


def make_manual_stair_spec(
    edge_id: str,
    from_node: dict,
    to_node: dict,
    x: float,
    z_start: float,
    direction: float,
    stair_width: float,
    landing_depth: float,
    placement: str,
    cutout_padding_x: float = 0.15,
    cutout_padding_z: float = 0.2,
    cutout_z_bounds: tuple[float, float] | None = None,
) -> dict:
    y_from = float(from_node["center"][1])
    y_to = float(to_node["center"][1])
    vertical_delta = y_to - y_from
    tread_count = max(5, int(math.ceil(vertical_delta / 0.7)))
    tread_run = 0.42
    z_end = z_start + direction * tread_count * tread_run
    cutout_z_min = min(z_start, z_end) - cutout_padding_z
    cutout_z_max = max(z_start, z_end) + landing_depth + cutout_padding_z
    if cutout_z_bounds is not None:
        cutout_z_min = max(cutout_z_bounds[0], cutout_z_min)
        cutout_z_max = min(cutout_z_bounds[1], cutout_z_max)
    return {
        "edge_id": edge_id,
        "from_deck": from_node["id"],
        "to_deck": to_node["id"],
        "x": round(x, 6),
        "z_start": round(z_start, 6),
        "z_end": round(z_end, 6),
        "direction": int(direction),
        "y_from": round(y_from, 6),
        "y_to": round(y_to, 6),
        "vertical_delta": round(vertical_delta, 6),
        "tread_count": tread_count,
        "tread_run": round(tread_run, 6),
        "stair_width": round(stair_width, 6),
        "landing_depth": landing_depth,
        "placement": placement,
        "cutout": {
            "x_min": round(x - stair_width * 0.5 - cutout_padding_x, 6),
            "x_max": round(x + stair_width * 0.5 + cutout_padding_x, 6),
            "z_min": round(cutout_z_min, 6),
            "z_max": round(cutout_z_max, 6),
        },
    }


def supplemental_stair_specs(graph: dict, nodes_by_id: dict[str, dict]) -> list[dict]:
    edges_by_id = {edge["id"]: edge for edge in graph["edges"]}
    specs: list[dict] = []

    mid_upper = edges_by_id.get("mid_deck_candidate_to_upper_deck_candidate")
    if mid_upper and not mid_upper["status"].startswith("FAIL"):
        from_node = nodes_by_id[mid_upper["from"]]
        to_node = nodes_by_id[mid_upper["to"]]
        overlap = mid_upper["overlap"]
        side_width = 1.55
        side_landing_depth = 0.75
        side_z_start = float(mid_upper["connector_center"][2])
        side_total_run = max(5, int(math.ceil(float(mid_upper["vertical_delta"]) / 0.7))) * 0.42
        x_left = float(overlap["x_min"]) + side_width * 0.5 + 0.3
        x_right = float(overlap["x_max"]) - side_width * 0.5 - 0.3
        cutout_bounds = (float(overlap["z_min"]) + 0.05, float(overlap["z_max"]) - 0.05)
        specs.extend(
            [
                make_manual_stair_spec(
                    "mid_deck_candidate_to_upper_deck_candidate_negative_x_side",
                    from_node,
                    to_node,
                    x_left,
                    side_z_start,
                    -1.0,
                    side_width,
                    side_landing_depth,
                    "main_deck_negative_x_side_replacement",
                    cutout_z_bounds=cutout_bounds,
                ),
                make_manual_stair_spec(
                    "mid_deck_candidate_to_upper_deck_candidate_positive_x_side",
                    from_node,
                    to_node,
                    x_right,
                    side_z_start - side_total_run,
                    1.0,
                    side_width,
                    side_landing_depth,
                    "main_deck_positive_x_side_replacement",
                    cutout_z_bounds=cutout_bounds,
                ),
            ]
        )

        cockpit_width = 1.35
        cockpit_landing_depth = 0.9
        cockpit_x = float(overlap["x_min"]) + cockpit_width * 0.5 + 0.75
        cockpit_total_run = max(5, int(math.ceil(float(mid_upper["vertical_delta"]) / 0.7))) * 0.42
        cockpit_z_start = float(overlap["z_max"]) - 0.25 + cockpit_total_run
        specs.append(
            make_manual_stair_spec(
                "mid_deck_candidate_to_upper_deck_candidate_cockpit_forward",
                from_node,
                to_node,
                cockpit_x,
                cockpit_z_start,
                -1.0,
                cockpit_width,
                cockpit_landing_depth,
                "cockpit_to_upper_forward_side",
                cutout_z_bounds=cutout_bounds,
            )
        )

        aft_width = 1.55
        aft_landing_depth = 0.75
        aft_z_start = max(float(overlap["z_min"]) + aft_landing_depth * 0.5 + 0.15, -34.225)
        aft_total_run = max(5, int(math.ceil(float(mid_upper["vertical_delta"]) / 0.7))) * 0.42
        aft_x = -(aft_width + 0.3)
        specs.append(
            make_manual_stair_spec(
                "mid_deck_candidate_to_upper_deck_candidate_rear_above_s3",
                from_node,
                to_node,
                aft_x,
                aft_z_start + aft_total_run,
                -1.0,
                aft_width,
                aft_landing_depth,
                "rear_above_s3_to_upper",
                cutout_z_bounds=cutout_bounds,
            )
        )

    return specs


def add_cockpit_floor_extension(objects: list[dict], nodes_by_id: dict[str, dict], thickness: float) -> list[dict]:
    mid = nodes_by_id.get("mid_deck_candidate")
    if not mid:
        return []
    bounds = rect_from_bounds(mid["bounds"])
    y = float(mid["center"][1])
    width = min(4.2, max(1.5, bounds["x_max"] - bounds["x_min"] - 1.2))
    z_min = bounds["z_max"] - 0.1
    z_max = bounds["z_max"] + 1.5
    obj = {
        "name": "COL_MX01_mid_deck_candidate_cockpit_forward_floor_extension",
        "role": "player_walkable_floor",
        "kind": "box",
        "center": [0.0, round(y - thickness * 0.5, 6), round((z_min + z_max) * 0.5, 6)],
        "size": [round(width, 6), thickness, round(z_max - z_min, 6)],
        "material": "MX01_PlayerFloor",
        "source": "cockpit_forward_extension",
    }
    objects.append(obj)
    return [{"deck": mid["id"], "object": obj["name"], "area_m2": round(width * (z_max - z_min), 4)}]


def add_stair_treads(objects: list[dict], spec: dict) -> None:
    y_from = float(spec["y_from"])
    vertical_delta = float(spec["vertical_delta"])
    tread_count = int(spec["tread_count"])
    tread_run = float(spec["tread_run"])
    direction = float(spec["direction"])
    x = float(spec["x"])
    z_start = float(spec["z_start"])
    for index in range(tread_count):
        t = (index + 1) / tread_count
        y = y_from + vertical_delta * t
        z = z_start + direction * tread_run * (index + 0.5)
        objects.append(
            {
                "name": f"COL_MX01_{spec['edge_id']}_stair_tread_{index + 1:02d}",
                "role": "player_connector_stair_tread",
                "kind": "box",
                "center": [round(x, 6), round(y - 0.07, 6), round(z, 6)],
                "size": [round(float(spec["stair_width"]), 6), 0.14, round(tread_run + 0.08, 6)],
                "material": "MX01_PlayerStair",
                "source": "traversal_graph_connector",
            }
        )


def generate(config: dict, graph: dict, occupancy: dict) -> tuple[dict, dict]:
    nodes_by_id = {node["id"]: node for node in graph["nodes"]}
    objects: list[dict] = []
    floor_thickness = 0.12
    inside = build_inside_set(occupancy)
    stair_specs = []
    deck_cutouts: dict[str, list[dict]] = {}
    for order_index, edge in enumerate(graph["edges"]):
        if edge["status"].startswith("FAIL") or edge["kind"] != "lift_or_stairwell_candidate":
            continue
        if edge["id"] == "mid_deck_candidate_to_upper_deck_candidate":
            continue
        from_node = nodes_by_id[edge["from"]]
        to_node = nodes_by_id[edge["to"]]
        spec = build_stair_spec(edge, from_node, to_node, order_index)
        if spec is None:
            continue
        stair_specs.append(spec)
    stair_specs.extend(supplemental_stair_specs(graph, nodes_by_id))
    stair_specs.sort(key=lambda spec: (spec["from_deck"], spec["to_deck"], spec["edge_id"]))
    for spec in stair_specs:
        deck_cutouts.setdefault(spec["to_deck"], []).append(spec["cutout"])

    floor_tile_summaries = []
    for node in graph["nodes"]:
        if node["kind"] != "deck":
            continue
        floor_tile_summaries.append(add_floor_tiles(objects, node, occupancy, inside, config, floor_thickness, deck_cutouts))
    floor_extensions = add_cockpit_floor_extension(objects, nodes_by_id, floor_thickness)

    for edge in graph["edges"]:
        if edge["status"].startswith("FAIL"):
            continue
        if edge["kind"] == "entry_handoff_candidate":
            center = edge["connector_center"]
            add_landing(objects, "COL_MX01_entry_ramp_threshold_pad", center[1], center[0], center[2], 3.0, 3.0)

    for spec in stair_specs:
        from_node = nodes_by_id[spec["from_deck"]]
        to_node = nodes_by_id[spec["to_deck"]]
        direction = float(spec["direction"])
        width = float(spec["stair_width"]) + 0.45
        depth = float(spec["landing_depth"])
        add_landing(objects, f"COL_MX01_{spec['edge_id']}_lower_landing", from_node["center"][1], float(spec["x"]), float(spec["z_start"]) - direction * depth * 0.5, width, depth)
        add_landing(objects, f"COL_MX01_{spec['edge_id']}_upper_landing", to_node["center"][1], float(spec["x"]), float(spec["z_end"]) + direction * depth * 0.5, width, depth)
        add_stair_treads(objects, spec)

    payload = {
        "ship_id": config["ship_id"],
        "method": "deck_floor_and_vertical_connector_collision_v1",
        "objects": objects,
        "floor_tile_summaries": floor_tile_summaries,
        "floor_extensions": floor_extensions,
        "stair_specs": stair_specs,
        "deck_cutouts": deck_cutouts,
    }
    report = {
        "ship_id": config["ship_id"],
        "method": payload["method"],
        "status": "PASS",
        "counts": {
            "collision_objects": len(objects),
            "walkable_floor_objects": sum(1 for obj in objects if obj["role"] == "player_walkable_floor"),
            "floor_source_cells": sum(summary["source_cells"] for summary in floor_tile_summaries),
            "connector_landing_objects": sum(1 for obj in objects if obj["role"] == "player_connector_landing"),
            "stair_tread_objects": sum(1 for obj in objects if obj["role"] == "player_connector_stair_tread"),
            "guard_objects": sum(1 for obj in objects if obj["role"] == "player_connector_guard"),
            "stairwells": len(stair_specs),
            "floor_extensions": len(floor_extensions),
            "floor_cutout_cells": sum(summary["cutout_cells"] for summary in floor_tile_summaries),
        },
        "notes": "Interior collision contains occupancy-clipped floors, a cockpit forward floor extension, steeper lengthwise stair treads, compact edge-biased cockpit stairs, supplemental main-body stair pairs, landings, and upper-deck stairwell cutouts. It does not yet include final wall blockers, doorways, railings, or capsule sweep validation.",
    }
    return payload, report


def write_markdown(path: Path, report: dict) -> None:
    lines = [
        "# MX01 Interior Collision Report",
        "",
        f"- Method: `{report['method']}`",
        f"- Status: `{report['status']}`",
        f"- Collision objects: `{report['counts']['collision_objects']}`",
        f"- Walkable floor tiles: `{report['counts']['walkable_floor_objects']}`",
        f"- Floor source cells: `{report['counts']['floor_source_cells']}`",
        f"- Floor cutout cells: `{report['counts']['floor_cutout_cells']}`",
        f"- Floor extensions: `{report['counts']['floor_extensions']}`",
        f"- Connector landings: `{report['counts']['connector_landing_objects']}`",
        f"- Stair treads: `{report['counts']['stair_tread_objects']}`",
        f"- Stairwells: `{report['counts']['stairwells']}`",
        f"- Guards: `{report['counts']['guard_objects']}`",
        "",
        "## Notes",
        "",
        report["notes"],
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    config_path = args.config.resolve()
    config = load_json(config_path)
    graph_path = resolve_config_path(config, "traversal_outputs", "graph_json")
    occupancy_path = resolve_config_path(config, "occupancy_outputs", "intervals_json")
    graph = load_json(graph_path)
    occupancy = load_json(occupancy_path)
    payload, report = generate(config, graph, occupancy)

    collision_json = resolve_config_path(config, "interior_collision_outputs", "collision_json")
    collision_obj = resolve_config_path(config, "interior_collision_outputs", "collision_obj")
    report_json = resolve_config_path(config, "interior_collision_outputs", "report_json")
    report_md = resolve_config_path(config, "interior_collision_outputs", "report_md")
    manifest_json = resolve_config_path(config, "interior_collision_outputs", "manifest_json")

    write_json(collision_json, payload)
    obj_counts = write_box_obj(collision_obj, payload["objects"], "MX01 interior collision")
    report["obj_counts"] = obj_counts
    report["source"] = {
        "traversal_graph": rel(graph_path),
        "traversal_graph_sha256": sha256(graph_path),
        "occupancy_intervals": rel(occupancy_path),
        "occupancy_intervals_sha256": sha256(occupancy_path),
    }
    report["config"] = {"path": rel(config_path), "sha256": sha256(config_path), "effective_values": config}
    report["tools"] = {
        "generate_mx01_interior_collision.py": {"path": rel(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())},
        "mesh_writer.py": {"path": rel((Path(__file__).resolve().parent / "mesh_writer.py")), "sha256": sha256(Path(__file__).resolve().parent / "mesh_writer.py")},
    }
    report["outputs"] = {"collision_json": rel(collision_json), "collision_obj": rel(collision_obj)}
    write_json(report_json, report)
    write_markdown(report_md, report)
    write_json(
        manifest_json,
        {
            "ship_id": config["ship_id"],
            "stage": "interior_collision_generation",
            "source": report["source"],
            "config": report["config"],
            "outputs": {
                "collision_json": rel(collision_json),
                "collision_json_sha256": sha256(collision_json),
                "collision_obj": rel(collision_obj),
                "collision_obj_sha256": sha256(collision_obj),
                "report_json": rel(report_json),
                "report_md": rel(report_md),
            },
            "tools": report["tools"],
        },
    )
    print(f"Wrote {rel(collision_json)}")
    print(f"Wrote {rel(collision_obj)}")
    print(f"Wrote {rel(report_json)}")
    print(f"Wrote {rel(report_md)}")
    print(f"Wrote {rel(manifest_json)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
