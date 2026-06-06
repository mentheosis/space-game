using Godot;

public enum PlayerMovementMode
{
    Surface,
    Airborne,
    WeakGravity,
    ZeroGravity
}

public enum PlayerContext
{
    OnFoot,
    InShipInterior,
    Seated
}

public partial class PlayerController : CharacterBody3D
{
    [Export] public float WalkSpeed { get; set; } = 7.0f;
    [Export] public float Acceleration { get; set; } = 20.0f;
    [Export] public float AirAcceleration { get; set; } = 6.0f;
    [Export] public float WeakGravityAcceleration { get; set; } = 12.0f;
    [Export] public float JumpSpeed { get; set; } = 10.0f;
    [Export] public float MouseHorizontalSensitivity { get; set; } = 0.0070f;
    [Export] public float MouseVerticalSensitivity { get; set; } = 0.0025f;
    [Export] public bool InvertMouseX { get; set; } = false;
    [Export] public bool InvertMouseY { get; set; } = false;
    [Export] public float AlignmentSharpness { get; set; } = 12.0f;
    [Export] public float JetpackFuelMax { get; set; } = 30.0f;
    [Export] public float JetpackFuelUseRate { get; set; } = 1.0f;
    [Export] public float JetpackFuelRechargeRate { get; set; } = 0.75f;
    [Export] public float JetpackUpThrust { get; set; } = 28.0f;
    [Export] public float JetpackDirectionalThrust { get; set; } = 10.0f;
    [Export] public float WeakGravityThreshold { get; set; } = 8.0f;
    [Export] public float ZeroGravityThreshold { get; set; } = 0.25f;
    [Export] public float ZeroGravityThrust { get; set; } = 8.0f;
    [Export] public float ZeroGravityBrakeStrength { get; set; } = 16.0f;
    [Export] public float ZeroGravityDamping { get; set; } = 0.05f;
    [Export] public float ShipInteriorGravityAcceleration { get; set; } = 18.0f;
    [Export] public bool AutoStepEnabled { get; set; } = false;
    [Export] public float AutoStepHeight { get; set; } = 1.1f;
    [Export] public float AutoStepForwardProbe { get; set; } = 0.58f;
    [Export] public float AutoStepDownProbe { get; set; } = 1.1f;
    [Export] public bool AutoStepUseSurfaceProjection { get; set; } = false;
    [Export] public bool AutoStepHorizontalCatchup { get; set; } = true;
    [Export] public int AutoStepProbeCount { get; set; } = 5;
    [Export] public float AutoStepLateralProbeSpacing { get; set; } = 0.24f;
    [Export] public bool UseWalkableSupportSurfaces { get; set; } = true;
    [Export(PropertyHint.Layers3DPhysics)] public uint WalkableSupportCollisionMask { get; set; } = 1u << 7;
    [Export] public float WalkableSupportMaxRise { get; set; } = 1.15f;
    [Export] public float WalkableSupportMaxDrop { get; set; } = 1.35f;
    [Export] public float WalkableSupportProbePadding { get; set; } = 0.25f;
    [Export] public float WalkableSupportJumpDetachTime { get; set; } = 0.22f;
    [Export] public float ShipInteriorAftExitLocalZ { get; set; } = 4.75f;
    [Export] public Vector3 ShipInteriorBoundsMin { get; set; } = new(-2.55f, -0.8f, -11.3f);
    [Export] public Vector3 ShipInteriorBoundsMax { get; set; } = new(2.55f, 3.8f, 4.35f);
    [Export] public float OxygenMax { get; set; } = 120.0f;
    [Export] public NodePath ViewPivotPath { get; set; } = "ViewPivot";
    [Export] public NodePath CameraPath { get; set; } = "ViewPivot/Camera3D";
    [Export] public NodePath CollisionShapePath { get; set; } = "CollisionShape3D";

