# DecisionRecord Telemetry Contract

This appendix defines the runtime telemetry contract used by the engine when decisions are resolved.

Canonical schema:
- `docs/DECISION_RECORD_SCHEMA.json`

Runtime guarantees:
- A `DecisionRecord` is emitted for each resolved decision.
- Valid decisions (`valid=true`) include `chosen_action_id`, and that action is present in `candidates`.
- Invalid decisions (`valid=false`) include `invalid_attempt` and `rejection_reason`.
- For freeform human payloads (movement payloads with `model_positions`), the engine may inject a `HumanActionCandidate` so the chosen action is represented inside `candidates`.

Determinism fields:
- `global_seed`
- `decision_seed`
- deterministically ordered `candidates`
- `mask` aligned to `candidates`
