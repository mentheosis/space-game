#!/usr/bin/env python3
"""Regularize CargoCrane objective voxels into Shuttle-style floorplan surfaces."""

from __future__ import annotations

import heapq
import json
import math
from collections import defaultdict
from pathlib import Path

import build_shuttle_p3_from_exterior_glb as ship_voxels


ROOT = Path(__file__).resolve().parents[2]
OUT_MODEL_DIR = ROOT / "assets/models/ship/cargo_crane"
OUT_REPORT_DIR = ROOT / "reports/ship_pipeline/cargo_crane_voxel_fit"
VOXELS_JSON = OUT_REPORT_DIR / "cargo_crane_objective_interior_voxels_compact.json"
SURFACES_JSON = OUT_MODEL_DIR / "cargo_crane_objective_walkable_surfaces.json"
REPORT_JSON = OUT_REPORT_DIR / "cargo_crane_regularized_floorplan_report.json"
REPORT_MD = OUT_REPORT_DIR / "cargo_crane_regularized_floorplan_report.md"
PROJECTION_PNG = OUT_REPORT_DIR / "cargo_crane_regularized_floorplan_projection_current.png"

VOXEL_SIZE = 1.0
FLOOR_THICKNESS = 0.22
RAMP_THICKNESS = 0.24
STAIR_THICKNESS = 0.24
MAX_CENTERLINE_X = 12.0
MIN_NODE_COUNT = 8
REGULARIZE_Z_GAP = 8.0
GRAPH_MAX_STEP = 0.6
GRAPH_MAX_DIST = 1.65
CONNECTOR_MAX_STEP = 8.0
CONNECTOR_MAX_DIST = 12.0


REGION_SPECS = [
    {
        "id": "aft_center_service",
        "roles": ["engineering", "aft service"],
        "z_min": -64.0,
        "z_max": -38.0,
        "floor_y_mode": "sampled",
        "max_half_width": 8.5,
    },
    {
        "id": "central_body_lower",
        "roles": ["medical", "living", "corridor"],
        "z_min": -30.0,
        "z_max": 32.0,
        "floor_y_mode": "sampled",
        "max_half_width": 6.5,
    },
    {
        "id": "forward_access",
        "roles": ["cockpit access", "corridor"],
        "z_min": 33.0,
        "z_max": 59.0,
        "floor_y_mode": "sampled",
        "max_half_width": 5.5,
    },
    {
        "id": "cockpit_lower",
        "roles": ["cockpit"],
        "z_min": 60.0,
        "z_max": 73.0,
        "floor_y_mode": "sampled",
        "max_half_width": 4.5,
    },
]


def load_voxels() -> list[dict]:
    raw_voxels = json.loads(VOXELS_JSON.read_text(encoding="utf-8"))
    return [
        {
            "center": [float(voxel[0]), float(voxel[1]), float(voxel[2])],
            "can_stand": bool(voxel[3]),
            "head_clearance": float(voxel[4]),
        }
        for voxel in raw_voxels
    ]


def key_for(center: list[float]) -> tuple[int, int, int]:
    return tuple(int(round(value / VOXEL_SIZE)) for value in center)


