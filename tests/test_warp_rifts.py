import pytest

from warhammer40k_ai.classes.game import Game, Battlefield, BattlefieldSize
from warhammer40k_ai.classes.player import Player, PlayerType
from warhammer40k_ai.classes.army import Army
from warhammer40k_ai.classes.unit import Unit


class MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None):
        self.name = name
        self.faction_data = {"name": "Chaos Daemons"}
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": 100}]
        self.datasheets_models = [{
            "M": "6", "T": "4", "Sv": "3", "W": "1",
            "Ld": "7", "OC": "1",
            "base_size": "32mm", "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        for ability_name in list(abilities or []):
            self.datasheets_abilities.append({
                "name": ability_name,
                "description": "",
                "type": "Datasheet",
                "parameter": "",
            })
        self.loadout = "This model is equipped with: nothing"


def _setup_game(detachment_name: str):
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    game.turn = 2

    p1 = Player("P1", PlayerType.HUMAN, None)
    p2 = Player("P2", PlayerType.AI, None)
    game.add_player(p1)
    game.add_player(p2)

    a1 = Army("Chaos Daemons", detachment_name)
    a1.faction_id = "CD"
    a2 = Army("Opponents", "Other")
    p1.set_army(a1)
    p2.set_army(a2)

    belakor = Unit(MockDatasheet("Be'lakor", abilities=["The Dark Master (Aura)"], keywords=["LEGIONES DAEMONICA"]))
    a1.add_unit(belakor)
    belakor.deployed = True
    belakor.models[0].set_location(20.0, 15.5, 0.0, 0.0)

    arriver = Unit(MockDatasheet("Arriver", keywords=["LEGIONES DAEMONICA"]))
    a1.add_unit(arriver)
    arriver.reserve_status = "reserves"
    arriver.deployed = False
    arriver.has_deep_strike = lambda: True

    enemy = Unit(MockDatasheet("Enemy"))
    a2.add_unit(enemy)
    enemy.deployed = True
    enemy.models[0].set_location(12.0, 10.0, 8.0, 0.0)

    game.map.units = [belakor, enemy]
    return game, arriver


def test_warp_rifts_allows_6_horizontal_in_shadow():
    game, unit = _setup_game("Daemonic Incursion")
    position = (20.0, 10.0, 0.0)
    assert game.can_place_unit_arriving_from_reserves(unit, position) is True


def test_standard_deep_strike_still_needs_9_horizontal():
    game, unit = _setup_game("Other Detachment")
    position = (20.0, 10.0, 0.0)
    assert game.can_place_unit_arriving_from_reserves(unit, position) is False
