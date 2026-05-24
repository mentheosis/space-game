# Phase 6 Implementation Plan: First Exploration Tool

## 1. Phase Goal

Add the first exploration tool: a signal scanner that lets the player detect and locate something they could easily miss by sight alone.

This phase should turn the two-planet travel prototype into the first real exploration loop:

1. Launch from Planet A.
2. Travel to Planet B.
3. Land and exit.
4. Use the scanner to detect a hidden signal.
5. Follow signal feedback to a point of interest.
6. Inspect it and record the first clue.

Phase 6 is not about a full mystery chain, ship log, save/load, or multiple tools. Those belong to Phase 7 and later.

## 2. Current Project Reality

Phase 5 established:

- Main scene is `res://scenes/solar_system/Phase5TestWorld.tscn`.
- The playable world contains Planet A and Planet B.
- Planet B is a distinct travel destination with a landing pad and beacon.
- `GravityBody` supports optional gravity falloff.
- There is an intentional true zero-g gap between planet influence spheres.
- The ship can launch from Planet A, travel toward Planet B, enter Planet B gravity, land, and exit.
- `ShipHud` shows target, distance, closing speed, active gravity source, and gravity magnitude.
- `NavigationTarget.cs` exists for named travel targets.
- Seated controls are stable:
  - `F`: interact.
  - `W/S/A/D`: ship-local translation.
  - `Space`: ascend.
  - `Left Shift`: descend.
  - `Control`: dampen ship velocity.
  - Arrow keys: pitch/yaw.
  - `Q/E`: roll.
- `scripts/validate.sh` runs Phase 1 through Phase 5 validation.
- Demo window is currently `2400x1350`.

Important constraints:

- Do not break existing movement, ship, hatch, and validation flows.
- Keep interaction on `F`.
- Keep tool controls out of the ship piloting controls unless deliberately supported.
- Avoid a full knowledge database until Phase 7.

## 3. Proposal Updates Needed

The proposal's Phase 6 direction is still correct:

- Signal scanner or probe tool.
- `SignalSource.tscn`.
- Audio/visual signal feedback.
- First hidden point of interest.
- First clue resource.

Implementation interpretation:

- Choose **signal scanner** for Phase 6.
- Defer probe/camera tool.
- Defer full ship log UI.
- The first clue can be a lightweight `Resource` and runtime discovery event, not a full persistent save system.
- The signal source should live on Planet B so the tool builds directly on the new interplanetary loop.

## 4. Scope

### In Scope

- Add scanner input action.
- Add signal source data/component.
- Add signal service or query system.
- Add signal scanner component on the player.
- Add scanner HUD.
- Add one hidden signal source on Planet B.
- Add one inspectable point of interest tied to the signal.
- Add one clue resource.
- Add Phase 6 test world.
- Add Phase 6 automated validation.
- Update `scripts/validate.sh`.
- Update `SETUP.md`.

### Out of Scope

- Full ship log.
- Save/load of discoveries.
- Multiple signal frequencies if one frequency is enough for validation.
- Probe launcher.
- Translator.
- Inventory.
- Narrative writing beyond placeholder clue text.
- Audio polish.
- Complex line-of-sight occlusion.
- Signal triangulation.
- Signal source movement.
- Scanner use while piloting, unless it is trivial after the on-foot scanner works.

## 5. Design Decisions

### Tool Choice

Use a handheld signal scanner.

Why:

- It gives the player an active reason to explore after landing.
- It can be implemented with current systems: player camera, input, UI, and world nodes.
- It introduces knowledge progression without requiring a full story chain.
- It scales naturally into future phases with multiple frequencies, ship log entries, and hidden locations.

### Scanner Control

Add a new input action:

```text
scan
```

Recommended binding:

```text
R
```

Behavior:

- Hold `R` to use the scanner.
- Release `R` to hide scanner feedback.
- Scanner works while the player is on foot or inside the landed ship interior.
- Scanner does not operate while seated/piloting in Phase 6.

Reasoning:

- `F` is interact.
- `Q/E` are ship roll while seated.
- `Space`, `Left Shift`, `Control`, arrows, and `WASD` are already movement/ship controls.
- Holding `R` is simple and avoids adding tool equip state too early.

