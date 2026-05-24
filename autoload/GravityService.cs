using System.Collections.Generic;
using Godot;

public partial class GravityService : Node
{
    public static GravityService? Instance { get; private set; }

    private readonly List<GravityBody> _bodies = new();

    public override void _EnterTree()
    {
        Instance = this;
    }

    public override void _ExitTree()
    {
        if (Instance == this)
        {
            Instance = null;
        }
    }

    public void Register(GravityBody body)
    {
        if (!_bodies.Contains(body))
        {
            _bodies.Add(body);
        }
    }

    public void Unregister(GravityBody body)
    {
        _bodies.Remove(body);
    }

    public GravityBody? GetBestBody(Vector3 worldPosition)
    {
        GravityBody? best = null;
        var bestPriority = int.MinValue;
        var bestSurfaceDistance = float.MaxValue;

        foreach (var body in _bodies)
        {
            if (!GodotObject.IsInstanceValid(body) || !body.ContainsPoint(worldPosition))
            {
                continue;
            }

            var surfaceDistance = Mathf.Abs(body.GetDistanceToSurface(worldPosition));
            if (
                best is null
                || body.Priority > bestPriority
                || (body.Priority == bestPriority && surfaceDistance < bestSurfaceDistance)
            )
            {
                best = body;
                bestPriority = body.Priority;
                bestSurfaceDistance = surfaceDistance;
            }
        }

        return best;
    }

    public Vector3 GetGravityAcceleration(Vector3 worldPosition)
    {
        return GetBestBody(worldPosition)?.GetGravityAcceleration(worldPosition) ?? Vector3.Zero;
    }

    public Vector3 GetGravityDirection(Vector3 worldPosition)
    {
        return GetBestBody(worldPosition)?.GetGravityDirection(worldPosition) ?? Vector3.Down;
    }

    public Vector3 GetUpDirection(Vector3 worldPosition)
    {
        return -GetGravityDirection(worldPosition);
    }
}
