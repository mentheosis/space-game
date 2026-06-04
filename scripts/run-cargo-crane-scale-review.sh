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
  echo "ERROR: Godot executable not found or executable: ${GODOT_BIN}" >&2
  echo "Set GODOT_BIN or run: source .tools/env.sh" >&2
  exit 1
fi

echo "Opening CargoCrane scale review demo."
echo "Candidate dimensions: 52.04m wide x 28.12m tall x 149.62m long."
echo "Clean review view: opaque ship skin, opaque walkable collision surfaces, and opaque enclosure bands."
echo "Controls: walk normally; press G to toggle ship skin, T to toggle walkable collision surfaces, E to toggle enclosure bands."
"${GODOT_BIN}" --path . res://scenes/debug/CargoCraneScaleReview.tscn
