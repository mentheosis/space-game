using Godot;

public partial class ShipInteriorVolume : Area3D
{
    [Export] public NodePath ShipControllerPath { get; set; } = "../..";

    private ShipController? _ship;

    public override void _Ready()
    {
        _ship = GetNodeOrNull<ShipController>(ShipControllerPath);
        BodyExited += OnBodyExited;
    }

    private void OnBodyExited(Node3D body)
    {
        if (body is PlayerController player && player.DebugPlayerContext == PlayerContext.InShipInterior)
        {
            player.SetPlayerContext(PlayerContext.OnFoot);
            _ship?.SetInteriorViewActive(false);
        }
    }
}
