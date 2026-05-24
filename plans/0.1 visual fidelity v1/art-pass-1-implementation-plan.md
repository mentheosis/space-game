# Art Pass 1 Implementation Plan: Materials, Lighting, and Sky

## 1. Pass Goal

Make the current prototype look intentionally art-directed without changing gameplay geometry or ship/planet mechanics.

Art Pass 1 should improve:

- Space sky and atmosphere.
- Planet surface materials.
- Ship hull, floor, wall, cockpit, and interior readability.
- Lighting balance in space and inside the ship.
- Asset organization and licensing discipline.

This pass should not replace the ship model, add complex terrain, add rocks, or remodel landmarks. Those belong to later visual passes.

## 2. Current Project Reality

The game currently has:

- Phase 5 playable scene: `res://scenes/solar_system/Phase5TestWorld.tscn`.
- Two planets:
  - `PlanetBody.tscn`
  - `PlanetB.tscn`
- A placeholder ship:
  - `Ship.tscn`
  - boxy exterior
  - simple interior geometry
  - direct Godot primitive meshes/materials
- A procedural dark space sky in Phase 5 scenes.
- Basic directional light.
- Interior light in the ship.
- `assets/ASSET_LEDGER.md` exists.
- Project-authored material resources exist under `assets/materials/`.
- Planet and ship scenes now reference reusable `.tres` materials for major surfaces.
- Ship has visual-only emissive ceiling strip and rear thruster accents.
- Phase 5 sky, ambient light, and directional light have received a first tuning pass.
- Existing validation through Phase 5.

Important constraints:

- Do not change ship collision, player movement, hatches, seat, or gravity systems.
- Do not change gameplay scale.
- Do not alter controls.
- Preserve Phase 1 through Phase 5 automated validation.
- Keep imported assets documented from the first import.

## 2.1 Current Art Pass 1 Status

The first implementation pass completed the low-risk foundation:

- Asset ledger created.
- Asset folder structure started.
- Project-authored materials created for planets and ship surfaces.
- Planet A and Planet B now use reusable materials.
- Ship hull, floor, walls, hatch, and seat now use reusable materials.
- Ship interior lighting is improved.
- Simple emissive accents were added to the ship.
- Phase 5 sky and lighting were tuned.
- Phase 1 through Phase 5 validation passes.

However, Art Pass 1 is **not complete** against the original proposal.

Remaining proposal requirements after the first implementation pass were:

- Add a real starfield/HDRI or stronger procedural space treatment.
- Add texture-based materials or generated texture masks to the planets.
- Add roughness/normal variation to ship hull, floor, and walls.
- Add stronger material response so surfaces do not still read as flat color.
- Decide whether to import 1 to 2 CC0 PBR material sets.
- Update the asset ledger with any imported or generated assets.

Continuation status:

- CC0 texture sets from ambientCG were imported for gravel and sheet metal.
- A CC0 Kenney Space Kit craft model was imported for evaluation, but it is currently hidden because it did not integrate cleanly with the existing ship shell.
- A generated starfield texture was added.
- The asset ledger was updated for external and generated assets.
- Full validation still passes.

## 3. Scope

### In Scope

- Create asset folder structure.
- Create asset ledger.
- Add material naming conventions.
- Add first texture/material assets or generated project-native materials.
- Improve Planet A material.
- Improve Planet B material.
- Improve ship exterior material.
- Improve ship interior floor/wall material.
- Improve cockpit/interior lighting.
- Improve space sky/star treatment.
- Update Phase 5 world lighting if needed.
- Add a visual review checklist.
- Run validation after changes.

### Out of Scope

- Full custom ship mesh.
- New terrain geometry.
- Rocks/props/clutter.
- Landing pad redesign.
- Signal ruin visuals.
- Scanner UI visuals.
- Animation.
- Particle effects.
- Post-processing heavy effects.
- Asset streaming or LOD.
- Full material library.

### Optional Extension

- Source and import one open/CC0 placeholder ship model as a **visual-only child** of the existing `Ship.tscn`.
- Preserve the current ship `RigidBody3D`, collision shapes, hatches, seat, markers, third-person camera, and interior gameplay layout.
- Treat this as a placeholder visual upgrade, not the final ship design.

## 4. Visual Target for This Pass

Aim for **stylized but materially grounded**.

Practical interpretation:

- Planets should have different color/material identities.
- Ship should look like metal or coated composite rather than flat grey.
- Ship interior should be readable and navigable.
- Lighting should reveal forms without washing everything out.
- Materials should have roughness/normal variation where possible.
- Star/space background should add depth without distracting from navigation markers.

Avoid:

- Photorealistic texture packs on primitive geometry if they clash.
- High-contrast noisy planet surfaces that make movement hard to read.
- Dark ship interior corners.
- Excess bloom.
- A single blue/purple palette across everything.
- Large binary asset imports without a ledger entry.

## 5. Asset Strategy for Pass 1

Use the hybrid strategy from the visual fidelity proposal, but keep this pass narrow.

Recommended priority:

1. Project-native `StandardMaterial3D` resources for fast baseline improvement.
2. CC0 PBR texture sets for 2 to 4 important surfaces.
3. Generated or hand-authored simple masks only if open textures do not match the planet style.
4. No imported model assets in this pass.

This keeps risk low:

- Materials and lighting are easy to revert.
- Validation should not be affected.
- We can establish the asset pipeline before importing lots of meshes.

## 6. Proposed Asset Sources

### Primary Sources

Use CC0 sources first:

- Poly Haven:
  - HDRI or star/space-adjacent environment if suitable.
  - rock/ground material references.
  - Source: https://polyhaven.com/license
- ambientCG:
  - rocky ground materials.
  - worn metal or painted metal materials.
  - floor/panel materials.
  - Source: https://ambientcg.com/

### Project-Native Materials

For early implementation, it is acceptable to create `.tres` materials without external textures:

- `mat_planet_a_surface.tres`
- `mat_planet_b_surface.tres`
- `mat_ship_hull.tres`
- `mat_ship_floor.tres`
- `mat_ship_wall.tres`
- `mat_ship_light_emissive.tres`

These can use:

- albedo color
- roughness
- metallic
- emission
- generated noise texture resources if useful

### Generated Textures

Use only if needed:

- Planet color masks.
- Subtle surface variation.
- Simple starfield texture.

Track generated assets in the asset ledger:

- prompt/source
- generation date
- local path
- edits

## 7. Folder Structure

Add:

```text
assets/
  ASSET_LEDGER.md
  external/
    polyhaven/
    ambientcg/
  generated/
    textures/
  materials/
    planets/
    ship/
    environment/
  textures/
    planets/
    ship/
    environment/
  hdri/
```

Optional later:

```text
assets/models/
assets/licenses/
```

Do not add empty directories unless the repo convention supports them. If needed, add `.gitkeep` files only where useful.

## 8. Asset Ledger Format

Create:

```text
assets/ASSET_LEDGER.md
```

Initial columns:

```text
| Asset | Local Path | Source | Author | License | Download/Created Date | Modifications | Notes |
```

Rules:

- Every external asset gets a row before it is used in a scene.
- CC0 assets still get source and date.
- Generated assets get a row.
- Project-native materials can be listed in a separate "Project-authored" section if helpful.

## 9. Material Naming Convention

Use lowercase descriptive names:

```text
mat_planet_a_surface.tres
mat_planet_b_surface.tres
mat_ship_hull.tres
mat_ship_floor.tres
mat_ship_wall.tres
mat_ship_accent_emissive.tres
mat_space_sky.tres
```

Texture naming:

```text
tex_ship_hull_albedo.png
tex_ship_hull_normal.png
tex_ship_hull_roughness.png
```

Keep source names in the ledger, not necessarily in runtime material names.

## 10. Implementation Steps

### Step 1: Create Asset Structure and Ledger

Checklist:

- [x] Add `assets/ASSET_LEDGER.md`.
- [x] Add material folders.
- [x] Add texture folders.
- [x] Add external source folders only if assets are actually imported.
- [x] Document naming convention in the ledger or a short README section.

Acceptance:

- [x] Future asset imports have a clear place to go.
- [x] The first material assets can be tracked cleanly.

### Step 2: Create Baseline Project Materials

Create project-authored material resources first:

- [x] Planet A surface material.
- [x] Planet B surface material.
- [x] Ship hull material.
- [x] Ship floor material.
- [x] Ship wall material.
- [x] Ship accent/emissive material.

Suggested material direction:

Planet A:

- cooler teal/blue base
- higher roughness
- subtle noise or color variation

Planet B:

- warmer violet/magenta or mineral tone
- separate highlight/accent color
- rough surface response

