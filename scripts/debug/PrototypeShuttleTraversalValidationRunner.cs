using Godot;
using System.Collections.Generic;
using GDict = Godot.Collections.Dictionary<string, Godot.Variant>;
using GEventArray = Godot.Collections.Array<Godot.Collections.Dictionary<string, Godot.Variant>>;

public partial class PrototypeShuttleTraversalValidationRunner : Node
{
    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public NodePath LoaderPath { get; set; } = "../PrototypeShuttleDebugLoader";
    [Export] public string MarkerPath { get; set; } = "res://assets/models/ship/prototype_shuttle/prototype_shuttle_markers.json";
    [Export] public string CollisionLayoutPath { get; set; } = "res://assets/models/ship/prototype_shuttle/prototype_shuttle_collision_layout_report.json";
    [Export] public string ReportPath { get; set; } = "res://reports/ship_pipeline/prototype_shuttle_traversal_validation_report.json";
    [Export] public float CheckpointTolerance { get; set; } = 0.72f;
    [Export] public int MaxFrames { get; set; } = 2400;
    [Export] public int MaxUngroundedFrames { get; set; } = 24;

    private readonly List<RouteCheckpoint> _route = new();
    private readonly GEventArray _events = new();
    private PlayerController _player = null!;
    private PrototypeShuttleDebugLoader _loader = null!;
    private int _frame;
    private int _routeIndex;
    private int _ungroundedFrames;
    private bool _failed;

    public override void _Ready()
    {
        _player = GetNode<PlayerController>(PlayerPath);
        _loader = GetNode<PrototypeShuttleDebugLoader>(LoaderPath);
        BuildRoute();

        if (_route.Count == 0)
        {
            Fail("No traversal route checkpoints were generated.");
            return;
        }

        var start = _route[0].Position;
        _player.GlobalPosition = start;
        _player.Velocity = Vector3.Zero;
        _player.SetPlayerContext(PlayerContext.OnFoot);
        _player.AutoStepEnabled = true;
        Input.ActionPress("move_forward");
        Record("start", $"Traversal route has {_route.Count} checkpoints.");
    }

    public override void _ExitTree()
    {
        Input.ActionRelease("move_forward");
    }

    public override void _PhysicsProcess(double delta)
    {
        if (_failed)
        {
            return;
        }

        _frame++;
        if (_frame > MaxFrames)
        {
            Fail($"Timed out at checkpoint {_routeIndex + 1}/{_route.Count}: {_route[_routeIndex].Name}");
            return;
        }

        if (!_player.DebugGrounded)
        {
            _ungroundedFrames++;
            if (_ungroundedFrames > MaxUngroundedFrames)
            {
                Fail($"Player lost grounded traversal near checkpoint {_route[_routeIndex].Name}.");
                return;
            }
        }
        else
        {
            _ungroundedFrames = 0;
        }

        var target = _route[_routeIndex];
        FaceTarget(target.Position);

        if (HorizontalDistance(_player.GlobalPosition, target.Position) <= CheckpointTolerance)
        {
            Record("checkpoint", $"Reached {target.Name}.");
            _routeIndex++;
            if (_routeIndex >= _route.Count)
            {
                Pass();
                return;
            }
        }
    }

    private void BuildRoute()
    {
        var markers = LoadDictionary(MarkerPath);
        var layout = LoadDictionary(CollisionLayoutPath);
        var surfaces = BuildSurfaceLookup(layout);
        var shuttleOffset = _loader.ShuttlePosition;

        var rampEnd = ReadVector(markers, "RampEnd") + shuttleOffset;
        var rampStart = ReadVector(markers, "RampStart") + shuttleOffset;
        _route.Add(new RouteCheckpoint("ramp_bottom", rampEnd + Vector3.Up * 0.95f));
        _route.Add(new RouteCheckpoint("ramp_top", rampStart + Vector3.Up * 0.95f));

        AddSurfaceCheckpoint(surfaces, "cargo_forward_lower", shuttleOffset);
        AddSurfaceCheckpoint(surfaces, "left_stair_09", shuttleOffset);
        AddSurfaceCheckpoint(surfaces, "left_stair_06", shuttleOffset);
        AddSurfaceCheckpoint(surfaces, "left_stair_03", shuttleOffset);
        AddSurfaceCheckpoint(surfaces, "left_stair_00", shuttleOffset);
        AddSurfaceCheckpoint(surfaces, "cockpit_entry_landing", shuttleOffset);

        var cockpit = SurfaceCheckpoint(surfaces, "cockpit_floor", shuttleOffset);
        cockpit.Position = new Vector3(0.0f, cockpit.Position.Y, -5.6f) + new Vector3(shuttleOffset.X, 0.0f, shuttleOffset.Z);
        _route.Add(cockpit);
    }

    private void AddSurfaceCheckpoint(Dictionary<string, GDict> surfaces, string id, Vector3 shuttleOffset)
    {
        _route.Add(SurfaceCheckpoint(surfaces, id, shuttleOffset));
    }

