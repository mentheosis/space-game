#!/usr/bin/env python3
"""Generate CargoCrane enclosure wall and ceiling bands from the layout contract."""

from __future__ import annotations

import json
import math
from pathlib import Path

import build_shuttle_p3_from_exterior_glb as ship_voxels


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "assets/source/blender/ships/cargo_crane/cargo_crane_interior_layout_contract.json"
VOXELS_PATH = ROOT / "reports/ship_pipeline/cargo_crane_voxel_fit/cargo_crane_voxels_full_compact.json"
OUT_PATH = ROOT / "assets/models/ship/cargo_crane/cargo_crane_enclosure_bands.json"
REPORT_JSON = ROOT / "reports/ship_pipeline/cargo_crane_voxel_fit/cargo_crane_enclosure_bands_report.json"
REPORT_MD = ROOT / "reports/ship_pipeline/cargo_crane_voxel_fit/cargo_crane_enclosure_bands_report.md"
CEILING_FIT_PNG = ROOT / "reports/ship_pipeline/cargo_crane_voxel_fit/cargo_crane_voxel_ceiling_fit_current.png"
AFT_TO_CENTRAL_RAMP_HALF_WIDTH = 6.3
AFT_TO_CENTRAL_RAMP_CAP_OPENING_HALF_WIDTH = 5.85


def load_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def load_compact_voxels() -> list[tuple[float, float, float, bool, float]]:
    raw = json.loads(VOXELS_PATH.read_text(encoding="utf-8"))
    return [(float(v[0]), float(v[1]), float(v[2]), bool(v[3]), float(v[4])) for v in raw]


def make_band(
    region: dict,
    name: str,
    band_type: str,
    center: list[float],
    size: list[float],
    rotation_degrees: list[float] | None = None,
) -> dict:
    band = {
        "name": name,
        "type": band_type,
        "region": region["id"],
        "center": [round(value, 4) for value in center],
        "size": [round(value, 4) for value in size],
    }
    if rotation_degrees is not None:
        band["rotation_degrees"] = [round(value, 4) for value in rotation_degrees]
    return band


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


def smooth_limited(values: list[float], max_step: float) -> list[float]:
    if len(values) < 2:
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


def add_end_wall_band(
    bands: list[dict],
    region: dict,
    name: str,
    z: float,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    thickness: float,
) -> None:
    x_min -= 0.2
    x_max += 0.2
    if x_max - x_min < 0.4 or y_max - y_min < 0.4:
        return
    bands.append(
        make_band(
            region,
            name,
            "end_wall",
            [(x_min + x_max) * 0.5, (y_min + y_max) * 0.5, z],
            [x_max - x_min, y_max - y_min, thickness],
        )
    )


