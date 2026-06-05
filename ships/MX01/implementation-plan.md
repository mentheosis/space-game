# 0.4 MX01 Skin-To-Collision Experiment

## Purpose

Create an isolated, from-scratch experiment that turns the MX01 reference ship
skin at `ships/MX01/input/CargoCrane.obj` into a production-oriented collision
package for a new ship named **MX01**.

This experiment must not reuse prior CargoCrane generated assets, prior
CargoCrane tools, existing CargoCrane contracts, or old interior planning
outputs. Existing repo work may be read only for general project conventions.
All implementation files, outputs, validation reports, Godot scenes, generated
assets, manifests, and review artifacts for this run must live under
`ships/MX01`.

## Goal

Build two related but separate collision products from the same exterior skin:

- **Interior traversal collision:** a fully walkable multi-level interior that
  uses as much of the ship vertical volume as practical. The player must be able
  to traverse from entry to every intended deck without clipping through the
  exterior skin.
- **Dynamic exterior physics collision:** a simplified compound collision hull
  suitable for ship-to-ship, ship-to-planet, landing, scraping, and broad world
  contact. This collision must be stable for a moving ship and must not be one
  giant concave mesh.

The output is a repeatable process, not a one-off manual model.

## Non-Goals

- Do not polish final interior art.
- Do not reuse the existing CargoCrane model package under
  `assets/models/ship/cargo_crane`.
- Do not reuse existing CargoCrane voxel, enclosure, traversal, or floorplan
  scripts.
- Do not rely on Godot runtime calls to create collision from a visual mesh.
- Do not make one collision shape serve every purpose.

## MX01 Workspace

Use `ships/MX01` as the only workspace for this ship. Keep all ship-specific
work colocated there until there is a proven reason to extract reusable
components.

Required directory layout:

- `ships/MX01/input/`
- `ships/MX01/implementation-plan.md`
- `ships/MX01/config/`
- `ships/MX01/tools/`
- `ships/MX01/source/`
- `ships/MX01/generated/`
- `ships/MX01/generated/models/`
- `ships/MX01/generated/scenes/`
- `ships/MX01/generated/collision/`
- `ships/MX01/reports/`
- `ships/MX01/reports/images/`
- `ships/MX01/reports/manifests/`

No generated MX01 file should overwrite or depend on prior CargoCrane outputs.
If a later component is useful for other ships, extract it only after the MX01
experiment proves the interface and behavior.

## Deterministic Config Contract

Create `ships/MX01/config/mx01_collision_generation.json` before generating
collision outputs. Every tool must read its tunable parameters from this file or
from a stage-specific config referenced by this file. No geometry-affecting
threshold should be hard-coded without also being reported.

The contract must include at least:

- `voxel_size`;
- `refined_voxel_size`;
- `max_surface_error`;
- `max_normal_error_degrees`;
- `min_component_volume`;
- `weld_epsilon`;
- `vertex_quantization_epsilon`;
- `surface_offset_modes`;
- `max_convex_hull_vertices`;
- `max_dynamic_hull_error`;
- `player_capsule_radius`;
- `player_capsule_height`;
- `player_clearance_margin`;
- `deterministic_sort_keys`;
- tool version or script hashes.

Each generated manifest must copy the effective config values and source hashes
used for that run. Re-running the same input and same config should produce
byte-stable mesh, report, and manifest outputs, except for explicitly marked
wall-clock timestamps if those are ever added.

## Source Of Truth

The only initial geometry source is:

`ships/MX01/input/CargoCrane.obj`

The matching source material file is:

`ships/MX01/input/CargoCrane.mtl`

The first script must parse and normalize the OBJ directly. It should select the
highest-detail object section as the default skin source, record the selected
object name, triangulate deterministically, weld vertices with an explicit
epsilon, remove degenerate triangles, and write a source audit report.

Required source audit data:

- source path;
- source file hash;
- selected OBJ object names;
- source bounds;
- normalized bounds;
- vertex count;
- triangle count;
- non-manifold or open-edge count if available;
- material names;
- chosen coordinate transform;
- all numeric tolerances.

## Collision Architecture

### 1. Interior Traversal Collision

Interior traversal collision is player collision. It should be optimized for
walkability, not rigid-body physics.

It should include:

- floors for multiple decks;
- ramps, stairs, ladders, or lifts connecting decks;
- walls and ceiling blockers that prevent skin clipping;
- entry hatch and ramp collision;
- guardrails around vertical drops;
- semantic room and corridor boundaries;
- debug materials and named regions.

The interior generator should derive usable volume from the exterior skin with a
signed distance field or equivalent inside/outside classifier. It may then place
authored procedural deck surfaces inside that volume.

Target deck strategy:

- lower deck near the ship belly for cargo, engineering, and entry;
- mid deck through the central body for living, service, and traversal spine;
- upper deck where the hull has headroom for cockpit, bridge, command gallery,
  or observation spaces;
- local mezzanines where vertical clearance exists but full deck continuity
  does not.

Decks must be validated against player capsule height and radius. A deck is not
accepted unless it has usable head clearance and connects to the traversal graph.

Interior wall and ceiling blockers should be generated from the exterior skin
through the signed distance / occupancy field. The plan should preserve two
surface reconstruction options:

- **Marching cubes:** the simpler first implementation. It extracts a watertight
  triangle surface from the signed distance field at a chosen offset from the
  visual skin. Use this when the priority is getting deterministic evidence and
  collision into Godot quickly.
- **Dual contouring:** the higher-quality follow-up. It preserves harder panel
  edges and sharper ship silhouettes better than marching cubes when the SDF
  includes reliable gradients or Hermite edge data. Use this if marching cubes
  rounds off important hull boundaries or creates too much stair-stepping.

The interior collision generator may use reconstructed shell patches as
blockers, but it should not blindly use the full exterior mesh as interior
collision. Traversal surfaces still need authored/procedural floors, ramps,
stairs, rails, and connectors that are validated against the player capsule.

### 2. Dynamic Exterior Physics Collision

Exterior physics collision is ship-world collision. It should be optimized for
stable dynamic motion, not exact skin fidelity.

It should include:

- compound convex hulls or simple primitives;
- separate broad hull regions for nose, main body, aft body, wings or booms,
  engine pods, belly support, and landing contact areas;
- no single full-ship concave collision shape for dynamic physics;
- no exterior physics shape that blocks required interior traversal;
- deterministic region names and transforms.

The exterior physics surface should be generated from the skin by partitioning
the normalized mesh into spatial or semantic regions, fitting convex hulls per
region, and simplifying until the shape is stable. Fit quality should be
measured against the skin, but stability is more important than perfect detail.

A direct triangle copy of the source skin, or a marching-cubes/dual-contouring
reconstruction of the full skin, is acceptable only as static review/debug
collision. It is not the dynamic ship-world physics solution. The dynamic
solution must remain compound convex/simple so it can move, collide, and rest
stably in Godot.

## Deterministic Geometry Process

### Stage 1: Normalize Skin

Create `ships/MX01/tools/normalize_mx01_skin.py`.

Responsibilities:

- parse OBJ without relying on Blender import state;
- choose source object sections explicitly;
- triangulate polygons in stable vertex order;
- apply a documented transform to project coordinates into the game convention;
- center or anchor the ship consistently;
- write a normalized mesh artifact;
- write a JSON audit report.

Acceptance:

- repeated runs produce identical hashes;
- source bounds and normalized bounds are reported;
- the normalized mesh can be inspected independently of later collision steps.

### Stage 2: Build Signed Distance / Occupancy Field

Create `ships/MX01/tools/build_mx01_sdf.py`.

Responsibilities:

- build a fixed grid over normalized skin bounds plus margin;
- classify each cell as inside, outside, near-surface, or uncertain;
- compute signed distance samples where practical;
- use fixed voxel size, fixed origin, fixed axis order, and fixed tie-breaking;
- record uncertain cells caused by holes, thin surfaces, or non-manifold input.

Initial recommended settings:

- coarse voxel size: `0.50m`;
- refined voxel size near skin and traversal candidates: `0.25m`;
- player clearance margin: `0.10m`;
- shell safety margin: `0.20m`;
- minimum accepted head clearance: player capsule height plus `0.15m`.

Acceptance:

- report includes occupied/free/uncertain voxel counts;
- report includes slice images from side, top, and front;
- every later generated surface can trace back to this field version.

### Stage 3: Reconstruct Skin-Derived Boundary Surfaces

Create `ships/MX01/tools/reconstruct_mx01_boundary_surfaces.py`.