### Signal Source Model

Add a signal source component.

Recommended file:

```text
res://scripts/signals/SignalSource.cs
```

Recommended scene:

```text
res://scenes/tools/SignalSource.tscn
```

Fields:

- `SignalName`
- `Frequency`
- `MaxRange`
- `FullStrengthRange`
- `DiscoveryRange`
- `ClueResource`
- `IsHidden`

Minimum behavior:

- Source can report signal strength from any world position.
- Source can report direction from scanner position.
- Source can report whether the scanner is close enough to identify it.
- Source can be registered with a signal service.

Strength model:

```text
distance = distance(scanner_position, source_position)
if distance > max_range:
    strength = 0
else if distance <= full_strength_range:
    strength = 1
else:
    t = (distance - full_strength_range) / (max_range - full_strength_range)
    strength = 1 - t
```

Optional refinement:

- Multiply strength by camera alignment so pointing toward the source makes the signal clearer.
- Do not require this for basic detection; use it for direction feedback.

### Signal Registry

Add a lightweight service similar to `GravityService`.

Recommended file:

```text
res://autoload/SignalService.tscn
res://autoload/SignalService.cs
```

Responsibilities:

- Register and unregister `SignalSource` nodes.
- Return the strongest source for scanner position and active frequency.
- Return all sources if debug validation needs it.

Reasoning:

- Avoid searching the whole scene tree every frame.
- Mirrors the existing gravity body registration pattern.
- Keeps scanner code focused on scanner behavior.

Alternative:

- Use Godot groups and query nodes in group `signal_sources`.

Recommendation:

- Use `SignalService` because it matches the codebase style established by `GravityService`.

### Scanner Component

Add scanner logic as a player child script.

Recommended file:

```text
res://scripts/tools/SignalScanner.cs
```

Recommended scene placement:

```text
Player
  SignalScanner
```

Responsibilities:

- Read `scan` input.
- Check player context.
- Query `SignalService`.
- Compute:
  - active/inactive
  - strongest source
  - strength
  - distance
  - direction relative to camera
  - whether source is identified
- Emit or expose state to HUD.
- Trigger clue discovery when close enough and aimed enough, or when player interacts with the point of interest.

Player context rule:

- Scanner allowed:
  - `OnFoot`
  - `InShipInterior`
- Scanner blocked:
  - `Seated`

### Scanner HUD

Add a simple UI layer.

Recommended files:

```text
res://scenes/ui/SignalScannerHud.tscn
res://scripts/ui/SignalScannerHud.cs
```

HUD should show only while scanning:

- signal strength bar
- directional indicator
- frequency/name text
- distance when identified or close enough
- "No Signal" when no source is in range

Suggested first layout:

```text
[ Signal ]
Strength: #####-----
Bearing: < / > / centered
Source: Unknown Signal
```

Avoid:

- Large explanatory text.
- Full-screen tool tutorial.
- Complex compass UI.

### Signal Direction Feedback

Minimum:

- Use a horizontal direction indicator based on camera forward versus source direction.
- Show left/right/center.

Preferred:

- Show an arrow or small marker that moves horizontally as the player turns.
- Increase strength when looking near the source.

Initial math:

```text
to_source = normalize(source_position - scanner_position)
camera_forward = -camera_basis.Z
camera_right = camera_basis.X
alignment = dot(camera_forward, to_source)
side = dot(camera_right, to_source)
```

Use:

- `alignment` for "centered" or "aimed at signal".
- `side` for left/right marker.

Suggested thresholds:

- Aimed if `alignment >= 0.85`.
- Centered if `abs(side) <= 0.15`.

### Hidden Point of Interest

Add one signal-driven point of interest on Planet B.

Recommended files:

```text
res://scenes/points_of_interest/SignalRuin.tscn
res://scripts/points_of_interest/ClueInteractable.cs
```

Behavior:

- The signal source is near or inside the point of interest.
- The point is visually subtle from the landing pad.
- Scanner can detect it from a reasonable distance.
- When close, the player can press `F` to inspect.
- Inspecting displays or records the first clue.

Placement:

- On Planet B, away from the landing pad but within walking/jetpack distance.
- Far enough that it is not the first obvious object the player sees.
- Close enough that Phase 6 manual testing is short.

