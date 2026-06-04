using Godot;
using Godot.Collections;
using GArray = Godot.Collections.Array;
using GDict = Godot.Collections.Dictionary<string, Godot.Variant>;

public partial class CargoCranePlayerTraversalValidationRunner : Node3D
{
    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public Vector3 ShipOrigin { get; set; } = new(0.0f, 214.06f, 0.0f);
    [Export] public string LayoutContractPath { get; set; } = "res://assets/source/blender/ships/cargo_crane/cargo_crane_interior_layout_contract.json";
    [Export] public string TraversalSurfacesPath { get; set; } = "res://assets/models/ship/cargo_crane/cargo_crane_traversal_surfaces.json";
    [Export] public string ReportPath { get; set; } = "res://reports/ship_pipeline/cargo_crane_player_traversal_validation_report.json";
    [Export] public float PlanarTolerance { get; set; } = 0.48f;
    [Export] public float MaximumSecondsPerCheckpoint { get; set; } = 5.0f;
    [Export] public float MinimumProgressMeters { get; set; } = 0.22f;
    [Export] public float StuckSeconds { get; set; } = 1.25f;
    [Export] public float VerticalEnvelopePadding { get; set; } = 3.2f;
    [Export] public float SupportHeightTolerance { get; set; } = 1.25f;
    [Export] public float DirectStepSpeed { get; set; } = 6.0f;
    [Export] public float EdgeProbeStep { get; set; } = 0.65f;
    [Export] public float EdgeProbeInsideInset { get; set; } = 0.24f;
    [Export] public float EdgeProbeOutwardDistance { get; set; } = 0.78f;
    [Export] public float ShoveProbeSeconds { get; set; } = 1.35f;
    [Export] public float ShoveProbeFallTolerance { get; set; } = 1.25f;
    [Export] public float ShoveProbeEscapeDistance { get; set; } = 1.15f;

    private const uint SolidCollisionLayer = 1u;
    private const uint WalkableSupportCollisionLayer = 1u << 7;

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
    private bool _negativeEdgeProbeComplete;
    private readonly System.Collections.Generic.List<HatchOpening> _approvedOpenings = new();
    private int _shoveProbeIndex;
    private float _shoveProbeSeconds;
    private bool _shoveProbeActive;

    private readonly ShoveProbe[] _shoveProbes =
    {
        new("Port upper stair outer side", new Vector3(-3.72f, -1.0f, 61.2f), Vector3.Left, false),
        new("Port upper stair outer aft diagonal jump", new Vector3(-4.02f, -1.0f, 60.95f), new Vector3(-1.0f, 0.0f, -0.55f), true),
        new("Port upper stair outer forward diagonal jump", new Vector3(-4.02f, -1.0f, 61.65f), new Vector3(-1.0f, 0.0f, 0.55f), true),
        new("Port mid stair outer side", new Vector3(-3.72f, -3.6f, 63.5f), Vector3.Left, false),
        new("Port mid stair outer diagonal jump", new Vector3(-4.02f, -3.6f, 63.6f), new Vector3(-1.0f, 0.0f, 0.35f), true),
        new("Port lower stair outer side", new Vector3(-3.72f, -6.2f, 65.9f), Vector3.Left, false),
        new("Starboard upper stair outer side", new Vector3(3.72f, -1.0f, 61.2f), Vector3.Right, false),
        new("Starboard upper stair outer aft diagonal jump", new Vector3(4.02f, -1.0f, 60.95f), new Vector3(1.0f, 0.0f, -0.55f), true),
        new("Starboard upper stair outer forward diagonal jump", new Vector3(4.02f, -1.0f, 61.65f), new Vector3(1.0f, 0.0f, 0.55f), true),
        new("Starboard mid stair outer side", new Vector3(3.72f, -3.6f, 63.5f), Vector3.Right, false),
        new("Starboard mid stair outer diagonal jump", new Vector3(4.02f, -3.6f, 63.6f), new Vector3(1.0f, 0.0f, 0.35f), true),
        new("Starboard lower stair outer side", new Vector3(3.72f, -6.2f, 65.9f), Vector3.Right, false),
        new("Port upper cockpit aft edge", new Vector3(-4.0f, -1.0f, 60.15f), new Vector3(0.0f, 0.0f, -1.0f), false),
        new("Starboard upper cockpit aft edge", new Vector3(4.0f, -1.0f, 60.15f), new Vector3(0.0f, 0.0f, -1.0f), false),
        new("Port upper cockpit forward-deck aft edge", new Vector3(-3.7f, -1.0f, 66.35f), new Vector3(0.0f, 0.0f, -1.0f), false),
        new("Starboard upper cockpit forward-deck aft edge", new Vector3(3.7f, -1.0f, 66.35f), new Vector3(0.0f, 0.0f, -1.0f), false),
    };

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
        LoadApprovedOpenings(root);
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

