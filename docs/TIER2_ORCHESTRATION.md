# Tier 2 Orchestration Scaffolding

Tier-2 now emits deterministic per-unit task bundles derived from the Tier-1 plan.

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
