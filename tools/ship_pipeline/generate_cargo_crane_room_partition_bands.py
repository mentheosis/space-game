#!/usr/bin/env python3
"""Generate CargoCrane interior room partition bands from the 2D proposal."""

from __future__ import annotations

import json
from pathlib import Path

from propose_cargo_crane_room_partition_plan import split_line_segments


ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / "reports/ship_pipeline/cargo_crane_room_partition_plan/cargo_crane_room_partition_plan.json"
OUT_PATH = ROOT / "assets/models/ship/cargo_crane/cargo_crane_room_partition_bands.json"
REPORT_JSON = ROOT / "reports/ship_pipeline/cargo_crane_room_partition_plan/cargo_crane_room_partition_bands_report.json"
REPORT_MD = ROOT / "reports/ship_pipeline/cargo_crane_room_partition_plan/cargo_crane_room_partition_bands_report.md"

WALL_THICKNESS = 0.18
MAIN_FLOOR_Y = -1.0
WALL_HEIGHT = 5.9
MIN_SEGMENT_LENGTH = 0.35


def make_band(name: str, partition: dict, start: list[float], end: list[float]) -> dict | None:
    if abs(start[0] - end[0]) < 0.001:
        length = abs(end[1] - start[1])
        if length < MIN_SEGMENT_LENGTH:
            return None
        center = [start[0], MAIN_FLOOR_Y + WALL_HEIGHT * 0.5, (start[1] + end[1]) * 0.5]
        size = [WALL_THICKNESS, WALL_HEIGHT, length]
    elif abs(start[1] - end[1]) < 0.001:
        length = abs(end[0] - start[0])
        if length < MIN_SEGMENT_LENGTH:
            return None
        center = [(start[0] + end[0]) * 0.5, MAIN_FLOOR_Y + WALL_HEIGHT * 0.5, start[1]]
        size = [length, WALL_HEIGHT, WALL_THICKNESS]
    else:
        raise ValueError(f"Partition segment must be axis-aligned: {start} -> {end}")

    return {
        "name": name,
        "type": "room_partition_wall",
        "source_partition": partition["name"],
        "center": [round(value, 4) for value in center],
        "size": [round(value, 4) for value in size],
    }


def generate_bands(plan: dict) -> dict:
    bands = []
    for partition in plan["partitions"]:
        solid_segments = split_line_segments(partition["from"], partition["to"], partition["door_gaps"])
        for index, (start, end) in enumerate(solid_segments, start=1):
            band = make_band(f"{partition['name']}_{index:02d}", partition, start, end)
            if band is not None:
                bands.append(band)

    return {
        "schema_version": 1,
        "ship_id": "cargo_crane",
        "coordinate_space": "ship local",
        "source_plan": str(PLAN_PATH.relative_to(ROOT)),
        "wall_thickness": WALL_THICKNESS,
        "wall_height": WALL_HEIGHT,
        "collision_default": False,
        "bands": bands,
    }


def write_report(room_bands: dict) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(room_bands, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# CargoCrane Room Partition Bands Report",
        "",
        f"- Source plan: `{room_bands['source_plan']}`",
        f"- Band count: `{len(room_bands['bands'])}`",
        f"- Wall thickness: `{room_bands['wall_thickness']}`",
        f"- Wall height: `{room_bands['wall_height']}`",
        f"- Collision default: `{room_bands['collision_default']}`",
        "",
        "## Bands",
        "",
    ]
    for band in room_bands["bands"]:
        lines.append(f"- `{band['name']}` from `{band['source_partition']}` center `{band['center']}` size `{band['size']}`")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    room_bands = generate_bands(plan)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(room_bands, indent=2) + "\n", encoding="utf-8")
    write_report(room_bands)
    print(f"Wrote {OUT_PATH.relative_to(ROOT)}")
    print(f"Wrote {REPORT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
