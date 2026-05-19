# Tier 2 Orchestration Scaffolding

Tier-2 emits deterministic per-unit task bundles derived from the Tier-1 plan.
In the policy orchestration runtime, this bundle is an optional tactical context provider
and intent generator. It enriches candidate generation and ranking when useful; it is not
a mandatory control layer between the engine and every decision-specific ranker.

Task schema:
- `SCORE`
- `SCREEN`
- `STAGE`
- `TRADE`
- `DENY`
- `PROTECT`
- `BAIT`

Bundle fields:
- `plan_id`
- `player_id`
- `cp_reserve_policy`
- `tasks_by_unit_id`

Decision context integration:
- `tier2_task` (for unit-scoped decisions)
- `movement_intent` from Tier-2 task when not explicitly provided
- `compute_tier` from Tier-2 task
- `cp_reserve_policy` stub for downstream CP posture enforcement
- `unit_battle_task` and phase-specific `commander_*` assignments from the cached `BattleRoundPlan`
- `battle_round_plan_id`; the full `battle_round_plan` dict is audit/debug-only
- `commander_dirty_flags` and `commander_replan_scope` for variance-aware local fallback/repair decisions

Attachment rules:
- `attach_ai_orchestration_context(...)` returns a new context dict and never generates candidates or mutates game state.
- Tier-2 task context attaches only when `request.context["unit_id"]` matches a task in the bundle.
- `compute_tier` precedence is matching Tier-2 task, then existing valid engine-provided value, then `P1`.
- Valid `compute_tier` values are `P0`, `P1`, and `P2`; invalid, empty, or unknown values normalize to `P1`.

Current baseline:
- Deterministic heuristic assignment by Tier-1 unit priority tiers.
- `BattleRoundPlan` derives cross-phase unit tasks and movement/shooting/charge/fight assignment shells from this bundle.
- Dirty flags and phase reports are event-driven telemetry only; they do not mutate plans or legality.
- Time budgets continue to derive from decision type + compute tier after orchestration context has been attached.

Runtime use:
- The orchestrator builds or refreshes the bundle at Command phase start when possible, and lazily for decisions that need tactical context.
- Movement and other unit-scoped rankers may consume `tier2_task`, `movement_intent`, and `compute_tier`.
- Cross-phase commander consumers should prefer `unit_battle_task`, `commander_movement_task`, `commander_fire_assignment`, `commander_charge_assignment`, and `commander_fight_assignment` when present, while still treating the engine as the only legality authority.
- Reactions, dice, allocation, and other local decisions can route directly to their component when Tier-2 context would not add useful signal.
- The bundle never creates legality; Tier 0 and the engine own candidate generation, masks, validation, and mutation.