Responsibilities:

- extract skin-derived boundary surfaces from the SDF / occupancy field;
- support marching cubes as the first deterministic implementation;
- reserve dual contouring as the edge-preserving implementation path;
- allow explicit offset modes: `visual_skin`, `inset_for_interior_clearance`,
  and `outset_for_debug_review`;
- quantize vertices with a fixed epsilon;
- weld and sort vertices/faces deterministically;
- tag output surfaces by role: `static_review_shell`, `interior_blocker_shell`,
  or `debug_only`;
- write a fit report comparing reconstructed surfaces to the normalized skin.

Marching cubes requirements:

- fixed cube traversal order;
- fixed edge interpolation rule;
- fixed lookup table version checked into `ships/MX01/tools/`;
- deterministic handling for exact-zero SDF values;
- post-weld and component filtering with recorded thresholds.

Dual contouring requirements:

- use only after marching cubes evidence exists;
- derive Hermite samples from SDF gradients or triangle nearest-point normals;
- preserve sharp features where normal angle exceeds a configured threshold;
- clamp generated vertices to their source cells to avoid unstable spikes;
- report whether edge preservation improves fit enough to justify the added
  complexity.

Acceptance:

- repeated runs produce identical reconstructed mesh hashes;
- fit report includes max, mean, and percentile distance to source skin;
- report lists protrusion and inset distances separately;
- review images show side/top/front overlays against the source skin;
- interior blocker shell surfaces stay outside the accepted traversal volume.

### Stage 4: Simplify And Stabilize Reconstructed Surfaces

Create `ships/MX01/tools/simplify_mx01_surfaces.py`.

Responsibilities:

- simplify reconstructed boundary surfaces with deterministic decimation or
  grid/voxel clustering;
- use locked config values from
  `ships/MX01/config/mx01_collision_generation.json`;
- enforce `max_surface_error`, `max_normal_error_degrees`,
  `min_component_volume`, and `weld_epsilon`;
- remove tiny disconnected components below `min_component_volume`;
- preserve tagged sharp features when dual contouring or normal thresholds mark
  them as important;
- sort components, vertices, faces, and materials by deterministic keys before
  writing output;
- write a simplification report comparing pre- and post-simplification meshes.

Accepted simplification methods:

- **Deterministic voxel clustering:** first-choice method for early runs because
  it is simple, stable, and naturally tied to the SDF grid.
- **Deterministic quadric/error decimation:** allowed after the clustering
  baseline exists, but only if tie-breaking, priority queues, and output
  ordering are locked and reproducible.
- **Convex hull simplification:** used separately for dynamic exterior physics
  hulls, with `max_convex_hull_vertices` and `max_dynamic_hull_error`.

Required simplification report fields:

- input mesh hash;
- output mesh hash;
- effective config hash;
- input vertex and triangle counts;
- output vertex and triangle counts;
- removed component count and volume;
- max and mean surface error;
- max and mean normal error;
- sharp-feature preservation count;
- byte-stability check result from an immediate second run.

Acceptance:

- repeated runs produce identical output hashes;
- simplification does not exceed `max_surface_error`;
- simplification does not exceed `max_normal_error_degrees` in protected
  regions;
- no accepted traversal blocker or dynamic hull loses its semantic role tag;
- the generated manifest records every simplification parameter.

### Stage 5: Extract Usable Interior Volume

Create `ships/MX01/tools/extract_mx01_interior_volume.py`.

Responsibilities:

- remove exterior appendages that cannot contain player-scale interiors;
- identify continuous internal cavities or feasible carved volume;
- generate candidate deck bands along ship length;
- estimate floor, wall, and ceiling envelopes per band;
- reject spaces below player clearance;
- preserve high-value vertical volume for multi-level traversal.

Acceptance:

- at least three vertical bands are evaluated: lower, mid, and upper;
- the report lists accepted and rejected volume regions;
- projection evidence shows player-scale clearance, not just raw empty space.

### Stage 6: Fit Multi-Level Traversal Layout

Create `ships/MX01/tools/fit_mx01_multilevel_traversal.py`.

Responsibilities:

- place connected floors inside accepted volume;
- create vertical connectors between decks;
- keep routes away from the exterior skin by clearance margin;
- reserve entry and hatch zones;
- output a traversal graph with named nodes and edges;
- flag unreachable spaces.

