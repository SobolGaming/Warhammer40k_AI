# DecisionRequest/Command API Audit (Tracked Issues)

Date: January 28, 2026  
Status: Draft (tracking list)

This list enumerates **all known player-facing decisions** that do **not** currently route through the unified DecisionRequest/Command API, including cases where a DecisionRequest is created and then **auto-resolved** inside the engine. Each item should be updated so the decision is emitted and resolved through the deterministic decision/command flow.

## Non-DecisionRequest Flows (Direct UI/Console/Provider)

- [ ] DEC-DEP-001 Deployment zone selection bypasses DecisionRequest. Current path uses DeploymentDecisionMaker/UI. Files: `src/warhammer40k_ai/engine/deployment.py:21`, `src/warhammer40k_ai/UI/human_interface.py:33`. Suggested: new DecisionRequest (e.g., DECISION_CHOOSE_DEPLOYMENT_ZONE) with deterministic options.
- [x] DEC-DEP-002 Reserves declaration bypasses DecisionRequest. Current path uses UI or console input. Files: `src/warhammer40k_ai/engine/deployment.py:26`, `src/warhammer40k_ai/engine/deployment.py:507`. Suggested: reuse DECISION_DECLARE_RESERVES with deterministic options.
- [x] DEC-DEP-003 Unit deployment position bypasses DecisionRequest. Current path uses UI click/console input. Files: `src/warhammer40k_ai/engine/deployment.py:31`, `src/warhammer40k_ai/engine/deployment.py:265`, `src/warhammer40k_ai/UI/human_interface.py:39`. Suggested: DecisionRequest (likely DECISION_MOVE_UNIT with placement_kind="deployment").
- [x] DEC-RES-001 Reserves arrival panel placement bypasses DecisionRequest. Current path uses panel callbacks. Files: `src/warhammer40k_ai/UI/panels/reserves_arrival_panel.py`. Suggested: DecisionRequest (likely DECISION_MOVE_UNIT with placement_kind="reserves_arrival" or new decision kind).
- [x] DEC-DMG-001 Damage allocation choice bypasses DecisionRequest. Current path uses provider callbacks in damage allocation. Files: `src/warhammer40k_ai/utility/damage_allocation.py`, `src/warhammer40k_ai/units/unit.py:5814`, `src/warhammer40k_ai/units/wargear.py:8063`, `src/warhammer40k_ai/UI/phases/phase_manager.py:3506`. Suggested: DECISION_ALLOCATE_DAMAGE.
- [x] DEC-DMG-002 Hazardous failure allocation bypasses DecisionRequest. Current path uses provider callbacks. Files: `src/warhammer40k_ai/utility/damage_allocation.py`, `src/warhammer40k_ai/engine/attack_resolution.py:1497`, `src/warhammer40k_ai/units/wargear.py:1718`. Suggested: DECISION_ALLOCATE_DAMAGE (with context selection_kind="hazardous").
- [x] DEC-DMG-003 Precision target allocation bypasses DecisionRequest. Current path uses UI provider. Files: `src/warhammer40k_ai/UI/phases/phase_manager.py:3521`. Suggested: DECISION_SELECT_PRECISION_TARGET.
- [x] DEC-FAITH-001 Miracle Die selection bypasses DecisionRequest. Current path returns None in Acts of Faith without issuing decisions. Files: `src/warhammer40k_ai/rules/acts_of_faith.py`. Suggested: DECISION_USE_MIRACLE_DIE.
- [x] DEC-FIGHT-001 Fight Within 3" optional ability uses direct UI/hook. Files: `src/warhammer40k_ai/UI/game_ui.py:5893`. Suggested: DECISION_CONFIRM_YES_NO with context ability_name.

## Optional Selection Decisions (Player._choose_optional_value)

Each of the following uses `_choose_optional_value` directly instead of a DecisionRequest:

- [ ] DEC-OPT-001 COMBAT_DOCTRINE → use DECISION_CHOOSE_COMBAT_DOCTRINE. File: `src/warhammer40k_ai/engine/game.py:637`
- [ ] DEC-OPT-002 GRAND_COVEN → use DECISION_CHOOSE_GRAND_COVEN. File: `src/warhammer40k_ai/engine/game.py:686`
- [ ] DEC-OPT-003 COMBAT_DRUGS → use DECISION_CHOOSE_COMBAT_DRUGS. File: `src/warhammer40k_ai/engine/game.py:742`
- [ ] DEC-OPT-004 BLOOD_TITHE → use DECISION_CHOOSE_BLOOD_TITHE. File: `src/warhammer40k_ai/rules/world_eaters_detachments.py:318`
- [ ] DEC-OPT-005 HARBINGERS_OF_DREAD → use DECISION_CHOOSE_HARBINGER. File: `src/warhammer40k_ai/rules/harbingers_of_dread.py:328`
- [ ] DEC-OPT-006 HYPER_ADAPTATIONS → use DECISION_CHOOSE_HYPER_ADAPTATION. File: `src/warhammer40k_ai/rules/tyranids_detachments.py:209`
- [ ] DEC-OPT-007 DOCTRINA_IMPERATIVE → use DECISION_CHOOSE_DOCTRINA. File: `src/warhammer40k_ai/rules/doctrina_imperatives.py:206`
- [ ] DEC-OPT-008 NURGLE_PLAGUE → use DECISION_CHOOSE_PLAGUE. File: `src/warhammer40k_ai/rules/nurgles_gift.py:116`
- [ ] DEC-OPT-009 SHADOW_FORM → use DECISION_CHOOSE_SHADOW_FORM. File: `src/warhammer40k_ai/rules/shadow_form.py:320`
- [ ] DEC-OPT-010 TEMPLAR_VOW → use DECISION_CHOOSE_VOW. File: `src/warhammer40k_ai/rules/templar_vows.py:349`
- [ ] DEC-OPT-011 WRATHFUL_PRESENCE → use DECISION_CHOOSE_WRATHFUL_PRESENCE. File: `src/warhammer40k_ai/rules/wrathful_presence.py:338`
- [ ] DEC-OPT-012 DARK_PACTS_CHOICE → use DECISION_CHOOSE_DARK_PACT. File: `src/warhammer40k_ai/units/unit.py:10170`
- [ ] DEC-OPT-013 DAEMONIC_ALLEGIANCE → use DECISION_CHOOSE_DAEMONIC_ALLEGIANCE. File: `src/warhammer40k_ai/roster/army.py:834`
- [ ] DEC-OPT-014 CODE_CHIVALRIC_DEED → use DECISION_CHOOSE_CHIVALRIC_OATH with context (deed vs quality). File: `src/warhammer40k_ai/rules/code_chivalric.py:294`
- [ ] DEC-OPT-015 CODE_CHIVALRIC_QUALITY → use DECISION_CHOOSE_CHIVALRIC_OATH with context (deed vs quality). File: `src/warhammer40k_ai/rules/code_chivalric.py:316`
- [ ] DEC-OPT-016 HIT_MODIFIER_IGNORES → use DECISION_CHOOSE_HIT_MODIFIER_IGNORES. Files: `src/warhammer40k_ai/engine/attack_resolution.py:551`, `src/warhammer40k_ai/engine/attack_resolution.py:682`, `src/warhammer40k_ai/units/wargear.py:2899`, `src/warhammer40k_ai/units/wargear.py:2996`
- [ ] DEC-OPT-017 SKILL_MODIFIER_IGNORES → use DECISION_CHOOSE_SKILL_MODIFIER_IGNORES. Files: `src/warhammer40k_ai/engine/attack_resolution.py:617`, `src/warhammer40k_ai/units/wargear.py:2953`
- [ ] DEC-OPT-018 OATH_OF_MOMENT_TARGET → likely DECISION_CHOOSE_QUARRY with context ability_name. File: `src/warhammer40k_ai/rules/oath_of_moment.py:230`
- [ ] DEC-OPT-019 BONDSMAN_TARGET → needs decision kind (new or DECISION_CHOOSE_QUARRY with context). File: `src/warhammer40k_ai/rules/bondsman.py:254`
- [ ] DEC-OPT-020 COMMAND_PHASE_BEARER_TARGET → needs decision kind (new or DECISION_CHOOSE_QUARRY with context). File: `src/warhammer40k_ai/rules/necrons_detachments.py:528`
- [ ] DEC-OPT-021 POWER_FROM_PAIN_ARCHON_POISONED_TONGUE → needs decision kind (new or reuse with context). File: `src/warhammer40k_ai/rules/power_from_pain.py:605`
- [ ] DEC-OPT-022 POWER_FROM_PAIN_EXPERIMENTAL_ENHANCEMENTS → needs decision kind (new or reuse with context). File: `src/warhammer40k_ai/rules/power_from_pain.py:682`
- [ ] DEC-OPT-023 CULT_AMBUSH_REINFORCEMENTS → needs decision kind. File: `src/warhammer40k_ai/rules/cult_ambush.py:728`
- [ ] DEC-OPT-024 CHARGE_MORTAL_WOUNDS_TARGET → needs decision kind (new or reuse with context). File: `src/warhammer40k_ai/engine/game.py:3108`
- [ ] DEC-OPT-025 MOVE_OVER_MORTAL_WOUNDS_TARGET → needs decision kind (new or reuse with context). File: `src/warhammer40k_ai/engine/game.py:3257`
- [ ] DEC-OPT-026 FIGHT_PHASE_END_MORTAL_WOUNDS_TARGET → needs decision kind (new or reuse with context). File: `src/warhammer40k_ai/engine/game.py:3562`
- [ ] DEC-OPT-027 CHARGE_PHASE_BODYGUARD_LOSS_MODEL → needs decision kind. File: `src/warhammer40k_ai/engine/game.py:3423`
- [ ] DEC-OPT-028 BATTLE_FOCUS_MOVE_MANEUVER / BATTLE_FOCUS_{single option} → needs decision kind (new) or DecisionRequest per maneuver. File: `src/warhammer40k_ai/rules/battle_focus.py:514`, `src/warhammer40k_ai/rules/battle_focus.py:518`

