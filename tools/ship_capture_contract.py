#!/usr/bin/env python3
"""Verify screenshot capture names stay synchronized across C# and Python tools."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts/debug/ShipAlignmentCaptureRunner.cs"
CAPTURE_SCENE_PATH = ROOT / "scenes/debug/ShipAlignmentCapture.tscn"
MANIFEST_TOOL_PATH = ROOT / "tools/ship_capture_manifest.py"
DASHBOARD_TOOL_PATH = ROOT / "tools/ship_alignment_dashboard.py"


def load_expected_captures(path: Path) -> list[str]:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.EXPECTED_CAPTURES)


def runner_capture_names() -> list[str]:
    text = RUNNER_PATH.read_text(encoding="utf-8")
    return [f"{match}.png" for match in re.findall(r'new\("([^"]+)"\s*,', text)]


def validate_pairs(names: list[str]) -> list[str]:
    failures: list[str] = []
    if len(names) % 2 != 0:
        failures.append("Capture list must contain clean/overlay pairs.")
        return failures
    for index in range(0, len(names), 2):
        clean = names[index]
        overlay = names[index + 1]
        expected_overlay = clean.removesuffix(".png") + "_overlay.png"
        if overlay != expected_overlay:
            failures.append(f"Expected overlay pair `{expected_overlay}` after `{clean}`, got `{overlay}`.")
    return failures


def validate_scene_overlay() -> list[str]:
    failures: list[str] = []
    text = CAPTURE_SCENE_PATH.read_text(encoding="utf-8")
    if "ShipAlignmentOverlay.tscn" not in text:
        failures.append("Capture scene does not instance generated ShipAlignmentOverlay.tscn.")
    if 'node name="ShipAlignmentOverlay"' not in text:
        failures.append("Capture scene does not contain a ShipAlignmentOverlay node.")
    return failures


def main() -> int:
    runner_names = runner_capture_names()
    manifest_names = load_expected_captures(MANIFEST_TOOL_PATH)
    dashboard_names = load_expected_captures(DASHBOARD_TOOL_PATH)
    failures: list[str] = []

    if runner_names != manifest_names:
        failures.append("Capture runner names do not match ship_capture_manifest.py EXPECTED_CAPTURES.")
    if runner_names != dashboard_names:
        failures.append("Capture runner names do not match ship_alignment_dashboard.py EXPECTED_CAPTURES.")
    failures.extend(validate_pairs(runner_names))
    failures.extend(validate_scene_overlay())

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    print(f"Capture contract passed: {len(runner_names)} screenshots.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
