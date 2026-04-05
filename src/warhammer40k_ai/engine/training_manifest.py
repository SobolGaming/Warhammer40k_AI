from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any


MANIFEST_VERSION = "1.3.0"
PRE_ML_BASELINE_GATE_PROFILE_ID = "pre_ml_baseline_v1"
_RATIO_PRECISION = 6

_SEMANTIC_METADATA_KEYS = (
    "projected_score_delta_next_window",
    "projected_score_delta_round",
    "projected_deny_delta_next_window",
    "projected_control_delta",
    "projected_action_enablement_delta",
    "projected_exposure_delta",
    "projected_trade_ev",
    "cover_delta",
    "los_delta",
    "resource_delta",
    "rules_provenance_refs",
)

_DEPLOYMENT_SEMANTIC_METADATA_KEYS = (
    "reserve_denial_delta",
    "screen_integrity_delta",
    "countercharge_coverage_delta",
    "aura_connectivity_delta",
    "projected_exposure_delta_if_enemy_goes_first",
    "projected_melee_staging_delta",
)

_DEPLOYMENT_DECISION_TYPES = {
    "CHOOSE_DEPLOYMENT_ZONE",
    "DECLARE_RESERVES",
    "SELECT_NEXT_DEPLOY_UNIT",
    "SCOUT_MOVE",
}

_TACTICAL_DECISION_TYPES = {
    "MOVE_UNIT",
    "SELECT_UNIT",
    "SELECT_MOVEMENT_ACTION",
    "DECLARE_SHOTS",
    "DECLARE_CHARGE",
    "SELECT_FIGHT_TARGETS",
    "DECLARE_MELEE_WEAPONS",
    "ALLOCATE_MELEE_TARGETS",
    "ALLOCATE_TARGETS",
    "SPLIT_ATTACKS",
    "SELECT_TARGET_MODEL",
    "SELECT_PRECISION_TARGET",
}

_COMBAT_DECISION_TYPES = {
    "SELECT_UNIT",
    "DECLARE_SHOTS",
    "DECLARE_CHARGE",
    "SELECT_FIGHT_TARGETS",
    "DECLARE_MELEE_WEAPONS",
    "ALLOCATE_MELEE_TARGETS",
    "ALLOCATE_TARGETS",
    "SPLIT_ATTACKS",
    "SELECT_TARGET_MODEL",
    "SELECT_PRECISION_TARGET",
}


@dataclass(frozen=True)
class TrainingDataGateProfile:
    gate_profile_id: str
    minimum_tier3_pretraining_records: int
    required_semantic_candidate_metadata_ratio: float
    required_relabel_status_ratio: float
    minimum_games_observed: int
    required_records_with_game_id_ratio: float
    minimum_tactical_decisions_per_game: int
    required_combat_or_scoring_active_game_ratio: float
    maximum_no_progress_game_ratio: float
    required_nontrivial_vp_game_ratio: float
    minimum_nontrivial_total_vp: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_profile_id": str(self.gate_profile_id or ""),
            "minimum_tier3_pretraining_records": int(self.minimum_tier3_pretraining_records),
            "required_semantic_candidate_metadata_ratio": float(self.required_semantic_candidate_metadata_ratio),
            "required_relabel_status_ratio": float(self.required_relabel_status_ratio),
            "minimum_games_observed": int(self.minimum_games_observed),
            "required_records_with_game_id_ratio": float(self.required_records_with_game_id_ratio),
            "minimum_tactical_decisions_per_game": int(self.minimum_tactical_decisions_per_game),
            "required_combat_or_scoring_active_game_ratio": float(
                self.required_combat_or_scoring_active_game_ratio
            ),
            "maximum_no_progress_game_ratio": float(self.maximum_no_progress_game_ratio),
            "required_nontrivial_vp_game_ratio": float(self.required_nontrivial_vp_game_ratio),
            "minimum_nontrivial_total_vp": int(self.minimum_nontrivial_total_vp),
        }


PRE_ML_BASELINE_GATE_PROFILE = TrainingDataGateProfile(
    gate_profile_id=PRE_ML_BASELINE_GATE_PROFILE_ID,
    minimum_tier3_pretraining_records=10000,
    required_semantic_candidate_metadata_ratio=1.0,
    required_relabel_status_ratio=1.0,
    minimum_games_observed=20,
    required_records_with_game_id_ratio=1.0,
    minimum_tactical_decisions_per_game=25,
    required_combat_or_scoring_active_game_ratio=0.8,
    maximum_no_progress_game_ratio=0.2,
    required_nontrivial_vp_game_ratio=0.8,
    minimum_nontrivial_total_vp=5,
)


