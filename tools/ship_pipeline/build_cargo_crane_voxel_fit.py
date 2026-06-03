#!/usr/bin/env python3
"""Build CargoCrane voxel/free-space evidence from the approved exterior GLB."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import build_shuttle_p3_from_exterior_glb as ship_voxels


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "assets/source/blender/ships/cargo_crane/cargo_crane_interior_layout_contract.json"
OUT_REPORT_DIR = ROOT / "reports/ship_pipeline/cargo_crane_voxel_fit"
REPORT_JSON = OUT_REPORT_DIR / "cargo_crane_voxel_report.json"
REPORT_MD = OUT_REPORT_DIR / "cargo_crane_voxel_report.md"
FULL_COMPACT_JSON = OUT_REPORT_DIR / "cargo_crane_voxels_full_compact.json"
LLM_SERIALIZED_JSON = OUT_REPORT_DIR / "cargo_crane_voxel_serialized_for_llm.json"
VOXEL_PNG = OUT_REPORT_DIR / "cargo_crane_voxel_free_space_projection_current.png"
SEMANTIC_PNG = OUT_REPORT_DIR / "cargo_crane_semantic_regions_projection_current.png"


REGION_COLORS = {
    "lower_deck_corridor_spine": (85, 185, 225),
    "medical": (220, 90, 110),
    "living_quarters": (110, 205, 130),
    "atrium_lower": (235, 180, 75),
    "aft_to_central_transition": (65, 235, 220),
    "engine_room": (205, 120, 235),
    "mezzanine": (255, 220, 95),
    "central_service_spine": (65, 235, 220),
    "central_to_cockpit_transition": (65, 235, 220),
    "cockpit_descent_transition": (65, 235, 220),
    "cockpit_access": (125, 155, 255),
    "cockpit": (255, 245, 150),
}


def load_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def voxel_config(contract: dict) -> dict:
    voxelization = contract["voxelization"]
    capsule = contract["player_capsule"]
    return {
        "voxel_size": voxelization["voxel_size"],
        "local_refine_voxel_size": voxelization["local_refine_voxel_size"],
        "player_capsule_radius": capsule["radius"],
        "standing_height": capsule["height"],
        "clearance_margin": voxelization["clearance_margin"],
        "shell_margin": voxelization["shell_margin"],
        "central_x_quantiles": voxelization["central_x_quantiles"],
        "central_y_quantiles": voxelization["central_y_quantiles"],
    }


def distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def collect_surface_samples(gltf: dict, bin_chunk: bytes, spacing: float) -> list[tuple[float, float, float]]:
    """Sample triangle interiors so long low-vertex hull faces contribute to slice profiles."""
    samples: list[tuple[float, float, float]] = []
    sample_spacing = max(0.5, spacing)
    max_subdivisions = 12
    for mesh in gltf.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            position_index = primitive.get("attributes", {}).get("POSITION")
            if position_index is None:
                continue
            positions = ship_voxels.accessor_vec3(gltf, bin_chunk, position_index)
            for index in range(0, len(positions) - 2, 3):
                a = positions[index]
                b = positions[index + 1]
                c = positions[index + 2]
                samples.extend((a, b, c))
                max_edge = max(distance(a, b), distance(b, c), distance(c, a))
                subdivisions = min(max_subdivisions, max(1, int(max_edge / sample_spacing + 0.999)))
                if subdivisions <= 1:
                    continue
                for u_index in range(subdivisions + 1):
                    for v_index in range(subdivisions + 1 - u_index):
                        if u_index == 0 and v_index == 0:
                            continue
                        u = u_index / subdivisions
                        v = v_index / subdivisions
                        w = 1.0 - u - v
                        if w < -0.000001:
                            continue
                        samples.append(
                            (
                                a[0] * w + b[0] * u + c[0] * v,
                                a[1] * w + b[1] * u + c[1] * v,
                                a[2] * w + b[2] * u + c[2] * v,
                            )
                        )
    return samples


def apply_interior_envelope(profiles: list[dict], contract: dict) -> list[dict]:
    envelope = contract.get("voxelization", {}).get("interior_envelope", [])
    if not envelope:
        return profiles

    clamped = []
    for profile in profiles:
        z = profile["z"]
        matching = [entry for entry in envelope if entry["z_min"] <= z <= entry["z_max"]]
        if not matching:
            continue
        entry = matching[0]
        adjusted = dict(profile)
        adjusted["x_min"] = max(float(adjusted["x_min"]), float(entry["x_min"]))
        adjusted["x_max"] = min(float(adjusted["x_max"]), float(entry["x_max"]))
        adjusted["y_min"] = max(float(adjusted["y_min"]), float(entry["y_min"]))
        adjusted["y_max"] = min(float(adjusted["y_max"]), float(entry["y_max"]))
        adjusted["source"] = f"{profile.get('source', 'sampled')}_interior_envelope"
        if adjusted["x_max"] > adjusted["x_min"] and adjusted["y_max"] > adjusted["y_min"]:
            clamped.append(adjusted)
    return clamped


def contract_regions(contract: dict) -> list[dict]:
    return contract.get("semantic_regions", [])


def point_in_bounds(point: list[float], bounds: dict) -> bool:
    return all(bounds["min"][axis] <= point[axis] <= bounds["max"][axis] for axis in range(3))


def region_ids_for_voxel(voxel: dict, regions: list[dict]) -> list[str]:
    center = voxel["center"]
    return [region["id"] for region in regions if point_in_bounds(center, region["bounds"])]


def summarize_regions(voxels: list[dict], regions: list[dict]) -> list[dict]:
    summaries = []
    for region in regions:
        selected = [voxel for voxel in voxels if point_in_bounds(voxel["center"], region["bounds"])]
        standing = [voxel for voxel in selected if voxel["can_stand"]]
        summary = {
            "id": region["id"],
            "label": region.get("label", region["id"]),
            "level": region.get("level"),
            "roles": region.get("roles", []),
            "contract_bounds": region["bounds"],
            "voxel_count": len(selected),
            "standing_voxel_count": len(standing),
            "status": "PASS" if standing else "NO_STANDING_VOXELS",
        }
        if selected:
            mins = [min(voxel["center"][axis] for voxel in selected) for axis in range(3)]
            maxs = [max(voxel["center"][axis] for voxel in selected) for axis in range(3)]
            summary["sampled_bounds"] = {"min": [round(v, 4) for v in mins], "max": [round(v, 4) for v in maxs]}
        summaries.append(summary)
    return summaries


def entrance_summaries(voxels: list[dict], contract: dict) -> list[dict]:
    results = []
    for entrance in contract.get("entrance_hatches", []):
        cx, cy, cz = entrance["cut_center"]
        sx, sy, sz = entrance["cut_size"]
        bounds = {
            "min": [cx - sx * 0.5 - 2.0, cy - sy * 0.5, cz - sz * 0.5],
            "max": [cx + sx * 0.5 + 2.0, cy + sy * 0.5, cz + sz * 0.5],
        }
        selected = [voxel for voxel in voxels if point_in_bounds(voxel["center"], bounds)]
        standing = [voxel for voxel in selected if voxel["can_stand"]]
        results.append(
            {
                "name": entrance["name"],
                "side": entrance["side"],
                "cut_center": entrance["cut_center"],
                "cut_size": entrance["cut_size"],
                "nearby_voxel_count": len(selected),
                "nearby_standing_voxel_count": len(standing),
                "status": "PASS" if standing else "NEEDS_CUT_OR_RAMP_REVIEW",
            }
        )
    return results


def semantic_connectivity(voxels: list[dict], regions: list[dict], contract: dict) -> dict:
    standing_by_region: dict[str, list[list[float]]] = defaultdict(list)
    for voxel in voxels:
        if not voxel["can_stand"]:
            continue
        for region_id in region_ids_for_voxel(voxel, regions):
            standing_by_region[region_id].append(voxel["center"])

    edges = []
    max_handoff_distance = float(contract.get("semantic_connectivity", {}).get("max_handoff_distance", 2.25))
    for pair in contract.get("semantic_connection_targets", []):
        if not isinstance(pair, list) or len(pair) != 2:
            continue
        a, b = pair
        a_points = standing_by_region.get(a, [])
        b_points = standing_by_region.get(b, [])
        best_distance = None
        if a_points and b_points:
            # The connector lists are small enough for direct pair search at 1m evidence resolution.
            best_distance = min(
                (
                    ((ap[0] - bp[0]) ** 2 + (ap[1] - bp[1]) ** 2 + (ap[2] - bp[2]) ** 2) ** 0.5
                    for ap in a_points
                    for bp in b_points
                ),
                default=None,
            )
        status = "PASS" if best_distance is not None and best_distance <= max_handoff_distance else "FAIL"
        edges.append(
            {
                "from": a,
                "to": b,
                "from_standing_voxels": len(a_points),
                "to_standing_voxels": len(b_points),
                "nearest_standing_distance": round(best_distance, 4) if best_distance is not None else None,
                "max_handoff_distance": max_handoff_distance,
                "status": status,
            }
        )
    return {
        "status": "PASS" if all(edge["status"] == "PASS" for edge in edges) else "FAIL",
        "edges": edges,
    }


def slice_summary(voxels: list[dict], regions: list[dict], voxel_size: float) -> list[dict]:
    by_z: dict[float, list[dict]] = defaultdict(list)
    for voxel in voxels:
        by_z[voxel["center"][2]].append(voxel)
    summaries = []
    for z, items in sorted(by_z.items()):
        standing = [voxel for voxel in items if voxel["can_stand"]]
        if not standing:
            continue
        region_counts: Counter[str] = Counter()
        for voxel in standing:
            region_counts.update(region_ids_for_voxel(voxel, regions))
        summaries.append(
            {
                "z": round(z, 4),
                "standing_count": len(standing),
                "x_min": round(min(voxel["center"][0] for voxel in standing), 4),
                "x_max": round(max(voxel["center"][0] for voxel in standing), 4),
                "y_min": round(min(voxel["center"][1] for voxel in standing), 4),
                "y_max": round(max(voxel["center"][1] for voxel in standing), 4),
                "region_counts": dict(sorted(region_counts.items())),
            }
        )
    # Keep LLM evidence compact on large ships.
    if len(summaries) <= 80:
        return summaries
    step = max(1, len(summaries) // 80)
    compact = summaries[::step]
    if compact[-1] != summaries[-1]:
        compact.append(summaries[-1])
    return compact


def draw_projection(path: Path, points: list[tuple[float, float, float]], voxels: list[dict], regions: list[dict], semantic: bool) -> None:
    canvas = ship_voxels.ImageCanvas(1920, 720, (12, 15, 19))
    panels = [(24, 36, 604, 648, (2, 1)), (658, 36, 604, 648, (2, 0)), (1292, 36, 604, 648, (0, 1))]
    all_points = list(points) + [tuple(voxel["center"]) for voxel in voxels]

    for px, py, pw, ph, axes in panels:
        canvas.rect(px, py, px + pw - 1, py + ph - 1, (40, 46, 54))
        coords = [(point[axes[0]], point[axes[1]]) for point in all_points]
        min_x, max_x = min(c[0] for c in coords) - 3.0, max(c[0] for c in coords) + 3.0
        min_y, max_y = min(c[1] for c in coords) - 3.0, max(c[1] for c in coords) + 3.0

        def map_point(x: float, y: float) -> tuple[int, int]:
            sx = int(px + (x - min_x) / max(0.001, max_x - min_x) * (pw - 1))
            sy = int(py + (1.0 - (y - min_y) / max(0.001, max_y - min_y)) * (ph - 1))
            return sx, sy

        sample_step = max(1, len(points) // 70000)
        for point in points[::sample_step]:
            sx, sy = map_point(point[axes[0]], point[axes[1]])
            canvas.set_pixel(sx, sy, (195, 205, 215))

        for voxel in voxels:
            sx, sy = map_point(voxel["center"][axes[0]], voxel["center"][axes[1]])
            color = (75, 155, 210) if voxel["can_stand"] else (45, 75, 100)
            if semantic:
                ids = region_ids_for_voxel(voxel, regions)
                if ids:
                    color = REGION_COLORS.get(ids[-1], (210, 210, 210))
            canvas.rect(sx - 1, sy - 1, sx + 1, sy + 1, color, fill=True)

        if semantic:
            for region in regions:
                color = REGION_COLORS.get(region["id"], (230, 230, 230))
                bmin = region["bounds"]["min"]
                bmax = region["bounds"]["max"]
                if axes == (2, 1):
                    corners = [(bmin[2], bmin[1]), (bmax[2], bmin[1]), (bmax[2], bmax[1]), (bmin[2], bmax[1])]
                elif axes == (2, 0):
                    corners = [(bmin[2], bmin[0]), (bmax[2], bmin[0]), (bmax[2], bmax[0]), (bmin[2], bmax[0])]
                else:
                    corners = [(bmin[0], bmin[1]), (bmax[0], bmin[1]), (bmax[0], bmax[1]), (bmin[0], bmax[1])]
                mapped = [map_point(x, y) for x, y in corners]
                for index, start in enumerate(mapped):
                    end = mapped[(index + 1) % len(mapped)]
                    canvas.line(start[0], start[1], end[0], end[1], color)
                    canvas.line(start[0] + 1, start[1], end[0] + 1, end[1], color)

    canvas.write_png(path)


def write_outputs(
    contract: dict,
    points: list[tuple[float, float, float]],
    profile_points: list[tuple[float, float, float]],
    profiles: list[dict],
    voxels: list[dict],
    regions: list[dict],
) -> None:
    OUT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    region_summaries = summarize_regions(voxels, regions)
    entrances = entrance_summaries(voxels, contract)
    connectivity = semantic_connectivity(voxels, regions, contract)
    standing_voxel_count = sum(1 for voxel in voxels if voxel["can_stand"])
    region_failures = [summary for summary in region_summaries if summary["status"] != "PASS"]
    entrance_failures = [summary for summary in entrances if summary["status"] != "PASS"]
    status = "PASS" if standing_voxel_count and not region_failures and not entrance_failures and connectivity["status"] == "PASS" else "NEEDS_REVIEW"

    compact_voxels = [
        [
            voxel["center"][0],
            voxel["center"][1],
            voxel["center"][2],
            voxel["can_stand"],
            voxel["head_clearance"],
            region_ids_for_voxel(voxel, regions),
        ]
        for voxel in voxels
    ]
    FULL_COMPACT_JSON.write_text(json.dumps(compact_voxels, separators=(",", ":")) + "\n", encoding="utf-8")
    serialized = {
        "schema_version": 1,
        "ship_id": "cargo_crane",
        "coordinate_space": "ship local, +Y up, +Z forward",
        "voxel_format": "[x, y, z, can_stand, head_clearance, semantic_region_ids]",
        "voxel_size": contract["voxelization"]["voxel_size"],
        "standing_voxel_count": standing_voxel_count,
        "slice_summary": slice_summary(voxels, regions, float(contract["voxelization"]["voxel_size"])),
        "semantic_region_summaries": region_summaries,
        "entrance_summaries": entrances,
        "semantic_connectivity": connectivity,
    }
    LLM_SERIALIZED_JSON.write_text(json.dumps(serialized, indent=2) + "\n", encoding="utf-8")

    draw_projection(VOXEL_PNG, points, voxels, regions, semantic=False)
    draw_projection(SEMANTIC_PNG, points, voxels, regions, semantic=True)

    report = {
        "schema_version": 1,
        "ship_id": "cargo_crane",
        "status": status,
        "contract": str(CONTRACT_PATH.relative_to(ROOT)),
        "exterior_glb": contract["source_assets"]["exterior_glb"],
        "exterior_bounds": ship_voxels.bounds(points),
        "slice_profile_count": len(profiles),
        "profile_sample_count": len(profile_points),
        "voxel_count": len(voxels),
        "standing_voxel_count": standing_voxel_count,
        "semantic_region_summaries": region_summaries,
        "entrance_summaries": entrances,
        "semantic_connectivity": connectivity,
        "evidence": {
            "voxel_projection": str(VOXEL_PNG.relative_to(ROOT)),
            "semantic_projection": str(SEMANTIC_PNG.relative_to(ROOT)),
            "full_compact_voxels": str(FULL_COMPACT_JSON.relative_to(ROOT)),
            "llm_serialized": str(LLM_SERIALIZED_JSON.relative_to(ROOT)),
        },
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# CargoCrane Voxel Fit Report",
        "",
        f"Status: **{status}**",
        "",
        f"- Exterior GLB: `{contract['source_assets']['exterior_glb']}`",
        f"- Contract: `{CONTRACT_PATH.relative_to(ROOT)}`",
        f"- Slice profiles: `{len(profiles)}`",
        f"- Profile samples: `{len(profile_points)}`",
        f"- Voxels: `{len(voxels)}`",
        f"- Standing voxels: `{standing_voxel_count}`",
        f"- Voxel projection: `{VOXEL_PNG.relative_to(ROOT)}`",
        f"- Semantic projection: `{SEMANTIC_PNG.relative_to(ROOT)}`",
        "",
        "## Semantic Regions",
        "",
    ]
    for summary in region_summaries:
        lines.append(
            f"- `{summary['id']}` {summary['status']}: voxels={summary['voxel_count']} "
            f"standing={summary['standing_voxel_count']} level={summary.get('level')}"
        )
    lines += ["", "## Entrances", ""]
    for entrance in entrances:
        lines.append(
            f"- `{entrance['name']}` {entrance['status']}: nearby={entrance['nearby_voxel_count']} "
            f"standing={entrance['nearby_standing_voxel_count']} center={entrance['cut_center']}"
        )
    lines += ["", "## Semantic Connectivity", ""]
    for edge in connectivity["edges"]:
        lines.append(
            f"- `{edge['from']}` -> `{edge['to']}` {edge['status']}: "
            f"nearest={edge['nearest_standing_distance']}m "
            f"from_standing={edge['from_standing_voxels']} to_standing={edge['to_standing_voxels']}"
        )
    if status != "PASS":
        lines += [
            "",
            "## Review Notes",
            "",
            "- Any `NO_STANDING_VOXELS`, `NEEDS_CUT_OR_RAMP_REVIEW`, or failed semantic connectivity item must be addressed before traversal surface generation.",
        ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    contract = load_contract()
    source_glb = ROOT / contract["source_assets"]["exterior_glb"]
    gltf, bin_chunk = ship_voxels.read_glb(source_glb)
    points = ship_voxels.collect_vertices(gltf, bin_chunk)
    config = voxel_config(contract)
    profile_points = collect_surface_samples(gltf, bin_chunk, float(config["voxel_size"]))
    profiles = ship_voxels.sample_profiles(profile_points, config)
    profiles = apply_interior_envelope(profiles, contract)
    voxels = ship_voxels.generate_voxels(profiles, config)
    write_outputs(contract, points, profile_points, profiles, voxels, contract_regions(contract))
    print(f"Wrote {REPORT_JSON.relative_to(ROOT)}")
    print(f"Wrote {REPORT_MD.relative_to(ROOT)}")
    print(f"Wrote {FULL_COMPACT_JSON.relative_to(ROOT)}")
    print(f"Wrote {LLM_SERIALIZED_JSON.relative_to(ROOT)}")
    print(f"Wrote {VOXEL_PNG.relative_to(ROOT)}")
    print(f"Wrote {SEMANTIC_PNG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
