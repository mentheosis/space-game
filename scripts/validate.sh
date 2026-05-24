#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

DOTNET_BIN_OVERRIDE="${DOTNET_BIN:-}"
GODOT_BIN_OVERRIDE="${GODOT_BIN:-}"

if [[ -f "${ROOT_DIR}/.tools/env.sh" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.tools/env.sh"
fi

if [[ -n "${DOTNET_BIN_OVERRIDE}" ]]; then
  DOTNET_BIN="${DOTNET_BIN_OVERRIDE}"
fi

if [[ -n "${GODOT_BIN_OVERRIDE}" ]]; then
  GODOT_BIN="${GODOT_BIN_OVERRIDE}"
fi

DOTNET_BIN="${DOTNET_BIN:-dotnet}"
GODOT_BIN="${GODOT_BIN:-godot}"

echo "Building C# project"
"${DOTNET_BIN}" build SmallSolarSystem.csproj

echo "Importing Godot project"
"${GODOT_BIN}" --headless --path . --import

echo "Smoke testing Phase 1 scene"
"${GODOT_BIN}" --headless --path . --quit-after 30 scenes/solar_system/Phase1TestWorld.tscn

echo "Running Phase 1 automated validation"
"${GODOT_BIN}" --headless --path . scenes/solar_system/Phase1Validation.tscn

echo "Running Phase 2 automated validation"
"${GODOT_BIN}" --headless --path . scenes/solar_system/Phase2Validation.tscn

echo "Running Phase 3 automated validation"
"${GODOT_BIN}" --headless --path . scenes/solar_system/Phase3Validation.tscn
