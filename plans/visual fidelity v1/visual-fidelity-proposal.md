# Visual Fidelity and Asset Pipeline Proposal

## 1. Goal

Increase the prototype's graphical fidelity without turning the project into an art-production sink.

The next visual pass should make the game feel more like a deliberate place and less like a greybox:

- Textured planets.
- Better ship exterior and interior geometry.
- More readable landing locations.
- Rocks, surface props, and landmarks.
- Improved lighting, sky, and material response.
- A repeatable asset import pipeline for Godot.

The goal is not final art. The goal is a stronger visual target that supports exploration and gives future gameplay phases better context.

## 2. Research Summary

Useful asset sources:

- Kenney assets are public domain/CC0 according to Kenney's support page and asset listings. Good for prototype props, simple shapes, UI assets, and low-poly kits. Source: https://kenney.nl/support and https://kenney.itch.io/kenney-game-assets
- Poly Haven provides CC0 HDRIs, textures, and models. Best fit for sky lighting, PBR materials, rocks, terrain-adjacent surfaces, and reference-quality textures. Source: https://polyhaven.com/license
- ambientCG provides CC0 PBR materials, HDRIs, and models. Best fit for surface materials, rocky ground, metal, panels, fabric, and generic PBR texture sets. Source: https://ambientcg.com/
- Quaternius has CC0 game-ready low-poly packs, including sci-fi modular assets in formats that include glTF. Best fit for quick modular interior/exterior kitbashing if the stylized look matches. Source: https://quaternius.com/packs/modularscifimegakit.html
- NASA 3D resources and imagery can be useful for space reference and some planet/space assets, but NASA's media guidelines have specific brand/identifier restrictions. Use carefully and avoid NASA logos, insignia, endorsement implications, and mission-identifying assets unless explicitly appropriate. Sources: https://www.nasa.gov/3d-resources/ and https://www.nasa.gov/nasa-brand-center/images-and-media/
- Sketchfab has many downloadable Creative Commons models and provides glTF exports, but licenses vary by asset. Use only if we maintain per-asset attribution and license records. Source: https://sketchfab.com/features/gltf
- OpenGameArt has useful assets, but licenses vary and preview media may not match downloadable asset licenses. Use only with careful asset-by-asset review. Source: https://opengameart.org/content/faq
- Godot supports importing 3D scenes including glTF. Use glTF/GLB as the primary interchange format. Source: https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/index.html

## 3. Recommendation

Use a **hybrid asset strategy**:

1. Use CC0/open asset libraries for generic materials, HDRIs, rocks, small props, surface clutter, and temporary kitbash pieces.
2. Create or generate custom assets for the ship, key landmarks, signal ruins, planet silhouettes, cockpit forms, and anything players will emotionally remember.
3. Keep a documented asset ledger from the start, even for CC0 assets.
4. Import assets through a controlled folder structure and Godot scene-wrapper pattern.

This is better than either extreme:

- Using only open assets risks a generic asset-pack look.
- Generating or modeling everything from scratch slows gameplay development too much.

## 4. Asset Source Tradeoffs

### CC0/Open Asset Libraries

Best for:

- PBR texture sets.
- HDRIs and sky lighting.
- Rocks and terrain props.
- Crates, panels, cables, pipes, vents, antennas.
- Placeholder sci-fi modular pieces.
- Generic ship-interior kitbash geometry.

Benefits:

- Fastest way to improve visual quality.
- Low legal friction if using CC0.
- Good enough for prototype and vertical slice.
- Lets us spend custom art time on the game's unique identity.

Risks:

- Style mismatch.
- Overused assets can be recognizable.
- Model scale, pivots, collision, and materials often need cleanup.
- Non-CC0 licenses require attribution and tracking.

Recommendation:

- Prefer CC0 sources first: Poly Haven, ambientCG, Kenney, Quaternius.
- Use Sketchfab/OpenGameArt only when an asset is especially useful and the license is clean.

### Generated Assets

Best for:

- Planet surface textures.
- Concept directions.
- Unique decals and signs.
- Stylized material masks.
- Rough design explorations for ship shapes and ruins.

Benefits:

- Can create a more unique look quickly.
- Good for ideation and placeholder textures.
- Useful when open libraries do not fit the desired tone.

Risks:

- Consistency can be poor.
- Generated outputs often need cleanup.
- Licensing and provenance should still be tracked.
- Generated 3D models may need retopology, UVs, scale correction, and material work.

Recommendation:

- Use generated bitmap textures and concept references selectively.
- Do not rely on generated 3D models as production-ready meshes.
- Prefer Blender-authored or kitbashed geometry for ship, interiors, and landmarks.

### Custom Modeling

Best for:

- Ship exterior.
- Cockpit and seat.
- Hatch/door shape.
- Planet landmarks.
- Signal ruin.
- Landing pads.
- Any recurring visual language.

Benefits:

- Creates a coherent identity.
- Geometry can match gameplay needs exactly.
- Collision and scale can be authored cleanly.
- Easier to revise around interaction points.

Risks:

- Slower.
- Requires a consistent modeling workflow.
- Can distract from gameplay if scope is too broad.

Recommendation:

- Custom-model only the hero assets and reusable kits.
- Use open textures and simple materials on custom geometry.

## 5. Visual Direction

The game should not chase photorealism yet.

Recommended target:

- Stylized but materially grounded.
- Readable silhouettes.
- Strong color identity per planet.
- Simple geometry with better materials.
- Clear landmarks visible from the ship.
- Practical, compact ship interior.

Avoid:

- Asset-store realism mixed with low-poly placeholders.
- Busy surface noise that hides navigation cues.
- Dark interiors where interaction points disappear.
- High-poly assets with no gameplay value.
- A one-note palette across all planets.

## 6. Proposed Art Passes

### Pass 1: Materials, Lighting, and Sky

Goal:

- Make the current geometry look less placeholder with minimal gameplay risk.

Tasks:

- Add a real space sky/HDRI or improved procedural sky.
- Add basic starfield treatment if HDRI is not enough.
- Replace flat planet materials with authored or CC0 texture-based materials.
- Add roughness/normal variation to ship hull, floor, and walls.
- Improve interior lighting so the ship is readable.
- Add material naming conventions.

Recommended sources:

- Poly Haven HDRIs and textures.
- ambientCG PBR materials.
- Generated planet texture masks if open materials do not fit.

Deliverables:

- `assets/materials/`
- `assets/textures/`
- Updated Planet A and Planet B materials.
- Updated ship interior/exterior materials.
- Updated lighting in Phase 5 or new visual test scene.

### Pass 2: Planet Surface Geometry

Goal:

- Establish planet surface layout, placement rules, and exploration readability beyond smooth spheres.

Tasks:

- Add initial surface rocks and small props.
- Add a more readable Planet B landing pad.
- Add first-pass landmark placement to Planet A and Planet B.
- Add local terrain-feature placeholders near key areas using placed meshes.
- Keep the base planet sphere for now.

Recommended sources:

- Project-authored primitive placeholders.
- CC0/open assets only if they are quick and clean.

Deliverables:

- `scenes/props/`
- `scenes/landmarks/`
- Improved Planet A and Planet B scene layout.
- Surface placement conventions.
- Validation-safe collision policy.

Important note:

- Pass 2 is allowed to use crude placeholder geometry to prove placement and readability. It should not be considered the final quality bar for props or landmarks.

### Pass 3: High-Quality Geometry and Model Framework

Goal:

- Establish the geometry quality bar for all future art work, then replace crude placeholders with higher-quality models across planets, props, landmarks, and reusable environment kits.

Reason for adding this pass:

- The first surface geometry pass proved that decorations and landmarks help, but cube-based placeholders are too crude for the visual bar we want.
- We should establish higher-quality geometry standards before moving on to ship exterior, interior, exploration tools, and future planets.
- Every later phase will inherit the visual precedent set here.
- Planet surfaces are the largest visible play spaces, but the same quality expectations should apply to props, landmarks, interactable objects, and eventual ship assets.

Tasks:

- Define geometry quality guidelines for the project.
- Source and review open/CC0 model candidates before importing.
- Decide which asset categories can use open placeholders and which should be custom modeled.
- Replace cube rock clusters with higher-quality low/mid-poly props.
- Replace or upgrade Planet B mineral arch geometry.
- Upgrade Planet A launch landmark silhouette.
- Improve Planet B landing pad visual geometry while preserving gameplay collision.
- Introduce a small reusable model kit for planet surfaces, landmarks, and future interactable props.
- Create wrapper scenes for imported models.
- Establish collision-authoring rules for imported/custom geometry.
- Maintain simple collision separately from render geometry.
- Keep base planet sphere for now, but add placed local terrain features around authored locations.

Recommended sources:

- CC0 low-poly rock/mineral/terrain assets where style fits.
- Poly Haven rock models only if the style does not clash with the stylized target.
- Kenney Nature Kit, Space Kit, and Modular Space Kit for CC0 placeholder models if the style fits.
- Quaternius for CC0-style low-poly packs only after verifying the specific pack license.
- Custom Blender meshes for hero landmarks and any asset that defines planet identity.

Quality target:

- Geometry should read clearly from walking distance and low-altitude ship view.
- Props should look intentionally modeled, not like scaled cubes.
- Silhouettes should help navigation.
- Collision should remain simple and authored separately.
- Assets should remain lightweight enough for fast iteration.
- Open placeholder models should be good enough to keep for several phases, not throwaway cubes.
- Hero assets should have recognizable shape language even if still low/mid-poly.