def add_floorplan_end_caps(bands: list[dict], region: dict, thickness: float) -> None:
    region_id = region["id"]
    bounds = region["bounds"]
    bmin = bounds["min"]
    bmax = bounds["max"]

    if region_id == "aft_center_service":
        forward_floor_z = -37.5 + thickness * 0.5
        ramp_min_x = -AFT_TO_CENTRAL_RAMP_CAP_OPENING_HALF_WIDTH
        ramp_max_x = AFT_TO_CENTRAL_RAMP_CAP_OPENING_HALF_WIDTH
        add_end_wall_band(
            bands,
            region,
            f"{region_id}_aft_end_wall",
            bmin[2] - thickness * 0.5,
            bmin[0],
            bmax[0],
            bmin[1],
            bmax[1],
            thickness,
        )
        # Close the engine room forward face around the central ramp opening.
        add_end_wall_band(
            bands,
            region,
            f"{region_id}_forward_port_end_wall",
            forward_floor_z,
            bmin[0],
            ramp_min_x,
            bmin[1],
            bmax[1],
            thickness,
        )
        add_end_wall_band(
            bands,
            region,
            f"{region_id}_forward_starboard_end_wall",
            forward_floor_z,
            ramp_max_x,
            bmax[0],
            bmin[1],
            bmax[1],
            thickness,
        )
        add_end_wall_band(
            bands,
            region,
            f"{region_id}_forward_upper_end_wall",
            forward_floor_z,
            ramp_min_x,
            ramp_max_x,
            -1.4,
            bmax[1],
            thickness,
        )
    elif region_id == "central_body_lower":
        aft_floor_z = -28.5 - thickness * 0.5
        ramp_min_x = -AFT_TO_CENTRAL_RAMP_CAP_OPENING_HALF_WIDTH
        ramp_max_x = AFT_TO_CENTRAL_RAMP_CAP_OPENING_HALF_WIDTH
        add_end_wall_band(
            bands,
            region,
            f"{region_id}_aft_port_end_wall",
            aft_floor_z,
            bmin[0],
            ramp_min_x,
            bmin[1],
            bmax[1],
            thickness,
        )
        add_end_wall_band(
            bands,
            region,
            f"{region_id}_aft_starboard_end_wall",
            aft_floor_z,
            ramp_max_x,
            bmax[0],
            bmin[1],
            bmax[1],
            thickness,
        )
        add_end_wall_band(
            bands,
            region,
            f"{region_id}_aft_upper_end_wall",
            aft_floor_z,
            ramp_min_x,
            ramp_max_x,
            1.2,
            bmax[1],
            thickness,
        )
        # Close the broad main body forward face around the narrow cockpit hallway.
        add_end_wall_band(
            bands,
            region,
            f"{region_id}_forward_port_end_wall",
            bmax[2] + thickness * 0.5,
            bmin[0],
            -3.5,
            bmin[1],
            bmax[1],
            thickness,
        )
        add_end_wall_band(
            bands,
            region,
            f"{region_id}_forward_starboard_end_wall",
            bmax[2] + thickness * 0.5,
            3.5,
            bmax[0],
            bmin[1],
            bmax[1],
            thickness,
        )
        add_end_wall_band(
            bands,
            region,
            f"{region_id}_forward_upper_end_wall",
            bmax[2] + thickness * 0.5,
            -3.5,
            3.5,
            5.5,
            bmax[1],
            thickness,
        )
    elif region_id == "cockpit_lower":
        upper_floor_y = -1.0
        upper_floor_z = 60.8
        lower_floor_y = bmin[1]
        lower_floor_aft_z = bmin[2] - thickness * 0.45
        bulkhead_dy = upper_floor_y - lower_floor_y
        bulkhead_dz = lower_floor_aft_z - upper_floor_z
        bulkhead_length = math.sqrt(bulkhead_dy * bulkhead_dy + bulkhead_dz * bulkhead_dz)
        bulkhead_pitch = math.degrees(math.atan2(abs(bulkhead_dy), abs(bulkhead_dz)))
        bands.append(
            make_band(
                region,
                f"{region_id}_sloped_aft_bulkhead",
                "end_wall",
                [
                    (bmin[0] + bmax[0]) * 0.5,
                    (upper_floor_y + lower_floor_y) * 0.5,
                    (upper_floor_z + lower_floor_aft_z) * 0.5,
                ],
                [bmax[0] - bmin[0] + 0.8, thickness, bulkhead_length],
                [bulkhead_pitch, 0.0, 0.0],
            )
        )
        add_end_wall_band(
            bands,
            region,
            f"{region_id}_forward_end_wall",
            bmax[2] + thickness * 0.5,
            bmin[0],
            bmax[0],
            bmin[1],
            bmax[1],
            thickness,
        )
    elif region_id == "cockpit_upper_command_gallery":
        add_end_wall_band(
            bands,
            region,
            f"{region_id}_forward_end_wall",
            bmax[2] + thickness * 0.5,
            bmin[0],
            bmax[0],
            bmin[1],
            bmax[1],
            thickness,
        )


def split_z_segments(z_min: float, z_max: float, openings: list[dict]) -> list[tuple[float, float]]:
    segments = [(z_min, z_max)]
    for opening in openings:
        center_z = float(opening["center_z"])
        half_width = float(opening["width_z"]) * 0.5
        gap_min = center_z - half_width
        gap_max = center_z + half_width
        next_segments = []
        for start, end in segments:
            if gap_max <= start or gap_min >= end:
                next_segments.append((start, end))
                continue
            if gap_min > start:
                next_segments.append((start, gap_min))
            if gap_max < end:
                next_segments.append((gap_max, end))
        segments = next_segments
    return [(start, end) for start, end in segments if end - start >= 0.5]


