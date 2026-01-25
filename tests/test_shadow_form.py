import pytest

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize, BattleRoundPhases
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers
from warhammer40k_ai.rules.shadow_form import (
    KEY_WREATHED,
    KEY_SHADOW_LORD,
    KEY_PALL,
    set_active_shadow_form,
)


class MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None, model_count=1, wounds="6", leadership="7"):
        self.name = name
        self.faction_data = {"name": "Chaos Daemons"}
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [{
            "M": "6", "T": "4", "Sv": "3", "W": str(wounds),
            "Ld": str(leadership), "OC": "1",
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


class _StubRng:
    def __init__(self, values):
        self._it = iter(values)

    def randint(self, _a, _b):
        return next(self._it)


def _setup_game():
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    p1 = Player("P1", PlayerControl.LOCAL, None)
    p2 = Player("P2", PlayerControl.REMOTE, None)
    game.add_player(p1)
    game.add_player(p2)

    a1 = Army("Chaos Daemons", "Detachment A")
    a2 = Army("Enemy", "Other")
    p1.set_army(a1)
    p2.set_army(a2)
    return game, a1, a2


def _make_profile():
    return WargearProfile(
        "Test Gun",
        {
            "range": "36",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "Indirect Fire",
        },
    )


def test_wreathed_in_shadows_blocks_targets_beyond_18():
    game, a1, a2 = _setup_game()
    game.turn = 1

    belakor = Unit(MockDatasheet(
        "Be'lakor",
        abilities=["Shadow Form", "Wreathed in Shadows (Aura, Psychic)"],
        keywords=["LEGIONES DAEMONICA"],
        wounds="10",
    ))
    target = Unit(MockDatasheet("Daemon Target", keywords=["LEGIONES DAEMONICA"]))
    shooter = Unit(MockDatasheet("Shooter"))

    a1.add_unit(belakor)
    a1.add_unit(target)
    a2.add_unit(shooter)

    belakor.deployed = True
    target.deployed = True
    shooter.deployed = True

    belakor.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(0.0, 4.0, 0.0, 0.0)
    shooter.models[0].set_location(0.0, 30.0, 0.0, 0.0)

    game.map.units = [belakor, target, shooter]

    set_active_shadow_form(belakor, KEY_WREATHED, battle_round=1)

    profile = _make_profile()
    assert shooter._can_model_shoot_weapon_at_target(shooter.models[0], profile, target, game.map) is False

    shooter.models[0].set_location(0.0, 15.0, 0.0, 0.0)
    assert shooter._can_model_shoot_weapon_at_target(shooter.models[0], profile, target, game.map) is True


def test_shadow_lord_grants_reroll_hit_ones():
    game, a1, a2 = _setup_game()
    game.turn = 1

    belakor = Unit(MockDatasheet(
        "Be'lakor",
        abilities=["Shadow Form", "Shadow Lord (Aura, Psychic)"],
        keywords=["LEGIONES DAEMONICA"],
        wounds="10",
    ))
    attacker = Unit(MockDatasheet("Daemon Attacker", keywords=["LEGIONES DAEMONICA"]))
    enemy = Unit(MockDatasheet("Enemy"))

    a1.add_unit(belakor)
    a1.add_unit(attacker)
    a2.add_unit(enemy)

    belakor.deployed = True
    attacker.deployed = True
    enemy.deployed = True

    belakor.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    attacker.models[0].set_location(0.0, 5.0, 0.0, 0.0)
    enemy.models[0].set_location(30.0, 0.0, 0.0, 0.0)

    game.map.units = [belakor, attacker, enemy]

    set_active_shadow_form(belakor, KEY_SHADOW_LORD, battle_round=1)

    profile = _make_profile()
    mods = get_aura_attack_modifiers(attacker, enemy, profile, game_map=game.map)
    assert mods.reroll_hit_ones is True


def test_pall_of_despair_heals_on_failed_battle_shock(monkeypatch):
    game, a1, a2 = _setup_game()
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 1

    belakor = Unit(MockDatasheet(
        "Be'lakor",
        abilities=["Shadow Form", "Pall of Despair (Aura, Psychic)"],
        keywords=["LEGIONES DAEMONICA"],
        wounds="10",
    ))
    enemy = Unit(MockDatasheet("Enemy", wounds="6"))

    a1.add_unit(belakor)
    a2.add_unit(enemy)

    belakor.deployed = True
    enemy.deployed = True

    belakor.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(0.0, 8.0, 0.0, 0.0)

    belakor.models[0].wounds = 8
    enemy.models[0].wounds = 4

    game.map.units = [belakor, enemy]

    set_active_shadow_form(belakor, KEY_PALL, battle_round=1)

    import warhammer40k_ai.rules.shadow_form as shadow_form_mod

    game.random_source = _StubRng([6, 6])
    monkeypatch.setattr(shadow_form_mod, "get_roll", lambda _expr: 2)

    enemy.take_battle_shock_test(game.turn)

    assert belakor.models[0].wounds == 10
