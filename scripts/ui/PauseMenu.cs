using Godot;
using System.Collections.Generic;

public partial class PauseMenu : CanvasLayer
{
    [Export] public NodePath PlayerPath { get; set; } = new("../Player");
    [Export] public NodePath ShipPath { get; set; } = new("../Ship");

    private const string SettingsPath = "user://settings.cfg";

    private readonly (string ActionName, string Label, Key DefaultKey, int Column)[] _flightBindings =
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

    private readonly (string ActionName, string Label, Key DefaultKey, int Column)[] _walkBindings =
    {
        ("move_forward", "Forward", Key.W, 0),
        ("move_back", "Back", Key.S, 0),
        ("move_left", "Left", Key.A, 0),
        ("move_right", "Right", Key.D, 0),
        ("jump", "Jump", Key.Space, 1),
        ("jetpack", "Jetpack", Key.Shift, 1),
        ("brake", "Brake", Key.Ctrl, 1),
        ("interact", "Interact", Key.F, 1),
    };

    private PlayerController? _player;
    private ShipController? _ship;
    private HSlider _uiScaleSlider = null!;
    private HSlider _flightLookXSlider = null!;
    private HSlider _flightLookYSlider = null!;
    private HSlider _walkLookXSlider = null!;
    private HSlider _walkLookYSlider = null!;
    private Label _uiScaleValue = null!;
    private Label _flightLookXValue = null!;
    private Label _flightLookYValue = null!;
    private Label _walkLookXValue = null!;
    private Label _walkLookYValue = null!;
    private CheckBox _flightInvertX = null!;
    private CheckBox _flightInvertY = null!;
    private CheckBox _walkInvertX = null!;
    private CheckBox _walkInvertY = null!;
    private HBoxContainer _flightBindingColumns = null!;
    private HBoxContainer _walkBindingColumns = null!;
    private Button _resumeButton = null!;
    private readonly ConfigFile _settings = new();
    private readonly Dictionary<string, Button> _bindingButtons = new();
    private string _pendingBindingAction = "";
    private string _pendingBindingSection = "";

