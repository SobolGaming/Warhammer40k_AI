from __future__ import annotations

import json

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.replay_store import ReplayStoreReader, enable_decision_replay_recording
from warhammer40k_ai.roster.player import Player


def _build_game() -> tuple[Game, Player]:
    player = Player("P1")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    game.turn = 1
    return game, player


def _queue_confirmation(game: Game, player: Player) -> DecisionRequest:
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm?",
        player_id=player.id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
    )
    game.request_decision(request)
    return request


def _resolve_option(game: Game, request: DecisionRequest, *, option_index: int) -> None:
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=request.player_id,
        option_id=request.options[int(option_index)].option_id,
        payload={},
    )
    apply_result = game.resolve_decision(result)
    assert bool(getattr(apply_result, "ok", False))


def _canonical_snapshot(snapshot: dict) -> str:
    payload = dict(snapshot or {})
    payload.pop("events", None)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def test_replay_store_records_decisions_events_and_keyframes(tmp_path) -> None:
    game, player = _build_game()
    replay_path = tmp_path / "pvp_match.replay.sqlite3"
    enable_decision_replay_recording(
        game,
        replay_path=replay_path,
        keyframe_interval=1,
        session_id="session-1",
        label="PvP Match",
    )
    request = _queue_confirmation(game, player)
    _resolve_option(game, request, option_index=0)

    reader = ReplayStoreReader(replay_path)
    assert reader.decision_count() == 1
    assert reader.keyframe_count() >= 2

    steps = reader.list_steps(limit=10)
    assert len(steps) == 1
    step = steps[0]
    assert step.decision_idx == 1
    assert step.decision_type == DECISION_CONFIRM_YES_NO
    assert step.actor_player_id == str(player.id)
    assert step.controller_kind in ("human_local", "human_remote", "ai", "unknown")

    record = reader.get_decision_record(1)
    assert str(record.get("decision_id", "")) == str(request.decision_id)
    assert str(record.get("decision_type", "")) == DECISION_CONFIRM_YES_NO

    events = reader.get_events_for_decision(1)
    event_types = {str(entry.get("type", "") or "") for entry in events}
    assert "decision_requested" in event_types
    assert "decision_resolved" in event_types


def test_replay_store_reconstructs_state_at_decision_idx(tmp_path) -> None:
    game, player = _build_game()
    replay_path = tmp_path / "reconstruct.replay.sqlite3"
    enable_decision_replay_recording(
        game,
        replay_path=replay_path,
        keyframe_interval=25,
        session_id="session-2",
        label="Replay Reconstruction",
    )

    first = _queue_confirmation(game, player)
    _resolve_option(game, first, option_index=0)
    expected_after_first = game.save_snapshot()

    second = _queue_confirmation(game, player)
    _resolve_option(game, second, option_index=1)

    reader = ReplayStoreReader(replay_path)
    replayed_game = reader.reconstruct_game_at_decision(1, strict=True)
    replayed_snapshot = replayed_game.save_snapshot()

    assert _canonical_snapshot(replayed_snapshot) == _canonical_snapshot(expected_after_first)