def clipped_opening_bounds(opening: dict, y_min: float, y_max: float, z_min: float, z_max: float) -> tuple[float, float, float, float] | None:
    center_z = float(opening["center_z"])
    half_width = float(opening["width_z"]) * 0.5
    open_z_min = max(z_min, center_z - half_width)
    open_z_max = min(z_max, center_z + half_width)
    if open_z_max - open_z_min < 0.5:
        return None

    center_y = float(opening.get("center_y", (y_min + y_max) * 0.5))
    half_height = float(opening.get("height_y", y_max - y_min)) * 0.5
    open_y_min = max(y_min, center_y - half_height)
    open_y_max = min(y_max, center_y + half_height)
    if open_y_max - open_y_min < 0.4:
        return None
    return open_y_min, open_y_max, open_z_min, open_z_max


def side_wall_openings(contract: dict, region_id: str, side: str) -> list[dict]:
    openings = contract.get("enclosure_generation", {}).get("side_wall_openings", [])
    return [
        opening
        for opening in openings
        if opening.get("region") == region_id and opening.get("side") == side
    ]


def add_side_wall_bands(
    bands: list[dict],
    contract: dict,
    region: dict,
    side: str,
    wall_x: float,
    y_min: float,
    y_max: float,
    z_min: float,
    z_max: float,
    thickness: float,
) -> None:
    openings = side_wall_openings(contract, region["id"], side)
    y_mid = (y_min + y_max) * 0.5
    y_size = y_max - y_min
    for index, (segment_min, segment_max) in enumerate(split_z_segments(z_min, z_max, openings)):
        segment_mid = (segment_min + segment_max) * 0.5
        segment_size = segment_max - segment_min
        suffix = side if len(openings) == 0 else f"{side}_{index + 1:02d}"
        bands.append(
            make_band(
                region,
                f"{region['id']}_{suffix}_wall",
                "side_wall",
                [wall_x, y_mid, segment_mid],
                [thickness, y_size, segment_size],
            )
        )

    for index, opening in enumerate(openings):
        bounds = clipped_opening_bounds(opening, y_min, y_max, z_min, z_max)
        if bounds is None:
            continue
        open_y_min, open_y_max, open_z_min, open_z_max = bounds
        open_z_mid = (open_z_min + open_z_max) * 0.5
        open_z_size = open_z_max - open_z_min
        if open_y_min > y_min + 0.4:
            bottom_y_mid = (y_min + open_y_min) * 0.5
            bottom_y_size = open_y_min - y_min
            bands.append(
                make_band(
                    region,
                    f"{region['id']}_{side}_hatch_{index + 1:02d}_lower_wall",
                    "side_wall",
                    [wall_x, bottom_y_mid, open_z_mid],
                    [thickness, bottom_y_size, open_z_size],
                )
            )
        if open_y_max < y_max - 0.4:
            top_y_mid = (open_y_max + y_max) * 0.5
            top_y_size = y_max - open_y_max
            bands.append(
                make_band(
                    region,
                    f"{region['id']}_{side}_hatch_{index + 1:02d}_upper_wall",
                    "side_wall",
                    [wall_x, top_y_mid, open_z_mid],
                    [thickness, top_y_size, open_z_size],
                )
            )


def build_ceiling_zones(contract: dict) -> list[dict]:
    zones = []
    for region in contract["semantic_regions"]:
        if region["id"] == "cockpit_lower":
            continue
        bounds = region["bounds"]
        bmin = bounds["min"]
        bmax = bounds["max"]
        zones.append(
            {
                "id": region["id"],
                "label": region["id"],
                "x_min": float(bmin[0]),
                "x_max": float(bmax[0]),
                "z_min": float(bmin[2]),
                "z_max": float(bmax[2]),
                "floor_y": float(bmin[1]),
                "max_ceiling_y": float(bmax[1]),
                "slice_size": 4.0,
                "min_headroom": 2.25,
                "ceiling_percentile": 88.0,
                "x_percentile_low": 5.0,
                "x_percentile_high": 95.0,
            }
        )

    zones.append(
        {
            "id": "aft_to_central_ramp",
            "label": "aft_to_central_ramp",
            "x_min": -6.4,
            "x_max": 6.4,
            "z_min": -37.4,
            "z_max": -28.2,
            "floor_y": -1.0,
            "max_ceiling_y": 2.2,
            "slice_size": 2.4,
            "min_headroom": 2.25,
            "ceiling_percentile": 86.0,
            "x_percentile_low": 6.0,
            "x_percentile_high": 94.0,
        }
    )
    return zones