    private Node3D _viewPivot = null!;
    private Camera3D _camera = null!;
    private CollisionShape3D _collisionShape = null!;
    private float _pitch;
    private float _pendingYaw;
    private Vector3 _lastUp = Vector3.Up;
    private Vector3 _lastGravityDirection = Vector3.Down;
    private Vector3 _lastGravityAcceleration = Vector3.Zero;
    private string _activeGravityBodyName = "None";
    private PlayerMovementMode _movementMode = PlayerMovementMode.Airborne;
    private PlayerContext _playerContext = PlayerContext.OnFoot;
    private float _jetpackFuel;
    private float _oxygen;
    private bool _jetpackFiring;
    private IInteractable? _seatedInteractable;
    private ShipController? _interiorShip;
    private Transform3D _shipLocalTransform = Transform3D.Identity;
    private Vector3 _shipLocalVelocity = Vector3.Zero;
    private uint _defaultPlatformFloorLayers;
    private int _autoStepCount;
    private bool _hasWalkableSupport;
    private Vector3 _lastWalkableSupportPoint = Vector3.Zero;
    private float _walkableSupportClearance = 0.9f;
    private float _walkableSupportDetachTimer;

    public bool DebugGrounded => IsOnFloor();
    public Vector3 DebugUpDirection => _lastUp;
    public Vector3 DebugGravityDirection => _lastGravityDirection;
    public Vector3 DebugGravityAcceleration => _lastGravityAcceleration;
    public string DebugActiveGravityBodyName => _activeGravityBodyName;
    public float DebugSpeed => Velocity.Length();
    public PlayerMovementMode DebugMovementMode => _movementMode;
    public float DebugJetpackFuel => _jetpackFuel;
    public float DebugJetpackFuelMax => JetpackFuelMax;
    public float DebugOxygen => _oxygen;
    public float DebugOxygenMax => OxygenMax;
    public bool DebugJetpackFiring => _jetpackFiring;
    public PlayerContext DebugPlayerContext => _playerContext;
    public bool DebugMovementEnabled => IsMovementEnabled;
    public IInteractable? SeatedInteractable => _seatedInteractable;
    public bool DebugUsingShipInteriorFrame => _interiorShip is not null && _playerContext == PlayerContext.InShipInterior;
    public int DebugAutoStepCount => _autoStepCount;
    public string DebugGravityFrame => DebugUsingShipInteriorFrame
        ? "Ship Interior"
        : _lastGravityAcceleration.Length() <= ZeroGravityThreshold
            ? "Space / Zero-G"
            : "Planetary / External";

    private bool IsMovementEnabled => _playerContext != PlayerContext.Seated;

    public override void _Ready()
    {
        _viewPivot = GetNode<Node3D>(ViewPivotPath);
        _camera = GetNode<Camera3D>(CameraPath);
        _collisionShape = GetNode<CollisionShape3D>(CollisionShapePath);
        _jetpackFuel = JetpackFuelMax;
        _oxygen = OxygenMax;
        _defaultPlatformFloorLayers = PlatformFloorLayers;
        if (_collisionShape.Shape is CapsuleShape3D capsule)
        {
            _walkableSupportClearance = capsule.Height * 0.5f;
        }
        FloorStopOnSlope = true;
        MotionMode = MotionModeEnum.Grounded;
        Input.MouseMode = Input.MouseModeEnum.Captured;
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (@event is InputEventMouseMotion motion && Input.MouseMode == Input.MouseModeEnum.Captured)
        {
            var yawDirection = InvertMouseX ? 1.0f : -1.0f;
            var pitchDirection = InvertMouseY ? 1.0f : -1.0f;
            _pendingYaw += motion.Relative.X * MouseHorizontalSensitivity * yawDirection;
            _pitch = Mathf.Clamp(_pitch + motion.Relative.Y * MouseVerticalSensitivity * pitchDirection, Mathf.DegToRad(-85.0f), Mathf.DegToRad(85.0f));
            _viewPivot.Rotation = new Vector3(_pitch, 0.0f, 0.0f);
        }
    }

    public override void _PhysicsProcess(double delta)
    {
        var deltaSeconds = (float)delta;
        _jetpackFiring = false;
        _walkableSupportDetachTimer = Mathf.Max(0.0f, _walkableSupportDetachTimer - deltaSeconds);

        ApplyShipInteriorFrame();
        UpdateGravityState();
        UpdateWalkableSupportState();
        UpdateMovementMode();
        UpdateBodyAlignment(deltaSeconds);
        if (IsMovementEnabled)
        {
            ApplyMovement(deltaSeconds);
        }
        else
        {
            Velocity = Vector3.Zero;
            MoveAndSlide();
        }
        CaptureShipInteriorFrame();
        UpdateShipInteriorContainment();
        UpdateSuitResources(deltaSeconds);
    }

