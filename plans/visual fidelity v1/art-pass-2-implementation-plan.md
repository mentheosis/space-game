# Art Pass 2 Implementation Plan: Planet Surface Geometry

## 1. Pass Goal

Make Planet A and Planet B feel explorable beyond smooth textured spheres by adding surface geometry, landmarks, landing readability, and small props.

Art Pass 2 should improve:

- Planet silhouettes from space.
- On-foot navigation.
- Landing approach readability.
- Surface variety near player-relevant areas.
- Visual identity difference between Planet A and Planet B.

This pass should not replace the base planet sphere, remodel the ship, implement terrain streaming, or create a full environment art pipeline.

## 2. Current Project Reality

Art Pass 1 established:

- Asset ledger exists at `assets/ASSET_LEDGER.md`.
- Planet surfaces use ambientCG gravel texture maps through reusable materials.
- Ship hull/floor/walls use ambientCG sheet metal texture maps.
- Phase 5 has a generated starfield.
- The Kenney placeholder ship model was imported but hidden because it did not integrate cleanly.
- The current visible ship is still the project-authored hull with improved materials.
- Validation passes through Phase 5.

Current relevant scenes:

- `scenes/planets/PlanetBody.tscn`
- `scenes/planets/PlanetB.tscn`
- `scenes/solar_system/Phase5TestWorld.tscn`
- `scenes/solar_system/Phase5Validation.tscn`
- `scenes/ship/Ship.tscn`

Current planet geometry:

- Planet A:
  - textured sphere
  - one simple `NorthTower`
- Planet B:
  - textured sphere
  - simple landing pad
  - beacon

Important constraints:

- Keep planet base spheres.
- Keep current gravity setup.
- Keep ship landing and validation stable.
- Avoid placing props where the ship spawns, lands, exits, or validation moves the player.
- Do not block hatches, landing pad, or validation paths.
- Track any imported assets in the asset ledger.

## 3. Scope

### In Scope

- Add reusable rock/surface prop scenes.
- Add simple surface landmark scenes.
- Improve Planet B landing pad readability.
- Add local terrain dressing near Planet A spawn/ship area.
- Add local terrain dressing near Planet B landing area.
- Add distinct landmark geometry to Planet A and Planet B.
- Add collision only where it improves gameplay/readability.
- Add surface placement conventions for spherical planets.
- Run full validation.

### Out of Scope

- Procedural terrain generation.
- Heightmapped planets.
- Destructible terrain.
- Large imported environment kits.
- Ship exterior remodel.
- Ship interior remodel.
- New gameplay mechanics.
- Scanner/signals/clues.
- Moving planets or orbital simulation.
- Floating origin.
- Vegetation systems.

## 4. Visual Target

The surface pass should remain stylized and readable.

Planet A:

- Cooler, practical, exploratory feel.
- More geometric/technical landmarks.
- Teal/blue surface tone with warm landmark contrast.
- Should feel like a starting planet with recognizable launch area.

Planet B:

- More mineral/alien feel.
- Violet/magenta surface tone.
- Landing pad and beacon should be readable from approach.
- Surface props should frame the first exploration destination without becoming clutter.

Avoid:

- Dense noisy scatter.
- Props that make spherical walking awkward.
- Large collision clutter near ship exits.
- Random asset-pack look.
- Overly realistic rocks that clash with simple planet/ship geometry.

## 5. Asset Strategy

Use three asset tiers.

### Tier 1: Project-Authored Primitive Props

Use first.

Examples:

- low-poly rocks made from scaled/rotated primitives
- beacon fins
- landing pad edge markers
- simple monoliths
- antenna blocks
- surface panels

Benefits:

- Fast.
- Consistent style.
- No license complexity.
- Easy collision control.

### Tier 2: CC0 Placeholder Props

Use selectively.

Potential sources:

- Kenney for low-poly rocks, crates, sci-fi pieces.
- Quaternius for stylized low-poly props if style fits.
- Poly Haven for rocks only if the visual style does not clash.

Rules:

- Use only CC0 assets for this pass.
- Import only curated files, not large full packs unless necessary.
- Add ledger rows before committing.
- Wrap imported models in project scenes.

### Tier 3: Custom Hero Landmarks

Use for the main landmarks.

Examples:

- Planet A launch landmark.
- Planet B mineral arch or signal monolith.
- Better landing pad geometry.

Recommendation:

- Use simple project-authored meshes or Godot primitive compositions for now.
- Defer Blender-authored hero assets until the surface layout is proven.

## 6. Surface Placement Rules

Because planets are spherical, every placed prop needs a clear radial-up convention.

For a prop on a planet:

