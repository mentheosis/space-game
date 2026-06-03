#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f "${ROOT_DIR}/.tools/env.sh" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.tools/env.sh"
fi

GODOT_BIN="${GODOT_BIN:-godot}"
CAPTURE_SCENE="scenes/debug/CargoCranePlayerWalkthroughCapture.tscn"
OUT_DIR="${ROOT_DIR}/reports/cargo_crane_player_walkthrough"

if [[ ! -x "${GODOT_BIN}" ]] && ! command -v "${GODOT_BIN}" >/dev/null 2>&1; then
  echo "ERROR: Godot executable not found or not executable: ${GODOT_BIN}" >&2
  echo "Set GODOT_BIN or run: source .tools/env.sh" >&2
  exit 1
fi

if [[ ! -f "${CAPTURE_SCENE}" ]]; then
  echo "ERROR: Missing ${CAPTURE_SCENE}" >&2
  exit 1
fi

if [[ "${SKIP_VALIDATION:-0}" != "1" ]]; then
  echo "Validating CargoCrane real player traversal"
  scripts/validate-cargo-crane-player-traversal.sh
else
  echo "Skipping CargoCrane real player traversal validation for capture-only run"
fi

rm -rf "${OUT_DIR}/frames"
mkdir -p "${OUT_DIR}/frames"

"${GODOT_BIN}" --path . "res://${CAPTURE_SCENE}"
python3 tools/raw_rgb_to_review_artifacts.py reports/cargo_crane_player_walkthrough cargo_crane_player_walkthrough

if [[ -f tools/ship_pipeline/standardize_evidence.py ]]; then
  python3 tools/ship_pipeline/standardize_evidence.py
fi

echo "CargoCrane player walkthrough MP4: reports/cargo_crane_player_walkthrough/cargo_crane_player_walkthrough_current.mp4"
echo "CargoCrane player walkthrough contact sheet: reports/cargo_crane_player_walkthrough/cargo_crane_player_walkthrough_contact_sheet_current.png"
