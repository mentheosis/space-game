using Godot;

public partial class Phase1ValidationRunner : Node
{
    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public NodePath GravityBodyPath { get; set; } = "../PlanetBody/GravityBody";

    private PlayerController _player = null!;
    private GravityBody _gravityBody = null!;
    private int _frame;
    private Vector3 _startPosition;
    private bool _sawGrounded;
    private bool _sawAirborneAfterJump;
    private bool _failed;

    public override void _Ready()
    {
        _player = GetNode<PlayerController>(PlayerPath);
        _gravityBody = GetNode<GravityBody>(GravityBodyPath);
        _startPosition = _player.GlobalPosition;

        Assert(GravityService.Instance is not null, "GravityService autoload exists.");
        Assert(GravityService.Instance?.GetBestBody(_player.GlobalPosition) == _gravityBody, "Planet gravity body is selected at player spawn.");
        Assert(_gravityBody.ContainsPoint(_player.GlobalPosition), "Player starts inside planet influence radius.");
    }

    public override void _PhysicsProcess(double delta)
    {
        if (_failed)
        {
            return;
        }

        _frame++;

        if (_frame == 30)
        {
            Input.ActionPress("move_forward");
        }

        if (_frame == 100)
        {
            Input.ActionPress("jump");
        }

        if (_frame == 101)
        {
            Input.ActionRelease("jump");
        }

        if (_frame > 30 && _player.DebugGrounded)
        {
            _sawGrounded = true;
        }

        if (_frame > 105 && !_player.DebugGrounded)
        {
            _sawAirborneAfterJump = true;
        }

        if (_frame == 420)
        {
            Input.ActionRelease("move_forward");
            ValidateFinalState();
            GetTree().Quit(_failed ? 1 : 0);
        }
    }

    private void ValidateFinalState()
    {
        var distanceMoved = _player.GlobalPosition.DistanceTo(_startPosition);
        var surfaceDistance = Mathf.Abs(_gravityBody.GetDistanceToSurface(_player.GlobalPosition));
        var upAlignment = _player.DebugUpDirection.Dot((_player.GlobalPosition - _gravityBody.GlobalPosition).Normalized());

        Assert(distanceMoved > 2.0f, $"Player moved across the planet surface. Distance: {distanceMoved:0.00}");
        Assert(_sawGrounded, "Player reported grounded during validation.");
        Assert(_sawAirborneAfterJump, "Player became airborne after jump input.");
        Assert(surfaceDistance < 3.0f, $"Player recovered near the planet surface. Surface distance: {surfaceDistance:0.00}");
        Assert(upAlignment > 0.98f, $"Player up direction matches radial surface up. Dot: {upAlignment:0.000}");

        if (!_failed)
        {
            GD.Print("Phase 1 validation passed.");
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
        GetTree().Quit(1);
    }
}

