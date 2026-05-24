# Phase 2 Implementation Plan: Jetpack and Weak-Gravity Movement

## 1. Phase Goal

Make player movement interesting beyond surface walking by adding:

- Short-burst jetpack thrust.
- Fuel or heat limiting.
- Weak-gravity and zero-g movement behavior.
- Suit HUD placeholder.
- Basic oxygen placeholder.
- Repeatable validation for the new movement states.

Phase 2 should preserve the good parts of Phase 1: spherical gravity walking, stable camera alignment, jump/fall behavior, debug overlay, and automated validation.

## 2. Phase 1 Reality Check

Phase 1 was implemented successfully with a few practical choices that should guide Phase 2:

- `GravityService` is an autoloaded scene at `res://autoload/GravityService.tscn`, not a direct `.cs` autoload. Keep this pattern because it imports cleanly in Godot C#.
- Godot-facing C# scripts are in the global namespace. Keep this unless there is a strong reason to change it.
- `PlayerController.cs` currently owns gravity updates, body alignment, walking, jumping, camera look, and debug data.
- `Phase1Validation.tscn` and `Phase1ValidationRunner.cs` provide a useful pattern for automated movement checks.
- Setup and validation are automated through `scripts/setup-macos.sh` and `scripts/validate.sh`.
- The project is currently local-first for Linux/macOS. Docker remains deferred.

Anything that changes the controller should keep `scripts/validate.sh` passing.

## 3. Proposal Updates Needed

The proposal does not need a major rewrite, but these details should be noted after Phase 1:

- Phase 1 and later phases should refer to `GravityService.tscn` plus `GravityService.cs`, not only `GravityService.cs`.
- The project now has a formal validation pattern. Future phases should include a validation scene and runner.
- Phase 2 should explicitly include a small movement-state refactor before adding jetpack and zero-g behavior.
- The setup path is now scripted and documented in `SETUP.md`.
- The player controller should remain C# first and avoid GDScript unless used for isolated tooling.

Do not edit the proposal until after Phase 2 planning is reviewed, unless we want the proposal to become a living status document.

## 4. Scope

### In Scope

- Jetpack input action.
- Jetpack thrust while airborne and grounded.
- Jetpack fuel or heat limiter.
- Recharge/cooldown model.
- Weak-gravity movement mode.
- Zero-g drift mode when no gravity body is active or gravity is below a threshold.
- Suit HUD placeholder showing fuel/heat, oxygen, speed, and movement mode.
- Expanded debug overlay data.
- More varied Phase 2 test geometry.
- Automated Phase 2 validation scene.
- Updates to `scripts/validate.sh` to run Phase 2 validation.

### Out of Scope

- Ship.
- Multiple planets.
- Floating origin.
- Inventory.
- Scanner.
- Narrative clues.
- Full oxygen death/failure loop.
- Polished UI art.
- Audio pass.
- Procedural terrain.
- Save/load.

## 5. Design Decisions

### Jetpack Limiter

Use **fuel** for Phase 2, not heat.

Reasoning:

- Fuel is easier for players to read immediately.
- Fuel supports clear HUD feedback.
- Recharge rules can be tuned later.
- Heat can be added later if we want riskier sustained thrust.

Initial model:

- Jetpack has `JetpackFuelMax`.
- Holding jetpack consumes fuel.
- Fuel recharges when jetpack is not firing.
- Recharge starts immediately for Phase 2. Add recharge delay later only if needed.

### Jetpack Direction

Use camera-relative thrust with gravity-aware constraints:

- On a planet, jetpack thrust should bias upward away from gravity.
- In air, allow directional influence based on movement input.
- In zero-g, thrust should move the player in camera-relative directions.

Initial behavior:

- Holding jetpack applies upward thrust along `DebugUpDirection`.
- Movement input adds a smaller tangent/camera-relative component.
- Jump remains a short impulse.
- Jetpack is sustained thrust.

### Weak Gravity

Define weak gravity as:

- A gravity body exists, but effective gravity is below a threshold, or
- The player is near the edge of a body's influence, or
- A test scene uses a low-gravity body.

For Phase 2, use a low-gravity moon/test body rather than complex falloff. Phase 1 gravity currently uses constant surface gravity inside the influence radius. Do not add orbital-scale falloff unless Phase 2 needs it.

### Zero-G

Define zero-g as:

- No gravity body is selected by `GravityService`, or
- The active gravity acceleration magnitude is below `ZeroGravityThreshold`.

Initial zero-g movement:

