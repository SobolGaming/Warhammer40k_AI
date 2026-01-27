from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.units.unit import Unit


_ADVANCE_NO_ROLL_TEXT = (
    'Each time this unit Advances, do not make an Advance roll. Instead, until the end of the '
    'phase, add 6" to the Move characteristic of models in this unit.'
)


class _MockDatasheet:
    def __init__(self, ability_text: str) -> None:
        self.id = "advance-no-roll"
        self.name = "Swift Unit"
        self.faction_data = {"name": "Test"}
        self.keywords = ["INFANTRY"]
        self.faction_keywords = ["TEST"]
        self.attached_to = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "2",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [
            {
                "name": "Fixed Advance",
                "description": ability_text,
                "type": "",
                "parameter": "",
            }
        ]
        self.loadout = "This model is equipped with: nothing"


def _make_unit(ability_text: str = _ADVANCE_NO_ROLL_TEXT) -> Unit:
    return Unit(_MockDatasheet(ability_text))


def test_advance_no_roll_is_parsed_and_skips_roll():
    unit = _make_unit()
    effect = unit._get_advance_no_roll_effect()
    assert effect is not None
    assert int(effect.get("distance", 0) or 0) == 6

    with patch("warhammer40k_ai.units.unit.get_roll") as roll_mock:
        advance = unit.prepare_advance()

    assert int(advance or 0) == 6
    roll_mock.assert_not_called()


def test_advance_no_roll_ignores_advance_roll_modifiers():
    unit = _make_unit()
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    sr["advance_roll_modifier"] = 3
    unit.special_rules = sr

    assert unit._apply_advance_roll_modifiers(1) == 6

