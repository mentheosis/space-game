using Godot;

public static class PrototypeShuttleLightingRig
{
    public static void AddInteriorPracticalLights(Node parent)
    {
        AddSpot(parent, "RampPoolLeft", new Vector3(-1.45f, -0.70f, -1.70f), new Vector3(-0.35f, -2.25f, -3.20f), 3.45f, 8.0f, 34.0f, new Color(1.0f, 0.74f, 0.45f));
        AddSpot(parent, "RampPoolRight", new Vector3(1.45f, -0.70f, -1.70f), new Vector3(0.35f, -2.25f, -3.20f), 3.45f, 8.0f, 34.0f, new Color(1.0f, 0.74f, 0.45f));
        AddSpot(parent, "RampDoorHingeWarmWash", new Vector3(0.0f, -1.26f, -0.35f), new Vector3(0.0f, -2.95f, -2.70f), 2.6f, 6.0f, 32.0f, new Color(1.0f, 0.70f, 0.42f));
        AddSpot(parent, "RampGuideLightLeft", new Vector3(-1.18f, -1.28f, -0.42f), new Vector3(-0.45f, -2.35f, -2.80f), 1.45f, 4.5f, 28.0f, new Color(1.0f, 0.72f, 0.42f));
        AddSpot(parent, "RampGuideLightRight", new Vector3(1.18f, -1.28f, -0.42f), new Vector3(0.45f, -2.35f, -2.80f), 1.45f, 4.5f, 28.0f, new Color(1.0f, 0.72f, 0.42f));

        foreach (var z in new[] { 1.4f, 3.0f, 4.6f, 6.2f, 7.8f })
        {
            AddSpot(parent, $"CargoCeilingPool{z:0.0}", new Vector3(0.0f, 2.68f, z), new Vector3(0.0f, -1.32f, z + 0.18f), 3.45f, 6.8f, 36.0f, new Color(1.0f, 0.82f, 0.60f));
            AddSpot(parent, $"CargoLeftRoofSidePool{z:0.0}", new Vector3(-2.62f, 2.22f, z + 0.24f), new Vector3(-2.90f, -1.36f, z + 0.36f), 4.15f, 7.2f, 36.0f, new Color(1.0f, 0.76f, 0.48f));
            AddSpot(parent, $"CargoRightRoofSidePool{z:0.0}", new Vector3(2.62f, 2.22f, z + 0.24f), new Vector3(2.90f, -1.36f, z + 0.36f), 4.15f, 7.2f, 36.0f, new Color(1.0f, 0.76f, 0.48f));
            AddSpot(parent, $"CargoLeftWallWash{z:0.0}", new Vector3(-2.28f, 2.10f, z + 0.10f), new Vector3(-3.18f, -0.62f, z + 0.32f), 4.10f, 7.0f, 38.0f, new Color(1.0f, 0.72f, 0.44f));
            AddSpot(parent, $"CargoRightWallWash{z:0.0}", new Vector3(2.28f, 2.10f, z + 0.10f), new Vector3(3.18f, -0.62f, z + 0.32f), 4.10f, 7.0f, 38.0f, new Color(1.0f, 0.72f, 0.44f));
            AddSpot(parent, $"CargoLeftLowPractical{z:0.0}", new Vector3(-3.08f, -0.72f, z + 0.18f), new Vector3(-0.85f, -1.42f, z + 0.45f), 1.85f, 4.8f, 30.0f, new Color(1.0f, 0.66f, 0.38f));
            AddSpot(parent, $"CargoRightLowPractical{z:0.0}", new Vector3(3.08f, -0.72f, z + 0.18f), new Vector3(0.85f, -1.42f, z + 0.45f), 1.85f, 4.8f, 30.0f, new Color(1.0f, 0.66f, 0.38f));
        }

        AddSpot(parent, "LandingPoolLeft", new Vector3(-1.55f, 1.92f, -2.35f), new Vector3(-1.70f, 0.78f, -1.05f), 2.0f, 5.4f, 34.0f, new Color(0.78f, 0.92f, 1.0f));
        AddSpot(parent, "LandingPoolRight", new Vector3(1.55f, 1.92f, -2.35f), new Vector3(1.70f, 0.78f, -1.05f), 2.0f, 5.4f, 34.0f, new Color(0.78f, 0.92f, 1.0f));
        AddSpot(parent, "LeftStairCoolMarkerWash", new Vector3(-2.42f, 0.46f, -0.80f), new Vector3(-2.05f, -0.80f, 0.65f), 1.35f, 3.8f, 30.0f, new Color(0.56f, 0.82f, 1.0f));
        AddSpot(parent, "RightStairCoolMarkerWash", new Vector3(2.42f, 0.46f, -0.80f), new Vector3(2.05f, -0.80f, 0.65f), 1.35f, 3.8f, 30.0f, new Color(0.56f, 0.82f, 1.0f));
        AddSpot(parent, "CockpitEntryRouteCue", new Vector3(0.0f, 1.44f, -5.15f), new Vector3(0.0f, 0.96f, -4.10f), 1.10f, 3.4f, 30.0f, new Color(1.0f, 0.72f, 0.42f));
        AddSpot(parent, "CockpitApproachLeftPoolA", new Vector3(-1.34f, 1.18f, -5.92f), new Vector3(-0.20f, 0.92f, -6.18f), 2.15f, 4.6f, 33.0f, new Color(1.0f, 0.73f, 0.45f));
        AddSpot(parent, "CockpitApproachRightPoolA", new Vector3(1.34f, 1.18f, -5.92f), new Vector3(0.20f, 0.92f, -6.18f), 2.15f, 4.6f, 33.0f, new Color(1.0f, 0.73f, 0.45f));
        AddSpot(parent, "CockpitApproachLeftPoolB", new Vector3(-1.34f, 1.18f, -7.42f), new Vector3(-0.18f, 0.92f, -7.70f), 2.05f, 4.5f, 32.0f, new Color(0.95f, 0.78f, 0.56f));
        AddSpot(parent, "CockpitApproachRightPoolB", new Vector3(1.34f, 1.18f, -7.42f), new Vector3(0.18f, 0.92f, -7.70f), 2.05f, 4.5f, 32.0f, new Color(0.95f, 0.78f, 0.56f));
        AddSpot(parent, "CockpitApproachLeftPoolC", new Vector3(-1.34f, 1.18f, -8.92f), new Vector3(-0.18f, 0.92f, -9.20f), 1.90f, 4.3f, 31.0f, new Color(0.82f, 0.90f, 1.0f));
        AddSpot(parent, "CockpitApproachRightPoolC", new Vector3(1.34f, 1.18f, -8.92f), new Vector3(0.18f, 0.92f, -9.20f), 1.90f, 4.3f, 31.0f, new Color(0.82f, 0.90f, 1.0f));
        AddSpot(parent, "CockpitApproachLeftPoolD", new Vector3(-1.34f, 1.18f, -10.42f), new Vector3(-0.20f, 0.92f, -10.75f), 1.65f, 3.9f, 30.0f, new Color(0.74f, 0.86f, 1.0f));
        AddSpot(parent, "CockpitApproachRightPoolD", new Vector3(1.34f, 1.18f, -10.42f), new Vector3(0.20f, 0.92f, -10.75f), 1.65f, 3.9f, 30.0f, new Color(0.74f, 0.86f, 1.0f));
        AddSpot(parent, "CockpitDashboardCoolLeft", new Vector3(-0.72f, 1.30f, -14.36f), new Vector3(-0.18f, 1.05f, -13.32f), 1.95f, 3.9f, 34.0f, new Color(0.46f, 0.76f, 1.0f));
        AddSpot(parent, "CockpitDashboardCoolRight", new Vector3(0.72f, 1.30f, -14.36f), new Vector3(0.18f, 1.05f, -13.32f), 1.95f, 3.9f, 34.0f, new Color(0.46f, 0.76f, 1.0f));
        AddSpot(parent, "CockpitLowerBulkheadWarm", new Vector3(0.0f, 1.22f, -14.98f), new Vector3(0.0f, 1.02f, -13.78f), 1.70f, 3.6f, 32.0f, new Color(1.0f, 0.70f, 0.42f));
        AddSpot(parent, "CockpitConsoleWarmPractical", new Vector3(0.0f, 1.34f, -14.05f), new Vector3(0.0f, 1.04f, -13.42f), 1.35f, 3.2f, 30.0f, new Color(1.0f, 0.70f, 0.42f));
        AddSpot(parent, "CockpitLeftMetalSidePractical", new Vector3(-1.30f, 1.22f, -13.18f), new Vector3(-0.52f, 1.10f, -13.42f), 1.12f, 3.1f, 30.0f, new Color(0.45f, 0.78f, 1.0f));
        AddSpot(parent, "CockpitRightMetalSidePractical", new Vector3(1.30f, 1.22f, -13.18f), new Vector3(0.52f, 1.10f, -13.42f), 1.12f, 3.1f, 30.0f, new Color(0.45f, 0.78f, 1.0f));
        AddSpot(parent, "CockpitFootwellPanelLight", new Vector3(0.0f, 1.10f, -13.10f), new Vector3(0.0f, 0.98f, -13.70f), 1.08f, 3.0f, 30.0f, new Color(0.74f, 0.86f, 1.0f));
    }

    private static void AddSpot(Node parent, string name, Vector3 position, Vector3 target, float energy, float range, float angle, Color color)
    {
        var light = new SpotLight3D
        {
            Name = name,
            Position = position,
            LightEnergy = energy,
            LightColor = color,
            SpotRange = range,
            SpotAngle = angle,
            SpotAngleAttenuation = 2.15f,
            ShadowEnabled = true
        };
        light.Transform = new Transform3D(Basis.Identity, position).LookingAt(target, Vector3.Up);
        parent.AddChild(light);
    }
}
