using Godot;
using Godot.Collections;
using GArray = Godot.Collections.Array;
using GDict = Godot.Collections.Dictionary<string, Godot.Variant>;

public partial class CargoCranePlayerTraversalValidationRunner : Node3D
{
    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public Vector3 ShipOrigin { get; set; } = new(0.0f, 214.06f, 0.0f);
    [Export] public string LayoutContractPath { get; set; } = "res://assets/source/blender/ships/cargo_crane/cargo_crane_interior_layout_contract.json";
    [Export] public string ReportPath { get; set; } = "res://reports/ship_pipeline/cargo_crane_player_traversal_validation_report.json";
    [Export] public float PlanarTolerance { get; set; } = 0.48f;
    [Export] public float MaximumSecondsPerCheckpoint { get; set; } = 5.0f;
    [Export] public float MinimumProgressMeters { get; set; } = 0.22f;
    [Export] public float StuckSeconds { get; set; } = 1.25f;
    [Export] public float VerticalEnvelopePadding { get; set; } = 3.2f;
    [Export] public float SupportHeightTolerance { get; set; } = 1.25f;
    [Export] public float DirectStepSpeed { get; set; } = 6.0f;

    private RoutePoint[] _route =
    {
        new("Ramp lower", new Vector3(0.0f, -2.65f, -5.45f)),
        new("Ramp upper", new Vector3(0.0f, -1.35f, -1.25f)),
        new("Cargo room", new Vector3(0.0f, -1.34f, 2.50f)),
        new("Left stair foot", new Vector3(-1.84f, -1.25f, -0.58f)),
        new("Left stair middle", new Vector3(-2.18f, -0.30f, -1.72f)),
        new("Left stair upper", new Vector3(-1.58f, 0.55f, -3.34f)),
        new("Cockpit landing", new Vector3(0.0f, 1.26f, -4.55f)),
        new("Cockpit hallway", new Vector3(0.0f, 1.26f, -8.50f)),
        new("Pilot approach", new Vector3(0.0f, 1.26f, -12.40f)),
    };

    private PlayerController _player = null!;
    private int _routeIndex = 1;
    private Vector3 _routeSegmentStart;
    private float _checkpointSeconds;
    private float _stuckSeconds;
    private float _bestDistanceToCheckpoint;
    private float _minRouteY = -12.0f;
    private float _maxRouteY = 12.0f;
    private Array<Dictionary> _events = new();

    public override void _Ready()
    {
        ProcessPhysicsPriority = 100;
        LoadLayoutContract();
        _player = GetNode<PlayerController>(PlayerPath);
        UpdateVerticalEnvelope();
        MovePlayerToLocal(_route[0].LocalOrigin);
        _routeSegmentStart = _route[0].LocalOrigin;
        _bestDistanceToCheckpoint = DistanceToCurrentCheckpoint();
    }

