# DecisionRecord Telemetry Contract

This appendix defines the runtime telemetry contract used by the engine when decisions are resolved.

Canonical schema:
- `docs/DECISION_RECORD_SCHEMA.json`

Runtime guarantees:
- A `DecisionRecord` is emitted for each resolved decision and for each rejected `RESOLVE_DECISION` command that can still be mapped to a pending request.
- Every record includes decomposed `rules_bundle` ids plus convenience `rules_bundle_id`.
- Every record includes `request_context`, a JSON-safe snapshot of the originating `DecisionRequest.context`, so replay audits can identify rule-specific timing such as `ability`, `battle_round`, source unit, and player context even when candidate payloads are compact.
- Optional Tier-1/Tier-2 orchestration context is recorded only as normal `request_context` data. Headless/evaluation LLM audit report keys such as `llm_adapter_traces` and `llm_adapter_trace_counts` are report payloads, not `DecisionRecord` schema fields.
- Limited-use ability records normalize consumable-resource context before emission: `limited_use`, `limited_use_scope`, and `limited_use_key` are present when a request carries explicit limited-use metadata, legacy `once_key` context, once-per-battle prompt text, or a known limited-use optional-confirmation key. Once-per-battle decisions also include `once_per_battle`, `once_per_battle_key`, and `once_per_battle_scope`; battle-round, turn, and phase windows include the corresponding `once_per_*` boolean/key fields. Battle-scoped multi-use abilities can include `limited_use_call_number` and `limited_use_max_uses`. `FIRE OVERWATCH` selector records are turn-scoped limited-use stratagem decisions.
- Every record includes `descriptor_ids` (`mission/objective/terrain/deployment/army-build/tool`) used at record time.
- Every record includes the compiled `descriptor_bundle_id` used for the request.
- Every record includes `version_adapter_boundary`, preserving the exact adapter-conditioned replay/training boundary that was active when the decision was made.
- Decision context descriptor ids are compiled by Tier 0 (`docs/RULES_DESCRIPTOR_COMPILER.md`) and injected by `Game.request_decision(...)`.
- If a request is recorded without descriptor ids in context, `DecisionRecordStore` recompiles descriptor ids from current game state before emission.
- If a request is recorded without `descriptor_bundle_id` / `version_adapter_boundary`, `DecisionRecordStore` reconstructs them from the active rules bundle plus compiled descriptors before emission.
- Candidate metadata is normalized to include portability semantic keys (`projected_*`, `cover_delta`, `los_delta`, `resource_delta`, `rules_provenance_refs`) for all decision types.
- Semantic numeric metadata is computed deterministically from decision context and candidate params (movement, deployment-pregame, targeting, charge, fight, and tool classes), rather than static heuristic defaults.
- Candidate metadata must not include wall-clock-derived performance fields such as `solver_ms`. Solver and profiling timings belong in record-level telemetry (`wall_clock_ms`) or sidecar profile/report artifacts, not in candidate features used for replay, ranking, or training.
- Reroll decisions with roll snapshots (`roll_state` / `roll_spec`) are scored from the concrete rolled dice: whole-roll rerolls (for example charge or Battle-shock tests) and single-die rerolls (for example fast-rolled hit/wound pools) project different expected-value deltas.
- Deployment candidates may include extra pregame deltas (`reserve_denial_delta`, `screen_integrity_delta`, `countercharge_coverage_delta`, `aura_connectivity_delta`, `projected_exposure_delta_if_enemy_goes_first`, `projected_melee_staging_delta`) in addition to portable `projected_*` keys.
- When deployment lookahead is enabled, deployment candidates may also include deterministic bounded rollout metadata (`lookahead_immediate_value`, `lookahead_worst_branch_value`, `lookahead_followup_value`, `lookahead_enemy_pressure`, `lookahead_total_value`) and `lookahead_base_*`/`lookahead_adjusted_*` projection fields.
- `outcome.immediate_deltas.actor_player_id` is recorded for each decision resolution and is used by reward-profile labeling.
- Valid decisions (`valid=true`) include `chosen_action_id`, and that action is present in `candidates`.
- Invalid decisions (`valid=false`) include `invalid_attempt` and `rejection_reason`; this includes command-level validation rejections such as malformed candidate payloads submitted through `RESOLVE_DECISION`.
- For freeform human payloads (movement payloads with `model_positions`), the engine may inject a `HumanActionCandidate` so the chosen action is represented inside `candidates`. Generated deployment placement decisions must resolve with the selected candidate payload, so replay-stable deployment `MOVE_UNIT` candidates are matched directly instead of being logged as injected human actions.
- Network auto-dice resolution paths (controller-hub and fallback event subscription) use the same `AutoDiceDecisionController` logic.
- Fight-phase target selection, melee weapon declaration, multi-target melee allocation, preview pile-in decisions, and preview consolidate decisions are emitted from the authoritative engine path in both UI and headless execution; replay/telemetry should therefore capture the same fight decision sequence regardless of controller type.
- Fight-phase `SELECT_UNIT` and `MOVE_UNIT` records may include `request_context.fight_scheduler`, `request_context.fight_stage_boundary`, and `request_context.fight_move_decision_categories`. These fields preserve scheduler stage, entitlement snapshots, pending pile-in/consolidate queues, `must_fight_next` constraints, and consolidate-to-engage/objective categories for replay and AI ranking without introducing faction-specific decision types.
- Movement-phase unit activation is exhaustive for alive battlefield units that are not embarked or in reserves. Explicit movement activations record move, advance, fall back, or remain-stationary choices; manual phase-end attempts mark unresolved units that can legally Remain Stationary as stationary and keep the phase open for units that still require a non-stationary movement activation. Reserves arrivals and disembarks from moved transports are marked as completed Normal moves.
- In-memory retention is bounded: default `1024` records (`WH40K_DECISION_RECORD_MAX`), oldest-first pruning, with `dropped_records` tracking.

