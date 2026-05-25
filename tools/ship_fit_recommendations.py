#!/usr/bin/env python3
"""Summarize measured ShuttleA fit data into actionable recommendations."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIT_TARGETS_JSON_PATH = ROOT / "reports/ship_fit_targets.json"
RECOMMENDATIONS_MD_PATH = ROOT / "reports/ship_fit_recommendations.md"
RECOMMENDATIONS_JSON_PATH = ROOT / "reports/ship_fit_recommendations.json"


AXES = ("x", "y", "z")


def vector_text(values: list[float]) -> str:
    return f"({values[0]:6.2f}, {values[1]:5.2f}, {values[2]:6.2f})"


def recommendation_for_comparison(comparison: dict[str, object]) -> dict[str, object]:
    name = str(comparison["name"])
    center_delta = list(comparison["center_delta"])  # type: ignore[arg-type]
    size_delta = list(comparison["size_delta"])  # type: ignore[arg-type]
    overlap = list(comparison["overlap"])  # type: ignore[arg-type]
    target_size = list(comparison["target_bounds"]["size"])  # type: ignore[index]
    actual_size = list(comparison["actual_bounds"]["size"])  # type: ignore[index]

    severity = "ok"
    notes: list[str] = []
    suggested_move = [-round(value, 4) for value in center_delta]
    relevant_axes = ["x", "y", "z"]

    if name == "Interior volume vs cabin":
        relevant_axes = ["x", "y", "z"]
        if max(abs(center_delta[0]), abs(center_delta[1]), abs(center_delta[2])) > 0.3:
            severity = "review"
            notes.append("Interior volume center is drifting from the measured cabin envelope.")
        if actual_size[0] < target_size[0] * 0.88 or actual_size[2] < target_size[2] * 0.88:
            severity = max_severity(severity, "review")
            notes.append("Interior volume is materially smaller than the measured cabin envelope.")
    elif name == "Floor plate vs walk path":
        relevant_axes = ["z"]
        if abs(center_delta[2]) > 0.25:
            severity = "adjust"
            notes.append("Floor fore/aft position should be tuned to the measured walk path.")
        if overlap[2] < target_size[2] * 0.94:
            severity = max_severity(severity, "adjust")
            notes.append("Floor does not cover enough of the measured walk path length.")
        if actual_size[0] > target_size[0] * 1.35:
            severity = max_severity(severity, "review")
            notes.append("Floor is substantially wider than the measured walk path; confirm this is intentional side plating.")
    elif name in ("Exterior hatch vs rear zone", "Interior hatch vs rear zone"):
        relevant_axes = ["y", "z"]
        if abs(center_delta[1]) > 0.35 or abs(center_delta[2]) > 0.45:
            severity = "adjust"
            notes.append("Hatch center should be closer to the measured rear hatch zone.")
        if actual_size[0] < 1.6 or actual_size[1] < 1.6:
            severity = max_severity(severity, "review")
            notes.append("Hatch visual may be too small for comfortable player-scale entry.")
    elif name == "Pilot cushion vs cockpit":
        relevant_axes = ["z"]
        if abs(center_delta[2]) > 0.75:
            severity = "adjust"
            notes.append("Pilot seat fore/aft position is not centered in the measured cockpit/canopy region.")
        if abs(center_delta[1]) > 0.55:
            severity = max_severity(severity, "review")
            notes.append("Pilot seat is vertically below the canopy slice; verify player eye height and canopy readability in screenshots before raising the chair.")
        if overlap[1] < 0.9 or overlap[2] < 1.1:
            severity = max_severity(severity, "review")
            notes.append("Seat/cockpit overlap is low; review player eye position and canopy readability.")
    elif name == "Interior canopy glass vs cockpit":
        relevant_axes = ["y", "z"]
        if abs(center_delta[1]) > 0.35 or abs(center_delta[2]) > 0.35:
            severity = "adjust"
            notes.append("Canopy glass center should be recentered against the cockpit slice.")
        if overlap[1] < 1.2 or overlap[2] < 3.2:
            severity = max_severity(severity, "adjust")
            notes.append("Canopy glass overlap with measured cockpit slice is too low.")

    if not notes:
        notes.append("Measured fit is within current tolerance.")

    return {
        "name": name,
        "severity": severity,
        "relevant_axes": relevant_axes,
        "center_delta": center_delta,
        "size_delta": size_delta,
        "overlap": overlap,
        "suggested_centering_move": suggested_move,
        "notes": notes,
    }


def max_severity(left: str, right: str) -> str:
    order = {"ok": 0, "review": 1, "adjust": 2, "critical": 3}
    return left if order[left] >= order[right] else right


def write_outputs(data: dict[str, object], recommendations: list[dict[str, object]]) -> None:
    failures = list(data.get("failures", []))
    generated = {
        "source": data.get("artifacts", {}).get("fit_targets_json", str(FIT_TARGETS_JSON_PATH.relative_to(ROOT))),  # type: ignore[union-attr]
        "recommendations": recommendations,
        "upstream_failures": failures,
    }
    RECOMMENDATIONS_JSON_PATH.write_text(json.dumps(generated, indent=2) + "\n", encoding="utf-8")

    lines: list[str] = []
    lines.append("# Ship Fit Recommendations")
    lines.append("")
    lines.append("Generated from `reports/ship_fit_targets.json`.")
    lines.append("")
    if failures:
        lines.append("## Upstream Alignment Gate Failures")
        lines.append("")
        for failure in failures:
            lines.append(f"- {failure}")
        lines.append("")
    lines.append("## Fit Recommendations")
    lines.append("")
    lines.append("| Fit | Severity | Center Delta | Suggested Centering Move | Notes |")
    lines.append("| --- | --- | --- | --- | --- |")
    for recommendation in recommendations:
        notes = "<br>".join(str(note) for note in recommendation["notes"])
        lines.append(
            f"| `{recommendation['name']}` | `{recommendation['severity']}` | "
            f"`{vector_text(recommendation['center_delta'])}` | "
            f"`{vector_text(recommendation['suggested_centering_move'])}` | {notes} |"
        )
    lines.append("")
    lines.append("## Usage")
    lines.append("")
    lines.append("- Treat `adjust` rows as the next authored scene or mesh tuning candidates.")
    lines.append("- Treat `review` rows as screenshot/manual-review prompts before changing geometry.")
    lines.append("- Suggested moves are measurement-derived center offsets; apply only on the listed relevant axes and only when the visual result remains plausible.")
    RECOMMENDATIONS_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    check_mode = "--check" in sys.argv[1:]
    if not FIT_TARGETS_JSON_PATH.exists():
        print(f"FAIL: {FIT_TARGETS_JSON_PATH.relative_to(ROOT)} does not exist.", file=sys.stderr)
        return 1

    data = json.loads(FIT_TARGETS_JSON_PATH.read_text(encoding="utf-8"))
    comparisons = data.get("fit_comparisons", [])
    if not isinstance(comparisons, list) or not comparisons:
        print("FAIL: fit target JSON does not contain fit_comparisons.", file=sys.stderr)
        return 1

    recommendations = [recommendation_for_comparison(comparison) for comparison in comparisons]
    write_outputs(data, recommendations)
    print(f"Wrote {RECOMMENDATIONS_MD_PATH.relative_to(ROOT)}")
    print(f"Wrote {RECOMMENDATIONS_JSON_PATH.relative_to(ROOT)}")

    upstream_failures = data.get("failures", [])
    if check_mode and upstream_failures:
        for failure in upstream_failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
