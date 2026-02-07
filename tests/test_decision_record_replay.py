from __future__ import annotations

import copy
import json

import pytest

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.replay import replay_decision_records
from warhammer40k_ai.roster.player import Player


def _build_game() -> tuple[Game, Player]:
    player = Player("P1")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
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


def test_replay_decision_records_round_trip_matches_end_state() -> None:
    game, player = _build_game()
    request = _queue_confirmation(game, player)
    snapshot_before = game.save_snapshot()
    event_id_before = int(snapshot_before["events"][-1]["event_id"]) if snapshot_before.get("events") else 0

    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={},
    )
    apply_result = game.resolve_decision(result)
    assert apply_result.ok is True
    expected_snapshot = game.save_snapshot()
    decision_record = copy.deepcopy(game.decision_record_store.records[-1])
    event_tail = game.event_log.serialize_events(since_event_id=event_id_before)

    replayed_game, replay_results = replay_decision_records(
        snapshot_before,
        [decision_record],
        strict=True,
        event_tail=event_tail,
    )
    assert replay_results[0].ok is True
    replayed_snapshot = replayed_game.save_snapshot()

    expected_comp = dict(expected_snapshot)
    replayed_comp = dict(replayed_snapshot)
    expected_comp.pop("events", None)
    replayed_comp.pop("events", None)
    expected_blob = json.dumps(expected_comp, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    replayed_blob = json.dumps(replayed_comp, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert replayed_blob == expected_blob


def test_replay_decision_records_strict_mode_rejects_candidate_mismatch() -> None:
    game, player = _build_game()
    request = _queue_confirmation(game, player)
    snapshot_before = game.save_snapshot()
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={},
    )
    apply_result = game.resolve_decision(result)
    assert apply_result.ok is True

    bad_record = copy.deepcopy(game.decision_record_store.records[-1])
    bad_record["candidates"][0]["action_id"] = "tampered-action-id"

    with pytest.raises(ValueError, match="strict replay mismatch"):
        replay_decision_records(snapshot_before, [bad_record], strict=True)
