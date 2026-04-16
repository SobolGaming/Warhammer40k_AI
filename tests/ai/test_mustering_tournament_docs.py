from __future__ import annotations

import json
from pathlib import Path
import re

from warhammer40k_ai.roster.event_policy import (
    chapter_approved_10e_event_policy,
    preview_new40k_event_policy,
)
from warhammer40k_ai.roster.muster_manifest import validate_mustering_manifest
from warhammer40k_ai.roster.muster_record import MusterRecord, validate_muster_record
from warhammer40k_ai.roster.tournament_field import TournamentFieldDistribution


DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
REGISTRY_DOC = DOCS_DIR / "ML_ARTIFACT_REGISTRY.md"
ARCHITECTURE_DOC = DOCS_DIR / "AI_MUSTERING_TOURNAMENT_ARCHITECTURE.md"
OBJECTIVE_DOC = DOCS_DIR / "TOURNAMENT_EVALUATION_OBJECTIVE.md"
BUILD_CAPABILITY_DOC = DOCS_DIR / "BUILD_CAPABILITY_SCHEMA.md"
TOURNAMENT_FIELD_DOC = DOCS_DIR / "TOURNAMENT_FIELD_SCHEMA.md"
EVALUATION_PIPELINE_DOC = DOCS_DIR / "TOURNAMENT_EVALUATION_PIPELINE.md"
ROSTER_SEARCH_DOC = DOCS_DIR / "ROSTER_SEARCH.md"
MUSTERING_DATA_DOC = DOCS_DIR / "MUSTERING_DATA_SPEC.md"
ROSTER_SYNTHESIS_DOC = DOCS_DIR / "ROSTER_SYNTHESIS.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_json_block(markdown: str, heading: str) -> dict[str, object]:
    pattern = re.compile(
        rf"## {re.escape(heading)}\s+```json\n(.*?)\n```",
        re.DOTALL,
    )
    match = pattern.search(markdown)
    if match is None:
        raise AssertionError(f"Missing JSON example for heading: {heading}")
    return json.loads(match.group(1))


def test_pr_muster_001_docs_exist() -> None:
    assert REGISTRY_DOC.is_file()
    assert ARCHITECTURE_DOC.is_file()
    assert OBJECTIVE_DOC.is_file()
    assert EVALUATION_PIPELINE_DOC.is_file()
    assert ROSTER_SEARCH_DOC.is_file()
    assert MUSTERING_DATA_DOC.is_file()
    assert ROSTER_SYNTHESIS_DOC.is_file()


def test_build_capability_schema_doc_exists_and_locks_portable_schema() -> None:
    assert BUILD_CAPABILITY_DOC.is_file()
    text = _read(BUILD_CAPABILITY_DOC)

    schema = _extract_json_block(text, "Example Build Capability Schema")
    preview_schema = _extract_json_block(text, "Example Preview Combat Capability Schema")

    assert schema["capability_schema_id"] == "capability_schema:build_capability_v1"
    assert schema["aggregate_count_names"] == [
        "unit_count",
        "detachment_count",
        "enhancement_count",
        "attachment_binding_count",
        "leader_binding_count",
        "support_binding_count",
        "battleline_unit_count",
        "character_unit_count",
        "vehicle_or_monster_unit_count",
        "towering_unit_count",
        "titanic_unit_count",
        "deep_strike_unit_count",
        "infiltrator_unit_count",
        "scout_unit_count",
        "attachment_capable_unit_count",
    ]
    feature_names = [feature["name"] for feature in schema["feature_definitions"]]
    assert "terrain_occlusion_reliance" in feature_names
    assert "elevated_fire_affinity" in feature_names
    assert "deployment_reveal_pressure" in feature_names
    assert "charge_delivery_reliance" in feature_names
    assert "objective_spread_tolerance" in feature_names
    assert "attachment_dependency_risk" in feature_names
    assert "controller_complexity_index" in feature_names
    assert "mission_action_flex_capacity" in feature_names
    assert "detachment_diversity_index" in feature_names
    assert "towering_exposure_index" in feature_names
    assert "wahapedia_data_dir" in text
    assert "ambient default-data resolution" in text
    assert preview_schema["capability_schema_id"] == "capability_schema:build_capability_v2"
    preview_feature_names = [feature["name"] for feature in preview_schema["feature_definitions"]]
    assert "charge_option_flexibility" in preview_feature_names
    assert "ingress_charge_conversion" in preview_feature_names
    assert "fight_order_resilience" in preview_feature_names
    assert "overrun_chain_potential" in preview_feature_names
    assert "consolidate_objective_swing" in preview_feature_names
    assert "engagement_footprint_pressure" in preview_feature_names
    assert "transport_pop_punish_index" in preview_feature_names
    assert "preview combat bundles" in text.lower()
    assert "build_capability_v2" in text
    assert "11e" not in text


