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
        AssertAuthoredMesh("../Ship/Interior/Floor/MainPlate", "Tapered cabin floor mesh is present.");
        AssertAuthoredMesh("../Ship/Interior/LeftWall/UpperPanel", "Left authored wall panel is present.");
        AssertAuthoredMesh("../Ship/Interior/RightWall/UpperPanel", "Right authored wall panel is present.");
        AssertAuthoredMesh("../Ship/Interior/ForwardBulkhead", "Authored forward bulkhead is present.");
        AssertAuthoredMesh("../Ship/Interior/RearBulkhead", "Authored rear bulkhead is present.");
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
                Assert(_pilotSeat.CanInteract(_player), "Pilot seat remains interactable inside revised interior.");
                _pilotSeat.Interact(_player);
                break;
            case 30:
                Assert(_player.DebugPlayerContext == PlayerContext.Seated, "Player sits in authored pilot chair.");
                Assert(_exteriorVisual.Visible, "Exterior ShuttleA visual is restored for seated ship camera view.");
                Assert(_ship.IsPiloted, "Ship pilot state is active after sitting.");
                Assert(_player.GlobalPosition.DistanceTo(_seatAnchor.GlobalPosition) < 0.05f, "Seated player aligns to revised seat anchor.");
                _pilotSeat.Interact(_player);
                break;
            case 40:
                Assert(_player.DebugPlayerContext == PlayerContext.InShipInterior, "Player stands from authored pilot chair.");
                Assert(!_exteriorVisual.Visible, "Exterior ShuttleA visual is hidden again after standing inside.");
                Assert(!_ship.IsPiloted, "Ship pilot state clears after standing.");
                Assert(_player.GlobalPosition.DistanceTo(_seatExit.GlobalPosition) < 0.05f, "Standing places player on revised seat exit marker.");
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
            && local.Y <= 3.35f
            && local.Z >= -4.85f
            && local.Z <= 4.35f;
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
