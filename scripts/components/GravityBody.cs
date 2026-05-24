using Godot;

public partial class GravityBody : Node3D
{
    [Export] public float Radius { get; set; } = 50.0f;
    [Export] public float SurfaceGravity { get; set; } = 24.0f;
    [Export] public float InfluenceRadius { get; set; } = 250.0f;
    [Export] public int Priority { get; set; }
    [Export] public bool UseFalloff { get; set; }
    [Export] public float EdgeGravity { get; set; } = 0.2f;
    [Export] public float FalloffExponent { get; set; } = 2.5f;

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
        return GetGravityDirection(worldPosition) * GetGravityMagnitude(worldPosition);
    }

    public float GetGravityMagnitude(Vector3 worldPosition)
    {
        if (!UseFalloff)
        {
            return SurfaceGravity;
        }

        var distanceFromCenter = GlobalPosition.DistanceTo(worldPosition);
        var altitude = Mathf.Max(0.0f, distanceFromCenter - Radius);
        var falloffRange = Mathf.Max(0.001f, InfluenceRadius - Radius);
        var t = Mathf.Clamp(altitude / falloffRange, 0.0f, 1.0f);
        var exponent = Mathf.Max(0.1f, FalloffExponent);
        var gravityRatio = Mathf.Pow(1.0f - t, exponent);

        return EdgeGravity + (SurfaceGravity - EdgeGravity) * gravityRatio;
    }

    public float GetDistanceToSurface(Vector3 worldPosition)
    {
        return GlobalPosition.DistanceTo(worldPosition) - Radius;
    }
}