    public void SetPlayerContext(PlayerContext context)
    {
        _playerContext = context;
        _collisionShape.Disabled = context == PlayerContext.Seated;
        if (context != PlayerContext.InShipInterior)
        {
            ClearShipInteriorFrame();
        }
        PlatformFloorLayers = context == PlayerContext.InShipInterior ? 0u : _defaultPlatformFloorLayers;
        if (context != PlayerContext.Seated)
        {
            _seatedInteractable = null;
        }
    }

    public void SetSeatedInteractable(IInteractable? interactable)
    {
        _seatedInteractable = interactable;
    }

    public void MoveToTransform(Transform3D targetTransform)
    {
        GlobalTransform = targetTransform;
        Velocity = Vector3.Zero;
        CaptureShipInteriorFrame();
    }

    public void ForceSeatTransform(Transform3D seatTransform)
    {
        if (_playerContext == PlayerContext.Seated)
        {
            MoveToTransform(seatTransform);
        }
    }

    public void SetPlayerCameraActive(bool active)
    {
        _camera.Current = active;
    }

    public void AttachToShipInteriorFrame(ShipController? ship, bool preserveRelativeVelocity = false)
    {
        _interiorShip = ship;

        if (_interiorShip is null)
        {
            _shipLocalTransform = Transform3D.Identity;
            _shipLocalVelocity = Vector3.Zero;
            return;
        }

        var shipTransform = _interiorShip.GlobalTransform;
        var shipBasis = shipTransform.Basis.Orthonormalized();
        _shipLocalTransform = shipTransform.AffineInverse() * GlobalTransform;

        var frameVelocity = preserveRelativeVelocity
            ? _interiorShip.LinearVelocity + _interiorShip.AngularVelocity.Cross(GlobalPosition - _interiorShip.GlobalPosition)
            : Vector3.Zero;
        _shipLocalVelocity = shipBasis.Inverse() * (Velocity - frameVelocity);
    }

    public void ClearShipInteriorFrame()
    {
        _interiorShip = null;
        _shipLocalTransform = Transform3D.Identity;
        _shipLocalVelocity = Vector3.Zero;
    }

    public void DetachFromShipInteriorFrame(bool inheritShipMomentum)
    {
        if (_interiorShip is not null && inheritShipMomentum)
        {
            var shipBasis = _interiorShip.GlobalTransform.Basis.Orthonormalized();
            var radiusFromShipCenter = GlobalPosition - _interiorShip.GlobalPosition;
            Velocity = _interiorShip.LinearVelocity
                + _interiorShip.AngularVelocity.Cross(radiusFromShipCenter)
                + shipBasis * _shipLocalVelocity;
        }

        ClearShipInteriorFrame();
    }

    private void UpdateGravityState()
    {
        if (_playerContext == PlayerContext.InShipInterior && _interiorShip is not null)
        {
            var shipBasis = _interiorShip.GlobalTransform.Basis.Orthonormalized();
            _activeGravityBodyName = $"{_interiorShip.Name} Interior";
            _lastUp = shipBasis.Y.Normalized();
            _lastGravityDirection = -_lastUp;
            _lastGravityAcceleration = _lastGravityDirection * ShipInteriorGravityAcceleration;
            UpDirection = _lastUp;
            return;
        }

        var service = GravityService.Instance;
        var body = service?.GetBestBody(GlobalPosition);

        _activeGravityBodyName = body?.Name ?? "None";
        _lastGravityAcceleration = body?.GetGravityAcceleration(GlobalPosition) ?? Vector3.Zero;

        if (_lastGravityAcceleration.LengthSquared() > 0.0001f)
        {
            _lastGravityDirection = _lastGravityAcceleration.Normalized();
            _lastUp = -_lastGravityDirection;
        }
        else
        {
            _lastGravityDirection = Vector3.Zero;
            _lastUp = GlobalTransform.Basis.Orthonormalized().Y;
        }

        UpDirection = _lastUp;
    }

    private void ApplyShipInteriorFrame()
    {
        if (_playerContext != PlayerContext.InShipInterior || _interiorShip is null)
        {
            return;
        }

        GlobalTransform = _interiorShip.GlobalTransform * _shipLocalTransform;
        Velocity = _interiorShip.GlobalTransform.Basis.Orthonormalized() * _shipLocalVelocity;
    }

