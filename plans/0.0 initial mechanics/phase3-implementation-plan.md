# Phase 3 Implementation Plan: Ship Interior and Interaction

## 1. Phase Goal

Build the first version of the player's relationship with the ship before adding flight.

Phase 3 should let the player:

- Walk up to a placeholder ship.
- Interact with the hatch.
- Enter the ship interior without changing scenes.
- Walk inside the ship.
- Interact with the pilot seat.
- Sit at the controls.
- Stand back up.
- Exit through the hatch.

The ship does not fly in this phase. It is a stationary, landed prototype used to prove interaction, interior traversal, and player state transitions.

## 2. Current Project Reality

Phase 1 and Phase 2 established:

- Godot 4.6 C# project.
- `GravityService.tscn` autoload plus `GravityService.cs`.
- Spherical gravity walking.
- Jetpack, weak-gravity, and zero-g movement modes.
- `PlayerController.cs` owns movement, camera, resources, and debug state.
- `SuitHud` and `GravityDebugOverlay` read player debug properties.
- `scripts/validate.sh` runs build, import, Phase 1 validation, and Phase 2 validation.

Phase 3 should preserve all of that.

Important constraint:

- The current player controller has no interaction system. Phase 3 must add one.

## 3. Proposal Updates Needed

The proposal's Phase 3 description is still directionally correct, but it should eventually be updated with these implementation details:

- Add a reusable interaction system before ship-specific interactions.
- Treat the first ship as a stationary landed scene, not a physics body.
- Use same-scene interior/exterior transitions for Phase 3.
- Defer ship movement, ship gravity, landing gear simulation, and cockpit flight controls to Phase 4.
- Add automated validation for hatch, seat, stand, and exit transitions.

Do not merge Phase 4 concerns into Phase 3. Sitting in the pilot seat should not imply the ship can fly yet.

## 4. Scope

### In Scope

- Interaction input action.
- Interaction raycast from the player camera.
- Interaction prompt UI.
- Reusable interactable contract.
- Placeholder ship scene.
- Walkable ship interior.
- Hatch enter/exit interaction.
- Pilot seat interaction.
- Seated player state.
- Basic cockpit UI placeholder.
- Exterior and interior spawn markers.
- Phase 3 test world.
- Phase 3 automated validation.
- Updates to `scripts/validate.sh`.

### Out of Scope

- Ship flight.
- Ship physics.
- Ship damage.
- Ship fuel.
- Ship takeoff/landing.
- Moving interior reference frames.
- Artificial gravity inside a moving ship.
- Detailed ship art.
- Real cockpit instruments.
- Saving ship state.

## 5. Design Decisions

### Interaction Model

Use a simple raycast interaction system from the player camera.

Reasons:

- First-person interaction should feel direct.
- It works for hatches, seats, buttons, tools, and future clues.
- It keeps interaction separate from movement.

Initial behavior:

- Raycast from camera center.
- If the ray hits an interactable, show a prompt.
- Press `interact` to trigger it.

Recommended input:

- `E`: interact.

### Interactable Contract

Use a C# interface for code clarity:

```csharp
public interface IInteractable
{
    string GetPrompt(PlayerController player);
    bool CanInteract(PlayerController player);
    void Interact(PlayerController player);
}
```

Godot nodes that implement this:

- `ShipHatch`
- `PilotSeat`

Practical Godot note:

- The interaction raycast should walk up the hit node's parent chain until it finds a node implementing `IInteractable`.
- This avoids requiring the exact collision child to own the script.

### Player State

Add a separate player context enum, distinct from movement mode:

```csharp
public enum PlayerContext
{
    OnFoot,
    InShipInterior,
    Seated
}
```

This should not replace `PlayerMovementMode`.

Responsibilities:

- Movement mode describes physics movement: surface, airborne, weak gravity, zero-g.
- Player context describes interaction/control state: on foot, inside ship, seated.

Phase 3 rules:

- `OnFoot`: normal movement.
- `InShipInterior`: normal movement, but ship interaction prompts are available.
- `Seated`: movement disabled, camera remains active, cockpit UI visible.

### Ship Representation

Use a stationary ship scene for Phase 3.

Root:

- `Node3D` named `Ship`

Children:

- Exterior placeholder mesh.
- Interior floor/walls collision.
- Hatch interactable.
- Pilot seat interactable.
- Interior spawn marker.
- Exterior exit marker.
- Seat camera/anchor marker.
- Cockpit UI anchor or screen.

