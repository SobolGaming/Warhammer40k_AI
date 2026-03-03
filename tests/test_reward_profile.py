from __future__ import annotations

import pytest

from warhammer40k_ai.engine.reward_profile import annotate_decision_records_with_rewards


def _record(*, game_id: str, actor: str | None, active_player_id: str, p1_score: int, p2_score: int) -> dict:
    immediate = {}
    if actor is not None:
        immediate["actor_player_id"] = actor
    return {
        "game_id": game_id,
        "omniscient_state": {
            "active_player_id": active_player_id,
            "players": [
                {"player_id": "p1", "score": int(p1_score)},
                {"player_id": "p2", "score": int(p2_score)},
            ],
        },
        "outcome": {
            "immediate_deltas": immediate,
            "end_of_turn_return": 0.0,
        },
    }


def test_reward_profile_dense_vp_delta_adds_step_and_terminal_returns() -> None:
    records = [
        _record(game_id="g1", actor="p1", active_player_id="p1", p1_score=0, p2_score=0),
        _record(game_id="g1", actor="p1", active_player_id="p1", p1_score=5, p2_score=0),
        _record(game_id="g1", actor="p2", active_player_id="p2", p1_score=5, p2_score=3),
    ]

    annotated = annotate_decision_records_with_rewards(records, profile_id="dense_vp_delta_v1")

    assert len(annotated) == 3
    assert float(annotated[0]["outcome"]["end_of_turn_return"]) == 0.0
    assert float(annotated[1]["outcome"]["end_of_turn_return"]) == pytest.approx(0.5)
    assert float(annotated[2]["outcome"]["end_of_turn_return"]) == pytest.approx(0.3)
    assert float(annotated[0]["outcome"]["end_of_game_return"]) == 2.0
    assert float(annotated[1]["outcome"]["end_of_game_return"]) == 2.0
    assert float(annotated[2]["outcome"]["end_of_game_return"]) == -2.0
    assert str(annotated[1]["outcome"]["immediate_deltas"]["reward_profile_id"]) == "dense_vp_delta_v1"


def test_reward_profile_falls_back_to_active_player_for_actor_id() -> None:
    records = [
        _record(game_id="g1", actor=None, active_player_id="p1", p1_score=0, p2_score=0),
        _record(game_id="g1", actor=None, active_player_id="p1", p1_score=4, p2_score=1),
    ]

    annotated = annotate_decision_records_with_rewards(records, profile_id="terminal_vp_delta_v1")

    assert len(annotated) == 2
    assert float(annotated[0]["outcome"]["end_of_turn_return"]) == 0.0
    assert float(annotated[1]["outcome"]["end_of_turn_return"]) == 0.0
    assert float(annotated[0]["outcome"]["end_of_game_return"]) == 3.0
    assert float(annotated[1]["outcome"]["end_of_game_return"]) == 3.0
    assert str(annotated[0]["outcome"]["immediate_deltas"]["actor_player_id"]) == "p1"
