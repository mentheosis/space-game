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
CONTRACT_PATH = ROOT / "assets/source/blender/ships/shuttle_p3/shuttle_p3_interior_layout_contract.json"


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
        "min_headroom": 5.05,
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
        "min_headroom": 4.75,
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
        "max_wall_half_width": 3.18,
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


def build_slice_bounds(z_min: float, z_max: float, target_size: float) -> list[tuple[float, float]]:
    count = max(1, int(math.ceil((z_max - z_min) / target_size)))
    return [
        (
            z_min + (z_max - z_min) * index / count,
            z_min + (z_max - z_min) * (index + 1) / count,
        )
        for index in range(count)
    ]


def smooth_values(values: list[float], max_step: float) -> list[float]:
    if not values:
        return values

    result = values[:]
    for index in range(1, len(result)):
        delta = result[index] - result[index - 1]
        if abs(delta) > max_step:
            result[index] = result[index - 1] + math.copysign(max_step, delta)

    for index in range(len(result) - 2, -1, -1):
        delta = result[index] - result[index + 1]
        if abs(delta) > max_step:
            result[index] = result[index + 1] + math.copysign(max_step, delta)

    return result


STAIR_LEFT_PATH = [
    (-1.95, -2.15, -0.55),
    (-2.22, -1.28, -1.25),
    (-2.30, -0.42, -2.10),
    (-1.85, 0.45, -3.05),
    (-1.15, 0.45, -3.75),
]
STAIR_SURFACE_WIDTH = 1.08
STAIR_WALL_CLEARANCE = 0.24


def load_layout_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


LAYOUT_CONTRACT = load_layout_contract()
GENERATION_CONFIG = LAYOUT_CONTRACT["enclosure_generation"]
ZONES = LAYOUT_CONTRACT["enclosure_zones"]
STAIR_CONTRACT = LAYOUT_CONTRACT["stair_paths"]["cargo_to_cockpit_left"]
STAIR_LEFT_PATH = [tuple(float(value) for value in point) for point in STAIR_CONTRACT["points"]]
STAIR_SURFACE_WIDTH = float(STAIR_CONTRACT["surface_width"])
STAIR_WALL_CLEARANCE = float(STAIR_CONTRACT["wall_clearance"])


def sample_authored_stair_required_half_width(z_min: float, z_max: float) -> float | None:
    samples: list[float] = []
    for start, end in zip(STAIR_LEFT_PATH, STAIR_LEFT_PATH[1:]):
        x0, _y0, z0 = start
        x1, _y1, z1 = end
        low = min(z0, z1)
        high = max(z0, z1)
        if high < z_min or low > z_max:
            continue

        for index in range(8):
            t = index / 7.0
            z = z0 + (z1 - z0) * t
            if z_min - 0.1 <= z <= z_max + 0.1:
                x = x0 + (x1 - x0) * t
                samples.append(abs(x) + STAIR_SURFACE_WIDTH * 0.5 + STAIR_WALL_CLEARANCE)

    return max(samples) if samples else None


def sample_zone_slice(
    zone: dict,
    voxels: list[list[float]],
    z_min: float,
    z_max: float,
) -> dict:
    walk_y_min = zone["walk_y_min"]
    walk_y_max = zone["walk_y_max"]
    route_half_width = zone["route_half_width"]
    slice_voxels = [v for v in voxels if z_min <= v[2] <= z_max]

    ceiling_samples = [
        v[1]
        for v in slice_voxels
        if abs(v[0]) <= route_half_width + 0.65
        and v[1] >= walk_y_max + 1.0
    ]
    sampled_ceiling = percentile(ceiling_samples, zone["ceiling_percentile"])
    ceiling_y = sampled_ceiling if sampled_ceiling is not None else walk_y_max + zone["min_headroom"]
    ceiling_y = clamp(ceiling_y, walk_y_max + zone["min_headroom"], zone["max_ceiling_y"])

    wall_samples = [
        abs(v[0])
        for v in slice_voxels
        if walk_y_min + 0.12 <= v[1] <= ceiling_y - 0.12
    ]
    sampled_half_width = percentile(wall_samples, zone["wall_percentile"])
    if sampled_half_width is None:
        sampled_half_width = zone["route_half_width"] + 0.35

    # The local voxel envelope is the primary source. Min/max only prevent
    # unusably narrow route-adjacent walls or obvious exterior protrusion.
    half_width = sampled_half_width + 0.06
    min_half_width = zone["route_half_width"] + 0.28
    if zone["name"] == "StairTransition":
        z_center = (z_min + z_max) * 0.5
        t = clamp((z_center - zone["z_min"]) / (zone["z_max"] - zone["z_min"]), 0.0, 1.0)
        min_half_width = (zone["route_half_width"] + 0.28) * t + 2.08 * (1.0 - t)
        authored_stair_width = sample_authored_stair_required_half_width(z_min, z_max)
        if authored_stair_width is not None:
            min_half_width = max(min_half_width, authored_stair_width)
    half_width = clamp(half_width, min_half_width, zone["max_wall_half_width"])

    return {
        "voxel_count": len(slice_voxels),
        "sampled_wall_half_width": sampled_half_width,
        "sampled_ceiling_y": sampled_ceiling,
        "wall_half_width": half_width,
        "ceiling_y": ceiling_y,
    }


