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
    y_mid: float,
    y_size: float,
    z_min: float,
    z_max: float,
    thickness: float,
) -> None:
    openings = side_wall_openings(contract, region["id"], side)
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
            y_mid,
            y_size,
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
            y_mid,
            y_size,
            bmin[2],
            bmax[2],
            thickness,
        )
        bands.append(
            make_band(
                region,
                f"{region['id']}_ceiling",
                "ceiling",
                [x_mid, bmax[1] + ceiling_thickness * 0.5, z_mid],
                [x_size, ceiling_thickness, z_size],
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
