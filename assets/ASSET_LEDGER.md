# Asset Ledger

This ledger tracks external, generated, and project-authored assets used by the game.

## External Assets

| Asset | Local Path | Source | Author | License | Download/Created Date | Modifications | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Kenney Space Kit craft cargo A | `assets/models/ship/placeholders/kenney_craft_cargo_a.glb` | https://kenney.nl/assets/space-kit | Kenney | Creative Commons CC0 | 2026-05-24 | Extracted one GLB from source pack, wrapped in `scenes/ship/PlaceholderShipVisual.tscn`, scaled/rotated for current ship shell. | Imported for evaluation but hidden in `Ship.tscn`; current visible ship uses the project-authored hull because this placeholder did not integrate cleanly. |
| OpenGameArt 3D Space Ship Pack ShuttleA | `assets/models/ship/placeholders/oga_3d_space_ship_pack/ShuttleA.obj` | https://opengameart.org/content/3d-space-ship-pack | anaxarch | Creative Commons CC0 | 2026-05-24 | Extracted `ShuttleA.obj` and `.mtl`, wrapped in `scenes/ship/OpenGameArtShuttleVisual.tscn`, scaled to the current ship shell. | Active visual-only placeholder; collision remains project-authored. |
| ambientCG Gravel043 1K JPG maps | `assets/textures/planets/gravel043/` | https://ambientCG.com/get?file=Gravel043_1K-JPG.zip | ambientCG | Creative Commons CC0 | 2026-05-24 | Extracted color, normal GL, roughness, and ambient occlusion maps; applied through project-authored planet materials. | Used for Planet A and Planet B surface variation. |
| ambientCG SheetMetal001 1K JPG maps | `assets/textures/ship/sheetmetal001/` | https://ambientCG.com/get?file=SheetMetal001_1K-JPG.zip | ambientCG | Creative Commons CC0 | 2026-05-24 | Extracted color, normal GL, roughness, and metalness maps; applied through project-authored ship materials. | Used for ship hull, floor, and wall variation. |

## Generated Assets

| Asset | Local Path | Source | Author | License | Download/Created Date | Modifications | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Generated starfield texture | `assets/textures/environment/starfield_generated.png` | Project-generated procedural script | Project | Project asset | 2026-05-24 | Generated 2048x1024 PNG starfield using deterministic random seed. | Used by `assets/materials/environment/mat_starfield.tres`. |

## Project-Authored Assets

