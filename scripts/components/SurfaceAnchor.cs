using Godot;

public partial class SurfaceAnchor : Node3D
{
    [Export] public float SurfaceRadius { get; set; } = 50.0f;
    [Export] public float SurfaceOffset { get; set; }
    [Export] public float YawDegrees { get; set; }

    public override void _Ready()
    {
        AlignToSurface();
    }

    private void AlignToSurface()
    {
        if (Position.LengthSquared() < 0.001f)
        {
            return;
        }

        var up = Position.Normalized();
        Position = up * (SurfaceRadius + SurfaceOffset);

        var forward = Vector3.Forward - (Vector3.Forward.Dot(up) * up);
        if (forward.LengthSquared() < 0.001f)
        {
            forward = Vector3.Right - (Vector3.Right.Dot(up) * up);
        }

        forward = forward.Normalized().Rotated(up, Mathf.DegToRad(YawDegrees));
        var right = forward.Cross(up).Normalized();
        Basis = new Basis(right, up, -forward).Orthonormalized();
    }
}
