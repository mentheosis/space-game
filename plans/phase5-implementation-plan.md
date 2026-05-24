# Phase 5 Implementation Plan: Two-Planet Travel

## 1. Phase Goal

Prove the core travel loop: the player can launch from the starting planet, navigate through open space to a second planet, enter that planet's gravity, land, stand up, exit the ship, and walk on the second planet.

This phase is about **interplanetary travel between two authored bodies**. It is not about story content, a full solar system, orbital simulation, floating origin, or final ship feel.

Phase 5 should deliver:

- A playable second destination planet.
- A main solar-system scene with both planets placed at intentional travel scale.
- Navigation marker UI for at least the second planet.
- Ship HUD improvements for target distance, speed, and current gravity body.
- Stable gravity handoff between planets.
- Tuned gravity falloff inside each planet's influence radius.
- Tuned ship control for travel away from the starting planet.
- Basic match-velocity or dampening assist if manual travel is too hard.
- Automated validation proving ship travel from Planet A toward Planet B, gravity handoff, landing eligibility, and exit on the second planet.

## 2. Current Project Reality

Phase 4 established:

- `Ship.tscn` root is a `RigidBody3D`.
- `ShipController.cs` owns active pilot state, ship-local thrust, ship-local pitch/yaw/roll, gravity, landing state, and third-person ship camera.
- Player can enter the ship, sit, pilot, stand, and exit.
- Ship hatches are usable only while the ship is landed and slow enough.
- Player remains snapped to `SeatAnchor` while seated.
- Player collision is disabled while seated to prevent ship/player collision feedback.
- Interaction is bound to `F`.
- Seated ship controls are:
  - `W/S/A/D`: local ship translation in the forward/back/left/right plane.
  - `Space`: ascend along ship-local up.
  - `Left Shift`: descend along ship-local down.
  - Arrow keys: pitch/yaw.
  - `Q/E`: roll.
- Ship pitch is inverted after manual testing.
- `Phase4TestWorld.tscn` already contains:
  - `PlanetBody` at the origin.
  - `LowGravityPlanet` at `Vector3(400, 0, 0)`.
  - A dark space sky and basic directional light.
  - Suit HUD, ship HUD, interaction prompt, and debug overlay.
- `scripts/validate.sh` runs Phase 1 through Phase 4 automated validation.

Important implementation notes from Phase 4:

- The ship now uses ship-local axes for controls. Do not reintroduce planet-relative control axes.
- `F` must remain the interaction action.
- Seated `F` stand should use the stored seat interactable, not the camera raycast.
- The current second planet is present but is not yet a designed travel destination with navigation, landing validation, or player exploration success criteria.
- Landing detection currently uses approximate surface distance, speed, and uprightness. This is acceptable for Phase 5 but may need more tuning around Planet B.
- `GravityBody` currently applies constant gravity inside its influence radius and zero gravity outside. Phase 5 should replace this with a falloff curve so gravity becomes weak near the edge before the ship reaches true zero-g.

## 3. Proposal Updates Needed

The proposal's Phase 5 direction is still correct:

- Second planet.
- Solar-system scene root.
- Navigation markers.
- Ship velocity or match-speed assist.
- Tuned travel scale.
- Basic space sky and sun.

Update the implementation interpretation:

- The project already has a second placeholder planet, so Phase 5 should evolve it into an intentional destination instead of adding an unrelated third body.
- The current ship controls are translation-first and keyboard-rotation driven. Phase 5 should tune around this actual control model.
- Full floating origin remains deferred. Keep distances compact enough for stable Godot transforms.
- Travel should feel short and readable, not astronomically realistic.
- Match velocity assist can be simple and optional, but there must be a practical way to slow down near the destination.

## 4. Scope

### In Scope

- Create or revise a dedicated Phase 5 test world.
- Make Planet B visually distinct from Planet A.
- Add a landing target or landmark on Planet B.
- Add navigation target data for planets.
- Add a world-space or HUD navigation marker for Planet B.
- Add target distance and relative speed readouts.
- Add current gravity body display for ship flight.
- Tune planet positions, influence radii, gravity strengths, and ship thrust so travel is feasible.
- Add a simple ship dampening or match-velocity assist if needed.
- Ensure player can land on Planet B, stand, exit, and walk on its surface.
- Add Phase 5 automated validation.
- Update `scripts/validate.sh`.
- Update `SETUP.md` controls and manual test instructions if controls or validation commands change.

