using Godot;

public partial class ShipAlignmentCaptureRunner : Node
{
    [Export] public NodePath ShipPath { get; set; } = "../Ship";
    [Export] public NodePath OverlayPath { get; set; } = "../ShipAlignmentOverlay";
    [Export] public string OutputDirectory { get; set; } = "res://reports/ship_alignment_captures";
    [Export] public int CaptureWidth { get; set; } = 1600;
    [Export] public int CaptureHeight { get; set; } = 1000;

    private readonly CaptureView[] _views =
    {
        new("01_exterior_front", new Vector3(0.0f, 3.0f, -24.0f), new Vector3(0.0f, 2.4f, -1.6f), 58.0f, false),
        new("01_exterior_front_overlay", new Vector3(0.0f, 3.0f, -24.0f), new Vector3(0.0f, 2.4f, -1.6f), 58.0f, true),
        new("02_exterior_rear_hatch", new Vector3(0.0f, 3.2f, 18.0f), new Vector3(0.0f, 1.9f, 3.4f), 55.0f, false),
        new("02_exterior_rear_hatch_overlay", new Vector3(0.0f, 3.2f, 18.0f), new Vector3(0.0f, 1.9f, 3.4f), 55.0f, true),
        new("03_exterior_left", new Vector3(-22.0f, 3.4f, -1.8f), new Vector3(0.0f, 2.0f, -1.2f), 56.0f, false),
        new("03_exterior_left_overlay", new Vector3(-22.0f, 3.4f, -1.8f), new Vector3(0.0f, 2.0f, -1.2f), 56.0f, true),
        new("04_exterior_top", new Vector3(0.0f, 22.0f, -0.8f), new Vector3(0.0f, 1.5f, -0.8f), 48.0f, false),
        new("04_exterior_top_overlay", new Vector3(0.0f, 22.0f, -0.8f), new Vector3(0.0f, 1.5f, -0.8f), 48.0f, true),
        new("05_cockpit_glass_close", new Vector3(0.0f, 5.1f, -9.2f), new Vector3(0.0f, 2.7f, -3.2f), 42.0f, false),
        new("05_cockpit_glass_close_overlay", new Vector3(0.0f, 5.1f, -9.2f), new Vector3(0.0f, 2.7f, -3.2f), 42.0f, true),
        new("06_interior_entry", new Vector3(-4.35f, 1.85f, 2.55f), new Vector3(0.0f, 1.20f, -1.35f), 62.0f, false, true),
        new("06_interior_entry_overlay", new Vector3(-4.35f, 1.85f, 2.55f), new Vector3(0.0f, 1.20f, -1.35f), 62.0f, true, true),
        new("07_interior_seat", new Vector3(-4.05f, 1.75f, -1.00f), new Vector3(0.0f, 1.25f, -3.35f), 60.0f, false, true),
        new("07_interior_seat_overlay", new Vector3(-4.05f, 1.75f, -1.00f), new Vector3(0.0f, 1.25f, -3.35f), 60.0f, true, true),
        new("08_interior_cockpit_backlook", new Vector3(-4.15f, 1.85f, -3.45f), new Vector3(0.0f, 1.22f, 1.70f), 66.0f, false, true),
        new("08_interior_cockpit_backlook_overlay", new Vector3(-4.15f, 1.85f, -3.45f), new Vector3(0.0f, 1.22f, 1.70f), 66.0f, true, true),
        new("09_player_entry_forward", new Vector3(0.0f, 1.62f, 3.05f), new Vector3(0.0f, 1.55f, -0.95f), 76.0f, false),
        new("09_player_entry_forward_overlay", new Vector3(0.0f, 1.62f, 3.05f), new Vector3(0.0f, 1.55f, -0.95f), 76.0f, true),
        new("10_pilot_eye_forward", new Vector3(0.0f, 1.54f, -3.00f), new Vector3(0.0f, 1.82f, -5.55f), 74.0f, false),
        new("10_pilot_eye_forward_overlay", new Vector3(0.0f, 1.54f, -3.00f), new Vector3(0.0f, 1.82f, -5.55f), 74.0f, true),
    };

    private ShipController _ship = null!;
    private Node3D? _overlay;
    private Camera3D _camera = null!;
    private readonly Node3D?[] _cutawayNodes = new Node3D?[9];
    private int _frame;
    private int _viewIndex = -1;
    private bool _captureQueued;