def build_slice_bounds(z_min: float, z_max: float, target_size: float) -> list[tuple[float, float]]:
    count = max(1, int(math.ceil((z_max - z_min) / target_size)))
    return [
        (
            z_min + (z_max - z_min) * index / count,
            z_min + (z_max - z_min) * (index + 1) / count,
        )
        for index in range(count)
    ]


def sample_ceiling_slice(zone: dict, voxels: list[tuple[float, float, float, bool, float]], z_min: float, z_max: float) -> dict:
    x_padding = 0.8
    floor_y = zone["floor_y"]
    zone_voxels = [
        voxel
        for voxel in voxels
        if zone["x_min"] - x_padding <= voxel[0] <= zone["x_max"] + x_padding
        and z_min <= voxel[2] <= z_max
        and voxel[1] >= floor_y + 1.0
    ]
    ceiling_samples = [
        y
        for _x, y, _z, _can_stand, _headroom in zone_voxels
        if y >= floor_y + zone["min_headroom"] - 0.35
    ]
    sampled_ceiling = percentile(ceiling_samples, zone["ceiling_percentile"])
    ceiling_lower_y = sampled_ceiling if sampled_ceiling is not None else floor_y + zone["min_headroom"]
    ceiling_lower_y = clamp(ceiling_lower_y, floor_y + zone["min_headroom"], zone["max_ceiling_y"])

    # Walls are still generated from the accepted region bounds. Until walls are
    # also voxel-fitted, ceiling slices must overlap those wall tops to keep the
    # collision enclosure sealed. Height is voxel-fitted in this pass.
    x_min = zone["x_min"]
    x_max = zone["x_max"]

    return {
        "z_min": z_min,
        "z_max": z_max,
        "voxel_count": len(zone_voxels),
        "sampled_ceiling_y": sampled_ceiling,
        "ceiling_lower_y": ceiling_lower_y,
        "x_min": x_min,
        "x_max": x_max,
    }


def add_voxel_ceiling_bands(
    bands: list[dict],
    contract: dict,
    voxels: list[tuple[float, float, float, bool, float]],
    ceiling_thickness: float,
) -> list[dict]:
    rows: list[dict] = []
    for zone in build_ceiling_zones(contract):
        slices = build_slice_bounds(zone["z_min"], zone["z_max"], zone["slice_size"])
        samples = [sample_ceiling_slice(zone, voxels, z0, z1) for z0, z1 in slices]
        ceiling_ys = smooth_limited([sample["ceiling_lower_y"] for sample in samples], 0.55)
        x_mins = smooth_limited([sample["x_min"] for sample in samples], 0.65)
        x_maxs = smooth_limited([sample["x_max"] for sample in samples], 0.65)

        region = {"id": zone["id"]}
        for index, (sample, ceiling_y, x_min, x_max) in enumerate(zip(samples, ceiling_ys, x_mins, x_maxs), start=1):
            if x_max - x_min < 0.8:
                continue
            z_min = sample["z_min"]
            z_max = sample["z_max"]
            z_center = (z_min + z_max) * 0.5
            bands.append(
                make_band(
                    region,
                    f"{zone['id']}_voxel_ceiling_{index:02d}",
                    "ceiling",
                    [(x_min + x_max) * 0.5, ceiling_y + ceiling_thickness * 0.5, z_center],
                    [x_max - x_min, ceiling_thickness, z_max - z_min],
                )
            )
            rows.append(
                {
                    "zone": zone["id"],
                    "index": index,
                    "z_min": round(z_min, 4),
                    "z_max": round(z_max, 4),
                    "x_min": round(x_min, 4),
                    "x_max": round(x_max, 4),
                    "ceiling_lower_y": round(ceiling_y, 4),
                    "voxel_count": sample["voxel_count"],
                    "sampled_ceiling_y": None if sample["sampled_ceiling_y"] is None else round(sample["sampled_ceiling_y"], 4),
                }
            )
    return rows