Geometry framework deliverables:

- Asset review shortlist with source links and license notes.
- Import/wrapper rules for external models.
- Collision rules for visual meshes.
- Scale and pivot conventions.
- Material override conventions.
- Decision matrix for open-source vs custom modeling.

Deliverables:

- `assets/models/props/`
- `assets/models/landmarks/`
- `assets/models/environment/`
- `scenes/props/` upgraded with higher-quality visual meshes.
- `scenes/landmarks/` upgraded with higher-quality visual meshes.
- `scenes/environment/` for reusable non-planet-specific dressing if needed.
- Updated Planet A and Planet B scenes.
- Collision for props that matter.

### Pass 4: Ship Exterior

Goal:

- Replace the box ship silhouette with a recognizable prototype spacecraft.

Tasks:

- Create a custom low/mid-poly ship exterior in Blender.
- Preserve current hatch, seat, camera, collision, and physics behavior.
- Keep collision simple and separate from render mesh.
- Add visual thrusters and landing contact points.
- Add emissive accents for readability.

Recommendation:

- Custom-model the ship exterior rather than relying on an asset pack.

Reason:

- The ship is a central emotional and functional object.
- A generic CC0 spaceship will likely not fit the interior, hatch, collision, or future identity.

Deliverables:

- `assets/models/ship/ship_exterior.glb`
- `scenes/ship/ShipVisuals.tscn` or child visual scene.
- Updated `Ship.tscn` with visual mesh and simple collision.

### Pass 5: Ship Interior Kit

Goal:

- Make the ship interior readable and useful without overbuilding it.

Tasks:

- Replace black/flat interior surfaces with panels, floor material, light strips, and cockpit frame.
- Add simple cockpit geometry around the pilot seat.
- Add hatch frame and visual door marker.
- Add a small equipment wall or scanner/tool area.
- Keep interior walkable while landed.

Recommended sources:

- Quaternius Modular Sci-Fi Megakit for optional kitbash pieces if style fits.
- ambientCG metal/panel materials.
- Custom simple modular pieces in Blender if Quaternius style clashes.

Deliverables:

- `assets/models/ship/interior_kit.glb`
- Updated `Ship.tscn` child visuals.
- Maintained Phase 1-5 validations.

### Pass 6: Signal Ruin and Exploration Props

Goal:

- Prepare visuals for Phase 6 exploration content.

Tasks:

- Create a simple visual language for alien or ancient signal objects.
- Model or kitbash the signal ruin.
- Add emissive material or animated light pulse.
- Keep interaction collision simple.

Recommendation:

- Custom model this. It is part of the game's identity.

Deliverables:

- `scenes/points_of_interest/SignalRuin.tscn`
- `assets/models/ruins/`
- `assets/materials/ruins/`

## 7. Asset Pipeline

### Folder Structure

Recommended:

```text
assets/
  external/
    polyhaven/
    ambientcg/
    kenney/
    quaternius/
    nasa/
    sketchfab/
  generated/
    textures/
    concepts/
  models/
    ship/
    props/
    planets/
    ruins/
  materials/
  textures/
  hdri/
  licenses/
```

Scene wrappers:

```text
scenes/
  props/
  landmarks/
  materials/
  ship/
  points_of_interest/
```

### Asset Ledger

Add:

```text
assets/ASSET_LEDGER.md
```

Track:

- Asset name.
- Source URL.
- Author/source.
- License.
- Download date.
- Local path.
- Modifications.
- Attribution text if required.

Even for CC0, track source and download date. It prevents confusion later.

### Import Format

Preferred:

- `.glb` for models when possible.
- `.png` or `.jpg` for texture maps.
- `.hdr` or `.exr` for HDRIs if used.

Godot workflow:

- Import source `.glb`.
- Create inherited or wrapper `.tscn` scenes.
- Apply project materials in wrapper scenes where possible.
- Keep collision authored separately unless imported collision is intentionally clean.

### Material Standards

Use Godot `StandardMaterial3D` first.

Texture maps:

- Albedo/base color.
- Normal.
- Roughness.
- Metallic where relevant.
- Emission for lights and alien/signal objects.

Avoid:

- Huge 8K textures in the repo.
- Uncompressed texture sprawl.
- Mixing many unrelated material styles.

Recommended starting resolution:

- 1K for small props.
- 2K for ship/planet-important materials.
- 4K only for large hero surfaces if visibly needed.

## 8. Open Asset Usage Policy

### Preferred Licenses

Use in this order:

1. CC0/public domain.
2. MIT/Apache-style for code-like assets if applicable.
3. CC-BY only if the asset is valuable and attribution is tracked.

