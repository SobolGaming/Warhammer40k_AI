# Commander Roadmap

This file tracks the commander orchestration PR sequence. The repository has
been receiving these as PR-sized commits directly on `dev`; the commit mapping
below is the durable reference for future "PR N" work.

## Strategic Hierarchy

The long-horizon orchestration stack is:

- `GeneralPlan`: game-level / multi-battle-round strategist.
- `BattleRoundPlan`: battle-round / phase commander orchestrator.
- phase rankers: local legal-candidate executors.
- engine: legality, masks, validation, PathWitness artifacts, and mutation
  authority.

The General answers whole-game questions: win path, battle-round posture,
scarce resource reserves, once-per-game timing, CP policy, transport doctrine,
late-game preservation, and primary push/trading/staging rounds.

The Commander answers current battle-round questions: priority targets, unit
tasks, movement/shooting/charge/fight subplans, transport execution for the
current round, dirty-flag repair, and phase reports.

Rankers execute legal candidates locally. They may consume General/Commander
metadata for ordering, but they do not create legality or mutate state.

Engine validation remains authoritative.

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

### PR 6A - General Plan Scaffold And Limited Resource Ledger

Commit: `Add general plan scaffold`

Added a non-behavior-changing General scaffold above the battle-round
commander.

Planned data model:

- `GeneralPlan`
- `GeneralRoundDirective`
- `LimitedResourcePolicy`
- `TransportDoctrine`
- optional `GeneralDirtyFlags` / `GeneralVarianceReport`

Planned behavior:

- `get_or_create_general_plan(player_id)` caches a serializable whole-game plan.
- `BattleRoundPlan.metadata.general_plan_id` links each commander plan to the
  active General plan.
- full `general_plan` payload is audit/debug-only, matching the slim context
  rule for full battle-round plans.
- one-shot weapons, once-per-battle abilities, rare stratagem windows, and CP
  reserves are represented as policy data only.

Acceptance criteria:

- General plan serializes deterministically.
- normal decision context remains slim.
- commander plan includes `general_plan_id`.
- limited-resource policy structures exist but do not alter legality, masks, or
  decision choices.
- tests cover cache identity, context slimming, and deterministic serialization.

### PR 6B - Commander Transport Intent

Add explicit transport doctrine/execution slices before deeper movement
behavior.

Planned data model:

- `TransportAssignment`
- General `transport_policy` slice consumed by the commander.
- `movement_plan.transport_assignments`.
- unit-local `commander_transport_assignment`,
  `commander_embark_assignment`, and `commander_disembark_assignment` context
  slices.

Planned behavior:

- embarked units can receive `stay_embarked`, `disembark`, or `deliver` intent.
- transports can receive `deliver`, `screen_with_transport`, or `reposition`
  intent.
- embark/disembark decisions receive unit-local commander transport metadata.

Acceptance criteria:

- no candidate generation, legality, or decision choice changes.
- transport assignments serialize deterministically.
- unit-scoped decision context stays slim and local.
- tests cover embarked passenger, transport delivery, and missing/stale
  transport intent cases.

Implemented behavior:

- General `TransportDoctrine` records planned riders, current passengers,
  delivery round, preservation posture, staging region, and post-delivery role.
- `BattleRoundPlan.movement_plan.transport_assignments` converts doctrine into
  unit-local execution hints.
- embarked passengers receive `stay_embarked` before the delivery round and
  `disembark_this_round` at or after the delivery round.
- planned unembarked riders receive `embark_after_action`.
- transports receive `deliver_to_staging_region` or
  `transport_screen_after_delivery`.
- `Game.request_decision(...)` attaches `commander_transport_assignment`,
  `commander_embark_assignment`, and `commander_disembark_assignment` as slim
  local slices.
- rankers do not consume these transport slices yet.

### PR 6C - Movement Ranker Consumes Commander Transport Intent

Extend the completed PR5 movement ranker consumption to transport-specific
movement decisions.

Movement ranker should score:

- embark intent.
- disembark intent.
- transport delivery intent.
- destination-region alignment.
- stale/illegal transport intent fallback.

Acceptance criteria:

- unit with disembark intent prefers legal disembark candidate matching the
  commander destination.
- unit with embark intent prefers legal embark candidate.
- transport with delivery intent prefers legal movement toward commander staging
  region.
- local fallback still wins if commander transport intent is illegal, stale, or
  unsupported by candidate metadata.
- legality remains owned by existing validators.

Implemented behavior:

- `EMBARK` and `DISEMBARK` now use movement semantic normalization so transport
  intent can be scored by the movement ranker.
- semantic movement metadata now includes commander transport alignment,
  transport match, destination match, embark/disembark intent satisfaction,
  transport action violation, and stale transport-plan penalty.
- the movement ranker weights these fields after normal movement semantics and
  PR5 commander movement fields.
- embark intent prefers legal candidates for the assigned transport.
- disembark intent prefers legal candidates for the assigned transport and
  matching destination metadata when present.
- transport delivery intent prefers legal movement candidates whose metadata
  matches the commander staging region.
- masked candidates remain unavailable, and unsupported/stale transport metadata
  falls back to existing local semantic movement scoring.

## Remaining

### PR 7 - Shooting Executes Commander Fire Assignments And General Resource Policy

Make `DECLARE_SHOTS` try commander preferred targets/declarations first, validate
through existing legal candidate paths, fall back when stale or illegal, and
update target commitments after each shooting resolution. Shooting should also
consume General limited-resource policy for one-shot weapons and once-per-battle
offensive effects.

Acceptance criteria:

- planned targets/declarations are tried first but never bypass validation.
- dead or unreachable planned targets fall back legally.
- overkill guard redirects later shooters after target destruction or projected
  damage saturation.
- one-shot / once-per-battle resources are used only when General policy
  authorizes them.
- local fallback remains deterministic when General/Commander policy is absent.

### PR 8 - Charge And Fight Consume Commander Assignments

Make charge/fight target selection prefer commander assignments while preserving
existing charge/fight legality and fallback behavior. General posture/resource
constraints can influence whether melee assets are preserved, traded, or
committed.

### PR 9 - Weapon And Ability Trigger-Band Planner

Extract and model trigger bands such as Melta, Rapid Fire, Assault, Heavy,
Torrent, Pistol, half-range unit abilities, advance-and-charge, and
fall-back-and-shoot as planning metadata. This should feed both General
whole-game resource timing and Commander current-round movement/fire planning.

### PR 10 - General/Commander Telemetry And Audit Tooling

Add structured General and Commander events/counters:

- `general_plan_built`
- `general_resource_authorized`
- `general_resource_spent`
- `commander_plan_repaired`
- `commander_assignment_used`
- `commander_assignment_fallback`
- `transport_plan_used`
- `transport_plan_fallback`
- context payload size, hit rates, fallback rates, and repair timing.

### PR 11 - Performance Guardrails And Cache Hardening

Add budgets/top-K constraints and representative performance checks so commander
and General planning stay bounded and improve later phase work without bloating
default cache keys.

Performance counters should include:

- `general_plan_build_ms`
- `commander_plan_build_ms`
- `repair_ms`
- `context_payload_bytes`
- movement candidate reduction.
- shooting validation reduction.
