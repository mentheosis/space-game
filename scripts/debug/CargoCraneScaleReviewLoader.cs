using Godot;
using GDict = Godot.Collections.Dictionary<string, Godot.Variant>;

public partial class CargoCraneScaleReviewLoader : Node3D
{
    private const uint SolidCollisionLayer = 1u;
    private const uint WalkableSupportCollisionLayer = 1u << 7;

    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public string ExteriorScenePath { get; set; } = "res://assets/models/ship/cargo_crane/cargo_crane_exterior.glb";
    [Export] public string LayoutContractPath { get; set; } = "res://assets/source/blender/ships/cargo_crane/cargo_crane_interior_layout_contract.json";
    [Export] public string TraversalSurfacesPath { get; set; } = "res://assets/models/ship/cargo_crane/cargo_crane_traversal_surfaces.json";
    [Export] public string ObjectiveWalkableSurfacesPath { get; set; } = "res://assets/models/ship/cargo_crane/cargo_crane_objective_walkable_surfaces.json";
    [Export] public string EnclosureBandsPath { get; set; } = "res://assets/models/ship/cargo_crane/cargo_crane_enclosure_bands.json";
    [Export] public string RoomPartitionBandsPath { get; set; } = "res://assets/models/ship/cargo_crane/cargo_crane_room_partition_bands.json";
    [Export] public Vector3 ShipPosition { get; set; } = new(0.0f, 214.06f, 0.0f);
    [Export] public Vector3 PlayerSpawnPosition { get; set; } = new(0.0f, 210.07f, -55.0f);
    [Export] public Key GhostToggleKey { get; set; } = Key.G;
    [Export] public Key ReferenceToggleKey { get; set; } = Key.R;
    [Export] public Key SemanticToggleKey { get; set; } = Key.B;
    [Export] public Key TraversalToggleKey { get; set; } = Key.T;
    [Export] public Key EnclosureToggleKey { get; set; } = Key.E;
    [Export] public Key RoomPartitionToggleKey { get; set; } = Key.P;
    [Export] public Key CollisionSurfaceToggleKey { get; set; } = Key.V;
    [Export] public bool EnclosureCollisionEnabled { get; set; } = true;
    [Export] public bool RoomPartitionCollisionEnabled { get; set; } = false;
    [Export] public bool ShowScaleReferences { get; set; } = false;
    [Export] public bool ShowSemanticContractBoxes { get; set; } = false;
    [Export] public bool ShowTraversalSurfaceVisuals { get; set; } = true;
    [Export] public bool ShowEnclosureBandVisuals { get; set; } = true;
    [Export] public bool ShowRoomPartitionWallVisuals { get; set; } = false;
    [Export] public bool ShowReviewPad { get; set; } = false;
    [Export] public bool AddInteriorReviewLighting { get; set; } = true;

    private Node3D? _shipRoot;
    private Node3D? _referenceRoot;
    private Node3D? _semanticRoot;
    private Node3D? _traversalVisualRoot;
    private Node3D? _enclosureVisualRoot;
    private Node3D? _roomPartitionVisualRoot;
    private StandardMaterial3D? _ghostMaterial;
    private bool _ghostEnabled = true;

