using Godot;
using Godot.Collections;

public partial class ShipWalkthroughCaptureRunner : Node
{
    public enum ReviewMode
    {
        Walkthrough,
        CockpitWalkthrough
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
            if (name is "BlenderInteriorVisual" || node is Light3D)
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
        var pose = Mode switch
        {
            ReviewMode.CockpitWalkthrough => CockpitWalkthroughPose(progress),
            _ => WalkthroughPose(progress)
        };
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
        var start = new Vector3(0.0f, 1.58f, 2.12f);
        var aftReview = new Vector3(0.0f, 1.60f, 1.54f);
        var cockpit = new Vector3(0.0f, 2.34f, -7.35f);
        var noseTarget = new Vector3(0.0f, 1.46f, -10.76f);
        var aftTarget = new Vector3(0.0f, 1.64f, 3.54f);

        if (progress < 0.30f)
        {
            var t = SmoothStep(progress / 0.30f);
            var position = Lerp(start, cockpit, t);
            var yaw = Mathf.Sin(t * Mathf.Tau * 1.80f) * 0.32f;
            var pitch = Mathf.Sin(t * Mathf.Tau * 1.35f + 0.55f) * 0.22f;
            var target = new Vector3(yaw, position.Y + 0.04f + pitch, position.Z - 2.72f);
            return new WalkthroughCameraPose(position, target);
        }

        if (progress < 0.58f)
        {
            var reviewT = SmoothStep((progress - 0.30f) / 0.28f);
            Vector3 noseReviewTarget;
            if (reviewT < 0.20f)
            {
                var t = SmoothStep(reviewT / 0.20f);
                noseReviewTarget = Lerp(new Vector3(0.0f, 2.45f, -10.50f), noseTarget, t);
            }
            else if (reviewT < 0.40f)
            {
                var t = SmoothStep((reviewT - 0.20f) / 0.20f);
                noseReviewTarget = Lerp(noseTarget, new Vector3(-1.10f, 1.74f, -9.72f), t);
            }
            else if (reviewT < 0.60f)
            {
                var t = SmoothStep((reviewT - 0.40f) / 0.20f);
                noseReviewTarget = Lerp(new Vector3(-1.10f, 1.74f, -9.72f), new Vector3(1.10f, 1.74f, -9.72f), t);
            }
            else if (reviewT < 0.80f)
            {
                var t = SmoothStep((reviewT - 0.60f) / 0.20f);
                noseReviewTarget = Lerp(new Vector3(1.10f, 1.74f, -9.72f), new Vector3(0.0f, 3.18f, -9.92f), t);
            }
            else
            {
                var t = SmoothStep((reviewT - 0.80f) / 0.20f);
                noseReviewTarget = Lerp(new Vector3(0.0f, 3.18f, -9.92f), new Vector3(0.0f, 1.16f, -10.12f), t);
            }

            return new WalkthroughCameraPose(cockpit, noseReviewTarget);
        }

        if (progress < 0.64f)
        {
            var turnT = SmoothStep((progress - 0.58f) / 0.06f);
            var target = Lerp(new Vector3(0.0f, 1.16f, -10.12f), aftTarget, turnT);
            return new WalkthroughCameraPose(cockpit, target);
        }

        if (progress < 0.78f)
        {
            var returnT = SmoothStep((progress - 0.64f) / 0.14f);
            var returnPosition = Lerp(cockpit, aftReview, returnT);
            var rearYaw = Mathf.Sin(returnT * Mathf.Tau * 1.20f + 0.3f) * 0.34f;
            var rearPitch = Mathf.Sin(returnT * Mathf.Tau * 1.05f + 1.1f) * 0.22f;
            var rearTarget = new Vector3(rearYaw, returnPosition.Y + 0.10f + rearPitch, Mathf.Min(3.54f, returnPosition.Z + 2.08f));
            return new WalkthroughCameraPose(returnPosition, rearTarget);
        }