```text
surface_normal = normalize(prop_world_position - planet_center)
prop_up = surface_normal
prop_position = planet_center + surface_normal * (planet_radius + offset)
```

Recommended approach for Art Pass 2:

- Place important props manually in scene files.
- Use a small helper script only if manual placement becomes error-prone.
- Avoid procedural scatter for now.

Potential helper:

```text
res://scripts/components/SurfaceAnchor.cs
```

Fields:

- `PlanetPath`
- `SurfaceOffset`
- `YawDegrees`

Behavior:

- On ready or editor update, align node up to radial planet up.
- Keep yaw around local up.

Recommendation:

- Add `SurfaceAnchor.cs` only if we place enough props that manual transforms become painful.

## 7. Collision Policy

Not every surface prop needs collision.

Collision should exist for:

- landing pad surface
- large rocks the player would expect to stand on
- major landmarks
- props that visibly block the path

Collision should not exist for:

- tiny scatter
- background-only decoration
- thin antenna details
- emissive markers

Rules:

- Use simple collision shapes.
- Avoid concave imported collision.
- Do not add collision near ship hatch exit points unless tested.
- Keep validation paths clear.

## 8. Proposed New Files

### Props

```text
scenes/props/RockSmall.tscn
scenes/props/RockMedium.tscn
scenes/props/RockCluster.tscn
scenes/props/SurfaceMarker.tscn
```

### Landmarks

```text
scenes/landmarks/PlanetALaunchLandmark.tscn
scenes/landmarks/PlanetBMineralArch.tscn
```

### Planet B Landing

```text
scenes/landmarks/PlanetBLandingPadVisual.tscn
```

### Materials

```text
assets/materials/props/mat_rock_a.tres
assets/materials/props/mat_rock_b.tres
assets/materials/props/mat_surface_marker.tres
assets/materials/landmarks/mat_landmark_a.tres
assets/materials/landmarks/mat_mineral_b.tres
```

Optional:

```text
scripts/components/SurfaceAnchor.cs
```

## 9. Existing Files to Modify

### `scenes/planets/PlanetBody.tscn`

- Add Planet A prop clusters.
- Replace or supplement `NorthTower` with a more intentional launch landmark.
- Add a few visible navigation silhouettes.
- Keep spawn point and ship area clear.

### `scenes/planets/PlanetB.tscn`

- Improve landing pad visual.
- Add landing pad edge markers.
- Add Planet B mineral/alien landmark.
- Add rock clusters around but not on top of the landing area.
- Preserve:
  - `PlanetBGravity`
  - `NavigationTarget`
  - `SpawnPoint`
  - `LandingMarker`

### `assets/ASSET_LEDGER.md`

- Add any imported CC0 prop/model assets.
- Add any project-authored material entries.

### `scripts/validate.sh`

- No change expected.
- Only modify if Art Pass 2 adds a dedicated visual validation scene.

## 10. Implementation Steps

### Step 1: Create Prop and Landmark Folders

Checklist:

- [x] Add `scenes/props/`.
- [x] Add `scenes/landmarks/`.
- [x] Add `assets/materials/props/`.
- [x] Add `assets/materials/landmarks/`.

Acceptance:

- [x] New surface assets have clear locations.

### Step 2: Create Project-Authored Prop Materials

Checklist:

- [x] Add rock material for Planet A.
- [x] Add rock/mineral material for Planet B.
- [x] Add surface marker material.
- [x] Add landmark material for Planet A.
- [x] Add mineral/emissive accent material for Planet B.

Acceptance:

- [x] Materials fit the existing Art Pass 1 palette.
- [x] Materials do not make props look like unrelated asset-pack objects.

### Step 3: Create Reusable Rock Props

Recommended implementation:

- Use `MeshInstance3D` with simple primitive meshes.
- Compose rocks from one or more scaled boxes or low-poly shapes.
- Use simple collision only for medium/large rocks.

Checklist:

- [x] `RockClusterA.tscn`
- [x] `RockClusterB.tscn`
- [x] `SurfaceMarker.tscn`
- [x] Collision on medium rocks only if useful.
- [x] No collision on tiny decorative pieces.

Acceptance:

- [x] Rocks add surface variation without clutter.
- [x] Rocks fit both planets with material overrides or variants.

### Step 4: Improve Planet B Landing Pad

Goal:

- Make the landing destination readable from approach without redesigning gameplay.

Checklist:

- [x] Add visual pad edge markers.
- [x] Add low-profile lights or colored strips.
- [x] Add a clearer center/landing target.
- [x] Keep existing landing pad collision stable.
- [x] Keep validation landing position clear.
- [x] Keep ship exit area clear.

Acceptance:

- [x] Planet B landing pad is easier to spot from the ship.
- [x] Landing pad does not trap or snag the player/ship.

### Step 5: Add Planet A Surface Dressing

Checklist:

- [x] Add 2 to 4 small rock clusters around the starting region.
- [x] Add one intentional launch-area landmark.
- [x] Add at least one distant silhouette visible from the surface.
- [x] Keep ship spawn and player spawn clear.
- [x] Keep existing `NorthTower` or replace it with a more intentional landmark.

Acceptance:

- [x] Planet A no longer feels like a smooth sphere with one tower.
- [x] The starting region remains readable.
- [x] Phase 1 and Phase 5 validation still pass.

### Step 6: Add Planet B Surface Dressing

Checklist:

- [x] Add 2 to 4 rock/mineral clusters near but not on the landing pad.
- [x] Add one distinctive mineral arch, shard group, or monolith.
- [x] Add a visual route from landing pad toward the landmark.
- [x] Keep `LandingMarker` area clear.
- [x] Keep player walking test clear.

Acceptance:

- [x] Planet B feels visually distinct from Planet A.
- [x] The landing zone has a sense of place.
- [x] The added geometry does not interfere with Phase 5 validation.

### Step 7: Optional CC0 Prop Import

Only do this if project-authored primitive props are too weak.

Checklist:

- [ ] Select one CC0 rock/prop source.
- [ ] Add ledger entry before committing.
- [ ] Import only curated model files.
- [ ] Wrap imported model in `scenes/props/`.
- [ ] Disable imported collision unless intentionally authored.
- [ ] Use project materials where possible.

Acceptance:

- [ ] Imported prop improves the surface more than a simple authored primitive.
- [ ] Style matches the current visual direction.
- [ ] License/source tracking is complete.

### Step 8: Validation

Run:

```bash
scripts/validate.sh
```

Acceptance:

- [x] Phase 1 validation passes.
- [x] Phase 2 validation passes.
- [x] Phase 3 validation passes.
- [x] Phase 4 validation passes.
- [x] Phase 5 validation passes.

If validation fails:

- [ ] Check whether a new collision shape blocks player movement.
- [ ] Check whether a new collision shape affects ship landing.
- [ ] Check whether node paths in planet scenes changed.
- [ ] Check whether validation direct placement now intersects a prop.

### Step 9: Manual Visual QA

Manual viewpoints:

- [ ] Planet A spawn.
- [ ] Planet A near ship.
- [ ] Planet A from low-altitude ship view.
- [ ] Planet B approach.
- [ ] Planet B landing pad.
- [ ] Planet B on foot.
- [ ] Third-person ship camera near both planets.

Check:

- [ ] Surface props do not look randomly scattered.
- [ ] Props help navigation rather than obscure it.
- [ ] Landing pad is more readable.
- [ ] Planet A and B identities are clearer.
- [ ] Prop collision behaves as expected.
- [ ] No props visibly float above or sink below the spherical surface.

## 11. Success Criteria

Art Pass 2 is complete when:

- [x] Planet A has surface dressing near the starting region.
- [x] Planet B has surface dressing near the landing region.
- [x] Planet B landing pad is easier to read from approach.
- [x] Each planet has at least one distinctive landmark.
- [x] Props align convincingly to spherical surfaces.
- [x] Collision exists only where useful.
- [x] Phase 1 through Phase 5 validation passes.
- [x] The asset ledger covers any imported/generated assets.
- [x] The pass does not introduce a generic asset-pack look.

## 12. Recommended Implementation Order

1. Create prop/landmark folders and materials.
2. Create project-authored rock and marker props.
3. Improve Planet B landing pad visuals.
4. Add Planet A dressing and landmark.
5. Add Planet B dressing and landmark.
6. Run validation.
7. Manual visual QA.
8. Decide whether a CC0 prop import is needed.

## 13. Open Questions

1. Should Art Pass 2 use only project-authored primitive props first, or should we immediately import CC0 rock models?

Recommended answer:

- Start project-authored. Import CC0 rocks only if primitive props look too weak.

2. Should surface props have collision by default?

Recommended answer:

- No. Collision only for large, readable props.

3. Should we add a `SurfaceAnchor` helper now?

Recommended answer:

- Only if manual radial placement becomes tedious or error-prone during implementation.

4. Should Planet B landing pad become a real gameplay landing zone?

Recommended answer:

- Not yet. Keep it visual in Art Pass 2; landing logic remains surface/speed/upright based.

5. Should Art Pass 2 touch old validation/test scenes?

Recommended answer:

- Only through shared planet scenes. Avoid hand-editing old validation scenes unless a prop breaks validation.

