from __future__ import annotations

from warhammer40k_ai.roster.army_build import ArmyBlueprint, DetachmentSelection, RosterEntry
from warhammer40k_ai.roster.muster_manifest import (
    build_mustering_manifest,
    validate_mustering_manifest,
)
from warhammer40k_ai.roster.muster_record import (
    MusterRecord,
    muster_records_from_search_report,
    validate_muster_record,
)


def _muster_record(
    *,
    record_kind: str = "evaluation",
    rules_bundle_id: str = "rules_bundle:keep",
    field_distribution_id: str = "field_distribution:keep",
    event_policy_id: str = "event_policy:keep",
    policy_bundle_id: str = "policy_bundle:keep",
    controller_bundle_id: str = "policy_bundle:controller_keep",
    army_blueprint_hash: str = "army_blueprint:keep",
    build_capability_profile_id: str = "build_capability_profile:keep",
    faction: str = "Space Marines",
    detachment_type: str = "Gladius Task Force",
) -> MusterRecord:
    return MusterRecord(
        record_kind=record_kind,
        army_blueprint_hash=army_blueprint_hash,
        rules_bundle_id=rules_bundle_id,
        descriptor_bundle_id="descriptor_bundle:keep",
        capability_schema_id="capability_schema:build_capability_v1",
        build_capability_profile_id=build_capability_profile_id,
        field_distribution_id=field_distribution_id,
        event_policy_id=event_policy_id,
        policy_bundle_id=policy_bundle_id,
        controller_bundle_id=controller_bundle_id,
        faction=faction,
        detachment_type=detachment_type,
        faction_tags=(faction, "Imperium"),
        detachment_tags=(detachment_type,),
        utility_terms={
            "score": 3.0,
            "components": {
                "mobility": 1.0,
                "durability": 2.0,
            },
        },
        replay_gate_outcomes={
            "success": True,
            "replay_audit": {"passed": True},
            "manifest_gate": {"passed": True},
        },
        search_edit_sequence=(
            {
                "action_id": "roster_edit:add_intercessors",
                "action_type": "add_unit",
            },
        ),
        provenance={
            "git_commit": "0123456789abcdef0123456789abcdef01234567",
            "evaluation_mode": "headless_fixed",
        },
        descriptor_provenance={
            "rules_bundle_id": rules_bundle_id,
            "descriptor_bundle_id": "descriptor_bundle:keep",
        },
        report_paths={"report_dir": "/tmp/report"},
    )


def test_muster_record_round_trips_and_validates_schema_version() -> None:
    record = _muster_record()
    payload = record.to_dict()

    assert validate_muster_record(payload) == []
    assert MusterRecord.from_dict(payload).to_dict() == payload

    payload["muster_record_version"] = "2.0.0"
    errors = validate_muster_record(payload)
    assert errors
    assert "Unsupported muster_record_version" in errors[0]


