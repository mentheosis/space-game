# Phase 1 Implementation Plan: Spherical Gravity Walking Prototype

## 1. Phase Goal

Prove that a first-person player can walk, jump, fall, and recover on a small spherical planet using custom gravity in Godot.

This phase is not about art, story, ship travel, procedural planets, or a complete movement suite. It is about validating the hardest early foundation: gravity-aligned walking on a curved world.

Success means:

- The player can walk around an entire spherical planet.
- The player's feet remain oriented toward the planet surface.
- Jumping and falling feel consistent.
- The camera stays readable and does not roll unpredictably.
- The prototype gives enough confidence to build jetpack and ship systems on top of it.

## 2. Prerequisites

Phase 1 assumes Phase 0 has produced:

- A Godot 4.6 C# project.
- A committed folder structure.
- A runnable main scene.
- Input actions for movement, camera, jump, sprint/debug, and pause.
- Basic project settings for 3D rendering and physics.
- Local Linux and macOS development/export assumptions. Docker build automation is intentionally deferred.

If Phase 0 is not complete, finish the minimum setup first. Phase 1 should not spend time on menus, save systems, art direction, or general game structure beyond what is needed to test movement.

## 3. Deliverables

Required scenes:

- `res://scenes/player/Player.tscn`
- `res://scenes/planets/PlanetBody.tscn`
- `res://scenes/solar_system/Phase1TestWorld.tscn`

Required C# scripts:

- `res://scripts/components/GravityBody.cs`
- `res://autoload/GravityService.cs`
- `res://scenes/player/PlayerController.cs`
- `res://scripts/debug/GravityDebugOverlay.cs`

Optional scripts:

- `res://scripts/components/PlanetSpawnPoint.cs`
- `res://scripts/debug/DebugLineDrawer.cs`

Required prototype content:

- One spherical planet.
- One spawn point on the planet surface.
- One visible landmark on the planet so movement around the sphere is easy to judge.
- Debug display showing active gravity body, gravity vector, speed, grounded state, and up vector.

## 4. Scene Design

### Phase1TestWorld.tscn

Root:

- `Node3D` named `Phase1TestWorld`

Children:

- `PlanetBody`
- `Player`
- `DirectionalLight3D`
- `WorldEnvironment`
- Optional debug geometry

Responsibilities:

- Own the test setup.
- Place the player at a known surface spawn.
- Keep the scene simple enough to diagnose movement bugs.

### PlanetBody.tscn

Root:

- `StaticBody3D` or `Node3D` named `PlanetBody`

Children:

- `MeshInstance3D` using a sphere mesh.
- `CollisionShape3D` using a sphere shape.
- `GravityBody` script.
- `Marker3D` spawn point on the surface.
- Landmark mesh, such as a tower, arch, colored pillar, or ring.

Initial values:

- Radius: `50.0`
- Surface gravity: `24.0`
- Influence radius: `250.0`
- Priority: `0`

Notes:

- A 50-meter radius is small enough to quickly test curved walking but large enough to avoid absurd camera rotation every few steps.
- The exact values should be tuned during playtesting.

### Player.tscn

Root:

- `CharacterBody3D` named `Player`

Children:

- `CollisionShape3D` using a capsule.
- `Node3D` named `ViewPivot`
- `Camera3D` under `ViewPivot`
- Optional `RayCast3D` for future interactions and ground checks.

Initial values:

- Capsule height: roughly `1.8`
- Capsule radius: roughly `0.35`
- Camera local height: roughly `0.7` to `0.8` above the capsule center depending on final capsule setup.
- Mouse sensitivity configurable through exported variables.

## 5. Core Systems

### GravityBody.cs

Purpose:

- Represent one source of custom gravity.

Responsibilities:

- Expose radius, surface gravity, influence radius, and priority.
- Register with `GravityService` when entering the scene tree.
- Unregister from `GravityService` when exiting the scene tree.
- Return gravity direction and acceleration for a world position.

Expected API:

```csharp
public partial class GravityBody : Node3D
{
    [Export] public float Radius { get; set; } = 50.0f;
    [Export] public float SurfaceGravity { get; set; } = 24.0f;
    [Export] public float InfluenceRadius { get; set; } = 250.0f;
    [Export] public int Priority { get; set; } = 0;

    public bool ContainsPoint(Vector3 worldPosition);
    public Vector3 GetGravityDirection(Vector3 worldPosition);
    public Vector3 GetGravityAcceleration(Vector3 worldPosition);
    public float GetDistanceToSurface(Vector3 worldPosition);
}
```

