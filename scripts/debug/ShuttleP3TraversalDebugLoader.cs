using Godot;
using GDict = Godot.Collections.Dictionary<string, Godot.Variant>;

public partial class ShuttleP3TraversalDebugLoader : Node3D
{
    private const uint SolidCollisionLayer = 1u;
    private const uint WalkableSupportCollisionLayer = 1u << 7;

    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public Vector3 ShuttlePosition { get; set; } = new(0.0f, 205.6f, 0.0f);
    [Export] public Vector3 PlayerSpawnPosition { get; set; } = new(0.0f, 201.15f, -8.0f);
    [Export] public string ExteriorScenePath { get; set; } = "res://assets/models/ship/shuttle_p3/shuttle_p3_exterior.glb";
    [Export] public string EnclosureBandsPath { get; set; } = "res://assets/models/ship/shuttle_p3/shuttle_p3_enclosure_bands.json";
    [Export] public Key CollisionVisualToggleKey { get; set; } = Key.V;

    private Node3D? _collisionVisualRoot;

    public override void _Ready()
    {
        var root = new Node3D
        {
            Name = "ShuttleP3TraversalBlockout",
            Position = ShuttlePosition
        };
        AddChild(root);

        LoadExterior(root);
        AddTraversalBlockout(root);
        MovePlayerToSpawn();
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (@event is not InputEventKey keyEvent
            || !keyEvent.Pressed
            || keyEvent.Echo
            || keyEvent.Keycode != CollisionVisualToggleKey
            || _collisionVisualRoot is null)
        {
            return;
        }

        _collisionVisualRoot.Visible = !_collisionVisualRoot.Visible;
        GD.Print($"Shuttle p3 traversal collision visuals: {(_collisionVisualRoot.Visible ? "visible" : "hidden")}");
        GetViewport().SetInputAsHandled();
    }

    private void LoadExterior(Node3D parent)
    {
        var packed = ResourceLoader.Load<PackedScene>(ExteriorScenePath);
        if (packed is null)
        {
            GD.PushError($"Could not load shuttle p3 exterior scene: {ExteriorScenePath}");
            return;
        }

        var exterior = packed.Instantiate<Node3D>();
        exterior.Name = "ExteriorSkin";
        parent.AddChild(exterior);
    }

