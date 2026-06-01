using Godot;

public partial class PrototypeShuttleInteriorCaptureRunner : Node3D
{
    [Export] public string OutputDirectory { get; set; } = "res://reports/prototype_shuttle_interior/frames";
    [Export] public int CaptureWidth { get; set; } = 1600;
    [Export] public int CaptureHeight { get; set; } = 900;
    [Export] public bool HidePlanningVolumes { get; set; } = true;

    private const string ExteriorScenePath = "res://assets/models/ship/prototype_shuttle/prototype_shuttle_exterior.glb";
    private const string InteriorScenePath = "res://assets/models/ship/prototype_shuttle/prototype_shuttle_interior.glb";

    private readonly CaptureView[] _views =
    {
        new("frame_00", "Iteration 2 cargo aisle material separation and practical light read", new Vector3(-1.55f, 0.95f, 5.65f), new Vector3(0.20f, -0.74f, -1.60f), 68.0f, true),
        new("frame_01", "Iteration 2 ramp close-up: hinge, tread, scuffs, and threshold", new Vector3(1.45f, -0.78f, -2.05f), new Vector3(-0.35f, -0.92f, 0.25f), 70.0f, true),
        new("frame_02", "Iteration 2 left cargo wall low light and service boxes", new Vector3(1.35f, 1.05f, 3.60f), new Vector3(-3.72f, 0.20f, 5.10f), 62.0f, true),
        new("frame_03", "Iteration 2 right cargo wall low light and tie-down track", new Vector3(-1.35f, 1.05f, 3.60f), new Vector3(3.72f, 0.20f, 5.10f), 62.0f, true),
        new("frame_04", "Iteration 2 left stair ascent scuffed step noses and marker lights", new Vector3(0.55f, 2.22f, 0.45f), new Vector3(-2.20f, -0.32f, -1.15f), 78.0f, true),
        new("frame_05", "Iteration 2 right stair ascent scuffed step noses and marker lights", new Vector3(-0.55f, 2.22f, 0.45f), new Vector3(2.20f, -0.32f, -1.15f), 78.0f, true),
        new("frame_06", "Iteration 2 top landing and cockpit transition material/collision review", new Vector3(-1.30f, 1.88f, -5.65f), new Vector3(1.60f, 0.05f, 1.35f), 70.0f, true),
        new("frame_07", "Iteration 2 bottom of ramp looking up across full ramp surface", new Vector3(0.0f, -2.36f, -4.10f), new Vector3(0.0f, -1.10f, 0.60f), 78.0f, true),
        new("frame_08", "Iteration 2 cockpit left seat controls, MFDs, and floor readability", new Vector3(-1.75f, 1.70f, -11.35f), new Vector3(0.20f, 1.38f, -14.35f), 62.0f, true),
        new("frame_09", "Iteration 2 cockpit right seat controls, sill structure, and clearance", new Vector3(1.85f, 1.72f, -10.85f), new Vector3(-0.20f, 1.34f, -14.10f), 62.0f, true),
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
        if (HidePlanningVolumes)
        {
            HideReviewOnlyNodes(_interiorRoot);
        }

        _camera = new Camera3D
        {
            Name = "PrototypeShuttleInteriorCamera",
            Current = true,
            Near = 0.02f,
            Far = 120.0f
        };
        AddChild(_camera);

        AddLighting();
        DirAccess.MakeDirRecursiveAbsolute(ProjectSettings.GlobalizePath(OutputDirectory));
        GD.Print($"Prototype shuttle interior captures will be written to: {ProjectSettings.GlobalizePath(OutputDirectory)}");
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

    private void AddLighting()
    {
        var key = new DirectionalLight3D
        {
            Name = "InteriorKeyLight",
            LightEnergy = 1.55f,
            ShadowEnabled = true
        };
        key.GlobalTransform = new Transform3D(Basis.Identity, new Vector3(0, 7, -6))
            .LookingAt(new Vector3(0, 0, 2), Vector3.Up);
        AddChild(key);

        var cargoFill = new OmniLight3D
        {
            Name = "CargoInteriorFill",
            Position = new Vector3(0.0f, 2.5f, 4.0f),
            LightEnergy = 1.6f,
            OmniRange = 13.0f
        };
        AddChild(cargoFill);

        var rampFill = new OmniLight3D
        {
            Name = "RampInteriorFill",
            Position = new Vector3(0.0f, 1.2f, -1.0f),
            LightEnergy = 1.2f,
            OmniRange = 9.0f
        };
        AddChild(rampFill);

        var cockpitFill = new OmniLight3D
        {
            Name = "CockpitInteriorFill",
            Position = new Vector3(0.0f, 2.6f, -10.5f),
            LightEnergy = 0.95f,
            OmniRange = 8.5f
        };
        AddChild(cockpitFill);
    }

    private void QueueNextView()
    {
        _viewIndex++;
        if (_viewIndex >= _views.Length)
        {
            GD.Print("Prototype shuttle interior capture complete.");
            GetTree().Quit(0);
            return;
        }

        var view = _views[_viewIndex];
        _exteriorRoot.Visible = view.ShowExterior;
        _interiorRoot.Visible = true;

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
        GD.Print($"Capturing prototype shuttle interior view: {view.Label}");
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

        public CaptureView(string name, string label, Vector3 position, Vector3 target, float fov, bool showExterior)
        {
            Name = name;
            Label = label;
            Position = position;
            Target = target;
            Fov = fov;
            ShowExterior = showExterior;
        }
    }
}
