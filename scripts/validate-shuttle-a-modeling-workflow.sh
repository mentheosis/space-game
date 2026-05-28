#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f "${ROOT_DIR}/.tools/env.sh" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.tools/env.sh"
fi

BLENDER_BIN="${BLENDER_BIN:-blender}"
GODOT_BIN="${GODOT_BIN:-godot}"
DOTNET_BIN="${DOTNET_BIN:-dotnet}"

if [[ ! -x "${BLENDER_BIN}" ]] && ! command -v "${BLENDER_BIN}" >/dev/null 2>&1; then
  echo "ERROR: Blender executable not found: ${BLENDER_BIN}" >&2
  exit 1
fi

echo "Exporting ShuttleA Blender source"
scripts/export-shuttle-a-blender.sh

for artifact in \
  assets/source/blender/ships/shuttle_a/shuttle_a_interior.blend \
  assets/models/ship/shuttle_a/shuttle_a_interior.glb \
  assets/models/ship/shuttle_a/shuttle_a_collision.glb \
  assets/models/ship/shuttle_a/shuttle_a_markers.json \
  assets/models/ship/shuttle_a/shuttle_a_asset_report.json \
  assets/models/ship/shuttle_a/shuttle_a_material_report.json \
  assets/models/ship/shuttle_a/shuttle_a_light_report.json \
  assets/models/ship/shuttle_a/shuttle_a_scale_proxy_report.json \
  reports/ship_modeling/shuttle_a_export_report.json; do
  if [[ ! -s "${artifact}" ]]; then
    echo "ERROR: Expected artifact is missing or empty: ${artifact}" >&2
    exit 1
  fi
done

python3 -m json.tool assets/models/ship/shuttle_a/shuttle_a_markers.json >/dev/null
python3 -m json.tool assets/models/ship/shuttle_a/shuttle_a_asset_report.json >/dev/null
python3 -m json.tool assets/models/ship/shuttle_a/shuttle_a_material_report.json >/dev/null
python3 -m json.tool assets/models/ship/shuttle_a/shuttle_a_light_report.json >/dev/null
python3 -m json.tool assets/models/ship/shuttle_a/shuttle_a_scale_proxy_report.json >/dev/null
python3 -m json.tool reports/ship_modeling/shuttle_a_export_report.json >/dev/null
echo "Validating ShuttleA package markers against Godot scene"
python3 tools/ship_pipeline/sync_ship_markers.py --source exported --check
echo "Validating ShuttleA package lights against Godot scene"
python3 tools/ship_pipeline/sync_ship_lights.py --check
echo "Validating ShuttleA scale proxy contract"
python3 tools/ship_pipeline/validate_ship_scale_proxies.py
echo "Validating ShuttleA package reports"
python3 tools/ship_pipeline/validate_ship_package.py

if [[ -x "${GODOT_BIN}" ]] || command -v "${GODOT_BIN}" >/dev/null 2>&1; then
  echo "Importing Godot project after Blender export"
  "${GODOT_BIN}" --headless --path . --import
else
  echo "Skipping Godot import; GODOT_BIN is not available in this shell."
fi

if command -v "${DOTNET_BIN}" >/dev/null 2>&1; then
  echo "Building C# project"
  "${DOTNET_BIN}" build SmallSolarSystem.csproj
else
  echo "Skipping dotnet build; DOTNET_BIN/dotnet is not available in this shell."
fi

if [[ -x "${GODOT_BIN}" ]] || command -v "${GODOT_BIN}" >/dev/null 2>&1; then
  echo "Running airborne ship interior frame validation"
  "${GODOT_BIN}" --headless --path . scenes/solar_system/Phase4Validation.tscn
  echo "Capturing ShuttleA 0.3 reference screenshots"
  "${GODOT_BIN}" --path . res://scenes/debug/ShipReferenceCapture.tscn
  echo "Capturing ShuttleA interior walkthrough"
  scripts/capture-ship-walkthrough.sh
  echo "Running ShuttleA interior runtime validation"
  "${GODOT_BIN}" --headless --path . scenes/solar_system/Phase021bValidation.tscn
  echo "Capturing ShuttleA cockpit walkthrough"
  scripts/capture-ship-cockpit-walkthrough.sh
fi

echo "ShuttleA modeling workflow validation passed."
