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

## Cross-Version Relabel

Relabeling is supported by:
- `src/warhammer40k_ai/engine/relabel.py`
- `scripts/relabel_decision_records.py`

CLI example:

```bash
python scripts/relabel_decision_records.py \
  --input data/decision_records.json \
  --output data/decision_records_relabeled.json \
  --core-rules-id core_11e \
  --rules-commentary-id commentary_11e \
  --mission-pack-id mission_11e \
  --terrain-pack-id terrain_11e \
  --dataslate-id dataslate_11e \
  --points-id points_11e \
  --faction-pack-id faction_11e \
  --detachment-pack-id detachment_11e
```

Relabel outputs include:
- `relabel_rules_bundle`
- `relabel_rules_bundle_id`
- `relabel_status`
- `relabel_candidate_map`
- `chosen_action_status_under_relabel`

The relabel CLI also prints a training-scope recommendation from
`docs/SEMANTIC_DIFF_CLASSIFIER.md` for adapter-first retraining selection.