Avoid for now:

- GPL/CC-BY-SA art assets.
- Non-commercial licenses.
- Editorial-only assets.
- Assets with unclear AI/provenance terms.
- Assets requiring account-specific marketplace restrictions.

### Source-Specific Policy

Kenney:

- Good for prototypes and clean low-poly pieces.
- Use if style fits.
- Track source even though attribution is not required.

Poly Haven:

- Use for HDRIs, PBR materials, and some high-quality models.
- Good default for physically grounded materials.

ambientCG:

- Use for PBR material sets.
- Strong default for metal, rock, ground, panels, and generic surfaces.

Quaternius:

- Use selectively for sci-fi modular pieces or props.
- Confirm style fit before importing many pieces.

NASA:

- Use for reference and possibly space/planet textures.
- Avoid logos, insignia, mission branding, and endorsement implications.
- Track NASA source and usage guideline link.

Sketchfab:

- Use cautiously.
- Prefer CC0.
- If CC-BY, add attribution to asset ledger immediately.

OpenGameArt:

- Use cautiously.
- Check actual downloadable asset license, not just preview media.

## 9. Generate vs Source Decision Matrix

Use open assets when:

- The asset is generic.
- It will not define the game's identity.
- License is CC0.
- Style matches existing target.
- It saves substantial time.

Generate textures/concepts when:

- We need a unique surface motif.
- We need quick visual exploration.
- The result can be edited or used as a basis, not blindly imported.

Custom model when:

- The asset affects gameplay collision or interaction.
- The asset is a hero object.
- The shape must match our ship/interior layout.
- The asset will recur across the game.
- A generic asset would make the game feel derivative.

For this project:

- Ship exterior: custom.
- Ship interior shell: custom with optional kitbash props.
- Cockpit controls: custom/simple kitbash.
- Planet PBR materials: open assets plus generated masks.
- Rocks and small clutter: open assets.
- Landing pads: custom/simple modular.
- Signal ruin: custom.
- Starfield/HDRI: open or generated.

## 10. Implementation Plan

### Step 1: Create Asset Structure

- Add `assets/` subfolders.
- Add `assets/ASSET_LEDGER.md`.
- Add a short import naming convention.

### Step 2: Lighting and Material Baseline

- Improve world environment.
- Add or refine space sky.
- Add first texture-based materials.
- Apply materials to planets and ship placeholder geometry.

### Step 3: Planet Surface Dressing

- Add rock/prop scenes.
- Place small clusters on Planet A and Planet B.
- Add landmark silhouettes visible from ship distance.

### Step 4: Ship Visual Replacement

- Build or import custom ship exterior mesh.
- Keep current RigidBody/collision as gameplay shell.
- Add visual mesh as child.
- Preserve third-person camera framing.
- Verify hatch/interior positions still make sense.

### Step 5: Interior Upgrade

- Add panel materials, light strips, cockpit frame, and floor detail.
- Keep navigation clear.
- Avoid adding complex walkable collision inside moving ship.

### Step 6: Visual Validation

- Run automated validation after each structural change.
- Manual check from:
  - on-foot Planet A
  - inside ship
  - third-person flight
  - Planet B landing
  - Planet B on-foot exploration

## 11. Success Criteria

This visual fidelity pass is successful when:

- The game no longer reads as pure primitives.
- Planet A and Planet B are visually distinct.
- The ship has a recognizable silhouette.
- The ship interior is readable and not black/flat.
- Landmarks are visible enough to aid navigation.
- Materials react plausibly to lighting.
- All existing Phase 1-5 validation still passes.
- Assets have documented sources and licenses.
- The pipeline is repeatable for future phases.

## 12. Recommended First Sprint

Start with a constrained one-week-equivalent pass:

1. Add asset folders and ledger.
2. Add two CC0 PBR material sets:
   - rocky ground
   - worn metal/panel
3. Add one HDRI or improved procedural star/space environment.
4. Add simple rock prop scene.
5. Add Planet B surface prop clusters.
6. Add ship hull material and emissive thruster accents.
7. Add basic interior panel/floor materials and lights.
8. Run validation and manual visual review.

Do not start with a full ship remodel. First prove the asset pipeline and material direction on the existing geometry, then replace geometry in a controlled pass.

## 13. Final Recommendation

We should not try to find one open-source asset pack that solves the whole game's look. The better approach is:

- Use CC0 libraries aggressively for materials, HDRIs, rocks, and generic props.
- Custom-build the ship, signal ruin, and key landmarks.
- Use generated assets for texture ideation and unique surface motifs.
- Keep every imported/generated asset documented from day one.

This gives us a visible fidelity jump quickly while protecting the game's long-term visual identity.