def test_build_mustering_manifest_filters_and_summarizes_slice() -> None:
    keep = _muster_record(record_kind="search_candidate")
    drop = _muster_record(
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

    manifest = build_mustering_manifest(
        [keep, drop],
        corpus_id="mustering_corpus:test",
        source_tag="mixed",
        rules_bundle_ids=["rules_bundle:keep"],
        capability_schema_ids=["capability_schema:build_capability_v1"],
        field_distribution_ids=["field_distribution:keep"],
        event_policy_ids=["event_policy:keep"],
        policy_bundle_ids=["policy_bundle:keep"],
        controller_bundle_ids=["policy_bundle:controller_keep"],
        faction_tags=["Imperium"],
        detachment_tags=["Gladius Task Force"],
        record_kinds=["search_candidate"],
        build_capability_profile_ids=["build_capability_profile:keep"],
    ).to_dict()

    assert validate_mustering_manifest(manifest) == []
    assert manifest["total_records"] == 1
    assert manifest["record_kind_counts"] == {"search_candidate": 1}
    assert manifest["rules_bundle_ids"] == ["rules_bundle:keep"]
    assert manifest["field_distribution_ids"] == ["field_distribution:keep"]
    assert manifest["event_policy_ids"] == ["event_policy:keep"]
    assert manifest["policy_bundle_ids"] == ["policy_bundle:keep"]
    assert manifest["controller_bundle_ids"] == ["policy_bundle:controller_keep"]
    assert manifest["faction_tags"] == ["Imperium", "Space Marines"]
    assert manifest["utility_term_summary"]["score"]["mean"] == 3.0
    assert manifest["utility_term_summary"]["components.mobility"]["count"] == 1
    assert manifest["outcome_summary"]["success_ratio"] == 1.0
    assert manifest["outcome_summary"]["replay_passed_ratio"] == 1.0
    assert manifest["outcome_summary"]["gate_passed_ratio"] == 1.0
    assert manifest["search_summary"]["total_search_edit_count"] == 1
    assert manifest["search_summary"]["edit_action_type_counts"] == {"add_unit": 1}
    assert manifest["provenance_summary"]["git_commits"] == [
        "0123456789abcdef0123456789abcdef01234567"
    ]
    assert manifest["slice_filters"]["faction_tags"] == ["Imperium"]


def test_build_mustering_manifest_preserves_duplicate_record_id_cardinality() -> None:
    first = _muster_record()
    second = _muster_record()
    assert first.record_id == second.record_id

    manifest = build_mustering_manifest(
        [first, second],
        corpus_id="mustering_corpus:test",
        source_tag="mixed",
    ).to_dict()

    assert validate_mustering_manifest(manifest) == []
    assert manifest["total_records"] == 2
    assert manifest["record_ids"] == [first.record_id, second.record_id]
    assert manifest["record_kind_counts"] == {"evaluation": 2}
    assert manifest["utility_term_summary"]["score"]["count"] == 2


def test_mustering_manifest_validation_rejects_schema_changes() -> None:
    manifest = build_mustering_manifest(
        [_muster_record()],
        corpus_id="mustering_corpus:test",
        source_tag="mixed",
    ).to_dict()

    manifest["mustering_manifest_schema_id"] = "mustering_manifest_schema:v2"
    errors = validate_mustering_manifest(manifest)
    assert errors
    assert "mustering_manifest_schema_id" in errors[0]


def test_search_report_candidates_convert_to_muster_records_with_edit_trace() -> None:
    blueprint = ArmyBlueprint(
        faction="Space Marines",
        detachments=(
            DetachmentSelection(
                selection_id="det_gladius",
                detachment_type="Gladius Task Force",
            ),
            DetachmentSelection(
                selection_id="det_anvil",
                detachment_type="Anvil Siege Force",
                metadata={"detachment_tags": ["Heavy Infantry"]},
            ),
        ),
        unit_entries=(
            RosterEntry(
                entry_id="entry_intercessors",
                name="Intercessor Squad",
                count=5,
                detachment_selection_id="det_gladius",
            ),
        ),
    )
    search_report = {
        "strategy": "local",
        "random_seed": 17,
        "top_candidates": [
            {
                "candidate_id": "candidate:1",
                "army_blueprint_hash": blueprint.army_blueprint_hash,
                "army_blueprint": blueprint.to_dict(),
                "score": 4.25,
                "utility_decomposition": {"score": 4.25},
                "edit_trace": [
                    {
                        "action_id": "roster_edit:set_warlord",
                        "action_type": "select_warlord",
                    }
                ],
                "evaluation_summary": {
                    "capability_schema_id": "capability_schema:build_capability_v1",
                    "build_capability_profile_id": "build_capability_profile:search",
                },
                "validation_summary": {"valid": True},
            }
        ],
    }

    records = muster_records_from_search_report(
        search_report,
        rules_bundle_id="rules_bundle:search",
        capability_schema_id="capability_schema:build_capability_v1",
        field_distribution_id="field_distribution:search",
        event_policy_id="event_policy:search",
        policy_bundle_id="policy_bundle:search",
        descriptor_bundle_id="descriptor_bundle:search",
    )

    assert len(records) == 1
    record = records[0].to_dict()
    assert validate_muster_record(record) == []
    assert record["record_kind"] == "search_candidate"
    assert record["army_blueprint_hash"] == blueprint.army_blueprint_hash
    assert record["utility_terms"] == {"score": 4.25}
    assert record["search_edit_sequence"][0]["action_type"] == "select_warlord"
    assert record["provenance"]["strategy"] == "local"
    assert record["detachment_tags"] == [
        "Anvil Siege Force",
        "Gladius Task Force",
        "Heavy Infantry",
    ]
