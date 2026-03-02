from __future__ import annotations

import copy
from typing import Any

from .ruleset import RulesetBundle


RELABEL_STATUS_NOT_RELABELED = "NOT_RELABELED"
RELABEL_STATUS_LEGAL_SEMANTICALLY_COMPARABLE = "RELABELED_LEGAL_SEMANTICALLY_COMPARABLE"
RELABEL_STATUS_LEGAL_VALUE_CHANGED = "RELABELED_LEGAL_VALUE_CHANGED"
RELABEL_STATUS_INVALID_UNDER_TARGET_BUNDLE = "RELABELED_INVALID_UNDER_TARGET_BUNDLE"
RELABEL_STATUS_MAPPED_TO_ANALOGUE = "RELABELED_MAPPED_TO_ANALOGUE"
RELABEL_STATUS_UNREPRESENTABLE = "RELABELED_UNREPRESENTABLE"
RELABEL_STATUS_FAILED = "RELABEL_FAILED"

CHOSEN_ACTION_STATUS_LEGAL_SEMANTICALLY_COMPARABLE = "LEGAL_SEMANTICALLY_COMPARABLE"
CHOSEN_ACTION_STATUS_LEGAL_VALUE_CHANGED = "LEGAL_VALUE_CHANGED"
CHOSEN_ACTION_STATUS_INVALID_UNDER_TARGET_BUNDLE = "INVALID_UNDER_TARGET_BUNDLE"
CHOSEN_ACTION_STATUS_MAPPED_TO_ANALOGUE = "MAPPED_TO_ANALOGUE"
CHOSEN_ACTION_STATUS_UNREPRESENTABLE = "UNREPRESENTABLE"
CHOSEN_ACTION_STATUS_UNKNOWN = "UNKNOWN"

MAPPING_STATUS_UNCHANGED = "UNCHANGED"
MAPPING_STATUS_VALUE_CHANGED = "VALUE_CHANGED"
MAPPING_STATUS_MAPPED_TO_ANALOGUE = "MAPPED_TO_ANALOGUE"
MAPPING_STATUS_INVALID_UNDER_TARGET_BUNDLE = "INVALID_UNDER_TARGET_BUNDLE"
MAPPING_STATUS_UNREPRESENTABLE = "UNREPRESENTABLE"
MAPPING_STATUS_NOT_FOUND = "NOT_FOUND"

_SEMANTIC_METADATA_NUMERIC_KEYS = (
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
)


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _candidate_ids(record: dict[str, Any]) -> set[str]:
    action_ids: set[str] = set()
    for candidate in list(record.get("candidates", []) or []):
        action_id = str(dict(candidate or {}).get("action_id", "") or "")
        if action_id:
            action_ids.add(action_id)
    return action_ids


def _normalized_rules_provenance_refs(
    metadata: dict[str, Any],
    *,
    target_rules_bundle_id: str,
) -> list[str]:
    refs = metadata.get("rules_provenance_refs", [])
    if not isinstance(refs, list):
        refs = []
    normalized = {str(ref) for ref in refs if str(ref)}
    if target_rules_bundle_id:
        normalized.add(str(target_rules_bundle_id))
    return sorted(normalized)


def _relabel_candidate_metadata(
    metadata: dict[str, Any],
    *,
    target_rules_bundle_id: str,
) -> dict[str, Any]:
    updated = dict(metadata or {})
    for key in _SEMANTIC_METADATA_NUMERIC_KEYS:
        updated[key] = _safe_float(updated.get(key, 0.0), 0.0)
    updated["rules_provenance_refs"] = _normalized_rules_provenance_refs(
        updated,
        target_rules_bundle_id=target_rules_bundle_id,
    )
    updated["relabel_generated"] = True
    return updated


def _mapping_status_for_candidate(
    *,
    action_id: str,
    mask_value: bool,
    source_rules_bundle_id: str,
    target_rules_bundle_id: str,
) -> tuple[str, str]:
    if not action_id:
        return MAPPING_STATUS_UNREPRESENTABLE, "Candidate action_id is missing."
    if not mask_value:
        return (
            MAPPING_STATUS_INVALID_UNDER_TARGET_BUNDLE,
            "Candidate was masked illegal in source record.",
        )
    if source_rules_bundle_id == target_rules_bundle_id:
        return MAPPING_STATUS_UNCHANGED, "Rules bundle is unchanged."
    return (
        MAPPING_STATUS_VALUE_CHANGED,
        "Semantic metadata refreshed under target rules bundle.",
    )


