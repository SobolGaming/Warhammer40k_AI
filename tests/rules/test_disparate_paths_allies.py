import pytest

import warhammer40k_ai.roster.army as army_module
from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.utility.ability_support import (
    ABILITY_CORSAIRS_AND_TRAVELLING_PLAYERS,
    ABILITY_DISPARATE_PATHS,
)
from warhammer40k_ai.units.unit import Unit


class MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None, cost=100):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": cost}]
        self.datasheets_models = [{
            "M": "6", "T": "4", "Sv": "3", "W": "1",
            "Ld": "7", "OC": "1",
            "base_size": "32mm", "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def make_unit(name: str, *, keywords=None, faction_keywords=None, cost=100) -> Unit:
    datasheet = MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords, cost=cost)
    return Unit(datasheet)


def setup_army(*, faction: str = "Drukhari", faction_id: str = "DRU", points_limit: int = 2000) -> Army:
    army = Army.with_detachment(faction, "Detachment", points_limit=points_limit)
    army.faction_id = faction_id
    return army


def activate_disparate_only(monkeypatch):
    def _fake_has_ability_id(_army, ability_id: str) -> bool:
        if ability_id == ABILITY_CORSAIRS_AND_TRAVELLING_PLAYERS:
            return False
        if ability_id == ABILITY_DISPARATE_PATHS:
            return True
        return False

    monkeypatch.setattr(army_module, "army_has_ability_id", _fake_has_ability_id)


def test_disparate_paths_allows_harlequins_for_drukhari_when_active(monkeypatch):
    activate_disparate_only(monkeypatch)
    army = setup_army()
    army.add_unit(make_unit("Kabalites", faction_keywords=["DRUKHARI"]))
    army.add_unit(make_unit("Troupe", faction_keywords=["HARLEQUINS"]))

    army.validate_allies()


def test_disparate_paths_rejects_non_base_non_harlequins_ynnari(monkeypatch):
    activate_disparate_only(monkeypatch)
    army = setup_army()
    army.add_unit(make_unit("Kabalites", faction_keywords=["DRUKHARI"]))
    army.add_unit(make_unit("Outsider", faction_keywords=["IMPERIUM"]))

    with pytest.raises(ArmyValidationError, match="Disparate Paths"):
        army.validate_allies()


def test_disparate_paths_forbids_harlequins_or_ynnari_as_army_faction(monkeypatch):
    activate_disparate_only(monkeypatch)

    for forbidden in ("HARLEQUINS", "YNNARI"):
        army = setup_army(faction="Aeldari", faction_id="AE")
        army.faction_keyword = [forbidden]
        with pytest.raises(ArmyValidationError, match="cannot select 'HARLEQUINS' or 'Ynnari'"):
            army.validate_allies()
