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

echo "Opening shuttle p3 traversal review."
echo "Route to test: entry ramp -> cargo floor -> stairs/corridor -> cockpit deck/seats."
echo "Press V to toggle generated traversal surface visibility."
"${GODOT_BIN}" --path . res://scenes/debug/ShuttleP3TraversalReview.tscn
