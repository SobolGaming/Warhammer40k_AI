# Space Marines FAQ/Errata Notes (2026-03-20)

This note records the Space Marines FAQ and errata clarifications implemented in the engine as of 2026-03-20.

## Implemented Clarifications

- `Codex: Space Marines Detachments` now includes the generic codex detachments plus `Bastion Task Force` and `Orbital Assault Force` from the Space Marines faction pack for codex-gated rules such as the Oath of Moment wound bonus.
- `A Deadly Prize` sabotage persists after the opponent takes control of the objective marker.
  - The mortal-wound trigger is inactive while the opponent controls that marker.
- `Oath of Moment` persists on a surviving unit when an attached target stops being an Attached unit.
  - The engine now tracks all members of the targeted Attached unit so the effect rebinds to the surviving unit after separation.
- `Rapid Ingress` cannot target a `Drop Pod Assault` unit during the first battle round.
  - This carve-out is limited to the Drop Pod FAQ case and does not block other round-one reserve effects such as `Hunter's Instincts`.
- `Orbital Comms Array` only allows one refund roll per targeted unit, even if multiple Impulsors are in range.
  - Matching Aura abilities do not stack, and a failed roll cannot be retried from another Impulsor.
- `Master of Battle` backup Oath targets only become active after the attacking unit has finished resolving all of its attacks.
  - Destroying the first Oath target mid-sequence does not grant re-rolls against the backup target until that attacking unit fully resolves.

## Validation

- Focused regression coverage was added or updated in:
  - `tests/test_oath_of_moment.py`
  - `tests/test_space_marines_vanguard_spearhead_stratagems.py`
  - `tests/test_homing_beacon_rapid_ingress.py`
  - `tests/test_space_marines_faq_validation.py`
- Additional FAQ cases now have explicit regression coverage for:
  - `Rites of Battle` targeting the Captain's unit while in `Reserves` or `Strategic Reserves`
  - `Oath of Moment` selecting a target in `Reserves`
  - `Enhancement` use while in `Reserves` via `Beacon Angelis`
  - multiple `Astartes Banner` instances stacking
  - `Firing Deck` attacks not inheriting an embarked attached Leader's weapon keywords
