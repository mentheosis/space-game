#!/usr/bin/env python3
"""Generate CargoCrane traversal surface candidates from the layout contract."""

from __future__ import annotations

import json
from pathlib import Path

import build_shuttle_p3_from_exterior_glb as ship_voxels


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "assets/source/blender/ships/cargo_crane/cargo_crane_interior_layout_contract.json"
OUT_MODEL_DIR = ROOT / "assets/models/ship/cargo_crane"
OUT_REPORT_DIR = ROOT / "reports/ship_pipeline/cargo_crane_voxel_fit"
SURFACES_JSON = OUT_MODEL_DIR / "cargo_crane_traversal_surfaces.json"
FEATURE_VOXELS_JSON = OUT_REPORT_DIR / "cargo_crane_voxels_with_traversal_features.json"
REPORT_JSON = OUT_REPORT_DIR / "cargo_crane_traversal_surfaces_report.json"
REPORT_MD = OUT_REPORT_DIR / "cargo_crane_traversal_surfaces_report.md"
PROJECTION_PNG = OUT_REPORT_DIR / "cargo_crane_voxel_traversal_projection_current.png"
VOXELS_JSON = OUT_REPORT_DIR / "cargo_crane_voxels_full_compact.json"


FLOOR_THICKNESS = 0.22
RAMP_THICKNESS = 0.24
ENTRY_RAMP_WIDTH = 3.2
CORRIDOR_WIDTH = 2.4


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def center_and_size(bounds: dict) -> tuple[list[float], list[float]]:
    bmin = bounds["min"]
    bmax = bounds["max"]
    center = [(bmin[index] + bmax[index]) * 0.5 for index in range(3)]
    size = [bmax[index] - bmin[index] for index in range(3)]
    return center, size


def surface_box(name: str, region: dict, y: float, width_scale: float = 1.0) -> dict:
    center, size = center_and_size(region["bounds"])
    return {
        "name": name,
        "type": "floor_box",
        "region": region["id"],
        "center": [round(center[0], 4), round(y, 4), round(center[2], 4)],
        "size": [round(max(0.8, size[0] * width_scale), 4), FLOOR_THICKNESS, round(max(0.8, size[2]), 4)],
        "roles": region.get("roles", []),
    }


def ramp_between(name: str, start: list[float], end: list[float], width: float, role: str) -> dict:
    return {
        "name": name,
        "type": "ramp",
        "start": [round(value, 4) for value in start],
        "end": [round(value, 4) for value in end],
        "width": width,
        "thickness": RAMP_THICKNESS,
        "role": role,
    }


def stair_path(name: str, points: list[list[float]], width: float, role: str) -> dict:
    return {
        "name": name,
        "type": "stair_path",
        "points": [[round(value, 4) for value in point] for point in points],
        "width": width,
        "thickness": RAMP_THICKNESS,
        "role": role,
    }


def generate_surfaces(contract: dict) -> dict:
    regions = {region["id"]: region for region in contract["semantic_regions"]}
    surfaces = []

    for region_id in [
        "engine_room",
        "lower_deck_corridor_spine",
        "atrium_lower",
        "mezzanine",
        "medical",
        "living_quarters",
        "central_service_spine",
        "central_to_cockpit_transition",
        "cockpit_access",
        "cockpit",
    ]:
        region = regions[region_id]
        y = region["bounds"]["min"][1]
        surfaces.append(surface_box(f"{region_id}_floor", region, y))

    for entrance in contract.get("entrance_hatches", []):
        side_sign = -1.0 if entrance["side"] == "port" else 1.0
        cx, cy, cz = entrance["cut_center"]
        exterior = [cx + side_sign * 4.0, entrance["entry_floor_y"] - 0.55, cz]
        threshold = [cx - side_sign * 0.35, entrance["entry_floor_y"], cz]
        interior = [side_sign * 3.5, entrance["entry_floor_y"], cz]
        surfaces.append(ramp_between(f"{entrance['name']}_exterior_ramp", exterior, threshold, ENTRY_RAMP_WIDTH, "entry_ramp"))
        surfaces.append(ramp_between(f"{entrance['name']}_hatch_to_corridor", threshold, interior, ENTRY_RAMP_WIDTH, "entry_hatch_path"))

    for connector in contract.get("vertical_connectors", []):
        surfaces.append(stair_path(connector["name"], connector["points"], connector["surface_width"], "vertical_connector"))

    surfaces.append(
        ramp_between(
            "AftAccessToCentralBodyRamp",
            [0.0, -8.5, -40.0],
            [0.0, -2.0, -28.0],
            CORRIDOR_WIDTH,
            "interstitial_connector",
        )
    )
    surfaces.append(
        ramp_between(
            "CentralToCockpitAccessRamp",
            [0.0, -2.0, 38.0],
            [0.0, -1.5, 45.0],
            CORRIDOR_WIDTH,
            "interstitial_connector",
        )
    )
    surfaces.append(
        stair_path(
            "CockpitAccessDescentStairs",
            [
                [0.0, -1.5, 52.0],
                [-3.2, -3.5, 55.0],
                [3.2, -6.5, 58.5],
                [0.0, -10.5, 62.0],
            ],
            2.2,
            "cockpit_descent",
        )
    )

    route = [
        checkpoint["local_origin"]
        for checkpoint in contract["player_traversal_validation"]["checkpoints"]
    ]

    return {
        "schema_version": 1,
        "ship_id": "cargo_crane",
        "coordinate_space": "ship local",
        "source_contract": str(CONTRACT_PATH.relative_to(ROOT)),
        "surfaces": surfaces,
        "primary_route": [[round(value, 4) for value in point] for point in route],
    }