- Player does not align to a global up direction.
- Mouse look controls orientation.
- Movement input plus jetpack thrust accelerates the player.
- Velocity persists until counter-thrust is applied.
- Add damping only as a tuning assist, not as normal friction.

## 6. Architecture Changes

### Player Movement State

Add a simple movement state enum:

```csharp
public enum PlayerMovementMode
{
    Surface,
    Airborne,
    WeakGravity,
    ZeroGravity
}
```

State selection rules:

- `ZeroGravity`: no active gravity body or gravity acceleration below threshold.
- `Surface`: active gravity body and `IsOnFloor()`.
- `WeakGravity`: active gravity body and gravity magnitude below `WeakGravityThreshold`.
- `Airborne`: active gravity body, not grounded, normal gravity.

Expose:

- `DebugMovementMode`.
- `DebugJetpackFuel`.
- `DebugOxygen`.

### PlayerController Refactor

Current `PlayerController.cs` methods:

- `UpdateGravityState`
- `AlignToGravity`
- `ApplyMovement`

Proposed Phase 2 structure:

- `UpdateGravityState`
- `UpdateMovementMode`
- `UpdateBodyAlignment`
- `ApplySurfaceMovement`
- `ApplyAirborneMovement`
- `ApplyWeakGravityMovement`
- `ApplyZeroGravityMovement`
- `ApplyJetpack`
- `UpdateSuitResources`
- `UpdateDebugState`

Keep this in `PlayerController.cs` for Phase 2. Do not split into many files until the controller becomes difficult to read.

### Suit Resources

Add exported tuning values:

```csharp
[Export] public float JetpackFuelMax { get; set; } = 3.0f;
[Export] public float JetpackFuelUseRate { get; set; } = 1.0f;
[Export] public float JetpackFuelRechargeRate { get; set; } = 0.75f;
[Export] public float JetpackUpThrust { get; set; } = 28.0f;
[Export] public float JetpackDirectionalThrust { get; set; } = 10.0f;
[Export] public float WeakGravityThreshold { get; set; } = 8.0f;
[Export] public float ZeroGravityThreshold { get; set; } = 0.25f;
[Export] public float ZeroGravityThrust { get; set; } = 8.0f;
[Export] public float ZeroGravityDamping { get; set; } = 0.05f;
[Export] public float OxygenMax { get; set; } = 120.0f;
```

Internal state:

```csharp
private float _jetpackFuel;
private float _oxygen;
private PlayerMovementMode _movementMode;
```

Initialize fuel and oxygen to max in `_Ready`.

### Input Actions

Add to `project.godot`:

- `jetpack`: Space, right mouse, or another key?
- `brake`: Shift or Ctrl for future zero-g counter-thrust.

Recommended Phase 2 bindings:

- `jump`: Space.
- `jetpack`: Left Shift.
- `brake`: Ctrl.

Reasoning:

- Keeping jump and jetpack separate lets us tune each cleanly.
- Shift is already present as `sprint` from Phase 1 setup, but sprint is unused. Reuse or rename it deliberately.

Decision needed before implementation:

- Either keep `sprint` and bind jetpack separately, or rename `sprint` to `jetpack`.

Recommendation:

- Rename `sprint` to `jetpack` for now. Sprint is not part of the current game.

### HUD

Create:

- `res://scenes/ui/SuitHud.tscn`
- `res://scripts/ui/SuitHud.cs`

HUD should show:

- Jetpack fuel bar.
- Oxygen placeholder bar.
- Movement mode text.
- Speed text.

Keep visual styling simple:

- `CanvasLayer`
- `PanelContainer`
- `ProgressBar`
- `Label`

Do not polish this. It is a functional tuning instrument.

### Debug Overlay

Extend `GravityDebugOverlay.cs` to show:

- Movement mode.
- Jetpack fuel.
- Oxygen.
- Active gravity acceleration magnitude.
- Whether jetpack is firing.

The debug overlay and HUD may duplicate information in Phase 2. That is acceptable.

## 7. Test Scene Changes

### Phase2TestWorld.tscn

Create:

- `res://scenes/solar_system/Phase2TestWorld.tscn`

Contents:

- Existing Phase 1 planet.
- Player.
- Debug overlay.
- Suit HUD.
- A raised platform or ramp.
- A low-gravity test body or low-gravity zone.
- A zero-g test volume or spawn/teleport marker outside gravity influence.

Keep the main scene as `Phase1TestWorld.tscn` until Phase 2 is stable, or switch `project.godot` to `Phase2TestWorld.tscn` once Phase 2 validation passes.