    private void CaptureShipInteriorFrame()
    {
        if (_playerContext != PlayerContext.InShipInterior || _interiorShip is null)
        {
            return;
        }

        _shipLocalTransform = _interiorShip.GlobalTransform.AffineInverse() * GlobalTransform;
        _shipLocalVelocity = _interiorShip.GlobalTransform.Basis.Orthonormalized().Inverse() * Velocity;
    }

    private void UpdateShipInteriorContainment()
    {
        if (_playerContext != PlayerContext.InShipInterior || _interiorShip is null)
        {
            return;
        }

        if (IsInsideShipInteriorBounds(_shipLocalTransform.Origin)
            && _shipLocalTransform.Origin.Z <= GetShipInteriorAftExitLocalZ())
        {
            return;
        }

        var ship = _interiorShip;
        DetachFromShipInteriorFrame(inheritShipMomentum: true);
        SetPlayerContext(PlayerContext.OnFoot);
        ship.SetInteriorViewActive(false);
    }

    private bool IsInsideShipInteriorBounds(Vector3 shipLocalPosition)
    {
        var boundsMin = _interiorShip?.InteriorBoundsMin ?? ShipInteriorBoundsMin;
        var boundsMax = _interiorShip?.InteriorBoundsMax ?? ShipInteriorBoundsMax;
        return shipLocalPosition.X >= boundsMin.X
            && shipLocalPosition.X <= boundsMax.X
            && shipLocalPosition.Y >= boundsMin.Y
            && shipLocalPosition.Y <= boundsMax.Y
            && shipLocalPosition.Z >= boundsMin.Z
            && shipLocalPosition.Z <= boundsMax.Z;
    }

    private float GetShipInteriorAftExitLocalZ()
    {
        return _interiorShip?.InteriorAftExitLocalZ ?? ShipInteriorAftExitLocalZ;
    }

    private void UpdateMovementMode()
    {
        var gravityMagnitude = _lastGravityAcceleration.Length();

        if (IsOnFloor() || _hasWalkableSupport)
        {
            _movementMode = PlayerMovementMode.Surface;
        }
        else if (gravityMagnitude <= ZeroGravityThreshold)
        {
            _movementMode = PlayerMovementMode.ZeroGravity;
        }
        else if (gravityMagnitude < WeakGravityThreshold)
        {
            _movementMode = PlayerMovementMode.WeakGravity;
        }
        else
        {
            _movementMode = PlayerMovementMode.Airborne;
        }
    }

    private void UpdateBodyAlignment(float delta)
    {
        AlignToUp(delta, _lastUp);
    }

    private void AlignToUp(float delta, Vector3 targetUp)
    {
        var basis = GlobalTransform.Basis.Orthonormalized();
        var forward = -basis.Z;
        forward = ProjectOnPlane(forward, targetUp);

        if (forward.LengthSquared() < 0.0001f)
        {
            forward = ProjectOnPlane(Vector3.Forward, targetUp);
        }

        if (forward.LengthSquared() < 0.0001f)
        {
            forward = ProjectOnPlane(Vector3.Right, targetUp);
        }

        forward = RotateAroundAxis(forward.Normalized(), targetUp, _pendingYaw).Normalized();
        _pendingYaw = 0.0f;

        var right = forward.Cross(targetUp).Normalized();
        var backward = -forward;
        var targetBasis = new Basis(right, targetUp, backward).Orthonormalized();

        var currentRotation = GlobalTransform.Basis.Orthonormalized().GetRotationQuaternion();
        var targetRotation = targetBasis.GetRotationQuaternion();
        var weight = 1.0f - Mathf.Exp(-AlignmentSharpness * delta);
        var alignedBasis = new Basis(currentRotation.Slerp(targetRotation, weight)).Orthonormalized();

        var transform = GlobalTransform;
        transform.Basis = alignedBasis;
        GlobalTransform = transform;
    }

    private void ApplyMovement(float delta)
    {
        var input = Input.GetVector("move_left", "move_right", "move_forward", "move_back");

        switch (_movementMode)
        {
            case PlayerMovementMode.Surface:
                ApplySurfaceMovement(delta, input);
                break;
            case PlayerMovementMode.WeakGravity:
                ApplyAirborneMovement(delta, input, WeakGravityAcceleration);
                break;
            case PlayerMovementMode.ZeroGravity:
                ApplyZeroGravityMovement(delta, input);
                break;
            default:
                ApplyAirborneMovement(delta, input, AirAcceleration);
                break;
        }
    }

