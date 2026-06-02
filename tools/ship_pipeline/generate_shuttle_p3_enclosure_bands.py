#!/usr/bin/env python3
"""Generate repeatable Shuttle P3 interior enclosure bands from voxel bounds.

The playable route is still a design contract, but wall and ceiling placement is
derived from the voxelized interior envelope around that route instead of being
hand-entered in the Godot debug loader.
"""

from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VOXEL_PATH = ROOT / "reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_voxels_full_compact.json"
OUTPUT_PATH = ROOT / "assets/models/ship/shuttle_p3/shuttle_p3_enclosure_bands.json"
REPORT_PATH = ROOT / "reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_enclosure_bands_report.md"


ZONES = [
    {
        "name": "CargoForward",
        "z_min": -0.30,
        "z_max": 1.20,
        "walk_y_min": -2.24,
        "walk_y_max": -2.24,
        "route_half_width": 2.50,
        "min_wall_half_width": 2.55,
        "max_wall_half_width": 2.80,
        "wall_percentile": 90,
        "ceiling_percentile": 72,
        "min_headroom": 2.45,
        "max_ceiling_y": 2.95,
    },
    {
        "name": "CargoMain",
        "z_min": 1.20,
        "z_max": 7.70,
        "walk_y_min": -2.24,
        "walk_y_max": -2.24,
        "route_half_width": 2.80,
        "min_wall_half_width": 2.90,
        "max_wall_half_width": 3.15,
        "wall_percentile": 91,
        "ceiling_percentile": 80,
        "min_headroom": 2.45,
        "max_ceiling_y": 3.05,
    },
    {
        "name": "StairTransition",
        "z_min": -3.75,
        "z_max": -0.30,
        "walk_y_min": -2.15,
        "walk_y_max": 0.45,
        "route_half_width": 2.35,
        "min_wall_half_width": 2.62,
        "max_wall_half_width": 2.95,
        "wall_percentile": 92,
        "ceiling_percentile": 92,
        "min_headroom": 2.55,
        "max_ceiling_y": 3.35,
    },
    {
        "name": "CockpitHall",
        "z_min": -10.20,
        "z_max": -3.75,
        "walk_y_min": 0.36,
        "walk_y_max": 0.45,
        "route_half_width": 1.625,
        "min_wall_half_width": 1.72,
        "max_wall_half_width": 2.05,
        "wall_percentile": 92,
        "ceiling_percentile": 90,
        "min_headroom": 2.45,
        "max_ceiling_y": 3.25,
    },
    {
        "name": "CockpitRear",
        "z_min": -13.20,
        "z_max": -10.20,
        "walk_y_min": 0.36,
        "walk_y_max": 0.45,
        "route_half_width": 1.75,
        "min_wall_half_width": 1.75,
        "max_wall_half_width": 1.95,
        "wall_percentile": 95,
        "ceiling_percentile": 88,
        "min_headroom": 2.55,
        "max_ceiling_y": 3.35,
    },
    {
        "name": "CockpitForward",
        "z_min": -16.65,
        "z_max": -13.20,
        "walk_y_min": 0.02,
        "walk_y_max": 0.45,
        "route_half_width": 1.25,
        "min_wall_half_width": 1.28,
        "max_wall_half_width": 1.65,
        "wall_percentile": 95,
        "ceiling_percentile": 88,
        "min_headroom": 2.35,
        "max_ceiling_y": 3.05,
    },
]


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * (p / 100.0)
    low = math.floor(index)
    high = math.ceil(index)
    if low == high:
        return ordered[low]
    return ordered[low] * (high - index) + ordered[high] * (index - low)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def box(name: str, kind: str, center: tuple[float, float, float], size: tuple[float, float, float], source: dict) -> dict:
    return {
        "name": name,
        "kind": kind,
        "center": [round(v, 4) for v in center],
        "size": [round(v, 4) for v in size],
        "source": source,
    }


