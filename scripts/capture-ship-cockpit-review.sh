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

"$GODOT_BIN" --path . res://scenes/debug/ShipCockpitReviewCapture.tscn
python3 tools/raw_rgb_to_gif.py reports/ship_cockpit_review reports/ship_cockpit_review/ship_cockpit_review.gif

echo "Cockpit review GIF: reports/ship_cockpit_review/ship_cockpit_review.gif"
