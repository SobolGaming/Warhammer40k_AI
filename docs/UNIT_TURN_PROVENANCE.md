# Unit Turn Provenance And Status Tokens

PR-014H adds a normalized runtime layer for "what happened to this unit this
turn" and transient tactical conditions. The layer is preview-safe: it supports
11e preview mechanics without turning any faction-focus preview rule into live
faction data.

Runtime module:
- `src/warhammer40k_ai/engine/unit_turn_provenance.py`

Core records:
- `UnitTurnProvenance`
  - `set_up_this_turn`
  - `arrived_from_reserves_this_turn`
  - `made_normal_move`
  - `made_advance_move`
  - `made_fall_back_move`
  - `made_disembark_move`
  - `made_charge_move`
  - `shot_this_turn`
  - `shot_previous_player_turn`
  - `max_model_move_distance_this_turn`
  - `hidden_shooting_exemptions`
- `StatusToken` / `UnitCondition`
  - stable `token_id`
  - `unit_id`
  - `source_id`
  - generic `condition_kind`
  - `expires_at` as `PhaseBoundary`, `TurnBoundary`, or `Manual`
  - JSON-safe `payload`

Design rules:
- Heavy-style stationary checks should read `UnitTurnProvenance`, not bespoke
  faction state.
- Hidden clearing can be evaluated from `shot_this_turn` /
  `shot_previous_player_turn` while respecting `hidden_shooting_exemptions`.
- Bridgehead-style "set up this turn" bonuses are represented as generic
  `set_up_this_turn_modifier` tokens.
- Battle-shock preview persistence can be represented with a `battle_shock`
  token using manual expiry that names the required clearing condition rather
  than assuming automatic Command phase cleanup.
- Fight-order hooks such as Fights First injection and "must fight next" are
  represented as status tokens so PR-014I/PR-014J can make the scheduler act on
  them.

Serialization:
- Game snapshots store `unit_turn_provenance` and `status_tokens` per unit.
- State blobs version `1.8.0` expose those records on omniscient and
  owning-player unit entries.
- Player-observation state does not expose opponent hidden/owning-player unit
  provenance or tokens through the unit-entry hidden block.

Preview tests:
- `tests/preview_11e/test_unit_turn_provenance_golden.py`
