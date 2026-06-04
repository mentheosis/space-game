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


def add_floor_tiles(objects: list[dict], deck: dict, occupancy: dict, inside: set[tuple[int, int, int]], config: dict, thickness: float) -> dict:
    voxel_size = float(occupancy["voxel_size"])
    x_edges = axis_edges(occupancy["axis_centers"]["x"], voxel_size)
    z_edges = axis_edges(occupancy["axis_centers"]["z"], voxel_size)
    y_count = len(occupancy["axis_centers"]["y"])
    clearance = float(config["player_capsule_height"]) + float(config["player_clearance_margin"])
    clearance_cells = max(1, int(math.ceil(clearance / voxel_size)))
    deck_y = float(deck["center"][1])
    y_index = min(range(y_count), key=lambda index: (abs(float(occupancy["axis_centers"]["y"][index]) - deck_y), index))
    cells = walkable_cells_at_y(inside, y_index, y_count, clearance_cells)
    components = connected_components(cells)
    if not components:
        return {"deck": deck["id"], "tile_count": 0, "source_cells": 0}
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
    return {"deck": deck["id"], "tile_count": len(rectangles), "source_cells": len(largest)}


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


def add_landing(objects: list[dict], name: str, y: float, x: float, z: float, size: float) -> None:
    objects.append(
        {
            "name": name,
            "role": "player_connector_landing",
            "kind": "box",
            "center": [round(x, 6), round(y - 0.05, 6), round(z, 6)],
            "size": [round(size, 6), 0.1, round(size, 6)],
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


def add_stair_treads(objects: list[dict], edge: dict, y_from: float, y_to: float) -> None:
    overlap = edge.get("overlap") or {}
    center = edge.get("connector_center")
    if not overlap or not center:
        return
    vertical_delta = y_to - y_from
    if vertical_delta <= 0.0:
        return
    # Use many low-rise treads across the connector width. The earlier short
    # Z-run stairs were too steep and started near the inspection spawn.
    tread_count = max(8, int((vertical_delta / 0.175) + 0.999))
    available_width = max(1.0, float(overlap["width"]) - 0.6)
    tread_run = max(0.32, min(0.6, available_width / tread_count))
    tread_depth = max(1.4, min(2.6, float(overlap["depth"]) - 0.8))
    total_run = tread_run * tread_count
    x_start = max(float(overlap["x_min"]) + 0.3, float(center[0]) - total_run * 0.5)
    if x_start + total_run > float(overlap["x_max"]) - 0.3:
        x_start = float(overlap["x_max"]) - 0.3 - total_run
    z = float(center[2])
    for index in range(tread_count):
        t = (index + 1) / tread_count
        y = y_from + vertical_delta * t
        x = x_start + tread_run * (index + 0.5)
        objects.append(
            {
                "name": f"COL_MX01_{edge['id']}_stair_tread_{index + 1:02d}",
                "role": "player_connector_stair_tread",
                "kind": "box",
                "center": [round(x, 6), round(y - 0.06, 6), round(z, 6)],
                "size": [round(tread_run, 6), 0.12, round(tread_depth, 6)],
                "material": "MX01_PlayerStair",
                "source": "traversal_graph_connector",
            }
        )


def generate(config: dict, graph: dict, occupancy: dict) -> tuple[dict, dict]:
    nodes_by_id = {node["id"]: node for node in graph["nodes"]}
    objects: list[dict] = []
    floor_thickness = 0.12
    inside = build_inside_set(occupancy)
    floor_tile_summaries = []
    for node in graph["nodes"]:
        if node["kind"] != "deck":
            continue
        floor_tile_summaries.append(add_floor_tiles(objects, node, occupancy, inside, config, floor_thickness))

    for edge in graph["edges"]:
        if edge["status"].startswith("FAIL"):
            continue
        if edge["kind"] == "entry_handoff_candidate":
            center = edge["connector_center"]
            add_landing(objects, "COL_MX01_entry_ramp_threshold_pad", center[1], center[0], center[2], 3.0)
            continue
        if edge["kind"] == "lift_or_stairwell_candidate":
            from_node = nodes_by_id[edge["from"]]
            to_node = nodes_by_id[edge["to"]]
            center = edge["connector_center"]
            overlap = edge["overlap"] or {}
            landing_size = min(3.0, max(1.5, overlap.get("width", 2.0)), max(1.5, overlap.get("depth", 2.0)))
            add_landing(objects, f"COL_MX01_{edge['id']}_lower_landing", from_node["center"][1], center[0], center[2], landing_size)
            add_landing(objects, f"COL_MX01_{edge['id']}_upper_landing", to_node["center"][1], center[0], center[2], landing_size)
            add_stair_treads(objects, edge, from_node["center"][1], to_node["center"][1])

    payload = {
        "ship_id": config["ship_id"],
        "method": "deck_floor_and_vertical_connector_collision_v1",
        "objects": objects,
        "floor_tile_summaries": floor_tile_summaries,
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
        },
        "notes": "First-pass interior collision contains floors, connector landings, and low-rise stair treads. It does not yet include final wall blockers, doorways, railings, or capsule sweep validation.",
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
        f"- Connector landings: `{report['counts']['connector_landing_objects']}`",
        f"- Stair treads: `{report['counts']['stair_tread_objects']}`",
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
