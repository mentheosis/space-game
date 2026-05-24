using Godot;
using System.Collections.Generic;

public partial class PauseMenu : CanvasLayer
{
    [Export] public NodePath PlayerPath { get; set; } = new("../Player");

    private const string SettingsPath = "user://settings.cfg";
    private readonly (string ActionName, string Label, Key DefaultKey, int Column)[] _shipBindings =
    {
        ("ship_translate_forward", "Forward", Key.W, 0),
        ("ship_translate_back", "Back", Key.S, 0),
        ("ship_translate_left", "Left", Key.A, 0),
        ("ship_translate_right", "Right", Key.D, 0),
        ("ship_pitch_up", "Pitch Up", Key.Up, 1),
        ("ship_pitch_down", "Pitch Down", Key.Down, 1),
        ("ship_roll_left", "Roll Left", Key.Q, 1),
        ("ship_roll_right", "Roll Right", Key.E, 1),
        ("ship_yaw_left", "Yaw Left", Key.Left, 2),
        ("ship_yaw_right", "Yaw Right", Key.Right, 2),
        ("ship_translate_up", "Ascent", Key.Space, 2),
        ("ship_translate_down", "Descend", Key.Shift, 2),
        ("ship_brake", "Dampen", Key.Ctrl, 2),
    };

    private PlayerController? _player;
    private HSlider _horizontalSlider = null!;
    private HSlider _verticalSlider = null!;
    private HSlider _uiScaleSlider = null!;
    private Label _horizontalValue = null!;
    private Label _verticalValue = null!;
    private Label _uiScaleValue = null!;
    private HBoxContainer _shipBindingColumns = null!;
    private Button _resumeButton = null!;
    private readonly ConfigFile _settings = new();
    private readonly Dictionary<string, Button> _bindingButtons = new();
    private string _pendingBindingAction = "";

    public override void _Ready()
    {
        EnsureDefaultShipBindings();
        _settings.Load(SettingsPath);
        _player = GetNodeOrNull<PlayerController>(PlayerPath);
        _horizontalSlider = GetNode<HSlider>("Panel/MarginContainer/Root/HorizontalLook/Slider");
        _verticalSlider = GetNode<HSlider>("Panel/MarginContainer/Root/VerticalLook/Slider");
        _uiScaleSlider = GetNode<HSlider>("Panel/MarginContainer/Root/UiScale/Slider");
        _horizontalValue = GetNode<Label>("Panel/MarginContainer/Root/HorizontalLook/Value");
        _verticalValue = GetNode<Label>("Panel/MarginContainer/Root/VerticalLook/Value");
        _uiScaleValue = GetNode<Label>("Panel/MarginContainer/Root/UiScale/Value");
        _shipBindingColumns = GetNode<HBoxContainer>("Panel/MarginContainer/Root/ShipBindingColumns");
        _resumeButton = GetNode<Button>("Panel/MarginContainer/Root/ResumeButton");

        if (_player is not null)
        {
            _player.MouseHorizontalSensitivity = GetFloatSetting("look", "horizontal", _player.MouseHorizontalSensitivity);
            _player.MouseVerticalSensitivity = GetFloatSetting("look", "vertical", _player.MouseVerticalSensitivity);
            _horizontalSlider.Value = _player.MouseHorizontalSensitivity;
            _verticalSlider.Value = _player.MouseVerticalSensitivity;
        }

        _uiScaleSlider.Value = GetFloatSetting("ui", "scale", 1.0f);
        _horizontalSlider.ValueChanged += OnHorizontalSensitivityChanged;
        _verticalSlider.ValueChanged += OnVerticalSensitivityChanged;
        _uiScaleSlider.ValueChanged += OnUiScaleChanged;
        _uiScaleSlider.DragEnded += OnUiScaleDragEnded;
        _resumeButton.Pressed += CloseMenu;

        LoadSavedShipBindings();
        BuildShipBindingRows();
        UpdateValueLabels();
        ApplyUiScale((float)_uiScaleSlider.Value);
        CallDeferred(nameof(ApplyUiScaleDeferred));
        Visible = false;
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (_pendingBindingAction.Length > 0)
        {
            if (@event is InputEventKey keyEvent && keyEvent.Pressed && !keyEvent.Echo)
            {
                if (keyEvent.Keycode == Key.Escape)
                {
                    CancelBinding();
                }
                else
                {
                    ApplyBinding(_pendingBindingAction, keyEvent.Keycode);
                }

                GetViewport().SetInputAsHandled();
            }

            return;
        }

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

        SaveSetting("look", "horizontal", value);
        UpdateValueLabels();
    }

    private void OnVerticalSensitivityChanged(double value)
    {
        if (_player is not null)
        {
            _player.MouseVerticalSensitivity = (float)value;
        }

        SaveSetting("look", "vertical", value);
        UpdateValueLabels();
    }

    private void OnUiScaleChanged(double value)
    {
        UpdateValueLabels();
    }

    private void OnUiScaleDragEnded(bool valueChanged)
    {
        if (!valueChanged)
        {
            return;
        }

        SaveSetting("ui", "scale", _uiScaleSlider.Value);
        ApplyUiScale((float)_uiScaleSlider.Value);
    }