    private void AddTraversalBlockout(Node3D parent)
    {
        var collisionRoot = new StaticBody3D
        {
            Name = "TraversalCollision",
            CollisionLayer = SolidCollisionLayer,
            CollisionMask = SolidCollisionLayer
        };
        parent.AddChild(collisionRoot);

        var supportRoot = new StaticBody3D
        {
            Name = "WalkableSupportSurfaces",
            CollisionLayer = WalkableSupportCollisionLayer,
            CollisionMask = 0
        };
        parent.AddChild(supportRoot);

        _collisionVisualRoot = new Node3D
        {
            Name = "TraversalCollisionVisual",
            Visible = false
        };
        parent.AddChild(_collisionVisualRoot);

        var floorMaterial = CreateMaterial(new Color(0.58f, 0.66f, 0.72f, 1.0f), metallic: 0.15f, roughness: 0.55f);
        var rampMaterial = CreateMaterial(new Color(0.68f, 0.55f, 0.34f, 1.0f), metallic: 0.1f, roughness: 0.5f);
        var stairMaterial = CreateMaterial(new Color(0.48f, 0.58f, 0.62f, 1.0f), metallic: 0.1f, roughness: 0.6f);
        var seatMaterial = CreateMaterial(new Color(0.1f, 0.12f, 0.15f, 1.0f), metallic: 0.0f, roughness: 0.75f);
        var railingMaterial = CreateMaterial(new Color(0.18f, 0.21f, 0.24f, 1.0f), metallic: 0.35f, roughness: 0.42f);
        var wallMaterial = CreateMaterial(new Color(0.34f, 0.39f, 0.42f, 1.0f), metallic: 0.18f, roughness: 0.62f);

        AddSlopedBox(supportRoot, _collisionVisualRoot, "EntryRamp", new Vector3(0.0f, -3.55f, -6.2f), new Vector3(0.0f, -2.15f, -1.15f), 2.75f, 0.18f, rampMaterial);
        AddBox(supportRoot, _collisionVisualRoot, "CargoFloor", new Vector3(0.0f, -2.24f, 3.15f), new Vector3(5.8f, 0.18f, 8.8f), floorMaterial);
        AddCurvedStairPath(
            supportRoot,
            _collisionVisualRoot,
            "CargoEdgeStairsLeft",
            new[]
            {
                new Vector3(-1.95f, -2.15f, -0.55f),
                new Vector3(-2.22f, -1.28f, -1.25f),
                new Vector3(-2.3f, -0.42f, -2.1f),
                new Vector3(-1.85f, 0.45f, -3.05f),
                new Vector3(-1.15f, 0.45f, -3.75f)
            },
            0.86f,
            10,
            stairMaterial);
        AddCurvedStairPath(
            supportRoot,
            _collisionVisualRoot,
            "CargoEdgeStairsRight",
            new[]
            {
                new Vector3(1.95f, -2.15f, -0.55f),
                new Vector3(2.22f, -1.28f, -1.25f),
                new Vector3(2.3f, -0.42f, -2.1f),
                new Vector3(1.85f, 0.45f, -3.05f),
                new Vector3(1.15f, 0.45f, -3.75f)
            },
            0.86f,
            10,
            stairMaterial);
        AddBox(supportRoot, _collisionVisualRoot, "CockpitHallMergeFloor", new Vector3(0.0f, 0.36f, -4.15f), new Vector3(3.25f, 0.18f, 1.45f), floorMaterial);
        AddBox(supportRoot, _collisionVisualRoot, "CockpitHallwayFloor", new Vector3(0.0f, 0.36f, -7.35f), new Vector3(3.25f, 0.18f, 5.35f), floorMaterial);
        AddLandingRailing(collisionRoot, _collisionVisualRoot, railingMaterial);
        AddCurvedStairInsideRailing(collisionRoot, _collisionVisualRoot, "Left", new[]
        {
            new Vector3(-1.95f, -2.15f, -0.55f),
            new Vector3(-2.22f, -1.28f, -1.25f),
            new Vector3(-2.3f, -0.42f, -2.1f),
            new Vector3(-1.85f, 0.45f, -3.05f),
            new Vector3(-1.15f, 0.45f, -3.75f),
        }, 0.46f, new Vector3(-0.68f, 0.45f, -3.34f), railingMaterial);
        AddCurvedStairInsideRailing(collisionRoot, _collisionVisualRoot, "Right", new[]
        {
            new Vector3(1.95f, -2.15f, -0.55f),
            new Vector3(2.22f, -1.28f, -1.25f),
            new Vector3(2.3f, -0.42f, -2.1f),
            new Vector3(1.85f, 0.45f, -3.05f),
            new Vector3(1.15f, 0.45f, -3.75f),
        }, -0.46f, new Vector3(0.68f, 0.45f, -3.34f), railingMaterial);
        AddBox(supportRoot, _collisionVisualRoot, "CockpitDeck", new Vector3(0.0f, 0.36f, -13.0f), new Vector3(3.5f, 0.18f, 6.6f), floorMaterial);
        AddSlopedBox(supportRoot, _collisionVisualRoot, "CockpitForwardFootwell", new Vector3(0.0f, 0.45f, -13.9f), new Vector3(0.0f, 0.02f, -16.5f), 2.35f, 0.14f, floorMaterial);
        AddSeat(collisionRoot, _collisionVisualRoot, "PilotSeatLeft", new Vector3(-0.68f, 0.92f, -14.05f), seatMaterial);
        AddSeat(collisionRoot, _collisionVisualRoot, "PilotSeatRight", new Vector3(0.68f, 0.92f, -14.05f), seatMaterial);
        AddGeneratedInteriorEnclosureBands(collisionRoot, _collisionVisualRoot, wallMaterial);
    }

