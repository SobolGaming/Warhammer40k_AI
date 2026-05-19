from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_DECLARE_RESERVES,
    DECISION_MOVE_UNIT,
    DECISION_SELECT_NEXT_DEPLOY_UNIT,
)
from warhammer40k_ai.engine.ai_component_rankers import default_ai_component_rankers
from warhammer40k_ai.engine.ai_policy_orchestrator import COMPONENT_DEPLOYMENT_RANKER
from warhammer40k_ai.engine.decisions import CandidateAction, DecisionOption, DecisionRequest
from warhammer40k_ai.engine.deployment_intent import DeploymentIntent
from warhammer40k_ai.engine.deployment_ranker import DeploymentCandidateRanker
from warhammer40k_ai.engine.deployment_ranker_training import (
    build_deployment_ranking_dataset,
    train_deployment_ranker_model,
)
from warhammer40k_ai.engine.deployment_solver import generate_deployment_candidates


class _Map:
    width = 60.0
    height = 44.0


class _Game:
    players: list[object] = []
    time_manager = None
    map = _Map()


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
        "deep_strike_pressure_delta": float(deny) * 0.4,
        "reserve_entry_lane_delta": float(deny) * 0.3,
        "reserve_unit_slots_ratio": 0.2,
        "reserve_points_ratio": 0.2,
        "strategic_points_ratio": 0.1,
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


