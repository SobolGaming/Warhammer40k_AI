from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


def _load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "run_promoted_ranker_baseline_gate.py"
    spec = importlib.util.spec_from_file_location("run_promoted_ranker_baseline_gate_module", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load run_promoted_ranker_baseline_gate.py for testing.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _promoted_artifact() -> dict:
    return {
        "artifact_kind": "ranker_weight_baseline_promotion",
        "promotion": {
            "source_weight_set_id": "score_focus",
            "promoted_weight_set_id": "score_focus_v1",
        },
        "weight_sets": [
            {
                "weight_set_id": "score_focus_v1",
                "description": "Promoted score focus.",
                "component_weight_multipliers": {
                    "movement_ranker": {"projected_score_delta_next_window": 1.25},
                },
            }
        ],
    }


def _analysis(candidate_status: str = "promote_candidate", blockers: list[str] | None = None) -> dict:
    return {
        "summary": {
            "recommended_weight_set_id": "score_focus_v1",
            "recommended_status": candidate_status,
        },
        "all_weight_sets": [
            {
                "weight_set_id": "baseline",
                "status": "baseline",
            },
            {
                "weight_set_id": "score_focus_v1",
                "status": candidate_status,
                "blockers": list(blockers or []),
                "review_flags": [],
                "baseline_delta": {
                    "mean_vp_differential_player1_minus_player2": 2.0,
                    "player1_win_count": 1,
                },
                "consistency": {"improved_count": 3, "worsened_count": 0},
            },
        ],
    }


def test_gate_weight_sets_pair_builtin_previous_baseline_with_promoted_artifact() -> None:
    mod = _load_script_module()

    gate_config, previous_id, promoted_id = mod.build_gate_weight_sets(
        promoted_artifact=_promoted_artifact(),
        previous_baseline_weight_set_id="baseline",
    )

    assert previous_id == "baseline"
    assert promoted_id == "score_focus_v1"
    assert [item["weight_set_id"] for item in gate_config["weight_sets"]] == ["baseline", "score_focus_v1"]
    assert gate_config["weight_sets"][0]["components"] == {}
    assert gate_config["weight_sets"][1]["component_weight_multipliers"]["movement_ranker"] == {
        "projected_score_delta_next_window": 1.25,
    }


def test_gate_weight_sets_reject_matching_baseline_and_promoted_ids() -> None:
    mod = _load_script_module()
    artifact = _promoted_artifact()
    artifact["weight_sets"][0]["weight_set_id"] = "baseline"

    with pytest.raises(ValueError, match="must differ"):
        mod.build_gate_weight_sets(
            promoted_artifact=artifact,
            previous_baseline_weight_set_id="baseline",
        )


def test_gate_report_passes_when_candidate_promotes_for_all_seeds(tmp_path) -> None:
    mod = _load_script_module()

    report = mod.build_gate_report(
        previous_weight_set_id="baseline",
        promoted_weight_set_id="score_focus_v1",
        seed_results=[
            {
                "seed": 101,
                "sweep_report_path": str(tmp_path / "seed_101" / "weight_sweep_report.json"),
                "analysis_path": str(tmp_path / "seed_101" / "weight_sweep_analysis.json"),
                "sweep_report": {"smoke_status": {"ui": "pass", "network": "pass", "snapshot": "pass"}},
                "analysis": _analysis(),
            },
            {
                "seed": 102,
                "sweep_report_path": str(tmp_path / "seed_102" / "weight_sweep_report.json"),
                "analysis_path": str(tmp_path / "seed_102" / "weight_sweep_analysis.json"),
                "sweep_report": {"smoke_status": {"ui": "pass", "network": "pass", "snapshot": "pass"}},
                "analysis": _analysis(),
            },
        ],
        dry_run=False,
        allow_not_run_smoke=False,
        weight_sets_path=tmp_path / "gate_weight_sets.json",
    )

    assert report["gate_status"] == "pass"
    assert report["seed_count"] == 2
    assert all(row["status"] == "pass" for row in report["seed_results"])


def test_gate_report_fails_on_blocker_or_missing_smoke(tmp_path) -> None:
    mod = _load_script_module()

    report = mod.build_gate_report(
        previous_weight_set_id="baseline",
        promoted_weight_set_id="score_focus_v1",
        seed_results=[
            {
                "seed": 101,
                "sweep_report": {"smoke_status": {"ui": "pass", "network": "not_run", "snapshot": "pass"}},
                "analysis": _analysis(blockers=["fallback_rate_regression"]),
            }
        ],
        dry_run=False,
        allow_not_run_smoke=False,
        weight_sets_path=tmp_path / "gate_weight_sets.json",
    )

    assert report["gate_status"] == "fail"
    assert report["seed_results"][0]["status"] == "fail"
    assert report["seed_results"][0]["smoke_passed"] is False
    assert report["seed_results"][0]["blockers"] == ["fallback_rate_regression"]


def test_gate_report_requires_all_smoke_keys_even_without_blockers(tmp_path) -> None:
    mod = _load_script_module()

    missing = mod.build_gate_report(
        previous_weight_set_id="baseline",
        promoted_weight_set_id="score_focus_v1",
        seed_results=[
            {
                "seed": 101,
                "sweep_report": {"smoke_status": {}},
                "analysis": _analysis(),
            }
        ],
        dry_run=False,
        allow_not_run_smoke=False,
        weight_sets_path=tmp_path / "gate_weight_sets.json",
    )
    relaxed = mod.build_gate_report(
        previous_weight_set_id="baseline",
        promoted_weight_set_id="score_focus_v1",
        seed_results=[
            {
                "seed": 102,
                "sweep_report": {"smoke_status": {"ui": "pass", "network": "not_run", "snapshot": "pass"}},
                "analysis": _analysis(),
            }
        ],
        dry_run=False,
        allow_not_run_smoke=True,
        weight_sets_path=tmp_path / "gate_weight_sets.json",
    )

    assert missing["gate_status"] == "fail"
    assert missing["seed_results"][0]["smoke_passed"] is False
    assert relaxed["gate_status"] == "pass"
    assert relaxed["seed_results"][0]["smoke_passed"] is True


def test_gate_cli_dry_run_writes_config_and_command_plan(tmp_path, monkeypatch) -> None:
    mod = _load_script_module()
    promoted_path = tmp_path / "promoted.json"
    output_dir = tmp_path / "gate"
    _write_json(promoted_path, _promoted_artifact())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_promoted_ranker_baseline_gate.py",
            "--promoted-artifact",
            str(promoted_path),
            "--output-dir",
            str(output_dir),
            "--seed",
            "101",
            "--seed",
            "102",
            "--dry-run",
        ],
    )

    assert mod.main() == 0
    gate_config = json.loads((output_dir / "gate_weight_sets.json").read_text(encoding="utf-8"))
    report = json.loads((output_dir / "promoted_baseline_gate_report.json").read_text(encoding="utf-8"))
    assert [item["weight_set_id"] for item in gate_config["weight_sets"]] == ["baseline", "score_focus_v1"]
    assert report["gate_status"] == "dry_run"
    assert [entry["seed"] for entry in report["command_plan"]] == [101, 102]
