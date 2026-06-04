# Repeatable Voxel-First Ship Interior Process

This document captures the reusable process proven during `shuttle_p3`.
It is intentionally about ship asset creation only. Player-controller movement
helpers, support-surface runtime behavior, and playtest tuning are separate
gameplay systems and are not part of this repeatable asset pipeline.

## Goal

Create a ship interior that fits its exterior hull by deriving room volumes,
walkable surfaces, stairs, landings, rails, walls, and ceilings from voxelized
interior space instead of hand-guessing them from screenshots.

The key lesson from `shuttle_p3` is that the LLM became much more useful once
the ship interior was serialized into compact voxel and feature data. The LLM
should not invent geometry directly from vague screenshots. It should inspect
machine-generated spatial data, identify semantic intent, then propose or adjust
deterministic geometry rules.

## Required Inputs

- Accepted exterior skin mesh with scale, origin, and orientation locked.
- Any human-authored hull cuts that define real openings, such as ramp doors.
- Ship brief: entry location, cargo/living role, cockpit role, seat count, and
  expected traversal route.
- Player scale and clearance values.
- Reference images for later art direction, not for initial collision/layout.

For `shuttle_p3`, the only retained prototype-shuttle input was the accepted
scaled exterior skin with the manually cut forward belly ramp doorway.

## Required Outputs

- Exterior-only ship model package.
- Ship-local interior layout contract.
- Voxel interior report and projections.
- Compact voxel serialization for script and LLM review.
- Semantic region projection.
- Regularized floorplan report and projection.
- Feature-tagged voxel serialization after traversal surfaces are generated.
- Generated traversal surfaces.
- Generated enclosure bands.
- Godot review scene and evidence video/contact sheet.

## Process

### 0. Author The Interior Layout Contract

Before generating walls or accepting traversal, create a ship-local layout
contract that records the human design decisions and player-scale constraints
that should not remain hidden in scripts.

Current `shuttle_p3` contract:

- `assets/source/blender/ships/shuttle_p3/shuttle_p3_interior_layout_contract.json`

The contract owns:

- player capsule radius, height, and origin clearance;
- enclosure generation slice sizes, wall thickness, smoothing limits, and stair
  transition rules;
- named enclosure zones with z spans, route widths, ceiling bounds, and voxel
  sampling settings;
- authored stair path points, stair width, and wall clearance;
- real-player traversal validation checkpoints and tolerances.

Acceptance:

- generator and validation tools read this contract instead of carrying
  ship-specific constants in code;
- future ships can create their own contract without changing the generic
  algorithm shape;
- any later hand-authored layout decision is added to the contract before it is
  used by tooling.

### 1. Lock The Exterior Skin

Start from an accepted hull. Do not build interior layout against a changing
exterior.

For `shuttle_p3`, this was:

- `assets/models/ship/shuttle_p3/shuttle_p3_exterior.glb`
- copied from the accepted prototype exterior skin;
- manually edited in Blender to remove the hull faces inside the belly ramp
  doorway.

Acceptance:

- silhouette and scale are accepted;
- ramp/opening cut is physically present in the mesh;
- no previous interior, collision, stairs, ramp, furniture, or lighting are
  carried forward.

### 2. Voxelize Interior Free Space

Voxelize the hull in ship-local coordinates. The current `shuttle_p3` tool is:

- `tools/ship_pipeline/build_shuttle_p3_from_exterior_glb.py`

Current key settings:

- voxel size: `0.25m`;
- local refine voxel size: `0.125m`;
- player capsule radius: `0.42m`;
- standing height: `1.82m`;
- clearance margin: `0.18m`.

The generated voxel artifacts are:

- `reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_voxel_report.md`
- `reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_voxel_report.json`
- `reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_voxels_full_compact.json`
- `reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_voxel_free_space_projection_current.png`

Acceptance:

- interior free-space projection fits inside the hull;
- free space recognizes the cargo belly, cockpit/neck, and ramp opening;
- obvious exterior regions, wings, tail, and nose tips are not treated as
  playable interior.

### 3. Serialize Voxel Data For LLM Spatial Review

Produce compact data small enough for an LLM to reason about directly.

For `shuttle_p3`, the useful formats were:

- full compact voxel list:
  `shuttle_p3_voxels_full_compact.json`
