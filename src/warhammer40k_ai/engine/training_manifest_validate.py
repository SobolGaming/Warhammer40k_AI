from __future__ import annotations

from typing import Any

from .training_manifest_schema import PRE_ML_BASELINE_GATE_PROFILE, PRE_ML_BASELINE_GATE_PROFILE_ID, _ratio


def _validate_str_list(payload: dict[str, Any], key: str, errors: list[str]) -> None:
    value = payload.get(key)
    if not isinstance(value, list):
        errors.append(f"{key} must be a list")
        return
    if any(not isinstance(item, str) for item in value):
        errors.append(f"{key} must contain only strings")


def _validate_slice_filters(payload: dict[str, Any], errors: list[str]) -> None:
    slice_filters = payload.get("slice_filters")
    if not isinstance(slice_filters, dict):
        errors.append("slice_filters must be an object")
        return
    expected_keys = (
        "rules_bundle_ids",
        "descriptor_bundle_ids",
        "mission_descriptor_ids",
        "objective_descriptor_ids",
        "terrain_descriptor_ids",
        "deployment_descriptor_ids",
        "army_build_descriptor_ids",
        "tool_descriptor_ids",
    )
    unknown = sorted(str(key) for key in slice_filters.keys() if str(key) not in expected_keys)
    if unknown:
        errors.append(f"slice_filters contains unknown keys: {', '.join(unknown)}")
    for key in expected_keys:
        _validate_str_list(slice_filters, key, errors)


