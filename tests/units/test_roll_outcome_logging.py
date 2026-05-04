from __future__ import annotations

import logging
from unittest.mock import patch

from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(self, name: str = "Test Unit"):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = ["Infantry"]
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def test_failed_leadership_roll_logs_info_not_error(caplog) -> None:
    unit = Unit(_MockDatasheet("Leadership Unit"))

    with (
        patch("warhammer40k_ai.units.unit_mixins.state_attachment_mixin.get_roll", return_value=12),
        caplog.at_level(logging.INFO),
    ):
        passed = unit.pass_leadership_check()

    assert passed is False
    assert "Leadership Unit Leadership test: 2D6 rolled 12 vs Ld 7 - FAILED!" in caplog.text
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]


def test_failed_feel_no_pain_roll_logs_info_not_error(caplog) -> None:
    unit = Unit(_MockDatasheet("Feel No Pain Unit"))
    model = unit.models[0]
    unit.has_feel_no_pain = lambda target_model=None: [(5, None)]

    with patch("warhammer40k_ai.units.model.get_roll", return_value=1), caplog.at_level(logging.INFO):
        model.take_damage(1, is_mortal=False, game_map=None)

    assert model.wounds == 1
    assert "Feel No Pain" in caplog.text
    assert "FAILED" in caplog.text
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]