### Out of Scope

- More than two planets.
- Planetary orbits.
- N-body physics.
- Floating origin.
- Solar-system streaming.
- Save/load.
- Ship damage, fuel, repairs, or autopilot.
- Full cockpit instrumentation.
- Planet B story content.
- Exploration tools, signals, clues, or ship log.
- Walking inside the ship while it is moving.

## 5. Design Decisions

### Solar-System Scale

Use compact authored scale.

Initial recommended values:

- Planet A radius: `50`.
- Planet A influence radius: `250`.
- Planet B radius: `45` to `60`.
- Planet B influence radius: `180` to `250`.
- Planet separation: `450` to `650`.

Reasoning:

- The current project already uses a planet at `400` units. That is close enough for quick testing, but the final Phase 5 distance should leave a visible space-travel segment.
- Keep a small neutral-space gap between influence spheres so weak/zero-g ship travel is obvious.
- Avoid distances that require floating origin work.

Target feel:

- Launch to arrival should take roughly `20` to `60` seconds with direct flight.
- Planet B should be visible or locatable soon after takeoff.
- The player should not need orbital mechanics knowledge.

### Planet B

Create a more explicit Planet B scene.

Recommended file:

```text
res://scenes/planets/PlanetB.tscn
```

Planet B should include:

- Distinct material color.
- Different surface gravity from Planet A, but not so low that landing becomes chaotic.
- One obvious landmark or landing pad.
- `GravityBody`.
- `PlanetSpawnPoint` or a marker useful for validation.

Recommended initial values:

- Radius: `45`.
- Surface gravity: `14` to `18`.
- Influence radius: `220`.
- Priority: `1` unless priority causes unwanted dominance.

Notes:

- If the existing `LowGravityPlanet.tscn` remains useful for Phase 2 validation, keep it.
- Do not break Phase 2 weak/zero-g validation. If needed, create a new `TravelPlanet.tscn` rather than repurposing `LowGravityPlanet.tscn`.

### Gravity Handoff

The existing `GravityService` selects one dominant gravity body.

Phase 5 should validate:

- Ship starts under Planet A gravity.
- Ship moves through strong gravity, then weak gravity near the influence edge.
- Ship leaves Planet A influence and reaches true zero-g.
- Ship enters Planet B influence.
- Ship experiences weak Planet B gravity near the influence edge, then stronger gravity near the surface.
- Ship's active gravity body changes to Planet B.

Implementation options:

1. Keep current priority-and-range selection.
2. Add nearest-body selection when multiple bodies contain the point.
3. Add strength-based selection later.

Recommendation:

- Keep the current model if it works for two bodies.
- Add public debug fields to `ShipController` only if validation needs to inspect active gravity body name or current gravity magnitude.
- Avoid redesigning gravity until travel proves the current model is insufficient.

### Gravity Falloff

Use dominant-body gravity with an intentional zero-g gap between planet influence spheres, but add falloff inside each influence sphere.

Current behavior:

- Gravity is constant anywhere inside a planet's influence radius.
- Gravity instantly becomes zero outside the influence radius.

Phase 5 behavior:

- Gravity is strongest near the surface.
- Gravity falls off steeply soon after leaving the surface.
- Gravity falls off more gently near the edge of influence.
- At the influence boundary, gravity becomes effectively zero.
- Outside all influence radii, the ship and player are in true zero-g.

Recommended model:

```text
distance_from_center = distance(body_center, world_position)
altitude = max(0, distance_from_center - planet_radius)
falloff_range = influence_radius - planet_radius
t = clamp(altitude / falloff_range, 0, 1)
gravity_ratio = pow(1 - t, falloff_exponent)
gravity = edge_gravity + (surface_gravity - edge_gravity) * gravity_ratio
```

Suggested initial values:

- Planet A `SurfaceGravity`: `24`
- Planet A `EdgeGravity`: `0.15` to `0.35`
- Planet A `FalloffExponent`: `2.0` to `3.0`
- Planet B `SurfaceGravity`: `16`
- Planet B `EdgeGravity`: `0.10` to `0.25`
- Planet B `FalloffExponent`: `2.0` to `3.0`