        if (progress < 0.96f)
        {
            var tailReviewT = SmoothStep((progress - 0.78f) / 0.18f);
            Vector3 tailReviewTarget;
            if (tailReviewT < 0.20f)
            {
                var t = SmoothStep(tailReviewT / 0.20f);
                tailReviewTarget = Lerp(aftTarget, new Vector3(0.0f, 0.64f, 3.48f), t);
            }
            else if (tailReviewT < 0.40f)
            {
                var t = SmoothStep((tailReviewT - 0.20f) / 0.20f);
                tailReviewTarget = Lerp(new Vector3(0.0f, 0.64f, 3.48f), new Vector3(-1.20f, 1.16f, 3.34f), t);
            }
            else if (tailReviewT < 0.60f)
            {
                var t = SmoothStep((tailReviewT - 0.40f) / 0.20f);
                tailReviewTarget = Lerp(new Vector3(-1.20f, 1.16f, 3.34f), new Vector3(1.20f, 1.16f, 3.34f), t);
            }
            else if (tailReviewT < 0.80f)
            {
                var t = SmoothStep((tailReviewT - 0.60f) / 0.20f);
                tailReviewTarget = Lerp(new Vector3(1.20f, 1.16f, 3.34f), new Vector3(0.0f, 2.42f, 3.34f), t);
            }
            else
            {
                var t = SmoothStep((tailReviewT - 0.80f) / 0.20f);
                tailReviewTarget = Lerp(new Vector3(0.0f, 2.42f, 3.34f), new Vector3(0.0f, 2.14f, -1.40f), t);
            }

            return new WalkthroughCameraPose(aftReview, tailReviewTarget);
        }

        var finalReviewT = SmoothStep((progress - 0.96f) / 0.04f);
        var reviewTarget = Lerp(new Vector3(0.0f, 2.14f, -1.40f), new Vector3(0.0f, 2.36f, -5.80f), finalReviewT);
        return new WalkthroughCameraPose(aftReview, reviewTarget);
    }

    private WalkthroughCameraPose CockpitWalkthroughPose(float progress)
    {
        var stairBase = new Vector3(0.0f, 1.56f, -5.82f);
        var stairTop = new Vector3(0.0f, 1.86f, -6.58f);
        var reviewStation = new Vector3(0.0f, 2.34f, -7.08f);
        var forwardTarget = new Vector3(0.0f, 2.08f, -9.88f);
        var leftTarget = new Vector3(-2.18f, 2.00f, -8.82f);
        var leftUpTarget = OrbitLookTarget(reviewStation, -Mathf.Pi / 2.0f, 0.92f, 2.95f);

        if (progress < 0.16f)
        {
            var t = SmoothStep(progress / 0.16f);
            var position = Lerp(stairBase, stairTop, t);
            var target = Lerp(new Vector3(0.0f, 1.86f, -8.10f), new Vector3(0.0f, 2.02f, -8.88f), t);
            return new WalkthroughCameraPose(position, target);
        }

        if (progress < 0.30f)
        {
            var t = SmoothStep((progress - 0.16f) / 0.14f);
            var position = Lerp(stairTop, reviewStation, t);
            var target = Lerp(new Vector3(0.0f, 2.04f, -8.85f), forwardTarget, t);
            return new WalkthroughCameraPose(position, target);
        }

        if (progress < 0.42f)
        {
            var t = SmoothStep((progress - 0.30f) / 0.12f);
            var target = Lerp(forwardTarget, leftTarget, t);
            return new WalkthroughCameraPose(reviewStation, target);
        }

        if (progress < 0.54f)
        {
            var t = SmoothStep((progress - 0.42f) / 0.12f);
            var target = Lerp(leftTarget, leftUpTarget, t);
            return new WalkthroughCameraPose(reviewStation, target);
        }

        float scanT;
        float yaw;
        float pitchOffset;
        if (progress < 0.77f)
        {
            scanT = SmoothStep((progress - 0.54f) / 0.23f);
            yaw = Mathf.Lerp(-Mathf.Pi / 2.0f, Mathf.Pi, scanT);
            pitchOffset = Mathf.Lerp(0.92f, 0.08f, scanT) + Mathf.Sin(scanT * Mathf.Pi) * 0.10f;
        }
        else if (progress < 0.85f)
        {
            yaw = Mathf.Pi;
            pitchOffset = 0.08f;
        }
        else
        {
            scanT = SmoothStep((progress - 0.85f) / 0.15f);
            yaw = Mathf.Lerp(Mathf.Pi, Mathf.Tau, scanT);
            pitchOffset = Mathf.Lerp(0.08f, 0.06f, scanT) + Mathf.Sin(scanT * Mathf.Pi) * 0.08f;
        }

        var scanTarget = OrbitLookTarget(reviewStation, yaw, pitchOffset, 2.95f);
        return new WalkthroughCameraPose(reviewStation, scanTarget);
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

    private static Vector3 OrbitLookTarget(Vector3 position, float yaw, float pitchOffset, float distance)
    {
        return new Vector3(
            position.X + Mathf.Sin(yaw) * distance,
            position.Y + pitchOffset,
            position.Z - Mathf.Cos(yaw) * distance
        );
    }

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