def build_walkable_nodes(voxels: list[dict]) -> dict[tuple[int, int, int], dict]:
    bottom_by_xz: dict[tuple[int, int], dict] = {}
    for voxel in voxels:
        if not voxel["can_stand"]:
            continue
        x, y, z = key_for(voxel["center"])
        if abs(x * VOXEL_SIZE) > MAX_CENTERLINE_X:
            continue
        existing = bottom_by_xz.get((x, z))
        if existing is None or y < key_for(existing["center"])[1]:
            bottom_by_xz[(x, z)] = voxel

    nodes = {}
    for voxel in bottom_by_xz.values():
        key = key_for(voxel["center"])
        nodes[key] = {"key": key, **voxel}
    return nodes


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def regularized_region(spec: dict, nodes: dict[tuple[int, int, int], dict]) -> dict | None:
    candidates = [
        node
        for node in nodes.values()
        if spec["z_min"] <= node["center"][2] <= spec["z_max"]
        and abs(node["center"][0]) <= spec["max_half_width"] + 0.75
    ]
    if len(candidates) < MIN_NODE_COUNT:
        return None

    by_z: dict[float, list[dict]] = defaultdict(list)
    for node in candidates:
        by_z[node["center"][2]].append(node)
    z_values = sorted(by_z)
    kept_z = []
    for z in z_values:
        if not kept_z or z - kept_z[-1] <= REGULARIZE_Z_GAP:
            kept_z.append(z)

    selected = [node for node in candidates if node["center"][2] in kept_z]
    if len(selected) < MIN_NODE_COUNT:
        return None

    floor_y = percentile([node["center"][1] for node in selected], 0.18)
    if floor_y is None:
        return None
    z_min = min(node["center"][2] for node in selected)
    z_max = max(node["center"][2] for node in selected)
    x_abs = percentile([abs(node["center"][0]) for node in selected], 0.90)
    if x_abs is None:
        return None
    half_width = max(1.2, min(spec["max_half_width"], x_abs + 0.5))

    sections = []
    for z in kept_z:
        slice_nodes = by_z[z]
        if not slice_nodes:
            continue
        sections.append(
            {
                "z": z,
                "x_min": round(max(-half_width, min(node["center"][0] for node in slice_nodes)), 4),
                "x_max": round(min(half_width, max(node["center"][0] for node in slice_nodes)), 4),
                "y_min": round(min(node["center"][1] for node in slice_nodes), 4),
                "y_max": round(max(node["center"][1] for node in slice_nodes), 4),
                "node_count": len(slice_nodes),
            }
        )

    return {
        "id": spec["id"],
        "roles": spec["roles"],
        "node_count": len(selected),
        "bounds": {
            "min": [round(-half_width, 4), round(floor_y, 4), round(z_min, 4)],
            "max": [round(half_width, 4), round(floor_y, 4), round(z_max, 4)],
        },
        "center": [0.0, round(floor_y, 4), round((z_min + z_max) * 0.5, 4)],
        "size": [round(half_width * 2.0, 4), FLOOR_THICKNESS, round(z_max - z_min + VOXEL_SIZE, 4)],
        "sections": sections,
    }


def nearest_node(nodes: dict[tuple[int, int, int], dict], target: list[float]) -> tuple[int, int, int] | None:
    if not nodes:
        return None
    best = min(
        nodes.values(),
        key=lambda node: (
            (node["center"][0] - target[0]) ** 2
            + (node["center"][1] - target[1]) ** 2
            + (node["center"][2] - target[2]) ** 2
        ),
    )
    return best["key"]


def find_path(
    nodes: dict[tuple[int, int, int], dict],
    start_key: tuple[int, int, int],
    goal_key: tuple[int, int, int],
    max_step: float,
    max_dist: float,
) -> list[dict]:
    centers = {key: node["center"] for key, node in nodes.items()}
    bucket_size = max(VOXEL_SIZE, max_dist)
    buckets: dict[tuple[int, int], list[tuple[int, int, int]]] = defaultdict(list)
    for key, center in centers.items():
        buckets[(math.floor(center[0] / bucket_size), math.floor(center[2] / bucket_size))].append(key)
    bucket_radius = max(1, int(math.ceil(max_dist / bucket_size)))
    open_set = [(0.0, start_key)]
    came_from: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    g_score = {start_key: 0.0}
    closed = set()

    def heuristic(a_key: tuple[int, int, int], b_key: tuple[int, int, int]) -> float:
        a = centers[a_key]
        b = centers[b_key]
        return math.dist((a[0], a[2]), (b[0], b[2]))

    while open_set:
        _score, current = heapq.heappop(open_set)
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
            nx, ny, nz = centers[key]
            horizontal = math.dist((cx, cz), (nx, nz))
            if horizontal <= 0.001 or horizontal > max_dist:
                continue
            vertical = abs(ny - cy)
            if vertical > max_step:
                continue
            candidate = g_score[current] + horizontal + vertical * 2.0
            if candidate < g_score.get(key, float("inf")):
                came_from[key] = current
                g_score[key] = candidate
                heapq.heappush(open_set, (candidate + heuristic(key, goal_key), key))
    return []


def region_nodes(region: dict, nodes: dict[tuple[int, int, int], dict]) -> dict[tuple[int, int, int], dict]:
    bmin = region["bounds"]["min"]
    bmax = region["bounds"]["max"]
    return {
        key: node
        for key, node in nodes.items()
        if bmin[0] - 0.75 <= node["center"][0] <= bmax[0] + 0.75
        and bmin[2] - 0.75 <= node["center"][2] <= bmax[2] + 0.75
    }


