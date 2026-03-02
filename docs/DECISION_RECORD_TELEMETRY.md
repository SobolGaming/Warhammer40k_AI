# DecisionRecord Telemetry Contract

This appendix defines the runtime telemetry contract used by the engine when decisions are resolved.

Canonical schema:
- `docs/DECISION_RECORD_SCHEMA.json`

Runtime guarantees:
- A `DecisionRecord` is emitted for each resolved decision.
- Every record includes decomposed `rules_bundle` ids plus convenience `rules_bundle_id`.
- Every record includes `descriptor_ids` (`mission/objective/terrain/deployment/tool`) used at record time.
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
