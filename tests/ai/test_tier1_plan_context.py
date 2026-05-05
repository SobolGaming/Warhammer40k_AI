from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.tier1_plan import _unit_priority_tiers
from warhammer40k_ai.roster.player import Player


class _ModelWithExpensiveMovement:
    _movement = 12

    @property
    def movement(self) -> int:
        raise AssertionError("Tier1 planning should use cached _movement when present")


def _build_game() -> tuple[Game, Player, Player]:
    p1 = Player("P1")
    p2 = Player("P2")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
    return game, p1, p2


def _confirm_request(player_id: str) -> DecisionRequest:
    return DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm?",
        player_id=player_id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
    )


def test_tier1_plan_is_attached_to_decision_context() -> None:
    game, p1, _p2 = _build_game()
    request = _confirm_request(p1.id)
    game.request_decision(request)

    assert "plan_id" in request.context
    assert "turn_plan" in request.context
    assert request.context["turn_plan"]["plan_id"] == request.context["plan_id"]


def test_tier1_plan_id_threads_through_same_turn_decisions() -> None:
    game, p1, _p2 = _build_game()
    first = _confirm_request(p1.id)
    game.request_decision(first)
    second = _confirm_request(p1.id)
    game.request_decision(second)

    assert first.context["plan_id"] == second.context["plan_id"]


def test_tier1_plan_exists_at_command_phase_start() -> None:
    game, p1, _p2 = _build_game()
    game.start_command_phase()
    plan = game.get_or_create_tier1_plan(p1.id)
    assert str(plan.plan_id)


def test_tier1_unit_priority_uses_cached_model_movement() -> None:
    unit = SimpleNamespace(id="unit:fast", deployed=True, models=[_ModelWithExpensiveMovement()])
    player = SimpleNamespace(army=SimpleNamespace(units=[unit]))

    tiers = _unit_priority_tiers(player)

    assert tiers["P0"] == ["unit:fast"]
