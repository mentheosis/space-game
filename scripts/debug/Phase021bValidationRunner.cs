using Godot;

public partial class Phase021bValidationRunner : Node
{
    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public NodePath ShipPath { get; set; } = "../Ship";
    [Export] public NodePath ExteriorHatchPath { get; set; } = "../Ship/ExteriorHatch";
    [Export] public NodePath InteriorHatchPath { get; set; } = "../Ship/InteriorHatch";
    [Export] public NodePath PilotSeatPath { get; set; } = "../Ship/PilotSeat";
    [Export] public NodePath InteriorSpawnPath { get; set; } = "../Ship/Markers/InteriorSpawn";
    [Export] public NodePath ExteriorExitPath { get; set; } = "../Ship/Markers/ExteriorExit";
    [Export] public NodePath SeatAnchorPath { get; set; } = "../Ship/Markers/SeatAnchor";
    [Export] public NodePath SeatExitPath { get; set; } = "../Ship/Markers/SeatExit";
    [Export] public NodePath ExteriorVisualPath { get; set; } = "../Ship/OpenGameArtShuttleVisual";

    private PlayerController _player = null!;
    private ShipController _ship = null!;
    private ShipHatch _exteriorHatch = null!;
    private ShipHatch _interiorHatch = null!;
    private PilotSeat _pilotSeat = null!;
    private Marker3D _interiorSpawn = null!;
    private Marker3D _exteriorExit = null!;
    private Marker3D _seatAnchor = null!;
    private Marker3D _seatExit = null!;
    private Node3D _exteriorVisual = null!;
    private int _frame;
    private bool _failed;

    public override void _Ready()
    {
        _player = GetNode<PlayerController>(PlayerPath);
        _ship = GetNode<ShipController>(ShipPath);
        _exteriorHatch = GetNode<ShipHatch>(ExteriorHatchPath);
        _interiorHatch = GetNode<ShipHatch>(InteriorHatchPath);
        _pilotSeat = GetNode<PilotSeat>(PilotSeatPath);
        _interiorSpawn = GetNode<Marker3D>(InteriorSpawnPath);
        _exteriorExit = GetNode<Marker3D>(ExteriorExitPath);
        _seatAnchor = GetNode<Marker3D>(SeatAnchorPath);
        _seatExit = GetNode<Marker3D>(SeatExitPath);
        _exteriorVisual = GetNode<Node3D>(ExteriorVisualPath);

        Assert(_ship.IsLanded, "Ship starts landed for 0.2.1b validation.");
        Assert(_exteriorVisual.Visible, "Exterior ShuttleA visual starts visible.");
        AssertBlenderInteriorVisual();
        AssertAuthoredMesh("../Ship/Interior/Floor/MainPlate", "Tapered cabin floor mesh is present.");
        AssertAuthoredMesh("../Ship/Interior/LeftWall/UpperPanel", "Left authored wall panel is present.");
        AssertAuthoredMesh("../Ship/Interior/RightWall/UpperPanel", "Right authored wall panel is present.");
        AssertRetiredMeshHidden("../Ship/Interior/ForwardBulkhead", "Legacy forward bulkhead blockout is hidden behind Blender interior.");
        AssertRetiredMeshHidden("../Ship/Interior/RearBulkhead", "Legacy rear bulkhead blockout is hidden behind Blender interior.");
        AssertAuthoredMesh("../Ship/Interior/Ribs/ForwardFrame", "Authored forward cabin rib frame is present.");
        AssertAuthoredMesh("../Ship/Interior/Ribs/MidFrame", "Authored middle cabin rib frame is present.");
        AssertAuthoredMesh("../Ship/Interior/Ribs/RearFrame", "Authored rear cabin rib frame is present.");
        AssertAuthoredMesh("../Ship/Interior/Cockpit/ConsoleBase", "Authored cockpit console is present.");
        AssertAuthoredMesh("../Ship/Interior/Cockpit/CenterScreen", "Authored screen cluster is present.");
        AssertAuthoredMesh("../Ship/Interior/Cockpit/ControlCluster", "Authored control cluster is present.");
        AssertAuthoredMesh("../Ship/PilotSeat/SeatVisual/Base", "Authored pilot chair frame is present.");
        AssertAuthoredMesh("../Ship/PilotSeat/SeatVisual/Cushion", "Authored pilot chair cushion shell is present.");
        AssertAuthoredMesh("../Ship/ExteriorHatch/MeshInstance3D", "Authored exterior hatch door is present.");
        AssertAuthoredMesh("../Ship/ExteriorHatch/ExteriorHatchFrame", "Authored exterior hatch frame is present.");
        AssertAuthoredMesh("../Ship/InteriorHatch/MeshInstance3D", "Authored interior hatch door is present.");
        AssertAuthoredMesh("../Ship/InteriorHatch/InteriorHatchFrame", "Authored interior hatch frame is present.");
        AssertHidden("../Ship/PilotSeat/SeatVisual/Back", "Legacy blockout seat back is hidden.");
        AssertHidden("../Ship/Interior/Cockpit/LeftScreen", "Legacy left screen box is hidden.");
        AssertHidden("../Ship/Interior/Cockpit/RightScreen", "Legacy right screen box is hidden.");
        AssertHidden("../Ship/Interior/Ribs/LeftForwardRib", "Legacy rib column boxes are hidden.");
        AssertHidden("../Ship/Interior/Ribs/ForwardCrossRib", "Legacy rib crossbar boxes are hidden.");
        AssertHidden("../Ship/ExteriorHatch/ExteriorHatchFrameTop", "Legacy exterior hatch frame boxes are hidden.");
        AssertHidden("../Ship/InteriorHatch/InteriorHatchFrameTop", "Legacy interior hatch frame boxes are hidden.");
        AssertMarkerLayout();
    }

