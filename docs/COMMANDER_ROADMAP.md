# Commander Roadmap

This file tracks the commander orchestration PR sequence. The repository has
been receiving these as PR-sized commits directly on `dev`; the commit mapping
below is the durable reference for future "PR N" work.

## Completed

### PR 1 - Commander Scaffold

Commit: `f117d6f6 Add commander orchestration plan scaffold`

Added the commander data model, cached battle-round plan, dirty flags, phase
reports, and unit-local commander context scaffold. This established
`BattleRoundPlan` plus movement, shooting, charge, and fight subplan shells
without making rankers obey the plan.

### PR 1 Follow-Up - Context Slimming

Commit: `6d45f7df Slim commander plan decision context`

Made the full `battle_round_plan` payload audit/debug-only by default. Normal
decision context keeps `battle_round_plan_id` and unit-local commander slices.

### PR 1 Follow-Up - Context Payload Guard

Commit: `cfe70dc8 Strip unaudited commander plan payloads`

Strips caller-provided full `battle_round_plan` payloads unless audit/debug
opt-in is active, preventing large unaudited context payloads from leaking into
cache keys.

### PR 2 - Commander Analysis Matrices

Commit: `a8d3365b Add commander analysis snapshot`

Goal: build deterministic, serializable commander analysis inputs at Command
phase / lazy plan creation time, without consuming them for decisions yet.

Planned outputs:

- enemy target threat, scoring, and denial values
- friendly shooting capability
- friendly melee capability
- friendly mobility profile
- friendly survivability and risk profile
- bounded unit-target expected shooting damage
- bounded unit-target expected melee damage
- bounded unit-target movement-to-LoS feasibility
- bounded unit-target movement-to-half-range feasibility
- bounded unit-target charge feasibility

Acceptance criteria:

- Plan still serializes deterministically.
- No decision choice changes unless audit/debug context is requested.
- Matrices are small/top-K, not full combinatorial explosions.
- Analysis includes battle round, player, and map generation in its cache key.
- Deterministic tests cover ordering, threat scoring, anti-tank-style damage,
  melee/charge capability, and snapshot bounds.

Implementation notes:

- Snapshot data is stored under `BattleRoundPlan.metadata.analysis_snapshot`.
- The snapshot is audit-only in normal operation because full plans are not
  attached to decision context by default.
- Unit-target entries are bounded by top-K target and unit limits.

### PR 3 - Greedy Commander Assignment Planner

Commit: `d2f3abc2 Add greedy commander assignments`

Use the PR 2 analysis snapshot to populate meaningful `UnitBattleTask`,
`TargetFirePlan`, `UnitFireAssignment`, `ChargeTargetAssignment`, and
`FightTargetAssignment` fields while keeping the engine as the sole legality
authority.

Implementation notes:

- Enemy targets are ranked by threat plus scoring and denial pressure.
- Friendly units are classified as `shooting_first`, `melee_first`, `mixed`,
  `scorer`, `screen`, or `preserve`.
- Shooting assignments greedily commit expected damage into priority targets
  until a kill-damage threshold plus overkill limit is reached.
- Melee-first units receive charge/fight assignments and intentionally skip
  shooting so later movement can stage them for charges.
- Rankers still do not have to obey these assignments; they are commander
  metadata for later PRs.

### PR 4 - Phase Checkpoint And Repair Loop

Commit: `Add commander phase repair checkpoints`

Make dirty flags operational at phase boundaries. Phase-start checkpoints choose
the narrowest applicable repair scope, refresh the relevant commander subplan,
consume or retain dirty flags deterministically, increment repair counts only
when a repair runs, and attach pre/post dirty summaries to phase reports.

Implementation notes:

- `unit_move_ended` can dirty shooting and charge, then Shooting phase start
  repairs only the shooting scope and leaves charge dirty for Charge phase.
- `charge_move_failed` can repair charge at Charge phase start and fight at
  Fight phase start without full-round replanning.
- target/objective/CP priority variance uses `phase` repair, while explicit
  full-round variance rebuilds the battle-round plan and dependencies.
- repeated phase-start calls are idempotent once the matching scope has been
  consumed.

### PR 5 - Movement Ranker Consumes Commander Movement Intent

Commit: `Let movement ranker consume commander intent`

Score movement actions/endpoints against commander movement intent without
changing candidate generation, masks, PathWitness generation, or authoritative
movement validation.

Implementation notes:

- semantic movement metadata now includes `commander_task_alignment`,
  `commander_action_violation`, LoS/range-band satisfaction, charge-lane score,
  intentional shooting-ineligible staging, future-phase EV, and stale-plan
  penalty.
- the movement ranker weights those commander fields after normal semantic
  projection fields, so commander intent can break ties or steer among legal
  candidates.
- shooting-first units penalize Advance when it would make shooting ineligible;
  melee-first units can reward Advance when the commander intentionally accepts
  shooting ineligibility for charge staging.
- dirty movement/phase/full-round commander scopes reduce commander alignment
  so stale plans give way to local movement scoring.
- forbidden movement actions receive negative commander score only; they are not
  masked illegal by this layer.

## Remaining

### PR 6 - Shooting Executes Commander Fire Assignments

Make `DECLARE_SHOTS` try commander preferred targets/declarations first, validate
through existing legal candidate paths, fall back when stale or illegal, and
update target commitments after each shooting resolution.

### PR 7 - Charge And Fight Consume Commander Assignments

Make charge/fight target selection prefer commander assignments while preserving
existing charge/fight legality and fallback behavior.

### PR 8 - Weapon And Ability Trigger-Band Planner

Extract and model trigger bands such as Melta, Rapid Fire, Assault, Heavy,
Torrent, Pistol, half-range unit abilities, advance-and-charge, and
fall-back-and-shoot as planning metadata.

### PR 9 - Commander Telemetry And Audit Tooling

Add structured commander events and counters for plan build/repair, assignment
hits/rejections/fallbacks, overkill redirects, phase reports, hit rates,
fallback rates, and default context payload size.

### PR 10 - Performance Guardrails And Cache Hardening

Add budgets/top-K constraints and representative performance checks so commander
planning stays bounded and improves later phase work without bloating default
cache keys.
