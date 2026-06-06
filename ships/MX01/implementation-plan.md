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

The enclosure generator may use reconstructed shell patches as blockers, but it
should not blindly use the full exterior mesh as interior collision. Traversal
surfaces still need authored/procedural floors, ramps, stairs, rails, and
connectors that are validated against the player capsule.

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

### Stage 7: Generate Interior Player Collision

Stage 7 is intentionally split into two deterministic generators. Floors and
traversal are authored/procedural player-route geometry. The enclosure is a
skin-fitted shell reconstruction problem. These must not be solved by one broad
rectangular room generator.

#### Stage 7A: Generate Floors And Traversal Collision

Create or maintain `ships/MX01/tools/generate_mx01_interior_collision.py`.

Responsibilities:

- convert the traversal graph into Godot-loadable player collision;
- generate walkable floors, ramps, stairs, landings, rails, hatch pads, and
  connector collision;
- keep floors and connectors inside accepted occupancy volume with player
  clearance;
- keep route objects independent from wall and ceiling enclosure objects;
- split collision by semantic region and role;
- assign debug materials;
- export collision-only GLB or OBJ assets and a manifest.

Acceptance:

- every floor, stair, landing, rail, and connector has a deterministic name;
- player traversal collision is separate from dynamic exterior physics;
- player traversal collision is separate from skin-fitted enclosure collision;
- no floor, stair, ramp, or landing intersects the exterior skin after
  clearance;
- generated traversal meshes pass player capsule sweep checks.

#### Stage 7B: Generate Skin-Fitted Interior Enclosure

Create `ships/MX01/tools/generate_mx01_interior_enclosure.py`.

Responsibilities:

- generate exterior-wall and ceiling blockers from a smooth signed-distance
  field or source-triangle projection field, not from rectangular deck bounds
  and not directly from raw binary occupancy boundaries;
- reconstruct an interior shell offset inward from the visual skin so it errs
  toward staying inside the ship skin;
- clip the shell to accepted interior deck bands and required traversal
  openings;
- preserve stairwell, hatch, and connector clearance volumes created by Stage
  7A;
- output semantic enclosure regions such as `player_enclosure_wall`,
  `player_enclosure_ceiling`, `player_enclosure_hatch_cut`, and
  `player_enclosure_opening`;
- export enclosure-only GLB or OBJ assets, JSON contracts, fit metrics, and a
  manifest.

Algorithm path:

- **Playable collider replacement target: exact floor-boundary containment.**
  The player-facing wall collider should be generated from the accepted Stage
  7A floor footprint, not from local voxel edge boxes, row-filled silhouettes,
  or triangle shell collision. The floor is the contract for where the player
  can stand; the ship skin is the constraint for where the enclosure is allowed
  to sit. For each accepted deck:
  - derive a deterministic 2D floor-support cell set directly from Stage 7A
    `player_walkable_floor` primitives, `player_connector_landing` pads whose
    top surface matches that deck height, and the 2D footprint of
    `player_connector_stair_tread` support surfaces that bridge into or out of
    the deck;
  - classify exterior-reachable empty space by flood-filling around the exact
    floor cell set in a padded grid;
  - extract every floor edge adjacent to exterior-reachable empty space;
  - discard interior cutaway and stair/dropdown hole edges unless they are also
    exterior-reachable. Stair tread footprints participate in the containment
    footprint so perimeter walls cannot cross a stair route, but the generator
    must not add separate connector guard-wall primitives;
  - reclassify exterior-reachable upper-deck edges as
    `interior_balcony_edge` when the adjacent empty cell is backed by a lower
    traversable/interior footprint and that adjacent cell is still inside the
    hull at the current deck's wall height. A lower floor below is not enough
    by itself to suppress a wall; if the adjacent cell is outside the hull at
    the current height, the edge remains a `ship_edge_boundary`;
  - keep `ship_edge_boundary` precedence over stair clearance. If a stair
    footprint reaches the hull boundary, the enclosure wall remains at the hull
    edge; the stair must fit inside that wall instead of deleting or shifting
    the wall;
  - when a required hull wall intersects stair traversal clearance, split only
    the affected wall run, offset that local segment outward toward the hull
    just enough to clear the stair path, and add short return segments at both
    ends so it reconnects to the original wall line. This is a
    `hull_wall_detour`, not a stair guard wall, and it must preserve enclosure
    coverage and stay inside the inward hull limit. Detour clearance must be
    capsule-scale; the earlier `0.18m` geometry margin left S2/S4 top routes
    playable in static checks but pinched in controller movement;
  - generate `player_enclosure_stair_cutaway_sleeve` blockers where a stair
    swept/cutaway volume intersects hull, floor, or ceiling boundaries. These
    sleeves enclose only the exposed cutaway boundary: side, underside, or
    soffit surfaces needed to prevent leaks around the stair void. They must
    not become broad stair guard walls. The first MX01 side-sleeve attempt
    emitted vertical stair-local walls and failed play review by cluttering the
    interior while still leaving floor/ceiling holes. Do not use vertical
    stair-edge wall sleeves as a general solution. The next stair-specific
    closure pass should focus on missing floor, ceiling, and soffit blockers
    around exposed stair cutaway boundaries while leaving stair side movement
    open except where the normal ship-edge perimeter wall already exists;
  - stair cutaway floor/ceiling closure should be horizontal-only. For each
    connector group, find small gaps between the stair/landing envelope and an
    already-generated ship-edge perimeter wall at each landing deck height.
    Fill only that horizontal gap with a thin
    `controller_safe_stair_cutaway_horizontal_closure` slab. Do not create new
    vertical stair walls, do not bridge to non-perimeter interior walls, and
    reject any slab that intrudes into stair or landing clearance, including
    full-height route headroom;
  - do not add broad automatic upper-hull continuations from every lower wall
    that has remaining hull height. The first MX01 continuation attempt created
    random interior walls and did not fix the false-balcony gap. Any
    balcony-adjacent hull continuation must be generated from a targeted
    classified edge/skin diagnostic that identifies the specific missing hull
    segment and proves it is not interior open volume;
  - constrain/clip only against the inward ship-skin occupancy silhouette; do
    not delete exposed floor edges for stair routes;
  - merge only collinear adjacent boundary runs with locked tolerances;
  - extrude each exterior floor edge run into a controller-safe wall box whose
    inner face is flush with the traversable floor edge and whose body is
    biased outward toward the skin;
  - split wall runs when their top limit changes so walls rise to the nearest
    floor-above or inward hull-skin limit instead of stopping at a fixed low
    height;
  - use short, deterministic run overlap to seal corners, but never shift wall
    runs away from the floor edge just to satisfy connector keepouts.