def write_ceiling_fit_projection(rows: list[dict], contract: dict) -> None:
    canvas = ship_voxels.ImageCanvas(1600, 900, (12, 15, 19))
    x_min, x_max = -15.0, 15.0
    z_min, z_max = -68.0, 76.0
    y_min, y_max = -10.5, 9.5

    def sx(x: float) -> int:
        return int((x - x_min) / (x_max - x_min) * 760) + 20

    def sz_top(z: float) -> int:
        return 410 - int((z - z_min) / (z_max - z_min) * 380)

    def sz_side(z: float) -> int:
        return 860 - int((z - z_min) / (z_max - z_min) * 380)

    def sy(y: float) -> int:
        return 460 + int((y_max - y) / (y_max - y_min) * 380)

    for region in contract["semantic_regions"]:
        bmin = region["bounds"]["min"]
        bmax = region["bounds"]["max"]
        canvas.rect(sx(bmin[0]), sz_top(bmax[2]), sx(bmax[0]), sz_top(bmin[2]), (54, 67, 83), False)
        canvas.rect(835, sz_side(bmax[2]), 835 + int((bmax[1] - y_min) / (y_max - y_min) * 700), sz_side(bmin[2]), (45, 52, 64), False)

    for row in rows:
        color = (97, 196, 255)
        canvas.rect(sx(row["x_min"]), sz_top(row["z_max"]), sx(row["x_max"]), sz_top(row["z_min"]), color, False)
        y = sy(row["ceiling_lower_y"])
        canvas.line(835 + int((row["ceiling_lower_y"] - y_min) / (y_max - y_min) * 700), sz_side(row["z_min"]), 835 + int((row["ceiling_lower_y"] - y_min) / (y_max - y_min) * 700), sz_side(row["z_max"]), color)
        canvas.rect(835 + int((row["ceiling_lower_y"] - y_min) / (y_max - y_min) * 700) - 2, sz_side(row["z_max"]), 835 + int((row["ceiling_lower_y"] - y_min) / (y_max - y_min) * 700) + 2, sz_side(row["z_min"]), color, True)

    # Top labels as simple guide bars: top projection on left, side Y/Z on right.
    canvas.rect(20, 20, 780, 410, (70, 70, 70), False)
    canvas.rect(835, 460, 1540, 860, (70, 70, 70), False)
    CEILING_FIT_PNG.parent.mkdir(parents=True, exist_ok=True)
    canvas.write_png(CEILING_FIT_PNG)


