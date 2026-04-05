from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


def _build_game() -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    lov_army = Army("Leagues of Votann", "Mercenary Oathband")
    lov_army.faction_id = "LOV"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    p1 = Player("Votann", control=PlayerControl.REMOTE, army=lov_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    return game, lov_army, enemy_army, p1, p2


def _yes_option_id(request) -> str:
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if bool(payload.get("choice")):
            return str(getattr(opt, "option_id", "") or "")
    return ""


def test_ruthless_reinvestment_disables_auto_threshold_mode_switch():
    game, army, _enemy_army, player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.turn = 2

    pe = getattr(army, "prioritised_efficiency", None)
    assert pe is not None
    assert bool(pe.is_hostile_acquisition()) is True
    pe.add_yield_points(8, game=game)

    changed = bool(pe.update_mode_for_player(game, player))
    assert changed is False
    assert bool(pe.is_hostile_acquisition()) is True


def test_ruthless_reinvestment_command_phase_spend_toggles_mode_and_costs_three_yp():
    game, army, _enemy_army, player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.turn = 2

    pe = getattr(army, "prioritised_efficiency", None)
    assert pe is not None
    pe.add_yield_points(3, game=game)

    game._on_phase_end_ruthless_reinvestment(player=player, phase=BattleRoundPhases.COMMAND_PHASE)
    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "")) == DECISION_CONFIRM_YES_NO
        and str((getattr(req, "context", {}) or {}).get("ability", "")) == "ruthless_reinvestment"
    ]
    assert len(pending) == 1
    request = pending[0]
    yes_option_id = _yes_option_id(request)
    assert yes_option_id

    resolve_decision_command(game, request, yes_option_id, player_id=player.id)

    assert int(getattr(pe, "yield_points", 0) or 0) == 0
    assert bool(pe.is_fortify_takeover()) is True


def test_ruthless_reinvestment_can_only_toggle_once_per_command_phase():
    game, army, _enemy_army, player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.turn = 2

    pe = getattr(army, "prioritised_efficiency", None)
    assert pe is not None
    pe.add_yield_points(6, game=game)

    game._on_phase_end_ruthless_reinvestment(player=player, phase=BattleRoundPhases.COMMAND_PHASE)
    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "")) == DECISION_CONFIRM_YES_NO
        and str((getattr(req, "context", {}) or {}).get("ability", "")) == "ruthless_reinvestment"
    ]
    assert len(pending) == 1
    request = pending[0]
    yes_option_id = _yes_option_id(request)
    assert yes_option_id
    resolve_decision_command(game, request, yes_option_id, player_id=player.id)
    assert bool(pe.is_fortify_takeover()) is True

    game._on_phase_end_ruthless_reinvestment(player=player, phase=BattleRoundPhases.COMMAND_PHASE)
    pending_again = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "")) == DECISION_CONFIRM_YES_NO
        and str((getattr(req, "context", {}) or {}).get("ability", "")) == "ruthless_reinvestment"
    ]
    assert pending_again == []


def test_ruthless_reinvestment_can_toggle_again_on_later_turn():
    game, army, _enemy_army, player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.turn = 2

    pe = getattr(army, "prioritised_efficiency", None)
    assert pe is not None
    pe.add_yield_points(6, game=game)

    game._on_phase_end_ruthless_reinvestment(player=player, phase=BattleRoundPhases.COMMAND_PHASE)
    first_req = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "")) == DECISION_CONFIRM_YES_NO
        and str((getattr(req, "context", {}) or {}).get("ability", "")) == "ruthless_reinvestment"
    ][0]
    resolve_decision_command(game, first_req, _yes_option_id(first_req), player_id=player.id)
    assert bool(pe.is_fortify_takeover()) is True

    game.turn = 3
    pe.add_yield_points(3, game=game)
    game._on_phase_end_ruthless_reinvestment(player=player, phase=BattleRoundPhases.COMMAND_PHASE)
    second_req = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "")) == DECISION_CONFIRM_YES_NO
        and str((getattr(req, "context", {}) or {}).get("ability", "")) == "ruthless_reinvestment"
    ]
    assert len(second_req) == 1
    resolve_decision_command(game, second_req[0], _yes_option_id(second_req[0]), player_id=player.id)
    assert bool(pe.is_hostile_acquisition()) is True
