using Godot;

public partial class PrototypeShuttleDebugLoader : Node3D
{
    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public Vector3 ShuttlePosition { get; set; } = new(0.0f, 58.0f, 0.0f);
    [Export] public Vector3 PlayerSpawnPosition { get; set; } = new(0.0f, 59.6f, 0.9f);
    [Export] public string ExteriorScenePath { get; set; } = "res://assets/models/ship/prototype_shuttle/prototype_shuttle_exterior.glb";
    [Export] public string InteriorScenePath { get; set; } = "res://assets/models/ship/prototype_shuttle/prototype_shuttle_interior.glb";
    [Export] public string CollisionScenePath { get; set; } = "res://assets/models/ship/prototype_shuttle/prototype_shuttle_collision.glb";
    [Export] public bool ShowInterior { get; set; } = true;
    [Export] public bool AddDebugTraversalCollision { get; set; } = true;
    [Export] public bool ShowCollisionVisualReference { get; set; } = false;
    [Export] public Key CollisionVisualToggleKey { get; set; } = Key.V;

    private Node3D? _collisionVisual;

    public override void _Ready()
    {
        var shuttleRoot = new Node3D
        {
            Name = "PrototypeShuttleBlockout",
            Position = ShuttlePosition
        };
        AddChild(shuttleRoot);

        LoadPackagePart(ExteriorScenePath, "Exterior", shuttleRoot, visible: true, createCollision: false);
        LoadPackagePart(InteriorScenePath, "Interior", shuttleRoot, visible: ShowInterior, createCollision: false);
        _collisionVisual = LoadPackagePart(CollisionScenePath, "Collision", shuttleRoot, visible: ShowCollisionVisualReference, createCollision: AddDebugTraversalCollision);
        if (_collisionVisual is not null)
        {
            ApplyCollisionVisualMaterial(_collisionVisual);
        }

        var player = GetNodeOrNull<PlayerController>(PlayerPath);
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
            || _collisionVisual is null)
        {
            return;
        }

        _collisionVisual.Visible = !_collisionVisual.Visible;
        GD.Print($"Prototype shuttle collision visuals: {(_collisionVisual.Visible ? "visible" : "hidden")}");
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

    private void CreateTrimeshCollision(Node node)
    {
        if (node is MeshInstance3D meshInstance)
        {
            meshInstance.CreateTrimeshCollision();
        }

        foreach (var child in node.GetChildren())
        {
            CreateTrimeshCollision(child);
        }
    }

    private void ApplyCollisionVisualMaterial(Node node)
    {
        if (node is MeshInstance3D meshInstance)
        {
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

}
