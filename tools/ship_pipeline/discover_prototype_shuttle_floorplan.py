#!/usr/bin/env python3
"""Search for a traversable prototype shuttle floorplan candidate."""

from __future__ import annotations

import argparse
import itertools
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DISCOVERY_DIR = ROOT / "reports/ship_pipeline/prototype_shuttle_floorplan_discovery"
CANDIDATE_DIR = DISCOVERY_DIR / "candidates"
REPORT_JSON = DISCOVERY_DIR / "floorplan_discovery_report.json"
REPORT_MD = DISCOVERY_DIR / "floorplan_discovery_report.md"
LAYOUT_REPORT = ROOT / "assets/models/ship/prototype_shuttle/prototype_shuttle_collision_layout_report.json"
STATIC_REPORT = ROOT / "reports/ship_pipeline/prototype_shuttle_collision_layout_validation_report.json"
TRAVERSAL_REPORT = ROOT / "reports/ship_pipeline/prototype_shuttle_traversal_validation_report.json"
GOLDEN_DIR = ROOT / "assets/models/ship/prototype_shuttle/golden_baselines/human_approved_walkable_v1"
GOLDEN_LAYOUT = GOLDEN_DIR / "collision_layout_report.json"
GOLDEN_CANDIDATE = GOLDEN_DIR / "floorplan_candidate.json"

DEFAULT_CANDIDATE: dict[str, Any] = {
    "id": "candidate",
    "ramp_floor_edge_z_offset": 1.25,
    "ramp_hinge_y_offset": -0.06,
    "ramp_tip_y_delta": -1.98,
    "ramp_tip_z_delta": -3.95,
    "ramp_aperture_z_min_delta": -1.45,
    "ramp_aperture_z_max_from_original_floor": 0.80,
    "ramp_aperture_z_max_delta": 0.65,
    "cargo_forward_floor_trim": 1.25,
    "stair_count": 10,
    "stair_depth_scale": 1.08,
    "stair_width": 1.0,
    "stair_lane_gap": 0.18,
    "cockpit_entry_depth": 3.2,
    "cockpit_entry_z_bias": -0.42,
}


def run(command: list[str], env: dict[str, str], log_path: Path) -> tuple[bool, str]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(completed.stdout, encoding="utf-8")
    return completed.returncode == 0, completed.stdout


def candidate_grid(limit: int, blind: bool = False) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    def add(candidate_id: str, **overrides: Any) -> None:
        candidate = dict(DEFAULT_CANDIDATE)
        candidate.update(overrides)
        candidate["id"] = candidate_id
        candidates.append(candidate)

    if not blind:
        add("golden_like")
    add("reject_shallow_landing", cockpit_entry_depth=0.8)
    add("reject_small_cargo_trim", cargo_forward_floor_trim=0.55)
    add("reject_upward_ramp_lip", ramp_hinge_y_offset=0.30)
    add("reject_too_few_steps", stair_count=5)
    add("reject_narrow_stair_lane", stair_lane_gap=-0.18)

    if blind:
        landing_depths = [2.4, 2.8, 3.2, 2.0, 3.6, 1.6]
        ramp_offsets = [-0.12, -0.06, 0.00, -0.18, 0.08]
        trims = [1.00, 1.25, 1.40, 0.85, 1.60]
        stair_counts = [9, 10, 11, 8, 12]
        lane_gaps = [0.12, 0.18, 0.26, 0.04, 0.34]
    else:
        landing_depths = [1.6, 2.4, 3.2]
        ramp_offsets = [-0.14, -0.06, 0.00]
        trims = [0.95, 1.25]
        stair_counts = [8, 10]
        lane_gaps = [0.10, 0.18]

    grid_values = list(itertools.product(landing_depths, ramp_offsets, trims, stair_counts, lane_gaps))
    if blind:
        index_rank = {
            "landing": {value: index for index, value in enumerate(landing_depths)},
            "ramp": {value: index for index, value in enumerate(ramp_offsets)},
            "trim": {value: index for index, value in enumerate(trims)},
            "stair": {value: index for index, value in enumerate(stair_counts)},
            "gap": {value: index for index, value in enumerate(lane_gaps)},
        }
        grid_values.sort(
            key=lambda values: (
                index_rank["landing"][values[0]]
                + index_rank["ramp"][values[1]]
                + index_rank["trim"][values[2]]
                + index_rank["stair"][values[3]]
                + index_rank["gap"][values[4]],
                values,
            )
        )

    for index, values in enumerate(grid_values, start=1):
        landing_depth, ramp_offset, trim, stair_count, lane_gap = values
        add(
            f"grid_{index:03d}",
            cockpit_entry_depth=landing_depth,
            ramp_hinge_y_offset=ramp_offset,
            cargo_forward_floor_trim=trim,
            stair_count=stair_count,
            stair_lane_gap=lane_gap,
        )
        if len(candidates) >= limit:
            break

    return candidates[:limit]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def numeric_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    total = 0.0
    for key, value in DEFAULT_CANDIDATE.items():
        if key == "id" or isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        total += abs(float(a.get(key, value)) - float(b.get(key, value)))
    return round(total, 5)


