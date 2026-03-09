from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_MISSION
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import SetupPhase
from warhammer40k_ai.roster.player import Player, PlayerControl


def _build_game(*, authoritative: bool) -> Game:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.add_player(Player("Player 1", control=PlayerControl.LOCAL, army=None))
    game.add_player(Player("Player 2", control=PlayerControl.LOCAL, army=None))
    game.setup_phase = SetupPhase.MUSTER_ARMIES
    game.setup_complete = False
    game.is_authoritative = bool(authoritative)
    return game


def _pending_mission_requests(game: Game):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "")) == DECISION_CHOOSE_MISSION
    ]


def test_advancing_to_select_mission_phase_queues_authoritative_request() -> None:
    game = _build_game(authoritative=True)

    setup_complete = game._advance_setup_phase_impl()

    assert setup_complete is False
    assert game.setup_phase == SetupPhase.SELECT_MISSION_OBJECTIVES
    pending = _pending_mission_requests(game)
    assert len(pending) == 1
    assert pending[0].player_id == game.get_current_player().id


def test_request_mission_selection_is_idempotent_for_pending_request() -> None:
    game = _build_game(authoritative=True)

    first = game.request_mission_selection()
    second = game.request_mission_selection()

    assert second.decision_id == first.decision_id
    assert len(_pending_mission_requests(game)) == 1


def test_set_selected_mission_clears_pending_mission_requests() -> None:
    game = _build_game(authoritative=True)

    req = game.request_mission_selection()
    option = req.options[0]
    combo = dict(getattr(option, "payload", {})["combination"])
    layout = list(combo.get("layouts", []) or [1])[0]

    game.set_selected_mission(combo, layout)

    assert _pending_mission_requests(game) == []


def test_advancing_to_select_mission_phase_does_not_queue_on_non_authoritative_copy() -> None:
    game = _build_game(authoritative=False)

    setup_complete = game._advance_setup_phase_impl()

    assert setup_complete is False
    assert game.setup_phase == SetupPhase.SELECT_MISSION_OBJECTIVES
    assert _pending_mission_requests(game) == []
