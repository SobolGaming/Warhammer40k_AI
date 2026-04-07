from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 1
    return game, sm_army, enemy_army, sm_player


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for index, model in enumerate(list(unit.models or [])):
        model.set_location(x + (index * 0.1), y, 0.0, 0.0)


def _use_option_id(request) -> str:
    for option in list(request.options or []):
        payload = getattr(option, "payload", {}) or {}
        if bool(payload.get("choice", False)):
            return option.option_id
    raise AssertionError("Use option not found")


def test_exploit_their_cowardice_queues_reactive_move_after_enemy_falls_back() -> None:
    game, sm_army, enemy_army, sm_player = _build_game()
    sword_brethren = _actual_unit("Sword Brethren Squad")
    enemy = _actual_unit("Scout Squad")
    sm_army.add_unit(sword_brethren)
    enemy_army.add_unit(enemy)

    _set_unit_position(sword_brethren, 0.0, 0.0)
    _set_unit_position(enemy, 1.0, 0.0)
    game.map.units = [sword_brethren, enemy]
    game.rebuild_entity_registry()

    rule = sword_brethren.get_enemy_fall_back_end_normal_move_rule()
    assert isinstance(rule, dict)
    assert str(rule.get("source", "") or "") == "Exploit Their Cowardice"
    assert bool(game.map.is_within_engagement_range(sword_brethren, enemy)) is True

    game.event_system.publish("unit_move_started", unit=enemy, action="fall_back")
    _set_unit_position(enemy, 8.0, 0.0)
    game.event_system.publish("unit_move_ended", unit=enemy, action="fall_back")

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    request = pending[0]
    assert request.decision_type == DECISION_CONFIRM_YES_NO
    assert request.player_id == sm_player.id
    context = dict(getattr(request, "context", {}) or {})
    assert str(context.get("reactive_move_kind", "") or "") == "enemy_fall_back_end_normal_move"
    assert str(context.get("reactive_move_unit_id", "") or "") == str(get_entity_id(sword_brethren))
    assert str(context.get("reactive_move_moving_unit_id", "") or "") == str(get_entity_id(enemy))
    assert str(context.get("reactive_move_source", "") or "") == "Exploit Their Cowardice"
    assert int(context.get("max_distance", 0) or 0) > 0

    resolve_decision_command(game, request, _use_option_id(request), player_id=sm_player.id)

    follow_up = list(game.decision_queue.list() or [])
    assert len(follow_up) == 1
    move_request = follow_up[0]
    assert move_request.decision_type == DECISION_MOVE_UNIT
    move_context = dict(getattr(move_request, "context", {}) or {})
    assert str(move_context.get("reactive_move_kind", "") or "") == "enemy_fall_back_end_normal_move"
    assert str(move_context.get("reactive_move_unit_id", "") or "") == str(get_entity_id(sword_brethren))
    assert int(move_context.get("max_distance", 0) or 0) == int(context.get("max_distance", 0) or 0)


def test_exploit_their_cowardice_does_not_trigger_if_unit_remains_engaged() -> None:
    game, sm_army, enemy_army, _sm_player = _build_game()
    sword_brethren = _actual_unit("Sword Brethren Squad")
    enemy = _actual_unit("Scout Squad")
    blocker = _actual_unit("Scout Squad")
    sm_army.add_unit(sword_brethren)
    enemy_army.add_unit(enemy)
    enemy_army.add_unit(blocker)

    _set_unit_position(sword_brethren, 0.0, 0.0)
    _set_unit_position(enemy, 1.0, 0.0)
    _set_unit_position(blocker, -1.0, 0.0)
    game.map.units = [sword_brethren, enemy, blocker]
    game.rebuild_entity_registry()

    assert bool(game.map.is_within_engagement_range(sword_brethren, enemy)) is True
    assert bool(game.map.is_within_engagement_range(sword_brethren, blocker)) is True

    game.event_system.publish("unit_move_started", unit=enemy, action="fall_back")
    _set_unit_position(enemy, 8.0, 0.0)
    game.event_system.publish("unit_move_ended", unit=enemy, action="fall_back")

    assert list(game.decision_queue.list() or []) == []
