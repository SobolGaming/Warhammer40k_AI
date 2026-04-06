# Charge Roll Modifiers

## Overview
Charge roll modifiers are aggregated in `Game._collect_charge_modifiers()` and applied
when resolving charge rolls. The engine supports **additive** modifiers, rule-based rerolls,
and non-additive dice mechanics (e.g., 3D6 drop lowest).

## Supported Sources
- Unit abilities that state: "Add X to Charge rolls made for this unit."
- Bearer/leader abilities that grant charge bonuses to the bearer's unit.
- Per-unit charge roll modifiers stored in `special_rules`:
  - `enhancement_battle_lust_bonus_if_unbridled`
  - `code_chivalric_charge_bonus`
  - `charge_roll_modifier` / `charge_roll_modifiers`
  - `goretrack_onslaught_active`
- Friendly advance/charge auras parsed in `utility/aura_effects.py`.
- Target-strength conditional bonuses parsed by `Unit.get_charge_roll_target_strength_modifiers(...)`.
- Wargear keyword hits vs MONSTER/VEHICLE targets (Harpooned/Hooked/Impaled/Snagged) via
  `Unit.get_wargear_charge_keyword_modifiers(...)`.

## Notes
- Modifiers are additive and can stack.
- Some effects filter negative modifiers (e.g., Internal Rivalries / Driven by Ultimate Rage).
- Charge eligibility uses `Game.get_max_charge_distance(...)`, which includes modifiers and
  the configured charge dice spec.
- Re-roll prompts are handled by the reroll provider / unit abilities; the roll itself
  uses the configured charge dice spec.
- Declared charge targets are now preserved separately from post-roll movement legality.
  - `round_state.charge_target_ids` tracks the original declaration payload.
  - `round_state.charge_move_target_ids` stores the post-roll legal target set chosen by
    `engine/combat_timing.py::bind_charge_move_targets(...)`.
  - Charge movement requests use the post-roll bound target ids so later legality checks can
    vary by rules bundle without rewriting charge declaration flow.

## Charge Dice Spec (Non-Additive)
Charge rolls read the following optional per-unit keys from `unit.special_rules`:
- `charge_roll_dice_count`: total number of D6 rolled (default `2`)
- `charge_roll_keep_highest`: number of highest dice summed (default `2`)

Examples:
- Standard charge: `dice_count=2`, `keep_highest=2` (2D6)
- 3D6 drop lowest: `dice_count=3`, `keep_highest=2`
- 3D6 sum: `dice_count=3`, `keep_highest=3`
