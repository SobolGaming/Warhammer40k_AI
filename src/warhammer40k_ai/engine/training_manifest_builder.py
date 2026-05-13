from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable

from .training_manifest_schema import (
    MANIFEST_VERSION,
    PRE_ML_BASELINE_GATE_PROFILE_ID,
    TrainingDataManifest,
    TrainingManifestSlice,
    _normalize_str_tuple,
    _ratio,
    _resolve_gate_profile,
    _safe_float,
)


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
    "REACTIVE_MOVE",
    "SURGE_MOVE",
    "SELECT_REACTIVE_RESERVE_EXIT",
    "SELECT_UNIT",
    "SELECT_MOVEMENT_ACTION",
    "DECLARE_SHOTS",
    "DECLARE_CHARGE",
    "SELECT_HEROIC_INTERVENTION_MODE",
    "SELECT_STRATAGEM_MODE",
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
    "SELECT_HEROIC_INTERVENTION_MODE",
    "SELECT_FIGHT_TARGETS",
    "DECLARE_MELEE_WEAPONS",
    "ALLOCATE_MELEE_TARGETS",
    "ALLOCATE_TARGETS",
    "SPLIT_ATTACKS",
    "SELECT_TARGET_MODEL",
    "SELECT_PRECISION_TARGET",
}


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


def _record_descriptor_ids(record: dict[str, Any]) -> dict[str, Any]:
    return dict(record.get("descriptor_ids", {}) or {})


def _record_descriptor_bundle_id(record: dict[str, Any]) -> str:
    explicit = str(record.get("descriptor_bundle_id", "") or "")
    if explicit:
        return explicit
    descriptor_ids = _record_descriptor_ids(record)
    if not descriptor_ids:
        return ""
    return _descriptor_bundle_fingerprint(descriptor_ids)


def _decision_type_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in list(records or []):
        decision_type = str(record.get("decision_type", "") or "UNKNOWN")
        counts[decision_type] = int(counts.get(decision_type, 0) or 0) + 1
    return {key: counts[key] for key in sorted(counts.keys())}


def _rules_bundle_ids(records: list[dict[str, Any]]) -> tuple[str, ...]:
    ids = {
        str(record.get("rules_bundle_id", "") or "")
        for record in list(records or [])
        if str(record.get("rules_bundle_id", "") or "")
    }
    return tuple(sorted(ids))


def _descriptor_bundle_ids(records: list[dict[str, Any]]) -> tuple[str, ...]:
    ids: set[str] = set()
    for record in list(records or []):
        bundle_id = _record_descriptor_bundle_id(record)
        if bundle_id:
            ids.add(bundle_id)
    return tuple(sorted(ids))


def _descriptor_family_ids(records: list[dict[str, Any]], key: str) -> tuple[str, ...]:
    values: set[str] = set()
    for record in list(records or []):
        descriptor_ids = _record_descriptor_ids(record)
        raw_value = descriptor_ids.get(key)
        if isinstance(raw_value, list):
            values.update(str(item) for item in list(raw_value or []) if str(item))
            continue
        text = str(raw_value or "")
        if text:
            values.add(text)
    return tuple(sorted(values))


def build_training_manifest_slice(
    *,
    rules_bundle_ids: list[str] | tuple[str, ...] | None = None,
    descriptor_bundle_ids: list[str] | tuple[str, ...] | None = None,
    mission_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    objective_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    terrain_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    deployment_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    army_build_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    tool_descriptor_ids: list[str] | tuple[str, ...] | None = None,
) -> TrainingManifestSlice:
    return TrainingManifestSlice(
        rules_bundle_ids=_normalize_str_tuple(rules_bundle_ids),
        descriptor_bundle_ids=_normalize_str_tuple(descriptor_bundle_ids),
        mission_descriptor_ids=_normalize_str_tuple(mission_descriptor_ids),
        objective_descriptor_ids=_normalize_str_tuple(objective_descriptor_ids),
        terrain_descriptor_ids=_normalize_str_tuple(terrain_descriptor_ids),
        deployment_descriptor_ids=_normalize_str_tuple(deployment_descriptor_ids),
        army_build_descriptor_ids=_normalize_str_tuple(army_build_descriptor_ids),
        tool_descriptor_ids=_normalize_str_tuple(tool_descriptor_ids),
    )


