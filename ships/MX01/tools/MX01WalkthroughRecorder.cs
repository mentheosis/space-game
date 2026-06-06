using Godot;
using Godot.Collections;

public partial class MX01WalkthroughRecorder : Node
{
    private const string Format = "mx_path_f32_v1";
    private const int FloatsPerSample = 15;

    [Export] public NodePath PlayerPath { get; set; } = "../Player";
    [Export] public NodePath CameraPath { get; set; } = "../Player/ViewPivot/Camera3D";
    [Export] public string ToggleAction { get; set; } = "record_walkthrough";
    [Export] public string OutputDirectory { get; set; } = "res://ships/MX01/reports/walkthrough_paths";
    [Export] public string SceneResourcePath { get; set; } = "res://ships/MX01/generated/scenes/mx01_playable_inspection.tscn";
    [Export] public float SampleRateHz { get; set; } = 30.0f;
    [Export] public float MinPositionDelta { get; set; } = 0.01f;
    [Export] public float MinRotationDeltaDegrees { get; set; } = 0.1f;
    [Export] public bool SkipUnchangedSamples { get; set; } = false;

    private Node3D _player = null!;
    private Camera3D _camera = null!;
    private Godot.FileAccess? _sampleFile;
    private string _activeManifestPath = string.Empty;
    private string _activeSamplePath = string.Empty;
    private string _activeSampleFileName = string.Empty;
    private double _elapsed;
    private double _sampleAccumulator;
    private int _sampleCount;
    private bool _recording;
    private Vector3 _lastPlayerPosition;
    private Quaternion _lastPlayerRotation = Quaternion.Identity;
    private Vector3 _lastCameraPosition;
    private Quaternion _lastCameraRotation = Quaternion.Identity;
    private bool _hasLastSample;

    public override void _Ready()
    {
        _player = GetNode<Node3D>(PlayerPath);
        _camera = GetNode<Camera3D>(CameraPath);
        EnsureToggleActionExists();
        GD.Print($"MX01 walkthrough recorder ready. Press {ToggleAction} to start/stop recording.");
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (@event is InputEventKey { Echo: true })
        {
            return;
        }

        if (@event.IsActionPressed(ToggleAction))
        {
            if (_recording)
            {
                StopRecording();
            }
            else
            {
                StartRecording();
            }

            GetViewport().SetInputAsHandled();
        }
    }

    public override void _PhysicsProcess(double delta)
    {
        if (!_recording)
        {
            return;
        }

        _elapsed += delta;
        _sampleAccumulator += delta;
        var sampleInterval = 1.0 / Mathf.Max(1.0f, SampleRateHz);
        while (_sampleAccumulator >= sampleInterval)
        {
            _sampleAccumulator -= sampleInterval;
            WriteSample((float)(_elapsed - _sampleAccumulator));
        }
    }

    public override void _ExitTree()
    {
        if (_recording)
        {
            StopRecording();
        }
    }

    private void StartRecording()
    {
        var absoluteOutputDirectory = ProjectSettings.GlobalizePath(OutputDirectory);
        DirAccess.MakeDirRecursiveAbsolute(absoluteOutputDirectory);

        var timestamp = Time.GetDatetimeStringFromSystem(true).Replace(":", "").Replace("-", "");
        var baseName = $"mx01_walkthrough_{timestamp}";
        _activeSampleFileName = $"{baseName}.mxpath";
        _activeSamplePath = $"{absoluteOutputDirectory}/{_activeSampleFileName}";
        _activeManifestPath = $"{absoluteOutputDirectory}/{baseName}.json";
        _sampleFile = Godot.FileAccess.Open(_activeSamplePath, Godot.FileAccess.ModeFlags.Write);
        if (_sampleFile is null)
        {
            GD.PushError($"Unable to open MX01 walkthrough sample file: {_activeSamplePath}");
            return;
        }

        _elapsed = 0.0;
        _sampleAccumulator = 0.0;
        _sampleCount = 0;
        _hasLastSample = false;
        _recording = true;
        WriteSample(0.0f);
        GD.Print($"MX01 walkthrough recording started: {_activeManifestPath}");
    }

    private void StopRecording()
    {
        _recording = false;
        _sampleFile?.Close();
        _sampleFile = null;
        WriteManifest();
        GD.Print($"MX01 walkthrough recording saved: {_activeManifestPath} ({_sampleCount} samples)");
    }

