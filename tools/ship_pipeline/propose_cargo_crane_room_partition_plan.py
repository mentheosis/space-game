#!/usr/bin/env python3
"""Propose a cheap 2D room partition plan for CargoCrane."""

from __future__ import annotations

import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "assets/source/blender/ships/cargo_crane/cargo_crane_interior_layout_contract.json"
SURFACES_PATH = ROOT / "assets/models/ship/cargo_crane/cargo_crane_traversal_surfaces.json"
OUT_DIR = ROOT / "reports/ship_pipeline/cargo_crane_room_partition_plan"
PLAN_JSON = OUT_DIR / "cargo_crane_room_partition_plan.json"
PLAN_MD = OUT_DIR / "cargo_crane_room_partition_plan.md"
PLAN_SVG = OUT_DIR / "cargo_crane_room_partition_plan_current.svg"


COLORS = {
    "floor": "#1f2937",
    "route": "#f8fafc",
    "engineering": "#7c3aed",
    "medical": "#ef4444",
    "living": "#22c55e",
    "atrium": "#f59e0b",
    "corridor": "#38bdf8",
    "cockpit": "#e5e7eb",
    "partition": "#111827",
    "door": "#fde68a",
    "hatch": "#fb923c",
    "mezzanine": "#facc15",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rect_from_bounds(name: str, bounds: dict, role: str, deck: str, notes: str = "") -> dict:
    bmin = bounds["min"]
    bmax = bounds["max"]
    return {
        "name": name,
        "role": role,
        "deck": deck,
        "bounds": {"min": [bmin[0], bmin[2]], "max": [bmax[0], bmax[2]]},
        "notes": notes,
    }


def make_plan(contract: dict, surfaces: dict) -> dict:
    regions = {region["id"]: region for region in contract["semantic_regions"]}

    zones = [
        rect_from_bounds(
            "Engine room",
            regions["aft_center_service"]["bounds"],
            "engineering",
            "lower_engine",
            "Open engineering/service room. Broad ramp transition remains unobstructed.",
        ),
        {
            "name": "Aft atrium lower floor",
            "role": "atrium",
            "deck": "main",
            "bounds": {"min": [-6.5, -28.7], "max": [6.5, -16.0]},
            "notes": "Open atrium behind the aft entrances and around the ramp to engineering.",
        },
        {
            "name": "Aft atrium mezzanine placeholder",
            "role": "mezzanine",
            "deck": "upper",
            "bounds": {"min": [-5.8, -27.0], "max": [5.8, -18.0]},
            "notes": "Planning placeholder for an upper overlook around the engineering ramp.",
        },
        {
            "name": "Starboard main corridor",
            "role": "corridor",
            "deck": "main",
            "bounds": {"min": [3.0, -16.0], "max": [6.5, 24.0]},
            "notes": "Primary side corridor around the living rooms and central medical suite.",
        },
        {
            "name": "Port medical corridor",
            "role": "corridor",
            "deck": "main",
            "bounds": {"min": [-6.5, 4.0], "max": [-3.6, 24.0]},
            "notes": "Port side of the corridor loop around the central medical suite.",
        },
        {
            "name": "Aft medical cross corridor",
            "role": "corridor",
            "deck": "main",
            "bounds": {"min": [-6.5, 2.0], "max": [6.5, 4.0]},
            "notes": "Aft side of the corridor loop around the central medical suite.",
        },
        {
            "name": "Forward center corridor",
            "role": "corridor",
            "deck": "main",
            "bounds": {"min": [-3.6, 24.0], "max": [3.0, 30.5]},
            "notes": "Forward side of the corridor loop, continuing into forward access.",
        },
        {
            "name": "Crew cabin A",
            "role": "living",
            "deck": "main",
            "bounds": {"min": [-6.5, -16.0], "max": [2.8, -10.0]},
            "notes": "Living room sized for bunk, closet, and compact shower.",
        },
        {
            "name": "Crew cabin B",
            "role": "living",
            "deck": "main",
            "bounds": {"min": [-6.5, -10.0], "max": [2.8, -4.0]},
            "notes": "Living room sized for bunk, closet, and compact shower.",
        },
        {
            "name": "Crew cabin C",
            "role": "living",
            "deck": "main",
            "bounds": {"min": [-6.5, -4.0], "max": [2.8, 2.0]},
            "notes": "Living room sized for bunk, closet, and compact shower.",
        },
        {
            "name": "Central medical suite",
            "role": "medical",
            "deck": "main",
            "bounds": {"min": [-3.6, 4.0], "max": [3.0, 22.0]},
            "notes": "One large central medical room/suite so the surrounding corridor loop stays intact.",
        },
        {
            "name": "Port forward exam room",
            "role": "medical",
            "deck": "main",
            "bounds": {"min": [-6.5, 24.0], "max": [-3.6, 30.5]},
            "notes": "Small forward medical room.",
        },
        {
            "name": "Starboard forward exam room",
            "role": "medical",
            "deck": "main",
            "bounds": {"min": [3.0, 24.0], "max": [6.5, 30.5]},
            "notes": "Small forward medical room.",
        },
        rect_from_bounds(
            "Forward access hallway",
            regions["forward_access"]["bounds"],
            "corridor",
            "main",
            "Narrow hallway between main body and cockpit.",
        ),
        rect_from_bounds(
            "Upper cockpit",
            regions["cockpit_upper_command_gallery"]["bounds"],
            "cockpit",
            "upper_cockpit",
            "Pilot/support seating deck. Stairs to lower cockpit remain clear.",
        ),
        rect_from_bounds(
            "Lower cockpit",
            regions["cockpit_lower"]["bounds"],
            "cockpit",
            "lower_cockpit",
            "Lower cockpit deck reached by paired side ramps/stairs.",
        ),
    ]

    partitions = [
        {
            "name": "living_to_starboard_corridor_wall",
            "kind": "longitudinal_wall",
            "from": [2.8, -16.0],
            "to": [2.8, 2.0],
            "door_gaps": [
                {"name": "Crew cabin A door", "center": [2.8, -13.0], "width": 1.8},
                {"name": "Crew cabin B door", "center": [2.8, -7.0], "width": 1.8},
                {"name": "Crew cabin C door", "center": [2.8, -1.0], "width": 1.8},
            ],
        },
        {
            "name": "atrium_to_room_block_frame",
            "kind": "transverse_bulkhead",
            "from": [-6.5, -16.0],
            "to": [6.5, -16.0],
            "door_gaps": [
                {"name": "Atrium to starboard corridor opening", "center": [4.8, -16.0], "width": 3.0},
                {"name": "Atrium to living door", "center": [-1.0, -16.0], "width": 2.4},
            ],
        },
        {"name": "living_room_split_a", "kind": "transverse_partition", "from": [-6.5, -10.0], "to": [2.8, -10.0], "door_gaps": []},
        {"name": "living_room_split_b", "kind": "transverse_partition", "from": [-6.5, -4.0], "to": [2.8, -4.0], "door_gaps": []},
        {"name": "living_to_medical_transition", "kind": "transverse_partition", "from": [-6.5, 2.0], "to": [6.5, 2.0], "door_gaps": [{"name": "Starboard corridor opening", "center": [4.8, 2.0], "width": 3.0}, {"name": "Port loop opening", "center": [-5.0, 2.0], "width": 2.4}]},
        {"name": "medical_aft_wall", "kind": "transverse_partition", "from": [-3.6, 4.0], "to": [3.0, 4.0], "door_gaps": [{"name": "Aft medical suite door", "center": [0.0, 4.0], "width": 2.6}]},
        {"name": "medical_port_wall", "kind": "longitudinal_wall", "from": [-3.6, 4.0], "to": [-3.6, 22.0], "door_gaps": [{"name": "Port medical suite door", "center": [-3.6, 12.0], "width": 2.4}]},
        {"name": "medical_starboard_wall", "kind": "longitudinal_wall", "from": [3.0, 4.0], "to": [3.0, 22.0], "door_gaps": [{"name": "Starboard medical suite door", "center": [3.0, 12.0], "width": 2.4}]},
        {"name": "medical_forward_wall", "kind": "transverse_partition", "from": [-3.6, 22.0], "to": [3.0, 22.0], "door_gaps": [{"name": "Forward medical suite door", "center": [0.0, 22.0], "width": 2.6}]},
        {"name": "medical_to_forward_rooms_frame", "kind": "transverse_partition", "from": [-6.5, 24.0], "to": [6.5, 24.0], "door_gaps": [{"name": "Forward center corridor opening", "center": [0.0, 24.0], "width": 6.6}, {"name": "Port forward med door", "center": [-5.0, 24.0], "width": 2.0}, {"name": "Starboard forward med door", "center": [5.0, 24.0], "width": 2.0}]},
        {"name": "port_forward_med_wall", "kind": "longitudinal_wall", "from": [-3.6, 24.0], "to": [-3.6, 30.5], "door_gaps": [{"name": "Port forward med corridor door", "center": [-3.6, 27.0], "width": 2.0}]},
        {"name": "starboard_forward_med_wall", "kind": "longitudinal_wall", "from": [3.0, 24.0], "to": [3.0, 30.5], "door_gaps": [{"name": "Starboard forward med corridor door", "center": [3.0, 27.0], "width": 2.0}]},
        {
            "name": "atrium_to_forward_access_frame",
            "kind": "transverse_frame",
            "from": [-6.5, 30.5],
            "to": [6.5, 30.5],
            "door_gaps": [{"name": "Forward access double door", "center": [0.0, 30.5], "width": 7.0}],
        },
        {
            "name": "forward_access_to_cockpit_frame",
            "kind": "transverse_frame",
            "from": [-3.5, 59.5],
            "to": [3.5, 59.5],
            "door_gaps": [{"name": "Cockpit pressure door", "center": [0.0, 59.5], "width": 4.0}],
        },
    ]

    hatches = []
    for hatch in contract["entrance_hatches"]:
        cx, _cy, cz = hatch["cut_center"]
        sx, _sy, sz = hatch["cut_size"]
        if cz < -16.0:
            proposed_zone = "Aft atrium lower floor"
        elif cz < 2.0:
            proposed_zone = "Starboard main corridor" if hatch["side"] == "starboard" else "Crew cabin C"
        elif hatch["side"] == "port":
            proposed_zone = "Port medical corridor"
        else:
            proposed_zone = "Starboard main corridor"
        hatches.append(
            {
                "name": hatch["name"],
                "side": hatch["side"],
                "center": [cx, cz],
                "clearance_size": [sx, sz],
                "target_room": hatch["target_room"],
                "proposed_zone": proposed_zone,
                "notes": "Keep partition-free clearance from hatch to nearest corridor or room door.",
            }
        )

    route = contract["player_traversal_validation"]["checkpoints"]
    proposed_route = [
        [0.0, -50.5],
        [0.0, -37.0],
        [0.0, -28.0],
        [0.0, -22.0],
        [4.8, -16.0],
        [4.8, -4.0],
        [4.8, 12.0],
        [4.8, 22.0],
        [4.8, 24.0],
        [3.2, 27.0],
        [0.0, 27.0],
        [0.0, 31.5],
        [0.0, 46.0],
        [0.0, 60.15],
        [0.0, 68.0],
    ]
    plan = {
        "schema_version": 1,
        "ship_id": "cargo_crane",
        "coordinate_space": "ship local top-down x/z plan",
        "source_contract": str(CONTRACT_PATH.relative_to(ROOT)),
        "source_surfaces": str(SURFACES_PATH.relative_to(ROOT)),
        "purpose": "cheap proposal for semantic room partitioning before 3D collision implementation",
        "zones": zones,
        "partitions": partitions,
        "hatches": hatches,
        "route_checkpoints": route,
        "proposed_primary_route": proposed_route,
        "acceptance_notes": [
            "Proposed side/center circulation route remains clear from engine ramp through forward access.",
            "Four side hatches remain traversible and are not crossed by partition walls.",
            "Room partitions are proposal geometry only; no 3D collision has been generated yet.",
            "Door gaps are intentionally oversized for first review.",
        ],
    }
    plan["validation"] = validate_plan(plan)
    return plan


def orientation(a: list[float], b: list[float], c: list[float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def interval_overlap(a0: float, a1: float, b0: float, b1: float) -> bool:
    amin, amax = sorted([a0, a1])
    bmin, bmax = sorted([b0, b1])
    return max(amin, bmin) <= min(amax, bmax)


def segments_intersect(a: list[float], b: list[float], c: list[float], d: list[float]) -> bool:
    if a[0] == b[0] == c[0] == d[0]:
        return interval_overlap(a[1], b[1], c[1], d[1])
    if a[1] == b[1] == c[1] == d[1]:
        return interval_overlap(a[0], b[0], c[0], d[0])
    o1 = orientation(a, b, c)
    o2 = orientation(a, b, d)
    o3 = orientation(c, d, a)
    o4 = orientation(c, d, b)
    return o1 * o2 <= 0 and o3 * o4 <= 0


def solid_partition_segments(plan: dict) -> list[dict]:
    solids = []
    for partition in plan["partitions"]:
        for start, end in split_line_segments(partition["from"], partition["to"], partition["door_gaps"]):
            solids.append({"partition": partition["name"], "from": start, "to": end})
    return solids


def validate_plan(plan: dict) -> dict:
    solids = solid_partition_segments(plan)
    route_points = plan.get("proposed_primary_route") or [
        [checkpoint["local_origin"][0], checkpoint["local_origin"][2]]
        for checkpoint in plan["route_checkpoints"]
    ]
    route_hits = []
    for index, (start, end) in enumerate(zip(route_points, route_points[1:])):
        for solid in solids:
            if segments_intersect(start, end, solid["from"], solid["to"]):
                route_hits.append({"route_segment": index, "partition": solid["partition"], "from": start, "to": end})

    hatch_notes = []
    for hatch in plan["hatches"]:
        if hatch["proposed_zone"] == "Aft atrium lower floor":
            access = "directly into the aft atrium, then up the central spine or down the engineering ramp"
        elif hatch["proposed_zone"] == "Port forward hatch vestibule":
            access = "through the port vestibule door into the central spine"
        elif hatch["proposed_zone"] == "Starboard forward hatch vestibule":
            access = "through the starboard vestibule door into the central spine"
        elif hatch["proposed_zone"] == "Medical ward":
            access = "via medical room doors into the central spine"
        elif hatch["proposed_zone"] == "Living quarters":
            access = "via living room doors into the central spine"
        else:
            access = "via local room door into the central spine"
        hatch_notes.append({"hatch": hatch["name"], "proposed_zone": hatch["proposed_zone"], "access": access})

    errors = []
    if route_hits:
        errors.append("Primary route intersects a solid partition segment.")
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "route_solid_partition_intersections": route_hits,
        "hatch_access_notes": hatch_notes,
    }


def transform(bounds: tuple[float, float, float, float], width: int, height: int, margin: int):
    min_x, max_x, min_z, max_z = bounds
    sx = (width - margin * 2) / (max_x - min_x)
    sz = (height - margin * 2) / (max_z - min_z)
    scale = min(sx, sz)

    def tx(x: float) -> float:
        return margin + (x - min_x) * scale

    def tz(z: float) -> float:
        return height - margin - (z - min_z) * scale

    return tx, tz, scale


def svg_rect(tx, tz, zone: dict, opacity: float = 0.72) -> str:
    bmin = zone["bounds"]["min"]
    bmax = zone["bounds"]["max"]
    x = tx(bmin[0])
    y = tz(bmax[1])
    w = tx(bmax[0]) - tx(bmin[0])
    h = tz(bmin[1]) - tz(bmax[1])
    color = COLORS.get(zone["role"], "#94a3b8")
    label_x = x + w * 0.5
    label_y = y + h * 0.5
    title = html.escape(zone["name"])
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'fill="{color}" fill-opacity="{opacity}" stroke="#0f172a" stroke-width="1.4"/>'
        f'<text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="middle" '
        f'class="label">{title}</text>'
    )


def split_line_segments(start: list[float], end: list[float], gaps: list[dict]) -> list[tuple[list[float], list[float]]]:
    if start[0] == end[0]:
        x = start[0]
        z0, z1 = sorted([start[1], end[1]])
        segments = [(z0, z1)]
        for gap in gaps:
            center_z = gap["center"][1]
            half = gap["width"] * 0.5
            next_segments = []
            for a, b in segments:
                if center_z + half <= a or center_z - half >= b:
                    next_segments.append((a, b))
                    continue
                if center_z - half > a:
                    next_segments.append((a, center_z - half))
                if center_z + half < b:
                    next_segments.append((center_z + half, b))
            segments = next_segments
        return [([x, a], [x, b]) for a, b in segments if b - a > 0.05]

    z = start[1]
    x0, x1 = sorted([start[0], end[0]])
    segments = [(x0, x1)]
    for gap in gaps:
        center_x = gap["center"][0]
        half = gap["width"] * 0.5
        next_segments = []
        for a, b in segments:
            if center_x + half <= a or center_x - half >= b:
                next_segments.append((a, b))
                continue
            if center_x - half > a:
                next_segments.append((a, center_x - half))
            if center_x + half < b:
                next_segments.append((center_x + half, b))
        segments = next_segments
    return [([a, z], [b, z]) for a, b in segments if b - a > 0.05]


def render_svg(plan: dict) -> str:
    width = 1080
    height = 1560
    bounds = (-13.0, 13.0, -66.0, 75.0)
    tx, tz, _scale = transform(bounds, width, height, 64)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        ".title{font:700 28px sans-serif;fill:#0f172a}",
        ".subtitle{font:15px sans-serif;fill:#334155}",
        ".label{font:700 12px sans-serif;fill:#0f172a;paint-order:stroke;stroke:#f8fafc;stroke-width:3px;stroke-linejoin:round}",
        ".small{font:12px sans-serif;fill:#0f172a}",
        ".door{font:11px sans-serif;fill:#92400e}",
        "</style>",
        '<rect x="0" y="0" width="1080" height="1560" fill="#f8fafc"/>',
        '<text x="64" y="42" class="title">CargoCrane semantic room partition proposal</text>',
        '<text x="64" y="66" class="subtitle">Top-down ship-local plan: horizontal = X, vertical = Z/cockpit forward</text>',
    ]

    floor_zones = [
        {
            "name": "Engine floor",
            "role": "floor",
            "bounds": {"min": [-6.5, -63.5], "max": [6.5, -36.8]},
        },
        {
            "name": "Main body",
            "role": "floor",
            "bounds": {"min": [-6.5, -28.7], "max": [6.5, 30.5]},
        },
        {
            "name": "Forward access",
            "role": "floor",
            "bounds": {"min": [-3.5, 29.5], "max": [3.5, 59.5]},
        },
        {
            "name": "Cockpit upper",
            "role": "floor",
            "bounds": {"min": [-4.25, 59.5], "max": [4.25, 70.0]},
        },
        {
            "name": "Cockpit lower",
            "role": "floor",
            "bounds": {"min": [-3.7, 64.0], "max": [3.7, 72.5]},
        },
    ]
    for zone in floor_zones:
        parts.append(svg_rect(tx, tz, zone, 0.12))

    for zone in plan["zones"]:
        parts.append(svg_rect(tx, tz, zone, 0.64 if zone["role"] != "mezzanine" else 0.28))

    route_points = [
        [point[0], 0.0, point[1]]
        for point in plan.get("proposed_primary_route", [])
    ]
    if not route_points:
        route_points = [checkpoint["local_origin"] for checkpoint in plan["route_checkpoints"]]
    if route_points:
        coords = " ".join(f"{tx(p[0]):.1f},{tz(p[2]):.1f}" for p in route_points)
        parts.append(f'<polyline points="{coords}" fill="none" stroke="{COLORS["route"]}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>')
        parts.append('<polyline points="' + coords + '" fill="none" stroke="#0f172a" stroke-width="2" stroke-dasharray="7 5" stroke-linecap="round" stroke-linejoin="round"/>')

    for partition in plan["partitions"]:
        for seg_start, seg_end in split_line_segments(partition["from"], partition["to"], partition["door_gaps"]):
            parts.append(
                f'<line x1="{tx(seg_start[0]):.1f}" y1="{tz(seg_start[1]):.1f}" '
                f'x2="{tx(seg_end[0]):.1f}" y2="{tz(seg_end[1]):.1f}" '
                f'stroke="{COLORS["partition"]}" stroke-width="5" stroke-linecap="square"/>'
            )
        for gap in partition["door_gaps"]:
            x = tx(gap["center"][0])
            y = tz(gap["center"][1])
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="{COLORS["door"]}" stroke="#92400e" stroke-width="2"/>')

    for hatch in plan["hatches"]:
        cx, cz = hatch["center"]
        x = tx(cx)
        y = tz(cz)
        parts.append(f'<rect x="{x - 10:.1f}" y="{y - 18:.1f}" width="20" height="36" fill="{COLORS["hatch"]}" stroke="#7c2d12" stroke-width="2"/>')
        parts.append(f'<text x="{x:.1f}" y="{y - 24:.1f}" text-anchor="middle" class="door">{html.escape(hatch["name"])}</text>')

    legend_x = 720
    legend_y = 104
    parts.append(f'<rect x="{legend_x - 20}" y="{legend_y - 34}" width="300" height="248" fill="#ffffff" stroke="#cbd5e1"/>')
    parts.append(f'<text x="{legend_x}" y="{legend_y - 10}" class="small" font-weight="700">Legend</text>')
    for index, (label, role) in enumerate(
        [
            ("Engineering", "engineering"),
            ("Medical", "medical"),
            ("Living", "living"),
            ("Atrium", "atrium"),
            ("Corridor", "corridor"),
            ("Cockpit", "cockpit"),
            ("Mezzanine placeholder", "mezzanine"),
            ("Door gap", "door"),
            ("External hatch", "hatch"),
        ]
    ):
        y = legend_y + 18 + index * 23
        parts.append(f'<rect x="{legend_x}" y="{y - 12}" width="18" height="14" fill="{COLORS[role]}" stroke="#0f172a" stroke-width="0.6"/>')
        parts.append(f'<text x="{legend_x + 28}" y="{y}" class="small">{label}</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def write_markdown(plan: dict) -> str:
    lines = [
        "# CargoCrane Room Partition Plan",
        "",
        "Cheap 2D proposal before 3D partition collision generation.",
        "",
        "## Zones",
        "",
    ]
    for zone in plan["zones"]:
        lines.append(f"- **{zone['name']}** ({zone['role']}): `{zone['bounds']}`. {zone['notes']}")
    lines.extend(["", "## Partitions And Doors", ""])
    for partition in plan["partitions"]:
        door_names = ", ".join(gap["name"] for gap in partition["door_gaps"]) or "none"
        lines.append(f"- **{partition['name']}**: `{partition['from']}` to `{partition['to']}`; gaps: {door_names}.")
    lines.extend(["", "## Hatch Clearances", ""])
    for hatch in plan["hatches"]:
        lines.append(f"- **{hatch['name']}** ({hatch['side']}): enters proposed zone `{hatch['proposed_zone']}` at `{hatch['center']}`.")
    lines.extend(["", "## Cheap Validation", ""])
    lines.append(f"- Status: **{plan['validation']['status']}**")
    lines.append(f"- Primary route solid partition intersections: `{len(plan['validation']['route_solid_partition_intersections'])}`")
    for note in plan["validation"]["hatch_access_notes"]:
        lines.append(f"- **{note['hatch']}**: {note['access']}.")
    lines.extend(["", "## Acceptance Notes", ""])
    for note in plan["acceptance_notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    contract = load_json(CONTRACT_PATH)
    surfaces = load_json(SURFACES_PATH)
    plan = make_plan(contract, surfaces)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PLAN_JSON.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    PLAN_MD.write_text(write_markdown(plan), encoding="utf-8")
    PLAN_SVG.write_text(render_svg(plan), encoding="utf-8")
    print(f"Wrote {PLAN_JSON.relative_to(ROOT)}")
    print(f"Wrote {PLAN_MD.relative_to(ROOT)}")
    print(f"Wrote {PLAN_SVG.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
