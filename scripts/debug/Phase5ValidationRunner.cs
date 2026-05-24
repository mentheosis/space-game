using Godot;

public partial class Phase5ValidationRunner : Node
{
    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public NodePath ShipPath { get; set; } = "../Ship";
    [Export] public NodePath PlanetBPath { get; set; } = "../PlanetB";
    [Export] public NodePath ExteriorHatchPath { get; set; } = "../Ship/ExteriorHatch";
    [Export] public NodePath InteriorHatchPath { get; set; } = "../Ship/InteriorHatch";
    [Export] public NodePath PilotSeatPath { get; set; } = "../Ship/PilotSeat";
    [Export] public NodePath SeatAnchorPath { get; set; } = "../Ship/Markers/SeatAnchor";

    private PlayerController _player = null!;
    private ShipController _ship = null!;
    private Node3D _planetB = null!;
    private ShipHatch _exteriorHatch = null!;
    private ShipHatch _interiorHatch = null!;
    private PilotSeat _pilotSeat = null!;
    private Marker3D _seatAnchor = null!;
    private float _startingTargetDistance;
    private Vector3 _walkStart;
    private int _frame;
    private bool _failed;

    public override void _Ready()
    {
        _player = GetNode<PlayerController>(PlayerPath);
        _ship = GetNode<ShipController>(ShipPath);
        _planetB = GetNode<Node3D>(PlanetBPath);
        _exteriorHatch = GetNode<ShipHatch>(ExteriorHatchPath);
        _interiorHatch = GetNode<ShipHatch>(InteriorHatchPath);
        _pilotSeat = GetNode<PilotSeat>(PilotSeatPath);
        _seatAnchor = GetNode<Marker3D>(SeatAnchorPath);
        _startingTargetDistance = _ship.GlobalPosition.DistanceTo(_planetB.GlobalPosition);

        Assert(_ship.IsLanded, "Ship starts landed on Planet A.");
        Assert(_exteriorHatch.CanInteract(_player), "Exterior hatch can enter while landed on Planet A.");
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
                Assert(_player.DebugPlayerContext == PlayerContext.InShipInterior, "Player enters ship before interplanetary flight.");
                _pilotSeat.Interact(_player);
                break;
            case 30:
                Assert(_player.DebugPlayerContext == PlayerContext.Seated, "Player sits before interplanetary flight.");
                Assert(_ship.IsPiloted, "Ship has an active pilot for interplanetary flight.");
                Input.ActionPress("ship_translate_up");
                break;
            case 90:
                Input.ActionRelease("ship_translate_up");
                Assert(!_ship.IsLanded, "Ship becomes airborne before travel.");
                var toPlanetB = (_planetB.GlobalPosition - _ship.GlobalPosition).Normalized();
                _ship.LinearVelocity = toPlanetB * 80.0f;
                break;
            case 120:
                Assert(_ship.GlobalPosition.DistanceTo(_planetB.GlobalPosition) < _startingTargetDistance, "Ship closes distance to Planet B.");
                break;
            case 130:
                MoveShipTo(new Vector3(290.0f, 0.0f, 0.0f), Vector3.Zero);
                break;
            case 132:
                Assert(_ship.ActiveGravityBodyName == "Zero-G", $"Ship reaches true zero-g gap. Actual: {_ship.ActiveGravityBodyName}");
                Assert(_ship.GravityMagnitude <= 0.001f, $"Zero-g gap has no gravity. Magnitude: {_ship.GravityMagnitude:0.000}");
                break;
            case 140:
                MoveShipTo(_planetB.GlobalPosition + new Vector3(-210.0f, 0.0f, 0.0f), Vector3.Zero);
                break;
            case 142:
                Assert(_ship.ActiveGravityBodyName == "PlanetBGravity", $"Ship enters Planet B gravity. Actual: {_ship.ActiveGravityBodyName}");
                Assert(_ship.GravityMagnitude > 0.05f && _ship.GravityMagnitude < 1.0f, $"Planet B edge gravity is weak. Magnitude: {_ship.GravityMagnitude:0.000}");
                break;
            case 150:
                MoveShipTo(_planetB.GlobalPosition + new Vector3(0.0f, 46.1f, -9.0f), Vector3.Zero);
                _ship.ForceLandedForValidation();
                _player.ForceSeatTransform(_seatAnchor.GlobalTransform);
                break;
            case 170:
                Assert(_ship.IsLanded, "Ship can land on Planet B.");
                Assert(_ship.ActiveGravityBodyName == "PlanetBGravity", $"Landed ship uses Planet B gravity. Actual: {_ship.ActiveGravityBodyName}");
                Assert(_pilotSeat.CanInteract(_player), "Pilot seat can stand after landing on Planet B.");
                _pilotSeat.Interact(_player);
                break;
            case 190:
                Assert(_player.DebugPlayerContext == PlayerContext.InShipInterior, "Player stands inside ship after landing on Planet B.");
                Assert(_interiorHatch.CanInteract(_player), "Interior hatch can exit after landing on Planet B.");
                _interiorHatch.Interact(_player);
                break;
            case 210:
                Assert(_player.DebugPlayerContext == PlayerContext.OnFoot, "Player exits ship on Planet B.");
                Assert(_player.DebugActiveGravityBodyName == "PlanetBGravity", $"Player is under Planet B gravity after exit. Actual: {_player.DebugActiveGravityBodyName}");
                _walkStart = _player.GlobalPosition;
                Input.ActionPress("ship_translate_forward");
                break;
            case 250:
                Input.ActionRelease("ship_translate_forward");
                Assert(_player.GlobalPosition.DistanceTo(_walkStart) > 0.5f, $"Player can walk on Planet B. Distance: {_player.GlobalPosition.DistanceTo(_walkStart):0.00}");
                GD.Print("Phase 5 validation passed.");
                GetTree().Quit(0);
                break;
        }
    }

    private void MoveShipTo(Vector3 position, Vector3 velocity)
    {
        var transform = _ship.GlobalTransform;
        transform.Basis = Basis.Identity;
        transform.Origin = position;
        _ship.GlobalTransform = transform;
        _ship.LinearVelocity = velocity;
        _ship.AngularVelocity = Vector3.Zero;
        _ship.Freeze = false;
        _ship.Sleeping = false;
    }

    private void Assert(bool condition, string message)
    {
        if (condition)
        {
            GD.Print($"PASS: {message}");
            return;
        }

        _failed = true;
        Input.ActionRelease("ship_translate_up");
        Input.ActionRelease("ship_translate_forward");
        GD.PushError($"FAIL: {message}");
        SetPhysicsProcess(false);
        GetTree().Quit(1);
    }
}
