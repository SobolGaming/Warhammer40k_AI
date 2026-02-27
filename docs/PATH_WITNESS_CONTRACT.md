# PathWitness Contract

PathWitness artifacts are referenced by candidate metadata as `path_witness_ref` (`pathwitness://...`).

Artifact fields:
- `schema_version`
- `movement_type`
- `corridors`: compact per-model corridor descriptors
- `models`:
  - `model_id`
  - `path` steps (`translate`, `pivot`)
  - `final_pose` (`x`, `y`, `z`, `facing`)

Validation invariants:
- Witness path entries must be contiguous and complete.
- `final_pose` must match the move payload end pose.
- For normal moves, continuous segment checks reject paths that cross enemy engagement range.
- For normal moves, continuous sweep checks reject paths that cross blocking terrain between waypoints.