Recommended distance:

- `40` to `90` meters from Planet B landing pad along the surface.

### First Clue Resource

Add a lightweight clue resource.

Recommended file:

```text
res://scripts/resources/ClueResource.cs
```

Recommended resource:

```text
res://resources/clues/planet_b_signal_clue.tres
```

Fields:

- `Id`
- `Title`
- `Body`

Example placeholder:

```text
Id: planet_b_signal_clue
Title: Resonant Stone
Body: The stone repeats a pattern that does not match the planet's beacon.
```

Phase 6 does not need save/load.

Runtime discovery:

- `ClueInteractable` can print to debug and show a small HUD message.
- Optionally add `GameState` in Phase 6 only if it remains tiny.

Recommendation:

- Add a `DiscoveryService` only in Phase 7.
- For Phase 6, keep clue discovery local and visible through a temporary message.

### Discovery Feedback

Minimum:

- Press `F` at the point of interest.
- Show a temporary UI message with clue title/body.

Recommended files:

```text
res://scenes/ui/DiscoveryToast.tscn
res://scripts/ui/DiscoveryToast.cs
```

Behavior:

- Hidden by default.
- Shows clue title/body for a few seconds.
- Does not persist.

Alternative:

- Reuse existing `InteractionPrompt` for the inspect prompt and print clue text in the debug overlay.

Recommendation:

- Add `DiscoveryToast`. It is small and makes the tool loop legible.

## 6. New Files

### Signals

- `res://autoload/SignalService.tscn`
- `res://autoload/SignalService.cs`
- `res://scripts/signals/SignalSource.cs`
- `res://scenes/tools/SignalSource.tscn`

### Scanner

- `res://scripts/tools/SignalScanner.cs`
- `res://scenes/ui/SignalScannerHud.tscn`
- `res://scripts/ui/SignalScannerHud.cs`

### Point of Interest

- `res://scenes/points_of_interest/SignalRuin.tscn`
- `res://scripts/points_of_interest/ClueInteractable.cs`

### Clue

- `res://scripts/resources/ClueResource.cs`
- `res://resources/clues/planet_b_signal_clue.tres`

### Discovery UI

- `res://scenes/ui/DiscoveryToast.tscn`
- `res://scripts/ui/DiscoveryToast.cs`

### Phase Scene and Validation

- `res://scenes/solar_system/Phase6TestWorld.tscn`
- `res://scenes/solar_system/Phase6Validation.tscn`
- `res://scripts/debug/Phase6ValidationRunner.cs`

## 7. Existing Files to Modify

### `project.godot`

- Add `SignalService` autoload.
- Add `scan` input action bound to `R`.
- Set main scene to `Phase6TestWorld.tscn` after implementation.

### `res://scenes/player/Player.tscn`

- Add `SignalScanner` child node.
- Assign player and camera paths if needed.

### `res://scenes/solar_system/Phase6TestWorld.tscn`

- Based on Phase 5 world.
- Add scanner HUD.
- Add discovery toast.
- Add Planet B signal point of interest.

### `res://scripts/interaction/PlayerInteractionController.cs`

Potential changes:

- None required if `ClueInteractable` implements `IInteractable`.
- Confirm scanner input does not interfere with `F`.

### `SETUP.md`

Update:

- Main scene.
- Validation commands.
- Controls:
  - `R`: hold scanner.

### `scripts/validate.sh`

Add Phase 6 validation.

## 8. Implementation Steps

### Step 1: Preserve Current Baseline

Checklist:

- [ ] Run `scripts/validate.sh` before Phase 6 edits.
- [ ] Confirm Phase 1 through Phase 5 pass.
- [ ] Confirm `Phase5TestWorld.tscn` still launches and is playable.

### Step 2: Add Signal Service

Checklist:

- [ ] Add `SignalService.cs`.
- [ ] Add `SignalService.tscn`.
- [ ] Register it as an autoload in `project.godot`.
- [ ] Implement `Register(SignalSource source)`.
- [ ] Implement `Unregister(SignalSource source)`.
- [ ] Implement strongest-signal query.

Validation:

- [ ] Service exists at runtime.
- [ ] Service returns no source when none are registered.
- [ ] Registered source can be queried.

### Step 3: Add Signal Source

Checklist:

- [ ] Add `SignalSource.cs`.
- [ ] Add `SignalSource.tscn`.
- [ ] Add exported signal fields.
- [ ] Register/unregister with `SignalService`.
- [ ] Implement strength calculation.
- [ ] Implement identified/discovery range helper.

Validation:

- [ ] Strength is `1` inside full-strength range.
- [ ] Strength falls to `0` at max range.
- [ ] Strength is `0` outside max range.

### Step 4: Add Scanner Input

Checklist:

- [ ] Add `scan` action to `project.godot`.
- [ ] Bind to `R`.
- [ ] Confirm no seated ship control uses `R`.
- [ ] Update `SETUP.md`.

### Step 5: Add Signal Scanner to Player

Checklist:

- [ ] Add `SignalScanner.cs`.
- [ ] Add `SignalScanner` node to `Player.tscn`.
- [ ] Read `scan` input.
- [ ] Check `PlayerContext`.
- [ ] Query `SignalService`.
- [ ] Expose debug/scanner state for HUD and validation.

Suggested public properties:

```csharp
public bool IsScanning { get; }
public bool HasSignal { get; }
public float SignalStrength { get; }
public string SignalName { get; }
public float SignalDistance { get; }
public float SignalSide { get; }
public float SignalAlignment { get; }
public SignalSource? ActiveSignal { get; }
```

### Step 6: Add Scanner HUD

Checklist:

- [ ] Add `SignalScannerHud.tscn`.
- [ ] Add `SignalScannerHud.cs`.
- [ ] Export scanner path.
- [ ] Hide when not scanning.
- [ ] Show no-signal state.
- [ ] Show signal strength.
- [ ] Show direction cue.
- [ ] Show source name only when identified or close enough.

Validation:

- [ ] HUD hides when `R` is not held.
- [ ] HUD shows while `R` is held.
- [ ] HUD reflects signal strength.

### Step 7: Add First Clue Resource and Discovery UI

Checklist:

- [ ] Add `ClueResource.cs`.
- [ ] Add first `.tres` clue.
- [ ] Add `DiscoveryToast.tscn`.
- [ ] Add `DiscoveryToast.cs`.
- [ ] Add method to show clue title/body for a short duration.

Validation:

- [ ] Toast can show a test message.
- [ ] Toast hides after timeout.

### Step 8: Add Point of Interest on Planet B

Checklist:

- [ ] Add `SignalRuin.tscn`.
- [ ] Add simple visual geometry.
- [ ] Add collision for interaction.
- [ ] Add `ClueInteractable.cs`.
- [ ] Add child or nearby `SignalSource`.
- [ ] Assign first clue resource.
- [ ] Place instance on Planet B in Phase 6 world.

Validation:

- [ ] Point of interest exists in Phase 6 world.
- [ ] Signal source registers.
- [ ] Player can inspect point with `F`.
- [ ] Discovery toast appears.

### Step 9: Create Phase 6 World

Checklist:

- [ ] Copy or derive from `Phase5TestWorld.tscn`.
- [ ] Add scanner HUD.
- [ ] Add discovery toast.
- [ ] Add Planet B signal point of interest.
- [ ] Set `ShipHud` target to Planet B.
- [ ] Keep existing Phase 5 travel loop intact.
- [ ] Set main scene to `Phase6TestWorld.tscn`.

### Step 10: Add Phase 6 Validation

Checklist:

- [ ] Add `Phase6Validation.tscn`.
- [ ] Add `Phase6ValidationRunner.cs`.
- [ ] Reuse Phase 5 validation flow enough to place player on Planet B.
- [ ] Assert `SignalService` exists.
- [ ] Assert signal source registers.
- [ ] Hold `scan`.
- [ ] Assert scanner detects signal.
- [ ] Move player closer or place player near source.
- [ ] Assert strength increases.
- [ ] Aim toward source or assert direction data.
- [ ] Interact with clue.
- [ ] Assert clue feedback appears or discovery state is set.
- [ ] Add Phase 6 validation to `scripts/validate.sh`.

### Step 11: Manual Test