def discover_route(regions: list[dict], nodes: dict[tuple[int, int, int], dict]) -> dict:
    route_keys = []
    for region in regions:
        target = region["center"]
        key = nearest_node(region_nodes(region, nodes), target)
        if key is None:
            return {"status": "FAIL", "reason": f"no route node in {region['id']}", "path": [], "segments": []}
        route_keys.append(key)

    full_path = []
    segments = []
    connectors = []
    for start_key, goal_key in zip(route_keys, route_keys[1:]):
        segment = find_path(nodes, start_key, goal_key, GRAPH_MAX_STEP, GRAPH_MAX_DIST)
        requires_connector = False
        if not segment:
            segment = find_path(nodes, start_key, goal_key, CONNECTOR_MAX_STEP, CONNECTOR_MAX_DIST)
            requires_connector = bool(segment)
        if not segment:
            return {
                "status": "FAIL",
                "reason": "no graph path between regularized regions",
                "route_keys": route_keys,
                "path": [node["center"] for node in full_path],
                "segments": segments,
            }
        max_vertical = max((abs(a["center"][1] - b["center"][1]) for a, b in zip(segment, segment[1:])), default=0.0)
        max_horizontal = max(
            (math.dist((a["center"][0], a["center"][2]), (b["center"][0], b["center"][2])) for a, b in zip(segment, segment[1:])),
            default=0.0,
        )
        if max_vertical > GRAPH_MAX_STEP or max_horizontal > GRAPH_MAX_DIST:
            requires_connector = True
        if full_path:
            full_path.extend(segment[1:])
        else:
            full_path.extend(segment)
        report = {
            "start": nodes[start_key]["center"],
            "goal": nodes[goal_key]["center"],
            "node_count": len(segment),
            "requires_connector": requires_connector,
            "max_vertical_delta": round(max_vertical, 4),
            "max_horizontal_delta": round(max_horizontal, 4),
        }
        segments.append(report)
        if requires_connector:
            connectors.append(report)
    return {
        "status": "PASS_WITH_CONNECTORS" if connectors else "PASS",
        "route_keys": route_keys,
        "path_node_count": len(full_path),
        "path": [node["center"] for node in full_path],
        "segments": segments,
        "connector_segments": connectors,
    }


