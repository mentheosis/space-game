using Godot;
using Godot.Collections;
using GArray = Godot.Collections.Array;

public partial class ShuttleP3PlayerTraversalValidationRunner : Node3D
{
    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public Vector3 ShuttleOrigin { get; set; } = new(0.0f, 205.6f, 0.0f);
    [Export] public string ReportPath { get; set; } = "res://reports/ship_pipeline/shuttle_p3_player_traversal_validation_report.json";
    [Export] public float PlanarTolerance { get; set; } = 0.48f;
    [Export] public float MaximumSecondsPerCheckpoint { get; set; } = 5.0f;
    [Export] public float MinimumProgressMeters { get; set; } = 0.22f;
    [Export] public float StuckSeconds { get; set; } = 1.25f;

    private readonly RoutePoint[] _route =
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
    private float _checkpointSeconds;
    private float _stuckSeconds;
    private float _bestDistanceToCheckpoint;
    private Array<Dictionary> _events = new();

    public override void _Ready()
    {
        _player = GetNode<PlayerController>(PlayerPath);
        MovePlayerToLocal(_route[0].LocalOrigin);
        _bestDistanceToCheckpoint = DistanceToCurrentCheckpoint();
        Input.ActionPress("move_forward");
    }

    public override void _ExitTree()
    {
        Input.ActionRelease("move_forward");
    }

    public override void _PhysicsProcess(double delta)
    {
        var deltaSeconds = (float)delta;
        if (_routeIndex >= _route.Length)
            return;

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
                Pass("Shuttle P3 real player traversal reached pilot approach.");
            }
            return;
        }

        if (local.Y < -4.15f || local.Y > 2.75f)
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
        var world = ShuttleOrigin + localOrigin;
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
        return _player.GlobalPosition - ShuttleOrigin;
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
        Input.ActionRelease("move_forward");
        WriteReport(true, message);
        GD.Print(message);
        GetTree().Quit(0);
    }

    private void Fail(string message, Vector3 localOrigin, float distance)
    {
        Input.ActionRelease("move_forward");
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
            ["ship_id"] = "shuttle_p3",
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

    private readonly record struct RoutePoint(string Name, Vector3 LocalOrigin);
}