def surface_lookup(layout: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(surface.get("id")): surface for surface in layout.get("surfaces", []) if isinstance(surface, dict)}


def top_y(surface: dict[str, Any]) -> float:
    center = surface["center"]
    size = surface["size"]
    return float(center[1]) + float(size[1]) * 0.5


def interior_bounds_penalty(layout: dict[str, Any]) -> float:
    """Broad proxy that discourages candidate floors outside the usable hull envelope."""
    penalty = 0.0
    bounds = {
        0: (-4.8, 4.8),
        1: (-15.0, 13.0),
        2: (-22.0, 14.5),
    }
    for surface in layout.get("surfaces", []):
        if not isinstance(surface, dict):
            continue
        center = surface.get("center")
        size = surface.get("size")
        if not isinstance(center, list) or not isinstance(size, list):
            continue
        for axis, (minimum, maximum) in bounds.items():
            low = float(center[axis]) - float(size[axis]) * 0.5
            high = float(center[axis]) + float(size[axis]) * 0.5
            penalty += max(0.0, minimum - low)
            penalty += max(0.0, high - maximum)
    return penalty


def score_candidate(
    candidate: dict[str, Any],
    static_pass: bool,
    traversal_pass: bool,
    layout: dict[str, Any] | None,
    traversal: dict[str, Any] | None = None,
) -> float:
    if not static_pass:
        return 0.0

    score = 100.0
    if traversal_pass:
        score += 1000.0
    score += min(3.2, float(candidate["cockpit_entry_depth"])) * 12.0
    score -= max(0.0, 10 - int(candidate["stair_count"])) * 4.0
    score -= abs(float(candidate["ramp_hinge_y_offset"])) * 20.0

    if layout is not None:
        surfaces = surface_lookup(layout)
        special_case_panel_count = sum(1 for surface_id in ["forward_belly_ramp", "cockpit_entry_landing"] if surface_id in surfaces)
        score -= special_case_panel_count * 1.0
        ramp = surfaces.get("forward_belly_ramp")
        cargo = surfaces.get("cargo_forward_lower")
        if ramp is not None and cargo is not None:
            hinge = ramp["hinge"]
            lip = float(hinge[1]) - top_y(cargo)
            score -= abs(lip) * 20.0
        score -= interior_bounds_penalty(layout) * 5.0

    if traversal is not None:
        score -= float(traversal.get("auto_step_count", 0)) * 2.0
        score -= max(0.0, float(traversal.get("frames", 0)) - 109.0) * 0.05

    return round(score, 4)