    private RouteCheckpoint SurfaceCheckpoint(Dictionary<string, GDict> surfaces, string id, Vector3 shuttleOffset)
    {
        if (!surfaces.TryGetValue(id, out var surface))
        {
            Fail($"Missing traversal surface: {id}");
            return new RouteCheckpoint(id, shuttleOffset);
        }

        var center = ReadVector(surface, "center");
        var size = ReadVector(surface, "size");
        var position = center + new Vector3(0.0f, size.Y * 0.5f + 0.95f, 0.0f) + shuttleOffset;
        return new RouteCheckpoint(id, position);
    }

    private void FaceTarget(Vector3 target)
    {
        var up = _player.DebugUpDirection.LengthSquared() > 0.0001f ? _player.DebugUpDirection.Normalized() : Vector3.Up;
        var toTarget = target - _player.GlobalPosition;
        var forward = toTarget - up * toTarget.Dot(up);
        if (forward.LengthSquared() < 0.0001f)
        {
            return;
        }

        forward = forward.Normalized();
        var right = forward.Cross(up).Normalized();
        var basis = new Basis(right, up, -forward).Orthonormalized();
        var transform = _player.GlobalTransform;
        transform.Basis = basis;
        _player.GlobalTransform = transform;
    }

    private static float HorizontalDistance(Vector3 a, Vector3 b)
    {
        var delta = a - b;
        delta.Y = 0.0f;
        return delta.Length();
    }

    private Dictionary<string, GDict> BuildSurfaceLookup(GDict layout)
    {
        var lookup = new Dictionary<string, GDict>();
        if (!layout.TryGetValue("surfaces", out var surfacesVariant) || surfacesVariant.VariantType != Variant.Type.Array)
        {
            Fail("Collision layout report has no surfaces array.");
            return lookup;
        }

        foreach (var item in surfacesVariant.AsGodotArray())
        {
            if (item.VariantType != Variant.Type.Dictionary)
            {
                continue;
            }

            var surface = item.AsGodotDictionary<string, Variant>();
            var id = surface.GetValueOrDefault("id").AsString();
            if (!string.IsNullOrEmpty(id))
            {
                lookup[id] = surface;
            }
        }

        return lookup;
    }

    private GDict LoadDictionary(string path)
    {
        if (!Godot.FileAccess.FileExists(path))
        {
            Fail($"Missing JSON file: {path}");
            return new GDict();
        }

        var text = Godot.FileAccess.GetFileAsString(path);
        var parsed = Json.ParseString(text);
        if (parsed.VariantType != Variant.Type.Dictionary)
        {
            Fail($"JSON file is not an object: {path}");
            return new GDict();
        }

        return parsed.AsGodotDictionary<string, Variant>();
    }

    private static Vector3 ReadVector(GDict source, string key)
    {
        if (!source.TryGetValue(key, out var value) || value.VariantType != Variant.Type.Array)
        {
            return Vector3.Zero;
        }

        var array = value.AsGodotArray();
        if (array.Count < 3)
        {
            return Vector3.Zero;
        }

        return new Vector3((float)array[0], (float)array[1], (float)array[2]);
    }

    private void Pass()
    {
        Record("pass", "Prototype shuttle traversal validation passed.");
        WriteReport(true, "Prototype shuttle traversal validation passed.");
        GD.Print("Prototype shuttle traversal validation passed.");
        GetTree().Quit(0);
    }

    private void Fail(string message)
    {
        if (_failed)
        {
            return;
        }

        _failed = true;
        Input.ActionRelease("move_forward");
        Record("fail", message);
        WriteReport(false, message);
        GD.PushError($"FAIL: {message}");
        GetTree().Quit(1);
    }

    private void Record(string status, string message)
    {
        _events.Add(new GDict
        {
            ["frame"] = _frame,
            ["status"] = status,
            ["message"] = message,
            ["player_position"] = new Godot.Collections.Array<float> { _player.GlobalPosition.X, _player.GlobalPosition.Y, _player.GlobalPosition.Z },
            ["checkpoint_index"] = _routeIndex,
            ["grounded"] = _player.DebugGrounded,
        });
    }

    private void WriteReport(bool pass, string message)
    {
        var report = new GDict
        {
            ["schema_version"] = 1,
            ["pass"] = pass,
            ["message"] = message,
            ["frames"] = _frame,
            ["checkpoint_count"] = _route.Count,
            ["auto_step_count"] = _player.DebugAutoStepCount,
            ["events"] = _events,
        };

        var absolutePath = ProjectSettings.GlobalizePath(ReportPath);
        using var file = Godot.FileAccess.Open(absolutePath, Godot.FileAccess.ModeFlags.Write);
        file?.StoreString(Json.Stringify(report, "\t"));
    }

    private struct RouteCheckpoint
    {
        public string Name;
        public Vector3 Position;

        public RouteCheckpoint(string name, Vector3 position)
        {
            Name = name;
            Position = position;
        }
    }
}
