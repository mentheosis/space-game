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

echo "Generating 0.2.1b ship alignment report"
python3 tools/ship_alignment_report.py --check
python3 tools/ship_fit_recommendations.py --check
python3 tools/ship_alignment_dashboard.py --check

echo "Building C# project"
"${DOTNET_BIN}" build SmallSolarSystem.csproj

echo "Importing Godot project"
"${GODOT_BIN}" --headless --path . --import

echo "Running 0.2.1b ship interior validation"
"${GODOT_BIN}" --headless --path . scenes/solar_system/Phase021bValidation.tscn