def _record_matches_slice(record: dict[str, Any], slice_filters: TrainingManifestSlice) -> bool:
    if slice_filters.is_empty():
        return True
    descriptor_ids = _record_descriptor_ids(record)
    rules_bundle_id = str(record.get("rules_bundle_id", "") or "")
    descriptor_bundle_id = _record_descriptor_bundle_id(record)
    mission_descriptor_id = str(descriptor_ids.get("mission_descriptor_id", "") or "")
    deployment_descriptor_id = str(descriptor_ids.get("deployment_descriptor_id", "") or "")
    army_build_descriptor_id = str(descriptor_ids.get("army_build_descriptor_id", "") or "")
    objective_descriptor_ids = {str(item) for item in list(descriptor_ids.get("objective_descriptor_ids", []) or []) if str(item)}
    terrain_descriptor_ids = {str(item) for item in list(descriptor_ids.get("terrain_descriptor_ids", []) or []) if str(item)}
    tool_descriptor_ids = {str(item) for item in list(descriptor_ids.get("tool_descriptor_ids", []) or []) if str(item)}

    if slice_filters.rules_bundle_ids and rules_bundle_id not in set(slice_filters.rules_bundle_ids):
        return False
    if slice_filters.descriptor_bundle_ids and descriptor_bundle_id not in set(slice_filters.descriptor_bundle_ids):
        return False
    if slice_filters.mission_descriptor_ids and mission_descriptor_id not in set(slice_filters.mission_descriptor_ids):
        return False
    if (
        slice_filters.deployment_descriptor_ids
        and deployment_descriptor_id not in set(slice_filters.deployment_descriptor_ids)
    ):
        return False
    if (
        slice_filters.army_build_descriptor_ids
        and army_build_descriptor_id not in set(slice_filters.army_build_descriptor_ids)
    ):
        return False
    if slice_filters.objective_descriptor_ids and objective_descriptor_ids.isdisjoint(
        set(slice_filters.objective_descriptor_ids)
    ):
        return False
    if slice_filters.terrain_descriptor_ids and terrain_descriptor_ids.isdisjoint(
        set(slice_filters.terrain_descriptor_ids)
    ):
        return False
    if slice_filters.tool_descriptor_ids and tool_descriptor_ids.isdisjoint(set(slice_filters.tool_descriptor_ids)):
        return False
    return True


def filter_training_records(
    records: list[dict[str, Any]],
    *,
    slice_filters: TrainingManifestSlice | None = None,
    rules_bundle_ids: list[str] | tuple[str, ...] | None = None,
    descriptor_bundle_ids: list[str] | tuple[str, ...] | None = None,
    mission_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    objective_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    terrain_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    deployment_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    army_build_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    tool_descriptor_ids: list[str] | tuple[str, ...] | None = None,
) -> tuple[list[dict[str, Any]], TrainingManifestSlice]:
    normalized = slice_filters or build_training_manifest_slice(
        rules_bundle_ids=rules_bundle_ids,
        descriptor_bundle_ids=descriptor_bundle_ids,
        mission_descriptor_ids=mission_descriptor_ids,
        objective_descriptor_ids=objective_descriptor_ids,
        terrain_descriptor_ids=terrain_descriptor_ids,
        deployment_descriptor_ids=deployment_descriptor_ids,
        army_build_descriptor_ids=army_build_descriptor_ids,
        tool_descriptor_ids=tool_descriptor_ids,
    )
    if normalized.is_empty():
        return [dict(record or {}) for record in list(records or [])], normalized
    filtered = [
        dict(record or {})
        for record in list(records or [])
        if _record_matches_slice(dict(record or {}), normalized)
    ]
    return filtered, normalized


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
    gate_profile,
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
            final_total_vp = _safe_float(sum(float(value) for value in list(last_scores.values() or [])), default=0.0)
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


