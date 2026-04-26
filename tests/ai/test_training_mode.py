from __future__ import annotations

import json

from warhammer40k_ai.engine.ai_controller_router import COMPONENT_DEPLOYMENT_RANKER, COMPONENT_SHOOTING_RANKER
from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_RESERVES, DECISION_DECLARE_SHOTS
from warhammer40k_ai.engine.training_mode import (
    TRAINING_STAGE_DEPLOYMENT_RESERVES,
    TRAINING_STAGE_SHOOTING,
    TrainingObservationStore,
    TrainingScenarioConfig,
    TrainingScenarioGenerator,
    TrainingSession,
    best_training_action_id,
    evaluate_training_selection,
    load_training_observations,
)


def test_shooting_training_scenario_is_deterministic_and_decision_backed() -> None:
    config = TrainingScenarioConfig(stage=TRAINING_STAGE_SHOOTING, seed=123, candidate_count=5)
    first = TrainingScenarioGenerator(config).generate(0)
    second = TrainingScenarioGenerator(config).generate(0)

    assert first.scenario_id == second.scenario_id
    assert first.component_name == COMPONENT_SHOOTING_RANKER
    assert first.request.decision_type == DECISION_DECLARE_SHOTS
    assert first.request.decision_id == second.request.decision_id
    assert [candidate.action_id for candidate in first.request.candidates] == [
        candidate.action_id for candidate in second.request.candidates
    ]
    assert all(first.request.mask)
    assert first.request.context["training_mode"] is True
    assert first.to_ui_payload()["candidates"]


def test_deployment_reserves_training_scenario_masks_over_budget_plans() -> None:
    config = TrainingScenarioConfig(stage=TRAINING_STAGE_DEPLOYMENT_RESERVES, seed=7, candidate_count=7)
    scenario = TrainingScenarioGenerator(config).generate(0)

    assert scenario.component_name == COMPONENT_DEPLOYMENT_RANKER
    assert scenario.request.decision_type == DECISION_DECLARE_RESERVES
    assert scenario.request.context["reserve_cap_points"] == 500
    assert sum(unit["points"] for unit in scenario.situation["army"]) == 2000
    assert any(scenario.request.mask)
    for index, candidate in enumerate(scenario.request.candidates):
        reserve_points = int(candidate.metadata["reserve_points"])
        if index < len(scenario.request.mask) and scenario.request.mask[index]:
            assert reserve_points <= 500


def test_training_observation_store_records_selection_and_updates_model(tmp_path) -> None:
    output_path = tmp_path / "observations.jsonl"
    model_path = tmp_path / "preference_model.json"
    config = TrainingScenarioConfig(stage=TRAINING_STAGE_SHOOTING, seed=11)
    store = TrainingObservationStore(
        session_id=config.normalized_session_id(),
        output_path=output_path,
        model_output_path=model_path,
    )
    session = TrainingSession(config, store=store)
    scenario = session.next_scenario()
    action_id = best_training_action_id(scenario)

    observation = session.record_selection(scenario, action_id, source="test")

    assert observation.legal is True
    assert observation.evaluation.matched_best is True
    assert observation.evaluation.reward == 1.0
    assert store.model.component_counts[COMPONENT_SHOOTING_RANKER] == 1
    assert output_path.is_file()
    assert model_path.is_file()
    loaded = load_training_observations(output_path)
    assert len(loaded) == 1
    assert loaded[0]["chosen_action_id"] == action_id
    assert loaded[0]["supervised_example"]["chosen_action_id"] == action_id
    model_payload = json.loads(model_path.read_text(encoding="utf-8"))
    assert model_payload["component_counts"][COMPONENT_SHOOTING_RANKER] == 1


def test_training_evaluation_handles_non_best_legal_choice() -> None:
    config = TrainingScenarioConfig(stage=TRAINING_STAGE_DEPLOYMENT_RESERVES, seed=19, candidate_count=6)
    scenario = TrainingScenarioGenerator(config).generate(0)
    legal_ids = [
        candidate.action_id
        for index, candidate in enumerate(scenario.request.candidates)
        if index < len(scenario.request.mask) and scenario.request.mask[index]
    ]

    chosen = legal_ids[-1]
    evaluation = evaluate_training_selection(scenario, chosen)

    assert evaluation.selected_action_id == chosen
    assert evaluation.best_action_id in legal_ids
    assert 0.0 <= evaluation.reward <= 1.0
