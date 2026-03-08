# DecisionRecord Telemetry Contract

This appendix defines the runtime telemetry contract used by the engine when decisions are resolved.

Canonical schema:
- `docs/DECISION_RECORD_SCHEMA.json`

Runtime guarantees:
- A `DecisionRecord` is emitted for each resolved decision.
- Every record includes decomposed `rules_bundle` ids plus convenience `rules_bundle_id`.
- Every record includes `descriptor_ids` (`mission/objective/terrain/deployment/tool`) used at record time.
- Decision context descriptor ids are compiled by Tier 0 (`docs/RULES_DESCRIPTOR_COMPILER.md`) and injected by `Game.request_decision(...)`.
- If a request is recorded without descriptor ids in context, `DecisionRecordStore` recompiles descriptor ids from current game state before emission.
- Candidate metadata is normalized to include portability semantic keys (`projected_*`, `cover_delta`, `los_delta`, `resource_delta`, `rules_provenance_refs`) for all decision types.
- Semantic numeric metadata is computed deterministically from decision context and candidate params (movement, deployment-pregame, targeting, charge, fight, and tool classes), rather than static heuristic defaults.
- Deployment candidates may include extra pregame deltas (`reserve_denial_delta`, `screen_integrity_delta`, `countercharge_coverage_delta`, `aura_connectivity_delta`, `projected_exposure_delta_if_enemy_goes_first`, `projected_melee_staging_delta`) in addition to portable `projected_*` keys.
- `outcome.immediate_deltas.actor_player_id` is recorded for each decision resolution and is used by reward-profile labeling.
- Valid decisions (`valid=true`) include `chosen_action_id`, and that action is present in `candidates`.
- Invalid decisions (`valid=false`) include `invalid_attempt` and `rejection_reason`.
- For freeform human payloads (movement payloads with `model_positions`), the engine may inject a `HumanActionCandidate` so the chosen action is represented inside `candidates`.
- Network auto-dice resolution paths (controller-hub and fallback event subscription) use the same `AutoDiceDecisionController` logic.
- In-memory retention is bounded: default `1024` records (`WH40K_DECISION_RECORD_MAX`), oldest-first pruning, with `dropped_records` tracking.

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
