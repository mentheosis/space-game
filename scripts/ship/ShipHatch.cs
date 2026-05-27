using Godot;

public partial class ShipHatch : Area3D, IInteractable
{
    [Export] public bool EntersShip { get; set; } = true;
    [Export] public NodePath TargetMarkerPath { get; set; } = new("");
    [Export] public NodePath ShipControllerPath { get; set; } = "..";

    private Marker3D _targetMarker = null!;
    private ShipController? _ship;

    public override void _Ready()
    {
        _targetMarker = GetNode<Marker3D>(TargetMarkerPath);
        _ship = GetNodeOrNull<ShipController>(ShipControllerPath);
    }

    public string GetPrompt(PlayerController player)
    {
        if (_ship is not null && !_ship.CanUseHatches)
        {
            return "Ship Airborne";
        }

        return EntersShip ? "F Enter Ship" : "F Exit Ship";
    }

    public bool CanInteract(PlayerController player)
    {
        if (_ship is not null && !_ship.CanUseHatches)
        {
            return false;
        }

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

        if (EntersShip)
        {
            player.MoveToTransform(_targetMarker.GlobalTransform);
            player.SetPlayerContext(PlayerContext.InShipInterior);
            player.AttachToShipInteriorFrame(_ship);
        }
        else
        {
            player.MoveToTransform(_targetMarker.GlobalTransform);
            player.DetachFromShipInteriorFrame(inheritShipMomentum: true);
            player.SetPlayerContext(PlayerContext.OnFoot);
        }
        _ship?.SetInteriorViewActive(EntersShip);
    }
}
