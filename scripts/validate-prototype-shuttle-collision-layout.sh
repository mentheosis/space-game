#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

python3 tools/ship_pipeline/validate_prototype_shuttle_collision_layout.py
