from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from warhammer40k_ai.engine.training_mode import load_training_observations


def _load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "run_training_mode.py"
    spec = importlib.util.spec_from_file_location("run_training_mode_module", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load run_training_mode.py for testing.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_training_mode_parser_supports_mixed_default() -> None:
    mod = _load_script_module()

    args = mod._build_parser().parse_args([])

    assert args.stage == "mixed"
    assert args.situations == 20
    assert args.headless_auto_choice == ""


def test_headless_training_mode_writes_observations_and_model(tmp_path) -> None:
    mod = _load_script_module()
    output_path = tmp_path / "training.jsonl"
    model_path = tmp_path / "model.json"
    args = SimpleNamespace(
        stage="mixed",
        situations=4,
        seed=31,
        session_id="training:test",
        user_side="player1",
        opponent_mode="ai",
        point_limit=2000,
        candidate_count=5,
        time_budget_ms=250,
        output=str(output_path),
        model_input="",
        model_output=str(model_path),
        headless_auto_choice="best",
    )

    observations = mod.run_headless_training(args)
    summary = mod._write_summary(observations)

    assert summary["observations"] == 4
    assert summary["matched_best"] == 4
    assert output_path.is_file()
    assert model_path.is_file()
    records = load_training_observations(output_path)
    assert len(records) == 4
    assert {record["component_name"] for record in records} == {"shooting_ranker", "deployment_ranker"}
