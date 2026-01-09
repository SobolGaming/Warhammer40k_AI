import pytest

from warhammer40k_ai.classes.army import Army, ArmyValidationError
from warhammer40k_ai.classes.enhancement import Enhancement
from warhammer40k_ai.classes.unit import Unit


class MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None, cost=100, abilities=None):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": cost}]
        self.datasheets_models = [{
            "M": "10", "T": "10", "Sv": "2", "W": "12",
            "Ld": "7", "OC": "5",
            "base_size": "100mm", "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [{"name": a, "description": "", "type": "Abilities", "parameter": None} for a in (abilities or [])]
        self.loadout = "This model is equipped with: nothing"


def make_unit(name: str, *, keywords=None, faction_keywords=None, cost=100, abilities=None) -> Unit:
    datasheet = MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        cost=cost,
        abilities=abilities,
    )
    return Unit(datasheet)


def setup_imperium_army(points_limit=2000) -> Army:
    army = Army("Space Marines", "Detachment", points_limit=points_limit)
    army.faction_id = "SM"
    base = make_unit("Intercessors", faction_keywords=["IMPERIUM"])
    army.add_unit(base)
    return army


def _imperial_knight_unit(name: str, *, keywords=None) -> Unit:
    return make_unit(
        name,
        keywords=["IMPERIAL KNIGHTS"] + list(keywords or []),
        faction_keywords=["IMPERIUM"],
    )


def test_freeblades_requires_imperium():
    army = setup_imperium_army()
    outsider = make_unit("Outsider", faction_keywords=["XENOS"])
    knight = _imperial_knight_unit("Knight Errant", keywords=["TITANIC"])
    army.add_unit(outsider)
    army.add_unit(knight)

    with pytest.raises(ArmyValidationError):
        army.validate_allies()


def test_freeblades_armiger_limit():
    army = setup_imperium_army()
    for idx in range(4):
        army.add_unit(_imperial_knight_unit(f"Armiger {idx}", keywords=["ARMIGER"]))

    with pytest.raises(ArmyValidationError):
        army.validate_allies()


def test_freeblades_titanic_limit():
    army = setup_imperium_army()
    army.add_unit(_imperial_knight_unit("Titanic 1", keywords=["TITANIC"]))
    army.add_unit(_imperial_knight_unit("Titanic 2", keywords=["TITANIC"]))

    with pytest.raises(ArmyValidationError):
        army.validate_allies()


def test_freeblades_cannot_mix_armiger_and_titanic():
    army = setup_imperium_army()
    army.add_unit(_imperial_knight_unit("Armiger", keywords=["ARMIGER"]))
    army.add_unit(_imperial_knight_unit("Titanic", keywords=["TITANIC"]))

    with pytest.raises(ArmyValidationError):
        army.validate_allies()


def test_freeblades_warlord_or_enhancement_forbidden():
    army = setup_imperium_army()
    knight = _imperial_knight_unit("Knight Warlord", keywords=["TITANIC"])
    knight.is_warlord = True
    knight.enhancement = Enhancement(
        id="enh",
        name="Test Enhancement",
        faction_id="QI",
        detachment="Freeblade Lance",
        points=10,
    )
    army.add_unit(knight)

    with pytest.raises(ArmyValidationError):
        army.validate_allies()


def test_freeblades_allows_three_armigers():
    army = setup_imperium_army()
    for idx in range(3):
        army.add_unit(_imperial_knight_unit(f"Armiger {idx}", keywords=["ARMIGER"]))

    army.validate_allies()
