from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


def _load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "run_general_profile_eval.py"
    spec = importlib.util.spec_from_file_location("run_general_profile_eval_module", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load run_general_profile_eval.py for testing.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _records() -> list[dict]:
    return [
        {
            "game_id": "general_profile_eval:000000:seed:101",
            "global_seed": 101,
            "turn_id": 1,
            "phase": "MOVEMENT_PHASE",
            "decision_id": "decision-1",
            "decision_type": "MOVE_UNIT",
            "request_context": {
                "player_id": "player-1",
                "deployment_dirty_flags": {"status": "dirty", "terrain": True},
                "deployment_candidate_tempo_capabilities": {
                    "unit-1": {"has_scout": True, "has_infiltrate": False}
                },
                "commander_resource_authorizations": {"resource-1": {"status": "approved"}},
            },
            "candidates": [
                {
                    "action_id": "candidate-1",
                    "params": {"unit_id": "unit-1"},
                    "metadata": {
                        "fallback_mode": True,
                        "resource_authorization_id": "resource-1",
                    },
                },
                {
                    "action_id": "candidate-2",
                    "params": {"unit_id": "unit-1"},
                    "metadata": {"commander_alignment": {"role": "screen"}},
                },
            ],
            "mask": [False, True],
            "chosen_action_id": "candidate-2",
        }
    ]


def test_profile_matrix_report_summarizes_scores_and_ranker_coverage(tmp_path) -> None:
    mod = _load_script_module()
    player1_label, player2_label = mod.self_play._army_labels_from_paths(
        "army_lists/chaos_test.txt",
        "army_lists/aeldari_test.txt",
    )
    summaries = [
        {
            "profile_pair_id": "p1_01_alpha_vs_p2_02_beta",
            "seed": 101,
            "player1_profile_id": "alpha",
            "player2_profile_id": "beta",
            "player1_profile_index": 1,
            "player2_profile_index": 2,
            "winner_army_label": player1_label,
            "winner_score_line": "<SCORE: 20 vs 15>",
            "phase_steps": 7,
            "decision_record_count": 1,
            "scoreboard": {player1_label: 20, player2_label: 15},
            "records_path": str(tmp_path / "alpha_records.json"),
            "summary_path": str(tmp_path / "alpha_summary.json"),
        }
    ]

    report = mod._build_profile_matrix_report(
        summaries=summaries,
        records_by_profile_pair_id={"p1_01_alpha_vs_p2_02_beta": _records()},
        profiles_path=tmp_path / "profiles.json",
        player1_army="army_lists/chaos_test.txt",
        player2_army="army_lists/aeldari_test.txt",
        seed=101,
        decision_record_max=4096,
        pairing_mode="zip",
        smoke_status={"ui": "pass", "network": "pass", "snapshot": "pass"},
        ranker_rows_path=str(tmp_path / "rows.jsonl"),
        ranker_coverage_path=str(tmp_path / "coverage.json"),
    )

    assert report["profile_pair_count"] == 1
    assert report["aggregate"]["player1_win_count"] == 1
    assert report["aggregate"]["mean_vp_differential_player1_minus_player2"] == 5.0
    assert report["ranker_diagnostics"]["rows_path"] == str(tmp_path / "rows.jsonl")
    row = report["rows"][0]
    assert row["player1_result"] == "win"
    assert row["vp"] == {"differential_player1_minus_player2": 5, "player1": 20, "player2": 15}
    assert row["phase_count"] == 7
    assert row["decision_count"] == 1
    assert row["coverage"]["mask_ratio"]["masked_ratio"] == 0.5
    assert row["coverage"]["chosen_action_rank_under_current_ranker"]["rank_counts"] == {"2": 1}
    assert row["coverage"]["fallback_count"] == 1
    assert row["coverage"]["commander_assignment_hit_rate"] == 1.0
    assert row["coverage"]["stale_plan_rate"]["stale_rate"] == 1.0
    assert row["coverage"]["resource_authorization_usage"] == {"available": 1, "used": 1}
    assert row["coverage"]["deployment_tempo_usage"]["scout_hit_count"] == 2


def test_profile_eval_writes_ranker_diagnostics(tmp_path) -> None:
    mod = _load_script_module()
    rows_path = tmp_path / "ranker_rows.jsonl"
    coverage_path = tmp_path / "ranker_coverage.json"

    info = mod._write_ranker_diagnostics(
        records=_records(),
        rows_path=rows_path,
        coverage_path=coverage_path,
        smoke_status={"ui": "pass", "network": "not_run", "snapshot": "pass"},
    )

    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines()]
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    assert info["record_count"] == 1
    assert info["candidate_row_count"] == 2
    assert len(rows) == 2
    assert coverage["smoke_status"] == {"network": "not_run", "snapshot": "pass", "ui": "pass"}


