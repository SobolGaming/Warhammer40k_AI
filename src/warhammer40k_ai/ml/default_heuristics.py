from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ..engine.decisions import DecisionRequest
from .interfaces import CandidateRanker, MatchupEvaluator, PlaybookSelector
from .registry import HeuristicRegistry


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _sorted_playbooks(playbook_ids: Sequence[str]) -> list[str]:
    return sorted(str(playbook_id or "").strip() for playbook_id in list(playbook_ids or []) if str(playbook_id or "").strip())


@dataclass(frozen=True)
class GreedyCandidateRanker(CandidateRanker):
    """Baseline framework-free headless ranker using candidate metadata only."""

    primary_score_key: str = "projected_score_delta_next_window"
    secondary_score_key: str = "projected_trade_ev"

    def choose_action_id(self, request: DecisionRequest) -> str:
        best_action_id = ""
        best_sort_key = (float("-inf"), float("-inf"), "")
        candidates = list(getattr(request, "candidates", []) or [])
        mask = [bool(value) for value in list(getattr(request, "mask", []) or [])]
        for index, candidate in enumerate(candidates):
            if index < len(mask) and not mask[index]:
                continue
            metadata = dict(getattr(candidate, "metadata", {}) or {})
            primary = _safe_float(metadata.get(self.primary_score_key), default=0.0)
            secondary = _safe_float(metadata.get(self.secondary_score_key), default=0.0)
            action_id = str(getattr(candidate, "action_id", "") or "")
            sort_key = (primary, secondary, action_id)
            if sort_key > best_sort_key:
                best_sort_key = sort_key
                best_action_id = action_id
        return best_action_id


@dataclass(frozen=True)
class CapabilityMatchupHeuristic(MatchupEvaluator):
    """Small deterministic heuristic over roster capability and matchup context."""

    def evaluate_matchup(self, context: Mapping[str, Any]) -> Mapping[str, Any]:
        payload = dict(context or {})
        profile = dict(payload.get("build_capability_profile", {}) or {})
        pressure = dict(profile.get("pressure_profile", {}) or {})
        scores = dict(profile.get("capability_scores", {}) or {})
        matchup_context = dict(payload.get("matchup_context", {}) or {})

        round_count = max(1.0, _safe_float(matchup_context.get("round_count"), default=1.0))
        objective_spread = _safe_float(scores.get("objective_spread_tolerance"), default=0.0)
        action_flex = _safe_float(scores.get("mission_action_flex_capacity"), default=0.0)
        deployment_pressure = _safe_float(scores.get("deployment_reveal_pressure"), default=0.0)
        detachment_diversity = _safe_float(scores.get("detachment_diversity_index"), default=0.0)
        attachment_risk = _safe_float(scores.get("attachment_dependency_risk"), default=0.0)
        towering_exposure = _safe_float(scores.get("towering_exposure_index"), default=0.0)
        controller_complexity = _safe_float(scores.get("controller_complexity_index"), default=0.0)
        melee_pressure = _safe_float(pressure.get("melee_pressure"), default=0.0)
        ranged_pressure = _safe_float(pressure.get("ranged_pressure"), default=0.0)
        anti_tank = _safe_float(pressure.get("anti_tank_pressure"), default=0.0)

        normalized_pressure = min(1.0, (melee_pressure + ranged_pressure + anti_tank) / 120.0)
        round_bonus = min(1.0, round_count / 5.0)
        utility = (
            (0.22 * objective_spread)
            + (0.18 * action_flex)
            + (0.12 * deployment_pressure)
            + (0.10 * detachment_diversity)
            + (0.18 * normalized_pressure)
            + (0.08 * round_bonus)
            - (0.07 * attachment_risk)
            - (0.05 * towering_exposure)
            - (0.08 * controller_complexity)
        )
        utility = round(utility, 4)
        return {
            "utility": utility,
            "status": "ok",
            "breakdown": {
                "objective_spread_tolerance": round(objective_spread, 4),
                "mission_action_flex_capacity": round(action_flex, 4),
                "deployment_reveal_pressure": round(deployment_pressure, 4),
                "detachment_diversity_index": round(detachment_diversity, 4),
                "normalized_pressure": round(normalized_pressure, 4),
                "round_bonus": round(round_bonus, 4),
                "attachment_dependency_risk": round(attachment_risk, 4),
                "towering_exposure_index": round(towering_exposure, 4),
                "controller_complexity_index": round(controller_complexity, 4),
            },
        }


@dataclass(frozen=True)
class IdentityPlaybookSelector(PlaybookSelector):
    """Deterministic first-id playbook selector."""

    def select_playbook(self, playbook_ids: Sequence[str], context: Mapping[str, Any]) -> str:
        del context
        ordered = _sorted_playbooks(playbook_ids)
        if not ordered:
            raise ValueError("playbook_ids must contain at least one playbook id.")
        return ordered[0]


def default_heuristic_registry() -> HeuristicRegistry:
    shared_ranker = GreedyCandidateRanker()
    return HeuristicRegistry(
        {
            "heuristic:headless_candidate_ranker:v1": shared_ranker,
            "heuristic:capability_matchup:v1": CapabilityMatchupHeuristic(),
            "heuristic:identity_playbook:v1": IdentityPlaybookSelector(),
            "heuristic:identity_playbook_fallback:v1": IdentityPlaybookSelector(),
            "heuristic:roster_edit_search:v1": shared_ranker,
        }
    )


__all__ = [
    "CapabilityMatchupHeuristic",
    "GreedyCandidateRanker",
    "IdentityPlaybookSelector",
    "default_heuristic_registry",
]
