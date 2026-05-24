using Godot;

public partial class PilotSeat : Area3D, IInteractable
{
    [Export] public NodePath SeatAnchorPath { get; set; } = new("");
    [Export] public NodePath SeatExitPath { get; set; } = new("");
    [Export] public NodePath CockpitUiPath { get; set; } = new("");
    [Export] public NodePath ShipControllerPath { get; set; } = "..";

    private Marker3D _seatAnchor = null!;
    private Marker3D _seatExit = null!;
    private CanvasLayer? _cockpitUi;
    private ShipController? _ship;

    public override void _Ready()
    {
        _seatAnchor = GetNode<Marker3D>(SeatAnchorPath);
        _seatExit = GetNode<Marker3D>(SeatExitPath);
        _cockpitUi = GetNodeOrNull<CanvasLayer>(CockpitUiPath);
        _ship = GetNodeOrNull<ShipController>(ShipControllerPath);
        if (_cockpitUi is not null)
        {
            _cockpitUi.Visible = false;
        }
    }

    public string GetPrompt(PlayerController player)
    {
        if (player.DebugPlayerContext == PlayerContext.Seated && _ship is not null && !_ship.CanExitShip())
        {
            return "Ship Airborne";
        }

        return player.DebugPlayerContext == PlayerContext.Seated ? "F Stand" : "F Sit";
    }

    public bool CanInteract(PlayerController player)
    {
        if (player.DebugPlayerContext == PlayerContext.InShipInterior)
        {
            return _ship is null || _ship.CanUseHatches;
        }

        return player.DebugPlayerContext == PlayerContext.Seated;
    }

    public void Interact(PlayerController player)
    {
        if (!CanInteract(player))
        {
            return;
        }

        if (player.DebugPlayerContext == PlayerContext.Seated)
        {
            if (_ship is not null && !_ship.CanExitShip())
            {
                return;
            }

            Stand(player);
        }
        else
        {
            Sit(player);
        }
    }

    private void Sit(PlayerController player)
    {
        player.MoveToTransform(_seatAnchor.GlobalTransform);
        player.SetPlayerContext(PlayerContext.Seated);
        player.SetSeatedInteractable(this);
        _ship?.SetPilot(player);
        if (_cockpitUi is not null)
        {
            _cockpitUi.Visible = true;
        }
    }

    private void Stand(PlayerController player)
    {
        player.MoveToTransform(_seatExit.GlobalTransform);
        _ship?.ClearPilot(player);
        player.SetPlayerContext(PlayerContext.InShipInterior);
        if (_cockpitUi is not null)
        {
            _cockpitUi.Visible = false;
        }
    }
}
