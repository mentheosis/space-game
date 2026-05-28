#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f "${ROOT_DIR}/.tools/env.sh" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.tools/env.sh"
fi

export DOTNET_BIN="${DOTNET_BIN:-dotnet}"
export GODOT_BIN="${GODOT_BIN:-godot}"
export BLENDER_BIN="${BLENDER_BIN:-blender}"

python3 tools/ship_pipeline/discover_prototype_shuttle_floorplan.py --blind --limit 120 --traversal-limit 12 "$@"