Ship hull:

- off-white or muted light grey composite
- low metallic or mild metallic
- medium roughness
- subtle blue/green accent striping if done with separate simple materials

Ship floor:

- darker desaturated material
- rough
- readable against walls

Ship walls:

- lighter than floor
- not pure black
- low saturation

Acceptance:

- [x] Materials are `.tres` resources under `assets/materials/`.
- [x] Materials are reusable.
- [x] Scene files no longer rely only on anonymous inline materials for major surfaces.

### Step 3: Apply Materials to Planets

Files likely touched:

- `scenes/planets/PlanetBody.tscn`
- `scenes/planets/PlanetB.tscn`

Checklist:

- [x] Apply Planet A material to Planet A mesh.
- [x] Apply Planet B material to Planet B mesh.
- [x] Keep collision unchanged.
- [x] Keep gravity node settings unchanged.
- [x] Preserve Planet B navigation target data.
- [x] Preserve Planet B landing pad and beacon materials or improve them with project materials.

Acceptance:

- [x] Planet A and Planet B are visually distinct from orbit and on foot.
- [x] Planet surfaces are not overly noisy.
- [x] Validation still passes.

### Step 4: Improve Space Sky and Lighting

Files likely touched:

- `scenes/solar_system/Phase5TestWorld.tscn`
- `scenes/solar_system/Phase5Validation.tscn`
- possibly earlier test scenes only if needed

Checklist:

- [x] Improve procedural sky colors or add starfield treatment.
- [x] Tune ambient light so planets and ship remain readable.
- [x] Tune directional light energy and angle if necessary.
- [x] Keep navigation marker readable.
- [x] Avoid overusing glow.

Options:

1. Improved procedural sky:
   - lowest risk
   - no external assets
   - fastest
2. CC0 HDRI:
   - better lighting/reflections
   - requires asset import and ledger entry
   - may not look like stylized space
3. Generated starfield texture:
   - controllable
   - needs ledger entry
   - can be used as a background or sky material later

Recommendation:

- Start with improved procedural sky and lighting.
- Add HDRI only if it clearly improves the look.

Acceptance:

- [x] Space feels deeper than a flat dark background.
- [x] Ship silhouette is visible in third-person camera.
- [x] Planet B remains findable with HUD marker.
- [x] Interior is not washed out by ambient lighting.

### Step 5: Improve Ship Exterior Materials

Files likely touched:

- `scenes/ship/Ship.tscn`

Checklist:

- [x] Replace hull inline material with reusable hull material.
- [x] Add accent/emissive material to visual thruster or accent geometry if existing geometry supports it.
- [x] Avoid changing collision shapes.
- [x] Preserve third-person camera.
- [x] Preserve hatch/interior/seat nodes.

Acceptance:

- [x] Ship reads as a deliberate object from third-person view.
- [x] Ship is visible against space.
- [x] No physics or interaction behavior changes.

### Step 6: Improve Ship Interior Materials and Lighting

Files likely touched:

- `scenes/ship/Ship.tscn`

Checklist:

- [x] Replace black/flat interior surfaces with readable wall/floor materials.
- [x] Increase or tune interior light if needed.
- [x] Add emissive strip material to existing simple geometry if low risk.
- [x] Keep player movement through the interior unchanged.
- [x] Keep pilot seat prompt and hatch prompts readable.

Acceptance:

- [x] Interior is no longer black.
- [x] Floor/walls/cockpit are visually separable.
- [x] Player can orient inside ship quickly.
- [x] Seated third-person camera still activates correctly.

### Step 7: Optional First External Texture Import

Only do this after project-authored materials are working.

Candidate imports:

- One ambientCG or Poly Haven rocky ground material.
- One ambientCG or Poly Haven worn metal/panel material.

Checklist:

- [x] Download only needed resolution, likely 1K or 2K.
- [x] Add ledger row before use.
- [x] Place source files under `assets/external/...`.
- [x] Place project-ready textures under `assets/textures/...` if edited/renamed.
- [x] Create `.tres` material using imported maps.
- [x] Apply to one surface.

Acceptance:

- [x] Texture improves the look more than the project-authored material.
- [x] Texture style does not clash.
- [x] Repo size impact is acceptable.

### Step 8: Visual QA

Manual viewpoints:

- [ ] Player on Planet A.
- [ ] Ship exterior from outside.
- [ ] Ship interior before sitting.
- [ ] Third-person ship camera after takeoff.
- [ ] Zero-g gap between planets.
- [ ] Approach to Planet B.
- [ ] Planet B on foot.

Check:

- [ ] No surfaces are unexpectedly black.
- [ ] UI remains readable.
- [ ] Navigation marker remains readable.
- [ ] Planet colors are distinct.
- [ ] Ship does not disappear into the background.
- [ ] Interior lighting is usable.
- [ ] No material makes collision/interaction misleading.

### Step 9: Automated Validation

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

- [ ] Confirm no collision shape was modified accidentally.
- [ ] Confirm node names and paths were preserved.
- [ ] Confirm Phase 5 scenes still reference valid resources.

## 11. Deliverables

Required:

- [x] `assets/ASSET_LEDGER.md`
- [x] `assets/materials/planets/`
- [x] `assets/materials/ship/`
- [x] `assets/materials/environment/`
- [x] Updated Planet A material.
- [x] Updated Planet B material.
- [x] Updated ship hull material.
- [x] Updated ship interior materials.
- [x] Improved Phase 5 lighting/sky.
- [x] Validation still passing.

Optional:

- [x] One CC0 rocky ground PBR material.
- [x] One CC0 metal/panel PBR material.
- [x] One generated starfield or sky texture.
- [ ] One environment/HDRI asset.

## 11.1 Remaining To-Do Items

The next continuation of Art Pass 1 should complete these items before moving to Art Pass 2.

### A. Add Surface Variation to Planets

Current state:

- Planet A and Planet B have reusable materials, but they are still mostly color-only.

Remaining work:

- [x] Add authored or generated texture variation to Planet A.
- [x] Add authored or generated texture variation to Planet B.
- [x] Prefer subtle color/noise masks over high-frequency detail.
- [x] Keep planet surfaces readable while walking.
- [x] Update `assets/ASSET_LEDGER.md` for any generated or imported textures.

Implementation options:

- Use generated/simple hand-authored planet masks.
- Use a CC0 rocky/mineral PBR material as source inspiration.
- Use Godot `NoiseTexture2D` resources if they give acceptable results without bitmap files.

Acceptance:

- [x] Planet surfaces no longer read as single flat colors.
- [x] Planet A and Planet B remain visually distinct.
- [x] No texture noise interferes with navigation or landing.

### B. Add Roughness/Normal Variation to Ship Materials

Current state:

- Ship hull, floor, and walls now use reusable materials, but still lack real surface variation.

Remaining work:

- [x] Add normal/roughness variation to ship hull.
- [x] Add normal/roughness variation to ship floor.
- [x] Add normal/roughness variation to ship walls.
- [x] Consider one CC0 metal/panel PBR set from ambientCG or Poly Haven.
- [x] Keep material style consistent with the simple ship geometry.

Acceptance:

- [x] Hull catches light in a less flat way.
- [x] Floor and wall surfaces separate visually without relying only on color.
- [x] Interior still feels readable and not visually noisy.

### C. Add a Better Space Treatment

Current state:

- Phase 5 has tuned procedural sky colors, but no real starfield, HDRI, or authored sky texture.

Remaining work:

- [x] Decide between improved procedural starfield, generated starfield texture, or CC0 HDRI.
- [x] Add basic starfield treatment if not using HDRI.
- [x] Keep stars subtle enough that navigation UI remains readable.
- [x] Track imported/generated sky assets in the ledger.

Acceptance:

- [x] Space feels deeper than a flat dark background.
- [x] Ship and planets remain readable against the sky.
- [x] The target marker remains legible.

### D. Material Naming and Ledger Cleanup

Current state:

- Material files and ledger exist, but the naming convention is not yet documented inside the ledger.

Remaining work:

- [x] Add a naming convention section to `assets/ASSET_LEDGER.md`.
- [x] Add any missing project-authored material entries if more materials are added.
- [x] Add source rows before any external download is committed.

Acceptance:

- [x] A future asset import has clear naming and ledger rules.
- [x] All generated/imported assets have provenance.

### E. Optional CC0 Texture Import

Current state:

- No external assets have been imported yet.

Remaining work:

- [x] Choose at most two CC0 texture sets:
  - one rocky/mineral surface
  - one worn metal/panel surface
- [x] Use 1K or 2K resolution only.
- [x] Add asset ledger rows.
- [x] Apply only if the texture improves the current authored material.