- The static validator must independently recompute the Stage 7A exact
  exterior floor-edge set, classify `ship_edge_boundary` versus
  `interior_balcony_edge`, and prove that every ship-edge boundary is covered
  by a generated wall primitive while balcony edges are not converted into full
  walls. A green primitive count or a closed-looking visible shell is not
  enough.
- **Global leak closure rule:** after the ordinary wall/ceiling generation,
  run a deterministic 3D leak pass that is not stair-specific. The first MX01
  local face-sampling attempt failed play review because it sampled many
  support-adjacent faces but did not prove connected escape paths from the
  interior. Replace that with a water-fill method:
  - rasterize accepted Stage 7A floors, stair/landing traversal supports, and
    all generated Stage 7B collision primitives into the same occupancy grid;
  - seed "water" in non-solid cells above every accepted floor, landing, and
    stair support surface;
  - flood-fill water only through connected non-solid cells inside the inward
    ship-skin occupancy;
  - separately flood-fill exterior air from the world/grid boundary through
    non-solid outside-hull cells;
  - treat a face as a leak candidate only when connected water reaches an
    outside-hull neighbor that is also connected to the exterior flood, through
    a face that is not already blocked by a floor, wall, ceiling, or stair
    support. Do not close faces into disconnected outside-hull pockets; these
    are usually local occupancy/skin classification artifacts and can create
    false interior walls;
  - vertical water-fill wall candidates must be support-anchored: the leaking
    water cell's X/Z footprint must have an accepted floor, landing, or stair
    support top within player-height below the candidate. High unanchored
    vertical faces are reported as `unanchored_vertical_faces` rather than
    becoming walls, because these produced false interior cockpit walls in
    MX01;
  - merge leak candidate faces by axis, plane, row, and locked height/width
    bins, then emit thin `controller_safe_global_leak_closure` slabs oriented
    on the leaking face. This can produce wall, floor, or ceiling blockers
    depending on the face normal;
  - reject any closure slab that intrudes into stair/landing/tread traversal
    clearance. Clearance must include both low tread/landing footprint overlap
    and full-height player headroom above every stair route sample; low
    footprint checks alone missed top-stair obstructions on MX01. If a leak is
    inside traversal clearance, report it as unresolved rather than placing a
    blocker in the route;
  - record generated, rejected, and unresolved leak counts in the report. Stage
    7B is not complete until unresolved exterior leaks are zero in this pass
    and play review confirms the result.
