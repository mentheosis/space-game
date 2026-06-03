#!/usr/bin/env python3
"""Discover CargoCrane walkable surface candidates from objective interior voxels."""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import build_shuttle_p3_from_exterior_glb as ship_voxels


ROOT = Path(__file__).resolve().parents[2]
OUT_MODEL_DIR = ROOT / "assets/models/ship/cargo_crane"
OUT_REPORT_DIR = ROOT / "reports/ship_pipeline/cargo_crane_voxel_fit"
VOXELS_JSON = OUT_REPORT_DIR / "cargo_crane_objective_interior_voxels_compact.json"
SURFACES_JSON = OUT_MODEL_DIR / "cargo_crane_objective_walkable_surfaces.json"
REPORT_JSON = OUT_REPORT_DIR / "cargo_crane_objective_walkable_surfaces_report.json"
REPORT_MD = OUT_REPORT_DIR / "cargo_crane_objective_walkable_surfaces_report.md"
PROJECTION_PNG = OUT_REPORT_DIR / "cargo_crane_objective_walkable_surfaces_projection_current.png"

VOXEL_SIZE = 1.0
MIN_COMPONENT_STANDING_VOXELS = 20
MIN_PATCH_VOXELS = 8
MAX_CENTERLINE_X = 12.0
FLOOR_THICKNESS = 0.22


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


def bounds_for(voxels: list[dict]) -> dict:
    return {
        "min": [round(min(voxel["center"][axis] for voxel in voxels), 4) for axis in range(3)],
        "max": [round(max(voxel["center"][axis] for voxel in voxels), 4) for axis in range(3)],
    }


def discover_components(voxels: list[dict]) -> list[dict]:
    standing = [voxel for voxel in voxels if voxel["can_stand"]]
    by_key = {key_for(voxel["center"]): voxel for voxel in standing}
    seen = set()
    components = []
    for key in sorted(by_key):
        if key in seen:
            continue
        queue = deque([key])
        seen.add(key)
        items = []
        while queue:
            current = queue.popleft()
            items.append(by_key[current])
            x, y, z = current
            for neighbor in (
                (x + 1, y, z),
                (x - 1, y, z),
                (x, y + 1, z),
                (x, y - 1, z),
                (x, y, z + 1),
                (x, y, z - 1),
            ):
                if neighbor in by_key and neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        if len(items) < MIN_COMPONENT_STANDING_VOXELS:
            continue
        bounds = bounds_for(items)
        center_x = (bounds["min"][0] + bounds["max"][0]) * 0.5
        x_span = bounds["max"][0] - bounds["min"][0]
        centered = abs(center_x) <= MAX_CENTERLINE_X and bounds["min"][0] >= -MAX_CENTERLINE_X and bounds["max"][0] <= MAX_CENTERLINE_X
        classification = "centerline_interior_candidate" if centered else "side_engine_exterior_candidate"
        components.append(
            {
                "standing_voxel_count": len(items),
                "bounds": bounds,
                "center_x": round(center_x, 4),
                "x_span": round(x_span, 4),
                "classification": classification,
                "voxels": items,
            }
        )
    components.sort(key=lambda component: component["standing_voxel_count"], reverse=True)
    for index, component in enumerate(components, 1):
        component["id"] = index
    return components


def discover_patches_for_component(component: dict) -> list[dict]:
    bottom_by_xz: dict[tuple[int, int], dict] = {}
    for voxel in component["voxels"]:
        x, y, z = key_for(voxel["center"])
        existing = bottom_by_xz.get((x, z))
        if existing is None or y < key_for(existing["center"])[1]:
            bottom_by_xz[(x, z)] = voxel

    by_y: dict[int, dict[tuple[int, int], dict]] = {}
    for voxel in bottom_by_xz.values():
        x, y, z = key_for(voxel["center"])
        by_y.setdefault(y, {})[(x, z)] = voxel

    patches = []
    for y_key, plane in sorted(by_y.items()):
        seen = set()
        for key in sorted(plane):
            if key in seen:
                continue
            queue = deque([key])
            seen.add(key)
            items = []
            while queue:
                current = queue.popleft()
                items.append(plane[current])
                x, z = current
                for neighbor in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
                    if neighbor in plane and neighbor not in seen:
                        seen.add(neighbor)
                        queue.append(neighbor)
            if len(items) < MIN_PATCH_VOXELS:
                continue
            bounds = bounds_for(items)
            center = [(bounds["min"][axis] + bounds["max"][axis]) * 0.5 for axis in range(3)]
            size = [
                bounds["max"][0] - bounds["min"][0] + VOXEL_SIZE,
                FLOOR_THICKNESS,
                bounds["max"][2] - bounds["min"][2] + VOXEL_SIZE,
            ]
            patches.append(
                {
                    "component_id": component["id"],
                    "voxel_count": len(items),
                    "bounds": bounds,
                    "center": [round(center[0], 4), round(float(y_key) * VOXEL_SIZE, 4), round(center[2], 4)],
                    "size": [round(size[0], 4), FLOOR_THICKNESS, round(size[2], 4)],
                }
            )
    patches.sort(key=lambda patch: patch["voxel_count"], reverse=True)
    return patches


