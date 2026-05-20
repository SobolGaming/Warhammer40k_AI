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
- General policy is compiled by `strategic_intent_compiler.py` into
  `DeploymentOrderBundle`, `PreBattleOrderBundle`, and
  `CommanderOrderBundle` before lower plans materialize local slices.

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

PR14 adds a compiler normalization step: each round directive becomes a
`RoundCommanderDirective` with posture budgets for aggression, exposure, trade,
resources, CP reserve, preservation, and primary phase focus.

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

The compiler also maps transport doctrine through deployment and commander
orders so transport delivery intent remains traceable from whole-game policy to
setup and battle-round local slices.

## Non-Behavioral Boundary

The General layer is a policy ledger and audit context. It must not:

- create legal candidates.
- alter masks.
- bypass validation.
- change ranker scores.
- mutate game state.

The engine remains the source of legality and mutation authority.

## Profile Evaluation Harness

Reusable General strategy profiles are stored in
`data/general_profiles/we_vs_aeldari_general_profiles.json`. The evaluation
runner is `scripts/run_general_profile_eval.py`.

The runner is intentionally outside the core engine path. It temporarily
overrides each selected player's cached `GeneralPlan` with that player's own
profile-specific round directives, resource policy, CP policy, target-order
overrides, unit-order overrides, and transport doctrine before downstream
deployment/pre-battle/commander order bundles compile. It does not patch
rankers, legality checks, candidate masks, or engine mutation.

Profile privacy is part of the harness contract. A General may evaluate public
state such as both army compositions, mission, deployment, reserves, and board
state, but it must not receive the opponent's selected profile id or profile
knobs. The harness may record the profile pair only in post-game evaluation
summaries. The runner also keeps in-game `game_id` values profile-agnostic so
DecisionRecords do not directly encode the selected profile pair.

By default, the harness sets `WH40K_DECISION_RECORD_MAX=4096` for the process so
strategy comparisons do not truncate normal full-game records at the older
small cap.
