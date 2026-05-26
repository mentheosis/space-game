using Godot;
using Godot.Collections;

public partial class ShipWalkthroughCaptureRunner : Node
{
    public enum ReviewMode
    {
        Walkthrough,
        Cockpit
    }

    [Export] public NodePath ShipPath { get; set; } = "../Ship";
    [Export] public string OutputDirectory { get; set; } = "res://reports/ship_walkthrough";
    [Export] public ReviewMode Mode { get; set; } = ReviewMode.Walkthrough;
    [Export] public int CaptureWidth { get; set; } = 480;
    [Export] public int CaptureHeight { get; set; } = 270;
    [Export] public int FrameCount { get; set; } = 120;
    [Export] public int FramesPerSecond { get; set; } = 12;
    [Export] public float HoldLastFrameSeconds { get; set; } = 1.0f;
    [Export] public bool IsolateBlenderInteriorForReview { get; set; } = true;

    private ShipController _ship = null!;
    private Camera3D _camera = null!;
    private int _frame = -1;
    private bool _captureQueued;
    private string _outputAbsolute = "";
    private string _framesAbsolute = "";

    public override void _Ready()
    {
        _ship = GetNode<ShipController>(ShipPath);
        _ship.Freeze = true;
        _ship.SetInteriorViewActive(true);
        if (IsolateBlenderInteriorForReview)
        {
            IsolateBlenderInterior();
        }

        var window = GetWindow();
        window.Size = new Vector2I(CaptureWidth, CaptureHeight);

        _camera = new Camera3D
        {
            Name = "ShipWalkthroughCamera",
            Current = true,
            Near = 0.02f,
            Far = 200.0f,
            Fov = 76.0f
        };
        AddChild(_camera);

        _outputAbsolute = ProjectSettings.GlobalizePath(OutputDirectory);
        _framesAbsolute = ProjectSettings.GlobalizePath($"{OutputDirectory}/frames");
        ResetOutputDirectory();
        WriteManifest();
        GD.Print($"Ship walkthrough frames will be written to: {_framesAbsolute}");
    }

    private void IsolateBlenderInterior()
    {
        foreach (var child in _ship.GetChildren())
        {
            if (child is not Node3D node)
            {
                continue;
            }

            var name = node.Name.ToString();
            if (name is "Interior" or "Markers")
            {
                continue;
            }

            node.Visible = false;
        }

        var interior = _ship.GetNodeOrNull<Node3D>("Interior");
        if (interior is null)
        {
            return;
        }

        foreach (var child in interior.GetChildren())
        {
            if (child is not Node3D node)
            {
                continue;
            }

            var name = node.Name.ToString();
            if (name is "BlenderInteriorVisual" or "InteriorLight" or "CockpitGlow")
            {
                continue;
            }

            node.Visible = false;
        }
    }

    public override void _Process(double delta)
    {
        if (!_captureQueued)
        {
            QueueNextFrame();
            return;
        }

        SaveCurrentFrame();
        _captureQueued = false;
    }

    private void QueueNextFrame()
    {
        _frame++;
        if (_frame >= FrameCount)
        {
            GD.Print("Ship walkthrough capture complete.");
            GetTree().Quit(0);
            return;
        }

        var progress = FrameCount <= 1 ? 1.0f : _frame / (float)(FrameCount - 1);
        var pose = Mode == ReviewMode.Cockpit ? CockpitPose(progress) : WalkthroughPose(progress);
        var shipTransform = _ship.GlobalTransform;
        var cameraPosition = shipTransform * pose.Position;
        var lookTarget = shipTransform * pose.Target;
        var cameraUp = shipTransform.Basis.Y.Normalized();

        _camera.GlobalTransform = new Transform3D(Basis.Identity, cameraPosition)
            .LookingAt(lookTarget, cameraUp);
        _camera.Current = true;
        _captureQueued = true;
    }

