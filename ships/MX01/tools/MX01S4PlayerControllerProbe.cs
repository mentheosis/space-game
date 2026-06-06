using Godot;
using GDict = Godot.Collections.Dictionary;

public partial class MX01S4PlayerControllerProbe : Node3D
{
    [Export] public NodePath PlayerPath { get; set; } = "MX01PlayableInspection/Player";
    [Export] public NodePath ShipRootPath { get; set; } = "MX01PlayableInspection/ShipRoot";
    [Export] public string ReportPath { get; set; } = "res://ships/MX01/reports/mx01_s4_player_controller_probe.json";
    [Export] public float CheckpointTolerance { get; set; } = 0.38f;
    [Export] public float StuckSeconds { get; set; } = 1.2f;
    [Export] public float MinimumProgressMeters { get; set; } = 0.06f;
    [Export] public float MaximumSeconds { get; set; } = 18.0f;

    private readonly RoutePoint[] _route =
    {
        new("lower_landing", new Vector3(-3.325f, 0.15f, 45.55f)),
        new("tread_01", new Vector3(-3.325f, 0.85f, 44.89f)),
        new("tread_02", new Vector3(-3.325f, 1.55f, 44.47f)),
        new("tread_03", new Vector3(-3.325f, 2.25f, 44.05f)),
        new("tread_04", new Vector3(-3.325f, 2.95f, 43.63f)),
        new("tread_05", new Vector3(-3.325f, 3.65f, 43.21f)),
        new("upper_landing", new Vector3(-3.325f, 3.65f, 42.55f)),
        new("upper_exit_forward", new Vector3(-3.325f, 3.65f, 41.65f)),
    };

    private PlayerController _player = null!;
    private Node3D _shipRoot = null!;
    private int _routeIndex = 1;
    private int _frame;
    private float _elapsedSeconds;
    private float _stuckSeconds;
    private float _bestDistance;
    private bool _finished;
    private readonly Godot.Collections.Array<GDict> _events = new();

    public override void _Ready()
    {
        ProcessPhysicsPriority = 100;
        _player = GetNode<PlayerController>(PlayerPath);
        _shipRoot = GetNode<Node3D>(ShipRootPath);
        MovePlayerToLocalOrigin(_route[0].LocalOrigin);
        FaceCurrentCheckpoint();
        _bestDistance = DistanceToCurrentCheckpoint();
        Record("start", "S4 player-controller probe started.");
        Input.ActionPress("move_forward");
    }

    public override void _ExitTree()
    {
        ReleaseMovementInput();
    }

    public override void _PhysicsProcess(double delta)
    {
        if (_finished)
        {
            return;
        }

        var deltaSeconds = (float)delta;
        _frame++;
        _elapsedSeconds += deltaSeconds;
        FaceCurrentCheckpoint();

        var distance = DistanceToCurrentCheckpoint();
        if (distance < _bestDistance - MinimumProgressMeters)
        {
            _bestDistance = distance;
            _stuckSeconds = 0.0f;
        }
        else
        {
            _stuckSeconds += deltaSeconds;
        }

        if (_frame % 15 == 0)
        {
            Record("sample", $"Moving toward {_route[_routeIndex].Name}.");
        }

        if (distance <= CheckpointTolerance)
        {
            Record("checkpoint", $"Reached {_route[_routeIndex].Name}.");
            _routeIndex++;
            if (_routeIndex >= _route.Length)
            {
                Pass("S4 route is passable with the real PlayerController.");
                return;
            }

            _bestDistance = DistanceToCurrentCheckpoint();
            _stuckSeconds = 0.0f;
            FaceCurrentCheckpoint();
            return;
        }

        if (_stuckSeconds >= StuckSeconds)
        {
            Fail($"Player stalled before {_route[_routeIndex].Name}.");
            return;
        }

        if (_elapsedSeconds >= MaximumSeconds)
        {
            Fail($"Timed out before {_route[_routeIndex].Name}.");
        }
    }

    private void MovePlayerToLocalOrigin(Vector3 localOrigin)
    {
        var worldOrigin = _shipRoot.GlobalPosition + localOrigin;
        _player.SetPlayerContext(PlayerContext.OnFoot);
        _player.MoveToTransform(new Transform3D(Basis.Identity, worldOrigin));
        _player.Velocity = Vector3.Zero;
    }

    private void FaceCurrentCheckpoint()
    {
        if (_routeIndex >= _route.Length)
        {
            return;
        }

        var local = LocalPlayerOrigin();
        var target = _route[_routeIndex].LocalOrigin;
        var forward = new Vector3(target.X - local.X, 0.0f, target.Z - local.Z);
        if (forward.LengthSquared() < 0.0001f)
        {
            return;
        }

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
        {
            return 0.0f;
        }

        var local = LocalPlayerOrigin();
        var target = _route[_routeIndex].LocalOrigin;
        return new Vector2(local.X - target.X, local.Z - target.Z).Length();
    }

    private Vector3 LocalPlayerOrigin()
    {
        return _player.GlobalPosition - _shipRoot.GlobalPosition;
    }

    private void Pass(string message)
    {
        _finished = true;
        ReleaseMovementInput();
        Record("pass", message);
        WriteReport("pass", message);
        GD.Print(message);
        GetTree().Quit(0);
    }

    private void Fail(string message)
    {
        _finished = true;
        ReleaseMovementInput();
        Record("fail", message);
        WriteReport("fail", message);
        GD.PushError(message);
        GetTree().Quit(2);
    }

