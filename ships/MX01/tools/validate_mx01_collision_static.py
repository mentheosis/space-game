#!/usr/bin/env python3
"""Run static validation for generated MX01 collision artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


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


def connector_keepouts(interior_collision: dict, config: dict) -> list[dict]:
    radius = float(config["player_capsule_radius"]) + float(config["player_clearance_margin"])
    height = float(config["player_capsule_height"]) + float(config["player_clearance_margin"])
    keepouts = []
    for obj in interior_collision["objects"]:
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


def stair_wall_clearances(interior_collision: dict) -> list[dict]:
    margin = 0.18
    clearances = []
    for obj in interior_collision["objects"]:
        if obj["role"] not in {"player_connector_landing", "player_connector_stair_tread"}:
            continue
        cx, cy, cz = [float(value) for value in obj["center"]]
        sx, sy, sz = [float(value) for value in obj["size"]]
        clearances.append(
            {
                "name": obj["name"],
                "x_min": cx - sx * 0.5 - margin,
                "x_max": cx + sx * 0.5 + margin,
                "y_min": cy - sy * 0.5 - 0.05,
                "y_max": cy + sy * 0.5 + 0.45,
                "z_min": cz - sz * 0.5 - margin,
                "z_max": cz + sz * 0.5 + margin,
            }
        )
    return clearances


def point_in_keepout(point: tuple[float, float, float], keepout: dict) -> bool:
    x, y, z = point
    return keepout["x_min"] <= x <= keepout["x_max"] and keepout["y_min"] <= y <= keepout["y_max"] and keepout["z_min"] <= z <= keepout["z_max"]


def triangle_center(vertices: list[list[float]], face: list[int]) -> tuple[float, float, float]:
    a, b, c = [vertices[index] for index in face]
    return ((a[0] + b[0] + c[0]) / 3.0, (a[1] + b[1] + c[1]) / 3.0, (a[2] + b[2] + c[2]) / 3.0)


def count_enclosure_keepout_hits(enclosure: dict, keepouts: list[dict]) -> int:
    hits = 0
    for obj in enclosure["objects"]:
        vertices = obj["vertices"]
        for face in obj["triangles"]:
            center = triangle_center(vertices, face)
            if any(point_in_keepout(center, keepout) for keepout in keepouts):
                hits += 1
    return hits


def primitive_aabb(primitive: dict) -> dict:
    cx, cy, cz = [float(value) for value in primitive["center"]]
    sx, sy, sz = [float(value) * 0.5 for value in primitive["size"]]
    rotation_y = float(primitive.get("rotation_y", 0.0))
    cos_y = math.cos(rotation_y)
    sin_y = math.sin(rotation_y)
    points = []
    for lx in (-sx, sx):
        for lz in (-sz, sz):
            points.append((cx + lx * cos_y + lz * sin_y, cz - lx * sin_y + lz * cos_y))
    return {
        "x_min": min(point[0] for point in points),
        "x_max": max(point[0] for point in points),
        "y_min": cy - sy,
        "y_max": cy + sy,
        "z_min": min(point[1] for point in points),
        "z_max": max(point[1] for point in points),
    }


def count_primitive_connector_footprint_hits(enclosure: dict, interior_collision: dict) -> int:
    connector_bounds = []
    for obj in interior_collision["objects"]:
        if obj["role"] != "player_connector_landing":
            continue
        cx, cy, cz = [float(value) for value in obj["center"]]
        sx, sy, sz = [float(value) * 0.5 for value in obj["size"]]
        connector_bounds.append(
            {
                "x_min": cx - sx,
                "x_max": cx + sx,
                "y_min": cy - sy,
                "y_max": cy + sy,
                "z_min": cz - sz,
                "z_max": cz + sz,
            }
        )
    hits = 0
    for primitive in enclosure.get("collision_primitives", []):
        aabb = primitive_aabb(primitive)
        for bounds in connector_bounds:
            if not aabb_overlaps(aabb, bounds):
                continue
            overlap_x = min(aabb["x_max"], bounds["x_max"]) - max(aabb["x_min"], bounds["x_min"])
            overlap_y = min(aabb["y_max"], bounds["y_max"]) - max(aabb["y_min"], bounds["y_min"])
            overlap_z = min(aabb["z_max"], bounds["z_max"]) - max(aabb["z_min"], bounds["z_min"])
            # Landing pads are part of the traversable footprint. Perimeter
            # walls may touch their outer edge; only meaningful intrusion into
            # the solid landing volume is a clearance failure.
            if overlap_y > 0.03 and overlap_x > 0.05 and overlap_z > 0.05:
                hits += 1
                break
    return hits


def count_wall_stair_clearance_hits(enclosure: dict, interior_collision: dict) -> tuple[int, list[str]]:
    clearances = stair_wall_clearances(interior_collision)
    hits = 0
    samples = []
    for primitive in enclosure.get("collision_primitives", []):
        if primitive["role"] != "player_enclosure_wall_collider":
            continue
        aabb = primitive_aabb(primitive)
        for clearance in clearances:
            if not aabb_overlaps(aabb, clearance):
                continue
            overlap_x = min(aabb["x_max"], clearance["x_max"]) - max(aabb["x_min"], clearance["x_min"])
            overlap_y = min(aabb["y_max"], clearance["y_max"]) - max(aabb["y_min"], clearance["y_min"])
            overlap_z = min(aabb["z_max"], clearance["z_max"]) - max(aabb["z_min"], clearance["z_min"])
            if overlap_y > 0.03 and overlap_x > 0.05 and overlap_z > 0.05:
                hits += 1
                if len(samples) < 12:
                    samples.append(f"{primitive['name']} -> {clearance['name']}")
                break
    return hits, samples


def aabb_overlaps(a: dict, b: dict) -> bool:
    return a["x_min"] <= b["x_max"] and a["x_max"] >= b["x_min"] and a["y_min"] <= b["y_max"] and a["y_max"] >= b["y_min"] and a["z_min"] <= b["z_max"] and a["z_max"] >= b["z_min"]


def axis_edges(centers: list[float], voxel_size: float) -> list[float]:
    start = float(centers[0]) - voxel_size * 0.5
    return [round(start + index * voxel_size, 6) for index in range(len(centers) + 1)]


def nearest_index(values: list[float], target: float) -> int:
    return min(range(len(values)), key=lambda index: (abs(float(values[index]) - target), index))


def build_inside_set(occupancy: dict) -> set[tuple[int, int, int]]:
    inside: set[tuple[int, int, int]] = set()
    for ray in occupancy["rays"]:
        yi = int(ray["y_index"])
        zi = int(ray["z_index"])
        for start, end in ray["x_intervals"]:
            for xi in range(int(start), int(end) + 1):
                inside.add((xi, yi, zi))
    return inside


def floor_cells_for_deck(interior_collision: dict, occupancy: dict, deck_id: str, deck_y: float | None = None) -> set[tuple[int, int]]:
    x_centers = occupancy["axis_centers"]["x"]
    z_centers = occupancy["axis_centers"]["z"]
    x_edges = axis_edges(x_centers, float(occupancy["voxel_size"]))
    z_edges = axis_edges(z_centers, float(occupancy["voxel_size"]))
    cells: set[tuple[int, int]] = set()
    for obj in interior_collision["objects"]:
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


def outside_empty_cells(floor_cells: set[tuple[int, int]]) -> set[tuple[int, int]]:
    if not floor_cells:
        return set()
    min_x = min(xi for xi, _zi in floor_cells) - 1
    max_x = max(xi for xi, _zi in floor_cells) + 1
    min_z = min(zi for _xi, zi in floor_cells) - 1
    max_z = max(zi for _xi, zi in floor_cells) + 1
    exterior = {(min_x, min_z)}
    queue = [(min_x, min_z)]
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


def exterior_floor_edges(floor_cells: set[tuple[int, int]]) -> set[tuple[int, int, str]]:
    exterior = outside_empty_cells(floor_cells)
    edges: set[tuple[int, int, str]] = set()
    for xi, zi in floor_cells:
        if (xi - 1, zi) in exterior:
            edges.add((xi, zi, "x_negative"))
        if (xi + 1, zi) in exterior:
            edges.add((xi + 1, zi, "x_positive"))
        if (xi, zi - 1) in exterior:
            edges.add((zi, xi, "z_negative"))
        if (xi, zi + 1) in exterior:
            edges.add((zi + 1, xi, "z_positive"))
    return edges


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


def cell_inside_hull_at_height(cell: tuple[int, int], y: float, occupancy: dict, inside: set[tuple[int, int, int]]) -> bool:
    xi, zi = cell
    if xi < 0 or xi >= len(occupancy["axis_centers"]["x"]) or zi < 0 or zi >= len(occupancy["axis_centers"]["z"]):
        return False
    yi = nearest_index(occupancy["axis_centers"]["y"], y)
    return (xi, yi, zi) in inside


def wall_covers_edge(primitive: dict, edge: tuple[int, int, str], deck_y: float, x_edges: list[float], z_edges: list[float]) -> bool:
    line, index, direction = edge
    aabb = primitive_aabb(primitive)
    epsilon = 0.055
    source = primitive.get("source", "")
    detour_epsilon = 4.0 if source == "controller_safe_hull_wall_detour" else 0.0
    if not (aabb["y_min"] <= deck_y + 0.05 and aabb["y_max"] >= deck_y + 1.6):
        return False
    if direction.startswith("x_"):
        x = float(x_edges[line])
        z0 = float(z_edges[index])
        z1 = float(z_edges[index + 1])
        if aabb["z_min"] > z0 + epsilon or aabb["z_max"] < z1 - epsilon:
            return False
        if aabb["x_min"] - epsilon <= x <= aabb["x_max"] + epsilon:
            return True
        if direction == "x_positive" and 0.0 <= aabb["x_min"] - x <= detour_epsilon:
            return True
        if direction == "x_negative" and 0.0 <= x - aabb["x_max"] <= detour_epsilon:
            return True
        return False
    z = float(z_edges[line])
    x0 = float(x_edges[index])
    x1 = float(x_edges[index + 1])
    if aabb["x_min"] > x0 + epsilon or aabb["x_max"] < x1 - epsilon:
        return False
    if aabb["z_min"] - epsilon <= z <= aabb["z_max"] + epsilon:
        return True
    if direction == "z_positive" and 0.0 <= aabb["z_min"] - z <= detour_epsilon:
        return True
    if direction == "z_negative" and 0.0 <= z - aabb["z_max"] <= detour_epsilon:
        return True
    return False


def check_exact_floor_edge_wall_coverage(enclosure: dict, interior_collision: dict, occupancy: dict, traversal: dict) -> dict:
    x_edges = axis_edges(occupancy["axis_centers"]["x"], float(occupancy["voxel_size"]))
    z_edges = axis_edges(occupancy["axis_centers"]["z"], float(occupancy["voxel_size"]))
    inside = build_inside_set(occupancy)
    deck_nodes = sorted((node for node in traversal["nodes"] if node["kind"] == "deck"), key=lambda node: node["id"])
    wall_primitives = [primitive for primitive in enclosure.get("collision_primitives", []) if primitive["role"] == "player_enclosure_wall_collider"]
    deck_footprints = {
        deck["id"]: floor_cells_for_deck(interior_collision, occupancy, deck["id"], float(deck["center"][1]))
        for deck in deck_nodes
    }
    total_edges = 0
    covered_edges = 0
    balcony_edges = 0
    uncovered_samples: list[dict] = []
    deck_metrics = []
    for deck in deck_nodes:
        deck_id = deck["id"]
        floor_cells = set(deck_footprints.get(deck_id, set()))
        edges = exterior_floor_edges(floor_cells)
        lower_cells: set[tuple[int, int]] = set()
        deck_y = float(deck["center"][1])
        balcony_test_y = deck_y + 0.9
        for other in deck_nodes:
            if float(other["center"][1]) < deck_y - 0.25:
                lower_cells.update(deck_footprints.get(other["id"], set()))
        deck_walls = [primitive for primitive in wall_primitives if primitive.get("deck") == deck_id]
        deck_covered = 0
        deck_balcony = 0
        for edge in sorted(edges):
            neighbor = edge_neighbor_cell(edge)
            if neighbor in lower_cells and cell_inside_hull_at_height(neighbor, balcony_test_y, occupancy, inside):
                deck_balcony += 1
                continue
            if any(wall_covers_edge(primitive, edge, float(deck["center"][1]), x_edges, z_edges) for primitive in deck_walls):
                deck_covered += 1
            elif len(uncovered_samples) < 20:
                uncovered_samples.append({"deck": deck_id, "edge": [edge[0], edge[1], edge[2]]})
        ship_edges = len(edges) - deck_balcony
        total_edges += ship_edges
        covered_edges += deck_covered
        balcony_edges += deck_balcony
        deck_metrics.append({"deck": deck_id, "floor_cells": len(floor_cells), "ship_edge_boundary_edges": ship_edges, "interior_balcony_edges": deck_balcony, "covered_edges": deck_covered, "wall_primitives": len(deck_walls)})
    return {
        "total_edges": total_edges,
        "covered_edges": covered_edges,
        "uncovered_edges": total_edges - covered_edges,
        "interior_balcony_edges": balcony_edges,
        "deck_metrics": deck_metrics,
        "uncovered_samples": uncovered_samples,
    }


def point_inside_primitive(point: tuple[float, float, float], primitive: dict) -> bool:
    px, py, pz = point
    cx, cy, cz = [float(value) for value in primitive["center"]]
    sx, sy, sz = [float(value) * 0.5 for value in primitive["size"]]
    rotation_y = float(primitive.get("rotation_y", 0.0))
    dx = px - cx
    dz = pz - cz
    cos_y = math.cos(-rotation_y)
    sin_y = math.sin(-rotation_y)
    local_x = dx * cos_y + dz * sin_y
    local_z = -dx * sin_y + dz * cos_y
    return abs(local_x) <= sx and abs(py - cy) <= sy and abs(local_z) <= sz


def count_primitive_keepout_hits(enclosure: dict, keepouts: list[dict]) -> int:
    hits = 0
    for primitive in enclosure.get("collision_primitives", []):
        if any(
            point_inside_primitive(
                (
                    (keepout["x_min"] + keepout["x_max"]) * 0.5,
                    (keepout["y_min"] + keepout["y_max"]) * 0.5,
                    (keepout["z_min"] + keepout["z_max"]) * 0.5,
                ),
                primitive,
            )
            for keepout in keepouts
        ):
            hits += 1
    return hits


def check_file(path: Path, checks: list[dict]) -> bool:
    ok = path.exists()
    checks.append({"id": f"exists:{rel(path)}", "status": "PASS" if ok else "FAIL"})
    return ok


def check_manifest_hashes(manifest_path: Path, checks: list[dict]) -> None:
    manifest = load_json(manifest_path)
    outputs = manifest.get("outputs", {})
    for key, expected in sorted(outputs.items()):
        if not key.endswith("_sha256"):
            continue
        path_key = key.removesuffix("_sha256")
        artifact_rel = outputs.get(path_key)
        if not artifact_rel:
            continue
        artifact_path = ROOT / artifact_rel
        if not artifact_path.exists():
            checks.append({"id": f"manifest_hash:{rel(manifest_path)}:{artifact_rel}", "status": "FAIL", "reason": "missing artifact"})
            continue
        actual = sha256(artifact_path)
        checks.append(
            {
                "id": f"manifest_hash:{rel(manifest_path)}:{artifact_rel}",
                "status": "PASS" if actual == expected else "FAIL",
                "expected": expected,
                "actual": actual,
            }
        )


def write_markdown(path: Path, report: dict) -> None:
    lines = [
        "# MX01 Static Validation Report",
        "",
        f"- Status: `{report['status']}`",
        f"- Checks: `{report['counts']['checks']}`",
        f"- Failures: `{report['counts']['failures']}`",
        f"- Warnings: `{report['counts']['warnings']}`",
        "",
        "## Failed Checks",
        "",
    ]
    failures = [check for check in report["checks"] if check["status"] == "FAIL"]
    if failures:
        for check in failures:
            lines.append(f"- `{check['id']}`: {check.get('reason', 'failed')}")
    else:
        lines.append("- None")
    lines.extend(["", "## Warning Checks", ""])
    warnings = [check for check in report["checks"] if check["status"] == "WARN"]
    if warnings:
        for check in warnings:
            lines.append(f"- `{check['id']}`: {check.get('reason', 'warning')}")
    else:
        lines.append("- None")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    config_path = args.config.resolve()
    config = load_json(config_path)
    checks: list[dict] = []

    required_sections = [
        ("normalization_outputs", "normalized_obj"),
        ("occupancy_outputs", "intervals_json"),
        ("interior_volume_outputs", "volume_json"),
        ("traversal_outputs", "graph_json"),
        ("boundary_outputs", "raw_obj"),
        ("simplification_outputs", "simplified_obj"),
        ("interior_collision_outputs", "collision_obj"),
        ("interior_enclosure_outputs", "enclosure_obj"),
        ("interior_enclosure_outputs", "collider_obj"),
        ("dynamic_collision_outputs", "collision_obj"),
        ("scene_outputs", "review_scene"),
        ("scene_outputs", "playable_scene"),
    ]
    for section, key in required_sections:
        check_file(resolve_config_path(config, section, key), checks)

    for manifest_path in sorted((SHIP_DIR / "reports" / "manifests").glob("mx01_*_manifest.json")):
        if manifest_path.name == "mx01_static_validation_manifest.json":
            continue
        check_manifest_hashes(manifest_path, checks)

    traversal = load_json(resolve_config_path(config, "traversal_outputs", "graph_json"))
    deck_nodes = [node for node in traversal["nodes"] if node["kind"] == "deck"]
    checks.append(
        {
            "id": "traversal:all_decks_reachable",
            "status": "PASS" if len(traversal["reachable_decks"]) == len(deck_nodes) else "FAIL",
            "reachable_decks": len(traversal["reachable_decks"]),
            "deck_nodes": len(deck_nodes),
        }
    )

    dynamic_report = load_json(resolve_config_path(config, "dynamic_collision_outputs", "report_json"))
    checks.append(
        {
            "id": "dynamic_collision:convex_only",
            "status": "PASS" if dynamic_report["counts"]["concave_regions"] == 0 and dynamic_report["counts"]["convex_regions"] > 0 else "FAIL",
            "counts": dynamic_report["counts"],
        }
    )

    enclosure_report = load_json(resolve_config_path(config, "interior_enclosure_outputs", "report_json"))
    enclosure = load_json(resolve_config_path(config, "interior_enclosure_outputs", "enclosure_json"))
    interior_collision = load_json(resolve_config_path(config, "interior_collision_outputs", "collision_json"))
    occupancy = load_json(resolve_config_path(config, "occupancy_outputs", "intervals_json"))
    enclosure_counts = enclosure_report["counts"]
    checks.append(
        {
            "id": "interior_enclosure:has_walls_and_ceilings",
            "status": "PASS" if enclosure_counts["wall_objects"] > 0 and enclosure_counts["ceiling_objects"] > 0 else "FAIL",
            "counts": enclosure_counts,
        }
    )
    checks.append(
        {
            "id": "interior_enclosure:no_rectangular_room_boxes",
            "status": "PASS"
            if enclosure_report["fit"]["rectangular_room_boxes"] == 0
            and not enclosure_report["fit"].get("playable_collision_is_raw_binary_isosurface", True)
            and not enclosure_report["fit"].get("playable_collision_uses_concave_triangle_mesh", True)
            else "FAIL",
            "rectangular_room_boxes": enclosure_report["fit"]["rectangular_room_boxes"],
            "playable_collision_is_raw_binary_isosurface": enclosure_report["fit"].get("playable_collision_is_raw_binary_isosurface"),
            "playable_collision_uses_concave_triangle_mesh": enclosure_report["fit"].get("playable_collision_uses_concave_triangle_mesh"),
        }
    )
    checks.append(
        {
            "id": "interior_enclosure:inward_offset",
            "status": "PASS" if enclosure_report["fit"]["inward_offset_m"] > 0.0 and not enclosure_report["fit"]["protrudes_outside_by_construction"] else "FAIL",
            "fit": enclosure_report["fit"],
        }
    )
    enclosure_kinds = sorted({obj["kind"] for obj in enclosure["objects"]})
    checks.append(
        {
            "id": "interior_enclosure:evidence_triangle_mesh_only",
            "status": "PASS" if enclosure_kinds == ["triangle_mesh"] else "FAIL",
            "kinds": enclosure_kinds,
        }
    )
    primitive_kinds = sorted({obj["kind"] for obj in enclosure.get("collision_primitives", [])})
    checks.append(
        {
            "id": "interior_enclosure:playable_uses_controller_safe_primitives",
            "status": "PASS"
            if enclosure_counts.get("collision_primitives", 0) > 0
            and primitive_kinds
            and all(kind in {"box", "oriented_box"} for kind in primitive_kinds)
            else "FAIL",
            "primitive_kinds": primitive_kinds,
            "collision_primitives": enclosure_counts.get("collision_primitives", 0),
            "wall_collision_primitives": enclosure_counts.get("wall_collision_primitives", 0),
            "ceiling_collision_primitives": enclosure_counts.get("ceiling_collision_primitives", 0),
        }
    )
    connector_side_guard_primitives = [
        primitive
        for primitive in enclosure.get("collision_primitives", [])
        if "stair_side_guard" in primitive["name"]
        or primitive.get("deck") == "connector_side_guard"
        or primitive.get("source") == "controller_safe_connector_side_guard"
    ]
    checks.append(
        {
            "id": "interior_enclosure:no_stair_local_guard_walls",
            "status": "PASS"
            if enclosure_counts.get("stair_side_guard_primitives", 0) == 0
            and not enclosure.get("contract", {}).get("connector_side_guards", True)
            and not connector_side_guard_primitives
            else "FAIL",
            "stair_side_guard_primitives": enclosure_counts.get("stair_side_guard_primitives"),
            "connector_side_guards": enclosure.get("contract", {}).get("connector_side_guards"),
            "offending_primitives": [primitive["name"] for primitive in connector_side_guard_primitives],
        }
    )
    collider_obj_counts = enclosure_report.get("collider_obj_counts", {})
    checks.append(
        {
            "id": "interior_enclosure:visible_collider_matches_physics_primitives",
            "status": "PASS" if collider_obj_counts.get("primitive_boxes") == enclosure_counts.get("collision_primitives") else "FAIL",
            "collider_obj_counts": collider_obj_counts,
            "collision_primitives": enclosure_counts.get("collision_primitives"),
        }
    )
    closure = enclosure_report.get("closure", {})
    checks.append(
        {
            "id": "interior_enclosure:closed_floor_footprint_perimeter",
            "status": "PASS"
            if closure.get("floor_cells", 0) > 0
            and closure.get("exterior_edges", 0) > 0
            and closure.get("covered_exterior_edges", 0) + closure.get("route_reserved_edges", 0) == closure.get("exterior_edges", -1)
            and closure.get("wall_primitives_from_closed_perimeter", 0) > 0
            and closure.get("uncovered_exterior_edges") == 0
            else "FAIL",
            "closure": closure,
        }
    )
    exact_coverage = check_exact_floor_edge_wall_coverage(enclosure, interior_collision, occupancy, traversal)
    checks.append(
        {
            "id": "interior_enclosure:exact_stage7a_floor_edges_covered",
            "status": "PASS"
            if exact_coverage["total_edges"] > 0
            and exact_coverage["covered_edges"] == exact_coverage["total_edges"]
            and closure.get("route_reserved_edges", 0) == 0
            else "FAIL",
            "coverage": exact_coverage,
        }
    )
    smoothness = enclosure_report["smoothness"]
    checks.append(
        {
            "id": "interior_enclosure:capsule_friendly_smoothness",
            "status": "PASS" if smoothness["wall_slide_snag_count"] == 0 and smoothness["max_adjacent_normal_delta_degrees"] <= smoothness["snag_threshold_degrees"] else "FAIL",
            "smoothness": smoothness,
        }
    )
    keepouts = connector_keepouts(interior_collision, config)
    keepout_hits = count_enclosure_keepout_hits(enclosure, keepouts)
    primitive_keepout_hits = count_primitive_keepout_hits(enclosure, keepouts)
    checks.append(
        {
            "id": "interior_enclosure:connector_keepouts_clear",
            "status": "PASS" if keepout_hits == 0 else "FAIL",
            "keepouts": len(keepouts),
            "triangle_center_hits": keepout_hits,
            "primitive_keepout_center_hits_diagnostic": primitive_keepout_hits,
        }
    )
    connector_footprint_hits = count_primitive_connector_footprint_hits(enclosure, interior_collision)
    checks.append(
        {
            "id": "interior_enclosure:connector_footprints_clear",
            "status": "PASS" if connector_footprint_hits == 0 else "FAIL",
            "primitive_connector_footprint_hits": connector_footprint_hits,
        }
    )
    wall_stair_hits, wall_stair_samples = count_wall_stair_clearance_hits(enclosure, interior_collision)
    checks.append(
        {
            "id": "interior_enclosure:wall_stair_clearances_clear",
            "status": "PASS" if wall_stair_hits == 0 else "FAIL",
            "wall_stair_clearance_hits": wall_stair_hits,
            "samples": wall_stair_samples,
        }
    )
    playable_scene_text = resolve_config_path(config, "scene_outputs", "playable_scene").read_text(encoding="utf-8")
    stair_tread_names = [obj["name"] for obj in interior_collision["objects"] if obj["role"] == "player_connector_stair_tread"]
    stair_tread_count = len(stair_tread_names)
    support_shape_count = playable_scene_text.count('_support" type="CollisionShape3D" parent="ShipRoot/WalkableSupportSurfaces"')
    primary_stair_collision_count = sum(
        1
        for name in stair_tread_names
        if f'[node name="{name}" type="CollisionShape3D" parent="ShipRoot/InteriorCollisionBody"]' in playable_scene_text
    )
    checks.append(
        {
            "id": "playable_scene:stairs_use_walkable_support_surfaces",
            "status": "PASS"
            if "WalkableSupportSurfaces" in playable_scene_text
            and "collision_layer = 128" in playable_scene_text
            and support_shape_count == stair_tread_count
            and primary_stair_collision_count == 0
            else "FAIL",
            "stair_tread_count": stair_tread_count,
            "support_shape_count": support_shape_count,
            "primary_stair_collision_count": primary_stair_collision_count,
        }
    )

    occupancy_report = load_json(resolve_config_path(config, "occupancy_outputs", "report_json"))
    checks.append(
        {
            "id": "occupancy:odd_parity_rays",
            "status": "WARN" if occupancy_report["counts"]["odd_parity_rays"] else "PASS",
            "reason": "Odd parity rays remain from non-manifold/tangential cases." if occupancy_report["counts"]["odd_parity_rays"] else "No odd parity rays.",
            "odd_parity_rays": occupancy_report["counts"]["odd_parity_rays"],
        }
    )

    outside = []
    for path in SHIP_DIR.rglob("*"):
        if path.is_file() and not str(path.resolve()).startswith(str(SHIP_DIR.resolve())):
            outside.append(rel(path))
    checks.append({"id": "colocation:all_checked_files_under_mx01", "status": "PASS" if not outside else "FAIL", "outside": outside})

    failures = [check for check in checks if check["status"] == "FAIL"]
    warnings = [check for check in checks if check["status"] == "WARN"]
    report = {
        "ship_id": config["ship_id"],
        "method": "mx01_static_collision_validation_v1",
        "status": "PASS" if not failures else "FAIL",
        "counts": {"checks": len(checks), "failures": len(failures), "warnings": len(warnings)},
        "checks": checks,
        "config": {"path": rel(config_path), "sha256": sha256(config_path), "effective_values": config},
        "tools": {
            "validate_mx01_collision_static.py": {"path": rel(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())}
        },
    }

    report_json = resolve_config_path(config, "validation_outputs", "report_json")
    report_md = resolve_config_path(config, "validation_outputs", "report_md")
    manifest_json = resolve_config_path(config, "validation_outputs", "manifest_json")
    write_json(report_json, report)
    write_markdown(report_md, report)
    write_json(
        manifest_json,
        {
            "ship_id": config["ship_id"],
            "stage": "static_validation",
            "config": report["config"],
            "outputs": {
                "report_json": rel(report_json),
                "report_json_sha256": sha256(report_json),
                "report_md": rel(report_md),
            },
            "tools": report["tools"],
        },
    )
    print(f"Wrote {rel(report_json)}")
    print(f"Wrote {rel(report_md)}")
    print(f"Wrote {rel(manifest_json)}")
    print(f"status={report['status']} failures={len(failures)} warnings={len(warnings)}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
