# Training Reward Profiles

This document defines how to turn engine DecisionRecords into reward targets suitable for policy/value training.

Module:
- `src/warhammer40k_ai/engine/reward_profile.py`

CLI:
- `scripts/annotate_decision_rewards.py`

Operational runbook:
- `docs/HEADLESS_SELF_PLAY_RUNBOOK.md`

## Why this exists

Raw DecisionRecords are legality/telemetry artifacts. They are not automatically reward-labeled.
By default, `DecisionRecordStore` records `outcome.end_of_turn_return = 0.0`.

Reward annotation provides deterministic labels without changing legality/replay behavior.

## Profiles

Available profile ids:
- `dense_vp_delta_v1`
  - step shaping: `0.1 * VP-delta step change`
  - terminal return: `1.0 * final VP delta`
- `terminal_vp_delta_v1`
  - step shaping: `0.0`
  - terminal return: `1.0 * final VP delta`

Both profiles are deterministic and derived from `omniscient_state.players[*].score`.

## Actor attribution

Reward labeling uses `outcome.immediate_deltas.actor_player_id` when present.
If missing, it falls back to `omniscient_state.active_player_id`.

`DecisionRecordStore` now writes `actor_player_id` for every resolved decision.

## CLI usage

```bash
uv run python scripts/annotate_decision_rewards.py \
  --input data/decision_records_relabeled.json \
  --output data/decision_records_rewarded.json \
  --reward-profile dense_vp_delta_v1
```

## Recommended pre-training pipeline

1. Generate records:
   - `uv run python scripts/run_headless_self_play.py --games <N> --output data/decision_records_raw.json`
2. Relabel to target rules bundle:
   - `uv run python scripts/relabel_decision_records.py ...`
3. Annotate rewards:
   - `uv run python scripts/annotate_decision_rewards.py ...`
4. Build and enforce manifest gate:
   - `uv run python scripts/build_training_manifest.py --input ... --output ... --source-tag self_play --enforce-gate-profile`

## Quality notes

- Legal vs illegal actions are still enforced by the decision mask plus decision validation/command validation.
- Reward profiles do not legalize actions; they only label already-recorded decisions.
- Do not start expensive training runs until your dataset includes meaningful counts of core tactical decision types (movement/shooting/charge/fight), not only setup or optional ability prompts.
