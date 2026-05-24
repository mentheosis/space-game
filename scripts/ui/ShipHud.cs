using Godot;

public partial class ShipHud : CanvasLayer
{
    [Export] public NodePath ShipPath { get; set; } = new("");

    private ShipController? _ship;
    private Label _label = null!;

    public override void _Ready()
    {
        _ship = GetNodeOrNull<ShipController>(ShipPath);
        _label = GetNode<Label>("Panel/MarginContainer/Label");
    }

    public override void _Process(double delta)
    {
        if (_ship is null)
        {
            _label.Text = "No ship";
            return;
        }

        _label.Text =
            $"Ship: {(_ship.IsPiloted ? "PILOTED" : "IDLE")}\n" +
            $"Landed: {_ship.IsLanded}\n" +
            $"Speed: {_ship.Speed:0.0} m/s\n" +
            $"Surface: {_ship.SurfaceDistance:0.0} m";
    }
}

