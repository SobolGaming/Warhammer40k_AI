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

Current baseline:
- Deterministic heuristic assignment by Tier-1 unit priority tiers.
- Time budgets continue to derive from decision type + compute tier.

Runtime use:
- The orchestrator builds or refreshes the bundle at Command phase start when possible, and lazily for decisions that need tactical context.
- Movement and other unit-scoped rankers may consume `tier2_task`, `movement_intent`, and `compute_tier`.
- Reactions, dice, allocation, and other local decisions can route directly to their component when Tier-2 context would not add useful signal.
- The bundle never creates legality; Tier 0 and the engine own candidate generation, masks, validation, and mutation.
