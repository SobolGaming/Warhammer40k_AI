# MovementIntent and Candidate Metrics

`MovementIntent` is stored in move decision context under `movement_intent`.

Schema:
- `objective_targets`: list of objective ids
- `screen_deny_targets`: list of deny lanes/regions
- `weights`:
  - `screen_coverage`
  - `coherency`
  - `threat_avoid`
  - `obj_proximity`
- `anchors`: optional stable anchor ids
- `constraint_toggles`: optional constraint switches

Move candidate metadata includes:
- `candidate_kind` (`noop` or `move`)
- `solver_ms`
- `fallback_mode`
- `intent_hash`
- scoring fields:
  - `screen_coverage_score`
  - `coherency_score`
  - `threat_score`
  - `objective_score`
- `path_witness_ref` for non-noop move candidates
