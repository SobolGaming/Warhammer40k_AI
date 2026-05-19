# Tier 1 Plan Schema

The engine produces a deterministic Tier-1 strategic-context plan per player per battle
round and attaches it to decision contexts. In the policy orchestration runtime this plan
is a reusable context artifact, not a required parent decision for every ranker.

Context keys:
- `plan_id`
- `turn_plan`
- `general_plan_id`
- `deployment_plan_id` for setup/deployment decisions
- `battle_round_plan_id`
- `deployment_dirty_flags` for setup/deployment decisions
- `deployment_replan_scope` for setup/deployment decisions
- `commander_dirty_flags`
- `commander_replan_scope`
- `last_commander_phase_report`

Audit/debug-only context keys:
- `general_plan`
- `deployment_plan`
- `battle_round_plan`

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

Runtime use:
- The orchestrator may build or refresh this plan at Command phase start or lazily when a decision benefits from strategic context.
- Lazy attachment is handled by `attach_ai_orchestration_context(...)` after rules, descriptor, and version-adapter context is attached and before time-budget decoration.
- A cached `GeneralPlan` supplies whole-game posture, transport doctrine, and
  limited-resource policy. Eligible requests receive `general_plan_id`; the
  full payload is audit/debug-only.
- A cached `DeploymentPlan` supplies setup/deployment posture. Deployment
  requests receive `deployment_plan_id`, `deployment_dirty_flags`,
  `deployment_replan_scope`, and unit-local deployment slices when applicable.
- A cached `BattleRoundPlan` is built from the Tier-1 plan plus the Tier-2 task bundle. Eligible requests receive `battle_round_plan_id`; unit-scoped requests receive the relevant local commander slices.
- The full `deployment_plan` dict is attached only when `request.context["include_full_deployment_plan"]` or `game.attach_full_deployment_plan_context` enables audit/debug payloads.
- The full `battle_round_plan` dict is attached only when `request.context["include_full_battle_round_plan"]` or `game.attach_full_battle_round_plan_context` enables audit/debug payloads.
- Incoming full `deployment_plan`, `battle_round_plan`, and `general_plan`
  payloads are removed unless the matching audit/debug opt-in is active, so
  cache keys do not silently inherit large plan dicts.
- Event-driven commander dirty flags and the last phase report are attached so downstream rankers can detect stale or variance-affected plans without triggering a full replan.
- Decision-specific rankers consume the plan through `request.context` when useful.
- A local reaction, dice, allocation, or simple tool decision may route without consulting a fresh Tier-1 plan.
- The engine remains authoritative for legality, masks, candidate generation, and state mutation.

See `docs/DEPLOYMENT_COMMANDER_PLAN.md` for the setup/deployment commander
schema and `docs/BATTLE_ROUND_COMMANDER_PLAN.md` for the cross-phase commander
plan schema.
