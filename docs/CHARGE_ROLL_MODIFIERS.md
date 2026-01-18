# Charge Roll Modifiers

## Overview
Charge roll modifiers are aggregated in `Game._collect_charge_modifiers()` and applied
when resolving charge rolls. The engine currently supports **additive** modifiers and
rule-based rerolls; non-additive dice mechanics (e.g., 3D6 drop lowest) are not yet wired.

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
- Charge eligibility uses `Game.get_max_charge_distance(...)`, which includes modifiers.
- Re-roll prompts are handled by the reroll provider / unit abilities; the roll itself
  is still `2D6` in the current engine.
