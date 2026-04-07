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
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, sm_army, enemy_army


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    for unit in (leader, bodyguard):
        invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()
        else:
            unit._ability_cache = {}


def test_wolf_guard_battle_leader_tempered_ferocity_grants_hit_reroll_ones_only_within_six_while_leading() -> None:
    game, sm_army, enemy_army = _build_game()

    bodyguard = _actual_unit("Intercessor Squad", datasheet_id="000001157")
    leader = _actual_unit("Wolf Guard Battle Leader", datasheet_id="000004130")
    enemy_near = _actual_unit("Intercessor Squad", datasheet_id="000001157")
    enemy_far = _actual_unit("Intercessor Squad", datasheet_id="000001157")

    sm_army.add_unit(bodyguard)
    sm_army.add_unit(leader)
    enemy_army.add_unit(enemy_near)
    enemy_army.add_unit(enemy_far)

    _attach_leader(bodyguard, leader)
    _set_unit_position(bodyguard, 0.0, 0.0)
    _set_unit_position(leader, 0.0, 0.0)
    _set_unit_position(enemy_near, 5.5, 0.0)
    _set_unit_position(enemy_far, 7.5, 0.0)

    game.map.units = [bodyguard, leader, enemy_near, enemy_far]
    game.rebuild_entity_registry()

    near_mods = bodyguard.get_leading_attack_roll_modifiers("melee", target=enemy_near)
    far_mods = bodyguard.get_leading_attack_roll_modifiers("melee", target=enemy_far)

    assert 1 in tuple(near_mods.get("reroll_hit_values", ()) or ())
    assert any("Tempered Ferocity" in str(reason) for reason in list(near_mods.get("reroll_hit_reasons", ()) or ()))
    assert any("within 6.0" in str(reason) for reason in list(near_mods.get("reroll_hit_reasons", ()) or ()))
    assert 1 not in tuple(far_mods.get("reroll_hit_values", ()) or ())
