from __future__ import annotations

from typing import Any

from .ai_policy_orchestrator import (
    COMPONENT_ALLOCATION_RANKER,
    COMPONENT_DEPLOYMENT_RANKER,
    COMPONENT_DICE_POLICY,
    COMPONENT_NO_AI,
)
from .decision_kinds import (
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_DECLARE_RESERVES,
    DECISION_MOVE_UNIT,
    DECISION_SCOUT_MOVE,
    DECISION_SELECT_NEXT_DEPLOY_UNIT,
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


def _should_attach_full_battle_round_plan(game: object, context: dict[str, Any]) -> bool:
    """Return whether to attach the full commander plan payload for audit/debug."""

    if bool(context.get("include_full_battle_round_plan", False)):
        return True
    return bool(getattr(game, "attach_full_battle_round_plan_context", False))


def _should_attach_full_general_plan(game: object, context: dict[str, Any]) -> bool:
    """Return whether to attach the full General plan payload for audit/debug."""

    if bool(context.get("include_full_general_plan", False)):
        return True
    return bool(getattr(game, "attach_full_general_plan_context", False))


def _should_attach_full_deployment_plan(game: object, context: dict[str, Any]) -> bool:
    """Return whether to attach the full deployment plan payload for audit/debug."""

    if bool(context.get("include_full_deployment_plan", False)):
        return True
    return bool(getattr(game, "attach_full_deployment_plan_context", False))


def _is_deployment_plan_context(
    request: DecisionRequest,
    context: dict[str, Any],
    component_name: str,
) -> bool:
    if str(component_name or "") == COMPONENT_DEPLOYMENT_RANKER:
        return True
    decision_type = str(getattr(request, "decision_type", "") or "")
    if decision_type in {
        DECISION_CHOOSE_DEPLOYMENT_ZONE,
        DECISION_DECLARE_RESERVES,
        DECISION_SELECT_NEXT_DEPLOY_UNIT,
        DECISION_SCOUT_MOVE,
    }:
        return True
    if decision_type == DECISION_MOVE_UNIT and str(context.get("placement_kind", "") or "").strip().lower() == "deployment":
        return True
    phase_blob = " ".join(
        str(context.get(key, "") or "").strip().upper()
        for key in ("phase", "phase_name", "phase_step", "selection_purpose", "placement_kind")
    )
    return bool("DEPLOY" in phase_blob or "SETUP" in phase_blob)


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
    attach_full_battle_round_plan = _should_attach_full_battle_round_plan(game, updated)
    attach_full_general_plan = _should_attach_full_general_plan(game, updated)
    attach_full_deployment_plan = _should_attach_full_deployment_plan(game, updated)
    if not attach_full_battle_round_plan:
        updated.pop("battle_round_plan", None)
    if not attach_full_general_plan:
        updated.pop("general_plan", None)
    if not attach_full_deployment_plan:
        updated.pop("deployment_plan", None)

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
    get_general_plan = getattr(game, "get_or_create_general_plan", None)
    get_deployment_plan = getattr(game, "get_or_create_deployment_plan", None)
    get_battle_round_plan = getattr(game, "get_or_create_battle_round_plan", None)
    if not callable(get_tier1_plan) or not callable(get_tier2_bundle):
        updated["compute_tier"] = _normalize_compute_tier(updated.get("compute_tier"))
        return updated

    plan = get_tier1_plan(player_id)
    tier2_bundle = get_tier2_bundle(player_id)
    general_plan = get_general_plan(player_id) if callable(get_general_plan) else None
    deployment_plan = (
        get_deployment_plan(player_id)
        if callable(get_deployment_plan) and _is_deployment_plan_context(request, updated, requested_component)
        else None
    )
    battle_round_plan = get_battle_round_plan(player_id) if callable(get_battle_round_plan) else None
    get_dirty_flags = getattr(game, "get_commander_dirty_flags", None)
    dirty_flags = get_dirty_flags(player_id) if callable(get_dirty_flags) else None
    get_deployment_dirty_flags = getattr(game, "get_deployment_dirty_flags", None)
    deployment_dirty_flags = (
        get_deployment_dirty_flags(player_id)
        if callable(get_deployment_dirty_flags) and deployment_plan is not None
        else None
    )
    get_phase_reports = getattr(game, "get_commander_phase_reports", None)
    phase_reports = get_phase_reports(player_id) if callable(get_phase_reports) else []
    if "plan_id" not in updated:
        updated["plan_id"] = plan.plan_id
    if battle_round_plan is not None and "battle_round_plan_id" not in updated:
        updated["battle_round_plan_id"] = battle_round_plan.plan_id
    if general_plan is not None and "general_plan_id" not in updated:
        updated["general_plan_id"] = general_plan.plan_id
    if deployment_plan is not None and "deployment_plan_id" not in updated:
        updated["deployment_plan_id"] = deployment_plan.plan_id
    if "turn_plan" not in updated:
        updated["turn_plan"] = plan.to_dict()
    if general_plan is not None and "general_plan" not in updated and attach_full_general_plan:
        updated["general_plan"] = general_plan.to_dict()
    if deployment_plan is not None and "deployment_plan" not in updated and attach_full_deployment_plan:
        updated["deployment_plan"] = deployment_plan.to_dict()
    if (
        battle_round_plan is not None
        and "battle_round_plan" not in updated
        and attach_full_battle_round_plan
    ):
        updated["battle_round_plan"] = battle_round_plan.to_dict()
    if deployment_dirty_flags is not None and "deployment_dirty_flags" not in updated:
        updated["deployment_dirty_flags"] = deployment_dirty_flags.to_dict()
    if deployment_dirty_flags is not None and "deployment_replan_scope" not in updated:
        updated["deployment_replan_scope"] = deployment_dirty_flags.recommended_replan_scope()
    if dirty_flags is not None and "commander_dirty_flags" not in updated:
        updated["commander_dirty_flags"] = dirty_flags.to_dict()
    if dirty_flags is not None and "commander_replan_scope" not in updated:
        updated["commander_replan_scope"] = dirty_flags.recommended_replan_scope()
    if phase_reports and "last_commander_phase_report" not in updated:
        updated["last_commander_phase_report"] = phase_reports[-1].to_dict()
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
    if battle_round_plan is not None and unit_id:
        unit_task = dict(getattr(battle_round_plan, "unit_tasks", {}) or {}).get(unit_id)
        if unit_task is not None and "unit_battle_task" not in updated:
            updated["unit_battle_task"] = unit_task.to_dict()
        movement_task = dict(getattr(battle_round_plan.movement_plan, "unit_positioning_tasks", {}) or {}).get(unit_id)
        if movement_task is not None and "commander_movement_task" not in updated:
            updated["commander_movement_task"] = movement_task.to_dict()
        transport_assignment = dict(
            getattr(battle_round_plan.movement_plan, "transport_assignments", {}) or {}
        ).get(unit_id)
        if transport_assignment is not None and "commander_transport_assignment" not in updated:
            transport_assignment_data = transport_assignment.to_dict()
            updated["commander_transport_assignment"] = transport_assignment_data
            transport_intent = str(transport_assignment_data.get("intent", "") or "")
            if (
                transport_intent == "embark_after_action"
                and "commander_embark_assignment" not in updated
            ):
                updated["commander_embark_assignment"] = transport_assignment_data
            if (
                transport_intent in {"stay_embarked", "disembark_this_round"}
                and "commander_disembark_assignment" not in updated
            ):
                updated["commander_disembark_assignment"] = transport_assignment_data
        fire_assignment = dict(getattr(battle_round_plan.shooting_plan, "unit_fire_assignments", {}) or {}).get(unit_id)
        if fire_assignment is not None and "commander_fire_assignment" not in updated:
            updated["commander_fire_assignment"] = fire_assignment.to_dict()
        charge_assignments = dict(
            getattr(battle_round_plan.charge_plan, "unit_charge_assignments", {}) or {}
        )
        charge_assignment = charge_assignments.get(unit_id)
        if charge_assignment is not None and "commander_charge_assignment" not in updated:
            updated["commander_charge_assignment"] = charge_assignment.to_dict()
        fight_assignment = dict(getattr(battle_round_plan.fight_plan, "unit_fight_assignments", {}) or {}).get(unit_id)
        if fight_assignment is not None and "commander_fight_assignment" not in updated:
            updated["commander_fight_assignment"] = fight_assignment.to_dict()

    if deployment_plan is not None and unit_id:
        deployment_task = dict(getattr(deployment_plan, "unit_tasks", {}) or {}).get(unit_id)
        if deployment_task is not None and "unit_deployment_task" not in updated:
            updated["unit_deployment_task"] = deployment_task.to_dict()
        transport_tasks = dict(getattr(deployment_plan, "transport_tasks", {}) or {})
        transport_task = transport_tasks.get(unit_id)
        if transport_task is None:
            for candidate in transport_tasks.values():
                passenger_ids = {
                    str(passenger_id)
                    for passenger_id in list(getattr(candidate, "passenger_unit_ids", []) or [])
                }
                if unit_id in passenger_ids:
                    transport_task = candidate
                    break
        if transport_task is not None and "transport_deployment_task" not in updated:
            updated["transport_deployment_task"] = transport_task.to_dict()

    updated["compute_tier"] = _normalize_compute_tier(
        task_compute_tier if task_compute_tier is not None else updated.get("compute_tier")
    )
    return updated
