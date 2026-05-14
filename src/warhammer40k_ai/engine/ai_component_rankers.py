from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .decisions import CandidateAction, DecisionRequest


METADATA_PROJECTED_SCORE_NEXT = "projected_score_delta_next_window"
METADATA_PROJECTED_SCORE_ROUND = "projected_score_delta_round"
METADATA_PROJECTED_DENY_NEXT = "projected_deny_delta_next_window"
METADATA_PROJECTED_CONTROL = "projected_control_delta"
METADATA_PROJECTED_ACTION_ENABLEMENT = "projected_action_enablement_delta"
METADATA_PROJECTED_EXPOSURE = "projected_exposure_delta"
METADATA_PROJECTED_TRADE_EV = "projected_trade_ev"
METADATA_COVER_DELTA = "cover_delta"
METADATA_LOS_DELTA = "los_delta"
METADATA_RESOURCE_DELTA = "resource_delta"

_DECLINE_ACTIONS = {"decline", "none", "noop", "pass", "skip"}


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _metadata(candidate: CandidateAction) -> dict[str, Any]:
    return dict(getattr(candidate, "metadata", {}) or {})


def _params(candidate: CandidateAction) -> dict[str, Any]:
    return dict(getattr(candidate, "params", {}) or {})


def legal_candidates(request: DecisionRequest) -> list[CandidateAction]:
    """Return deterministic legal candidates from a request, ordered by action id."""
    candidates = list(getattr(request, "candidates", []) or [])
    mask = [bool(value) for value in list(getattr(request, "mask", []) or [])]
    legal: list[CandidateAction] = []
    for index, candidate in enumerate(candidates):
        if index < len(mask) and not mask[index]:
            continue
        action_id = str(getattr(candidate, "action_id", "") or "")
        if not action_id:
            continue
        legal.append(candidate)
    return sorted(legal, key=lambda candidate: str(getattr(candidate, "action_id", "") or ""))


def action_id_is_legal(request: DecisionRequest, action_id: str) -> bool:
    wanted = str(action_id or "")
    if not wanted:
        return False
    for candidate in legal_candidates(request):
        if str(getattr(candidate, "action_id", "") or "") == wanted:
            return True
    return False


def candidate_requests_decline(candidate: CandidateAction) -> bool:
    params = _params(candidate)
    metadata = _metadata(candidate)
    action = str(params.get("action", params.get("choice", "")) or "").strip().lower()
    candidate_kind = str(metadata.get("candidate_kind", "") or "").strip().lower()
    return (
        action in _DECLINE_ACTIONS
        or candidate_kind in _DECLINE_ACTIONS
        or bool(params.get("skip", False))
        or bool(params.get("skipped", False))
        or params.get("choice") is False
    )


def first_legal_action_id(request: DecisionRequest, *, prefer_decline: bool = False) -> str:
    legal = legal_candidates(request)
    if not legal:
        return ""
    if prefer_decline:
        for candidate in legal:
            if candidate_requests_decline(candidate):
                return str(candidate.action_id)
    return str(legal[0].action_id)


@dataclass(frozen=True)
class CandidateScoreWeights:
    weights: Mapping[str, float] = field(default_factory=dict)
    skip_penalty: float = -1.0
    fallback_penalty: float = -0.1

    def score(self, candidate: CandidateAction) -> float:
        metadata = _metadata(candidate)
        score = 0.0
        for key, weight in sorted(dict(self.weights or {}).items()):
            score += float(weight) * _safe_float(metadata.get(key), default=0.0)
        if candidate_requests_decline(candidate):
            score += float(self.skip_penalty)
        if bool(metadata.get("fallback_mode", False)):
            score += float(self.fallback_penalty)
        return float(score)


@dataclass(frozen=True)
class DeterministicComponentRanker:
    """Framework-free component candidate ranker used by policy bundles and tests.

    It never generates actions or bypasses masks; it only selects from legal
    `DecisionRequest.candidates`.
    """

    component_name: str
    score_weights: CandidateScoreWeights

    def choose_action_id(self, request: DecisionRequest) -> str:
        best_action_id = ""
        best_score = float("-inf")
        for candidate in legal_candidates(request):
            action_id = str(candidate.action_id)
            score = self.score_weights.score(candidate)
            if score > best_score:
                best_score = float(score)
                best_action_id = action_id
        return best_action_id

    def rank_candidates(self, request: DecisionRequest) -> list[CandidateAction]:
        return sorted(
            legal_candidates(request),
            key=lambda candidate: (
                -self.score_weights.score(candidate),
                str(getattr(candidate, "action_id", "") or ""),
            ),
        )


def _weights(values: Mapping[str, float], *, skip_penalty: float = -1.0) -> CandidateScoreWeights:
    return CandidateScoreWeights(weights=dict(values), skip_penalty=skip_penalty)


