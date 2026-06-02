using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;
using Godot;

public partial class PrototypeShuttleDebugLoader : Node3D
{
    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public Vector3 ShuttlePosition { get; set; } = new(0.0f, 58.0f, 0.0f);
    [Export] public Vector3 PlayerSpawnPosition { get; set; } = new(0.0f, 59.6f, 0.9f);
    [Export] public string ExteriorScenePath { get; set; } = "res://assets/models/ship/prototype_shuttle/prototype_shuttle_exterior.glb";
    [Export] public string InteriorScenePath { get; set; } = "res://assets/models/ship/prototype_shuttle/prototype_shuttle_interior.glb";
    [Export] public string CollisionScenePath { get; set; } = "res://assets/models/ship/prototype_shuttle/prototype_shuttle_collision.glb";
    [Export] public string ExteriorCollisionContractPath { get; set; } = "res://assets/source/blender/ships/prototype_shuttle/prototype_shuttle_exterior_collision_contract.json";
    [Export] public string InteriorCollisionContractPath { get; set; } = "res://assets/source/blender/ships/prototype_shuttle/prototype_shuttle_interior_collision_contract.json";
    [Export] public string CollisionLayoutReportPath { get; set; } = "res://assets/models/ship/prototype_shuttle/prototype_shuttle_collision_layout_report.json";
    [Export] public bool ShowInterior { get; set; } = true;
    [Export] public bool HideReviewOnlyInteriorNodes { get; set; } = true;
    [Export] public bool AddDebugTraversalCollision { get; set; } = true;
    [Export] public bool ShowCollisionVisualReference { get; set; } = false;
    [Export] public bool AddAuthoredInteriorLights { get; set; } = true;
    [Export] public bool EnableShipControls { get; set; } = true;
    [Export] public bool MovePlayerToSpawnOnReady { get; set; } = true;
    [Export] public Key CollisionVisualToggleKey { get; set; } = Key.V;

    private Node3D? _collisionVisual;
    private Node3D? _contractCollisionVisual;
    private Node3D? _interiorCollisionVisual;
    private ShipController? _ship;

    public override void _Ready()
    {
        var shuttleRoot = EnableShipControls
            ? CreatePlayableShipRoot()
            : new Node3D
            {
                Name = "PrototypeShuttleBlockout",
                Position = ShuttlePosition
            };

        var exterior = LoadPackagePart(ExteriorScenePath, "Exterior", shuttleRoot, visible: true, createCollision: false);
        if (exterior is not null)
        {
            ForceExteriorSkinOpaque(exterior);
        }

        var interior = LoadPackagePart(InteriorScenePath, "Interior", shuttleRoot, visible: ShowInterior, createCollision: false);
        if (interior is not null && HideReviewOnlyInteriorNodes)
        {
            HideReviewOnlyNodes(interior);
        }

        if (EnableShipControls && shuttleRoot is ShipController ship)
        {
            AddPlayableShipNodes(ship);
        }

        if (AddAuthoredInteriorLights)
        {
            PrototypeShuttleLightingRig.AddInteriorPracticalLights(shuttleRoot);
        }

        _collisionVisual = LoadPackagePart(CollisionScenePath, "Collision", shuttleRoot, visible: ShowCollisionVisualReference, createCollision: AddDebugTraversalCollision);
        if (_collisionVisual is not null)
        {
            ApplyCollisionVisualMaterial(_collisionVisual);
        }

        AddChild(shuttleRoot);

        var collisionExceptionPlayer = GetNodeOrNull<PlayerController>(PlayerPath);
        if (_ship is not null && collisionExceptionPlayer is not null)
        {
            _ship.AddCollisionExceptionWith(collisionExceptionPlayer);
            collisionExceptionPlayer.AddCollisionExceptionWith(_ship);
        }

        var player = MovePlayerToSpawnOnReady ? GetNodeOrNull<PlayerController>(PlayerPath) : null;
        if (player is not null)
        {
            player.GlobalPosition = PlayerSpawnPosition;
            player.Velocity = Vector3.Zero;
            player.SetPlayerContext(PlayerContext.OnFoot);
        }
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (@event is not InputEventKey keyEvent
            || !keyEvent.Pressed
            || keyEvent.Echo
            || keyEvent.Keycode != CollisionVisualToggleKey
            || (_collisionVisual is null && _contractCollisionVisual is null && _interiorCollisionVisual is null))
        {
            return;
        }

        var nextVisible = !((_collisionVisual?.Visible ?? false)
            || (_contractCollisionVisual?.Visible ?? false)
            || (_interiorCollisionVisual?.Visible ?? false));
        if (_collisionVisual is not null)
        {
            _collisionVisual.Visible = nextVisible;
        }

        if (_contractCollisionVisual is not null)
        {
            _contractCollisionVisual.Visible = nextVisible;
        }

        if (_interiorCollisionVisual is not null)
        {
            _interiorCollisionVisual.Visible = nextVisible;
        }

        GD.Print($"Prototype shuttle collision visuals: {(nextVisible ? "visible" : "hidden")}");
        GetViewport().SetInputAsHandled();
    }