def wall_bottom_y_for_slice(zone: dict, z_center: float) -> float:
    if zone["name"] != "StairTransition":
        return zone["walk_y_min"] - 0.08

    # The transition runs from the raised cockpit landing at negative z down to
    # the cargo floor at the ramp. Keep the side wall bases near that local
    # walking height instead of making one tall rectangular wall.
    top_z = zone["z_min"]
    lower_z = zone["z_max"]
    t = clamp((z_center - top_z) / (lower_z - top_z), 0.0, 1.0)
    top_y = zone["walk_y_max"] - 0.14
    lower_y = zone["walk_y_min"] - 0.08
    return top_y * (1.0 - t) + lower_y * t


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


def add_stair_transition_bands(
    bands: list[dict],
    report_rows: list[dict],
    voxel_size: float,
    wall_thickness: float,
    ceiling_thickness: float,
) -> None:
    """Use piecewise transition enclosure instead of one oversized wall.

    The ramp/stair/cockpit threshold changes width and height rapidly. A single
    rectangular wall band protrudes outside the ship near the ramp and leaves
    awkward gaps near the top landing, so this zone is intentionally split.
    """

    segments = [
        {
            "name": "StairTransitionLower",
            "z_min": -1.35,
            "z_max": -0.30,
            "wall_half_width": 2.28,
            "wall_bottom_y": -2.12,
            "ceiling_y": 2.55,
            "ceiling_half_width": 2.08,
        },
        {
            "name": "StairTransitionMid",
            "z_min": -2.55,
            "z_max": -1.35,
            "wall_half_width": 2.62,
            "wall_bottom_y": -1.62,
            "ceiling_y": 3.10,
            "ceiling_half_width": 2.42,
        },
        {
            "name": "StairTransitionUpper",
            "z_min": -3.75,
            "z_max": -2.55,
            "wall_half_width": 2.42,
            "wall_bottom_y": -0.28,
            "ceiling_y": 3.18,
            "ceiling_half_width": 2.22,
        },
        {
            "name": "StairTopLandingClosure",
            "z_min": -3.75,
            "z_max": -3.18,
            "wall_half_width": 1.84,
            "wall_bottom_y": 0.28,
            "ceiling_y": 2.92,
            "ceiling_half_width": 1.70,
        },
    ]

    for segment in segments:
        z_min = segment["z_min"]
        z_max = segment["z_max"]
        z_center = (z_min + z_max) * 0.5
        z_size = z_max - z_min
        wall_height = segment["ceiling_y"] - segment["wall_bottom_y"]
        wall_center_y = segment["wall_bottom_y"] + wall_height * 0.5
        source = {
            "zone": "StairTransition",
            "segment": segment["name"],
            "voxel_size": voxel_size,
            "z_min": z_min,
            "z_max": z_max,
            "piecewise": True,
        }

        bands.append(
            box(
                f"{segment['name']}LeftWall",
                "wall",
                (-segment["wall_half_width"], wall_center_y, z_center),
                (wall_thickness, wall_height, z_size),
                source,
            )
        )
        bands.append(
            box(
                f"{segment['name']}RightWall",
                "wall",
                (segment["wall_half_width"], wall_center_y, z_center),
                (wall_thickness, wall_height, z_size),
                source,
            )
        )
        bands.append(
            box(
                f"{segment['name']}Ceiling",
                "ceiling",
                (0.0, segment["ceiling_y"], z_center),
                (max(0.1, segment["ceiling_half_width"] * 2.0 - wall_thickness), ceiling_thickness, z_size),
                source,
            )
        )
        report_rows.append(
            {
                "zone": segment["name"],
                "z_min": z_min,
                "z_max": z_max,
                "voxel_count": 0,
                "wall_half_width": segment["wall_half_width"],
                "ceiling_y": segment["ceiling_y"],
                "wall_height": wall_height,
            }
        )