def surfaces_from_regions(regions: list[dict], route: dict) -> list[dict]:
    surfaces = []
    for region in regions:
        surfaces.append(
            {
                "name": f"{region['id']}_regularized_floor",
                "type": "floor_box",
                "region": region["id"],
                "center": region["center"],
                "size": region["size"],
                "roles": region["roles"],
                "source": "regularized_objective_voxels",
            }
        )

    connector_index = 1
    for current, following in zip(regions, regions[1:]):
        current_max_z = current["bounds"]["max"][2]
        following_min_z = following["bounds"]["min"][2]
        z_gap = following_min_z - current_max_z
        y_delta = following["center"][1] - current["center"][1]
        if following["id"] == "cockpit_lower":
            continue
        if abs(y_delta) <= 0.6 and 0.0 < z_gap <= 4.0:
            width = min(current["size"][0], following["size"][0])
            surfaces.append(
                {
                    "name": f"{current['id']}_to_{following['id']}_same_level_bridge",
                    "type": "floor_box",
                    "region": f"{current['id']}_to_{following['id']}",
                    "center": [0.0, current["center"][1], round((current_max_z + following_min_z) * 0.5, 4)],
                    "size": [round(width, 4), FLOOR_THICKNESS, round(z_gap + VOXEL_SIZE, 4)],
                    "roles": ["same_level_interstitial_connector"],
                    "source": "regularized_gap_fill",
                }
            )
            continue
        if abs(y_delta) <= 0.6 and z_gap <= 3.0:
            continue

        start = [0.0, current["center"][1], current_max_z + min(1.0, max(0.0, z_gap * 0.25))]
        end = [0.0, following["center"][1], following_min_z - min(1.0, max(0.0, z_gap * 0.25))]
        surfaces.append(
            {
                "name": f"regularized_connector_{connector_index:02d}",
                "type": "ramp",
                "start": [round(value, 4) for value in start],
                "end": [round(value, 4) for value in end],
                "width": 2.4,
                "thickness": RAMP_THICKNESS,
                "role": "edge_to_edge_inter_region_connector",
            }
        )
        connector_index += 1

    cockpit_lower = next((region for region in regions if region["id"] == "cockpit_lower"), None)
    if cockpit_lower is not None:
        lower_center = [0.0, cockpit_lower["center"][1], 67.5]
        lower_size = [7.4, FLOOR_THICKNESS, 10.0]
        for surface in surfaces:
            if surface.get("region") == "cockpit_lower":
                surface["center"] = lower_center
                surface["size"] = lower_size
                surface["source"] = "trimmed_objective_voxels_for_cockpit_lower"
                break

        upper_floor_pieces = [
            ("cockpit_upper_aft_full_width_landing", [0.0, -1.0, 60.15], [8.5, FLOOR_THICKNESS, 1.3]),
            ("cockpit_upper_narrow_stair_clearance_bridge", [0.0, -1.0, 64.6], [3.8, FLOOR_THICKNESS, 7.6]),
            ("cockpit_upper_forward_full_width_deck", [0.0, -1.0, 68.0], [8.5, FLOOR_THICKNESS, 4.0]),
        ]
        for name, center, size in upper_floor_pieces:
            surfaces.append(
                {
                    "name": name,
                    "type": "floor_box",
                    "region": "cockpit_upper_command_gallery",
                    "center": center,
                    "size": size,
                    "roles": ["cockpit", "upper level", "support seats"],
                    "source": "approved_two_level_cockpit_requirement_with_stair_openings",
                }
            )
        for side, x in (("port", -3.31), ("starboard", 3.31)):
            surfaces.append(
                {
                    "name": f"cockpit_{side}_edge_stairs_to_lower_deck",
                    "type": "stair_path",
                    "points": [
                        [x, -1.0, 60.8],
                        [x, -3.6, 63.1],
                        [x, -6.2, 65.7],
                        [x, lower_center[1], 68.2],
                    ],
                    "width": 1.68,
                    "thickness": STAIR_THICKNESS,
                    "role": "cockpit_edge_stair",
                }
            )
    return surfaces


def draw_projection(path: Path, nodes: dict[tuple[int, int, int], dict], regions: list[dict], surfaces: list[dict], route: dict) -> None:
    canvas = ship_voxels.ImageCanvas(1920, 720, (12, 15, 19))
    panels = [(24, 36, 604, 648, (2, 1)), (658, 36, 604, 648, (2, 0)), (1292, 36, 604, 648, (0, 1))]
    points = [node["center"] for node in nodes.values()] + route.get("path", [])
    if not points:
        canvas.write_png(path)
        return

    for px, py, pw, ph, axes in panels:
        canvas.rect(px, py, px + pw - 1, py + ph - 1, (40, 46, 54))
        coords = [(point[axes[0]], point[axes[1]]) for point in points]
        min_x, max_x = min(c[0] for c in coords) - 3.0, max(c[0] for c in coords) + 3.0
        min_y, max_y = min(c[1] for c in coords) - 3.0, max(c[1] for c in coords) + 3.0

        def map_point(x: float, y: float) -> tuple[int, int]:
            sx = int(px + (x - min_x) / max(0.001, max_x - min_x) * (pw - 1))
            sy = int(py + (1.0 - (y - min_y) / max(0.001, max_y - min_y)) * (ph - 1))
            return sx, sy

        for node in nodes.values():
            sx, sy = map_point(node["center"][axes[0]], node["center"][axes[1]])
            canvas.rect(sx - 1, sy - 1, sx + 1, sy + 1, (70, 135, 175), fill=True)

        for surface in surfaces:
            if surface["type"] == "floor_box":
                center = surface["center"]
                size = surface["size"]
                color = (245, 205, 80)
                bmin = [center[index] - size[index] * 0.5 for index in range(3)]
                bmax = [center[index] + size[index] * 0.5 for index in range(3)]
                if axes == (2, 1):
                    corners = [(bmin[2], bmin[1]), (bmax[2], bmin[1]), (bmax[2], bmax[1]), (bmin[2], bmax[1])]
                elif axes == (2, 0):
                    corners = [(bmin[2], bmin[0]), (bmax[2], bmin[0]), (bmax[2], bmax[0]), (bmin[2], bmax[0])]
                else:
                    corners = [(bmin[0], bmin[1]), (bmax[0], bmin[1]), (bmax[0], bmax[1]), (bmin[0], bmax[1])]
                mapped = [map_point(x, y) for x, y in corners]
                for index, start in enumerate(mapped):
                    end = mapped[(index + 1) % len(mapped)]
                    canvas.line(start[0], start[1], end[0], end[1], color)
                    canvas.line(start[0] + 1, start[1], end[0] + 1, end[1], color)
            elif surface["type"] == "ramp":
                a = surface["start"]
                b = surface["end"]
                x0, y0 = map_point(a[axes[0]], a[axes[1]])
                x1, y1 = map_point(b[axes[0]], b[axes[1]])
                canvas.line(x0, y0, x1, y1, (255, 130, 70))
                canvas.line(x0 + 1, y0, x1 + 1, y1, (255, 130, 70))

        route_points = route.get("path", [])
        mapped_route = [map_point(point[axes[0]], point[axes[1]]) for point in route_points]
        for a, b in zip(mapped_route, mapped_route[1:]):
            canvas.line(a[0], a[1], b[0], b[1], (245, 245, 245))

    canvas.write_png(path)


