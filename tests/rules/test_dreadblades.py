import pytest

from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.rules.enhancement import Enhancement
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


def setup_csm_army() -> Army:
    army = Army.with_detachment("Chaos Space Marines", "Detachment", points_limit=2000)
    army.faction_id = "CSM"
    base = make_unit("CSM Unit", keywords=["CHAOS"], faction_keywords=["HERETIC ASTARTES"])
    army.add_unit(base)
    return army


def test_dreadblades_requires_chaos_keyword():
    army = setup_csm_army()
    knight = make_unit("War Dog", keywords=["CHAOS", "CHAOS KNIGHTS", "WAR DOG"])
    outsider = make_unit("Outsider", keywords=["IMPERIUM"])
    army.add_unit(knight)
    army.add_unit(outsider)

    with pytest.raises(ArmyValidationError):
        army.validate_dreadblades()


def test_dreadblades_war_dog_limit():
    army = setup_csm_army()
    for idx in range(4):
        army.add_unit(make_unit(f"War Dog {idx}", keywords=["CHAOS", "CHAOS KNIGHTS", "WAR DOG"]))

    with pytest.raises(ArmyValidationError):
        army.validate_dreadblades()


def test_dreadblades_titanic_limit():
    army = setup_csm_army()
    army.add_unit(make_unit("Titanic 1", keywords=["CHAOS", "CHAOS KNIGHTS", "TITANIC"]))
    army.add_unit(make_unit("Titanic 2", keywords=["CHAOS", "CHAOS KNIGHTS", "TITANIC"]))

    with pytest.raises(ArmyValidationError):
        army.validate_dreadblades()


def test_dreadblades_warlord_or_enhancement_forbidden():
    army = setup_csm_army()
    knight = make_unit("War Dog", keywords=["CHAOS", "CHAOS KNIGHTS", "WAR DOG"])
    knight.is_warlord = True
    knight.enhancement = Enhancement(
        id="enh",
        name="Test Enhancement",
        faction_id="CSM",
        detachment="Detachment",
        points=10,
    )
    army.add_unit(knight)

    with pytest.raises(ArmyValidationError):
        army.validate_dreadblades()
