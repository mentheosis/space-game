using Godot;

public partial class ShipController : RigidBody3D
{
    private enum PilotCameraMode
    {
        ExteriorOrbit,
        CockpitFirstPerson
    }

    [Export] public NodePath SeatAnchorPath { get; set; } = "Markers/SeatAnchor";
    [Export] public NodePath PilotEyePath { get; set; } = "Markers/PilotEye";
    [Export] public NodePath ShipCameraPath { get; set; } = "ShipCamera";
    [Export] public NodePath ExteriorVisualPath { get; set; } = "OpenGameArtShuttleVisual";
    [Export] public NodePath ExteriorGlassPath { get; set; } = "CockpitGlassExterior";
    [Export] public float MainThrust { get; set; } = 30.0f;
    [Export] public float ReverseThrust { get; set; } = 15.0f;
    [Export] public float LateralThrust { get; set; } = 24.0f;
    [Export] public float VerticalThrust { get; set; } = 50.0f;
    [Export] public float YawTorque { get; set; } = 80.0f;
    [Export] public float PitchTorque { get; set; } = 70.0f;
    [Export] public float RollTorque { get; set; } = 55.0f;
    [Export] public float BrakeStrength { get; set; } = 14.0f;
    [Export] public float MaxLandedSpeed { get; set; } = 3.0f;
    [Export] public float LandingDistance { get; set; } = 8.0f;
    [Export] public float MinLandingUpDot { get; set; } = 0.65f;
    [Export] public float OrbitCameraDistance { get; set; } = 15.0f;
    [Export] public float OrbitCameraTargetHeight { get; set; } = 1.6f;
    [Export] public float OrbitCameraHorizontalSensitivity { get; set; } = 0.003f;
    [Export] public float OrbitCameraVerticalSensitivity { get; set; } = 0.003f;
    [Export] public bool InvertOrbitCameraX { get; set; } = false;
    [Export] public bool InvertOrbitCameraY { get; set; } = false;
    [Export] public float OrbitCameraMinPitchDegrees { get; set; } = -35.0f;
    [Export] public float OrbitCameraMaxPitchDegrees { get; set; } = 75.0f;
    [Export] public float CockpitCameraHorizontalSensitivity { get; set; } = 0.0025f;
    [Export] public float CockpitCameraVerticalSensitivity { get; set; } = 0.0025f;
    [Export] public float CockpitCameraMinPitchDegrees { get; set; } = -35.0f;
    [Export] public float CockpitCameraMaxPitchDegrees { get; set; } = 55.0f;

    private Marker3D _seatAnchor = null!;
    private Marker3D? _pilotEye;
    private Camera3D _shipCamera = null!;
    private Node3D? _exteriorVisual;
    private Node3D? _exteriorGlass;
    private readonly Node3D?[] _interiorOnlyCanopyNodes = new Node3D?[2];
    private bool _exteriorVisualDefaultVisible = true;
    private bool _exteriorGlassDefaultVisible = true;
    private PlayerController? _pilot;
    private GravityBody? _activeGravityBody;
    private Vector3 _gravityAcceleration = Vector3.Zero;
    private Vector3 _gravityUp = Vector3.Up;
    private bool _isLanded = true;
    private PilotCameraMode _pilotCameraMode = PilotCameraMode.ExteriorOrbit;
    private float _orbitYaw;
    private float _orbitPitch = Mathf.DegToRad(22.0f);
    private float _cockpitYaw;
    private float _cockpitPitch;

    public bool IsPiloted => _pilot is not null;
    public bool IsLanded => _isLanded;
    public float Speed => LinearVelocity.Length();
    public Vector3 GravityAcceleration => _gravityAcceleration;
    public float GravityMagnitude => _gravityAcceleration.Length();
    public string ActiveGravityBodyName => _activeGravityBody?.Name ?? "Zero-G";
    public float SurfaceDistance => _activeGravityBody?.GetDistanceToSurface(GlobalPosition) ?? float.PositiveInfinity;
    public bool CanUseHatches => _isLanded && Speed <= MaxLandedSpeed;
    public bool IsCockpitCameraActive => _pilotCameraMode == PilotCameraMode.CockpitFirstPerson;

