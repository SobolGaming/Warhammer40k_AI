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
- Cross-phase commander context is exposed separately as `unit_battle_task` and `commander_movement_task`. Movement rankers may use those fields to score future shooting/charge/fight enablement, but movement legality still comes from the normal movement validator and PathWitness contract.

Move candidate metadata includes:
- Movement-phase `SELECT_MOVEMENT_ACTION` candidates are endpoint-aware for headless
  control. The movement solver plans a destination first, annotates each action
  candidate with `planned_model_positions`, and marks redundant action labels in
  metadata. The headless controller then avoids the restrictive label when a less
  restrictive action can realize the same endpoint.
- `candidate_kind` (`noop`, `move`, or `charge`)
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
- Wall-clock solver timings are intentionally excluded from candidate metadata so
  profiled and unprofiled runs produce the same policy/training candidate
  surface.
- Charge `MOVE_UNIT` candidates are generated from declared `target_unit_ids` and aim to end
  in a legal engagement state rather than using the generic objective/staging translation path.
- In budgeted solving, charge candidates try bounded heuristic engagement endpoints before
  falling back to routed destination search, so headless self-play can keep charge generation responsive.

Movement action distance contract:
- Movement-phase `MOVE_UNIT` validation compares the selected action against the
  longest actual per-model displacement.
- `move` and `fall_back` cannot exceed the model's Normal Move distance.
- `advance` is rejected when every model endpoint is reachable with a Normal Move.
- Placement-style moves such as reserves arrival, redeploys, disembarks, and
  emergency disembarks are outside this action-distance derivation path.
