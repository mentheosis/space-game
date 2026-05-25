#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

echo "Checking 0.2.1b Python tooling"
python3 -m py_compile \
  tools/ship_alignment_report.py \
  tools/ship_fit_recommendations.py \
  tools/ship_alignment_overlay_scene.py \
  tools/ship_capture_contract.py \
  tools/ship_capture_manifest.py \
  tools/ship_alignment_dashboard.py \
  tools/ship_phase_completion_audit.py \
  tools/ship_review_checklist_contract.py

echo "Generating 0.2.1b static alignment artifacts"
python3 tools/ship_alignment_report.py --check
python3 tools/ship_fit_recommendations.py --check
python3 tools/ship_alignment_overlay_scene.py --check
python3 tools/ship_capture_contract.py
python3 tools/ship_review_checklist_contract.py
python3 tools/ship_capture_manifest.py
python3 tools/ship_phase_completion_audit.py
python3 tools/ship_alignment_dashboard.py --check

echo "Validating generated JSON artifacts"
python3 -m json.tool reports/ship_fit_targets.json >/dev/null
python3 -m json.tool reports/ship_fit_recommendations.json >/dev/null
python3 -m json.tool reports/ship_alignment_captures.json >/dev/null

echo "Checking shell scripts"
bash -n \
  scripts/ship_alignment_report.sh \
  scripts/capture-ship-alignment.sh \
  scripts/validate-0.2.1b.sh \
  scripts/validate.sh

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Checking whitespace"
  git diff --check
fi

echo "0.2.1b static preflight passed."