    private void ApplySurfaceMovement(float delta, Vector2 input)
    {
        var desiredDirection = GetSurfaceMoveDirection(input);
        var velocity = Velocity;
        var verticalSpeed = velocity.Dot(_lastUp);
        var verticalVelocity = _lastUp * verticalSpeed;
        var horizontalVelocity = velocity - verticalVelocity;
        var targetHorizontalVelocity = desiredDirection * WalkSpeed;
        var jumpPressed = Input.IsActionJustPressed("jump");

        horizontalVelocity = horizontalVelocity.MoveToward(targetHorizontalVelocity, Acceleration * delta);
        if (_hasWalkableSupport && !jumpPressed)
        {
            verticalVelocity = Vector3.Zero;
        }
        else
        {
            verticalVelocity += _lastGravityAcceleration * delta;
        }

        if (jumpPressed)
        {
            verticalVelocity = _lastUp * JumpSpeed;
            _walkableSupportDetachTimer = WalkableSupportJumpDetachTime;
        }

        velocity = horizontalVelocity + verticalVelocity;
        ApplyJetpack(delta, input, ref velocity);

        if (UseWalkableSupportSurfaces
            && _hasWalkableSupport
            && !jumpPressed
            && !_jetpackFiring)
        {
            Velocity = horizontalVelocity;
            MoveAndSlide();
            TrySnapToWalkableSupportSurface();
            return;
        }

        Velocity = velocity;
        MoveAndSlide();
    }

    private bool TryProjectedSurfaceMove(bool wasOnFloor, Transform3D transformBeforeMove, Vector3 desiredDirection, Vector3 intendedHorizontalVelocity, float delta)
    {
        if (!AutoStepEnabled
            || !wasOnFloor
            || intendedHorizontalVelocity.LengthSquared() < 0.0001f)
        {
            return false;
        }

        if (!TryGetWalkableSurface(transformBeforeMove.Origin, out var currentSurface))
        {
            return false;
        }

        if (!TryResolveAutoStepDirection(transformBeforeMove.Origin, desiredDirection, intendedHorizontalVelocity, out var forward))
        {
            return false;
        }

        var motionLength = ProjectOnPlane(intendedHorizontalVelocity * delta, _lastUp).Length();
        if (motionLength <= 0.001f)
        {
            return false;
        }

        var horizontalMotion = forward * motionLength;
        if (!TryGetProjectedSurfaceAhead(transformBeforeMove.Origin, forward, currentSurface, out var targetSurface))
        {
            return false;
        }

        var currentSurfaceHeight = currentSurface.Dot(_lastUp);
        var targetSurfaceHeight = targetSurface.Dot(_lastUp);
        var heightDelta = targetSurfaceHeight - currentSurfaceHeight;
        if (Mathf.Abs(heightDelta) <= 0.02f)
        {
            return false;
        }

        if (heightDelta > AutoStepHeight || heightDelta < -AutoStepDownProbe)
        {
            return false;
        }

        var originSurfaceClearance = transformBeforeMove.Origin.Dot(_lastUp) - currentSurfaceHeight;
        var projectedHorizontalPosition = transformBeforeMove.Origin + horizontalMotion;
        var targetOriginHeight = targetSurfaceHeight + originSurfaceClearance;
        var projectedPosition = projectedHorizontalPosition + _lastUp * (targetOriginHeight - projectedHorizontalPosition.Dot(_lastUp));

        GlobalPosition = projectedPosition;
        Velocity = intendedHorizontalVelocity;
        _autoStepCount++;
        return true;
    }

