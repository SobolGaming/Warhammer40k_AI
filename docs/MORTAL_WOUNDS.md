# Mortal Wounds

This engine follows the 10th edition mortal wound sequence with the current spillover clarifications.

## Core behavior
- Each mortal wound is 1 damage and is applied one at a time.
- Mortal wounds are allocated using normal wound allocation rules (wounded models first).
- No saving throws (including invulnerable saves) can be made against mortal wounds.
- Feel No Pain rolls still apply to mortal wounds (unless a rule says wounds cannot be ignored).

## Spillover rules
- Default: mortal wounds spill over within the target unit until all mortal wounds are allocated or the unit is destroyed.
- Mortal wounds never spill to a different unit.

## No-spill carve-outs
- Mortal wounds caused by a failed [HAZARDOUS] test do not spill.
- Mortal wounds caused by a [DEVASTATING WOUNDS] critical wound do not spill; remaining mortal wounds from that attack are lost if the allocated model is destroyed.

## Timing for attack-sourced mortals
- For attacks that inflict mortal wounds, all normal damage is resolved first.
- Mortal wounds (including "in addition" mortals) are applied after normal damage, even if the normal damage was saved.

## Precision interaction
- If a mortal wound is caused by a [PRECISION] attack, the attacker can allocate those mortal wounds to a CHARACTER model in the target attached unit (subject to visibility).

## Engine notes
- Attack-based mortal wounds are queued per target and resolved after normal damage for that target.
- [DEVASTATING WOUNDS] uses no-spill logic; other attack-based mortal wounds use default spillover.
- Rules that add mortal wounds "in addition" should set `mortal_wound_in_addition=True` and provide a `mortal_wound_amount` on the attack instance.

## Non-attack mortal wound triggers (engine support)
- Movement phase end: roll a D6 for each enemy unit within range of the model; 2-3 = 1 mortal wound, 4-5 = D3, 6 = D6. If the ability also requires Battle-shock tests for units within range, those tests are triggered after resolving mortals.
- Fight phase end (model aura threshold): roll a D6 for each enemy unit within the model's range; on the listed threshold, that enemy unit suffers the listed mortal wounds (e.g. `4+` => `D3`).
