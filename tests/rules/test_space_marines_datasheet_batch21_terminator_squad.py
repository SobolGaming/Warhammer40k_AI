from __future__ import annotations

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, sm_army, enemy_army


def test_fury_of_the_first_adds_hit_bonus_vs_oath_target() -> None:
    _game, sm_army, enemy_army = _build_game()
    terminators = _actual_unit("Terminator Squad", datasheet_id="000001183")
    oath_target = _actual_unit("Scout Squad", datasheet_id="000001160")
    other_target = _actual_unit("Outrider Squad", datasheet_id="000002712")
    sm_army.add_unit(terminators)
    enemy_army.add_unit(oath_target)
    enemy_army.add_unit(other_target)
    sm_army.oath_of_moment.set_target(oath_target)

    ranged_mods = terminators.get_unit_hit_reroll_modifiers("ranged", target=oath_target)
    melee_mods = terminators.get_unit_hit_reroll_modifiers("melee", target=oath_target)
    other_mods = terminators.get_unit_hit_reroll_modifiers("ranged", target=other_target)

    assert int(ranged_mods.get("hit", 0) or 0) == 1
    assert int(melee_mods.get("hit", 0) or 0) == 1
    assert any("Fury of the First" in reason for reason in list(ranged_mods.get("hit_reasons", ()) or ()))
    assert any("Fury of the First" in reason for reason in list(melee_mods.get("hit_reasons", ()) or ()))
    assert int(other_mods.get("hit", 0) or 0) == 0
    assert not any("Fury of the First" in reason for reason in list(other_mods.get("hit_reasons", ()) or ()))