def test_tournament_field_schema_doc_exists_and_locks_event_policy_examples() -> None:
    assert TOURNAMENT_FIELD_DOC.is_file()
    text = _read(TOURNAMENT_FIELD_DOC)

    field_distribution = _extract_json_block(text, "Example Tournament Field Distribution")
    current_policy = _extract_json_block(text, "Example 10th-Style Event Policy")
    preview_policy = _extract_json_block(text, "Example Preview 11e Event Policy")

    assert TournamentFieldDistribution.from_dict(field_distribution).to_dict() == field_distribution
    assert current_policy == chapter_approved_10e_event_policy().to_dict()
    assert preview_policy == preview_new40k_event_policy().to_dict()
    assert "Swiss" in text or "swiss" in text
    assert "Battle Ready" in text
    assert "WTC 2025 clock rules" in text
    assert "canonical runtime `to_dict()`" in text
    assert "illustrative shape" in text


def test_ml_artifact_registry_examples_are_valid_and_complete() -> None:
    text = _read(REGISTRY_DOC)
    artifact = _extract_json_block(text, "Example Artifact Manifest")
    bundle = _extract_json_block(text, "Example Bundle Manifest")

    assert {
        "artifact_manifest_schema_id",
        "artifact_id",
        "family_id",
        "component_type",
        "tier",
        "architecture_id",
        "feature_schema_id",
        "capability_schema_id",
        "training_manifest_path",
        "training_manifest_hash",
        "rules_bundle_scope",
        "descriptor_bundle_scope",
        "version_adapter_boundary_id",
        "event_policy_scope",
        "git_commit",
        "parent_artifact_ids",
        "metrics",
        "status",
    }.issubset(artifact)
    assert artifact["status"] in {"experimental", "candidate", "blessed", "deprecated"}
    assert artifact["rules_bundle_scope"]["match_mode"] == "exact"
    assert artifact["descriptor_bundle_scope"]["match_mode"] == "exact"
    assert artifact["event_policy_scope"]["match_mode"] == "exact"

    assert {
        "policy_bundle_schema_id",
        "policy_bundle_id",
        "controller_type",
        "rules_bundle_scope",
        "descriptor_bundle_scope",
        "event_policy_scope",
        "components",
        "fallbacks",
        "required_feature_schema_ids",
        "required_capability_schema_ids",
        "created_from_commit",
    }.issubset(bundle)
    assert bundle["components"]["matchup_evaluator"]["resolver_kind"] == "artifact"
    assert bundle["components"]["playbook_selector"]["resolver_kind"] == "heuristic"
    assert bundle["rules_bundle_scope"]["match_mode"] == "exact"
    assert bundle["descriptor_bundle_scope"]["match_mode"] == "exact"
    assert bundle["event_policy_scope"]["match_mode"] == "exact"
    assert bundle["fallbacks"]["matchup_evaluator"] == ["heuristic:capability_matchup:v1"]
    assert bundle["fallbacks"]["playbook_selector"] == ["heuristic:identity_playbook:v1"]
    assert bundle["fallbacks"]["roster_edit_ranker"] == ["heuristic:roster_edit_search:v1"]


def test_registry_doc_locks_no_ml_extras_and_patch_scope_rules() -> None:
    text = _read(REGISTRY_DOC)
    assert "warhammer40k_ai[ml]" in text
    assert "base project dependencies" in text
    assert "## Patch Scope and Retraining Scope" in text
    assert "Points-only or narrow dataslate changes" in text
    assert "Mission, terrain, or event-policy changes" in text
    assert "Feature or capability schema changes" in text


