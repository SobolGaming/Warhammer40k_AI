# Astra Militarum Faction Pack FAQ Notes (2026-04-08)

This note records Astra Militarum faction-pack FAQ clarifications validated against the current official `ASTRA MILITARUM` Faction Pack v1.4 on 2026-04-08.

Implemented / regression-covered FAQ cases:

- `Inspired Command` and `Snap To It` now have explicit regression coverage showing that their out-of-sequence Order is still legal after the selected `OFFICER` has already used its normal datasheet order quota earlier in the same battle round.
- Reissuing the same Order to a unit does not stack its effect; the engine keeps a single active instance of that Order.
- `Reinforcements!` now rejects a destroyed `Battle-shocked` unit, matching the FAQ answer.
- `vox-caster` CP refunds now dedupe identical bearer-generated refund specs so two `vox-caster` bearers in the same unit only create one refund attempt.
- Destroyed units do not resolve targeted-Stratagem CP refunds, which closes the `vox-caster` plus `Reinforcements!` FAQ case.
- `Creeping Barrage` now resolves one eligible enemy unit at a time, in player-chosen order, and stops rolling once the battle-size maximum number of shaken units has been reached.
- An attached `Ogryn Bodyguard` prevents a `Militarum Tempestus Command Squad` attached unit from using `Deep Strike`, because every model in the combined unit must have that ability.