    public override void _Ready()
    {
        EnsureDefaultBindings(_flightBindings);
        EnsureDefaultBindings(_walkBindings);
        _settings.Load(SettingsPath);

        _player = GetNodeOrNull<PlayerController>(PlayerPath);
        _ship = GetNodeOrNull<ShipController>(ShipPath);

        _uiScaleSlider = GetNode<HSlider>("Panel/MarginContainer/Root/UiScale/Slider");
        _uiScaleValue = GetNode<Label>("Panel/MarginContainer/Root/UiScale/Value");
        _resumeButton = GetNode<Button>("Panel/MarginContainer/Root/ResumeButton");

        _flightLookXSlider = GetNode<HSlider>("Panel/MarginContainer/Root/Tabs/Flight/Camera/LookX/Slider");
        _flightLookYSlider = GetNode<HSlider>("Panel/MarginContainer/Root/Tabs/Flight/Camera/LookY/Slider");
        _flightLookXValue = GetNode<Label>("Panel/MarginContainer/Root/Tabs/Flight/Camera/LookX/Value");
        _flightLookYValue = GetNode<Label>("Panel/MarginContainer/Root/Tabs/Flight/Camera/LookY/Value");
        _flightInvertX = GetNode<CheckBox>("Panel/MarginContainer/Root/Tabs/Flight/Camera/Inverts/InvertX");
        _flightInvertY = GetNode<CheckBox>("Panel/MarginContainer/Root/Tabs/Flight/Camera/Inverts/InvertY");
        _flightBindingColumns = GetNode<HBoxContainer>("Panel/MarginContainer/Root/Tabs/Flight/FlightBindingColumns");

        _walkLookXSlider = GetNode<HSlider>("Panel/MarginContainer/Root/Tabs/Walk/Camera/LookX/Slider");
        _walkLookYSlider = GetNode<HSlider>("Panel/MarginContainer/Root/Tabs/Walk/Camera/LookY/Slider");
        _walkLookXValue = GetNode<Label>("Panel/MarginContainer/Root/Tabs/Walk/Camera/LookX/Value");
        _walkLookYValue = GetNode<Label>("Panel/MarginContainer/Root/Tabs/Walk/Camera/LookY/Value");
        _walkInvertX = GetNode<CheckBox>("Panel/MarginContainer/Root/Tabs/Walk/Camera/Inverts/InvertX");
        _walkInvertY = GetNode<CheckBox>("Panel/MarginContainer/Root/Tabs/Walk/Camera/Inverts/InvertY");
        _walkBindingColumns = GetNode<HBoxContainer>("Panel/MarginContainer/Root/Tabs/Walk/WalkBindingColumns");

        LoadCameraSettings();
        LoadSavedBindings(_flightBindings, "flight_bindings");
        LoadSavedBindings(_walkBindings, "walk_bindings");
        BuildBindingRows(_flightBindings, _flightBindingColumns, "flight_bindings", 3);
        BuildBindingRows(_walkBindings, _walkBindingColumns, "walk_bindings", 2);

        _uiScaleSlider.Value = GetFloatSetting("ui", "scale", 1.0f);
        _uiScaleSlider.ValueChanged += OnUiScaleChanged;
        _uiScaleSlider.DragEnded += OnUiScaleDragEnded;

        _flightLookXSlider.ValueChanged += OnFlightLookXChanged;
        _flightLookYSlider.ValueChanged += OnFlightLookYChanged;
        _flightInvertX.Toggled += OnFlightInvertXToggled;
        _flightInvertY.Toggled += OnFlightInvertYToggled;

        _walkLookXSlider.ValueChanged += OnWalkLookXChanged;
        _walkLookYSlider.ValueChanged += OnWalkLookYChanged;
        _walkInvertX.Toggled += OnWalkInvertXToggled;
        _walkInvertY.Toggled += OnWalkInvertYToggled;

        _resumeButton.Pressed += CloseMenu;

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
                    ApplyBinding(_pendingBindingAction, _pendingBindingSection, keyEvent.Keycode);
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

    public void ApplyUiScaleDeferred()
    {
        ApplyUiScale((float)_uiScaleSlider.Value);
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

    private void LoadCameraSettings()
    {
        if (_ship is not null)
        {
            _ship.OrbitCameraHorizontalSensitivity = GetFloatSetting("flight_camera", "horizontal", _ship.OrbitCameraHorizontalSensitivity);
            _ship.OrbitCameraVerticalSensitivity = GetFloatSetting("flight_camera", "vertical", _ship.OrbitCameraVerticalSensitivity);
            _ship.InvertOrbitCameraX = GetBoolSetting("flight_camera", "invert_x", _ship.InvertOrbitCameraX);
            _ship.InvertOrbitCameraY = GetBoolSetting("flight_camera", "invert_y", _ship.InvertOrbitCameraY);
            _flightLookXSlider.Value = _ship.OrbitCameraHorizontalSensitivity;
            _flightLookYSlider.Value = _ship.OrbitCameraVerticalSensitivity;
            _flightInvertX.ButtonPressed = _ship.InvertOrbitCameraX;
            _flightInvertY.ButtonPressed = _ship.InvertOrbitCameraY;
        }

        if (_player is not null)
        {
            var oldHorizontal = GetFloatSetting("look", "horizontal", _player.MouseHorizontalSensitivity);
            var oldVertical = GetFloatSetting("look", "vertical", _player.MouseVerticalSensitivity);
            _player.MouseHorizontalSensitivity = GetFloatSetting("walk_camera", "horizontal", oldHorizontal);
            _player.MouseVerticalSensitivity = GetFloatSetting("walk_camera", "vertical", oldVertical);
            _player.InvertMouseX = GetBoolSetting("walk_camera", "invert_x", _player.InvertMouseX);
            _player.InvertMouseY = GetBoolSetting("walk_camera", "invert_y", _player.InvertMouseY);
            _walkLookXSlider.Value = _player.MouseHorizontalSensitivity;
            _walkLookYSlider.Value = _player.MouseVerticalSensitivity;
            _walkInvertX.ButtonPressed = _player.InvertMouseX;
            _walkInvertY.ButtonPressed = _player.InvertMouseY;
        }
    }

    private void OnFlightLookXChanged(double value)
    {
        if (_ship is not null)
        {
            _ship.OrbitCameraHorizontalSensitivity = (float)value;
        }

        SaveSetting("flight_camera", "horizontal", value);
        UpdateValueLabels();
    }

    private void OnFlightLookYChanged(double value)
    {
        if (_ship is not null)
        {
            _ship.OrbitCameraVerticalSensitivity = (float)value;
        }

        SaveSetting("flight_camera", "vertical", value);
        UpdateValueLabels();
    }

    private void OnWalkLookXChanged(double value)
    {
        if (_player is not null)
        {
            _player.MouseHorizontalSensitivity = (float)value;
        }

        SaveSetting("walk_camera", "horizontal", value);
        UpdateValueLabels();
    }

    private void OnWalkLookYChanged(double value)
    {
        if (_player is not null)
        {
            _player.MouseVerticalSensitivity = (float)value;
        }

        SaveSetting("walk_camera", "vertical", value);
        UpdateValueLabels();
    }

    private void OnFlightInvertXToggled(bool pressed)
    {
        if (_ship is not null)
        {
            _ship.InvertOrbitCameraX = pressed;
        }

        SaveSetting("flight_camera", "invert_x", pressed);
    }

    private void OnFlightInvertYToggled(bool pressed)
    {
        if (_ship is not null)
        {
            _ship.InvertOrbitCameraY = pressed;
        }

        SaveSetting("flight_camera", "invert_y", pressed);
    }

    private void OnWalkInvertXToggled(bool pressed)
    {
        if (_player is not null)
        {
            _player.InvertMouseX = pressed;
        }

        SaveSetting("walk_camera", "invert_x", pressed);
    }

    private void OnWalkInvertYToggled(bool pressed)
    {
        if (_player is not null)
        {
            _player.InvertMouseY = pressed;
        }

        SaveSetting("walk_camera", "invert_y", pressed);
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
        _uiScaleValue.Text = $"{_uiScaleSlider.Value:0.00}x";
        _flightLookXValue.Text = $"{_flightLookXSlider.Value:0.0000}";
        _flightLookYValue.Text = $"{_flightLookYSlider.Value:0.0000}";
        _walkLookXValue.Text = $"{_walkLookXSlider.Value:0.0000}";
        _walkLookYValue.Text = $"{_walkLookYSlider.Value:0.0000}";
    }

    private void BuildBindingRows(
        (string ActionName, string Label, Key DefaultKey, int Column)[] bindings,
        HBoxContainer container,
        string settingsSection,
        int columnCount)
    {
        var columns = new VBoxContainer[columnCount];
        for (var i = 0; i < columnCount; i++)
        {
            columns[i] = new VBoxContainer();
            columns[i].AddThemeConstantOverride("separation", 5);
            columns[i].SizeFlagsHorizontal = Control.SizeFlags.ExpandFill;
            container.AddChild(columns[i]);
        }

        foreach (var binding in bindings)
        {
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
            button.Pressed += () => BeginBinding(binding.ActionName, settingsSection, button);

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

    private void BeginBinding(string actionName, string settingsSection, Button button)
    {
        _pendingBindingAction = actionName;
        _pendingBindingSection = settingsSection;
        button.Text = "Press key";
    }

    private void CancelBinding()
    {
        if (_bindingButtons.TryGetValue(_pendingBindingAction, out var button))
        {
            button.Text = GetBindingText(_pendingBindingAction);
        }

        _pendingBindingAction = "";
        _pendingBindingSection = "";
    }

    private void ApplyBinding(string actionName, string settingsSection, Key key)
    {
        InputMap.ActionEraseEvents(actionName);
        InputMap.ActionAddEvent(actionName, new InputEventKey { Keycode = key });
        SaveSetting(settingsSection, actionName, (long)key);

        if (_bindingButtons.TryGetValue(actionName, out var button))
        {
            button.Text = GetBindingText(actionName);
        }

        _pendingBindingAction = "";
        _pendingBindingSection = "";
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

    private void LoadSavedBindings((string ActionName, string Label, Key DefaultKey, int Column)[] bindings, string section)
    {
        foreach (var binding in bindings)
        {
            var keyValue = _settings.GetValue(section, binding.ActionName, (long)binding.DefaultKey).AsInt64();
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

    private static void EnsureDefaultBindings((string ActionName, string Label, Key DefaultKey, int Column)[] bindings)
    {
        foreach (var binding in bindings)
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

    private bool GetBoolSetting(string section, string key, bool defaultValue)
    {
        return _settings.GetValue(section, key, defaultValue).AsBool();
    }

    private void SaveSetting(string section, string key, Variant value)
    {
        _settings.SetValue(section, key, value);
        _settings.Save(SettingsPath);
    }
}