Required traversal graph checks:

- entry connects to lower deck;
- lower deck connects to mid deck;
- mid deck connects to upper deck where upper deck exists;
- every named room or traversal region is reachable from entry;
- no connector exceeds slope or step constraints unless marked as ladder/lift;
- player capsule sweep passes along each edge.

Acceptance:

- all intended decks are reachable;
- no accepted room is isolated;
- no floor, stair, ramp, or ladder intersects the exterior skin after clearance.

Human review requirements:

- Every vertical connector must have a stable generated ID, a from-deck, a
  to-deck, an X/Z footprint, a direction, and a placement role in the generated
  JSON report.
- Generate a top-down X/Z stair ID diagram before review. The diagram must show
  deck bounds, connector footprints, stair IDs, direction lines, and the exact
  X/Z coordinate convention used by the playable scene.
- Do not rely on unverified `port` / `starboard` labels. Use neutral `+X` and
  `-X` side labels unless the ship coordinate convention has been verified
  against the in-game view. If human review establishes a side convention, write
  it directly on the diagram.
- Human feedback about stairs should reference diagram labels such as `S3` and
  generated IDs, not only phrases like "main deck", "rear", "left", or "upper
  stair", because those phrases are ambiguous across deck transitions.
- When replacing a stair, remove or disable the superseded stair in the same
  deterministic generation pass. Do not leave a center stair in place when the
  requested result is a side-pair replacement.
- Supplemental stairs added during review must still be generated from the
  pipeline, not hand-authored in the Godot scene.

### Stage 7: Generate Interior Collision Meshes

Create `ships/MX01/tools/generate_mx01_interior_collision.py`.

Responsibilities:

- convert traversal layout into Godot-loadable collision meshes;
- generate walkable floors, ramps, stairs, blockers, walls, ceilings, rails,
  hatch blockers, and connector collision;
- split collision by semantic region and role;
- assign debug materials;
- export collision-only GLB or OBJ assets and a manifest.

Acceptance:

- every collision object has a deterministic name;
- player collision surfaces are separate from dynamic exterior physics;
- generated meshes pass static intersection checks against the exterior skin;
- generated meshes pass player capsule sweep checks.

Human review lessons from MX01 floor and stair iteration:

- Occupancy-clipped floor tiles should be preferred over broad rectangular
  slabs. Broad slabs can protrude outside the ship silhouette even when their
  source deck bounds look valid.
- Stair cutaways should normally be applied to the deck being entered above,
  not to the lower/source deck. Cutting the source deck can create unnecessary
  holes under stairs on the lowest level.
- Use the same stair footprint data for treads, landings, and cutaways. If
  these are derived separately, the visible stairwell opening can drift away
  from the passable collision path.
- The player controller handled the steeper MX01 stair profile better than the
  initial shallow high-tread-count profile. Record stair run/rise in the report
  and validate with playable inspection, not only with generic slope rules.
- Compact stair placement should prefer room edges only when that edge is still
  inside the accepted interior volume. "Move to the side" means near the usable
  floor edge, not necessarily all the way to the connector overlap bound.
- A stair aligned "above" another stair should use the lower stair's footprint
  as a reference, then offset only as much as needed to remain adjacent and
  inside the narrow floor section.
- After every human-reviewed stair change, regenerate the playable scene, the
  stair ID diagram, the interior collision report, and static validation before
  requesting another review.

### Stage 8: Generate Dynamic Exterior Compound Collision

Create `ships/MX01/tools/generate_mx01_dynamic_collision.py`.

Responsibilities:

- partition the normalized exterior skin into physics regions;
- fit convex hulls or simple primitives per region;
- simplify hulls according to vertex and error limits;
- prevent hulls from invading required interior traversal space;
- export a compound physics collision asset and report.

Initial target regions:

- nose;
- central fuselage;
- aft fuselage;
- belly landing/contact surfaces;
- port lateral structures;
- starboard lateral structures;
- engine or rear mass regions;
- large fins/booms if they materially affect contact.

Acceptance:

- no dynamic collision region is concave;
- compound hull count is high enough to match the silhouette but low enough for
  stable physics;
- exterior protrusion and omission errors are measured;
- a test scene can move the ship against static world geometry without using
  visual mesh collision.