    private Node3D? LoadPackagePart(string path, string name, Node parent, bool visible, bool createCollision)
    {
        var packed = ResourceLoader.Load<PackedScene>(path);
        if (packed is null)
        {
            GD.PushError($"Could not load prototype shuttle package scene: {path}");
            return null;
        }

        var instance = packed.Instantiate<Node3D>();
        instance.Name = name;
        instance.Visible = visible;
        parent.AddChild(instance);

        if (createCollision)
        {
            CreateTrimeshCollision(instance);
        }

        return instance;
    }

    private ShipController CreatePlayableShipRoot()
    {
        _ship = new ShipController
        {
            Name = "PrototypeShuttleShip",
            Position = ShuttlePosition,
            Mass = 28.0f,
            GravityScale = 0.0f,
            Freeze = true,
            SeatAnchorPath = "Markers/SeatAnchor",
            PilotEyePath = "Markers/PilotEye",
            ShipCameraPath = "ShipCamera",
            ExteriorVisualPath = "Exterior",
            ExteriorGlassPath = "PrototypeNoSeparateGlass",
            HideExteriorDuringInteriorView = false,
            OrbitCameraDistance = 38.0f,
            OrbitCameraTargetHeight = 2.6f,
            MainThrust = 42.0f,
            ReverseThrust = 24.0f,
            LateralThrust = 34.0f,
            VerticalThrust = 70.0f,
            YawTorque = 120.0f,
            PitchTorque = 105.0f,
            RollTorque = 90.0f,
            LandingDistance = 14.0f,
            InteriorBoundsMin = new Vector3(-4.8f, -2.05f, -18.8f),
            InteriorBoundsMax = new Vector3(4.8f, 4.8f, 13.4f),
            InteriorAftExitLocalZ = 14.0f
        };

        _ship.ContactMonitor = true;
        _ship.MaxContactsReported = 16;
        return _ship;
    }

    private void AddPlayableShipNodes(ShipController ship)
    {
        var markers = new Node3D { Name = "Markers" };
        ship.AddChild(markers);
        AddMarker(markers, "InteriorSpawn", new Vector3(0.0f, -0.57748f, -0.18828f), faceForward: true);
        AddMarker(markers, "ExteriorExit", new Vector3(0.0f, -3.65286f, -3.6776f), faceForward: true);
        AddMarker(markers, "SeatAnchor", new Vector3(-0.55f, 1.68285f, -13.64876f), faceForward: true);
        AddMarker(markers, "PilotEye", new Vector3(-0.55f, 2.26285f, -14.26876f), faceForward: true);
        AddMarker(markers, "SeatExit", new Vector3(-0.55f, 1.51043f, -11.9f), faceForward: true);
        AddMarker(markers, "CopilotSeatAnchor", new Vector3(0.55f, 1.68285f, -13.64876f), faceForward: true);

        ship.AddChild(new Camera3D
        {
            Name = "ShipCamera",
            Fov = 72.0f,
            Current = false
        });

        AddInteriorVolume(ship);
        AddHatch(ship, "PrototypeEnterHatch", true, "../Markers/InteriorSpawn", new Vector3(0.0f, -2.7f, -3.1f), new Vector3(3.8f, 2.4f, 2.4f));
        AddHatch(ship, "PrototypeExitHatch", false, "../Markers/ExteriorExit", new Vector3(0.0f, -0.65f, -1.4f), new Vector3(3.8f, 2.8f, 2.4f));
        AddPilotSeat(ship);
        AddShipWorldPhysicsCollisionFromContract(ship);
        AddInteriorEnclosureCollisionFromContract(ship);
        AddUniformStairStepCollisionFromLayout(ship);
    }

