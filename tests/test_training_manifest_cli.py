from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def _record(decision_id: str, decision_type: str) -> dict:
    metadata = {
        "projected_score_delta_next_window": 0.0,
        "projected_score_delta_round": 0.0,
        "projected_deny_delta_next_window": 0.0,
        "projected_control_delta": 0.0,
        "projected_action_enablement_delta": 0.0,
        "projected_exposure_delta": 0.0,
        "projected_trade_ev": 0.0,
        "cover_delta": 0.0,
        "los_delta": 0.0,
        "resource_delta": 0.0,
        "rules_provenance_refs": ["rules_bundle:test"],
    }
    return {
        "decision_id": decision_id,
        "decision_type": decision_type,
        "rules_bundle_id": "rules_bundle:test",
        "relabel_status": "updated_under_target_rules_bundle",
        "descriptor_ids": {
            "mission_descriptor_id": "mission_descriptor:test",
            "objective_descriptor_ids": ["objective_descriptor:test"],
            "terrain_descriptor_ids": ["terrain_descriptor:test"],
            "deployment_descriptor_id": "deployment_descriptor:test",
            "tool_descriptor_ids": ["tool_descriptor:test"],
        },
        "candidates": [
            {
                "action_id": f"{decision_id}:a",
                "params": {},
                "metadata": metadata,
            }
        ],
    }


def test_build_training_manifest_cli_outputs_manifest(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    input_path = tmp_path / "records.json"
    output_path = tmp_path / "manifest.json"
    input_path.write_text(
        json.dumps([_record("d1", "MOVE_UNIT"), _record("d2", "DECLARE_SHOTS")], indent=2, sort_keys=True),
        encoding="utf-8",
    )

    script_path = repo_root / "scripts" / "build_training_manifest.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--source-tag",
        "mixed",
        "--min-tier3-records",
        "1",
    ]
    completed = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    assert completed.returncode == 0
    manifest = json.loads(output_path.read_text(encoding="utf-8"))
    assert manifest["source_tag"] == "mixed"
    assert manifest["total_records"] == 2
    assert manifest["gate_requirements"]["meets_minimum_tier3_pretraining_records"] is True
    assert manifest["gate_requirements"]["gate_profile_id"] == "pre_ml_baseline_v1"


def test_build_training_manifest_cli_enforce_gate_profile_fails_for_small_dataset(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    input_path = tmp_path / "records.json"
    output_path = tmp_path / "manifest.json"
    input_path.write_text(
        json.dumps([_record("d1", "MOVE_UNIT"), _record("d2", "DECLARE_SHOTS")], indent=2, sort_keys=True),
        encoding="utf-8",
    )

    script_path = repo_root / "scripts" / "build_training_manifest.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--source-tag",
        "mixed",
        "--enforce-gate-profile",
    ]
    completed = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    assert completed.returncode != 0
    assert "Gate profile enforcement failed" in completed.stderr


def test_build_training_manifest_cli_enforce_gate_profile_passes_for_baseline_dataset(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    input_path = tmp_path / "records.json"
    output_path = tmp_path / "manifest.json"
    input_path.write_text(
        json.dumps([_record(f"d{idx}", "MOVE_UNIT") for idx in range(10000)], indent=2, sort_keys=True),
        encoding="utf-8",
    )

    script_path = repo_root / "scripts" / "build_training_manifest.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--source-tag",
        "self_play",
        "--enforce-gate-profile",
    ]
    completed = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    assert completed.returncode == 0
    manifest = json.loads(output_path.read_text(encoding="utf-8"))
    assert manifest["gate_requirements"]["meets_gate_profile"] is True
