# General Plan

`GeneralPlan` is the game-level, multi-battle-round strategic scaffold above
the battle-round commander. It is cached by `player_id` and is intentionally
non-authoritative: it does not generate candidates, change masks, validate
actions, or mutate state.

## Runtime Contract

- `Game.get_or_create_general_plan(player_id)` returns the cached General plan.
- `BattleRoundPlan.metadata.general_plan_id` links each commander plan to the
  active General plan.
- `Game.request_decision(...)` attaches `general_plan_id` to normal strategic
  contexts.
- The full `general_plan` payload is attached only for audit/debug contexts,
  either when `request.context["include_full_general_plan"]` is true or when
  `game.attach_full_general_plan_context` is true.
- A caller-provided `general_plan` payload is stripped unless that audit/debug
  opt-in is active.
- Rankers do not consume General policy yet.

## Plan Shape

Top-level fields:

- `plan_id`
- `player_id`
- `created_at_generation`
- `strategic_posture`
- `battle_round_directives`
- `limited_resource_policy`
- `resource_ledger`
- `transport_policy`
- `reserve_policy`
- `target_priority_doctrine`
- `cp_policy`
- `dirty_flags`
- `metadata`

## Resource Ledger

`GeneralResourceLedger` stores `LimitedResourcePolicy` entries for scarce
resources such as:

- CP pool reservation.
- stratagem reserve posture.
- one-shot weapon usage policy.
- once-per-battle ability usage policy.

Current PR6A behavior is scaffold-only. The default ledger creates CP and
stratagem reserve policies, and it can detect simple one-shot / once-per-battle
text hints in unit data. No downstream decision consumes those policies yet.

## Round Directives

`GeneralRoundDirective` gives each battle round a coarse posture:

- round 1: stage
- rounds 2-3: push
- rounds 4-5: preserve

These directives are high-level strategic metadata. The commander can later use
them to choose battle-round tasks, preserve late-game scoring units, and decide
when to commit scarce resources.

## Transport Doctrine

`TransportDoctrine` is a high-level General policy for transport units. It owns:

- which units are planned passengers for each transport.
- whether current passengers should be preserved before delivery.
- the desired delivery round.
- the transport staging destination.
- the post-delivery role, such as screening or objective work.

The battle-round commander consumes this doctrine and emits local
`TransportAssignment` slices. The General doctrine itself is still metadata; it
does not make embark/disembark legal, force choices, or alter ranker scores.

## Non-Behavioral Boundary

The General layer is a policy ledger and audit context. It must not:

- create legal candidates.
- alter masks.
- bypass validation.
- change ranker scores.
- mutate game state.

The engine remains the source of legality and mutation authority.