    public override void _PhysicsProcess(double delta)
    {
        if (_failed)
        {
            return;
        }

        _frame++;

        switch (_frame)
        {
            case 10:
                Assert(_exteriorHatch.CanInteract(_player), "Exterior hatch can enter while landed.");
                _exteriorHatch.Interact(_player);
                break;
            case 20:
                Assert(_player.DebugPlayerContext == PlayerContext.InShipInterior, "Player enters revised ship interior.");
                Assert(!_exteriorVisual.Visible, "Exterior ShuttleA visual is hidden for first-person interior view.");
                Assert(_player.GlobalPosition.DistanceTo(_interiorSpawn.GlobalPosition) < 0.05f, "Enter hatch lands player on revised interior spawn.");
                Assert(IsShipLocalInsideCabin(_player.GlobalPosition), "Interior spawn is inside measured cabin envelope.");
                AssertPlayableInteriorTraversal();
                Assert(_pilotSeat.CanInteract(_player), "Pilot seat remains interactable inside revised interior.");
                _pilotSeat.Interact(_player);
                break;
            case 30:
                Assert(_player.DebugPlayerContext == PlayerContext.Seated, "Player sits in authored pilot chair.");
                Assert(_ship.IsCockpitCameraActive, "Ship defaults to cockpit first-person view after sitting.");
                Assert(!_exteriorVisual.Visible, "Exterior ShuttleA visual is hidden for default seated cockpit first-person view.");
                Assert(_ship.IsPiloted, "Ship pilot state is active after sitting.");
                Assert(_player.GlobalPosition.DistanceTo(_seatAnchor.GlobalPosition) < 0.05f, "Seated player aligns to revised seat anchor.");
                Input.ActionPress("ship_toggle_camera");
                break;
            case 31:
                Assert(!_ship.IsCockpitCameraActive, "Ship camera toggles to exterior orbital view while piloted.");
                Assert(_exteriorVisual.Visible, "Exterior ShuttleA visual is restored after toggling to orbital ship view.");
                Input.ActionRelease("ship_toggle_camera");
                Input.ActionPress("ship_toggle_camera");
                break;
            case 32:
                Assert(_ship.IsCockpitCameraActive, "Ship camera toggles back to cockpit first-person view while piloted.");
                Assert(!_exteriorVisual.Visible, "Exterior ShuttleA visual is hidden after returning to cockpit first-person view.");
                Input.ActionRelease("ship_toggle_camera");
                _pilotSeat.Interact(_player);
                break;
            case 40:
                Assert(_player.DebugPlayerContext == PlayerContext.InShipInterior, "Player stands from authored pilot chair.");
                Assert(!_exteriorVisual.Visible, "Exterior ShuttleA visual is hidden again after standing inside.");
                Assert(!_ship.IsPiloted, "Ship pilot state clears after standing.");
                Assert(_player.GlobalPosition.DistanceTo(_seatExit.GlobalPosition) < 0.35f, "Standing places player on revised seat exit marker.");
                Assert(IsShipLocalInsideCabin(_player.GlobalPosition), "Seat exit remains inside measured cabin envelope.");
                Assert(_interiorHatch.CanInteract(_player), "Interior hatch remains interactable after standing.");
                _interiorHatch.Interact(_player);
                Assert(_player.GlobalPosition.DistanceTo(_exteriorExit.GlobalPosition) < 0.05f, "Exit hatch lands player on revised exterior exit marker.");
                break;
            case 50:
                Assert(_player.DebugPlayerContext == PlayerContext.OnFoot, "Player exits revised ship interior.");
                Assert(_exteriorVisual.Visible, "Exterior ShuttleA visual is restored after exiting ship.");
                Assert(_player.GlobalPosition.DistanceTo(_exteriorExit.GlobalPosition) < 0.75f, "Exited player remains near revised exterior exit marker after settling.");
                GD.Print("0.2.1b ship interior validation passed.");
                GetTree().Quit(0);
                break;
        }
    }

