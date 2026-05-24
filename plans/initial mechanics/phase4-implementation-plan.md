# Phase 4 Implementation Plan: Ship Takeoff and Local Flight

## 1. Phase Goal

Prove that the player can sit in the ship, take off from the first planet, fly locally around that planet, land, stand up, and exit.

This phase is about **one-planet ship flight**. It is not about flying to another planet yet. Phase 5 owns interplanetary travel, navigation markers, travel scale, and second-body approach/landing.

Phase 4 should deliver:

- Physics-driven ship movement.
- Gravity influence on the ship.
- Seated piloting state.
- Takeoff from the current planet.
- Local flight around the planet.
- Basic landing detection.
- Hatch lockout while airborne.
- Exit after landing.
- Automated validation proving the ship can become piloted, receive thrust, move, and return to an exit-capable landed state.

## 2. Current Project Reality

Phase 3 established:

- `Ship.tscn` is a stationary `Node3D` placeholder.
- Player enters/exits through `ShipHatch`.
- Player can sit/stand via `PilotSeat`.
- Player context is tracked in `PlayerController` as:
  - `OnFoot`
  - `InShipInterior`
  - `Seated`
- Movement and jetpack are disabled while seated.
- `ShipInteriorVolume` resets context to `OnFoot` if the player leaves the interior without using the hatch.
- `CockpitPlaceholder` is shown while seated.
- `scripts/validate.sh` runs Phase 1, Phase 2, and Phase 3 validation.

Phase 4 should build on this rather than replacing it wholesale.

Important constraint:

- The current ship root is not a physics body. Phase 4 must introduce a physics-driven ship while preserving Phase 3 hatch/seat behavior.

## 3. Proposal Updates Needed

The proposal's Phase 4 direction is still correct, but implementation should clarify:

- Phase 4 uses a single landed ship on one planet.
- Ship flight is enabled only while the player is seated.
- Ship hatches are usable only when the ship is landed.
- While flying, the player remains locked to the pilot seat.
- Ship interior walking while the ship is in motion is deferred.
- Interplanetary navigation and second-planet landing remain Phase 5.

## 4. Scope

### In Scope

- Refactor `Ship.tscn` to support physics-driven movement.
- Add `ShipController.cs`.
- Add ship piloting state.
- Add thrust controls.
- Add rotation controls.
- Apply custom gravity from `GravityService` to ship.
- Keep seated player aligned to the seat anchor while piloting.
- Add landed/airborne state.
- Disable hatch exit while airborne.
- Add landing assist/debug indicators.
- Add Phase 4 test world.
- Add Phase 4 automated validation.
- Update `scripts/validate.sh`.

### Out of Scope

- Flying to another planet.
- Navigation markers.
- Match velocity assist.
- Ship damage.
- Ship fuel.
- Ship repair.
- Full cockpit instruments.
- Walking inside the ship while it is moving.
- Artificial ship gravity.
- Floating origin.
- Save/load.

## 5. Design Decisions

### Ship Physics Structure

Use `RigidBody3D` for the ship's physical root.

Recommended structure:

```text
Ship
  RigidBody3D or root converted to RigidBody3D
    CollisionShape3D
    ExteriorHull
    Interior
    Hatch nodes
    PilotSeat
    Markers
    ShipController.cs
```

Preferred implementation:

- Convert `Ship.tscn` root from `Node3D` to `RigidBody3D`.
- Attach `ShipController.cs` to the root.
- Keep existing child nodes and markers.

Reasoning:

- The whole ship should move as one physics object.
- Child markers naturally move with the ship.
- The seated player can be snapped to the moving `SeatAnchor`.

Alternative:

- Add a `RigidBody3D` child under the existing root.

Avoid this unless root conversion becomes painful. A nested physics body makes transform ownership more confusing.

### Player While Piloting

Phase 4 rule:

- The player must be seated to pilot.
- While seated and the ship is airborne, player movement remains disabled.
- The player's transform should be kept at `SeatAnchor` every physics frame.

Implementation options:

1. `ShipController` stores the active seated player and updates their transform to the seat anchor.
2. `PilotSeat` stores the active player and updates them.

Recommendation:

- Use `ShipController` for active pilot tracking.
- `PilotSeat` should call `ship.SetPilot(player)` when sitting and `ship.ClearPilot(player)` when standing.

### Hatch Lockout

Hatches should only work while landed.

Rules:

- Exterior hatch can enter only if ship is landed.
- Interior hatch can exit only if ship is landed.
- If airborne, prompt should say `Ship Airborne` or show no prompt.

Implementation:

- `ShipHatch` gets a reference to `ShipController`.
- `ShipHatch.CanInteract` returns false when `!ShipController.IsLanded`.
- Prompt can return a disabled message if we decide to show disabled prompts.

### Flight Controls

Use simple controls first. Do not overfit to final ship feel.

Recommended seated controls:

- `W`: forward thrust.
- `S`: reverse thrust.
- `A`: yaw left.
- `D`: yaw right.
- Mouse Y: pitch.
- `Q`: roll left.
- `R`: roll right.
- `Left Shift`: upward/landing thrust.
- `Control`: downward thrust.
- `Space`: brake/dampen velocity.
- `E`: stand, only if landed.

Notes:

- `E` already means interact. Keep it as stand/interact.
- `Left Shift` and `Control` currently drive jetpack/brake outside the ship. Reuse them as vertical ship thrust while seated.
- Mouse X can either yaw the ship or remain camera look. Start with keyboard yaw and mouse pitch only if simpler; revise after testing.

Input actions to add:

- `ship_roll_left`
- `ship_roll_right`
- `ship_brake`

Existing movement inputs can be reused while seated:

- `move_forward`
- `move_back`
- `move_left`
- `move_right`
- `jetpack`
- `brake`

### Ship Gravity

Use the existing `GravityService`.

Implementation:

- Each physics frame, ship queries gravity acceleration at its global position.
- Apply gravity to the `RigidBody3D`.
- Ship should not use Godot global gravity.

Initial gravity behavior:

- Same constant acceleration inside the planet's influence radius as the player.
- Do not add orbital mechanics or falloff yet.

### Landing Detection

Use a simple landing model:

- Ship has one or more downward raycasts.
- Down direction is current gravity direction.
- Landed if:
  - At least one landing ray is close to surface.
  - Ship speed is below threshold.
  - Ship is roughly upright relative to local gravity up.

Initial thresholds:

- Max landed speed: `3.0`.
- Max landing distance: `2.0`.
- Min upright dot: `0.65`.

Add debug output:

- `IsLanded`
- `IsPiloted`
- ship speed
- altitude/surface distance
- gravity acceleration

### Landing Assist

Phase 4 should include basic debug/assist, not a full autopilot.

Add:

- Landing status text.
- Speed readout.
- Altitude readout.
- Upright indicator.

Optional:

- Strong damping when `ship_brake` is held.

## 6. New Files

### Ship

- `res://scripts/ship/ShipController.cs`
- `res://scenes/ui/ShipHud.tscn`
- `res://scripts/ui/ShipHud.cs`

### Test and Validation

- `res://scenes/solar_system/Phase4TestWorld.tscn`
- `res://scenes/solar_system/Phase4Validation.tscn`
- `res://scripts/debug/Phase4ValidationRunner.cs`

## 7. Existing Files to Modify

### `Ship.tscn`

Modify:

- Convert root to `RigidBody3D`.
- Add ship collision suitable for landing.
- Add `ShipController.cs`.
- Add landing raycasts or marker/raycast nodes.
- Keep existing hatch, seat, cockpit, and interior nodes.

Risk:

- Existing interior collisions may behave differently when under a `RigidBody3D`.

Mitigation:

- Keep Phase 3 validation passing.
- If interior walking becomes unstable, freeze ship while not piloted and keep walking tests limited to landed state.

### `PilotSeat.cs`

Modify:

- Add `ShipController` reference.
- On sit: call `ShipController.SetPilot(player)`.
- On stand: call `ShipController.ClearPilot(player)`.
- Allow standing only when ship is landed.

### `ShipHatch.cs`

Modify:

- Add `ShipController` reference.
- Allow enter/exit only when ship is landed.
- Return prompt text appropriate to landed/airborne state.

### `PlayerController.cs`

Modify only if needed:

- Add method to allow an external system to keep seated player anchored.
- Avoid adding ship input handling to `PlayerController`.

Recommended:

```csharp
public void ForceSeatTransform(Transform3D seatTransform)
{
    if (_playerContext == PlayerContext.Seated)
    {
        MoveToTransform(seatTransform);
    }
}
```

### `GravityDebugOverlay.cs`

Optional:

- Add ship state if a ship path is assigned.

### `SETUP.md`

Update controls after implementation.

### `scripts/validate.sh`

Add:

```bash
echo "Running Phase 4 automated validation"
"${GODOT_BIN}" --headless --path . scenes/solar_system/Phase4Validation.tscn
```

## 8. ShipController Design

Expected exported values:

```csharp
[Export] public float MainThrust { get; set; } = 45.0f;
[Export] public float ReverseThrust { get; set; } = 25.0f;
[Export] public float VerticalThrust { get; set; } = 35.0f;
[Export] public float YawTorque { get; set; } = 18.0f;
[Export] public float PitchTorque { get; set; } = 18.0f;
[Export] public float RollTorque { get; set; } = 14.0f;
[Export] public float BrakeStrength { get; set; } = 8.0f;
[Export] public float MaxLandedSpeed { get; set; } = 3.0f;
[Export] public float LandingRayLength { get; set; } = 3.0f;
[Export] public float MinLandingUpDot { get; set; } = 0.65f;
```

Runtime state:

```csharp
private PlayerController? _pilot;
private bool _isLanded;
private Vector3 _lastGravityAcceleration;
```

Public debug properties:

```csharp
public bool IsPiloted { get; }
public bool IsLanded { get; }
public float Speed { get; }
public Vector3 GravityAcceleration { get; }
```

Core methods:

```csharp
public void SetPilot(PlayerController player);
public void ClearPilot(PlayerController player);
public bool CanExitShip();
```

Physics loop:

1. Query gravity.
2. Apply gravity force.
3. Update landed state.
4. If piloted, apply thrust/torque input.
5. If piloted, keep player at seat anchor.

## 9. Phase 4 Test Scene

Create `Phase4TestWorld.tscn`.

Contents:

- First planet.
- Player.
- Physics-enabled ship near player spawn.
- Suit HUD.
- Ship HUD.
- Debug overlay.
- Interaction prompt.

Starting state:

- Player starts outside ship.
- Ship starts landed.
- Player can enter, sit, take off, land, stand, and exit.

Do not include second planet yet.

## 10. Phase 4 Validation

Create `Phase4Validation.tscn` and `Phase4ValidationRunner.cs`.

Automated validation should check:

- Phase 3 enter/sit flow still works.
- Sitting sets ship pilot.
- Ship starts landed.
- Hatch exit is allowed while landed.
- Applying takeoff thrust changes ship velocity/position.
- Ship becomes airborne after thrust.
- Player remains seated and follows `SeatAnchor` while ship moves.
- Hatch exit is not allowed while airborne.
- Test can force or simulate a landed state.
- After returning to landed state, standing/exiting works.

Important:

- Automated landing can be hard with real physics. It is acceptable for validation to use a controlled helper method or test-only positioning to place the ship back in a landed state, as long as manual landing is still tested.

Recommended validation structure:

1. Enter ship.
2. Sit.
3. Apply thrust for several physics frames.
4. Assert ship moved and is airborne.
5. Assert player stayed seated at seat anchor.
6. Assert interior hatch cannot exit while airborne.
7. Move ship to a safe landed pose or let it settle if reliable.
8. Assert landed.
9. Stand.
10. Exit ship.

## 11. Acceptance Test Checklist

Phase 4 is complete when:

- [ ] Phase 1 validation passes.
- [ ] Phase 2 validation passes.
- [ ] Phase 3 validation passes.
- [ ] Phase 4 validation passes.
- [ ] Player can enter ship.
- [ ] Player can sit in pilot seat.
- [ ] Ship accepts pilot controls only while seated.
- [ ] Ship takes off from the planet.
- [ ] Ship is affected by planet gravity.
- [ ] Ship can fly around the local planet.
- [ ] Ship can land at low speed.
- [ ] Hatch cannot be used while airborne.
- [ ] Player remains seated during flight.
- [ ] Player can stand and exit after landing.
- [ ] Ship HUD/debug info is readable.
- [ ] No script errors appear during validation.

