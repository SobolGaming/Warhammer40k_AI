import pytest

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class MockDatasheet:
    def __init__(self, name: str, keywords=None, movement=6, model_count=1, base_size="32mm", save="4", wounds="1"):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = keywords or []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [{
            "M": str(movement), "T": "4", "Sv": str(save), "W": str(wounds),
            "Ld": "7", "OC": "1",
            "base_size": base_size, "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _install_deterministic_rolls(monkeypatch, rolls):
    import warhammer40k_ai.utility.dice as dice_mod
    import warhammer40k_ai.units.wargear as wargear_mod

    it = iter(rolls)

    def rigged(_expr: str):
        try:
            return next(it)
        except StopIteration:
            return 6

    monkeypatch.setattr(dice_mod, "get_roll", rigged)
    monkeypatch.setattr(wargear_mod, "get_roll", rigged)


def test_model_destroyed_event_carries_attacker_and_allows_cp_gain(monkeypatch):
    # Rolls: hit=6, wound=6, save=1 (fail)
    _install_deterministic_rolls(monkeypatch, [6, 6, 1])

    bf = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    p1 = Player("P1", PlayerControl.LOCAL, Army("Army A", "Detachment A"))
    p2 = Player("P2", PlayerControl.REMOTE, Army("Army B", "Detachment B"))
    game.add_player(p1)
    game.add_player(p2)

    attacker = Unit(MockDatasheet("Attacker", model_count=1))
    attacker.deployed = True
    attacker.models[0].set_location(10.0, 10.0, 0.0, 0.0)

    # Target is a CHARACTER model
    target = Unit(MockDatasheet("Target", keywords=["CHARACTER"], model_count=1))
    target.deployed = True
    target.models[0].set_location(20.0, 10.0, 0.0, 0.0)

    p1.army.add_unit(attacker)
    p2.army.add_unit(target)
    game.map.units = [attacker, target]

    # Give attacker a ranged weapon
    gun = Wargear({
        "name": "Test Gun",
        "type": "Ranged",
        "range": "24",
        "A": "1",
        "BS_WS": "2",
        "S": "10",
        "AP": "0",
        "D": "1",
        "description": "",
    })
    attacker.models[0].wargear.append(gun)

    # Attacker has Trophy Taker (generic description-based support).
    attacker.possible_abilities.append(
        Ability(
            name="Trophy Taker",
            faction_id="",
            description="Each time this model destroys an enemy <span class=\"kwb\">CHARACTER</span> model, you gain 1CP.",
            type="Datasheet",
            parameter="",
        )
    )
    attacker._invalidate_ability_cache()

    start_cp = p1.command_points

    # CP gain should be applied automatically by the game's default event subscribers.

    # Fire the weapon and kill the target model
    profile = gun.profiles["default"]
    profile.attack(target, attacker.models[0], game_map=game.map)

    assert target.is_alive() is False
    assert p1.command_points == start_cp + 1


def test_unit_destroyed_character_model_without_enemy_keyword_grants_cp(monkeypatch):
    # Rolls: hit=6, wound=6, save=1 (fail)
    _install_deterministic_rolls(monkeypatch, [6, 6, 1])

    bf = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    p1 = Player("P1", PlayerControl.LOCAL, Army("Army A", "Detachment A"))
    p2 = Player("P2", PlayerControl.REMOTE, Army("Army B", "Detachment B"))
    game.add_player(p1)
    game.add_player(p2)

    attacker = Unit(MockDatasheet("Attacker", model_count=1))
    attacker.deployed = True
    attacker.models[0].set_location(10.0, 10.0, 0.0, 0.0)

    # Target is a CHARACTER model
    target = Unit(MockDatasheet("Target", keywords=["CHARACTER"], model_count=1))
    target.deployed = True
    target.models[0].set_location(20.0, 10.0, 0.0, 0.0)

    p1.army.add_unit(attacker)
    p2.army.add_unit(target)
    game.map.units = [attacker, target]

    gun = Wargear({
        "name": "Test Gun",
        "type": "Ranged",
        "range": "24",
        "A": "1",
        "BS_WS": "2",
        "S": "10",
        "AP": "0",
        "D": "1",
        "description": "",
    })
    attacker.models[0].wargear.append(gun)

    attacker.possible_abilities.append(
        Ability(
            name="Skull Taker",
            faction_id="",
            description="Each time this model's unit destroys a CHARACTER model, you gain 1CP.",
            type="Datasheet",
            parameter="",
        )
    )
    attacker._invalidate_ability_cache()

    start_cp = p1.command_points
    profile = gun.profiles["default"]
    profile.attack(target, attacker.models[0], game_map=game.map)

    assert target.is_alive() is False
    assert p1.command_points == start_cp + 1


def test_the_great_wolf_gains_cp_on_destroying_enemy_unit(monkeypatch):
    # Rolls: hit=6, wound=6, save=1 (fail)
    _install_deterministic_rolls(monkeypatch, [6, 6, 1])

    bf = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    p1 = Player("P1", PlayerControl.LOCAL, Army("Army A", "Detachment A"))
    p2 = Player("P2", PlayerControl.REMOTE, Army("Army B", "Detachment B"))
    game.add_player(p1)
    game.add_player(p2)

    attacker = Unit(MockDatasheet("Attacker", model_count=1))
    attacker.deployed = True
    attacker.models[0].set_location(10.0, 10.0, 0.0, 0.0)

    target = Unit(MockDatasheet("Target", model_count=1))
    target.deployed = True
    target.models[0].set_location(20.0, 10.0, 0.0, 0.0)

    p1.army.add_unit(attacker)
    p2.army.add_unit(target)
    game.map.units = [attacker, target]

    gun = Wargear({
        "name": "Test Gun",
        "type": "Ranged",
        "range": "24",
        "A": "1",
        "BS_WS": "2",
        "S": "10",
        "AP": "0",
        "D": "1",
        "description": "",
    })
    attacker.models[0].wargear.append(gun)

    attacker.possible_abilities.append(
        Ability(
            name="The Great Wolf",
            faction_id="",
            description="Each time this model destroys an enemy unit, you gain 1CP.",
            type="Datasheet",
            parameter="",
        )
    )
    attacker._invalidate_ability_cache()

    start_cp = p1.command_points
    gun.profiles["default"].attack(target, attacker.models[0], game_map=game.map)
    assert target.is_alive() is False
    assert p1.command_points == start_cp + 1


def test_feared_interrogator_cp_requires_melee_kill(monkeypatch):
    # First sequence: melee kill grants CP. Rolls: hit=6, wound=6, save=1 (fail)
    _install_deterministic_rolls(monkeypatch, [6, 6, 1])

    bf = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    p1 = Player("P1", PlayerControl.LOCAL, Army("Army A", "Detachment A"))
    p2 = Player("P2", PlayerControl.REMOTE, Army("Army B", "Detachment B"))
    game.add_player(p1)
    game.add_player(p2)

    attacker = Unit(MockDatasheet("Attacker", model_count=1))
    attacker.deployed = True
    attacker.models[0].set_location(10.0, 10.0, 0.0, 0.0)

    target = Unit(MockDatasheet("Target", keywords=["CHARACTER"], model_count=1))
    target.deployed = True
    target.models[0].set_location(11.0, 10.0, 0.0, 0.0)

    p1.army.add_unit(attacker)
    p2.army.add_unit(target)
    game.map.units = [attacker, target]

    sword = Wargear({
        "name": "Test Sword",
        "type": "Melee",
        "range": "Melee",
        "A": "1",
        "BS_WS": "2",
        "S": "10",
        "AP": "0",
        "D": "1",
        "description": "",
    })
    gun = Wargear({
        "name": "Test Gun",
        "type": "Ranged",
        "range": "24",
        "A": "1",
        "BS_WS": "2",
        "S": "10",
        "AP": "0",
        "D": "1",
        "description": "",
    })
    attacker.models[0].wargear.extend([sword, gun])

    attacker.possible_abilities.append(
        Ability(
            name="Feared Interrogator",
            faction_id="",
            description="Each time this model destroys an enemy <span class=\"kwb\">CHARACTER</span> model with a melee attack, you gain 1CP.",
            type="Datasheet",
            parameter="",
        )
    )
    attacker._invalidate_ability_cache()

    start_cp = p1.command_points
    sword.profiles["default"].attack(target, attacker.models[0], game_map=game.map)
    assert target.is_alive() is False
    assert p1.command_points == start_cp + 1

    # Second sequence: ranged kill should NOT grant CP
    _install_deterministic_rolls(monkeypatch, [6, 6, 1])
    target2 = Unit(MockDatasheet("Target2", keywords=["CHARACTER"], model_count=1))
    target2.deployed = True
    target2.models[0].set_location(20.0, 10.0, 0.0, 0.0)
    p2.army.add_unit(target2)
    game.map.units = [attacker, target2]

    start_cp2 = p1.command_points
    gun.profiles["default"].attack(target2, attacker.models[0], game_map=game.map)
    assert target2.is_alive() is False
    assert p1.command_points == start_cp2


def test_champion_slayer_heals_on_destroying_character_or_monster_unit(monkeypatch):
    # Rolls: hit=6, wound=6, save=1 (fail), then heal roll D6=4
    _install_deterministic_rolls(monkeypatch, [6, 6, 1, 4])

    bf = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    p1 = Player("P1", PlayerControl.LOCAL, Army("Army A", "Detachment A"))
    p2 = Player("P2", PlayerControl.REMOTE, Army("Army B", "Detachment B"))
    game.add_player(p1)
    game.add_player(p2)

    attacker = Unit(MockDatasheet("Attacker", model_count=1, wounds="6"))
    attacker.deployed = True
    attacker.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    # Pre-damage the attacker so healing matters
    attacker.models[0].wounds = 2

    target = Unit(MockDatasheet("Target", keywords=["MONSTER"], model_count=1))
    target.deployed = True
    target.models[0].set_location(20.0, 10.0, 0.0, 0.0)

    p1.army.add_unit(attacker)
    p2.army.add_unit(target)
    game.map.units = [attacker, target]

    gun = Wargear({
        "name": "Test Gun",
        "type": "Ranged",
        "range": "24",
        "A": "1",
        "BS_WS": "2",
        "S": "10",
        "AP": "0",
        "D": "1",
        "description": "",
    })
    attacker.models[0].wargear.append(gun)

    attacker.possible_abilities.append(
        Ability(
            name="Champion Slayer",
            faction_id="",
            description="Each time this model destroys an enemy <span class=\"kwb\">CHARACTER</span> or <span class=\"kwb\">MONSTER</span> unit, this model regains up to D6 lost wounds.",
            type="Datasheet",
            parameter="",
        )
    )
    attacker._invalidate_ability_cache()

    gun.profiles["default"].attack(target, attacker.models[0], game_map=game.map)
    assert target.is_alive() is False
    # Heal roll was 4; starting wounds 2 -> 6 would cap at base (6)
    assert attacker.models[0].wounds == 6
