#!/usr/bin/env python3
"""Generate CargoCrane enclosure wall and ceiling bands from the layout contract."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "assets/source/blender/ships/cargo_crane/cargo_crane_interior_layout_contract.json"
OUT_PATH = ROOT / "assets/models/ship/cargo_crane/cargo_crane_enclosure_bands.json"
REPORT_JSON = ROOT / "reports/ship_pipeline/cargo_crane_voxel_fit/cargo_crane_enclosure_bands_report.json"
REPORT_MD = ROOT / "reports/ship_pipeline/cargo_crane_voxel_fit/cargo_crane_enclosure_bands_report.md"
AFT_TO_CENTRAL_RAMP_HALF_WIDTH = 6.3


def load_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def make_band(region: dict, name: str, band_type: str, center: list[float], size: list[float]) -> dict:
    return {
        "name": name,
        "type": band_type,
        "region": region["id"],
        "center": [round(value, 4) for value in center],
        "size": [round(value, 4) for value in size],
    }


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
        ramp_min_x = -AFT_TO_CENTRAL_RAMP_HALF_WIDTH
        ramp_max_x = AFT_TO_CENTRAL_RAMP_HALF_WIDTH
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
        ramp_min_x = -AFT_TO_CENTRAL_RAMP_HALF_WIDTH
        ramp_max_x = AFT_TO_CENTRAL_RAMP_HALF_WIDTH
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
        # Keep side stair passage slots open, but close the center and low aft wall.
        add_end_wall_band(
            bands,
            region,
            f"{region_id}_aft_center_lower_end_wall",
            bmin[2] - thickness * 0.5,
            -2.35,
            2.35,
            bmin[1],
            -3.6,
            thickness,
        )
        for side, x_min, x_max in (
            ("port", bmin[0], -2.55),
            ("starboard", 2.55, bmax[0]),
        ):
            add_end_wall_band(
                bands,
                region,
                f"{region_id}_aft_{side}_low_end_wall",
                bmin[2] - thickness * 0.5,
                x_min,
                x_max,
                bmin[1],
                -7.0,
                thickness,
            )
        add_end_wall_band(
            bands,
            region,
            f"{region_id}_aft_center_end_wall",
            bmin[2] - thickness * 0.5,
            -2.25,
            2.25,
            -3.6,
            bmax[1],
            thickness,
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


def generate_bands(contract: dict) -> dict:
    thickness = float(contract["enclosure_generation"]["wall_thickness"])
    ceiling_thickness = float(contract["enclosure_generation"]["ceiling_thickness"])
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
            bmin[2],
            bmax[2],
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
            bmin[2],
            bmax[2],
            thickness,
        )
        add_floorplan_end_caps(bands, region, thickness)
        if region["id"] == "cockpit_lower":
            bands.append(
                make_band(
                    region,
                    f"{region['id']}_center_ceiling",
                    "ceiling",
                    [0.0, bmax[1] + ceiling_thickness * 0.5, z_mid],
                    [4.5, ceiling_thickness, z_size],
                )
            )
        else:
            bands.append(
                make_band(
                    region,
                    f"{region['id']}_ceiling",
                    "ceiling",
                    [x_mid, bmax[1] + ceiling_thickness * 0.5, z_mid],
                    [x_size, ceiling_thickness, z_size],
                )
            )

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

    cockpit_stair_region = {"id": "cockpit_stair_guard"}
    for side, x in (("port", -2.35), ("starboard", 2.35)):
        bands.append(
            make_band(
                cockpit_stair_region,
                f"cockpit_{side}_inner_stair_guard_wall",
                "side_wall",
                [x, -3.45, 65.1],
                [thickness, 10.9, 5.8],
            )
        )

    return {
        "schema_version": 1,
        "ship_id": "cargo_crane",
        "coordinate_space": "ship local",
        "source_contract": str(CONTRACT_PATH.relative_to(ROOT)),
        "bands": bands,
    }


def write_outputs(enclosure: dict) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(enclosure, indent=2) + "\n", encoding="utf-8")
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
        "",
        "## Regions",
        "",
    ]
    for region, types in sorted(by_region.items()):
        lines.append(f"- `{region}`: {', '.join(types)}")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    enclosure = generate_bands(load_contract())
    write_outputs(enclosure)
    print(f"Wrote {OUT_PATH.relative_to(ROOT)}")
    print(f"Wrote {REPORT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
