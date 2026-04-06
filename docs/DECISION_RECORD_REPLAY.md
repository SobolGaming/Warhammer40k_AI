# DecisionRecord Replay (Strict Mode)

`replay_decision_records(...)` replays decisions from telemetry records against a snapshot.

Strict mode guarantees:
- Runtime `candidates` must exactly match recorded `candidates`.
- Runtime `mask` must exactly match recorded `mask`.
- `chosen_action_id` must appear in recorded candidates.
- Resolution failure during strict replay raises an error immediately.

## Rules-Bundle Reproducibility Matrix (PR-AI-012)

Regression gate:
- `tests/test_rules_bundle_reproducibility_matrix.py`

Locked invariants:
- DecisionRecord logging:
  - recorded `rules_bundle` always matches game atomic ids.
  - recorded `rules_bundle_id` always matches the derived bundle id.
  - recorded `descriptor_bundle_id` always matches the compiled descriptor bundle used for the request.
  - recorded `version_adapter_boundary` preserves the active adapter-conditioned replay/training boundary.
- Snapshot save/load:
  - snapshot `game.ruleset` contains atomic ids and `rules_bundle_id`.
  - load preserves atomic ids and derived `rules_bundle_id`.
- StateBlob:
  - `canonical_omniscient_state(...)` and `player_obs_state(...)` include identical `rules_bundle` payloads.
  - `canonical_omniscient_state(...)` preserves `army_build_state`, `objectives`, `scoring_surfaces`, and `control_regions` across snapshot/replay round-trips.
- Strict replay round-trip:
  - replayed DecisionRecord keeps identical atomic `rules_bundle` and `rules_bundle_id` under `strict=True`.
  - replayed DecisionRecord keeps the original `descriptor_bundle_id` / `version_adapter_boundary` provenance and preserves the same public army-build/objective-site state surface.

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

When relabeling to a different rules bundle, semantic candidate metadata is recomputed
with decision-class projections (movement, targeting, charge, fight, tool) under the
target bundle, then persisted with updated `rules_provenance_refs`.

Relabeling does not discard original provenance:
- `descriptor_ids`
- `descriptor_bundle_id`
- `version_adapter_boundary`
- `omniscient_state.army_build_state`
- `omniscient_state.objectives`
- `omniscient_state.scoring_surfaces`
- `omniscient_state.control_regions`

The relabel CLI also prints a training-scope recommendation from
`docs/SEMANTIC_DIFF_CLASSIFIER.md` for adapter-first retraining selection.