- LLM slice summary:
  `shuttle_p3_voxel_serialized_for_llm.json`
- later, feature-tagged voxels:
  `shuttle_p3_voxels_with_traversal_features.json`

The full compact voxel format is:

```text
[x, y, z, can_stand, head_clearance]
```

The slice summary lets the LLM classify broad spatial zones without loading all
voxels at once. The full compact list is useful when asking targeted questions
about a specific feature, such as whether stairs or landing surfaces use the
available side-wall volume.

Acceptance:

- LLM-facing files are concise enough to inspect in context;
- each report names voxel size, count, standing-capable count, and coordinate
  convention;
- the LLM review is treated as planning evidence, not as final geometry.

### 4. Classify Semantic Interior Regions

Use voxel slice trends and projections to classify broad regions:

- cargo belly;
- cockpit/canopy volume;
- neck or access gap;
- transition core;
- ramp threshold/opening;
- non-playable nose/tail/exterior volumes.

For `shuttle_p3`, this evidence lives in:

- `reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_llm_voxel_semantic_review.md`
- `reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_semantic_regions_projection_current.png`

Important p3 lesson:

- rectangular room boxes were too crude;
- prismatic or slice-derived regions better matched the hull;
- semantic spaces must fill available interior volume in all dimensions, not
  only look correct from one projection.

Acceptance:

- cargo and cockpit regions connect through a plausible transition space;
- cockpit uses the forward/upper neck volume rather than shrinking into a
  placeholder box;
- transition space leaves room for stairs without blocking the ramp entry.

### 5. Regularize The Floorplan Before Playable Surfaces

Do not convert raw voxel components directly into floors. Raw interior voxels
are evidence, not final playable geometry. They are often fragmented by mesh
holes, sparse cross-sections, non-watertight hulls, side pods, engine nacelles,
and sampling gaps. Turning those fragments directly into floor boxes produces
disconnected patches, exterior clipping, and inaccessible stairs.

The next required stage is a deterministic floorplan regularizer. It should:

- build one bottom walkable node per `(x,z)` column, as `shuttle_p3` did;
- reject or quarantine side/exterior components before floor generation;
- merge sparse but aligned interior evidence into coherent longitudinal zones;
- preserve the difference between machine evidence and design constraints;
- generate floor regions from regularized zones, not from every raw component;
- add same-level bridge floors where small gaps would otherwise make regions
  feel discontinuous;
- add ramps or stair paths only where level changes or graph gaps require them;
- serialize both the regularized floorplan and the evidence that produced it.

For larger ships, this stage also owns explicit deck-level constraints. For
example, `cargo_crane` needed a two-level cockpit: an upper level at the central
body floor height, a lower cockpit deck, and paired side stair paths with clear
openings through the upper floor. That requirement should live in the layout
contract or floorplan config before traversal surfaces are accepted.

The floorplan config should record:

- named regularized regions and their intended roles;
- target level heights or sampled floor-height modes;
- maximum widths and z spans derived from voxel evidence;
- bridge-gap thresholds;
- stair/ramp centerlines, widths, and landing/opening rules;
- connector width policy, including whether a connector should use full
  available interior width instead of a narrow default;
- trim rules for areas that clip outside the exterior skin;
- any human-approved design constraints, such as multi-level cockpits,
  mezzanines, side entrances, or cargo atriums.

Acceptance:

- floor regions are coherent and readable as ship spaces, not raw voxel shards;
- all same-level regions either touch or have a generated bridge floor;
- level changes have explicit stairs or ramps with landing surfaces at both
  ends;
- upper floors do not cover stair/ramp openings;
- no floor region visibly clips outside the exterior hull in review;
- side-engine/exterior components are excluded unless explicitly approved as
  interior;
- the projection includes a color key for evidence nodes, regularized floors,
  bridge floors, ramps/stairs, and graph routes;
- if a human adjusts the result, the adjustment is captured as a config rule so
  the next generation is repeatable.

### 6. Generate Traversal Surfaces From Regularized Floorplan Space

Generate surfaces from the accepted semantic regions and regularized floorplan,
not from visual guesswork or raw voxel fragments.

For `shuttle_p3`, the successful traversal surface set includes:

- forward belly entry ramp;
- cargo floor;
- side stairs wrapping around the ramp opening;
- upper landing at the top of the stairs;
- straight cockpit hallway/cockpit floor extension;
- railing at the aft edge of the upper landing;
- curved inner stair railings.

The important adjustment loop was:

1. Generate surfaces from semantic zones.
2. Serialize voxels with feature tags.
3. Ask whether the features use the available voxel space correctly.
4. Move stairs outward, widen them, and raise the landing based on direct voxel
   evidence.
5. Regenerate and review projection/evidence.

Feature review artifact:

- `reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_feature_voxel_review.md`

Connector width policy:

- derive ramp, stair, bridge, and landing widths from connected room widths and
  the usable interior envelope;
- avoid narrow hardcoded connectors unless the contract explicitly marks them
  as crawlways, ladders, maintenance passages, or intentionally constrained
  spaces;
- where two large rooms connect across a level change, prefer a broad connector
  such as `min(connected_widths) - wall_clearance` and clamp it to voxel-proven
  interior width;
- keep lower landing, upper landing, sloped ramp, and guard-wall openings the
  same width unless the contract declares a taper;
- serialize the derived width and the reason it was chosen into the traversal
  report.

Acceptance:

- ramp does not block cargo flow;
- stairs start near the ramp/cargo threshold but hug the side walls;
- stairs rise steeply enough to remain inside the hull;
- stairs and landing connect without gaps;
- ramp and stair landings are flush with adjacent floor edges, not separated by
  a drop, curb, or collision seam;
- ramp, stair, and bridge widths are justified by the connected spaces and are
  not left at generic defaults;
- stair/ramp openings are not covered by upper floor slabs;
- cockpit floor extends to the landing without unnecessary tapering;
- railing protects the fall edge but does not block stair access.

### 6a. Validate Walkable Perimeters Before Enclosure

Before generating walls, classify the perimeter of every walkable surface:

- floor boxes;
- same-level bridge floors;
- ramp landings;
- sloped ramps;
- stair paths;
- mezzanine and upper-deck slabs;
- hatch and entry threshold surfaces.

For each perimeter segment, classify it as one of:

- connected to another walkable surface with sufficient overlap;
- intentional entry or hatch opening;
- intentional vertical connector opening;
- exterior access ramp edge;
- exposed edge that requires a wall, guard, railing, or end cap.

This pass should produce an exposed-edge report and projection before the
Godot review scene. Exposed edges should be drawn in a warning color and named
by surface and side, for example
`aft_center_service_to_central_body_lower_ramp:port_edge`.

Acceptance:

- every walkable perimeter segment has a classification;
- unclassified exposed edges fail validation;
- connected edges overlap or touch within tolerance in X/Z and have compatible
  floor heights or declared ramp/stair transitions;
- broad ramps and landings have side guards whose inner faces are flush with
  the ramp edge for the full landing-to-landing span;
- fall edges are guarded even if the happy-path route checkpoint stays near the
  centerline;
- the exposed-edge report is reviewed before player walkthrough capture.

### 7. Generate Enclosure Bands From Voxel Bounds

After traversal surfaces are accepted, generate walls and ceilings from voxel
slice bounds around the route.

Current tool:

- `tools/ship_pipeline/generate_shuttle_p3_enclosure_bands.py`

Current source layout contract:

- `assets/source/blender/ships/shuttle_p3/shuttle_p3_interior_layout_contract.json`

Current generated contract:

- `assets/models/ship/shuttle_p3/shuttle_p3_enclosure_bands.json`

Current report:

- `reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_enclosure_bands_report.md`

The tool creates named wall and ceiling bands for:

- cargo forward;
- cargo main;
- stair transition;
- cockpit hall;
- cockpit rear;
- cockpit forward.

For larger multi-room ships, enclosure generation must be driven by the
floorplan topology as well as voxel bounds. Every semantic region boundary
should be classified as:

- connected to an adjacent region;
- closed wall/end cap;
- hatch or doorway;
- ramp/stair transition;
- ceiling/floor opening;
- intentionally open atrium/mezzanine edge with guard rail.

Anything not classified should fail as an unknown boundary. Do not rely on
route reachability to prove enclosure completeness; a player can often complete
the centerline route while still being able to fall through side or end gaps.

Acceptance:

- enclosure follows the interior envelope near the route;
- ceilings preserve headroom over stairs and landing;
- walls do not extend far outside the exterior hull;
- end caps exist at every region end that is not a connected region, hatch,
  stair, ramp, or doorway;
- caps and guards are flush with the playable floor/ramp/landing edge they
  protect, with a small intentional overlap rather than a gap;
- side guards cover the full sloped-ramp span plus both landings;
- hatch openings are only as large as the authored hatch/doorway cut, not full
  height slices through the wall;
- nose, cargo, stair, and cockpit regions are closed enough to read as a real
  interior before art detail begins.

### 7a. Validate Enclosure Quality Before Art

Run an enclosure quality audit before treating generated walls and ceilings as
accepted.

Current p3 tool:

- `tools/ship_pipeline/validate_shuttle_p3_enclosure_quality.py`
- `scripts/validate-shuttle-p3-enclosure-quality.sh`

Current CargoCrane exposed-edge audit:

- `tools/ship_pipeline/audit_cargo_crane_enclosure_edges.py`
- `scripts/audit-cargo-crane-enclosure-edges.sh`

Current CargoCrane exposed-edge report:

- `reports/ship_pipeline/cargo_crane_enclosure_edge_audit/cargo_crane_enclosure_edge_audit.md`
- `reports/ship_pipeline/cargo_crane_enclosure_edge_audit/cargo_crane_enclosure_edge_audit_current.svg`

The audit checks:

- seam continuity between adjacent wall bands;
- every exposed walkable edge has a blocking wall, guard, railing, hatch, or
  declared connector within tolerance;
- wall/end-cap overlap with the floor/ramp edge it protects;
- ramp and stair side-guard coverage over the full connector span, including
  lower and upper landings;
- no full-height doorway cuts where the contract declares a smaller hatch;
- player-route clearance against stair, cargo, cockpit feature voxels, and
  authored stair corridor geometry from the layout contract;
- whether rectangular bands fit the voxel envelope or should become
  polygon/mesh strips;
- excessive protrusion outside the usable interior envelope.

For larger ships, add a deterministic exposed-edge audit before any manual
playtest review. This audit treats the accepted traversal surface file as the
source of truth and runs the same checks a player would exploit:

1. Convert every `floor_box` into four top-down edge obligations.
2. Convert every ramp or stair path into left/right side-edge guard
   obligations, plus endpoint obligations unless the endpoint touches another
   traversable surface.
3. Sample each obligation at capsule-radius or smaller intervals.
4. For each sample, classify it as:
   - `connected_traversal` when another floor/ramp/stair surface covers the
     outward probe point;
   - `approved_opening` when it lies inside an authored hatch, doorway, or
     declared atrium/mezzanine opening;
   - `guarded` when a wall, guard, railing, or end cap overlaps the sample
     and vertically covers the player capsule;
   - `failure` when none of the above are true.
5. Independently audit every wall/guard band for anchoring. A wall that is not
   near any exposed traversal edge is suspicious because it may be extending
   into exterior space instead of closing a floor edge.
6. Emit both machine-readable failures and a sparse projection that only shows
   failed sample points and suspicious walls. Full debug overlays should not be
   used for this step because they hide the specific failure.

The generator must then consume the exposed-edge audit output, not screenshots.
Missing closure should become a new generated wall/guard segment. Offset closure
should move the wall inner face flush to the source edge with a small intentional
overlap. Oversized hatch cuts should shrink to the authored opening bounds.
Manual Godot-scene edits are not accepted fixes because they cannot be repeated
for the next ship.

### 7b. Validate Collision-Shell Water Leaks

After exposed-edge validation passes, run a voxel flood-fill against the
generated collision shell. This is the deterministic version of asking: if the
playable interior were filled with water, where would it escape?

The leak audit source of truth is collision, not the visual exterior skin:

- traversal floors, ramps, stairs, generated walls, guards, caps, and ceilings
  are solid blockers;
- the fill is seeded from accepted playable interior route/floor points;
- the fill may leave through explicitly approved exterior hatches only;
- ramp-to-room and stairwell transitions are approved internal transitions, not
  exterior leaks;
- every other exit from the intended interior domain is a failure.

Current CargoCrane water-fill audit:

- `tools/ship_pipeline/audit_cargo_crane_enclosure_leaks.py`
- `scripts/audit-cargo-crane-enclosure-leaks.sh`

