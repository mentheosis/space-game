#!/usr/bin/env python3
"""Fit a first-pass connected traversal graph across MX01 deck candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict, deque
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


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resolve_config_path(config: dict, section: str, key: str) -> Path:
    return ROOT / config[section][key]


def rect_from_bounds(bounds: dict) -> dict:
    return {
        "x_min": float(bounds["min"][0]),
        "x_max": float(bounds["max"][0]),
        "z_min": float(bounds["min"][2]),
        "z_max": float(bounds["max"][2]),
    }


def overlap(a: dict, b: dict) -> dict | None:
    x_min = max(a["x_min"], b["x_min"])
    x_max = min(a["x_max"], b["x_max"])
    z_min = max(a["z_min"], b["z_min"])
    z_max = min(a["z_max"], b["z_max"])
    if x_max <= x_min or z_max <= z_min:
        return None
    return {
        "x_min": round(x_min, 6),
        "x_max": round(x_max, 6),
        "z_min": round(z_min, 6),
        "z_max": round(z_max, 6),
        "width": round(x_max - x_min, 6),
        "depth": round(z_max - z_min, 6),
        "area": round((x_max - x_min) * (z_max - z_min), 6),
        "center": [round((x_min + x_max) * 0.5, 6), round((z_min + z_max) * 0.5, 6)],
    }


def build_graph(config: dict, volume: dict) -> tuple[dict, dict]:
    decks = sorted(volume["accepted_decks"], key=lambda deck: (deck["y"], deck["id"]))
    min_connector_width = 2.0 * float(config["player_capsule_radius"]) + 2.0 * float(config["player_clearance_margin"])
    nodes = []
    for deck in decks:
        bounds = deck["largest_component_bounds"]
        rect = rect_from_bounds(bounds)
        nodes.append(
            {
                "id": deck["id"],
                "kind": "deck",
                "center": [
                    round((rect["x_min"] + rect["x_max"]) * 0.5, 6),
                    deck["y"],
                    round((rect["z_min"] + rect["z_max"]) * 0.5, 6),
                ],
                "bounds": bounds,
                "estimated_area_m2": deck["largest_component_area_m2"],
                "status": "ACCEPTED_FIRST_PASS",
            }
        )

    edges = []
    connected_decks: set[str] = set()
    for index, a in enumerate(decks[:-1]):
        higher = decks[index + 1 :]
        connectable = []
        for b in higher:
            connector_overlap = overlap(rect_from_bounds(a["largest_component_bounds"]), rect_from_bounds(b["largest_component_bounds"]))
            if connector_overlap is None:
                continue
            connectable.append((float(b["y"]) - float(a["y"]), b, connector_overlap))
        if not connectable:
            b = higher[0]
            connector_overlap = None
        else:
            _delta, b, connector_overlap = min(connectable, key=lambda item: (item[0], -item[2]["area"], item[1]["id"]))
        if connector_overlap is None:
            status = "FAIL_NO_XZ_OVERLAP"
            connector_center = None
            connector_type = "unresolved_vertical_connector"
        else:
            status = "PASS" if connector_overlap["width"] >= min_connector_width and connector_overlap["depth"] >= min_connector_width else "WARN_NARROW_OVERLAP"
            connector_center = [
                connector_overlap["center"][0],
                round((a["y"] + b["y"]) * 0.5, 6),
                connector_overlap["center"][1],
            ]
            connector_type = "lift_or_stairwell_candidate"
            connected_decks.update({a["id"], b["id"]})
        edges.append(
            {
                "id": f"{a['id']}_to_{b['id']}",
                "kind": connector_type,
                "from": a["id"],
                "to": b["id"],
                "vertical_delta": round(b["y"] - a["y"], 6),
                "connector_center": connector_center,
                "overlap": connector_overlap,
                "min_connector_width": round(min_connector_width, 6),
                "status": status,
            }
        )

    extra_edges = []
    if "lower_deck_candidate" in {deck["id"] for deck in decks}:
        lower = next(deck for deck in decks if deck["id"] == "lower_deck_candidate")
        for b in decks:
            if float(b["y"]) <= float(lower["y"]) or b["id"] in connected_decks:
                continue
            connector_overlap = overlap(rect_from_bounds(lower["largest_component_bounds"]), rect_from_bounds(b["largest_component_bounds"]))
            if connector_overlap is None:
                continue
            status = "PASS" if connector_overlap["width"] >= min_connector_width and connector_overlap["depth"] >= min_connector_width else "WARN_NARROW_OVERLAP"
            extra_edges.append(
                {
                    "id": f"{lower['id']}_to_{b['id']}",
                    "kind": "lift_or_stairwell_candidate",
                    "from": lower["id"],
                    "to": b["id"],
                    "vertical_delta": round(b["y"] - lower["y"], 6),
                    "connector_center": [
                        connector_overlap["center"][0],
                        round((lower["y"] + b["y"]) * 0.5, 6),
                        connector_overlap["center"][1],
                    ],
                    "overlap": connector_overlap,
                    "min_connector_width": round(min_connector_width, 6),
                    "status": status,
                }
            )
    edges.extend(extra_edges)
    edges.sort(key=lambda edge: (edge["from"], edge["to"], edge["id"]))

    entry_target = next((deck for deck in decks if deck["id"] == "lower_deck_candidate"), decks[0] if decks else None)
    entry_node = {
        "id": "entry_ramp_candidate",
        "kind": "entry",
        "center": [0.0, entry_target["y"] if entry_target else 0.0, entry_target["largest_component_bounds"]["min"][2] if entry_target else 0.0],
        "target_deck": entry_target["id"] if entry_target else None,
        "status": "ACCEPTED_FIRST_PASS" if decks else "FAIL_NO_DECK",
    }
    nodes.insert(0, entry_node)
    if entry_target:
        edges.insert(
            0,
            {
                "id": f"entry_ramp_candidate_to_{entry_target['id']}",
                "kind": "entry_handoff_candidate",
                "from": entry_node["id"],
                "to": entry_target["id"],
                "vertical_delta": 0.0,
                "connector_center": entry_node["center"],
                "overlap": None,
                "min_connector_width": round(min_connector_width, 6),
                "status": "PASS",
            },
        )

    reachable = reachable_nodes(nodes, edges, "entry_ramp_candidate")
    deck_ids = {deck["id"] for deck in decks}
    reachable_decks = sorted(deck_ids & reachable)
    failing_edges = [edge for edge in edges if edge["status"].startswith("FAIL")]
    warning_edges = [edge for edge in edges if edge["status"].startswith("WARN")]
    graph = {
        "ship_id": config["ship_id"],
        "method": "deck_overlap_traversal_graph_v1",
        "nodes": nodes,
        "edges": edges,
        "entry_node": "entry_ramp_candidate",
        "reachable_nodes": sorted(reachable),
        "reachable_decks": reachable_decks,
    }
    report = {
        "ship_id": config["ship_id"],
        "method": graph["method"],
        "min_connector_width": round(min_connector_width, 6),
        "counts": {
            "nodes": len(nodes),
            "edges": len(edges),
            "decks": len(deck_ids),
            "reachable_decks": len(reachable_decks),
            "failing_edges": len(failing_edges),
            "warning_edges": len(warning_edges),
        },
        "status": "PASS" if len(reachable_decks) == len(deck_ids) and not failing_edges else "FAIL",
        "warnings": warning_edges,
        "failures": failing_edges,
        "notes": "This graph proves coarse deck connectivity only. It does not yet prove ramp, stair, ladder, or capsule-sweep geometry.",
    }
    return graph, report


def reachable_nodes(nodes: list[dict], edges: list[dict], start: str) -> set[str]:
    ids = {node["id"] for node in nodes}
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if edge["status"].startswith("FAIL"):
            continue
        adjacency[edge["from"]].add(edge["to"])
        adjacency[edge["to"]].add(edge["from"])
    seen = {start} if start in ids else set()
    queue: deque[str] = deque(seen)
    while queue:
        node = queue.popleft()
        for neighbor in sorted(adjacency[node]):
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return seen


def draw_projection(path: Path, graph: dict) -> None:
    deck_nodes = [node for node in graph["nodes"] if node["kind"] == "deck"]
    if not deck_nodes:
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>\n', encoding="utf-8")
        return
    x_values = []
    z_values = []
    for node in deck_nodes:
        b = node["bounds"]
        x_values.extend([b["min"][0], b["max"][0]])
        z_values.extend([b["min"][2], b["max"][2]])
    x_min, x_max = min(x_values), max(x_values)
    z_min, z_max = min(z_values), max(z_values)
    pad = 24
    width = 1000
    height = 420

    def map_point(x: float, z: float) -> tuple[float, float]:
        px = pad + (z - z_min) / max(0.001, z_max - z_min) * (width - 2 * pad)
        py = height - pad - (x - x_min) / max(0.001, x_max - x_min) * (height - 2 * pad)
        return px, py

    colors = {"lower_deck_candidate": "#22c55e", "mid_deck_candidate": "#38bdf8", "upper_deck_candidate": "#facc15"}
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#111827"/>',
        '<text x="16" y="24" font-family="Arial, sans-serif" font-size="14" fill="#f9fafb">MX01 traversal graph top projection</text>',
    ]
    for node in deck_nodes:
        b = node["bounds"]
        x1, y1 = map_point(b["min"][0], b["min"][2])
        x2, y2 = map_point(b["max"][0], b["max"][2])
        rect_x = min(x1, x2)
        rect_y = min(y1, y2)
        rect_w = abs(x2 - x1)
        rect_h = abs(y2 - y1)
        color = colors.get(node["id"], "#a78bfa")
        lines.append(f'<rect x="{rect_x:.2f}" y="{rect_y:.2f}" width="{rect_w:.2f}" height="{rect_h:.2f}" fill="{color}" fill-opacity="0.20" stroke="{color}" stroke-width="2"/>')
        lines.append(f'<text x="{rect_x + 4:.2f}" y="{rect_y + 16:.2f}" font-family="Arial, sans-serif" font-size="12" fill="{color}">{node["id"]}</text>')
    for edge in graph["edges"]:
        center = edge.get("connector_center")
        if not center:
            continue
        px, py = map_point(center[0], center[2])
        color = "#fb7185" if edge["status"].startswith("WARN") else "#f9fafb"
        lines.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="5" fill="{color}"/>')
    lines.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_markdown(path: Path, report: dict, graph: dict) -> None:
    lines = [
        "# MX01 Traversal Graph Report",
        "",
        f"- Method: `{report['method']}`",
        f"- Status: `{report['status']}`",
        f"- Nodes: `{report['counts']['nodes']}`",
        f"- Edges: `{report['counts']['edges']}`",
        f"- Reachable decks: `{report['counts']['reachable_decks']} / {report['counts']['decks']}`",
        f"- Warning edges: `{report['counts']['warning_edges']}`",
        f"- Failing edges: `{report['counts']['failing_edges']}`",
        "",
        "## Edges",
        "",
    ]
    for edge in graph["edges"]:
        lines.append(f"- `{edge['id']}`: {edge['status']}, delta_y={edge['vertical_delta']}")
    lines.extend(["", "## Notes", "", report["notes"]])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    config_path = args.config.resolve()
    config = load_json(config_path)
    volume_path = resolve_config_path(config, "interior_volume_outputs", "volume_json")
    volume = load_json(volume_path)
    graph, report = build_graph(config, volume)

    graph_json = resolve_config_path(config, "traversal_outputs", "graph_json")
    report_json = resolve_config_path(config, "traversal_outputs", "report_json")
    report_md = resolve_config_path(config, "traversal_outputs", "report_md")
    projection_svg = resolve_config_path(config, "traversal_outputs", "projection_svg")
    manifest_json = resolve_config_path(config, "traversal_outputs", "manifest_json")

    report["source"] = {"interior_volume": rel(volume_path), "interior_volume_sha256": sha256(volume_path)}
    report["config"] = {"path": rel(config_path), "sha256": sha256(config_path), "effective_values": config}
    report["tools"] = {
        "fit_mx01_multilevel_traversal.py": {"path": rel(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())}
    }
    report["outputs"] = {"graph_json": rel(graph_json), "projection_svg": rel(projection_svg)}

    write_json(graph_json, graph)
    write_json(report_json, report)
    write_markdown(report_md, report, graph)
    draw_projection(projection_svg, graph)
    write_json(
        manifest_json,
        {
            "ship_id": config["ship_id"],
            "stage": "traversal_graph_fitting",
            "source": report["source"],
            "config": report["config"],
            "outputs": {
                "graph_json": rel(graph_json),
                "graph_json_sha256": sha256(graph_json),
                "report_json": rel(report_json),
                "report_md": rel(report_md),
                "projection_svg": rel(projection_svg),
            },
            "tools": report["tools"],
        },
    )
    print(f"Wrote {rel(graph_json)}")
    print(f"Wrote {rel(report_json)}")
    print(f"Wrote {rel(report_md)}")
    print(f"Wrote {rel(projection_svg)}")
    print(f"Wrote {rel(manifest_json)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
