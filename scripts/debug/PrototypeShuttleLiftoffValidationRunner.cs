using Godot;
using GDict = Godot.Collections.Dictionary<string, Godot.Variant>;
using GEventArray = Godot.Collections.Array<Godot.Collections.Dictionary<string, Godot.Variant>>;

public partial class PrototypeShuttleLiftoffValidationRunner : Node
{
    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public NodePath LoaderPath { get; set; } = "../PrototypeShuttle";
    [Export] public string ReportPath { get; set; } = "res://reports/ship_pipeline/prototype_shuttle_liftoff_validation_report.json";
    [Export] public int MaxFrames { get; set; } = 240;
    [Export] public int WarmupFrames { get; set; } = 8;
    [Export] public float MaxAllowedDrop { get; set; } = 0.45f;
    [Export] public float RequiredLiftGain { get; set; } = 0.65f;
    [Export] public int RequiredContractCollisionShapes { get; set; } = 4;

    private readonly GEventArray _events = new();
    private PlayerController _player = null!;
    private PrototypeShuttleDebugLoader _loader = null!;
    private ShipController? _ship;
    private int _frame;
    private float _initialY;
    private float _lowestY;
    private bool _started;
    private bool _finished;

    public override void _Ready()
    {
        _player = GetNode<PlayerController>(PlayerPath);
        _loader = GetNode<PrototypeShuttleDebugLoader>(LoaderPath);
        CallDeferred(MethodName.TryStartValidation);
    }

    public override void _ExitTree()
    {
        Input.ActionRelease("ship_translate_up");
    }

    public override void _PhysicsProcess(double delta)
    {
        if (!_started || _finished || _ship is null)
        {
            return;
        }

        _frame++;
        var currentY = _ship.GlobalPosition.Y;
        _lowestY = Mathf.Min(_lowestY, currentY);

        if (_frame == WarmupFrames)
        {
            Input.ActionPress("ship_translate_up");
            Record("ascend_start", "Pressed ship_translate_up.");
        }

        if (_lowestY < _initialY - MaxAllowedDrop)
        {
            Fail($"Prototype shuttle dropped below allowed threshold during liftoff. InitialY={_initialY:0.00}, LowestY={_lowestY:0.00}.");
            return;
        }

        if (_frame >= MaxFrames)
        {
            var gained = currentY - _initialY;
            if (gained >= RequiredLiftGain)
            {
                Pass($"Prototype shuttle liftoff validation passed. GainedY={gained:0.00}, LowestY={_lowestY:0.00}.");
            }
            else
            {
                Fail($"Prototype shuttle did not gain enough altitude. GainedY={gained:0.00}, Required={RequiredLiftGain:0.00}.");
            }
        }
    }

    private void TryStartValidation()
    {
        _ship = _loader.GetNodeOrNull<ShipController>("PrototypeShuttleShip");
        if (_ship is null)
        {
            Fail("Prototype shuttle ship controller was not spawned by loader.");
            return;
        }

        var contractShapeCount = CountContractPhysicsCollisionShapes(_ship);
        if (contractShapeCount < RequiredContractCollisionShapes)
        {
            Fail($"Expected at least {RequiredContractCollisionShapes} contract physics collision shapes, found {contractShapeCount}.");
            return;
        }

        var seatAnchor = _ship.GetNodeOrNull<Marker3D>("Markers/SeatAnchor");
        if (seatAnchor is null)
        {
            Fail("Prototype shuttle has no SeatAnchor marker.");
            return;
        }

        _player.MoveToTransform(seatAnchor.GlobalTransform);
        _player.SetPlayerContext(PlayerContext.Seated);
        _ship.SetPilot(_player);
        _ship.ForceLandedForValidation();

        _initialY = _ship.GlobalPosition.Y;
        _lowestY = _initialY;
        _started = true;
        Record("start", $"Starting liftoff validation at Y={_initialY:0.00} with {contractShapeCount} contract physics shapes.");
    }

    private static int CountContractPhysicsCollisionShapes(Node node)
    {
        var count = 0;
        foreach (var child in node.GetChildren())
        {
            if (child is CollisionShape3D shape && shape.Name.ToString().EndsWith("_PhysicsCollision"))
            {
                count++;
            }

            count += CountContractPhysicsCollisionShapes(child);
        }

        return count;
    }

    private void Pass(string message)
    {
        if (_finished)
        {
            return;
        }

        _finished = true;
        Input.ActionRelease("ship_translate_up");
        Record("pass", message);
        WriteReport(true, message);
        GD.Print(message);
        GetTree().Quit(0);
    }

    private void Fail(string message)
    {
        if (_finished)
        {
            return;
        }

        _finished = true;
        Input.ActionRelease("ship_translate_up");
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
            ["ship_position"] = _ship is null
                ? new Godot.Collections.Array<float>()
                : new Godot.Collections.Array<float> { _ship.GlobalPosition.X, _ship.GlobalPosition.Y, _ship.GlobalPosition.Z },
            ["ship_speed"] = _ship?.Speed ?? 0.0f,
            ["is_landed"] = _ship?.IsLanded ?? false,
            ["pilot_active"] = _ship?.IsPiloted ?? false,
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
            ["initial_y"] = _initialY,
            ["lowest_y"] = _lowestY,
            ["max_allowed_drop"] = MaxAllowedDrop,
            ["required_lift_gain"] = RequiredLiftGain,
            ["events"] = _events,
        };

        var absolutePath = ProjectSettings.GlobalizePath(ReportPath);
        using var file = Godot.FileAccess.Open(absolutePath, Godot.FileAccess.ModeFlags.Write);
        file?.StoreString(Json.Stringify(report, "\t"));
    }
}
