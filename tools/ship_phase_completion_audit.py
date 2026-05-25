#!/usr/bin/env python3
"""Audit current evidence for closing 0.2.1b."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
AUDIT_PATH = REPORTS / "ship_phase_0_2_1b_completion_audit.md"
HOST_REVIEW_LOG_PATH = REPORTS / "ship_phase_0_2_1b_host_review.log"
HOST_REVIEW_SUCCESS_MARKER = "0.2.1b host review passed."
CAPTURE_MANIFEST_PATH = REPORTS / "ship_alignment_captures.json"
RECOMMENDATIONS_JSON_PATH = REPORTS / "ship_fit_recommendations.json"
CHECKLIST_PATH = REPORTS / "ship_alignment_review_checklist.md"


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def checklist_counts() -> tuple[int, int]:
    if not CHECKLIST_PATH.exists():
        return (0, 0)
    checked = 0
    unchecked = 0
    for line in CHECKLIST_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- [x]") or stripped.startswith("- [X]"):
            checked += 1
        elif stripped.startswith("- [ ]"):
            unchecked += 1
    return checked, unchecked


def recommendation_counts() -> dict[str, int]:
    data = read_json(RECOMMENDATIONS_JSON_PATH)
    counts = {"ok": 0, "review": 0, "adjust": 0, "critical": 0, "unknown": 0}
    rows = data.get("recommendations", [])
    if not isinstance(rows, list):
        return counts
    for row in rows:
        if not isinstance(row, dict):
            continue
        severity = str(row.get("severity", "unknown"))
        counts[severity if severity in counts else "unknown"] += 1
    return counts


def host_log_has_success_marker() -> bool:
    if not HOST_REVIEW_LOG_PATH.exists() or HOST_REVIEW_LOG_PATH.stat().st_size == 0:
        return False
    return HOST_REVIEW_SUCCESS_MARKER in HOST_REVIEW_LOG_PATH.read_text(encoding="utf-8", errors="replace")


def status_line(name: str, passed: bool, evidence: str) -> str:
    marker = "PASS" if passed else "PENDING"
    return f"| {name} | {marker} | {evidence} |"


def write_audit() -> bool:
    REPORTS.mkdir(parents=True, exist_ok=True)
    capture_manifest = read_json(CAPTURE_MANIFEST_PATH)
    checked, unchecked = checklist_counts()
    recommendation_summary = recommendation_counts()

    static_artifacts = [
        REPORTS / "ship_alignment_report.md",
        REPORTS / "ship_fit_targets.json",
        REPORTS / "ship_fit_recommendations.md",
        REPORTS / "ship_fit_recommendations.json",
        REPORTS / "ship_alignment_dashboard.html",
        ROOT / "scenes/debug/generated/ShipAlignmentOverlay.tscn",
    ]
    static_ready = all(path.exists() and path.stat().st_size > 0 for path in static_artifacts)
    host_log_present = HOST_REVIEW_LOG_PATH.exists() and HOST_REVIEW_LOG_PATH.stat().st_size > 0
    host_log_success = host_log_has_success_marker()
    capture_complete = bool(capture_manifest.get("complete", False))
    checklist_complete = checked > 0 and unchecked == 0
    no_adjust_recommendations = recommendation_summary.get("adjust", 0) == 0 and recommendation_summary.get("critical", 0) == 0
    review_rows_resolved = recommendation_summary.get("review", 0) == 0 or checklist_complete
    host_review_proven = host_log_success and capture_complete and checklist_complete
    complete = static_ready and no_adjust_recommendations and review_rows_resolved and host_review_proven

    lines: list[str] = []
    lines.append("# 0.2.1b Completion Audit")
    lines.append("")
    lines.append("Generated from current repo-side evidence. This audit is intentionally conservative: host-rendered screenshots and completed manual review remain required before closing 0.2.1b.")
    lines.append("")
    lines.append("## Gate Summary")
    lines.append("")
    lines.append("| Gate | Status | Evidence |")
    lines.append("| --- | --- | --- |")
    lines.append(status_line("Static alignment artifacts generated", static_ready, "`scripts/preflight-0.2.1b-static.sh` regenerated report, JSON, overlay scene, manifest, and dashboard."))
    lines.append(status_line("No unresolved adjust/critical recommendations", no_adjust_recommendations, f"`reports/ship_fit_recommendations.json`: {recommendation_summary}."))
    lines.append(status_line("Review recommendations resolved", review_rows_resolved, "Review rows require completed screenshot/manual checklist unless none remain."))
    lines.append(status_line("Host review log present", host_log_present, "`reports/ship_phase_0_2_1b_host_review.log` is written by `scripts/review-0.2.1b-host.sh`."))
    lines.append(status_line("Host review completed successfully", host_log_success, f"Log contains `{HOST_REVIEW_SUCCESS_MARKER}`."))
    lines.append(status_line("Host captures complete", capture_complete, f"`reports/ship_alignment_captures.json`: {capture_manifest.get('present_count', 0)}/{capture_manifest.get('expected_count', 16)} present."))
    lines.append(status_line("Manual review checklist complete", checklist_complete, f"`reports/ship_alignment_review_checklist.md`: {checked}/{checked + unchecked} checked."))
    lines.append("")
    lines.append("## Result")
    lines.append("")
    if complete:
        lines.append("0.2.1b has enough recorded evidence to be considered complete.")
    else:
        lines.append("0.2.1b is not complete yet. Remaining evidence requires host Godot capture/validation and completed visual/gameplay checklist review.")
    lines.append("")
    lines.append("## Required Host Command")
    lines.append("")
    lines.append("```bash")
    lines.append("scripts/review-0.2.1b-host.sh")
    lines.append("```")
    lines.append("")
    lines.append("Then review:")
    lines.append("")
    lines.append("- `reports/ship_alignment_dashboard.html`")
    lines.append("- `reports/ship_alignment_review_checklist.md`")

    AUDIT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return complete


def main() -> int:
    check_mode = "--check" in sys.argv[1:]
    complete = write_audit()
    print(f"Wrote {AUDIT_PATH.relative_to(ROOT)}")
    if check_mode and not complete:
        print("0.2.1b completion audit is not yet complete.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