### Stage 9: Godot Integration Scene

Create a standalone scene under:

`ships/MX01/generated/scenes/`

The scene should contain:

- visual reference mesh;
- generated interior player collision;
- generated exterior dynamic physics collision;
- debug overlay toggles;
- player spawn points at entry and on each deck;
- ship physics test setup;
- camera anchors for evidence capture.

Acceptance:

- the scene imports through Godot on the host;
- the player can walk the generated interior route;
- dynamic collision is attached to the moving ship body, not the visual mesh;
- debug overlays can show interior and exterior collision separately.

## Validation Requirements

### Static Validation

Create `ships/MX01/tools/validate_mx01_collision_static.py`.

Checks:

- source and generated artifact hashes match the manifest;
- generated files exist only under `ships/MX01`;
- interior collision is inside the exterior shell after clearance;
- dynamic collision is composed only of convex/simple shapes;
- no dynamic physics shape blocks a required interior route;
- traversal graph is fully connected;
- player capsule sweep passes along all required routes;
- each generated collision object has a semantic role and stable name.

### Godot / Host Validation

Use the host MCP bridge for Godot import and .NET/Godot validation when needed.

Recommended order:

1. Run local static validation.
2. Run host `dotnet build` if C# or Godot scene code changed.
3. Run host `import godot project` after adding scenes or imported assets.
4. Add a future host review profile for the 0.4 MX01 experiment once the
   scene and evidence capture are stable.

### Evidence Artifacts

Each full run should produce:

- normalized source audit report;
- SDF/voxel report;
- reconstructed boundary surface report;
- deterministic simplification report;
- interior volume report;
- traversal graph report;
- interior collision fit report;
- dynamic exterior collision fit report;
- side/top/front projection images;
- Godot contact sheet or screenshots;
- machine-readable manifest with all hashes and settings.

## Fit Metrics

Track these metrics per run:

- maximum interior collision protrusion outside skin;
- reconstructed shell max/mean distance to visual skin;
- reconstructed shell protrusion and inset distance percentiles;
- simplification input/output triangle counts;
- simplification max surface error;
- simplification max normal error;
- removed component count and total removed volume;
- mean and maximum distance from interior blockers to skin;
- floor area by deck;
- reachable floor area percentage;
- vertical space utilization percentage;
- traversal graph connected component count;
- minimum route clearance;
- dynamic collision hull count;
- dynamic collision total vertices;
- dynamic collision maximum skin omission distance;
- dynamic collision maximum protrusion distance;
- Godot import/build status.

## Acceptance For The Experiment

The experiment is considered successful when:

- a fresh 0.4 pipeline can rebuild all collision artifacts from the OBJ and
  config only;
- generated outputs are deterministic across repeated runs;
- generated manifests record the locked simplification contract;
- immediate second-run byte-stability checks pass for simplified outputs;
- the player can traverse all accepted interior decks in the review scene;
- at least three vertical levels or level bands are used where the hull permits;
- exterior dynamic collision is compound convex/simple, not concave trimesh;
- interior traversal collision and exterior dynamic collision are separate;
- validation reports show no untracked reuse of old CargoCrane outputs;
- all MX01-specific tools, scenes, assets, reports, and manifests are colocated
  under `ships/MX01`;
- Godot imports the generated assets through the host toolchain.

## Implementation Order

1. Create the `ships/MX01` workspace directories and config skeleton.
2. Implement OBJ normalization and source audit.
3. Implement SDF/occupancy field generation with projection evidence.
4. Implement marching-cubes boundary reconstruction and fit evidence.
5. Add dual-contouring support only if marching cubes loses important edges.
6. Implement deterministic simplification and byte-stability checks.
7. Implement interior volume extraction and deck-band discovery.
8. Implement traversal graph fitting and route validation.
9. Implement generated interior collision meshes.
10. Implement dynamic exterior compound collision fitting.
11. Implement static validation.
12. Add a standalone Godot review scene.
13. Add host import/build/review validation.

## Key Design Rule

The process may use the exterior skin to discover space, boundaries, and fit
targets, but generated collision must remain purpose-specific:

- player traversal collision is for walking inside the ship;
- dynamic exterior collision is for ship physics;
- debug visualization is for review only;
- no generated shape should silently serve multiple roles without being named
  and validated for each role.