def point_near_box(point: list[float], surface: dict) -> bool:
    center = surface["center"]
    size = surface["size"]
    return (
        abs(point[0] - center[0]) <= size[0] * 0.5
        and abs(point[1] - center[1]) <= 1.2
        and abs(point[2] - center[2]) <= size[2] * 0.5
    )


def point_near_segment(point: list[float], start: list[float], end: list[float], width: float) -> bool:
    ax, ay, az = start
    bx, by, bz = end
    px, py, pz = point
    ab = [bx - ax, by - ay, bz - az]
    ap = [px - ax, py - ay, pz - az]
    denom = max(0.0001, sum(value * value for value in ab))
    t = max(0.0, min(1.0, sum(ap[index] * ab[index] for index in range(3)) / denom))
    closest = [start[index] + ab[index] * t for index in range(3)]
    horizontal = ((px - closest[0]) ** 2 + (pz - closest[2]) ** 2) ** 0.5
    vertical = abs(py - closest[1])
    return horizontal <= width * 0.65 and vertical <= 1.35


def feature_voxels(voxels: list[list], surfaces: list[dict]) -> list[list]:
    tagged = []
    for voxel in voxels:
        point = voxel[:3]
        tags = []
        for surface in surfaces:
            if surface["type"] == "floor_box" and point_near_box(point, surface):
                tags.append(surface["name"])
            elif surface["type"] == "ramp" and point_near_segment(point, surface["start"], surface["end"], surface["width"]):
                tags.append(surface["name"])
            elif surface["type"] == "stair_path":
                for start, end in zip(surface["points"], surface["points"][1:]):
                    if point_near_segment(point, start, end, surface["width"]):
                        tags.append(surface["name"])
                        break
        if tags:
            tagged.append(voxel + [tags])
    return tagged


