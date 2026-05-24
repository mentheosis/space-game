using Godot;

public partial class ShipHatch : Area3D, IInteractable
{
    [Export] public bool EntersShip { get; set; } = true;
    [Export] public NodePath TargetMarkerPath { get; set; } = new("");

    private Marker3D _targetMarker = null!;

    public override void _Ready()
    {
        _targetMarker = GetNode<Marker3D>(TargetMarkerPath);
    }

    public string GetPrompt(PlayerController player)
    {
        return EntersShip ? "E Enter Ship" : "E Exit Ship";
    }

    public bool CanInteract(PlayerController player)
    {
        return EntersShip
            ? player.DebugPlayerContext == PlayerContext.OnFoot
            : player.DebugPlayerContext == PlayerContext.InShipInterior;
    }

    public void Interact(PlayerController player)
    {
        if (!CanInteract(player))
        {
            return;
        }

        player.MoveToTransform(_targetMarker.GlobalTransform);
        player.SetPlayerContext(EntersShip ? PlayerContext.InShipInterior : PlayerContext.OnFoot);
    }
}
