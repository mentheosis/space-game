# MX01 Scene Report

- Review scene: `ships/MX01/generated/scenes/mx01_collision_review.tscn`
- Playable scene: `ships/MX01/generated/scenes/mx01_playable_inspection.tscn`
- Status: `PASS`

## Referenced Artifacts

- `ships/MX01/source/mx01_normalized_skin.obj` sha256=`9558dd1c2fee857c58ba6792c2961c7b9b8e171c350c1d42528bf2c0a132cfca`
- `ships/MX01/generated/collision/mx01_boundary_surface_simplified.obj` sha256=`e4239e3e1b241deccf3c6a0dba4879f85ac6f5d20521dc07998fb86661cac64b`
- `ships/MX01/generated/collision/mx01_interior_collision.obj` sha256=`01ef15f36e4278d138aef7630b45c1018db8c25f3740844d6656324320be6a5f`
- `ships/MX01/generated/collision/mx01_dynamic_collision.obj` sha256=`c36054c1d05bdb3ce952d737321b5a9a5b1f1540754a74094c8ec8296bf7875b`
- `ships/MX01/generated/collision/mx01_interior_collision.json` sha256=`267aa2f5dd964f93b70d4b9eb829fb87fb317636a240ded3120b245c0e574824`

## Notes

The review scene references generated OBJ assets. The playable scene instances the real Player scene and generated StaticBody3D box collision from MX01 interior collision JSON.