def draw_projection(path: Path, voxels: list[list], traversal: dict) -> None:
    canvas = ship_voxels.ImageCanvas(1920, 720, (12, 15, 19))
    panels = [(24, 36, 604, 648, (2, 1)), (658, 36, 604, 648, (2, 0)), (1292, 36, 604, 648, (0, 1))]
    points = [voxel[:3] for voxel in voxels] + traversal["primary_route"]

    for px, py, pw, ph, axes in panels:
        canvas.rect(px, py, px + pw - 1, py + ph - 1, (40, 46, 54))
        coords = [(point[axes[0]], point[axes[1]]) for point in points]
        min_x, max_x = min(c[0] for c in coords) - 3.0, max(c[0] for c in coords) + 3.0
        min_y, max_y = min(c[1] for c in coords) - 3.0, max(c[1] for c in coords) + 3.0

        def map_point(x: float, y: float) -> tuple[int, int]:
            sx = int(px + (x - min_x) / max(0.001, max_x - min_x) * (pw - 1))
            sy = int(py + (1.0 - (y - min_y) / max(0.001, max_y - min_y)) * (ph - 1))
            return sx, sy

        for voxel in voxels:
            if not voxel[3]:
                continue
            sx, sy = map_point(voxel[axes[0]], voxel[axes[1]])
            canvas.rect(sx - 1, sy - 1, sx + 1, sy + 1, (50, 105, 145), fill=True)

        for surface in traversal["surfaces"]:
            color = (245, 205, 80)
            if surface["type"] == "floor_box":
                center = surface["center"]
                size = surface["size"]
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
            elif surface["type"] == "ramp":
                a = surface["start"]
                b = surface["end"]
                x0, y0 = map_point(a[axes[0]], a[axes[1]])
                x1, y1 = map_point(b[axes[0]], b[axes[1]])
                canvas.line(x0, y0, x1, y1, (255, 130, 70))
                canvas.line(x0 + 1, y0, x1 + 1, y1, (255, 130, 70))
            elif surface["type"] == "stair_path":
                mapped = [map_point(point[axes[0]], point[axes[1]]) for point in surface["points"]]
                for a, b in zip(mapped, mapped[1:]):
                    canvas.line(a[0], a[1], b[0], b[1], (120, 245, 210))
                    canvas.line(a[0] + 1, a[1], b[0] + 1, b[1], (120, 245, 210))

        mapped_route = [map_point(point[axes[0]], point[axes[1]]) for point in traversal["primary_route"]]
        for a, b in zip(mapped_route, mapped_route[1:]):
            canvas.line(a[0], a[1], b[0], b[1], (255, 255, 255))
            canvas.line(a[0], a[1] + 1, b[0], b[1] + 1, (255, 255, 255))

    canvas.write_png(path)


def write_outputs(traversal: dict, voxels: list[list]) -> None:
    OUT_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    OUT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    SURFACES_JSON.write_text(json.dumps(traversal, indent=2) + "\n", encoding="utf-8")
    tagged = feature_voxels(voxels, traversal["surfaces"])
    FEATURE_VOXELS_JSON.write_text(json.dumps(tagged, separators=(",", ":")) + "\n", encoding="utf-8")
    draw_projection(PROJECTION_PNG, voxels, traversal)

    surface_counts = {}
    for tagged_voxel in tagged:
        for tag in tagged_voxel[-1]:
            surface_counts[tag] = surface_counts.get(tag, 0) + 1
    uncovered = [surface["name"] for surface in traversal["surfaces"] if surface_counts.get(surface["name"], 0) == 0]
    report = {
        "schema_version": 1,
        "ship_id": "cargo_crane",
        "status": "PASS" if not uncovered else "NEEDS_REVIEW",
        "surface_count": len(traversal["surfaces"]),
        "primary_route_checkpoint_count": len(traversal["primary_route"]),
        "feature_tagged_voxel_count": len(tagged),
        "uncovered_surfaces": uncovered,
        "surface_feature_counts": surface_counts,
        "evidence": {
            "surfaces": str(SURFACES_JSON.relative_to(ROOT)),
            "feature_voxels": str(FEATURE_VOXELS_JSON.relative_to(ROOT)),
            "projection": str(PROJECTION_PNG.relative_to(ROOT)),
        },
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# CargoCrane Traversal Surfaces Report",
        "",
        f"Status: **{report['status']}**",
        "",
        f"- Traversal surfaces: `{len(traversal['surfaces'])}`",
        f"- Primary route checkpoints: `{len(traversal['primary_route'])}`",
        f"- Feature-tagged voxels: `{len(tagged)}`",
        f"- Projection: `{PROJECTION_PNG.relative_to(ROOT)}`",
        f"- Surfaces JSON: `{SURFACES_JSON.relative_to(ROOT)}`",
        "",
        "## Surface Feature Coverage",
        "",
    ]
    for surface in traversal["surfaces"]:
        lines.append(f"- `{surface['name']}` `{surface['type']}` tagged_voxels={surface_counts.get(surface['name'], 0)}")
    if uncovered:
        lines += ["", "## Review Notes", "", "- These surfaces have no nearby standing voxels and need adjustment:"]
        for name in uncovered:
            lines.append(f"  - `{name}`")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    contract = load_json(CONTRACT_PATH)
    voxels = load_json(VOXELS_JSON)
    traversal = generate_surfaces(contract)
    write_outputs(traversal, voxels)
    print(f"Wrote {SURFACES_JSON.relative_to(ROOT)}")
    print(f"Wrote {REPORT_MD.relative_to(ROOT)}")
    print(f"Wrote {PROJECTION_PNG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
