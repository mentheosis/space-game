# ShuttleA Blender Source Notes

This directory holds the editable Blender source for the ShuttleA ship interior.

Expected generated source file:

```text
assets/source/blender/ships/shuttle_a/shuttle_a_interior.blend
```

The `.blend` file should contain these collections:

- `Reference_Exterior`: imported ShuttleA exterior reference mesh.
- `Interior_Render`: authored visible interior shell, floor, cockpit, seat, hatch route, and structural forms.
- `Interior_Glass`: authored canopy glass and transparent cockpit pieces.
- `Collision_Proxy`: simplified collision guide meshes.
- `Markers`: hatch, seat, pilot eye, exit, and camera reference empties.
- `Review_Cameras`: optional Blender cameras matching Godot review angles.

Run:

```bash
scripts/bootstrap-shuttle-a-blender.sh
scripts/export-shuttle-a-blender.sh
scripts/validate-shuttle-a-modeling-workflow.sh
```

