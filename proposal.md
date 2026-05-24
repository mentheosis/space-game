# Small Solar System Exploration Game Proposal

## 1. Intent

Build a first-person 3D exploration game in Godot where the player can walk on small planets, enter a spaceship, take off, fly through a compact solar system, land on other planets, and uncover mysteries through observation and experimentation.

The closest comparison is *Outer Wilds*, but this project should not copy its story, planets, time loop, or exact toolset. The useful lessons are structural: a dense miniature solar system, strong movement verbs, authored planetary rules, and knowledge-driven progression.

## 2. Research Summary

Outer Wilds sources reviewed:

- Mobius Digital official *Outer Wilds* page: https://www.mobiusdigitalgames.com/outer-wilds.html
- MobyGames overview: https://www.mobygames.com/game/127776/outer-wilds/
- Tom's Guide review: https://www.tomsguide.com/reviews/outer-wilds
- Nintendo Life review: https://www.nintendolife.com/reviews/switch-eshop/outer-wilds

Godot sources reviewed:

- Godot 4.6 documentation: https://docs.godotengine.org/
- Godot 4.6 feature list: https://docs.godotengine.org/en/4.6/about/list_of_features.html
- Godot `CharacterBody3D` documentation: https://docs.godotengine.org/en/latest/classes/class_characterbody3d.html
- Godot license page: https://godotengine.org/license/

Key observations from *Outer Wilds*:

- The world is small but dense. The player can reach interesting places quickly.
- Ship travel, walking, zero-g movement, landing, and environmental inspection are the core game, not secondary features.
- Progression is mostly knowledge-based. Players advance because they understand locations, clues, timing, hazards, and physical rules.
- Planets are memorable because each one has a clear identity and central behavior.
- The ship functions as transport, home base, navigation tool, and emotional anchor.

Key observations for Godot:

- Godot is free and open source under the MIT license.
- Godot 4.6 provides the core 3D building blocks we need: `Node3D`, `CharacterBody3D`, `RigidBody3D`, `StaticBody3D`, `Area3D`, 3D physics, CSG prototyping, glTF import/export, shaders, animation, audio, UI, and scripting.
- Godot is a good fit if we keep the visual target controlled and build focused custom systems for planetary gravity, floating origin, ship control, and world streaming.
- Godot is less turnkey than Unreal or Unity for ambitious 3D production, so the project should aggressively prototype technical risks before expanding content.

## 3. Engine Decision

Use **Godot 4.6** as the base engine.

Primary reasons:

- Open-source MIT license removes engine pricing and vendor-control risk.
- Lightweight editor and fast iteration fit an experimental exploration game.
- C# gives the project stronger type safety and refactoring support for gravity, movement, ship control, save data, and other long-lived systems.
- GDScript can still be useful for small editor glue, throwaway experiments, or very simple scene scripts.
- Godot's scene/node architecture maps well to ships, planets, tools, interactables, signals, and location chunks.

Tradeoffs:

- We must own more of the advanced 3D tech ourselves.
- Planetary gravity, local reference frames, floating origin, and ship-to-player transitions need custom engineering.
- Visual and asset-pipeline scope must stay disciplined.
- We should expect to build project-specific tools instead of relying on a huge marketplace.

Initial language choice:

- Use **C#** as the primary project language for gameplay, tools, UI models, game state, interactions, and technical systems.
- Use **GDScript** only for small editor helpers, temporary prototypes, or simple scene glue where C# adds unnecessary ceremony.
- Use **GDExtension** only for proven performance bottlenecks or low-level engine integration.

Rationale:

- The core mechanics involve custom gravity, curved-surface movement, ship physics, coordinate handling, and state transitions. These systems benefit from static typing, explicit interfaces, compiler errors, and stronger refactoring tools.
- Godot examples and quick scripts are often GDScript-first, but this project should optimize for maintainability of complex systems rather than the lowest-friction scripting path.
- Avoid casual language mixing. The codebase should be C# first, with GDScript used only when it is clearly simpler and isolated.

## 4. Game Pillars