| Asset | Local Path | Source | Author | License | Download/Created Date | Modifications | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Planet A surface material | `assets/materials/planets/mat_planet_a_surface.tres` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Reusable baseline material. |
| Planet A landmark material | `assets/materials/planets/mat_planet_a_landmark.tres` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Replaces inline landmark material. |
| Planet B surface material | `assets/materials/planets/mat_planet_b_surface.tres` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Reusable baseline material. |
| Planet B landing pad material | `assets/materials/planets/mat_planet_b_landing_pad.tres` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Replaces inline landing pad material. |
| Planet B beacon material | `assets/materials/planets/mat_planet_b_beacon.tres` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Emissive beacon material. |
| Ship hull material | `assets/materials/ship/mat_ship_hull.tres` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Replaces inline hull material. |
| Ship floor material | `assets/materials/ship/mat_ship_floor.tres` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Replaces inline floor material. |
| Ship wall material | `assets/materials/ship/mat_ship_wall.tres` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Replaces inline wall material. |
| Ship hatch material | `assets/materials/ship/mat_ship_hatch.tres` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Replaces inline hatch material. |
| Ship seat material | `assets/materials/ship/mat_ship_seat.tres` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Replaces inline seat material. |
| Ship accent emissive material | `assets/materials/ship/mat_ship_accent_emissive.tres` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Used for interior light strips and thruster accents. |
| Planet A gravel material | `assets/materials/planets/mat_planet_a_gravel_surface.tres` | Project-authored using ambientCG Gravel043 maps | Project | Project asset | 2026-05-24 | Tinted and scaled imported CC0 maps. | Current Planet A surface material. |
| Planet B gravel material | `assets/materials/planets/mat_planet_b_gravel_surface.tres` | Project-authored using ambientCG Gravel043 maps | Project | Project asset | 2026-05-24 | Tinted and scaled imported CC0 maps. | Current Planet B surface material. |
| Ship hull sheet metal material | `assets/materials/ship/mat_ship_hull_sheetmetal.tres` | Project-authored using ambientCG SheetMetal001 maps | Project | Project asset | 2026-05-24 | Tinted and scaled imported CC0 maps. | Current ship hull material. |
| Ship floor sheet metal material | `assets/materials/ship/mat_ship_floor_sheetmetal.tres` | Project-authored using ambientCG SheetMetal001 maps | Project | Project asset | 2026-05-24 | Tinted and scaled imported CC0 maps. | Current ship floor material. |
| Ship wall sheet metal material | `assets/materials/ship/mat_ship_wall_sheetmetal.tres` | Project-authored using ambientCG SheetMetal001 maps | Project | Project asset | 2026-05-24 | Tinted and scaled imported CC0 maps. | Current ship wall material. |
| Starfield sky material | `assets/materials/environment/mat_starfield.tres` | Project-authored using generated starfield texture | Project | Project asset | 2026-05-24 | N/A | Current Phase 5 sky material. |
| Planet A rock material | `assets/materials/props/mat_rock_a.tres` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Used by Planet A rock clusters. |
| Planet B rock material | `assets/materials/props/mat_rock_b.tres` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Used by Planet B rock/mineral clusters. |
| Surface marker material | `assets/materials/props/mat_surface_marker.tres` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Used for landing pad visual markers and surface markers. |
| Planet A landmark material | `assets/materials/landmarks/mat_landmark_a.tres` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Used by launch landmark geometry. |
| Planet B mineral material | `assets/materials/landmarks/mat_mineral_b.tres` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Used by Planet B mineral arch. |
| Planet A rock cluster | `scenes/props/RockClusterA.tscn` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Primitive mesh prop scene. |
| Planet B rock cluster | `scenes/props/RockClusterB.tscn` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Primitive mesh prop scene. |
| Surface marker prop | `scenes/props/SurfaceMarker.tscn` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Primitive mesh marker scene. |
| Planet A launch landmark | `scenes/landmarks/PlanetALaunchLandmark.tscn` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Primitive mesh landmark scene. |
| Planet B mineral arch | `scenes/landmarks/PlanetBMineralArch.tscn` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Primitive mesh landmark scene. |
| Planet B landing pad visual | `scenes/landmarks/PlanetBLandingPadVisual.tscn` | Project-authored | Project | Project asset | 2026-05-24 | N/A | Visual-only landing pad marker scene. |
| Low-poly Planet A rock mesh | `assets/models/props/rock_lowpoly_a.obj` | Project-generated procedural mesh | Project | Project asset | 2026-05-24 | Generated as lightweight irregular OBJ mesh. | Replaces cube visuals in `RockClusterA.tscn`. |
| Low-poly Planet B rock mesh | `assets/models/props/rock_lowpoly_b.obj` | Project-generated procedural mesh | Project | Project asset | 2026-05-24 | Generated as taller irregular OBJ mesh. | Replaces cube visuals in `RockClusterB.tscn`. |
| Mineral shard mesh | `assets/models/props/mineral_shard.obj` | Project-generated procedural mesh | Project | Project asset | 2026-05-24 | Generated as faceted crystal/shard OBJ mesh. | Used by `PlanetBMineralArch.tscn`. |
| Planet A launch beacon mesh | `assets/models/landmarks/launch_beacon.obj` | Project-generated procedural mesh | Project | Project asset | 2026-05-24 | Generated as tapered pylon with fins. | Used by `PlanetALaunchLandmark.tscn`. |

## Naming Convention

- Materials use `mat_<domain>_<description>.tres`.
- Textures use `<source_asset>_<map>.jpg` or `tex_<domain>_<description>_<map>.png`.
- Placeholder model files keep source and role in the name, such as `kenney_craft_cargo_a.glb`.
- Source folders are grouped by provider under `assets/external/` when full source packs are retained, or normalized under `assets/textures/` and `assets/models/` when only curated project-ready files are committed.