    private bool TryVerticalTerrainAssist(bool wasOnFloor, Transform3D transformBeforeMove, Vector3 desiredDirection, Vector3 intendedHorizontalVelocity, float delta)
    {
        if (!AutoStepEnabled
            || !wasOnFloor
            || Input.IsActionJustPressed("jump"))
        {
            return false;
        }

        var startPosition = transformBeforeMove.Origin;
        var horizontalProgress = ProjectOnPlane(GlobalPosition - startPosition, _lastUp).Length();
        var expectedProgress = Mathf.Min(WalkSpeed * delta, AutoStepForwardProbe);
        if (horizontalProgress >= expectedProgress * 0.45f)
        {
            return false;
        }

        if (!TryResolveAutoStepDirection(startPosition, desiredDirection, intendedHorizontalVelocity, out var forward))
        {
            return false;
        }

        if (!TryGetWalkableSurface(GlobalPosition, out var currentSurface))
        {
            return false;
        }

        if (!TryGetProjectedSurfaceAhead(GlobalPosition, forward, currentSurface, out var aheadSurface))
        {
            return false;
        }

        var currentHeight = currentSurface.Dot(_lastUp);
        var aheadHeight = aheadSurface.Dot(_lastUp);
        var heightDelta = aheadHeight - currentHeight;
        if (heightDelta <= 0.025f || heightDelta > AutoStepHeight)
        {
            return false;
        }

        var liftMotion = _lastUp * (heightDelta + 0.015f);
        if (TestMove(GlobalTransform, liftMotion))
        {
            return false;
        }

        GlobalPosition += liftMotion;
        if (AutoStepHorizontalCatchup)
        {
            var remainingProgress = Mathf.Max(0.0f, expectedProgress - horizontalProgress);
            var catchupMotion = forward * remainingProgress;
            if (catchupMotion.LengthSquared() > 0.0001f && !TestMove(GlobalTransform, catchupMotion))
            {
                GlobalPosition += catchupMotion;
            }
        }

        Velocity = intendedHorizontalVelocity;
        _autoStepCount++;
        return true;
    }

    private bool TryResolveAutoStepDirection(Vector3 startPosition, Vector3 desiredDirection, Vector3 intendedHorizontalVelocity, out Vector3 direction)
    {
        var intended = ProjectOnPlane(intendedHorizontalVelocity, _lastUp);
        if (intended.LengthSquared() > 0.0001f)
        {
            direction = intended.Normalized();
            return true;
        }

        var actual = ProjectOnPlane(GlobalPosition - startPosition, _lastUp);
        if (actual.LengthSquared() > 0.0001f)
        {
            direction = actual.Normalized();
            return true;
        }

        var desired = ProjectOnPlane(desiredDirection, _lastUp);
        if (desired.LengthSquared() > 0.0001f)
        {
            direction = desired.Normalized();
            return true;
        }

        direction = Vector3.Zero;
        return false;
    }

    private void UpdateWalkableSupportState()
    {
        _hasWalkableSupport = false;
        _lastWalkableSupportPoint = Vector3.Zero;
        if (!UseWalkableSupportSurfaces || _walkableSupportDetachTimer > 0.0f)
        {
            return;
        }

        _hasWalkableSupport = TryGetWalkableSupportSurface(GlobalPosition, out _lastWalkableSupportPoint);
    }

    private bool TrySnapToWalkableSupportSurface()
    {
        if (!TryGetWalkableSupportSurface(GlobalPosition, out var supportPoint))
        {
            return false;
        }

        var targetOriginHeight = supportPoint.Dot(_lastUp) + _walkableSupportClearance;
        var currentOriginHeight = GlobalPosition.Dot(_lastUp);
        var heightDelta = targetOriginHeight - currentOriginHeight;
        if (heightDelta > WalkableSupportMaxRise || heightDelta < -WalkableSupportMaxDrop)
        {
            return false;
        }

        if (Mathf.Abs(heightDelta) > 0.005f)
        {
            GlobalPosition += _lastUp * heightDelta;
        }

        Velocity = ProjectOnPlane(Velocity, _lastUp);
        _lastWalkableSupportPoint = supportPoint;
        _hasWalkableSupport = true;
        return true;
    }

    private bool TryGetWalkableSupportSurface(Vector3 origin, out Vector3 surfacePosition)
    {
        surfacePosition = Vector3.Zero;
        if (WalkableSupportCollisionMask == 0)
        {
            return false;
        }

        var from = origin + _lastUp * (WalkableSupportMaxRise + WalkableSupportProbePadding);
        var to = origin - _lastUp * (WalkableSupportMaxDrop + WalkableSupportProbePadding);
        var query = PhysicsRayQueryParameters3D.Create(
            from,
            to,
            WalkableSupportCollisionMask,
            new Godot.Collections.Array<Rid> { GetRid() });
        query.CollideWithAreas = false;
        query.CollideWithBodies = true;
        query.HitBackFaces = false;

        var hit = GetWorld3D().DirectSpaceState.IntersectRay(query);
        if (hit.Count == 0)
        {
            return false;
        }

        var normal = hit["normal"].AsVector3();
        if (normal.Dot(_lastUp) < 0.55f)
        {
            return false;
        }

        surfacePosition = hit["position"].AsVector3();
        return true;
    }

