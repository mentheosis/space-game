using Godot;

public partial class SuitHud : CanvasLayer
{
    [Export] public NodePath PlayerPath { get; set; } = new("");

    private PlayerController? _player;
    private ProgressBar _fuelBar = null!;
    private ProgressBar _oxygenBar = null!;
    private Label _modeLabel = null!;
    private Label _speedLabel = null!;

    public override void _Ready()
    {
        _player = GetNodeOrNull<PlayerController>(PlayerPath);
        _fuelBar = GetNode<ProgressBar>("Root/FuelBar");
        _oxygenBar = GetNode<ProgressBar>("Root/OxygenBar");
        _modeLabel = GetNode<Label>("Root/ModeLabel");
        _speedLabel = GetNode<Label>("Root/SpeedLabel");
    }

    public override void _Process(double delta)
    {
        if (_player is null)
        {
            _modeLabel.Text = "NO PLAYER";
            return;
        }

        _fuelBar.MaxValue = _player.DebugJetpackFuelMax;
        _fuelBar.Value = _player.DebugJetpackFuel;
        _oxygenBar.MaxValue = _player.DebugOxygenMax;
        _oxygenBar.Value = _player.DebugOxygen;
        _modeLabel.Text = _player.DebugMovementMode.ToString().ToUpperInvariant();
        _speedLabel.Text = $"{_player.DebugSpeed:0.0} m/s";
    }
}

