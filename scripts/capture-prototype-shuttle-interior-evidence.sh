#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f "${ROOT_DIR}/.tools/env.sh" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.tools/env.sh"
fi

GODOT_BIN="${GODOT_BIN:-godot}"
CAPTURE_SCENE="scenes/debug/PrototypeShuttleInteriorCapture.tscn"
OUT_DIR="${ROOT_DIR}/reports/prototype_shuttle_interior"
FRAMES_DIR="${OUT_DIR}/frames"

if [[ ! -x "${GODOT_BIN}" ]] && ! command -v "${GODOT_BIN}" >/dev/null 2>&1; then
  echo "ERROR: Godot executable not found or not executable: ${GODOT_BIN}" >&2
  echo "Set GODOT_BIN or run: source .tools/env.sh" >&2
  exit 1
fi

if [[ ! -f "${CAPTURE_SCENE}" ]]; then
  echo "ERROR: Missing ${CAPTURE_SCENE}" >&2
  echo "Create the prototype shuttle interior capture scene before running this profile." >&2
  exit 1
fi

rm -rf "${FRAMES_DIR}"
mkdir -p "${FRAMES_DIR}"

"${GODOT_BIN}" --path . "res://${CAPTURE_SCENE}"

if command -v ffmpeg >/dev/null 2>&1; then
  ffmpeg -y \
    -framerate 1 \
    -i "${FRAMES_DIR}/frame_%02d.png" \
    -vf "scale=520:-1,tile=5x2:padding=16:margin=16:color=0x101316" \
    -update 1 \
    -frames:v 1 \
    "${OUT_DIR}/prototype_shuttle_interior_contact_sheet_current.png"
  echo "Interior contact sheet: reports/prototype_shuttle_interior/prototype_shuttle_interior_contact_sheet_current.png"
else
  echo "WARNING: ffmpeg not found; skipping prototype shuttle interior contact sheet." >&2
fi

if [[ -f scripts/capture-prototype-shuttle-material-walkthrough.sh ]]; then
  bash scripts/capture-prototype-shuttle-material-walkthrough.sh
fi

if [[ -f tools/ship_pipeline/standardize_evidence.py ]]; then
  python3 tools/ship_pipeline/standardize_evidence.py
fi

echo "Prototype shuttle interior evidence capture passed."
