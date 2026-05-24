from __future__ import annotations

from warhammer40k_ai.engine import decision_record, game_decision_runtime
from warhammer40k_ai.engine.battlefield import Battlefield
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.mechanical_decisions import MECHANICAL_DESCRIPTOR_BUNDLE_ID, MECHANICAL_DESCRIPTOR_IDS
from warhammer40k_ai.roster.player import Player
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


def _make_game() -> Game:
    game = Game(Battlefield(width=60, height=44), players=[Player("P1"), Player("P2")])
    game.auto_resolve_dice_rolls = False
    return game


def test_dice_request_fast_path_skips_ai_and_descriptor_context(monkeypatch) -> None:
    def fail_runtime_compile_descriptor_bundle(_game):
        raise AssertionError("mechanical dice requests must not compile descriptor bundles")

    def fail_compile_descriptor_bundle(_game):
        raise AssertionError("mechanical dice records must use deterministic mechanical descriptors")

    monkeypatch.setattr(game_decision_runtime, "compile_descriptor_bundle", fail_runtime_compile_descriptor_bundle)
    monkeypatch.setattr(decision_record, "compile_descriptor_bundle", fail_compile_descriptor_bundle)
    game = _make_game()

    request = game.request_dice_roll(
        player_id=None,
        spec={
            "dice_count": 1,
            "faces": 6,
            "fixed_dice": [4],
            "reason": "Fast-path roll",
            "roll_type": "test",
        },
        prompt="Fast-path roll",
    )

    assert "descriptor_ids" not in request.context
    assert "descriptor_bundle_id" not in request.context
    assert "version_adapter_boundary" not in request.context
    assert "plan_id" not in request.context
    assert "turn_plan" not in request.context
    assert "movement_intent" not in request.context
    assert request.context["compute_tier"] == "P1"
    assert request.context["roll_spec"]["reason"] == "Fast-path roll"
    assert str(request.context["rules_bundle_id"]).startswith("rules_bundle:")
    assert "semantic_projection_kind" not in request.candidates[0].metadata
    assert "rules_provenance_refs" not in request.candidates[0].metadata

    resolve_decision_command(game, request, request.options[0].option_id)
    record = dict(game.decision_record_store.records[-1])

    assert record["descriptor_ids"] == MECHANICAL_DESCRIPTOR_IDS
    assert record["descriptor_bundle_id"] == MECHANICAL_DESCRIPTOR_BUNDLE_ID
    assert record["version_adapter_boundary"]["descriptor_ids"] == MECHANICAL_DESCRIPTOR_IDS
    assert record["version_adapter_boundary"]["descriptor_bundle_id"] == MECHANICAL_DESCRIPTOR_BUNDLE_ID


def test_dice_request_fast_path_ignores_cached_descriptor_context(monkeypatch) -> None:
    def fail_compile_descriptor_bundle(_game):
        raise AssertionError("mechanical dice requests must not compile descriptor bundles")

    monkeypatch.setattr(game_decision_runtime, "compile_descriptor_bundle", fail_compile_descriptor_bundle)
    game = _make_game()
    cached_descriptor_ids = {
        "mission_descriptor_id": "mission_descriptor:cached",
        "objective_descriptor_ids": ["objective_descriptor:cached"],
        "terrain_descriptor_ids": ["terrain_descriptor:cached"],
        "deployment_descriptor_id": "deployment_descriptor:cached",
        "army_build_descriptor_id": "army_build_descriptor:cached",
        "tool_descriptor_ids": ["tool_descriptor:cached"],
    }
    game._decision_request_descriptor_context = {
        "descriptor_ids": cached_descriptor_ids,
        "descriptor_bundle_id": "descriptor_bundle:cached",
        "descriptor_generation_key": ("stale", "ignored"),
        "version_adapter_boundary": {
            "adapter_family": "rules_conditioned_path",
            "adapter_version": "1",
            "adapter_id": "adapter:default",
            "rules_bundle_id": "rules_bundle:cached",
            "descriptor_bundle_id": "descriptor_bundle:cached",
            "descriptor_ids": cached_descriptor_ids,
            "conditioning_keys": [],
            "conditioning_signature": "conditioning:cached",
        },
    }

    request = game.request_dice_roll(
        player_id=None,
        spec={
            "dice_count": 1,
            "faces": 6,
            "fixed_dice": [4],
            "reason": "Cached descriptor roll",
            "roll_type": "test",
        },
        prompt="Cached descriptor roll",
    )

    assert "descriptor_ids" not in request.context
    assert "descriptor_bundle_id" not in request.context
    assert "version_adapter_boundary" not in request.context
    assert "plan_id" not in request.context
    assert "movement_intent" not in request.context
