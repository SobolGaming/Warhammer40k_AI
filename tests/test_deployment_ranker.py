from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_MOVE_UNIT,
)
from warhammer40k_ai.engine.decisions import CandidateAction, DecisionOption, DecisionRequest
from warhammer40k_ai.engine.deployment_ranker import DeploymentCandidateRanker
from warhammer40k_ai.engine.deployment_ranker_training import (
    build_deployment_ranking_dataset,
    train_deployment_ranker_model,
)


def _metadata(*, score: float, deny: float, candidate_kind: str = "deployment_zone") -> dict:
    return {
        "candidate_kind": candidate_kind,
        "projected_score_delta_next_window": float(score),
        "projected_score_delta_round": float(score) * 1.1,
        "projected_deny_delta_next_window": float(deny),
        "projected_control_delta": float(score) * 0.8,
        "projected_action_enablement_delta": float(score) * 0.4,
        "projected_exposure_delta": -float(score) * 0.2,
        "projected_trade_ev": float(score) * 0.3,
        "cover_delta": 0.0,
        "los_delta": 0.0,
        "resource_delta": 0.0,
        "reserve_denial_delta": float(deny) * 0.5,
        "screen_integrity_delta": float(deny) * 0.4,
        "countercharge_coverage_delta": 0.0,
        "aura_connectivity_delta": 0.0,
        "projected_exposure_delta_if_enemy_goes_first": 0.0,
        "projected_melee_staging_delta": 0.0,
        "rules_provenance_refs": ["rules_bundle:test"],
    }


def _record(
    *,
    decision_id: str,
    chosen_action_id: str,
    first_score: float,
    second_score: float,
) -> dict:
    return {
        "decision_id": decision_id,
        "decision_type": DECISION_CHOOSE_DEPLOYMENT_ZONE,
        "game_id": "game:test",
        "player_id": "player:test",
        "valid": True,
        "chosen_action_id": chosen_action_id,
        "mask": [True, True],
        "candidates": [
            {
                "action_id": "zone:a",
                "metadata": _metadata(score=first_score, deny=0.2),
            },
            {
                "action_id": "zone:b",
                "metadata": _metadata(score=second_score, deny=0.1),
            },
        ],
    }


def test_build_deployment_ranking_dataset_filters_and_projects_features() -> None:
    records = [
        _record(
            decision_id="d1",
            chosen_action_id="zone:a",
            first_score=1.0,
            second_score=0.3,
        ),
        {
            "decision_id": "ignored",
            "decision_type": DECISION_MOVE_UNIT,
            "valid": True,
            "chosen_action_id": "x",
            "candidates": [],
            "mask": [],
        },
    ]
    dataset = build_deployment_ranking_dataset(records)
    assert int(dataset["total_input_records"]) == 2
    assert int(dataset["total_rank_decisions"]) == 1
    assert int(dataset["total_candidate_rows"]) == 2
    decision = dict(dataset["decisions"][0])
    assert str(decision.get("chosen_action_id", "") or "") == "zone:a"
    row = dict(list(decision.get("candidates", []) or [])[0])
    features = dict(row.get("features", {}) or {})
    assert "projected_score_delta_next_window" in features
    assert "reserve_denial_delta" in features


def test_trained_deployment_ranker_selects_higher_value_candidate() -> None:
    records = [
        _record(
            decision_id="d1",
            chosen_action_id="zone:a",
            first_score=1.2,
            second_score=0.2,
        ),
        _record(
            decision_id="d2",
            chosen_action_id="zone:b",
            first_score=0.3,
            second_score=1.1,
        ),
        _record(
            decision_id="d3",
            chosen_action_id="zone:a",
            first_score=0.9,
            second_score=0.1,
        ),
    ]
    dataset = build_deployment_ranking_dataset(records)
    model = train_deployment_ranker_model(dataset, epochs=200, learning_rate=0.08, l2_weight=1e-5, seed=7)
    ranker = DeploymentCandidateRanker(model)

    request = DecisionRequest.create(
        DECISION_CHOOSE_DEPLOYMENT_ZONE,
        "Choose zone",
        player_id="player:test",
        options=[
            DecisionOption.create("Zone A", payload={"zone_key": "a"}),
            DecisionOption.create("Zone B", payload={"zone_key": "b"}),
        ],
        context={},
    )
    assert request is not None
    action_a = request.action_id_for_option_id(request.options[0].option_id)
    action_b = request.action_id_for_option_id(request.options[1].option_id)
    request.candidates = [
        CandidateAction(
            action_id=action_a,
            params={},
            metadata=_metadata(score=1.3, deny=0.2),
        ),
        CandidateAction(
            action_id=action_b,
            params={},
            metadata=_metadata(score=0.2, deny=0.1),
        ),
    ]
    request.mask = [True, True]
    chosen = ranker.choose_action_id(request)
    assert str(chosen) == str(action_a)