def _chosen_action_status_from_mapping(mapping_status: str) -> str:
    if mapping_status == MAPPING_STATUS_UNCHANGED:
        return CHOSEN_ACTION_STATUS_LEGAL_SEMANTICALLY_COMPARABLE
    if mapping_status == MAPPING_STATUS_VALUE_CHANGED:
        return CHOSEN_ACTION_STATUS_LEGAL_VALUE_CHANGED
    if mapping_status == MAPPING_STATUS_MAPPED_TO_ANALOGUE:
        return CHOSEN_ACTION_STATUS_MAPPED_TO_ANALOGUE
    if mapping_status == MAPPING_STATUS_INVALID_UNDER_TARGET_BUNDLE:
        return CHOSEN_ACTION_STATUS_INVALID_UNDER_TARGET_BUNDLE
    if mapping_status == MAPPING_STATUS_UNREPRESENTABLE:
        return CHOSEN_ACTION_STATUS_UNREPRESENTABLE
    return CHOSEN_ACTION_STATUS_UNKNOWN


def _relabel_status_from_chosen(chosen_action_status: str) -> str:
    if chosen_action_status == CHOSEN_ACTION_STATUS_LEGAL_SEMANTICALLY_COMPARABLE:
        return RELABEL_STATUS_LEGAL_SEMANTICALLY_COMPARABLE
    if chosen_action_status == CHOSEN_ACTION_STATUS_LEGAL_VALUE_CHANGED:
        return RELABEL_STATUS_LEGAL_VALUE_CHANGED
    if chosen_action_status == CHOSEN_ACTION_STATUS_MAPPED_TO_ANALOGUE:
        return RELABEL_STATUS_MAPPED_TO_ANALOGUE
    if chosen_action_status == CHOSEN_ACTION_STATUS_INVALID_UNDER_TARGET_BUNDLE:
        return RELABEL_STATUS_INVALID_UNDER_TARGET_BUNDLE
    if chosen_action_status == CHOSEN_ACTION_STATUS_UNREPRESENTABLE:
        return RELABEL_STATUS_UNREPRESENTABLE
    return RELABEL_STATUS_FAILED


def relabel_decision_record(
    record: dict[str, Any],
    *,
    target_rules_bundle: RulesetBundle,
) -> dict[str, Any]:
    relabeled = copy.deepcopy(dict(record or {}))
    candidates = [dict(candidate or {}) for candidate in list(relabeled.get("candidates", []) or [])]
    mask = [bool(value) for value in list(relabeled.get("mask", []) or [])]
    if len(mask) != len(candidates):
        mask = [True] * len(candidates)
        relabeled["mask"] = list(mask)

    source_rules_bundle_id = str(relabeled.get("rules_bundle_id", "") or "")
    target_rules_bundle_id = str(target_rules_bundle.rules_bundle_id or "")
    relabel_candidate_map: dict[str, dict[str, str]] = {}

    for idx, candidate in enumerate(candidates):
        action_id = str(candidate.get("action_id", "") or "")
        mapping_status, reason = _mapping_status_for_candidate(
            action_id=action_id,
            mask_value=bool(mask[idx]) if idx < len(mask) else True,
            source_rules_bundle_id=source_rules_bundle_id,
            target_rules_bundle_id=target_rules_bundle_id,
        )
        if action_id:
            relabel_candidate_map[action_id] = {
                "mapped_action_id": action_id,
                "mapping_status": mapping_status,
                "reason": reason,
            }
        candidate["metadata"] = _relabel_candidate_metadata(
            dict(candidate.get("metadata", {}) or {}),
            target_rules_bundle_id=target_rules_bundle_id,
        )

    relabeled["candidates"] = candidates

    chosen_action_status = CHOSEN_ACTION_STATUS_UNKNOWN
    chosen_action_id = str(relabeled.get("chosen_action_id", "") or "")
    valid_flag = bool(relabeled.get("valid", True))
    if valid_flag and chosen_action_id:
        mapping = relabel_candidate_map.get(chosen_action_id)
        if mapping is None:
            chosen_action_status = CHOSEN_ACTION_STATUS_INVALID_UNDER_TARGET_BUNDLE
            relabel_candidate_map[chosen_action_id] = {
                "mapped_action_id": "",
                "mapping_status": MAPPING_STATUS_NOT_FOUND,
                "reason": "Chosen action_id is missing from candidates under relabel.",
            }
        else:
            chosen_action_status = _chosen_action_status_from_mapping(
                str(mapping.get("mapping_status", "") or "")
            )

    relabeled["relabel_rules_bundle"] = target_rules_bundle.to_dict()
    relabeled["relabel_rules_bundle_id"] = target_rules_bundle_id
    relabeled["relabel_candidate_map"] = relabel_candidate_map
    relabeled["chosen_action_status_under_relabel"] = chosen_action_status
    relabeled["relabel_status"] = _relabel_status_from_chosen(chosen_action_status)
    relabeled["relabel_notes"] = (
        "Semantic metadata regenerated under target rules bundle; legality mapping uses "
        "record candidate/mask compatibility."
    )
    return relabeled


def relabel_decision_records(
    records: list[dict[str, Any]],
    *,
    target_rules_bundle: RulesetBundle,
) -> list[dict[str, Any]]:
    return [
        relabel_decision_record(record, target_rules_bundle=target_rules_bundle)
        for record in list(records or [])
    ]
