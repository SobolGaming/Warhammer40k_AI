from __future__ import annotations

import pytest

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.candidate_semantics import (
    SEMANTIC_NUMERIC_KEYS,
    ensure_candidate_semantic_metadata,
)
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_ALLOCATE_MELEE_TARGETS,
    DECISION_CONFIRM_YES_NO,
    DECISION_DECLARE_CHARGE,
    DECISION_DECLARE_SHOTS,
    DECISION_MOVE_UNIT,
    DECISION_USE_GILDED_CHAMPION,
)
from warhammer40k_ai.engine.decisions import CandidateAction, DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.player import Player


def _build_game() -> tuple[Game, Player]:
    player = Player("P1")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    return game, player


def test_request_decision_adds_semantic_metadata_keys_to_candidates() -> None:
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

    for candidate in list(request.candidates or []):
        metadata = dict(candidate.metadata or {})
        for key in SEMANTIC_NUMERIC_KEYS:
            assert key in metadata
        assert isinstance(metadata.get("rules_provenance_refs"), list)
        assert request.context["rules_bundle_id"] in metadata["rules_provenance_refs"]


def test_semantic_augmenter_preserves_existing_numeric_values() -> None:
    request = DecisionRequest.create(
        DECISION_DECLARE_SHOTS,
        "Declare shots",
        player_id="player_1",
        options=[DecisionOption.create("Declare", payload={"action": "declare"})],
        candidates=[
            CandidateAction(
                action_id="candidate_1",
                params={"action": "declare"},
                metadata={"projected_trade_ev": 1.75},
            )
        ],
        mask=[True],
    )
    ensure_candidate_semantic_metadata(request, rules_bundle_id="rules_bundle:test")

    metadata = dict(request.candidates[0].metadata or {})
    assert metadata["projected_trade_ev"] == 1.75
    for key in SEMANTIC_NUMERIC_KEYS:
        assert key in metadata
    assert metadata["rules_provenance_refs"] == ["rules_bundle:test"]


def _rules_bundle_with_suffix(suffix: str) -> dict[str, str]:
    return {
        "core_rules_id": f"core_{suffix}",
        "rules_commentary_id": f"commentary_{suffix}",
        "mission_pack_id": f"mission_{suffix}",
        "terrain_pack_id": f"terrain_{suffix}",
        "dataslate_id": f"dataslate_{suffix}",
        "points_id": f"points_{suffix}",
        "faction_pack_id": f"faction_{suffix}",
        "detachment_pack_id": f"detachment_{suffix}",
    }


def _single_candidate_request(
    decision_type: str,
    *,
    params: dict,
    context: dict | None = None,
) -> DecisionRequest:
    return DecisionRequest.create(
        decision_type,
        "Semantic projection test",
        player_id="player_1",
        options=[DecisionOption.create("Apply", payload=dict(params or {}))],
        context=dict(context or {}),
        candidates=[
            CandidateAction(
                action_id=f"{decision_type}:candidate",
                params=dict(params or {}),
                metadata={},
            )
        ],
        mask=[True],
    )


@pytest.mark.parametrize(
    ("decision_type", "params", "context", "expected_kind"),
    [
        (
            DECISION_MOVE_UNIT,
            {"action": "confirm", "unit_id": "unit_1", "movement_type": "move"},
            {
                "movement_intent": {
                    "target_region_ids": ["region_1"],
                    "target_opportunity_ids": ["opp_1"],
                    "desired_affordances": ["HOLD_SCORE_SOURCE"],
                    "screen_deny_targets": ["lane_1"],
                    "weights": {
                        "score": 0.55,
                        "deny": 0.2,
                        "safety": 0.25,
                        "coherency": 0.2,
                        "action_enable": 0.2,
                        "trade": 0.1,
                    },
                },
                "score_window_state": {"windows": [{"id": "window_1"}]},
            },
            "movement",
        ),
        (
            DECISION_DECLARE_SHOTS,
            {
                "action": "declare",
                "unit_id": "unit_1",
                "target_unit_ids": ["target_a", "target_b"],
                "declared_shots": [{"weapon_id": "weapon_1", "shots": 4}],
            },
            {
                "opportunity_catalog": {
                    "priority": [{"id": "priority_1"}],
                    "denial": [{"id": "deny_1"}],
                }
            },
            "targeting",
        ),
        (
            DECISION_DECLARE_CHARGE,
            {
                "action": "declare",
                "unit_id": "unit_1",
                "target_unit_ids": ["target_a"],
                "charge_distance": 7,
            },
            {},
            "charge",
        ),
        (
            DECISION_ALLOCATE_MELEE_TARGETS,
            {
                "action": "allocate",
                "attack_declarations": [
                    {
                        "model_id": "model_1",
                        "wargear_id": "wargear_1",
                        "profile_name": "talons",
                        "target_unit_id": "target_a",
                        "attacks_override": 4,
                    }
                ],
            },
            {},
            "fight",
        ),
        (
            DECISION_USE_GILDED_CHAMPION,
            {
                "action": "use",
                "model_id": "model_1",
                "ability_key": "precision_cut",
                "ability_name": "Precision Strike",
                "cp_cost": 1,
            },
            {"tool_descriptor_ids": ["tool_descriptor:stratagem:001"]},
            "tool",
        ),
    ],
)
def test_semantic_projection_value_shifts_with_bundle_change(
    decision_type: str,
    params: dict,
    context: dict,
    expected_kind: str,
) -> None:
    old_bundle = _rules_bundle_with_suffix("old")
    new_bundle = _rules_bundle_with_suffix("new")
    old_bundle_id = "rules_bundle:old"
    new_bundle_id = "rules_bundle:new"

    old_request = _single_candidate_request(decision_type, params=params, context=context)
    new_request = _single_candidate_request(decision_type, params=params, context=context)
    ensure_candidate_semantic_metadata(
        old_request,
        rules_bundle_id=old_bundle_id,
        rules_bundle=old_bundle,
    )
    ensure_candidate_semantic_metadata(
        new_request,
        rules_bundle_id=new_bundle_id,
        rules_bundle=new_bundle,
    )

    old_metadata = dict(old_request.candidates[0].metadata or {})
    new_metadata = dict(new_request.candidates[0].metadata or {})
    assert old_metadata["semantic_projection_kind"] == expected_kind
    assert new_metadata["semantic_projection_kind"] == expected_kind
    assert old_bundle_id in old_metadata["rules_provenance_refs"]
    assert new_bundle_id in new_metadata["rules_provenance_refs"]

    value_pairs = [
        (
            float(old_metadata.get(key, 0.0)),
            float(new_metadata.get(key, 0.0)),
        )
        for key in SEMANTIC_NUMERIC_KEYS
    ]
    assert any(old_value != new_value for old_value, new_value in value_pairs)
