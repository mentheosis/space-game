using Godot;

public partial class GravityDebugOverlay : CanvasLayer
{
    [Export] public NodePath PlayerPath { get; set; } = new("");

    private Label _label = null!;
    private PlayerController? _player;
    private bool _visible = true;

    public override void _Ready()
    {
        _label = GetNode<Label>("Panel/MarginContainer/Label");
        _player = GetNodeOrNull<PlayerController>(PlayerPath);
        Visible = _visible;
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (@event.IsActionPressed("debug_toggle"))
        {
            _visible = !_visible;
            Visible = _visible;
            GetViewport().SetInputAsHandled();
        }
    }

    public override void _Process(double delta)
    {
        if (_player is null)
        {
            _label.Text = "No player assigned";
            return;
        }

        var surfaceDistance = "n/a";
        var root = GetTree().CurrentScene;
        var gravityBody = root?.FindChild("GravityBody", true, false) as GravityBody;
        if (gravityBody is not null)
        {
            surfaceDistance = gravityBody.GetDistanceToSurface(_player.GlobalPosition).ToString("0.00");
        }

        _label.Text =
            $"Gravity Body: {_player.DebugActiveGravityBodyName}\n" +
            $"Mode: {_player.DebugMovementMode}\n" +
            $"Grounded: {_player.DebugGrounded}\n" +
            $"Speed: {_player.DebugSpeed:0.00}\n" +
            $"Jetpack: {(_player.DebugJetpackFiring ? "firing" : "idle")} {_player.DebugJetpackFuel:0.00}/{_player.DebugJetpackFuelMax:0.00}\n" +
            $"Oxygen: {_player.DebugOxygen:0.0}/{_player.DebugOxygenMax:0.0}\n" +
            $"Gravity Accel: {_player.DebugGravityAcceleration.Length():0.00}\n" +
            $"Gravity Dir: {FormatVector(_player.DebugGravityDirection)}\n" +
            $"Up Dir: {FormatVector(_player.DebugUpDirection)}\n" +
            $"Surface Dist: {surfaceDistance}";
    }

    private static string FormatVector(Vector3 vector)
    {
        return $"({vector.X:0.00}, {vector.Y:0.00}, {vector.Z:0.00})";
    }
}
