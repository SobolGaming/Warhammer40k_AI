from __future__ import annotations

from warhammer40k_ai.engine.training_manifest import (
    build_training_manifest,
    validate_training_manifest,
)


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


def test_build_training_manifest_counts_records_and_decision_types() -> None:
    records = [
        _record("d1", "MOVE_UNIT"),
        _record("d2", "DECLARE_SHOTS"),
        _record("d3", "MOVE_UNIT"),
    ]
    manifest = build_training_manifest(records, source_tag="human", min_tier3_records=2).to_dict()

    assert manifest["total_records"] == 3
    assert manifest["decision_type_counts"]["MOVE_UNIT"] == 2
    assert manifest["decision_type_counts"]["DECLARE_SHOTS"] == 1
    assert manifest["gate_requirements"]["meets_minimum_tier3_pretraining_records"] is True
    assert manifest["coverage"]["records_with_semantic_candidate_metadata"] == 3
    assert validate_training_manifest(manifest) == []


def test_validate_training_manifest_detects_total_count_mismatch() -> None:
    records = [_record("d1", "MOVE_UNIT")]
    manifest = build_training_manifest(records, source_tag="heuristic", min_tier3_records=10).to_dict()
    manifest["total_records"] = 2
    errors = validate_training_manifest(manifest)
    assert any("total_records mismatch" in err for err in errors)