At the exact influence boundary, `GravityBody.ContainsPoint` should still return false once outside the radius. The small edge gravity exists only just inside the boundary, making the transition to zero-g less surprising.

Implementation details:

- Add exported fields to `GravityBody.cs`:
  - `UseFalloff`
  - `EdgeGravity`
  - `FalloffExponent`
- Keep constant gravity available for validation/debug scenes if needed.
- Clamp gravity to zero outside `InfluenceRadius`.
- Clamp `FalloffExponent` to a sane minimum such as `0.1`.
- Surface and below-surface points should still use full `SurfaceGravity`.

Design consequence:

- Near a planet, the ship naturally falls back unless it keeps thrusting.
- Near the influence edge, ship handling approaches zero-g before the hard zero-g gap.
- The HUD should show current gravity magnitude so the player can feel and read the transition.

### Navigation Marker

Add a simple HUD marker for Planet B.

Recommended behavior:

- Marker appears while piloting the ship.
- Marker points to Planet B in screen space.
- Marker shows target name and distance.
- If the target is off-screen, clamp marker to screen edge.
- If the target is behind the camera, place the marker on the nearest edge and indicate direction by position only.

Minimum acceptable version:

- A text panel in `ShipHud` showing:
  - target name
  - distance
  - relative speed
  - current gravity body

Preferred Phase 5 version:

- Text readouts plus a simple 2D marker anchored over the target direction.

Implementation files:

```text
res://scripts/ui/NavigationMarker.cs
res://scenes/ui/NavigationMarker.tscn
```

or integrate into:

```text
res://scripts/ui/ShipHud.cs
res://scenes/ui/ShipHud.tscn
```

Recommendation:

- Start inside `ShipHud` to avoid premature UI architecture.
- Extract a reusable marker component only if the code gets awkward.

### Navigation Target Data

Use simple exported node paths first.

Option A:

- `ShipHud` gets an exported `TargetPath`.
- Phase 5 world assigns Planet B or a `Marker3D` at Planet B center.

Option B:

- Add `NavigationTarget.cs` component with:
  - display name
  - target radius
  - marker color
  - landing marker path

Recommendation:

- Add `NavigationTarget.cs` if the marker needs a clean target name and radius.
- Keep it lightweight. This is not the full map/log system.

Suggested script:

```text
res://scripts/navigation/NavigationTarget.cs
```

Fields:

- `DisplayName`
- `MarkerColor`
- `TargetRadius`

### Ship Travel Assist

Manual flight currently works around one planet but may become hard over longer distances.

Add a minimal assist only if needed:

- Hold `Control` to dampen ship velocity and angular velocity.
- Or hold a new `ship_match_velocity` input to reduce relative velocity to the selected navigation target.

Recommendation:

- First restore/use `Control` as a ship brake while seated.
- Keep `Space` as ascend.
- Avoid full autopilot.

Potential control:

- `Control`: dampen linear and angular velocity while seated.

Implementation:

- Add `BrakeStrength` back to `ShipController`.
- If `brake` is pressed while piloting, move `LinearVelocity` and `AngularVelocity` toward zero.
- Later, match velocity can move toward target velocity. Since planets are stationary in Phase 5, zero velocity is effectively match velocity near the target.

### Landing on Planet B

Landing detection may remain the current simple model:

- Close to active gravity body's surface.
- Speed below `MaxLandedSpeed`.
- Ship local up roughly matches gravity up.

Potential improvements:

- Increase `LandingDistance` slightly if landing feels too strict.
- Add a visible landing pad on Planet B so manual testing has a clear target.
- Add a `LandingZone` area later if surface-distance landing is too unpredictable.

Recommendation:

- Do not add a `LandingZone` dependency unless needed.
- Test landing anywhere on Planet B first.

### Scene Organization

Add a Phase 5 scene:

```text
res://scenes/solar_system/Phase5TestWorld.tscn
```

Add validation scene:

```text
res://scenes/solar_system/Phase5Validation.tscn
```

Question for implementation:

- Should `project.godot` main scene move to Phase 5 immediately?

Recommendation:

- Yes, after Phase 5 implementation passes validation, set the main scene to `Phase5TestWorld.tscn`.

## 6. New Files

### Planets

- `res://scenes/planets/PlanetB.tscn`

Optional:

- `res://scripts/components/LandingZone.cs`
- `res://scenes/components/LandingZone.tscn`

### Navigation

Recommended:

- `res://scripts/navigation/NavigationTarget.cs`

Optional:

- `res://scripts/ui/NavigationMarker.cs`
- `res://scenes/ui/NavigationMarker.tscn`

### Solar System

- `res://scenes/solar_system/Phase5TestWorld.tscn`
- `res://scenes/solar_system/Phase5Validation.tscn`

### Debug and Validation

- `res://scripts/debug/Phase5ValidationRunner.cs`

## 7. Existing Files to Modify

### `res://scripts/ship/ShipController.cs`

Potential changes:

- Expose active gravity body name for HUD/validation.
- Expose current gravity acceleration magnitude.
- Add seated brake/dampening if travel/landing needs it.
- Tune thrust/torque/damping values for interplanetary travel.
- Preserve ship-local control axes.
- Preserve inverted pitch.

Expected useful public properties:

```csharp
public string ActiveGravityBodyName { get; }
public float GravityMagnitude { get; }
public Vector3 GravityAcceleration { get; }
public bool IsLanded { get; }
public float Speed { get; }
```

### `res://scripts/ui/ShipHud.cs`

Potential changes:

- Add target distance.
- Add relative speed.
- Add active gravity body.
- Add landing status.
- Add target marker if implemented inside `ShipHud`.

### `res://scenes/ui/ShipHud.tscn`

Potential changes:

- Add labels for target, distance, relative speed, gravity source.
- Add marker control node if using screen-space marker.

### `res://autoload/GravityService.cs`

Potential changes only if needed:

- Add body lookup by name.
- Add list/debug access for validation.
- Improve body selection if overlapping influence radii cause wrong behavior.

Do not redesign this unless testing proves it necessary.

### `res://scripts/validate.sh`

Add Phase 5 validation:

```bash
"$GODOT_BIN" --headless --path . scenes/solar_system/Phase5Validation.tscn
```

### `res://project.godot`

Potential changes:

- Set main scene to `Phase5TestWorld.tscn` after implementation.
- Add any new input action only if needed.

### `SETUP.md`

Update:

- Main scene path.
- Validation command list.
- Current controls if brake/match velocity is added.
- Phase 5 manual test instructions.

## 8. Implementation Steps

### Step 1: Preserve Current Baseline

Checklist:

- [ ] Run `scripts/validate.sh` before edits.
- [ ] Confirm Phase 1 through Phase 4 validation passes.
- [ ] Confirm current main scene is playable.
- [ ] Note current ship control tuning values before changing them.

### Step 2: Create Planet B

Checklist:

- [ ] Add `PlanetB.tscn`.
- [ ] Use a sphere mesh and collision shape.
- [ ] Add `GravityBody`.
- [ ] Set distinct radius, gravity, and influence radius.
- [ ] Add distinct visual material.
- [ ] Add at least one surface landmark or landing pad.
- [ ] Add a marker at or near the intended validation landing area.
- [ ] Confirm player can stand on Planet B if spawned there manually.

Validation:

- [ ] Planet B registers with `GravityService`.
- [ ] `GravityBody.GetDistanceToSurface` returns expected values.
- [ ] Planet B collision matches its visual surface closely enough for landing.

### Step 3: Create Phase 5 Test World

Checklist:

- [ ] Add `Phase5TestWorld.tscn`.
- [ ] Instance Planet A.
- [ ] Instance Planet B at tuned travel distance.
- [ ] Instance player at Planet A spawn.
- [ ] Instance ship near Planet A spawn.
- [ ] Instance suit HUD.
- [ ] Instance ship HUD.
- [ ] Instance interaction prompt.
- [ ] Instance debug overlay.
- [ ] Add directional light or sun placeholder.
- [ ] Add space environment.
- [ ] Add target marker node for Planet B if needed.

Validation:

- [ ] Scene opens in Godot.
- [ ] Player starts on Planet A.
- [ ] Ship starts landed on Planet A.
- [ ] Planet B is reachable without precision issues.

