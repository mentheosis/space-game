#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f "${ROOT_DIR}/.tools/env.sh" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.tools/env.sh"
fi

BLENDER_BIN="${BLENDER_BIN:-blender}"
SOURCE_BLEND="${ROOT_DIR}/assets/source/blender/ships/prototype_shuttle/prototype_shuttle.blend"

if [[ ! -x "${BLENDER_BIN}" ]] && ! command -v "${BLENDER_BIN}" >/dev/null 2>&1; then
  echo "ERROR: Blender executable not found: ${BLENDER_BIN}" >&2
  echo "Install Blender and set BLENDER_BIN, for example:" >&2
  echo "  export BLENDER_BIN=\"/Applications/Blender.app/Contents/MacOS/Blender\"" >&2
  exit 1
fi

if [[ ! -f "${SOURCE_BLEND}" ]]; then
  echo "ERROR: Missing Blender source scene: ${SOURCE_BLEND}" >&2
  echo "Run scripts/bootstrap-prototype-shuttle-blender.sh first." >&2
  exit 1
fi

if [[ ! -f tools/blender/export_prototype_shuttle.py ]]; then
  echo "ERROR: Missing tools/blender/export_prototype_shuttle.py" >&2
  echo "Create the prototype shuttle Blender export tool before running this profile." >&2
  exit 1
fi

export SPACE_GAME_ROOT="${ROOT_DIR}"

if [[ "${PROTOTYPE_SHUTTLE_SKIP_STRUCTURAL_DETAIL:-0}" != "1" ]]; then
  if [[ ! -f tools/blender/apply_prototype_shuttle_structural_detail.py ]]; then
    echo "ERROR: Missing tools/blender/apply_prototype_shuttle_structural_detail.py" >&2
    echo "Set PROTOTYPE_SHUTTLE_SKIP_STRUCTURAL_DETAIL=1 to export without the structural detail pass." >&2
    exit 1
  fi
  "${BLENDER_BIN}" --background "${SOURCE_BLEND}" --python tools/blender/apply_prototype_shuttle_structural_detail.py
fi

"${BLENDER_BIN}" --background "${SOURCE_BLEND}" --python tools/blender/export_prototype_shuttle.py
