# MX01 Dynamic Collision Report

- Method: `spatial_partition_compound_convex_boxes_v1`
- Status: `PASS`
- Convex regions: `7`
- Concave regions: `0`
- Skipped regions: `0`

## Regions

- `COL_MX01_dynamic_aft_body`: center=[0.0, 1.024418, -41.682209], size=[37.474242, 18.233627, 23.805961], source_vertices=10963
- `COL_MX01_dynamic_central_body`: center=[0.0, 4.043506, -4.266224], size=[12.548716, 12.300208, 51.477339], source_vertices=1494
- `COL_MX01_dynamic_forward_nose`: center=[4e-06, -0.659095, 37.414348], size=[12.548719, 19.069029, 32.34168], source_vertices=2606
- `COL_MX01_dynamic_port_lateral`: center=[14.255347, -2.997399, -28.601325], size=[3.472449, 5.22017, 2.913842], source_vertices=789
- `COL_MX01_dynamic_starboard_lateral`: center=[-14.255347, -2.997399, -28.601323], size=[3.47245, 5.220171, 2.913842], source_vertices=790
- `COL_MX01_dynamic_belly_support`: center=[1e-06, -4.737853, -28.601323], size=[31.825199, 1.739262, 2.913842], source_vertices=550
- `COL_MX01_dynamic_upper_superstructure`: center=[1e-06, 6.739216, -4.263012], size=[9.623068, 6.908787, 51.470915], source_vertices=1088

## Notes

First-pass dynamic collision uses simple convex boxes. It is suitable for broad moving-ship physics tests, not final skin fit.
