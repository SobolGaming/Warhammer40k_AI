# DecisionRecord Telemetry Contract

This appendix defines the runtime telemetry contract used by the engine when decisions are resolved.

Canonical schema:
- `docs/DECISION_RECORD_SCHEMA.json`

Runtime guarantees:
- A `DecisionRecord` is emitted for each resolved decision.
- Every record includes decomposed `rules_bundle` ids plus convenience `rules_bundle_id`.
- Every record includes `descriptor_ids` (`mission/objective/terrain/deployment/army-build/tool`) used at record time.
- Every record includes the compiled `descriptor_bundle_id` used for the request.
- Every record includes `version_adapter_boundary`, preserving the exact adapter-conditioned replay/training boundary that was active when the decision was made.
- Decision context descriptor ids are compiled by Tier 0 (`docs/RULES_DESCRIPTOR_COMPILER.md`) and injected by `Game.request_decision(...)`.
- If a request is recorded without descriptor ids in context, `DecisionRecordStore` recompiles descriptor ids from current game state before emission.
- If a request is recorded without `descriptor_bundle_id` / `version_adapter_boundary`, `DecisionRecordStore` reconstructs them from the active rules bundle plus compiled descriptors before emission.
- Candidate metadata is normalized to include portability semantic keys (`projected_*`, `cover_delta`, `los_delta`, `resource_delta`, `rules_provenance_refs`) for all decision types.
- Semantic numeric metadata is computed deterministically from decision context and candidate params (movement, deployment-pregame, targeting, charge, fight, and tool classes), rather than static heuristic defaults.
- Reroll decisions with roll snapshots (`roll_state` / `roll_spec`) are scored from the concrete rolled dice: whole-roll rerolls (for example charge or Battle-shock tests) and single-die rerolls (for example fast-rolled hit/wound pools) project different expected-value deltas.
- Deployment candidates may include extra pregame deltas (`reserve_denial_delta`, `screen_integrity_delta`, `countercharge_coverage_delta`, `aura_connectivity_delta`, `projected_exposure_delta_if_enemy_goes_first`, `projected_melee_staging_delta`) in addition to portable `projected_*` keys.
- When deployment lookahead is enabled, deployment candidates may also include deterministic bounded rollout metadata (`lookahead_immediate_value`, `lookahead_worst_branch_value`, `lookahead_followup_value`, `lookahead_enemy_pressure`, `lookahead_total_value`) and `lookahead_base_*`/`lookahead_adjusted_*` projection fields.
- `outcome.immediate_deltas.actor_player_id` is recorded for each decision resolution and is used by reward-profile labeling.
- Valid decisions (`valid=true`) include `chosen_action_id`, and that action is present in `candidates`.
- Invalid decisions (`valid=false`) include `invalid_attempt` and `rejection_reason`.
- For freeform human payloads (movement payloads with `model_positions`), the engine may inject a `HumanActionCandidate` so the chosen action is represented inside `candidates`.
- Network auto-dice resolution paths (controller-hub and fallback event subscription) use the same `AutoDiceDecisionController` logic.
- Fight-phase target selection, melee weapon declaration, and multi-target melee allocation are emitted from the authoritative engine path in both UI and headless execution; replay/telemetry should therefore capture the same fight decision sequence regardless of controller type.
- In-memory retention is bounded: default `1024` records (`WH40K_DECISION_RECORD_MAX`), oldest-first pruning, with `dropped_records` tracking.

Replay/relabel provenance surfaces inside `omniscient_state`:
- `army_build_state` including `army_build_descriptor_id`, detachments, attachment bindings, and Force Disposition
- `objectives`
- `scoring_surfaces`
- `control_regions`

These surfaces are preserved so replay, relabeling, and manifest slicing can condition on the same 11th-oriented runtime state that produced the original decision.

Validation guarantees:
- `DecisionRecordStore` rejects records whose `omniscient_state` omits required replay surfaces.
- `player_obs_state` entries are validated per-player, including `viewer_player_id` matching the owning player map key.
- Objective-site replay surfaces are validated for internal consistency: top-level `control_regions` and `scoring_surfaces` must be declared by some objective entry.
- `detachment_points_summary.spent` is always an integer; `budget` and `remaining` may be `null` until a detachment-point budget is authored for that army build.

Determinism fields:
- `global_seed`
- `decision_seed`
- deterministically ordered `candidates`
- `mask` aligned to `candidates`

Relabel tooling:
- Cross-version relabel helper: `src/warhammer40k_ai/engine/relabel.py`
- Batch relabel CLI: `scripts/relabel_decision_records.py`
- Semantic diff classifier: `src/warhammer40k_ai/engine/semantic_diff.py`

Reward labeling:
- Reward profiles: `src/warhammer40k_ai/engine/reward_profile.py`
- Reward annotation CLI: `scripts/annotate_decision_rewards.py`
