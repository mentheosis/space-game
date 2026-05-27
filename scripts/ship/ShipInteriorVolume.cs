using Godot;

public partial class ShipInteriorVolume : Area3D
{
    [Export] public NodePath ShipControllerPath { get; set; } = "../..";
    [Export] public Vector3 InteriorBoundsMin { get; set; } = new(-2.55f, -0.8f, -11.3f);
    [Export] public Vector3 InteriorBoundsMax { get; set; } = new(2.55f, 3.8f, 4.35f);

    private ShipController? _ship;

    public override void _Ready()
    {
        _ship = GetNodeOrNull<ShipController>(ShipControllerPath);
        BodyEntered += OnBodyEntered;
        BodyExited += OnBodyExited;
    }

    public override void _PhysicsProcess(double delta)
    {
        foreach (var body in GetOverlappingBodies())
        {
            if (body is not PlayerController player)
            {
                continue;
            }

            var insideInterior = IsInsideInteriorBounds(player.GlobalPosition);
            if (insideInterior && player.DebugPlayerContext == PlayerContext.OnFoot)
            {
                EnterInterior(player);
            }
            else if (!insideInterior && player.DebugPlayerContext == PlayerContext.InShipInterior)
            {
                ExitInterior(player);
            }
        }
    }

    private void OnBodyEntered(Node3D body)
    {
        if (body is PlayerController player
            && player.DebugPlayerContext == PlayerContext.OnFoot
            && IsInsideInteriorBounds(player.GlobalPosition))
        {
            EnterInterior(player);
        }
    }

    private void OnBodyExited(Node3D body)
    {
        if (body is PlayerController player && player.DebugPlayerContext == PlayerContext.InShipInterior)
        {
            ExitInterior(player);
        }
    }

    private void EnterInterior(PlayerController player)
    {
        player.SetPlayerContext(PlayerContext.InShipInterior);
        player.AttachToShipInteriorFrame(_ship, preserveRelativeVelocity: true);
        _ship?.SetInteriorViewActive(true);
    }

    private void ExitInterior(PlayerController player)
    {
        player.DetachFromShipInteriorFrame(inheritShipMomentum: true);
        player.SetPlayerContext(PlayerContext.OnFoot);
        _ship?.SetInteriorViewActive(false);
    }

    private bool IsInsideInteriorBounds(Vector3 globalPosition)
    {
        if (_ship is null)
        {
            return false;
        }

        var localPosition = _ship.GlobalTransform.AffineInverse() * globalPosition;
        return localPosition.X >= InteriorBoundsMin.X
            && localPosition.X <= InteriorBoundsMax.X
            && localPosition.Y >= InteriorBoundsMin.Y
            && localPosition.Y <= InteriorBoundsMax.Y
            && localPosition.Z >= InteriorBoundsMin.Z
            && localPosition.Z <= InteriorBoundsMax.Z;
    }
}