    public override void _Ready()
    {
        _ghostMaterial = CreateExteriorSkinMaterial(new Color(0.46f, 0.62f, 0.76f, 1.0f));

        _shipRoot = new Node3D
        {
            Name = "CargoCraneScaleReviewRoot",
            Position = ShipPosition
        };
        AddChild(_shipRoot);

        LoadGhostSkin(_shipRoot);
        if (ShowScaleReferences)
        {
            AddScaleReferences(_shipRoot);
        }
        if (ShowSemanticContractBoxes)
        {
            AddSemanticContractBoxes(_shipRoot);
        }
        AddTraversalSurfaces(_shipRoot);
        AddEnclosureBands(_shipRoot);
        if (ShowRoomPartitionWallVisuals)
        {
            AddRoomPartitionBands(_shipRoot);
        }
        if (AddInteriorReviewLighting)
        {
            AddInteriorReviewLights(_shipRoot);
        }
        if (ShowReviewPad)
        {
            AddReviewPad();
        }
        MovePlayerToSpawn();

        GD.Print("CargoCrane interior review loaded.");
        GD.Print("Controls: walk normally; G toggles ship skin; R toggles scale references if loaded; B toggles semantic boxes if loaded; T toggles traversal/collision floor visuals; E toggles enclosure bands; V toggles all collision surface visuals.");
        GD.Print("Candidate: 52.04m wide x 28.12m tall x 149.62m long, source +Z forward/cockpit end.");
        GD.Print("Review color key: blue shell=opaque ship skin, gold=opaque walkable collision floors, orange=opaque ramps/stairs, blue wall bands=opaque enclosure collision.");
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (@event is not InputEventKey keyEvent || !keyEvent.Pressed || keyEvent.Echo)
        {
            return;
        }

        if (keyEvent.Keycode == GhostToggleKey && _shipRoot is not null)
        {
            _ghostEnabled = !_ghostEnabled;
            SetMeshVisibility(_shipRoot, _ghostEnabled);
            GD.Print($"CargoCrane ghost skin: {(_ghostEnabled ? "visible" : "hidden")}");
            GetViewport().SetInputAsHandled();
        }
        else if (keyEvent.Keycode == ReferenceToggleKey && _referenceRoot is not null)
        {
            _referenceRoot.Visible = !_referenceRoot.Visible;
            GD.Print($"CargoCrane scale references: {(_referenceRoot.Visible ? "visible" : "hidden")}");
            GetViewport().SetInputAsHandled();
        }
        else if (keyEvent.Keycode == SemanticToggleKey && _semanticRoot is not null)
        {
            _semanticRoot.Visible = !_semanticRoot.Visible;
            GD.Print($"CargoCrane semantic boxes: {(_semanticRoot.Visible ? "visible" : "hidden")}");
            GetViewport().SetInputAsHandled();
        }
        else if (keyEvent.Keycode == TraversalToggleKey && _traversalVisualRoot is not null)
        {
            _traversalVisualRoot.Visible = !_traversalVisualRoot.Visible;
            GD.Print($"CargoCrane traversal surface visuals: {(_traversalVisualRoot.Visible ? "visible" : "hidden")}");
            GetViewport().SetInputAsHandled();
        }
        else if (keyEvent.Keycode == EnclosureToggleKey && _enclosureVisualRoot is not null)
        {
            _enclosureVisualRoot.Visible = !_enclosureVisualRoot.Visible;
            GD.Print($"CargoCrane enclosure bands: {(_enclosureVisualRoot.Visible ? "visible" : "hidden")}");
            GetViewport().SetInputAsHandled();
        }
        else if (keyEvent.Keycode == RoomPartitionToggleKey && _roomPartitionVisualRoot is not null)
        {
            _roomPartitionVisualRoot.Visible = !_roomPartitionVisualRoot.Visible;
            GD.Print($"CargoCrane room partition walls: {(_roomPartitionVisualRoot.Visible ? "visible" : "hidden")}");
            GetViewport().SetInputAsHandled();
        }
        else if (keyEvent.Keycode == CollisionSurfaceToggleKey)
        {
            var visible = !AnyCollisionSurfaceVisualsVisible();
            SetCollisionSurfaceVisualsVisible(visible);
            GD.Print($"CargoCrane collision surface visuals: {(visible ? "visible" : "hidden")}");
            GetViewport().SetInputAsHandled();
        }
    }

    private void LoadGhostSkin(Node3D parent)
    {
        var packed = ResourceLoader.Load<PackedScene>(ExteriorScenePath);
        if (packed is null)
        {
            GD.PushError($"Could not load CargoCrane exterior scene: {ExteriorScenePath}");
            return;
        }

        var exterior = packed.Instantiate<Node3D>();
        exterior.Name = "GhostExteriorSkin";
        parent.AddChild(exterior);
        ApplyGhostMaterial(exterior);
    }

