using Godot;

public partial class PauseMenu : CanvasLayer
{
    [Export] public NodePath PlayerPath { get; set; } = new("../Player");

    private PlayerController? _player;
    private HSlider _horizontalSlider = null!;
    private HSlider _verticalSlider = null!;
    private Label _horizontalValue = null!;
    private Label _verticalValue = null!;
    private Button _resumeButton = null!;

    public override void _Ready()
    {
        _player = GetNodeOrNull<PlayerController>(PlayerPath);
        _horizontalSlider = GetNode<HSlider>("Panel/MarginContainer/Root/HorizontalLook/Slider");
        _verticalSlider = GetNode<HSlider>("Panel/MarginContainer/Root/VerticalLook/Slider");
        _horizontalValue = GetNode<Label>("Panel/MarginContainer/Root/HorizontalLook/Value");
        _verticalValue = GetNode<Label>("Panel/MarginContainer/Root/VerticalLook/Value");
        _resumeButton = GetNode<Button>("Panel/MarginContainer/Root/ResumeButton");

        if (_player is not null)
        {
            _horizontalSlider.Value = _player.MouseHorizontalSensitivity;
            _verticalSlider.Value = _player.MouseVerticalSensitivity;
        }

        _horizontalSlider.ValueChanged += OnHorizontalSensitivityChanged;
        _verticalSlider.ValueChanged += OnVerticalSensitivityChanged;
        _resumeButton.Pressed += CloseMenu;

        UpdateValueLabels();
        Visible = false;
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (@event.IsActionPressed("pause"))
        {
            if (Visible)
            {
                CloseMenu();
            }
            else
            {
                OpenMenu();
            }

            GetViewport().SetInputAsHandled();
        }
    }

    private void OpenMenu()
    {
        Visible = true;
        Input.MouseMode = Input.MouseModeEnum.Visible;
    }

    private void CloseMenu()
    {
        Visible = false;
        Input.MouseMode = Input.MouseModeEnum.Captured;
    }

    private void OnHorizontalSensitivityChanged(double value)
    {
        if (_player is not null)
        {
            _player.MouseHorizontalSensitivity = (float)value;
        }

        UpdateValueLabels();
    }

    private void OnVerticalSensitivityChanged(double value)
    {
        if (_player is not null)
        {
            _player.MouseVerticalSensitivity = (float)value;
        }

        UpdateValueLabels();
    }

    private void UpdateValueLabels()
    {
        _horizontalValue.Text = $"{_horizontalSlider.Value:0.0000}";
        _verticalValue.Text = $"{_verticalSlider.Value:0.0000}";
    }
}
