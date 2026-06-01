#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f "${ROOT_DIR}/.tools/env.sh" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.tools/env.sh"
fi

GODOT_BIN="${GODOT_BIN:-godot}"
REFRESH_PROTOTYPE_SHUTTLE="${REFRESH_PROTOTYPE_SHUTTLE:-1}"

if [[ ! -x "${GODOT_BIN}" ]] && ! command -v "${GODOT_BIN}" >/dev/null 2>&1; then
  echo "ERROR: Godot executable not found or not executable: ${GODOT_BIN}" >&2
  echo "Set GODOT_BIN or run: source .tools/env.sh" >&2
  exit 1
fi

if [[ "${REFRESH_PROTOTYPE_SHUTTLE}" != "0" ]]; then
  echo "Refreshing prototype shuttle Blender export..."
  scripts/export-prototype-shuttle-blender.sh

  echo "Importing refreshed prototype shuttle assets into Godot..."
  "${GODOT_BIN}" --path . --headless --import
fi

"${GODOT_BIN}" --path . res://scenes/debug/PrototypeShuttleDebugWorld.tscn