def _round_ratio(value: float) -> float:
    return float(round(float(value), _RATIO_PRECISION))


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return _round_ratio(float(numerator) / float(denominator))


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _resolve_gate_profile(profile_id: str) -> TrainingDataGateProfile:
    normalized = str(profile_id or PRE_ML_BASELINE_GATE_PROFILE_ID)
    if normalized == PRE_ML_BASELINE_GATE_PROFILE_ID:
        return PRE_ML_BASELINE_GATE_PROFILE
    raise ValueError(f"Unknown training-data gate profile id: {normalized}")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _descriptor_bundle_fingerprint(descriptor_ids: dict[str, Any]) -> str:
    payload = {
        "mission_descriptor_id": str(descriptor_ids.get("mission_descriptor_id", "") or ""),
        "objective_descriptor_ids": sorted(
            str(item) for item in list(descriptor_ids.get("objective_descriptor_ids", []) or []) if str(item)
        ),
        "terrain_descriptor_ids": sorted(
            str(item) for item in list(descriptor_ids.get("terrain_descriptor_ids", []) or []) if str(item)
        ),
        "deployment_descriptor_id": str(descriptor_ids.get("deployment_descriptor_id", "") or ""),
        "army_build_descriptor_id": str(descriptor_ids.get("army_build_descriptor_id", "") or ""),
        "tool_descriptor_ids": sorted(
            str(item) for item in list(descriptor_ids.get("tool_descriptor_ids", []) or []) if str(item)
        ),
    }
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"descriptor_bundle:{digest[:16]}"


def _decision_type_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in list(records or []):
        decision_type = str(record.get("decision_type", "") or "UNKNOWN")
        counts[decision_type] = int(counts.get(decision_type, 0) or 0) + 1
    return {key: counts[key] for key in sorted(counts.keys())}


def _rules_bundle_ids(records: list[dict[str, Any]]) -> list[str]:
    ids = {str(record.get("rules_bundle_id", "") or "") for record in list(records or []) if str(record.get("rules_bundle_id", "") or "")}
    return sorted(ids)


def _descriptor_bundle_ids(records: list[dict[str, Any]]) -> list[str]:
    ids: set[str] = set()
    for record in list(records or []):
        descriptor_ids = dict(record.get("descriptor_ids", {}) or {})
        if not descriptor_ids:
            continue
        ids.add(_descriptor_bundle_fingerprint(descriptor_ids))
    return sorted(ids)


def _candidates_have_semantic_metadata(record: dict[str, Any]) -> bool:
    for candidate in list(record.get("candidates", []) or []):
        metadata = dict(candidate.get("metadata", {}) or {})
        for key in _SEMANTIC_METADATA_KEYS:
            if key not in metadata:
                return False
    return True


def _is_deployment_move_record(record: dict[str, Any]) -> bool:
    if str(record.get("decision_type", "") or "") != "MOVE_UNIT":
        return False
    context = dict(record.get("context", {}) or {})
    return str(context.get("placement_kind", "") or "").strip().lower() == "deployment"


def _is_deployment_related_record(record: dict[str, Any]) -> bool:
    decision_type = str(record.get("decision_type", "") or "")
    if decision_type in _DEPLOYMENT_DECISION_TYPES:
        return True
    return _is_deployment_move_record(record)


def _candidates_have_deployment_semantic_metadata(record: dict[str, Any]) -> bool:
    if not _is_deployment_related_record(record):
        return False
    for candidate in list(record.get("candidates", []) or []):
        metadata = dict(candidate.get("metadata", {}) or {})
        for key in _DEPLOYMENT_SEMANTIC_METADATA_KEYS:
            if key not in metadata:
                return False
    return True