    private void AddScaleReferences(Node3D shipRoot)
    {
        _referenceRoot = new Node3D { Name = "ScaleReferences" };
        shipRoot.AddChild(_referenceRoot);

        var playerMaterial = CreateMaterial(new Color(0.05f, 0.75f, 1.0f, 0.62f), transparent: true);
        var cockpitMaterial = CreateMaterial(new Color(1.0f, 0.85f, 0.1f, 0.86f), transparent: false);
        var entryMaterial = CreateMaterial(new Color(1.0f, 0.38f, 0.08f, 0.72f), transparent: true);
        var rulerMaterial = CreateMaterial(new Color(0.1f, 1.0f, 0.35f, 0.85f), transparent: false);
        var envelopeMaterial = CreateMaterial(new Color(0.9f, 0.9f, 1.0f, 0.18f), transparent: true);

        AddCapsule(_referenceRoot, "StandingPlayerSideReference", new Vector3(-30.0f, -13.16f, -28.0f), playerMaterial);
        AddCapsule(_referenceRoot, "StandingPlayerCargoReference", new Vector3(0.0f, -13.16f, -18.0f), playerMaterial);
        AddCapsule(_referenceRoot, "CockpitCrewLeftReference", new Vector3(-1.2f, -4.4f, 65.0f), playerMaterial);
        AddCapsule(_referenceRoot, "CockpitCrewRightReference", new Vector3(1.2f, -4.4f, 65.0f), playerMaterial);
        AddBox(_referenceRoot, "CockpitForwardMarker", new Vector3(0.0f, -5.0f, 75.0f), new Vector3(8.0f, 0.24f, 0.24f), cockpitMaterial, withCollision: false);
        AddBox(_referenceRoot, "CandidateBellyEntryMarker", new Vector3(0.0f, -13.2f, -34.0f), new Vector3(4.2f, 2.4f, 0.32f), entryMaterial, withCollision: false);
        AddBox(_referenceRoot, "InteriorEnvelopeThoughtStarter", new Vector3(0.0f, -7.8f, -5.0f), new Vector3(16.0f, 8.0f, 72.0f), envelopeMaterial, withCollision: false);

        for (var meter = 0; meter <= 50; meter += 5)
        {
            AddBox(
                _referenceRoot,
                $"FiftyMeterRulerTick{meter:00}",
                new Vector3(-25.0f + meter, -14.02f, -82.0f),
                new Vector3(meter == 0 || meter == 50 ? 0.32f : 0.16f, 0.42f, 0.24f),
                rulerMaterial,
                withCollision: false);
        }
        AddBox(_referenceRoot, "FiftyMeterRulerRail", new Vector3(0.0f, -14.11f, -82.0f), new Vector3(50.0f, 0.12f, 0.12f), rulerMaterial, withCollision: false);
    }

    private void AddSemanticContractBoxes(Node3D shipRoot)
    {
        _semanticRoot = new Node3D { Name = "SemanticContractBoxes" };
        shipRoot.AddChild(_semanticRoot);

        if (!Godot.FileAccess.FileExists(LayoutContractPath))
        {
            GD.PushWarning($"CargoCrane layout contract not found: {LayoutContractPath}");
            return;
        }

        var parsed = Json.ParseString(Godot.FileAccess.GetFileAsString(LayoutContractPath));
        if (parsed.VariantType != Variant.Type.Dictionary)
        {
            GD.PushWarning($"CargoCrane layout contract is not an object: {LayoutContractPath}");
            return;
        }

        var contract = parsed.AsGodotDictionary<string, Variant>();
        AddSemanticRegions(contract);
        AddEntranceCutBoxes(contract);
    }

    private void AddSemanticRegions(GDict contract)
    {
        if (_semanticRoot is null
            || !contract.TryGetValue("semantic_regions", out var regionsValue)
            || regionsValue.VariantType != Variant.Type.Array)
        {
            return;
        }

        foreach (var item in regionsValue.AsGodotArray())
        {
            if (item.VariantType != Variant.Type.Dictionary)
            {
                continue;
            }

            var region = item.AsGodotDictionary<string, Variant>();
            var id = ReadString(region, "id", "semantic_region");
            if (!region.TryGetValue("bounds", out var boundsValue) || boundsValue.VariantType != Variant.Type.Dictionary)
            {
                continue;
            }

            var bounds = boundsValue.AsGodotDictionary<string, Variant>();
            var min = ReadVector3(bounds, "min");
            var max = ReadVector3(bounds, "max");
            var center = (min + max) * 0.5f;
            var size = new Vector3(Mathf.Abs(max.X - min.X), Mathf.Abs(max.Y - min.Y), Mathf.Abs(max.Z - min.Z));
            if (size.X <= 0.0f || size.Y <= 0.0f || size.Z <= 0.0f)
            {
                continue;
            }

            AddBox(_semanticRoot, $"Semantic_{id}", center, size, MaterialForSemanticRegion(id), withCollision: false);
        }
    }