def generate() -> tuple[dict, list[dict]]:
    raw = json.loads(VOXEL_PATH.read_text())
    voxels = raw["voxels"]
    voxel_size = float(raw["voxel_size"])
    wall_thickness = 0.16
    ceiling_thickness = 0.16

    bands: list[dict] = []
    report_rows: list[dict] = []

    for zone in ZONES:
        z_min = zone["z_min"]
        z_max = zone["z_max"]
        z_center = (z_min + z_max) * 0.5
        z_size = z_max - z_min
        walk_y_min = zone["walk_y_min"]
        walk_y_max = zone["walk_y_max"]
        route_half_width = zone["route_half_width"]

        zone_voxels = [v for v in voxels if z_min <= v[2] <= z_max]
        ceiling_samples = [
            v[1]
            for v in zone_voxels
            if abs(v[0]) <= route_half_width + 0.45 and v[1] >= walk_y_max + 1.15
        ]
        sampled_ceiling = percentile(ceiling_samples, zone["ceiling_percentile"])
        ceiling_y = sampled_ceiling if sampled_ceiling is not None else walk_y_max + zone["min_headroom"]
        ceiling_y = clamp(
            ceiling_y,
            walk_y_max + zone["min_headroom"],
            zone["max_ceiling_y"],
        )

        wall_samples = [
            abs(v[0])
            for v in zone_voxels
            if walk_y_min + 0.2 <= v[1] <= ceiling_y - 0.15
        ]
        sampled_half_width = percentile(wall_samples, zone["wall_percentile"])
        half_width = sampled_half_width if sampled_half_width is not None else zone["min_wall_half_width"]
        half_width = clamp(half_width, zone["min_wall_half_width"], zone["max_wall_half_width"])

        wall_bottom_y = walk_y_min - 0.08
        wall_height = max(0.8, ceiling_y - wall_bottom_y)
        wall_center_y = wall_bottom_y + wall_height * 0.5
        wall_size = (wall_thickness, wall_height, z_size)

        source = {
            "zone": zone["name"],
            "voxel_count": len(zone_voxels),
            "voxel_size": voxel_size,
            "sampled_wall_half_width": None if sampled_half_width is None else round(sampled_half_width, 4),
            "sampled_ceiling_y": None if sampled_ceiling is None else round(sampled_ceiling, 4),
            "route_half_width": route_half_width,
            "z_min": z_min,
            "z_max": z_max,
        }

        bands.append(
            box(
                f"{zone['name']}LeftWall",
                "wall",
                (-half_width, wall_center_y, z_center),
                wall_size,
                source,
            )
        )
        bands.append(
            box(
                f"{zone['name']}RightWall",
                "wall",
                (half_width, wall_center_y, z_center),
                wall_size,
                source,
            )
        )
        bands.append(
            box(
                f"{zone['name']}Ceiling",
                "ceiling",
                (0.0, ceiling_y, z_center),
                (max(0.1, half_width * 2.0 - wall_thickness), ceiling_thickness, z_size),
                source,
            )
        )

        report_rows.append(
            {
                "zone": zone["name"],
                "z_min": z_min,
                "z_max": z_max,
                "voxel_count": len(zone_voxels),
                "wall_half_width": half_width,
                "ceiling_y": ceiling_y,
                "wall_height": wall_height,
            }
        )

    # Close the aft end of the cargo volume; this is derived from the final
    # cargo z boundary and generated wall width rather than authored in Godot.
    cargo_main = next(row for row in report_rows if row["zone"] == "CargoMain")
    cargo_ceiling = cargo_main["ceiling_y"]
    cargo_wall_bottom = next(zone for zone in ZONES if zone["name"] == "CargoMain")["walk_y_min"] - 0.08
    aft_height = cargo_ceiling - cargo_wall_bottom
    aft_center_y = cargo_wall_bottom + aft_height * 0.5
    bands.append(
        box(
            "CargoAftWall",
            "wall",
            (0.0, aft_center_y, cargo_main["z_max"]),
            (cargo_main["wall_half_width"] * 2.0 - wall_thickness, aft_height, wall_thickness),
            {"zone": "CargoMain", "derived_from": "aft z boundary"},
        )
    )

    data = {
        "schema_version": 1,
        "ship_id": "shuttle_p3",
        "generator": "tools/ship_pipeline/generate_shuttle_p3_enclosure_bands.py",
        "source_voxel_file": str(VOXEL_PATH.relative_to(ROOT)),
        "coordinate_space": "ship local",
        "band_count": len(bands),
        "bands": bands,
    }
    return data, report_rows


def write_report(rows: list[dict], data: dict) -> None:
    lines = [
        "# Shuttle P3 Generated Enclosure Bands",
        "",
        "Generated from voxel slice bounds around the approved playable route zones.",
        "",
        f"- Output data: `{OUTPUT_PATH.relative_to(ROOT)}`",
        f"- Band count: `{data['band_count']}`",
        "",
        "| Zone | Z Min | Z Max | Voxels | Wall Half Width | Ceiling Y | Wall Height |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['zone']} | {row['z_min']:.2f} | {row['z_max']:.2f} | {row['voxel_count']} | "
            f"{row['wall_half_width']:.2f} | {row['ceiling_y']:.2f} | {row['wall_height']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Loader Contract",
            "",
            "Godot should consume `bands[]` directly. Each band is an axis-aligned box in ship-local coordinates.",
            "The generator owns wall and ceiling placement; the runtime loader should not hand-author these values.",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines))


def main() -> None:
    data, rows = generate()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, indent=2) + "\n")
    write_report(rows, data)
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)}")
    print(f"Wrote {REPORT_PATH.relative_to(ROOT)}")
    print(f"Generated {data['band_count']} enclosure bands")


if __name__ == "__main__":
    main()