- **Ceiling height rule:** ceilings are generated from available vertical
  interior span, not from fixed player clearance. For each traversable ceiling
  region:
  - if a floor exists above that cell, rely on the accepted Stage 7A floor box
    above as the ceiling collision and do not add a duplicate low ceiling slab;
  - if no floor exists above, place a generated ceiling blocker at the highest
    inward-clamped ship-skin height available for that footprint;
  - derive ceiling blockers from per-cell top limits and merge only cells with
    compatible height bins, so curved/inward hull sections produce local
    ceiling strips instead of dragging an entire large slab low;
  - skip or split ceiling regions that would cross an interior balcony or stair
    transition;
  - do not delete high hull-ceiling cells merely because their 2D footprint
    overlaps a stair connector keepout. That policy creates ceiling holes
    around stairs. Stair clearance should be protected by the generated
    ceiling height and connector clearance validation, while ceilings remain
    present wherever the hull or next floor provides enclosure above;
  - use player capsule clearance only as a minimum validity check, never as the
    target height.
- Marching cubes and dual contouring remain evidence-shell tools. They can
  show the fitted skin and support future smoothing, but they are not the
  final playable wall collider for MX01 unless converted into simple
  controller-safe polygon/convex wall strips.
- **Build a smooth narrow-band SDF first:** derive signed distances near the
  accepted interior from the normalized OBJ triangles, including nearest
  triangle distance, projected source normal, and inside/outside sign. Binary
  occupancy may seed the sign and search bounds, but it is not enough for final
  player wall collision because it produces voxel stair-stepping and fragmented
  triangles.
- **Marching cubes first:** sample the smooth SDF at the configured enclosure
  offset and extract the inward collision shell with fixed cube traversal
  order, fixed interpolation, deterministic vertex quantization, deterministic
  triangle ordering, and locked simplification parameters. This is the first
  implementation target because it provides fast, inspectable evidence.
- **Dual contouring follow-up:** use dual contouring when marching cubes
  visibly rounds off panel edges, creates stair-stepped silhouettes, or loses
  tight fit around sharp hull features. Dual contouring should use deterministic
  Hermite samples / gradients, fixed QEF solving tolerances, stable cell order,
  and the same JSON configuration contract.
- Both algorithms must apply the same enclosure contract values:
  `voxel_size`, `refined_voxel_size`, `skin_inset`, `max_surface_error`,
  `max_normal_error`, `min_component_volume`, `weld_epsilon`,
  `vertex_quantization_epsilon`, and `player_clearance_margin`.
- **Controller-safe collider synthesis:** the extracted skin-fit shell is an
  evidence mesh, not the final player collider. Do not use raw or smoothed
  ConcavePolygonShape3D triangle soup for player-facing walls. Instead, derive
  controller-safe blockers from clean floor-aware deck polygons: continuous wall
  ribbons, swept capsule/box bands, convex strips, or other smooth primitives
  with deliberate overlap at joins. The playable collider should have
  predictable normals and no triangle-scale features for the character
  controller to catch on.
- **Debug/evidence separation:** retain raw voxel, raw marching-cubes, and
  smoothed skin-fit outputs as separate artifacts. The playable scene should
  use the controller-safe primitive collider, while review overlays may show raw
  reconstruction and smoothed shell evidence.

Acceptance:

- enclosure output contains no broad rectangular room walls or ceilings;
- playable enclosure collision is not a raw binary-occupancy isosurface;
- playable enclosure collision is not a ConcavePolygonShape3D triangle shell;
- enclosure walls and ceilings follow the ship skin silhouette within
  `max_surface_error`;
- enclosure geometry never protrudes outside the visual skin after the chosen
  inward offset;
- enclosure geometry does not invade Stage 7A traversal clearance volumes;
- controller-safe wall collision lets the player capsule slide along walls
  without catching on seams, triangle edges, or voxel-scale jagged features;
- tiny disconnected enclosure fragments below `min_component_volume` are
  removed before playable collision export;
- stairwells, hatches, and connector openings remain passable;
- repeated runs produce identical output hashes;
- generated enclosure meshes pass static skin-fit checks and player capsule
  clearance checks near required routes.

Lessons from failed MX01 enclosure pass:

- The `deterministic_tetrahedral_isosurface_enclosure_v1` attempt was better
  than rectangular rooms because it was skin-derived, but it was still based on
  binary occupancy sign changes at coarse voxel resolution. That produced
  fragmented, jagged wall triangles and player snagging.
- A binary occupancy shell is acceptable as a diagnostic artifact and as a
  conservative source of inside/outside evidence, but it is not acceptable as
  the final Stage 7B player collider.
