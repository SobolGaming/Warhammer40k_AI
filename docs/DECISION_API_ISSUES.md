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
- [acts_of_faith.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/rules/acts_of_faith.py:1561)
  now emits and settles repeated `DECISION_USE_MIRACLE_DIE` requests for the
  Miracle-dice-pool discard abilities (`Chaplet of Sacrifice`, `Righteous
  Repugnance`, `Rapturous Blows`, `Righteous Rage`, `Manual of Saint Griselda`,
  and `Psalm of Righteous Judgement`) instead of jumping straight from
  `miracle_dice_pool_reroll_provider` or the deterministic fallback heuristic
  to the final discard effect.
- [acts_of_faith.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/rules/acts_of_faith.py:1561)
  now consults local/provider Miracle-pool discard fallbacks one queued request
  at a time. The provider path no longer tries to pre-answer later
  `DECISION_USE_MIRACLE_DIE` prompts before those later requests exist, which
  keeps local discard flows aligned with the same sequential request chain used
  by headless and remote resolution.
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
- [player.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/roster/player.py:2843),
  [game_ui.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/UI/game_ui.py:3427),
  and [reactive_decisions_mixin.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/engine/game_mixins/reactive_decisions_mixin.py:266)
  now keep local optional yes/no abilities on the same emitted request chain. A
  local controlled player now gets a dedicated synchronous `optional_decision_hook`
  installed by `GameView`, the generic local `decision_requested` UI path stays
  out of those optional confirmations, and reachability checks recognize that hook
  as a valid decision owner instead of falling back to an implicit `Skip`. If an
  optional yes/no request is emitted with no synchronous owner attached, the player
  path now fails explicitly rather than silently continuing past the pending request.
- [keywords_detachments_mixin.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/units/unit_mixins/keywords_detachments_mixin.py:10840)
  no longer over-classifies generic “core stratagems for 0CP” leader rules as
  `Beast Handler` Heroic Intervention discounts. That false positive surfaced once
  the optional-decision path stopped auto-skipping unresolved prompts; the parser
  now only matches explicit “target that unit with the Heroic Intervention
  Stratagem for 0CP” wording.
- [stratagems.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/rules/stratagems.py:2161)
  no longer bypasses `DecisionRequest` for the Drukhari `Power from Pain`
  stratagem add-on spend; it now settles the same emitted confirmation request that
  the player/controller answers.
- [map.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/battlefield/map.py:172),
  [game.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/engine/game.py:14646),
  [actions_movement_mixin.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/units/unit_mixins/actions_movement_mixin.py:16964),
  [dice_rolls.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/engine/dice_rolls.py:781),
  [shooting_mixin.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/units/unit_mixins/shooting_mixin.py:2947),
  [state_attachment_mixin.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/units/unit_mixins/state_attachment_mixin.py:1820),
  [stratagems_emperors_children.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/rules/stratagems_emperors_children.py:2040),
  [stratagems_world_eaters.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/rules/stratagems_world_eaters.py:2617),
  and the audited reroll paths in [wargear.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/units/wargear.py:5768)
  now route local, remote, and headless reroll prompts through the same emitted
  `DECISION_REROLL_ROLL` request. The reroll wrapper preserves the old fallback
  strategies where they existed (`below average` attack/damage rolls and the
  reactive `<= 3` distance heuristics) instead of skipping the reroll decision
  entirely in non-local flows.
- [shooting_mixin.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/units/unit_mixins/shooting_mixin.py:3141)
  now emits and settles `DECISION_ALLOCATE_DAMAGE` for Reanimation Protocols
  model selection in both local-provider and non-local flows. Restoring a wound
  to one of several wounded models and returning one of several destroyed models
  now resolve the same queued allocation request instead of selecting directly
  through `reanimation_allocation_provider` or defaulting to the first candidate
  without a decision.
- [wargear.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/units/wargear.py:9220)
  now emits and settles `DECISION_USE_LEADING_UNMODIFIED_SIX`,
  `DECISION_USE_MODEL_UNMODIFIED_SIX`, and `DECISION_CHOOSE_ASPECT` even for the
  local/provider path. Human-provider answers now settle those emitted requests
  instead of bypassing them and writing the chosen effect directly.
- [game.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/engine/game.py:3009),
  [shooting_fight_handlers_mixin.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/engine/game_mixins/shooting_fight_handlers_mixin.py:244),
  and [game_ui.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/UI/game_ui.py:10750)
  now keep the same request chain for local-human and non-local reactive prompts.
  `Battle Focus` opportunity/fade-back and `Loping Speed` still publish the local
  UI prompt, but they now also issue the same queued request first instead of
  letting the local path run ahead of the engine queue.
