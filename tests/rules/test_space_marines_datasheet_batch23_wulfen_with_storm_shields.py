from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_POST_FIGHT_SUPPRESSION_TARGET
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, datasheet_id: str | None = None) -> Unit:
    kwargs = {"faction_id": "SM"}
    if datasheet_id:
        kwargs["datasheet_id"] = datasheet_id
    unit = Unit(_WAHA.get_datasheet(name, **kwargs))
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
    game.turn = 1
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.battle_round_starting_player_index = 0
    return game, sm_player, enemy_player, sm_army, enemy_army


def _deploy(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(unit.models or [])):
        model.set_location(x + (idx * 0.5), y, 0.0, 0.0)


def _find_pending_post_fight_suppression_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == DECISION_CHOOSE_POST_FIGHT_SUPPRESSION_TARGET:
            return request
    return None


def test_wulfen_with_storm_shields_hammer_blow_suppresses_hit_vehicle_until_end_of_next_turn():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    attacker = _actual_unit("Wulfen with Storm Shields", datasheet_id="000004132")
    target_vehicle = _actual_unit("Dreadnought")
    target_infantry = _actual_unit("Intercessor Squad")

    sm_army.add_unit(attacker)
    enemy_army.add_unit(target_vehicle)
    enemy_army.add_unit(target_infantry)
    _deploy(attacker, 0.0, 0.0)
    _deploy(target_vehicle, 2.0, 0.0)
    _deploy(target_infantry, 4.0, 0.0)
    game.map.units = [attacker, target_vehicle, target_infantry]
    game.rebuild_entity_registry()

    game._on_fight_attacks_resolved_post_fight_suppression(
        unit=attacker,
        attacker_unit=attacker,
        hits_by_target={target_vehicle: 1, target_infantry: 1},
    )

    request = _find_pending_post_fight_suppression_request(game)
    assert request is not None
    assert str(request.player_id) == str(sm_player.id)
    assert len(list(request.options or [])) == 1
    target_option = request.options[0]
    assert str((target_option.payload or {}).get("unit_id") or "") == str(get_entity_id(target_vehicle) or "")

    result = resolve_decision_command(game, request, target_option.option_id, player_id=sm_player.id)
    assert bool(getattr(result, "ok", False)) is True

    sr = dict(getattr(target_vehicle, "special_rules", {}) or {})
    assert bool(sr.get("post_fight_suppressed_active"))
    assert str(sr.get("post_fight_suppressed_expires_turn_owner", "") or "") == str(enemy_player.id)
    assert int(sr.get("post_fight_suppressed_expires_turn", 0) or 0) == 1

    target_model = target_vehicle.models[0]
    ranged_profile = next(
        iter(next(wg for wg in list(target_model.wargear or []) if not wg.is_melee()).profiles.values())
    )
    melee_profile = next(
        iter(next(wg for wg in list(target_model.wargear or []) if wg.is_melee()).profiles.values())
    )

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[3]):
        ranged_hit = ranged_profile._hit_target_with_tracking(
            attacker,
            target_model,
            {"attacker_model": target_model, "target_unit": attacker, "_aura_attack_mods": SimpleNamespace()},
        )
    assert bool(ranged_hit.get("hit", False)) is False
    assert any("Suppressed" in str(entry) for entry in list(ranged_hit.get("modifiers", []) or []))

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[3]):
        melee_hit = melee_profile._hit_target_with_tracking(
            attacker,
            target_model,
            {"attacker_model": target_model, "target_unit": attacker, "_aura_attack_mods": SimpleNamespace()},
        )
    assert bool(melee_hit.get("hit", False)) is False
    assert any("Suppressed" in str(entry) for entry in list(melee_hit.get("modifiers", []) or []))

    game._on_phase_end_post_fight_suppression_cleanup(player=sm_player, phase=game.phase)
    assert bool(target_vehicle.special_rules.get("post_fight_suppressed_active"))

    game.current_player_index = 1
    game._on_phase_end_post_fight_suppression_cleanup(player=enemy_player, phase=game.phase)
    assert not bool(target_vehicle.special_rules.get("post_fight_suppressed_active"))


def test_wulfen_with_storm_shields_hammer_blow_can_trigger_in_opponents_turn():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    attacker = _actual_unit("Wulfen with Storm Shields", datasheet_id="000004132")
    target_vehicle = _actual_unit("Dreadnought")

    sm_army.add_unit(attacker)
    enemy_army.add_unit(target_vehicle)
    _deploy(attacker, 0.0, 0.0)
    _deploy(target_vehicle, 2.0, 0.0)
    game.map.units = [attacker, target_vehicle]
    game.rebuild_entity_registry()

    game.current_player_index = 1

    game._on_fight_attacks_resolved_post_fight_suppression(
        unit=attacker,
        attacker_unit=attacker,
        hits_by_target={target_vehicle: 1},
    )

    request = _find_pending_post_fight_suppression_request(game)
    assert request is not None
    assert str(request.player_id) == str(sm_player.id)
    assert int((request.context or {}).get("expires_turn", 0) or 0) == 2
    assert str((request.context or {}).get("expires_turn_owner", "") or "") == str(sm_player.id)

    target_option = request.options[0]
    result = resolve_decision_command(game, request, target_option.option_id, player_id=sm_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert bool(target_vehicle.special_rules.get("post_fight_suppressed_active"))

    game._on_phase_end_post_fight_suppression_cleanup(player=enemy_player, phase=game.phase)
    assert bool(target_vehicle.special_rules.get("post_fight_suppressed_active"))

    game.turn = 2
    game.current_player_index = 0
    game._on_phase_end_post_fight_suppression_cleanup(player=sm_player, phase=game.phase)
    assert not bool(target_vehicle.special_rules.get("post_fight_suppressed_active"))
