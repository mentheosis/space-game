#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f "${ROOT_DIR}/.tools/env.sh" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.tools/env.sh"
fi

BLENDER_BIN="${BLENDER_BIN:-blender}"
SOURCE_BLEND="${ROOT_DIR}/assets/source/blender/ships/shuttle_p3/shuttle_p3.blend"

if [[ ! -x "${BLENDER_BIN}" ]] && ! command -v "${BLENDER_BIN}" >/dev/null 2>&1; then
  echo "ERROR: Blender executable not found: ${BLENDER_BIN}" >&2
  exit 1
fi

if [[ ! -f "${SOURCE_BLEND}" ]]; then
  echo "ERROR: Missing shuttle_p3 source blend: ${SOURCE_BLEND}" >&2
  echo "Run scripts/bootstrap-shuttle-p3-from-skin.sh first." >&2
  exit 1
fi

export SPACE_GAME_ROOT="${ROOT_DIR}"
"${BLENDER_BIN}" --background "${SOURCE_BLEND}" --python tools/blender/analyze_shuttle_p3_voxel_milestone.py

python3 -m json.tool reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_voxel_report.json >/dev/null
test -s reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_exterior_skin_projection_current.png
test -s reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_voxel_free_space_projection_current.png
test -s reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_semantic_regions_projection_current.png

echo "Shuttle P3 voxel milestone review passed."
