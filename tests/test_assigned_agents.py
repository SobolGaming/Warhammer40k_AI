import pytest
from types import SimpleNamespace

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


def setup_sm_army(points_limit=2000) -> Army:
    army = Army("Space Marines", "Detachment", points_limit=points_limit)
    army.faction_id = "SM"
    base = make_unit("Intercessors", faction_keywords=["IMPERIUM", "ADEPTUS ASTARTES"])
    army.add_unit(base)
    return army


def test_assigned_agents_caps_allow_transports():
    army = setup_sm_army()
    retinue = make_unit(
        "Retinue",
        keywords=["Retinue"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    character = make_unit(
        "Character",
        keywords=["Character"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    requisitioned = make_unit(
        "Requisitioned",
        keywords=["Requisitioned"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    transport = make_unit(
        "AoI Transport",
        keywords=["Dedicated Transport"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    for unit in (retinue, character, requisitioned, transport):
        army.add_unit(unit)

    army.validate_allies()


def test_assigned_agents_caps_enforced():
    army = setup_sm_army()
    retinue = make_unit(
        "Retinue",
        keywords=["Retinue"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    character = make_unit(
        "Character",
        keywords=["Character"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    requisitioned = make_unit(
        "Requisitioned",
        keywords=["Requisitioned"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    extra_req = make_unit(
        "Requisitioned 2",
        keywords=["Requisitioned"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    for unit in (retinue, character, requisitioned, extra_req):
        army.add_unit(unit)

    with pytest.raises(ArmyValidationError):
        army.validate_allies()


def test_assigned_agents_requires_imperium():
    army = setup_sm_army()
    outsider = make_unit("Outsider", faction_keywords=["XENOS"])
    agents = make_unit(
        "Agents",
        keywords=["Retinue"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    army.add_unit(outsider)
    army.add_unit(agents)

    with pytest.raises(ArmyValidationError):
        army.validate_allies()


def test_assigned_agents_empty_transport_destroyed_round_one():
    army = setup_sm_army()
    transport = make_unit(
        "AoI Transport",
        keywords=["Dedicated Transport"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    army.add_unit(transport)
    army.player = SimpleNamespace(game=SimpleNamespace(map=None))

    army.on_battle_round_start(1)

    assert not transport.is_alive()