### Seamless Embodied Travel

The player should experience one continuous physical adventure:

- Walk on curved planet surfaces.
- Enter the ship through a door or hatch.
- Move inside the ship while grounded or landed.
- Sit at the controls.
- Take off manually.
- Fly through local space.
- Approach and land on another body.
- Exit and continue exploring on foot.

### Compact Handcrafted Solar System

The first full version should use a small number of high-quality destinations:

- 3 to 5 major planets.
- 1 to 3 moons, stations, comets, or anomalies.
- Short travel times between destinations.
- Strong silhouettes visible from space.
- Each body has one primary environmental rule.

Example planet rules:

- Ice crust above liquid tunnels.
- Storm bands that periodically expose landing windows.
- Tidally locked desert with dangerous day/night extremes.
- Hollow asteroid with inverted interior gravity.
- Garden world where vegetation opens and closes routes.

## 5. Godot Technical Architecture

### Project Structure

Proposed folder layout:

```text
res://
  autoload/
    GameState.gd
    GravityService.gd
    SignalRegistry.gd
  scenes/
    player/
    ship/
    planets/
    tools/
    ui/
    solar_system/
  scripts/
    components/
    resources/
    debug/
  assets/
    models/
    materials/
    audio/
    textures/
  addons/
```

Use Godot scenes as reusable gameplay units:

- `Player.tscn`
- `Ship.tscn`
- `PlanetBody.tscn`
- `LandingZone.tscn`
- `GravityField.tscn`
- `SignalSource.tscn`
- `Interactable.tscn`
- `ShipLog.tscn`

### Gravity Model

Godot's default global gravity is not enough for a solar system with spherical planets. We should implement custom gravity.

Core approach:

- Disable or ignore global gravity for the player and ship.
- Create `GravityBody` nodes for planets, moons, and anomalies.
- Register gravity bodies with an autoloaded `GravityService`.
- Each body exposes radius, surface gravity, falloff, priority, and optional influence range.
- Player and ship query the dominant gravity vector every physics frame.

Godot nodes:

- `Area3D` can define influence zones.
- `CharacterBody3D` can drive player movement.
- `RigidBody3D` can drive ship physics.
- `Node3D` transforms provide the planet-centered coordinate logic.

### Player Controller

Use `CharacterBody3D` for the first player implementation.

Responsibilities:

- First-person camera.
- Custom gravity alignment.
- Surface walking on curved planets.
- Jumping.
- Short jetpack thrust.
- Zero-g drift when gravity is weak.
- Interaction raycast.
- Suit resource feedback.

Important implementation detail:

- The character's local up direction should be derived from the active gravity vector.
- Movement input should be projected onto the tangent plane of the current gravity source.
- Camera roll should be controlled carefully to avoid disorientation.

### Ship Controller

Use `RigidBody3D` for ship flight once the basic controls are known. A temporary scripted `Node3D` ship is acceptable during very early prototyping, but the vertical slice should use physics.

Responsibilities:

- Main thrust.
- Reverse thrust.
- Strafe thrusters.
- Pitch, yaw, and roll.
- Landing mode.
- Match velocity assist.
- Gravity influence.
- Seat enter/exit.
- Ship interior reference frame.

Ship/player transition:

- When the player enters the ship, keep the player scene active but parent or constrain it to the ship interior while not piloting.
- When seated, route input to the ship controller.
- When exiting, place the player at the hatch transform and restore normal movement.

### Planet Representation

Start simple:

- Use sphere meshes for planet bodies.
- Add authored surface props, rocks, ruins, caves, paths, and landing pads.
- Use separate scenes for major locations.
- Use Godot's CSG only for blockout, then replace important spaces with proper meshes.

Avoid at the start:

- Procedural planet generation.
- Realistic n-body orbital mechanics.
- Fully destructible terrain.
- Large terrain streaming systems.

Later options:

- Cube-sphere terrain.
- Authored heightfield chunks.
- Scene streaming around the player.
- Origin shifting for larger distances.

### Floating Origin and Scale

Problem:

- Space travel can create floating-point precision issues.

Initial mitigation:

- Keep the solar system compact.
- Use stylized distances and speeds.
- Keep bodies much closer than real astronomical scale.

Later mitigation:

- Implement a floating origin manager that recenters the active world around the player or ship.
- Store solar-system positions in a higher-level coordinate model.
- Move scene roots rather than individual content nodes where possible.

### World Simulation

Use simplified authored motion:

- Planets can be stationary for the first prototype.
- Later, planets can move on `Path3D` or custom circular/orbital paths.
- Avoid n-body simulation unless it becomes a deliberate design feature.

### Tools and Knowledge

Early player tools:

- Signal scanner.
- Translator or glyph reader.
- Probe/camera.
- Ship log.

Data model:

- Use Godot `Resource` files for clue definitions, signal definitions, planet metadata, and ship-log entries.
- Use `GameState` autoload to track discoveries.
- Save knowledge state, not every temporary physics detail.

## 6. Project Phases

### Phase 0: Godot Project Foundation

Goal:

- Create the Godot project and establish the working structure.

Deliverables:

- Godot 4.6 project committed to the repo.
- Folder structure.
- Input map for movement, looking, jump, jetpack, interact, pilot controls, scanner, and pause.
- Basic debug overlay.
- Placeholder main scene.
- Initial `GameState` autoload.

Success criteria:

- Project opens cleanly in Godot.
- A blank playable scene runs from the editor.
- Input actions are named and stable.

### Phase 1: Spherical Gravity Walking Prototype

Goal:

- Prove that the player can walk on a small spherical planet.

Deliverables:

- `PlanetBody.tscn`.
- `GravityService.cs`.
- `GravityBody.cs`.
- `Player.tscn` using `CharacterBody3D`.
- Gravity-aligned first-person movement.
- Jumping and falling.
- One test landmark.

Success criteria:

- Player can walk around the planet in every direction.
- The camera remains readable at poles and steep transitions.
- Jumping and landing work consistently.

### Phase 2: Jetpack and Weak-Gravity Movement

Goal:

- Make movement interesting beyond basic walking.

Deliverables:

- Short-burst jetpack.
- Fuel or heat limiter.
- Weak-gravity/zero-g movement mode.
- Suit HUD placeholder.
- Basic oxygen timer placeholder.

Success criteria:

- Player can leave the ground briefly, recover, and navigate uneven surface layouts.
- Weak gravity feels distinct from surface walking.

### Phase 3: Ship Interior and Interaction

Goal:

- Build the player's relationship with the ship before full space flight.

Deliverables:

- Placeholder `Ship.tscn`.
- Walkable ship interior.
- Hatch interaction.
- Pilot seat interaction.
- Basic cockpit UI.
- Exit points and spawn transforms.

Success criteria:

- Player can enter the ship, walk or look inside, sit down, stand up, and exit.
- State transitions do not break camera, collision, or input.

### Phase 4: Ship Takeoff and Local Flight

Goal:

- Prove takeoff, flight, and landing around one planet.

Deliverables:

- `RigidBody3D` ship controller.
- Thruster controls.
- Rotation controls.
- Gravity influence on ship.
- Landing legs or landing collision.
- Landing assist/debug indicators.

Success criteria:

- Player can take off from the first planet, fly around it, land, and exit the ship.
- The ship feels controllable without heavy assists.

### Phase 5: Two-Planet Travel

Goal:

- Prove the core fantasy of traveling between worlds.

Deliverables:

- Second planet.
- Solar-system scene root.
- Navigation markers.
- Ship velocity/match-speed assist.
- Tuned travel scale.
- Basic space sky and sun.

Success criteria:

- Player can launch from Planet A, fly to Planet B, land, exit, and explore.
- Travel time feels intentional rather than tedious.

### Phase 6: First Exploration Tool

Goal:

- Add a reason to explore.

Deliverables:

- Signal scanner or probe tool.
- `SignalSource.tscn`.
- Audio/visual signal feedback.
- First hidden point of interest.
- First clue resource.

