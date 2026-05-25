#!/usr/bin/env bash
set -euo pipefail

if [ -f .tools/env.sh ]; then
  # shellcheck disable=SC1091
  source .tools/env.sh
fi

if [ -z "${GODOT_BIN:-}" ]; then
  echo "GODOT_BIN is not set. Run: source .tools/env.sh" >&2
  exit 1
fi

python3 tools/ship_alignment_report.py
python3 tools/ship_fit_recommendations.py
python3 tools/ship_alignment_dashboard.py
"$GODOT_BIN" --headless --path . res://scenes/debug/ShipAlignmentCapture.tscn
python3 tools/ship_alignment_dashboard.py

echo "Static report: reports/ship_alignment_report.md"
echo "Fit recommendations: reports/ship_fit_recommendations.md"
echo "Dashboard: reports/ship_alignment_dashboard.html"
echo "Screenshots: reports/ship_alignment_captures"
