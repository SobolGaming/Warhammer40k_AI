# DecisionRecord Replay (Strict Mode)

`replay_decision_records(...)` replays decisions from telemetry records against a snapshot.

Strict mode guarantees:
- Runtime `candidates` must exactly match recorded `candidates`.
- Runtime `mask` must exactly match recorded `mask`.
- `chosen_action_id` must appear in recorded candidates.
- Resolution failure during strict replay raises an error immediately.

Expected strict failure modes:
- Candidate mismatch after engine behavior changes.
- Mask mismatch after legality/rules changes.
- Missing pending decision for recorded `decision_id`.
- Chosen action that cannot be mapped back to the current decision.

These failures are intentional and are used to detect replay drift.

Retention note:
- Runtime in-memory `DecisionRecordStore` is bounded (default `1024` records). Export records you need for long-horizon replay before pruning if your match exceeds that window.
