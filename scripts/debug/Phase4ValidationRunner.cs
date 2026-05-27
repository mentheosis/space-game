using Godot;

public partial class Phase4ValidationRunner : Node
{
    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public NodePath ShipPath { get; set; } = "../Ship";
    [Export] public NodePath ExteriorHatchPath { get; set; } = "../Ship/ExteriorHatch";
    [Export] public NodePath InteriorHatchPath { get; set; } = "../Ship/InteriorHatch";
    [Export] public NodePath PilotSeatPath { get; set; } = "../Ship/PilotSeat";
    [Export] public NodePath SeatAnchorPath { get; set; } = "../Ship/Markers/SeatAnchor";
    [Export] public NodePath ExteriorVisualPath { get; set; } = "../Ship/OpenGameArtShuttleVisual";

    private PlayerController _player = null!;
    private ShipController _ship = null!;
    private ShipHatch _exteriorHatch = null!;
    private ShipHatch _interiorHatch = null!;
    private PilotSeat _pilotSeat = null!;
    private Marker3D _seatAnchor = null!;
    private Node3D _exteriorVisual = null!;
    private Transform3D _startingShipTransform;
    private Vector3 _shipStartPosition;
    private Vector3 _interiorWalkStartLocal;
    private Vector3 _preStandLinearVelocity;
    private Vector3 _preStandAngularVelocity;
    private Vector3 _expectedExteriorExitVelocity;
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
        _exteriorVisual = GetNode<Node3D>(ExteriorVisualPath);
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
                Input.ActionPress("ship_translate_up");
                break;
            case 130:
                Input.ActionRelease("ship_translate_up");
                Assert(_ship.GlobalPosition.DistanceTo(_shipStartPosition) > 2.0f, $"Ship moved under thrust. Distance: {_ship.GlobalPosition.DistanceTo(_shipStartPosition):0.00}");
                Assert(_ship.Speed > 1.0f, $"Ship has velocity after thrust. Speed: {_ship.Speed:0.00}");
                Assert(!_ship.IsLanded, "Ship becomes airborne after takeoff thrust.");
                Assert(!_interiorHatch.CanInteract(_player), "Interior hatch cannot exit while airborne.");
                Assert(_pilotSeat.CanInteract(_player), "Pilot seat remains usable while airborne.");
                Assert(_player.DebugPlayerContext == PlayerContext.Seated, "Player remains seated before airborne stand test.");
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
                _preStandLinearVelocity = _ship.LinearVelocity;
                _preStandAngularVelocity = _ship.AngularVelocity;
                _pilotSeat.Interact(_player);
                break;
            case 151:
                Assert(_ship.AngularVelocity.DistanceTo(_preStandAngularVelocity) < 0.02f, $"Standing does not immediately add ship spin. Angular delta: {_ship.AngularVelocity.DistanceTo(_preStandAngularVelocity):0.000}");
                Assert(_ship.LinearVelocity.DistanceTo(_preStandLinearVelocity) < 1.5f, $"Standing does not immediately shove ship trajectory. Linear delta: {_ship.LinearVelocity.DistanceTo(_preStandLinearVelocity):0.000}");
                break;
            case 165:
                Assert(_player.DebugPlayerContext == PlayerContext.InShipInterior, "Player can stand from pilot seat while ship is airborne.");
                Assert(!_ship.IsPiloted, "Ship no longer has active pilot after airborne stand.");
                Assert(_ship.AngularVelocity.DistanceTo(_preStandAngularVelocity) < 0.02f, $"Standing preserves ship angular velocity. Before: {_preStandAngularVelocity.Length():0.000}, after: {_ship.AngularVelocity.Length():0.000}");
                Assert(_player.DebugUsingShipInteriorFrame, "Airborne interior player uses ship-local movement frame.");
                Assert(_player.DebugActiveGravityBodyName == "Ship Interior", $"Interior gravity is anchored to ship. Actual: {_player.DebugActiveGravityBodyName}");
                Assert(_player.DebugGravityDirection.Dot(-_ship.GlobalTransform.Basis.Y.Normalized()) > 0.99f, "Interior gravity points along ship-local down.");
                _interiorWalkStartLocal = ToShipLocal(_player.GlobalPosition);
                Input.ActionPress("move_back");
                break;
            case 205:
                Input.ActionRelease("move_back");
                var interiorWalkEndLocal = ToShipLocal(_player.GlobalPosition);
                var localWalkDistance = interiorWalkEndLocal.DistanceTo(_interiorWalkStartLocal);
                Assert(localWalkDistance > 0.25f, $"Player walks in ship-local interior frame while airborne. Local distance: {localWalkDistance:0.00}");
                Assert(_player.GlobalPosition.DistanceTo(_ship.GlobalPosition) < 20.0f, "Player remains near moving airborne ship after interior walk.");
                Assert(_ship.AngularVelocity.DistanceTo(_preStandAngularVelocity) < 0.02f, $"Walking inside does not add ship spin. Angular delta: {_ship.AngularVelocity.DistanceTo(_preStandAngularVelocity):0.000}");
                break;
            case 215:
                _pilotSeat.Interact(_player);
                break;
            case 235:
                Assert(_player.DebugPlayerContext == PlayerContext.Seated, "Player can sit back down while ship is airborne.");
                Assert(_ship.IsPiloted, "Ship restores active pilot after airborne re-seat.");
                Assert(_player.GlobalPosition.DistanceTo(_seatAnchor.GlobalPosition) < 0.5f, "Re-seated player follows moving seat anchor.");
                break;
            case 240:
                _pilotSeat.Interact(_player);
                break;
            case 245:
                Assert(_player.DebugPlayerContext == PlayerContext.InShipInterior, "Player can stand again before airborne exterior momentum handoff.");
                var exitLocalPosition = ToShipLocal(_player.GlobalPosition);
                exitLocalPosition.Z = 4.95f;
                var exitTransform = _player.GlobalTransform;
                exitTransform.Origin = _ship.GlobalTransform * exitLocalPosition;
                _player.MoveToTransform(exitTransform);
                _expectedExteriorExitVelocity = _ship.LinearVelocity
                    + _ship.AngularVelocity.Cross(_player.GlobalPosition - _ship.GlobalPosition)
                    + _player.Velocity;
                break;
            case 247:
                Assert(_player.DebugPlayerContext == PlayerContext.OnFoot, "Crossing the aft hatch boundary exits ship-local interior gravity.");
                Assert(_player.Velocity.DistanceTo(_expectedExteriorExitVelocity) < 1.0f, $"Airborne exterior exit inherits ship momentum. Delta: {_player.Velocity.DistanceTo(_expectedExteriorExitVelocity):0.000}");
                Assert(_exteriorVisual.Visible, "Exterior ShuttleA visual is restored after clipping outside interior bounds.");
                var reentryTransform = _player.GlobalTransform;
                reentryTransform.Origin = _ship.GlobalTransform * new Vector3(0.0f, 1.1f, -2.0f);
                _player.MoveToTransform(reentryTransform);
                break;
            case 249:
                Assert(_player.DebugPlayerContext == PlayerContext.InShipInterior, "Clipping back inside interior bounds restores ship interior context.");
                Assert(_player.DebugUsingShipInteriorFrame, "Clipping back inside interior bounds restores ship-local gravity frame.");
                Assert(!_exteriorVisual.Visible, "Exterior ShuttleA visual is hidden again after clipping back inside.");
                _player.MoveToTransform(_seatAnchor.GlobalTransform);
                _player.SetPlayerContext(PlayerContext.Seated);
                _ship.SetPilot(_player);
                break;
            case 250:
                _ship.GlobalTransform = _startingShipTransform;
                _ship.ForceLandedForValidation();
                _player.ForceSeatTransform(_seatAnchor.GlobalTransform);
                break;
            case 270:
                Assert(_ship.IsLanded, "Ship can be returned to landed state for exit validation.");
                _pilotSeat.Interact(_player);
                break;
            case 290:
                Assert(_player.DebugPlayerContext == PlayerContext.InShipInterior, "Player can stand after ship is landed.");
                _interiorHatch.Interact(_player);
                break;
            case 310:
                Assert(_player.DebugPlayerContext == PlayerContext.OnFoot, "Player can exit after landing.");
                Assert(!_ship.IsPiloted, "Ship has no active pilot after standing.");
                GD.Print("Phase 4 validation passed.");
                GetTree().Quit(0);
                break;
        }
    }

    private Vector3 ToShipLocal(Vector3 globalPosition)
    {
        return _ship.GlobalTransform.AffineInverse() * globalPosition;
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
