# Battle-Round Commander Plan

`BattleRoundPlan` is the cross-phase commander context for one player in one
battle round. It is built from the existing Tier-1 strategic plan and Tier-2
task bundle, cached by `(battle_round, player_id)`, and exposed to eligible
decision contexts through stable identifiers plus unit-local serializable
metadata.

The plan is not a legality source. Tier 0 candidate generation, masks,
validation, PathWitness generation, and command resolution remain authoritative.
The commander layer also carries event-driven dirty flags and phase reports so
later work can repair subplans without rescanning the full game after every
decision.

## Runtime Contract

- `Game.get_or_create_battle_round_plan(player_id)` returns the cached plan.
- `Game.get_commander_dirty_flags(player_id)` returns current repair pressure.
- `Game.mark_commander_dirty(...)` records event-driven repair pressure.
- `Game.clear_commander_dirty_flags(player_id)` resets repair pressure after a
  future repair implementation consumes it.
- `Game.get_commander_phase_reports(player_id)` returns recent phase summaries.
- Command phase start prebuilds the plan for the active player.
- `Game.request_decision(...)` attaches by default:
  - `battle_round_plan_id`
  - `commander_dirty_flags`
  - `commander_replan_scope`
  - `last_commander_phase_report` when one exists
  - `unit_battle_task` for unit-scoped decisions
  - `commander_movement_task`
  - `commander_fire_assignment`
  - `commander_charge_assignment`
  - `commander_fight_assignment`
- The full `battle_round_plan` payload is attached only for audit/debug
  contexts, either when `request.context["include_full_battle_round_plan"]` is
  true or when `game.attach_full_battle_round_plan_context` is true.
- Dice, allocation, and `n/a` decisions still skip strategic context.

## Plan Shape

Top-level fields:

- `plan_id`
- `player_id`
- `battle_round`
- `created_at_generation`
- `strategic_posture`
- `priority_targets`
- `unit_tasks`
- `movement_plan`
- `shooting_plan`
- `charge_plan`
- `fight_plan`
- `invalidation`
- `metadata`

`UnitBattleTask` is the cross-phase unit assignment:

- `unit_id`
- `role`
- `primary_target_unit_id`
- `backup_target_unit_ids`
- `movement_intent`
- `shooting_intent`
- `charge_intent`
- `fight_intent`
- `allowed_movement_actions`
- `forbidden_movement_actions`
- `desired_weapon_bands`
- `required_position_features`
- `risk_budget`
- `compute_tier`

Phase subplans carry late-bound execution hints:

- `MovementPhasePlan.unit_positioning_tasks`
- `ShootingPhasePlan.target_fire_plans`
- `ShootingPhasePlan.unit_fire_assignments`
- `ChargePhasePlan.unit_charge_assignments`
- `FightPhasePlan.unit_fight_assignments`

## Dirty Flags

Dirty flags are serializable, cumulative repair hints. Event subscribers set
them; local rankers may inspect them; the current implementation does not
automatically rebuild plans.

Fields:

- `movement_plan_dirty`
- `shooting_plan_dirty`
- `charge_plan_dirty`
- `fight_plan_dirty`
- `target_priorities_dirty`
- `objective_priorities_dirty`
- `cp_policy_dirty`
- `full_replan_required`
- `reasons`
- `max_severity`

Derived fields:

- `status`: `on_plan`, `minor_variance`, or `major_variance`
- `recommended_replan_scope`: `none`, `movement_only`, `shooting_only`,
  `charge_only`, `fight_only`, `phase`, or `full_round`

Current event mapping:

- `unit_move_ended`: dirty shooting and charge plans for the unit owner.
- `charge_move_failed`: dirty charge and fight plans for the unit owner.
- `unit_destroyed`: dirty target priorities and combat phase plans for relevant
  cached plans.
- `model_damage_resolved`: dirty target/fire-plan pressure for relevant plans.
- `unit_shooting_resolved`: dirty charge/fight follow-on plans for the shooter.
- `fight_attacks_resolved`: dirty fight and target-priority pressure.
- `objective_control_changed`: dirty movement and objective priorities for
  current cached plans.

## Phase Reports

At `phase_end`, the commander records a compact `PhaseExecutionReport`:

- `phase_name`
- `player_id`
- `plan_id`
- `status`
- `unit_reports`
- `target_reports`
- `objective_reports`
- `recommended_replan_scope`
- `metadata.dirty_flags`

The first implementation records dirty-flag summaries only. Future executors can
populate per-unit, per-target, and per-objective reports as they compare planned
intent with actual execution outcomes.

## Current Baseline

The first implementation is deliberately conservative:

- target priorities are deterministic enemy-unit wound estimates.
- unit roles derive from Tier-2 task types.
- movement tasks mirror Tier-2 target regions and eligibility posture.
- fire, charge, and fight assignments are serializable intent placeholders.
- dirty flags and phase reports are recorded from engine events.
- no phase behavior changes consume or clear repair pressure yet.

This establishes the stable data contract for later work where movement can
score LoS/range/trigger-band enablement, shooting can try preferred
declarations first, and charge/fight can execute or repair precommitted intent.
