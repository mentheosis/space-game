using Godot;
using GDict = Godot.Collections.Dictionary<string, Godot.Variant>;
using GEventArray = Godot.Collections.Array<Godot.Collections.Dictionary<string, Godot.Variant>>;

public partial class PrototypeShuttleRampApproachValidationRunner : Node
{
    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public NodePath LoaderPath { get; set; } = "../PrototypeShuttle";
    [Export] public string ReportPath { get; set; } = "res://reports/ship_pipeline/prototype_shuttle_ramp_approach_validation_report.json";
    [Export] public int MaxFrames { get; set; } = 540;
    [Export] public float RequiredInteriorLocalZ { get; set; } = 0.35f;
    [Export] public float MaxExteriorHideBeforeLocalY { get; set; } = -2.05f;
    [Export] public float MinRequiredProgressZ { get; set; } = 3.2f;

    private readonly GEventArray _events = new();
    private PlayerController _player = null!;
    private PrototypeShuttleDebugLoader _loader = null!;
    private ShipController? _ship;
    private Node3D? _exterior;
    private int _frame;
    private bool _finished;
    private float _startLocalZ;
    private float _bestLocalZ;

    public override void _Ready()
    {
        _player = GetNode<PlayerController>(PlayerPath);
        _loader = GetNode<PrototypeShuttleDebugLoader>(LoaderPath);
        CallDeferred(MethodName.TryStartValidation);
    }

    public override void _ExitTree()
    {
        Input.ActionRelease("move_forward");
    }

    public override void _PhysicsProcess(double delta)
    {
        if (_finished || _ship is null)
        {
            return;
        }

        _frame++;
        var localPosition = ToShipLocal(_player.GlobalPosition);
        _bestLocalZ = Mathf.Max(_bestLocalZ, localPosition.Z);
        FaceTarget(_ship.GlobalTransform * new Vector3(0.0f, -0.80f, 1.15f));

        if (_exterior is not null
            && !_exterior.Visible
            && localPosition.Y < MaxExteriorHideBeforeLocalY
            && _player.DebugPlayerContext == PlayerContext.InShipInterior)
        {
            Fail($"Exterior hidden before player crossed the interior threshold. local={Format(localPosition)}");
            return;
        }

        if (_frame == 1)
        {
            Input.ActionPress("move_forward");
            Record("move_start", $"Walking from ramp exterior. local={Format(localPosition)}");
        }

        if (localPosition.Z >= RequiredInteriorLocalZ && _player.DebugPlayerContext == PlayerContext.InShipInterior)
        {
            Pass($"Ramp approach validation passed. Entered interior at local={Format(localPosition)}.");
            return;
        }

        if (_frame >= MaxFrames)
        {
            var progressZ = _bestLocalZ - _startLocalZ;
            if (progressZ < MinRequiredProgressZ)
            {
                Fail($"Player did not make enough forward progress up the ramp. ProgressZ={progressZ:0.00}, local={Format(localPosition)}.");
            }
            else
            {
                Fail($"Player progressed up ramp but did not enter interior by frame {MaxFrames}. local={Format(localPosition)}, context={_player.DebugPlayerContext}.");
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

        _ship.ForceLandedForValidation();
        _exterior = _ship.GetNodeOrNull<Node3D>("Exterior");
        if (_exterior is null)
        {
            Fail("Prototype shuttle exterior visual node was not found.");
            return;
        }

        var startLocal = new Vector3(0.0f, -2.70f, -4.15f);
        _player.MoveToTransform(new Transform3D(Basis.Identity, _ship.GlobalTransform * startLocal));
        _player.SetPlayerContext(PlayerContext.OnFoot);
        _player.DetachFromShipInteriorFrame(inheritShipMomentum: false);
        _player.Velocity = Vector3.Zero;

        _startLocalZ = startLocal.Z;
        _bestLocalZ = startLocal.Z;
        Record("start", $"Starting outside ramp. local={Format(startLocal)}, exteriorVisible={_exterior.Visible}.");
    }

    private Vector3 ToShipLocal(Vector3 globalPosition)
    {
        return _ship is null ? Vector3.Zero : _ship.GlobalTransform.AffineInverse() * globalPosition;
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
        _player.GlobalTransform = new Transform3D(new Basis(right, up, -forward).Orthonormalized(), _player.GlobalPosition);
    }

    private void Pass(string message)
    {
        if (_finished)
        {
            return;
        }

        _finished = true;
        Input.ActionRelease("move_forward");
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
        Input.ActionRelease("move_forward");
        Record("fail", message);
        WriteReport(false, message);
        GD.PushError($"FAIL: {message}");
        GetTree().Quit(1);
    }

    private void Record(string status, string message)
    {
        var local = ToShipLocal(_player.GlobalPosition);
        _events.Add(new GDict
        {
            ["frame"] = _frame,
            ["status"] = status,
            ["message"] = message,
            ["player_local"] = new Godot.Collections.Array<float> { local.X, local.Y, local.Z },
            ["player_context"] = _player.DebugPlayerContext.ToString(),
            ["exterior_visible"] = _exterior?.Visible ?? false,
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
            ["events"] = _events,
        };

        var globalPath = ProjectSettings.GlobalizePath(ReportPath);
        using var file = Godot.FileAccess.Open(globalPath, Godot.FileAccess.ModeFlags.Write);
        file.StoreString(Json.Stringify(report, "\t"));
    }

    private static string Format(Vector3 value)
    {
        return $"({value.X:0.00}, {value.Y:0.00}, {value.Z:0.00})";
    }
}