Manual playtest checks:

- [ ] Takeoff feels understandable.
- [ ] Rotation controls are not disorienting.
- [ ] Landing is possible without extreme precision.
- [ ] Brake/damping behavior is useful but not overpowered.
- [ ] Ship does not jitter heavily on the surface.
- [ ] Player camera remains stable while seated.

## 12. Known Technical Questions

Resolve during Phase 4:

- Should mouse control rotate the ship, the camera, or both while seated?
- Should the ship use `Freeze`/sleeping while landed and unpiloted?
- Should landing use physical collision alone or raycast-assisted state?
- How much damping should the ship have by default?
- Should the player be parented to the ship while seated, or continuously snapped to the seat anchor?
- Should ship interior walking while landed remain supported after converting the ship root to `RigidBody3D`?

Recommended Phase 4 answers:

- Use simple keyboard rotation first; add mouse ship rotation only if needed.
- Freeze or heavily damp the ship while landed and unpiloted if surface jitter appears.
- Use raycast-assisted landed state.
- Snap seated player to the seat anchor every physics frame.
- Keep interior walking supported only while landed.

## 13. Risks

### RigidBody Interior Complexity

Risk:

- A moving physics ship with walkable interior can become unstable.

Mitigation:

- Do not support walking inside while airborne.
- Keep player seated during flight.
- Keep ship stationary or frozen while not piloted and landed.

### Control Feel

Risk:

- Ship controls may feel awkward or hard to land.

Mitigation:

- Start with conservative thrust and torque.
- Add brake/damping early.
- Tune around manual landing rather than physical realism.

### Phase Creep

Risk:

- Local flight can expand into interplanetary flight.

Mitigation:

- No second planet in Phase 4.
- No navigation markers.
- No match velocity assist unless landing is impossible without it.

## 14. Recommended Implementation Order

1. Add ship input actions.
2. Convert `Ship.tscn` root to `RigidBody3D`.
3. Add `ShipController.cs` with gravity and landed state only.
4. Update hatch/seat scripts to reference ship landed/pilot state.
5. Keep Phase 3 validation passing.
6. Add piloted thrust controls.
7. Add seated player seat-anchor following.
8. Add ship HUD/debug info.
9. Add Phase 4 test scene.
10. Add Phase 4 validation.
11. Set Phase 4 test world as main scene after validation passes.
12. Manual playtest takeoff, local flight, landing, stand, exit.

Do not start Phase 5 until a player can reliably take off, fly around the first planet, land, stand up, and exit.

## 15. Implementation Verification

Implemented files include:

- `res://scripts/ship/ShipController.cs`
- `res://scenes/ui/ShipHud.tscn`
- `res://scripts/ui/ShipHud.cs`
- `res://scenes/solar_system/Phase4TestWorld.tscn`
- `res://scenes/solar_system/Phase4Validation.tscn`
- `res://scripts/debug/Phase4ValidationRunner.cs`
- Updated `res://scenes/ship/Ship.tscn`
- Updated `res://scripts/ship/ShipHatch.cs`
- Updated `res://scripts/ship/PilotSeat.cs`
- Updated `res://scenes/player/PlayerController.cs`
- Updated `res://scripts/validate.sh`

Validation command:

```bash
scripts/validate.sh
```

Automated validation currently checks:

- Phase 1, Phase 2, and Phase 3 validations still pass.
- Ship starts landed.
- Exterior hatch works while landed.
- Player can enter and sit.
- Sitting assigns an active ship pilot.
- Up thrust moves the ship.
- Ship becomes airborne.
- Interior hatch cannot exit while airborne.
- Player remains seated and follows the moving seat anchor.
- Test can return the ship to landed state.
- Player can stand and exit after landing.
- Ship clears active pilot after standing.

Manual playtest focus:

- Tune thrust and torque values.
- Check whether the ship rises too fast from `Left Shift`.
- Check whether keyboard yaw/roll are understandable.
- Verify hatch lockout while airborne is clear enough.
- Validate landing feel; automated landing is intentionally assisted for now.
