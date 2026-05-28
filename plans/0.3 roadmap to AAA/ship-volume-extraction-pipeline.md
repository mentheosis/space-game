# Ship Volume Extraction Pipeline

This document captures the repeatable process learned during the prototype shuttle volume lock. The goal is to turn a ship exterior mesh into validated interior planning volumes before detailed interior art, collision, animation, or gameplay integration begins.

## Purpose

The volume extraction stage answers one question:

Can this exterior ship shape support the intended interior layout with plausible scale, connected walkable spaces, and clear semantic regions?

This stage is not final art and not final collision. It is a deterministic planning and validation pass that prevents us from modeling interiors into a shape that cannot physically contain them.

## Inputs

- Source exterior mesh or reference mesh.
- Ship design brief.
- Intended interior roles, for example cargo, cockpit, engineering, bunks, corridors, ramp, hatch, seats.
- Player scale and clearance requirements.
- Required traversal path, for example entry -> cargo -> transition -> cockpit.
- Any known animated entry components, such as ramps, hatches, lifts, ladders, or docking ports.

## Output Artifacts

Each ship volume extraction pass should produce:

- Exterior shape fit report.
- Interior volume extraction report.
- Projection/contact-sheet evidence.
- Semantic volume definitions.
- Connectivity validation results.
- Scale proxy validation results.
- Generated Godot/GLB debug assets for review.

For the prototype shuttle, the key current artifacts are:

- `reports/prototype_shuttle_shape_fit/shape_fit_report.md`
- `reports/prototype_shuttle_volume_fit/interior_volume_report.md`
- `reports/prototype_shuttle_volume_fit/interior_volume_projection_current.png`
- `reports/prototype_shuttle_blockout/prototype_shuttle_blockout_contact_sheet_current.png`

## Pipeline

### 1. Exterior Silhouette Lock

Start with the exterior. Do not design the interior layout against an unstable hull.

Acceptance criteria:

- Exterior silhouette matches the chosen reference from front, side, top, and three-quarter views.
- Any intentional design deltas are documented.
- Scale is large enough for the intended interior concept.
- The asset has stable orientation and coordinate conventions.

### 2. Usable Interior Envelope Extraction

Extract a clearance field from the exterior shape. The extraction should avoid guessing fixed boxes directly.

Current prototype approach:

- Slice the exterior along ship length.
- Build robust central fuselage profiles using quantiles instead of full min/max so wings, fins, and decorative details do not dominate interior volume.
- Sample usable interior points inside the central fuselage envelope.
- Apply wall and player clearance margins.

Future improvement:

- Use true mesh inside/outside tests or signed distance fields when the exterior mesh is sufficiently closed and clean.
- Store the extraction settings in a ship config file instead of hard-coding them per ship.

### 3. Semantic Volume Fitting

Fit named volumes to the usable envelope. Do not use arbitrary boxes as the first design mechanism.

Recommended semantic volumes:

- Cargo or main cabin.
- Cockpit or bridge.
- Transition/neck/corridor.
- Entry ramp or hatch zone.
- Seat positions.
- Special functional spaces as needed.

Volume representation should match shape complexity:

- Use boxes only for simple placeholders, markers, or temporary collision.
- Use prismatic sections for tapered or curved fuselage spaces.
- Use multiple sections when a space widens, narrows, rises, or changes floor height.
- Treat animated entry elements as special-case assemblies, not ordinary room volumes.

Prototype shuttle decision:

- Cargo is represented as a blue prismatic volume.
- Cockpit is represented as a yellow forward volume.
- Cargo-to-cockpit transition is represented as a green prismatic connector.
- Ramp remains a red placeholder because it will become an animated hatch/ramp assembly.

### 4. Connectivity Validation

Connectivity must be validated at the volume stage. Do not defer basic continuity questions to final collision.

Required checks:

- Entry/ramp overlaps the first interior volume.
- Cargo/main cabin overlaps the transition volume.
- Transition volume overlaps cockpit/bridge volume.
- Minimum connector width is greater than player width plus clearance.
- Floor heights meet within tolerance or have enough length/height for a ramp/stair solution.
- Projection evidence shows a continuous route through the ship.

For the prototype shuttle, current connectivity checks include:

- `transition_overlaps_cockpit`
- `transition_overlaps_cargo`
- `transition_minimum_width`
- `cargo_floor_meets_transition`

### 5. Scale Proxy Validation

Place scale proxies before detailed art begins.

Required proxies:

- Standing player in cargo/main cabin.
- Standing player in cockpit or bridge, if intended.
- Seated pilot.
- Seated copilot/passenger if intended.
- Entry/ramp standing position.
- Critical traversal points.

Acceptance criteria:

- Proxies fit without clipping volume ceilings.
- Seats do not block the entire cockpit view.
- Standing positions have plausible head clearance.
- Entry/exit markers are inside intended spaces.

### 6. Evidence Review

Every volume iteration should produce visual evidence that makes failures obvious.

Required views:

- Exterior shape/contact sheet.
- Interior volume projection: side, top, front.
- Optional Godot flythrough or no-collision scene.

The projection should use consistent color conventions:

- Blue: cargo/main cabin.
- Yellow: cockpit/bridge.
- Green: transition/connector.
- Red/orange: ramp/hatch entry element.
- Purple: seats or occupant proxies.

### 7. Volume Lock Decision

Only proceed to detailed modeling when:

- Exterior silhouette is accepted.
- Interior semantic volumes fit the hull.
- Connectivity checks pass.
- Scale proxies pass.
- Remaining special-case elements are explicitly scoped for later work.

For the prototype shuttle, the ramp placeholder is acceptable during volume lock because the ramp is a future animated component.

## What To Generalize Next

The current prototype shuttle implementation is useful but still too ship-specific. Before the next ship, extract the following into reusable configuration:

- `ship_id`
- source exterior mesh path
- source/reference transform
- semantic volume names
- volume color conventions
- player clearance settings
- section count per semantic volume
- connector requirements
- validation thresholds
- generated report paths
- debug scene/capture configuration

The target interface should be:

```text
ship_volume_extract --ship-id <id> --config <ship-volume-config.json>
```

The output should be the same report/evidence package regardless of ship type.

## Collision Floor Discovery Stage

After semantic volumes and connectivity pass, add an automated floorplan
discovery stage before detailed interior art.

The prototype shuttle proved this workflow:

1. Start from an intentionally invalid no-walkable-floorplan state.
2. Generate candidate walkable surfaces from semantic volumes:
   - entry/ramp surface,
   - ramp-to-main-deck connection,
   - main floor segments,
   - stairs/ramps/transition lanes,
   - cockpit/bridge landing,
   - cockpit/bridge floor.
3. Export a machine-readable collision layout report.
4. Run static adjacency validation.
5. Run real engine traversal validation with the player controller.
6. Score candidates by traversal success, low auto-step reliance, fewer special
   cases, landing depth, small gaps/lips, and staying inside the interior
   envelope.
7. Persist the selected candidate as the active floorplan for subsequent
   export/review profiles.
8. Use human playtest as the final acceptance check after automated validation.

This stage should not depend on a human-approved golden floorplan. A golden
baseline may be useful for a prototype calibration pass, but the repeatable
pipeline for new ships should run blind and use any baseline only for post-hoc
comparison.

## Lessons From Prototype Shuttle

- Do not rely on hand-placed boxes for interior planning.
- Do not lock interior art before exterior volume and connectivity are validated.
- Single boxes are useful for markers, but poor for curved ship interiors.
- Piecewise boxes help diagnose shape, but can become visually noisy.
- Prismatic sections are a better intermediate representation for fuselage spaces.
- Connectivity must be explicit and measurable.
- Animated hatches and ramps should be modeled as special-case assemblies after volume lock.
