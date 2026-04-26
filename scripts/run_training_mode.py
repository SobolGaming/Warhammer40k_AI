#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
from typing import Sequence

from warhammer40k_ai.engine.training_mode import (
    SUPPORTED_TRAINING_STAGES,
    TRAINING_STAGE_MIXED,
    TrainingObservation,
    TrainingObservationStore,
    TrainingPreferenceModel,
    TrainingScenario,
    TrainingScenarioConfig,
    TrainingSession,
    best_training_action_id,
)


def _first_legal_action_id(scenario: TrainingScenario) -> str:
    for index, candidate in enumerate(list(scenario.request.candidates or [])):
        if index < len(scenario.request.mask) and bool(scenario.request.mask[index]):
            return str(candidate.action_id)
    return ""


def _random_legal_action_id(scenario: TrainingScenario, rng: random.Random) -> str:
    legal = [
        str(candidate.action_id)
        for index, candidate in enumerate(list(scenario.request.candidates or []))
        if index < len(scenario.request.mask) and bool(scenario.request.mask[index])
    ]
    if not legal:
        return ""
    return rng.choice(legal)


def _choose_auto_action(
    scenario: TrainingScenario,
    *,
    mode: str,
    model: TrainingPreferenceModel,
    rng: random.Random,
) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized == "best":
        return best_training_action_id(scenario)
    if normalized == "first":
        return _first_legal_action_id(scenario)
    if normalized == "random":
        return _random_legal_action_id(scenario, rng)
    if normalized == "model":
        model_choice = model.choose_action_id(scenario)
        if model_choice:
            return model_choice
        return _first_legal_action_id(scenario)
    raise ValueError(f"Unsupported auto-choice mode: {mode}")


def _load_model(model_input: str, model_output: str) -> TrainingPreferenceModel:
    input_path = Path(str(model_input or "").strip()) if str(model_input or "").strip() else None
    if input_path is not None:
        return TrainingPreferenceModel.load(input_path)
    output_path = Path(str(model_output or "").strip()) if str(model_output or "").strip() else None
    if output_path is not None and output_path.is_file():
        return TrainingPreferenceModel.load(output_path)
    return TrainingPreferenceModel()


def run_headless_training(args: argparse.Namespace) -> list[TrainingObservation]:
    config = TrainingScenarioConfig(
        stage=str(args.stage),
        seed=int(args.seed),
        session_id=str(args.session_id or ""),
        user_side=str(args.user_side),
        opponent_mode=str(args.opponent_mode),
        point_limit=int(args.point_limit),
        candidate_count=int(args.candidate_count),
        time_budget_ms=int(args.time_budget_ms),
    )
    model = _load_model(str(args.model_input or ""), str(args.model_output or ""))
    store = TrainingObservationStore(
        session_id=config.normalized_session_id(),
        output_path=args.output,
        model=model,
        model_output_path=args.model_output,
    )
    session = TrainingSession(config, store=store)
    rng = random.Random(int(args.seed))
    observations: list[TrainingObservation] = []
    for _index in range(max(1, int(args.situations))):
        scenario = session.next_scenario()
        action_id = _choose_auto_action(
            scenario,
            mode=str(args.headless_auto_choice),
            model=store.model,
            rng=rng,
        )
        observations.append(session.record_selection(scenario, action_id, source="headless_training"))
    return observations


def run_ui_training(args: argparse.Namespace) -> list[TrainingObservation]:
    config = TrainingScenarioConfig(
        stage=str(args.stage),
        seed=int(args.seed),
        session_id=str(args.session_id or ""),
        user_side=str(args.user_side),
        opponent_mode=str(args.opponent_mode),
        point_limit=int(args.point_limit),
        candidate_count=int(args.candidate_count),
        time_budget_ms=int(args.time_budget_ms),
    )
    model = _load_model(str(args.model_input or ""), str(args.model_output or ""))
    store = TrainingObservationStore(
        session_id=config.normalized_session_id(),
        output_path=args.output,
        model=model,
        model_output_path=args.model_output,
    )
    session = TrainingSession(config, store=store)
    from warhammer40k_ai.UI.training_mode_ui import TrainingModeApp

    app = TrainingModeApp(session, situations=max(1, int(args.situations)))
    return app.run()


def _write_summary(observations: Sequence[TrainingObservation]) -> dict[str, object]:
    records = [observation.to_dict() for observation in list(observations or [])]
    by_component: dict[str, int] = {}
    matched_best = 0
    for record in records:
        component = str(record.get("component_name", "") or "")
        by_component[component] = int(by_component.get(component, 0)) + 1
        evaluation = dict(record.get("evaluation", {}) or {})
        if bool(evaluation.get("matched_best", False)):
            matched_best += 1
    return {
        "observations": len(records),
        "matched_best": matched_best,
        "components": by_component,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one-step Warhammer 40,000 AI training situations.")
    parser.add_argument(
        "--stage",
        choices=[TRAINING_STAGE_MIXED, *SUPPORTED_TRAINING_STAGES],
        default=TRAINING_STAGE_MIXED,
    )
    parser.add_argument("--situations", type=int, default=20)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--user-side", choices=["player1", "player2", "both"], default="player1")
    parser.add_argument("--opponent-mode", choices=["ai", "human", "none"], default="ai")
    parser.add_argument("--point-limit", type=int, default=2000)
    parser.add_argument("--candidate-count", type=int, default=6)
    parser.add_argument("--time-budget-ms", type=int, default=250)
    parser.add_argument("--output", default="data/training_mode_observations.jsonl")
    parser.add_argument("--model-input", default="")
    parser.add_argument("--model-output", default="data/training_mode_preference_model.json")
    parser.add_argument(
        "--headless-auto-choice",
        choices=["", "first", "best", "random", "model"],
        default="",
        help="Choose actions without opening the Pygame UI.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if str(args.headless_auto_choice or "").strip():
        observations = run_headless_training(args)
    else:
        observations = run_ui_training(args)
    summary = _write_summary(observations)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
