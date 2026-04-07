import pytest

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class MockDatasheet:
    def __init__(self, name: str, *, movement=6, model_count=1, base_size="32mm", save="4", wounds="1"):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
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
    import warhammer40k_ai.units.unit as unit_mod
    import warhammer40k_ai.units.wargear as wargear_mod

    it = iter(rolls)

    def rigged(_expr: str):
        try:
            return next(it)
        except StopIteration:
            return 6

    monkeypatch.setattr(dice_mod, "get_roll", rigged)
    monkeypatch.setattr(unit_mod, "get_roll", rigged)
    monkeypatch.setattr(wargear_mod, "get_roll", rigged)


def _make_game():
    bf = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    p1 = Player("P1", PlayerControl.LOCAL, Army.with_detachment("Army A", "Detachment A"))
    p2 = Player("P2", PlayerControl.REMOTE, Army.with_detachment("Army B", "Detachment B"))
    game.add_player(p1)
    game.add_player(p2)
    return game, p1, p2


def _add_simple_gun(unit):
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
    unit.models[0].wargear.append(gun)
    return gun


def test_phase_end_leadership_cp_gain_shooting_pass(monkeypatch):
    _install_deterministic_rolls(monkeypatch, [6, 6, 1, 6])

    game, p1, p2 = _make_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    attacker = Unit(MockDatasheet("Attacker", model_count=1))
    attacker.deployed = True
    attacker.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    _add_simple_gun(attacker)

    target = Unit(MockDatasheet("Target", model_count=1))
    target.deployed = True
    target.models[0].set_location(20.0, 10.0, 0.0, 0.0)

    p1.army.add_unit(attacker)
    p2.army.add_unit(target)
    game.map.units = [attacker, target]

    attacker.possible_abilities.append(
        Ability(
            name="Icon of Excess",
            faction_id="",
            description=(
                "At the end of your Shooting phase or the Fight phase, if the bearer's unit destroyed one or more "
                "enemy units that phase, the bearer's unit takes a Leadership test. If that test is passed, you gain 1CP."
            ),
            type="Datasheet",
            parameter="",
        )
    )
    attacker._invalidate_ability_cache()

    start_cp = p1.command_points
    profile = attacker.models[0].wargear[0].profiles["default"]
    profile.attack(target, attacker.models[0], game_map=game.map)

    assert target.is_alive() is False
    game.event_system.publish("phase_end", player=p1, phase=game.phase)
    assert p1.command_points == start_cp + 1


def test_phase_end_leadership_cp_gain_fight_fail(monkeypatch):
    _install_deterministic_rolls(monkeypatch, [6, 6, 1, 12])

    game, p1, p2 = _make_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE

    attacker = Unit(MockDatasheet("Attacker", model_count=1))
    attacker.deployed = True
    attacker.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    _add_simple_gun(attacker)

    target = Unit(MockDatasheet("Target", model_count=1))
    target.deployed = True
    target.models[0].set_location(20.0, 10.0, 0.0, 0.0)

    p1.army.add_unit(attacker)
    p2.army.add_unit(target)
    game.map.units = [attacker, target]

    attacker.possible_abilities.append(
        Ability(
            name="Icon of Excess",
            faction_id="",
            description=(
                "At the end of your Shooting phase or the Fight phase, if the bearer's unit destroyed one or more "
                "enemy units that phase, the bearer's unit takes a Leadership test. If that test is passed, you gain 1CP."
            ),
            type="Datasheet",
            parameter="",
        )
    )
    attacker._invalidate_ability_cache()

    start_cp = p1.command_points
    profile = attacker.models[0].wargear[0].profiles["default"]
    profile.attack(target, attacker.models[0], game_map=game.map)

    assert target.is_alive() is False
    game.event_system.publish("phase_end", player=p1, phase=game.phase)
    assert p1.command_points == start_cp


def test_command_phase_end_leadership_cp_gain_pass(monkeypatch):
    _install_deterministic_rolls(monkeypatch, [4])

    game, p1, _p2 = _make_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE

    unit = Unit(MockDatasheet("Kairos", model_count=1))
    unit.deployed = True
    unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    p1.army.add_unit(unit)
    game.map.units = [unit]

    unit.possible_abilities.append(
        Ability(
            name="One Head Looks Forward",
            faction_id="",
            description=(
                "At the end of your Command phase, if this model is on the battlefield, "
                "take a Leadership test for this model; if that test is passed, you gain 1CP."
            ),
            type="Datasheet",
            parameter="",
        )
    )
    unit._invalidate_ability_cache()

    start_cp = p1.command_points
    game.event_system.publish("phase_end", player=p1, phase=game.phase)
    assert p1.command_points == start_cp + 1


def test_command_phase_end_leadership_cp_gain_fail(monkeypatch):
    _install_deterministic_rolls(monkeypatch, [12])

    game, p1, _p2 = _make_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE

    unit = Unit(MockDatasheet("Kairos", model_count=1))
    unit.deployed = True
    unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    p1.army.add_unit(unit)
    game.map.units = [unit]

    unit.possible_abilities.append(
        Ability(
            name="One Head Looks Forward",
            faction_id="",
            description=(
                "At the end of your Command phase, if this model is on the battlefield, "
                "take a Leadership test for this model; if that test is passed, you gain 1CP."
            ),
            type="Datasheet",
            parameter="",
        )
    )
    unit._invalidate_ability_cache()

    start_cp = p1.command_points
    game.event_system.publish("phase_end", player=p1, phase=game.phase)
    assert p1.command_points == start_cp


def test_command_phase_end_leadership_cp_gain_not_on_battlefield(monkeypatch):
    _install_deterministic_rolls(monkeypatch, [4])

    game, p1, _p2 = _make_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE

    unit = Unit(MockDatasheet("Kairos", model_count=1))
    unit.deployed = False
    unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    p1.army.add_unit(unit)
    game.map.units = [unit]

    unit.possible_abilities.append(
        Ability(
            name="One Head Looks Forward",
            faction_id="",
            description=(
                "At the end of your Command phase, if this model is on the battlefield, "
                "take a Leadership test for this model; if that test is passed, you gain 1CP."
            ),
            type="Datasheet",
            parameter="",
        )
    )
    unit._invalidate_ability_cache()

    start_cp = p1.command_points
    game.event_system.publish("phase_end", player=p1, phase=game.phase)
    assert p1.command_points == start_cp
