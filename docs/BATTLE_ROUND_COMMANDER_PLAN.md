# Battle-Round Commander Plan

`BattleRoundPlan` is the cross-phase commander context for one player in one
battle round. It sits below the game-level `GeneralPlan` and the setup-level
`DeploymentPlan`, and above the phase rankers. It is built from the existing
Tier-1 strategic plan, Tier-2 task bundle, and active game-level `GeneralPlan`,
cached by `(battle_round, player_id)`, and exposed to eligible decision
contexts through stable
identifiers plus unit-local serializable metadata.

The plan is not a legality source. Tier 0 candidate generation, masks,
validation, PathWitness generation, and command resolution remain authoritative.
The commander layer also carries event-driven dirty flags and phase reports so
later work can repair subplans without rescanning the full game after every
decision.

## Runtime Contract

- `Game.get_or_create_battle_round_plan(player_id)` returns the cached plan.
- `Game.get_or_create_general_plan(player_id)` returns the cached game-level
  General plan that owns long-horizon resource and transport doctrine.
- `Game.get_or_create_deployment_plan(player_id)` returns the cached
  setup/deployment commander plan that owns uncertainty-aware initial posture.
- `Game.get_or_create_deployment_order_bundle(player_id)` returns compiled
  General-to-deployment intent.
- `Game.get_or_create_prebattle_order_bundle(player_id)` returns compiled
  Scout/Infiltrate/pre-battle intent.
- `Game.get_commander_dirty_flags(player_id)` returns current repair pressure.
- `Game.mark_commander_dirty(...)` records event-driven repair pressure.
- `Game.clear_commander_dirty_flags(player_id, consumed_scope=...)` resets or
  downgrades repair pressure after the matching checkpoint consumes it.
- `Game.get_commander_phase_reports(player_id)` returns recent phase summaries.
- `Game.record_orchestration_audit_event(...)` records compact General,
  Deployment, Commander, and decision-context audit events.
- `Game.get_orchestration_audit_events(...)` returns the bounded audit history.
- `Game.get_orchestration_audit_counters()` returns event-kind counters.
- Command phase start prebuilds the plan for the active player.
- `Game.request_decision(...)` attaches by default:
  - `general_plan_id`
  - `deployment_order_bundle_id` for deployment/pre-battle contexts
  - `prebattle_order_bundle_id` for deployment/pre-battle contexts
  - `battle_round_plan_id`
  - `commander_order_bundle_id`
  - `commander_dirty_flags`
  - `commander_replan_scope`
  - `last_commander_phase_report` when one exists
  - `unit_battle_task` for unit-scoped decisions
  - `commander_movement_task`
  - `commander_transport_assignment`
  - `commander_embark_assignment` for planned embark decisions
  - `commander_disembark_assignment` for planned stay/disembark decisions
  - `commander_fire_assignment`
  - `preferred_target_unit_ids` for unit-scoped shooting decisions
  - `preferred_declarations` when the commander has prebuilt declaration
    hints
  - `target_fire_plan_summary` for the unit's primary fire target
  - `commander_charge_assignment`
  - `commander_fight_assignment`
  - `commander_candidate_charge_assignments` for charge-phase unit selection
    requests
  - `commander_candidate_fight_assignments` for fight-phase unit selection
    requests
  - `commander_resource_authorizations` for unit-owned authorized resources
  - `general_limited_resource_policy` for resources relevant to the unit plus
    global CP/stratagem reserves
  - `general_cp_policy`
- The full `battle_round_plan` payload is attached only for audit/debug
  contexts, either when `request.context["include_full_battle_round_plan"]` is
  true or when `game.attach_full_battle_round_plan_context` is true.
- The full `general_plan` payload follows the same audit/debug rule via
  `request.context["include_full_general_plan"]` or
  `game.attach_full_general_plan_context`.
- Deployment decisions follow the same slim-context rule via
  `deployment_plan_id` and unit-local deployment slices. The full
  `deployment_plan` payload is attached only through
  `request.context["include_full_deployment_plan"]` or
  `game.attach_full_deployment_plan_context`.
- A caller-provided `battle_round_plan` payload is stripped unless the same
  audit/debug opt-in is active, including for decisions that skip strategic
  context.
