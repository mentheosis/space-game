using Godot;
using GDict = Godot.Collections.Dictionary;

public partial class MX01AllStairsPlayerControllerProbe : Node3D
{
    [Export] public NodePath PlayerPath { get; set; } = "MX01PlayableInspection/Player";
    [Export] public NodePath ShipRootPath { get; set; } = "MX01PlayableInspection/ShipRoot";
    [Export] public string ReportPath { get; set; } = "res://ships/MX01/reports/mx01_all_stairs_player_controller_probe.json";
    [Export] public float CheckpointTolerance { get; set; } = 0.4f;
    [Export] public float StuckSeconds { get; set; } = 1.2f;
    [Export] public float MinimumProgressMeters { get; set; } = 0.06f;
    [Export] public float MaximumRouteSeconds { get; set; } = 18.0f;

    private readonly Route[] _routes =
    {
        new("S1 forward cockpit lower 01 to lower 02", new RoutePoint[]
        {
            new("lower_landing", new Vector3(-2.325f, -6.85f, 49.7f)),
            new("tread_01", new Vector3(-2.325f, -6.45f, 49.04f)),
            new("tread_02", new Vector3(-2.325f, -6.05f, 48.62f)),
            new("tread_03", new Vector3(-2.325f, -5.65f, 48.2f)),
            new("tread_04", new Vector3(-2.325f, -5.25f, 47.78f)),
            new("tread_05", new Vector3(-2.325f, -4.85f, 47.36f)),
            new("upper_landing", new Vector3(-2.325f, -4.85f, 46.7f)),
            new("upper_exit", new Vector3(-2.325f, -4.85f, 45.8f)),
        }),
        new("S2 forward cockpit lower 02 to mid", new RoutePoint[]
        {
            new("lower_landing", new Vector3(3.325f, -4.85f, 47.45f)),
            new("tread_01", new Vector3(3.325f, -4.225f, 46.79f)),
            new("tread_02", new Vector3(3.325f, -3.6f, 46.37f)),
            new("tread_03", new Vector3(3.325f, -2.975f, 45.95f)),
            new("tread_04", new Vector3(3.325f, -2.35f, 45.53f)),
            new("tread_05", new Vector3(3.325f, -1.725f, 45.11f)),
            new("tread_06", new Vector3(3.325f, -1.1f, 44.69f)),
            new("tread_07", new Vector3(3.325f, -0.475f, 44.27f)),
            new("tread_08", new Vector3(3.325f, 0.15f, 43.85f)),
            new("upper_landing", new Vector3(3.325f, 0.15f, 43.19f)),
            new("upper_exit", new Vector3(3.325f, 0.15f, 42.29f)),
        }),
        new("S3 lower to mid aft", new RoutePoint[]
        {
            new("lower_landing", new Vector3(0.0f, -3.35f, -34.6f)),
            new("tread_01", new Vector3(0.0f, -2.65f, -34.015f)),
            new("tread_02", new Vector3(0.0f, -1.95f, -33.595f)),
            new("tread_03", new Vector3(0.0f, -1.25f, -33.175f)),
            new("tread_04", new Vector3(0.0f, -0.55f, -32.755f)),
            new("tread_05", new Vector3(0.0f, 0.15f, -32.335f)),
            new("upper_landing", new Vector3(0.0f, 0.15f, -31.75f)),
            new("upper_exit", new Vector3(0.0f, 0.15f, -30.85f)),
        }),
        new("S4 mid to upper cockpit forward", new RoutePoint[]
        {
            new("lower_landing", new Vector3(-3.325f, 0.15f, 45.55f)),
            new("tread_01", new Vector3(-3.325f, 0.85f, 44.89f)),
            new("tread_02", new Vector3(-3.325f, 1.55f, 44.47f)),
            new("tread_03", new Vector3(-3.325f, 2.25f, 44.05f)),
            new("tread_04", new Vector3(-3.325f, 2.95f, 43.63f)),
            new("tread_05", new Vector3(-3.325f, 3.65f, 43.21f)),
            new("upper_landing", new Vector3(-3.325f, 3.65f, 42.55f)),
            new("upper_exit", new Vector3(-3.325f, 3.65f, 41.65f)),
        }),
        new("S5 mid to upper port side", new RoutePoint[]
        {
            new("lower_landing", new Vector3(-3.675f, 0.15f, 4.625f)),
            new("tread_01", new Vector3(-3.675f, 0.85f, 4.04f)),
            new("tread_02", new Vector3(-3.675f, 1.55f, 3.62f)),
            new("tread_03", new Vector3(-3.675f, 2.25f, 3.2f)),
            new("tread_04", new Vector3(-3.675f, 2.95f, 2.78f)),
            new("tread_05", new Vector3(-3.675f, 3.65f, 2.36f)),
            new("upper_landing", new Vector3(-3.675f, 3.65f, 1.775f)),
            new("upper_exit", new Vector3(-3.675f, 3.65f, 0.875f)),
        }),
        new("S6 mid to upper starboard side", new RoutePoint[]
        {
            new("lower_landing", new Vector3(3.675f, 0.15f, 1.775f)),
            new("tread_01", new Vector3(3.675f, 0.85f, 2.36f)),
            new("tread_02", new Vector3(3.675f, 1.55f, 2.78f)),
            new("tread_03", new Vector3(3.675f, 2.25f, 3.2f)),
            new("tread_04", new Vector3(3.675f, 2.95f, 3.62f)),
            new("tread_05", new Vector3(3.675f, 3.65f, 4.04f)),
            new("upper_landing", new Vector3(3.675f, 3.65f, 4.625f)),
            new("upper_exit", new Vector3(3.675f, 3.65f, 5.525f)),
        }),
        new("S7 mid to upper rear above S3", new RoutePoint[]
        {
            new("lower_landing", new Vector3(-1.85f, 0.15f, -31.75f)),
            new("tread_01", new Vector3(-1.85f, 0.85f, -32.335f)),
            new("tread_02", new Vector3(-1.85f, 1.55f, -32.755f)),
            new("tread_03", new Vector3(-1.85f, 2.25f, -33.175f)),
            new("tread_04", new Vector3(-1.85f, 2.95f, -33.595f)),
            new("tread_05", new Vector3(-1.85f, 3.65f, -34.015f)),
            new("upper_landing", new Vector3(-1.85f, 3.65f, -34.6f)),
            new("upper_exit", new Vector3(-1.85f, 3.65f, -35.5f)),
        }),
    };

