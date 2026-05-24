using Godot;

public partial class NavigationTarget : Node3D
{
    [Export] public string DisplayName { get; set; } = "Target";
    [Export] public Color MarkerColor { get; set; } = new(0.45f, 0.95f, 1.0f);
    [Export] public float TargetRadius { get; set; } = 50.0f;
}