    private bool TryGetBestAheadSurface(Vector3 forward, Vector3 currentSurface, out Vector3 bestSurface)
    {
        var right = forward.Cross(_lastUp);
        if (right.LengthSquared() < 0.0001f)
        {
            right = GlobalTransform.Basis.X;
        }
        right = right.Normalized();

        var probeDistance = Mathf.Max(AutoStepForwardProbe, 0.28f);
        var bestDelta = float.MaxValue;
        var found = false;
        bestSurface = Vector3.Zero;

        foreach (var lateralOffset in GetAutoStepLateralOffsets())
        {
            var probeOrigin = GlobalPosition + forward * probeDistance + right * lateralOffset;
            if (!TryGetWalkableSurface(probeOrigin, out var surface))
            {
                continue;
            }

            var delta = surface.Dot(_lastUp) - currentSurface.Dot(_lastUp);
            if (delta <= 0.025f || delta > AutoStepHeight || delta >= bestDelta)
            {
                continue;
            }

            bestDelta = delta;
            bestSurface = surface;
            found = true;
        }

        return found;
    }

    private bool TryGetProjectedSurfaceAhead(Vector3 origin, Vector3 forward, Vector3 currentSurface, out Vector3 bestSurface)
    {
        var right = forward.Cross(_lastUp);
        if (right.LengthSquared() < 0.0001f)
        {
            right = GlobalTransform.Basis.X;
        }
        right = right.Normalized();

        var currentHeight = currentSurface.Dot(_lastUp);
        var bestDistance = float.MaxValue;
        var bestClimb = float.MaxValue;
        var found = false;
        bestSurface = Vector3.Zero;

        var probeCount = Mathf.Max(2, AutoStepProbeCount);
        for (var probeIndex = 1; probeIndex <= probeCount; probeIndex++)
        {
            var distance = AutoStepForwardProbe * (probeIndex / (float)probeCount);
            foreach (var lateralOffset in GetAutoStepLateralOffsets())
            {
                var probeOrigin = origin + forward * distance + right * lateralOffset;
                if (!TryGetWalkableSurface(probeOrigin, out var surface))
                {
                    continue;
                }

                var heightDelta = surface.Dot(_lastUp) - currentHeight;
                if (heightDelta <= 0.02f || heightDelta > AutoStepHeight)
                {
                    continue;
                }

                if (distance < bestDistance - 0.001f
                    || (Mathf.Abs(distance - bestDistance) <= 0.001f && heightDelta < bestClimb))
                {
                    bestDistance = distance;
                    bestClimb = heightDelta;
                    bestSurface = surface;
                    found = true;
                }
            }
        }

        return found;
    }

    private float[] GetAutoStepLateralOffsets()
    {
        var spacing = Mathf.Max(0.0f, AutoStepLateralProbeSpacing);
        return new[] { 0.0f, -spacing, spacing, -spacing * 1.75f, spacing * 1.75f };
    }

    private bool TryGetWalkableSurface(Vector3 origin, out Vector3 surfacePosition)
    {
        var from = origin + _lastUp * (AutoStepHeight + 0.25f);
        var to = origin - _lastUp * (AutoStepDownProbe + 0.25f);
        var query = PhysicsRayQueryParameters3D.Create(
            from,
            to,
            CollisionMask,
            new Godot.Collections.Array<Rid> { GetRid() });
        query.CollideWithAreas = false;
        query.CollideWithBodies = true;
        query.HitBackFaces = false;

        var hit = GetWorld3D().DirectSpaceState.IntersectRay(query);
        if (hit.Count == 0)
        {
            surfacePosition = Vector3.Zero;
            return false;
        }

        var normal = hit["normal"].AsVector3();
        if (normal.Dot(_lastUp) < 0.55f)
        {
            surfacePosition = Vector3.Zero;
            return false;
        }

        surfacePosition = hit["position"].AsVector3();
        return true;
    }

