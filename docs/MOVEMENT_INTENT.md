# MovementIntent and Candidate Metrics

`MovementIntent` is stored in move decision context under `movement_intent`.

Schema:
- `target_region_ids`: list of region ids
- `target_opportunity_ids`: list of opportunity ids
- `desired_affordances`: list of semantic goals (hold, deny, stage, action-enable, reserve-deny, lane-control)
- `screen_deny_targets`: list of deny lanes/regions
- `weights`: weighting map for intent preferences
- `anchors`: optional stable anchor ids
- `constraint_toggles`: optional constraint switches

Design note:
- `objective_targets` can exist as a late-bound execution field inside Tier 0 and Tier 2, but it is not the primary strategic abstraction.

Move candidate metadata includes:
- `candidate_kind` (`noop`, `move`, or `charge`)
- `solver_ms`
- `fallback_mode`
- `intent_hash`
- Headless move candidates now carry actual translated `model_positions` payloads rather than
  mirroring the unit's current footprint, so a selected `MOVE_UNIT` candidate represents a real
  battlefield relocation.
- solver/geometry fields:
  - `screen_coverage_score`
  - `coherency_score`
  - `threat_score`
  - `movement_distance_inches`
  - `distance_to_enemy_delta`
  - `distance_to_objective_delta`
- semantic projection fields:
  - `projected_score_delta_next_window`
  - `projected_deny_delta_next_window`
  - `projected_control_delta`
  - `projected_action_enablement_delta`
  - `projected_melee_staging_delta`
  - `projected_exposure_delta`
  - `cover_delta`
  - `los_delta`
  - `resource_delta`
- provenance fields:
  - `rules_provenance_refs`
- `path_witness_ref` for non-noop move candidates
- Charge `MOVE_UNIT` candidates are generated from declared `target_unit_ids` and aim to end
  in a legal engagement state rather than using the generic objective/staging translation path.
