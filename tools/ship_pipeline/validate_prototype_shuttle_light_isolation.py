#!/usr/bin/env python3
"""Validate that prototype shuttle review scenes do not use leaking exterior fill."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports/ship_pipeline/prototype_shuttle_light_isolation_report.json"
SCENES = [
    ROOT / "scenes/debug/PrototypeShuttleDebugWorld.tscn",
    ROOT / "scenes/debug/PrototypeShuttleFlythrough.tscn",
    ROOT / "scenes/debug/PrototypeShuttleMaterialWalkthroughCapture.tscn",
]


def parse_float_property(text: str, property_name: str) -> float | None:
    match = re.search(rf"^{re.escape(property_name)} = ([0-9.]+)$", text, re.MULTILINE)
    if match is None:
        return None
    return float(match.group(1))


def node_blocks(text: str) -> list[tuple[str, str, str]]:
    matches = list(re.finditer(r'^\[node name="([^"]+)" type="([^"]+)"[^\]]*\]$', text, re.MULTILINE))
    blocks: list[tuple[str, str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks.append((match.group(1), match.group(2), text[start:end]))
    return blocks


def validate_scene(path: Path) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    text = path.read_text(encoding="utf-8")
    rel = str(path.relative_to(ROOT))
    ambient = parse_float_property(text, "ambient_light_energy")
    if ambient is not None and ambient > 0.10:
        issues.append({
            "severity": "FAIL",
            "scene": rel,
            "kind": "ambient_leak",
            "ambient_light_energy": ambient,
            "reason": "Scene ambient is high enough to fake exterior light through closed hull surfaces.",
        })

    leaking_names = ("fill", "review")
    for name, node_type, block in node_blocks(text):
        if node_type not in {"OmniLight3D", "SpotLight3D"}:
            continue
        lower = name.lower()
        shadow_enabled = "shadow_enabled = true" in block
        if any(token in lower for token in leaking_names) and not shadow_enabled:
            issues.append({
                "severity": "FAIL",
                "scene": rel,
                "kind": "unshadowed_review_light",
                "node": name,
                "type": node_type,
                "reason": "Unshadowed fill/review light can illuminate through the shuttle hull.",
            })
    return issues


def main() -> int:
    issues: list[dict[str, object]] = []
    for scene in SCENES:
        if not scene.exists():
            issues.append({
                "severity": "FAIL",
                "scene": str(scene.relative_to(ROOT)),
                "kind": "missing_scene",
                "reason": "Expected prototype shuttle review scene is missing.",
            })
            continue
        issues.extend(validate_scene(scene))

    payload = {
        "status": "PASS" if not any(issue["severity"] == "FAIL" for issue in issues) else "FAIL",
        "checked_scenes": [str(scene.relative_to(ROOT)) for scene in SCENES],
        "issues": issues,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"Prototype shuttle light isolation: {payload['status']}")
    print(f"Report: {REPORT.relative_to(ROOT)}")
    for issue in issues:
        print(f"{issue['severity']}: {issue['scene']}: {issue['reason']}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