    private void ApplyAirborneMovement(float delta, Vector2 input, float airControl)
    {
        var desiredDirection = GetSurfaceMoveDirection(input);
        var velocity = Velocity;
        var verticalSpeed = velocity.Dot(_lastUp);
        var verticalVelocity = _lastUp * verticalSpeed;
        var horizontalVelocity = velocity - verticalVelocity;
        var targetHorizontalVelocity = desiredDirection * WalkSpeed;

        horizontalVelocity = horizontalVelocity.MoveToward(targetHorizontalVelocity, airControl * delta);
        verticalVelocity += _lastGravityAcceleration * delta;

        velocity = horizontalVelocity + verticalVelocity;
        ApplyJetpack(delta, input, ref velocity);
        Velocity = velocity;
        MoveAndSlide();
    }

    private void ApplyZeroGravityMovement(float delta, Vector2 input)
    {
        var velocity = Velocity;

        if (Input.IsActionPressed("brake"))
        {
            velocity = velocity.MoveToward(Vector3.Zero, ZeroGravityBrakeStrength * delta);
        }
        else
        {
            velocity = velocity.MoveToward(Vector3.Zero, ZeroGravityDamping * delta);
        }

        ApplyJetpack(delta, input, ref velocity);
        Velocity = velocity;
        MoveAndSlide();
    }

    private void ApplyJetpack(float delta, Vector2 input, ref Vector3 velocity)
    {
        if (!Input.IsActionPressed("jetpack") || _jetpackFuel <= 0.0f)
        {
            return;
        }

        var requestedFuel = JetpackFuelUseRate * delta;
        var consumedFuel = Mathf.Min(_jetpackFuel, requestedFuel);
        var fuelScale = requestedFuel > 0.0f ? consumedFuel / requestedFuel : 0.0f;

        _jetpackFuel -= consumedFuel;
        _jetpackFiring = consumedFuel > 0.0f;

        if (!_jetpackFiring)
        {
            return;
        }

        var thrust = _movementMode == PlayerMovementMode.ZeroGravity
            ? GetZeroGravityThrustDirection(input) * ZeroGravityThrust
            : GetGravityJetpackThrust(input);

        velocity += thrust * fuelScale * delta;
    }

    private void UpdateSuitResources(float delta)
    {
        if (!_jetpackFiring)
        {
            _jetpackFuel = Mathf.Min(JetpackFuelMax, _jetpackFuel + JetpackFuelRechargeRate * delta);
        }

        _oxygen = Mathf.Clamp(_oxygen, 0.0f, OxygenMax);
    }

    private Vector3 GetGravityJetpackThrust(Vector2 input)
    {
        var directional = GetSurfaceMoveDirection(input) * JetpackDirectionalThrust;
        return _lastUp * JetpackUpThrust + directional;
    }

    private Vector3 GetSurfaceMoveDirection(Vector2 input)
    {
        var basis = GlobalTransform.Basis.Orthonormalized();
        var forward = ProjectOnPlane(-basis.Z, _lastUp);
        var right = ProjectOnPlane(basis.X, _lastUp);

        if (forward.LengthSquared() > 0.0001f)
        {
            forward = forward.Normalized();
        }

        if (right.LengthSquared() > 0.0001f)
        {
            right = right.Normalized();
        }

        var desiredDirection = right * input.X - forward * input.Y;
        return desiredDirection.LengthSquared() > 1.0f ? desiredDirection.Normalized() : desiredDirection;
    }

    private Vector3 GetZeroGravityThrustDirection(Vector2 input)
    {
        var camera = _viewPivot.GetNodeOrNull<Camera3D>("Camera3D");
        var basis = (camera?.GlobalTransform.Basis ?? GlobalTransform.Basis).Orthonormalized();
        var forward = -basis.Z;
        var right = basis.X;
        var direction = right * input.X - forward * input.Y;

        if (direction.LengthSquared() < 0.0001f)
        {
            direction = forward;
        }

        return direction.Normalized();
    }

    private static Vector3 ProjectOnPlane(Vector3 vector, Vector3 normal)
    {
        return vector - normal * vector.Dot(normal);
    }

    private static Vector3 RotateAroundAxis(Vector3 vector, Vector3 axis, float angle)
    {
        if (Mathf.IsZeroApprox(angle))
        {
            return vector;
        }

        return new Quaternion(axis.Normalized(), angle) * vector;
    }
}