    private void AssertAuthoredMesh(string path, string message)
    {
        var meshInstance = GetNodeOrNull<MeshInstance3D>(path);
        Assert(meshInstance is not null, message);
        if (meshInstance is null)
        {
            return;
        }

        Assert(meshInstance.Visible, $"{message} It is visible.");
        Assert(meshInstance.Mesh is not null, $"{message} It has a mesh resource.");
        Assert(meshInstance.Mesh?.ResourcePath.EndsWith(".obj") ?? false, $"{message} It uses an authored OBJ mesh.");
    }

    private void AssertBlenderInteriorVisual()
    {
        var visual = GetNodeOrNull<Node3D>("../Ship/Interior/BlenderInteriorVisual");
        Assert(visual is not null, "Blender-authored ShuttleA interior visual is present.");
        if (visual is null)
        {
            return;
        }

        Assert(visual.Visible, "Blender-authored ShuttleA interior visual is visible.");
        Assert(visual.GetChildCount() > 0, "Blender-authored ShuttleA interior visual has imported child geometry.");
    }

    private void AssertRetiredMeshHidden(string path, string message)
    {
        var meshInstance = GetNodeOrNull<MeshInstance3D>(path);
        Assert(meshInstance is not null, message);
        if (meshInstance is null)
        {
            return;
        }

        Assert(!meshInstance.Visible, message);
        Assert(meshInstance.Mesh is not null, $"{message} It still keeps a mesh resource for fallback/reference.");
    }

    private void AssertHidden(string path, string message)
    {
        var node = GetNodeOrNull<GeometryInstance3D>(path);
        Assert(node is not null, message);
        if (node is not null)
        {
            Assert(!node.Visible, message);
        }
    }

