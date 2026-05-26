#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f "${ROOT_DIR}/.tools/env.sh" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.tools/env.sh"
fi

BLENDER_BIN="${BLENDER_BIN:-blender}"
SOURCE_BLEND="${ROOT_DIR}/assets/source/blender/ships/shuttle_a/shuttle_a_interior.blend"

if [[ ! -x "${BLENDER_BIN}" ]] && ! command -v "${BLENDER_BIN}" >/dev/null 2>&1; then
  echo "ERROR: Blender executable not found: ${BLENDER_BIN}" >&2
  echo "Install Blender and set BLENDER_BIN, for example:" >&2
  echo "  export BLENDER_BIN=\"/Applications/Blender.app/Contents/MacOS/Blender\"" >&2
  exit 1
fi

if [[ ! -f "${SOURCE_BLEND}" ]]; then
  echo "ERROR: Missing Blender source scene: ${SOURCE_BLEND}" >&2
  echo "Run scripts/bootstrap-shuttle-a-blender.sh first." >&2
  exit 1
fi

export SPACE_GAME_ROOT="${ROOT_DIR}"
"${BLENDER_BIN}" --background "${SOURCE_BLEND}" --python tools/blender/export_shuttle_a.py