Replay/relabel provenance surfaces inside `omniscient_state`:
- `army_build_state` including `army_build_descriptor_id`, detachments, attachment bindings, and Force Disposition
- `objectives`
- `scoring_surfaces`
- `control_regions`
- preview visibility marker state (`detection_markers`, `hidden_shooting_exemptions`)
- hidden/owning-player unit tactical state (`turn_provenance`, `status_tokens`)

These surfaces are preserved so replay, relabeling, and manifest slicing can condition on the same 11th-oriented runtime state that produced the original decision.

Validation guarantees:
- `DecisionRecordStore` rejects records whose `omniscient_state` omits required replay surfaces.
- `player_obs_state` entries are validated per-player, including `viewer_player_id` matching the owning player map key.
- Objective-site replay surfaces are validated for internal consistency: top-level `control_regions` and `scoring_surfaces` must be declared by some objective entry.
- `detachment_points_summary.spent` is always an integer; `budget` and `remaining` may be `null` until a detachment-point budget is authored for that army build.

Determinism fields:
- `global_seed`
- `decision_seed` (derived from stable decision identity and type, not request creation time)
- deterministically ordered `candidates`
- `mask` aligned to `candidates`
  - `true` means the runtime prevalidated the candidate payload against the same non-mutating legality checks used by authoritative resolution.
  - `false` means the candidate must not be auto-submitted by headless/UI controllers.
- `wall_clock_ms`, `expires_at`, and other wall-clock-derived diagnostics are explicitly excluded from deterministic equality checks. Determinism signatures also normalize Python memory-address substrings in object reprs that can appear in diagnostic outcome payloads. Use `warhammer40k_ai.engine.decision_record_determinism` for canonical profiled-vs-unprofiled signatures and digests.

Relabel tooling:
- Cross-version relabel helper: `src/warhammer40k_ai/engine/relabel.py`
- Batch relabel CLI: `scripts/relabel_decision_records.py`
- Semantic diff classifier: `src/warhammer40k_ai/engine/semantic_diff.py`

Reward labeling:
- Reward profiles: `src/warhammer40k_ai/engine/reward_profile.py`
- Reward annotation CLI: `scripts/annotate_decision_rewards.py`
