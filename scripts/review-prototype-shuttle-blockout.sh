#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

LOG_PATH="${ROOT_DIR}/reports/prototype_shuttle_blockout_review.log"
mkdir -p "${ROOT_DIR}/reports"
exec > >(tee "${LOG_PATH}") 2>&1

DOTNET_BIN_OVERRIDE="${DOTNET_BIN:-}"
GODOT_BIN_OVERRIDE="${GODOT_BIN:-}"
BLENDER_BIN_OVERRIDE="${BLENDER_BIN:-}"

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

if [[ -n "${BLENDER_BIN_OVERRIDE}" ]]; then
  BLENDER_BIN="${BLENDER_BIN_OVERRIDE}"
fi

DOTNET_BIN="${DOTNET_BIN:-dotnet}"
GODOT_BIN="${GODOT_BIN:-godot}"
BLENDER_BIN="${BLENDER_BIN:-blender}"

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

if [[ ! -x "${BLENDER_BIN}" ]] && ! command -v "${BLENDER_BIN}" >/dev/null 2>&1; then
  echo "ERROR: Blender executable not found: ${BLENDER_BIN}" >&2
  echo "Set BLENDER_BIN or run: source .tools/env.sh" >&2
  exit 1
fi

echo "Using dotnet: ${DOTNET_BIN}"
echo "Using Godot: ${GODOT_BIN}"
echo "Using Blender: ${BLENDER_BIN}"

echo "Bootstrapping prototype shuttle Blender scene"
scripts/bootstrap-prototype-shuttle-blender.sh

echo "Exporting prototype shuttle Blender package"
scripts/export-prototype-shuttle-blender.sh

echo "Validating prototype shuttle package"
scripts/validate-prototype-shuttle-package.sh

echo "Validating prototype shuttle collision layout"
scripts/validate-prototype-shuttle-collision-layout.sh

echo "Building C# project"
"${DOTNET_BIN}" build SmallSolarSystem.csproj

echo "Importing Godot project"
"${GODOT_BIN}" --headless --path . --import

echo "Validating prototype shuttle traversal"
scripts/validate-prototype-shuttle-traversal.sh

echo "Capturing prototype shuttle blockout evidence"
scripts/capture-prototype-shuttle-evidence.sh

echo "Analyzing deterministic ShuttleA shape fit"
scripts/analyze-prototype-shuttle-shape-fit.sh

echo "Extracting deterministic prototype shuttle interior volumes"
scripts/extract-prototype-shuttle-interior-volumes.sh

echo "Prototype shuttle blockout review passed."
echo "Review log: reports/prototype_shuttle_blockout_review.log"
