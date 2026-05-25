using Godot;

public partial class ShipAlignmentCaptureRunner : Node
{
    [Export] public NodePath ShipPath { get; set; } = "../Ship";
    [Export] public string OutputDirectory { get; set; } = "res://reports/ship_alignment_captures";
    [Export] public int CaptureWidth { get; set; } = 1600;
    [Export] public int CaptureHeight { get; set; } = 1000;

    private readonly CaptureView[] _views =
    {
        new("01_exterior_front", new Vector3(0.0f, 3.0f, -24.0f), new Vector3(0.0f, 2.4f, -1.6f), 58.0f),
        new("02_exterior_rear_hatch", new Vector3(0.0f, 3.2f, 18.0f), new Vector3(0.0f, 1.9f, 3.4f), 55.0f),
        new("03_exterior_left", new Vector3(-22.0f, 3.4f, -1.8f), new Vector3(0.0f, 2.0f, -1.2f), 56.0f),
        new("04_exterior_top", new Vector3(0.0f, 22.0f, -0.8f), new Vector3(0.0f, 1.5f, -0.8f), 48.0f),
        new("05_cockpit_glass_close", new Vector3(0.0f, 5.1f, -9.2f), new Vector3(0.0f, 2.7f, -3.2f), 42.0f),
        new("06_interior_entry", new Vector3(0.0f, 1.65f, 3.0f), new Vector3(0.0f, 1.45f, -1.6f), 72.0f),
        new("07_interior_seat", new Vector3(0.0f, 1.75f, -0.55f), new Vector3(0.0f, 1.45f, -3.55f), 72.0f),
        new("08_interior_cockpit_backlook", new Vector3(0.0f, 1.75f, -3.45f), new Vector3(0.0f, 1.45f, 1.7f), 72.0f),
    };

    private ShipController _ship = null!;
    private Camera3D _camera = null!;
    private int _frame;
    private int _viewIndex = -1;
    private bool _captureQueued;

    public override void _Ready()
    {
        _ship = GetNode<ShipController>(ShipPath);
        _ship.Freeze = true;

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
            GetTree().Quit(0);
            return;
        }

        var view = _views[_viewIndex];
        var shipTransform = _ship.GlobalTransform;
        var cameraPosition = shipTransform * view.Position;
        var lookTarget = shipTransform * view.Target;

        _camera.GlobalTransform = new Transform3D(Basis.Identity, cameraPosition)
            .LookingAt(lookTarget, shipTransform.Basis.Y.Normalized());
        _camera.Fov = view.Fov;
        _camera.Current = true;
        _captureQueued = true;
        _frame = 0;
    }

    private void SaveCurrentView()
    {
        var image = GetViewport().GetTexture().GetImage();
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
        public readonly Vector3 Position;
        public readonly Vector3 Target;
        public readonly float Fov;

        public CaptureView(string name, Vector3 position, Vector3 target, float fov)
        {
            Name = name;
            Position = position;
            Target = target;
            Fov = fov;
        }
    }
}
