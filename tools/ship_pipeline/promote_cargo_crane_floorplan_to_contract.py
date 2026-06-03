#!/usr/bin/env python3
"""Promote the accepted CargoCrane floorplan review data into the layout contract."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "assets/source/blender/ships/cargo_crane/cargo_crane_interior_layout_contract.json"
FLOORPLAN_PATH = ROOT / "assets/models/ship/cargo_crane/cargo_crane_objective_walkable_surfaces.json"
FLOORPLAN_REPORT_PATH = ROOT / "reports/ship_pipeline/cargo_crane_voxel_fit/cargo_crane_regularized_floorplan_report.json"


CEILING_BY_REGION = {
    "aft_center_service": 0.0,
    "central_body_lower": 7.5,
    "central_body_lower_to_forward_access": 5.5,
    "forward_access": 5.5,
    "cockpit_lower": -3.0,
    "cockpit_upper_command_gallery": 4.0,
}

ROUTE_CHECKPOINTS = [
    ("Aft service floor", [0.0, -5.0, -50.5]),
    ("Aft service to central ramp foot", [0.0, -5.0, -37.0]),
    ("Central body aft landing", [0.0, -1.0, -28.0]),
    ("Central body center", [0.0, -1.0, 1.0]),
    ("Central body forward bridge", [0.0, -1.0, 31.5]),
    ("Forward access", [0.0, -1.0, 46.0]),
    ("Cockpit upper aft landing", [0.0, -1.0, 60.15]),
    ("Cockpit upper forward deck", [0.0, -1.0, 68.0]),
    ("Port cockpit stair upper", [-3.31, -1.0, 60.8]),
    ("Port cockpit stair lower", [-3.31, -9.0, 68.2]),
    ("Lower cockpit center", [0.0, -9.0, 67.5]),
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def bounds_from_surface(surface: dict) -> tuple[list[float], list[float]]:
    center = surface["center"]
    size = surface["size"]
    return (
        [center[index] - size[index] * 0.5 for index in range(3)],
        [center[index] + size[index] * 0.5 for index in range(3)],
    )


def merge_bounds(items: list[tuple[list[float], list[float]]]) -> tuple[list[float], list[float]]:
    return (
        [min(item[0][axis] for item in items) for axis in range(3)],
        [max(item[1][axis] for item in items) for axis in range(3)],
    )


def round_values(values: list[float]) -> list[float]:
    return [round(value, 4) for value in values]


def build_semantic_regions(surfaces: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    roles_by_region: dict[str, set[str]] = defaultdict(set)
    for surface in surfaces:
        if surface["type"] != "floor_box":
            continue
        region_id = surface.get("region") or surface["name"].replace("_regularized_floor", "")
        grouped[region_id].append(surface)
        for role in surface.get("roles", []):
            roles_by_region[region_id].add(role)

    regions = []
    for region_id, region_surfaces in grouped.items():
        bounds = [bounds_from_surface(surface) for surface in region_surfaces]
        bmin, bmax = merge_bounds(bounds)
        floor_y = min(surface["center"][1] for surface in region_surfaces)
        bmin[1] = floor_y
        bmax[1] = CEILING_BY_REGION.get(region_id, floor_y + 4.0)
        regions.append(
            {
                "id": region_id,
                "representation": "accepted_regularized_floorplan_region",
                "roles": sorted(roles_by_region[region_id]),
                "bounds": {"min": round_values(bmin), "max": round_values(bmax)},
                "source_surfaces": [surface["name"] for surface in region_surfaces],
            }
        )

    order = {
        "aft_center_service": 0,
        "central_body_lower": 1,
        "central_body_lower_to_forward_access": 2,
        "forward_access": 3,
        "cockpit_upper_command_gallery": 4,
        "cockpit_lower": 5,
    }
    return sorted(regions, key=lambda region: order.get(region["id"], 100))


def build_vertical_connectors(surfaces: list[dict]) -> list[dict]:
    connectors = []
    for surface in surfaces:
        if surface["type"] != "stair_path":
            continue
        connectors.append(
            {
                "name": surface["name"],
                "type": "stair_path",
                "points": surface["points"],
                "surface_width": surface["width"],
                "thickness": surface.get("thickness", 0.24),
                "role": surface.get("role", "vertical_connector"),
            }
        )
    return connectors


def build_connection_targets(surfaces: list[dict]) -> list[dict]:
    targets = []
    for surface in surfaces:
        if surface["type"] == "floor_box":
            targets.append({"name": surface["name"], "surface": surface["name"], "local_origin": surface["center"]})
        elif surface["type"] == "ramp":
            targets.append({"name": f"{surface['name']}_start", "surface": surface["name"], "local_origin": surface["start"]})
            targets.append({"name": f"{surface['name']}_end", "surface": surface["name"], "local_origin": surface["end"]})
        elif surface["type"] == "stair_path":
            targets.append({"name": f"{surface['name']}_top", "surface": surface["name"], "local_origin": surface["points"][0]})
            targets.append({"name": f"{surface['name']}_bottom", "surface": surface["name"], "local_origin": surface["points"][-1]})
    return targets


def build_side_wall_openings(contract: dict) -> list[dict]:
    openings = []
    for entrance in contract.get("entrance_hatches", []):
        openings.append(
            {
                "name": f"{entrance['name']}_side_wall_opening",
                "region": entrance.get("target_room", "central_body_lower"),
                "side": entrance["side"],
                "center_y": round(float(entrance["cut_center"][1]), 4),
                "height_y": round(float(entrance["cut_size"][1]), 4),
                "center_z": round(float(entrance["cut_center"][2]), 4),
                "width_z": round(max(5.8, float(entrance["cut_size"][2]) + 0.8), 4),
                "source": "approved_center_body_hatchway",
            }
        )
    return openings


def main() -> int:
    contract = load_json(CONTRACT_PATH)
    floorplan = load_json(FLOORPLAN_PATH)
    floorplan_report = load_json(FLOORPLAN_REPORT_PATH)
    surfaces = floorplan["surfaces"]

    contract["floorplan_generation"] = {
        "status": "accepted",
        "method": floorplan["method"],
        "source_surfaces": str(FLOORPLAN_PATH.relative_to(ROOT)),
        "source_report": str(FLOORPLAN_REPORT_PATH.relative_to(ROOT)),
        "regularized_regions": floorplan_report.get("regions", []),
        "accepted_surfaces": surfaces,
        "primary_route": floorplan.get("primary_route", []),
    }
    contract["semantic_regions"] = build_semantic_regions(surfaces)
    contract["semantic_connection_targets"] = build_connection_targets(surfaces)
    contract["vertical_connectors"] = build_vertical_connectors(surfaces)
    contract["player_traversal_validation"] = {
        "planar_tolerance": 1.2,
        "maximum_seconds_per_checkpoint": 10.0,
        "minimum_progress_meters": 0.2,
        "stuck_seconds": 2.0,
        "checkpoints": [
            {"name": name, "local_origin": [round(value, 4) for value in point]}
            for name, point in ROUTE_CHECKPOINTS
        ],
    }
    for entrance in contract.get("entrance_hatches", []):
        entrance["entry_floor_y"] = -1.0
        entrance["target_room"] = "central_body_lower"
    contract.setdefault("enclosure_generation", {})["side_wall_openings"] = build_side_wall_openings(contract)
    contract["semantic_discovery_notes"] = {
        "status": "floorplan_accepted_and_promoted",
        "finding": "Accepted CargoCrane floorplan is stored in floorplan_generation and drives traversal/enclosure generation.",
        "implication": "Do not regenerate traversal from raw voxel fragments or provisional manual envelopes.",
    }

    CONTRACT_PATH.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    print(f"Promoted accepted floorplan into {CONTRACT_PATH.relative_to(ROOT)}")
    print(f"Semantic regions: {len(contract['semantic_regions'])}")
    print(f"Accepted surfaces: {len(surfaces)}")
    print(f"Traversal checkpoints: {len(contract['player_traversal_validation']['checkpoints'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
