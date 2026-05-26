using Godot;

public partial class ShipInteriorMaterialOverrides : Node
{
    [Export] public NodePath InteriorRootPath { get; set; } = "../BlenderInteriorVisual";
    [Export] public Material? CanopyGlassMaterial { get; set; }
    [Export] public Material? WallMaterial { get; set; }
    [Export] public Material? FloorMaterial { get; set; }
    [Export] public Material? TrimMaterial { get; set; }
    [Export] public Material? DarkPanelMaterial { get; set; }
    [Export] public Material? RubberMaterial { get; set; }
    [Export] public Material? ScreenMaterial { get; set; }
    [Export] public Material? SeatMaterial { get; set; }
    [Export] public Material? WarningMaterial { get; set; }

    public override void _Ready()
    {
        var root = GetNodeOrNull<Node>(InteriorRootPath);
        if (root is null)
        {
            return;
        }

        ApplyOverrides(root);
    }

    private void ApplyOverrides(Node node)
    {
        if (node is MeshInstance3D meshInstance)
        {
            ApplyMaterialOverride(meshInstance);
        }

        foreach (var child in node.GetChildren())
        {
            ApplyOverrides(child);
        }
    }

    private void ApplyMaterialOverride(MeshInstance3D meshInstance)
    {
        var normalized = meshInstance.Name.ToString().ToLowerInvariant();
        var material = SelectMaterial(normalized);
        if (material is null)
        {
            return;
        }

        meshInstance.MaterialOverride = material;
        if (material == CanopyGlassMaterial)
        {
            meshInstance.CastShadow = GeometryInstance3D.ShadowCastingSetting.Off;
        }
    }

    private Material? SelectMaterial(string normalized)
    {
        if (normalized.Contains("canopy_glass")
            || normalized.Contains("canopy_subtle")
            || normalized.Contains("glass_edge")
            || normalized.Contains("crown_glass"))
        {
            return CanopyGlassMaterial;
        }

        if (normalized.Contains("screen")
            || normalized.Contains("display")
            || normalized.Contains("indicator")
            || normalized.Contains("status_light")
            || normalized.Contains("floor_light")
            || normalized.Contains("label_light"))
        {
            return ScreenMaterial;
        }

        if (normalized.Contains("warning") || normalized.Contains("stripe") || normalized.Contains("chip"))
        {
            return WarningMaterial;
        }

        if (normalized.Contains("seat") || normalized.Contains("cushion") || normalized.Contains("headrest"))
        {
            return SeatMaterial;
        }

        if (normalized.Contains("rubber") || normalized.Contains("gasket") || normalized.Contains("harness"))
        {
            return RubberMaterial;
        }

        if (normalized.Contains("dark")
            || normalized.Contains("recess")
            || normalized.Contains("sill")
            || normalized.Contains("vent"))
        {
            return DarkPanelMaterial;
        }

        if (normalized.Contains("floor") || normalized.Contains("walkway") || normalized.Contains("tread"))
        {
            return FloorMaterial;
        }

        if (normalized.Contains("trim")
            || normalized.Contains("rail")
            || normalized.Contains("rib")
            || normalized.Contains("spine")
            || normalized.Contains("hoop")
            || normalized.Contains("collar")
            || normalized.Contains("frame")
            || normalized.Contains("bolt")
            || normalized.Contains("handle")
            || normalized.Contains("armature")
            || normalized.Contains("longeron"))
        {
            return TrimMaterial;
        }

        if (normalized.Contains("shell")
            || normalized.Contains("skin")
            || normalized.Contains("liner")
            || normalized.Contains("panel")
            || normalized.Contains("cheek")
            || normalized.Contains("fairing")
            || normalized.Contains("cove")
            || normalized.Contains("bulkhead")
            || normalized.Contains("service"))
        {
            return WallMaterial;
        }

        return null;
    }
}