def generate_bands(contract: dict) -> dict:
    thickness = float(contract["enclosure_generation"]["wall_thickness"])
    ceiling_thickness = float(contract["enclosure_generation"]["ceiling_thickness"])
    voxels = load_compact_voxels()
    bands = []

    for region in contract["semantic_regions"]:
        bounds = region["bounds"]
        bmin = bounds["min"]
        bmax = bounds["max"]
        x_mid = (bmin[0] + bmax[0]) * 0.5
        y_mid = (bmin[1] + bmax[1]) * 0.5
        z_mid = (bmin[2] + bmax[2]) * 0.5
        x_size = max(0.1, bmax[0] - bmin[0])
        y_size = max(0.1, bmax[1] - bmin[1])
        z_size = max(0.1, bmax[2] - bmin[2])

        add_side_wall_bands(
            bands,
            contract,
            region,
            "port",
            bmin[0] - thickness * 0.5,
            bmin[1],
            bmax[1],
            bmin[2] - 0.4,
            bmax[2] + 0.4,
            thickness,
        )
        add_side_wall_bands(
            bands,
            contract,
            region,
            "starboard",
            bmax[0] + thickness * 0.5,
            bmin[1],
            bmax[1],
            bmin[2] - 0.4,
            bmax[2] + 0.4,
            thickness,
        )
        add_floorplan_end_caps(bands, region, thickness)

    ceiling_rows = add_voxel_ceiling_bands(bands, contract, voxels, ceiling_thickness)

    aft_ramp_region = {"id": "aft_to_central_ramp"}
    guard_x = AFT_TO_CENTRAL_RAMP_HALF_WIDTH + thickness * 0.5
    for side, x in (("port", -guard_x), ("starboard", guard_x)):
        bands.append(
            make_band(
                aft_ramp_region,
                f"aft_to_central_ramp_{side}_guard_wall",
                "side_wall",
                [x, -3.0, -32.75],
                [thickness, 7.2, 10.9],
            )
        )
        bands.append(
            make_band(
                aft_ramp_region,
                f"aft_to_central_ramp_{side}_upper_closure_wall",
                "side_wall",
                [x, 1.25, -31.0],
                [thickness, 2.5, 3.5],
            )
        )

    cockpit_stairwell_enclosure = {"id": "cockpit_stairwell_enclosure"}
    ramp_pitch_degrees = 47.25
    for side, x in (("port", -4.36), ("starboard", 4.36)):
        bands.append(
            make_band(
                cockpit_stairwell_enclosure,
                f"cockpit_{side}_stairwell_sloped_outer_enclosure_wall",
                "side_wall",
                [x, -4.95, 64.5],
                [0.35, 2.8, 11.1],
                [ramp_pitch_degrees, 0.0, 0.0],
            )
        )

    bands.append(
        make_band(
            {"id": "forward_access_to_cockpit_upper"},
            "forward_access_to_cockpit_upper_high_end_cap",
            "end_wall",
            [0.0, 4.85, 59.75],
            [7.0, 1.4, thickness],
        )
    )

    return {
        "schema_version": 1,
        "ship_id": "cargo_crane",
        "coordinate_space": "ship local",
        "source_contract": str(CONTRACT_PATH.relative_to(ROOT)),
        "ceiling_generation": {
            "method": "voxel_slice_envelope",
            "source_voxels": str(VOXELS_PATH.relative_to(ROOT)),
            "preview": str(CEILING_FIT_PNG.relative_to(ROOT)),
            "slices": ceiling_rows,
        },
        "bands": bands,
    }


def write_outputs(enclosure: dict) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(enclosure, indent=2) + "\n", encoding="utf-8")
    write_ceiling_fit_projection(enclosure.get("ceiling_generation", {}).get("slices", []), load_contract())
    by_region = {}
    for band in enclosure["bands"]:
        by_region.setdefault(band["region"], []).append(band["type"])
    report = {
        "schema_version": 1,
        "ship_id": "cargo_crane",
        "status": "PASS",
        "band_count": len(enclosure["bands"]),
        "region_count": len(by_region),
        "bands_by_region": by_region,
        "ceiling_generation": enclosure.get("ceiling_generation", {}),
        "output": str(OUT_PATH.relative_to(ROOT)),
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# CargoCrane Enclosure Bands Report",
        "",
        "Status: **PASS**",
        "",
        f"- Bands: `{len(enclosure['bands'])}`",
        f"- Regions: `{len(by_region)}`",
        f"- Output: `{OUT_PATH.relative_to(ROOT)}`",
        f"- Ceiling fit preview: `{CEILING_FIT_PNG.relative_to(ROOT)}`",
        f"- Voxel ceiling slices: `{len(enclosure.get('ceiling_generation', {}).get('slices', []))}`",
        "",
        "## Regions",
        "",
    ]
    for region, types in sorted(by_region.items()):
        lines.append(f"- `{region}`: {', '.join(types)}")
    lines.extend(["", "## Voxel Ceiling Slices", ""])
    for row in enclosure.get("ceiling_generation", {}).get("slices", [])[:120]:
        lines.append(
            f"- `{row['zone']}` #{row['index']:02d}: z `{row['z_min']}`..`{row['z_max']}`, "
            f"x `{row['x_min']}`..`{row['x_max']}`, lower y `{row['ceiling_lower_y']}`, voxels `{row['voxel_count']}`"
        )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    enclosure = generate_bands(load_contract())
    write_outputs(enclosure)
    print(f"Wrote {OUT_PATH.relative_to(ROOT)}")
    print(f"Wrote {REPORT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