- A high triangle count is not the same as smooth collision. The failed pass
  produced many triangles but still contained voxel-scale discontinuities.
- Static checks must measure smoothness and controller usability, not just
  object counts, inward offset, and absence of rectangular boxes.
- The next implementation should fit against the source OBJ surface or a true
  narrow-band SDF, then produce a simplified, smoothed, inward-constrained
  collision shell for gameplay.
- The `smoothed_occupancy_contour_enclosure_v2` attempt reduced fragmentation
  and triangle count, but still failed in playable review because it used a
  ConcavePolygonShape3D triangle shell as the actual wall collider. Static
  smoothness metrics were not enough to predict character-controller behavior.
- The next implementation must keep the skin-fitted shell as evidence and
  derive a separate primitive/swept-volume player collider from it.
- The first primitive-collider pass still failed because sampled wall ribbons
  did not prove containment. Primitive count is not a closure metric; any
  missed shell contour segment becomes a real escape gap in playable review.
- Stage 7B playable wall collision must include a deterministic containment
  invariant: every exterior-reachable edge of each accepted Stage 7A floor
  footprint is covered by a controller-safe blocker. MX01 currently has no
  player exterior portals, so route-reserved perimeter gaps are not allowed.
  The report and static validator must count exterior, covered, and uncovered
  perimeter edges from the exact floor footprint, not from a simplified
  left/right deck ring.
- Exterior perimeter blockers should be biased outside the traversable floor
  footprint with their inner face flush to the deck edge. Centering blockers on
  the floor edge can invade stair and landing clearance volumes while still
  leaving the same apparent wall line.
- Playable inspection must render the actual player collider primitives, not
  only the skin-fit evidence shell. Showing non-colliding evidence walls in the
  playable scene creates false positives during human review: a wall can look
  correct while the player passes through because the visible mesh is not the
  physics shape. Keep evidence visible in review scenes, and show the primitive
  collider mesh in playable scenes.

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
- Stair traversal should use nonblocking walkable support surfaces on the
  player support layer rather than solid stair tread collision. Connector
  landings should normally keep their primary collision so they remain reliable
  floors; only the specific landing/floor tile area that overlaps a stair
  transition lip should be converted to support-only collision. Removing all
  landing collision fixed one stair but caused deterministic fall-through
  regressions elsewhere.
- Stair transitions into an upper deck need a deterministic support apron at
  the highest tread extending toward the upper landing/exit lip by at least the
  player capsule radius plus clearance. The real MX01 S3-S6 failures showed
  that the PlayerController support ray can see the correct support while the
  capsule is still blocked by a normal floor or landing box edge. Any normal
  floor tile overlapping a stair top transition apron at the same height should
  be split around the local keepout, while the overlapping upper landing/floor
  transition area is represented by the nonblocking support layer instead. The
  keepout must be local to the transition, not applied to every connector
  landing globally.
- Stair passability fixes belong in the playable support/apron collision layer,
  not in broad Stage 7B enclosure clearance. Expanding the enclosure water-fill
  or ceiling clearances around stair standing envelopes moved too many sealing
  primitives and reopened exterior holes. Stage 7B may apply only narrow
  stair-route headroom adjustment to leak-closure primitives, and the report
  must record the adjusted primitive count.
- Static AABB/capsule checks are not sufficient for stair acceptance. Add a
  headless Godot probe that instances `Player.tscn`, drives real movement input
  up each stair route, and records `GetSlideCollision()` contacts plus
  walkable-support ray hits. Stage 7A/7B is not complete for a stair until this
  real PlayerController probe reaches the upper landing and exit pad without
  stalling.
- Enclosure route openings around stairs must reserve only the stair run axis
  for treads. Reserving the full inflated connector keepout around every tread
  leaves side gaps where the player can fall out beside stairways. Landings may
  reserve the same run axis as their stair group; landing side walls should
  normally remain enclosed.
- Stage 7B must not generate stair-local side walls, guard walls, or chute
  walls. Stairways are traversal features from Stage 7A; their only adjacent
  walls should be the enclosure walls that already lie on the ship-skin/floor
  footprint edge. Adding connector-derived guard primitives can make the
  stairs feel enclosed in static validation while blocking movement in play.
- Do not broadly replace stable floor-footprint wall primitives with smoothed
  contour-ribbon physics until the replacement has playable proof. The first
  MX01 contour-ribbon collider pass moved many wall surfaces at once and caused
  pass-through/stuck-wall regressions despite passing static checks.
- Floor cutaways, deck seams, and disconnected floor islands can become false
  "exterior" edges and produce interior walls inside the ship if edge
  classification is local. Fix these with padded-grid exterior flood fill from
  outside the exact footprint. Do not row-fill entire decks or use special
  deck-scoped rectangular wall footprints unless a human explicitly authors a
  solid interior obstruction.