    public override void _Ready()
    {
        _ship = GetNode<ShipController>(ShipPath);
        _overlay = GetNodeOrNull<Node3D>(OverlayPath);
        _ship.Freeze = true;
        CacheCutawayNodes();

        var window = GetWindow();
        window.Size = new Vector2I(CaptureWidth, CaptureHeight);

        _camera = new Camera3D
        {
            Name = "AlignmentCaptureCamera",
            Current = true,
            Near = 0.02f,
            Far = 200.0f
        };
        AddChild(_camera);

        DirAccess.MakeDirRecursiveAbsolute(ProjectSettings.GlobalizePath(OutputDirectory));
        GD.Print($"Ship alignment captures will be written to: {ProjectSettings.GlobalizePath(OutputDirectory)}");
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

    private void QueueNextView()
    {
        _viewIndex++;
        if (_viewIndex >= _views.Length)
        {
            GD.Print("Ship alignment screenshot capture complete.");
            SetInteriorCutawayActive(false);
            _ship.SetInteriorViewActive(false);
            GetTree().Quit(0);
            return;
        }

        var view = _views[_viewIndex];
        var isInteriorView = view.Name.StartsWith("06_")
            || view.Name.StartsWith("07_")
            || view.Name.StartsWith("08_")
            || view.Name.StartsWith("09_")
            || view.Name.StartsWith("10_");
        _ship.SetInteriorViewActive(isInteriorView);
        SetInteriorCutawayActive(view.UseCutaway);
        if (_overlay is not null)
        {
            _overlay.Visible = view.ShowOverlay;
        }

        var shipTransform = _ship.GlobalTransform;
        var cameraPosition = shipTransform * view.Position;
        var lookTarget = shipTransform * view.Target;

        var lookDirection = (lookTarget - cameraPosition).Normalized();
        var cameraUp = shipTransform.Basis.Y.Normalized();
        if (Mathf.Abs(lookDirection.Dot(cameraUp)) > 0.98f)
        {
            cameraUp = shipTransform.Basis.Z.Normalized();
        }

        _camera.GlobalTransform = new Transform3D(Basis.Identity, cameraPosition)
            .LookingAt(lookTarget, cameraUp);
        _camera.Fov = view.Fov;
        _camera.Current = true;
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

    private void CacheCutawayNodes()
    {
        _cutawayNodes[0] = _ship.GetNodeOrNull<Node3D>("Interior/LeftWall");
        _cutawayNodes[1] = _ship.GetNodeOrNull<Node3D>("Interior/CeilingSpine");
        _cutawayNodes[2] = _ship.GetNodeOrNull<Node3D>("Interior/CeilingLightStrip");
        _cutawayNodes[3] = _ship.GetNodeOrNull<Node3D>("Interior/LeftSideLight");
        _cutawayNodes[4] = _ship.GetNodeOrNull<Node3D>("Interior/Cockpit/CanopyGlassInterior");
        _cutawayNodes[5] = _ship.GetNodeOrNull<Node3D>("Interior/Cockpit/CanopyFrontFrame");
        _cutawayNodes[6] = _ship.GetNodeOrNull<Node3D>("Interior/Cockpit/CanopyLeftFrame");
        _cutawayNodes[7] = _ship.GetNodeOrNull<Node3D>("Interior/Cockpit/CanopyRearFrame");
        _cutawayNodes[8] = _ship.GetNodeOrNull<Node3D>("Interior/InnerShell");
    }

    private void SetInteriorCutawayActive(bool active)
    {
        foreach (var node in _cutawayNodes)
        {
            if (node is not null)
            {
                node.Visible = !active;
            }
        }
    }

    private readonly struct CaptureView
    {
        public readonly string Name;
        public readonly Vector3 Position;
        public readonly Vector3 Target;
        public readonly float Fov;
        public readonly bool ShowOverlay;
        public readonly bool UseCutaway;

        public CaptureView(string name, Vector3 position, Vector3 target, float fov, bool showOverlay, bool useCutaway = false)
        {
            Name = name;
            Position = position;
            Target = target;
            Fov = fov;
            ShowOverlay = showOverlay;
            UseCutaway = useCutaway;
        }
    }
}