def _coverage(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = int(len(records or []))
    with_semantics = 0
    relabeled = 0
    deployment_related = 0
    deployment_zone_choice_records = 0
    declare_reserves_records = 0
    select_next_deploy_unit_records = 0
    scout_move_records = 0
    deployment_move_records = 0
    deployment_semantic_records = 0
    for record in list(records or []):
        item = dict(record or {})
        if _candidates_have_semantic_metadata(record):
            with_semantics += 1
        if str(item.get("relabel_status", "") or ""):
            relabeled += 1
        decision_type = str(item.get("decision_type", "") or "")
        is_deployment_move = _is_deployment_move_record(item)
        is_deployment_related = decision_type in _DEPLOYMENT_DECISION_TYPES or is_deployment_move
        if is_deployment_related:
            deployment_related += 1
            if _candidates_have_deployment_semantic_metadata(item):
                deployment_semantic_records += 1
        if decision_type == "CHOOSE_DEPLOYMENT_ZONE":
            deployment_zone_choice_records += 1
        if decision_type == "DECLARE_RESERVES":
            declare_reserves_records += 1
        if decision_type == "SELECT_NEXT_DEPLOY_UNIT":
            select_next_deploy_unit_records += 1
        if decision_type == "SCOUT_MOVE":
            scout_move_records += 1
        if is_deployment_move:
            deployment_move_records += 1
    semantic_ratio = _ratio(with_semantics, total)
    relabel_ratio = _ratio(relabeled, total)
    deployment_semantic_ratio = (
        1.0
        if deployment_related <= 0
        else _ratio(deployment_semantic_records, deployment_related)
    )
    return {
        "records_with_semantic_candidate_metadata": int(with_semantics),
        "semantic_candidate_metadata_ratio": semantic_ratio,
        "records_with_relabel_status": int(relabeled),
        "relabel_status_ratio": relabel_ratio,
        "deployment_related_records": int(deployment_related),
        "deployment_zone_choice_records": int(deployment_zone_choice_records),
        "declare_reserves_records": int(declare_reserves_records),
        "select_next_deploy_unit_records": int(select_next_deploy_unit_records),
        "scout_move_records": int(scout_move_records),
        "deployment_move_records": int(deployment_move_records),
        "deployment_records_with_semantic_metadata": int(deployment_semantic_records),
        "deployment_semantic_metadata_ratio": float(deployment_semantic_ratio),
        "has_deployment_zone_choice_coverage": bool(deployment_zone_choice_records > 0),
        "has_declare_reserves_coverage": bool(declare_reserves_records > 0),
        "has_select_next_deploy_unit_coverage": bool(select_next_deploy_unit_records > 0),
        "has_scout_move_coverage": bool(scout_move_records > 0),
        "has_deployment_move_coverage": bool(deployment_move_records > 0),
    }


def _extract_player_scores(record: dict[str, Any]) -> dict[str, float]:
    state = dict(record.get("omniscient_state", {}) or {})
    players = list(state.get("players", []) or [])
    scores: dict[str, float] = {}
    for idx, player in enumerate(players):
        payload = dict(player or {})
        player_id = str(payload.get("player_id", "") or payload.get("id", "") or f"player:{idx}")
        raw_score = payload.get("score", payload.get("victory_points", payload.get("vp", None)))
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            continue
        scores[player_id] = score
    return scores


def _scores_changed(previous: dict[str, float], current: dict[str, float]) -> bool:
    if not previous or not current:
        return False
    all_player_ids = sorted(set(previous.keys()) | set(current.keys()))
    for player_id in all_player_ids:
        prev = _safe_float(previous.get(player_id, 0.0), default=0.0)
        curr = _safe_float(current.get(player_id, 0.0), default=0.0)
        if abs(prev - curr) > 1e-9:
            return True
    return False


def _gameplay_quality(
    records: list[dict[str, Any]],
    *,
    gate_profile: TrainingDataGateProfile,
) -> dict[str, Any]:
    total_records = int(len(records or []))
    if total_records <= 0:
        return {
            "games_observed": 0,
            "records_with_game_id": 0,
            "records_with_game_id_ratio": 0.0,
            "total_tactical_decisions": 0,
            "minimum_tactical_decisions_per_game": 0,
            "mean_tactical_decisions_per_game": 0.0,
            "combat_decisions": 0,
            "combat_decision_ratio": 0.0,
            "games_with_score_snapshots": 0,
            "games_with_score_snapshots_ratio": 0.0,
            "games_with_scoring_progress": 0,
            "scoring_progress_game_ratio": 0.0,
            "no_progress_game_ratio": 0.0,
            "games_with_combat_or_scoring_activity": 0,
            "combat_or_scoring_active_game_ratio": 0.0,
            "games_with_nontrivial_vp": 0,
            "nontrivial_vp_game_ratio": 0.0,
            "minimum_nontrivial_total_vp": int(gate_profile.minimum_nontrivial_total_vp),
        }

    records_with_game_id = 0
    combat_decisions = 0
    game_stats: dict[str, dict[str, Any]] = {}

    for record in list(records or []):
        game_id = str(record.get("game_id", "") or "")
        if game_id:
            records_with_game_id += 1
        else:
            game_id = "__missing_game_id__"

        stats = game_stats.setdefault(
            game_id,
            {
                "tactical_decisions": 0,
                "combat_decisions": 0,
                "has_score_snapshot": False,
                "scoring_progress": False,
                "last_scores": {},
            },
        )
        decision_type = str(record.get("decision_type", "") or "UNKNOWN")
        if decision_type in _TACTICAL_DECISION_TYPES:
            stats["tactical_decisions"] = int(stats.get("tactical_decisions", 0) or 0) + 1
        if decision_type in _COMBAT_DECISION_TYPES:
            stats["combat_decisions"] = int(stats.get("combat_decisions", 0) or 0) + 1
            combat_decisions += 1
        scores = _extract_player_scores(record)
        if scores:
            stats["has_score_snapshot"] = True
            if _scores_changed(dict(stats.get("last_scores", {}) or {}), scores):
                stats["scoring_progress"] = True
            stats["last_scores"] = dict(scores)

    games_observed = int(len(game_stats))
    total_tactical = 0
    minimum_tactical = 0
    games_with_score_snapshots = 0
    games_with_scoring_progress = 0
    games_with_combat_or_scoring_activity = 0
    games_with_nontrivial_vp = 0

    if games_observed > 0:
        tactical_values: list[int] = []
        for stats in game_stats.values():
            tactical = int(stats.get("tactical_decisions", 0) or 0)
            tactical_values.append(tactical)
            total_tactical += tactical
            has_snapshot = bool(stats.get("has_score_snapshot", False))
            if has_snapshot:
                games_with_score_snapshots += 1
            last_scores = dict(stats.get("last_scores", {}) or {})
            final_total_vp = _safe_float(sum(float(v) for v in list(last_scores.values() or [])), default=0.0)
            progressed = bool(stats.get("scoring_progress", False))
            if final_total_vp > 0.0:
                progressed = True
            if progressed:
                games_with_scoring_progress += 1
            combat_count = int(stats.get("combat_decisions", 0) or 0)
            if combat_count > 0 or progressed:
                games_with_combat_or_scoring_activity += 1
            if final_total_vp >= float(gate_profile.minimum_nontrivial_total_vp):
                games_with_nontrivial_vp += 1

        minimum_tactical = int(min(tactical_values or [0]))
        mean_tactical = _ratio(total_tactical, games_observed)
    else:
        mean_tactical = 0.0

    scoring_progress_ratio = _ratio(games_with_scoring_progress, games_observed)
    no_progress_games = max(0, games_observed - games_with_scoring_progress)
    no_progress_ratio = _ratio(no_progress_games, games_observed)

    return {
        "games_observed": games_observed,
        "records_with_game_id": int(records_with_game_id),
        "records_with_game_id_ratio": _ratio(records_with_game_id, total_records),
        "total_tactical_decisions": int(total_tactical),
        "minimum_tactical_decisions_per_game": int(minimum_tactical),
        "mean_tactical_decisions_per_game": float(mean_tactical),
        "combat_decisions": int(combat_decisions),
        "combat_decision_ratio": _ratio(combat_decisions, total_records),
        "games_with_score_snapshots": int(games_with_score_snapshots),
        "games_with_score_snapshots_ratio": _ratio(games_with_score_snapshots, games_observed),
        "games_with_scoring_progress": int(games_with_scoring_progress),
        "scoring_progress_game_ratio": float(scoring_progress_ratio),
        "no_progress_game_ratio": float(no_progress_ratio),
        "games_with_combat_or_scoring_activity": int(games_with_combat_or_scoring_activity),
        "combat_or_scoring_active_game_ratio": _ratio(games_with_combat_or_scoring_activity, games_observed),
        "games_with_nontrivial_vp": int(games_with_nontrivial_vp),
        "nontrivial_vp_game_ratio": _ratio(games_with_nontrivial_vp, games_observed),
        "minimum_nontrivial_total_vp": int(gate_profile.minimum_nontrivial_total_vp),
    }


@dataclass(frozen=True)
class TrainingDataManifest:
    manifest_version: str
    generated_at_utc: str
    source_tag: str
    total_records: int
    rules_bundle_ids: tuple[str, ...]
    descriptor_bundle_ids: tuple[str, ...]
    decision_type_counts: dict[str, int]
    coverage: dict[str, Any]
    gameplay_quality: dict[str, Any]
    gate_requirements: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_version": str(self.manifest_version or ""),
            "generated_at_utc": str(self.generated_at_utc or ""),
            "source_tag": str(self.source_tag or ""),
            "total_records": int(self.total_records),
            "rules_bundle_ids": list(self.rules_bundle_ids),
            "descriptor_bundle_ids": list(self.descriptor_bundle_ids),
            "decision_type_counts": {str(k): int(v) for k, v in sorted(self.decision_type_counts.items())},
            "coverage": dict(self.coverage or {}),
            "gameplay_quality": dict(self.gameplay_quality or {}),
            "gate_requirements": dict(self.gate_requirements or {}),
        }


