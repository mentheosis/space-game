using Godot;

public partial class ShipController : RigidBody3D
{
    [Export] public NodePath SeatAnchorPath { get; set; } = "Markers/SeatAnchor";
    [Export] public NodePath ShipCameraPath { get; set; } = "ShipCamera";
    [Export] public float MainThrust { get; set; } = 30.0f;
    [Export] public float ReverseThrust { get; set; } = 15.0f;
    [Export] public float LateralThrust { get; set; } = 24.0f;
    [Export] public float VerticalThrust { get; set; } = 50.0f;
    [Export] public float YawTorque { get; set; } = 80.0f;
    [Export] public float PitchTorque { get; set; } = 70.0f;
    [Export] public float RollTorque { get; set; } = 55.0f;
    [Export] public float MaxLandedSpeed { get; set; } = 3.0f;
    [Export] public float LandingDistance { get; set; } = 8.0f;
    [Export] public float MinLandingUpDot { get; set; } = 0.65f;

    private Marker3D _seatAnchor = null!;
    private Camera3D _shipCamera = null!;
    private PlayerController? _pilot;
    private GravityBody? _activeGravityBody;
    private Vector3 _gravityAcceleration = Vector3.Zero;
    private Vector3 _gravityUp = Vector3.Up;
    private bool _isLanded = true;

    public bool IsPiloted => _pilot is not null;
    public bool IsLanded => _isLanded;
    public float Speed => LinearVelocity.Length();
    public Vector3 GravityAcceleration => _gravityAcceleration;
    public float SurfaceDistance => _activeGravityBody?.GetDistanceToSurface(GlobalPosition) ?? float.PositiveInfinity;
    public bool CanUseHatches => _isLanded && Speed <= MaxLandedSpeed;

    public override void _Ready()
    {
        _seatAnchor = GetNode<Marker3D>(SeatAnchorPath);
        _shipCamera = GetNode<Camera3D>(ShipCameraPath);
        _shipCamera.Current = false;
        GravityScale = 0.0f;
        Freeze = true;
        _isLanded = true;
    }

    public override void _PhysicsProcess(double delta)
    {
        UpdateGravityState();
        UpdateLandedState();

        if (_pilot is not null)
        {
            if (HasPilotInput())
            {
                Freeze = false;
                Sleeping = false;
            }

            if (!Freeze)
            {
                ApplyPilotInput((float)delta);
            }

            _pilot.ForceSeatTransform(_seatAnchor.GlobalTransform);
        }
        else if (_isLanded)
        {
            LinearVelocity = Vector3.Zero;
            AngularVelocity = Vector3.Zero;
            Freeze = true;
        }
    }

    public void SetPilot(PlayerController player)
    {
        _pilot = player;
        _shipCamera.Current = true;
        player.SetPlayerCameraActive(false);
        player.ForceSeatTransform(_seatAnchor.GlobalTransform);
    }

    public void ClearPilot(PlayerController player)
    {
        if (_pilot == player)
        {
            _pilot = null;
            _shipCamera.Current = false;
            player.SetPlayerCameraActive(true);
        }
    }

    public bool CanExitShip()
    {
        return CanUseHatches;
    }

    public void ForceLandedForValidation()
    {
        LinearVelocity = Vector3.Zero;
        AngularVelocity = Vector3.Zero;
        Freeze = true;
        _isLanded = true;
    }

    private void UpdateGravityState()
    {
        _activeGravityBody = GravityService.Instance?.GetBestBody(GlobalPosition);
        _gravityAcceleration = _activeGravityBody?.GetGravityAcceleration(GlobalPosition) ?? Vector3.Zero;
        _gravityUp = _gravityAcceleration.LengthSquared() > 0.0001f ? -_gravityAcceleration.Normalized() : GlobalTransform.Basis.Y;

        if (!Freeze && _gravityAcceleration.LengthSquared() > 0.0001f)
        {
            ApplyCentralForce(_gravityAcceleration * Mass);
        }
    }

    private void UpdateLandedState()
    {
        if (Freeze)
        {
            _isLanded = true;
            return;
        }

        var surfaceDistance = Mathf.Abs(SurfaceDistance);
        var uprightDot = GlobalTransform.Basis.Y.Normalized().Dot(_gravityUp);
        _isLanded = surfaceDistance <= LandingDistance
            && Speed <= MaxLandedSpeed
            && uprightDot >= MinLandingUpDot;
    }

    private void ApplyPilotInput(float delta)
    {
        var basis = GlobalTransform.Basis.Orthonormalized();
        var forwardInput = Input.GetActionStrength("move_forward") - Input.GetActionStrength("move_back");
        var strafeInput = Input.GetActionStrength("move_right") - Input.GetActionStrength("move_left");
        var verticalInput = Input.GetActionStrength("jump") - Input.GetActionStrength("jetpack");
        var yawInput = Input.GetActionStrength("ship_yaw_left") - Input.GetActionStrength("ship_yaw_right");
        var pitchInput = Input.GetActionStrength("ship_pitch_down") - Input.GetActionStrength("ship_pitch_up");
        var rollInput = Input.GetActionStrength("ship_roll_right") - Input.GetActionStrength("ship_roll_left");

        if (forwardInput > 0.0f)
        {
            ApplyCentralForce(-basis.Z * MainThrust * forwardInput * Mass);
        }
        else if (forwardInput < 0.0f)
        {
            ApplyCentralForce(basis.Z * ReverseThrust * -forwardInput * Mass);
        }

        if (!Mathf.IsZeroApprox(strafeInput))
        {
            ApplyCentralForce(basis.X * LateralThrust * strafeInput * Mass);
        }

        if (!Mathf.IsZeroApprox(verticalInput))
        {
            ApplyCentralForce(basis.Y * VerticalThrust * verticalInput * Mass);
        }

        if (!Mathf.IsZeroApprox(yawInput))
        {
            ApplyTorque(basis.Y * yawInput * YawTorque);
        }

        if (!Mathf.IsZeroApprox(pitchInput))
        {
            ApplyTorque(basis.X * pitchInput * PitchTorque);
        }

        if (!Mathf.IsZeroApprox(rollInput))
        {
            ApplyTorque(-basis.Z * rollInput * RollTorque);
        }
    }

    private bool HasPilotInput()
    {
        if (_isLanded)
        {
            return Input.GetActionStrength("jump") > 0.0f;
        }

        return Input.IsActionPressed("move_forward")
            || Input.IsActionPressed("move_back")
            || Input.IsActionPressed("move_left")
            || Input.IsActionPressed("move_right")
            || Input.IsActionPressed("jump")
            || Input.IsActionPressed("jetpack")
            || Input.IsActionPressed("ship_yaw_left")
            || Input.IsActionPressed("ship_yaw_right")
            || Input.IsActionPressed("ship_pitch_up")
            || Input.IsActionPressed("ship_pitch_down")
            || Input.IsActionPressed("ship_roll_left")
            || Input.IsActionPressed("ship_roll_right");
    }
}