def test_profile_eval_main_writes_matrix_and_ranker_outputs(monkeypatch, tmp_path) -> None:
    mod = _load_script_module()
    profiles_path = tmp_path / "profiles.json"
    output_dir = tmp_path / "eval"
    profiles_path.write_text(
        json.dumps(
            {
                "default_player1_army": "army_lists/chaos_test.txt",
                "default_player2_army": "army_lists/aeldari_test.txt",
                "default_seed": 101,
                "profiles": [
                    {"id": "alpha", "index": 1, "description": "Alpha"},
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    def fake_run_profile_game(**kwargs):
        assert kwargs["collect_records"] is True
        assert kwargs["write_records"] is False
        player1_label, player2_label = mod.self_play._army_labels_from_paths(
            str(kwargs["player1_army"]),
            str(kwargs["player2_army"]),
        )
        label = mod._profile_pair_label(kwargs["player1_profile"], kwargs["player2_profile"])
        summary = {
            "profile_pair_id": label,
            "seed": int(kwargs["seed"]),
            "player1_profile_id": "alpha",
            "player2_profile_id": "alpha",
            "player1_profile_index": 1,
            "player2_profile_index": 1,
            "winner_army_label": player2_label,
            "winner_score_line": "<SCORE: 11 vs 9>",
            "elapsed_seconds": 0.25,
            "phase_steps": 3,
            "decision_record_count": 1,
            "scoreboard": {player1_label: 9, player2_label: 11},
            "records_path": str(output_dir / f"{label}_records.json"),
            "summary_path": str(output_dir / f"{label}_summary.json"),
        }
        return summary, _records()

    monkeypatch.setattr(mod, "_run_profile_game", fake_run_profile_game)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_general_profile_eval.py",
            "--profiles",
            str(profiles_path),
            "--profile-id",
            "alpha",
            "--pairing-mode",
            "mirror",
            "--write-ranker-diagnostics",
            "--output-dir",
            str(output_dir),
            "--ui-smoke-status",
            "pass",
            "--network-smoke-status",
            "pass",
            "--snapshot-smoke-status",
            "pass",
        ],
    )

    mod.main()

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    matrix = json.loads((output_dir / "matrix_report.json").read_text(encoding="utf-8"))
    coverage = json.loads((output_dir / "ranker_training_coverage.json").read_text(encoding="utf-8"))
    rows = (output_dir / "ranker_training_rows.jsonl").read_text(encoding="utf-8").splitlines()

    assert summary["matrix_report_path"] == str((output_dir / "matrix_report.json").resolve())
    assert summary["ranker_diagnostics"]["record_count"] == 1
    assert matrix["pairing_mode"] == "mirror"
    assert matrix["aggregate"]["player2_win_count"] == 1
    assert matrix["rows"][0]["player2_result"] == "win"
    assert matrix["rows"][0]["vp"]["differential_player1_minus_player2"] == -2
    assert coverage["smoke_status"] == {"network": "pass", "snapshot": "pass", "ui": "pass"}
    assert len(rows) == 2
