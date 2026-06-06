#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f "${ROOT_DIR}/.tools/env.sh" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.tools/env.sh"
fi

GODOT_BIN="${GODOT_BIN:-godot}"
CAPTURE_SCENE="ships/MX01/generated/scenes/mx01_walkthrough_replay_capture.tscn"
if [[ $# -gt 0 ]]; then
  MANIFEST_ARG="$1"
else
  MANIFEST_ARG="$(find ships/MX01/reports/walkthrough_paths -maxdepth 1 -name 'mx01_walkthrough_*.json' -type f -print | sort | tail -n 1)"
fi
MANIFEST_REL="${MANIFEST_ARG#res://}"
MANIFEST_REL="${MANIFEST_REL#${ROOT_DIR}/}"
BASE_NAME="$(basename "${MANIFEST_REL}" .json)"
OUT_REL="ships/MX01/reports/walkthrough_captures/${BASE_NAME}"
OUT_DIR="${ROOT_DIR}/${OUT_REL}"

if [[ ! -x "${GODOT_BIN}" ]] && ! command -v "${GODOT_BIN}" >/dev/null 2>&1; then
  echo "ERROR: Godot executable not found or not executable: ${GODOT_BIN}" >&2
  echo "Set GODOT_BIN or run: source .tools/env.sh" >&2
  exit 1
fi

if [[ ! -f "${CAPTURE_SCENE}" ]]; then
  echo "ERROR: Missing ${CAPTURE_SCENE}" >&2
  exit 1
fi

if [[ ! -f "${MANIFEST_REL}" ]]; then
  echo "ERROR: Missing walkthrough manifest ${MANIFEST_REL}" >&2
  exit 1
fi

rm -rf "${OUT_DIR}/frames"
mkdir -p "${OUT_DIR}/frames"

MX01_WALKTHROUGH_MANIFEST="res://${MANIFEST_REL}" \
MX01_WALKTHROUGH_OUTPUT="res://${OUT_REL}" \
  "${GODOT_BIN}" --path . "res://${CAPTURE_SCENE}"

python3 tools/raw_rgb_to_review_artifacts.py "${OUT_REL}" "${BASE_NAME}"
rm -rf "${OUT_DIR}/frames"

echo "MX01 walkthrough MP4: ${OUT_REL}/${BASE_NAME}_current.mp4"
echo "MX01 walkthrough contact sheet: ${OUT_REL}/${BASE_NAME}_contact_sheet_current.png"