Do not use `RigidBody3D` yet. Phase 4 owns ship physics.

### Interior Transition

Use same-scene teleport markers for Phase 3:

- Enter hatch moves player to `InteriorSpawn`.
- Exit hatch moves player to `ExteriorExit`.

Reasoning:

- It proves state transitions and interior navigation without needing final ship geometry.
- It avoids fragile collision doorway work before ship layout exists.
- It still keeps the world in one scene.

Later:

- Replace teleport hatch with physically walkable airlock/door if desired.

### Seated Transition

Sitting should:

- Store the player's previous transform.
- Move player to a seat anchor.
- Disable walking/jetpack input.
- Show cockpit UI.
- Allow `interact` or `cancel` to stand.

Standing should:

- Move player to `SeatExit`.
- Re-enable movement.
- Hide cockpit UI.

No ship controls in Phase 3.

## 6. New Files

### Interaction

- `res://scripts/interaction/IInteractable.cs`
- `res://scripts/interaction/PlayerInteractionController.cs`
- `res://scenes/ui/InteractionPrompt.tscn`
- `res://scripts/ui/InteractionPrompt.cs`

### Ship

- `res://scenes/ship/Ship.tscn`
- `res://scripts/ship/ShipHatch.cs`
- `res://scripts/ship/PilotSeat.cs`
- `res://scripts/ship/ShipInteriorState.cs` if needed.
- `res://scenes/ui/CockpitPlaceholder.tscn`
- `res://scripts/ui/CockpitPlaceholder.cs`

### Test and Validation

- `res://scenes/solar_system/Phase3TestWorld.tscn`
- `res://scenes/solar_system/Phase3Validation.tscn`
- `res://scripts/debug/Phase3ValidationRunner.cs`

## 7. Existing Files to Modify

### `project.godot`

Add input actions:

- `interact`: `E`
- `cancel`: `Esc` or a distinct key if `Esc` remains mouse capture toggle.

Recommendation:

- Use `E` for interact.
- Keep `Esc` as mouse capture toggle for now.
- Let seated exit use `interact` again to avoid overloading `Esc`.

### `Player.tscn`

Add:

- `RayCast3D` under `ViewPivot/Camera3D` or under `ViewPivot`.
- `PlayerInteractionController.cs` attached to a child node or the player root.

Recommended structure:

```text
Player
  CollisionShape3D
  ViewPivot
    Camera3D
      InteractionRayCast3D
  InteractionController
```

### `PlayerController.cs`

Add:

- `PlayerContext` state.
- Debug property for context.
- Methods:
  - `SetContext(PlayerContext context)`
  - `MoveToTransform(Transform3D transform)`
  - `SetMovementEnabled(bool enabled)`
  - `SetLookEnabled(bool enabled)` if needed.

Do not bury ship-specific logic in `PlayerController`.

### `GravityDebugOverlay.cs`

Add:

- Player context.
- Current interactable prompt if useful.

### `SuitHud.tscn`

No required change, unless seated state should hide or dim suit HUD.

### `scripts/validate.sh`

Add:

```bash
echo "Running Phase 3 automated validation"
"${GODOT_BIN}" --headless --path . scenes/solar_system/Phase3Validation.tscn
```

## 8. Scene Details

### Ship.tscn

Root:

- `Node3D` named `Ship`

Suggested children:

```text
Ship
  Exterior
    MeshInstance3D
  Interior
    StaticBody3D
      FloorCollision
      WallCollisions
      FloorMesh
      WallMeshes
  HatchExterior
    Area3D or StaticBody3D
    ShipHatch.cs
  HatchInterior
    Area3D or StaticBody3D
    ShipHatch.cs
  PilotSeat
    Area3D or StaticBody3D
    PilotSeat.cs
  Markers
    InteriorSpawn
    ExteriorExit
    SeatAnchor
    SeatExit
```

Placeholder geometry:

- Use Godot primitive meshes.
- Use simple collision boxes.
- Use high-contrast materials so interior/exterior orientation is clear.

Ship placement:

- Place ship on the Phase 3 planet surface near the player spawn.
- Do not worry about perfect curved-surface alignment yet.
- Use a relatively flat surface region near the north pole.

### InteractionPrompt.tscn

Use:

- `CanvasLayer`
- `PanelContainer`
- `Label`

Behavior:

- Hidden when no interactable is targeted.
- Shows text like:
  - `E Enter Ship`
  - `E Exit Ship`
  - `E Sit`
  - `E Stand`

