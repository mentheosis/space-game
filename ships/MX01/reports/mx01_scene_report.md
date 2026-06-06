# MX01 Scene Report

- Review scene: `ships/MX01/generated/scenes/mx01_collision_review.tscn`
- Playable scene: `ships/MX01/generated/scenes/mx01_playable_inspection.tscn`
- Status: `PASS`
- Stair walkable support shapes: `53`
- Stair transition support aprons: `7`
- Hatch ramp support shapes: `3`
- Visible hatch ramp meshes: `3`
- Stair transition floor keepout shapes: `18`

## Referenced Artifacts

- `ships/MX01/source/mx01_normalized_skin.obj` sha256=`9558dd1c2fee857c58ba6792c2961c7b9b8e171c350c1d42528bf2c0a132cfca`
- `ships/MX01/generated/collision/mx01_boundary_surface_simplified.obj` sha256=`e4239e3e1b241deccf3c6a0dba4879f85ac6f5d20521dc07998fb86661cac64b`
- `ships/MX01/generated/collision/mx01_interior_collision.obj` sha256=`3154417eb95b6267514e5692c25f395525d14328b5d745ba825c9746a7b4e876`
- `ships/MX01/generated/collision/mx01_interior_enclosure.obj` sha256=`2efc57e27a92bb4e7400abc33f6b9150a33b7d6d0a376a58f2503cfdd15f9fcc`
- `ships/MX01/generated/collision/mx01_dynamic_collision.obj` sha256=`c36054c1d05bdb3ce952d737321b5a9a5b1f1540754a74094c8ec8296bf7875b`
- `ships/MX01/generated/collision/mx01_interior_collision.json` sha256=`7c1765a969d2e0b62b659a1af030e6b7299f1d2eae24e2e422e535dafad332f1`
- `ships/MX01/generated/collision/mx01_interior_enclosure.json` sha256=`888032e0aa42a6b371f59a1905df82db3a1fa8d1d1519f16b388400672928843`

## Notes

The review scene references generated OBJ assets. The playable scene instances the real Player scene, Stage 7A StaticBody3D box collision from MX01 interior collision JSON, Stage 7A stair treads as nonblocking walkable support surfaces on physics layer 128, and Stage 7B controller-safe BoxShape3D enclosure primitives from MX01 interior enclosure JSON.