    private static void AddMarker(Node parent, string name, Vector3 position, bool faceForward)
    {
        var marker = new Marker3D
        {
            Name = name,
            Position = position
        };

        if (faceForward)
        {
            marker.Basis = Basis.Identity;
        }

        parent.AddChild(marker);
    }

    private static void AddInteriorVolume(ShipController ship)
    {
        var volume = new ShipInteriorVolume
        {
            Name = "PrototypeInteriorVolume",
            ShipControllerPath = "..",
            InteriorBoundsMin = ship.InteriorBoundsMin,
            InteriorBoundsMax = ship.InteriorBoundsMax,
            CollisionLayer = 2,
            CollisionMask = 1,
            Monitoring = true,
            Monitorable = false
        };
        volume.AddChild(new CollisionShape3D
        {
            Name = "CollisionShape3D",
            Position = new Vector3(0.0f, 1.375f, -2.7f),
            Shape = new BoxShape3D { Size = new Vector3(9.6f, 6.85f, 32.2f) }
        });
        ship.AddChild(volume);
    }

    private static void AddHatch(ShipController ship, string name, bool entersShip, NodePath targetMarkerPath, Vector3 position, Vector3 size)
    {
        var hatch = new ShipHatch
        {
            Name = name,
            EntersShip = entersShip,
            TargetMarkerPath = targetMarkerPath,
            ShipControllerPath = "..",
            Position = position,
            CollisionLayer = 1,
            CollisionMask = 1,
            Monitoring = true
        };
        hatch.AddChild(new CollisionShape3D
        {
            Name = "CollisionShape3D",
            Shape = new BoxShape3D { Size = size }
        });
        ship.AddChild(hatch);
    }

    private static void AddPilotSeat(ShipController ship)
    {
        var seat = new PilotSeat
        {
            Name = "PrototypePilotSeat",
            SeatAnchorPath = "../Markers/SeatAnchor",
            SeatExitPath = "../Markers/SeatExit",
            ShipControllerPath = "..",
            Position = new Vector3(-0.55f, 1.68f, -13.65f),
            CollisionLayer = 1,
            CollisionMask = 1,
            Monitoring = true
        };
        seat.AddChild(new CollisionShape3D
        {
            Name = "CollisionShape3D",
            Shape = new BoxShape3D { Size = new Vector3(1.8f, 1.9f, 2.2f) }
        });
        ship.AddChild(seat);
    }