- Wall boxes near stair landings need player-scale clearance, but perimeter
  closure has priority. MX01 should not shift perimeter walls away from the
  floor edge near S2/S4/S7, because that creates holes and pass-through lines.
  If a stair is too close to the skin wall, solve it by stair placement,
  thinner edge-biased wall primitives, or a deliberately authored local
  opening with replacement blocker geometry.
- Simplified left/right deck polygon rings can miss protruding floor edges and
  allow leaks. The playable wall polygon must remain exact-floor-edge aware:
  every exposed exterior edge of the Stage 7A floor footprint must be covered
  by a wall primitive unless an explicitly authored exterior portal replaces
  it.
- Perimeter wall overlap at run ends must stay small and connector-aware.
  Large overlap values can extend wall boxes into stair landings or support
  treads even when the route center remains clear. Static validation should
  check actual connector footprints, not only inflated keepout centers.
- Compact stair placement should prefer room edges only when that edge is still
  inside the accepted interior volume. "Move to the side" means near the usable
  floor edge, not necessarily all the way to the connector overlap bound.
- A stair aligned "above" another stair should use the lower stair's footprint
  as a reference, then offset only as much as needed to remain adjacent and
  inside the narrow floor section.
- After every human-reviewed stair change, regenerate the playable scene, the
  stair ID diagram, the traversal collision report, and static validation before
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
- generated skin-fitted interior enclosure collision;
- generated exterior dynamic physics collision;
- debug overlay toggles;
- player spawn points at entry and on each deck;
- ship physics test setup;
- camera anchors for evidence capture.

Acceptance:

- the scene imports through Godot on the host;
- the player can walk the generated interior route;
- dynamic collision is attached to the moving ship body, not the visual mesh;
- debug overlays can show traversal, enclosure, and exterior collision
  separately.

## Validation Requirements

### Static Validation

Create `ships/MX01/tools/validate_mx01_collision_static.py`.

Checks:

- source and generated artifact hashes match the manifest;
- generated files exist only under `ships/MX01`;
- traversal collision is inside the exterior shell after clearance;
- enclosure collision is inside the exterior shell at the configured inward
  offset;
- enclosure collision does not intersect required traversal clearance volumes;
- playable enclosure collision uses controller-safe primitive or convex/swept
  shapes derived from the fitted shell, not direct triangle mesh collision;
- playable enclosure collision passes capsule slide/sweep tests along wall and
  ceiling contact paths without snagging on voxel-scale features;
- enclosure smoothness metrics are below the configured snag threshold;
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
- interior traversal collision fit report;
- skin-fitted enclosure collision report;
- dynamic exterior collision fit report;
- side/top/front projection images;
- Godot contact sheet or screenshots;
- machine-readable manifest with all hashes and settings.

## Fit Metrics

Track these metrics per run:

- maximum traversal collision protrusion outside skin;
- maximum enclosure collision protrusion outside skin;
- reconstructed shell max/mean distance to visual skin;
- reconstructed shell protrusion and inset distance percentiles;
- enclosure raw triangle count;
- enclosure smoothed collision triangle count;
- enclosure playable primitive count;
- enclosure playable primitive seam/overlap count;
- enclosure disconnected fragment count before and after filtering;
- enclosure maximum adjacent-triangle normal delta after smoothing;
- enclosure maximum inward jag step against the player capsule radius;
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
- minimum route clearance after enclosure merge;
- player capsule wall-slide snag count;
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
- interior traversal collision, skin-fitted enclosure collision, and exterior
  dynamic collision are separate;
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
9. Implement generated floor/traversal collision meshes.
10. Implement a smooth narrow-band SDF or source-triangle projection field for
    Stage 7B enclosure.
11. Implement raw skin-fit enclosure reconstruction with marching cubes first.
12. Implement deterministic smoothing, simplification, fragment filtering, and
    capsule-friendly playable enclosure collision export.
13. Implement dynamic exterior compound collision fitting.
14. Implement static validation.
15. Add a standalone Godot review scene.
16. Add host import/build/review validation.

## Key Design Rule

The process may use the exterior skin to discover space, boundaries, and fit
targets, but generated collision must remain purpose-specific:

- player traversal collision is for walking inside the ship;
- skin-fitted enclosure collision is for preventing the player from clipping
  through the ship skin;
- dynamic exterior collision is for ship physics;
- debug visualization is for review only;
- no generated shape should silently serve multiple roles without being named
  and validated for each role.