Manual flow:

1. Start Phase 6 world.
2. Enter ship with `F`.
3. Sit with `F`.
4. Launch and travel to Planet B.
5. Land near the Planet B landing pad.
6. Stand and exit with `F`.
7. Hold `R` to scan.
8. Turn until the scanner direction cue centers.
9. Walk or jetpack toward stronger signal.
10. Find the point of interest.
11. Press `F` to inspect it.
12. Confirm clue feedback appears.

Manual acceptance:

- [ ] Scanner gives useful feedback without being too precise.
- [ ] Signal source can be found without knowing where it is.
- [ ] The point of interest is not obvious from the landing pad.
- [ ] The clue interaction is understandable.
- [ ] Existing ship and movement controls still feel unchanged.

## 9. Automated Validation Plan

Add `Phase6ValidationRunner.cs`.

Recommended validation sequence:

1. Assert Phase 6 scene contains player, ship, Planet B, scanner, scanner HUD, signal service, signal source, point of interest, and discovery toast.
2. Move or validate player to Planet B using the same deterministic approach as Phase 5 validation.
3. Assert scanner is inactive before `scan` input.
4. Press `scan`.
5. Assert scanner becomes active.
6. Assert scanner detects the Planet B signal source from a configured test position.
7. Record signal strength.
8. Move player closer to the source.
9. Assert signal strength increases.
10. Rotate or place player facing the source.
11. Assert alignment/direction values indicate the source is centered or near-centered.
12. Interact with point of interest.
13. Assert discovery toast or clue state is active.
14. Quit with success.

Automation note:

- Do not require full manual travel in the Phase 6 validation if Phase 5 already proves travel. Phase 6 validation can reposition the player near Planet B after confirming the scene setup, then focus on scanner behavior.

## 10. Success Criteria

Phase 6 is complete when:

- [ ] Player can hold `R` to use scanner.
- [ ] Scanner is blocked while seated/piloting.
- [ ] Scanner detects a signal source on Planet B.
- [ ] Scanner strength changes with distance.
- [ ] Scanner gives directional feedback.
- [ ] Player can locate a hidden point of interest using scanner feedback.
- [ ] Player can inspect the point of interest with `F`.
- [ ] Inspecting produces clue feedback.
- [ ] Phase 1 through Phase 6 validation passes.
- [ ] `SETUP.md` reflects the current scene, validation, and controls.

## 11. Risks

### Scanner Is Too Easy

Risk:

- If feedback is too precise, finding the point becomes trivial.

Mitigation:

- Use broad left/right/strength cues first.
- Reveal exact source name only when close.

### Scanner Is Too Vague

Risk:

- If feedback is too subtle, players cannot tell what to do.

Mitigation:

- Use a clear strength bar.
- Use an obvious direction cue.
- Place the first source within a short walk of the landing pad.

### UI Becomes Too Much Work

Risk:

- A polished scanner UI could consume the whole phase.

Mitigation:

- Start with text and a simple bar.
- Defer diegetic device visuals.

### Discovery System Expands Too Early

Risk:

- Clues invite save/load, ship log, categories, and mystery graph work.

Mitigation:

- Use one resource and one temporary feedback toast.
- Defer persistent discovery tracking to Phase 7.

### Control Conflicts

Risk:

- New scanner input conflicts with ship or movement controls.

Mitigation:

- Use `R`.
- Disable scanner while seated.
- Keep interaction on `F`.

## 12. Recommended Implementation Order

1. Add `SignalService`.
2. Add `SignalSource`.
3. Add `scan` input.
4. Add `SignalScanner` to player.
5. Add scanner HUD.
6. Add clue resource and discovery toast.
7. Add point of interest on Planet B.
8. Add Phase 6 scene.
9. Add Phase 6 validation.
10. Update setup docs and validation script.
11. Manual test full flow.

## 13. Deferred Questions

- Should scanner work from inside the ship cockpit in a later phase?
- Should the scanner have multiple frequencies or channels?
- Should signal source names reveal immediately or only after close inspection?
- Should clues be discovered by proximity, scanner lock-on, or explicit interaction?
- Should the first real ship log arrive in Phase 7 as a separate screen or as a cockpit display?

