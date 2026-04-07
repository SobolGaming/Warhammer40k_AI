import pytest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(self, name, *, faction_name="Leagues of Votann", faction_keywords=None):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = []
        self.faction_keywords = list(faction_keywords or [faction_name.upper()])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _make_unit(name, *, faction_name="Leagues of Votann", faction_keywords=None) -> Unit:
    return Unit(_MockDatasheet(name, faction_name=faction_name, faction_keywords=faction_keywords))


def _make_game(detachment: str):
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    lov_army = Army.with_detachment("Leagues of Votann", detachment)
    lov_army.faction_id = "LOV"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.LOCAL, army=lov_army)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    return game, lov_army, enemy_army


def test_martial_leverage_grants_yp_on_enemy_destroyed():
    game, lov_army, enemy_army = _make_game("Needgaard Oathband")
    enemy = _make_unit("Enemy", faction_name="Enemy", faction_keywords=["ENEMY"])
    enemy_army.add_unit(enemy)

    game.event_system.publish("unit_destroyed", unit=enemy)

    assert lov_army.prioritised_efficiency.yield_points == 1


def test_martial_leverage_requires_needgaard_oathband():
    game, lov_army, enemy_army = _make_game("Hearthband")
    enemy = _make_unit("Enemy", faction_name="Enemy", faction_keywords=["ENEMY"])
    enemy_army.add_unit(enemy)

    game.event_system.publish("unit_destroyed", unit=enemy)

    assert lov_army.prioritised_efficiency.yield_points == 0


def test_martial_leverage_ignores_friendly_unit_destroyed():
    game, lov_army, _enemy_army = _make_game("Needgaard Oathband")
    friendly = _make_unit("Hearthkyn Warriors", faction_keywords=["LEAGUES OF VOTANN"])
    lov_army.add_unit(friendly)

    game.event_system.publish("unit_destroyed", unit=friendly)

    assert lov_army.prioritised_efficiency.yield_points == 0
