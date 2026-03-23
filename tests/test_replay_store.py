from __future__ import annotations

import json
from types import MethodType

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.dice_rolls import DiceRollState
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.replay_store import (
    REPLAY_RECORDING_GROUP,
    ReplayStoreReader,
    _pack_json,
    _unpack_json,
    enable_decision_replay_recording,
)
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

    request_payload = reader.get_request_payload(1)
    assert str(request_payload.get("decision_id", "")) == str(request.decision_id)
    assert str(request_payload.get("prompt", "")) == "Confirm?"
    assert [str(option.get("label", "") or "") for option in list(request_payload.get("options", []) or [])] == [
        "Yes",
        "No",
    ]

    events = reader.get_events_for_decision(1)
    event_types = {str(entry.get("type", "") or "") for entry in events}
    assert "decision_requested" in event_types
    assert "decision_resolved" in event_types


def test_pack_json_normalizes_dice_roll_state_objects() -> None:
    state = DiceRollState(
        roll_id=7,
        player_id="player-1",
        spec={"reason": "advance_roll"},
        status="resolved",
        total=6,
        final=True,
    )

    unpacked = dict(_unpack_json(_pack_json({"roll_state": state})))

    assert dict(unpacked["roll_state"]) == {
        "created_at": float(state.created_at),
        "dice": [],
        "final": True,
        "per_die_success": {},
        "player_id": "player-1",
        "reroll_history": [],
        "reroll_options": [],
        "resolved_at": None,
        "roll_id": 7,
        "sorted_ids": [],
        "spec": {"reason": "advance_roll"},
        "status": "resolved",
        "sum_success": None,
        "total": 6,
    }


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


def test_replay_store_keyframe_is_captured_after_followups(tmp_path) -> None:
    game, player = _build_game()
    replay_path = tmp_path / "post_settled.replay.sqlite3"
    starting_turn = int(game.turn)

    def _apply_post_followup_side_effect(self, request, result) -> None:
        self.turn = int(self.turn) + 1

    game._maybe_apply_optional_ability_confirmation = MethodType(_apply_post_followup_side_effect, game)
    enable_decision_replay_recording(
        game,
        replay_path=replay_path,
        keyframe_interval=1,
        session_id="session-3",
        label="Post Settled Keyframe",
    )
    request = _queue_confirmation(game, player)
    _resolve_option(game, request, option_index=0)
    expected_snapshot = game.save_snapshot()

    reader = ReplayStoreReader(replay_path)
    replayed_game = reader.reconstruct_game_at_decision(1, strict=True)
    replayed_snapshot = replayed_game.save_snapshot()

    assert _canonical_snapshot(replayed_snapshot) == _canonical_snapshot(expected_snapshot)
    assert int(replayed_game.turn) == starting_turn + 1


def test_enable_decision_replay_recording_is_idempotent(tmp_path) -> None:
    game, player = _build_game()
    replay_path = tmp_path / "idempotent.replay.sqlite3"

    enable_decision_replay_recording(game, replay_path=replay_path, session_id="session-4")
    enable_decision_replay_recording(game, replay_path=replay_path, session_id="session-4")

    listeners = [
        group
        for _callback, group in list(getattr(game.event_system, "subscribers", {}).get("decision_settled", []))
        if str(group) == REPLAY_RECORDING_GROUP
    ]
    assert len(listeners) == 1

    request = _queue_confirmation(game, player)
    _resolve_option(game, request, option_index=0)

    reader = ReplayStoreReader(replay_path)
    assert reader.decision_count() == 1
