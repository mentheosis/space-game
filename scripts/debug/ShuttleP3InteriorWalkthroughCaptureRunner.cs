using Godot;
using Godot.Collections;

public partial class ShuttleP3InteriorWalkthroughCaptureRunner : Node3D
{
    [Export] public string OutputDirectory { get; set; } = "res://reports/shuttle_p3_interior_walkthrough";
    [Export] public int CaptureWidth { get; set; } = 1280;
    [Export] public int CaptureHeight { get; set; } = 720;
    [Export] public int FrameCount { get; set; } = 420;
    [Export] public int FramesPerSecond { get; set; } = 24;
    [Export] public float HoldLastFrameSeconds { get; set; } = 1.0f;
    [Export] public Vector3 ShuttleOrigin { get; set; } = new(0.0f, 205.6f, 0.0f);

    private Camera3D _camera = null!;
    private int _frame = -1;
    private bool _captureQueued;
    private string _outputAbsolute = "";
    private string _framesAbsolute = "";

    public override void _Ready()
    {
        GetWindow().Size = new Vector2I(CaptureWidth, CaptureHeight);
        _camera = new Camera3D
        {
            Name = "ShuttleP3InteriorWalkthroughCamera",
            Current = true,
            Near = 0.02f,
            Far = 180.0f,
            Fov = 78.0f
        };
        AddChild(_camera);

        ShowTraversalVisuals(GetTree().CurrentScene ?? this);
        _outputAbsolute = ProjectSettings.GlobalizePath(OutputDirectory);
        _framesAbsolute = ProjectSettings.GlobalizePath($"{OutputDirectory}/frames");
        ResetOutputDirectory();
        WriteManifest();
        GD.Print($"Shuttle p3 interior walkthrough frames will be written to: {_framesAbsolute}");
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
            GD.Print("Shuttle p3 interior walkthrough capture complete.");
            GetTree().Quit(0);
            return;
        }

        var progress = FrameCount <= 1 ? 1.0f : _frame / (float)(FrameCount - 1);
        var pose = WalkthroughPose(progress);
        var position = ShuttleOrigin + pose.Position;
        var target = ShuttleOrigin + pose.Target;
        var lookDirection = (target - position).Normalized();
        var cameraUp = Mathf.Abs(lookDirection.Dot(Vector3.Up)) > 0.98f ? Vector3.Back : Vector3.Up;
        _camera.GlobalTransform = new Transform3D(Basis.Identity, position).LookingAt(target, cameraUp);
        _camera.Current = true;
        _captureQueued = true;
    }

    private static WalkthroughCameraPose WalkthroughPose(float progress)
    {
        var keyframes = new[]
        {
            new WalkthroughKeyframe(0.00f, new Vector3(0.0f, -2.15f, -6.6f), new Vector3(0.0f, -2.45f, -3.3f)),
            new WalkthroughKeyframe(0.08f, new Vector3(0.0f, -1.25f, -3.0f), new Vector3(0.0f, -1.8f, 0.3f)),
            new WalkthroughKeyframe(0.18f, new Vector3(0.0f, -0.70f, 0.8f), new Vector3(-2.3f, -0.65f, 3.8f)),
            new WalkthroughKeyframe(0.28f, new Vector3(0.0f, -0.70f, 3.9f), new Vector3(2.3f, -0.55f, 5.6f)),
            new WalkthroughKeyframe(0.38f, new Vector3(-1.45f, -0.35f, -0.8f), new Vector3(-2.05f, 0.25f, -2.5f)),
            new WalkthroughKeyframe(0.50f, new Vector3(-1.55f, 0.90f, -2.55f), new Vector3(-0.35f, 1.20f, -3.65f)),
            new WalkthroughKeyframe(0.60f, new Vector3(0.0f, 1.55f, -3.95f), new Vector3(0.0f, 1.25f, -6.4f)),
            new WalkthroughKeyframe(0.72f, new Vector3(0.0f, 1.55f, -7.6f), new Vector3(0.0f, 1.35f, -11.0f)),
            new WalkthroughKeyframe(0.82f, new Vector3(0.0f, 1.55f, -11.6f), new Vector3(-1.25f, 1.15f, -14.0f)),
            new WalkthroughKeyframe(0.90f, new Vector3(0.0f, 1.55f, -11.6f), new Vector3(1.25f, 1.15f, -14.0f)),
            new WalkthroughKeyframe(0.96f, new Vector3(0.0f, 1.55f, -11.6f), new Vector3(0.0f, 1.10f, -15.5f)),
            new WalkthroughKeyframe(1.00f, new Vector3(0.0f, 1.55f, -11.6f), new Vector3(0.0f, 1.10f, -15.5f)),
        };

        var pose = PoseFromKeyframes(keyframes, progress);
        var walkBob = Mathf.Sin(progress * Mathf.Tau * 5.5f) * 0.012f;
        return new WalkthroughCameraPose(pose.Position + Vector3.Up * walkBob, pose.Target + Vector3.Up * walkBob);
    }

    private static WalkthroughCameraPose PoseFromKeyframes(WalkthroughKeyframe[] keyframes, float progress)
    {
        if (progress <= keyframes[0].Time)
        {
            return new WalkthroughCameraPose(keyframes[0].Position, keyframes[0].Target);
        }

        for (var index = 0; index < keyframes.Length - 1; index++)
        {
            var from = keyframes[index];
            var to = keyframes[index + 1];
            if (progress > to.Time)
            {
                continue;
            }

            var local = SmoothStep((progress - from.Time) / (to.Time - from.Time));
            return new WalkthroughCameraPose(from.Position.Lerp(to.Position, local), from.Target.Lerp(to.Target, local));
        }

        var last = keyframes[^1];
        return new WalkthroughCameraPose(last.Position, last.Target);
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
            GD.PushError($"Failed to open shuttle p3 walkthrough frame for writing: {framePath}");
            GetTree().Quit(1);
            return;
        }

        file.StoreBuffer(image.GetData());
        GD.Print($"Saved shuttle p3 walkthrough frame {framePath}");
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
        using var file = Godot.FileAccess.Open($"{_outputAbsolute}/manifest.json", Godot.FileAccess.ModeFlags.Write);
        file?.StoreString(Json.Stringify(payload, "\t") + "\n");
    }

    private static void ShowTraversalVisuals(Node node)
    {
        if (node is Node3D node3D && node.Name == "TraversalCollisionVisual")
        {
            node3D.Visible = true;
        }

        foreach (var child in node.GetChildren())
        {
            ShowTraversalVisuals(child);
        }
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

    private readonly struct WalkthroughKeyframe
    {
        public readonly float Time;
        public readonly Vector3 Position;
        public readonly Vector3 Target;

        public WalkthroughKeyframe(float time, Vector3 position, Vector3 target)
        {
            Time = time;
            Position = position;
            Target = target;
        }
    }
}
