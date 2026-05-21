from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_extract_ranker_training_rows_cli_outputs_rows_and_coverage(tmp_path) -> None:
    input_path = tmp_path / "records.json"
    rows_path = tmp_path / "rows.jsonl"
    coverage_path = tmp_path / "coverage.json"
    input_path.write_text(
        json.dumps(
            [
                {
                    "game_id": "game-1",
                    "global_seed": 2026052000,
                    "decision_seed": 2026052001,
                    "turn_id": 2,
                    "phase": "SHOOTING_PHASE",
                    "decision_id": "decision-1",
                    "decision_type": "DECLARE_SHOTS",
                    "request_context": {
                        "player_id": "player-1",
                        "unit_id": "unit-1",
                        "general_plan_id": "general:player-1",
                        "deployment_order_bundle_id": "deployment-orders:player-1",
                        "prebattle_order_bundle_id": "prebattle:player-1",
                        "commander_order_bundle_id": "commander:player-1",
                        "deployment_tempo_capability": {"has_scout": True, "has_infiltrate": False},
                        "commander_resource_authorizations": {"resource-1": {"status": "approved"}},
                    },
                    "candidates": [
                        {
                            "action_id": "candidate-1",
                            "params": {"unit_id": "unit-1"},
                            "metadata": {
                                "commander_alignment": {"role": "shoot"},
                                "resource_authorization_id": "resource-1",
                            },
                        },
                        {
                            "action_id": "candidate-2",
                            "params": {"unit_id": "unit-1"},
                            "metadata": {"fallback_mode": True},
                        },
                    ],
                    "mask": [True, False],
                    "chosen_action_id": "candidate-1",
                    "valid": True,
                    "outcome": {
                        "immediate_deltas": {
                            "actor_player_id": "player-1",
                            "score_delta": 1,
                            "wounds_inflicted": 2,
                            "target_destroyed": True,
                            "objective_control_delta": 1,
                        }
                    },
                }
            ],
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "extract_ranker_training_rows.py"),
            "--input",
            str(input_path),
            "--output-jsonl",
            str(rows_path),
            "--coverage-output",
            str(coverage_path),
            "--ui-smoke-status",
            "pass",
            "--network-smoke-status",
            "pass",
            "--snapshot-smoke-status",
            "pass",
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout
    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines()]
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))

    assert len(rows) == 2
    assert rows[0]["candidate_action_id"] == "candidate-1"
    assert rows[0]["chosen"] is True
    assert rows[0]["outcome_window"]["target_destroyed_next_phase"] is True
    assert coverage["decision_type_counts"] == {"DECLARE_SHOTS": 1}
    assert coverage["mask_ratio"]["legal_candidates"] == 1
    assert coverage["chosen_action_rank_under_current_ranker"]["rank_counts"] == {"1": 1}
    assert coverage["smoke_status"] == {"network": "pass", "snapshot": "pass", "ui": "pass"}


def test_extract_ranker_training_rows_cli_accepts_directory_inputs_and_reports_diagnostics(tmp_path) -> None:
    input_dir = tmp_path / "records"
    nested_dir = input_dir / "nested"
    nested_dir.mkdir(parents=True)
    rows_path = tmp_path / "rows.jsonl"
    coverage_path = tmp_path / "coverage.json"
    (input_dir / "ignore.txt").write_text("not json", encoding="utf-8")
    (input_dir / "snapshot.json").write_text(
        json.dumps(
            {
                "game_id": "not-a-decision-record",
                "decision_type": "SNAPSHOT_SHOULD_BE_IGNORED",
                "candidates": [{"action_id": "bad"}],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (input_dir / "alpha_records.json").write_text(
        json.dumps(
            [
                {
                    "game_id": "game-dir",
                    "global_seed": 101,
                    "turn_id": 1,
                    "phase": "MOVEMENT_PHASE",
                    "decision_id": "decision-dir-a",
                    "decision_type": "MOVE_UNIT",
                    "request_context": {
                        "player_id": "player-1",
                        "deployment_dirty_flags": {"status": "dirty", "terrain": True},
                        "deployment_candidate_tempo_capabilities": {
                            "unit-1": {"has_scout": True, "has_infiltrate": True}
                        },
                    },
                    "candidates": [
                        {
                            "action_id": "candidate-a1",
                            "params": {"unit_id": "unit-1"},
                            "metadata": {
                                "fallback_mode": True,
                                "resource_authorization_rejected": True,
                            },
                        },
                        {
                            "action_id": "candidate-a2",
                            "params": {"unit_id": "unit-1"},
                            "metadata": {},
                        },
                    ],
                    "mask": [False, True],
                    "chosen_action_id": "candidate-a2",
                }
            ],
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (nested_dir / "beta_records.jsonl").write_text(
        json.dumps(
            {
                "records": [
                    {
                        "game_id": "game-dir",
                        "global_seed": 101,
                        "turn_id": 1,
                        "phase": "COMMAND_PHASE",
                        "decision_id": "decision-dir-b",
                        "decision_type": "SELECT_OBJECTIVE",
                        "request_context": {"player_id": "player-2"},
                        "candidates": [],
                        "mask": [],
                    }
                ]
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "extract_ranker_training_rows.py"),
            "--input",
            str(input_dir),
            "--output-jsonl",
            str(rows_path),
            "--coverage-output",
            str(coverage_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout
    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines()]
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))

    assert len(rows) == 2
    assert rows[0]["legal"] is False
    assert rows[1]["chosen"] is True
    assert coverage["record_count"] == 2
    assert coverage["candidate_row_count"] == 2
    assert coverage["decision_type_counts"] == {"MOVE_UNIT": 1, "SELECT_OBJECTIVE": 1}
    assert coverage["candidate_count_distribution"]["buckets"] == {"0": 1, "2-4": 1}
    assert coverage["mask_ratio"] == {
        "legal_candidates": 1,
        "legal_ratio": 0.5,
        "masked_candidates": 1,
        "masked_ratio": 0.5,
        "total_candidates": 2,
    }
    assert coverage["chosen_action_rank_under_current_ranker"]["rank_counts"] == {"2": 1}
    assert coverage["commander_assignment_hit_fallback_rate"]["fallback_count"] == 1
    assert coverage["stale_plan_rate"] == {"records": 2, "stale_count": 1, "stale_rate": 0.5}
    assert coverage["resource_authorization_used_rejected"] == {"none": 1, "rejected": 1}
    assert coverage["deployment_tempo_usage"]["scout_hit_count"] == 2
    assert coverage["deployment_tempo_usage"]["infiltrate_hit_count"] == 2
