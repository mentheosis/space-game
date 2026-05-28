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

if [[ ! -f tools/blender/bootstrap_prototype_shuttle_scene.py ]]; then
  echo "ERROR: Missing tools/blender/bootstrap_prototype_shuttle_scene.py" >&2
  echo "Create the prototype shuttle Blender bootstrap tool before running this profile." >&2
  exit 1
fi

export SPACE_GAME_ROOT="${ROOT_DIR}"
if [[ -f "${SOURCE_BLEND}" && "${PROTOTYPE_SHUTTLE_ALLOW_BOOTSTRAP_OVERWRITE:-0}" != "1" ]]; then
  cat >&2 <<MSG
ERROR: Refusing to overwrite authored prototype shuttle source:
  ${SOURCE_BLEND}

The prototype shuttle is now Blender-authored source. Use
scripts/export-prototype-shuttle-blender.sh for normal asset updates.

If you intentionally want to regenerate the procedural blockout and discard
authored edits, rerun with:
  PROTOTYPE_SHUTTLE_ALLOW_BOOTSTRAP_OVERWRITE=1 scripts/bootstrap-prototype-shuttle-blender.sh
MSG
  exit 1
fi

"${BLENDER_BIN}" --background --python tools/blender/bootstrap_prototype_shuttle_scene.py
