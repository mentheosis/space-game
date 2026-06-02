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
- Voxel interior report and projections.
- Compact voxel serialization for script and LLM review.
- Semantic region projection.
- Feature-tagged voxel serialization after traversal surfaces are generated.
- Generated traversal surfaces.
- Generated enclosure bands.
- Godot review scene and evidence video/contact sheet.

## Process

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

### 5. Generate Traversal Surfaces From Voxel Space

Generate surfaces from the accepted semantic regions, not from visual guesswork.

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

Acceptance:

- ramp does not block cargo flow;
- stairs start near the ramp/cargo threshold but hug the side walls;
- stairs rise steeply enough to remain inside the hull;
- stairs and landing connect without gaps;
- cockpit floor extends to the landing without unnecessary tapering;
- railing protects the fall edge but does not block stair access.

### 6. Generate Enclosure Bands From Voxel Bounds

After traversal surfaces are accepted, generate walls and ceilings from voxel
slice bounds around the route.

Current tool:

- `tools/ship_pipeline/generate_shuttle_p3_enclosure_bands.py`

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

Acceptance:

- enclosure follows the interior envelope near the route;
- ceilings preserve headroom over stairs and landing;
- walls do not extend far outside the exterior hull;
- nose, cargo, stair, and cockpit regions are closed enough to read as a real
  interior before art detail begins.

### 7. Produce Evidence Before Art Detail

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
- "Given the feature-tagged voxels, do the stairs use the available side-wall
  volume, or are they too centered?"
- "Do the landing and cockpit floor connect, and do they use the available
  cockpit/neck width?"
- "Where should a railing prevent falling without blocking stair access?"
- "Which wall/ceiling bands are too low, too wide, or outside the hull?"

Avoid vague visual prompts:

- "Make it look better."
- "Guess where the stairs should go."
- "Fit the cockpit from this screenshot."

## What To Generalize For The Next Ship

Keep the algorithm. Replace the ship-specific constants.

Generalize:

- source exterior mesh path;
- voxel config;
- semantic region names and hints;
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
