using Godot;
using Godot.Collections;
using GArray = Godot.Collections.Array;

public partial class CargoCraneEngineRampInputTraversalValidationRunner : Node3D
{
    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public Vector3 ShipOrigin { get; set; } = new(0.0f, 214.06f, 0.0f);
    [Export] public string ReportPath { get; set; } = "res://reports/ship_pipeline/cargo_crane_engine_ramp_input_traversal_report.json";
    [Export] public float PlanarTolerance { get; set; } = 0.65f;
    [Export] public float MaximumSecondsPerCheckpoint { get; set; } = 7.0f;
    [Export] public float MinimumProgressMeters { get; set; } = 0.18f;
    [Export] public float StuckSeconds { get; set; } = 1.35f;
    [Export] public float SupportHeightTolerance { get; set; } = 1.4f;

    private readonly RoutePoint[] _route =
    {
        new("Engine room approach", new Vector3(0.0f, -5.0f, -44.0f)),
        new("Engine ramp foot", new Vector3(0.0f, -5.0f, -37.0f)),
        new("Engine ramp midpoint", new Vector3(0.0f, -3.0f, -32.75f)),
        new("Main body ramp top", new Vector3(0.0f, -1.0f, -28.5f)),
        new("Main body clear", new Vector3(0.0f, -1.0f, -24.0f)),
    };

    private PlayerController _player = null!;
    private int _routeIndex = 1;
    private float _checkpointSeconds;
    private float _stuckSeconds;
    private float _bestDistanceToCheckpoint;
    private Array<Dictionary> _events = new();

    public override void _Ready()
    {
        ProcessPhysicsPriority = 100;
        _player = GetNode<PlayerController>(PlayerPath);
        MovePlayerToLocalFloor(_route[0].LocalFloor);
        _bestDistanceToCheckpoint = DistanceToCurrentCheckpoint();
        FaceCurrentCheckpoint();
        Input.ActionPress("move_forward");
        GD.Print("CargoCrane engine ramp input traversal validation started.");
    }

    public override void _ExitTree()
    {
        ReleaseMovementInput();
    }

    public override void _PhysicsProcess(double delta)
    {
        if (_routeIndex >= _route.Length)
            return;

        var deltaSeconds = (float)delta;
        FaceCurrentCheckpoint();

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
            Record("checkpoint", $"Reached {_route[_routeIndex].Name}", local, distance);
            _routeIndex++;
            _checkpointSeconds = 0.0f;
            _stuckSeconds = 0.0f;
            _bestDistanceToCheckpoint = DistanceToCurrentCheckpoint();

            if (_routeIndex >= _route.Length)
            {
                Pass("CargoCrane engine ramp input traversal reached main body clear.");
            }
            return;
        }

        if (local.Y < -6.2f || local.Y > 1.2f)
        {
            Fail($"Player left expected ramp vertical envelope near {_route[_routeIndex].Name}.", local, distance);
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

    private void MovePlayerToLocalFloor(Vector3 localFloor)
    {
        var localRoot = ResolveSupportHeight(localFloor);
        _player.MoveToTransform(new Transform3D(Basis.Identity, ShipOrigin + localRoot));
    }

    private Vector3 ResolveSupportHeight(Vector3 localFloor)
    {
        var world = ShipOrigin + localFloor;
        var query = PhysicsRayQueryParameters3D.Create(world + Vector3.Up * 4.0f, world + Vector3.Down * 4.0f, 1u << 7);
        query.CollideWithAreas = false;
        query.CollideWithBodies = true;
        var hit = GetWorld3D().DirectSpaceState.IntersectRay(query);
        if (hit.Count == 0)
        {
            return new Vector3(localFloor.X, localFloor.Y + 0.9f, localFloor.Z);
        }

        var hitPosition = hit["position"].AsVector3();
        var resolvedRootY = hitPosition.Y - ShipOrigin.Y + 0.9f;
        if (Mathf.Abs(resolvedRootY - (localFloor.Y + 0.9f)) > SupportHeightTolerance)
        {
            return new Vector3(localFloor.X, localFloor.Y + 0.9f, localFloor.Z);
        }

        return new Vector3(localFloor.X, resolvedRootY, localFloor.Z);
    }

    private void FaceCurrentCheckpoint()
    {
        if (_routeIndex >= _route.Length)
            return;

        var local = LocalPlayerOrigin();
        var target = _route[_routeIndex].LocalFloor;
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

    private float DistanceToCurrentCheckpoint()
    {
        if (_routeIndex >= _route.Length)
            return 0.0f;

        var local = LocalPlayerOrigin();
        var target = _route[_routeIndex].LocalFloor;
        return new Vector2(local.X - target.X, local.Z - target.Z).Length();
    }

    private Vector3 LocalPlayerOrigin()
    {
        return _player.GlobalPosition - ShipOrigin;
    }

    private static void ReleaseMovementInput()
    {
        Input.ActionRelease("move_forward");
        Input.ActionRelease("move_back");
        Input.ActionRelease("move_left");
        Input.ActionRelease("move_right");
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
            ["velocity"] = FormatVector(_player.Velocity),
            ["grounded"] = _player.DebugGrounded,
            ["movement_mode"] = _player.DebugMovementMode.ToString(),
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
        DirAccess.MakeDirRecursiveAbsolute(absolutePath.GetBaseDir());
        var payload = new Dictionary
        {
            ["schema_version"] = 1,
            ["ship_id"] = "cargo_crane",
            ["test"] = "engine_ramp_input_traversal",
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

    private readonly record struct RoutePoint(string Name, Vector3 LocalFloor);
}
