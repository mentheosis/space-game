using Godot;
using System.Collections.Generic;
using GDict = Godot.Collections.Dictionary<string, Godot.Variant>;
using GEventArray = Godot.Collections.Array<Godot.Collections.Dictionary<string, Godot.Variant>>;

public partial class PrototypeShuttleInteriorCollisionValidationRunner : Node
{
    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public NodePath LoaderPath { get; set; } = "../PrototypeShuttle";
    [Export] public string ReportPath { get; set; } = "res://reports/ship_pipeline/prototype_shuttle_interior_collision_runtime_report.json";
    [Export] public int RequiredInteriorCollisionShapes { get; set; } = 20;

    private readonly GEventArray _events = new();
    private PlayerController _player = null!;
    private PrototypeShuttleDebugLoader _loader = null!;
    private ShipController? _ship;

    public override void _Ready()
    {
        _player = GetNode<PlayerController>(PlayerPath);
        _loader = GetNode<PrototypeShuttleDebugLoader>(LoaderPath);
        CallDeferred(MethodName.RunValidation);
    }

    private void RunValidation()
    {
        _ship = _loader.GetNodeOrNull<ShipController>("PrototypeShuttleShip");
        if (_ship is null)
        {
            Fail("Prototype shuttle ship controller was not spawned by loader.");
            return;
        }

        _ship.ForceLandedForValidation();
        _player.SetPlayerContext(PlayerContext.InShipInterior);
        _player.AttachToShipInteriorFrame(_ship);

        var shapeCount = CountInteriorCollisionShapes(_ship);
        if (shapeCount < RequiredInteriorCollisionShapes)
        {
            Fail($"Expected at least {RequiredInteriorCollisionShapes} interior collision shapes, found {shapeCount}.");
            return;
        }

        foreach (var probe in BuildProbes())
        {
            if (!RunProbe(probe))
            {
                return;
            }
        }

        Pass($"Interior collision runtime validation passed with {shapeCount} generated enclosure shapes.");
    }

    private bool RunProbe(Probe probe)
    {
        if (_ship is null)
        {
            return false;
        }

        _player.MoveToTransform(new Transform3D(Basis.Identity, _ship.GlobalTransform * probe.StartLocal));
        _player.Velocity = Vector3.Zero;

        var motion = _ship.GlobalTransform.Basis * probe.MotionLocal;
        var collision = _player.MoveAndCollide(motion, testOnly: true);
        var collided = collision is not null;
        var pass = collided == probe.ExpectCollision;
        Record(pass ? "probe_pass" : "probe_fail", probe, collided, collision);

        if (!pass)
        {
            var expected = probe.ExpectCollision ? "collision" : "clearance";
            var actual = collided ? $"collision with {collision?.GetCollider()}" : "clearance";
            Fail($"{probe.Id} expected {expected}, got {actual}.");
            return false;
        }

        return true;
    }

