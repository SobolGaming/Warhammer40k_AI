from __future__ import annotations

import json
from pathlib import Path
import re


DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
REGISTRY_DOC = DOCS_DIR / "ML_ARTIFACT_REGISTRY.md"
ARCHITECTURE_DOC = DOCS_DIR / "AI_MUSTERING_TOURNAMENT_ARCHITECTURE.md"
OBJECTIVE_DOC = DOCS_DIR / "TOURNAMENT_EVALUATION_OBJECTIVE.md"
BUILD_CAPABILITY_DOC = DOCS_DIR / "BUILD_CAPABILITY_SCHEMA.md"


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


def test_build_capability_schema_doc_exists_and_locks_portable_schema() -> None:
    assert BUILD_CAPABILITY_DOC.is_file()

    schema = _extract_json_block(_read(BUILD_CAPABILITY_DOC), "Example Build Capability Schema")

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
    assert "11e" not in _read(BUILD_CAPABILITY_DOC)


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