## Optional Yes/No Decisions (Player._should_use_optional_ability)

Each of the following uses `_should_use_optional_ability` directly instead of a DecisionRequest:

- [ ] DEC-YESNO-001 SHADOW_IN_THE_WARP → use DECISION_CONFIRM_YES_NO with context ability_name. File: `src/warhammer40k_ai/engine/game.py:571`
- [ ] DEC-YESNO-002 WAAAGH → use DECISION_CONFIRM_YES_NO with context ability_name. File: `src/warhammer40k_ai/engine/game.py:601`
- [ ] DEC-YESNO-003 POWER_FROM_PAIN (army rule activation) → use DECISION_CONFIRM_YES_NO. Files: `src/warhammer40k_ai/engine/game.py:790`, `src/warhammer40k_ai/rules/power_from_pain.py:1200`
- [ ] DEC-YESNO-004 POSSESSED_LORD activation → use DECISION_CONFIRM_YES_NO. File: `src/warhammer40k_ai/engine/game.py:843`
- [ ] DEC-YESNO-005 ENHANCEMENT_FIGHT_FIRST activation → use DECISION_CONFIRM_YES_NO. File: `src/warhammer40k_ai/engine/game.py:862`
- [ ] DEC-YESNO-006 RETURN_BODYGUARD_MODEL → use DECISION_CONFIRM_YES_NO. File: `src/warhammer40k_ai/engine/game.py:914`
- [ ] DEC-YESNO-007 OPPONENT_TURN_STRATEGIC_RESERVES → use DECISION_CONFIRM_YES_NO. File: `src/warhammer40k_ai/engine/game.py:1315`
- [ ] DEC-YESNO-008 SEDUCTIVE_GAMBIT → use DECISION_CONFIRM_YES_NO. File: `src/warhammer40k_ai/engine/game.py:3089`
- [ ] DEC-YESNO-009 MOVE_OVER_MORTAL_WOUNDS (use ability) → use DECISION_CONFIRM_YES_NO. File: `src/warhammer40k_ai/engine/game.py:3402`
- [ ] DEC-YESNO-010 FIGHT_PHASE_END_MORTAL_WOUNDS (use ability) → use DECISION_CONFIRM_YES_NO. File: `src/warhammer40k_ai/engine/game.py:3721`
- [ ] DEC-YESNO-011 SENSATIONAL_PERFORMANCE → use DECISION_CONFIRM_YES_NO. File: `src/warhammer40k_ai/engine/game.py:4729`
- [ ] DEC-YESNO-012 ASPECT_SHRINE_TOKEN → use DecisionRequest (likely DECISION_CHOOSE_ASPECT or DECISION_CONFIRM_YES_NO with context). File: `src/warhammer40k_ai/units/wargear.py:1883`
- [ ] DEC-YESNO-013 DARK_PACTS (use ability) → use DecisionRequest (likely DECISION_CONFIRM_YES_NO with context, then DECISION_CHOOSE_DARK_PACT). File: `src/warhammer40k_ai/units/unit.py:10167`
- [ ] DEC-YESNO-014 CULT_AMBUSH (use ability) → use DecisionRequest. File: `src/warhammer40k_ai/rules/cult_ambush.py:675`
- [ ] DEC-YESNO-015 CABAL_CHANNEL_WARP → use DecisionRequest. File: `src/warhammer40k_ai/rules/cabal_of_sorcerers.py:503`
- [ ] DEC-YESNO-016 POWER_FROM_PAIN_STRATAGEM → use DecisionRequest. File: `src/warhammer40k_ai/rules/stratagems.py:692`
- [ ] DEC-YESNO-017 GILDED_CHAMPION → use DecisionRequest (DECISION_USE_GILDED_CHAMPION). File: `src/warhammer40k_ai/rules/stratagems.py:2728`
- [ ] DEC-YESNO-018 DIRECT_THE_SLAUGHTER (CP discount usage) → use DecisionRequest. File: `src/warhammer40k_ai/roster/player.py:733`
- [ ] DEC-YESNO-019 TARGETED_STRATAGEM_DISCOUNT (CP discount usage) → use DecisionRequest. File: `src/warhammer40k_ai/roster/player.py:750`
- [ ] DEC-YESNO-020 GIFT_OF_FORESIGHT (CP discount usage) → use DecisionRequest. File: `src/warhammer40k_ai/roster/player.py:766`
- [ ] DEC-YESNO-021 MASTER_OF_THE_PAGEANT (CP discount usage) → use DecisionRequest. File: `src/warhammer40k_ai/roster/player.py:783`
- [ ] DEC-YESNO-022 BATTLE_FOCUS_FLITTING_SHADOWS → use DecisionRequest. Files: `src/warhammer40k_ai/rules/battle_focus.py:545`, `src/warhammer40k_ai/rules/battle_focus.py:574`
- [ ] DEC-YESNO-023 BATTLE_FOCUS_SUDDEN_STRIKE → use DecisionRequest. File: `src/warhammer40k_ai/rules/battle_focus.py:599`
- [ ] DEC-YESNO-024 BATTLE_FOCUS_FADE_BACK → use DecisionRequest. File: `src/warhammer40k_ai/rules/battle_focus.py:646`

