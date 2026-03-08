from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_DEPLOYMENT_ZONE


def _metadata(score: float) -> dict:
    return {
        "candidate_kind": "deployment_zone",
        "projected_score_delta_next_window": float(score),
        "projected_score_delta_round": float(score) * 1.1,
        "projected_deny_delta_next_window": 0.1,
        "projected_control_delta": 0.2,
        "projected_action_enablement_delta": 0.1,
        "projected_exposure_delta": -0.05,
        "projected_trade_ev": 0.1,
        "cover_delta": 0.0,
        "los_delta": 0.0,
        "resource_delta": 0.0,
        "reserve_denial_delta": 0.05,
        "screen_integrity_delta": 0.04,
        "countercharge_coverage_delta": 0.0,
        "aura_connectivity_delta": 0.0,
        "projected_exposure_delta_if_enemy_goes_first": 0.0,
        "projected_melee_staging_delta": 0.0,
        "rules_provenance_refs": ["rules_bundle:test"],
    }


def _record(decision_id: str, chosen_action_id: str, a_score: float, b_score: float) -> dict:
    return {
        "decision_id": decision_id,
        "decision_type": DECISION_CHOOSE_DEPLOYMENT_ZONE,
        "game_id": "game:test",
        "player_id": "player:test",
        "valid": True,
        "chosen_action_id": chosen_action_id,
        "mask": [True, True],
        "candidates": [
            {"action_id": "zone:a", "metadata": _metadata(a_score)},
            {"action_id": "zone:b", "metadata": _metadata(b_score)},
        ],
    }


def test_deployment_ranker_cli_dataset_and_training_round_trip(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    records_path = tmp_path / "records.json"
    dataset_path = tmp_path / "deployment_dataset.json"
    model_path = tmp_path / "deployment_ranker_model.json"

    records = [
        _record("d1", "zone:a", 1.2, 0.1),
        _record("d2", "zone:b", 0.2, 1.1),
        _record("d3", "zone:a", 0.9, 0.3),
    ]
    records_path.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")

    build_script = repo_root / "scripts" / "build_deployment_ranking_dataset.py"
    train_script = repo_root / "scripts" / "train_deployment_ranker.py"

    build_cmd = [
        sys.executable,
        str(build_script),
        "--input",
        str(records_path),
        "--output",
        str(dataset_path),
    ]
    build_completed = subprocess.run(
        build_cmd,
        check=True,
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    assert build_completed.returncode == 0
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    assert int(dataset.get("total_rank_decisions", 0) or 0) == 3

    train_cmd = [
        sys.executable,
        str(train_script),
        "--input",
        str(dataset_path),
        "--output",
        str(model_path),
        "--epochs",
        "150",
    ]
    train_completed = subprocess.run(
        train_cmd,
        check=True,
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    assert train_completed.returncode == 0
    model = json.loads(model_path.read_text(encoding="utf-8"))
    assert str(model.get("model_type", "") or "") == "deployment_linear_ranker_v1"
    metrics = dict(model.get("training_metrics", {}) or {})
    assert float(metrics.get("top1_accuracy", 0.0) or 0.0) >= 0.66