- A caller-provided `general_plan` payload is stripped unless the same
  audit/debug opt-in is active.
- A caller-provided `deployment_plan` payload is stripped unless deployment
  audit/debug opt-in is active.
- Full `deployment_order_bundle`, `prebattle_order_bundle`, and
  `commander_order_bundle` payloads are attached only through explicit
  audit/debug opt-in.
- Dice, allocation, and `n/a` decisions still skip strategic context.

## Orchestration Audit Events

Orchestration audit events are compact telemetry records for plan lifecycle and
context attachment. Each event contains:

- `sequence`
- `event_kind`
- `battle_round`
- `player_id`
- `plan_id`
- compact serializable `metadata`

The in-memory event history is bounded to the latest 256 events, while counters
remain cumulative per event kind. This is separate from `DecisionRecord`
telemetry: audit events explain which orchestration plans, dirty flags, repair
scopes, and context slices were available around a decision; DecisionRecords
remain the authoritative replay/audit artifact for the decision itself.

Current event kinds include:

- `general_plan_built`
- `deployment_plan_built`
- `deployment_plan_dirty_marked`
- `deployment_plan_repaired`
- `commander_plan_built`
- `commander_plan_dirty_marked`
- `commander_plan_repaired`
- `commander_phase_report`
- `orchestration_context_attached`

The `orchestration_context_attached` event records attached slim context keys
and whether full General, Deployment, or BattleRound plan payloads were
explicitly attached through audit/debug opt-in. Normal decision context keeps
only ids and local slices.

## Performance Guardrails

Planner guardrails are metadata and audit checks, not legality rules:

- General, Deployment, and BattleRound plan metadata includes configured
  build/repair budgets and compact count limits.
- Commander analysis snapshots expose top-K limits:
  - `max_targets`
  - `max_units`
  - `max_targets_per_unit`
  - `max_unit_target_entries`
- Commander snapshot metadata records whether target/unit analysis was
  truncated and estimates avoided unit-target matrix work.
- `orchestration_context_attached` audit metadata records context payload bytes,
  warning/hard-limit status, full-plan payload keys, and
  `context_cache_key_safe`.

Full `general_plan`, `deployment_plan`, and `battle_round_plan` payloads remain
audit/debug-only. A normal context is cache-key safe when it has no full plan
payload keys and stays below the warning payload size.

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

`metadata.general_plan_id` links the commander plan to the active game-level
General plan. `metadata.analysis_snapshot` is a bounded, audit-only commander
analysis input snapshot. It is built with the plan and includes:

- a `cache_key` with `battle_round`, `player_id`, and `map_generation`.
- enemy target threat, scoring, denial, wounds, toughness, save, OC, and
  keyword summaries.
- friendly unit shooting, melee, mobility, survivability, risk, and keyword
  summaries.
- top-K unit-target matrix entries for expected shooting damage, expected melee
  damage, movement-to-LoS feasibility, movement-to-half-range feasibility, and
  charge feasibility.

The snapshot is approximate planning metadata only. It does not create legal
candidates, change masks, validate attacks, or mutate state.

`metadata.commander_order_bundle_id` links the plan to the compiled
`CommanderOrderBundle`. The battle-round plan materializes that bundle into
existing priority target, unit task, movement, shooting, charge, fight, and
transport assignment structures. Full compiler output remains audit/debug-only
because the full battle-round plan is not attached in normal decision context.

Compiled commander orders are normally hints. The existing greedy assignment
planner remains the default source for unit-target commitments. If the active
`GeneralPlan.target_priority_doctrine` supplies explicit unit orders with
`constraint_mode` set to `constrain`, `replace`, or `override`, the commander
materializer may redirect shooting or charge assignments to those compiled
targets, but only when the target is present in the current commander analysis
matrix. Missing/stale compiled targets are rejected and the greedy assignment
is retained. Constraint diagnostics are recorded in full plan metadata and
trimmed from normal unit-local context to preserve cache-key and payload
guardrails.

Weapon/ability trigger metadata is included in unit capability and unit-target
matrix metadata when detected:

- `weapon_trigger_bands`
- `trigger_band_count`
- `trigger_band_kinds`
- `has_half_range_trigger`
- `half_range_trigger_value`
- `has_assault_trigger`
- `has_heavy_stationary_trigger`
- `stationary_trigger_value`
- `has_torrent_trigger`
- `has_pistol_trigger`
- `advance_and_charge`
- `fall_back_and_shoot`

Supported trigger kinds are:

- `melta_half_range_damage_bonus`
- `rapid_fire_half_range_extra_attacks`
- `advance_and_shoot_enabled`
- `stationary_shooting_bonus`
- `torrent_auto_hit_close_pressure`
- `pistol_engaged_shooting_relevance`

These are planning/scoring hints only. They do not make a unit eligible to
shoot, Advance, charge, fall back, or fight; the engine validators remain
authoritative.

`UnitBattleTask` is the cross-phase unit assignment:

- `unit_id`
- `role`: `shooting_first`, `melee_first`, `mixed`, `scorer`, `screen`, or
  `preserve`
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
- `MovementPhasePlan.transport_assignments`
- `ShootingPhasePlan.target_fire_plans`
- `ShootingPhasePlan.unit_fire_assignments`
- `ChargePhasePlan.unit_charge_assignments`
- `FightPhasePlan.unit_fight_assignments`

`TransportAssignment` is the movement-phase bridge from General transport
doctrine to battle-round execution. It can describe:

- `stay_embarked` for passengers protected before the delivery round.
- `disembark_this_round` for passengers at or after the doctrine delivery
  round.
- `embark_after_action` for planned riders that are not currently embarked.
- `deliver_to_staging_region` for transports moving passengers to a staging
  region.
- `transport_screen_after_delivery` for empty transports whose doctrine says
  they should become a screen or objective piece.

These assignments are local context only. They do not alter transport legality,
embark/disembark masks, or movement candidate generation.

## Dirty Flags

Dirty flags are serializable, cumulative repair hints. Event subscribers set
them; local rankers may inspect them; phase-start repair checkpoints consume or
downgrade the matching scope deterministically.

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
- `metadata.repair` when the same phase start repaired the plan, including the
  repair `scope`, `repair_count`, and pre/post dirty flag summaries.

Phase reports remain compact. Future executors can populate per-unit,
per-target, and per-objective reports as they compare planned intent with actual
execution outcomes.

## Greedy Assignment Baseline

The commander now consumes `metadata.analysis_snapshot` to populate tactical
assignments without making those assignments authoritative:

- enemy targets are ranked by threat plus scoring and denial value.
- friendly units are classified from Tier-2 task posture and PR 2 shooting/melee
  capability analysis.
- shooting-first and mixed units are greedily assigned to high-priority targets
  until expected committed damage reaches a kill-damage threshold plus a small
  overkill allowance.
- melee-first units receive charge and fight assignments instead of primary fire
  assignments.
- movement tasks expose future-phase intent such as required LoS,
  generic half-range bands, avoiding shooting ineligibility for shooters, and
  intentionally accepting shooting ineligibility for melee charge staging.
- trigger-band planning can replace generic half-range movement hints with
  Melta/Rapid Fire trigger bands, permit Assault shooters to Advance without a
  commander ineligibility penalty, and prefer stationary posture for Heavy
  profiles when the planned target is already viable.

These assignments are planning metadata. Rankers are not required to consume
them yet, and the engine remains the only source of legal candidates, masks,
validation, PathWitness artifacts, and state mutation.

## Movement Consumption Baseline

Movement rankers now consume commander movement intent as scoring metadata only.
Semantic normalization adds commander fields to movement candidates:

- `commander_task_alignment`
- `commander_action_violation`
- `commander_required_los_satisfied`
- `commander_desired_range_band_satisfied`
- `commander_charge_lane_score`
- `commander_intentional_shooting_ineligible`
- `commander_future_phase_ev`
- `commander_plan_stale_penalty`
- `commander_transport_alignment`
- `commander_transport_intent_satisfied`
- `commander_transport_match_satisfied`
- `commander_transport_destination_satisfied`
- `commander_embark_intent_satisfied`
- `commander_disembark_intent_satisfied`
- `commander_transport_action_violation`
- `commander_transport_plan_stale_penalty`

