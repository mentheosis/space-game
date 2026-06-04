#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f "${ROOT_DIR}/.tools/env.sh" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.tools/env.sh"
fi

GODOT_BIN="${GODOT_BIN:-godot}"

if [[ ! -x "${GODOT_BIN}" ]] && ! command -v "${GODOT_BIN}" >/dev/null 2>&1; then
  echo "ERROR: Godot executable not found or not executable: ${GODOT_BIN}" >&2
  echo "Set GODOT_BIN or run: source .tools/env.sh" >&2
  exit 1
fi

echo "Opening MX01 playable inspection scene."
echo "Scene: res://ships/MX01/generated/scenes/mx01_playable_inspection.tscn"
echo "This is first-pass generated collision: floors, stair treads, connector landings, and guard rails."

"${GODOT_BIN}" --path . res://ships/MX01/generated/scenes/mx01_playable_inspection.tscn