### Step 4: Add Navigation Target

Checklist:

- [ ] Add `NavigationTarget.cs` or equivalent exported data.
- [ ] Attach navigation target data to Planet B or a child marker.
- [ ] Give Planet B a display name.
- [ ] Expose target path to `ShipHud`.

Minimum HUD:

- [ ] Show target name.
- [ ] Show distance to target.
- [ ] Show ship speed.
- [ ] Show current gravity body.

Preferred HUD:

- [ ] Add screen-space marker direction.
- [ ] Clamp marker when target is off-screen.
- [ ] Hide marker or change style when not piloting.

Validation:

- [ ] HUD updates while seated.
- [ ] Distance decreases when flying toward Planet B.
- [ ] HUD does not throw errors when target path is missing.

### Step 5: Tune Travel

Checklist:

- [ ] Tune planet separation.
- [ ] Tune influence radii to create readable gravity transition.
- [ ] Tune ship thrust for reasonable travel time.
- [ ] Tune ship brake/dampening if needed.
- [ ] Confirm ship does not become uncontrollable leaving Planet A.
- [ ] Confirm ship can slow enough to enter Planet B gravity and land.

Suggested initial tuning targets:

- [ ] Direct launch to Planet B takes less than 60 seconds.
- [ ] Player can clearly see distance decreasing.
- [ ] Ship can descend under control near Planet B.
- [ ] Ship can reach landed state without perfect alignment.

### Step 6: Add Ship Brake or Match Velocity Assist

Only do this if manual travel and landing are too hard.

Checklist:

- [ ] Use existing `brake` action while seated.
- [ ] Add `BrakeStrength` export to `ShipController`.
- [ ] Dampen `LinearVelocity` and `AngularVelocity` while held.
- [ ] Keep `Space` as ascend.
- [ ] Update `SETUP.md`.
- [ ] Add validation that brake reduces speed.

Optional match velocity:

- [ ] Add selected target velocity support.
- [ ] Since planets are stationary, match velocity can initially mean slow toward world zero.
- [ ] Avoid adding autopilot steering.

### Step 7: Validate Gravity Handoff

Checklist:

- [ ] Add ship debug property for active gravity body name if not already present.
- [ ] Add validation runner that launches from Planet A.
- [ ] Move or pilot ship toward Planet B.
- [ ] Assert ship leaves Planet A influence or active body changes.
- [ ] Assert ship enters Planet B influence.
- [ ] Assert ship gravity acceleration points toward Planet B while near Planet B.

Implementation note:

- Automated validation can use controlled input, direct positioning, or helper methods where full manual piloting would be brittle.
- The validation must still prove the runtime systems support the travel state transitions.

### Step 8: Validate Landing and Exit on Planet B

Checklist:

- [ ] In validation, place or guide ship near Planet B surface.
- [ ] Ensure ship can become landed on Planet B.
- [ ] Assert hatches become usable when landed.
- [ ] Stand from pilot seat.
- [ ] Exit through interior hatch.
- [ ] Assert player context is `OnFoot`.
- [ ] Assert player active gravity body is Planet B.
- [ ] Assert player can move on Planet B surface.

### Step 9: Update Main Scene and Setup Docs

Checklist:

- [ ] Set `project.godot` main scene to `Phase5TestWorld.tscn`.
- [ ] Add Phase 5 validation to `scripts/validate.sh`.
- [ ] Update `SETUP.md` main scene.
- [ ] Update `SETUP.md` validation list.
- [ ] Update controls if brake/match velocity is introduced.
- [ ] Add Phase 5 manual test steps.

### Step 10: Manual Test

Manual flow:

1. Start `Phase5TestWorld`.
2. Enter ship with `F`.
3. Sit with `F`.
4. Launch with `Space`.
5. Use the navigation marker/HUD to orient toward Planet B.
6. Use `W/S/A/D`, arrow keys, `Q/E`, `Space`, and `Left Shift` to travel.
7. Approach Planet B.
8. Slow down if brake/dampening exists.
9. Land on Planet B.
10. Stand with `F`.
11. Exit ship with `F`.
12. Walk on Planet B.

Manual acceptance:

- [ ] Planet B is findable.
- [ ] Travel is not confusing.
- [ ] Ship remains controllable away from Planet A.
- [ ] Gravity transition is understandable.
- [ ] Landing on Planet B is possible without debug-only actions.
- [ ] Standing and exiting after landing work.
- [ ] Player movement on Planet B feels coherent.

## 9. Automated Validation Plan

Add `Phase5ValidationRunner.cs`.

Suggested validation sequence:

1. Assert Planet A, Planet B, player, ship, hatches, and pilot seat exist.
2. Assert ship starts landed on Planet A.
3. Enter ship and sit.
4. Apply controlled takeoff input.
5. Assert ship becomes airborne.
6. Move ship along a controlled vector toward Planet B or apply travel input long enough to approach.
7. Assert target distance decreases.
8. Assert active gravity body becomes Planet B or gravity acceleration points to Planet B within influence radius.
9. Place or guide ship to a valid landed pose on Planet B if fully manual landing is too brittle.
10. Assert ship is landed and hatches can be used.
11. Stand and exit.
12. Assert player context is `OnFoot`.
13. Assert player is near Planet B surface.
14. Apply walking input and assert player moves on Planet B.

Important:

- The test may use helper methods for deterministic positioning only after proving travel/handoff.
- Do not require perfect free-flight piloting in automated validation. Manual testing owns subjective flight feel.

## 10. Success Criteria

Phase 5 is complete when:

- [ ] The main playable scene contains two reachable planets.
- [ ] The player can launch from Planet A.
- [ ] The player can navigate to Planet B using in-game UI.
- [ ] The ship can enter Planet B gravity.
- [ ] The player can land on Planet B.
- [ ] The player can stand and exit after landing.
- [ ] The player can walk on Planet B.
- [ ] Ship controls remain ship-local in open space.
- [ ] `F` interaction remains reliable.
- [ ] Phase 1 through Phase 5 validation passes from `scripts/validate.sh`.
- [ ] `SETUP.md` reflects the current scene, validation, and controls.

## 11. Risks

### Travel Feels Tedious

Risk:

- Planet B is too far away or ship thrust is too low.

Mitigation:

- Tune distance and thrust around a short first travel loop.
- Add HUD distance feedback early.

### Travel Feels Chaotic

Risk:

- Ship arrives too fast and landing becomes impossible.

Mitigation:

- Add `Control` brake/dampening while seated.
- Keep Planet B gravity strong enough to capture the ship.
- Increase landing tolerance temporarily if needed.

### Gravity Handoff Is Confusing

Risk:

- The active gravity body changes abruptly or at unintuitive locations.

Mitigation:

- Keep influence radii separated or clearly overlapping by design.
- Show current gravity body in the ship HUD.
- Defer blended gravity until the simpler model fails.

### Navigation Marker Becomes a UI Sink

Risk:

- Screen-space marker math and edge clamping consume too much time.

Mitigation:

- Start with text distance/direction in `ShipHud`.
- Add visual marker only after the data model works.

### Landing Detection Is Too Fragile

Risk:

- The current distance/speed/upright checks are hard to satisfy on Planet B.

Mitigation:

- Tune `LandingDistance`, `MaxLandedSpeed`, and gravity.
- Add a landing pad/zone only if surface landing is unreliable.

## 12. Recommended Implementation Order

1. Add Planet B scene.
2. Add Phase 5 test world.
3. Add target distance/current gravity readouts to `ShipHud`.
4. Tune travel distance and ship thrust.
5. Add brake/dampening if manual approach is too hard.
6. Add Phase 5 validation runner.
7. Add navigation marker if text readouts are insufficient.
8. Update setup docs and main scene.
9. Run automated validation.
10. Manual test the full launch-travel-land-exit loop.

## 13. Deferred Questions

- Should planets remain stationary through the vertical slice, or should authored orbital motion start in Phase 6 or later?
- Should ship travel eventually use mouse steering, keyboard-only steering, or a selectable mode?
- Should landing be freeform anywhere on a planet, or should early gameplay prefer authored landing pads?
- Should the navigation UI eventually be part of an in-cockpit instrument rather than a screen overlay?
- Should gravity eventually blend between bodies, or should dominant-body gravity remain a design constraint?
