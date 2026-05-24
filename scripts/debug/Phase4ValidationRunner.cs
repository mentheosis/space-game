using Godot;

public partial class Phase4ValidationRunner : Node
{
    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public NodePath ShipPath { get; set; } = "../Ship";
    [Export] public NodePath ExteriorHatchPath { get; set; } = "../Ship/ExteriorHatch";
    [Export] public NodePath InteriorHatchPath { get; set; } = "../Ship/InteriorHatch";
    [Export] public NodePath PilotSeatPath { get; set; } = "../Ship/PilotSeat";
    [Export] public NodePath SeatAnchorPath { get; set; } = "../Ship/Markers/SeatAnchor";

    private PlayerController _player = null!;
    private ShipController _ship = null!;
    private ShipHatch _exteriorHatch = null!;
    private ShipHatch _interiorHatch = null!;
    private PilotSeat _pilotSeat = null!;
    private Marker3D _seatAnchor = null!;
    private Transform3D _startingShipTransform;
    private Vector3 _shipStartPosition;
    private int _frame;
    private bool _failed;

    public override void _Ready()
    {
        _player = GetNode<PlayerController>(PlayerPath);
        _ship = GetNode<ShipController>(ShipPath);
        _exteriorHatch = GetNode<ShipHatch>(ExteriorHatchPath);
        _interiorHatch = GetNode<ShipHatch>(InteriorHatchPath);
        _pilotSeat = GetNode<PilotSeat>(PilotSeatPath);
        _seatAnchor = GetNode<Marker3D>(SeatAnchorPath);
        _startingShipTransform = _ship.GlobalTransform;
        _shipStartPosition = _ship.GlobalPosition;

        Assert(_ship.IsLanded, "Ship starts landed.");
        Assert(_exteriorHatch.CanInteract(_player), "Exterior hatch can be used while landed.");
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
                Assert(_player.DebugPlayerContext == PlayerContext.InShipInterior, "Player enters ship before piloting.");
                _pilotSeat.Interact(_player);
                break;
            case 30:
                Assert(_player.DebugPlayerContext == PlayerContext.Seated, "Player sits before piloting.");
                Assert(_ship.IsPiloted, "Ship has an active pilot after sitting.");
                Input.ActionPress("jump");
                break;
            case 130:
                Input.ActionRelease("jump");
                Assert(_ship.GlobalPosition.DistanceTo(_shipStartPosition) > 2.0f, $"Ship moved under thrust. Distance: {_ship.GlobalPosition.DistanceTo(_shipStartPosition):0.00}");
                Assert(_ship.Speed > 1.0f, $"Ship has velocity after thrust. Speed: {_ship.Speed:0.00}");
                Assert(!_ship.IsLanded, "Ship becomes airborne after takeoff thrust.");
                Assert(!_interiorHatch.CanInteract(_player), "Interior hatch cannot exit while airborne.");
                Assert(_player.DebugPlayerContext == PlayerContext.Seated, "Player remains seated while airborne.");
                Assert(_player.GlobalPosition.DistanceTo(_seatAnchor.GlobalPosition) < 0.5f, "Seated player follows moving seat anchor.");
                break;
            case 132:
                Input.ActionPress("ship_yaw_left");
                Input.ActionPress("ship_pitch_up");
                break;
            case 145:
                Input.ActionRelease("ship_yaw_left");
                Input.ActionRelease("ship_pitch_up");
                Assert(_ship.AngularVelocity.Length() > 0.1f, $"Ship rotates from arrow-key pitch/yaw input. Angular speed: {_ship.AngularVelocity.Length():0.00}");
                break;
            case 150:
                _ship.GlobalTransform = _startingShipTransform;
                _ship.ForceLandedForValidation();
                _player.ForceSeatTransform(_seatAnchor.GlobalTransform);
                break;
            case 170:
                Assert(_ship.IsLanded, "Ship can be returned to landed state for exit validation.");
                _pilotSeat.Interact(_player);
                break;
            case 190:
                Assert(_player.DebugPlayerContext == PlayerContext.InShipInterior, "Player can stand after ship is landed.");
                _interiorHatch.Interact(_player);
                break;
            case 210:
                Assert(_player.DebugPlayerContext == PlayerContext.OnFoot, "Player can exit after landing.");
                Assert(!_ship.IsPiloted, "Ship has no active pilot after standing.");
                GD.Print("Phase 4 validation passed.");
                GetTree().Quit(0);
                break;
        }
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
