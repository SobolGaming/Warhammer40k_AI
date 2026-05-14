from __future__ import annotations

from typing import Any

from .ai_policy_orchestrator import (
    COMPONENT_ALLOCATION_RANKER,
    COMPONENT_DICE_POLICY,
    COMPONENT_NO_AI,
)
from .decisions import DecisionRequest


_STRATEGIC_CONTEXT_EXCLUDED_COMPONENTS = {
    COMPONENT_NO_AI,
    COMPONENT_DICE_POLICY,
    COMPONENT_ALLOCATION_RANKER,
}

_VALID_COMPUTE_TIERS = {"P0", "P1", "P2"}
_DEFAULT_COMPUTE_TIER = "P1"


def _normalize_compute_tier(value: object) -> str:
    tier = str(value or "").strip().upper()
    if tier in _VALID_COMPUTE_TIERS:
        return tier
    return _DEFAULT_COMPUTE_TIER


def _player_id_for_request(game: object, request: DecisionRequest) -> str:
    player_id = str(getattr(request, "player_id", "") or "")
    if player_id:
        return player_id
    get_current_player = getattr(game, "get_current_player", None)
    current_player = get_current_player() if callable(get_current_player) else None
    return str(getattr(current_player, "id", "") or "")


def _terrain_state_summary(game: object) -> dict[str, Any]:
    map_obj = getattr(game, "map", None)
    terrain_features = list(getattr(map_obj, "terrain_features", []) or [])
    terrain_ids = sorted(str(getattr(feature, "id", "") or "") for feature in terrain_features)
    return {
        "terrain_count": int(len(terrain_features)),
        "terrain_ids": terrain_ids,
    }


def attach_ai_orchestration_context(
    game: object,
    request: DecisionRequest,
    ctx: dict[str, Any],
    component_name: str,
) -> dict[str, Any]:
    """Return a new context dict enriched with optional AI orchestration context.

    Does not mutate ctx.
    Does not generate candidates.
    Does not decorate time budgets.
    Does not compile rules/descriptors.
    Does not validate, resolve, or mutate game state.
    """

    updated = dict(ctx or {})
    requested_component = str(component_name or "")
    if requested_component in _STRATEGIC_CONTEXT_EXCLUDED_COMPONENTS:
        updated["compute_tier"] = _normalize_compute_tier(updated.get("compute_tier"))
        return updated

    player_id = _player_id_for_request(game, request)
    if not player_id:
        updated["compute_tier"] = _normalize_compute_tier(updated.get("compute_tier"))
        return updated

    get_tier1_plan = getattr(game, "get_or_create_tier1_plan", None)
    get_tier2_bundle = getattr(game, "get_or_create_tier2_task_bundle", None)
    if not callable(get_tier1_plan) or not callable(get_tier2_bundle):
        updated["compute_tier"] = _normalize_compute_tier(updated.get("compute_tier"))
        return updated

    plan = get_tier1_plan(player_id)
    tier2_bundle = get_tier2_bundle(player_id)
    if "plan_id" not in updated:
        updated["plan_id"] = plan.plan_id
    if "turn_plan" not in updated:
        updated["turn_plan"] = plan.to_dict()
    if "score_window_state" not in updated:
        updated["score_window_state"] = {
            "windows": [window.to_dict() for window in list(plan.scoring_windows or [])],
            "battle_round": int(getattr(plan, "battle_round", 0) or 0),
        }
    if "opportunity_catalog" not in updated:
        updated["opportunity_catalog"] = {
            "priority": [opp.to_dict() for opp in list(plan.priority_opportunities or [])],
            "denial": [opp.to_dict() for opp in list(plan.denial_opportunities or [])],
        }
    if "mission_state" not in updated:
        updated["mission_state"] = {
            "selected_mission_info": dict(getattr(game, "selected_mission_info", {}) or {}),
            "secondary_mission_mode": str(getattr(game, "secondary_mission_mode", "") or ""),
        }
    if "terrain_state_summary" not in updated:
        updated["terrain_state_summary"] = _terrain_state_summary(game)
    if "cp_reserve_policy" not in updated:
        updated["cp_reserve_policy"] = dict(tier2_bundle.cp_reserve_policy or {})

    unit_id = str(updated.get("unit_id", "") or "")
    task = tier2_bundle.tasks_by_unit_id.get(unit_id) if unit_id else None
    task_compute_tier = None
    if task is not None:
        if "tier2_task" not in updated:
            updated["tier2_task"] = task.to_dict()
        if "movement_intent" not in updated:
            updated["movement_intent"] = task.movement_intent.to_dict()
        task_compute_tier = str(task.compute_tier)

    updated["compute_tier"] = _normalize_compute_tier(
        task_compute_tier if task_compute_tier is not None else updated.get("compute_tier")
    )
    return updated
