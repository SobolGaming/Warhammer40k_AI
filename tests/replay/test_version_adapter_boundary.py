from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.version_adapter import build_version_adapter_boundary
from warhammer40k_ai.roster.player import Player


def _build_game() -> tuple[Game, Player]:
    player = Player("P1")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    return game, player


def test_version_adapter_boundary_builder_is_deterministic() -> None:
    context = {
        "rules_bundle_id": "rules_bundle:test",
        "descriptor_bundle_id": "descriptor_bundle:test",
        "descriptor_ids": {
            "mission_descriptor_id": "mission_descriptor:1",
            "objective_descriptor_ids": ["objective_descriptor:1"],
            "terrain_descriptor_ids": ["terrain_descriptor:1"],
            "deployment_descriptor_id": "deployment_descriptor:1",
            "army_build_descriptor_id": "army_build_descriptor:1",
            "tool_descriptor_ids": ["tool_descriptor:1"],
        },
    }
    first = build_version_adapter_boundary(context).to_dict()
    second = build_version_adapter_boundary(context).to_dict()

    assert first == second
    assert first["conditioning_signature"].startswith("conditioning:")


def test_request_context_includes_version_adapter_boundary() -> None:
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

    boundary = dict(request.context.get("version_adapter_boundary", {}) or {})
    assert boundary["adapter_family"] == "rules_conditioned_path"
    assert boundary["adapter_version"] == "1"
    assert boundary["rules_bundle_id"] == request.context["rules_bundle_id"]
    assert boundary["descriptor_bundle_id"] == request.context["descriptor_bundle_id"]
    assert boundary["descriptor_ids"] == request.context["descriptor_ids"]
    assert boundary["descriptor_ids"]["army_build_descriptor_id"].startswith("army_build_descriptor:")
