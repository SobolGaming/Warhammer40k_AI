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


def _setup_game(
    detachment_name: str,
    *,
    include_dark_master_source: bool = False,
    include_greater: bool = False,
    belakor_position=(20.0, 12.0, 0.0),
    arriver_name: str = "Arriver",
    arriver_abilities=None,
    arriver_keywords=None,
):
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

    if include_dark_master_source:
        belakor = Unit(MockDatasheet("Be'lakor", abilities=["The Dark Master (Aura)"], keywords=["LEGIONES DAEMONICA"]))
        a1.add_unit(belakor)
        belakor.deployed = True
        belakor.models[0].set_location(belakor_position[0], belakor_position[1], belakor_position[2], 0.0)

    if arriver_keywords is None:
        arriver_keywords = ["LEGIONES DAEMONICA"]
    if arriver_abilities is None:
        arriver_abilities = []
    arriver = Unit(MockDatasheet(arriver_name, abilities=arriver_abilities, keywords=arriver_keywords))
    a1.add_unit(arriver)
    arriver.reserve_status = "reserves"
    arriver.deployed = False
    arriver.has_deep_strike = lambda: True

    enemy = Unit(MockDatasheet("Enemy"))
    a2.add_unit(enemy)
    enemy.deployed = True
    enemy.models[0].set_location(12.0, 10.0, 8.0, 0.0)

    game.map.units = [enemy]

    if include_greater:
        greater = Unit(MockDatasheet("Bloodthirster", keywords=["LEGIONES DAEMONICA", "KHORNE"]))
        a1.add_unit(greater)
        greater.deployed = True
        greater.models[0].set_location(18.0, 10.0, 0.0, 0.0)
        game.map.units.append(greater)

    if include_dark_master_source:
        game.map.units.append(belakor)

    return game, arriver


def test_warp_rifts_allows_6_horizontal_in_shadow_zone(monkeypatch):
    game, unit = _setup_game("Daemonic Incursion")
    monkeypatch.setattr(
        game,
        "is_position_wholly_in_deployment_zone",
        lambda _x, _y, _base, player_name: player_name == "P1",
    )
    position = (20.0, 10.0, 0.0)
    assert game.can_place_unit_arriving_from_reserves(unit, position) is True


def test_warp_rifts_does_not_allow_6_with_dark_master_self(monkeypatch):
    game, unit = _setup_game(
        "Daemonic Incursion",
        arriver_name="Be'lakor",
        arriver_abilities=["The Dark Master (Aura)"],
    )
    monkeypatch.setattr(
        game,
        "is_position_wholly_in_deployment_zone",
        lambda _x, _y, _base, _player_name: False,
    )
    position = (20.0, 10.0, 0.0)
    assert game.can_place_unit_arriving_from_reserves(unit, position) is False


def test_warp_rifts_allows_6_with_dark_master_other_unit(monkeypatch):
    game, unit = _setup_game("Daemonic Incursion", include_dark_master_source=True)
    monkeypatch.setattr(
        game,
        "is_position_wholly_in_deployment_zone",
        lambda _x, _y, _base, _player_name: False,
    )
    position = (20.0, 10.0, 0.0)
    assert game.can_place_unit_arriving_from_reserves(unit, position) is True


def test_warp_rifts_does_not_allow_6_with_greater_daemon_self(monkeypatch):
    game, unit = _setup_game(
        "Daemonic Incursion",
        arriver_name="Bloodthirster",
        arriver_keywords=["LEGIONES DAEMONICA", "KHORNE"],
    )
    monkeypatch.setattr(
        game,
        "is_position_wholly_in_deployment_zone",
        lambda _x, _y, _base, _player_name: False,
    )
    position = (20.0, 10.0, 0.0)
    assert game.can_place_unit_arriving_from_reserves(unit, position) is False


def test_warp_rifts_allows_6_with_greater_daemon_other_unit(monkeypatch):
    game, unit = _setup_game(
        "Daemonic Incursion",
        include_greater=True,
        arriver_keywords=["LEGIONES DAEMONICA", "KHORNE"],
    )
    monkeypatch.setattr(
        game,
        "is_position_wholly_in_deployment_zone",
        lambda _x, _y, _base, _player_name: False,
    )
    position = (20.0, 10.0, 0.0)
    assert game.can_place_unit_arriving_from_reserves(unit, position) is True


def test_standard_deep_strike_still_needs_9_horizontal():
    game, unit = _setup_game("Other Detachment")
    position = (20.0, 10.0, 0.0)
    assert game.can_place_unit_arriving_from_reserves(unit, position) is False
