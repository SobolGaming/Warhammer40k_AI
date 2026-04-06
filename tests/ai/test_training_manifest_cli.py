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
        "game_id": "game:test",
        "rules_bundle_id": "rules_bundle:test",
        "descriptor_bundle_id": "descriptor_bundle:test",
        "relabel_status": "updated_under_target_rules_bundle",
        "omniscient_state": {
            "players": [
                {"player_id": "player:test:1", "score": 0},
                {"player_id": "player:test:2", "score": 0},
            ]
        },
        "descriptor_ids": {
            "mission_descriptor_id": "mission_descriptor:test",
            "objective_descriptor_ids": ["objective_descriptor:test"],
            "terrain_descriptor_ids": ["terrain_descriptor:test"],
            "deployment_descriptor_id": "deployment_descriptor:test",
            "army_build_descriptor_id": "army_build_descriptor:test",
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


def _baseline_profile_records(*, games: int, records_per_game: int) -> list[dict]:
    decision_types = [
        "MOVE_UNIT",
        "DECLARE_SHOTS",
        "DECLARE_CHARGE",
        "SELECT_UNIT",
        "SELECT_FIGHT_TARGETS",
    ]
    output: list[dict] = []
    counter = 0
    for game_idx in range(int(games)):
        game_id = f"game:{game_idx}"
        for step in range(int(records_per_game)):
            decision_type = decision_types[step % len(decision_types)]
            record = _record(f"d{counter}", decision_type)
            record["game_id"] = game_id
            record["omniscient_state"] = {
                "players": [
                    {"player_id": "player:test:1", "score": int(step // 50)},
                    {"player_id": "player:test:2", "score": int(step // 100)},
                ]
            }
            output.append(record)
            counter += 1
    return output


def test_build_training_manifest_cli_outputs_manifest(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
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
    repo_root = Path(__file__).resolve().parents[2]
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
    repo_root = Path(__file__).resolve().parents[2]
    input_path = tmp_path / "records.json"
    output_path = tmp_path / "manifest.json"
    input_path.write_text(
        json.dumps(_baseline_profile_records(games=20, records_per_game=500), indent=2, sort_keys=True),
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


def test_build_training_manifest_cli_filters_on_army_build_descriptor(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    input_path = tmp_path / "records.json"
    output_path = tmp_path / "manifest.json"
    keep = _record("d1", "MOVE_UNIT")
    keep["descriptor_bundle_id"] = "descriptor_bundle:keep"
    keep["descriptor_ids"]["army_build_descriptor_id"] = "army_build_descriptor:keep"
    drop = _record("d2", "DECLARE_SHOTS")
    drop["descriptor_bundle_id"] = "descriptor_bundle:drop"
    drop["descriptor_ids"]["army_build_descriptor_id"] = "army_build_descriptor:drop"
    input_path.write_text(
        json.dumps([keep, drop], indent=2, sort_keys=True),
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
        "--army-build-descriptor-id",
        "army_build_descriptor:keep",
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
    assert manifest["total_records"] == 1
    assert manifest["army_build_descriptor_ids"] == ["army_build_descriptor:keep"]
    assert manifest["slice_filters"]["army_build_descriptor_ids"] == ["army_build_descriptor:keep"]


def test_build_training_manifest_cli_accepts_all_descriptor_filters_together(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    input_path = tmp_path / "records.json"
    output_path = tmp_path / "manifest.json"

    keep = _record("d1", "MOVE_UNIT")
    keep["rules_bundle_id"] = "rules_bundle:keep"
    keep["descriptor_bundle_id"] = "descriptor_bundle:keep"
    keep["descriptor_ids"] = {
        "mission_descriptor_id": "mission_descriptor:keep",
        "objective_descriptor_ids": ["objective_descriptor:keep"],
        "terrain_descriptor_ids": ["terrain_descriptor:keep"],
        "deployment_descriptor_id": "deployment_descriptor:keep",
        "army_build_descriptor_id": "army_build_descriptor:keep",
        "tool_descriptor_ids": ["tool_descriptor:keep"],
    }

    drop = _record("d2", "DECLARE_SHOTS")
    drop["rules_bundle_id"] = "rules_bundle:drop"
    drop["descriptor_bundle_id"] = "descriptor_bundle:drop"
    drop["descriptor_ids"] = {
        "mission_descriptor_id": "mission_descriptor:drop",
        "objective_descriptor_ids": ["objective_descriptor:drop"],
        "terrain_descriptor_ids": ["terrain_descriptor:drop"],
        "deployment_descriptor_id": "deployment_descriptor:drop",
        "army_build_descriptor_id": "army_build_descriptor:drop",
        "tool_descriptor_ids": ["tool_descriptor:drop"],
    }

    input_path.write_text(
        json.dumps([keep, drop], indent=2, sort_keys=True),
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
        "--rules-bundle-id",
        "rules_bundle:keep",
        "--descriptor-bundle-id",
        "descriptor_bundle:keep",
        "--mission-descriptor-id",
        "mission_descriptor:keep",
        "--objective-descriptor-id",
        "objective_descriptor:keep",
        "--terrain-descriptor-id",
        "terrain_descriptor:keep",
        "--deployment-descriptor-id",
        "deployment_descriptor:keep",
        "--army-build-descriptor-id",
        "army_build_descriptor:keep",
        "--tool-descriptor-id",
        "tool_descriptor:keep",
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
    assert manifest["total_records"] == 1
    assert manifest["rules_bundle_ids"] == ["rules_bundle:keep"]
    assert manifest["descriptor_bundle_ids"] == ["descriptor_bundle:keep"]
    assert manifest["mission_descriptor_ids"] == ["mission_descriptor:keep"]
    assert manifest["objective_descriptor_ids"] == ["objective_descriptor:keep"]
    assert manifest["terrain_descriptor_ids"] == ["terrain_descriptor:keep"]
    assert manifest["deployment_descriptor_ids"] == ["deployment_descriptor:keep"]
    assert manifest["army_build_descriptor_ids"] == ["army_build_descriptor:keep"]
    assert manifest["tool_descriptor_ids"] == ["tool_descriptor:keep"]
    assert manifest["slice_filters"] == {
        "rules_bundle_ids": ["rules_bundle:keep"],
        "descriptor_bundle_ids": ["descriptor_bundle:keep"],
        "mission_descriptor_ids": ["mission_descriptor:keep"],
        "objective_descriptor_ids": ["objective_descriptor:keep"],
        "terrain_descriptor_ids": ["terrain_descriptor:keep"],
        "deployment_descriptor_ids": ["deployment_descriptor:keep"],
        "army_build_descriptor_ids": ["army_build_descriptor:keep"],
        "tool_descriptor_ids": ["tool_descriptor:keep"],
    }