    private void AddEntranceCutBoxes(GDict contract)
    {
        if (_semanticRoot is null
            || !contract.TryGetValue("entrance_hatches", out var entrancesValue)
            || entrancesValue.VariantType != Variant.Type.Array)
        {
            return;
        }

        var material = CreateMaterial(new Color(1.0f, 0.35f, 0.05f, 0.62f), transparent: true);
        foreach (var item in entrancesValue.AsGodotArray())
        {
            if (item.VariantType != Variant.Type.Dictionary)
            {
                continue;
            }

            var entrance = item.AsGodotDictionary<string, Variant>();
            var name = ReadString(entrance, "name", "EntranceCut");
            var center = ReadVector3(entrance, "cut_center");
            var size = ReadVector3(entrance, "cut_size");
            if (size.X <= 0.0f || size.Y <= 0.0f || size.Z <= 0.0f)
            {
                continue;
            }

            AddBox(_semanticRoot, $"Entrance_{name}", center, size, material, withCollision: false);
        }
    }

    private Material MaterialForSemanticRegion(string id)
    {
        var color = id switch
        {
            "lower_deck_corridor_spine" => new Color(0.1f, 0.65f, 1.0f, 0.38f),
            "medical" => new Color(1.0f, 0.15f, 0.25f, 0.38f),
            "living_quarters" => new Color(0.15f, 0.9f, 0.35f, 0.38f),
            "atrium_lower" => new Color(1.0f, 0.72f, 0.1f, 0.34f),
            "aft_to_central_transition" => new Color(0.0f, 1.0f, 0.95f, 0.34f),
            "engine_room" => new Color(0.8f, 0.25f, 1.0f, 0.38f),
            "mezzanine" => new Color(1.0f, 0.92f, 0.2f, 0.3f),
            "central_service_spine" => new Color(0.0f, 1.0f, 0.95f, 0.34f),
            "central_to_cockpit_transition" => new Color(0.0f, 1.0f, 0.95f, 0.34f),
            "cockpit_descent_transition" => new Color(0.0f, 1.0f, 0.95f, 0.34f),
            "cockpit_access" => new Color(0.35f, 0.45f, 1.0f, 0.38f),
            "cockpit" => new Color(0.95f, 0.95f, 1.0f, 0.42f),
            _ => new Color(0.75f, 0.75f, 0.75f, 0.32f)
        };
        return CreateMaterial(color, transparent: true);
    }

    private void AddReviewPad()
    {
        var padBody = new StaticBody3D
        {
            Name = "CargoCraneScaleReviewPad",
            Position = new Vector3(0.0f, 199.92f, -8.0f),
            CollisionLayer = 1,
            CollisionMask = 1
        };
        AddChild(padBody);

        var shape = new CollisionShape3D { Shape = new BoxShape3D { Size = new Vector3(120.0f, 0.2f, 230.0f) } };
        padBody.AddChild(shape);

        var mesh = new MeshInstance3D
        {
            Name = "VisibleScaleReviewPad",
            Mesh = new BoxMesh { Size = new Vector3(120.0f, 0.12f, 230.0f) },
            MaterialOverride = CreateMaterial(new Color(0.12f, 0.14f, 0.16f, 0.52f), transparent: true)
        };
        padBody.AddChild(mesh);
    }

