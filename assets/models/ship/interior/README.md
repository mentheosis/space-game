# ShuttleA Interior Authored Asset Manifest

These meshes are project-authored MVP interior pieces for the current ShuttleA
ship integration. They are intentionally small, source-readable OBJ files so
the 0.2.1b alignment workbench can measure them without launching Godot.

The contract for this folder is:

- every listed OBJ must remain present,
- every listed OBJ must be referenced by `scenes/ship/Ship.tscn`,
- visible fitted interior pieces should use these meshes instead of primitive
  placeholder boxes,
- if a mesh is replaced, update this manifest and
  `tools/ship_alignment_report.py` in the same change.

## Required Assets

| File | Role |
| --- | --- |
| `cabin_floor_tapered.obj` | Main tapered walkable cabin floor plate. |
| `cabin_wall_panel.obj` | Mirrored shaped side wall panel. |
| `forward_bulkhead_tapered.obj` | Forward cockpit/cabin boundary. |
| `rear_bulkhead_tapered.obj` | Rear hatch/cabin boundary. |
| `cockpit_console_tapered.obj` | Main cockpit console body. |
| `cockpit_screen_cluster.obj` | Emissive cockpit display cluster. |
| `cockpit_control_cluster.obj` | Raised cockpit control cluster. |
| `pilot_chair_frame.obj` | Pilot chair structural shell. |
| `pilot_chair_cushions.obj` | Pilot chair cushion shell. |
| `hatch_door_recessed.obj` | Recessed hatch door panel. |
| `hatch_frame_beveled.obj` | Beveled hatch surround frame. |
| `cabin_rib_frame.obj` | Reusable structural cabin rib frame. |

## Alignment Notes

These assets are not final production models. They are the first repeatable
asset set for proving scale, cockpit readability, hatch placement, and interior
physical alignment against the ShuttleA exterior. The next collision work should
derive physical surfaces from measured meshes or authored collision assets
rather than broad hand-placed boxes.