    private void AssertMarkerLayout()
    {
        Assert(IsShipLocalInsideCabin(_interiorSpawn.GlobalPosition), "Interior spawn marker is inside cabin envelope.");
        Assert(IsShipLocalInsideCabin(_seatAnchor.GlobalPosition), "Seat anchor marker is inside cabin envelope.");
        Assert(IsShipLocalInsideCabin(_seatExit.GlobalPosition), "Seat exit marker is inside cabin envelope.");

        var exteriorExitLocal = _ship.ToLocal(_exteriorExit.GlobalPosition);
        Assert(exteriorExitLocal.Z > 4.5f, "Exterior exit marker is aft of the hatch area.");
        Assert(_seatAnchor.Position.Z < _seatExit.Position.Z, "Seat anchor is forward of seat exit.");
        Assert(_interiorSpawn.Position.Z > _seatExit.Position.Z, "Interior spawn is aft of seat exit.");
    }

    private bool IsShipLocalInsideCabin(Vector3 globalPosition)
    {
        var local = _ship.ToLocal(globalPosition);
        return Mathf.Abs(local.X) <= 3.15f
            && local.Y >= -0.1f
            && local.Y <= 3.75f
            && local.Z >= -11.6f
            && local.Z <= 4.35f;
    }

    private void AssertPlayableInteriorTraversal()
    {
        var wasProcessing = _player.IsPhysicsProcessing();
        _player.SetPhysicsProcess(false);

        var route = new[]
        {
            new TraversalSample("hatch spawn floor", new Vector3(0.0f, 1.10f, 2.35f), 0.26f, 0.12f),
            new TraversalSample("mid cabin floor", new Vector3(0.0f, 1.10f, 0.20f), 0.26f, 0.12f),
            new TraversalSample("forward cabin floor", new Vector3(0.0f, 1.10f, -3.70f), 0.26f, 0.12f),
            new TraversalSample("cockpit threshold floor", new Vector3(0.0f, 1.20f, -5.45f), 0.30f, 0.12f),
            new TraversalSample("lower access ramp", new Vector3(0.0f, 1.42f, -6.10f), 0.34f, 0.18f),
            new TraversalSample("mid access ramp", new Vector3(0.0f, 1.70f, -6.95f), 0.34f, 0.18f),
            new TraversalSample("upper access ramp", new Vector3(0.0f, 1.88f, -7.36f), 0.34f, 0.22f),
            new TraversalSample("chair approach clearance", new Vector3(0.0f, 1.82f, -7.42f), 0.34f, 0.18f),
            new TraversalSample("return upper ramp", new Vector3(0.0f, 1.88f, -7.36f), 0.34f, 0.22f),
            new TraversalSample("return cockpit threshold", new Vector3(0.0f, 1.20f, -5.45f), 0.30f, 0.12f),
            new TraversalSample("return seat exit marker", _ship.ToLocal(_seatExit.GlobalPosition), 0.38f, 0.12f),
        };

        var sideSupportSamples = new[]
        {
            new TraversalSample("left hatch floor edge", new Vector3(-0.52f, 1.10f, 2.70f), 0.26f, 0.14f),
            new TraversalSample("right hatch floor edge", new Vector3(0.52f, 1.10f, 2.70f), 0.26f, 0.14f),
            new TraversalSample("left mid cabin floor edge", new Vector3(-0.72f, 1.10f, 0.10f), 0.26f, 0.14f),
            new TraversalSample("right mid cabin floor edge", new Vector3(0.72f, 1.10f, 0.10f), 0.26f, 0.14f),
            new TraversalSample("left forward cabin floor edge", new Vector3(-0.56f, 1.10f, -3.55f), 0.26f, 0.14f),
            new TraversalSample("right forward cabin floor edge", new Vector3(0.56f, 1.10f, -3.55f), 0.26f, 0.14f),
            new TraversalSample("left cockpit threshold edge", new Vector3(-0.36f, 1.20f, -5.45f), 0.30f, 0.14f),
            new TraversalSample("right cockpit threshold edge", new Vector3(0.36f, 1.20f, -5.45f), 0.30f, 0.14f),
            new TraversalSample("left lower access ramp edge", new Vector3(-0.28f, 1.42f, -6.10f), 0.34f, 0.20f),
            new TraversalSample("right lower access ramp edge", new Vector3(0.28f, 1.42f, -6.10f), 0.34f, 0.20f),
            new TraversalSample("left upper access ramp edge", new Vector3(-0.26f, 1.88f, -7.36f), 0.34f, 0.24f),
            new TraversalSample("right upper access ramp edge", new Vector3(0.26f, 1.88f, -7.36f), 0.34f, 0.24f),
        };

        foreach (var sample in route)
        {
            AssertSupportAt(sample);
            AssertLateralClearanceAt(sample, 0.18f);
            Assert(IsShipLocalInsideCabin(_player.GlobalPosition), $"{sample.Name} remains inside measured cabin envelope.");
        }

        foreach (var sample in sideSupportSamples)
        {
            AssertSupportAt(sample);
            Assert(IsShipLocalInsideCabin(_player.GlobalPosition), $"{sample.Name} remains inside measured cabin envelope.");
        }

        AssertContinuousTraversal(route);

        _player.MoveToTransform(_seatExit.GlobalTransform);
        _player.SetPhysicsProcess(wasProcessing);
        Assert(_player.GlobalPosition.DistanceTo(_seatExit.GlobalPosition) < 0.05f, "Traversal validation returns player to revised seat exit marker.");
    }

