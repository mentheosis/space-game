#!/usr/bin/env python3
"""Write and optionally verify the ShuttleA fixed-camera capture manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CAPTURE_DIR = ROOT / "reports/ship_alignment_captures"
MANIFEST_PATH = ROOT / "reports/ship_alignment_captures.json"

EXPECTED_CAPTURES = [
    "01_exterior_front.png",
    "01_exterior_front_overlay.png",
    "02_exterior_rear_hatch.png",
    "02_exterior_rear_hatch_overlay.png",
    "03_exterior_left.png",
    "03_exterior_left_overlay.png",
    "04_exterior_top.png",
    "04_exterior_top_overlay.png",
    "05_cockpit_glass_close.png",
    "05_cockpit_glass_close_overlay.png",
    "06_interior_entry.png",
    "06_interior_entry_overlay.png",
    "07_interior_seat.png",
    "07_interior_seat_overlay.png",
    "08_interior_cockpit_backlook.png",
    "08_interior_cockpit_backlook_overlay.png",
    "09_player_entry_forward.png",
    "09_player_entry_forward_overlay.png",
    "10_pilot_eye_forward.png",
    "10_pilot_eye_forward_overlay.png",
]


def capture_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for filename in EXPECTED_CAPTURES:
        path = CAPTURE_DIR / filename
        exists = path.exists()
        size_bytes = path.stat().st_size if exists else 0
        rows.append(
            {
                "name": filename,
                "path": str(path.relative_to(ROOT)),
                "exists": exists,
                "size_bytes": size_bytes,
                "nonempty": size_bytes > 0,
            }
        )
    return rows


def write_manifest(rows: list[dict[str, object]]) -> None:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    complete = all(bool(row["exists"]) and bool(row["nonempty"]) for row in rows)
    payload = {
        "capture_directory": str(CAPTURE_DIR.relative_to(ROOT)),
        "expected_count": len(EXPECTED_CAPTURES),
        "present_count": sum(1 for row in rows if bool(row["exists"]) and bool(row["nonempty"])),
        "complete": complete,
        "captures": rows,
    }
    MANIFEST_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def clean_expected_captures() -> None:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    for filename in EXPECTED_CAPTURES:
        path = CAPTURE_DIR / filename
        if path.exists():
            path.unlink()
    if MANIFEST_PATH.exists():
        MANIFEST_PATH.unlink()


def main() -> int:
    check_mode = "--check" in sys.argv[1:]
    clean_mode = "--clean" in sys.argv[1:]
    if clean_mode:
        clean_expected_captures()
        print(f"Removed expected captures from {CAPTURE_DIR.relative_to(ROOT)}")
        if not check_mode:
            return 0

    rows = capture_rows()
    write_manifest(rows)
    print(f"Wrote {MANIFEST_PATH.relative_to(ROOT)}")

    missing = [str(row["name"]) for row in rows if not bool(row["exists"])]
    empty = [str(row["name"]) for row in rows if bool(row["exists"]) and not bool(row["nonempty"])]
    if check_mode and (missing or empty):
        for filename in missing:
            print(f"FAIL: missing capture {filename}", file=sys.stderr)
        for filename in empty:
            print(f"FAIL: empty capture {filename}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
