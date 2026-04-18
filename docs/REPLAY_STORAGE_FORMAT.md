# Replay Storage Format (SQLite v1)

This document defines the on-disk replay format used for step-by-step decision playback.

Canonical runtime module:
- `src/warhammer40k_ai/engine/replay_store.py`

## Goals

- Fast timeline browsing without loading full game state.
- Low memory playback for long PvP and human-vs-AI matches.
- Deterministic reconstruction of state at any decision index.

## File Format

- File extension: `.sqlite3` (default filename: `replay.sqlite3`)
- Format id: `wh40k_replay_sqlite_v1`
- Format version: `1`
- SQLite journal mode: `DELETE` (single portable replay file; no WAL sidecar dependency)

## Tables

### `meta`
- Key/value metadata (`format_id`, `format_version`, `created_at`, `updated_at`, `session_id`, `label`, `ruleset`, `keyframe_interval`, last offsets).

### `decision_steps`
- One row per accepted, settled decision in chronological order.
- Includes:
  - `decision_idx` (1-based timeline index)
  - decision identity (`decision_id`, `decision_type`)
  - actor metadata (`actor_player_id`, `controller_kind`)
  - chosen action metadata (`chosen_option_id`, `chosen_action_id`, `valid`)
  - timing (`wall_clock_ms`, `time_budget_ms`)
  - event linkage (`event_start_id`, `event_end_id`)
  - full DecisionRecord blob (compressed JSON)
- Step rows are persisted at `decision_resolved`, so nested follow-up decisions keep
  the same parent-before-child ordering that the engine validated at runtime.

### `events`
- Deterministic event log rows referenced by `decision_steps`.
- Includes `event_id`, `event_type`, `actor_id`, and compressed payload.

### `keyframes`
- Sparse full snapshots for fast seeking.
- Includes:
  - `decision_idx` represented by snapshot state
  - `event_id` watermark
  - compressed snapshot payload
  - snapshot hash
- Keyframe capture boundary: post-settlement (`decision_settled`) after all
  immediate follow-up handlers have completed for that decision.

## Compression

- JSON blobs are stored compressed with `zlib`.
- Replay blobs are JSON-normalized before compression, so dataclasses and engine
  objects with `to_dict()` payloads are persisted as plain JSON.
- Repeated timeline queries avoid decoding full snapshots or full DecisionRecords.

## Playback Model

Reader API supports:
- list decisions (`list_steps`)
- fetch one decision record (`get_decision_record`)
- fetch one decision request payload (`get_request_payload`)
- fetch events for a decision (`get_events_for_decision`)
- reconstruct state at decision `N` (`reconstruct_game_at_decision`)

State reconstruction strategy:
1. Load nearest keyframe at or before `N`.
2. Replay DecisionRecords from `keyframe_idx+1..N` with strict mode and event tail.
3. Reapply setup-only ownership side effects that are carried by recorded decisions rather than
   by standalone decision handlers. `CHOOSE_DEPLOYMENT_ZONE` restores the recorded player-to-zone
   assignment so later deployment legality checks use the same zone ownership as the original game.

Reconstruction guarantee:
- If a keyframe exists exactly at decision `N`, that snapshot already reflects
  post-follow-up settled state for decision `N`.

## Session Integration

Session store helpers:
- `enable_session_replay_recording(...)`
- `load_session_replay_reader(...)`
- Replay enablement is idempotent for a game instance (re-enabling replaces the
  recorder subscription group instead of stacking duplicate callbacks).

Autosave integration:
- `enable_phase_end_autosave(..., enable_replay=True)` enables replay capture by default.
