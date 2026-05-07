from __future__ import annotations

from warhammer40k_ai.engine.training_manifest import (
    PRE_ML_BASELINE_GATE_PROFILE_ID,
    build_training_manifest,
    build_training_manifest_from_records,
    filter_training_records,
    validate_gate_profile_compliance,
    validate_training_manifest,
)


def _record(decision_id: str, decision_type: str, *, relabel_status: str = "updated_under_target_rules_bundle") -> dict:
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
        "reserve_denial_delta": 0.0,
        "screen_integrity_delta": 0.0,
        "countercharge_coverage_delta": 0.0,
        "aura_connectivity_delta": 0.0,
        "projected_exposure_delta_if_enemy_goes_first": 0.0,
        "projected_melee_staging_delta": 0.0,
        "rules_provenance_refs": ["rules_bundle:test"],
    }
    return {
        "decision_id": decision_id,
        "decision_type": decision_type,
        "game_id": "game:test",
        "rules_bundle_id": "rules_bundle:test",
        "descriptor_bundle_id": "descriptor_bundle:test",
        "relabel_status": relabel_status,
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
    assert manifest["gate_requirements"]["gate_profile_id"] == PRE_ML_BASELINE_GATE_PROFILE_ID
    assert manifest["coverage"]["records_with_semantic_candidate_metadata"] == 3
    assert manifest["coverage"]["records_with_relabel_status"] == 3
    assert validate_training_manifest(manifest) == []


def test_streaming_training_manifest_matches_list_builder() -> None:
    records = [
        _record("d1", "MOVE_UNIT"),
        _record("d2", "DECLARE_SHOTS"),
        _record("d3", "SCOUT_MOVE"),
    ]
    list_manifest = build_training_manifest(records, source_tag="self_play", min_tier3_records=2).to_dict()
    stream_manifest = build_training_manifest_from_records(
        (dict(record) for record in records),
        source_tag="self_play",
        min_tier3_records=2,
    ).to_dict()

    list_manifest.pop("generated_at_utc", None)
    stream_manifest.pop("generated_at_utc", None)
    assert stream_manifest == list_manifest


def test_validate_training_manifest_detects_total_count_mismatch() -> None:
    records = [_record("d1", "MOVE_UNIT")]
    manifest = build_training_manifest(records, source_tag="heuristic", min_tier3_records=10).to_dict()
    manifest["total_records"] = 2
    errors = validate_training_manifest(manifest)
    assert any("total_records mismatch" in err for err in errors)


def test_validate_gate_profile_compliance_fails_when_canonical_thresholds_are_not_met() -> None:
    records = [_record("d1", "MOVE_UNIT")]
    manifest = build_training_manifest(records, source_tag="human", min_tier3_records=1).to_dict()
    failures = validate_gate_profile_compliance(manifest)
    assert any("minimum Tier3 record threshold" in failure for failure in failures)
    assert any("aggregate check did not pass" in failure for failure in failures)


def test_validate_gate_profile_compliance_passes_with_full_baseline_dataset() -> None:
    records = _baseline_profile_records(games=20, records_per_game=500)
    manifest = build_training_manifest(records, source_tag="self_play", min_tier3_records=10000).to_dict()
    assert manifest["gate_requirements"]["meets_gate_profile"] is True
    assert validate_gate_profile_compliance(manifest) == []


def test_build_training_manifest_tracks_deployment_surface_coverage() -> None:
    deployment_move = _record("d5", "MOVE_UNIT")
    deployment_move["context"] = {"placement_kind": "deployment"}
    records = [
        _record("d1", "CHOOSE_DEPLOYMENT_ZONE"),
        _record("d2", "DECLARE_RESERVES"),
        _record("d3", "SELECT_NEXT_DEPLOY_UNIT"),
        _record("d4", "SCOUT_MOVE"),
        deployment_move,
    ]
    manifest = build_training_manifest(records, source_tag="heuristic", min_tier3_records=1).to_dict()
    coverage = dict(manifest.get("coverage", {}) or {})
    assert int(coverage.get("deployment_related_records", 0) or 0) == 5
    assert int(coverage.get("deployment_zone_choice_records", 0) or 0) == 1
    assert int(coverage.get("declare_reserves_records", 0) or 0) == 1
    assert int(coverage.get("select_next_deploy_unit_records", 0) or 0) == 1
    assert int(coverage.get("scout_move_records", 0) or 0) == 1
    assert int(coverage.get("deployment_move_records", 0) or 0) == 1
    assert float(coverage.get("deployment_semantic_metadata_ratio", 0.0) or 0.0) == 1.0
    gate = dict(manifest.get("gate_requirements", {}) or {})
    assert bool(gate.get("meets_required_deployment_semantic_metadata_ratio", False)) is True


def test_build_training_manifest_lists_descriptor_family_ids_and_slice_filters() -> None:
    record = _record("d1", "MOVE_UNIT")
    manifest = build_training_manifest(
        [record],
        source_tag="human",
        min_tier3_records=1,
        rules_bundle_ids=["rules_bundle:test"],
        army_build_descriptor_ids=["army_build_descriptor:test"],
    ).to_dict()

    assert manifest["descriptor_bundle_ids"] == ["descriptor_bundle:test"]
    assert manifest["mission_descriptor_ids"] == ["mission_descriptor:test"]
    assert manifest["objective_descriptor_ids"] == ["objective_descriptor:test"]
    assert manifest["terrain_descriptor_ids"] == ["terrain_descriptor:test"]
    assert manifest["deployment_descriptor_ids"] == ["deployment_descriptor:test"]
    assert manifest["army_build_descriptor_ids"] == ["army_build_descriptor:test"]
    assert manifest["tool_descriptor_ids"] == ["tool_descriptor:test"]
    assert manifest["slice_filters"] == {
        "rules_bundle_ids": ["rules_bundle:test"],
        "descriptor_bundle_ids": [],
        "mission_descriptor_ids": [],
        "objective_descriptor_ids": [],
        "terrain_descriptor_ids": [],
        "deployment_descriptor_ids": [],
        "army_build_descriptor_ids": ["army_build_descriptor:test"],
        "tool_descriptor_ids": [],
    }


def test_filter_training_records_can_filter_on_army_build_and_tool_descriptors() -> None:
    keep = _record("d1", "MOVE_UNIT")
    keep["descriptor_bundle_id"] = "descriptor_bundle:keep"
    keep["descriptor_ids"]["army_build_descriptor_id"] = "army_build_descriptor:keep"
    keep["descriptor_ids"]["tool_descriptor_ids"] = ["tool_descriptor:keep", "tool_descriptor:shared"]

    drop = _record("d2", "DECLARE_SHOTS")
    drop["descriptor_bundle_id"] = "descriptor_bundle:drop"
    drop["descriptor_ids"]["army_build_descriptor_id"] = "army_build_descriptor:drop"
    drop["descriptor_ids"]["tool_descriptor_ids"] = ["tool_descriptor:drop"]

    filtered, slice_filters = filter_training_records(
        [keep, drop],
        army_build_descriptor_ids=["army_build_descriptor:keep"],
        tool_descriptor_ids=["tool_descriptor:shared"],
    )

    assert [record["decision_id"] for record in filtered] == ["d1"]
    assert slice_filters.to_dict() == {
        "rules_bundle_ids": [],
        "descriptor_bundle_ids": [],
        "mission_descriptor_ids": [],
        "objective_descriptor_ids": [],
        "terrain_descriptor_ids": [],
        "deployment_descriptor_ids": [],
        "army_build_descriptor_ids": ["army_build_descriptor:keep"],
        "tool_descriptor_ids": ["tool_descriptor:shared"],
    }