def validate_training_manifest(manifest: dict[str, Any]) -> list[str]:
    payload = dict(manifest or {})
    errors: list[str] = []
    required_fields = (
        "manifest_version",
        "generated_at_utc",
        "source_tag",
        "total_records",
        "rules_bundle_ids",
        "descriptor_bundle_ids",
        "mission_descriptor_ids",
        "objective_descriptor_ids",
        "terrain_descriptor_ids",
        "deployment_descriptor_ids",
        "army_build_descriptor_ids",
        "tool_descriptor_ids",
        "decision_type_counts",
        "coverage",
        "gameplay_quality",
        "gate_requirements",
        "slice_filters",
    )
    missing = [field for field in required_fields if field not in payload]
    if missing:
        errors.append(f"Missing manifest fields: {', '.join(missing)}")

    total_records = int(payload.get("total_records", 0) or 0)
    if total_records < 0:
        errors.append("total_records must be >= 0")

    decision_counts = dict(payload.get("decision_type_counts", {}) or {})
    counted = sum(int(value or 0) for value in decision_counts.values())
    if counted != total_records:
        errors.append(
            f"total_records mismatch: total_records={total_records} but decision_type_counts sum={counted}"
        )

    for key in (
        "rules_bundle_ids",
        "descriptor_bundle_ids",
        "mission_descriptor_ids",
        "objective_descriptor_ids",
        "terrain_descriptor_ids",
        "deployment_descriptor_ids",
        "army_build_descriptor_ids",
        "tool_descriptor_ids",
    ):
        _validate_str_list(payload, key, errors)

    _validate_slice_filters(payload, errors)

    coverage = dict(payload.get("coverage", {}) or {})
    semantic_count = int(coverage.get("records_with_semantic_candidate_metadata", 0) or 0)
    relabel_count = int(coverage.get("records_with_relabel_status", 0) or 0)
    if semantic_count > total_records:
        errors.append("coverage.records_with_semantic_candidate_metadata cannot exceed total_records")
    if relabel_count > total_records:
        errors.append("coverage.records_with_relabel_status cannot exceed total_records")

    semantic_ratio = float(coverage.get("semantic_candidate_metadata_ratio", 0.0) or 0.0)
    relabel_ratio = float(coverage.get("relabel_status_ratio", 0.0) or 0.0)
    if semantic_ratio < 0.0 or semantic_ratio > 1.0:
        errors.append("coverage.semantic_candidate_metadata_ratio must be in [0, 1]")
    if relabel_ratio < 0.0 or relabel_ratio > 1.0:
        errors.append("coverage.relabel_status_ratio must be in [0, 1]")
    if semantic_ratio != _ratio(semantic_count, total_records):
        errors.append(
            "coverage.semantic_candidate_metadata_ratio must match records_with_semantic_candidate_metadata"
        )
    if relabel_ratio != _ratio(relabel_count, total_records):
        errors.append("coverage.relabel_status_ratio must match records_with_relabel_status")

    deployment_related_records = int(coverage.get("deployment_related_records", 0) or 0)
    deployment_zone_choice_records = int(coverage.get("deployment_zone_choice_records", 0) or 0)
    declare_reserves_records = int(coverage.get("declare_reserves_records", 0) or 0)
    select_next_deploy_unit_records = int(coverage.get("select_next_deploy_unit_records", 0) or 0)
    scout_move_records = int(coverage.get("scout_move_records", 0) or 0)
    deployment_move_records = int(coverage.get("deployment_move_records", 0) or 0)
    deployment_semantic_records = int(coverage.get("deployment_records_with_semantic_metadata", 0) or 0)
    deployment_semantic_ratio = float(coverage.get("deployment_semantic_metadata_ratio", 1.0) or 0.0)
    if deployment_related_records < 0 or deployment_related_records > total_records:
        errors.append("coverage.deployment_related_records must be in [0, total_records]")
    deployment_count_fields = (
        ("coverage.deployment_zone_choice_records", deployment_zone_choice_records),
        ("coverage.declare_reserves_records", declare_reserves_records),
        ("coverage.select_next_deploy_unit_records", select_next_deploy_unit_records),
        ("coverage.scout_move_records", scout_move_records),
        ("coverage.deployment_move_records", deployment_move_records),
    )
    for label, value in deployment_count_fields:
        if value < 0 or value > total_records:
            errors.append(f"{label} must be in [0, total_records]")
    if deployment_semantic_records < 0 or deployment_semantic_records > deployment_related_records:
        errors.append(
            "coverage.deployment_records_with_semantic_metadata must be in [0, deployment_related_records]"
        )
    if deployment_semantic_ratio < 0.0 or deployment_semantic_ratio > 1.0:
        errors.append("coverage.deployment_semantic_metadata_ratio must be in [0, 1]")
    expected_deployment_ratio = (
        1.0
        if deployment_related_records <= 0
        else _ratio(deployment_semantic_records, deployment_related_records)
    )
    if deployment_semantic_ratio != expected_deployment_ratio:
        errors.append(
            "coverage.deployment_semantic_metadata_ratio must match deployment_records_with_semantic_metadata"
        )
    if bool(coverage.get("has_deployment_zone_choice_coverage", False)) != bool(deployment_zone_choice_records > 0):
        errors.append(
            "coverage.has_deployment_zone_choice_coverage must match deployment_zone_choice_records > 0"
        )
    if bool(coverage.get("has_declare_reserves_coverage", False)) != bool(declare_reserves_records > 0):
        errors.append(
            "coverage.has_declare_reserves_coverage must match declare_reserves_records > 0"
        )
    if bool(coverage.get("has_select_next_deploy_unit_coverage", False)) != bool(select_next_deploy_unit_records > 0):
        errors.append(
            "coverage.has_select_next_deploy_unit_coverage must match select_next_deploy_unit_records > 0"
        )
    if bool(coverage.get("has_scout_move_coverage", False)) != bool(scout_move_records > 0):
        errors.append(
            "coverage.has_scout_move_coverage must match scout_move_records > 0"
        )
    if bool(coverage.get("has_deployment_move_coverage", False)) != bool(deployment_move_records > 0):
        errors.append(
            "coverage.has_deployment_move_coverage must match deployment_move_records > 0"
        )

    gameplay_quality = dict(payload.get("gameplay_quality", {}) or {})
    games_observed = int(gameplay_quality.get("games_observed", 0) or 0)
    records_with_game_id = int(gameplay_quality.get("records_with_game_id", 0) or 0)
    total_tactical_decisions = int(gameplay_quality.get("total_tactical_decisions", 0) or 0)
    min_tactical_per_game = int(gameplay_quality.get("minimum_tactical_decisions_per_game", 0) or 0)
    mean_tactical_per_game = float(gameplay_quality.get("mean_tactical_decisions_per_game", 0.0) or 0.0)
    combat_decisions = int(gameplay_quality.get("combat_decisions", 0) or 0)
    games_with_score_snapshots = int(gameplay_quality.get("games_with_score_snapshots", 0) or 0)
    games_with_scoring_progress = int(gameplay_quality.get("games_with_scoring_progress", 0) or 0)
    games_with_activity = int(gameplay_quality.get("games_with_combat_or_scoring_activity", 0) or 0)
    games_with_nontrivial_vp = int(gameplay_quality.get("games_with_nontrivial_vp", 0) or 0)
    minimum_nontrivial_total_vp = int(gameplay_quality.get("minimum_nontrivial_total_vp", 0) or 0)

    if games_observed < 0:
        errors.append("gameplay_quality.games_observed must be >= 0")
    if records_with_game_id < 0 or records_with_game_id > total_records:
        errors.append("gameplay_quality.records_with_game_id must be in [0, total_records]")
    if total_tactical_decisions < 0 or total_tactical_decisions > total_records:
        errors.append("gameplay_quality.total_tactical_decisions must be in [0, total_records]")
    if min_tactical_per_game < 0 or min_tactical_per_game > total_tactical_decisions:
        errors.append(
            "gameplay_quality.minimum_tactical_decisions_per_game must be in [0, total_tactical_decisions]"
        )
    if combat_decisions < 0 or combat_decisions > total_records:
        errors.append("gameplay_quality.combat_decisions must be in [0, total_records]")
    if games_with_score_snapshots < 0 or games_with_score_snapshots > games_observed:
        errors.append("gameplay_quality.games_with_score_snapshots must be in [0, games_observed]")
    if games_with_scoring_progress < 0 or games_with_scoring_progress > games_observed:
        errors.append("gameplay_quality.games_with_scoring_progress must be in [0, games_observed]")
    if games_with_activity < 0 or games_with_activity > games_observed:
        errors.append("gameplay_quality.games_with_combat_or_scoring_activity must be in [0, games_observed]")
    if games_with_nontrivial_vp < 0 or games_with_nontrivial_vp > games_observed:
        errors.append("gameplay_quality.games_with_nontrivial_vp must be in [0, games_observed]")
    if minimum_nontrivial_total_vp < 0:
        errors.append("gameplay_quality.minimum_nontrivial_total_vp must be >= 0")

    records_with_game_id_ratio = float(gameplay_quality.get("records_with_game_id_ratio", 0.0) or 0.0)
    combat_decision_ratio = float(gameplay_quality.get("combat_decision_ratio", 0.0) or 0.0)
    games_with_score_snapshots_ratio = float(gameplay_quality.get("games_with_score_snapshots_ratio", 0.0) or 0.0)
    scoring_progress_game_ratio = float(gameplay_quality.get("scoring_progress_game_ratio", 0.0) or 0.0)
    no_progress_game_ratio = float(gameplay_quality.get("no_progress_game_ratio", 0.0) or 0.0)
    combat_or_scoring_active_game_ratio = float(
        gameplay_quality.get("combat_or_scoring_active_game_ratio", 0.0) or 0.0
    )
    nontrivial_vp_game_ratio = float(gameplay_quality.get("nontrivial_vp_game_ratio", 0.0) or 0.0)

    ratio_entries = (
        ("gameplay_quality.records_with_game_id_ratio", records_with_game_id_ratio),
        ("gameplay_quality.combat_decision_ratio", combat_decision_ratio),
        ("gameplay_quality.games_with_score_snapshots_ratio", games_with_score_snapshots_ratio),
        ("gameplay_quality.scoring_progress_game_ratio", scoring_progress_game_ratio),
        ("gameplay_quality.no_progress_game_ratio", no_progress_game_ratio),
        ("gameplay_quality.combat_or_scoring_active_game_ratio", combat_or_scoring_active_game_ratio),
        ("gameplay_quality.nontrivial_vp_game_ratio", nontrivial_vp_game_ratio),
    )
    for label, value in ratio_entries:
        if value < 0.0 or value > 1.0:
            errors.append(f"{label} must be in [0, 1]")

    if records_with_game_id_ratio != _ratio(records_with_game_id, total_records):
        errors.append("gameplay_quality.records_with_game_id_ratio must match records_with_game_id")
    if combat_decision_ratio != _ratio(combat_decisions, total_records):
        errors.append("gameplay_quality.combat_decision_ratio must match combat_decisions")
    if games_with_score_snapshots_ratio != _ratio(games_with_score_snapshots, games_observed):
        errors.append("gameplay_quality.games_with_score_snapshots_ratio must match games_with_score_snapshots")
    if scoring_progress_game_ratio != _ratio(games_with_scoring_progress, games_observed):
        errors.append("gameplay_quality.scoring_progress_game_ratio must match games_with_scoring_progress")
    expected_no_progress_games = max(0, games_observed - games_with_scoring_progress)
    if no_progress_game_ratio != _ratio(expected_no_progress_games, games_observed):
        errors.append("gameplay_quality.no_progress_game_ratio must match complement of scoring_progress_game_ratio")
    if combat_or_scoring_active_game_ratio != _ratio(games_with_activity, games_observed):
        errors.append(
            "gameplay_quality.combat_or_scoring_active_game_ratio must match games_with_combat_or_scoring_activity"
        )
    if nontrivial_vp_game_ratio != _ratio(games_with_nontrivial_vp, games_observed):
        errors.append("gameplay_quality.nontrivial_vp_game_ratio must match games_with_nontrivial_vp")
    if games_observed > 0 and mean_tactical_per_game != _ratio(total_tactical_decisions, games_observed):
        errors.append("gameplay_quality.mean_tactical_decisions_per_game must match total_tactical_decisions")
    if games_observed <= 0 and mean_tactical_per_game != 0.0:
        errors.append("gameplay_quality.mean_tactical_decisions_per_game must be 0 when games_observed is 0")

    gate_requirements = dict(payload.get("gate_requirements", {}) or {})
    min_records = int(gate_requirements.get("minimum_tier3_pretraining_records", 0) or 0)
    if min_records < 0:
        errors.append("gate_requirements.minimum_tier3_pretraining_records must be >= 0")
    if bool(gate_requirements.get("meets_minimum_tier3_pretraining_records", False)) != bool(
        total_records >= min_records
    ):
        errors.append(
            "gate_requirements.meets_minimum_tier3_pretraining_records must match total_records threshold evaluation"
        )

    if bool(gate_requirements.get("semantic_candidate_metadata_complete", False)) != bool(
        semantic_count == total_records
    ):
        errors.append(
            "gate_requirements.semantic_candidate_metadata_complete must match semantic coverage completeness"
        )
    if bool(gate_requirements.get("deployment_semantic_metadata_complete", False)) != bool(
        deployment_semantic_records == deployment_related_records
    ):
        errors.append(
            "gate_requirements.deployment_semantic_metadata_complete must match deployment semantic completeness"
        )
    if not bool(gate_requirements.get("deployment_semantic_metadata_required", False)):
        errors.append("gate_requirements.deployment_semantic_metadata_required must be true")

    gate_profile_id = str(gate_requirements.get("gate_profile_id", "") or "")
    if not gate_profile_id:
        errors.append("gate_requirements.gate_profile_id is required")
        return errors
    if gate_profile_id != PRE_ML_BASELINE_GATE_PROFILE_ID:
        errors.append(
            f"gate_requirements.gate_profile_id must be {PRE_ML_BASELINE_GATE_PROFILE_ID}"
        )
        return errors
    gate_profile = PRE_ML_BASELINE_GATE_PROFILE
    profile_min_records = int(gate_requirements.get("gate_profile_minimum_tier3_pretraining_records", 0) or 0)
    required_semantic_ratio = float(gate_requirements.get("required_semantic_candidate_metadata_ratio", 0.0) or 0.0)
    required_relabel_ratio = float(gate_requirements.get("required_relabel_status_ratio", 0.0) or 0.0)
    required_deployment_semantic_ratio = float(
        gate_requirements.get("required_deployment_semantic_metadata_ratio", 0.0) or 0.0
    )
    profile_min_games = int(gate_requirements.get("gate_profile_minimum_games_observed", 0) or 0)
    required_game_id_ratio = float(gate_requirements.get("required_records_with_game_id_ratio", 0.0) or 0.0)
    profile_min_tactical = int(
        gate_requirements.get("gate_profile_minimum_tactical_decisions_per_game", 0) or 0
    )
    required_activity_ratio = float(
        gate_requirements.get("required_combat_or_scoring_active_game_ratio", 0.0) or 0.0
    )
    maximum_no_progress_ratio = float(gate_requirements.get("maximum_no_progress_game_ratio", 0.0) or 0.0)
    required_nontrivial_vp_ratio = float(gate_requirements.get("required_nontrivial_vp_game_ratio", 0.0) or 0.0)
    required_min_nontrivial_total_vp = int(gate_requirements.get("minimum_nontrivial_total_vp", 0) or 0)
    if profile_min_records != int(gate_profile.minimum_tier3_pretraining_records):
        errors.append(
            "gate_requirements.gate_profile_minimum_tier3_pretraining_records must match canonical gate profile"
        )
    if required_semantic_ratio != float(gate_profile.required_semantic_candidate_metadata_ratio):
        errors.append(
            "gate_requirements.required_semantic_candidate_metadata_ratio must match canonical gate profile"
        )
    if required_relabel_ratio != float(gate_profile.required_relabel_status_ratio):
        errors.append("gate_requirements.required_relabel_status_ratio must match canonical gate profile")
    if required_deployment_semantic_ratio != 1.0:
        errors.append(
            "gate_requirements.required_deployment_semantic_metadata_ratio must match canonical gate profile"
        )
    if profile_min_games != int(gate_profile.minimum_games_observed):
        errors.append("gate_requirements.gate_profile_minimum_games_observed must match canonical gate profile")
    if required_game_id_ratio != float(gate_profile.required_records_with_game_id_ratio):
        errors.append("gate_requirements.required_records_with_game_id_ratio must match canonical gate profile")
    if profile_min_tactical != int(gate_profile.minimum_tactical_decisions_per_game):
        errors.append(
            "gate_requirements.gate_profile_minimum_tactical_decisions_per_game must match canonical gate profile"
        )
    if required_activity_ratio != float(gate_profile.required_combat_or_scoring_active_game_ratio):
        errors.append(
            "gate_requirements.required_combat_or_scoring_active_game_ratio must match canonical gate profile"
        )
    if maximum_no_progress_ratio != float(gate_profile.maximum_no_progress_game_ratio):
        errors.append("gate_requirements.maximum_no_progress_game_ratio must match canonical gate profile")
    if required_nontrivial_vp_ratio != float(gate_profile.required_nontrivial_vp_game_ratio):
        errors.append("gate_requirements.required_nontrivial_vp_game_ratio must match canonical gate profile")
    if required_min_nontrivial_total_vp != int(gate_profile.minimum_nontrivial_total_vp):
        errors.append("gate_requirements.minimum_nontrivial_total_vp must match canonical gate profile")
    if required_semantic_ratio < 0.0 or required_semantic_ratio > 1.0:
        errors.append("gate_requirements.required_semantic_candidate_metadata_ratio must be in [0, 1]")
    if required_relabel_ratio < 0.0 or required_relabel_ratio > 1.0:
        errors.append("gate_requirements.required_relabel_status_ratio must be in [0, 1]")
    if required_deployment_semantic_ratio < 0.0 or required_deployment_semantic_ratio > 1.0:
        errors.append("gate_requirements.required_deployment_semantic_metadata_ratio must be in [0, 1]")
    if required_game_id_ratio < 0.0 or required_game_id_ratio > 1.0:
        errors.append("gate_requirements.required_records_with_game_id_ratio must be in [0, 1]")
    if required_activity_ratio < 0.0 or required_activity_ratio > 1.0:
        errors.append("gate_requirements.required_combat_or_scoring_active_game_ratio must be in [0, 1]")
    if maximum_no_progress_ratio < 0.0 or maximum_no_progress_ratio > 1.0:
        errors.append("gate_requirements.maximum_no_progress_game_ratio must be in [0, 1]")
    if required_nontrivial_vp_ratio < 0.0 or required_nontrivial_vp_ratio > 1.0:
        errors.append("gate_requirements.required_nontrivial_vp_game_ratio must be in [0, 1]")
    if required_min_nontrivial_total_vp < 0:
        errors.append("gate_requirements.minimum_nontrivial_total_vp must be >= 0")

    meets_profile_minimum = bool(gate_requirements.get("meets_gate_profile_minimum_tier3_pretraining_records", False))
    meets_profile_semantic = bool(gate_requirements.get("meets_required_semantic_candidate_metadata_ratio", False))
    meets_profile_relabel = bool(gate_requirements.get("meets_required_relabel_status_ratio", False))
    meets_profile_deployment_semantic = bool(
        gate_requirements.get("meets_required_deployment_semantic_metadata_ratio", False)
    )
    meets_profile_games = bool(gate_requirements.get("meets_gate_profile_minimum_games_observed", False))
    meets_profile_game_id = bool(gate_requirements.get("meets_required_records_with_game_id_ratio", False))
    meets_profile_tactical = bool(
        gate_requirements.get("meets_gate_profile_minimum_tactical_decisions_per_game", False)
    )
    meets_profile_activity = bool(
        gate_requirements.get("meets_required_combat_or_scoring_active_game_ratio", False)
    )
    meets_profile_no_progress = bool(gate_requirements.get("meets_maximum_no_progress_game_ratio", False))
    meets_profile_nontrivial = bool(gate_requirements.get("meets_required_nontrivial_vp_game_ratio", False))
    if meets_profile_minimum != bool(total_records >= profile_min_records):
        errors.append(
            "gate_requirements.meets_gate_profile_minimum_tier3_pretraining_records must match profile minimum evaluation"
        )
    if meets_profile_semantic != bool(semantic_ratio >= required_semantic_ratio):
        errors.append(
            "gate_requirements.meets_required_semantic_candidate_metadata_ratio must match profile semantic ratio evaluation"
        )
    if meets_profile_relabel != bool(relabel_ratio >= required_relabel_ratio):
        errors.append(
            "gate_requirements.meets_required_relabel_status_ratio must match profile relabel ratio evaluation"
        )
    if meets_profile_deployment_semantic != bool(
        deployment_semantic_ratio >= required_deployment_semantic_ratio
    ):
        errors.append(
            "gate_requirements.meets_required_deployment_semantic_metadata_ratio must match deployment semantic ratio evaluation"
        )
    if meets_profile_games != bool(games_observed >= profile_min_games):
        errors.append("gate_requirements.meets_gate_profile_minimum_games_observed must match game count evaluation")
    if meets_profile_game_id != bool(records_with_game_id_ratio >= required_game_id_ratio):
        errors.append(
            "gate_requirements.meets_required_records_with_game_id_ratio must match records_with_game_id_ratio"
        )
    if meets_profile_tactical != bool(min_tactical_per_game >= profile_min_tactical):
        errors.append(
            "gate_requirements.meets_gate_profile_minimum_tactical_decisions_per_game must match tactical-per-game evaluation"
        )
    if meets_profile_activity != bool(combat_or_scoring_active_game_ratio >= required_activity_ratio):
        errors.append(
            "gate_requirements.meets_required_combat_or_scoring_active_game_ratio must match activity ratio evaluation"
        )
    if meets_profile_no_progress != bool(no_progress_game_ratio <= maximum_no_progress_ratio):
        errors.append(
            "gate_requirements.meets_maximum_no_progress_game_ratio must match no-progress ratio evaluation"
        )
    if meets_profile_nontrivial != bool(nontrivial_vp_game_ratio >= required_nontrivial_vp_ratio):
        errors.append(
            "gate_requirements.meets_required_nontrivial_vp_game_ratio must match nontrivial VP ratio evaluation"
        )
    if bool(gate_requirements.get("meets_gate_profile", False)) != bool(
        meets_profile_minimum
        and meets_profile_semantic
        and meets_profile_relabel
        and meets_profile_deployment_semantic
        and meets_profile_games
        and meets_profile_game_id
        and meets_profile_tactical
        and meets_profile_activity
        and meets_profile_no_progress
        and meets_profile_nontrivial
    ):
        errors.append("gate_requirements.meets_gate_profile must match gate-profile check conjunction")
    return errors


