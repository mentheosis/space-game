using Godot;
using Godot.Collections;
using System.Collections.Generic;

public partial class MX01WalkthroughReplayCaptureRunner : Node
{
    private const int FloatsPerSample = 15;

    [Export] public NodePath PlayerPath { get; set; } = "../MX01PlayableInspection/Player";
    [Export] public NodePath CameraPath { get; set; } = "../MX01PlayableInspection/Player/ViewPivot/Camera3D";
    [Export] public string ManifestPath { get; set; } = "res://ships/MX01/reports/walkthrough_paths/mx01_walkthrough_20260606T091217.json";
    [Export] public string OutputDirectory { get; set; } = "res://ships/MX01/reports/walkthrough_captures/mx01_walkthrough_20260606T091217";
    [Export] public int CaptureWidth { get; set; } = 960;
    [Export] public int CaptureHeight { get; set; } = 540;
    [Export] public int FramesPerSecond { get; set; } = 30;
    [Export] public float HoldLastFrameSeconds { get; set; } = 1.0f;

    private readonly List<Sample> _samples = new();
    private PlayerController _player = null!;
    private Camera3D _camera = null!;
    private string _outputAbsolute = string.Empty;
    private string _framesAbsolute = string.Empty;
    private int _frame = -1;
    private int _frameCount;
    private float _durationSeconds;
    private bool _captureQueued;

