#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

echo "Refreshing 0.2.1b alignment evidence"
python3 tools/ship_alignment_report.py --check
python3 tools/ship_fit_recommendations.py --check
python3 tools/ship_alignment_overlay_scene.py --check
python3 tools/ship_capture_contract.py
python3 tools/ship_review_checklist_contract.py
python3 tools/ship_capture_manifest.py --check

echo "Checking 0.2.1b completion audit"
python3 tools/ship_phase_completion_audit.py --check
python3 tools/ship_alignment_dashboard.py --check

echo "0.2.1b closeout audit passed."