    private void AddTraversalSurfaces(Node3D shipRoot)
    {
        var collisionRoot = new StaticBody3D
        {
            Name = "TraversalSurfaceCollision",
            CollisionLayer = WalkableSupportCollisionLayer,
            CollisionMask = 0
        };
        shipRoot.AddChild(collisionRoot);

        _traversalVisualRoot = new Node3D { Name = "TraversalSurfaceVisuals" };
        _traversalVisualRoot.Visible = ShowTraversalSurfaceVisuals;
        shipRoot.AddChild(_traversalVisualRoot);

        var surfacesPath = TraversalSurfacesPath;
        if (!Godot.FileAccess.FileExists(surfacesPath) && Godot.FileAccess.FileExists(ObjectiveWalkableSurfacesPath))
        {
            surfacesPath = ObjectiveWalkableSurfacesPath;
            GD.Print($"CargoCrane using objective walkable surfaces for review: {surfacesPath}");
        }

        if (!Godot.FileAccess.FileExists(surfacesPath))
        {
            GD.PushWarning($"CargoCrane traversal surfaces not found: {TraversalSurfacesPath}");
            return;
        }

        var parsed = Json.ParseString(Godot.FileAccess.GetFileAsString(surfacesPath));
        if (parsed.VariantType != Variant.Type.Dictionary)
        {
            GD.PushWarning($"CargoCrane traversal surfaces data is not an object: {surfacesPath}");
            return;
        }

        var root = parsed.AsGodotDictionary<string, Variant>();
        if (!root.TryGetValue("surfaces", out var surfacesValue) || surfacesValue.VariantType != Variant.Type.Array)
        {
            GD.PushWarning($"CargoCrane traversal surfaces data has no surfaces array: {surfacesPath}");
            return;
        }

        var floorMaterial = CreateMaterial(new Color(0.90f, 0.70f, 0.18f, 1.0f), transparent: false);
        var rampMaterial = CreateMaterial(new Color(1.0f, 0.46f, 0.12f, 1.0f), transparent: false);
        var stairMaterial = CreateMaterial(new Color(0.08f, 0.76f, 0.68f, 1.0f), transparent: false);

        foreach (var item in surfacesValue.AsGodotArray())
        {
            if (item.VariantType != Variant.Type.Dictionary)
            {
                continue;
            }

            var surface = item.AsGodotDictionary<string, Variant>();
            var name = ReadString(surface, "name", "TraversalSurface");
            var type = ReadString(surface, "type", "");
            if (type == "floor_box" || type == "objective_floor_patch")
            {
                AddTraversalBox(collisionRoot, _traversalVisualRoot, name, ReadVector3(surface, "center"), ReadVector3(surface, "size"), floorMaterial);
            }
            else if (type == "ramp")
            {
                AddTraversalSegment(collisionRoot, _traversalVisualRoot, name, ReadVector3(surface, "start"), ReadVector3(surface, "end"), ReadFloat(surface, "width", 1.0f), ReadFloat(surface, "thickness", 0.22f), rampMaterial);
            }
            else if (type == "stair_path")
            {
                if (!surface.TryGetValue("points", out var pointsValue) || pointsValue.VariantType != Variant.Type.Array)
                {
                    continue;
                }

                var points = pointsValue.AsGodotArray();
                for (var index = 0; index < points.Count - 1; index++)
                {
                    if (points[index].VariantType != Variant.Type.Array || points[index + 1].VariantType != Variant.Type.Array)
                    {
                        continue;
                    }

                    AddTraversalSegment(
                        collisionRoot,
                        _traversalVisualRoot,
                        $"{name}_{index:00}",
                        Vector3FromArray(points[index].AsGodotArray()),
                        Vector3FromArray(points[index + 1].AsGodotArray()),
                        ReadFloat(surface, "width", 1.0f),
                        ReadFloat(surface, "thickness", 0.22f),
                        stairMaterial);
                }
            }
        }
    }

    private void AddEnclosureBands(Node3D shipRoot)
    {
        StaticBody3D? collisionRoot = null;
        if (EnclosureCollisionEnabled)
        {
            collisionRoot = new StaticBody3D
            {
                Name = "EnclosureBandCollision",
                CollisionLayer = SolidCollisionLayer,
                CollisionMask = SolidCollisionLayer
            };
            shipRoot.AddChild(collisionRoot);
        }

        _enclosureVisualRoot = new Node3D { Name = "EnclosureBandVisuals" };
        _enclosureVisualRoot.Visible = ShowEnclosureBandVisuals;
        shipRoot.AddChild(_enclosureVisualRoot);

        if (!Godot.FileAccess.FileExists(EnclosureBandsPath))
        {
            GD.PushWarning($"CargoCrane enclosure bands not found: {EnclosureBandsPath}");
            return;
        }

        var parsed = Json.ParseString(Godot.FileAccess.GetFileAsString(EnclosureBandsPath));
        if (parsed.VariantType != Variant.Type.Dictionary)
        {
            GD.PushWarning($"CargoCrane enclosure bands data is not an object: {EnclosureBandsPath}");
            return;
        }

        var root = parsed.AsGodotDictionary<string, Variant>();
        if (!root.TryGetValue("bands", out var bandsValue) || bandsValue.VariantType != Variant.Type.Array)
        {
            GD.PushWarning($"CargoCrane enclosure bands data has no bands array: {EnclosureBandsPath}");
            return;
        }

        var sideWallMaterial = CreateMaterial(new Color(0.22f, 0.48f, 0.84f, 1.0f), transparent: false);
        var ceilingMaterial = CreateMaterial(new Color(0.46f, 0.58f, 0.82f, 1.0f), transparent: false);

        foreach (var item in bandsValue.AsGodotArray())
        {
            if (item.VariantType != Variant.Type.Dictionary)
            {
                continue;
            }

            var band = item.AsGodotDictionary<string, Variant>();
            var name = ReadString(band, "name", "EnclosureBand");
            var type = ReadString(band, "type", "side_wall");
            var center = ReadVector3(band, "center");
            var size = ReadVector3(band, "size");
            var rotationDegrees = ReadOptionalVector3(band, "rotation_degrees");
            if (size.X <= 0.0f || size.Y <= 0.0f || size.Z <= 0.0f)
            {
                continue;
            }

            if (collisionRoot is not null)
            {
                collisionRoot.AddChild(new CollisionShape3D
                {
                    Name = $"{name}Collision",
                    Position = center,
                    RotationDegrees = rotationDegrees,
                    Shape = new BoxShape3D { Size = size }
                });
            }

            AddBox(_enclosureVisualRoot, $"Enclosure_{name}", center, size, type == "ceiling" ? ceilingMaterial : sideWallMaterial, withCollision: false, rotationDegrees);
        }
    }

