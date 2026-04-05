from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.descriptor_compiler import compile_descriptor_bundle
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.player import Player


def _build_game() -> tuple[Game, Player]:
    player = Player("P1")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    return game, player


def test_descriptor_compiler_is_deterministic_for_same_state() -> None:
    game, _player = _build_game()
    first = compile_descriptor_bundle(game)
    second = compile_descriptor_bundle(game)

    assert first.bundle_id == second.bundle_id
    assert first.descriptor_ids() == second.descriptor_ids()
    assert first.descriptor_ids()["mission_descriptor_id"].startswith("mission_descriptor:")
    assert first.descriptor_ids()["deployment_descriptor_id"].startswith("deployment_descriptor:")


def test_request_decision_injects_compiled_descriptor_ids() -> None:
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
    descriptor_ids = request.context["descriptor_ids"]

    assert descriptor_ids["mission_descriptor_id"].startswith("mission_descriptor:")
    assert descriptor_ids["deployment_descriptor_id"].startswith("deployment_descriptor:")
    assert isinstance(descriptor_ids["objective_descriptor_ids"], list)
    assert isinstance(descriptor_ids["terrain_descriptor_ids"], list)
    assert isinstance(descriptor_ids["tool_descriptor_ids"], list)
    assert request.context["descriptor_bundle_id"].startswith("descriptor_bundle:")


def test_record_resolution_without_context_uses_compiled_descriptor_ids() -> None:
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
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={},
    )
    record = game.decision_record_store.record_resolution(
        request=request,
        result=result,
        ok=True,
        errors=(),
        value=None,
        wall_clock_ms=1,
    )

    descriptor_ids = record["descriptor_ids"]
    assert descriptor_ids["mission_descriptor_id"].startswith("mission_descriptor:")
    assert descriptor_ids["deployment_descriptor_id"].startswith("deployment_descriptor:")
    assert isinstance(descriptor_ids["objective_descriptor_ids"], list)
    assert isinstance(descriptor_ids["terrain_descriptor_ids"], list)
    assert isinstance(descriptor_ids["tool_descriptor_ids"], list)