    private void UpdateValueLabels()
    {
        _horizontalValue.Text = $"{_horizontalSlider.Value:0.0000}";
        _verticalValue.Text = $"{_verticalSlider.Value:0.0000}";
        _uiScaleValue.Text = $"{_uiScaleSlider.Value:0.00}x";
    }

    private void BuildShipBindingRows()
    {
        const int columnCount = 3;
        var columns = new VBoxContainer[columnCount];
        for (var i = 0; i < columnCount; i++)
        {
            columns[i] = new VBoxContainer();
            columns[i].AddThemeConstantOverride("separation", 5);
            columns[i].SizeFlagsHorizontal = Control.SizeFlags.ExpandFill;
            _shipBindingColumns.AddChild(columns[i]);
        }

        for (var i = 0; i < _shipBindings.Length; i++)
        {
            var binding = _shipBindings[i];
            var row = new HBoxContainer
            {
                CustomMinimumSize = new Vector2(0.0f, 28.0f)
            };
            row.AddThemeConstantOverride("separation", 8);

            var label = new Label
            {
                Text = binding.Label,
                CustomMinimumSize = new Vector2(105.0f, 0.0f)
            };

            var button = new Button
            {
                Text = GetBindingText(binding.ActionName),
                CustomMinimumSize = new Vector2(120.0f, 0.0f)
            };
            button.Pressed += () => BeginBinding(binding.ActionName, button);

            row.AddChild(label);
            row.AddChild(button);
            var columnIndex = binding.Column;
            if (columnIndex < 0 || columnIndex >= columnCount)
            {
                columnIndex = 0;
            }

            columns[columnIndex].AddChild(row);
            _bindingButtons[binding.ActionName] = button;
        }
    }

    private void BeginBinding(string actionName, Button button)
    {
        _pendingBindingAction = actionName;
        button.Text = "Press key";
    }

    private void CancelBinding()
    {
        if (_bindingButtons.TryGetValue(_pendingBindingAction, out var button))
        {
            button.Text = GetBindingText(_pendingBindingAction);
        }

        _pendingBindingAction = "";
    }

    private void ApplyBinding(string actionName, Key key)
    {
        InputMap.ActionEraseEvents(actionName);
        InputMap.ActionAddEvent(actionName, new InputEventKey { Keycode = key });
        SaveSetting("ship_bindings", actionName, (long)key);

        if (_bindingButtons.TryGetValue(actionName, out var button))
        {
            button.Text = GetBindingText(actionName);
        }

        _pendingBindingAction = "";
    }

    private static string GetBindingText(string actionName)
    {
        foreach (var inputEvent in InputMap.ActionGetEvents(actionName))
        {
            if (inputEvent is InputEventKey keyEvent)
            {
                return OS.GetKeycodeString(keyEvent.Keycode);
            }
        }

        return "Unbound";
    }

    private void ApplyUiScale(float scale)
    {
        foreach (var node in GetTree().GetNodesInGroup("scalable_ui"))
        {
            if (node is Control control)
            {
                if (control.IsInGroup("scale_from_bottom_left"))
                {
                    control.PivotOffset = new Vector2(0.0f, control.Size.Y);
                }
                else if (control.IsInGroup("scale_from_top_right"))
                {
                    control.PivotOffset = new Vector2(control.Size.X, 0.0f);
                }
                else
                {
                    control.PivotOffset = Vector2.Zero;
                }

                control.Scale = Vector2.One * scale;
            }
        }
    }

    public void ApplyUiScaleDeferred()
    {
        ApplyUiScale((float)_uiScaleSlider.Value);
    }

    private void LoadSavedShipBindings()
    {
        foreach (var binding in _shipBindings)
        {
            var keyValue = _settings.GetValue("ship_bindings", binding.ActionName, (long)binding.DefaultKey).AsInt64();
            ApplyBindingWithoutSaving(binding.ActionName, (Key)keyValue);
        }
    }

    private static void ApplyBindingWithoutSaving(string actionName, Key key)
    {
        if (!InputMap.HasAction(actionName))
        {
            InputMap.AddAction(actionName);
        }

        InputMap.ActionEraseEvents(actionName);
        InputMap.ActionAddEvent(actionName, new InputEventKey { Keycode = key });
    }

    private void EnsureDefaultShipBindings()
    {
        foreach (var binding in _shipBindings)
        {
            if (!InputMap.HasAction(binding.ActionName))
            {
                InputMap.AddAction(binding.ActionName);
            }

            if (InputMap.ActionGetEvents(binding.ActionName).Count == 0)
            {
                InputMap.ActionAddEvent(binding.ActionName, new InputEventKey { Keycode = binding.DefaultKey });
            }
        }
    }

    private float GetFloatSetting(string section, string key, float defaultValue)
    {
        return (float)_settings.GetValue(section, key, defaultValue).AsDouble();
    }

    private void SaveSetting(string section, string key, Variant value)
    {
        _settings.SetValue(section, key, value);
        _settings.Save(SettingsPath);
    }
}