Gravity convention:

- Gravity direction points from the affected object toward the gravity body's center.
- Player up direction is the opposite of gravity direction.

### GravityService.cs

Purpose:

- Provide a central query point for custom gravity.

Responsibilities:

- Store active `GravityBody` instances.
- Find the best gravity body for a world position.
- Return gravity acceleration, gravity direction, and up direction.
- Support debug inspection of the current gravity choice.

Selection rule for Phase 1:

- Use the closest body whose influence radius contains the query point.
- If multiple bodies contain the point, choose highest priority.
- If priority ties, choose closest surface distance.

Expected API:

```csharp
public partial class GravityService : Node
{
    public static GravityService Instance { get; private set; }

    public void Register(GravityBody body);
    public void Unregister(GravityBody body);
    public GravityBody GetBestBody(Vector3 worldPosition);
    public Vector3 GetGravityAcceleration(Vector3 worldPosition);
    public Vector3 GetGravityDirection(Vector3 worldPosition);
    public Vector3 GetUpDirection(Vector3 worldPosition);
}
```

Autoload:

- Add `GravityService.cs` as a Godot autoload named `GravityService`.

### PlayerController.cs

Purpose:

- Drive first-person movement on a spherical surface.

Responsibilities:

- Read movement and look input.
- Query gravity every physics frame.
- Align the player's local up axis to the gravity up direction.
- Project movement onto the tangent plane of the planet.
- Apply falling and jumping along the current up direction.
- Call `MoveAndSlide`.
- Keep camera pitch independent from body alignment.

Movement model:

- `CharacterBody3D.Velocity` stores world-space velocity.
- Gravity modifies velocity along the gravity direction.
- Horizontal movement is calculated along the tangent plane.
- Jump impulse is applied along the local up direction.

Important rules:

- Do not assume `Vector3.Up` means player up.
- Do not use global Y as the jump axis.
- Do not let camera pitch control the gravity alignment.
- Avoid abrupt roll changes unless the gravity vector changes abruptly.

Expected exported tuning values:

```csharp
[Export] public float WalkSpeed { get; set; } = 7.0f;
[Export] public float Acceleration { get; set; } = 20.0f;
[Export] public float AirAcceleration { get; set; } = 6.0f;
[Export] public float JumpSpeed { get; set; } = 10.0f;
[Export] public float MouseSensitivity { get; set; } = 0.0025f;
[Export] public float AlignmentSharpness { get; set; } = 12.0f;
```

Grounding:

- Start with Godot's `IsOnFloor()` if the floor normal is configured correctly.
- If `IsOnFloor()` is unreliable with custom up, add a short sphere/ray check along the gravity direction.
- Keep the first implementation simple, but record any grounding issues in the checklist.

Camera:

- Yaw rotates the player around the local up axis.
- Pitch rotates the `ViewPivot` locally.
- Clamp pitch to avoid flipping, for example `-85` to `85` degrees.
- Camera roll should come only from body alignment, not mouse input.

## 6. Implementation Steps

### Step 1: Create Phase 1 Scenes

Checklist:

- [ ] Create `res://scenes/solar_system/Phase1TestWorld.tscn`.
- [ ] Create `res://scenes/planets/PlanetBody.tscn`.
- [ ] Create `res://scenes/player/Player.tscn`.
- [ ] Add a light and environment to the test world.
- [ ] Add a visible landmark to the planet.
- [ ] Set `Phase1TestWorld.tscn` as the temporary main scene.

### Step 2: Implement GravityBody

Checklist:

- [ ] Create `GravityBody.cs`.
- [ ] Add exported values for radius, surface gravity, influence radius, and priority.
- [ ] Implement `ContainsPoint`.
- [ ] Implement `GetGravityDirection`.
- [ ] Implement `GetGravityAcceleration`.
- [ ] Implement `GetDistanceToSurface`.
- [ ] Attach `GravityBody.cs` to the planet scene.
- [ ] Confirm exported values appear in the Godot inspector.

### Step 3: Implement GravityService

Checklist:

- [ ] Create `GravityService.cs`.
- [ ] Register it as an autoload.
- [ ] Add register/unregister methods.
- [ ] Add best-body selection logic.
- [ ] Add gravity acceleration query.
- [ ] Add up direction query.
- [ ] Confirm the planet registers when the scene starts.
- [ ] Add temporary debug logging for registration.

