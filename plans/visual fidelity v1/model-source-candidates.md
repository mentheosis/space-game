# Open Model Candidate Review

## 1. Review Goal

Before importing more geometry, compare open/CC0 model sources for:

- ship exterior candidates
- rocks/minerals/surface props
- sci-fi props and landing-area dressing
- hero landmark starting points

The goal is not to pick final art immediately. The goal is to identify assets worth testing in Godot and decide where custom modeling is a better use of time.

## 2. Evaluation Criteria

Use these criteria for every candidate:

- License is CC0/public domain or otherwise acceptable.
- Download does not require awkward account flow if avoidable.
- Format is Godot-friendly: `.glb`, `.gltf`, `.fbx`, `.obj`, or `.blend`.
- Mesh has a clear silhouette.
- Mesh is not too low-detail for the current quality target.
- Mesh is not too high-poly for prototype use.
- Style can work with stylized-real PBR materials.
- Pivot/orientation can be fixed without major work.
- Collision can be authored separately.
- Asset can be wrapped in a project scene.

## 3. Ship Exterior Candidates

### Candidate A: OpenGameArt - 3d spaceship

Source:

- https://opengameart.org/content/3d-spaceship

License:

- CC0 according to the asset page.

Format:

- `.blend`

Pros:

- More substantial than Kenney Space Kit craft.
- License appears clean.
- Small enough to inspect and convert.

Risks:

- Requires Blender conversion to `.glb`.
- Unknown material quality until inspected.
- May still need scale, pivot, material, and topology cleanup.

Recommended use:

- Worth reviewing as a ship placeholder candidate.

### Candidate B: Blend Swap - SPACESHIP

Source:

- https://www.blendswap.com/blend/24525

License:

- Listed as CC-0 on the page.

Format:

- Blender file.

Pros:

- Stronger silhouette than Kenney.
- Around 5,446 faces according to the page, which is plausible for prototype use.
- More credible large-ship shape.

Risks:

- Blend Swap may require login to download.
- Inspired by existing sci-fi franchises, so we should avoid adopting it as final identity.
- Needs conversion and material cleanup.

Recommended use:

- Good comparison candidate, but probably not final.

### Candidate C: Blend Swap - Rugged Spaceship

Source:

- https://blendswap.com/blend/6475

License:

- Listed as CC-0 on the page.

Format:

- Blender file.

Pros:

- More detailed/rugged visual language.
- Could be useful as reference for ship structure and kitbash ideas.

Risks:

- Higher vertex count.
- Older Blender/internal-render setup.
- May require cleanup.
- May be too busy for current prototype.

Recommended use:

- Review visually, but do not prioritize for immediate import unless it looks compelling.

### Candidate D: OpenGameArt - Stylized Spaceship

Source:

- https://opengameart.org/content/stylized-spaceship-untextured-unwrapped-w-materials

License:

- Page is listed under CC0 vehicle collections.

Format:

- Likely Blender/source asset; verify before use.

Pros:

- Stylized, potentially closer to our non-photoreal target.
- Unwrapped/material-ready could be useful if the mesh is solid.

Risks:

- Needs inspection for actual license and files.
- Untextured means we must do material work.

Recommended use:

- Strong review candidate if the silhouette fits.

### Candidate E: OpenGameArt - 3D Space Ship Pack

Source:

- https://opengameart.org/content/3d-space-ship-pack

License:

- Listed as CC0 on the search result/page summary.

Format:

- Verify file formats before use.

Pros:

- Multiple ships to compare.
- Good for variety and silhouette exploration.

Risks:

- May skew toward arcade/fighter ships rather than explorable lander.
- Needs per-file inspection.

Recommended use:

- Useful for silhouette comparison, less likely to be final.

### Candidate F: Quaternius Spaceship via third-party mirrors

Source example:

- https://www.get3dmodels.com/space-sci-fi/spaceship-2/

License:

- Listed as public domain on the mirror.

Format:

- `.glb`

Pros:

- Godot-friendly format.
- Lightweight.
- Larger than the Kenney craft we tried.

Risks:

- This is a third-party mirror, not the preferred original source.
- Need to find/verify the original Quaternius source before using if possible.
- Still low-poly/stylized.

Recommended use:

- Only use if we can verify source and license cleanly.

## 4. Non-Ship Geometry Candidates

### Candidate G: Poly Haven Rocks

Source:

- https://polyhaven.com/models/rocks

License:

- Poly Haven assets are CC0.

Formats:

- Often includes Blender/glTF/FBX variants depending on asset.

Pros:

- Much higher visual quality than cube props.
- Good for rocks/mineral references.
- Clean CC0 license.

Risks:

- May be too realistic next to the stylized planets/ship.
- May need decimation or simplification.
- Polycount and texture size need review.

Recommended use:

- Use selectively for one or two hero rocks, or as modeling reference.

### Candidate H: Kenney Nature Kit

Source:

- https://kenney.nl/assets/nature-kit

License:

- CC0.

Formats:

- Kenney packs usually include game-ready formats.

Pros:

- Clean source.
- Consistent style.
- Easy to import.

Risks:

- May be too simple for the new quality target.

Recommended use:

- Good fallback for quick placeholder rocks, but not the final quality target.

### Candidate I: CG3D Public Domain Models

Source:

- https://cg3d.org/

License:

- Site describes itself as public domain/CC0 model library.

Formats:

- Lists `.blend`, `.obj`, `.fbx`, `.dae`, `.stl`, `.glb`, `.gltf`, and others.

Pros:

- Potentially broad variety.
- Public domain/CC0 focus.

Risks:

- Asset-by-asset quality likely varies.
- Need per-model review and source tracking.

Recommended use:

- Search for sci-fi props, rocks, and structural forms if Kenney/Poly Haven are insufficient.

## 5. Custom Modeling Candidates

Use custom modeling instead of sourced models for:

- final ship exterior
- ship hatch/door frame
- cockpit frame
- Planet B mineral arch if sourced assets do not match
- Planet A launch landmark
- signal ruin
- any recurring alien/ancient visual language

Why:

- These assets define the game identity.
- Open assets are good for placeholders, but hero geometry should not feel generic.
- Gameplay collision, hatch alignment, and ship camera framing need custom shapes.

## 6. Recommended Next Review Set

Review these first:

1. OpenGameArt `3d spaceship`
2. Blend Swap `SPACESHIP`
3. OpenGameArt `Stylized Spaceship`
4. OpenGameArt `3D Space Ship Pack`
5. Poly Haven rocks
6. CG3D public-domain sci-fi/rock candidates

Do not import all of them into the game immediately.

Recommended process:

1. Download candidates into `/tmp` first.
2. Inspect license and file contents.
3. Convert to `.glb` if needed.
4. Create isolated preview scenes.
5. Compare silhouette, scale, material readiness, and cleanup effort.
6. Pick one temporary ship visual and one surface-prop source.
7. Only then commit curated assets and update `assets/ASSET_LEDGER.md`.

## 7. Recommendation

For the ship:

- Do not keep searching only Kenney-scale models.
- Compare OpenGameArt and Blend Swap CC0 ships.
- Expect to custom model the final ship.
- Use a sourced model only as a temporary silhouette/reference if it integrates cleanly.

For surface geometry:

- Use Poly Haven or CG3D selectively for higher-quality rocks.
- Continue custom/project-authored landmarks.