### LowGravityPlanet.tscn

Option A:

- Instance `PlanetBody.tscn` with overridden `SurfaceGravity = 4.0`.

Option B:

- Create a separate `LowGravityPlanet.tscn`.

Recommendation:

- Use an instance override in `Phase2TestWorld.tscn` first. Create a separate scene only if repeated low-gravity bodies become useful.

### Zero-G Test

Simplest approach:

- Add a `Marker3D` outside the planet's influence radius.
- Automated validation can move the player there directly.

Do not create a full airlock/space transition yet. That belongs closer to ship work.

## 8. Implementation Steps

### Step 1: Update Input Map

Checklist:

- [ ] Decide whether to rename `sprint` to `jetpack`.
- [ ] Add `jetpack` input action.
- [ ] Add `brake` input action if used.
- [ ] Update `SETUP.md` manual controls.
- [ ] Update `plans/phase2-implementation-plan.md` if bindings change during implementation.

### Step 2: Add Movement Mode Enum

Checklist:

- [ ] Add `PlayerMovementMode` enum.
- [ ] Add `_movementMode` field.
- [ ] Add `DebugMovementMode` property.
- [ ] Implement `UpdateMovementMode`.
- [ ] Confirm Phase 1 validation still passes.

### Step 3: Refactor Player Movement Methods

Checklist:

- [ ] Preserve current walking behavior.
- [ ] Extract surface walking into `ApplySurfaceMovement`.
- [ ] Extract airborne behavior into `ApplyAirborneMovement`.
- [ ] Keep gravity update and alignment behavior intact.
- [ ] Run `scripts/validate.sh`.

### Step 4: Add Jetpack Resource State

Checklist:

- [ ] Add exported jetpack tuning values.
- [ ] Add `_jetpackFuel`.
- [ ] Initialize fuel in `_Ready`.
- [ ] Add fuel consume/recharge logic.
- [ ] Add debug properties for fuel and jetpack firing.

### Step 5: Add Jetpack Thrust

Checklist:

- [ ] Read `jetpack` input.
- [ ] Apply upward thrust while fuel is available.
- [ ] Add directional influence from movement input.
- [ ] Prevent fuel from going below zero.
- [ ] Recharge fuel when not firing.
- [ ] Tune thrust so the player can clear the test landmark but not fly indefinitely.

### Step 6: Add Weak-Gravity Movement

Checklist:

- [ ] Add weak-gravity threshold.
- [ ] Add low-gravity test body or scene override.
- [ ] Tune air control higher in weak gravity.
- [ ] Confirm weak gravity feels different from normal airborne movement.
- [ ] Ensure player still aligns to local gravity while weak gravity is active.

### Step 7: Add Zero-G Movement

Checklist:

- [ ] Add zero-g state when no gravity body is active.
- [ ] Stop forcing radial alignment in zero-g.
- [ ] Apply camera-relative thrust in zero-g.
- [ ] Preserve velocity between thrust inputs.
- [ ] Add optional low damping.
- [ ] Add brake/counter-thrust if needed for control.

### Step 8: Add Suit HUD

Checklist:

- [ ] Create `SuitHud.tscn`.
- [ ] Create `SuitHud.cs`.
- [ ] Add exported `PlayerPath`.
- [ ] Show jetpack fuel.
- [ ] Show oxygen placeholder.
- [ ] Show speed.
- [ ] Show movement mode.
- [ ] Add HUD to Phase 2 test scene.

### Step 9: Expand Debug Overlay

Checklist:

- [ ] Add movement mode.
- [ ] Add jetpack fuel.
- [ ] Add oxygen.
- [ ] Add active gravity acceleration magnitude.
- [ ] Add jetpack firing state.

### Step 10: Add Phase 2 Validation

Checklist:

- [ ] Create `Phase2Validation.tscn`.
- [ ] Create `Phase2ValidationRunner.cs`.
- [ ] Validate Phase 1 behavior still works.
- [ ] Simulate jetpack input.
- [ ] Confirm fuel decreases while firing.
- [ ] Confirm fuel recharges after release.
- [ ] Confirm player gains altitude from jetpack.
- [ ] Confirm weak-gravity mode can be entered.
- [ ] Confirm zero-g mode can be entered.
- [ ] Confirm zero-g velocity persists after thrust.
- [ ] Update `scripts/validate.sh` to run Phase 2 validation.

## 9. Acceptance Test Checklist

Phase 2 is complete when:

- [ ] Phase 1 validation still passes.
- [ ] Phase 2 validation passes.
- [ ] Player can use jetpack from the planet surface.
- [ ] Player can use jetpack while airborne.
- [ ] Jetpack fuel decreases while active.
- [ ] Jetpack fuel recharges when inactive.
- [ ] Player cannot fly indefinitely with default settings.
- [ ] Player can recover from a bad jump using jetpack.
- [ ] Player can move in weak gravity.
- [ ] Weak gravity feels distinct from normal gravity.
- [ ] Player can enter zero-g mode in the test scene.
- [ ] Zero-g movement preserves velocity.
- [ ] Zero-g movement has a usable brake/counter-thrust behavior or a documented reason to defer it.
- [ ] HUD shows jetpack fuel, oxygen placeholder, movement mode, and speed.
- [ ] Debug overlay shows movement mode and jetpack state.
- [ ] No script errors appear during validation.
- [ ] `scripts/validate.sh` passes on macOS.

Manual playtest checks:

- [ ] Jetpack is easy to understand without reading code.
- [ ] Jetpack does not make walking irrelevant.
- [ ] Camera remains comfortable during jetpack use.
- [ ] Landing after jetpack thrust feels predictable.
- [ ] Weak gravity feels floatier but still controllable.
- [ ] Zero-g is understandable enough to become the basis for later ship/space traversal.

## 10. Known Technical Questions

Resolve during Phase 2:

- Should jump and jetpack share a key later, or remain separate?
- Does `CharacterBody3D` remain sufficient for zero-g movement, or does it fight us?
- Should zero-g camera orientation roll freely, or stay mostly horizon-stabilized until ship/space systems exist?
- Should jetpack thrust be purely upward on planets, or camera-relative?
- Does fuel recharge immediately, or after a short delay?
- Does oxygen matter yet, or should it stay a HUD placeholder until hazards exist?

## 11. Risks

### Controller Complexity

Risk:

- `PlayerController.cs` could become a large pile of special cases.

Mitigation:

- Add a small movement mode enum.
- Keep methods clearly separated.
- Avoid splitting files too early, but do not keep unrelated HUD/resource code inside movement math.

### Zero-G Feel

Risk:

- Zero-g movement can feel confusing or nauseating.

Mitigation:

- Start with conservative thrust and optional damping.
- Add brake/counter-thrust early if needed.
- Keep visual test geometry simple.

### Jetpack Dominance

Risk:

- Jetpack may trivialize planet traversal.

Mitigation:

- Use limited fuel.
- Tune recharge and thrust.
- Use future level design to make jetpack useful but not universal.

## 12. Recommended Implementation Order

1. Add input and movement mode enum.
2. Refactor current movement without changing behavior.
3. Re-run Phase 1 validation.
4. Add fuel state and HUD.
5. Add jetpack thrust.
6. Add Phase 2 test scene geometry.
7. Add weak-gravity state.
8. Add zero-g state.
9. Add Phase 2 validation scene.
10. Update `scripts/validate.sh`.
11. Manual playtest and tune.

The key discipline is to keep Phase 1 green after every structural change. If surface walking regresses, stop and fix it before adding more movement features.

## 13. Implementation Verification

Implemented files include:

- `res://scenes/solar_system/Phase2TestWorld.tscn`
- `res://scenes/solar_system/Phase2Validation.tscn`
- `res://scripts/debug/Phase2ValidationRunner.cs`
- `res://scenes/planets/LowGravityPlanet.tscn`
- `res://scenes/ui/SuitHud.tscn`
- `res://scripts/ui/SuitHud.cs`
- Updated `res://scenes/player/PlayerController.cs`
- Updated `res://scripts/debug/GravityDebugOverlay.cs`
- Updated `res://scripts/validate.sh`

Validation commands:

```bash
scripts/validate.sh
```

Automated validation currently checks:

- Phase 1 movement still passes.
- Jetpack fires.
- Jetpack fuel decreases while firing.
- Jetpack fuel recharges after release.
- Jetpack increases distance from the planet surface.
- Weak-gravity mode can be entered.
- Zero-g mode can be entered.
- Zero-g thrust produces velocity.
- Zero-g velocity persists after thrust release.

Manual playtest focus:

- Tune `JetpackUpThrust`, `JetpackDirectionalThrust`, and fuel values.
- Check whether `Left Shift` is comfortable as the jetpack binding.
- Check whether zero-g brake on `Control` feels natural.
- Confirm the HUD is readable but not distracting.