    private void AddRoomPartitionBands(Node3D shipRoot)
    {
        StaticBody3D? collisionRoot = null;
        if (RoomPartitionCollisionEnabled)
        {
            collisionRoot = new StaticBody3D
            {
                Name = "RoomPartitionCollision",
                CollisionLayer = SolidCollisionLayer,
                CollisionMask = SolidCollisionLayer
            };
            shipRoot.AddChild(collisionRoot);
        }

        _roomPartitionVisualRoot = new Node3D { Name = "RoomPartitionWallVisuals" };
        _roomPartitionVisualRoot.Visible = ShowRoomPartitionWallVisuals;
        shipRoot.AddChild(_roomPartitionVisualRoot);

        if (!Godot.FileAccess.FileExists(RoomPartitionBandsPath))
        {
            GD.PushWarning($"CargoCrane room partition bands not found: {RoomPartitionBandsPath}");
            return;
        }

        var parsed = Json.ParseString(Godot.FileAccess.GetFileAsString(RoomPartitionBandsPath));
        if (parsed.VariantType != Variant.Type.Dictionary)
        {
            GD.PushWarning($"CargoCrane room partition bands data is not an object: {RoomPartitionBandsPath}");
            return;
        }

        var root = parsed.AsGodotDictionary<string, Variant>();
        if (!root.TryGetValue("bands", out var bandsValue) || bandsValue.VariantType != Variant.Type.Array)
        {
            GD.PushWarning($"CargoCrane room partition bands data has no bands array: {RoomPartitionBandsPath}");
            return;
        }

        var partitionMaterial = CreateMaterial(new Color(0.96f, 0.96f, 0.90f, 0.86f), transparent: true);
        foreach (var item in bandsValue.AsGodotArray())
        {
            if (item.VariantType != Variant.Type.Dictionary)
            {
                continue;
            }

            var band = item.AsGodotDictionary<string, Variant>();
            var name = ReadString(band, "name", "RoomPartitionBand");
            var center = ReadVector3(band, "center");
            var size = ReadVector3(band, "size");
            if (size.X <= 0.0f || size.Y <= 0.0f || size.Z <= 0.0f)
            {
                continue;
            }

            if (collisionRoot is not null)
            {
                collisionRoot.AddChild(new CollisionShape3D
                {
                    Name = $"{name}Collision",
                    Position = center,
                    Shape = new BoxShape3D { Size = size }
                });
            }

            AddBox(_roomPartitionVisualRoot, $"RoomPartition_{name}", center, size, partitionMaterial, withCollision: false);
        }
    }

    private static void AddTraversalBox(Node collisionRoot, Node3D visualRoot, string name, Vector3 center, Vector3 size, Material material)
    {
        if (size.X <= 0.0f || size.Y <= 0.0f || size.Z <= 0.0f)
        {
            return;
        }

        var body = new StaticBody3D
        {
            Name = $"{name}Collision",
            Position = center,
            CollisionLayer = WalkableSupportCollisionLayer,
            CollisionMask = 0
        };
        collisionRoot.AddChild(body);
        body.AddChild(new CollisionShape3D { Shape = new BoxShape3D { Size = size } });

        var mesh = new MeshInstance3D
        {
            Name = name,
            Position = center,
            Mesh = new BoxMesh { Size = size },
            MaterialOverride = material
        };
        ConfigureAlwaysVisible(mesh);
        visualRoot.AddChild(mesh);
    }