    private void WriteSample(float timeSeconds)
    {
        if (_sampleFile is null)
        {
            return;
        }

        var playerTransform = _player.GlobalTransform;
        var cameraTransform = _camera.GlobalTransform;
        var playerPosition = playerTransform.Origin;
        var cameraPosition = cameraTransform.Origin;
        var playerRotation = playerTransform.Basis.Orthonormalized().GetRotationQuaternion();
        var cameraRotation = cameraTransform.Basis.Orthonormalized().GetRotationQuaternion();

        if (SkipUnchangedSamples && _hasLastSample && !SampleChanged(playerPosition, playerRotation, cameraPosition, cameraRotation))
        {
            return;
        }

        StoreFloat(timeSeconds);
        StoreVector3(playerPosition);
        StoreQuaternion(playerRotation);
        StoreVector3(cameraPosition);
        StoreQuaternion(cameraRotation);

        _lastPlayerPosition = playerPosition;
        _lastPlayerRotation = playerRotation;
        _lastCameraPosition = cameraPosition;
        _lastCameraRotation = cameraRotation;
        _hasLastSample = true;
        _sampleCount += 1;
    }

    private bool SampleChanged(Vector3 playerPosition, Quaternion playerRotation, Vector3 cameraPosition, Quaternion cameraRotation)
    {
        if (playerPosition.DistanceTo(_lastPlayerPosition) >= MinPositionDelta)
        {
            return true;
        }

        if (cameraPosition.DistanceTo(_lastCameraPosition) >= MinPositionDelta)
        {
            return true;
        }

        var minRotationDelta = Mathf.DegToRad(MinRotationDeltaDegrees);
        return QuaternionAngle(playerRotation, _lastPlayerRotation) >= minRotationDelta
            || QuaternionAngle(cameraRotation, _lastCameraRotation) >= minRotationDelta;
    }

    private static float QuaternionAngle(Quaternion a, Quaternion b)
    {
        var dot = Mathf.Abs(a.Dot(b));
        return 2.0f * Mathf.Acos(Mathf.Clamp(dot, 0.0f, 1.0f));
    }

    private void StoreVector3(Vector3 value)
    {
        StoreFloat(value.X);
        StoreFloat(value.Y);
        StoreFloat(value.Z);
    }

    private void StoreQuaternion(Quaternion value)
    {
        StoreFloat(value.X);
        StoreFloat(value.Y);
        StoreFloat(value.Z);
        StoreFloat(value.W);
    }

    private void StoreFloat(float value)
    {
        _sampleFile?.StoreFloat(value);
    }

    private void WriteManifest()
    {
        var payload = new Dictionary
        {
            ["version"] = 1,
            ["ship"] = "MX01",
            ["scene"] = SceneResourcePath,
            ["format"] = Format,
            ["sample_file"] = _activeSampleFileName,
            ["sample_count"] = _sampleCount,
            ["sample_rate_hz"] = SampleRateHz,
            ["floats_per_sample"] = FloatsPerSample,
            ["bytes_per_sample"] = FloatsPerSample * sizeof(float),
            ["duration_seconds"] = _elapsed,
            ["coordinate_space"] = "global",
            ["channels"] = new Array<string>
            {
                "time_seconds",
                "player_position_x",
                "player_position_y",
                "player_position_z",
                "player_rotation_x",
                "player_rotation_y",
                "player_rotation_z",
                "player_rotation_w",
                "camera_position_x",
                "camera_position_y",
                "camera_position_z",
                "camera_rotation_x",
                "camera_rotation_y",
                "camera_rotation_z",
                "camera_rotation_w",
            },
        };

        using var manifest = Godot.FileAccess.Open(_activeManifestPath, Godot.FileAccess.ModeFlags.Write);
        manifest?.StoreString(Json.Stringify(payload, "  ") + "\n");
    }

    private void EnsureToggleActionExists()
    {
        if (InputMap.HasAction(ToggleAction))
        {
            return;
        }

        InputMap.AddAction(ToggleAction);
        var key = new InputEventKey
        {
            Keycode = Key.P,
        };
        InputMap.ActionAddEvent(ToggleAction, key);
    }
}
