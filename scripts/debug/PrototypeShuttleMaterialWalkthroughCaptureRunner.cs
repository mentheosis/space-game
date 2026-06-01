using Godot;
using Godot.Collections;

public partial class PrototypeShuttleMaterialWalkthroughCaptureRunner : Node3D
{
    [Export] public string OutputDirectory { get; set; } = "res://reports/prototype_shuttle_material_walkthrough";
    [Export] public int CaptureWidth { get; set; } = 1280;
    [Export] public int CaptureHeight { get; set; } = 720;
    [Export] public int FrameCount { get; set; } = 480;
    [Export] public int FramesPerSecond { get; set; } = 24;
    [Export] public float HoldLastFrameSeconds { get; set; } = 1.0f;

    private const string ExteriorScenePath = "res://assets/models/ship/prototype_shuttle/prototype_shuttle_exterior.glb";
    private const string InteriorScenePath = "res://assets/models/ship/prototype_shuttle/prototype_shuttle_interior.glb";

    private Camera3D _camera = null!;
    private int _frame = -1;
    private bool _captureQueued;
    private string _outputAbsolute = "";
    private string _framesAbsolute = "";

    public override void _Ready()
    {
        LoadPackageScene(ExteriorScenePath, "PrototypeShuttleExterior");
        var interior = LoadPackageScene(InteriorScenePath, "PrototypeShuttleInterior");
        HideReviewOnlyNodes(interior);

        GetWindow().Size = new Vector2I(CaptureWidth, CaptureHeight);
        _camera = new Camera3D
        {
            Name = "PrototypeShuttleMaterialWalkthroughCamera",
            Current = true,
            Near = 0.02f,
            Far = 150.0f,
            Fov = 78.0f
        };
        AddChild(_camera);

        PrototypeShuttleLightingRig.AddInteriorPracticalLights(this);
        _outputAbsolute = ProjectSettings.GlobalizePath(OutputDirectory);
        _framesAbsolute = ProjectSettings.GlobalizePath($"{OutputDirectory}/frames");
        ResetOutputDirectory();
        WriteManifest();
        GD.Print($"Prototype shuttle material walkthrough frames will be written to: {_framesAbsolute}");
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
            if (child is Node3D child3D
                && (name.StartsWith("VOLUME_") || name.Contains("ScaleBlockout") || name.Contains("ReferenceStrip")))
            {
                child3D.Visible = false;
            }

            HideReviewOnlyNodes(child);
        }
    }

    private void QueueNextFrame()
    {
        _frame++;
        if (_frame >= FrameCount)
        {
            GD.Print("Prototype shuttle material walkthrough capture complete.");
            GetTree().Quit(0);
            return;
        }

        var progress = FrameCount <= 1 ? 1.0f : _frame / (float)(FrameCount - 1);
        var pose = WalkthroughPose(progress);
        var lookDirection = (pose.Target - pose.Position).Normalized();
        var cameraUp = Mathf.Abs(lookDirection.Dot(Vector3.Up)) > 0.98f ? Vector3.Back : Vector3.Up;
        _camera.GlobalTransform = new Transform3D(Basis.Identity, pose.Position).LookingAt(pose.Target, cameraUp);
        _camera.Current = true;
        _captureQueued = true;
    }

    private WalkthroughCameraPose WalkthroughPose(float progress)
    {
        var keyframes = new[]
        {
            new WalkthroughKeyframe(0.00f, new Vector3(0.0f, -2.18f, -4.00f), new Vector3(0.0f, -1.10f, -1.45f)),
            new WalkthroughKeyframe(0.10f, new Vector3(0.0f, -1.82f, -2.70f), new Vector3(-0.85f, -1.06f, -0.35f)),
            new WalkthroughKeyframe(0.21f, new Vector3(0.0f, -1.22f, -0.48f), new Vector3(0.95f, -0.80f, 1.45f)),
            new WalkthroughKeyframe(0.34f, new Vector3(0.0f, -0.72f, 2.35f), new Vector3(-2.65f, -0.08f, 3.85f)),
            new WalkthroughKeyframe(0.46f, new Vector3(0.0f, -0.42f, 4.65f), new Vector3(2.55f, 0.10f, 5.55f)),
            new WalkthroughKeyframe(0.57f, new Vector3(-1.15f, -0.08f, 2.38f), new Vector3(-2.10f, 0.70f, 0.15f)),
            new WalkthroughKeyframe(0.67f, new Vector3(-1.55f, 0.72f, 0.20f), new Vector3(-1.92f, 1.35f, -2.15f)),
            new WalkthroughKeyframe(0.76f, new Vector3(-1.42f, 1.88f, -3.05f), new Vector3(0.0f, 1.40f, -6.65f)),
            new WalkthroughKeyframe(0.86f, new Vector3(-0.62f, 1.90f, -7.50f), new Vector3(0.0f, 1.45f, -11.50f)),
            new WalkthroughKeyframe(0.93f, new Vector3(0.0f, 1.88f, -11.25f), new Vector3(-1.35f, 1.48f, -13.35f)),
            new WalkthroughKeyframe(0.975f, new Vector3(0.22f, 1.88f, -11.45f), new Vector3(1.30f, 1.54f, -13.25f)),
            new WalkthroughKeyframe(1.00f, new Vector3(0.0f, 1.88f, -11.35f), new Vector3(0.0f, 1.50f, -14.55f)),
        };

        var pose = PoseFromKeyframes(keyframes, progress);
        var walkBob = Mathf.Sin(progress * Mathf.Tau * 7.5f) * 0.018f;
        pose = new WalkthroughCameraPose(pose.Position + Vector3.Up * walkBob, pose.Target + Vector3.Up * walkBob);
        return pose;
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
            return new WalkthroughCameraPose(Lerp(from.Position, to.Position, local), Lerp(from.Target, to.Target, local));
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
            GD.PushError($"Failed to open material walkthrough frame for writing: {framePath}");
            GetTree().Quit(1);
            return;
        }

        file.StoreBuffer(image.GetData());
        GD.Print($"Saved material walkthrough frame {framePath}");
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