def _empty_gameplay_quality(*, gate_profile) -> dict[str, Any]:
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


def _finalize_gameplay_quality(
    *,
    total_records: int,
    records_with_game_id: int,
    combat_decisions: int,
    game_stats: dict[str, dict[str, Any]],
    gate_profile,
) -> dict[str, Any]:
    if total_records <= 0:
        return _empty_gameplay_quality(gate_profile=gate_profile)

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
            final_total_vp = _safe_float(sum(float(value) for value in list(last_scores.values() or [])), default=0.0)
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


def _normalized_manifest_slice(
    *,
    slice_filters: TrainingManifestSlice | None = None,
    rules_bundle_ids: list[str] | tuple[str, ...] | None = None,
    descriptor_bundle_ids: list[str] | tuple[str, ...] | None = None,
    mission_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    objective_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    terrain_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    deployment_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    army_build_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    tool_descriptor_ids: list[str] | tuple[str, ...] | None = None,
) -> TrainingManifestSlice:
    return slice_filters or build_training_manifest_slice(
        rules_bundle_ids=rules_bundle_ids,
        descriptor_bundle_ids=descriptor_bundle_ids,
        mission_descriptor_ids=mission_descriptor_ids,
        objective_descriptor_ids=objective_descriptor_ids,
        terrain_descriptor_ids=terrain_descriptor_ids,
        deployment_descriptor_ids=deployment_descriptor_ids,
        army_build_descriptor_ids=army_build_descriptor_ids,
        tool_descriptor_ids=tool_descriptor_ids,
    )


def _manifest_from_metrics(
    *,
    source_tag: str,
    min_tier3_records: int,
    gate_profile_id: str,
    normalized_slice: TrainingManifestSlice,
    total_records: int,
    decision_type_counts: dict[str, int],
    coverage: dict[str, Any],
    gameplay_quality: dict[str, Any],
    rules_bundle_ids: set[str],
    descriptor_bundle_ids: set[str],
    mission_descriptor_ids: set[str],
    objective_descriptor_ids: set[str],
    terrain_descriptor_ids: set[str],
    deployment_descriptor_ids: set[str],
    army_build_descriptor_ids: set[str],
    tool_descriptor_ids: set[str],
) -> TrainingDataManifest:
    gate_profile = _resolve_gate_profile(gate_profile_id)
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
        total_records=int(total_records),
        rules_bundle_ids=tuple(sorted(rules_bundle_ids)),
        descriptor_bundle_ids=tuple(sorted(descriptor_bundle_ids)),
        mission_descriptor_ids=tuple(sorted(mission_descriptor_ids)),
        objective_descriptor_ids=tuple(sorted(objective_descriptor_ids)),
        terrain_descriptor_ids=tuple(sorted(terrain_descriptor_ids)),
        deployment_descriptor_ids=tuple(sorted(deployment_descriptor_ids)),
        army_build_descriptor_ids=tuple(sorted(army_build_descriptor_ids)),
        tool_descriptor_ids=tuple(sorted(tool_descriptor_ids)),
        decision_type_counts={key: int(decision_type_counts[key]) for key in sorted(decision_type_counts.keys())},
        coverage=coverage,
        gameplay_quality=gameplay_quality,
        gate_requirements=gate_requirements,
        slice_filters=normalized_slice,
    )