    private void AddGeneratedInteriorEnclosureBands(Node collisionRoot, Node3D visualRoot, Material wallMaterial)
    {
        if (!Godot.FileAccess.FileExists(EnclosureBandsPath))
        {
            GD.PushError($"Missing shuttle p3 enclosure band data: {EnclosureBandsPath}");
            return;
        }

        var text = Godot.FileAccess.GetFileAsString(EnclosureBandsPath);
        var parsed = Json.ParseString(text);
        if (parsed.VariantType != Variant.Type.Dictionary)
        {
            GD.PushError($"Shuttle p3 enclosure band data is not an object: {EnclosureBandsPath}");
            return;
        }

        var root = parsed.AsGodotDictionary<string, Variant>();
        if (!root.TryGetValue("bands", out var bandsValue) || bandsValue.VariantType != Variant.Type.Array)
        {
            GD.PushError($"Shuttle p3 enclosure band data has no bands array: {EnclosureBandsPath}");
            return;
        }

        foreach (var item in bandsValue.AsGodotArray())
        {
            if (item.VariantType != Variant.Type.Dictionary)
            {
                continue;
            }

            var band = item.AsGodotDictionary<string, Variant>();
            var name = ReadString(band, "name", "GeneratedEnclosureBand");
            var center = ReadVector3(band, "center");
            var size = ReadVector3(band, "size");
            if (size.X <= 0.0f || size.Y <= 0.0f || size.Z <= 0.0f)
            {
                GD.PushWarning($"Skipping invalid shuttle p3 enclosure band size for {name}: {size}");
                continue;
            }

            AddBox(collisionRoot, visualRoot, name, center, size, wallMaterial);
        }
    }

    private static string ReadString(GDict source, string key, string fallback)
    {
        return source.TryGetValue(key, out var value) ? value.AsString() : fallback;
    }

    private static Vector3 ReadVector3(GDict source, string key)
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

    private static void AddSeat(Node collisionRoot, Node3D visualRoot, string name, Vector3 position, Material material)
    {
        AddBox(collisionRoot, visualRoot, $"{name}Base", position + new Vector3(0.0f, -0.22f, 0.08f), new Vector3(0.72f, 0.28f, 0.78f), material);
        AddBox(collisionRoot, visualRoot, $"{name}Back", position + new Vector3(0.0f, 0.25f, 0.36f), new Vector3(0.72f, 0.86f, 0.22f), material);
    }

    private static void AddLandingRailing(Node collisionRoot, Node3D visualRoot, Material material)
    {
        const float floorTopY = 0.45f;
        const float aftEdgeZ = -3.34f;
        AddBox(collisionRoot, visualRoot, "LandingAftCenterRailingTop", new Vector3(0.0f, floorTopY + 0.94f, aftEdgeZ), new Vector3(1.32f, 0.12f, 0.12f), material);
        AddBox(collisionRoot, visualRoot, "LandingAftCenterRailingMid", new Vector3(0.0f, floorTopY + 0.58f, aftEdgeZ), new Vector3(1.18f, 0.08f, 0.1f), material);
        AddBox(collisionRoot, visualRoot, "LandingAftCenterRailingPostLeft", new Vector3(-0.68f, floorTopY + 0.48f, aftEdgeZ), new Vector3(0.12f, 0.96f, 0.12f), material);
        AddBox(collisionRoot, visualRoot, "LandingAftCenterRailingPostRight", new Vector3(0.68f, floorTopY + 0.48f, aftEdgeZ), new Vector3(0.12f, 0.96f, 0.12f), material);
    }

