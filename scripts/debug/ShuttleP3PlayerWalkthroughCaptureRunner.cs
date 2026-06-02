using Godot;
using Godot.Collections;

public partial class ShuttleP3PlayerWalkthroughCaptureRunner : Node3D
{
    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public string OutputDirectory { get; set; } = "res://reports/shuttle_p3_player_walkthrough";
    [Export] public int CaptureWidth { get; set; } = 1280;
    [Export] public int CaptureHeight { get; set; } = 720;
    [Export] public int FrameCount { get; set; } = 560;
    [Export] public int FramesPerSecond { get; set; } = 24;
    [Export] public float HoldLastFrameSeconds { get; set; } = 1.0f;
    [Export] public float SupportHeightTolerance { get; set; } = 0.55f;
    [Export] public Vector3 ShuttleOrigin { get; set; } = new(0.0f, 205.6f, 0.0f);

    private PlayerController _player = null!;
    private Camera3D _camera = null!;
    private int _frame = -1;
    private bool _captureQueued;
    private string _outputAbsolute = "";
    private string _framesAbsolute = "";
    private float _pathDistance;
    private float[] _segmentLengths = System.Array.Empty<float>();
    private float _pathLength;

    private readonly Vector3[] _localWaypoints =
    {
        new(0.0f, -2.58f, -5.55f),
        new(0.0f, -1.25f, -1.35f),
        new(0.0f, -1.34f, 2.60f),
        new(-1.62f, -1.25f, -0.55f),
        new(-2.05f, -0.32f, -1.42f),
        new(-2.04f, 0.55f, -2.25f),
        new(-1.38f, 1.35f, -3.40f),
        new(0.0f, 1.26f, -4.55f),
        new(0.0f, 1.26f, -8.50f),
        new(0.0f, 1.26f, -12.40f),
    };

    public override void _Ready()
    {
        _player = GetNode<PlayerController>(PlayerPath);
        _camera = _player.GetNode<Camera3D>("ViewPivot/Camera3D");
        _camera.Current = true;

        GetWindow().Size = new Vector2I(CaptureWidth, CaptureHeight);
        ShowTraversalVisuals(GetTree().CurrentScene ?? this);
        BuildPathMetrics();
        MovePlayerToStart();

        _outputAbsolute = ProjectSettings.GlobalizePath(OutputDirectory);
        _framesAbsolute = ProjectSettings.GlobalizePath($"{OutputDirectory}/frames");
        ResetOutputDirectory();
        WriteManifest();
        GD.Print($"Shuttle p3 player walkthrough frames will be written to: {_framesAbsolute}");
    }

    public override void _ExitTree()
    {
    }