- [shooting_fight_handlers_mixin.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/engine/game_mixins/shooting_fight_handlers_mixin.py:17318),
  [fight_phase_manager.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/engine/fight_phase_manager.py:722),
  [phase_handlers_mixin.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/engine/game_mixins/phase_handlers_mixin.py:12298),
  and [game_ui.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/UI/game_ui.py:11098)
  now keep the same engine-issued request chain for the audited local reactive
  prompt flows and their follow-ups. `Blood Surge`, `Unhinged Vengeance`,
  `Brazen Fury`, `Horde Move`, `Blistering Assault`, `Bestial Rage`,
  `Aggressive Leader Beast`, `Frenzy`, `Fight Within 3"`, and `For the Greater
  Good` no longer let the local-human path publish a prompt or continue a follow-up
  step before the matching `DecisionRequest` exists.
- [game_ui.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/UI/game_ui.py:12196),
  [game_ui.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/UI/game_ui.py:13630),
  [game_ui.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/UI/game_ui.py:13725),
  and [game_ui.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/UI/game_ui.py:15650)
  now consume even single-option local selections through the already-queued
  request instead of shortcutting them in UI code. The audited cases were
  `Oath of Moment`, single-maneuver `Battle Focus`, and single-choice
  modifier-ignore prompts.
- [voice_of_command.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/rules/voice_of_command.py:2147),
  [phase_handlers_mixin.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/engine/game_mixins/phase_handlers_mixin.py:18391),
  [abilities.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/engine/decision_handlers/abilities.py:12695),
  and [game_ui.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/UI/game_ui.py:8622)
  now normalize `Voice of Command` into an explicit three-step decision chain:
  choose officer, choose order, choose target. The engine now queues those staged
  requests for local, remote, and headless play instead of publishing a local-only
  prompt flow with no backing `DecisionRequest`.
- [game_ui.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/UI/game_ui.py:2857)
  now consumes pending local yes/no and Miracle-die requests by matching only the
  engine-issued lookup context and then marking the request as `ui_prompted`
  afterward. The generic `decision_requested` UI path also now stays out of
  provider-owned and custom local prompt flows (`Blood Surge`, `Brazen Fury`,
  `Horde Move`, `Hover Mode`, `Fight Within 3"`, `Acts of Faith`, and similar
  blocking/custom dialogs), so local-human handling no longer races or bypasses
  those already-issued requests.
- [reactive_decisions_mixin.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/engine/game_mixins/reactive_decisions_mixin.py:4926)
  now preserves the full local/headless/remote request chain for `Blood Surge`
  when `BERZERKER'S WRATH` is available. Confirming Blood Surge now emits and
  settles a second `DECISION_CONFIRM_YES_NO` for the stratagem before the move
  request is queued, instead of letting local UI ask an unbacked nested question.
- [stratagems_drukhari.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/rules/stratagems_drukhari.py:3223),
  [reactive_decisions_mixin.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/engine/game_mixins/reactive_decisions_mixin.py:5674),
  and [game_ui.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/UI/game_ui.py:22563)
  now keep `Instinctive Spite` on the same engine-owned request chain in every
  audited path. Selecting the affected Drukhari unit(s) now leads to an emitted
  `DECISION_CONFIRM_YES_NO` for the optional Pain token spend before the
  stratagem is applied, instead of the local UI asking that question itself
  after selection with no backing request.
- [decision_utils.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/utility/decision_utils.py:22),
  [cabal_of_sorcerers.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/rules/cabal_of_sorcerers.py:899),
  [damage_death_mixin.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/units/unit_mixins/damage_death_mixin.py:179),
  and the audited confirmation paths in [wargear.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/units/wargear.py:9999)
  now preserve tri-state fallback ownership when a `DECISION_CONFIRM_YES_NO`
  has already been queued. External synchronous rule callers no longer coerce a
  missing fallback owner into `False`; if they emit one of these confirmations
  without a synchronous controller, provider, or override attached, they now
  fail explicitly and leave the queued request pending instead of silently
  auto-skipping it.
- [map.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/battlefield/map.py:172),
  [acts_of_faith.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/rules/acts_of_faith.py:666),
  and [shooting_mixin.py](/c:/Users/nostr/Documents/Projects/Warhammer40k_AI/src/warhammer40k_ai/units/unit_mixins/shooting_mixin.py:3165)
  now apply the same contract to audited payload-choice requests. Pending
  reroll, Miracle-die, Miracle-pool discard, and Reanimation allocation
  decisions no longer skip the emitted request and then reconstruct a separate
  post-request answer. Rerolls and Miracle-pool discard now settle the emitted
  request through the same deterministic headless strategy used by those flows,
  while Miracle-die and Reanimation allocation only reuse an explicit
  provider/controller answer for that same request and otherwise fail
  explicitly with the request still pending.

## Remaining Known Gaps

- None in the tracked provider/request-parity buckets from this audit pass.

## Audit Scope

- This document covers the tracked gaps above. The audited request-reuse gaps from
  this pass are now closed, and the audited provider/request-parity buckets are
  also closed. This is still an audit claim, not a mathematical proof over every
  future call site.
- The invariant enforced by these fixes is: if a controller answers a tracked
  decision automatically, it settles exactly that emitted `DECISION_TYPE`; it does
  not skip the request and jump ahead to later effects.
