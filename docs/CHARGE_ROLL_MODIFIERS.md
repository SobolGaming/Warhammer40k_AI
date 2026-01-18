# Charge Roll Modifiers

## Overview
Charge roll modifiers are aggregated from unit rules and applied when resolving
charge rolls. The engine supports additive modifiers from unit abilities,
enhancements, and auras.

## Supported Sources
- Unit abilities that state: "Add X to Charge rolls made for this unit."
- Bearer/leader abilities that grant charge bonuses to the bearer's unit.
- Per-unit charge roll modifiers stored in `special_rules` (e.g. enhancements).
- Friendly advance/charge auras parsed in `utility/aura_effects.py`.

## Notes
- Modifiers are additive and can stack.
- Re-roll effects and alternative dice expressions (e.g., 3D6 drop lowest) are
  handled separately from numeric modifiers.
