#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

if [ -f .tools/env.sh ]; then
  # shellcheck disable=SC1091
  source .tools/env.sh
fi

if [ -z "${GODOT_BIN:-}" ]; then
  echo "GODOT_BIN is not set. Run: source .tools/env.sh" >&2
  exit 1
fi

"$GODOT_BIN" --path . res://scenes/debug/ShipWalkthroughCapture.tscn
python3 tools/raw_rgb_to_review_artifacts.py reports/ship_walkthrough ship_walkthrough
python3 tools/ship_pipeline/standardize_evidence.py

echo "Walkthrough MP4: reports/ship_walkthrough/ship_walkthrough_current.mp4"
echo "Walkthrough contact sheet: reports/ship_walkthrough/ship_walkthrough_contact_sheet_current.png"