    private PlayerController _player = null!;
    private Node3D _shipRoot = null!;
    private int _routeIndex;
    private int _pointIndex;
    private int _frame;
    private float _routeSeconds;
    private float _stuckSeconds;
    private float _bestDistance;
    private bool _finished;
    private int _failedRoutes;
    private readonly Godot.Collections.Array<GDict> _routeResults = new();
    private readonly Godot.Collections.Array<GDict> _events = new();

    public override void _Ready()
    {
        ProcessPhysicsPriority = 100;
        _player = GetNode<PlayerController>(PlayerPath);
        _shipRoot = GetNode<Node3D>(ShipRootPath);
        StartRoute(0);
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
        _routeSeconds += deltaSeconds;
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

        if (_frame % 20 == 0)
        {
            Record("sample", $"Moving toward {CurrentRoute().Points[_pointIndex].Name}.");
        }

        if (distance <= CheckpointTolerance)
        {
            Record("checkpoint", $"Reached {CurrentRoute().Points[_pointIndex].Name}.");
            _pointIndex++;
            if (_pointIndex >= CurrentRoute().Points.Length)
            {
                CompleteCurrentRoute("pass", "Route is passable.");
                StartRoute(_routeIndex + 1);
                return;
            }

            _bestDistance = DistanceToCurrentCheckpoint();
            _stuckSeconds = 0.0f;
            FaceCurrentCheckpoint();
            return;
        }

        if (_stuckSeconds >= StuckSeconds)
        {
            CompleteCurrentRoute("fail", $"Player stalled before {CurrentRoute().Points[_pointIndex].Name}.");
            StartRoute(_routeIndex + 1);
            return;
        }

        if (_routeSeconds >= MaximumRouteSeconds)
        {
            CompleteCurrentRoute("fail", $"Timed out before {CurrentRoute().Points[_pointIndex].Name}.");
            StartRoute(_routeIndex + 1);
        }
    }

    private void StartRoute(int routeIndex)
    {
        ReleaseMovementInput();
        if (routeIndex >= _routes.Length)
        {
            Finish();
            return;
        }

        _routeIndex = routeIndex;
        _pointIndex = 1;
        _routeSeconds = 0.0f;
        _stuckSeconds = 0.0f;
        MovePlayerToLocalOrigin(CurrentRoute().Points[0].LocalOrigin);
        FaceCurrentCheckpoint();
        _bestDistance = DistanceToCurrentCheckpoint();
        Record("start", $"Starting {CurrentRoute().Name}.");
        Input.ActionPress("move_forward");
    }

    private Route CurrentRoute()
    {
        return _routes[_routeIndex];
    }

