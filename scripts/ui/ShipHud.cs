using Godot;

public partial class ShipHud : CanvasLayer
{
    [Export] public NodePath ShipPath { get; set; } = new("");
    [Export] public NodePath TargetPath { get; set; } = new("");

    private ShipController? _ship;
    private Node3D? _target;
    private NavigationTarget? _navigationTarget;
    private Label _label = null!;
    private Label _targetMarker = null!;

    public override void _Ready()
    {
        _ship = GetNodeOrNull<ShipController>(ShipPath);
        _target = GetNodeOrNull<Node3D>(TargetPath);
        _navigationTarget = _target as NavigationTarget;
        _label = GetNode<Label>("Panel/MarginContainer/Label");
        _targetMarker = GetNode<Label>("TargetMarker");
        _targetMarker.Visible = false;
    }

    public override void _Process(double delta)
    {
        if (_ship is null)
        {
            _label.Text = "No ship";
            _targetMarker.Visible = false;
            return;
        }

        var targetText = GetTargetText();
        _label.Text =
            $"Ship: {(_ship.IsPiloted ? "PILOTED" : "IDLE")}\n" +
            $"Landed: {_ship.IsLanded}\n" +
            $"Speed: {_ship.Speed:0.0} m/s\n" +
            $"Gravity: {_ship.ActiveGravityBodyName} ({_ship.GravityMagnitude:0.00})\n" +
            $"Surface: {_ship.SurfaceDistance:0.0} m" +
            targetText;

        UpdateTargetMarker();
    }

    private string GetTargetText()
    {
        if (_target is null || _ship is null)
        {
            return "";
        }

        var toTarget = _target.GlobalPosition - _ship.GlobalPosition;
        var distance = toTarget.Length();
        var closingSpeed = 0.0f;
        if (distance > 0.001f)
        {
            closingSpeed = _ship.LinearVelocity.Dot(toTarget / distance);
        }

        return
            $"\nTarget: {GetTargetName()}" +
            $"\nDistance: {distance:0.0} m" +
            $"\nClosing: {closingSpeed:0.0} m/s";
    }

    private void UpdateTargetMarker()
    {
        if (_target is null || _ship is null || !_ship.IsPiloted)
        {
            _targetMarker.Visible = false;
            return;
        }

        var camera = GetViewport().GetCamera3D();
        if (camera is null)
        {
            _targetMarker.Visible = false;
            return;
        }

        var viewportSize = GetViewport().GetVisibleRect().Size;
        var screenPosition = camera.UnprojectPosition(_target.GlobalPosition);
        if (camera.IsPositionBehind(_target.GlobalPosition))
        {
            screenPosition = viewportSize - screenPosition;
        }

        const float margin = 32.0f;
        screenPosition.X = Mathf.Clamp(screenPosition.X, margin, viewportSize.X - margin);
        screenPosition.Y = Mathf.Clamp(screenPosition.Y, margin, viewportSize.Y - margin);

        _targetMarker.Text = $"> {GetTargetName()}";
        _targetMarker.Position = screenPosition - (_targetMarker.Size * 0.5f);
        _targetMarker.Visible = true;
    }

    private string GetTargetName()
    {
        return _navigationTarget?.DisplayName ?? _target?.Name ?? "Target";
    }
}
