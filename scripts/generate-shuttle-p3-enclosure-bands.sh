#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python3 tools/ship_pipeline/generate_shuttle_p3_enclosure_bands.py