    private void CompleteCurrentRoute(string status, string message)
    {
        ReleaseMovementInput();
        Record(status, message);
        if (status != "pass")
        {
            _failedRoutes++;
        }

        _routeResults.Add(new GDict
        {
            ["route"] = CurrentRoute().Name,
            ["status"] = status,
            ["message"] = message,
            ["frames"] = _frame,
            ["elapsed_seconds"] = Mathf.Snapped(_routeSeconds, 0.001f),
            ["point_index"] = _pointIndex,
            ["point_count"] = CurrentRoute().Points.Length,
            ["target"] = CurrentRoute().Points[Mathf.Min(_pointIndex, CurrentRoute().Points.Length - 1)].Name,
            ["player_local_origin"] = FormatVector(LocalPlayerOrigin()),
            ["slide_collision_count"] = _player.GetSlideCollisionCount(),
            ["slide_collision_details"] = ReadSlideCollisionDetails(),
            ["support_probe"] = ReadSupportProbe(),
        });
    }

    private void Finish()
    {
        _finished = true;
        ReleaseMovementInput();
        var status = _failedRoutes == 0 ? "pass" : "fail";
        var message = _failedRoutes == 0
            ? "All MX01 stair routes are passable with the real PlayerController."
            : $"{_failedRoutes} MX01 stair route(s) failed with the real PlayerController.";
        WriteReport(status, message);
        if (_failedRoutes == 0)
        {
            GD.Print(message);
            GetTree().Quit(0);
        }
        else
        {
            GD.PushError(message);
            GetTree().Quit(2);
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
        if (_pointIndex >= CurrentRoute().Points.Length)
        {
            return;
        }

        var local = LocalPlayerOrigin();
        var target = CurrentRoute().Points[_pointIndex].LocalOrigin;
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
        if (_pointIndex >= CurrentRoute().Points.Length)
        {
            return 0.0f;
        }

        var local = LocalPlayerOrigin();
        var target = CurrentRoute().Points[_pointIndex].LocalOrigin;
        return new Vector2(local.X - target.X, local.Z - target.Z).Length();
    }

    private Vector3 LocalPlayerOrigin()
    {
        return _player.GlobalPosition - _shipRoot.GlobalPosition;
    }

    private void Record(string kind, string message)
    {
        var target = CurrentRoute().Points[Mathf.Min(_pointIndex, CurrentRoute().Points.Length - 1)];
        _events.Add(new GDict
        {
            ["frame"] = _frame,
            ["route"] = CurrentRoute().Name,
            ["time_seconds"] = Mathf.Snapped(_routeSeconds, 0.001f),
            ["kind"] = kind,
            ["message"] = message,
            ["point_index"] = _pointIndex,
            ["target"] = target.Name,
            ["target_local_origin"] = FormatVector(target.LocalOrigin),
            ["player_local_origin"] = FormatVector(LocalPlayerOrigin()),
            ["distance_to_target"] = Mathf.Snapped(DistanceToCurrentCheckpoint(), 0.001f),
            ["best_distance_to_target"] = Mathf.Snapped(_bestDistance, 0.001f),
            ["stuck_seconds"] = Mathf.Snapped(_stuckSeconds, 0.001f),
            ["velocity"] = FormatVector(_player.Velocity),
            ["grounded"] = _player.DebugGrounded,
            ["movement_mode"] = _player.DebugMovementMode.ToString(),
            ["support_probe"] = ReadSupportProbe(),
            ["slide_collision_count"] = _player.GetSlideCollisionCount(),
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
            return new GDict { ["hit"] = false, ["from"] = FormatVector(from), ["to"] = FormatVector(to) };
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

    private Godot.Collections.Array<GDict> ReadSlideCollisionDetails()
    {
        var details = new Godot.Collections.Array<GDict>();
        for (var index = 0; index < _player.GetSlideCollisionCount(); index++)
        {
            var collision = _player.GetSlideCollision(index);
            var collider = collision.GetCollider();
            details.Add(new GDict
            {
                ["collider"] = collider is Node node ? node.Name.ToString() : collider.ToString(),
                ["collider_path"] = collider is Node nodeWithPath ? nodeWithPath.GetPath().ToString() : "",
                ["normal"] = FormatVector(collision.GetNormal()),
                ["position"] = FormatVector(collision.GetPosition()),
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
            ["test"] = "all_stairs_real_player_controller_movement",
            ["status"] = status,
            ["message"] = message,
            ["failed_routes"] = _failedRoutes,
            ["route_count"] = _routes.Length,
            ["route_results"] = _routeResults,
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

    private readonly record struct Route(string Name, RoutePoint[] Points);
    private readonly record struct RoutePoint(string Name, Vector3 LocalOrigin);
}