def draw_projection(path: Path, voxels: list[dict], surfaces: list[dict], components: list[dict]) -> None:
    canvas = ship_voxels.ImageCanvas(1920, 720, (12, 15, 19))
    panels = [(24, 36, 604, 648, (2, 1)), (658, 36, 604, 648, (2, 0)), (1292, 36, 604, 648, (0, 1))]
    component_by_key = {}
    for component in components:
        for voxel in component["voxels"]:
            component_by_key[key_for(voxel["center"])] = component
    points = [voxel["center"] for voxel in voxels if voxel["can_stand"]]

    colors = {
        "centerline_interior_candidate": (70, 160, 220),
        "side_engine_exterior_candidate": (220, 80, 80),
    }
    surface_color = (245, 205, 80)

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
            if not voxel["can_stand"]:
                continue
            component = component_by_key.get(key_for(voxel["center"]))
            color = colors.get(component["classification"], (120, 120, 130)) if component else (80, 85, 95)
            sx, sy = map_point(voxel["center"][axes[0]], voxel["center"][axes[1]])
            canvas.rect(sx - 1, sy - 1, sx + 1, sy + 1, color, fill=True)

        for surface in surfaces:
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
                canvas.line(start[0], start[1], end[0], end[1], surface_color)
                canvas.line(start[0] + 1, start[1], end[0] + 1, end[1], surface_color)

    canvas.write_png(path)


def main() -> int:
    voxels = load_voxels()
    components = discover_components(voxels)
    surfaces = []
    for component in components:
        if component["classification"] != "centerline_interior_candidate":
            continue
        for patch_index, patch in enumerate(discover_patches_for_component(component), 1):
            surfaces.append(
                {
                    "name": f"component_{component['id']:02d}_walkable_patch_{patch_index:02d}",
                    "type": "objective_floor_patch",
                    "component_id": component["id"],
                    "center": patch["center"],
                    "size": patch["size"],
                    "source_bounds": patch["bounds"],
                    "source_voxel_count": patch["voxel_count"],
                    "roles": ["walkable_surface_candidate"],
                }
            )

    traversal = {
        "schema_version": 1,
        "ship_id": "cargo_crane",
        "coordinate_space": "ship local",
        "source_voxels": str(VOXELS_JSON.relative_to(ROOT)),
        "method": "standing_voxel_connected_floor_patches",
        "surfaces": surfaces,
    }

    OUT_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    OUT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    SURFACES_JSON.write_text(json.dumps(traversal, indent=2) + "\n", encoding="utf-8")
    draw_projection(PROJECTION_PNG, voxels, surfaces, components)

    public_components = [
        {key: value for key, value in component.items() if key != "voxels"}
        for component in components
    ]
    report = {
        "schema_version": 1,
        "ship_id": "cargo_crane",
        "status": "REVIEW",
        "method": traversal["method"],
        "standing_component_count": len(components),
        "surface_count": len(surfaces),
        "centerline_surface_count": len(surfaces),
        "components": public_components,
        "evidence": {
            "surfaces": str(SURFACES_JSON.relative_to(ROOT)),
            "projection": str(PROJECTION_PNG.relative_to(ROOT)),
        },
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# CargoCrane Objective Walkable Surfaces Report",
        "",
        "Status: **REVIEW**",
        "",
        f"- Method: `{traversal['method']}`",
        f"- Candidate surfaces: `{len(surfaces)}`",
        f"- Standing components: `{len(components)}`",
        f"- Projection: `{PROJECTION_PNG.relative_to(ROOT)}`",
        f"- Surfaces JSON: `{SURFACES_JSON.relative_to(ROOT)}`",
        "",
        "## Color Key",
        "",
        "- Blue: centerline interior candidate voxels used for walkable surface discovery.",
        "- Red: side-engine exterior candidate voxels excluded from surface generation.",
        "- Yellow outline: discovered candidate floor patch.",
        "",
        "## Components",
        "",
    ]
    for component in public_components:
        lines.append(
            f"- `{component['id']}` {component['classification']} standing={component['standing_voxel_count']} bounds={component['bounds']}"
        )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {SURFACES_JSON.relative_to(ROOT)}")
    print(f"Wrote {REPORT_MD.relative_to(ROOT)}")
    print(f"Wrote {PROJECTION_PNG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
