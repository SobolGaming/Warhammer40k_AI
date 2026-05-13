# DecisionRecord Replay (Strict Mode)

`replay_decision_records(...)` replays decisions from telemetry records against a snapshot.

Strict mode guarantees:
- Runtime `candidates` must exactly match recorded `candidates`.
- Runtime `mask` must exactly match recorded `mask`.
- `chosen_action_id` must appear in recorded candidates.
- Resolution failure during strict replay raises an error immediately.

Replay-store persistence note:
- On-disk `decision_steps` are keyed by unique `decision_id`; repeated captures
  of the same resolved decision update the existing row and preserve the widest
  recorded event range for that decision.
- Runtime `DecisionRecordStore` is also idempotent by `decision_id`. Duplicate
  resolution records merge into the existing in-memory record, preserving richer
  outcome data and the largest timing value.
- Headless self-play JSON export defensively deduplicates by `decision_id` before
  reward annotation and before writing the output file.
- Rejected `RESOLVE_DECISION` commands that still reference a pending request are
  persisted as invalid DecisionRecords so replay/event diagnostics and exported
  training records agree on malformed candidate attempts.
- Resolved option decisions may persist a JSON-safe
  `candidate.metadata.resolved_result_payload` for the chosen candidate. Replay
  uses that payload when the request option alone is not sufficient to reproduce
  the applied engine action, such as shooting declarations resolved from a
  generic confirm option.
- Replay remaps recorded unit/model ids onto snapshot-loaded runtime ids before
  resolving decisions. Duplicate unit names are disambiguated with model counts,
  alive model counts, and recorded positions from the omniscient state.
- Event-tail advancement is bounded to the event range recorded for the current
  decision step. Decisions whose request/resolution events were already captured
  in the nearest keyframe are replayed from their stored request payload without
  consuming later events.
- Session snapshot saves flush any replay event tail that occurred after the
  latest resolved decision and emit a terminal keyframe at the current
  `decision_idx`. Strict replay of `reconstruct_game_at_decision(decision_count)`
  therefore round-trips end-of-battle scoring and other post-decision terminal
  state without requiring a synthetic trailing decision.
- When multiple keyframes share the same `decision_idx`, strict replay uses the
  newest keyframe for that index.
- Replay reconstruction suppresses live charge-phase followup queueing. Recorded
  charge declarations, rolls, and moves are replayed from the persisted decision
  stream instead of allowing reconstruction-time auto-followups to create extra
  charge move requests.
- Snapshot-loaded rule manager state restores existing set-typed runtime fields
  as sets so replayed stratagem bookkeeping keeps the same mutation semantics as
  live play.
- Snapshot mission-card state preserves live entity references, but stale unit,
  model, or wargear references are stored and restored as stable ids. This keeps
  strict replay keyframes loadable when a secondary objective still records a
  target that has since left the live game graph.
- Snapshot unit state preserves normalized `unit_turn_provenance` and tactical
  `status_tokens`, so replay-visible Heavy/Hidden/reserve-entry and fight-order
  preview hooks do not depend on scattered transient booleans.

## Rules-Bundle Reproducibility Matrix (PR-AI-012)

Regression gate:
- `tests/test_rules_bundle_reproducibility_matrix.py`

Locked invariants:
- DecisionRecord logging:
  - recorded `rules_bundle` always matches game atomic ids.
  - recorded `rules_bundle_id` always matches the derived bundle id.
  - recorded `request_context` preserves the original decision context for audit and dataset slicing; strict replay still resolves against the live pending `DecisionRequest`.
  - recorded `descriptor_bundle_id` always matches the compiled descriptor bundle used for the request.
  - recorded `version_adapter_boundary` preserves the active adapter-conditioned replay/training boundary.
- Snapshot save/load:
  - snapshot `game.ruleset` contains atomic ids and `rules_bundle_id`.
  - load preserves atomic ids and derived `rules_bundle_id`.
- StateBlob:
- `canonical_omniscient_state(...)` and `player_obs_state(...)` include identical `rules_bundle` payloads.
- `canonical_omniscient_state(...)` preserves `army_build_state`, `objectives`, `scoring_surfaces`, `control_regions`, preview visibility marker state, and unit turn provenance/status-token state across snapshot/replay round-trips.
- `DecisionRecord` validation rejects replay payloads whose player-perspective snapshots lose their required replay surfaces or drift from their owning `viewer_player_id`.
- Strict replay round-trip:
  - replayed DecisionRecord keeps identical atomic `rules_bundle` and `rules_bundle_id` under `strict=True`.
  - replayed DecisionRecord keeps the original `descriptor_bundle_id` / `version_adapter_boundary` provenance and preserves the same public army-build/objective-site state surface.

Expected strict failure modes:
- Candidate mismatch after engine behavior changes.
- Mask mismatch after legality/rules changes.
- Missing pending decision for recorded `decision_id`.
- Chosen action that cannot be mapped back to the current decision.
- Movement-phase `MOVE_UNIT` records whose selected movement action does not
  match the recorded endpoint distance now fail validation. For example, an
  `advance` record whose model endpoints were all reachable by Normal Move is
  rejected instead of replayed as an Advance.
- Fight-phase replay expects scheduler context to remain stable for preview
  pile-in, unit-selection, and consolidate decisions. Drift in
  `fight_stage_boundary`, entitlement snapshots, pending stage queues, or
  `fight_move_decision_categories` is treated as ordinary decision-context
  drift and should be investigated like candidate or mask mismatch.

These failures are intentional and are used to detect replay drift.

Retention note:
- Runtime in-memory `DecisionRecordStore` is bounded (default `1024` records). Export records you need for long-horizon replay before pruning if your match exceeds that window.

## Cross-Version Relabel

Relabeling is supported by:
- `src/warhammer40k_ai/engine/relabel.py`
- `scripts/relabel_decision_records.py`

CLI example:

```bash
uv run python scripts/relabel_decision_records.py \
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