def validate_gate_profile_compliance(manifest: dict[str, Any]) -> list[str]:
    payload = dict(manifest or {})
    gate_requirements = dict(payload.get("gate_requirements", {}) or {})
    failures: list[str] = []
    gate_profile_id = str(gate_requirements.get("gate_profile_id", "") or "")
    if gate_profile_id != PRE_ML_BASELINE_GATE_PROFILE_ID:
        failures.append(
            f"Gate profile id mismatch: expected {PRE_ML_BASELINE_GATE_PROFILE_ID}, found {gate_profile_id or 'missing'}"
        )
        return failures

    if not bool(gate_requirements.get("meets_gate_profile_minimum_tier3_pretraining_records", False)):
        failures.append("Gate profile minimum Tier3 record threshold not met")
    if not bool(gate_requirements.get("meets_required_semantic_candidate_metadata_ratio", False)):
        failures.append("Gate profile semantic metadata coverage threshold not met")
    if not bool(gate_requirements.get("meets_required_relabel_status_ratio", False)):
        failures.append("Gate profile relabel coverage threshold not met")
    if not bool(gate_requirements.get("meets_required_deployment_semantic_metadata_ratio", False)):
        failures.append("Gate profile deployment semantic metadata coverage threshold not met")
    if not bool(gate_requirements.get("meets_gate_profile_minimum_games_observed", False)):
        failures.append("Gate profile minimum games-observed threshold not met")
    if not bool(gate_requirements.get("meets_required_records_with_game_id_ratio", False)):
        failures.append("Gate profile game-id coverage threshold not met")
    if not bool(gate_requirements.get("meets_gate_profile_minimum_tactical_decisions_per_game", False)):
        failures.append("Gate profile minimum tactical-decisions-per-game threshold not met")
    if not bool(gate_requirements.get("meets_required_combat_or_scoring_active_game_ratio", False)):
        failures.append("Gate profile combat/scoring activity ratio threshold not met")
    if not bool(gate_requirements.get("meets_maximum_no_progress_game_ratio", False)):
        failures.append("Gate profile maximum no-progress game ratio threshold not met")
    if not bool(gate_requirements.get("meets_required_nontrivial_vp_game_ratio", False)):
        failures.append("Gate profile nontrivial VP game ratio threshold not met")
    if not bool(gate_requirements.get("meets_gate_profile", False)):
        failures.append("Gate profile aggregate check did not pass")
    return failures


__all__ = ["validate_gate_profile_compliance", "validate_training_manifest"]
