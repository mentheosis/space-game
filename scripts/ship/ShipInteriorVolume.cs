using Godot;

public partial class ShipInteriorVolume : Area3D
{
    public override void _Ready()
    {
        BodyExited += OnBodyExited;
    }

    private static void OnBodyExited(Node3D body)
    {
        if (body is PlayerController player && player.DebugPlayerContext == PlayerContext.InShipInterior)
        {
            player.SetPlayerContext(PlayerContext.OnFoot);
        }
    }
}