    private void AssertSupportAt(TraversalSample sample)
    {
        var shipBasis = _ship.GlobalTransform.Basis.Orthonormalized();
        var startLocal = sample.ExpectedOriginLocal + Vector3.Up * 0.28f;
        var startGlobal = _ship.GlobalTransform * startLocal;
        var down = -shipBasis.Y.Normalized();

        _player.MoveToTransform(new Transform3D(shipBasis, startGlobal));
        var collision = _player.MoveAndCollide(down * 0.85f, false, 0.001f, false);
        Assert(collision is not null, $"{sample.Name} has walkable support under the player capsule.");

        var local = _ship.ToLocal(_player.GlobalPosition);
        var yDelta = Mathf.Abs(local.Y - sample.ExpectedOriginLocal.Y);
        Assert(yDelta <= sample.VerticalTolerance, $"{sample.Name} support height is close to authored route. Delta: {yDelta:0.00}");
        Assert(Mathf.Abs(local.X - sample.ExpectedOriginLocal.X) <= sample.HorizontalTolerance, $"{sample.Name} does not push the player sideways.");
        Assert(Mathf.Abs(local.Z - sample.ExpectedOriginLocal.Z) <= sample.HorizontalTolerance, $"{sample.Name} does not push the player forward/back.");
    }

    private void AssertLateralClearanceAt(TraversalSample sample, float clearanceDistance)
    {
        var shipBasis = _ship.GlobalTransform.Basis.Orthonormalized();
        var startLocal = sample.ExpectedOriginLocal + Vector3.Up * 0.28f;
        var startGlobal = _ship.GlobalTransform * startLocal;
        var down = -shipBasis.Y.Normalized();

        foreach (var side in new[] { -1.0f, 1.0f })
        {
            _player.MoveToTransform(new Transform3D(shipBasis, startGlobal));
            var supportCollision = _player.MoveAndCollide(down * 0.85f, false, 0.001f, false);
            Assert(supportCollision is not null, $"{sample.Name} can settle before lateral clearance check.");
            var collision = _player.MoveAndCollide(shipBasis.X.Normalized() * side * clearanceDistance, false, 0.001f, false);
            Assert(collision is null, $"{sample.Name} has lateral body clearance to the {(side < 0.0f ? "left" : "right")}.");
        }
    }

