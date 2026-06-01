# Exterior Hope To Achieve 2

## Previous Iteration Review

Iteration 1 succeeded at moving the underside support collision out of hardcoded
runtime values and into a named source contract. It also added static
validation for the contract and made the `V` overlay include the contract
regions.

It did **not** fully prove the ship-world physics behavior. Build/import and
static contract validation are useful, but they do not prove the ship starts
supported on the platform or lifts off without clipping downward. That is the
main gap for this iteration.

## 1. Visual-To-Collision Hull Fit

I intend to add runtime validation that checks the named contract regions are
actually present on the spawned prototype shuttle. This does not improve the
visual shape itself, but it improves the evidence that the visible/debug
collision contract is connected to the gameplay object.

This is ambitious enough because it catches a class of failure where the JSON
contract passes but the playable ship is still using missing or stale collision
nodes.

## 2. Ship-World Physics

I intend to add a headless liftoff validation that places the prototype shuttle
on the landing platform, seats the player as pilot, holds ascend, and fails if
the ship drops below its starting height or does not gain altitude.

This is the most important aspect of the iteration because the latest failure
mode was the ship clipping down into the planet/platform during liftoff.

## 3. Player Exterior And Ramp Traversal

I intend to leave the existing traversal validator intact and keep the new
liftoff validation focused on ship-world collision. The liftoff test should not
require broad collision shapes that would block the ramp route.

This is ambitious enough because it keeps separate validation boundaries:
traversal is still covered by traversal validation, while liftoff gets its own
physics proof.

## 4. Integration With Gameplay Systems

I intend for the validation to use the real `ShipController` pilot path rather
than pushing the rigid body directly. The test should set the player into the
seat, call the normal pilot setup, press the actual `ship_translate_up` action,
and observe the real controller result.

This is ambitious enough because it validates cockpit seat control, ship input,
gravity, and physics together instead of only checking one isolated function.

## 5. Evidence And Validation

I intend to produce:

- a new C# validation runner;
- a Godot validation scene;
- a shell script to run it;
- a JSON report written under `reports/ship_pipeline`;
- `dotnet build`;
- Godot import.

If the host MCP server does not yet expose this script as a profile, the script
will still be available for host execution and can be added to MCP after this
pass.

