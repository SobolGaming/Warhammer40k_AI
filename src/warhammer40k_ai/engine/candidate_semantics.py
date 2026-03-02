from __future__ import annotations

from typing import Any

from .decisions import CandidateAction, DecisionRequest
from .decision_kinds import (
    DECISION_ALLOCATE_TARGETS,
    DECISION_DECLARE_CHARGE,
    DECISION_DECLARE_MELEE_WEAPONS,
    DECISION_DECLARE_SHOTS,
    DECISION_MOVE_UNIT,
    DECISION_PICK_OBJECTIVE,
    DECISION_PICK_POINT,
    DECISION_SELECT_TARGET_MODEL,
)


SEMANTIC_NUMERIC_KEYS = (
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


def _is_non_noop_candidate(params: dict[str, Any]) -> bool:
    action = str(params.get("action", "") or "").strip().lower()
    return action not in ("", "skip", "none", "noop")


def _heuristic_defaults(
    *,
    decision_type: str,
    params: dict[str, Any],
) -> dict[str, float]:
    defaults = {key: 0.0 for key in SEMANTIC_NUMERIC_KEYS}
    if decision_type == DECISION_MOVE_UNIT and _is_non_noop_candidate(params):
        defaults["projected_control_delta"] = 0.1
        defaults["projected_action_enablement_delta"] = 0.1
    elif decision_type in (DECISION_PICK_OBJECTIVE, DECISION_PICK_POINT) and _is_non_noop_candidate(params):
        defaults["projected_score_delta_next_window"] = 0.2
        defaults["projected_control_delta"] = 0.2
    elif decision_type in (
        DECISION_DECLARE_SHOTS,
        DECISION_SELECT_TARGET_MODEL,
        DECISION_DECLARE_MELEE_WEAPONS,
        DECISION_ALLOCATE_TARGETS,
    ) and _is_non_noop_candidate(params):
        defaults["projected_trade_ev"] = 0.2
        defaults["projected_exposure_delta"] = -0.1
    elif decision_type == DECISION_DECLARE_CHARGE and _is_non_noop_candidate(params):
        defaults["projected_trade_ev"] = 0.15
        defaults["projected_exposure_delta"] = -0.2
    return defaults


def _rules_provenance_refs(metadata: dict[str, Any], *, rules_bundle_id: str) -> list[str]:
    refs = metadata.get("rules_provenance_refs", [])
    if not isinstance(refs, list):
        refs = []
    normalized = {str(ref) for ref in refs if str(ref)}
    if str(rules_bundle_id or ""):
        normalized.add(str(rules_bundle_id))
    return sorted(normalized)


def ensure_candidate_semantic_metadata(
    request: DecisionRequest,
    *,
    rules_bundle_id: str,
) -> None:
    decision_type = str(getattr(request, "decision_type", "") or "")
    normalized_candidates: list[CandidateAction] = []
    for candidate in list(getattr(request, "candidates", []) or []):
        params = dict(candidate.params or {})
        metadata = dict(candidate.metadata or {})
        defaults = _heuristic_defaults(decision_type=decision_type, params=params)
        for key, default_value in defaults.items():
            metadata[key] = _safe_float(metadata.get(key, default_value), default_value)
        metadata["rules_provenance_refs"] = _rules_provenance_refs(
            metadata,
            rules_bundle_id=rules_bundle_id,
        )
        normalized_candidates.append(
            CandidateAction(
                action_id=str(candidate.action_id or ""),
                params=params,
                metadata=metadata,
            )
        )
    request.candidates = normalized_candidates