    private void AddShipWorldPhysicsCollisionFromContract(ShipController ship)
    {
        var contract = LoadExteriorCollisionContract();
        _contractCollisionVisual = new Node3D
        {
            Name = "ExteriorCollisionContractDebug",
            Visible = ShowCollisionVisualReference
        };
        ship.AddChild(_contractCollisionVisual);

        foreach (var region in contract.Regions)
        {
            if (!string.Equals(region.Role, "ship_world_physics", System.StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            if (!string.Equals(region.Kind, "box", System.StringComparison.OrdinalIgnoreCase))
            {
                GD.PushWarning($"Unsupported prototype shuttle exterior collision region kind: {region.Id} ({region.Kind})");
                continue;
            }

            var center = ToVector3(region.Center);
            var size = ToVector3(region.Size);
            ship.AddChild(new CollisionShape3D
            {
                Name = $"{region.Id}_PhysicsCollision",
                Position = center,
                Shape = new BoxShape3D { Size = size }
            });

            _contractCollisionVisual.AddChild(new MeshInstance3D
            {
                Name = $"{region.Id}_DebugBox",
                Position = center,
                Mesh = new BoxMesh { Size = size },
                MaterialOverride = CreateContractCollisionDebugMaterial(),
                CastShadow = GeometryInstance3D.ShadowCastingSetting.Off
            });
        }
    }

    private ExteriorCollisionContract LoadExteriorCollisionContract()
    {
        var globalPath = ProjectSettings.GlobalizePath(ExteriorCollisionContractPath);
        if (!File.Exists(globalPath))
        {
            GD.PushError($"Missing prototype shuttle exterior collision contract: {ExteriorCollisionContractPath}");
            return new ExteriorCollisionContract();
        }

        var json = File.ReadAllText(globalPath);
        return JsonSerializer.Deserialize<ExteriorCollisionContract>(json) ?? new ExteriorCollisionContract();
    }

    private void AddInteriorEnclosureCollisionFromContract(ShipController ship)
    {
        var contract = LoadInteriorCollisionContract();
        var collisionRoot = new StaticBody3D
        {
            Name = "PrototypeInteriorEnclosureCollision",
            CollisionLayer = 1,
            CollisionMask = 1
        };
        ship.AddChild(collisionRoot);

        _interiorCollisionVisual = new Node3D
        {
            Name = "InteriorCollisionContractDebug",
            Visible = ShowCollisionVisualReference
        };
        ship.AddChild(_interiorCollisionVisual);

        foreach (var region in contract.Regions)
        {
            if (!string.Equals(region.Role, "player_enclosure", System.StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            if (!string.Equals(region.Kind, "box", System.StringComparison.OrdinalIgnoreCase))
            {
                GD.PushWarning($"Unsupported prototype shuttle interior collision region kind: {region.Id} ({region.Kind})");
                continue;
            }

            var center = ToVector3(region.Center);
            var size = ToVector3(region.Size);
            collisionRoot.AddChild(new CollisionShape3D
            {
                Name = $"{region.Id}_InteriorCollision",
                Position = center,
                Shape = new BoxShape3D { Size = size }
            });

            _interiorCollisionVisual.AddChild(new MeshInstance3D
            {
                Name = $"{region.Id}_DebugBox",
                Position = center,
                Mesh = new BoxMesh { Size = size },
                MaterialOverride = CreateInteriorCollisionDebugMaterial(region.Surface),
                CastShadow = GeometryInstance3D.ShadowCastingSetting.Off
            });
        }
    }

    private void AddUniformStairStepCollisionFromLayout(ShipController ship)
    {
        var report = LoadCollisionLayoutReport();
        var surfaces = new Dictionary<string, CollisionLayoutSurface>();
        foreach (var surface in report.Surfaces)
        {
            if (!string.IsNullOrEmpty(surface.Id))
            {
                surfaces[surface.Id] = surface;
            }
        }

        if (!surfaces.TryGetValue("cargo_forward_lower", out var cargo)
            || !surfaces.TryGetValue("cockpit_entry_landing", out var landing)
            || cargo.Center.Count < 3
            || cargo.Size.Count < 3
            || landing.Center.Count < 3
            || landing.Size.Count < 3)
        {
            GD.PushWarning("Could not create uniform prototype stair collision; missing cargo or landing layout surfaces.");
            return;
        }

        var stairRoot = new StaticBody3D
        {
            Name = "PrototypeUniformStairStepCollision",
            CollisionLayer = 1,
            CollisionMask = 1
        };
        ship.AddChild(stairRoot);

        var cargoTop = cargo.Center[1] + cargo.Size[1] * 0.5f;
        var landingTop = landing.Center[1] + landing.Size[1] * 0.5f;
        const int stepCount = 10;
        for (var stepIndex = 0; stepIndex < stepCount; stepIndex++)
        {
            var rankFromBottom = stepCount - stepIndex;
            var topY = Mathf.Lerp(cargoTop, landingTop, rankFromBottom / (float)(stepCount + 1));
            AddUniformStairStep(stairRoot, _interiorCollisionVisual, surfaces, "left", stepIndex, topY);
            AddUniformStairStep(stairRoot, _interiorCollisionVisual, surfaces, "right", stepIndex, topY);
        }

        AddWideLandingExtension(stairRoot, _interiorCollisionVisual, surfaces, landingTop);
    }

    private static void AddUniformStairStep(Node stairRoot, Node3D? debugRoot, Dictionary<string, CollisionLayoutSurface> surfaces, string side, int stepIndex, float topY)
    {
        var id = $"{side}_stair_{stepIndex:00}";
        if (!surfaces.TryGetValue(id, out var surface)
            || surface.Center.Count < 3
            || surface.Size.Count < 3)
        {
            GD.PushWarning($"Could not create uniform stair collision for missing layout surface: {id}");
            return;
        }

        var size = ToVector3(surface.Size);
        var center = new Vector3(surface.Center[0], topY - size.Y * 0.5f, surface.Center[2]);
        stairRoot.AddChild(new CollisionShape3D
        {
            Name = $"{id}_UniformCollision",
            Position = center,
            Shape = new BoxShape3D { Size = size }
        });

        debugRoot?.AddChild(new MeshInstance3D
        {
            Name = $"{id}_UniformCollisionDebug",
            Position = center,
            Mesh = new BoxMesh { Size = size },
            MaterialOverride = CreateUniformStairCollisionDebugMaterial(),
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off
        });
    }

    private static void AddWideLandingExtension(Node stairRoot, Node3D? debugRoot, Dictionary<string, CollisionLayoutSurface> surfaces, float landingTop)
    {
        if (!surfaces.TryGetValue("cockpit_entry_landing", out var landing)
            || !surfaces.TryGetValue("cockpit_entry_landing_aft_extension", out var extension)
            || landing.Size.Count < 3
            || extension.Center.Count < 3
            || extension.Size.Count < 3)
        {
            GD.PushWarning("Could not create wide cockpit landing extension; missing landing layout surfaces.");
            return;
        }

        var size = new Vector3(Mathf.Min(landing.Size[0], 3.1f), extension.Size[1], extension.Size[2]);
        var center = new Vector3(0.0f, landingTop - size.Y * 0.5f, extension.Center[2]);
        stairRoot.AddChild(new CollisionShape3D
        {
            Name = "cockpit_entry_landing_aft_extension_WideCollision",
            Position = center,
            Shape = new BoxShape3D { Size = size }
        });

        debugRoot?.AddChild(new MeshInstance3D
        {
            Name = "cockpit_entry_landing_aft_extension_WideCollisionDebug",
            Position = center,
            Mesh = new BoxMesh { Size = size },
            MaterialOverride = CreateUniformStairCollisionDebugMaterial(),
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off
        });
    }


    private CollisionLayoutReport LoadCollisionLayoutReport()
    {
        var globalPath = ProjectSettings.GlobalizePath(CollisionLayoutReportPath);
        if (!File.Exists(globalPath))
        {
            GD.PushError($"Missing prototype shuttle collision layout report: {CollisionLayoutReportPath}");
            return new CollisionLayoutReport();
        }

        var json = File.ReadAllText(globalPath);
        return JsonSerializer.Deserialize<CollisionLayoutReport>(json) ?? new CollisionLayoutReport();
    }

    private InteriorCollisionContract LoadInteriorCollisionContract()
    {
        var globalPath = ProjectSettings.GlobalizePath(InteriorCollisionContractPath);
        if (!File.Exists(globalPath))
        {
            GD.PushError($"Missing prototype shuttle interior collision contract: {InteriorCollisionContractPath}");
            return new InteriorCollisionContract();
        }

        var json = File.ReadAllText(globalPath);
        return JsonSerializer.Deserialize<InteriorCollisionContract>(json) ?? new InteriorCollisionContract();
    }

    private static Vector3 ToVector3(IReadOnlyList<float> values)
    {
        return values.Count >= 3
            ? new Vector3(values[0], values[1], values[2])
            : Vector3.Zero;
    }

    private static StandardMaterial3D CreateContractCollisionDebugMaterial()
    {
        return new StandardMaterial3D
        {
            AlbedoColor = new Color(0.1f, 0.55f, 1.0f, 0.42f),
            Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
            ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded,
            NoDepthTest = true,
            CullMode = BaseMaterial3D.CullModeEnum.Disabled
        };
    }

    private static StandardMaterial3D CreateInteriorCollisionDebugMaterial(string surface)
    {
        var color = surface switch
        {
            "ceiling" => new Color(0.78f, 0.25f, 1.0f, 0.34f),
            "canopy" => new Color(0.25f, 0.85f, 1.0f, 0.34f),
            "guard" => new Color(1.0f, 0.72f, 0.15f, 0.36f),
            "door_frame" => new Color(1.0f, 0.45f, 0.15f, 0.36f),
            _ => new Color(1.0f, 0.12f, 0.45f, 0.34f)
        };

        return new StandardMaterial3D
        {
            AlbedoColor = color,
            Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
            ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded,
            NoDepthTest = true,
            CullMode = BaseMaterial3D.CullModeEnum.Disabled
        };
    }

    private static StandardMaterial3D CreateUniformStairCollisionDebugMaterial()
    {
        return new StandardMaterial3D
        {
            AlbedoColor = new Color(0.0f, 1.0f, 0.35f, 0.44f),
            Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
            ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded,
            NoDepthTest = true,
            CullMode = BaseMaterial3D.CullModeEnum.Disabled
        };
    }

    private void CreateTrimeshCollision(Node node)
    {
        if (node is MeshInstance3D meshInstance)
        {
            if (!ShouldSkipGeneratedCollisionMesh(meshInstance.Name.ToString()))
            {
                meshInstance.CreateTrimeshCollision();
            }
        }

        foreach (var child in node.GetChildren())
        {
            CreateTrimeshCollision(child);
        }
    }

    private static bool ShouldSkipGeneratedCollisionMesh(string name)
    {
        return name.Contains("CargoToCockpitTransitionStep")
            || name.Contains("CockpitEntryLandingRampDropGuardRail")
            || name.Contains("CockpitEntryLandingAftExtension");
    }

    private void HideReviewOnlyNodes(Node node)
    {
        foreach (var child in node.GetChildren())
        {
            var name = child.Name.ToString();
            if (child is Node3D child3D && IsReviewOnlyNode(name))
            {
                child3D.Visible = false;
            }

            HideReviewOnlyNodes(child);
        }
    }

    private static bool IsReviewOnlyNode(string name)
    {
        return name.StartsWith("VOLUME_")
            || name.Contains("ScaleBlockout")
            || name.Contains("ReferenceStrip");
    }

    private static void ForceExteriorSkinOpaque(Node node)
    {
        if (node is MeshInstance3D meshInstance && meshInstance.Mesh is not null)
        {
            for (var surface = 0; surface < meshInstance.Mesh.GetSurfaceCount(); surface++)
            {
                var material = meshInstance.GetActiveMaterial(surface);
                if (material is not StandardMaterial3D standardMaterial
                    || !standardMaterial.ResourceName.Contains("proto_hull_warm_white_silhouette"))
                {
                    continue;
                }

                var opaqueMaterial = (StandardMaterial3D)standardMaterial.Duplicate();
                var color = opaqueMaterial.AlbedoColor;
                opaqueMaterial.AlbedoColor = new Color(color.R, color.G, color.B, 1.0f);
                opaqueMaterial.Transparency = BaseMaterial3D.TransparencyEnum.Disabled;
                meshInstance.SetSurfaceOverrideMaterial(surface, opaqueMaterial);
            }
        }

        foreach (var child in node.GetChildren())
        {
            ForceExteriorSkinOpaque(child);
        }
    }

    private void ApplyCollisionVisualMaterial(Node node)
    {
        if (node is MeshInstance3D meshInstance)
        {
            if (ShouldSkipGeneratedCollisionMesh(meshInstance.Name.ToString()))
            {
                meshInstance.Visible = false;
                return;
            }

            var material = new StandardMaterial3D
            {
                AlbedoColor = new Color(0.0f, 1.0f, 0.35f, 0.48f),
                Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
                ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded,
                NoDepthTest = true,
                CullMode = BaseMaterial3D.CullModeEnum.Disabled
            };
            meshInstance.MaterialOverride = material;
            meshInstance.CastShadow = GeometryInstance3D.ShadowCastingSetting.Off;
        }

        foreach (var child in node.GetChildren())
        {
            ApplyCollisionVisualMaterial(child);
        }
    }

    private sealed class ExteriorCollisionContract
    {
        [JsonPropertyName("regions")]
        public List<ExteriorCollisionRegion> Regions { get; set; } = new();
    }

    private sealed class ExteriorCollisionRegion
    {
        [JsonPropertyName("id")]
        public string Id { get; set; } = "";

        [JsonPropertyName("kind")]
        public string Kind { get; set; } = "";

        [JsonPropertyName("role")]
        public string Role { get; set; } = "";

        [JsonPropertyName("center")]
        public List<float> Center { get; set; } = new();

        [JsonPropertyName("size")]
        public List<float> Size { get; set; } = new();
    }

    private sealed class InteriorCollisionContract
    {
        [JsonPropertyName("regions")]
        public List<InteriorCollisionRegion> Regions { get; set; } = new();
    }

    private sealed class InteriorCollisionRegion
    {
        [JsonPropertyName("id")]
        public string Id { get; set; } = "";

        [JsonPropertyName("kind")]
        public string Kind { get; set; } = "";

        [JsonPropertyName("role")]
        public string Role { get; set; } = "";

        [JsonPropertyName("surface")]
        public string Surface { get; set; } = "";

        [JsonPropertyName("center")]
        public List<float> Center { get; set; } = new();

        [JsonPropertyName("size")]
        public List<float> Size { get; set; } = new();
    }

    private sealed class CollisionLayoutReport
    {
        [JsonPropertyName("surfaces")]
        public List<CollisionLayoutSurface> Surfaces { get; set; } = new();
    }

    private sealed class CollisionLayoutSurface
    {
        [JsonPropertyName("id")]
        public string Id { get; set; } = "";

        [JsonPropertyName("center")]
        public List<float> Center { get; set; } = new();

        [JsonPropertyName("size")]
        public List<float> Size { get; set; } = new();
    }

}
