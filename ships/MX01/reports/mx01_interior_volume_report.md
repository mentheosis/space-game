# MX01 Interior Volume Report

- Method: `occupancy_clearance_deck_band_extraction_v1`
- Status: `PASS`
- Clearance cells: `4`
- Walkable Y levels: `36`
- Candidate components: `100`
- Accepted deck candidates: `3`

## Accepted Deck Candidates

### lower_deck_candidate

- Y: `-4.25`
- Estimated area: `435.25 m2`
- Largest component area: `131.0 m2`
- Bounds: `{'min': [-13.75, -4.25, -38.25], 'max': [13.75, -4.25, -29.25], 'size': [27.5, 0.0, 9.0]}`

### mid_deck_candidate

- Y: `-0.75`
- Estimated area: `925.5 m2`
- Largest component area: `862.0 m2`
- Bounds: `{'min': [-5.75, -0.75, -34.75], 'max': [5.75, -0.75, 48.75], 'size': [11.5, 0.0, 83.5]}`

### upper_deck_candidate

- Y: `2.75`
- Estimated area: `638.75 m2`
- Largest component area: `638.75 m2`
- Bounds: `{'min': [-4.75, 2.75, -38.25], 'max': [4.75, 2.75, 43.25], 'size': [9.5, 0.0, 81.5]}`

## Notes

First-pass deck candidates require traversal graph fitting before they are accepted as gameplay collision.
