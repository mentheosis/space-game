#!/usr/bin/env python3
"""Extract first-pass MX01 interior volume and deck candidates from occupancy."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict, deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SHIP_DIR = ROOT / "ships" / "MX01"
DEFAULT_CONFIG = SHIP_DIR / "config" / "mx01_collision_generation.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_config_path(config: dict, section: str, key: str) -> Path:
    return ROOT / config[section][key]


def build_inside_set(occupancy: dict) -> set[tuple[int, int, int]]:
    inside: set[tuple[int, int, int]] = set()
    for ray in occupancy["rays"]:
        yi = int(ray["y_index"])
        zi = int(ray["z_index"])
        for start, end in ray["x_intervals"]:
            for xi in range(int(start), int(end) + 1):
                inside.add((xi, yi, zi))
    return inside


def connected_components(cells: set[tuple[int, int]]) -> list[set[tuple[int, int]]]:
    remaining = set(cells)
    components: list[set[tuple[int, int]]] = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        component = {start}
        queue: deque[tuple[int, int]] = deque([start])
        while queue:
            x, z = queue.popleft()
            for neighbor in ((x - 1, z), (x + 1, z), (x, z - 1), (x, z + 1)):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)
        components.append(component)
    components.sort(key=lambda c: (-len(c), min(c)))
    return components


def component_bounds(component: set[tuple[int, int]], x_centers: list[float], y: float, z_centers: list[float]) -> dict:
    xs = [x_centers[xi] for xi, _zi in component]
    zs = [z_centers[zi] for _xi, zi in component]
    return {
        "min": [round(min(xs), 6), round(y, 6), round(min(zs), 6)],
        "max": [round(max(xs), 6), round(y, 6), round(max(zs), 6)],
        "size": [round(max(xs) - min(xs), 6), 0.0, round(max(zs) - min(zs), 6)],
    }


def deck_from_component(deck_id: str, y_index: int, y: float, component: set[tuple[int, int]], x_centers: list[float], z_centers: list[float], voxel_size: float, status: str = "ACCEPTED_FIRST_PASS") -> dict:
    return {
        "id": deck_id,
        "y_index": y_index,
        "y": y,
        "walkable_cells": len(component),
        "estimated_area_m2": round(len(component) * voxel_size * voxel_size, 4),
        "largest_component_cells": len(component),
        "largest_component_area_m2": round(len(component) * voxel_size * voxel_size, 4),
        "largest_component_bounds": component_bounds(component, x_centers, y, z_centers),
        "status": status,
    }


def extract(config: dict, occupancy: dict) -> tuple[dict, dict]:
    x_centers = occupancy["axis_centers"]["x"]
    y_centers = occupancy["axis_centers"]["y"]
    z_centers = occupancy["axis_centers"]["z"]
    voxel_size = float(occupancy["voxel_size"])
    inside = build_inside_set(occupancy)
    clearance = float(config["player_capsule_height"]) + float(config["player_clearance_margin"])
    clearance_cells = max(1, int(math.ceil(clearance / voxel_size)))
    min_component_cells = max(16, int(math.ceil(float(config["min_component_volume"]) / (voxel_size ** 3))))

    walkable_by_y: dict[int, set[tuple[int, int]]] = defaultdict(set)
    for xi, yi, zi in sorted(inside):
        if yi + clearance_cells >= len(y_centers):
            continue
        clear = True
        for offset in range(1, clearance_cells + 1):
            if (xi, yi + offset, zi) not in inside:
                clear = False
                break
        if clear:
            walkable_by_y[yi].add((xi, zi))

    y_summaries = []
    candidate_components = []
    components_by_y: dict[int, list[set[tuple[int, int]]]] = {}
    for yi in sorted(walkable_by_y):
        components = [component for component in connected_components(walkable_by_y[yi]) if len(component) >= min_component_cells]
        if not components:
            continue
        components_by_y[yi] = components
        largest = components[0]
        total_cells = sum(len(component) for component in components)
        y_summaries.append(
            {
                "y_index": yi,
                "y": y_centers[yi],
                "walkable_cells": total_cells,
                "component_count": len(components),
                "largest_component_cells": len(largest),
                "largest_component_bounds": component_bounds(largest, x_centers, y_centers[yi], z_centers),
            }
        )
        for component_index, component in enumerate(components[:4]):
            candidate_components.append(
                {
                    "id": f"y{yi:03d}_component_{component_index + 1:02d}",
                    "y_index": yi,
                    "y": y_centers[yi],
                    "cell_count": len(component),
                    "area_m2": round(len(component) * voxel_size * voxel_size, 4),
                    "bounds": component_bounds(component, x_centers, y_centers[yi], z_centers),
                }
            )

    deck_bands = choose_deck_bands(y_summaries, y_centers)
    accepted = []
    for deck_id, y_min, y_max in deck_bands:
        rows = [row for row in y_summaries if y_min <= row["y_index"] <= y_max]
        if not rows:
            continue
        best = max(rows, key=lambda row: (row["largest_component_cells"], row["walkable_cells"], -row["y_index"]))
        accepted.append(deck_from_component(deck_id, best["y_index"], best["y"], components_by_y[best["y_index"]][0], x_centers, z_centers, voxel_size))

    accepted.extend(choose_forward_lower_decks(accepted, components_by_y, x_centers, y_centers, z_centers, voxel_size))
    accepted.sort(key=lambda deck: (deck["y"], deck["id"]))

    total_walkable_cells = sum(row["walkable_cells"] for row in y_summaries)
    report = {
        "ship_id": config["ship_id"],
        "method": "occupancy_clearance_deck_band_extraction_v1",
        "voxel_size": voxel_size,
        "player_capsule_height": config["player_capsule_height"],
        "player_clearance_margin": config["player_clearance_margin"],
        "clearance_cells": clearance_cells,
        "min_component_cells": min_component_cells,
        "counts": {
            "inside_voxels": len(inside),
            "walkable_y_levels": len(y_summaries),
            "total_walkable_cells_across_y_levels": total_walkable_cells,
            "candidate_components": len(candidate_components),
            "accepted_decks": len(accepted),
        },
        "accepted_decks": accepted,
        "y_level_summaries": y_summaries,
        "status": "PASS" if len(accepted) >= 3 else "WARN",
        "notes": "First-pass deck candidates require traversal graph fitting before they are accepted as gameplay collision.",
    }
    payload = {
        "ship_id": config["ship_id"],
        "method": report["method"],
        "voxel_size": voxel_size,
        "accepted_decks": accepted,
        "candidate_components": candidate_components,
    }
    return payload, report


def choose_deck_bands(y_summaries: list[dict], y_centers: list[float]) -> list[tuple[str, int, int]]:
    if not y_summaries:
        return []
    min_yi = min(row["y_index"] for row in y_summaries)
    max_yi = max(row["y_index"] for row in y_summaries)
    span = max(1, max_yi - min_yi + 1)
    lower_end = min_yi + span // 3
    mid_end = min_yi + 2 * span // 3
    return [
        ("lower_deck_candidate", min_yi, lower_end),
        ("mid_deck_candidate", lower_end + 1, mid_end),
        ("upper_deck_candidate", mid_end + 1, max_yi),
    ]


def choose_forward_lower_decks(
    accepted: list[dict],
    components_by_y: dict[int, list[set[tuple[int, int]]]],
    x_centers: list[float],
    y_centers: list[float],
    z_centers: list[float],
    voxel_size: float,
) -> list[dict]:
    if not accepted:
        return []
    current_lowest_y = min(float(deck["y"]) for deck in accepted)
    z_min = min(z_centers)
    z_max = max(z_centers)
    forward_threshold = z_min + (z_max - z_min) * 0.72
    min_vertical_spacing = 1.6
    candidates = []
    for yi, components in components_by_y.items():
        y = float(y_centers[yi])
        if y >= current_lowest_y - 1.4:
            continue
        for component in components:
            bounds = component_bounds(component, x_centers, y, z_centers)
            if float(bounds["max"][2]) < forward_threshold:
                continue
            candidates.append((len(component), yi, y, component, bounds))

    selected: list[tuple[int, int, float, set[tuple[int, int]], dict]] = []
    for candidate in sorted(candidates, key=lambda item: (-item[0], -item[2], item[1])):
        _size, _yi, y, _component, _bounds = candidate
        if any(abs(y - other[2]) < min_vertical_spacing for other in selected):
            continue
        selected.append(candidate)
        if len(selected) == 2:
            break
    selected.sort(key=lambda item: item[2])
    decks = []
    for index, (_size, yi, y, component, _bounds) in enumerate(selected, start=1):
        decks.append(
            deck_from_component(
                f"forward_cockpit_lower_deck_{index:02d}",
                yi,
                y,
                component,
                x_centers,
                z_centers,
                voxel_size,
                "ACCEPTED_FORWARD_COCKPIT_SUBDECK",
            )
        )
    return decks


def draw_deck_projection(path: Path, occupancy: dict, volume: dict) -> None:
    x_count = len(occupancy["axis_centers"]["x"])
    z_count = len(occupancy["axis_centers"]["z"])
    scale = max(3, min(8, int(900 / max(x_count, z_count, 1))))
    width = z_count * scale
    height = x_count * scale + 40
    colors = ["#22c55e", "#38bdf8", "#facc15", "#fb7185", "#a78bfa"]
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#111827"/>',
        '<text x="8" y="22" font-family="Arial, sans-serif" font-size="13" fill="#f9fafb">MX01 accepted deck candidates, top projection</text>',
    ]
    for deck_index, deck in enumerate(volume["accepted_decks"]):
        color = colors[deck_index % len(colors)]
        bounds = deck["largest_component_bounds"]
        x_min, _y, z_min = bounds["min"]
        x_max, _y2, z_max = bounds["max"]
        xi_min = nearest_index(occupancy["axis_centers"]["x"], x_min)
        xi_max = nearest_index(occupancy["axis_centers"]["x"], x_max)
        zi_min = nearest_index(occupancy["axis_centers"]["z"], z_min)
        zi_max = nearest_index(occupancy["axis_centers"]["z"], z_max)
        x = zi_min * scale
        y = 40 + (x_count - 1 - xi_max) * scale
        w = max(scale, (zi_max - zi_min + 1) * scale)
        h = max(scale, (xi_max - xi_min + 1) * scale)
        lines.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{color}" fill-opacity="0.28" stroke="{color}" stroke-width="2"/>')
        lines.append(f'<text x="{x + 4}" y="{y + 16}" font-family="Arial, sans-serif" font-size="12" fill="{color}">{deck["id"]} y={deck["y"]}</text>')
    lines.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def nearest_index(values: list[float], target: float) -> int:
    return min(range(len(values)), key=lambda index: (abs(values[index] - target), index))


def write_markdown(path: Path, report: dict) -> None:
    lines = [
        "# MX01 Interior Volume Report",
        "",
        f"- Method: `{report['method']}`",
        f"- Status: `{report['status']}`",
        f"- Clearance cells: `{report['clearance_cells']}`",
        f"- Walkable Y levels: `{report['counts']['walkable_y_levels']}`",
        f"- Candidate components: `{report['counts']['candidate_components']}`",
        f"- Accepted deck candidates: `{report['counts']['accepted_decks']}`",
        "",
        "## Accepted Deck Candidates",
        "",
    ]
    for deck in report["accepted_decks"]:
        lines.extend(
            [
                f"### {deck['id']}",
                "",
                f"- Y: `{deck['y']}`",
                f"- Estimated area: `{deck['estimated_area_m2']} m2`",
                f"- Largest component area: `{deck['largest_component_area_m2']} m2`",
                f"- Bounds: `{deck['largest_component_bounds']}`",
                "",
            ]
        )
    lines.extend(["## Notes", "", report["notes"]])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    config_path = args.config.resolve()
    config = load_json(config_path)
    occupancy_path = resolve_config_path(config, "occupancy_outputs", "intervals_json")
    occupancy = load_json(occupancy_path)
    volume, report = extract(config, occupancy)

    volume_json = resolve_config_path(config, "interior_volume_outputs", "volume_json")
    report_json = resolve_config_path(config, "interior_volume_outputs", "report_json")
    report_md = resolve_config_path(config, "interior_volume_outputs", "report_md")
    deck_svg = resolve_config_path(config, "interior_volume_outputs", "deck_projection_svg")
    manifest_json = resolve_config_path(config, "interior_volume_outputs", "manifest_json")

    report["source"] = {"occupancy_intervals": rel(occupancy_path), "occupancy_intervals_sha256": sha256(occupancy_path)}
    report["config"] = {"path": rel(config_path), "sha256": sha256(config_path), "effective_values": config}
    report["tools"] = {
        "extract_mx01_interior_volume.py": {"path": rel(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())}
    }
    report["outputs"] = {"volume_json": rel(volume_json), "deck_projection_svg": rel(deck_svg)}

    write_json(volume_json, volume)
    write_json(report_json, report)
    write_markdown(report_md, report)
    draw_deck_projection(deck_svg, occupancy, volume)
    write_json(
        manifest_json,
        {
            "ship_id": config["ship_id"],
            "stage": "interior_volume_extraction",
            "source": report["source"],
            "config": report["config"],
            "outputs": {
                "volume_json": rel(volume_json),
                "volume_json_sha256": sha256(volume_json),
                "report_json": rel(report_json),
                "report_md": rel(report_md),
                "deck_projection_svg": rel(deck_svg),
            },
            "tools": report["tools"],
        },
    )
    print(f"Wrote {rel(volume_json)}")
    print(f"Wrote {rel(report_json)}")
    print(f"Wrote {rel(report_md)}")
    print(f"Wrote {rel(deck_svg)}")
    print(f"Wrote {rel(manifest_json)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