def generate() -> tuple[dict, list[dict]]:
    raw = json.loads(VOXEL_PATH.read_text())
    voxels = raw["voxels"]
    voxel_size = float(raw["voxel_size"])
    wall_thickness = float(GENERATION_CONFIG["wall_thickness"])
    ceiling_thickness = float(GENERATION_CONFIG["ceiling_thickness"])

    bands: list[dict] = []
    report_rows: list[dict] = []

    for zone in ZONES:
        target_slice_size = (
            float(GENERATION_CONFIG["stair_transition_slice_size"])
            if zone["name"] == "StairTransition"
            else float(GENERATION_CONFIG["default_slice_size"])
        )
        slice_bounds = build_slice_bounds(zone["z_min"], zone["z_max"], target_slice_size)
        slice_samples = [sample_zone_slice(zone, voxels, z0, z1) for z0, z1 in slice_bounds]
        smoothed_widths = smooth_values(
            [sample["wall_half_width"] for sample in slice_samples],
            float(GENERATION_CONFIG["max_wall_width_step"]),
        )
        if zone["name"] == "StairTransition" and smoothed_widths:
            smoothed_widths[0] = min(
                smoothed_widths[0],
                float(GENERATION_CONFIG["stair_transition_initial_wall_half_width"]),
            )
            smoothed_widths = smooth_values(
                smoothed_widths,
                float(GENERATION_CONFIG["stair_transition_max_wall_width_step"]),
            )
        smoothed_ceilings = smooth_values([sample["ceiling_y"] for sample in slice_samples], 0.42)

        for index, ((z_min, z_max), sample, half_width, ceiling_y) in enumerate(
            zip(slice_bounds, slice_samples, smoothed_widths, smoothed_ceilings)
        ):
            z_center = (z_min + z_max) * 0.5
            # Slightly overlap adjacent slices so renderer/collision precision
            # cannot expose pinholes between generated wall panels.
            z_size = (z_max - z_min) + 0.04
            wall_bottom_y = wall_bottom_y_for_slice(zone, z_center)
            wall_height = max(0.8, ceiling_y - wall_bottom_y)
            wall_center_y = wall_bottom_y + wall_height * 0.5
            wall_size = (wall_thickness, wall_height, z_size)

            source = {
                "zone": zone["name"],
                "slice": index,
                "slice_count": len(slice_bounds),
                "voxel_count": sample["voxel_count"],
                "voxel_size": voxel_size,
                "sampled_wall_half_width": None
                if sample["sampled_wall_half_width"] is None
                else round(sample["sampled_wall_half_width"], 4),
                "sampled_ceiling_y": None
                if sample["sampled_ceiling_y"] is None
                else round(sample["sampled_ceiling_y"], 4),
                "route_half_width": zone["route_half_width"],
                "z_min": z_min,
                "z_max": z_max,
                "sliced": True,
            }

            slice_name = f"{zone['name']}Slice{index:02d}"
            bands.append(
                box(
                    f"{slice_name}LeftWall",
                    "wall",
                    (-half_width, wall_center_y, z_center),
                    wall_size,
                    source,
                )
            )
            bands.append(
                box(
                    f"{slice_name}RightWall",
                    "wall",
                    (half_width, wall_center_y, z_center),
                    wall_size,
                    source,
                )
            )
            bands.append(
                box(
                    f"{slice_name}Ceiling",
                    "ceiling",
                    (0.0, ceiling_y, z_center),
                    (max(0.1, half_width * 2.0 - wall_thickness), ceiling_thickness, z_size),
                    source,
                )
            )

            report_rows.append(
                {
                    "zone": slice_name,
                    "z_min": z_min,
                    "z_max": z_max,
                    "voxel_count": sample["voxel_count"],
                    "wall_half_width": half_width,
                    "ceiling_y": ceiling_y,
                    "wall_height": wall_height,
                }
            )

    # Close the aft end of the cargo volume; this is derived from the final
    # cargo z boundary and generated wall width rather than authored in Godot.
    cargo_main = max(
        (row for row in report_rows if row["zone"].startswith("CargoMainSlice")),
        key=lambda row: row["z_max"],
    )
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
        "source_layout_contract": str(CONTRACT_PATH.relative_to(ROOT)),
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