    private static void AddCurvedStairInsideRailing(Node collisionRoot, Node3D visualRoot, string sideName, Vector3[] stairFloorPoints, float insideXOffset, Vector3 landingFloorPoint, Material material)
    {
        const float topRailHeight = 0.94f;
        const float midRailHeight = 0.58f;
        const float postHeight = 0.96f;
        const float railThickness = 0.1f;
        const float postThickness = 0.1f;

        var floorPoints = new Vector3[stairFloorPoints.Length + 1];
        for (var index = 0; index < stairFloorPoints.Length; index++)
        {
            floorPoints[index] = stairFloorPoints[index] + new Vector3(insideXOffset, 0.0f, 0.0f);
        }
        floorPoints[^1] = landingFloorPoint;

        for (var index = 0; index < floorPoints.Length; index++)
        {
            var floorPoint = floorPoints[index];
            AddBox(
                collisionRoot,
                visualRoot,
                $"StairInsideRailing{sideName}Post_{index:00}",
                floorPoint + new Vector3(0.0f, postHeight * 0.5f, 0.0f),
                new Vector3(postThickness, postHeight, postThickness),
                material);
        }

        for (var index = 0; index < floorPoints.Length - 1; index++)
        {
            AddRailSegment(collisionRoot, visualRoot, $"StairInsideRailing{sideName}Top_{index:00}", floorPoints[index] + new Vector3(0.0f, topRailHeight, 0.0f), floorPoints[index + 1] + new Vector3(0.0f, topRailHeight, 0.0f), railThickness, material);
            AddRailSegment(collisionRoot, visualRoot, $"StairInsideRailing{sideName}Mid_{index:00}", floorPoints[index] + new Vector3(0.0f, midRailHeight, 0.0f), floorPoints[index + 1] + new Vector3(0.0f, midRailHeight, 0.0f), railThickness * 0.8f, material);
        }
    }

    private static void AddRailSegment(Node collisionRoot, Node3D visualRoot, string name, Vector3 start, Vector3 end, float thickness, Material material)
    {
        var delta = end - start;
        var horizontalLength = new Vector2(delta.X, delta.Z).Length();
        var length = delta.Length();
        if (length <= 0.001f)
        {
            return;
        }

        var pitch = -Mathf.Atan2(delta.Y, horizontalLength);
        var yaw = Mathf.Atan2(delta.X, delta.Z);
        AddBox(collisionRoot, visualRoot, name, (start + end) * 0.5f, new Vector3(thickness, thickness, length), material, new Vector3(pitch, yaw, 0.0f));
    }

    private static void AddCurvedStairPath(Node collisionRoot, Node3D visualRoot, string name, Vector3[] points, float width, int stepCount, Material material)
    {
        if (points.Length < 2 || stepCount < 1)
        {
            return;
        }

        var segmentLengths = new float[points.Length - 1];
        var totalLength = 0.0f;
        for (var index = 0; index < points.Length - 1; index++)
        {
            var delta = points[index + 1] - points[index];
            segmentLengths[index] = new Vector2(delta.X, delta.Z).Length();
            totalLength += segmentLengths[index];
        }

        if (totalLength <= 0.001f)
        {
            return;
        }

        var stepDepth = totalLength / stepCount;
        for (var stepIndex = 0; stepIndex < stepCount; stepIndex++)
        {
            var topDistance = totalLength * ((stepIndex + 1.0f) / stepCount);
            var centerDistance = totalLength * ((stepIndex + 0.5f) / stepCount);
            var centerTop = SamplePath(points, segmentLengths, centerDistance);
            var topPoint = SamplePath(points, segmentLengths, topDistance);
            var forwardPoint = SamplePath(points, segmentLengths, Mathf.Min(totalLength, centerDistance + 0.05f));
            var backwardPoint = SamplePath(points, segmentLengths, Mathf.Max(0.0f, centerDistance - 0.05f));
            var tangent = forwardPoint - backwardPoint;
            var yaw = Mathf.Atan2(tangent.X, tangent.Z);
            centerTop.Y = topPoint.Y;

            var size = new Vector3(width, 0.16f, stepDepth + 0.04f);
            AddBox(collisionRoot, visualRoot, $"{name}_{stepIndex:00}", centerTop - new Vector3(0.0f, size.Y * 0.5f, 0.0f), size, material, new Vector3(0.0f, yaw, 0.0f));
        }
    }

