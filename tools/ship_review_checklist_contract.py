#!/usr/bin/env python3
"""Verify the 0.2.1b visual review checklist keeps its required structure."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKLIST_PATH = ROOT / "reports/ship_alignment_review_checklist.md"

REQUIRED_SECTIONS = [
    "## Required Evidence",
    "## Clean Screenshot Review",
    "## Overlay Screenshot Review",
    "## Gameplay Review",
    "## Deferrals / Follow-Up Notes",
]

EXPECTED_CHECKBOX_COUNT = 28


def main() -> int:
    if not CHECKLIST_PATH.exists():
        print(f"FAIL: missing {CHECKLIST_PATH.relative_to(ROOT)}", file=sys.stderr)
        return 1

    text = CHECKLIST_PATH.read_text(encoding="utf-8")
    failures: list[str] = []
    for section in REQUIRED_SECTIONS:
        if section not in text:
            failures.append(f"Missing checklist section: {section}")

    checkbox_count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [ ]") or stripped.startswith("- [x]") or stripped.startswith("- [X]"):
            checkbox_count += 1

    if checkbox_count != EXPECTED_CHECKBOX_COUNT:
        failures.append(f"Expected {EXPECTED_CHECKBOX_COUNT} checklist items, found {checkbox_count}.")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    print(f"Review checklist contract passed: {checkbox_count} checklist items.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