Recommended sources:

- ambientCG for PBR materials.
- Poly Haven for PBR materials or HDRI.

Acceptance:

- [x] Imported textures improve the scene more than project-authored materials alone.
- [x] Repo size remains reasonable.
- [x] License/source tracking is complete.

### F. Optional Placeholder Ship Model

Current state:

- Ship visuals are still mostly box primitives with improved materials.
- The proposal originally deferred full ship geometry to a later art pass, but an open placeholder model can improve readability now if integrated safely.

Recommended first source:

- Kenney Space Kit.
- Source: https://kenney.nl/assets/space-kit
- License: Creative Commons CC0.
- Reason: includes ship models, glTF-compatible formats, and a clean license.

Secondary candidates:

- OpenGameArt CC0 spaceship models, only if the asset format and style are better than Kenney.
- Use with stricter per-asset license checks because OpenGameArt license varies by asset.

Remaining work:

- [x] Download Kenney Space Kit or another verified CC0 ship source.
- [x] Add ledger entry before committing the model.
- [x] Import one ship model under `assets/external/kenney/space-kit/` or a normalized path under `assets/models/ship/placeholders/`.
- [x] Create a wrapper scene such as `scenes/ship/PlaceholderShipVisual.tscn`.
- [x] Instance the visual scene under `Ship.tscn`.
- [x] Disable or ignore imported collision.
- [x] Keep existing collision shapes as the gameplay/physics source of truth.
- [x] Scale and rotate the model to align with the current ship:
  - local forward should match current ship forward
  - hatch side should remain understandable
  - pilot camera should still frame the ship
- [ ] Hide or remove the current boxy exterior mesh only after the imported visual is aligned.
- [x] Keep interior walkability functional.
- [x] Run full validation.

Acceptance:

- [ ] Ship silhouette is noticeably more ship-like in third-person view.
- [x] Player can still enter, sit, fly, land, stand, and exit.
- [x] Collision behavior is unchanged.
- [x] Hatch/interior prompts remain understandable.
- [x] Asset ledger tracks source, license, date, local path, and modifications.

## 12. Success Criteria

Art Pass 1 is complete when:

- [x] The prototype no longer reads as purely flat primitive materials.
- [x] Planet A and Planet B have clear visual separation.
- [x] The ship exterior is visible and materially distinct.
- [x] The ship interior is readable without manual explanation.
- [x] Space lighting feels intentional and has depth.
- [x] The asset ledger exists.
- [x] The asset ledger covers every imported/generated asset if any are added.
- [x] No gameplay validation regresses.

## 13. Recommended Implementation Order

1. Create `assets/` structure and ledger.
2. Create project-authored `.tres` materials.
3. Apply materials to planets.
4. Apply materials to ship exterior/interior.
5. Tune lighting and sky.
6. Run validation.
7. Manual visual review.
8. Decide whether external textures are necessary for this pass.
9. If yes, import 1 to 2 CC0 texture sets and update ledger.
10. Run validation again.

## 14. Open Questions

1. Should Art Pass 1 use only project-authored materials first, or should we immediately import a small number of CC0 PBR texture sets?

Recommended answer:

- Start with project-authored materials, then import only the one or two texture sets that clearly improve the result.

2. Do we want the visual style closer to low-poly/stylized or stylized-real PBR?

Recommended answer:

- Stylized-real PBR: simple geometry, readable colors, but materials with roughness/normal response.

3. Should the sky stay procedural for now, or should we bring in an HDRI/starfield asset immediately?

Recommended answer:

- Keep procedural for the first implementation pass. Add HDRI/starfield only if the procedural sky still feels too flat.

4. What texture resolution budget should we allow in-repo?

Recommended answer:

- Use 1K for most textures, 2K for hero/large surfaces, and avoid 4K in this pass.

5. Should visual changes apply only to Phase 5 scenes or also earlier phase scenes?

Recommended answer:

- Update shared scenes like `PlanetBody.tscn`, `PlanetB.tscn`, and `Ship.tscn`, so all phases benefit where they instance the same assets. Avoid hand-editing old validation scenes unless needed.

6. Should we commit downloaded binary assets directly to the repo?

Recommended answer:

- Yes for a small number of curated CC0 assets in this prototype, as long as the ledger is accurate and file sizes remain reasonable. Revisit Git LFS only if assets become large.