    private static void AddTraversalSegment(Node collisionRoot, Node3D visualRoot, string name, Vector3 start, Vector3 end, float width, float thickness, Material material)
    {
        var delta = end - start;
        var length = delta.Length();
        if (length <= 0.01f)
        {
            return;
        }

        var forward = delta / length;
        var right = Vector3.Up.Cross(forward);
        if (right.Length() <= 0.01f)
        {
            right = Vector3.Right;
        }
        right = right.Normalized();
        var up = forward.Cross(right).Normalized();
        var basis = new Basis(right, up, forward).Orthonormalized();
        var center = (start + end) * 0.5f;
        var size = new Vector3(width, thickness, length);

        var body = new StaticBody3D
        {
            Name = $"{name}Collision",
            Transform = new Transform3D(basis, center),
            CollisionLayer = WalkableSupportCollisionLayer,
            CollisionMask = 0
        };
        collisionRoot.AddChild(body);
        body.AddChild(new CollisionShape3D { Shape = new BoxShape3D { Size = size } });

        var mesh = new MeshInstance3D
        {
            Name = name,
            Transform = new Transform3D(basis, center),
            Mesh = new BoxMesh { Size = size },
            MaterialOverride = material
        };
        ConfigureAlwaysVisible(mesh);
        visualRoot.AddChild(mesh);
    }

    private void MovePlayerToSpawn()
    {
        if (GetNodeOrNull<Node3D>(PlayerPath) is not { } player)
        {
            GD.PushWarning($"CargoCrane scale review could not find player at {PlayerPath}");
            return;
        }

        var basis = Basis.Identity.Rotated(Vector3.Up, Mathf.Pi);
        player.GlobalTransform = new Transform3D(basis, PlayerSpawnPosition);
        if (player is CharacterBody3D body)
        {
            body.Velocity = Vector3.Zero;
        }
    }

    private static void AddInteriorReviewLights(Node3D shipRoot)
    {
        AddReviewLight(shipRoot, "EngineRoomReviewLight", new Vector3(0.0f, 5.0f, -48.0f), 7.0f, 24.0f, new Color(1.0f, 0.78f, 0.56f));
        AddReviewLight(shipRoot, "AtriumReviewLight", new Vector3(0.0f, 5.8f, -20.0f), 8.0f, 30.0f, new Color(1.0f, 0.86f, 0.64f));
        AddReviewLight(shipRoot, "MainBodyReviewLightAft", new Vector3(0.0f, 5.4f, -2.0f), 6.5f, 30.0f, new Color(0.86f, 0.94f, 1.0f));
        AddReviewLight(shipRoot, "MainBodyReviewLightForward", new Vector3(0.0f, 5.4f, 21.0f), 6.5f, 30.0f, new Color(0.86f, 0.94f, 1.0f));
        AddReviewLight(shipRoot, "CockpitReviewLight", new Vector3(0.0f, 3.0f, 55.0f), 7.0f, 28.0f, new Color(0.82f, 0.90f, 1.0f));
        AddReviewLight(shipRoot, "LowerCockpitReviewLight", new Vector3(0.0f, -3.2f, 65.0f), 5.0f, 18.0f, new Color(0.82f, 0.90f, 1.0f));
    }

