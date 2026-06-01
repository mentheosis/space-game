#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f "$ROOT_DIR/.tools/env.sh" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.tools/env.sh"
fi

BLENDER_BIN="${BLENDER_BIN:-blender}"
SOURCE_BLEND="$ROOT_DIR/assets/source/blender/ships/prototype_shuttle/prototype_shuttle.blend"
REFRESH_PROTOTYPE_SHUTTLE="${REFRESH_PROTOTYPE_SHUTTLE:-1}"

if [[ ! -f "$SOURCE_BLEND" ]]; then
  echo "Missing prototype shuttle Blender source: $SOURCE_BLEND" >&2
  exit 1
fi

if [[ "$REFRESH_PROTOTYPE_SHUTTLE" != "0" ]]; then
  echo "Refreshing prototype shuttle exported assets before visual evaluation..."
  scripts/export-prototype-shuttle-blender.sh
fi

export SPACE_GAME_ROOT="$ROOT_DIR"

set +e
"$BLENDER_BIN" --background "$SOURCE_BLEND" --python tools/blender/evaluate_prototype_shuttle_interior_visuals.py
exit_status=$?
set -e

echo
echo "Visual evaluation artifacts:"
echo "  reports/prototype_shuttle_visual_eval/interior_visual_eval_report.md"
echo "  reports/prototype_shuttle_visual_eval/interior_visual_eval_report.json"
echo "  reports/prototype_shuttle_visual_eval/interior_visual_eval_contact_sheet_current.png"
echo "  reports/prototype_shuttle_visual_eval/interior_region_orbit_contact_sheet_current.png"
echo "  reports/prototype_shuttle_visual_eval/attachment_debug_overlay_current.png"
echo "  reports/prototype_shuttle_visual_eval/material_id_contact_sheet_current.png"

exit "$exit_status"