    public override void _Ready()
    {
        ApplyEnvironmentOverrides();
        _player = GetNode<PlayerController>(PlayerPath);
        _camera = GetNode<Camera3D>(CameraPath);
        _camera.Current = true;
        _player.SetPlayerCameraActive(true);

        LoadSamples();
        _durationSeconds = _samples.Count == 0 ? 0.0f : _samples[^1].TimeSeconds;
        _frameCount = Mathf.Max(1, Mathf.CeilToInt(_durationSeconds * FramesPerSecond) + 1);

        var window = GetWindow();
        window.Size = new Vector2I(CaptureWidth, CaptureHeight);

        _outputAbsolute = ProjectSettings.GlobalizePath(OutputDirectory);
        _framesAbsolute = ProjectSettings.GlobalizePath($"{OutputDirectory}/frames");
        ResetOutputDirectory();
        WriteCaptureManifest();
        GD.Print($"MX01 walkthrough replay capture frames will be written to: {_framesAbsolute}");
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

    private void ApplyEnvironmentOverrides()
    {
        var manifestOverride = OS.GetEnvironment("MX01_WALKTHROUGH_MANIFEST");
        if (!string.IsNullOrWhiteSpace(manifestOverride))
        {
            ManifestPath = manifestOverride;
        }

        var outputOverride = OS.GetEnvironment("MX01_WALKTHROUGH_OUTPUT");
        if (!string.IsNullOrWhiteSpace(outputOverride))
        {
            OutputDirectory = outputOverride;
        }
    }

    private void LoadSamples()
    {
        if (!Godot.FileAccess.FileExists(ManifestPath))
        {
            GD.PushError($"Missing MX01 walkthrough manifest: {ManifestPath}");
            GetTree().Quit(1);
            return;
        }

        var parsed = Json.ParseString(Godot.FileAccess.GetFileAsString(ManifestPath));
        if (parsed.VariantType != Variant.Type.Dictionary)
        {
            GD.PushError($"Invalid MX01 walkthrough manifest: {ManifestPath}");
            GetTree().Quit(1);
            return;
        }

        var manifest = parsed.AsGodotDictionary<string, Variant>();
        var format = manifest.TryGetValue("format", out var formatValue) ? formatValue.AsString() : "";
        if (format != "mx_path_f32_v1")
        {
            GD.PushError($"Unsupported MX01 walkthrough format '{format}' in {ManifestPath}");
            GetTree().Quit(1);
            return;
        }

        var sampleFile = manifest.TryGetValue("sample_file", out var sampleFileValue)
            ? sampleFileValue.AsString()
            : "";
        var samplePath = $"{ManifestPath.GetBaseDir()}/{sampleFile}";
        if (!Godot.FileAccess.FileExists(samplePath))
        {
            GD.PushError($"Missing MX01 walkthrough sample file: {samplePath}");
            GetTree().Quit(1);
            return;
        }

        using var sampleAccess = Godot.FileAccess.Open(samplePath, Godot.FileAccess.ModeFlags.Read);
        if (sampleAccess is null)
        {
            GD.PushError($"Unable to open MX01 walkthrough sample file: {samplePath}");
            GetTree().Quit(1);
            return;
        }

        while (sampleAccess.GetPosition() + FloatsPerSample * sizeof(float) <= sampleAccess.GetLength())
        {
            _samples.Add(ReadSample(sampleAccess));
        }

        if (_samples.Count == 0)
        {
            GD.PushError($"MX01 walkthrough has no samples: {samplePath}");
            GetTree().Quit(1);
        }
    }

    private static Sample ReadSample(Godot.FileAccess file)
    {
        var time = file.GetFloat();
        var playerPosition = ReadVector3(file);
        var playerRotation = ReadQuaternion(file);
        var cameraPosition = ReadVector3(file);
        var cameraRotation = ReadQuaternion(file);
        return new Sample(time, playerPosition, playerRotation, cameraPosition, cameraRotation);
    }

    private static Vector3 ReadVector3(Godot.FileAccess file)
    {
        return new Vector3(file.GetFloat(), file.GetFloat(), file.GetFloat());
    }

    private static Quaternion ReadQuaternion(Godot.FileAccess file)
    {
        return new Quaternion(file.GetFloat(), file.GetFloat(), file.GetFloat(), file.GetFloat()).Normalized();
    }

    private void QueueNextFrame()
    {
        _frame++;
        if (_frame >= _frameCount)
        {
            GD.Print("MX01 walkthrough replay capture complete.");
            GetTree().Quit(0);
            return;
        }

        var timeSeconds = Mathf.Min(_durationSeconds, _frame / (float)FramesPerSecond);
        ApplyPose(SampleAt(timeSeconds));
        _captureQueued = true;
    }

    private Sample SampleAt(float timeSeconds)
    {
        if (_samples.Count == 1 || timeSeconds <= _samples[0].TimeSeconds)
        {
            return _samples[0];
        }

        for (var index = 1; index < _samples.Count; index++)
        {
            var next = _samples[index];
            if (timeSeconds > next.TimeSeconds)
            {
                continue;
            }

            var previous = _samples[index - 1];
            var span = Mathf.Max(0.0001f, next.TimeSeconds - previous.TimeSeconds);
            var t = Mathf.Clamp((timeSeconds - previous.TimeSeconds) / span, 0.0f, 1.0f);
            return Sample.Lerp(previous, next, t);
        }

        return _samples[^1];
    }

    private void ApplyPose(Sample sample)
    {
        _player.MoveToTransform(new Transform3D(new Basis(sample.PlayerRotation), sample.PlayerPosition));
        _camera.GlobalTransform = new Transform3D(new Basis(sample.CameraRotation), sample.CameraPosition);
        _camera.Current = true;
    }

    private void SaveCurrentFrame()
    {
        var texture = GetViewport().GetTexture();
        if (texture is null)
        {
            GD.PushError("Viewport texture is unavailable. Run MX01 walkthrough replay capture with a real renderer.");
            GetTree().Quit(1);
            return;
        }

        var image = texture.GetImage();
        if (image is null)
        {
            GD.PushError("Viewport image is unavailable. Run MX01 walkthrough replay capture with a real renderer.");
            GetTree().Quit(1);
            return;
        }

        image.Resize(CaptureWidth, CaptureHeight, Image.Interpolation.Lanczos);
        image.Convert(Image.Format.Rgb8);

        var framePath = $"{_framesAbsolute}/frame_{_frame:0000}.rgb";
        using var file = Godot.FileAccess.Open(framePath, Godot.FileAccess.ModeFlags.Write);
        if (file is null)
        {
            GD.PushError($"Failed to open MX01 walkthrough replay frame for writing: {framePath}");
            GetTree().Quit(1);
            return;
        }

        file.StoreBuffer(image.GetData());
    }

    private void ResetOutputDirectory()
    {
        if (DirAccess.DirExistsAbsolute(_framesAbsolute))
        {
            var dir = DirAccess.Open(_framesAbsolute);
            if (dir is not null)
            {
                dir.ListDirBegin();
                var file = dir.GetNext();
                while (!string.IsNullOrEmpty(file))
                {
                    if (!dir.CurrentIsDir())
                    {
                        dir.Remove(file);
                    }
                    file = dir.GetNext();
                }
                dir.ListDirEnd();
            }
        }

        DirAccess.MakeDirRecursiveAbsolute(_framesAbsolute);
    }

    private void WriteCaptureManifest()
    {
        var payload = new Dictionary
        {
            ["source_manifest"] = ManifestPath,
            ["width"] = CaptureWidth,
            ["height"] = CaptureHeight,
            ["frame_count"] = _frameCount,
            ["fps"] = FramesPerSecond,
            ["hold_last_seconds"] = HoldLastFrameSeconds,
            ["frames_directory"] = "frames",
        };
        using var file = Godot.FileAccess.Open($"{_outputAbsolute}/manifest.json", Godot.FileAccess.ModeFlags.Write);
        file?.StoreString(Json.Stringify(payload, "  ") + "\n");
    }

    private readonly record struct Sample(
        float TimeSeconds,
        Vector3 PlayerPosition,
        Quaternion PlayerRotation,
        Vector3 CameraPosition,
        Quaternion CameraRotation)
    {
        public static Sample Lerp(Sample a, Sample b, float t)
        {
            return new Sample(
                Mathf.Lerp(a.TimeSeconds, b.TimeSeconds, t),
                a.PlayerPosition.Lerp(b.PlayerPosition, t),
                a.PlayerRotation.Slerp(b.PlayerRotation, t).Normalized(),
                a.CameraPosition.Lerp(b.CameraPosition, t),
                a.CameraRotation.Slerp(b.CameraRotation, t).Normalized());
        }
    }
}