    private void SaveCurrentFrame()
    {
        var texture = GetViewport().GetTexture();
        if (texture is null)
        {
            GD.PushError("Viewport texture is unavailable. Run walkthrough capture with a real renderer.");
            GetTree().Quit(1);
            return;
        }

        var image = texture.GetImage();
        if (image is null)
        {
            GD.PushError("Viewport image is unavailable. Run walkthrough capture with a real renderer.");
            GetTree().Quit(1);
            return;
        }

        image.Resize(CaptureWidth, CaptureHeight, Image.Interpolation.Lanczos);
        image.Convert(Image.Format.Rgb8);

        var framePath = $"{_framesAbsolute}/frame_{_frame:000}.rgb";
        using var file = Godot.FileAccess.Open(framePath, Godot.FileAccess.ModeFlags.Write);
        if (file is null)
        {
            GD.PushError($"Failed to open walkthrough frame for writing: {framePath}");
            GetTree().Quit(1);
            return;
        }

        file.StoreBuffer(image.GetData());
        GD.Print($"Saved walkthrough frame {framePath}");
    }

    private WalkthroughCameraPose WalkthroughPose(float progress)
    {
        if (progress < 0.24f)
        {
            var t = SmoothStep(progress / 0.24f);
            return new WalkthroughCameraPose(
                Lerp(new Vector3(0.0f, 1.58f, 3.30f), new Vector3(0.0f, 1.58f, 0.68f), t),
                Lerp(new Vector3(0.0f, 1.48f, 0.90f), new Vector3(0.0f, 1.46f, -1.25f), t)
            );
        }

        if (progress < 0.36f)
        {
            var t = SmoothStep((progress - 0.24f) / 0.12f);
            return new WalkthroughCameraPose(
                new Vector3(0.0f, 1.58f, 0.70f),
                Lerp(new Vector3(0.0f, 1.46f, -1.25f), new Vector3(0.0f, 0.22f, -0.55f), t)
            );
        }

        if (progress < 0.48f)
        {
            var t = SmoothStep((progress - 0.36f) / 0.12f);
            return new WalkthroughCameraPose(
                new Vector3(0.0f, 1.58f, 0.70f),
                Lerp(new Vector3(0.0f, 0.22f, -0.55f), new Vector3(0.0f, 2.18f, -0.35f), t)
            );
        }

        if (progress < 0.66f)
        {
            var t = SmoothStep((progress - 0.48f) / 0.18f);
            return new WalkthroughCameraPose(
                Lerp(new Vector3(0.0f, 1.58f, 0.70f), new Vector3(0.0f, 1.56f, -3.20f), t),
                Lerp(new Vector3(0.0f, 2.18f, -0.35f), new Vector3(0.0f, 1.58f, -4.85f), t)
            );
        }

        if (progress < 0.76f)
        {
            var t = SmoothStep((progress - 0.66f) / 0.10f);
            return new WalkthroughCameraPose(
                new Vector3(0.0f, 1.56f, -3.20f),
                Lerp(new Vector3(0.0f, 1.58f, -4.85f), new Vector3(-1.70f, 1.28f, -3.50f), t)
            );
        }

        if (progress < 0.86f)
        {
            var t = SmoothStep((progress - 0.76f) / 0.10f);
            return new WalkthroughCameraPose(
                new Vector3(0.0f, 1.56f, -3.20f),
                Lerp(new Vector3(-1.70f, 1.28f, -3.50f), new Vector3(1.70f, 1.70f, -4.25f), t)
            );
        }

        if (progress < 0.92f)
        {
            var t = SmoothStep((progress - 0.86f) / 0.06f);
            return new WalkthroughCameraPose(
                Lerp(new Vector3(0.0f, 1.56f, -3.20f), new Vector3(0.0f, 1.62f, -5.45f), t),
                Lerp(new Vector3(1.70f, 1.70f, -4.25f), new Vector3(0.0f, 1.90f, -7.15f), t)
            );
        }

        var finalT = SmoothStep((progress - 0.92f) / 0.08f);
        return new WalkthroughCameraPose(
            new Vector3(0.0f, 2.34f, -8.72f),
            Lerp(new Vector3(0.0f, 2.58f, -10.10f), new Vector3(0.0f, 3.05f, -13.10f), finalT)
        );
    }

