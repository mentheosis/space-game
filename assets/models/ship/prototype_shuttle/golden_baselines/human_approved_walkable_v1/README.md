# Human-Approved Walkable Floorplan V1

This is a prototype-shuttle-specific golden baseline captured after manual
playtesting confirmed that the generated blockout has an acceptable walkable
interior route.

This baseline is **not** a required step in the repeatable ship pipeline. It is
only calibration data for the prototype shuttle while the floorplan candidate
discovery system is being developed.

## Approved Route

The approved route is:

`forward belly ramp -> cargo floor -> left stair lane -> cockpit entry landing -> cockpit floor`

The matching right stair lane is statically validated by the collision-layout
validator, but the current Godot traversal runner drives the left lane as the
representative playable route.

## Captured Evidence

- `collision_layout_report.json`
  - Generated named collision layout contract for the approved floorplan.
- `static_collision_layout_validation_report.json`
  - Static route connectivity validation for ramp, cargo, stairs, landing, and
    cockpit floor.
- `godot_traversal_validation_report.json`
  - Real Godot traversal validation using `PlayerController`.
- `floorplan_candidate.json`
  - Explicit candidate parameters that reproduce this human-approved baseline.

## Generator Values Of Interest

The baseline corresponds to the current deterministic generator values in
`tools/blender/bootstrap_prototype_shuttle_scene.py`:

- ramp top edge: cargo floor edge, lowered by `0.06m`
- ramp tip: `1.98m` lower and `3.95m` forward from the hinge
- cargo forward floor trim: `+1.25m` from original forward edge
- stair count: `10`
- stair width: `1.0m`
- stair depth multiplier: `1.08`
- side stair lane offset: `ramp_width * 0.5 + step_width * 0.5 + 0.18`
- cockpit entry landing depth: `3.2m`
- cockpit entry landing z placement: `start_z - cockpit_entry_depth * 0.42`

Future discovery work should use this only as a known-good comparison target,
not as a hardcoded requirement.
