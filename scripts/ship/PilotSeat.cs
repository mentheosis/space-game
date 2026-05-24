using Godot;

public partial class PilotSeat : Area3D, IInteractable
{
    [Export] public NodePath SeatAnchorPath { get; set; } = new("");
    [Export] public NodePath SeatExitPath { get; set; } = new("");
    [Export] public NodePath CockpitUiPath { get; set; } = new("");

    private Marker3D _seatAnchor = null!;
    private Marker3D _seatExit = null!;
    private CanvasLayer? _cockpitUi;

    public override void _Ready()
    {
        _seatAnchor = GetNode<Marker3D>(SeatAnchorPath);
        _seatExit = GetNode<Marker3D>(SeatExitPath);
        _cockpitUi = GetNodeOrNull<CanvasLayer>(CockpitUiPath);
        if (_cockpitUi is not null)
        {
            _cockpitUi.Visible = false;
        }
    }

    public string GetPrompt(PlayerController player)
    {
        return player.DebugPlayerContext == PlayerContext.Seated ? "E Stand" : "E Sit";
    }

    public bool CanInteract(PlayerController player)
    {
        return player.DebugPlayerContext == PlayerContext.InShipInterior
            || player.DebugPlayerContext == PlayerContext.Seated;
    }

    public void Interact(PlayerController player)
    {
        if (!CanInteract(player))
        {
            return;
        }

        if (player.DebugPlayerContext == PlayerContext.Seated)
        {
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
        if (_cockpitUi is not null)
        {
            _cockpitUi.Visible = true;
        }
    }

    private void Stand(PlayerController player)
    {
        player.MoveToTransform(_seatExit.GlobalTransform);
        player.SetPlayerContext(PlayerContext.InShipInterior);
        if (_cockpitUi is not null)
        {
            _cockpitUi.Visible = false;
        }
    }
}
