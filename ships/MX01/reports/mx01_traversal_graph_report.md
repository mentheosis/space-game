# MX01 Traversal Graph Report

- Method: `deck_overlap_traversal_graph_v1`
- Status: `PASS`
- Nodes: `6`
- Edges: `5`
- Reachable decks: `5 / 5`
- Warning edges: `0`
- Failing edges: `0`

## Edges

- `entry_ramp_candidate_to_lower_deck_candidate`: PASS, delta_y=0.0
- `forward_cockpit_lower_deck_01_to_forward_cockpit_lower_deck_02`: PASS, delta_y=2.0
- `forward_cockpit_lower_deck_02_to_mid_deck_candidate`: PASS, delta_y=5.0
- `lower_deck_candidate_to_mid_deck_candidate`: PASS, delta_y=3.5
- `mid_deck_candidate_to_upper_deck_candidate`: PASS, delta_y=3.5

## Notes

This graph proves coarse deck connectivity only. It does not yet prove ramp, stair, ladder, or capsule-sweep geometry.
