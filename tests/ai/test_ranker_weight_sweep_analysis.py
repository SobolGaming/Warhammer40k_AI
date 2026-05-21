from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


def _load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "analyze_ranker_weight_sweep.py"
    spec = importlib.util.spec_from_file_location("analyze_ranker_weight_sweep_module", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load analyze_ranker_weight_sweep.py for testing.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _matrix(path: Path, values: dict[str, float]) -> str:
    _write_json(
        path,
        {
            "rows": [
                {
                    "profile_pair_id": pair_id,
                    "vp": {"differential_player1_minus_player2": vp_delta},
                }
                for pair_id, vp_delta in sorted(values.items())
            ]
        },
    )
    return str(path)


def _row(
    weight_set_id: str,
    *,
    matrix_path: str,
    mean_vp: float,
    wins: int,
    fallback_rate: float,
    commander_hit_rate: float,
    stale_rate: float,
    resource_used: int,
    context_mean: float,
    context_p90: float,
    decisions: int = 100,
    phases: int = 10,
) -> dict:
    return {
        "weight_set_id": weight_set_id,
        "description": weight_set_id,
        "mean_vp_differential_player1_minus_player2": mean_vp,
        "player1_win_count": wins,
        "player2_win_count": 0,
        "tie_count": 0,
        "total_decision_count": decisions,
        "total_phase_count": phases,
        "fallback_rate": fallback_rate,
        "commander_assignment_hit_rate": commander_hit_rate,
        "stale_plan_rate": stale_rate,
        "resource_authorization_usage": {"used": resource_used},
        "deployment_tempo_usage": {"scout_hit_count": 1},
        "chosen_action_rank_under_current_ranker": {"rank_counts": {"1": 2}},
        "context_payload_byte_distribution": {
            "count": decisions,
            "mean": context_mean,
            "p90": context_p90,
            "max": context_p90 + 250,
        },
        "smoke_status": {"ui": "pass", "network": "pass", "snapshot": "pass"},
        "matrix_report_path": matrix_path,
        "ranker_rows_path": "",
        "ranker_coverage_path": "",
    }


def test_weight_sweep_analysis_ranks_and_promotes_consistent_candidate(tmp_path) -> None:
    mod = _load_script_module()
    baseline_matrix = _matrix(tmp_path / "baseline" / "matrix_report.json", {"pair-a": 0, "pair-b": 0})
    good_matrix = _matrix(tmp_path / "good" / "matrix_report.json", {"pair-a": 2, "pair-b": 3})
    lucky_matrix = _matrix(tmp_path / "lucky" / "matrix_report.json", {"pair-a": 7, "pair-b": -1})
    regressed_matrix = _matrix(tmp_path / "regressed" / "matrix_report.json", {"pair-a": 4, "pair-b": 4})
    sweep = {
        "baseline_weight_set_id": "baseline",
        "rows": [
            _row(
                "baseline",
                matrix_path=baseline_matrix,
                mean_vp=0.0,
                wins=1,
                fallback_rate=0.10,
                commander_hit_rate=0.50,
                stale_rate=0.10,
                resource_used=10,
                context_mean=1000,
                context_p90=2000,
            ),
            _row(
                "good",
                matrix_path=good_matrix,
                mean_vp=2.5,
                wins=2,
                fallback_rate=0.09,
                commander_hit_rate=0.56,
                stale_rate=0.08,
                resource_used=11,
                context_mean=1050,
                context_p90=2100,
                decisions=102,
                phases=10,
            ),
            _row(
                "lucky",
                matrix_path=lucky_matrix,
                mean_vp=3.0,
                wins=2,
                fallback_rate=0.08,
                commander_hit_rate=0.55,
                stale_rate=0.08,
                resource_used=10,
                context_mean=1000,
                context_p90=2050,
            ),
            _row(
                "regressed",
                matrix_path=regressed_matrix,
                mean_vp=4.0,
                wins=2,
                fallback_rate=0.16,
                commander_hit_rate=0.40,
                stale_rate=0.16,
                resource_used=20,
                context_mean=3000,
                context_p90=6000,
                decisions=140,
                phases=14,
            ),
        ],
    }
    args = mod._build_parser().parse_args([])
    report = mod.build_analysis_report(sweep, args=args, input_path=tmp_path / "weight_sweep_report.json")
    by_id = {row["weight_set_id"]: row for row in report["all_weight_sets"]}

    assert report["summary"]["recommended_weight_set_id"] == "good"
    assert report["summary"]["recommended_status"] == "promote_candidate"
    assert by_id["good"]["status"] == "promote_candidate"
    assert by_id["good"]["baseline_delta"]["mean_vp_differential_player1_minus_player2"] == 2.5
    assert by_id["good"]["consistency"]["improved_count"] == 2
    assert by_id["lucky"]["status"] == "reject"
    assert "improvement_concentrated_in_one_matchup" in by_id["lucky"]["blockers"]
    assert by_id["regressed"]["status"] == "reject"
    assert "fallback_rate_regression" in by_id["regressed"]["blockers"]
    assert by_id["regressed"]["resource_usage_anomalies"][0]["reason"] == "resource_usage_shift"
    assert report["metric_leaders"]["best_vp_differential"] == "regressed"
    assert report["metric_leaders"]["lowest_fallback_rate"] == "lucky"


def test_weight_sweep_analysis_cli_writes_report(tmp_path, monkeypatch) -> None:
    mod = _load_script_module()
    baseline_matrix = _matrix(tmp_path / "baseline" / "matrix_report.json", {"pair-a": 0, "pair-b": 0})
    candidate_matrix = _matrix(tmp_path / "candidate" / "matrix_report.json", {"pair-a": 1, "pair-b": 1})
    sweep_path = tmp_path / "weight_sweep_report.json"
    output_path = tmp_path / "analysis.json"
    _write_json(
        sweep_path,
        {
            "baseline_weight_set_id": "baseline",
            "rows": [
                _row(
                    "baseline",
                    matrix_path=baseline_matrix,
                    mean_vp=0,
                    wins=1,
                    fallback_rate=0.1,
                    commander_hit_rate=0.5,
                    stale_rate=0.1,
                    resource_used=10,
                    context_mean=1000,
                    context_p90=2000,
                ),
                _row(
                    "candidate",
                    matrix_path=candidate_matrix,
                    mean_vp=1,
                    wins=2,
                    fallback_rate=0.1,
                    commander_hit_rate=0.52,
                    stale_rate=0.1,
                    resource_used=10,
                    context_mean=1000,
                    context_p90=2000,
                ),
            ],
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "analyze_ranker_weight_sweep.py",
            "--input",
            str(sweep_path),
            "--output",
            str(output_path),
        ],
    )

    assert mod.main() == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["summary"]["recommended_weight_set_id"] == "candidate"
    assert report["promotion_candidates"] == ["candidate"]
