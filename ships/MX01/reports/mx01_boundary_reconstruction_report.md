# MX01 Boundary Reconstruction Report

- Method: `voxel_exposed_faces_boundary_v1`
- Status: `PASS`
- Inside voxels: `83510`
- Boundary quads: `37856`
- OBJ vertices: `37155`
- Theoretical max surface error: `0.25`

## Orientation Counts

- `x_neg`: 6132
- `x_pos`: 6132
- `y_neg`: 8867
- `y_pos`: 8867
- `z_neg`: 3929
- `z_pos`: 3929

## Notes

This is the deterministic exposed-voxel boundary baseline. It is suitable for review and simplification, but it does not yet replace the planned marching-cubes or dual-contouring surface.
