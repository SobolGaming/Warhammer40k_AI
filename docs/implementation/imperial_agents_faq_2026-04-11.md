# Imperial Agents FAQ Notes (2026-04-11)

This note records the Imperial Agents FAQ clarification validated against the current official Imperial Agents FAQ/errata as of 2026-04-11.

Implemented / regression-covered FAQ case:

- `Imperialis Fleet` enhancement selections now continue to apply to a `CHARACTER` that is attached after the target unit was selected.
  - `Clandestine Operation` selected units still grant `Infiltrators` to a later-attached `CHARACTER`.
  - `Combat Landers` selected units still grant `Deep Strike` to a later-attached `CHARACTER`, and the attached unit keeps `Deep Strike` for the every-model check.

Validation:

- Focused regression coverage was added in `tests/rules/test_imperial_agents_imperialis_fleet_enhancements.py`.