Success criteria:

- Player can detect, locate, and inspect something they could easily miss without the tool.

### Phase 7: First Mystery Chain

Goal:

- Connect multiple places through knowledge.

Deliverables:

- Two or three clues across two bodies.
- Ship log UI.
- Discovery tracking.
- Save/load for discovered knowledge.
- One simple environmental gate based on learned information.

Success criteria:

- A player can find a clue on one planet that helps them understand or access a place on another.

### Phase 8: Vertical Slice

Goal:

- Deliver a 30 to 60 minute representative experience.

Deliverables:

- 2 planets and 1 moon, station, or anomaly.
- One complete mystery arc.
- Stable walking, jetpack, ship entry, flight, landing, and exit.
- Basic art direction pass.
- Audio pass for suit, ship, scanner, planets, and discoveries.
- Save/load for knowledge state.
- Main menu and pause menu.
- Exported desktop build.

Success criteria:

- A new player can start the game, learn the controls, explore, travel between bodies, solve one mystery, and understand the promise of the full game.

### Phase 9: Production Expansion

Goal:

- Expand from vertical slice to full game.

Deliverables:

- Additional planets and moons.
- More environmental rules.
- More clue chains.
- Improved ship log graph.
- Better ship interior.
- Finalized toolset.
- Performance pass.
- Accessibility and input remapping.
- Save migration strategy.

Success criteria:

- New content can be added using stable patterns without rewriting core movement or ship systems.

## 7. First Prototype Scope

The first real prototype should be deliberately narrow:

> Walk around a small spherical planet, enter a ship, take off, fly to a second small planet, land, exit, and discover one signal-based clue.

This is the smallest version that proves the game.

Do not start with:

- Procedural planets.
- Full story.
- Polished art.
- Ship damage.
- Inventory.
- Combat.
- Realistic orbital mechanics.
- Many planets.

## 8. Major Risks

### Custom Gravity

Risk:

- Godot's standard movement examples assume a conventional up/down axis.

Mitigation:

- Build spherical gravity first.
- Keep test planets small.
- Add automated debug visualization for gravity vectors and active gravity body.

### Ship Physics

Risk:

- Physics-based flight can become unstable or frustrating.

Mitigation:

- Start with simple controls.
- Add assists only after manual flight is understandable.
- Tune scale and speed around fun rather than realism.

### Precision and Scale

Risk:

- Larger space distances can expose jitter and precision problems.

Mitigation:

- Keep early solar system compact.
- Add floating origin only when the prototype demonstrates a real need.

### Content Tooling

Risk:

- Godot will not automatically provide all the custom tools a dense exploration game needs.

Mitigation:

- Use scene composition and `Resource` files for reusable content.
- Build small editor/debug helpers only when repeated content work becomes painful.

### Scope

Risk:

- A space exploration game can grow without limit.

Mitigation:

- One planet, one ship, one tool, one clue chain first.
- Add new celestial bodies only after the existing loop is fun.

## 9. Immediate Next Decisions

Before implementation, decide:

1. Player viewpoint: first-person only, or first-person with optional third-person ship camera.
2. Visual target: stylized realism, low-poly, retro sci-fi, or painterly.
3. First planet rule: ice, storm, desert, hollow asteroid, vegetation, or another concept.
4. First tool: signal scanner, probe, translator, camera, or repair tool.
5. Failure loop: quick respawn, expedition reset, rescue tow, or time-loop structure.

## 10. Recommended Next Step

Create the Godot 4.6 project and implement Phase 0 and Phase 1:

- Project structure.
- Input actions.
- `GravityService`.
- One `PlanetBody`.
- One `CharacterBody3D` player.
- Gravity-aligned walking around a sphere.

Once that feels good, the project has a real foundation. If that does not feel good, adding planets, story, or ship systems will not fix the game.

Initial platform scope:

- Target Linux and macOS first.
- Defer Windows, console, mobile, and Web export decisions.
- Skip Docker build automation for now. Revisit it after the Godot project exists and we have repeatable Linux/macOS export commands worth automating.