    private void AssertContinuousTraversal(TraversalSample[] route)
    {
        var shipBasis = _ship.GlobalTransform.Basis.Orthonormalized();
        var shipUp = shipBasis.Y.Normalized();

        AssertSupportAt(route[0]);
        _player.UpDirection = shipUp;
        _player.MotionMode = CharacterBody3D.MotionModeEnum.Grounded;
        _player.FloorStopOnSlope = true;

        for (var index = 1; index < route.Length; index++)
        {
            var target = route[index];
            var stagnantFrames = 0;
            var previousDistance = float.MaxValue;
            var reached = false;

            for (var frame = 0; frame < 90; frame++)
            {
                var local = _ship.ToLocal(_player.GlobalPosition);
                var targetDelta = GetTargetDelta(local, target);
                var planarDelta = targetDelta.PlanarDelta;
                var planarDistance = targetDelta.PlanarDistance;
                var verticalDelta = targetDelta.VerticalDelta;

                if (IsAtTarget(targetDelta, target))
                {
                    reached = true;
                    break;
                }

                if (planarDistance < previousDistance - 0.015f)
                {
                    stagnantFrames = 0;
                }
                else
                {
                    stagnantFrames++;
                }

                if (stagnantFrames >= 18)
                {
                    Assert(false, $"Continuous traversal blocked before {target.Name}. Local position: {FormatVector(local)}, target: {FormatVector(target.ExpectedOriginLocal)}, planar distance: {planarDistance:0.00}, vertical delta: {verticalDelta:0.00}");
                    return;
                }

                previousDistance = planarDistance;

                var moveLocal = new Vector3(planarDelta.X, 0.0f, planarDelta.Y);
                var moveGlobal = (shipBasis.X * moveLocal.X + shipBasis.Z * moveLocal.Z).Normalized();
                _player.Velocity = moveGlobal * 2.6f - shipUp * 1.4f;
                _player.MoveAndSlide();
                if (!IsShipLocalInsideCabin(_player.GlobalPosition))
                {
                    var exitedLocal = _ship.ToLocal(_player.GlobalPosition);
                    Assert(false, $"Continuous traversal left measured cabin envelope before {target.Name}. Local position: {FormatVector(exitedLocal)}");
                    return;
                }
            }

            if (!reached)
            {
                var local = _ship.ToLocal(_player.GlobalPosition);
                var targetDelta = GetTargetDelta(local, target);
                reached = IsAtTarget(targetDelta, target);
                if (!reached)
                {
                    Assert(false, $"Continuous traversal timed out before {target.Name}. Local position: {FormatVector(local)}, target: {FormatVector(target.ExpectedOriginLocal)}, planar distance: {targetDelta.PlanarDistance:0.00}, vertical delta: {targetDelta.VerticalDelta:0.00}");
                    return;
                }
            }

            Assert(true, $"Continuous traversal reaches {target.Name} using real MoveAndSlide capsule motion.");
        }

        _player.Velocity = Vector3.Zero;
    }

    private readonly record struct TraversalSample(string Name, Vector3 ExpectedOriginLocal, float VerticalTolerance, float HorizontalTolerance);
    private readonly record struct TargetDelta(Vector2 PlanarDelta, float PlanarDistance, float VerticalDelta);

    private static TargetDelta GetTargetDelta(Vector3 local, TraversalSample target)
    {
        var planarDelta = new Vector2(target.ExpectedOriginLocal.X - local.X, target.ExpectedOriginLocal.Z - local.Z);
        return new TargetDelta(planarDelta, planarDelta.Length(), Mathf.Abs(target.ExpectedOriginLocal.Y - local.Y));
    }

    private static bool IsAtTarget(TargetDelta delta, TraversalSample target)
    {
        return delta.PlanarDistance <= 0.22f && delta.VerticalDelta <= target.VerticalTolerance + 0.18f;
    }

    private static string FormatVector(Vector3 vector)
    {
        return $"({vector.X:0.00}, {vector.Y:0.00}, {vector.Z:0.00})";
    }

    private void Assert(bool condition, string message)
    {
        if (condition)
        {
            GD.Print($"PASS: {message}");
            return;
        }

        _failed = true;
        GD.PushError($"FAIL: {message}");
        SetPhysicsProcess(false);
        GetTree().Quit(1);
    }
}
