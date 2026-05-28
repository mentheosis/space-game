#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

SOURCE_DIR="${ROOT_DIR}/assets/source/blender/ships/prototype_shuttle"
MODEL_DIR="${ROOT_DIR}/assets/models/ship/prototype_shuttle"
REPORT_DIR="${ROOT_DIR}/reports/ship_pipeline"

required_files=(
  "${SOURCE_DIR}/prototype_shuttle_marker_contract.json"
  "${SOURCE_DIR}/prototype_shuttle_light_contract.json"
  "${SOURCE_DIR}/prototype_shuttle_scale_proxy_contract.json"
  "${MODEL_DIR}/prototype_shuttle_exterior.glb"
  "${MODEL_DIR}/prototype_shuttle_interior.glb"
  "${MODEL_DIR}/prototype_shuttle_collision.glb"
  "${MODEL_DIR}/prototype_shuttle_markers.json"
  "${MODEL_DIR}/prototype_shuttle_asset_report.json"
  "${MODEL_DIR}/prototype_shuttle_material_report.json"
  "${MODEL_DIR}/prototype_shuttle_light_report.json"
  "${MODEL_DIR}/prototype_shuttle_scale_proxy_report.json"
)

for path in "${required_files[@]}"; do
  if [[ ! -s "${path}" ]]; then
    echo "ERROR: Expected prototype shuttle artifact is missing or empty: ${path}" >&2
    exit 1
  fi
done

python3 -m json.tool "${MODEL_DIR}/prototype_shuttle_markers.json" >/dev/null
python3 -m json.tool "${MODEL_DIR}/prototype_shuttle_asset_report.json" >/dev/null
python3 -m json.tool "${MODEL_DIR}/prototype_shuttle_material_report.json" >/dev/null
python3 -m json.tool "${MODEL_DIR}/prototype_shuttle_light_report.json" >/dev/null
python3 -m json.tool "${MODEL_DIR}/prototype_shuttle_scale_proxy_report.json" >/dev/null

python3 tools/ship_pipeline/validate_ship_scale_proxies.py \
  --proxy-contract "${SOURCE_DIR}/prototype_shuttle_scale_proxy_contract.json" \
  --marker-contract "${SOURCE_DIR}/prototype_shuttle_marker_contract.json" \
  --report "${REPORT_DIR}/prototype_shuttle_scale_proxy_validation_report.json"

python3 tools/ship_pipeline/validate_ship_package.py \
  --asset-report "${MODEL_DIR}/prototype_shuttle_asset_report.json" \
  --material-report "${MODEL_DIR}/prototype_shuttle_material_report.json" \
  --light-report "${MODEL_DIR}/prototype_shuttle_light_report.json" \
  --scale-proxy-report "${MODEL_DIR}/prototype_shuttle_scale_proxy_report.json"

echo "Prototype shuttle package validation passed."
