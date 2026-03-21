# Chaos Space Marines FAQ/Errata Notes (2026-03-21)

This note records the Chaos Space Marines FAQ clarifications validated in the engine as of 2026-03-21.

## Implemented Clarifications

- `Soul Link` can select an eligible `CHARACTER` model from your army even if that model is off the battlefield, provided it is not embarked within a `TRANSPORT`.
- A `Soul Link` bearer can use the Enhancement while in `Reserves` or `Strategic Reserves`.
- `Soul Link` copies the selected model's `Core`, `Faction`, and `Datasheet` abilities, but it does not copy attachment permissions.
- Borrowed `Soul Link` once-per-battle and once-per-phase limits are tracked on the bearer model, not shared with the source `CHARACTER`.
- Effects granted by borrowed `Soul Link` abilities do not persist after the borrowed abilities are replaced or expire.
- `Cults of the Dark Gods` disables `Infused with the Blessings of Nurgle` when `Plague Marines` are added to a Chaos Space Marines army.
- `Scrambled Coordinates` only blocks reserve-arrival setup during the `Reinforcements` step.
  - End-of-Movement-phase abilities can be sequenced after that denial window ends.
- `Focus of Hatred` cannot target an embarked unit.
  - If the chosen Attached unit later splits, each resulting unit remains the focus until the next Command phase.
- `Opportunistic Raiders` can target a unit that did not fight this phase if it was eligible to fight earlier in the phase.
- `Warp Strike` now requires the unit to have actually fought this phase.
  - When `Warp Talons` destroyed an enemy unit this phase, `Opportunistic Raiders` can still Fall Back first and then queue `Warp Strike`.
- `Brutal Example` destroys the selected bodyguard model before `Fire Overwatch` resolves.
- A unit targeted to shoot out of phase, including via `Fire Overwatch`, can make a `Dark Pact`.
  - Fight-on-death attacks do not create a `Dark Pact` trigger, and a unit cannot be selected to shoot without an eligible target just to make a `Dark Pact`.
- `Enhanced Warriors` applies if `Fabius Bile` starts the battle attached to a unit inside a `TRANSPORT`.

## Validation

- Focused regression coverage was added or updated in:
  - `tests/test_csm_afflicted_and_rules.py`
  - `tests/test_csm_deceptors_enhancements.py`
  - `tests/test_csm_deceptors_stratagems.py`
  - `tests/test_csm_veterans_of_the_long_war_detachment.py`
  - `tests/test_csm_renegade_raiders_stratagems.py`
  - `tests/test_brutal_example_overwatch.py`
  - `tests/test_csm_enhanced_warriors.py`
- Existing `Dark Pacts` regressions in `tests/test_dark_pacts.py` continue to cover:
  - out-of-phase shooting triggers, including the `Fire Overwatch` path
  - fight-on-death exclusions
  - refusing `Dark Pacts` when no eligible shooting target exists