    public override void _Ready()
    {
        EnsureShipInputActions();
        _seatAnchor = GetNode<Marker3D>(SeatAnchorPath);
        _pilotEye = GetNodeOrNull<Marker3D>(PilotEyePath);
        _shipCamera = GetNode<Camera3D>(ShipCameraPath);
        _exteriorVisual = GetNodeOrNull<Node3D>(ExteriorVisualPath);
        _exteriorGlass = GetNodeOrNull<Node3D>(ExteriorGlassPath);
        _exteriorVisualDefaultVisible = _exteriorVisual?.Visible ?? true;
        _exteriorGlassDefaultVisible = _exteriorGlass?.Visible ?? true;
        CacheInteriorOnlyCanopyNodes();
        _shipCamera.Current = false;
        GravityScale = 0.0f;
        Freeze = true;
        _isLanded = true;
        SetInteriorViewActive(false);
        UpdatePilotCamera();
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (_pilot is null || Input.MouseMode != Input.MouseModeEnum.Captured)
        {
            return;
        }

        if (@event is InputEventMouseMotion motion)
        {
            UpdateMouseLook(motion);
        }
    }

    public override void _PhysicsProcess(double delta)
    {
        UpdateGravityState();
        UpdateLandedState();

        if (_pilot is not null)
        {
            if (Input.IsActionJustPressed("ship_toggle_camera"))
            {
                TogglePilotCameraMode();
            }

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
            UpdatePilotCamera();
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
        _pilotCameraMode = PilotCameraMode.ExteriorOrbit;
        SetInteriorViewActive(false);
        _shipCamera.Current = true;
        player.SetPlayerCameraActive(false);
        player.ForceSeatTransform(_seatAnchor.GlobalTransform);
        UpdatePilotCamera();
    }

    public void ClearPilot(PlayerController player)
    {
        if (_pilot == player)
        {
            _pilot = null;
            _pilotCameraMode = PilotCameraMode.ExteriorOrbit;
            _shipCamera.Current = false;
            SetInteriorViewActive(true);
            player.SetPlayerCameraActive(true);
        }
    }

    public void SetInteriorViewActive(bool active)
    {
        if (_exteriorVisual is not null)
        {
            _exteriorVisual.Visible = _exteriorVisualDefaultVisible && !active;
        }

        if (_exteriorGlass is not null)
        {
            _exteriorGlass.Visible = _exteriorGlassDefaultVisible && !active;
        }

        foreach (var node in _interiorOnlyCanopyNodes)
        {
            if (node is not null)
            {
                node.Visible = active;
            }
        }
    }

    private void CacheInteriorOnlyCanopyNodes()
    {
        _interiorOnlyCanopyNodes[0] = GetNodeOrNull<Node3D>("Interior/Cockpit/CanopyGlassInterior");
        _interiorOnlyCanopyNodes[1] = GetNodeOrNull<Node3D>("Interior/Cockpit/CanopyFrame");
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
        var forwardInput = Input.GetActionStrength("ship_translate_forward") - Input.GetActionStrength("ship_translate_back");
        var strafeInput = Input.GetActionStrength("ship_translate_right") - Input.GetActionStrength("ship_translate_left");
        var verticalInput = Input.GetActionStrength("ship_translate_up") - Input.GetActionStrength("ship_translate_down");
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

        if (Input.IsActionPressed("ship_brake"))
        {
            LinearVelocity = LinearVelocity.MoveToward(Vector3.Zero, BrakeStrength * delta);
            AngularVelocity = AngularVelocity.MoveToward(Vector3.Zero, BrakeStrength * delta);
        }
    }

    private bool HasPilotInput()
    {
        if (_isLanded)
        {
            return Input.GetActionStrength("ship_translate_up") > 0.0f;
        }

        return Input.IsActionPressed("ship_translate_forward")
            || Input.IsActionPressed("ship_translate_back")
            || Input.IsActionPressed("ship_translate_left")
            || Input.IsActionPressed("ship_translate_right")
            || Input.IsActionPressed("ship_translate_up")
            || Input.IsActionPressed("ship_translate_down")
            || Input.IsActionPressed("ship_brake")
            || Input.IsActionPressed("ship_yaw_left")
            || Input.IsActionPressed("ship_yaw_right")
            || Input.IsActionPressed("ship_pitch_up")
            || Input.IsActionPressed("ship_pitch_down")
            || Input.IsActionPressed("ship_roll_left")
            || Input.IsActionPressed("ship_roll_right");
    }

    private void TogglePilotCameraMode()
    {
        _pilotCameraMode = _pilotCameraMode == PilotCameraMode.ExteriorOrbit
            ? PilotCameraMode.CockpitFirstPerson
            : PilotCameraMode.ExteriorOrbit;

        if (_pilotCameraMode == PilotCameraMode.CockpitFirstPerson)
        {
            _cockpitYaw = 0.0f;
            _cockpitPitch = 0.0f;
        }

        SetInteriorViewActive(_pilotCameraMode == PilotCameraMode.CockpitFirstPerson);
        UpdatePilotCamera();
    }

    private void UpdateMouseLook(InputEventMouseMotion motion)
    {
        var yawDirection = InvertOrbitCameraX ? 1.0f : -1.0f;
        var pitchDirection = InvertOrbitCameraY ? 1.0f : -1.0f;

        if (_pilotCameraMode == PilotCameraMode.CockpitFirstPerson)
        {
            _cockpitYaw = Mathf.Clamp(
                _cockpitYaw + motion.Relative.X * CockpitCameraHorizontalSensitivity * yawDirection,
                Mathf.DegToRad(-70.0f),
                Mathf.DegToRad(70.0f));
            _cockpitPitch = Mathf.Clamp(
                _cockpitPitch + motion.Relative.Y * CockpitCameraVerticalSensitivity * pitchDirection,
                Mathf.DegToRad(CockpitCameraMinPitchDegrees),
                Mathf.DegToRad(CockpitCameraMaxPitchDegrees));
        }
        else
        {
            _orbitYaw += motion.Relative.X * OrbitCameraHorizontalSensitivity * yawDirection;
            _orbitPitch = Mathf.Clamp(
                _orbitPitch + motion.Relative.Y * OrbitCameraVerticalSensitivity * pitchDirection,
                Mathf.DegToRad(OrbitCameraMinPitchDegrees),
                Mathf.DegToRad(OrbitCameraMaxPitchDegrees));
        }

        UpdatePilotCamera();
    }

    private void UpdatePilotCamera()
    {
        if (_pilotCameraMode == PilotCameraMode.CockpitFirstPerson)
        {
            UpdateCockpitCamera();
        }
        else
        {
            UpdateOrbitCamera();
        }
    }

    private void UpdateOrbitCamera()
    {
        if (_shipCamera is null)
        {
            return;
        }

        var target = new Vector3(0.0f, OrbitCameraTargetHeight, 0.0f);
        var pitchCos = Mathf.Cos(_orbitPitch);
        var offset = new Vector3(
            Mathf.Sin(_orbitYaw) * pitchCos,
            Mathf.Sin(_orbitPitch),
            Mathf.Cos(_orbitYaw) * pitchCos) * OrbitCameraDistance;

        var cameraPosition = target + offset;
        var cameraTransform = new Transform3D(Basis.Identity, cameraPosition);
        _shipCamera.Transform = cameraTransform.LookingAt(target, Vector3.Up);
        _shipCamera.Fov = 72.0f;
    }

    private void UpdateCockpitCamera()
    {
        if (_shipCamera is null)
        {
            return;
        }

        var baseTransform = _pilotEye?.Transform
            ?? new Transform3D(_seatAnchor.Transform.Basis, _seatAnchor.Transform.Origin + new Vector3(0.0f, 0.14f, -0.34f));
        var lookBasis = Basis.FromEuler(new Vector3(_cockpitPitch, _cockpitYaw, 0.0f));
        _shipCamera.Transform = new Transform3D(baseTransform.Basis * lookBasis, baseTransform.Origin);
        _shipCamera.Fov = 78.0f;
    }

    private static void EnsureShipInputActions()
    {
        EnsureKeyAction("ship_translate_forward", Key.W);
        EnsureKeyAction("ship_translate_back", Key.S);
        EnsureKeyAction("ship_translate_left", Key.A);
        EnsureKeyAction("ship_translate_right", Key.D);
        EnsureKeyAction("ship_translate_up", Key.Space);
        EnsureKeyAction("ship_translate_down", Key.Shift);
        EnsureKeyAction("ship_brake", Key.Ctrl);
        EnsureKeyAction("ship_pitch_up", Key.Up);
        EnsureKeyAction("ship_pitch_down", Key.Down);
        EnsureKeyAction("ship_yaw_left", Key.Left);
        EnsureKeyAction("ship_yaw_right", Key.Right);
        EnsureKeyAction("ship_roll_left", Key.Q);
        EnsureKeyAction("ship_roll_right", Key.E);
        EnsureKeyAction("ship_toggle_camera", Key.V);
    }

    private static void EnsureKeyAction(string actionName, Key key)
    {
        if (!InputMap.HasAction(actionName))
        {
            InputMap.AddAction(actionName);
        }

        if (InputMap.ActionGetEvents(actionName).Count > 0)
        {
            return;
        }

        InputMap.ActionAddEvent(actionName, new InputEventKey { Keycode = key });
    }
}