def main() -> int:
    voxels = load_voxels()
    nodes = build_walkable_nodes(voxels)
    regions = [region for spec in REGION_SPECS if (region := regularized_region(spec, nodes)) is not None]
    route = discover_route(regions, nodes)
    surfaces = surfaces_from_regions(regions, route)

    OUT_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    OUT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    SURFACES_JSON.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "ship_id": "cargo_crane",
                "coordinate_space": "ship local",
                "source_voxels": str(VOXELS_JSON.relative_to(ROOT)),
                "method": "shuttle_style_regularized_floorplan_from_objective_voxels",
                "surfaces": surfaces,
                "primary_route": route.get("path", []),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    draw_projection(PROJECTION_PNG, nodes, regions, surfaces, route)

    report = {
        "schema_version": 1,
        "ship_id": "cargo_crane",
        "status": route.get("status", "UNKNOWN"),
        "method": "shuttle_style_regularized_floorplan_from_objective_voxels",
        "walkable_node_count": len(nodes),
        "region_count": len(regions),
        "surface_count": len(surfaces),
        "regions": regions,
        "route": route,
        "evidence": {
            "surfaces": str(SURFACES_JSON.relative_to(ROOT)),
            "projection": str(PROJECTION_PNG.relative_to(ROOT)),
        },
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# CargoCrane Regularized Floorplan Report",
        "",
        f"Status: **{report['status']}**",
        "",
        f"- Method: `{report['method']}`",
        f"- Walkable nodes: `{len(nodes)}`",
        f"- Regularized regions: `{len(regions)}`",
        f"- Review surfaces: `{len(surfaces)}`",
        f"- Projection: `{PROJECTION_PNG.relative_to(ROOT)}`",
        f"- Surfaces JSON: `{SURFACES_JSON.relative_to(ROOT)}`",
        "",
        "## Color Key",
        "",
        "- Blue: bottom walkable nodes derived from objective interior voxels.",
        "- Yellow outline: regularized floor regions.",
        "- Orange line: connector ramp recommended by graph discovery.",
        "- White line: discovered route through the regularized regions.",
        "",
        "## Regions",
        "",
    ]
    for region in regions:
        lines.append(f"- `{region['id']}` nodes={region['node_count']} center={region['center']} size={region['size']}")
    lines += ["", "## Route Segments", ""]
    for segment in route.get("segments", []):
        lines.append(
            f"- start={segment['start']} goal={segment['goal']} nodes={segment['node_count']} connector={segment['requires_connector']} "
            f"max_vertical={segment['max_vertical_delta']} max_horizontal={segment['max_horizontal_delta']}"
        )
    if route.get("reason"):
        lines += ["", f"Reason: `{route['reason']}`"]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {SURFACES_JSON.relative_to(ROOT)}")
    print(f"Wrote {REPORT_MD.relative_to(ROOT)}")
    print(f"Wrote {PROJECTION_PNG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
