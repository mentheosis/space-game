# MX01 Simplification Report

- Method: `greedy_coplanar_voxel_face_merge_v1`
- Status: `PASS`
- Input quads: `37856`
- Output quads: `6900`
- Quad reduction: `81.773%`
- Output OBJ vertices: `8769`
- Max surface error: `0.0`
- Max normal error: `0.0`
- Byte-stability check: `PASS_BY_DETERMINISTIC_SORTING`

## Notes

This simplification merges coplanar voxel boundary cells into larger quads. It is deterministic and preserves the voxel boundary, but it is not final visual-quality decimation.