def test_architecture_and_objective_docs_define_core_abi_terms() -> None:
    architecture = _read(ARCHITECTURE_DOC)
    objective = _read(OBJECTIVE_DOC)
    optimization_target = "(ArmyBlueprint, policy_bundle_id, rules_bundle_id, field_distribution_id, event_policy_id)"

    assert optimization_target in architecture
    assert optimization_target in objective
    assert "BuildCapabilityProfile" in architecture
    assert "TournamentFieldDistribution" in architecture
    assert "EventPolicyDescriptor" in architecture
    assert "PolicyBundle" in architecture
    assert "MusterRecord" in architecture
    assert "Direct end-to-end list generation is not the first learned target." in architecture
    assert "Direct end-to-end list generation is not the first learned target." in objective
    assert "TOURNAMENT_EVALUATION_PIPELINE.md" in architecture
    assert "TOURNAMENT_EVALUATION_PIPELINE.md" in objective
    assert "ROSTER_SEARCH.md" in architecture


def test_evaluation_pipeline_doc_locks_scripts_modes_and_report_contract() -> None:
    text = _read(EVALUATION_PIPELINE_DOC)

    assert "scripts/evaluate_policy_bundle.py" in text
    assert "scripts/evaluate_tournament_roster.py" in text
    assert "scripts/run_headless_self_play.py" in text
    assert "ReplayStoreReader.reconstruct_game_at_decision(..., strict=True)" in text
    assert "headless_fixed" in text
    assert "training_grade" in text
    assert "headless_fixed_v1" in text
    assert "pre_ml_baseline_v1" in text
    assert "summary.json" in text
    assert "per_match.csv" in text
    assert "roster_context.json" in text
    assert "muster_record.json" in text
    assert "mustering_manifest.json" in text
    assert "MUSTERING_DATA_SPEC.md" in text
    assert "The scripts return exit code `1` when replay audit fails" in text
    assert "warhammer40k_ai[ml]" in text
    assert "runtime army files" in text
    assert "actual self-play match execution" in text


def test_mustering_data_spec_examples_are_valid_and_sliceable() -> None:
    text = _read(MUSTERING_DATA_DOC)
    record = _extract_json_block(text, "Example Muster Record")
    manifest = _extract_json_block(text, "Example Mustering Manifest")

    assert validate_muster_record(record) == []
    assert MusterRecord.from_dict(record).to_dict()["record_id"] == "muster_record:example"
    assert validate_mustering_manifest(manifest) == []
    assert manifest["record_schema"]["muster_record_schema_id"] == "muster_record_schema:v1"
    assert manifest["mustering_manifest_schema_id"] == "mustering_manifest_schema:v1"
    assert "scripts/build_mustering_manifest.py" in text
    assert "rules_bundle_id" in text
    assert "capability_schema_id" in text
    assert "field_distribution_id" in text
    assert "event_policy_id" in text
    assert "policy_bundle_id" in text
    assert "controller_bundle_id" in text
    assert "search_edit_sequence" in text
    assert "descriptor_provenance" in text


def test_roster_search_doc_locks_validator_backed_search_contract() -> None:
    text = _read(ROSTER_SEARCH_DOC)

    assert "roster_edit_actions.py" in text
    assert "roster_repair.py" in text
    assert "roster_search.py" in text
    assert "roster_search_report.py" in text
    assert "ArmyMusterer.validate_runtime_legality()" in text
    assert "select warlord" in text
    assert "change wargear choice" in text
    assert "enhancement count limits" in text
    assert "duplicate datasheet caps" in text
    assert "Unit.apply_wargear_options_strict(...)" in text
    assert "unit.validate_wargear_selection()" in text
    assert "`beam`" in text
    assert "`local`" in text
    assert "`evolutionary`" in text


def test_roster_synthesis_doc_locks_seeded_10e_bridge_contract() -> None:
    text = _read(ROSTER_SYNTHESIS_DOC)

    assert "PR-MUSTER-008A" in text
    assert "RosterSynthesisSeed" in text
    assert "synthesize_rosters()" in text
    assert "scripts/synthesize_roster.py" in text
    assert "ArmyMusterer.validate_runtime_legality()" in text
    assert "parse_army_list_text()" in text
    assert "10th-edition" in text
    assert "Torch" in text
    assert "Omitted-faction mode" in text
