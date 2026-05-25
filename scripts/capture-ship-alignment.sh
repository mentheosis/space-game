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

python3 tools/ship_alignment_report.py
python3 tools/ship_fit_recommendations.py
python3 tools/ship_alignment_overlay_scene.py
python3 tools/ship_capture_contract.py
python3 tools/ship_alignment_dashboard.py
python3 tools/ship_capture_manifest.py --clean
"$GODOT_BIN" --path . res://scenes/debug/ShipAlignmentCapture.tscn
python3 tools/ship_capture_manifest.py --check
python3 tools/ship_phase_completion_audit.py
python3 tools/ship_alignment_dashboard.py

echo "Static report: reports/ship_alignment_report.md"
echo "Fit recommendations: reports/ship_fit_recommendations.md"
echo "Dashboard: reports/ship_alignment_dashboard.html"
echo "Capture manifest: reports/ship_alignment_captures.json"
echo "Completion audit: reports/ship_phase_0_2_1b_completion_audit.md"
echo "Screenshots: reports/ship_alignment_captures"
