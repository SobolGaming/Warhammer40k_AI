import pytest
from types import SimpleNamespace

from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.unit import Unit


class MockDatasheet:
    def __init__(self, name: str):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": 100}]
        self.datasheets_models = [{
            "M": "6", "T": "4", "Sv": "3", "W": "1",
            "Ld": "7", "OC": "1",
            "base_size": "32mm", "inv_sv": "7", "inv_sv_descr": "none"
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def test_strategic_reserves_unit_with_deep_strike_can_arrive_anywhere_like_deep_strike():
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    game.turn = 2  # arrivals start turn 2

    p1 = Player("P1", PlayerControl.LOCAL, None)
    p2 = Player("P2", PlayerControl.REMOTE, None)
    game.add_player(p1)
    game.add_player(p2)

    a1 = Army.with_detachment("Army1", "Det1")
    a2 = Army.with_detachment("Army2", "Det2")
    p1.set_army(a1)
    p2.set_army(a2)

    unit = Unit(MockDatasheet("Arriver"))
    a1.add_unit(unit)
    unit.reserve_status = "strategic_reserves"
    unit.deployed = False
    unit.has_deep_strike = lambda: True

    enemy = Unit(MockDatasheet("Enemy"))
    a2.add_unit(enemy)
    enemy.deployed = True
    enemy.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    game.map.units = [enemy]

    # Position is far from all edges (>6") so Strategic Reserves edge rules would fail,
    # but Deep Strike rules should allow it (>9" from enemies).
    position = (30.0, 22.0, 0.0)
    assert game.can_place_unit_arriving_from_reserves(unit, position) is True


