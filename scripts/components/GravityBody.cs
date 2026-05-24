using Godot;

public partial class GravityBody : Node3D
{
    [Export] public float Radius { get; set; } = 50.0f;
    [Export] public float SurfaceGravity { get; set; } = 24.0f;
    [Export] public float InfluenceRadius { get; set; } = 250.0f;
    [Export] public int Priority { get; set; }

    public override void _Ready()
    {
        GravityService.Instance?.Register(this);
    }

    public override void _ExitTree()
    {
        GravityService.Instance?.Unregister(this);
    }

    public bool ContainsPoint(Vector3 worldPosition)
    {
        return GlobalPosition.DistanceTo(worldPosition) <= InfluenceRadius;
    }

    public Vector3 GetGravityDirection(Vector3 worldPosition)
    {
        var toCenter = GlobalPosition - worldPosition;
        return toCenter.LengthSquared() > 0.0001f ? toCenter.Normalized() : Vector3.Down;
    }

    public Vector3 GetGravityAcceleration(Vector3 worldPosition)
    {
        return GetGravityDirection(worldPosition) * SurfaceGravity;
    }

    public float GetDistanceToSurface(Vector3 worldPosition)
    {
        return GlobalPosition.DistanceTo(worldPosition) - Radius;
    }
}
