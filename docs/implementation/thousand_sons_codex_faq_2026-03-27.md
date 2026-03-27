# Thousand Sons Codex FAQ Notes (2026-03-27)

This note records Thousand Sons codex FAQ clarifications validated in the engine as of 2026-03-27.

## Implemented Clarifications

- `Cabal of Sorcerers` rituals are selected and resolved one at a time during the Shooting phase; the engine does not require the full ritual sequence to be committed at phase start.
- `Touched by Tzeentch` grants a unit permission to shoot and charge after Advancing without forcing that choice to be declared when the Stratagem is used.
- A `Tzaangor` unit moved into Strategic Reserves mid-battle by `Ambushing Hunters` cannot use `Twisted Mirage` to arrive during turn 1.
- `Exalted Sorcerer on Disc of Tzeentch` and `Tzaangor Shaman` can lead `Tzaangor Enlightened with fatecaster greatbows`.
- `Risen Rubricae` grants `Infiltrators` to an attached CHARACTER as part of the Attached unit.
- `Channel the Warp` is chosen after the ritual's initial 2D6 roll is known.
- Doubles/triples only inflict the ritual's self-damage when `Channel the Warp` is actually used.

## Engine Notes

- `Twisted Mirage` now rejects direct/manual use when the selected unit is not currently eligible under the same reserve-arrival checks used by the normal reinforcements pipeline.

## Validation

- Focused regression coverage was added/updated in:
  - `tests/test_cabal_of_sorcerers.py`
  - `tests/test_thousand_sons_warpmeld_pact_stratagems.py`
  - `tests/test_thousand_sons_leader_attachments.py`
  - `tests/test_rubricae_phalanx_enhancements.py`
  - `tests/test_thousand_sons_batch1_abilities.py`