    public override void _PhysicsProcess(double delta)
    {
        AdvancePlayerAlongPath((float)delta);
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

    private void MovePlayerToStart()
    {
        var start = ShuttleOrigin + ResolveSupportHeight(_localWaypoints[0]);
        _player.MoveToTransform(new Transform3D(Basis.Identity, start));
        _pathDistance = 0.0f;
        ApplyPlayerPathPose(0.0f);
    }

    private void BuildPathMetrics()
    {
        _segmentLengths = new float[Mathf.Max(0, _localWaypoints.Length - 1)];
        _pathLength = 0.0f;
        for (var i = 0; i < _segmentLengths.Length; i++)
        {
            var a = _localWaypoints[i];
            var b = _localWaypoints[i + 1];
            var horizontalDelta = new Vector3(b.X - a.X, 0.0f, b.Z - a.Z);
            var verticalDelta = b.Y - a.Y;
            var length = Mathf.Sqrt(horizontalDelta.LengthSquared() + verticalDelta * verticalDelta);
            _segmentLengths[i] = Mathf.Max(length, 0.001f);
            _pathLength += _segmentLengths[i];
        }
    }

    private void AdvancePlayerAlongPath(float delta)
    {
        if (_pathLength <= 0.0f)
        {
            return;
        }

        var holdStartDistance = _pathLength;
        var holdFrames = Mathf.RoundToInt(HoldLastFrameSeconds * FramesPerSecond);
        var motionFrames = Mathf.Max(1, FrameCount - holdFrames);
        var targetDistance = Mathf.Min(_pathLength, _pathLength * Mathf.Clamp((float)_frame / motionFrames, 0.0f, 1.0f));
        var maxAdvance = 4.2f * delta;
        _pathDistance = Mathf.Min(targetDistance, _pathDistance + maxAdvance);

        if (_frame >= motionFrames)
            _pathDistance = holdStartDistance;

        ApplyPlayerPathPose(_pathDistance);
    }

    private void ApplyPlayerPathPose(float distance)
    {
        var localPosition = SamplePath(distance);
        var lookAhead = SamplePath(Mathf.Min(_pathLength, distance + 0.85f));
        localPosition = ResolveSupportHeight(localPosition);
        lookAhead = ResolveSupportHeight(lookAhead);

        var worldPosition = ShuttleOrigin + localPosition;
        var worldLookAhead = ShuttleOrigin + lookAhead;
        var forward = worldLookAhead - worldPosition;
        forward.Y = 0.0f;
        if (forward.LengthSquared() < 0.0001f)
            forward = -_player.GlobalTransform.Basis.Z;
        forward = forward.Normalized();

        var right = forward.Cross(Vector3.Up).Normalized();
        var backward = -forward;
        var transform = _player.GlobalTransform;
        transform.Basis = new Basis(right, Vector3.Up, backward).Orthonormalized();
        transform.Origin = worldPosition;
        _player.MoveToTransform(transform);
    }

    private Vector3 SamplePath(float distance)
    {
        if (_localWaypoints.Length == 0)
            return Vector3.Zero;
        if (_localWaypoints.Length == 1 || distance <= 0.0f)
            return _localWaypoints[0];

        var remaining = distance;
        for (var i = 0; i < _segmentLengths.Length; i++)
        {
            if (remaining <= _segmentLengths[i])
            {
                var t = Mathf.Clamp(remaining / _segmentLengths[i], 0.0f, 1.0f);
                return _localWaypoints[i].Lerp(_localWaypoints[i + 1], SmoothStep(t));
            }
            remaining -= _segmentLengths[i];
        }

        return _localWaypoints[^1];
    }

    private Vector3 ResolveSupportHeight(Vector3 localPosition)
    {
        var world = ShuttleOrigin + localPosition;
        var from = world + Vector3.Up * 3.0f;
        var to = world + Vector3.Down * 3.0f;
        var query = PhysicsRayQueryParameters3D.Create(from, to, 1u << 7);
        query.CollideWithAreas = false;
        query.CollideWithBodies = true;
        var hit = GetWorld3D().DirectSpaceState.IntersectRay(query);
        if (hit.Count == 0)
            return localPosition;

        var hitPosition = hit["position"].AsVector3();
        var resolvedRootY = hitPosition.Y - ShuttleOrigin.Y + 0.9f;
        if (Mathf.Abs(resolvedRootY - localPosition.Y) > SupportHeightTolerance)
            return localPosition;

        return new Vector3(localPosition.X, resolvedRootY, localPosition.Z);
    }

    private static float SmoothStep(float value)
    {
        return value * value * (3.0f - 2.0f * value);
    }

    private void QueueNextFrame()
    {
        _frame++;
        if (_frame >= FrameCount)
        {
            GD.Print("Shuttle p3 player walkthrough capture complete.");
            GetTree().Quit(0);
            return;
        }

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
            GD.PushError($"Failed to open shuttle p3 player walkthrough frame for writing: {framePath}");
            GetTree().Quit(1);
            return;
        }

        file.StoreBuffer(image.GetData());
        GD.Print($"Saved shuttle p3 player walkthrough frame {framePath}");
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
}
