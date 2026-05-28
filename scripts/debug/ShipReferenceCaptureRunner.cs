using Godot;

public partial class ShipReferenceCaptureRunner : Node
{
    [Export] public NodePath ShipPath { get; set; } = "../Ship";
    [Export] public string OutputDirectory { get; set; } = "res://plans/0.3 roadmap to AAA/0.3.2 references";
    [Export] public int CaptureWidth { get; set; } = 1920;
    [Export] public int CaptureHeight { get; set; } = 1080;

    private readonly CaptureView[] _views =
    {
        new("shuttle_a_exterior_front", new Vector3(0.0f, 3.8f, -30.0f), new Vector3(0.0f, 2.2f, -2.0f), 40.0f),
        new("shuttle_a_exterior_rear", new Vector3(0.0f, 3.7f, 24.0f), new Vector3(0.0f, 1.9f, 3.0f), 38.0f),
        new("shuttle_a_exterior_left", new Vector3(-30.0f, 3.5f, -1.5f), new Vector3(0.0f, 1.9f, -1.5f), 38.0f),
        new("shuttle_a_exterior_top", new Vector3(0.0f, 36.0f, -1.5f), new Vector3(0.0f, 1.2f, -1.5f), 38.0f),
        new("shuttle_a_cockpit_glass_close", new Vector3(0.0f, 5.3f, -13.2f), new Vector3(0.0f, 2.55f, -5.2f), 32.0f),
    };

    private ShipController _ship = null!;
    private Camera3D _camera = null!;
    private Node3D? _interior;
    private int _frame;
    private int _viewIndex = -1;
    private bool _captureQueued;

    public override void _Ready()
    {
        _ship = GetNode<ShipController>(ShipPath);
        _ship.Freeze = true;
        _ship.SetInteriorViewActive(false);
        _interior = _ship.GetNodeOrNull<Node3D>("Interior");
        if (_interior is not null)
        {
            _interior.Visible = false;
        }

        var window = GetWindow();
        window.Size = new Vector2I(CaptureWidth, CaptureHeight);

        _camera = new Camera3D
        {
            Name = "ReferenceCaptureCamera",
            Current = true,
            Near = 0.02f,
            Far = 240.0f
        };
        AddChild(_camera);

        DirAccess.MakeDirRecursiveAbsolute(ProjectSettings.GlobalizePath(OutputDirectory));
        GD.Print($"Ship reference captures will be written to: {ProjectSettings.GlobalizePath(OutputDirectory)}");
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
            GD.Print("Ship reference screenshot capture complete.");
            GetTree().Quit(0);
            return;
        }

        var view = _views[_viewIndex];
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
