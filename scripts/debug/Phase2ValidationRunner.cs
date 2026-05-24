using Godot;

public partial class Phase2ValidationRunner : Node
{
    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public NodePath NormalGravityBodyPath { get; set; } = "../PlanetBody/GravityBody";
    [Export] public NodePath LowGravityMarkerPath { get; set; } = "../LowGravityMarker";
    [Export] public NodePath ZeroGMarkerPath { get; set; } = "../ZeroGMarker";

    private PlayerController _player = null!;
    private GravityBody _normalGravityBody = null!;
    private Marker3D _lowGravityMarker = null!;
    private Marker3D _zeroGMarker = null!;
    private int _frame;
    private bool _failed;
    private bool _sawJetpackFiring;
    private float _startingFuel;
    private float _lowestFuel;
    private float _highestSurfaceDistance;
    private float _fuelAfterRecharge;
    private float _zeroGSpeedAfterThrust;

    public override void _Ready()
    {
        _player = GetNode<PlayerController>(PlayerPath);
        _normalGravityBody = GetNode<GravityBody>(NormalGravityBodyPath);
        _lowGravityMarker = GetNode<Marker3D>(LowGravityMarkerPath);
        _zeroGMarker = GetNode<Marker3D>(ZeroGMarkerPath);

        _startingFuel = _player.DebugJetpackFuel;
        _lowestFuel = _startingFuel;

        Assert(GravityService.Instance is not null, "GravityService autoload exists.");
        Assert(GravityService.Instance?.GetBestBody(_player.GlobalPosition) == _normalGravityBody, "Normal planet gravity is selected at spawn.");
        Assert(_player.DebugJetpackFuel > 0.0f, "Player starts with jetpack fuel.");
    }

    public override void _PhysicsProcess(double delta)
    {
        if (_failed)
        {
            return;
        }

        _frame++;
        TrackJetpackSurfaceState();

        switch (_frame)
        {
            case 40:
                Input.ActionPress("jump");
                Input.ActionPress("jetpack");
                break;
            case 41:
                Input.ActionRelease("jump");
                break;
            case 130:
                Input.ActionRelease("jetpack");
                break;
            case 260:
                ValidateJetpackState();
                MovePlayerTo(_lowGravityMarker.GlobalPosition);
                break;
            case 285:
                Assert(_player.DebugMovementMode == PlayerMovementMode.WeakGravity, $"Player enters weak-gravity mode. Actual: {_player.DebugMovementMode}");
                MovePlayerTo(_zeroGMarker.GlobalPosition);
                break;
            case 310:
                Assert(_player.DebugMovementMode == PlayerMovementMode.ZeroGravity, $"Player enters zero-g mode. Actual: {_player.DebugMovementMode}");
                Input.ActionPress("move_forward");
                Input.ActionPress("jetpack");
                break;
            case 390:
                Input.ActionRelease("move_forward");
                Input.ActionRelease("jetpack");
                _zeroGSpeedAfterThrust = _player.DebugSpeed;
                break;
            case 430:
                ValidateZeroGravityState();
                GD.Print("Phase 2 validation passed.");
                GetTree().Quit(0);
                break;
        }
    }

    private void TrackJetpackSurfaceState()
    {
        _lowestFuel = Mathf.Min(_lowestFuel, _player.DebugJetpackFuel);
        _highestSurfaceDistance = Mathf.Max(_highestSurfaceDistance, Mathf.Abs(_normalGravityBody.GetDistanceToSurface(_player.GlobalPosition)));

        if (_player.DebugJetpackFiring)
        {
            _sawJetpackFiring = true;
        }

        if (_frame == 250)
        {
            _fuelAfterRecharge = _player.DebugJetpackFuel;
        }
    }

    private void ValidateJetpackState()
    {
        Assert(_sawJetpackFiring, "Jetpack fired during validation.");
        Assert(_lowestFuel < _startingFuel - 0.25f, $"Jetpack fuel decreased. Start: {_startingFuel:0.00}, lowest: {_lowestFuel:0.00}");
        Assert(_fuelAfterRecharge > _lowestFuel + 0.25f, $"Jetpack fuel recharged. Lowest: {_lowestFuel:0.00}, recharged: {_fuelAfterRecharge:0.00}");
        Assert(_highestSurfaceDistance > 1.25f, $"Jetpack increased surface distance. Highest: {_highestSurfaceDistance:0.00}");
    }

    private void ValidateZeroGravityState()
    {
        Assert(_player.DebugMovementMode == PlayerMovementMode.ZeroGravity, $"Player remains in zero-g mode. Actual: {_player.DebugMovementMode}");
        Assert(_zeroGSpeedAfterThrust > 1.0f, $"Zero-g jetpack thrust produced velocity. Speed: {_zeroGSpeedAfterThrust:0.00}");
        Assert(_player.DebugSpeed > 0.5f, $"Zero-g velocity persists after thrust release. Speed: {_player.DebugSpeed:0.00}");
    }

    private void MovePlayerTo(Vector3 globalPosition)
    {
        Input.ActionRelease("move_forward");
        Input.ActionRelease("move_back");
        Input.ActionRelease("move_left");
        Input.ActionRelease("move_right");
        Input.ActionRelease("jump");
        Input.ActionRelease("jetpack");
        Input.ActionRelease("brake");

        _player.GlobalPosition = globalPosition;
        _player.Velocity = Vector3.Zero;
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
        GetTree().Quit(1);
    }
}