    private static void AddReviewLight(Node3D parent, string name, Vector3 position, float energy, float range, Color color)
    {
        parent.AddChild(new OmniLight3D
        {
            Name = name,
            Position = position,
            LightColor = color,
            LightEnergy = energy,
            OmniRange = range,
            ShadowEnabled = false
        });
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

    private static Vector3 ReadOptionalVector3(GDict source, string key)
    {
        return source.TryGetValue(key, out var value) && value.VariantType == Variant.Type.Array
            ? Vector3FromArray(value.AsGodotArray())
            : Vector3.Zero;
    }

    private static float ReadFloat(GDict source, string key, float fallback)
    {
        return source.TryGetValue(key, out var value) ? (float)value.AsDouble() : fallback;
    }

    private static Vector3 Vector3FromArray(Godot.Collections.Array array)
    {
        if (array.Count < 3)
        {
            return Vector3.Zero;
        }

        return new Vector3((float)array[0], (float)array[1], (float)array[2]);
    }

    private void ApplyGhostMaterial(Node node)
    {
        if (node is MeshInstance3D mesh && _ghostMaterial is not null)
        {
            mesh.MaterialOverride = _ghostMaterial;
            mesh.CastShadow = GeometryInstance3D.ShadowCastingSetting.Off;
            ConfigureAlwaysVisible(mesh);
        }

        foreach (var child in node.GetChildren())
        {
            ApplyGhostMaterial(child);
        }
    }

    private static void SetMeshVisibility(Node node, bool visible)
    {
        if (node is MeshInstance3D mesh)
        {
            mesh.Visible = visible;
        }

        foreach (var child in node.GetChildren())
        {
            SetMeshVisibility(child, visible);
        }
    }

    private bool AnyCollisionSurfaceVisualsVisible()
    {
        return (_traversalVisualRoot?.Visible ?? false)
            || (_enclosureVisualRoot?.Visible ?? false)
            || (_roomPartitionVisualRoot?.Visible ?? false);
    }

    private void SetCollisionSurfaceVisualsVisible(bool visible)
    {
        if (_traversalVisualRoot is not null)
        {
            _traversalVisualRoot.Visible = visible;
        }
        if (_enclosureVisualRoot is not null)
        {
            _enclosureVisualRoot.Visible = visible;
        }
        if (_roomPartitionVisualRoot is not null)
        {
            _roomPartitionVisualRoot.Visible = visible;
        }
    }

    private static void AddCapsule(Node parent, string name, Vector3 position, Material material)
    {
        var mesh = new MeshInstance3D
        {
            Name = name,
            Position = position,
            Mesh = new CapsuleMesh { Radius = 0.35f, Height = 1.8f },
            MaterialOverride = material
        };
        ConfigureAlwaysVisible(mesh);
        parent.AddChild(mesh);
    }

    private static void AddBox(Node parent, string name, Vector3 position, Vector3 size, Material material, bool withCollision, Vector3? rotationDegrees = null)
    {
        var mesh = new MeshInstance3D
        {
            Name = name,
            Position = position,
            RotationDegrees = rotationDegrees ?? Vector3.Zero,
            Mesh = new BoxMesh { Size = size },
            MaterialOverride = material
        };
        ConfigureAlwaysVisible(mesh);

        if (!withCollision)
        {
            parent.AddChild(mesh);
            return;
        }

        var body = new StaticBody3D
        {
            Name = $"{name}Body",
            Position = position,
            RotationDegrees = rotationDegrees ?? Vector3.Zero,
            CollisionLayer = 1,
            CollisionMask = 1
        };
        parent.AddChild(body);
        body.AddChild(new CollisionShape3D { Shape = new BoxShape3D { Size = size } });
        mesh.Position = Vector3.Zero;
        body.AddChild(mesh);
    }

    private static StandardMaterial3D CreateMaterial(Color color, bool transparent)
    {
        return new StandardMaterial3D
        {
            AlbedoColor = color,
            Transparency = transparent ? BaseMaterial3D.TransparencyEnum.Alpha : BaseMaterial3D.TransparencyEnum.Disabled,
            Roughness = 0.62f,
            Metallic = 0.0f,
            ShadingMode = BaseMaterial3D.ShadingModeEnum.PerPixel,
            CullMode = BaseMaterial3D.CullModeEnum.Disabled
        };
    }

    private static StandardMaterial3D CreateExteriorSkinMaterial(Color color)
    {
        return new StandardMaterial3D
        {
            AlbedoColor = color,
            Transparency = BaseMaterial3D.TransparencyEnum.Disabled,
            Roughness = 0.74f,
            Metallic = 0.0f,
            ShadingMode = BaseMaterial3D.ShadingModeEnum.PerPixel,
            CullMode = BaseMaterial3D.CullModeEnum.Back
        };
    }

    private static void ConfigureAlwaysVisible(GeometryInstance3D geometry)
    {
        geometry.VisibilityRangeBegin = 0.0f;
        geometry.VisibilityRangeEnd = 0.0f;
        geometry.VisibilityRangeFadeMode = GeometryInstance3D.VisibilityRangeFadeModeEnum.Disabled;
        geometry.ExtraCullMargin = 1000.0f;
        geometry.IgnoreOcclusionCulling = true;
    }
}
