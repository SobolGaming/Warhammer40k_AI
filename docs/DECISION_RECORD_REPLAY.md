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
- The replay recorder reserves a decision row from `decision_requested` before
  controller auto-resolution runs, and writes decision keyframes from
  `decision_resolved` before controller-hub follow-ups are drained. A keyframe
  for decision N therefore represents state after decision N only, not state
  from automatically resolved decision N+1.
- Decision controllers receive only the current FIFO queue head. If a nested
  request is published while an earlier request is still pending, controller
  dispatch waits until the earlier request resolves and then surfaces the new
  queue head. This prevents stale later candidates from being resolved against
  board state produced by intervening dice, damage, or movement decisions.
- Synchronous optional confirmation requests are the exception: when a rule
  needs an immediate yes/no answer while applying a parent decision, the
  controller hub may dispatch that confirmation before it becomes the FIFO head.
  The confirmation still records as its own decision and resolves before the
  parent decision completes.
- During reconstruction, recorded `REQUEST_DICE_ROLL` outcomes are injected back
  into live `get_roll(...)` calls. Nested dice consumed while applying a parent
  decision therefore use the original recorded value and do not create generic
  unlabeled replay rolls.
- Before returning a reconstructed game, replay syncs the visible battle phase
  from the selected decision step metadata. This keeps replay-viewer HUD phase
  labels aligned with Replay Controls without changing intermediate
  decision-handler replay semantics or overwriting turn-advance side effects.
- Replay-viewer HUD dice panes are bounded to the selected decision's own
  `decision_resolved` event. If a recorded decision step contains nested or
  follow-on decisions in its stored event range, later rolls remain visible on
  their own decision steps rather than leaking backward into the parent step.
- Movement-phase replay records parent choices before their automatic follow-up
  choices. A Move Units chain records the selected unit first, then its movement
  action, then any required Advance roll, then the resulting `MOVE_UNIT`
  endpoint payload.
- Voluntary movement-phase disembark choices use the same parent contract:
  the embarked unit is selected first, then its `DISEMBARK` choice is recorded.
- `SELECT_UNIT` option labels are replay-facing identifiers. When multiple units
  share the same datasheet/name within a roster, labels include roster ordinals
  such as `Rangers #1` and `Rangers #2`.
- Shooting- and fight-phase replay uses the same parent-before-child contract:
  selected unit decisions are recorded before declaration decisions, and
  declaration decisions are recorded before their attack-roll child decisions.
- A selected fight unit can legally have no remaining melee targets after prior
  attacks or fight-move effects remove engagement. In that case the activation
  still publishes `unit_fight_started`, `unit_fight_ended`, and
  `unit_activation_ended`, and the visible action log records that the fight
  activation ended with no eligible melee targets.
- Selected-unit workflows publish `unit_activation_started` and
  `unit_activation_ended` brackets; shooting and fight workflows also publish
  phase-specific brackets so reaction windows can subscribe to stable start/end
  boundaries.
- Replay-viewer overlays expand `MOVE_UNIT` endpoint payloads into per-model
  coordinates when `model_positions` are present, so movement and deployment
  steps do not appear as only a generic Confirm option.
- Session snapshot saves flush any replay event tail that occurred after the
  latest resolved decision and emit a terminal keyframe at the current
  `decision_idx`. Strict replay of `reconstruct_game_at_decision(decision_count)`
  therefore round-trips end-of-battle scoring and other post-decision terminal
  state without requiring a synthetic trailing decision.
- When multiple keyframes share the same `decision_idx`, strict replay uses the
  newest keyframe for that index.
- `scripts/audit_replay_decisions.py` performs a replay-facing sequence audit:
  parent/child decision ordering, duplicate selected-unit labels, dice-label
  quality, movement activation consistency, and strict reconstruction
  checkpoints. Fight `SELECT_UNIT` decisions that immediately advance to the
  next selection or end-turn decisions are accepted only when the decision's
  event range contains a matching fight-end event for the selected unit.
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

## Branch-Scoped RNG

Game-attached randomness is deterministic for the same seed and the same consumed
event-history prefix, but it is not a global stream whose future values can be
reused across divergent branches. Dice and other game random draws derive their
local RNG from:

- the game seed,
- the public deterministic event-history hash up to the draw,
- the random operation/context, and
- a per-operation/context counter.

This keeps replay and same-history reproduction stable while preventing
counterfactual training branches from learning that a future roll observed in a
baseline line will still be the next roll after a different action choice.
Strict replay treats recorded dice/roll events as authoritative outcomes rather
than validating them by advancing an RNG stream.

Retention note:
- Runtime in-memory `DecisionRecordStore` is bounded (default `4096` records). Export records you need for long-horizon replay before pruning if your match exceeds that window.

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
