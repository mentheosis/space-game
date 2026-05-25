#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

LOG_PATH="${ROOT_DIR}/reports/ship_phase_0_2_1b_host_review.log"
mkdir -p "${ROOT_DIR}/reports"
exec > >(tee "${LOG_PATH}") 2>&1

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

if ! command -v "${DOTNET_BIN}" >/dev/null 2>&1; then
  echo "ERROR: dotnet executable not found: ${DOTNET_BIN}" >&2
  echo "Set DOTNET_BIN or run: source .tools/env.sh" >&2
  exit 1
fi

if [[ ! -x "${GODOT_BIN}" ]] && ! command -v "${GODOT_BIN}" >/dev/null 2>&1; then
  echo "ERROR: Godot executable not found or not executable: ${GODOT_BIN}" >&2
  echo "Set GODOT_BIN or run: source .tools/env.sh" >&2
  exit 1
fi

echo "Using dotnet: ${DOTNET_BIN}"
echo "Using Godot: ${GODOT_BIN}"

echo "Running 0.2.1b static preflight"
scripts/preflight-0.2.1b-static.sh

echo "Building C# project"
"${DOTNET_BIN}" build SmallSolarSystem.csproj

echo "Importing Godot project"
"${GODOT_BIN}" --headless --path . --import

echo "Running 0.2.1b Godot validation"
"${GODOT_BIN}" --headless --path . scenes/solar_system/Phase021bValidation.tscn

echo "Capturing 0.2.1b alignment screenshots"
scripts/capture-ship-alignment.sh

echo "0.2.1b host review passed."
echo "Review dashboard: reports/ship_alignment_dashboard.html"
echo "Review checklist: reports/ship_alignment_review_checklist.md"
echo "Completion audit: reports/ship_phase_0_2_1b_completion_audit.md"
echo "Host review log: reports/ship_phase_0_2_1b_host_review.log"
