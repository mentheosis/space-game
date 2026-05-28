# 0.3.2 Production Prototype Shuttle Reference Brief

## Decision Summary

- Ship id: `prototype_shuttle`
- Role: larger compact exploration shuttle, still small enough for early gameplay but no longer a one-person craft
- Scale target: two-seat cockpit, standing cockpit/cabin where practical, forward-opening belly ramp under the main hull, lower cargo deck, upper cockpit deck, cockpit canopy, and small equipment/cargo allowance
- Direction: use ShuttleA as broad exterior inspiration only, not as a model to copy
- Pipeline: Blender-first package asset, with Godot hosting gameplay logic and validation

## Reference Set

### ShuttleA Exterior Reference

Files:

- `shuttle_a_exterior_front.png`
- `shuttle_a_exterior_rear.png`
- `shuttle_a_exterior_left.png`
- `shuttle_a_exterior_top.png`
- `shuttle_a_cockpit_glass_close.png`

Source:

- Captured from the current ShuttleA prototype and OpenGameArt shuttle reference model.
- Original model files remain at `assets/models/ship/placeholders/oga_3d_space_ship_pack/ShuttleA.obj` and `.mtl`.

Use for:

- broad shuttle proportions and exterior massing
- forward cockpit/canopy placement
- swept/functional exterior silhouette language
- underside belly volume that can support a ramp/cargo deck concept
- relationship between exterior hull and cockpit glass

Do not copy:

- exact mesh topology
- exact scale
- exact collision shape
- current interior placement
- current hatch solution

Design note:

The new ship should be a clean replacement asset inspired by the broad ShuttleA read: swept exterior, forward canopy, large belly volume, and practical explorer craft stance. It should not copy ShuttleA's current rear view as a hatch design. The production prototype should instead use a forward-opening ramp/hatch in the underside belly section. The ramp should lead into a lower cargo deck, with stairs or a short internal rise up into a cockpit deck. It should not inherit ShuttleA's cramped cockpit/interior mismatch or manual scene-history artifacts.

### Cockpit References

Files:

- `cockpit_ref_1.webp`
- `cockpit_ref_2.png`
- `cockpit_ref_3.webp`

Use for:

- clear transparent viewport/canopy treatment
- believable structural bulkheads around cockpit glass
- pilot/copilot seat shapes that do not obstruct forward view
- cockpit detail density without random noise
- instrument/control placement around the pilot rather than directly blocking the canopy

Design note:

The prototype shuttle cockpit should keep a clear view through the canopy for both pilot and copilot positions. Seats should feel integrated and human-scaled, with visible supporting structure, but should not become large walls in front of the player or block standing movement around the cockpit.

### Interior Lighting And Material Reference

File:

- `interior_lighting_material_ref.jpeg`

Use for:

- material richness and separation
- practical light source logic
- readable floor path and wall structure
- controlled reflectivity
- panel and trim detail that feels manufactured

Do not copy:

- exact color palette
- exact lounge layout
- bright white sci-fi room style as the only target

Design note:

The current desired mood is readable sci-fi interior rather than uniformly bright showroom. We should borrow material realism, fixture logic, and surface detail discipline without forcing the new shuttle into the exact brightness or panel style of the reference.

## 0.3.2a Blockout Targets

The first implementation pass should prove:

- exterior hull can contain the desired interior
- forward-opening belly ramp aligns with the lower cargo deck
- lower cargo deck has enough volume to feel like a real entry/cargo space
- cockpit deck sits above the cargo deck and is reached by stairs, ramp, or a short internal rise
- cockpit canopy aligns with two pilot/copilot eye positions
- both seated pilot proxies fit under canopy
- standing player proxy fits in the cockpit/cabin areas where intended
- pilot and copilot can see through the canopy without opaque obstruction
- player capsule can move from belly ramp to cargo deck to cockpit deck

## Initial Dimension Targets

These are starting targets, not final measurements:

- Overall length: 16-20 m
- Overall width: 9-13 m including wings/fins
- Hull/cabin width: 4.5-6.5 m around the cargo/cockpit volume
- Lower cargo deck standing clearance: 1.9-2.3 m where the player enters
- Cockpit deck standing clearance: 1.9-2.2 m near seats where practical
- Belly ramp opening width: 1.8-2.6 m
- Belly ramp opening height: 1.8-2.3 m
- Vertical rise from cargo deck to cockpit deck: roughly 0.8-1.5 m, subject to blockout fit
- Cockpit canopy eye clearance: pilot and copilot eyes should have clear forward/upward view
- Seat width: roughly 0.7-0.9 m per seat, with aisle/standing clearance nearby
- Walkable route width: minimum 0.9 m, preferred 1.1-1.4 m

## First-Pass Design Constraints

- Keep exterior and interior in the same Blender scene from the start.
- Use required package collections: `Exterior`, `Interior`, `Collision`, `Markers`, `Lights`, `ReviewCameras`, `ScaleProxies`, `Disabled_Source`.
- Use package markers and scale proxies before detailed modeling.
- Keep blockout geometry simple and readable.
- Do not add fine detail until the scale, canopy, ramp, and traversal are approved.
- Avoid Godot-authored visual geometry for the new ship except temporary debugging helpers.

## Human Review Questions For Blockout

Before detail modeling, review:

- Does the ship silhouette feel like a compact exploration shuttle?
- Does the cockpit/canopy location make sense from exterior and interior?
- Does the interior volume feel physically contained by the hull?
- Is the forward-opening belly ramp plausible and useful for gameplay?
- Does the two-level cargo-to-cockpit layout feel physically coherent?
- Is the ship large enough for two cockpit seats and comfortable traversal without becoming too large for early gameplay?
- Should the silhouette stay symmetrical, or should we introduce asymmetry later?

## Reference Folder Contents

This folder should remain the source trail for 0.3.2 visual direction. If new references are added, update this brief with:

- filename
- source/license note if applicable
- what the reference contributes
- what should not be copied
