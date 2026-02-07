from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.player import Player


def _build_game() -> tuple[Game, Player]:
    player = Player("P1")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    return game, player


def test_decision_record_valid_choice_has_chosen_action_in_candidates() -> None:
    game, player = _build_game()
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm action?",
        player_id=player.id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
    )
    game.request_decision(request)
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={},
    )
    apply_result = game.resolve_decision(result)
    assert apply_result.ok is True

    record = game.decision_record_store.records[-1]
    action_ids = {str(c["action_id"]) for c in record["candidates"]}
    assert record["valid"] is True
    assert record["chosen_action_id"] in action_ids


def test_decision_record_invalid_attempt_logs_rejection() -> None:
    game, player = _build_game()
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm action?",
        player_id=player.id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
    )
    game.request_decision(request)
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id="not-an-option",
        payload={"foo": "bar"},
    )
    apply_result = game.resolve_decision(result)
    assert apply_result.ok is False

    record = game.decision_record_store.records[-1]
    assert record["valid"] is False
    assert record["invalid_attempt"]["params"] == {"foo": "bar"}
    assert str(record["rejection_reason"])


def test_decision_record_human_action_candidate_injection_for_move_payload() -> None:
    game, player = _build_game()
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Move unit",
        player_id=player.id,
        options=[
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": "unit-1", "movement_type": "move", "action": "confirm"},
            ),
            DecisionOption.create(
                "Skip",
                payload={"unit_id": "unit-1", "movement_type": "move", "action": "skip"},
            ),
        ],
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={
            "model_positions": [
                {
                    "model_id": "model-1",
                    "position": [10.0, 8.0, 0.0],
                    "facing": 0.0,
                }
            ]
        },
    )
    record = game.decision_record_store.record_resolution(
        request,
        result,
        ok=True,
        errors=(),
        value=None,
        wall_clock_ms=1,
    )
    action_ids = {str(c["action_id"]) for c in record["candidates"]}
    injected = [c for c in record["candidates"] if c.get("metadata", {}).get("source") == "HumanActionCandidate"]
    assert record["human_action_injected"] is True
    assert record["chosen_action_id"] in action_ids
    assert len(injected) == 1
