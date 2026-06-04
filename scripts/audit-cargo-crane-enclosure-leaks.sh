#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python3 tools/ship_pipeline/audit_cargo_crane_enclosure_leaks.py
