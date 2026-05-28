using Godot;

public partial class PrototypeShuttleBlockoutCaptureRunner : Node3D
{
    [Export] public string OutputDirectory { get; set; } = "res://reports/prototype_shuttle_blockout/frames";
    [Export] public int CaptureWidth { get; set; } = 1600;
    [Export] public int CaptureHeight { get; set; } = 900;

    private const string ExteriorScenePath = "res://assets/models/ship/prototype_shuttle/prototype_shuttle_exterior.glb";
    private const string InteriorScenePath = "res://assets/models/ship/prototype_shuttle/prototype_shuttle_interior.glb";

    private readonly CaptureView[] _views =
    {
        new("frame_00", "Exterior front silhouette", new Vector3(0.0f, 4.8f, -31.0f), new Vector3(0.0f, 2.35f, -0.6f), 38.0f, true, false),
        new("frame_01", "Exterior side silhouette", new Vector3(-31.0f, 4.6f, 0.0f), new Vector3(0.0f, 2.35f, 0.0f), 38.0f, true, false),
        new("frame_02", "Exterior top silhouette", new Vector3(0.0f, 39.0f, 0.0f), new Vector3(0.0f, 2.0f, 0.0f), 38.0f, true, false),
        new("frame_03", "Three-quarter silhouette and volume", new Vector3(-16.0f, 9.0f, -20.0f), new Vector3(0.0f, 2.25f, -0.8f), 42.0f, true, true),
        new("frame_04", "Belly ramp and cargo volume placement", new Vector3(0.0f, 2.0f, -12.5f), new Vector3(0.0f, 1.45f, -2.0f), 58.0f, true, true),
        new("frame_05", "Raised cockpit and canopy volume", new Vector3(0.0f, 3.8f, -13.0f), new Vector3(0.0f, 3.65f, -6.5f), 54.0f, true, true),
    };

    private Node3D _exteriorRoot = null!;
    private Node3D _interiorRoot = null!;
    private Camera3D _camera = null!;
    private int _frame;
    private int _viewIndex = -1;
    private bool _captureQueued;

    public override void _Ready()
    {
        var window = GetWindow();
        window.Size = new Vector2I(CaptureWidth, CaptureHeight);

        _exteriorRoot = LoadPackageScene(ExteriorScenePath, "PrototypeShuttleExterior");
        _interiorRoot = LoadPackageScene(InteriorScenePath, "PrototypeShuttleInterior");

        _camera = new Camera3D
        {
            Name = "PrototypeShuttleBlockoutCamera",
            Current = true,
            Near = 0.02f,
            Far = 200.0f
        };
        AddChild(_camera);

        AddLighting();
        DirAccess.MakeDirRecursiveAbsolute(ProjectSettings.GlobalizePath(OutputDirectory));
        GD.Print($"Prototype shuttle blockout captures will be written to: {ProjectSettings.GlobalizePath(OutputDirectory)}");
    }

    public override void _Process(double delta)
    {
        _frame++;

        if (_viewIndex < 0 || (!_captureQueued && _frame > 2))
        {
            QueueNextView();
            return;
        }

        if (_captureQueued && _frame > 2)
        {
            SaveCurrentView();
            _captureQueued = false;
            _frame = 0;
        }
    }

    private Node3D LoadPackageScene(string path, string nodeName)
    {
        var packed = ResourceLoader.Load<PackedScene>(path);
        if (packed is null)
        {
            GD.PushError($"Could not load prototype shuttle scene: {path}");
            GetTree().Quit(1);
            return new Node3D();
        }

        var instance = packed.Instantiate<Node3D>();
        instance.Name = nodeName;
        AddChild(instance);
        return instance;
    }

    private void AddLighting()
    {
        var key = new DirectionalLight3D
        {
            Name = "KeyLight",
            LightEnergy = 2.4f,
            ShadowEnabled = true
        };
        key.GlobalTransform = new Transform3D(Basis.Identity, new Vector3(0, 8, 0))
            .LookingAt(new Vector3(-2, 0, -3), Vector3.Up);
        AddChild(key);

        var fill = new OmniLight3D
        {
            Name = "SoftFill",
            Position = new Vector3(-4, 4, 5),
            LightEnergy = 1.2f,
            OmniRange = 18.0f
        };
        AddChild(fill);
    }

    private void QueueNextView()
    {
        _viewIndex++;
        if (_viewIndex >= _views.Length)
        {
            GD.Print("Prototype shuttle blockout capture complete.");
            GetTree().Quit(0);
            return;
        }

        var view = _views[_viewIndex];
        _exteriorRoot.Visible = view.ShowExterior;
        _interiorRoot.Visible = view.ShowInterior;

        var lookDirection = (view.Target - view.Position).Normalized();
        var cameraUp = Vector3.Up;
        if (Mathf.Abs(lookDirection.Dot(cameraUp)) > 0.98f)
        {
            cameraUp = Vector3.Back;
        }

        _camera.GlobalTransform = new Transform3D(Basis.Identity, view.Position)
            .LookingAt(view.Target, cameraUp);
        _camera.Fov = view.Fov;
        _camera.Current = true;
        GD.Print($"Capturing prototype shuttle view: {view.Label}");
        _captureQueued = true;
        _frame = 0;
    }

    private void SaveCurrentView()
    {
        var texture = GetViewport().GetTexture();
        if (texture is null)
        {
            GD.PushError("Viewport texture is unavailable. Run screenshot capture with a real renderer, not --headless.");
            GetTree().Quit(1);
            return;
        }

        var image = texture.GetImage();
        if (image is null)
        {
            GD.PushError("Viewport image is unavailable. Run screenshot capture with a real renderer, not --headless.");
            GetTree().Quit(1);
            return;
        }

        var outputPath = $"{OutputDirectory}/{_views[_viewIndex].Name}.png";
        var error = image.SavePng(outputPath);
        if (error != Error.Ok)
        {
            GD.PushError($"Failed to save {outputPath}: {error}");
            GetTree().Quit(1);
            return;
        }

        GD.Print($"Saved {ProjectSettings.GlobalizePath(outputPath)}");
    }

    private readonly struct CaptureView
    {
        public readonly string Name;
        public readonly string Label;
        public readonly Vector3 Position;
        public readonly Vector3 Target;
        public readonly float Fov;
        public readonly bool ShowExterior;
        public readonly bool ShowInterior;

        public CaptureView(string name, string label, Vector3 position, Vector3 target, float fov, bool showExterior, bool showInterior)
        {
            Name = name;
            Label = label;
            Position = position;
            Target = target;
            Fov = fov;
            ShowExterior = showExterior;
            ShowInterior = showInterior;
        }
    }
}
