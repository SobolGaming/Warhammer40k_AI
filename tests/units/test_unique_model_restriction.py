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
    army = Army.with_detachment("Aeldari", "Detachment", points_limit=2000)
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
    army = Army.with_detachment("Aeldari", "Detachment", points_limit=2000)
    unit = make_unit("Death Jester", abilities=[ability])
    army.add_unit(unit)

    army.validate_unique_model_restrictions()


def test_named_unit_restriction_blocks_duplicates_with_word_limit():
    ability = {
        "name": "Captain of the Company",
        "description": "Your army cannot include more than one Captain Sicarius unit.",
        "type": "Datasheet",
        "parameter": "",
    }
    army = Army.with_detachment("Space Marines", "Detachment", points_limit=2000)
    unit1 = make_unit("Captain Sicarius", abilities=[ability])
    unit2 = make_unit("Captain Sicarius", abilities=[ability])
    army.add_unit(unit1)
    army.add_unit(unit2)

    with pytest.raises(ArmyValidationError):
        army.validate_unique_model_restrictions()


def test_named_unit_restriction_allows_up_to_digit_limit():
    ability = {
        "name": "Captain Cadre",
        "description": "Your army cannot include more than 2 Captain Sicarius units.",
        "type": "Datasheet",
        "parameter": "",
    }
    army = Army.with_detachment("Space Marines", "Detachment", points_limit=2000)
    army.add_unit(make_unit("Captain Sicarius", abilities=[ability]))
    army.add_unit(make_unit("Captain Sicarius", abilities=[ability]))

    army.validate_unique_model_restrictions()


def test_named_unit_restriction_blocks_when_above_digit_limit():
    ability = {
        "name": "Captain Cadre",
        "description": "Your army cannot include more than 2 Captain Sicarius units.",
        "type": "Datasheet",
        "parameter": "",
    }
    army = Army.with_detachment("Space Marines", "Detachment", points_limit=2000)
    army.add_unit(make_unit("Captain Sicarius", abilities=[ability]))
    army.add_unit(make_unit("Captain Sicarius", abilities=[ability]))
    army.add_unit(make_unit("Captain Sicarius", abilities=[ability]))

    with pytest.raises(ArmyValidationError):
        army.validate_unique_model_restrictions()


def test_named_unit_restriction_blocks_duplicates_with_digit_one_singular():
    ability = {
        "name": "Captain Cadre",
        "description": "Your army cannot include more than 1 Captain Sicarius unit.",
        "type": "Datasheet",
        "parameter": "",
    }
    army = Army.with_detachment("Space Marines", "Detachment", points_limit=2000)
    army.add_unit(make_unit("Captain Sicarius", abilities=[ability]))
    army.add_unit(make_unit("Captain Sicarius", abilities=[ability]))

    with pytest.raises(ArmyValidationError):
        army.validate_unique_model_restrictions()


def test_named_model_restriction_blocks_duplicates():
    ability = {
        "name": "CHOSEN OF THE EMPEROR",
        "description": "You cannot include more than one EMPEROR'S CHAMPION model in your army.",
        "type": "Datasheet",
        "parameter": "",
    }
    army = Army.with_detachment("Space Marines", "Detachment", points_limit=2000)
    army.add_unit(make_unit("Emperor's Champion", abilities=[ability]))
    army.add_unit(make_unit("Emperor's Champion", abilities=[ability]))

    with pytest.raises(ArmyValidationError):
        army.validate_unique_model_restrictions()
