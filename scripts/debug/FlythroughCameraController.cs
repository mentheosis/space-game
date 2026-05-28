using Godot;

public partial class FlythroughCameraController : Camera3D
{
    [Export] public float MoveSpeed { get; set; } = 8.0f;
    [Export] public float FastMultiplier { get; set; } = 4.0f;
    [Export] public float MouseSensitivity { get; set; } = 0.0025f;
    [Export] public NodePath ToggleTargetPath { get; set; } = "../PrototypeShuttleDebugLoader/PrototypeShuttleBlockout/Interior";

    private float _yaw;
    private float _pitch;
    private Node3D? _toggleTarget;

    public override void _Ready()
    {
        Current = true;
        _yaw = Rotation.Y;
        _pitch = Rotation.X;
        Input.MouseMode = Input.MouseModeEnum.Captured;
        _toggleTarget = GetNodeOrNull<Node3D>(ToggleTargetPath);
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (@event is InputEventKey keyEvent && keyEvent.Pressed && !keyEvent.Echo && keyEvent.Keycode == Key.Escape)
        {
            Input.MouseMode = Input.MouseMode == Input.MouseModeEnum.Captured
                ? Input.MouseModeEnum.Visible
                : Input.MouseModeEnum.Captured;
            GetViewport().SetInputAsHandled();
            return;
        }

        if (@event is InputEventKey toggleEvent && toggleEvent.Pressed && !toggleEvent.Echo && toggleEvent.Keycode == Key.V)
        {
            _toggleTarget ??= GetNodeOrNull<Node3D>(ToggleTargetPath);
            if (_toggleTarget is not null)
            {
                _toggleTarget.Visible = !_toggleTarget.Visible;
                GD.Print($"Prototype volume proxies visible: {_toggleTarget.Visible}");
            }
            GetViewport().SetInputAsHandled();
            return;
        }

        if (Input.MouseMode != Input.MouseModeEnum.Captured || @event is not InputEventMouseMotion motion)
        {
            return;
        }

        _yaw -= motion.Relative.X * MouseSensitivity;
        _pitch = Mathf.Clamp(_pitch - motion.Relative.Y * MouseSensitivity, Mathf.DegToRad(-88.0f), Mathf.DegToRad(88.0f));
        Rotation = new Vector3(_pitch, _yaw, 0.0f);
        GetViewport().SetInputAsHandled();
    }

    public override void _Process(double delta)
    {
        var input = Vector3.Zero;
        if (Input.IsKeyPressed(Key.W))
        {
            input -= Transform.Basis.Z;
        }
        if (Input.IsKeyPressed(Key.S))
        {
            input += Transform.Basis.Z;
        }
        if (Input.IsKeyPressed(Key.A))
        {
            input -= Transform.Basis.X;
        }
        if (Input.IsKeyPressed(Key.D))
        {
            input += Transform.Basis.X;
        }
        if (Input.IsKeyPressed(Key.Space))
        {
            input += Vector3.Up;
        }
        if (Input.IsKeyPressed(Key.Shift))
        {
            input -= Vector3.Up;
        }

        if (input.LengthSquared() <= 0.0001f)
        {
            return;
        }

        var speed = MoveSpeed * (Input.IsKeyPressed(Key.Ctrl) ? FastMultiplier : 1.0f);
        GlobalPosition += input.Normalized() * speed * (float)delta;
    }
}
