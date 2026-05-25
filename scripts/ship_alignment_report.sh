#!/usr/bin/env bash
set -euo pipefail

python3 tools/ship_alignment_report.py
python3 tools/ship_fit_recommendations.py
python3 tools/ship_alignment_dashboard.py
