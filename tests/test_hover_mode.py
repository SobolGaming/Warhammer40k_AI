from warhammer40k_ai.classes.game import Game, Battlefield, BattlefieldSize
from warhammer40k_ai.classes.player import Player, PlayerType
from warhammer40k_ai.classes.army import Army
from warhammer40k_ai.classes.deployment import DeploymentManager
from warhammer40k_ai.classes.unit import Unit


def _hover_ability_entry():
    return {
        "ability_data": {
            "name": "Hover",
            "faction_id": "",
            "description": "",
            "legend": "",
        },
        "type": "Core",
        "parameter": "",
    }


class MockDatasheet:
    def __init__(self, name: str, *, keywords=None, abilities=None, move: str = "12"):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": 100}]
        self.datasheets_models = [{
            "M": move, "T": "4", "Sv": "3", "W": "1",
            "Ld": "7", "OC": "1",
            "base_size": "32mm", "inv_sv": "7", "inv_sv_descr": "none"
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"


def test_hover_mode_sets_movement_and_disables_aircraft_keyword():
    unit = Unit(MockDatasheet(
        "Hovercraft",
        keywords=["Aircraft", "Fly"],
        abilities=[_hover_ability_entry()],
        move="14",
    ))

    assert unit.is_aircraft is True
    assert unit.movement == 14

    unit.set_hover_mode(True)

    assert unit.hover_mode is True
    assert unit.movement == 20
    assert unit.is_aircraft is False
    assert unit.has_any_keyword("AIRCRAFT") is False
    assert "aircraft" not in [k.lower() for k in unit.get_effective_keywords()]


def test_hover_declaration_applied_in_battle_formations():
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    p1 = Player("P1", PlayerType.HUMAN, None)
    p2 = Player("P2", PlayerType.AI, None)
    game.add_player(p1)
    game.add_player(p2)

    a1 = Army("Army1", "Det1")
    a2 = Army("Army2", "Det2")
    p1.set_army(a1)
    p2.set_army(a2)

    hover_unit = Unit(MockDatasheet(
        "Hover Unit",
        keywords=["Aircraft"],
        abilities=[_hover_ability_entry()],
    ))
    other_unit = Unit(MockDatasheet(
        "Hover Unit B",
        keywords=["Aircraft"],
        abilities=[_hover_ability_entry()],
    ))
    a1.add_unit(hover_unit)
    a1.add_unit(other_unit)

    p1.set_next_optional_selection("HOVER_MODE", [str(hover_unit._id)])

    game.execute_declare_battle_formations_phase()

    assert hover_unit.hover_mode is True
    assert hover_unit.hover_declared is True
    assert other_unit.hover_mode is False
    assert other_unit.hover_declared is True


def test_aircraft_forced_into_strategic_reserves_when_not_hover():
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    p1 = Player("P1", PlayerType.HUMAN, None)
    p2 = Player("P2", PlayerType.AI, None)
    game.add_player(p1)
    game.add_player(p2)

    a1 = Army("Army1", "Det1")
    a2 = Army("Army2", "Det2")
    p1.set_army(a1)
    p2.set_army(a2)

    forced_unit = Unit(MockDatasheet(
        "Forced Aircraft",
        keywords=["Aircraft"],
        abilities=[_hover_ability_entry()],
    ))
    hover_unit = Unit(MockDatasheet(
        "Hover Aircraft",
        keywords=["Aircraft"],
        abilities=[_hover_ability_entry()],
    ))
    hover_unit.set_hover_mode(True)

    a1.add_unit(forced_unit)
    a1.add_unit(hover_unit)

    manager = DeploymentManager(game)
    manager.attacker = p1
    manager.defender = p2

    deployment_results = {
        "reserves": {
            p1.name: {
                forced_unit.name: "deploy",
                hover_unit.name: "deploy",
            },
            p2.name: {},
        }
    }

    manager.set_reserves_status(deployment_results)

    assert forced_unit.reserve_status == "strategic_reserves"
    assert getattr(forced_unit, "_started_in_reserves", False) is True
    assert hover_unit.reserve_status == "deployed"
