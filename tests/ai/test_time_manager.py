from __future__ import annotations

import time

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.time_manager import TimeManager
from warhammer40k_ai.roster.player import Player


def test_time_manager_applies_tier_multipliers() -> None:
    manager = TimeManager()
    base = manager.get_time_budget_ms(DECISION_MOVE_UNIT, compute_tier="P1")
    fast = manager.get_time_budget_ms(DECISION_MOVE_UNIT, compute_tier="P0")
    low = manager.get_time_budget_ms(DECISION_MOVE_UNIT, compute_tier="P2")
    assert base == 220
    assert fast == 396
    assert low == 110


def test_time_manager_run_with_budget_uses_fallback_when_over_budget() -> None:
    manager = TimeManager()

    def _slow_action(_deadline: float):
        time.sleep(0.02)
        return "slow-result"

    result, fallback_used, wall_clock_ms = manager.run_with_time_budget(
        budget_ms=1,
        action=_slow_action,
        fallback=lambda: "fallback-result",
    )
    assert fallback_used is True
    assert result == "fallback-result"
    assert wall_clock_ms >= 1


def test_game_request_decision_sets_time_budget_in_context() -> None:
    p1 = Player("P1")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[p1])
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm?",
        player_id=p1.id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
        context={"compute_tier": "P2"},
    )
    game.request_decision(request)

    assert int(request.context["time_budget_ms"]) > 0
    assert request.context["compute_tier"] == "P2"


def test_game_request_decision_normalizes_invalid_compute_tier_before_time_budget() -> None:
    p1 = Player("P1")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[p1])
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm?",
        player_id=p1.id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
        context={"compute_tier": "unknown"},
    )

    game.request_decision(request)

    assert request.context["compute_tier"] == "P1"
    assert int(request.context["time_budget_ms"]) == game.time_manager.get_time_budget_ms(
        DECISION_CONFIRM_YES_NO,
        compute_tier="P1",
    )