    private void LoadApprovedOpenings(GDict root)
    {
        _approvedOpenings.Clear();
        if (!root.TryGetValue("enclosure_generation", out var generationValue)
            || generationValue.VariantType != Variant.Type.Dictionary)
        {
            return;
        }

        var generation = generationValue.AsGodotDictionary<string, Variant>();
        if (!generation.TryGetValue("side_wall_openings", out var openingsValue)
            || openingsValue.VariantType != Variant.Type.Array)
        {
            return;
        }

        foreach (var item in openingsValue.AsGodotArray())
        {
            if (item.VariantType != Variant.Type.Dictionary)
            {
                continue;
            }

            var opening = item.AsGodotDictionary<string, Variant>();
            _approvedOpenings.Add(
                new HatchOpening(
                    ReadString(opening, "side", ""),
                    ReadFloat(opening, "center_y", 0.0f),
                    ReadFloat(opening, "height_y", 0.0f),
                    ReadFloat(opening, "center_z", 0.0f),
                    ReadFloat(opening, "width_z", 0.0f)));
        }
    }

    public override void _ExitTree()
    {
        ReleaseMovementInput();
    }

    public override void _PhysicsProcess(double delta)
    {
        var deltaSeconds = (float)delta;
        if (!_negativeEdgeProbeComplete)
        {
            _negativeEdgeProbeComplete = true;
            if (!RunNegativeEdgeProbe())
            {
                return;
            }
        }

        if (_shoveProbeIndex < _shoveProbes.Length)
        {
            RunShoveProbe(deltaSeconds);
            return;
        }

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
        FaceLocalDirection(forward);
    }

    private void FaceLocalDirection(Vector3 forward)
    {
        if (forward.LengthSquared() < 0.0001f)
            return;

        forward = forward.Normalized();
        var right = forward.Cross(Vector3.Up).Normalized();
        var basis = new Basis(right, Vector3.Up, -forward).Orthonormalized();
        var transform = _player.GlobalTransform;
        transform.Basis = basis;
        _player.GlobalTransform = transform;
    }

