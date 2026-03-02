# Tier 1 Plan Schema

The engine produces a deterministic Tier-1 plan per player per battle round and attaches it to decision contexts.

Context keys:
- `plan_id`
- `turn_plan`

`turn_plan` fields:
- `plan_id`
- `battle_round`
- `player_id`
- `scoring_windows`
- `priority_opportunities`
- `denial_opportunities`
- `staging_regions`
- `action_enablement_goals`
- `resource_posture`
- `risk_posture` (`variance`, `aggression`)
- `cp_budget` (`reserve_for_defense`, `max_offensive_spend_this_turn`)
- `unit_priority_tiers` (`P0`, `P1`, `P2`)

Example opportunity-oriented shape:

```yaml
turn_plan:
  plan_id: "plan_r2_p1"
  battle_round: 2
  player_id: "player_1"
  scoring_windows:
    - window_id: "next_primary"
      owner: "player_1"
      phase: "COMMAND"
      urgency: "HIGH"
  priority_opportunities:
    - opportunity_id: "opp_next_primary_hold_home"
      kind: "SCORING_SOURCE"
      source_ref: "score_source:primary_home"
      target_region_id: "region_home_left"
      horizon: "NEXT_SCORE_WINDOW"
      estimated_value: 4.5
  denial_opportunities:
    - opportunity_id: "opp_deny_mid_score"
      kind: "DENY_SOURCE"
      source_ref: "score_source:mid_primary"
      target_region_id: "region_mid_left"
      horizon: "NEXT_OPPONENT_SCORE_WINDOW"
      estimated_value: 3.0
  staging_regions:
    - "region_mid_staging_a"
  action_enablement_goals:
    - "enable_secondary_action_site_left"
  resource_posture:
    cp_spend_profile: "CONSERVATIVE"
    preserve_command_reactions: true
  risk_posture:
    variance: "MEDIUM"
    aggression: "MEDIUM"
  cp_budget:
    reserve_for_defense: 1
    max_offensive_spend_this_turn: 2
  unit_priority_tiers:
    P0: ["unit:home_anchor", "unit:primary_striker"]
    P1: ["unit:mid_trader_a", "unit:mid_trader_b"]
    P2: ["unit:backfield_action_piece"]
```

Heuristic baseline behavior:
- Prioritizes upcoming scoring windows and denial windows.
- Emits abstract opportunities bound to score sources and regions.
- Sets risk posture from VP lead/deficit.
- Sets CP/resource posture from current CP and expected exchanges.
