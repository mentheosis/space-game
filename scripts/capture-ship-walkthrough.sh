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
python3 tools/raw_rgb_to_gif.py

echo "Walkthrough GIF: reports/ship_walkthrough/ship_walkthrough.gif"