def _decision_record(
    *,
    decision_id: str,
    decision_type: str,
    chosen_action_id: str,
    candidate_kind: str,
    context: dict | None = None,
) -> dict:
    return {
        "decision_id": decision_id,
        "decision_type": decision_type,
        "game_id": "game:test",
        "player_id": "player:test",
        "valid": True,
        "chosen_action_id": chosen_action_id,
        "mask": [True, True],
        "context": dict(context or {}),
        "candidates": [
            {
                "action_id": "a",
                "metadata": _metadata(score=1.0, deny=0.3, candidate_kind=candidate_kind),
            },
            {
                "action_id": "b",
                "metadata": _metadata(score=0.2, deny=0.1, candidate_kind=candidate_kind),
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


def test_default_dataset_includes_reserves_and_filters_non_deployment_move_records() -> None:
    records = [
        _decision_record(
            decision_id="reserve-1",
            decision_type=DECISION_DECLARE_RESERVES,
            chosen_action_id="a",
            candidate_kind="deployment_reserves",
        ),
        _decision_record(
            decision_id="move-1",
            decision_type=DECISION_MOVE_UNIT,
            chosen_action_id="a",
            candidate_kind="move",
            context={"placement_kind": "movement"},
        ),
        _decision_record(
            decision_id="move-2",
            decision_type=DECISION_MOVE_UNIT,
            chosen_action_id="a",
            candidate_kind="deployment_move",
            context={"placement_kind": "deployment"},
        ),
    ]
    dataset = build_deployment_ranking_dataset(records)
    assert int(dataset.get("total_rank_decisions", 0) or 0) == 2
    assert int(dataset.get("skipped_non_deployment_move_records", 0) or 0) == 1
    kinds = set(str(value) for value in list(dataset.get("candidate_kinds", []) or []))
    assert "deployment_reserves" in kinds
    assert "deployment_move" in kinds


def test_deployment_ranker_consumes_commander_sequence_priority_for_next_drop() -> None:
    request = DecisionRequest.create(
        DECISION_SELECT_NEXT_DEPLOY_UNIT,
        "Select next unit",
        player_id="player:test",
        options=[
            DecisionOption.create("Line", payload={"unit_id": "unit:line"}),
            DecisionOption.create("Scout", payload={"unit_id": "unit:scout"}),
        ],
        context={
            "already_deployed_count": 0,
            "undeployed_count": 2,
            "deployment_candidate_unit_tasks": {
                "unit:line": {
                    "unit_id": "unit:line",
                    "role": "stage",
                    "preferred_drop_window": "late",
                    "deployment_sequence_priority": 0.1,
                    "go_first_value": 0.4,
                    "go_second_safety": 0.6,
                    "tactical_flexibility": 0.4,
                },
                "unit:scout": {
                    "unit_id": "unit:scout",
                    "role": "screen",
                    "preferred_drop_window": "early",
                    "deployment_sequence_priority": 2.4,
                    "has_scout": True,
                    "scout_lane_targets": ["left_no_mans_land_lane"],
                    "no_mans_land_pressure_regions": ["left_forward_screen"],
                    "go_first_value": 0.65,
                    "go_second_safety": 0.55,
                    "tactical_flexibility": 0.75,
                },
            },
            "deployment_candidate_tempo_capabilities": {
                "unit:scout": {
                    "unit_id": "unit:scout",
                    "has_scout": True,
                    "early_drop_priority": 2.3,
                    "reveal_risk": 0.1,
                },
            },
            "mission_state": {"selected_mission_info": {"secondary_mission_mode": "tactical"}},
        },
    )
    candidates, mask, _wall_ms, fallback_mode = generate_deployment_candidates(
        _Game(),
        request,
        DeploymentIntent.from_context(request.context),
    )
    request.candidates = candidates
    request.mask = mask

    scout_action = request.action_id_for_option_id(request.options[1].option_id)
    scout_candidate = next(candidate for candidate in candidates if candidate.action_id == scout_action)
    assert fallback_mode is False
    assert scout_candidate.metadata["deployment_sequence_priority"] > 0.0
    assert scout_candidate.metadata["scout_lane_value"] > 0.0
    assert (
        default_ai_component_rankers()[COMPONENT_DEPLOYMENT_RANKER].choose_action_id(request)
        == scout_action
    )


def test_deployment_ranker_consumes_scout_placement_tempo_metadata() -> None:
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Deploy scout",
        player_id="player:test",
        options=[
            DecisionOption.create(
                "Back",
                payload={
                    "unit_id": "unit:scout",
                    "action": "confirm",
                    "deployment_anchor": [30.0, 4.0],
                    "model_positions": [{"model_id": "m1", "position": [30.0, 4.0, 0.0]}],
                },
            ),
            DecisionOption.create(
                "Forward",
                payload={
                    "unit_id": "unit:scout",
                    "action": "confirm",
                    "deployment_anchor": [30.0, 18.0],
                    "model_positions": [{"model_id": "m1", "position": [30.0, 18.0, 0.0]}],
                },
            ),
        ],
        context={
            "unit_id": "unit:scout",
            "placement_kind": "deployment",
            "deployment_candidate_count": 2,
            "deployment_intent": {
                "desired_affordances": ["FORWARD_SCREEN"],
                "anchors": {"deployment_center_x": "30.0", "deployment_center_y": "10.0"},
            },
            "unit_deployment_task": {
                "unit_id": "unit:scout",
                "role": "screen",
                "preferred_drop_window": "early",
                "deployment_sequence_priority": 2.0,
                "has_scout": True,
                "scout_lane_targets": ["left_no_mans_land_lane"],
                "no_mans_land_pressure_regions": ["left_forward_screen"],
                "go_first_value": 0.65,
                "go_second_safety": 0.75,
                "metadata": {"first_turn_uncertainty_risk": 0.05},
            },
            "deployment_tempo_capability": {
                "unit_id": "unit:scout",
                "has_scout": True,
                "early_drop_priority": 2.0,
                "reveal_risk": 0.05,
            },
            "scout_projection": {
                "unit_id": "unit:scout",
                "can_reach_cover": True,
                "can_screen_lane_ids": ["left_no_mans_land_lane"],
                "can_threaten_objective_ids": ["midfield_objective"],
            },
        },
    )
    candidates, mask, _wall_ms, _fallback_mode = generate_deployment_candidates(
        _Game(),
        request,
        DeploymentIntent.from_context(request.context),
    )
    request.candidates = candidates
    request.mask = mask

    forward_action = request.action_id_for_option_id(request.options[1].option_id)
    by_action = {candidate.action_id: candidate for candidate in candidates}
    assert by_action[forward_action].metadata["scout_lane_value"] > 0.0
    assert by_action[forward_action].metadata["scout_objective_threat_score"] > 0.0
    assert by_action[forward_action].metadata["commander_deployment_alignment"] > by_action[
        request.action_id_for_option_id(request.options[0].option_id)
    ].metadata["commander_deployment_alignment"]
    assert (
        default_ai_component_rankers()[COMPONENT_DEPLOYMENT_RANKER].choose_action_id(request)
        == forward_action
    )


def test_deployment_ranker_consumes_infiltrate_counter_scout_metadata() -> None:
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Deploy infiltrator",
        player_id="player:test",
        options=[
            DecisionOption.create(
                "Safe back",
                payload={
                    "unit_id": "unit:infiltrator",
                    "action": "confirm",
                    "deployment_anchor": [30.0, 6.0],
                    "model_positions": [{"model_id": "m1", "position": [30.0, 6.0, 0.0]}],
                },
            ),
            DecisionOption.create(
                "Counter scout",
                payload={
                    "unit_id": "unit:infiltrator",
                    "action": "confirm",
                    "deployment_anchor": [30.0, 20.0],
                    "model_positions": [{"model_id": "m1", "position": [30.0, 20.0, 0.0]}],
                },
            ),
        ],
        context={
            "unit_id": "unit:infiltrator",
            "placement_kind": "deployment",
            "deployment_candidate_count": 2,
            "deployment_intent": {
                "desired_affordances": ["FORWARD_SCREEN"],
                "anchors": {"deployment_center_x": "30.0", "deployment_center_y": "10.0"},
            },
            "unit_deployment_task": {
                "unit_id": "unit:infiltrator",
                "role": "screen",
                "preferred_drop_window": "early",
                "deployment_sequence_priority": 3.0,
                "has_infiltrate": True,
                "counter_scout_regions": ["left_forward_screen"],
                "infiltrate_screen_regions": ["left_forward_screen"],
                "no_mans_land_pressure_regions": ["left_forward_screen"],
                "go_first_value": 0.7,
                "go_second_safety": 0.7,
            },
            "deployment_tempo_capability": {
                "unit_id": "unit:infiltrator",
                "has_infiltrate": True,
                "early_drop_priority": 3.0,
                "reveal_risk": 0.1,
            },
            "infiltrate_projection": {
                "unit_id": "unit:infiltrator",
                "blocks_enemy_scout_lane_ids": ["left_no_mans_land_lane"],
                "denies_enemy_forward_regions": ["left_forward_screen"],
            },
        },
    )
    candidates, mask, _wall_ms, _fallback_mode = generate_deployment_candidates(
        _Game(),
        request,
        DeploymentIntent.from_context(request.context),
    )
    request.candidates = candidates
    request.mask = mask

    counter_action = request.action_id_for_option_id(request.options[1].option_id)
    counter_candidate = next(candidate for candidate in candidates if candidate.action_id == counter_action)
    assert counter_candidate.metadata["infiltrate_screen_value"] > 0.0
    assert counter_candidate.metadata["counter_scout_value"] > 0.0
    assert counter_candidate.metadata["enemy_forward_deny_value"] > 0.0
    assert (
        default_ai_component_rankers()[COMPONENT_DEPLOYMENT_RANKER].choose_action_id(request)
        == counter_action
    )
