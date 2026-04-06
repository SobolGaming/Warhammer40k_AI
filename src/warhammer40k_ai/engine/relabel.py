from __future__ import annotations

import copy
from typing import Any

from .candidate_semantics import SEMANTIC_NUMERIC_KEYS, normalize_candidate_semantic_metadata
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


def _relabel_candidate_metadata(
    *,
    decision_type: str,
    params: dict[str, Any],
    metadata: dict[str, Any],
    context: dict[str, Any],
    target_rules_bundle_id: str,
    target_rules_bundle: dict[str, Any],
    recompute_semantics: bool,
) -> dict[str, Any]:
    updated = normalize_candidate_semantic_metadata(
        decision_type=decision_type,
        params=dict(params or {}),
        metadata=dict(metadata or {}),
        context=dict(context or {}),
        rules_bundle_id=target_rules_bundle_id,
        rules_bundle=dict(target_rules_bundle or {}),
        overwrite_existing=bool(recompute_semantics),
    )
    updated["relabel_generated"] = True
    for key in SEMANTIC_NUMERIC_KEYS:
        updated[key] = float(updated.get(key, 0.0))
    return updated


def _relabel_context(record: dict[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {}
    phase = str(record.get("phase", "") or "")
    if phase:
        context["phase"] = phase
    descriptor_bundle_id = str(record.get("descriptor_bundle_id", "") or "")
    if descriptor_bundle_id:
        context["descriptor_bundle_id"] = descriptor_bundle_id
    descriptor_ids = dict(record.get("descriptor_ids", {}) or {})
    if descriptor_ids:
        context["descriptor_ids"] = descriptor_ids
        context["tool_descriptor_ids"] = list(descriptor_ids.get("tool_descriptor_ids", []) or [])
    version_adapter_boundary = dict(record.get("version_adapter_boundary", {}) or {})
    if version_adapter_boundary:
        context["version_adapter_boundary"] = version_adapter_boundary
    omniscient_state = record.get("omniscient_state")
    if isinstance(omniscient_state, dict):
        for key in (
            "army_build_state",
            "deployment_state",
            "movement_intent",
            "score_window_state",
            "opportunity_catalog",
            "mission_state",
            "objectives",
            "scoring_surfaces",
            "control_regions",
            "terrain_state_summary",
            "cp_reserve_policy",
        ):
            value = omniscient_state.get(key)
            if isinstance(value, dict):
                context[key] = dict(value)
            elif isinstance(value, list):
                context[key] = [dict(item or {}) if isinstance(item, dict) else item for item in list(value or [])]
    return context


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
    semantic_context = _relabel_context(relabeled)
    target_bundle_payload = target_rules_bundle.to_dict()
    recompute_semantics = source_rules_bundle_id != target_rules_bundle_id

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
            decision_type=str(relabeled.get("decision_type", "") or ""),
            params=dict(candidate.get("params", {}) or {}),
            metadata=dict(candidate.get("metadata", {}) or {}),
            context=semantic_context,
            target_rules_bundle_id=target_rules_bundle_id,
            target_rules_bundle=target_bundle_payload,
            recompute_semantics=recompute_semantics,
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