Current CargoCrane leak report:

- `reports/ship_pipeline/cargo_crane_enclosure_leak_audit/cargo_crane_enclosure_leak_audit.md`
- `reports/ship_pipeline/cargo_crane_enclosure_leak_audit/cargo_crane_enclosure_leak_audit_current.svg`

Repair rules:

- Add closure only when the leak cluster is a true unapproved escape through
  the collision shell.
- Do not add physical walls for audit-domain seams at approved internal
  transitions. Classify the transition explicitly in the audit instead.
- Do not add walls around approved entry ramps unless the hatch aperture itself
  is oversized or unclassified. Entry ramps are expected exits.
- Any generated closure must also pass the protrusion audit; a wall that sticks
  into traversable free space without anchoring to a protected edge is a failed
  repair.

Acceptance:

- zero unapproved leak clusters;
- approved exterior escape cells are limited to authored hatch apertures;
- approved internal transition cells are limited to declared ramp/stair
  connector seams;
- exposed-edge audit still reports zero unguarded samples and zero suspicious
  or intrusive walls after leak repairs.

### 7c. Validate Runtime Player Escape Edges

Static audits can still miss exact collision seams because they reason from
authored boxes rather than the loaded Godot physics world. The final enclosure
gate must run a real runtime negative edge probe in the same scene used for
player traversal.

The runtime probe should:

- load the generated traversal and enclosure collision exactly as the playtest
  scene does;
- sample floor, ramp, and stair boundary points;
- cast from a small inset inside the playable floor outward across the edge;
- pass only when the outward path hits solid collision, reaches connected
  walkable support, or lies inside an approved hatch opening;
- fail before the happy-path route if any sampled edge lets the player move
  into unsupported space.

Current CargoCrane implementation:

- `scripts/debug/CargoCranePlayerTraversalValidationRunner.cs`
- `scripts/validate-cargo-crane-player-traversal.sh`

This runtime probe is required in addition to the water-fill and exposed-edge
audits. The water-fill audit validates global collision-shell leakage; the
runtime probe validates player-scale escape at exact Godot collision seams.

Current p3 report:

- `reports/ship_pipeline/shuttle_p3_voxel_fit/shuttle_p3_enclosure_quality_report.md`

Acceptance:

- no seam failures;
- no unguarded exposed-edge failures;
- no floor-to-cap or ramp-to-guard flushness failures;
- no route-clearance failures;
- no wall band marked as requiring polygon/mesh replacement;
- failures must be solved in the generator, not by hand-editing the Godot
  loader.

### 7c. Validate Real Player Traversal

Static geometry checks are not enough. Run an actual Godot `PlayerController`
route validation before accepting walkthrough evidence.

Current p3 tools:

- `scripts/validate-shuttle-p3-player-traversal.sh`
- `scenes/debug/ShuttleP3PlayerTraversalValidation.tscn`
- `scripts/debug/ShuttleP3PlayerTraversalValidationRunner.cs`

Current report:

- `reports/ship_pipeline/shuttle_p3_player_traversal_validation_report.json`

Acceptance:

- the real player capsule reaches every contract checkpoint from ramp entry to
  pilot approach;
- the validator fails on stalls, timeouts, or leaving the expected vertical
  route envelope;
- negative probes attempt to walk off every exposed or guarded edge, including
  ramp sides, landings, mezzanines, lower decks, and region end caps;
- negative probes fail if the player can leave the intended interior envelope,
  fall below the expected deck, or pass through an undeclared wall gap;
- route checkpoints include edge-biased samples near ramps and wide connectors,
  not only centerline samples;
- visual walkthrough capture should run this validation first so a cinematic
  path cannot hide collision or traversal failures.

### 8. Produce Evidence Before Art Detail

Each iteration should produce review evidence before moving to materials,
furnishings, or lighting.

Useful p3 evidence:

- exterior projection;
- free-space projection;
- semantic region projection;
- traversal projection;
- feature voxel review report;
- enclosure band report;
- Godot review scene;
- player-height walkthrough after traversal is stable.

Current p3 walkthrough evidence:

- `reports/shuttle_p3_player_walkthrough/shuttle_p3_player_walkthrough_current.mp4`
- `reports/shuttle_p3_player_walkthrough/shuttle_p3_player_walkthrough_contact_sheet_current.png`