def copy_result(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def evaluate_candidate(candidate: dict[str, Any], run_traversal: bool, build_import: bool, save_active: bool = False) -> dict[str, Any]:
    candidate_path = CANDIDATE_DIR / f"{candidate['id']}.json"
    candidate_path.write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8")
    env = os.environ.copy()
    env["PROTOTYPE_SHUTTLE_FLOORPLAN_CANDIDATE"] = str(candidate_path)
    if save_active:
        env["PROTOTYPE_SHUTTLE_SAVE_ACTIVE_FLOORPLAN"] = "1"

    result: dict[str, Any] = {
        "id": candidate["id"],
        "candidate": candidate,
        "candidate_path": str(candidate_path.relative_to(ROOT)),
        "static_pass": False,
        "traversal_pass": False,
        "score": 0.0,
        "baseline_distance": numeric_distance(candidate, DEFAULT_CANDIDATE),
    }

    steps = [
        ("bootstrap", ["scripts/bootstrap-prototype-shuttle-blender.sh"]),
        ("export", ["scripts/export-prototype-shuttle-blender.sh"]),
        ("package", ["scripts/validate-prototype-shuttle-package.sh"]),
        ("static_collision", ["scripts/validate-prototype-shuttle-collision-layout.sh"]),
    ]
    for name, command in steps:
        ok, _ = run(command, env, DISCOVERY_DIR / "logs" / f"{candidate['id']}_{name}.log")
        result[f"{name}_pass"] = ok
        if not ok:
            copy_result(STATIC_REPORT, DISCOVERY_DIR / "artifacts" / candidate["id"] / "static_collision_report.json")
            return result

    result["static_pass"] = True
    layout = load_json(LAYOUT_REPORT)
    copy_result(LAYOUT_REPORT, DISCOVERY_DIR / "artifacts" / candidate["id"] / "collision_layout_report.json")
    copy_result(STATIC_REPORT, DISCOVERY_DIR / "artifacts" / candidate["id"] / "static_collision_report.json")

    if run_traversal:
        if build_import:
            for name, command in [
                ("dotnet_build", [os.environ.get("DOTNET_BIN", "dotnet"), "build", "SmallSolarSystem.csproj"]),
                ("godot_import", [os.environ.get("GODOT_BIN", "godot"), "--headless", "--path", ".", "--import"]),
            ]:
                ok, _ = run(command, env, DISCOVERY_DIR / "logs" / f"{candidate['id']}_{name}.log")
                result[f"{name}_pass"] = ok
                if not ok:
                    result["score"] = score_candidate(candidate, True, False, layout)
                    return result
        ok, _ = run(["scripts/validate-prototype-shuttle-traversal.sh"], env, DISCOVERY_DIR / "logs" / f"{candidate['id']}_traversal.log")
        result["traversal_pass"] = ok
        copy_result(TRAVERSAL_REPORT, DISCOVERY_DIR / "artifacts" / candidate["id"] / "traversal_report.json")
        if TRAVERSAL_REPORT.exists():
            traversal_report = load_json(TRAVERSAL_REPORT)
            result["auto_step_count"] = traversal_report.get("auto_step_count")
            result["traversal_frames"] = traversal_report.get("frames")
        else:
            traversal_report = None
    else:
        traversal_report = None

    result["score"] = score_candidate(candidate, result["static_pass"], result["traversal_pass"], layout, traversal_report)
    return result


def write_report(
    results: list[dict[str, Any]],
    selected: dict[str, Any] | None,
    rejected_count: int,
    restored_selected_candidate: bool,
    blind: bool,
) -> None:
    golden_layout = load_json(GOLDEN_LAYOUT) if GOLDEN_LAYOUT.exists() else {}
    golden_candidate = load_json(GOLDEN_CANDIDATE) if GOLDEN_CANDIDATE.exists() else golden_layout.get("floorplan_candidate", DEFAULT_CANDIDATE)
    report = {
        "schema_version": 1,
        "candidate_count": len(results),
        "static_pass_count": sum(1 for item in results if item["static_pass"]),
        "traversal_pass_count": sum(1 for item in results if item["traversal_pass"]),
        "rejected_count": rejected_count,
        "selected": selected,
        "blind": blind,
        "selection_policy": (
            "Blind Discovery V1 selects the highest-scoring traversal-passing candidate without using the golden baseline or golden_like seed. "
            "Golden comparison is reported only after selection."
            if blind
            else "Discovery V1 selects the traversal-passing candidate closest to the prototype-only golden baseline; score is used as a tie-breaker."
        ),
        "selection_reason": None if selected is None else (
            f"{selected['id']} passed traversal and has score={selected['score']}, "
            "the highest score among traversal-passing candidates."
            if blind
            else (
                f"{selected['id']} passed traversal and has baseline_distance={selected['baseline_distance']}, "
                f"the smallest distance among traversal-passing candidates."
            )
        ),
        "restored_selected_candidate": restored_selected_candidate,
        "golden_candidate": golden_candidate,
        "golden_comparison": None if selected is None else {
            "selected_to_golden_distance": numeric_distance(selected["candidate"], golden_candidate),
            "rediscovered_equivalent": numeric_distance(selected["candidate"], golden_candidate) <= 0.001,
        },
        "results": results,
    }
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Prototype Shuttle Floorplan Discovery Report",
        "",
        f"- candidates evaluated: {report['candidate_count']}",
        f"- static pass: {report['static_pass_count']}",
        f"- traversal pass: {report['traversal_pass_count']}",
        f"- rejected: {rejected_count}",
        f"- blind mode: `{blind}`",
    ]
    if selected is not None:
        lines.extend([
            f"- selected: `{selected['id']}`",
            f"- selected score: `{selected['score']}`",
            f"- selected to golden distance: `{report['golden_comparison']['selected_to_golden_distance']}`",
            f"- rediscovered equivalent: `{report['golden_comparison']['rediscovered_equivalent']}`",
            f"- restored selected candidate: `{restored_selected_candidate}`",
            f"- selection policy: {report['selection_policy']}",
        ])
    lines.extend(["", "## Results", ""])
    for item in results:
        lines.append(
            f"- `{item['id']}`: static={item['static_pass']} traversal={item['traversal_pass']} "
            f"score={item['score']} baseline_distance={item['baseline_distance']}"
        )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def restore_selected_candidate(selected: dict[str, Any]) -> dict[str, Any]:
    print(f"Restoring selected candidate {selected['id']} into generated assets")
    restored = evaluate_candidate(selected["candidate"], run_traversal=True, build_import=True, save_active=True)
    restored["restored_selected_candidate"] = True
    return restored


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=18)
    parser.add_argument("--traversal-limit", type=int, default=4)
    parser.add_argument("--blind", action="store_true", help="Do not seed or select by the human-approved golden floorplan.")
    args = parser.parse_args()

    CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    candidates = candidate_grid(args.limit, blind=args.blind)

    for candidate in candidates:
        print(f"Evaluating static candidate {candidate['id']}")
        results.append(evaluate_candidate(candidate, run_traversal=False, build_import=False))

    static_passes = [item for item in results if item["static_pass"]]
    if args.blind:
        static_passes.sort(key=lambda item: (-item["score"], item["id"]))
    else:
        static_passes.sort(key=lambda item: (-item["score"], item["baseline_distance"]))
    traversal_ids = {item["id"] for item in static_passes[: args.traversal_limit]}
    for index, item in enumerate(results):
        if item["id"] not in traversal_ids:
            continue
        print(f"Evaluating traversal candidate {item['id']}")
        traversal_result = evaluate_candidate(item["candidate"], run_traversal=True, build_import=True)
        results[index] = traversal_result

    traversal_passes = [item for item in results if item["traversal_pass"]]
    if args.blind:
        traversal_passes.sort(key=lambda item: (-item["score"], item["id"]))
    else:
        # Discovery V1 is a calibration pass. Prefer rediscovering the known-good
        # prototype shuttle floorplan before trying to optimize beyond it.
        traversal_passes.sort(key=lambda item: (item["baseline_distance"], -item["score"]))
    selected = traversal_passes[0] if traversal_passes else None
    rejected_count = sum(1 for item in results if not item["static_pass"] or not item["traversal_pass"])

    if selected is None:
        write_report(results, selected, rejected_count, restored_selected_candidate=False, blind=args.blind)
        print(f"ERROR: no traversable candidate discovered. See {REPORT_JSON.relative_to(ROOT)}")
        raise SystemExit(1)

    restored = restore_selected_candidate(selected)
    if not restored["static_pass"] or not restored["traversal_pass"]:
        write_report(results, selected, rejected_count, restored_selected_candidate=False, blind=args.blind)
        print(f"ERROR: selected candidate failed restore validation. See {REPORT_JSON.relative_to(ROOT)}")
        raise SystemExit(1)
    for index, item in enumerate(results):
        if item["id"] == restored["id"]:
            results[index] = restored
            selected = restored
            break
    write_report(results, selected, rejected_count, restored_selected_candidate=True, blind=args.blind)

    print(f"Selected floorplan candidate: {selected['id']}")
    print(f"Discovery report: {REPORT_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
