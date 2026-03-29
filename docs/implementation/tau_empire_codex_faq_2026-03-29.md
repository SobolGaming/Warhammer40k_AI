# T'au Empire Codex FAQ Notes (2026-03-29)

This note records T'au Empire codex FAQ clarifications validated in the engine as of 2026-03-29.

## Implemented Clarifications

- `Crisis Battlesuits` keep a pivot value of `0"` even when modeled on the flying stems supplied in the kit.
- `Join the Hunt` can react to a destroyed `Kroot Carnivores` bodyguard unit even during the temporary leader-separation window after that bodyguard is wiped out.
- A `Kroot War Shaper` cannot use `War Leader` to discount `Join the Hunt` when the selected destroyed unit is that War Shaper's own bodyguard unit.
- `Hidden Hunters` suppresses `Kroot Packmates` reactive shooting when the originally selected KROOT target becomes ineligible for all of those attacks because of the 18" targeting restriction.
- An embarked `ETHEREAL` cannot use `Coordinated Leadership`.
- A solo `ETHEREAL` with a marker drone cannot become an Observer; that interaction only works when the `ETHEREAL` is part of an Attached unit whose bodyguard already has `For the Greater Good`.

## Engine Notes

- `Join the Hunt` destroyed-state checks now treat a zero-model bodyguard as destroyed even before surviving attached leaders are split off into separate units.
- Observer eligibility no longer falls back to broad `T'AU EMPIRE` faction keywords; it now follows `For the Greater Good` ownership and attached-unit semantics directly.
- `Kroot Packmates` snapshots now retain their triggering friendly target roots so post-selection targeting restrictions can invalidate the reactive shot correctly.

## Validation

- Focused regression coverage was added or updated in:
  - `tests/test_tau_codex_faq_validation.py`
  - `tests/test_tau_ethereal.py`
  - `tests/test_tau_krootox_riders.py`
  - `tests/test_tau_kroot_hunting_pack_stratagems.py`
  - `tests/test_for_the_greater_good.py`
