#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f "${ROOT_DIR}/.tools/env.sh" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.tools/env.sh"
fi

export BLENDER_BIN="${BLENDER_BIN:-blender}"
export GODOT_BIN="${GODOT_BIN:-godot}"
export PROTOTYPE_SHUTTLE_FLOORPLAN_CANDIDATE="${ROOT_DIR}/reports/ship_pipeline/prototype_shuttle_floorplan_discovery/reset/no_walkable_floorplan_candidate.json"
export PROTOTYPE_SHUTTLE_SAVE_ACTIVE_FLOORPLAN=1

scripts/bootstrap-prototype-shuttle-blender.sh
scripts/export-prototype-shuttle-blender.sh
scripts/validate-prototype-shuttle-package.sh
"${GODOT_BIN}" --headless --path . --import