    private void RunShoveProbe(float deltaSeconds)
    {
        var probe = _shoveProbes[_shoveProbeIndex];
        if (!_shoveProbeActive)
        {
            ReleaseMovementInput();
            MovePlayerToLocal(probe.LocalOrigin);
            FaceLocalDirection(probe.Direction);
            _shoveProbeSeconds = 0.0f;
            _shoveProbeActive = true;
        }

        Input.ActionPress("move_forward");
        if (probe.JumpPulse && _shoveProbeSeconds < 0.15f)
        {
            Input.ActionPress("jump");
        }
        else
        {
            Input.ActionRelease("jump");
        }
        _shoveProbeSeconds += deltaSeconds;

        var local = LocalPlayerOrigin();
        var planarOffset = new Vector2(local.X - probe.LocalOrigin.X, local.Z - probe.LocalOrigin.Z);
        var direction = new Vector2(probe.Direction.X, probe.Direction.Z);
        if (direction.LengthSquared() > 0.0001f)
        {
            direction = direction.Normalized();
        }

        var outwardTravel = planarOffset.Dot(direction);
        if (local.Y < probe.LocalOrigin.Y - ShoveProbeFallTolerance)
        {
            Fail($"Shove probe fell out at {probe.Name}.", local, outwardTravel);
            return;
        }

        if (local.Z >= 58.5f && local.Z <= 73.5f && Mathf.Abs(local.X) > 4.85f)
        {
            Fail($"Shove probe left cockpit enclosure at {probe.Name}.", local, outwardTravel);
            return;
        }

        if (_shoveProbeSeconds < ShoveProbeSeconds)
        {
            return;
        }

        ReleaseMovementInput();
        Record("shove_probe", $"Passed {probe.Name}.", local, outwardTravel);
        _shoveProbeIndex++;
        _shoveProbeSeconds = 0.0f;
        _shoveProbeActive = false;
        if (_shoveProbeIndex >= _shoveProbes.Length)
        {
            MovePlayerToLocal(_route[0].LocalOrigin);
            _routeIndex = 1;
            _routeSegmentStart = _route[0].LocalOrigin;
            _checkpointSeconds = 0.0f;
            _stuckSeconds = 0.0f;
            _bestDistanceToCheckpoint = DistanceToCurrentCheckpoint();
            Record("route_reset", "Reset player to route start after shove probes.", LocalPlayerOrigin(), _bestDistanceToCheckpoint);
        }
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

    private bool RunNegativeEdgeProbe()
    {
        if (!Godot.FileAccess.FileExists(TraversalSurfacesPath))
        {
            Fail($"Missing traversal surfaces for negative edge probe: {TraversalSurfacesPath}", LocalPlayerOrigin(), 0.0f);
            return false;
        }

        var parsed = Json.ParseString(Godot.FileAccess.GetFileAsString(TraversalSurfacesPath));
        if (parsed.VariantType != Variant.Type.Dictionary)
        {
            Fail($"Invalid traversal surfaces for negative edge probe: {TraversalSurfacesPath}", LocalPlayerOrigin(), 0.0f);
            return false;
        }

        var root = parsed.AsGodotDictionary<string, Variant>();
        if (!root.TryGetValue("surfaces", out var surfacesValue) || surfacesValue.VariantType != Variant.Type.Array)
        {
            Fail($"Traversal surfaces file has no surfaces array: {TraversalSurfacesPath}", LocalPlayerOrigin(), 0.0f);
            return false;
        }

        var edges = BuildRuntimeEdgeProbes(surfacesValue.AsGodotArray());
        var sampleCount = 0;
        foreach (var edge in edges)
        {
            var delta = edge.End - edge.Start;
            var length = delta.Length();
            var count = Mathf.Max(2, Mathf.CeilToInt(length / EdgeProbeStep) + 1);
            for (var index = 0; index < count; index++)
            {
                var t = count <= 1 ? 0.0f : (float)index / (count - 1);
                var point = edge.Start.Lerp(edge.End, t);
                sampleCount++;

                if (IsApprovedOpening(edge, point))
                {
                    continue;
                }
                if (IsInternalCockpitStairwellOpening(edge, point))
                {
                    continue;
                }

                var inside = point - edge.Normal * EdgeProbeInsideInset;
                var outside = point + edge.Normal * EdgeProbeOutwardDistance;
                if (HasRuntimeSolidBarrier(inside, outside) || HasRuntimeSupport(outside))
                {
                    continue;
                }

                Fail($"Negative edge probe found fall-out gap at {edge.SurfaceName}:{edge.EdgeName}.", point, 0.0f);
                return false;
            }
        }

        Record("negative_edge_probe", $"Runtime edge escape probe passed {sampleCount} samples.", LocalPlayerOrigin(), 0.0f);
        return true;
    }

    private System.Collections.Generic.List<RuntimeEdgeProbe> BuildRuntimeEdgeProbes(GArray surfaces)
    {
        var edges = new System.Collections.Generic.List<RuntimeEdgeProbe>();
        foreach (var item in surfaces)
        {
            if (item.VariantType != Variant.Type.Dictionary)
            {
                continue;
            }

            var surface = item.AsGodotDictionary<string, Variant>();
            var name = ReadString(surface, "name", "surface");
            var type = ReadString(surface, "type", "");
            var role = ReadString(surface, "role", "");
            if (type == "floor_box" || type == "objective_floor_patch")
            {
                var center = ReadVector3(surface, "center");
                var size = ReadVector3(surface, "size");
                var x0 = center.X - size.X * 0.5f;
                var x1 = center.X + size.X * 0.5f;
                var z0 = center.Z - size.Z * 0.5f;
                var z1 = center.Z + size.Z * 0.5f;
                var y = center.Y;
                edges.Add(new RuntimeEdgeProbe(name, "port", new Vector3(x0, y, z0), new Vector3(x0, y, z1), Vector3.Left));
                edges.Add(new RuntimeEdgeProbe(name, "starboard", new Vector3(x1, y, z0), new Vector3(x1, y, z1), Vector3.Right));
                edges.Add(new RuntimeEdgeProbe(name, "aft", new Vector3(x0, y, z0), new Vector3(x1, y, z0), new Vector3(0.0f, 0.0f, -1.0f)));
                edges.Add(new RuntimeEdgeProbe(name, "forward", new Vector3(x0, y, z1), new Vector3(x1, y, z1), new Vector3(0.0f, 0.0f, 1.0f)));
            }
            else if (type == "ramp" && role is not "entry_ramp" and not "entry_hatch_path")
            {
                AddSegmentEdgeProbes(edges, name, ReadVector3(surface, "start"), ReadVector3(surface, "end"), ReadFloat(surface, "width", 1.0f));
            }
            else if (type == "stair_path" && surface.TryGetValue("points", out var pointsValue) && pointsValue.VariantType == Variant.Type.Array)
            {
                var points = pointsValue.AsGodotArray();
                for (var index = 0; index < points.Count - 1; index++)
                {
                    if (points[index].VariantType == Variant.Type.Array && points[index + 1].VariantType == Variant.Type.Array)
                    {
                        AddSegmentEdgeProbes(edges, $"{name}_{index:00}", Vector3FromArray(points[index].AsGodotArray()), Vector3FromArray(points[index + 1].AsGodotArray()), ReadFloat(surface, "width", 1.0f));
                    }
                }
            }
        }
        return edges;
    }

    private static void AddSegmentEdgeProbes(System.Collections.Generic.List<RuntimeEdgeProbe> edges, string name, Vector3 start, Vector3 end, float width)
    {
        var horizontal = new Vector3(end.X - start.X, 0.0f, end.Z - start.Z);
        if (horizontal.LengthSquared() <= 0.0001f)
        {
            return;
        }

        var forward = horizontal.Normalized();
        var right = Vector3.Up.Cross(forward).Normalized();
        edges.Add(new RuntimeEdgeProbe(name, "left_guard", start - right * width * 0.5f, end - right * width * 0.5f, -right));
        edges.Add(new RuntimeEdgeProbe(name, "right_guard", start + right * width * 0.5f, end + right * width * 0.5f, right));
    }

    private bool IsApprovedOpening(RuntimeEdgeProbe edge, Vector3 point)
    {
        if (edge.EdgeName is not "port" and not "starboard")
        {
            return false;
        }

        foreach (var opening in _approvedOpenings)
        {
            if (opening.Side != edge.EdgeName)
            {
                continue;
            }
            if (Mathf.Abs(point.Z - opening.CenterZ) <= opening.WidthZ * 0.5f + 0.2f
                && Mathf.Abs(point.Y - opening.CenterY) <= opening.HeightY * 0.5f + 0.7f)
            {
                return true;
            }
        }
        return false;
    }

    private static bool IsInternalCockpitStairwellOpening(RuntimeEdgeProbe edge, Vector3 point)
    {
        if (!edge.SurfaceName.StartsWith("cockpit_"))
        {
            return false;
        }
        return point.X >= -4.25f
            && point.X <= 4.25f
            && point.Z >= 59.3f
            && point.Z <= 68.6f
            && point.Y >= -9.4f
            && point.Y <= 0.6f;
    }

    private bool HasRuntimeSupport(Vector3 local)
    {
        var world = ShipOrigin + local;
        var query = PhysicsRayQueryParameters3D.Create(world + Vector3.Up * 1.6f, world + Vector3.Down * 2.2f, WalkableSupportCollisionLayer);
        query.CollideWithAreas = false;
        query.CollideWithBodies = true;
        return GetWorld3D().DirectSpaceState.IntersectRay(query).Count > 0;
    }

    private bool HasRuntimeSolidBarrier(Vector3 insideLocal, Vector3 outsideLocal)
    {
        foreach (var height in new[] { 0.35f, 0.95f, 1.55f })
        {
            var query = PhysicsRayQueryParameters3D.Create(
                ShipOrigin + insideLocal + Vector3.Up * height,
                ShipOrigin + outsideLocal + Vector3.Up * height,
                SolidCollisionLayer);
            query.CollideWithAreas = false;
            query.CollideWithBodies = true;
            if (GetWorld3D().DirectSpaceState.IntersectRay(query).Count > 0)
            {
                return true;
            }
        }
        return false;
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
        Input.ActionRelease("jump");
        Input.ActionRelease("jetpack");
        Input.ActionRelease("brake");
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

    private static string ReadString(GDict source, string key, string fallback)
    {
        return source.TryGetValue(key, out var value) ? value.AsString() : fallback;
    }

    private static Vector3 ReadVector3(GDict source, string key)
    {
        if (!source.TryGetValue(key, out var value) || value.VariantType != Variant.Type.Array)
            return Vector3.Zero;

        return Vector3FromArray(value.AsGodotArray());
    }

    private static Vector3 ReadVector3Array(GDict source, string key)
    {
        if (!source.TryGetValue(key, out var value) || value.VariantType != Variant.Type.Array)
            return Vector3.Zero;

        var array = value.AsGodotArray();
        return Vector3FromArray(array);
    }

    private static Vector3 Vector3FromArray(GArray array)
    {
        if (array.Count < 3)
            return Vector3.Zero;

        return new Vector3((float)array[0], (float)array[1], (float)array[2]);
    }

    private readonly record struct RoutePoint(string Name, Vector3 LocalOrigin);
    private readonly record struct ShoveProbe(string Name, Vector3 LocalOrigin, Vector3 Direction, bool JumpPulse);
    private readonly record struct RuntimeEdgeProbe(string SurfaceName, string EdgeName, Vector3 Start, Vector3 End, Vector3 Normal);
    private readonly record struct HatchOpening(string Side, float CenterY, float HeightY, float CenterZ, float WidthZ);
}
