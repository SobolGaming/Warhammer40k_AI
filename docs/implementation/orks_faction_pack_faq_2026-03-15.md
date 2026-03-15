# Orks Faction Pack FAQ/Errata Notes (2026-03-15)

This note records the Orks faction-pack FAQ/Errata clarifications validated in the engine as of 2026-03-15.

## Implemented Clarifications

- `Waaagh! active for your army` checks also apply when another rule makes Waaagh active for the unit.
  - Covered for Bully Boyz second Waaagh and unit-scoped Waaagh effects.
- `Krumpin' Time` only grants the attached CHARACTER the Feel No Pain 5+ ability while it remains part of the Attached unit.
- `Kunnin' Infiltrator` removal does not create a Fire Overwatch window.
- `Kunnin' Infiltrator` setup does create a Fire Overwatch window unless the unit cannot be targeted by Fire Overwatch, such as Kommandos via `Sneaky Surprise`.
- Waaagh-triggered abilities do not apply while the relevant unit/model is embarked in a TRANSPORT unless the rule explicitly says otherwise.
- `Conniving Runts` still grants its Normal move even if the mortal-wound roll fails or inflicts no mortal wounds.
- `GO GET 'EM!` checks the 10+ model rider after the attacking unit has finished shooting.
  - The Horde Move D6 reroll is now resolved from the post-shoot unit state rather than snapshotted when the Stratagem is used.
- `Bomb Squigs` cannot be used more than once in the same phase, even if the unit still has unused Bomb Squig tokens for later phases.

## Engine Notes

- Redeploy placements using setup-style movement now publish `unit_set_up` with `set_up_as_reinforcements=False`.
- Fire Overwatch now listens to `unit_set_up` in addition to move/charge triggers.
- Bomb Squig usage now records a deterministic turn/phase key so remaining tokens are preserved for later phases without allowing repeat use in the same phase.

## Validation

- Focused regression coverage was added/updated in:
  - `tests/test_bearer_unit_common_abilities.py`
  - `tests/test_orks_green_tide_stratagems.py`
  - `tests/test_orks_bomb_squigs.py`
  - `tests/test_overwatch_datasheet_abilities.py`
  - `tests/test_orks_datasheet_batch3_abilities.py`
