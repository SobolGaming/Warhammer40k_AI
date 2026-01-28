# DecisionRequest/Command API Audit (Tracked Issues)

Date: January 28, 2026  
Status: Draft (tracking list)

This list enumerates **all known player-facing decisions** that do **not** currently route through the unified DecisionRequest/Command API, including cases where a DecisionRequest is created and then **auto-resolved** inside the engine. Each item should be updated so the decision is emitted and resolved through the deterministic decision/command flow.

## Non-DecisionRequest Flows (Direct UI/Console/Provider)

- [ ] DEC-DEP-001 Deployment zone selection bypasses DecisionRequest. Current path uses DeploymentDecisionMaker/UI. Files: `src/warhammer40k_ai/engine/deployment.py:21`, `src/warhammer40k_ai/UI/human_interface.py:33`. Suggested: new DecisionRequest (e.g., DECISION_CHOOSE_DEPLOYMENT_ZONE) with deterministic options.

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
- [ ] DEC-OPT-012 DARK_PACTS_CHOICE → use DECISION_CHOOSE_DARK_PACT with “Skip” option (single-dialog pattern). File: `src/warhammer40k_ai/units/unit.py:10170`
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
- [ ] DEC-OPT-025 MOVE_OVER_MORTAL_WOUNDS_TARGET → needs decision kind (new or reuse with context), include “None/Skip” for optional use. File: `src/warhammer40k_ai/engine/game.py:3257`
- [ ] DEC-OPT-026 FIGHT_PHASE_END_MORTAL_WOUNDS_TARGET → needs decision kind (new or reuse with context), include “None/Skip” for optional use. File: `src/warhammer40k_ai/engine/game.py:3562`
- [ ] DEC-OPT-027 CHARGE_PHASE_BODYGUARD_LOSS_MODEL → needs decision kind. File: `src/warhammer40k_ai/engine/game.py:3423`
- [ ] DEC-OPT-028 BATTLE_FOCUS_MOVE_MANEUVER / BATTLE_FOCUS_{single option} → needs decision kind (new) or DecisionRequest per maneuver. File: `src/warhammer40k_ai/rules/battle_focus.py:514`, `src/warhammer40k_ai/rules/battle_focus.py:518`
- [ ] DEC-OPT-029 ASPECT_SHRINE_TOKEN → not YES/NO; requires multi-option choice (Use / Skip / Suppress). File: `src/warhammer40k_ai/units/wargear.py:1883`

## Optional Yes/No Decisions (Player._should_use_optional_ability)

All current true YES/NO confirmations have been routed through DecisionRequests. Optional target-pick flows that can be declined remain in the **DEC-OPT** list and should use a single selection dialog with a “None/Skip” option (e.g., Move-over mortals, Fight-phase end mortals, Dark Pacts).

## Notes

- Items above should be implemented so **all choices are exposed as DecisionRequests** with deterministic `decision_id` and option IDs, and resolved only through `RESOLVE_DECISION` commands.
- When a decision can be declined, follow the single-dialog pattern with an explicit “None/Skip” option.
- If a decision kind does not exist, add one and update `docs/NETWORK_SAVELOAD_DESIGN.md` mapping accordingly.
