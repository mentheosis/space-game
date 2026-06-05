# MX01 Scene Report

- Review scene: `ships/MX01/generated/scenes/mx01_collision_review.tscn`
- Playable scene: `ships/MX01/generated/scenes/mx01_playable_inspection.tscn`
- Status: `PASS`

## Referenced Artifacts

- `ships/MX01/source/mx01_normalized_skin.obj` sha256=`9558dd1c2fee857c58ba6792c2961c7b9b8e171c350c1d42528bf2c0a132cfca`
- `ships/MX01/generated/collision/mx01_boundary_surface_simplified.obj` sha256=`e4239e3e1b241deccf3c6a0dba4879f85ac6f5d20521dc07998fb86661cac64b`
- `ships/MX01/generated/collision/mx01_interior_collision.obj` sha256=`307c6ffa9a5bd8861101275c04d8954305f85cd9904b053c9a33da2690958fa2`
- `ships/MX01/generated/collision/mx01_dynamic_collision.obj` sha256=`c36054c1d05bdb3ce952d737321b5a9a5b1f1540754a74094c8ec8296bf7875b`
- `ships/MX01/generated/collision/mx01_interior_collision.json` sha256=`74874d89386192ae51e93b4f54b73157d9497e804eb297038589bd2e821bebb4`

## Notes

The review scene references generated OBJ assets. The playable scene instances the real Player scene and generated StaticBody3D box collision from MX01 interior collision JSON.
