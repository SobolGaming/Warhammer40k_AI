import pytest

from warhammer40k_ai.roster.army import Army, ArmyValidationError
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


def setup_csm_army(points_limit=2000) -> Army:
    army = Army("Chaos Space Marines", "Detachment", points_limit=points_limit)
    army.faction_id = "CSM"
    base = make_unit("CSM Unit", faction_keywords=["Heretic Astartes"])
    army.add_unit(base)
    return army


def test_cult_of_dark_gods_replaces_faction_keywords():
    army = setup_csm_army(points_limit=2000)
    cult = make_unit("Khorne Berzerkers", faction_keywords=["World Eaters"], cost=200)
    army.add_unit(cult)

    army.validate_cult_of_dark_gods()

    assert [str(k).strip().upper() for k in cult.faction_keywords] == ["HERETIC ASTARTES"]


def test_cult_of_dark_gods_points_cap_enforced():
    army = setup_csm_army(points_limit=2000)
    cult1 = make_unit("Rubric Marines", faction_keywords=["Thousand Sons"], cost=300)
    cult2 = make_unit("Plague Marines", faction_keywords=["Death Guard"], cost=250)
    army.add_unit(cult1)
    army.add_unit(cult2)

    with pytest.raises(ArmyValidationError):
        army.validate_cult_of_dark_gods()


def test_cult_of_dark_gods_ignored_for_non_csm():
    army = Army("World Eaters", "Detachment", points_limit=2000)
    army.faction_id = "WE"
    cult = make_unit("Khorne Berzerkers", faction_keywords=["World Eaters"], cost=200)
    army.add_unit(cult)

    army.validate_cult_of_dark_gods()

    assert [str(k).strip().upper() for k in cult.faction_keywords] == ["WORLD EATERS"]


def test_cult_of_dark_gods_disables_plague_marines_infusion():
    army = setup_csm_army(points_limit=2000)
    cult = make_unit("Plague Marines", faction_keywords=["Death Guard"], cost=200)
    cult.possible_abilities = ["Infused with the Blessings of Nurgle"]
    army.add_unit(cult)

    army.validate_cult_of_dark_gods()

    assert cult.special_rules.get("infused_blessings_of_nurgle_disabled") is True
