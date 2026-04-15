from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from warhammer40k_ai.roster.muster_record import MusterRecord


def _record(
    *,
    rules_bundle_id: str,
    field_distribution_id: str,
    event_policy_id: str,
    policy_bundle_id: str,
    controller_bundle_id: str,
    army_blueprint_hash: str,
    build_capability_profile_id: str,
    faction: str,
    detachment_type: str,
) -> dict[str, object]:
    return MusterRecord(
        record_kind="evaluation",
        army_blueprint_hash=army_blueprint_hash,
        rules_bundle_id=rules_bundle_id,
        descriptor_bundle_id="descriptor_bundle:test",
        capability_schema_id="capability_schema:build_capability_v1",
        build_capability_profile_id=build_capability_profile_id,
        field_distribution_id=field_distribution_id,
        event_policy_id=event_policy_id,
        policy_bundle_id=policy_bundle_id,
        controller_bundle_id=controller_bundle_id,
        faction=faction,
        detachment_type=detachment_type,
        faction_tags=(faction,),
        detachment_tags=(detachment_type,),
        utility_terms={"score": 1.5},
        replay_gate_outcomes={
            "success": True,
            "replay_audit": {"passed": True},
            "manifest_gate": {"passed": True},
        },
    ).to_dict()


def test_build_mustering_manifest_cli_filters_and_summarizes_corpus(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    first_input = tmp_path / "records_a.json"
    second_input = tmp_path / "records_b.json"
    output_path = tmp_path / "mustering_manifest.json"
    first_input.write_text(
        json.dumps(
            [
                _record(
                    rules_bundle_id="rules_bundle:keep",
                    field_distribution_id="field_distribution:keep",
                    event_policy_id="event_policy:keep",
                    policy_bundle_id="policy_bundle:keep",
                    controller_bundle_id="policy_bundle:controller_keep",
                    army_blueprint_hash="army_blueprint:keep",
                    build_capability_profile_id="build_capability_profile:keep",
                    faction="Space Marines",
                    detachment_type="Gladius Task Force",
                )
            ],
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    second_input.write_text(
        json.dumps(
            {
                "records": [
                    _record(
                        rules_bundle_id="rules_bundle:drop",
                        field_distribution_id="field_distribution:drop",
                        event_policy_id="event_policy:drop",
                        policy_bundle_id="policy_bundle:drop",
                        controller_bundle_id="policy_bundle:controller_drop",
                        army_blueprint_hash="army_blueprint:drop",
                        build_capability_profile_id="build_capability_profile:drop",
                        faction="Aeldari",
                        detachment_type="Battle Host",
                    )
                ]
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    script_path = repo_root / "scripts" / "build_mustering_manifest.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--input",
        str(first_input),
        "--input",
        str(second_input),
        "--output",
        str(output_path),
        "--corpus-id",
        "mustering_corpus:test",
        "--source-tag",
        "mixed",
        "--rules-bundle-id",
        "rules_bundle:keep",
        "--field-distribution-id",
        "field_distribution:keep",
        "--event-policy-id",
        "event_policy:keep",
        "--policy-bundle-id",
        "policy_bundle:keep",
        "--controller-bundle-id",
        "policy_bundle:controller_keep",
        "--faction-tag",
        "Space Marines",
        "--detachment-tag",
        "Gladius Task Force",
        "--build-capability-profile-id",
        "build_capability_profile:keep",
    ]
    completed = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )

    assert completed.returncode == 0
    assert "Total records: 1" in completed.stdout
    manifest = json.loads(output_path.read_text(encoding="utf-8"))
    assert manifest["corpus_id"] == "mustering_corpus:test"
    assert manifest["source_tag"] == "mixed"
    assert manifest["total_records"] == 1
    assert manifest["rules_bundle_ids"] == ["rules_bundle:keep"]
    assert manifest["field_distribution_ids"] == ["field_distribution:keep"]
    assert manifest["event_policy_ids"] == ["event_policy:keep"]
    assert manifest["policy_bundle_ids"] == ["policy_bundle:keep"]
    assert manifest["controller_bundle_ids"] == ["policy_bundle:controller_keep"]
    assert manifest["utility_term_summary"]["score"]["mean"] == 1.5
    assert manifest["slice_filters"]["rules_bundle_ids"] == ["rules_bundle:keep"]
    assert manifest["slice_filters"]["faction_tags"] == ["Space Marines"]


def test_build_mustering_manifest_cli_rejects_unknown_record_schema(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    input_path = tmp_path / "records.json"
    output_path = tmp_path / "mustering_manifest.json"
    payload = _record(
        rules_bundle_id="rules_bundle:test",
        field_distribution_id="field_distribution:test",
        event_policy_id="event_policy:test",
        policy_bundle_id="policy_bundle:test",
        controller_bundle_id="policy_bundle:test",
        army_blueprint_hash="army_blueprint:test",
        build_capability_profile_id="build_capability_profile:test",
        faction="Space Marines",
        detachment_type="Gladius Task Force",
    )
    payload["muster_record_schema_id"] = "muster_record_schema:v2"
    input_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    script_path = repo_root / "scripts" / "build_mustering_manifest.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--corpus-id",
            "mustering_corpus:test",
            "--source-tag",
            "mixed",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )

    assert completed.returncode != 0
    assert "Unsupported muster_record_schema_id" in completed.stderr
