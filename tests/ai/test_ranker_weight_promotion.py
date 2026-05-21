from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


def _load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "promote_ranker_weight_candidate.py"
    spec = importlib.util.spec_from_file_location("promote_ranker_weight_candidate_module", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load promote_ranker_weight_candidate.py for testing.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _matrix(path: Path, weight_set: dict) -> str:
    _write_json(
        path,
        {
            "weight_set_id": weight_set["weight_set_id"],
            "weight_set": weight_set,
            "rows": [],
        },
    )
    return str(path)


def _analysis(tmp_path: Path, *, status: str = "promote_candidate") -> tuple[Path, dict]:
    matrix_path = _matrix(
        tmp_path / "candidate" / "matrix_report.json",
        {
            "weight_set_id": "score_focus",
            "description": "Favor score pressure.",
            "component_weight_multipliers": {
                "movement_ranker": {
                    "projected_score_delta_next_window": 1.25,
                }
            },
        },
    )
    analysis = {
        "source_report": str(tmp_path / "weight_sweep_report.json"),
        "baseline_weight_set_id": "baseline",
        "promotion_policy": {"min_vp_delta": 1.0, "min_win_delta": 1},
        "summary": {
            "recommended_weight_set_id": "score_focus",
            "recommended_status": status,
        },
        "all_weight_sets": [
            {
                "weight_set_id": "baseline",
                "status": "baseline",
                "blockers": [],
                "review_flags": [],
                "artifact_paths": {},
            },
            {
                "weight_set_id": "score_focus",
                "status": status,
                "blockers": [],
                "review_flags": ["human_review"] if status == "review" else [],
                "metrics": {"mean_vp_differential_player1_minus_player2": 2.5},
                "baseline_delta": {"mean_vp_differential_player1_minus_player2": 2.5},
                "consistency": {"improved_count": 2, "worsened_count": 0},
                "resource_usage_anomalies": [],
                "artifact_paths": {"matrix_report": matrix_path},
            },
        ],
    }
    analysis_path = tmp_path / "weight_sweep_analysis.json"
    _write_json(analysis_path, analysis)
    return analysis_path, analysis


def test_build_promotion_artifact_uses_analysis_recommendation_and_matrix_weight_set(tmp_path) -> None:
    mod = _load_script_module()
    analysis_path, analysis = _analysis(tmp_path)

    artifact = mod.build_promotion_artifact(
        analysis,
        analysis_path=analysis_path,
        promoted_weight_set_id="baseline_candidate_score_focus_v1",
        notes="Manual promotion after smoke checks.",
    )

    assert artifact["artifact_kind"] == "ranker_weight_baseline_promotion"
    assert artifact["weight_sets"][0]["weight_set_id"] == "baseline_candidate_score_focus_v1"
    assert artifact["weight_sets"][0]["component_weight_multipliers"]["movement_ranker"] == {
        "projected_score_delta_next_window": 1.25,
    }
    promotion = artifact["promotion"]
    assert promotion["source_weight_set_id"] == "score_focus"
    assert promotion["candidate_status"] == "promote_candidate"
    assert promotion["promotion_policy"]["min_vp_delta"] == 1.0
    assert promotion["baseline_delta"]["mean_vp_differential_player1_minus_player2"] == 2.5
    assert promotion["notes"] == "Manual promotion after smoke checks."


def test_promotion_cli_writes_reusable_weight_set_artifact(tmp_path, monkeypatch) -> None:
    mod = _load_script_module()
    analysis_path, _analysis_doc = _analysis(tmp_path)
    output_path = tmp_path / "promoted.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "promote_ranker_weight_candidate.py",
            "--analysis",
            str(analysis_path),
            "--promoted-weight-set-id",
            "score_focus_promoted",
            "--output",
            str(output_path),
        ],
    )

    assert mod.main() == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["weight_sets"][0]["weight_set_id"] == "score_focus_promoted"
    assert payload["promotion"]["source_weight_set_id"] == "score_focus"


def test_review_candidate_requires_explicit_allow_review(tmp_path) -> None:
    mod = _load_script_module()
    analysis_path, analysis = _analysis(tmp_path, status="review")

    with pytest.raises(ValueError, match="review-only"):
        mod.build_promotion_artifact(analysis, analysis_path=analysis_path)

    artifact = mod.build_promotion_artifact(analysis, analysis_path=analysis_path, allow_review=True)
    assert artifact["promotion"]["candidate_status"] == "review"
    assert artifact["promotion"]["review_flags"] == ["human_review"]


def test_rejects_candidate_with_blockers(tmp_path) -> None:
    mod = _load_script_module()
    analysis_path, analysis = _analysis(tmp_path)
    analysis["all_weight_sets"][1]["blockers"] = ["fallback_rate_regression"]

    with pytest.raises(ValueError, match="blockers remain"):
        mod.build_promotion_artifact(analysis, analysis_path=analysis_path)
