using Godot;

public partial class Phase3ValidationRunner : Node
{
    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public NodePath ExteriorHatchPath { get; set; } = "../Ship/ExteriorHatch";
    [Export] public NodePath InteriorHatchPath { get; set; } = "../Ship/InteriorHatch";
    [Export] public NodePath PilotSeatPath { get; set; } = "../Ship/PilotSeat";
    [Export] public NodePath InteriorSpawnPath { get; set; } = "../Ship/Markers/InteriorSpawn";
    [Export] public NodePath ExteriorExitPath { get; set; } = "../Ship/Markers/ExteriorExit";
    [Export] public NodePath SeatAnchorPath { get; set; } = "../Ship/Markers/SeatAnchor";
    [Export] public NodePath SeatExitPath { get; set; } = "../Ship/Markers/SeatExit";

    private PlayerController _player = null!;
    private ShipHatch _exteriorHatch = null!;
    private ShipHatch _interiorHatch = null!;
    private PilotSeat _pilotSeat = null!;
    private Marker3D _interiorSpawn = null!;
    private Marker3D _exteriorExit = null!;
    private Marker3D _seatAnchor = null!;
    private Marker3D _seatExit = null!;
    private int _frame;
    private bool _failed;
    private Vector3 _seatedStartPosition;

    public override void _Ready()
    {
        _player = GetNode<PlayerController>(PlayerPath);
        _exteriorHatch = GetNode<ShipHatch>(ExteriorHatchPath);
        _interiorHatch = GetNode<ShipHatch>(InteriorHatchPath);
        _pilotSeat = GetNode<PilotSeat>(PilotSeatPath);
        _interiorSpawn = GetNode<Marker3D>(InteriorSpawnPath);
        _exteriorExit = GetNode<Marker3D>(ExteriorExitPath);
        _seatAnchor = GetNode<Marker3D>(SeatAnchorPath);
        _seatExit = GetNode<Marker3D>(SeatExitPath);

        Assert(_player.DebugPlayerContext == PlayerContext.OnFoot, "Player starts on foot.");
        Assert(_exteriorHatch.CanInteract(_player), "Exterior hatch can be used while on foot.");
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
                _exteriorHatch.Interact(_player);
                break;
            case 20:
                Assert(_player.DebugPlayerContext == PlayerContext.InShipInterior, $"Entering hatch sets interior context. Actual: {_player.DebugPlayerContext}");
                AssertNear(_player.GlobalPosition, _interiorSpawn.GlobalPosition, 0.5f, "Entering hatch moves player to interior spawn.");
                Assert(_pilotSeat.CanInteract(_player), "Pilot seat can be used inside ship.");
                _pilotSeat.Interact(_player);
                break;
            case 30:
                Assert(_player.DebugPlayerContext == PlayerContext.Seated, $"Pilot seat sets seated context. Actual: {_player.DebugPlayerContext}");
                Assert(!_player.DebugMovementEnabled, "Movement is disabled while seated.");
                AssertNear(_player.GlobalPosition, _seatAnchor.GlobalPosition, 0.5f, "Sitting moves player to seat anchor.");
                _seatedStartPosition = _player.GlobalPosition;
                Input.ActionPress("move_forward");
                Input.ActionPress("jetpack");
                break;
            case 80:
                Input.ActionRelease("move_forward");
                Input.ActionRelease("jetpack");
                AssertNear(_player.GlobalPosition, _seatedStartPosition, 0.5f, "Seated player does not move from movement or jetpack input.");
                _pilotSeat.Interact(_player);
                break;
            case 90:
                Assert(_player.DebugPlayerContext == PlayerContext.InShipInterior, $"Standing restores interior context. Actual: {_player.DebugPlayerContext}");
                Assert(_player.DebugMovementEnabled, "Movement is enabled after standing.");
                AssertNear(_player.GlobalPosition, _seatExit.GlobalPosition, 0.5f, "Standing moves player to seat exit.");
                _interiorHatch.Interact(_player);
                break;
            case 100:
                Assert(_player.DebugPlayerContext == PlayerContext.OnFoot, $"Interior hatch restores on-foot context. Actual: {_player.DebugPlayerContext}");
                AssertNear(_player.GlobalPosition, _exteriorExit.GlobalPosition, 0.5f, "Exiting hatch moves player outside.");
                if (_failed)
                {
                    return;
                }
                GD.Print("Phase 3 validation passed.");
                GetTree().Quit(0);
                break;
        }
    }

    private void AssertNear(Vector3 actual, Vector3 expected, float tolerance, string message)
    {
        var distance = actual.DistanceTo(expected);
        Assert(distance <= tolerance, $"{message} Distance: {distance:0.000}");
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
