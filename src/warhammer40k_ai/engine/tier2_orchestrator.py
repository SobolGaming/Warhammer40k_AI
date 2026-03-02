from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .movement_intent import MovementIntent
from .tier1_plan import Tier1Plan
from ..utility.entity_ids import get_entity_id

TASK_SCORE = "SCORE"
TASK_SCREEN = "SCREEN"
TASK_STAGE = "STAGE"
TASK_TRADE = "TRADE"
TASK_DENY = "DENY"
TASK_PROTECT = "PROTECT"
TASK_BAIT = "BAIT"


@dataclass(frozen=True)
class Tier2Task:
    unit_id: str
    task_type: str
    compute_tier: str
    movement_intent: MovementIntent
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": str(self.unit_id),
            "task_type": str(self.task_type),
            "compute_tier": str(self.compute_tier),
            "movement_intent": self.movement_intent.to_dict(),
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True)
class Tier2TaskBundle:
    plan_id: str
    player_id: str
    cp_reserve_policy: dict[str, int]
    tasks_by_unit_id: dict[str, Tier2Task]

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": str(self.plan_id),
            "player_id": str(self.player_id),
            "cp_reserve_policy": dict(self.cp_reserve_policy or {}),
            "tasks_by_unit_id": {
                str(unit_id): task.to_dict()
                for unit_id, task in sorted((self.tasks_by_unit_id or {}).items(), key=lambda item: str(item[0]))
            },
        }


def _resolve_player(game: object, player_id: str):
    for player in list(getattr(game, "players", []) or []):
        if str(getattr(player, "id", "") or "") == str(player_id or ""):
            return player
    return None


def _tier_for_unit(plan: Tier1Plan, unit_id: str) -> str:
    tiers = dict(plan.unit_priority_tiers or {})
    for tier, unit_ids in sorted(tiers.items()):
        if str(unit_id) in {str(uid) for uid in list(unit_ids or [])}:
            return str(tier)
    return "P1"


def _task_for_tier(compute_tier: str) -> str:
    tier = str(compute_tier or "P1").upper()
    if tier == "P0":
        return TASK_SCORE
    if tier == "P1":
        return TASK_STAGE
    return TASK_PROTECT


def _priority_region_ids(plan: Tier1Plan) -> list[str]:
    region_ids = [str(opp.target_region_id) for opp in list(plan.priority_opportunities or []) if str(opp.target_region_id)]
    if region_ids:
        return sorted(dict.fromkeys(region_ids))
    return sorted({str(region) for region in list(plan.staging_regions or []) if str(region)})


def _priority_opportunity_ids(plan: Tier1Plan) -> list[str]:
    return sorted(
        {
            str(opp.opportunity_id)
            for opp in list(plan.priority_opportunities or [])
            if str(opp.opportunity_id)
        }
    )


def _denial_opportunity_ids(plan: Tier1Plan) -> list[str]:
    return sorted(
        {
            str(opp.opportunity_id)
            for opp in list(plan.denial_opportunities or [])
            if str(opp.opportunity_id)
        }
    )


def _movement_intent_for_task(task_type: str, plan: Tier1Plan) -> MovementIntent:
    task = str(task_type or TASK_STAGE).upper()
    priority_regions = _priority_region_ids(plan)
    priority_opportunities = _priority_opportunity_ids(plan)
    denial_opportunities = _denial_opportunity_ids(plan)
    if task == TASK_SCORE:
        return MovementIntent(
            target_region_ids=priority_regions,
            target_opportunity_ids=priority_opportunities,
            desired_affordances=["HOLD_SCORE_SOURCE", "STAGE_FOR_NEXT_WINDOW"],
            screen_deny_targets=[],
            weights={"score": 0.5, "deny": 0.1, "safety": 0.2, "coherency": 0.15, "action_enable": 0.05},
        )
    if task == TASK_SCREEN:
        return MovementIntent(
            target_region_ids=priority_regions,
            target_opportunity_ids=denial_opportunities,
            desired_affordances=["RESERVE_DENY", "LANE_CONTROL", "DENY_SCORE_SOURCE"],
            screen_deny_targets=list(plan.staging_regions or []),
            weights={"score": 0.05, "deny": 0.5, "safety": 0.25, "coherency": 0.15, "action_enable": 0.05},
        )
    if task == TASK_PROTECT:
        return MovementIntent(
            target_region_ids=priority_regions,
            target_opportunity_ids=priority_opportunities,
            desired_affordances=["HOLD_SCORE_SOURCE", "STAGE_FOR_NEXT_WINDOW"],
            screen_deny_targets=[],
            weights={"score": 0.2, "deny": 0.1, "safety": 0.45, "coherency": 0.2, "action_enable": 0.05},
        )
    return MovementIntent(
        target_region_ids=priority_regions,
        target_opportunity_ids=priority_opportunities + denial_opportunities,
        desired_affordances=["STAGE_FOR_NEXT_WINDOW", "DENY_SCORE_SOURCE"],
        screen_deny_targets=list(plan.staging_regions or []),
        weights={"score": 0.25, "deny": 0.25, "safety": 0.25, "coherency": 0.2, "action_enable": 0.05},
    )


def build_tier2_task_bundle(game: object, plan: Tier1Plan) -> Tier2TaskBundle:
    player = _resolve_player(game, plan.player_id)
    if player is None:
        raise ValueError(f"Cannot build Tier2 tasks for unknown player_id: {plan.player_id}")
    army = getattr(player, "army", None)
    units = sorted(list(getattr(army, "units", []) or []), key=lambda unit: str(get_entity_id(unit)))
    tasks: dict[str, Tier2Task] = {}
    for unit in units:
        unit_id = str(get_entity_id(unit))
        compute_tier = _tier_for_unit(plan, unit_id)
        task_type = _task_for_tier(compute_tier)
        movement_intent = _movement_intent_for_task(task_type, plan)
        tasks[unit_id] = Tier2Task(
            unit_id=unit_id,
            task_type=task_type,
            compute_tier=compute_tier,
            movement_intent=movement_intent,
            metadata={"plan_id": plan.plan_id},
        )
    cp_policy = {
        "reserve_for_defense": int(plan.cp_budget.reserve_for_defense),
        "max_offensive_spend_this_turn": int(plan.cp_budget.max_offensive_spend_this_turn),
    }
    return Tier2TaskBundle(
        plan_id=plan.plan_id,
        player_id=plan.player_id,
        cp_reserve_policy=cp_policy,
        tasks_by_unit_id=tasks,
    )
