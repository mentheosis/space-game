using Godot;
using Godot.Collections;

public partial class CargoCranePlayerWalkthroughCaptureRunner : Node3D
{
    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public string OutputDirectory { get; set; } = "res://reports/cargo_crane_player_walkthrough";
    [Export] public int CaptureWidth { get; set; } = 1280;
    [Export] public int CaptureHeight { get; set; } = 720;
    [Export] public int FrameCount { get; set; } = 900;
    [Export] public int FramesPerSecond { get; set; } = 24;
    [Export] public float HoldLastFrameSeconds { get; set; } = 1.0f;
    [Export] public float SupportHeightTolerance { get; set; } = 1.25f;
    [Export] public Vector3 ShipOrigin { get; set; } = new(0.0f, 214.06f, 0.0f);

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
        new(-16.0f, -6.8f, -55.0f),
        new(0.0f, -6.8f, -55.0f),
        new(0.0f, -6.8f, -42.0f),
        new(-10.0f, -6.8f, -44.0f),
        new(-12.0f, -4.8f, -42.0f),
        new(-12.0f, -2.4f, -39.0f),
        new(-8.0f, 0.0f, -37.0f),
        new(-4.0f, 1.2f, -39.0f),
        new(0.0f, 1.2f, -42.0f),
        new(0.0f, 7.2f, -29.0f),
        new(0.0f, 7.2f, 0.0f),
        new(0.0f, 7.2f, 29.0f),
        new(0.0f, 5.6f, 45.0f),
        new(0.0f, 5.6f, 52.0f),
        new(-4.2f, 2.0f, 55.0f),
        new(4.2f, -2.5f, 58.5f),
        new(0.0f, -8.0f, 64.0f),
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
        GD.Print($"CargoCrane player walkthrough frames will be written to: {_framesAbsolute}");
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
        var start = ShipOrigin + ResolveSupportHeight(_localWaypoints[0]);
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
        var maxAdvance = 6.5f * delta;
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

        var worldPosition = ShipOrigin + localPosition;
        var worldLookAhead = ShipOrigin + lookAhead;
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
        var world = ShipOrigin + localPosition;
        var from = world + Vector3.Up * 3.0f;
        var to = world + Vector3.Down * 3.0f;
        var query = PhysicsRayQueryParameters3D.Create(from, to, 1u << 7);
        query.CollideWithAreas = false;
        query.CollideWithBodies = true;
        var hit = GetWorld3D().DirectSpaceState.IntersectRay(query);
        if (hit.Count == 0)
            return localPosition;

        var hitPosition = hit["position"].AsVector3();
        var resolvedRootY = hitPosition.Y - ShipOrigin.Y + 0.9f;
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
            GD.Print("CargoCrane player walkthrough capture complete.");
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
            GD.PushError($"Failed to open cargo crane player walkthrough frame for writing: {framePath}");
            GetTree().Quit(1);
            return;
        }

        file.StoreBuffer(image.GetData());
        GD.Print($"Saved cargo crane player walkthrough frame {framePath}");
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
