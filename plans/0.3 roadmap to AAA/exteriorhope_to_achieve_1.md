# Exterior Hope To Achieve 1

## Iteration Target

This iteration starts E1 Collision Audit And Contract and begins E2 with a
first deterministic ship-world physics collision pass. The goal is not final
exterior collision quality yet. The goal is to replace anonymous runtime skid
tuning with a named, inspectable contract that can support liftoff and collision
debugging.

## 1. Visual-To-Collision Hull Fit

I intend to define named exterior collision regions for the prototype shuttle
instead of leaving the current support shapes as hardcoded Godot-side skids.
The first contract should cover the lower belly support zones that actually
touch the platform during landed/liftoff states.

This is ambitious enough for this iteration because it changes collision from
an implicit runtime patch into an explicit source artifact. Evidence should show
semantic region names, local centers/sizes, intended purpose, and debug overlay
visibility.

## 2. Ship-World Physics

I intend to replace the temporary `LeftPhysicsSkidCollision` and
`RightPhysicsSkidCollision` hardcoded shapes with contract-driven ship-world
physics regions. The initial regions should support the ship on the landing
platform without a broad invisible box that blocks the interior.

This is ambitious enough because the liftoff failure came from missing
ship-world physics collision. The next implementation must make the ship's
contact surfaces explicit and repeatable rather than adjusting numbers in the
loader by feel.

## 3. Player Exterior And Ramp Traversal

I intend to keep the physics support regions outside the central ramp and
interior walking path. The contract must explicitly label these as
`ship_world_physics` rather than `player_walkable` so future validation can
distinguish between ship support and player traversal.

This is ambitious enough because it prevents the common regression where a
physics hull fixes ship contact but creates invisible blockers in the ramp or
cargo route.

## 4. Integration With Gameplay Systems

I intend to keep the existing hatch, interior-volume, seat, cockpit camera, and
ship-control wiring intact while changing the source of the prototype ship
physics collision. The loader should still support collision visibility toggled
with `V`.

This is ambitious enough because the prototype ship is now a playable gameplay
object, so collision changes must not break entry, ship-relative gravity, or
seat control.

## 5. Evidence And Validation

I intend to produce:

- an E1 audit/contract document;
- a source JSON exterior collision contract;
- a generated or maintained report that records the named regions;
- host `dotnet build`;
- host Godot import.

I will not claim the phase complete from build/import alone. Manual liftoff and
future automated liftoff validation are still required for full confidence.

