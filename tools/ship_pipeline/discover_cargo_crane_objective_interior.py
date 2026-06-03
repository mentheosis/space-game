#!/usr/bin/env python3
"""Discover CargoCrane interior voxels by slice flood-fill instead of hand envelopes."""

from __future__ import annotations

import json
import math
from collections import defaultdict, deque
from pathlib import Path

import build_cargo_crane_voxel_fit as cargo_fit
import build_shuttle_p3_from_exterior_glb as ship_voxels


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "assets/source/blender/ships/cargo_crane/cargo_crane_interior_layout_contract.json"
OUT_REPORT_DIR = ROOT / "reports/ship_pipeline/cargo_crane_voxel_fit"
REPORT_JSON = OUT_REPORT_DIR / "cargo_crane_objective_interior_report.json"
REPORT_MD = OUT_REPORT_DIR / "cargo_crane_objective_interior_report.md"
VOXELS_JSON = OUT_REPORT_DIR / "cargo_crane_objective_interior_voxels_compact.json"
PROJECTION_PNG = OUT_REPORT_DIR / "cargo_crane_objective_interior_projection_current.png"


def load_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def component_summary(voxels: list[dict], voxel_size: float) -> list[dict]:
    standing = [voxel for voxel in voxels if voxel["can_stand"]]
    by_key = {
        tuple(int(round(value / voxel_size)) for value in voxel["center"]): voxel
        for voxel in standing
    }
    seen = set()
    components = []
    for key in list(by_key):
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
        mins = [min(voxel["center"][axis] for voxel in items) for axis in range(3)]
        maxs = [max(voxel["center"][axis] for voxel in items) for axis in range(3)]
        components.append(
            {
                "standing_voxel_count": len(items),
                "bounds": {
                    "min": [round(value, 4) for value in mins],
                    "max": [round(value, 4) for value in maxs],
                },
            }
        )
    return sorted(components, key=lambda item: item["standing_voxel_count"], reverse=True)


def discover_slice_interior(
    samples: list[tuple[float, float, float]],
    z_center: float,
    exterior_bounds: dict,
    voxel_size: float,
    standing_height: float,
) -> list[dict]:
    z_half = voxel_size * 0.55
    slice_points = [point for point in samples if abs(point[2] - z_center) <= z_half]
    if len(slice_points) < 24:
        return []

    x_min = math.floor((exterior_bounds["min"][0] - 2.0) / voxel_size) * voxel_size
    x_max = math.ceil((exterior_bounds["max"][0] + 2.0) / voxel_size) * voxel_size
    y_min = math.floor((exterior_bounds["min"][1] - 2.0) / voxel_size) * voxel_size
    y_max = math.ceil((exterior_bounds["max"][1] + 2.0) / voxel_size) * voxel_size
    x_count = int(round((x_max - x_min) / voxel_size)) + 1
    y_count = int(round((y_max - y_min) / voxel_size)) + 1

    shell: set[tuple[int, int]] = set()
    for x, y, _ in slice_points:
        ix = int(round((x - x_min) / voxel_size))
        iy = int(round((y - y_min) / voxel_size))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = ix + dx, iy + dy
                if 0 <= nx < x_count and 0 <= ny < y_count:
                    shell.add((nx, ny))

    outside: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()
    for ix in range(x_count):
        for iy in (0, y_count - 1):
            if (ix, iy) not in shell and (ix, iy) not in outside:
                outside.add((ix, iy))
                queue.append((ix, iy))
    for iy in range(y_count):
        for ix in (0, x_count - 1):
            if (ix, iy) not in shell and (ix, iy) not in outside:
                outside.add((ix, iy))
                queue.append((ix, iy))

    while queue:
        ix, iy = queue.popleft()
        for nx, ny in ((ix + 1, iy), (ix - 1, iy), (ix, iy + 1), (ix, iy - 1)):
            if 0 <= nx < x_count and 0 <= ny < y_count and (nx, ny) not in shell and (nx, ny) not in outside:
                outside.add((nx, ny))
                queue.append((nx, ny))

    interior = {
        (ix, iy)
        for ix in range(x_count)
        for iy in range(y_count)
        if (ix, iy) not in shell and (ix, iy) not in outside
    }
    voxels = []
    for ix, iy in sorted(interior):
        top_iy = iy
        while (ix, top_iy + 1) in interior:
            top_iy += 1
        y = y_min + iy * voxel_size
        top_y = y_min + top_iy * voxel_size
        head_clearance = top_y - y
        voxels.append(
            {
                "center": [round(x_min + ix * voxel_size, 5), round(y, 5), round(z_center, 5)],
                "can_stand": head_clearance >= standing_height,
                "head_clearance": round(head_clearance, 5),
            }
        )
    return voxels


def main() -> int:
    contract = load_contract()
    source_glb = ROOT / contract["source_assets"]["exterior_glb"]
    gltf, bin_chunk = ship_voxels.read_glb(source_glb)
    exterior_points = ship_voxels.collect_vertices(gltf, bin_chunk)
    exterior_bounds = ship_voxels.bounds(exterior_points)
    voxel_size = float(contract["voxelization"]["voxel_size"])
    standing_height = float(contract["player_capsule"]["height"])
    samples = cargo_fit.collect_surface_samples(gltf, bin_chunk, voxel_size)

    z_start = math.floor(exterior_bounds["min"][2] / voxel_size) * voxel_size
    z_end = math.ceil(exterior_bounds["max"][2] / voxel_size) * voxel_size
    z_values = [z_start + index * voxel_size for index in range(int(round((z_end - z_start) / voxel_size)) + 1)]
    voxels: list[dict] = []
    for z_center in z_values:
        voxels.extend(discover_slice_interior(samples, z_center, exterior_bounds, voxel_size, standing_height))

    components = component_summary(voxels, voxel_size)
    OUT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    VOXELS_JSON.write_text(
        json.dumps([[*voxel["center"], voxel["can_stand"], voxel["head_clearance"]] for voxel in voxels], separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    cargo_fit.draw_projection(PROJECTION_PNG, exterior_points, voxels, [], semantic=False)
    report = {
        "schema_version": 1,
        "ship_id": "cargo_crane",
        "method": "slice_surface_raster_flood_fill",
        "voxel_size": voxel_size,
        "surface_sample_count": len(samples),
        "voxel_count": len(voxels),
        "standing_voxel_count": sum(1 for voxel in voxels if voxel["can_stand"]),
        "component_count": len(components),
        "components": components,
        "evidence": {
            "projection": str(PROJECTION_PNG.relative_to(ROOT)),
            "voxels": str(VOXELS_JSON.relative_to(ROOT)),
        },
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# CargoCrane Objective Interior Report",
        "",
        f"Method: `{report['method']}`",
        f"- Voxels: `{report['voxel_count']}`",
        f"- Standing voxels: `{report['standing_voxel_count']}`",
        f"- Components: `{report['component_count']}`",
        f"- Projection: `{PROJECTION_PNG.relative_to(ROOT)}`",
        "",
        "## Components",
        "",
    ]
    for index, component in enumerate(components[:12], 1):
        lines.append(f"- `{index}` standing={component['standing_voxel_count']} bounds={component['bounds']}")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT_JSON.relative_to(ROOT)}")
    print(f"Wrote {REPORT_MD.relative_to(ROOT)}")
    print(f"Wrote {PROJECTION_PNG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