    private static List<Probe> BuildProbes()
    {
        return new List<Probe>
        {
            new("cargo_left_wall_blocks", new Vector3(0.0f, -0.65f, 7.0f), new Vector3(-6.0f, 0.0f, 0.0f), true),
            new("cargo_right_wall_blocks", new Vector3(0.0f, -0.65f, 7.0f), new Vector3(6.0f, 0.0f, 0.0f), true),
            new("cargo_ceiling_blocks", new Vector3(0.0f, -0.65f, 7.0f), new Vector3(0.0f, 4.0f, 0.0f), true),
            new("cargo_aft_bulkhead_blocks", new Vector3(0.0f, 1.0f, 12.5f), new Vector3(0.0f, 0.0f, 4.0f), true),
            new("ramp_left_jamb_blocks", new Vector3(0.0f, -1.8f, -1.65f), new Vector3(-2.4f, 0.0f, 0.0f), true),
            new("ramp_right_jamb_blocks", new Vector3(0.0f, -1.8f, -1.65f), new Vector3(2.4f, 0.0f, 0.0f), true),
            new("left_stair_top_outer_guard_blocks", new Vector3(-2.17f, 1.62f, -2.15f), new Vector3(-1.25f, 0.0f, 0.0f), true),
            new("right_stair_top_outer_guard_blocks", new Vector3(2.17f, 1.62f, -2.15f), new Vector3(1.25f, 0.0f, 0.0f), true),
            new("left_stair_top_inner_guard_blocks", new Vector3(-1.9f, 1.62f, -2.15f), new Vector3(1.0f, 0.0f, 0.0f), true),
            new("right_stair_top_inner_guard_blocks", new Vector3(1.9f, 1.62f, -2.15f), new Vector3(-1.0f, 0.0f, 0.0f), true),
            new("cockpit_left_wall_blocks", new Vector3(0.0f, 1.82f, -9.0f), new Vector3(-3.0f, 0.0f, 0.0f), true),
            new("cockpit_right_wall_blocks", new Vector3(0.0f, 1.82f, -9.0f), new Vector3(3.0f, 0.0f, 0.0f), true),
            new("cockpit_canopy_blocks", new Vector3(0.0f, 1.82f, -9.0f), new Vector3(0.0f, 3.0f, 0.0f), true),
            new("cockpit_forward_glass_blocks", new Vector3(0.0f, 1.82f, -12.7f), new Vector3(0.0f, 0.0f, -2.2f), true),
            new("cargo_center_path_clear", new Vector3(0.0f, -0.65f, 4.0f), new Vector3(0.0f, 0.0f, 1.1f), false),
            new("cockpit_center_path_clear", new Vector3(0.0f, 1.82f, -9.0f), new Vector3(0.0f, 0.0f, 1.1f), false),
        };
    }

    private static int CountInteriorCollisionShapes(Node node)
    {
        var count = 0;
        foreach (var child in node.GetChildren())
        {
            if (child is CollisionShape3D shape && shape.Name.ToString().EndsWith("_InteriorCollision"))
            {
                count++;
            }

            count += CountInteriorCollisionShapes(child);
        }

        return count;
    }

    private void Pass(string message)
    {
        Record("pass", message);
        WriteReport(true, message);
        GD.Print(message);
        GetTree().Quit(0);
    }

    private void Fail(string message)
    {
        Record("fail", message);
        WriteReport(false, message);
        GD.PushError($"FAIL: {message}");
        GetTree().Quit(1);
    }

    private void Record(string status, string message)
    {
        _events.Add(new GDict
        {
            ["status"] = status,
            ["message"] = message,
        });
    }

    private void Record(string status, Probe probe, bool collided, KinematicCollision3D? collision)
    {
        _events.Add(new GDict
        {
            ["status"] = status,
            ["probe"] = probe.Id,
            ["expected_collision"] = probe.ExpectCollision,
            ["actual_collision"] = collided,
            ["collider"] = collision?.GetCollider()?.ToString() ?? "",
            ["start_local"] = new Godot.Collections.Array<float> { probe.StartLocal.X, probe.StartLocal.Y, probe.StartLocal.Z },
            ["motion_local"] = new Godot.Collections.Array<float> { probe.MotionLocal.X, probe.MotionLocal.Y, probe.MotionLocal.Z },
        });
    }

    private void WriteReport(bool pass, string message)
    {
        var report = new GDict
        {
            ["schema_version"] = 1,
            ["pass"] = pass,
            ["message"] = message,
            ["events"] = _events,
        };

        var globalPath = ProjectSettings.GlobalizePath(ReportPath);
        using var file = Godot.FileAccess.Open(globalPath, Godot.FileAccess.ModeFlags.Write);
        file.StoreString(Json.Stringify(report, "\t"));
    }

    private readonly record struct Probe(string Id, Vector3 StartLocal, Vector3 MotionLocal, bool ExpectCollision);
}