def default_ai_component_rankers() -> dict[str, DeterministicComponentRanker]:
    """Return baseline deterministic heuristic rankers keyed by policy component."""
    components: dict[str, CandidateScoreWeights] = {
        "strategic_planner": _weights(
            {
                METADATA_PROJECTED_SCORE_NEXT: 2.0,
                METADATA_PROJECTED_SCORE_ROUND: 1.5,
                METADATA_PROJECTED_DENY_NEXT: 1.0,
                METADATA_PROJECTED_CONTROL: 0.8,
                METADATA_RESOURCE_DELTA: 0.6,
            },
        ),
        "tactical_orchestrator": _weights(
            {
                METADATA_PROJECTED_SCORE_NEXT: 1.6,
                METADATA_PROJECTED_DENY_NEXT: 1.4,
                METADATA_PROJECTED_CONTROL: 1.2,
                METADATA_PROJECTED_ACTION_ENABLEMENT: 0.8,
                METADATA_RESOURCE_DELTA: 0.4,
            },
        ),
        "deployment_ranker": _weights(
            {
                METADATA_PROJECTED_SCORE_NEXT: 1.5,
                METADATA_PROJECTED_SCORE_ROUND: 1.2,
                METADATA_PROJECTED_DENY_NEXT: 1.0,
                METADATA_PROJECTED_CONTROL: 1.1,
                METADATA_PROJECTED_ACTION_ENABLEMENT: 0.8,
                METADATA_PROJECTED_EXPOSURE: -0.8,
                METADATA_COVER_DELTA: 0.7,
                METADATA_LOS_DELTA: 0.4,
                "reserve_denial_delta": 0.8,
                "screen_integrity_delta": 0.7,
                "countercharge_coverage_delta": 0.6,
                "aura_connectivity_delta": 0.5,
                "lookahead_total_value": 1.0,
            },
        ),
        "movement_ranker": _weights(
            {
                METADATA_PROJECTED_SCORE_NEXT: 1.8,
                METADATA_PROJECTED_DENY_NEXT: 1.4,
                METADATA_PROJECTED_CONTROL: 1.3,
                METADATA_PROJECTED_ACTION_ENABLEMENT: 0.8,
                METADATA_PROJECTED_EXPOSURE: -0.9,
                METADATA_COVER_DELTA: 0.5,
                METADATA_LOS_DELTA: 0.2,
                METADATA_RESOURCE_DELTA: 0.2,
            },
        ),
        "shooting_ranker": _weights(
            {
                METADATA_PROJECTED_TRADE_EV: 2.0,
                METADATA_PROJECTED_DENY_NEXT: 1.2,
                METADATA_PROJECTED_SCORE_NEXT: 0.9,
                METADATA_PROJECTED_CONTROL: 0.5,
                METADATA_LOS_DELTA: 0.4,
                METADATA_RESOURCE_DELTA: 0.5,
            },
        ),
        "charge_ranker": _weights(
            {
                METADATA_PROJECTED_TRADE_EV: 1.8,
                METADATA_PROJECTED_CONTROL: 1.2,
                METADATA_PROJECTED_SCORE_NEXT: 1.0,
                METADATA_PROJECTED_DENY_NEXT: 1.0,
                METADATA_PROJECTED_ACTION_ENABLEMENT: 0.8,
                METADATA_PROJECTED_EXPOSURE: -0.6,
                METADATA_RESOURCE_DELTA: 0.3,
            },
        ),
        "fight_ranker": _weights(
            {
                METADATA_PROJECTED_TRADE_EV: 2.1,
                METADATA_PROJECTED_CONTROL: 1.2,
                METADATA_PROJECTED_DENY_NEXT: 1.0,
                METADATA_PROJECTED_SCORE_NEXT: 0.8,
                METADATA_PROJECTED_EXPOSURE: -0.4,
                METADATA_RESOURCE_DELTA: 0.3,
            },
        ),
        "tool_ranker": _weights(
            {
                METADATA_PROJECTED_SCORE_NEXT: 1.4,
                METADATA_PROJECTED_DENY_NEXT: 1.2,
                METADATA_PROJECTED_TRADE_EV: 1.2,
                METADATA_PROJECTED_ACTION_ENABLEMENT: 1.0,
                METADATA_RESOURCE_DELTA: 0.9,
            },
        ),
        "reaction_ranker": _weights(
            {
                METADATA_PROJECTED_DENY_NEXT: 1.6,
                METADATA_PROJECTED_TRADE_EV: 1.3,
                METADATA_PROJECTED_CONTROL: 0.8,
                METADATA_PROJECTED_EXPOSURE: -0.8,
                METADATA_RESOURCE_DELTA: 1.0,
            },
        ),
        "dice_policy": _weights(
            {
                METADATA_PROJECTED_SCORE_NEXT: 1.5,
                METADATA_PROJECTED_SCORE_ROUND: 1.0,
                METADATA_PROJECTED_DENY_NEXT: 1.0,
                METADATA_PROJECTED_TRADE_EV: 1.3,
                METADATA_PROJECTED_ACTION_ENABLEMENT: 0.8,
                METADATA_RESOURCE_DELTA: 1.0,
            },
        ),
        "allocation_ranker": _weights(
            {
                METADATA_PROJECTED_SCORE_NEXT: 0.8,
                METADATA_PROJECTED_CONTROL: 1.2,
                METADATA_PROJECTED_TRADE_EV: 1.0,
                METADATA_PROJECTED_EXPOSURE: -1.0,
                METADATA_RESOURCE_DELTA: 0.6,
            },
        ),
    }
    return {
        component: DeterministicComponentRanker(component_name=component, score_weights=weights)
        for component, weights in sorted(components.items())
    }


def ranker_registry_entries() -> dict[str, DeterministicComponentRanker]:
    return {
        f"heuristic:{component}:v1": ranker
        for component, ranker in sorted(default_ai_component_rankers().items())
    }


def action_order_with_preselected(
    request: DecisionRequest,
    *,
    selected_action_id: str,
    fallback_order: Iterable[CandidateAction] | None = None,
) -> list[CandidateAction]:
    legal = legal_candidates(request)
    if not selected_action_id:
        return list(fallback_order or legal)
    selected = [candidate for candidate in legal if str(candidate.action_id) == str(selected_action_id)]
    if not selected:
        return list(fallback_order or legal)
    fallback = list(fallback_order or legal)
    return selected + [candidate for candidate in fallback if str(candidate.action_id) != str(selected_action_id)]