### CockpitPlaceholder.tscn

Use:

- `CanvasLayer`
- `PanelContainer`
- `Label`

Behavior:

- Hidden unless seated.
- Shows simple state text:
  - `PILOT SEAT`
  - `E Stand`
  - `Flight controls offline`

Do not add real ship controls yet.

## 9. Implementation Steps

### Step 1: Add Input

Checklist:

- [ ] Add `interact` action bound to `E`.
- [ ] Confirm existing `Esc` mouse capture still works.
- [ ] Update `SETUP.md` controls.

### Step 2: Add Player Context

Checklist:

- [ ] Add `PlayerContext` enum.
- [ ] Add `_playerContext` field.
- [ ] Add debug property.
- [ ] Add movement-enable flag.
- [ ] Gate walking, jumping, jetpack, and zero-g thrust when seated.
- [ ] Keep look enabled while seated unless testing shows it is disorienting.
- [ ] Run Phase 1 and Phase 2 validation.

### Step 3: Add Interaction Contract

Checklist:

- [ ] Create `IInteractable.cs`.
- [ ] Create `PlayerInteractionController.cs`.
- [ ] Add raycast reference.
- [ ] Find interactables from raycast collision.
- [ ] Show prompt when target is valid.
- [ ] Call `Interact(player)` on `interact`.

### Step 4: Add Interaction Prompt UI

Checklist:

- [ ] Create `InteractionPrompt.tscn`.
- [ ] Create `InteractionPrompt.cs`.
- [ ] Add prompt to Phase 3 scene.
- [ ] Connect prompt text to `PlayerInteractionController`.

### Step 5: Build Placeholder Ship

Checklist:

- [ ] Create `Ship.tscn`.
- [ ] Add exterior placeholder mesh.
- [ ] Add walkable interior floor.
- [ ] Add simple walls/collision.
- [ ] Add visible hatch points.
- [ ] Add pilot seat placeholder.
- [ ] Add markers for interior spawn, exterior exit, seat anchor, and seat exit.

### Step 6: Implement Hatch Interaction

Checklist:

- [ ] Create `ShipHatch.cs`.
- [ ] Support exterior hatch mode: enter ship.
- [ ] Support interior hatch mode: exit ship.
- [ ] Move player to correct marker.
- [ ] Set player context to `InShipInterior` or `OnFoot`.
- [ ] Ensure movement remains enabled after transition.

### Step 7: Implement Pilot Seat Interaction

Checklist:

- [ ] Create `PilotSeat.cs`.
- [ ] Allow sitting only while in ship interior.
- [ ] Move player to seat anchor.
- [ ] Set context to `Seated`.
- [ ] Disable movement/jetpack.
- [ ] Show cockpit placeholder UI.
- [ ] Pressing interact again stands up.
- [ ] Move player to seat exit.
- [ ] Restore context to `InShipInterior`.

### Step 8: Create Phase 3 Test World

Checklist:

- [ ] Create `Phase3TestWorld.tscn`.
- [ ] Instance Phase 2 planet/player/HUD/debug setup.
- [ ] Add `Ship.tscn` near player spawn.
- [ ] Add interaction prompt.
- [ ] Add cockpit placeholder.
- [ ] Set main scene to Phase 3 after validation passes.

### Step 9: Add Automated Validation

Checklist:

- [ ] Create `Phase3Validation.tscn`.
- [ ] Create `Phase3ValidationRunner.cs`.
- [ ] Validate Phase 1 and Phase 2 still pass through `scripts/validate.sh`.
- [ ] Validate hatch enter moves player to interior marker.
- [ ] Validate player context becomes `InShipInterior`.
- [ ] Validate seat interaction moves player to seat anchor.
- [ ] Validate context becomes `Seated`.
- [ ] Validate movement is disabled while seated.
- [ ] Validate stand interaction restores context to `InShipInterior`.
- [ ] Validate hatch exit moves player to exterior marker.
- [ ] Validate context becomes `OnFoot`.
- [ ] Update `scripts/validate.sh`.

## 10. Acceptance Test Checklist

Phase 3 is complete when:

- [ ] Phase 1 validation passes.
- [ ] Phase 2 validation passes.
- [ ] Phase 3 validation passes.
- [ ] Player can walk to the ship.
- [ ] Interaction prompt appears at the exterior hatch.
- [ ] Pressing `E` enters the ship.
- [ ] Player can walk inside the ship.
- [ ] Interaction prompt appears at the pilot seat.
- [ ] Pressing `E` sits in the pilot seat.
- [ ] Player movement is disabled while seated.
- [ ] Cockpit placeholder UI appears while seated.
- [ ] Pressing `E` stands up.
- [ ] Player can walk to the interior hatch.
- [ ] Pressing `E` exits the ship.
- [ ] Context/debug state is readable in the debug overlay.
- [ ] No script errors appear during validation or manual testing.

Manual playtest checks:

- [ ] It is obvious where the hatch is.
- [ ] Entering/exiting does not feel jarring.
- [ ] Ship interior scale feels plausible.
- [ ] Seat interaction is understandable.
- [ ] Mouse look while seated feels acceptable.
- [ ] Jetpack does not interfere with hatch/seat interactions.

## 11. Known Technical Questions

Resolve during Phase 3:

- Should the hatch be a teleport interaction for longer, or should Phase 4 require a physically walkable door?
- Should seated mode allow free mouse look or lock the camera forward?
- Should ship interior use planet gravity for now, or should it eventually have ship-local gravity?
- Should interaction prompts belong to the player or the world UI?
- Should `PlayerController` own context state, or should a separate `PlayerState` component own it?

Recommended answers for Phase 3:

- Use teleport hatch.
- Allow limited/free mouse look while seated.
- Use planet gravity for now because the ship is stationary.
- Let the player interaction controller own prompt targeting.
- Keep context state in `PlayerController` for now, but do not add ship-specific methods there.

## 12. Risks

### PlayerController Growth

Risk:

- The player controller may become too broad.

Mitigation:

- Put raycast targeting in `PlayerInteractionController`.
- Put hatch behavior in `ShipHatch`.
- Put seat behavior in `PilotSeat`.
- Keep `PlayerController` limited to movement/context primitives.

### Interaction Ambiguity

Risk:

- The player may target the wrong object inside a small ship.

Mitigation:

- Use clear prompt text.
- Use short interaction ranges.
- Keep hatch and seat collision shapes distinct.

### Ship Interior Scale

Risk:

- Placeholder interior may feel cramped or confusing.

Mitigation:

- Start oversized.
- Use visible color/material differences.
- Tune after manual testing.

## 13. Recommended Implementation Order

1. Add `interact` input.
2. Add `PlayerContext` and movement gating.
3. Add interaction raycast and prompt UI.
4. Add placeholder ship scene.
5. Add hatch interaction.
6. Add pilot seat interaction.
7. Add cockpit placeholder UI.
8. Add Phase 3 test scene.
9. Add Phase 3 validation.
10. Update `scripts/validate.sh`.
11. Set Phase 3 test world as main scene.
12. Manual playtest and tune.

Do not start ship physics until Phase 3 validation and manual seat/hatch testing are stable.

## 14. Implementation Verification

Implemented files include:

- `res://scripts/interaction/IInteractable.cs`
- `res://scripts/interaction/PlayerInteractionController.cs`
- `res://scenes/ui/InteractionPrompt.tscn`
- `res://scripts/ui/InteractionPrompt.cs`
- `res://scenes/ship/Ship.tscn`
- `res://scripts/ship/ShipHatch.cs`
- `res://scripts/ship/PilotSeat.cs`
- `res://scenes/ui/CockpitPlaceholder.tscn`
- `res://scripts/ui/CockpitPlaceholder.cs`
- `res://scenes/solar_system/Phase3TestWorld.tscn`
- `res://scenes/solar_system/Phase3Validation.tscn`
- `res://scripts/debug/Phase3ValidationRunner.cs`
- Updated `res://scenes/player/Player.tscn`
- Updated `res://scenes/player/PlayerController.cs`
- Updated `res://scripts/debug/GravityDebugOverlay.cs`
- Updated `res://scripts/validate.sh`

Validation command:

```bash
scripts/validate.sh
```

Automated validation currently checks:

- Phase 1 and Phase 2 validation still pass.
- Player starts on foot.
- Exterior hatch can be used while on foot.
- Exterior hatch moves player into the ship.
- Player context becomes `InShipInterior`.
- Pilot seat can be used inside the ship.
- Sitting moves the player to the seat anchor.
- Player context becomes `Seated`.
- Movement and jetpack input do not move the player while seated.
- Standing restores `InShipInterior`.
- Interior hatch exits the ship.
- Player context returns to `OnFoot`.