def build_training_manifest(
    records: list[dict[str, Any]],
    *,
    source_tag: str,
    min_tier3_records: int = 10000,
    gate_profile_id: str = PRE_ML_BASELINE_GATE_PROFILE_ID,
) -> TrainingDataManifest:
    record_list = [dict(record or {}) for record in list(records or [])]
    total_records = int(len(record_list))
    decision_type_counts = _decision_type_counts(record_list)
    coverage = _coverage(record_list)
    gate_profile = _resolve_gate_profile(gate_profile_id)
    gameplay_quality = _gameplay_quality(record_list, gate_profile=gate_profile)
    semantic_ratio = float(coverage.get("semantic_candidate_metadata_ratio", 0.0) or 0.0)
    relabel_ratio = float(coverage.get("relabel_status_ratio", 0.0) or 0.0)
    deployment_semantic_ratio = float(coverage.get("deployment_semantic_metadata_ratio", 1.0) or 0.0)
    deployment_related_records = int(coverage.get("deployment_related_records", 0) or 0)
    deployment_semantic_records = int(coverage.get("deployment_records_with_semantic_metadata", 0) or 0)
    profile_min_records = int(gate_profile.minimum_tier3_pretraining_records)
    profile_semantic_ratio = float(gate_profile.required_semantic_candidate_metadata_ratio)
    profile_relabel_ratio = float(gate_profile.required_relabel_status_ratio)
    required_deployment_semantic_ratio = 1.0
    profile_min_games = int(gate_profile.minimum_games_observed)
    profile_game_id_ratio = float(gate_profile.required_records_with_game_id_ratio)
    profile_min_tactical = int(gate_profile.minimum_tactical_decisions_per_game)
    profile_activity_ratio = float(gate_profile.required_combat_or_scoring_active_game_ratio)
    profile_max_no_progress_ratio = float(gate_profile.maximum_no_progress_game_ratio)
    profile_nontrivial_ratio = float(gate_profile.required_nontrivial_vp_game_ratio)
    profile_min_nontrivial_total_vp = int(gate_profile.minimum_nontrivial_total_vp)
    meets_profile_minimum = bool(total_records >= profile_min_records)
    meets_profile_semantic = bool(semantic_ratio >= profile_semantic_ratio)
    meets_profile_relabel = bool(relabel_ratio >= profile_relabel_ratio)
    meets_deployment_semantic = bool(deployment_semantic_ratio >= required_deployment_semantic_ratio)
    games_observed = int(gameplay_quality.get("games_observed", 0) or 0)
    records_with_game_id_ratio = float(gameplay_quality.get("records_with_game_id_ratio", 0.0) or 0.0)
    min_tactical_decisions = int(gameplay_quality.get("minimum_tactical_decisions_per_game", 0) or 0)
    combat_or_scoring_ratio = float(
        gameplay_quality.get("combat_or_scoring_active_game_ratio", 0.0) or 0.0
    )
    no_progress_ratio = float(gameplay_quality.get("no_progress_game_ratio", 0.0) or 0.0)
    nontrivial_vp_ratio = float(gameplay_quality.get("nontrivial_vp_game_ratio", 0.0) or 0.0)
    meets_profile_games_observed = bool(games_observed >= profile_min_games)
    meets_profile_game_id_ratio = bool(records_with_game_id_ratio >= profile_game_id_ratio)
    meets_profile_tactical = bool(min_tactical_decisions >= profile_min_tactical)
    meets_profile_activity = bool(combat_or_scoring_ratio >= profile_activity_ratio)
    meets_profile_no_progress = bool(no_progress_ratio <= profile_max_no_progress_ratio)
    meets_profile_nontrivial = bool(nontrivial_vp_ratio >= profile_nontrivial_ratio)
    gate_requirements = {
        "minimum_tier3_pretraining_records": int(min_tier3_records),
        "meets_minimum_tier3_pretraining_records": bool(total_records >= int(min_tier3_records)),
        "semantic_candidate_metadata_required": True,
        "semantic_candidate_metadata_complete": bool(
            coverage.get("records_with_semantic_candidate_metadata", 0) == total_records
        ),
        "deployment_semantic_metadata_required": True,
        "deployment_semantic_metadata_complete": bool(
            deployment_semantic_records == deployment_related_records
        ),
        "gate_profile_id": str(gate_profile.gate_profile_id),
        "gate_profile_minimum_tier3_pretraining_records": profile_min_records,
        "required_semantic_candidate_metadata_ratio": profile_semantic_ratio,
        "required_relabel_status_ratio": profile_relabel_ratio,
        "required_deployment_semantic_metadata_ratio": float(required_deployment_semantic_ratio),
        "gate_profile_minimum_games_observed": profile_min_games,
        "required_records_with_game_id_ratio": profile_game_id_ratio,
        "gate_profile_minimum_tactical_decisions_per_game": profile_min_tactical,
        "required_combat_or_scoring_active_game_ratio": profile_activity_ratio,
        "maximum_no_progress_game_ratio": profile_max_no_progress_ratio,
        "required_nontrivial_vp_game_ratio": profile_nontrivial_ratio,
        "minimum_nontrivial_total_vp": profile_min_nontrivial_total_vp,
        "meets_gate_profile_minimum_tier3_pretraining_records": meets_profile_minimum,
        "meets_required_semantic_candidate_metadata_ratio": meets_profile_semantic,
        "meets_required_relabel_status_ratio": meets_profile_relabel,
        "meets_required_deployment_semantic_metadata_ratio": meets_deployment_semantic,
        "meets_gate_profile_minimum_games_observed": meets_profile_games_observed,
        "meets_required_records_with_game_id_ratio": meets_profile_game_id_ratio,
        "meets_gate_profile_minimum_tactical_decisions_per_game": meets_profile_tactical,
        "meets_required_combat_or_scoring_active_game_ratio": meets_profile_activity,
        "meets_maximum_no_progress_game_ratio": meets_profile_no_progress,
        "meets_required_nontrivial_vp_game_ratio": meets_profile_nontrivial,
        "meets_gate_profile": bool(
            meets_profile_minimum
            and meets_profile_semantic
            and meets_profile_relabel
            and meets_deployment_semantic
            and meets_profile_games_observed
            and meets_profile_game_id_ratio
            and meets_profile_tactical
            and meets_profile_activity
            and meets_profile_no_progress
            and meets_profile_nontrivial
        ),
    }
    return TrainingDataManifest(
        manifest_version=MANIFEST_VERSION,
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        source_tag=str(source_tag or ""),
        total_records=total_records,
        rules_bundle_ids=tuple(_rules_bundle_ids(record_list)),
        descriptor_bundle_ids=tuple(_descriptor_bundle_ids(record_list)),
        decision_type_counts=decision_type_counts,
        coverage=coverage,
        gameplay_quality=gameplay_quality,
        gate_requirements=gate_requirements,
    )


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
        "decision_type_counts",
        "coverage",
        "gameplay_quality",
        "gate_requirements",
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

    rules_bundle_ids = payload.get("rules_bundle_ids")
    if not isinstance(rules_bundle_ids, list):
        errors.append("rules_bundle_ids must be a list")
    descriptor_bundle_ids = payload.get("descriptor_bundle_ids")
    if not isinstance(descriptor_bundle_ids, list):
        errors.append("descriptor_bundle_ids must be a list")

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
