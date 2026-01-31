import pytest

from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.units.unit import Unit


class MockDatasheet:
    def __init__(self, name: str, *, abilities=None, cost=100):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": cost}]
        self.datasheets_models = [{
            "M": "6", "T": "4", "Sv": "3", "W": "1",
            "Ld": "7", "OC": "1",
            "base_size": "32mm", "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"


def make_unit(name: str, *, abilities=None) -> Unit:
    datasheet = MockDatasheet(name, abilities=abilities)
    return Unit(datasheet)


def test_unique_model_restriction_blocks_duplicates():
    ability = {
        "name": "Travelling Players",
        "description": "Unless otherwise stated, you cannot include more than one of this model in your army.",
        "type": "Datasheet",
        "parameter": "",
    }
    army = Army("Aeldari", "Detachment", points_limit=2000)
    unit1 = make_unit("Death Jester", abilities=[ability])
    unit2 = make_unit("Death Jester", abilities=[ability])
    army.add_unit(unit1)
    army.add_unit(unit2)

    with pytest.raises(ArmyValidationError):
        army.validate_unique_model_restrictions()


def test_unique_model_restriction_allows_single_instance():
    ability = {
        "name": "Travelling Players",
        "description": "Unless otherwise stated, you cannot include more than one of this model in your army.",
        "type": "Datasheet",
        "parameter": "",
    }
    army = Army("Aeldari", "Detachment", points_limit=2000)
    unit = make_unit("Death Jester", abilities=[ability])
    army.add_unit(unit)

    army.validate_unique_model_restrictions()
