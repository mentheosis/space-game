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
- side/top/front silhouette relationships
- raised forward cockpit/neck mass above a larger belly/cargo mass
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

The first generated `prototype_shuttle` blockout should not be treated as a design reference. It proved the pipeline only. The next pass should return to ShuttleA exterior screenshots and this brief to lock silhouette and gross volume before collision or traversal is evaluated.

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

### Cargo Ramp And Lower Deck Reference

File:

- `cargo_ramp_ref.jpg`

Use for:

- forward ramp opening composition viewed from outside into the cargo bay
- thick, rounded hatch frame and sidewall return surfaces around the opening
- ramp surface paneling, edge rails, and inset tread detail
- lower cargo deck wall/ceiling structure with strong manufactured panel rhythm
- ceiling practical light strips that visibly explain the interior illumination
- side equipment bays, vertical supports, grab points, vents, and recessed panels
- clear central walking path from ramp into the interior

Do not copy:

- exact color blocking or faction markings
- exact room proportions if they conflict with the prototype shuttle hull
- exact rear bulkhead/door layout
- high brightness level as a requirement

Design note:

The prototype shuttle lower deck should borrow the reference's sense that the ramp, hatch frame, sidewalls, ceiling, and floor are one coherent manufactured structure. The ramp should not read as a loose plank outside a hollow shell. The next structural pass should especially improve the ramp threshold, hatch frame thickness, cargo bay side panels, ceiling ribs/light housings, floor panel seams, and visible route into the ship.

## 0.3.2a Exterior Silhouette And Volume Lock Targets

The first implementation pass should prove:

- exterior hull silhouette reads correctly before gameplay traversal is tested
- lower belly cargo mass and raised forward cockpit/neck mass are clear in side view
- top view has swept shuttle proportions rather than a boxy rectangular body
- front view supports enough volume for a believable two-level interior
- forward-opening belly ramp is placed at the front of the belly/cargo mass, slightly aft of the cockpit nose
- gross lower cargo deck and upper cockpit deck volume proxies fit inside the hull
- cockpit canopy aligns with two pilot/copilot eye positions
- both seated pilot proxies fit under canopy
- standing player proxies fit in the intended cargo and cockpit volume envelopes
- pilot and copilot sightline rays pass through the canopy volume without opaque obstruction

Traversal from belly ramp to cockpit is intentionally deferred until the silhouette and gross volumes are approved.

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