    private void Record(string kind, string message)
    {
        var target = _routeIndex < _route.Length ? _route[_routeIndex] : _route[^1];
        var local = LocalPlayerOrigin();
        _events.Add(new GDict
        {
            ["frame"] = _frame,
            ["time_seconds"] = Mathf.Snapped(_elapsedSeconds, 0.001f),
            ["kind"] = kind,
            ["message"] = message,
            ["route_index"] = _routeIndex,
            ["target"] = target.Name,
            ["target_local_origin"] = FormatVector(target.LocalOrigin),
            ["player_local_origin"] = FormatVector(local),
            ["player_world_origin"] = FormatVector(_player.GlobalPosition),
            ["distance_to_target"] = Mathf.Snapped(DistanceToCurrentCheckpoint(), 0.001f),
            ["best_distance_to_target"] = Mathf.Snapped(_bestDistance, 0.001f),
            ["stuck_seconds"] = Mathf.Snapped(_stuckSeconds, 0.001f),
            ["velocity"] = FormatVector(_player.Velocity),
            ["grounded"] = _player.DebugGrounded,
            ["movement_mode"] = _player.DebugMovementMode.ToString(),
            ["gravity_body"] = _player.DebugActiveGravityBodyName,
            ["up_direction"] = FormatVector(_player.DebugUpDirection),
            ["support_probe"] = ReadSupportProbe(),
            ["slide_collision_count"] = _player.GetSlideCollisionCount(),
            ["slide_colliders"] = ReadSlideColliders(),
            ["slide_collision_details"] = ReadSlideCollisionDetails(),
        });
    }

    private GDict ReadSupportProbe()
    {
        var up = _player.DebugUpDirection.LengthSquared() > 0.0001f ? _player.DebugUpDirection.Normalized() : Vector3.Up;
        var from = _player.GlobalPosition + up * (_player.WalkableSupportMaxRise + _player.WalkableSupportProbePadding);
        var to = _player.GlobalPosition - up * (_player.WalkableSupportMaxDrop + _player.WalkableSupportProbePadding);
        var query = PhysicsRayQueryParameters3D.Create(
            from,
            to,
            _player.WalkableSupportCollisionMask,
            new Godot.Collections.Array<Rid> { _player.GetRid() });
        query.CollideWithAreas = false;
        query.CollideWithBodies = true;
        query.HitBackFaces = false;

        var hit = GetWorld3D().DirectSpaceState.IntersectRay(query);
        if (hit.Count == 0)
        {
            return new GDict
            {
                ["hit"] = false,
                ["from"] = FormatVector(from),
                ["to"] = FormatVector(to),
            };
        }

        var collider = hit["collider"].AsGodotObject();
        var position = hit["position"].AsVector3();
        var normal = hit["normal"].AsVector3();
        return new GDict
        {
            ["hit"] = true,
            ["from"] = FormatVector(from),
            ["to"] = FormatVector(to),
            ["collider"] = collider is Node node ? node.Name.ToString() : collider.ToString(),
            ["collider_path"] = collider is Node nodeWithPath ? nodeWithPath.GetPath().ToString() : "",
            ["position"] = FormatVector(position),
            ["local_position"] = FormatVector(position - _shipRoot.GlobalPosition),
            ["normal"] = FormatVector(normal),
            ["normal_dot_up"] = Mathf.Snapped(normal.Dot(up), 0.001f),
        };
    }

    private Godot.Collections.Array<string> ReadSlideColliders()
    {
        var colliders = new Godot.Collections.Array<string>();
        for (var index = 0; index < _player.GetSlideCollisionCount(); index++)
        {
            var collision = _player.GetSlideCollision(index);
            var collider = collision.GetCollider();
            colliders.Add(collider is Node node ? node.Name.ToString() : collider.ToString());
        }
        return colliders;
    }

    private Godot.Collections.Array<GDict> ReadSlideCollisionDetails()
    {
        var details = new Godot.Collections.Array<GDict>();
        for (var index = 0; index < _player.GetSlideCollisionCount(); index++)
        {
            var collision = _player.GetSlideCollision(index);
            var collider = collision.GetCollider();
            var normal = collision.GetNormal();
            var position = collision.GetPosition();
            details.Add(new GDict
            {
                ["collider"] = collider is Node node ? node.Name.ToString() : collider.ToString(),
                ["collider_path"] = collider is Node nodeWithPath ? nodeWithPath.GetPath().ToString() : "",
                ["normal"] = FormatVector(normal),
                ["position"] = FormatVector(position),
            });
        }
        return details;
    }

    private void WriteReport(string status, string message)
    {
        var absolutePath = ProjectSettings.GlobalizePath(ReportPath);
        DirAccess.MakeDirRecursiveAbsolute(absolutePath.GetBaseDir());
        var payload = new GDict
        {
            ["schema_version"] = 1,
            ["ship_id"] = "MX01",
            ["test"] = "s4_real_player_controller_movement",
            ["status"] = status,
            ["message"] = message,
            ["frames"] = _frame,
            ["elapsed_seconds"] = Mathf.Snapped(_elapsedSeconds, 0.001f),
            ["route_index"] = _routeIndex,
            ["route_count"] = _route.Length,
            ["events"] = _events,
        };
        using var file = Godot.FileAccess.Open(absolutePath, Godot.FileAccess.ModeFlags.Write);
        file?.StoreString(Json.Stringify(payload, "  "));
    }

    private static void ReleaseMovementInput()
    {
        Input.ActionRelease("move_forward");
        Input.ActionRelease("move_back");
        Input.ActionRelease("move_left");
        Input.ActionRelease("move_right");
    }

    private static Godot.Collections.Array<float> FormatVector(Vector3 value)
    {
        return new Godot.Collections.Array<float>
        {
            Mathf.Snapped(value.X, 0.001f),
            Mathf.Snapped(value.Y, 0.001f),
            Mathf.Snapped(value.Z, 0.001f),
        };
    }

    private readonly record struct RoutePoint(string Name, Vector3 LocalOrigin);
}
