from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_REQUEST_DICE_ROLL
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.auto_resolve_dice_rolls = False
    return game, sm_player, enemy_player, sm_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _get_stasis_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("mortal_wounds_kind", "") or "").strip().lower() == "stasis_bomb":
            return request
    return None


def _target_option_id(request, target: Unit) -> str | None:
    target_id = str(get_entity_id(target) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == target_id:
            return str(getattr(option, "option_id", "") or "")
    return None


def _resolve_next_roll(game: Game, player: Player, *, fixed_dice: list[int]) -> None:
    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_REQUEST_DICE_ROLL
    ]
    assert pending
    request = pending[0]
    context = dict(getattr(request, "context", {}) or {})
    roll_id = context.get("roll_id")
    assert roll_id is not None
    state = game.roll_manager.get_roll(int(roll_id))
    state.spec["fixed_dice"] = list(fixed_dice or [])
    resolve_decision_command(game, request, request.options[0].option_id, player_id=player.id)


def test_ravenwing_dark_talon_stasis_bomb_applies_remain_stationary_restriction() -> None:
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    dark_talon = _actual_unit("Ravenwing Dark Talon", datasheet_id="000000240")
    target = _actual_unit("Outrider Squad", datasheet_id="000002712")
    sm_army.add_unit(dark_talon)
    enemy_army.add_unit(target)
    _deploy_unit(game, dark_talon, 10.0, 10.0)
    _deploy_unit(game, target, 15.0, 10.0)
    game.map.units = [dark_talon, target]
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    with patch("warhammer40k_ai.utility.calcs.get_enemy_units_moved_over", return_value=[target]):
        game._on_unit_move_ended_move_over_mortal_wounds(unit=dark_talon, action="move")

    request = _get_stasis_request(game)
    assert request is not None
    option_id = _target_option_id(request, target)
    assert option_id
    resolve_decision_command(game, request, option_id, player_id=sm_player.id)

    _resolve_next_roll(game, sm_player, fixed_dice=[2])
    _resolve_next_roll(game, sm_player, fixed_dice=[5])

    sr = dict(getattr(target, "special_rules", {}) or {})
    assert bool(sr.get("stasis_bomb_active", False)) is True
    assert str(sr.get("stasis_bomb_mode", "") or "") == "remain_stationary"

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    moved = target.move((18.0, 10.0, 0.0), game.map)
    assert moved is False
    assert bool(getattr(getattr(target, "round_state", None), "remained_stationary_this_round", False)) is True