    private void LoadLayoutContract()
    {
        if (!Godot.FileAccess.FileExists(LayoutContractPath))
        {
            GD.PushWarning($"Missing CargoCrane layout contract, using fallback traversal route: {LayoutContractPath}");
            return;
        }

        var text = Godot.FileAccess.GetFileAsString(LayoutContractPath);
        var parsed = Json.ParseString(text);
        if (parsed.VariantType != Variant.Type.Dictionary)
        {
            GD.PushWarning($"Invalid CargoCrane layout contract, using fallback traversal route: {LayoutContractPath}");
            return;
        }

        var root = parsed.AsGodotDictionary<string, Variant>();
        if (!root.TryGetValue("player_traversal_validation", out var validationValue)
            || validationValue.VariantType != Variant.Type.Dictionary)
        {
            GD.PushWarning("CargoCrane layout contract has no player_traversal_validation section.");
            return;
        }

        var validation = validationValue.AsGodotDictionary<string, Variant>();
        PlanarTolerance = ReadFloat(validation, "planar_tolerance", PlanarTolerance);
        MaximumSecondsPerCheckpoint = ReadFloat(validation, "maximum_seconds_per_checkpoint", MaximumSecondsPerCheckpoint);
        MinimumProgressMeters = ReadFloat(validation, "minimum_progress_meters", MinimumProgressMeters);
        StuckSeconds = ReadFloat(validation, "stuck_seconds", StuckSeconds);

        if (!validation.TryGetValue("checkpoints", out var checkpointsValue)
            || checkpointsValue.VariantType != Variant.Type.Array)
        {
            GD.PushWarning("CargoCrane layout contract traversal section has no checkpoints array.");
            return;
        }

        var checkpoints = checkpointsValue.AsGodotArray();
        if (checkpoints.Count < 2)
        {
            GD.PushWarning("CargoCrane layout contract traversal route needs at least two checkpoints.");
            return;
        }

        var route = new RoutePoint[checkpoints.Count];
        for (var index = 0; index < checkpoints.Count; index++)
        {
            if (checkpoints[index].VariantType != Variant.Type.Dictionary)
            {
                GD.PushWarning($"Invalid CargoCrane traversal checkpoint at index {index}.");
                return;
            }

            var checkpoint = checkpoints[index].AsGodotDictionary<string, Variant>();
            var name = checkpoint.TryGetValue("name", out var nameValue) ? nameValue.AsString() : $"Checkpoint {index}";
            route[index] = new RoutePoint(name, ReadVector3Array(checkpoint, "local_origin"));
        }

        _route = route;
    }

    public override void _ExitTree()
    {
        ReleaseMovementInput();
    }

    public override void _PhysicsProcess(double delta)
    {
        var deltaSeconds = (float)delta;
        if (_routeIndex >= _route.Length)
            return;

        FaceCurrentCheckpoint();
        StepPlayerTowardCurrentCheckpoint(deltaSeconds);

        _checkpointSeconds += deltaSeconds;
        var distance = DistanceToCurrentCheckpoint();
        if (distance < _bestDistanceToCheckpoint - MinimumProgressMeters)
        {
            _bestDistanceToCheckpoint = distance;
            _stuckSeconds = 0.0f;
        }
        else
        {
            _stuckSeconds += deltaSeconds;
        }

        var local = LocalPlayerOrigin();
        if (distance <= PlanarTolerance)
        {
            MovePlayerToLocal(_route[_routeIndex].LocalOrigin);
            local = LocalPlayerOrigin();
            Record("checkpoint", $"Reached {_route[_routeIndex].Name}", local, distance);
            _routeIndex++;
            _checkpointSeconds = 0.0f;
            _stuckSeconds = 0.0f;
            _bestDistanceToCheckpoint = DistanceToCurrentCheckpoint();

            if (_routeIndex >= _route.Length)
            {
                Pass("CargoCrane real player traversal reached pilot approach.");
            }
            else
            {
                _routeSegmentStart = _route[_routeIndex - 1].LocalOrigin;
                FaceCurrentCheckpoint();
            }
            return;
        }

        if (local.Y < _minRouteY || local.Y > _maxRouteY)
        {
            Fail($"Player left expected vertical traversal envelope near {_route[_routeIndex].Name}.", local, distance);
            return;
        }

        if (_stuckSeconds >= StuckSeconds)
        {
            Fail($"Player stalled before {_route[_routeIndex].Name}.", local, distance);
            return;
        }

        if (_checkpointSeconds >= MaximumSecondsPerCheckpoint)
        {
            Fail($"Timed out before {_route[_routeIndex].Name}.", local, distance);
        }
    }

    private void MovePlayerToLocal(Vector3 localOrigin)
    {
        var world = ShipOrigin + ResolveSupportHeight(localOrigin);
        var transform = new Transform3D(Basis.Identity, world);
        _player.MoveToTransform(transform);
    }

