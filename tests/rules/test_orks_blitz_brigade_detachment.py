from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        slug = str(name or "unit").lower().replace(" ", "-")
        self.id = f"mock-{slug}"
        self.name = name
        self.faction_data = {"name": "Orks"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ORKS"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "5",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game(*, detachment: str = "Blitz Brigade"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
    ork_army = Army.with_detachment("Orks", detachment)
    ork_army.faction_id = "ORK"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"
    ork_player = Player("Ork Player", control=PlayerControl.REMOTE, army=ork_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ork_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, ork_army, enemy_army


def test_eager_for_the_fight_grants_turn_long_advance_and_charge_rerolls_on_disembark():
    game, army, enemy_army = _build_game()
    boyz = _unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    trukk = _unit("Trukk", keywords=["TRANSPORT", "VEHICLE"], faction_keywords=["ORKS"])
    enemy = _unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    army.add_unit(boyz)
    army.add_unit(trukk)
    enemy_army.add_unit(enemy)
    game.rebuild_entity_registry()

    assert army.orks_detachments.apply_blitz_brigade_eager_for_the_fight_on_disembark(
        boyz,
        transport_unit=trukk,
        game=game,
        current_turn=1,
    )

    assert boyz.can_reroll_advance_roll() is True
    assert boyz.can_reroll_charge_roll(target_unit=enemy, game=game) is True
    effect_ids = {
        str(entry.get("id", "") or "")
        for entry in list(boyz.special_rules.get("orks_temp_effects", []) or [])
    }
    assert "detachment:blitz_brigade:eager_for_the_fight:advance" in effect_ids
    assert "detachment:blitz_brigade:eager_for_the_fight:charge" in effect_ids


def test_eager_for_the_fight_requires_blitz_brigade_and_a_friendly_transport():
    game, army, _enemy_army = _build_game(detachment="War Horde")
    boyz = _unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    trukk = _unit("Trukk", keywords=["TRANSPORT", "VEHICLE"], faction_keywords=["ORKS"])
    wagon = _unit("Battlewagon", keywords=["VEHICLE"], faction_keywords=["ORKS"])
    army.add_unit(boyz)
    army.add_unit(trukk)
    army.add_unit(wagon)
    game.rebuild_entity_registry()

    assert army.orks_detachments.apply_blitz_brigade_eager_for_the_fight_on_disembark(
        boyz,
        transport_unit=trukk,
        game=game,
        current_turn=1,
    ) is False
    assert boyz.can_reroll_advance_roll() is False

    blitz_game, blitz_army, _ = _build_game()
    blitz_boyz = _unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    blitz_wagon = _unit("Battlewagon", keywords=["VEHICLE"], faction_keywords=["ORKS"])
    blitz_army.add_unit(blitz_boyz)
    blitz_army.add_unit(blitz_wagon)
    blitz_game.rebuild_entity_registry()

    assert blitz_army.orks_detachments.apply_blitz_brigade_eager_for_the_fight_on_disembark(
        blitz_boyz,
        transport_unit=blitz_wagon,
        game=blitz_game,
        current_turn=1,
    ) is False
    assert blitz_boyz.can_reroll_advance_roll() is False


def test_eager_for_the_fight_disembark_hook_applies_existing_reroll_path():
    game, army, enemy_army = _build_game()
    boyz = _unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    trukk = _unit("Trukk", keywords=["TRANSPORT", "VEHICLE"], faction_keywords=["ORKS"])
    enemy = _unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    army.add_unit(boyz)
    army.add_unit(trukk)
    enemy_army.add_unit(enemy)
    game.rebuild_entity_registry()

    boyz._apply_blitz_brigade_eager_for_the_fight_disembark_effect(
        transport_unit=trukk,
        game=game,
        current_turn=1,
    )

    assert boyz.can_reroll_advance_roll() is True
    assert boyz.can_reroll_charge_roll(target_unit=enemy, game=game) is True