### Step 4: Implement Player Alignment

Checklist:

- [ ] Create `PlayerController.cs`.
- [ ] Attach it to `Player.tscn`.
- [ ] Query gravity up direction every physics frame.
- [ ] Align the player's basis so local up matches gravity up.
- [ ] Smooth alignment enough to avoid jitter.
- [ ] Spawn the player upright on the planet surface.
- [ ] Confirm the player stays visually upright relative to the surface.

### Step 5: Implement Walking

Checklist:

- [ ] Read movement input.
- [ ] Calculate camera-relative forward and right vectors.
- [ ] Project forward and right onto the tangent plane.
- [ ] Apply acceleration toward target horizontal velocity.
- [ ] Preserve vertical velocity along the gravity axis.
- [ ] Call `MoveAndSlide`.
- [ ] Tune walk speed and acceleration.

### Step 6: Implement Jumping and Falling

Checklist:

- [ ] Apply gravity acceleration while not grounded.
- [ ] Apply jump impulse along local up.
- [ ] Prevent repeated jumps while airborne.
- [ ] Confirm falling returns the player to the planet.
- [ ] Tune jump speed.
- [ ] Check behavior near the planet poles and on the opposite side of the sphere.

### Step 7: Implement Camera Look

Checklist:

- [ ] Capture mouse input.
- [ ] Apply yaw around local up.
- [ ] Apply pitch to `ViewPivot`.
- [ ] Clamp pitch.
- [ ] Ensure camera does not roll from mouse input.
- [ ] Add an escape/pause path to release mouse capture during testing.

### Step 8: Add Debug Overlay

Checklist:

- [ ] Create `GravityDebugOverlay.cs`.
- [ ] Show active gravity body name.
- [ ] Show speed.
- [ ] Show grounded state.
- [ ] Show gravity direction.
- [ ] Show player up direction.
- [ ] Show distance from planet surface.
- [ ] Add a toggle input for debug visibility.

### Step 9: Tune and Stabilize

Checklist:

- [ ] Walk a full loop around the planet.
- [ ] Walk across both poles.
- [ ] Jump while moving uphill, downhill, and sideways.
- [ ] Fall from a raised landmark.
- [ ] Run for at least five minutes without visible drift, jitter, or control inversion.
- [ ] Record tuning values in this document or a tuning note.

## 7. Acceptance Test Checklist

Phase 1 is complete only when all required checks pass:

- [ ] The project opens without script errors.
- [ ] `Phase1TestWorld.tscn` runs from the editor.
- [ ] The player starts on the planet surface.
- [ ] The player can walk forward, backward, left, and right.
- [ ] The player can circumnavigate the planet.
- [ ] The player can cross the top, bottom, and sides of the sphere without input inversion.
- [ ] The player remains aligned feet-down toward the planet center.
- [ ] The camera remains readable while walking around the planet.
- [ ] The player can jump and land.
- [ ] The player falls back to the planet after walking or jumping off a raised object.
- [ ] Debug overlay reports active gravity body, grounded state, and velocity.
- [ ] There are no recurring physics warnings or script errors in the Godot output panel.

## 8. Known Technical Questions

Resolve during implementation:

- Is `CharacterBody3D.IsOnFloor()` reliable enough with arbitrary up direction for our controller?
- Does `MoveAndSlide` behave cleanly when the player basis changes every physics frame?
- How much alignment smoothing is comfortable before movement feels laggy?
- Should the controller use a custom ground probe instead of relying on default floor detection?
- What planet radius feels good for walking without excessive curvature discomfort?

Do not over-engineer these before testing. Phase 1 exists to answer them empirically.

## 9. Out of Scope

Do not implement these in Phase 1:

- Jetpack.
- Ship.
- Multiple planets.
- Floating origin.
- Save/load.
- Scanner.
- Inventory.
- Narrative clues.
- Procedural terrain.
- Advanced art.
- Audio pass.
- Menus beyond minimal pause/debug support.

## 10. Phase 1 Exit Criteria

The phase is ready to close when:

- All acceptance tests pass.
- Movement values are tuned well enough to support Phase 2.
- The player controller has no hardcoded global-up assumptions.
- Gravity code is isolated enough to be reused by jetpack and ship systems.
- Any unresolved controller issues are documented with reproduction steps.

At that point, Phase 2 can start by adding jetpack thrust and weak-gravity movement on top of this controller.