    private WalkthroughCameraPose CockpitPose(float progress)
    {
        if (progress < 0.18f)
        {
            var t = SmoothStep(progress / 0.18f);
            return new WalkthroughCameraPose(
                Lerp(new Vector3(0.0f, 1.70f, -5.88f), new Vector3(0.0f, 1.82f, -6.72f), t),
                Lerp(new Vector3(0.0f, 1.96f, -8.35f), new Vector3(0.0f, 2.18f, -8.45f), t)
            );
        }

        if (progress < 0.34f)
        {
            var t = SmoothStep((progress - 0.18f) / 0.16f);
            return new WalkthroughCameraPose(
                Lerp(new Vector3(-0.78f, 1.78f, -6.82f), new Vector3(-0.84f, 1.70f, -7.60f), t),
                Lerp(new Vector3(0.0f, 1.32f, -9.70f), new Vector3(-0.64f, 1.18f, -9.25f), t)
            );
        }

        if (progress < 0.50f)
        {
            var t = SmoothStep((progress - 0.34f) / 0.16f);
            return new WalkthroughCameraPose(
                Lerp(new Vector3(0.84f, 1.70f, -7.60f), new Vector3(0.78f, 1.78f, -6.82f), t),
                Lerp(new Vector3(0.64f, 1.18f, -9.25f), new Vector3(0.0f, 1.32f, -9.70f), t)
            );
        }

        if (progress < 0.66f)
        {
            var t = SmoothStep((progress - 0.50f) / 0.16f);
            return new WalkthroughCameraPose(
                Lerp(new Vector3(0.0f, 2.24f, -8.92f), new Vector3(0.0f, 2.32f, -8.92f), t),
                Lerp(new Vector3(0.0f, 1.26f, -9.82f), new Vector3(0.0f, 1.70f, -10.22f), t)
            );
        }

        if (progress < 0.82f)
        {
            var t = SmoothStep((progress - 0.66f) / 0.16f);
            return new WalkthroughCameraPose(
                new Vector3(0.0f, 2.36f, -8.86f),
                Lerp(new Vector3(0.0f, 2.46f, -11.40f), new Vector3(0.0f, 3.18f, -9.05f), t)
            );
        }

        var finalT = SmoothStep((progress - 0.82f) / 0.18f);
        return new WalkthroughCameraPose(
            new Vector3(0.0f, 2.38f, -8.82f),
            Lerp(new Vector3(0.0f, 2.50f, -11.60f), new Vector3(0.0f, 3.05f, -13.10f), finalT)
        );
    }

    private void ResetOutputDirectory()
    {
        if (DirAccess.DirExistsAbsolute(_framesAbsolute))
        {
            var dir = DirAccess.Open(_framesAbsolute);
            if (dir is not null)
            {
                foreach (var file in dir.GetFiles())
                {
                    dir.Remove(file);
                }
            }
        }

        DirAccess.MakeDirRecursiveAbsolute(_framesAbsolute);
    }

    private void WriteManifest()
    {
        var payload = new Dictionary
        {
            ["width"] = CaptureWidth,
            ["height"] = CaptureHeight,
            ["frame_count"] = FrameCount,
            ["fps"] = FramesPerSecond,
            ["hold_last_seconds"] = HoldLastFrameSeconds,
            ["frames_directory"] = "frames",
        };
        var json = Json.Stringify(payload, "\t");
        using var file = Godot.FileAccess.Open($"{_outputAbsolute}/manifest.json", Godot.FileAccess.ModeFlags.Write);
        file?.StoreString(json + "\n");
    }

    private static Vector3 Lerp(Vector3 from, Vector3 to, float t) => from.Lerp(to, t);

    private static float SmoothStep(float t)
    {
        t = Mathf.Clamp(t, 0.0f, 1.0f);
        return t * t * (3.0f - 2.0f * t);
    }

    private readonly struct WalkthroughCameraPose
    {
        public readonly Vector3 Position;
        public readonly Vector3 Target;

        public WalkthroughCameraPose(Vector3 position, Vector3 target)
        {
            Position = position;
            Target = target;
        }
    }
}