The movement ranker weights these fields to prefer legal candidates that match
the unit's current commander task. This can penalize Advance for shooting-first
units, reward intentional Advance staging for melee-first units, reward
candidate-provided LoS/range-band satisfaction, prefer matching embark and
disembark choices, prefer transport delivery moves toward commander staging
regions, and reduce commander influence when movement/phase/full-round repair
pressure says the plan is stale.

This does not generate new movement candidates, mask forbidden actions, bypass
validation, or alter PathWitness requirements. If commander intent is stale,
impossible, or unsupported by candidate metadata, existing local semantic
movement scoring remains the fallback.

## Shooting Consumption Baseline

Headless `DECLARE_SHOTS` synthesis now consumes commander fire intent as an
execution hint, not a legality source.

For unit-scoped shooting decisions, the context can include:

- `commander_fire_assignment`
- `preferred_target_unit_ids`
- `preferred_declarations`
- `target_fire_plan_summary`
- `general_limited_resource_policy`
- `general_cp_policy`

The declaration builder follows this order:

1. Try `preferred_declarations` only if each model/profile/target tuple is
   present in the current legal `shooting_target_candidates` context.
2. If no preferred declaration is currently legal, prioritize commander
   primary and backup targets when choosing targets from legal cached target
   rows.
3. If the commander target is stale, dead, out of range, or absent from legal
   target rows, fall back to the existing local target/profile ranking and
   validation path.
4. Preserve General-reserved one-shot / once-per-battle shooting profiles
   unless policy marks them available/authorized, reserves them for the current
   target, or the target fire plan meets the policy authorization threshold.

All shooting legality still comes from existing legal target candidate
generation and profile validation. The commander and General only influence
which legal declaration is tried first.

## Charge/Fight Consumption Baseline

Charge and Fight rankers now consume commander assignments as scoring metadata
only.

Charge metadata includes:

- `commander_charge_alignment`
- `commander_charge_primary_target_selected`
- `commander_charge_backup_target_selected`
- `commander_charge_multi_target_penalty`
- `commander_charge_probability`
- `commander_charge_plan_stale_penalty`

Fight metadata includes:

- `commander_fight_alignment`
- `commander_fight_primary_target_selected`
- `commander_fight_backup_target_selected`
- `commander_fight_multi_target_penalty`
- `commander_fight_activation_priority`
- `commander_fight_plan_stale_penalty`

Unit-scoped charge/fight decisions use the local `commander_charge_assignment`
or `commander_fight_assignment`. Phase unit-selection requests can receive
candidate-local assignment maps so activation ordering can see commander
priority without attaching the full battle-round plan.

Stale charge/fight repair pressure reduces commander alignment. If a primary
target is dead, unavailable, or absent from the legal candidate set, local
semantic scoring remains the fallback.

This does not generate charge/fight candidates, mask unavailable targets,
bypass engagement/charge validation, or alter charge/fight mutation.

## Current Baseline

The first implementation is deliberately conservative:

- target priorities are deterministic commander threat/scoring/denial estimates.
- analysis snapshots are deterministic, bounded, and audit-only.
- unit roles derive from Tier-2 task types plus capability analysis.
- movement tasks mirror Tier-2 target regions and commander phase intent.
- fire, charge, and fight assignments are populated by the greedy commander
  assignment baseline.
- dirty flags are recorded from engine events and consumed at phase-start repair
  checkpoints.
- phase-start repair scopes refresh only the matching subplan when possible, or
  the phase/full-round plan when target, objective, CP, or full replan pressure
  requires it.
- phase reports record the current dirty state plus the most recent same-phase
  repair scope and pre/post dirty state when a repair ran.
- movement rankers can now score legal candidates against commander intent, but
  legality and mutation remain owned by the existing engine validators.
- General policy is linked by `general_plan_id`; movement rankers consume only
  local commander transport slices derived from General transport doctrine, and
  shooting declaration synthesis consumes slim General limited-resource policy
  without attaching the full General plan.
- charge/fight rankers can score legal candidates against commander assignments
  and activation priority, while validation and mutation remain engine-owned.

This establishes the stable data contract for later work where movement can
score LoS/range/trigger-band enablement, shooting can execute preferred legal
declarations, and charge/fight can execute or repair precommitted intent.
