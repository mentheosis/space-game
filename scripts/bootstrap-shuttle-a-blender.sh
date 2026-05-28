#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f "${ROOT_DIR}/.tools/env.sh" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.tools/env.sh"
fi

BLENDER_BIN="${BLENDER_BIN:-blender}"

if [[ ! -x "${BLENDER_BIN}" ]] && ! command -v "${BLENDER_BIN}" >/dev/null 2>&1; then
  echo "ERROR: Blender executable not found: ${BLENDER_BIN}" >&2
  echo "Install Blender and set BLENDER_BIN, for example:" >&2
  echo "  export BLENDER_BIN=\"/Applications/Blender.app/Contents/MacOS/Blender\"" >&2
  exit 1
fi

export SPACE_GAME_ROOT="${ROOT_DIR}"
"${BLENDER_BIN}" --background --python tools/blender/bootstrap_shuttle_a_scene.py