Acceptance:

- evidence shows the route from entry ramp to cargo, stairs, landing, cockpit
  hallway, and cockpit;
- if evidence fails, inspect voxel/feature serialization before hand-editing;
- screenshots are secondary to voxel reports and deterministic generation.

## Repeatable LLM Review Prompts

Use targeted spatial questions:

- "Given these voxel slice summaries, classify cargo, cockpit, transition,
  ramp threshold, and non-playable regions."
- "Given the objective voxel components, which components are likely exterior
  side pods or engine shells rather than interior?"
- "Given these regularized floor regions, are any same-level floors
  disconnected or missing bridge pieces?"
- "Given these connected regions, should each ramp/bridge use a narrow
  connector or the full available interior width?"
- "Given the feature-tagged voxels, do the stairs use the available side-wall
  volume, or are they too centered?"
- "Do the landing and cockpit floor connect, and do they use the available
  cockpit/neck width?"
- "Do upper floors leave openings for stairs, ramps, hatches, and vertical
  connectors?"
- "Which walkable perimeter edges are unconnected, and does each one have a
  wall, guard, railing, hatch, or declared opening?"
- "Are wall caps and guard walls flush with the floor/ramp/landing edge they
  protect, including both ends of ramps?"
- "Where should a railing prevent falling without blocking stair access?"
- "Which wall/ceiling bands are too low, too wide, or outside the hull?"

Avoid vague visual prompts:

- "Make it look better."
- "Guess where the stairs should go."
- "Fit the cockpit from this screenshot."

## Failure Modes To Guard Against

The `cargo_crane` floorplan iteration exposed several repeatability failures
that the pipeline should detect earlier:

- Manual hull envelopes were used before the objective interior had been
  reviewed. They hid ambiguity and made the rear engine area look traversable
  when much of it was exterior.
- Objective voxel components were treated as floor surfaces too early. The
  result was many disconnected floor patches instead of a coherent ship
  floorplan.
- A sparse voxel graph made the central body look fragmented even though the
  regularized design intent was one continuous main interior body.
- Cockpit floors clipped because upper/lower level requirements were added as
  geometry edits rather than recorded first as floorplan constraints.
- Stair openings were not validated, so upper floor slabs covered the stair
  paths that were supposed to connect the levels.
- Enclosure generation initially validated the centerline route but did not
  validate walkable perimeter edges, so players could still fall from ramps,
  landings, lower cockpit edges, and uncapped region ends.
- End caps and guard walls were generated at semantic-region bounds rather than
  at the actual floor/ramp/landing edges. This left small but playable gaps.
- The engine-to-main-body ramp used a narrow default width even though both
  connected rooms supported a broad full-width connector.
- Main-body hatch openings were cut as full-height wall slices instead of being
  constrained to the authored hatch placeholder dimensions.
- Small projection views were hard to interpret without explicit color keys and
  named surface classes.

Add or keep validators for:

- exterior clipping for every floor, bridge, ramp, stair, wall, and ceiling;
- same-level floor contiguity and bridge coverage;
- stair/ramp endpoint contact with floor surfaces;
- derived connector width compared with connected room width and available
  interior envelope;
- exposed walkable perimeter edge coverage;
- wall/end-cap flushness against the protected floor edge;
- ramp side-guard flushness and full landing-to-landing coverage;
- negative player probes at guarded/exposed edges;
- stair/ramp clearance through upper floors;
- lower/upper deck overlap without a declared vertical connector;
- hatch cut dimensions compared with authored hatch dimensions;
- side-engine or exterior components accidentally promoted to interior;
- review projection color keys and named surface categories.

## What To Generalize For The Next Ship

Keep the algorithm. Replace the ship-specific constants.

Generalize:

- source exterior mesh path;
- voxel config;
- semantic region names and hints;
- regularized floorplan region specs and level constraints;
- route endpoints;
- traversal surface generator;
- feature-tag serializer;
- enclosure-band zones;
- evidence output paths.

Do not generalize yet:

- art style;
- furnishings;
- runtime player movement helpers;
- main-game integration;
- ship flight behavior.

The next ship should start by producing voxel reports and serialized LLM review
data before any interior art or collision is authored.
