# DecisionRequest/Command API Audit (Tracked Issues)

Date: April 18, 2026
Status: Updated after targeted parity fixes

This note tracks the specific decision-parity regressions audited in this pass.

## Resolved In This Pass

- [reactive_decisions_mixin.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/engine/game_mixins/reactive_decisions_mixin.py:11207)
  no longer bypasses `DecisionRequest` for the immediate bodyguard-loss path used by
  Brutal Example Overwatch. It now issues `DECISION_ALLOCATE_DAMAGE` first and then
  resolves that same request through local-provider, headless, or override control.
- [cabal_of_sorcerers.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/rules/cabal_of_sorcerers.py:893)
  no longer rebuilds Arcane Focus from `_should_use_optional_ability(...)` after
  queueing a confirmation. The queued `DECISION_CONFIRM_YES_NO` now owns the answer.
- [damage_death_mixin.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/units/unit_mixins/damage_death_mixin.py:184)
  now queues and resolves the same confirmation request for Watcher in the Dark,
  Null Nodules, and Death Vision of Sanguinius across local-provider and non-local
  flows.
- [wargear.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/units/wargear.py:9939)
  now uses the resolved `DECISION_CONFIRM_YES_NO` result for the audited optional
  wargear flows instead of reconstructing the answer from controller fallbacks
  (`MODEL_ALLOCATED_DAMAGE_ZERO`, `DESTINED_BY_FATE`, `DISTRACTION_GROT`, and
  `FIRST_FAILED_SAVE_DAMAGE_ZERO`).
- [wargear.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/units/wargear.py:9243)
  now reuses already-settled multi-option decision payloads for
  `DECISION_USE_LEADING_UNMODIFIED_SIX`, `DECISION_USE_MODEL_UNMODIFIED_SIX`,
  and `DECISION_CHOOSE_ASPECT` instead of reconstructing a post-request fallback
  answer from `_next_optional_selections`.
- [acts_of_faith.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/rules/acts_of_faith.py:658)
  now emits and settles `DECISION_USE_MIRACLE_DIE` before consuming a Miracle
  die in engine-backed flows. Local provider answers now resolve that same
  request instead of bypassing it.
- [attack_modifiers.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/engine/attack_modifiers.py:15)
  and [wargear.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/units/wargear.py:14418)
  now emit and settle `DECISION_CHOOSE_HIT_MODIFIER_IGNORES` /
  `DECISION_CHOOSE_SKILL_MODIFIER_IGNORES` for local/provider modifier-ignore
  choices instead of writing directly into attack state.
- [player.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/roster/player.py:2843)
  now routes legacy `_should_use_optional_ability(...)` yes/no choices through an
  emitted `DECISION_CONFIRM_YES_NO`, while keeping a separate fallback-only helper
  for already-queued request flows. Preview checks also now treat attached decision
  controllers as reachable choice paths, so optional discounts are not hidden from
  headless/controller-driven play before the actual request is issued.
- [stratagems.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/rules/stratagems.py:2161)
  no longer bypasses `DecisionRequest` for the Drukhari `Power from Pain`
  stratagem add-on spend; it now settles the same emitted confirmation request that
  the player/controller answers.

## Remaining Known Gaps

- Direct `roll_reroll_provider` paths remain in several engine/rules attack and
  reroll flows, so not every reroll decision has been normalized to the same
  emitted request path yet.

## Audit Scope

- This document covers the tracked gaps above. The audited request-reuse gaps from
  this pass are now closed, but this is still not a full-repo proof that every
  optional provider path has been audited.
- The invariant enforced by these fixes is: if a controller answers a tracked
  decision automatically, it settles exactly that emitted `DECISION_TYPE`; it does
  not skip the request and jump ahead to later effects.
