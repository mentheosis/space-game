#!/usr/bin/env python3
"""Validate the generated prototype shuttle walkable collision layout."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LAYOUT_PATH = ROOT / "assets/models/ship/prototype_shuttle/prototype_shuttle_collision_layout_report.json"
REPORT_PATH = ROOT / "reports/ship_pipeline/prototype_shuttle_collision_layout_validation_report.json"


def axis_bounds(surface: dict[str, object], axis: int) -> tuple[float, float]:
    center = surface["center"]
    size = surface["size"]
    assert isinstance(center, list)
    assert isinstance(size, list)
    half = float(size[axis]) * 0.5
    value = float(center[axis])
    return value - half, value + half


def top_y(surface: dict[str, object]) -> float:
    center = surface["center"]
    size = surface["size"]
    assert isinstance(center, list)
    assert isinstance(size, list)
    return float(center[1]) + float(size[1]) * 0.5


def overlap_1d(a: tuple[float, float], b: tuple[float, float]) -> float:
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def gap_1d(a: tuple[float, float], b: tuple[float, float]) -> float:
    if a[1] < b[0]:
        return b[0] - a[1]
    if b[1] < a[0]:
        return a[0] - b[1]
    return 0.0


def require_surface(surfaces: dict[str, dict[str, object]], surface_id: str, errors: list[dict[str, object]]) -> dict[str, object] | None:
    surface = surfaces.get(surface_id)
    if surface is None:
        errors.append({"check": "required_surface", "status": "missing", "surface": surface_id})
    return surface


def check_floor_overlap(
    errors: list[dict[str, object]],
    a: dict[str, object],
    b: dict[str, object],
    check_id: str,
    min_overlap: float,
    max_vertical_delta: float,
    max_gap: float = 0.08,
) -> None:
    x_overlap = overlap_1d(axis_bounds(a, 0), axis_bounds(b, 0))
    z_overlap = overlap_1d(axis_bounds(a, 2), axis_bounds(b, 2))
    z_gap = gap_1d(axis_bounds(a, 2), axis_bounds(b, 2))
    vertical_delta = abs(top_y(a) - top_y(b))
    if x_overlap < min_overlap:
        errors.append({"check": check_id, "status": "insufficient_x_overlap", "value": round(x_overlap, 4), "required": min_overlap})
    if z_overlap < min_overlap and z_gap > max_gap:
        errors.append({"check": check_id, "status": "z_gap", "value": round(z_gap, 4), "max": max_gap})
    if vertical_delta > max_vertical_delta:
        errors.append({"check": check_id, "status": "vertical_delta", "value": round(vertical_delta, 4), "max": max_vertical_delta})


def check_stair_lane(
    errors: list[dict[str, object]],
    surfaces: dict[str, dict[str, object]],
    side: str,
    min_overlap: float,
    max_step_height: float,
) -> None:
    steps = [
        surface for surface in surfaces.values()
        if surface.get("side") == side and str(surface.get("id", "")).startswith(f"{side}_stair_")
    ]
    steps.sort(key=lambda item: int(item.get("step_index", -1)))
    if len(steps) < 2:
        errors.append({"check": f"{side}_stair_lane", "status": "too_few_steps", "count": len(steps)})
        return

    # Steps are indexed from cockpit/top toward cargo/bottom by z interpolation.
    for lower, upper in zip(reversed(steps), reversed(steps[:-1])):
        check_floor_overlap(
            errors,
            lower,
            upper,
            f"{side}_stair_{lower['step_index']}_to_{upper['step_index']}",
            min_overlap=min_overlap * 0.6,
            max_vertical_delta=max_step_height,
            max_gap=0.18,
        )

    cargo = surfaces.get("cargo_forward_lower")
    if cargo is not None:
        check_floor_overlap(errors, cargo, steps[-1], f"cargo_to_{side}_stair_bottom", min_overlap * 0.6, max_step_height, max_gap=0.24)

    landing = surfaces.get("cockpit_entry_landing")
    if landing is not None:
        check_floor_overlap(errors, steps[0], landing, f"{side}_stair_top_to_landing", min_overlap, max_step_height, max_gap=0.04)


def validate(payload: dict[str, object]) -> list[dict[str, object]]:
    errors: list[dict[str, object]] = []
    player = payload.get("player", {})
    if not isinstance(player, dict):
        return [{"check": "player", "status": "missing"}]

    min_overlap = float(player.get("minimum_overlap", 0.24))
    max_step_height = float(player.get("max_step_height", 0.48))
    min_landing_depth = float(player.get("minimum_landing_depth", 1.1))
    surfaces_list = payload.get("surfaces", [])
    if not isinstance(surfaces_list, list):
        return [{"check": "surfaces", "status": "not_list"}]
    surfaces = {str(surface.get("id")): surface for surface in surfaces_list if isinstance(surface, dict)}

    required = [
        "forward_belly_ramp",
        "cargo_forward_lower",
        "cockpit_entry_landing",
        "cockpit_floor",
    ]
    for surface_id in required:
        require_surface(surfaces, surface_id, errors)

    ramp = surfaces.get("forward_belly_ramp")
    cargo_forward = surfaces.get("cargo_forward_lower")
    if ramp is not None and cargo_forward is not None:
        hinge = ramp.get("hinge")
        width = float(ramp.get("width", 0.0))
        if not isinstance(hinge, list) or len(hinge) != 3:
            errors.append({"check": "ramp_hinge", "status": "invalid"})
        else:
            ramp_top_y = float(hinge[1])
            cargo_top = top_y(cargo_forward)
            if ramp_top_y > cargo_top + 0.04:
                errors.append({"check": "ramp_to_cargo", "status": "upward_lip", "value": round(ramp_top_y - cargo_top, 4), "max": 0.04})
            if cargo_top - ramp_top_y > max_step_height * 0.75:
                errors.append({"check": "ramp_to_cargo", "status": "excessive_drop", "value": round(cargo_top - ramp_top_y, 4)})
            x_overlap = min(width, axis_bounds(cargo_forward, 0)[1] - axis_bounds(cargo_forward, 0)[0])
            if x_overlap < min_overlap:
                errors.append({"check": "ramp_to_cargo", "status": "insufficient_x_overlap", "value": round(x_overlap, 4)})

    check_stair_lane(errors, surfaces, "left", min_overlap, max_step_height)
    check_stair_lane(errors, surfaces, "right", min_overlap, max_step_height)

    landing = surfaces.get("cockpit_entry_landing")
    cockpit = surfaces.get("cockpit_floor")
    if landing is not None:
        landing_depth = axis_bounds(landing, 2)[1] - axis_bounds(landing, 2)[0]
        if landing_depth < min_landing_depth:
            errors.append({"check": "cockpit_entry_landing", "status": "insufficient_depth", "value": round(landing_depth, 4), "required": min_landing_depth})
    if landing is not None and cockpit is not None:
        check_floor_overlap(errors, landing, cockpit, "landing_to_cockpit_floor", min_overlap, max_step_height * 0.35, max_gap=0.02)

    return errors


def main() -> None:
    if not LAYOUT_PATH.exists():
        raise SystemExit(f"ERROR: missing collision layout report: {LAYOUT_PATH}")
    payload = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
    errors = validate(payload)
    report = {
        "schema_version": 1,
        "source": str(LAYOUT_PATH.relative_to(ROOT)),
        "error_count": len(errors),
        "errors": errors,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if errors:
        print(f"ERROR: {len(errors)} collision layout issue(s). See {REPORT_PATH.relative_to(ROOT)}")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("PASS: prototype shuttle collision layout is statically traversable.")


if __name__ == "__main__":
    main()
