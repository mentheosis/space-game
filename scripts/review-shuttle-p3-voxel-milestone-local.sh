#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

python3 tools/ship_pipeline/build_shuttle_p3_from_exterior_glb.py
python3 -m json.tool reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_voxel_report.json >/dev/null
test -s reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_exterior_skin_projection_current.png
test -s reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_voxel_free_space_projection_current.png
test -s reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_semantic_regions_projection_current.png

echo "Shuttle P3 local voxel milestone review passed."
