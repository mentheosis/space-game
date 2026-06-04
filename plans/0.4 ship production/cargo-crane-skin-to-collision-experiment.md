# 0.4 CargoCrane Skin-To-Collision Experiment

## Purpose

Create an isolated, from-scratch experiment that turns the source ship skin at
`assets/models/ship/placeholders/oga_3d_space_ship_pack/CargoCrane.obj` into a
production-oriented collision package.

This experiment must not reuse prior CargoCrane generated assets, prior
CargoCrane tools, existing CargoCrane contracts, or old interior planning
outputs. Existing repo work may be read only for general project conventions,
but the implementation, outputs, validation reports, and Godot integration path
for this experiment must live under a new 0.4 namespace.

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

## Fresh Experiment Namespace

Use a new namespace for all generated work:

- `tools/ship_production_04/`
- `assets/source/ship_production_04/cargo_crane/`
- `assets/models/ship_production_04/cargo_crane/`
- `reports/ship_production_04/cargo_crane/`
- `scenes/ship_production_04/cargo_crane/`

No generated 0.4 file should overwrite or depend on prior CargoCrane outputs.

## Source Of Truth

The only initial geometry source is:

`assets/models/ship/placeholders/oga_3d_space_ship_pack/CargoCrane.obj`

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

## Deterministic Geometry Process

### Stage 1: Normalize Skin

Create `normalize_cargo_crane_skin.py`.

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

Create `build_cargo_crane_sdf.py`.

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

### Stage 3: Extract Usable Interior Volume

Create `extract_cargo_crane_interior_volume.py`.

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

### Stage 4: Fit Multi-Level Traversal Layout

Create `fit_cargo_crane_multilevel_traversal.py`.

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

### Stage 5: Generate Interior Collision Meshes

Create `generate_cargo_crane_interior_collision.py`.

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

### Stage 6: Generate Dynamic Exterior Compound Collision

Create `generate_cargo_crane_dynamic_collision.py`.

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

### Stage 7: Godot Integration Scene

Create a standalone scene under:

`scenes/ship_production_04/cargo_crane/`

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

Create `validate_cargo_crane_collision_static.py`.

Checks:

- source and generated artifact hashes match the manifest;
- generated files exist only in the 0.4 namespace;
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
4. Add a future host review profile for the 0.4 CargoCrane experiment once the
   scene and evidence capture are stable.

### Evidence Artifacts

Each full run should produce:

- normalized source audit report;
- SDF/voxel report;
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
- the player can traverse all accepted interior decks in the review scene;
- at least three vertical levels or level bands are used where the hull permits;
- exterior dynamic collision is compound convex/simple, not concave trimesh;
- interior traversal collision and exterior dynamic collision are separate;
- validation reports show no untracked reuse of old CargoCrane outputs;
- Godot imports the generated assets through the host toolchain.

## Implementation Order

1. Create the 0.4 namespace directories and config skeleton.
2. Implement OBJ normalization and source audit.
3. Implement SDF/occupancy field generation with projection evidence.
4. Implement interior volume extraction and deck-band discovery.
5. Implement traversal graph fitting and route validation.
6. Implement generated interior collision meshes.
7. Implement dynamic exterior compound collision fitting.
8. Implement static validation.
9. Add a standalone Godot review scene.
10. Add host import/build/review validation.

## Key Design Rule

The process may use the exterior skin to discover space, boundaries, and fit
targets, but generated collision must remain purpose-specific:

- player traversal collision is for walking inside the ship;
- dynamic exterior collision is for ship physics;
- debug visualization is for review only;
- no generated shape should silently serve multiple roles without being named
  and validated for each role.