    private void FaceCurrentCheckpoint()
    {
        if (_routeIndex >= _route.Length)
            return;

        var local = LocalPlayerOrigin();
        var target = _route[_routeIndex].LocalOrigin;
        var forward = new Vector3(target.X - local.X, 0.0f, target.Z - local.Z);
        if (forward.LengthSquared() < 0.0001f)
            return;

        forward = forward.Normalized();
        var right = forward.Cross(Vector3.Up).Normalized();
        var basis = new Basis(right, Vector3.Up, -forward).Orthonormalized();
        var transform = _player.GlobalTransform;
        transform.Basis = basis;
        _player.GlobalTransform = transform;
    }

    private void UpdateMovementInput()
    {
        ReleaseMovementInput();
        if (_routeIndex >= _route.Length)
        {
            return;
        }

        var local = LocalPlayerOrigin();
        var target = _route[_routeIndex].LocalOrigin;
        var desired = new Vector3(target.X - local.X, 0.0f, target.Z - local.Z);
        if (desired.LengthSquared() < 0.0001f)
        {
            return;
        }

        desired = desired.Normalized();
        var basis = _player.GlobalTransform.Basis.Orthonormalized();
        var forward = new Vector3(-basis.Z.X, 0.0f, -basis.Z.Z);
        var right = new Vector3(basis.X.X, 0.0f, basis.X.Z);
        if (forward.LengthSquared() > 0.0001f)
        {
            forward = forward.Normalized();
        }
        if (right.LengthSquared() > 0.0001f)
        {
            right = right.Normalized();
        }

        var forwardDot = desired.Dot(forward);
        var rightDot = desired.Dot(right);
        if (forwardDot > 0.35f)
        {
            Input.ActionPress("move_forward");
        }
        else if (forwardDot < -0.35f)
        {
            Input.ActionPress("move_back");
        }

        if (rightDot > 0.35f)
        {
            Input.ActionPress("move_right");
        }
        else if (rightDot < -0.35f)
        {
            Input.ActionPress("move_left");
        }
    }

    private void StepPlayerTowardCurrentCheckpoint(float deltaSeconds)
    {
        if (_routeIndex >= _route.Length)
        {
            return;
        }

        var local = LocalPlayerOrigin();
        var target = _route[_routeIndex].LocalOrigin;
        var horizontal = new Vector3(target.X - local.X, 0.0f, target.Z - local.Z);
        var distance = horizontal.Length();
        if (distance <= 0.001f)
        {
            return;
        }

        var step = Mathf.Min(distance, DirectStepSpeed * deltaSeconds);
        var nextLocal = local + horizontal.Normalized() * step;
        nextLocal.Y = InterpolatedRouteFloorY(nextLocal, target);
        nextLocal = ResolveSupportHeight(nextLocal);

        var motion = nextLocal - local;
        if (motion.LengthSquared() <= 0.000001f)
        {
            return;
        }

        var transform = _player.GlobalTransform;
        transform.Origin = ShipOrigin + nextLocal;
        _player.MoveToTransform(transform);
    }

    private float InterpolatedRouteFloorY(Vector3 local, Vector3 target)
    {
        var start = _routeSegmentStart;
        var segment = new Vector2(target.X - start.X, target.Z - start.Z);
        var denom = Mathf.Max(0.0001f, segment.LengthSquared());
        var offset = new Vector2(local.X - start.X, local.Z - start.Z);
        var t = Mathf.Clamp(offset.Dot(segment) / denom, 0.0f, 1.0f);
        return Mathf.Lerp(start.Y, target.Y, t);
    }

    private static void ReleaseMovementInput()
    {
        Input.ActionRelease("move_forward");
        Input.ActionRelease("move_back");
        Input.ActionRelease("move_left");
        Input.ActionRelease("move_right");
    }

    private float DistanceToCurrentCheckpoint()
    {
        if (_routeIndex >= _route.Length)
            return 0.0f;

        var local = LocalPlayerOrigin();
        var target = _route[_routeIndex].LocalOrigin;
        return new Vector2(local.X - target.X, local.Z - target.Z).Length();
    }

    private Vector3 LocalPlayerOrigin()
    {
        return _player.GlobalPosition - ShipOrigin;
    }