    private static Vector3 SamplePath(Vector3[] points, float[] segmentLengths, float distance)
    {
        var remaining = distance;
        for (var index = 0; index < segmentLengths.Length; index++)
        {
            var length = segmentLengths[index];
            if (remaining <= length || index == segmentLengths.Length - 1)
            {
                var t = length <= 0.001f ? 0.0f : Mathf.Clamp(remaining / length, 0.0f, 1.0f);
                return points[index].Lerp(points[index + 1], t);
            }

            remaining -= length;
        }

        return points[^1];
    }

    private static void AddStairRun(Node collisionRoot, Node3D visualRoot, string name, Vector3 startTop, Vector3 endTop, float width, int stepCount, Material material)
    {
        var direction = endTop - startTop;
        var stepDepth = new Vector2(direction.X, direction.Z).Length() / stepCount;
        var yaw = Mathf.Atan2(direction.X, direction.Z);
        for (var index = 0; index < stepCount; index++)
        {
            var t0 = index / (float)stepCount;
            var t1 = (index + 1) / (float)stepCount;
            var centerTop = startTop.Lerp(endTop, (t0 + t1) * 0.5f);
            centerTop.Y = Mathf.Lerp(startTop.Y, endTop.Y, t1);
            var size = new Vector3(width, 0.16f, stepDepth + 0.05f);
            AddBox(collisionRoot, visualRoot, $"{name}_{index:00}", centerTop - new Vector3(0.0f, size.Y * 0.5f, 0.0f), size, material, new Vector3(0.0f, yaw, 0.0f));
        }
    }

    private static void AddSlopedBox(Node collisionRoot, Node3D visualRoot, string name, Vector3 startTop, Vector3 endTop, float width, float thickness, Material material)
    {
        var centerTop = (startTop + endTop) * 0.5f;
        var delta = endTop - startTop;
        var horizontalLength = new Vector2(delta.X, delta.Z).Length();
        var pitch = -Mathf.Atan2(delta.Y, horizontalLength);
        var yaw = Mathf.Atan2(delta.X, delta.Z);
        var length = Mathf.Sqrt(horizontalLength * horizontalLength + delta.Y * delta.Y);
        AddBox(collisionRoot, visualRoot, name, centerTop - new Vector3(0.0f, thickness * 0.5f, 0.0f), new Vector3(width, thickness, length), material, new Vector3(pitch, yaw, 0.0f));
    }

    private static void AddBox(Node collisionRoot, Node3D visualRoot, string name, Vector3 position, Vector3 size, Material material, Vector3? rotation = null)
    {
        var collisionShape = new CollisionShape3D
        {
            Name = $"{name}Collision",
            Position = position,
            Rotation = rotation ?? Vector3.Zero,
            Shape = new BoxShape3D { Size = size }
        };
        collisionRoot.AddChild(collisionShape);

        var visual = new MeshInstance3D
        {
            Name = name,
            Position = position,
            Rotation = rotation ?? Vector3.Zero,
            Mesh = new BoxMesh { Size = size },
            MaterialOverride = material
        };
        visualRoot.AddChild(visual);
    }

    private void MovePlayerToSpawn()
    {
        var player = GetNodeOrNull<PlayerController>(PlayerPath);
        if (player is null)
        {
            return;
        }

        player.GlobalPosition = PlayerSpawnPosition;
        player.Velocity = Vector3.Zero;
        player.SetPlayerContext(PlayerContext.OnFoot);
    }

    private static StandardMaterial3D CreateMaterial(Color color, float metallic, float roughness)
    {
        return new StandardMaterial3D
        {
            AlbedoColor = color,
            Metallic = metallic,
            Roughness = roughness
        };
    }
}