def build_training_manifest_from_records(
    records: Iterable[dict[str, Any]],
    *,
    source_tag: str,
    min_tier3_records: int = 10000,
    gate_profile_id: str = PRE_ML_BASELINE_GATE_PROFILE_ID,
    slice_filters: TrainingManifestSlice | None = None,
    rules_bundle_ids: list[str] | tuple[str, ...] | None = None,
    descriptor_bundle_ids: list[str] | tuple[str, ...] | None = None,
    mission_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    objective_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    terrain_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    deployment_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    army_build_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    tool_descriptor_ids: list[str] | tuple[str, ...] | None = None,
) -> TrainingDataManifest:
    normalized_slice = _normalized_manifest_slice(
        slice_filters=slice_filters,
        rules_bundle_ids=rules_bundle_ids,
        descriptor_bundle_ids=descriptor_bundle_ids,
        mission_descriptor_ids=mission_descriptor_ids,
        objective_descriptor_ids=objective_descriptor_ids,
        terrain_descriptor_ids=terrain_descriptor_ids,
        deployment_descriptor_ids=deployment_descriptor_ids,
        army_build_descriptor_ids=army_build_descriptor_ids,
        tool_descriptor_ids=tool_descriptor_ids,
    )

    total_records = 0
    with_semantics = 0
    relabeled = 0
    deployment_related = 0
    deployment_zone_choice_records = 0
    declare_reserves_records = 0
    select_next_deploy_unit_records = 0
    scout_move_records = 0
    deployment_move_records = 0
    deployment_semantic_records = 0
    records_with_game_id = 0
    combat_decisions = 0
    decision_type_counts: dict[str, int] = {}
    rules_bundle_id_set: set[str] = set()
    descriptor_bundle_id_set: set[str] = set()
    mission_descriptor_id_set: set[str] = set()
    objective_descriptor_id_set: set[str] = set()
    terrain_descriptor_id_set: set[str] = set()
    deployment_descriptor_id_set: set[str] = set()
    army_build_descriptor_id_set: set[str] = set()
    tool_descriptor_id_set: set[str] = set()
    game_stats: dict[str, dict[str, Any]] = {}

    for raw_record in records:
        item = dict(raw_record or {})
        if not _record_matches_slice(item, normalized_slice):
            continue
        total_records += 1
        decision_type = str(item.get("decision_type", "") or "UNKNOWN")
        decision_type_counts[decision_type] = int(decision_type_counts.get(decision_type, 0) or 0) + 1

        rules_bundle_id = str(item.get("rules_bundle_id", "") or "")
        if rules_bundle_id:
            rules_bundle_id_set.add(rules_bundle_id)
        descriptor_bundle_id = _record_descriptor_bundle_id(item)
        if descriptor_bundle_id:
            descriptor_bundle_id_set.add(descriptor_bundle_id)
        descriptor_ids = _record_descriptor_ids(item)
        mission_descriptor_id = str(descriptor_ids.get("mission_descriptor_id", "") or "")
        if mission_descriptor_id:
            mission_descriptor_id_set.add(mission_descriptor_id)
        deployment_descriptor_id = str(descriptor_ids.get("deployment_descriptor_id", "") or "")
        if deployment_descriptor_id:
            deployment_descriptor_id_set.add(deployment_descriptor_id)
        army_build_descriptor_id = str(descriptor_ids.get("army_build_descriptor_id", "") or "")
        if army_build_descriptor_id:
            army_build_descriptor_id_set.add(army_build_descriptor_id)
        objective_descriptor_id_set.update(
            str(value) for value in list(descriptor_ids.get("objective_descriptor_ids", []) or []) if str(value)
        )
        terrain_descriptor_id_set.update(
            str(value) for value in list(descriptor_ids.get("terrain_descriptor_ids", []) or []) if str(value)
        )
        tool_descriptor_id_set.update(
            str(value) for value in list(descriptor_ids.get("tool_descriptor_ids", []) or []) if str(value)
        )

        if _candidates_have_semantic_metadata(item):
            with_semantics += 1
        if str(item.get("relabel_status", "") or ""):
            relabeled += 1
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

        game_id = str(item.get("game_id", "") or "")
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
        if decision_type in _TACTICAL_DECISION_TYPES:
            stats["tactical_decisions"] = int(stats.get("tactical_decisions", 0) or 0) + 1
        if decision_type in _COMBAT_DECISION_TYPES:
            stats["combat_decisions"] = int(stats.get("combat_decisions", 0) or 0) + 1
            combat_decisions += 1
        scores = _extract_player_scores(item)
        if scores:
            stats["has_score_snapshot"] = True
            if _scores_changed(dict(stats.get("last_scores", {}) or {}), scores):
                stats["scoring_progress"] = True
            stats["last_scores"] = dict(scores)

    deployment_semantic_ratio = (
        1.0
        if deployment_related <= 0
        else _ratio(deployment_semantic_records, deployment_related)
    )
    coverage = {
        "records_with_semantic_candidate_metadata": int(with_semantics),
        "semantic_candidate_metadata_ratio": _ratio(with_semantics, total_records),
        "records_with_relabel_status": int(relabeled),
        "relabel_status_ratio": _ratio(relabeled, total_records),
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
    gate_profile = _resolve_gate_profile(gate_profile_id)
    gameplay_quality = _finalize_gameplay_quality(
        total_records=total_records,
        records_with_game_id=records_with_game_id,
        combat_decisions=combat_decisions,
        game_stats=game_stats,
        gate_profile=gate_profile,
    )
    return _manifest_from_metrics(
        source_tag=source_tag,
        min_tier3_records=min_tier3_records,
        gate_profile_id=gate_profile_id,
        normalized_slice=normalized_slice,
        total_records=total_records,
        decision_type_counts=decision_type_counts,
        coverage=coverage,
        gameplay_quality=gameplay_quality,
        rules_bundle_ids=rules_bundle_id_set,
        descriptor_bundle_ids=descriptor_bundle_id_set,
        mission_descriptor_ids=mission_descriptor_id_set,
        objective_descriptor_ids=objective_descriptor_id_set,
        terrain_descriptor_ids=terrain_descriptor_id_set,
        deployment_descriptor_ids=deployment_descriptor_id_set,
        army_build_descriptor_ids=army_build_descriptor_id_set,
        tool_descriptor_ids=tool_descriptor_id_set,
    )


def build_training_manifest(
    records: list[dict[str, Any]],
    *,
    source_tag: str,
    min_tier3_records: int = 10000,
    gate_profile_id: str = PRE_ML_BASELINE_GATE_PROFILE_ID,
    slice_filters: TrainingManifestSlice | None = None,
    rules_bundle_ids: list[str] | tuple[str, ...] | None = None,
    descriptor_bundle_ids: list[str] | tuple[str, ...] | None = None,
    mission_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    objective_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    terrain_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    deployment_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    army_build_descriptor_ids: list[str] | tuple[str, ...] | None = None,
    tool_descriptor_ids: list[str] | tuple[str, ...] | None = None,
) -> TrainingDataManifest:
    return build_training_manifest_from_records(
        records,
        source_tag=source_tag,
        min_tier3_records=min_tier3_records,
        gate_profile_id=gate_profile_id,
        slice_filters=slice_filters,
        rules_bundle_ids=rules_bundle_ids,
        descriptor_bundle_ids=descriptor_bundle_ids,
        mission_descriptor_ids=mission_descriptor_ids,
        objective_descriptor_ids=objective_descriptor_ids,
        terrain_descriptor_ids=terrain_descriptor_ids,
        deployment_descriptor_ids=deployment_descriptor_ids,
        army_build_descriptor_ids=army_build_descriptor_ids,
        tool_descriptor_ids=tool_descriptor_ids,
    )
__all__ = [
    "build_training_manifest",
    "build_training_manifest_from_records",
    "build_training_manifest_slice",
    "filter_training_records",
]