## Auto-Resolved DecisionRequests (Must Remain External)

These create a DecisionRequest but immediately resolve it inside the engine based on hooks. They should be emitted and **left pending** for the controller (human UI, remote client, or AI) to resolve deterministically.

- [ ] DEC-AUTO-001 Reactive move positions auto-resolve DECISION_MOVE_UNIT using `choose_reactive_move_positions`. File: `src/warhammer40k_ai/engine/game.py:2024`
- [ ] DEC-AUTO-002 Battle Focus reactive selection auto-resolves DECISION_SELECT_OVERWATCH_SHOOTER. File: `src/warhammer40k_ai/engine/game.py:2123`
- [ ] DEC-AUTO-003 Loping Speed confirmation auto-resolves DECISION_CONFIRM_YES_NO. File: `src/warhammer40k_ai/engine/game.py:2711`
- [ ] DEC-AUTO-004 Transport reactive disembark auto-resolves DECISION_DISEMBARK. File: `src/warhammer40k_ai/engine/game.py:3910`
- [ ] DEC-AUTO-005 Blood Surge confirmation auto-resolves DECISION_CONFIRM_YES_NO. File: `src/warhammer40k_ai/engine/game.py:5021`

## Notes

- Items above should be implemented so **all choices are exposed as DecisionRequests** with deterministic `decision_id` and option IDs, and resolved only through `RESOLVE_DECISION` commands.
- When a decision can be declined, follow the single-dialog pattern with an explicit “None/Skip” option.
- If a decision kind does not exist, add one and update `docs/NETWORK_SAVELOAD_DESIGN.md` mapping accordingly.