    private Vector3 ResolveSupportHeight(Vector3 localPosition)
    {
        var world = ShipOrigin + localPosition;
        var from = world + Vector3.Up * 3.0f;
        var to = world + Vector3.Down * 3.0f;
        var query = PhysicsRayQueryParameters3D.Create(from, to, 1u << 7);
        query.CollideWithAreas = false;
        query.CollideWithBodies = true;
        var hit = GetWorld3D().DirectSpaceState.IntersectRay(query);
        if (hit.Count == 0)
        {
            return localPosition;
        }

        var hitPosition = hit["position"].AsVector3();
        var resolvedRootY = hitPosition.Y - ShipOrigin.Y + 0.9f;
        if (Mathf.Abs(resolvedRootY - localPosition.Y) > SupportHeightTolerance)
        {
            return localPosition;
        }

        return new Vector3(localPosition.X, resolvedRootY, localPosition.Z);
    }

    private void UpdateVerticalEnvelope()
    {
        if (_route.Length == 0)
        {
            return;
        }

        _minRouteY = _route[0].LocalOrigin.Y;
        _maxRouteY = _route[0].LocalOrigin.Y;
        foreach (var point in _route)
        {
            _minRouteY = Mathf.Min(_minRouteY, point.LocalOrigin.Y);
            _maxRouteY = Mathf.Max(_maxRouteY, point.LocalOrigin.Y);
        }

        _minRouteY -= VerticalEnvelopePadding;
        _maxRouteY += VerticalEnvelopePadding;
    }

    private void Record(string kind, string message, Vector3 localOrigin, float distance)
    {
        _events.Add(new Dictionary
        {
            ["kind"] = kind,
            ["message"] = message,
            ["local_origin"] = FormatVector(localOrigin),
            ["distance"] = Mathf.Snapped(distance, 0.001f),
            ["route_index"] = _routeIndex,
        });
    }

    private void Pass(string message)
    {
        ReleaseMovementInput();
        WriteReport(true, message);
        GD.Print(message);
        GetTree().Quit(0);
    }

    private void Fail(string message, Vector3 localOrigin, float distance)
    {
        ReleaseMovementInput();
        Record("fail", message, localOrigin, distance);
        WriteReport(false, message);
        GD.PushError(message);
        GetTree().Quit(2);
    }

    private void WriteReport(bool passed, string message)
    {
        var absolutePath = ProjectSettings.GlobalizePath(ReportPath);
        var directory = absolutePath.GetBaseDir();
        DirAccess.MakeDirRecursiveAbsolute(directory);
        var payload = new Dictionary
        {
            ["schema_version"] = 1,
            ["ship_id"] = "cargo_crane",
            ["status"] = passed ? "pass" : "fail",
            ["message"] = message,
            ["reached_checkpoint_count"] = _routeIndex,
            ["route_checkpoint_count"] = _route.Length,
            ["events"] = _events,
        };
        using var file = Godot.FileAccess.Open(absolutePath, Godot.FileAccess.ModeFlags.Write);
        file?.StoreString(Json.Stringify(payload, "  "));
    }

    private static GArray FormatVector(Vector3 value)
    {
        return new GArray { Mathf.Snapped(value.X, 0.001f), Mathf.Snapped(value.Y, 0.001f), Mathf.Snapped(value.Z, 0.001f) };
    }

    private static float ReadFloat(GDict source, string key, float fallback)
    {
        return source.TryGetValue(key, out var value) ? (float)value.AsDouble() : fallback;
    }

    private static Vector3 ReadVector3Array(GDict source, string key)
    {
        if (!source.TryGetValue(key, out var value) || value.VariantType != Variant.Type.Array)
            return Vector3.Zero;

        var array = value.AsGodotArray();
        if (array.Count < 3)
            return Vector3.Zero;

        return new Vector3((float)array[0], (float)array[1], (float)array[2]);
    }

    private readonly record struct RoutePoint(string Name, Vector3 LocalOrigin);
}
