# Tier 1 Plan Schema

The engine now produces a deterministic Tier-1 plan per player per battle round and attaches it to decision contexts.

Context keys:
- `plan_id`
- `turn_plan`

`turn_plan` fields:
- `plan_id`
- `battle_round`
- `player_id`
- `primary_hold_objective_ids`
- `contest_objective_ids`
- `deny_opponent_primary_next_round`
- `secondary_posture` (`mode`, `discard_policy`)
- `risk_posture` (`variance`, `aggression`)
- `cp_budget` (`reserve_for_defense`, `max_offensive_spend_this_turn`)
- `unit_priority_tiers` (`P0`, `P1`, `P2`)

Heuristic baseline behavior:
- Holds already-controlled objectives.
- Contests non-controlled objectives.
- Sets risk posture from VP lead/deficit.
- Sets CP reserve posture from current CP.
