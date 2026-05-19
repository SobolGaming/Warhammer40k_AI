from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .tier1_plan import Tier1Plan
from .tier2_orchestrator import (
    TASK_BAIT,
    TASK_DENY,
    TASK_PROTECT,
    TASK_SCORE,
    TASK_SCREEN,
    TASK_STAGE,
    TASK_TRADE,
    Tier2Task,
    Tier2TaskBundle,
)
from ..utility.entity_ids import get_entity_id


COMMANDER_STATUS_ON_PLAN = "on_plan"
COMMANDER_STATUS_MINOR_VARIANCE = "minor_variance"
COMMANDER_STATUS_MAJOR_VARIANCE = "major_variance"

REPLAN_SCOPE_NONE = "none"
REPLAN_SCOPE_MOVEMENT_ONLY = "movement_only"
REPLAN_SCOPE_SHOOTING_ONLY = "shooting_only"
REPLAN_SCOPE_CHARGE_ONLY = "charge_only"
REPLAN_SCOPE_FIGHT_ONLY = "fight_only"
REPLAN_SCOPE_PHASE = "phase"
REPLAN_SCOPE_FULL_ROUND = "full_round"

ROLE_KILL = "kill"
ROLE_SCORE = "score"
ROLE_SCREEN = "screen"
ROLE_STAGE = "stage"
ROLE_SACRIFICE = "sacrifice"
ROLE_TRADE = "trade"
ROLE_DENY = "deny"
ROLE_PROTECT = "protect"

MOVEMENT_ACTION_STATIONARY = "stationary"
MOVEMENT_ACTION_NORMAL_MOVE = "normal_move"
MOVEMENT_ACTION_ADVANCE = "advance"
MOVEMENT_ACTION_FALL_BACK = "fall_back"

COMMANDER_ANALYSIS_MAX_TARGETS = 6
COMMANDER_ANALYSIS_MAX_UNITS = 24
COMMANDER_ANALYSIS_MAX_TARGETS_PER_UNIT = 4


def _sorted_strings(values: list[object] | tuple[object, ...] | set[object] | None) -> list[str]:
    return sorted({str(value) for value in list(values or []) if str(value)})


def _sorted_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    return {str(key): value for key, value in sorted(dict(metadata or {}).items(), key=lambda item: str(item[0]))}


def _entity_id(entity: object) -> str:
    return str(get_entity_id(entity) or getattr(entity, "id", "") or getattr(entity, "_id", "") or "")


@dataclass(frozen=True)
class CommanderDirtyFlags:
    movement_plan_dirty: bool = False
    shooting_plan_dirty: bool = False
    charge_plan_dirty: bool = False
    fight_plan_dirty: bool = False
    target_priorities_dirty: bool = False
    objective_priorities_dirty: bool = False
    cp_policy_dirty: bool = False
    full_replan_required: bool = False
    reasons: list[str] = field(default_factory=list)
    max_severity: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "movement_plan_dirty": bool(self.movement_plan_dirty),
            "shooting_plan_dirty": bool(self.shooting_plan_dirty),
            "charge_plan_dirty": bool(self.charge_plan_dirty),
            "fight_plan_dirty": bool(self.fight_plan_dirty),
            "target_priorities_dirty": bool(self.target_priorities_dirty),
            "objective_priorities_dirty": bool(self.objective_priorities_dirty),
            "cp_policy_dirty": bool(self.cp_policy_dirty),
            "full_replan_required": bool(self.full_replan_required),
            "reasons": _sorted_strings(self.reasons),
            "max_severity": float(self.max_severity),
            "status": self.status(),
            "recommended_replan_scope": self.recommended_replan_scope(),
        }

    def any_dirty(self) -> bool:
        return any(
            (
                self.movement_plan_dirty,
                self.shooting_plan_dirty,
                self.charge_plan_dirty,
                self.fight_plan_dirty,
                self.target_priorities_dirty,
                self.objective_priorities_dirty,
                self.cp_policy_dirty,
                self.full_replan_required,
            )
        )

    def status(self) -> str:
        if not self.any_dirty():
            return COMMANDER_STATUS_ON_PLAN
        if self.full_replan_required or self.max_severity >= 0.65:
            return COMMANDER_STATUS_MAJOR_VARIANCE
        return COMMANDER_STATUS_MINOR_VARIANCE

    def recommended_replan_scope(self) -> str:
        if not self.any_dirty():
            return REPLAN_SCOPE_NONE
        if self.full_replan_required:
            return REPLAN_SCOPE_FULL_ROUND
        if self.target_priorities_dirty or self.objective_priorities_dirty or self.cp_policy_dirty:
            return REPLAN_SCOPE_PHASE
        if self.shooting_plan_dirty:
            return REPLAN_SCOPE_SHOOTING_ONLY
        if self.charge_plan_dirty:
            return REPLAN_SCOPE_CHARGE_ONLY
        if self.fight_plan_dirty:
            return REPLAN_SCOPE_FIGHT_ONLY
        if self.movement_plan_dirty:
            return REPLAN_SCOPE_MOVEMENT_ONLY
        return REPLAN_SCOPE_NONE

    def marked(
        self,
        *,
        movement_plan_dirty: bool = False,
        shooting_plan_dirty: bool = False,
        charge_plan_dirty: bool = False,
        fight_plan_dirty: bool = False,
        target_priorities_dirty: bool = False,
        objective_priorities_dirty: bool = False,
        cp_policy_dirty: bool = False,
        full_replan_required: bool = False,
        reason: str = "",
        severity: float = 0.0,
    ) -> "CommanderDirtyFlags":
        reasons = _sorted_strings(list(self.reasons or []) + ([reason] if str(reason or "") else []))
        return CommanderDirtyFlags(
            movement_plan_dirty=bool(self.movement_plan_dirty or movement_plan_dirty),
            shooting_plan_dirty=bool(self.shooting_plan_dirty or shooting_plan_dirty),
            charge_plan_dirty=bool(self.charge_plan_dirty or charge_plan_dirty),
            fight_plan_dirty=bool(self.fight_plan_dirty or fight_plan_dirty),
            target_priorities_dirty=bool(self.target_priorities_dirty or target_priorities_dirty),
            objective_priorities_dirty=bool(self.objective_priorities_dirty or objective_priorities_dirty),
            cp_policy_dirty=bool(self.cp_policy_dirty or cp_policy_dirty),
            full_replan_required=bool(self.full_replan_required or full_replan_required),
            reasons=reasons,
            max_severity=max(float(self.max_severity), float(severity or 0.0)),
        )


@dataclass(frozen=True)
class UnitExecutionReport:
    unit_id: str
    planned_role: str = ""
    planned_target_unit_id: str | None = None
    variance: str = ""
    severity: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "unit_id": str(self.unit_id),
            "planned_role": str(self.planned_role),
            "variance": str(self.variance),
            "severity": float(self.severity),
            "metadata": _sorted_metadata(self.metadata),
        }
        if self.planned_target_unit_id is not None:
            data["planned_target_unit_id"] = str(self.planned_target_unit_id)
        return data


@dataclass(frozen=True)
class TargetPlanReport:
    target_unit_id: str
    variance: str = ""
    severity: float = 0.0
    remaining_wounds_estimate: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "target_unit_id": str(self.target_unit_id),
            "variance": str(self.variance),
            "severity": float(self.severity),
            "metadata": _sorted_metadata(self.metadata),
        }
        if self.remaining_wounds_estimate is not None:
            data["remaining_wounds_estimate"] = float(self.remaining_wounds_estimate)
        return data


@dataclass(frozen=True)
class ObjectivePlanReport:
    objective_id: str
    variance: str = ""
    severity: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective_id": str(self.objective_id),
            "variance": str(self.variance),
            "severity": float(self.severity),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class PhaseExecutionReport:
    phase_name: str
    player_id: str
    plan_id: str
    status: str
    unit_reports: list[UnitExecutionReport] = field(default_factory=list)
    target_reports: list[TargetPlanReport] = field(default_factory=list)
    objective_reports: list[ObjectivePlanReport] = field(default_factory=list)
    recommended_replan_scope: str = REPLAN_SCOPE_NONE
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase_name": str(self.phase_name),
            "player_id": str(self.player_id),
            "plan_id": str(self.plan_id),
            "status": str(self.status),
            "unit_reports": [
                report.to_dict()
                for report in sorted(self.unit_reports, key=lambda item: str(item.unit_id))
            ],
            "target_reports": [
                report.to_dict()
                for report in sorted(self.target_reports, key=lambda item: str(item.target_unit_id))
            ],
            "objective_reports": [
                report.to_dict()
                for report in sorted(self.objective_reports, key=lambda item: str(item.objective_id))
            ],
            "recommended_replan_scope": str(self.recommended_replan_scope),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class TargetPriority:
    target_unit_id: str
    priority_kind: str
    threat_score: float
    scoring_value: float = 0.0
    denial_value: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_unit_id": str(self.target_unit_id),
            "priority_kind": str(self.priority_kind),
            "threat_score": float(self.threat_score),
            "scoring_value": float(self.scoring_value),
            "denial_value": float(self.denial_value),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class CommanderTargetAnalysis:
    target_unit_id: str
    threat_score: float
    scoring_value: float = 0.0
    denial_value: float = 0.0
    wounds_estimate: float = 0.0
    toughness_estimate: float = 0.0
    save_estimate: float = 0.0
    objective_control_estimate: float = 0.0
    keywords: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_unit_id": str(self.target_unit_id),
            "threat_score": float(self.threat_score),
            "scoring_value": float(self.scoring_value),
            "denial_value": float(self.denial_value),
            "wounds_estimate": float(self.wounds_estimate),
            "toughness_estimate": float(self.toughness_estimate),
            "save_estimate": float(self.save_estimate),
            "objective_control_estimate": float(self.objective_control_estimate),
            "keywords": _sorted_strings(self.keywords),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class CommanderUnitCapability:
    unit_id: str
    shooting_capability: float = 0.0
    melee_capability: float = 0.0
    mobility_profile: dict[str, float] = field(default_factory=dict)
    survivability_score: float = 0.0
    risk_profile: float = 0.0
    keywords: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": str(self.unit_id),
            "shooting_capability": float(self.shooting_capability),
            "melee_capability": float(self.melee_capability),
            "mobility_profile": {
                str(key): float(value)
                for key, value in sorted(
                    dict(self.mobility_profile or {}).items(),
                    key=lambda item: str(item[0]),
                )
            },
            "survivability_score": float(self.survivability_score),
            "risk_profile": float(self.risk_profile),
            "keywords": _sorted_strings(self.keywords),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class CommanderUnitTargetAnalysis:
    unit_id: str
    target_unit_id: str
    expected_shooting_damage: float = 0.0
    expected_melee_damage: float = 0.0
    movement_to_los_feasibility: float = 0.0
    movement_to_half_range_feasibility: float = 0.0
    charge_feasibility: float = 0.0
    priority_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": str(self.unit_id),
            "target_unit_id": str(self.target_unit_id),
            "expected_shooting_damage": float(self.expected_shooting_damage),
            "expected_melee_damage": float(self.expected_melee_damage),
            "movement_to_los_feasibility": float(self.movement_to_los_feasibility),
            "movement_to_half_range_feasibility": float(self.movement_to_half_range_feasibility),
            "charge_feasibility": float(self.charge_feasibility),
            "priority_score": float(self.priority_score),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class CommanderAnalysisSnapshot:
    player_id: str
    battle_round: int
    map_generation: int
    target_analysis: list[CommanderTargetAnalysis] = field(default_factory=list)
    unit_capabilities: dict[str, CommanderUnitCapability] = field(default_factory=dict)
    unit_target_matrix: list[CommanderUnitTargetAnalysis] = field(default_factory=list)
    max_targets: int = COMMANDER_ANALYSIS_MAX_TARGETS
    max_units: int = COMMANDER_ANALYSIS_MAX_UNITS
    max_targets_per_unit: int = COMMANDER_ANALYSIS_MAX_TARGETS_PER_UNIT
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        target_analysis = sorted(
            self.target_analysis,
            key=lambda item: (-float(item.threat_score), str(item.target_unit_id)),
        )
        unit_target_matrix = sorted(
            self.unit_target_matrix,
            key=lambda item: (
                str(item.unit_id),
                -float(item.priority_score),
                str(item.target_unit_id),
            ),
        )
        unit_capabilities = {
            str(unit_id): capability.to_dict()
            for unit_id, capability in sorted(
                self.unit_capabilities.items(),
                key=lambda item: str(item[0]),
            )
        }
        return {
            "player_id": str(self.player_id),
            "battle_round": int(self.battle_round),
            "map_generation": int(self.map_generation),
            "cache_key": {
                "battle_round": int(self.battle_round),
                "player_id": str(self.player_id),
                "map_generation": int(self.map_generation),
            },
            "limits": {
                "max_targets": int(self.max_targets),
                "max_units": int(self.max_units),
                "max_targets_per_unit": int(self.max_targets_per_unit),
            },
            "target_count": int(len(target_analysis)),
            "unit_count": int(len(unit_capabilities)),
            "unit_target_entry_count": int(len(unit_target_matrix)),
            "target_analysis": [target.to_dict() for target in target_analysis],
            "unit_capabilities": unit_capabilities,
            "unit_target_matrix": [entry.to_dict() for entry in unit_target_matrix],
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class PositionRegion:
    region_id: str
    kind: str = "abstract"
    anchor_id: str | None = None
    radius_inches: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "region_id": str(self.region_id),
            "kind": str(self.kind),
            "metadata": _sorted_metadata(self.metadata),
        }
        if self.anchor_id is not None:
            data["anchor_id"] = str(self.anchor_id)
        if self.radius_inches is not None:
            data["radius_inches"] = float(self.radius_inches)
        return data


@dataclass(frozen=True)
class RangeBand:
    target_unit_id: str
    minimum_inches: float | None = None
    maximum_inches: float | None = None
    trigger_kind: str = ""
    priority: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "target_unit_id": str(self.target_unit_id),
            "trigger_kind": str(self.trigger_kind),
            "priority": float(self.priority),
        }
        if self.minimum_inches is not None:
            data["minimum_inches"] = float(self.minimum_inches)
        if self.maximum_inches is not None:
            data["maximum_inches"] = float(self.maximum_inches)
        return data


@dataclass(frozen=True)
class WeaponTriggerBand:
    weapon_profile_id: str
    trigger_kind: str
    range_threshold_inches: float
    value_delta: float
    requires_los: bool = True
    requires_stationary: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "weapon_profile_id": str(self.weapon_profile_id),
            "trigger_kind": str(self.trigger_kind),
            "range_threshold_inches": float(self.range_threshold_inches),
            "value_delta": float(self.value_delta),
            "requires_los": bool(self.requires_los),
            "requires_stationary": bool(self.requires_stationary),
        }


@dataclass(frozen=True)
class UnitBattleTask:
    unit_id: str
    role: str
    primary_target_unit_id: str | None = None
    backup_target_unit_ids: list[str] = field(default_factory=list)
    movement_intent: str = ""
    shooting_intent: str = "opportunistic"
    charge_intent: str = "opportunistic"
    fight_intent: str = "opportunistic"
    allowed_movement_actions: list[str] = field(default_factory=list)
    forbidden_movement_actions: list[str] = field(default_factory=list)
    desired_weapon_bands: dict[str, float] = field(default_factory=dict)
    required_position_features: list[str] = field(default_factory=list)
    risk_budget: float = 0.0
    compute_tier: str = "P1"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "unit_id": str(self.unit_id),
            "role": str(self.role),
            "backup_target_unit_ids": _sorted_strings(self.backup_target_unit_ids),
            "movement_intent": str(self.movement_intent),
            "shooting_intent": str(self.shooting_intent),
            "charge_intent": str(self.charge_intent),
            "fight_intent": str(self.fight_intent),
            "allowed_movement_actions": _sorted_strings(self.allowed_movement_actions),
            "forbidden_movement_actions": _sorted_strings(self.forbidden_movement_actions),
            "desired_weapon_bands": {
                str(key): float(value)
                for key, value in sorted(dict(self.desired_weapon_bands or {}).items(), key=lambda item: str(item[0]))
            },
            "required_position_features": _sorted_strings(self.required_position_features),
            "risk_budget": float(self.risk_budget),
            "compute_tier": str(self.compute_tier),
            "metadata": _sorted_metadata(self.metadata),
        }
        if self.primary_target_unit_id is not None:
            data["primary_target_unit_id"] = str(self.primary_target_unit_id)
        return data


@dataclass(frozen=True)
class UnitPositioningTask:
    unit_id: str
    desired_action: str
    target_regions: list[PositionRegion] = field(default_factory=list)
    required_los_to_unit_ids: list[str] = field(default_factory=list)
    desired_range_bands: list[RangeBand] = field(default_factory=list)
    avoid_becoming_shooting_ineligible: bool = True
    intentionally_accept_shooting_ineligible: bool = False
    charge_staging_target_unit_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "unit_id": str(self.unit_id),
            "desired_action": str(self.desired_action),
            "target_regions": [
                region.to_dict()
                for region in sorted(self.target_regions, key=lambda item: item.region_id)
            ],
            "required_los_to_unit_ids": _sorted_strings(self.required_los_to_unit_ids),
            "desired_range_bands": [
                band.to_dict()
                for band in sorted(
                    self.desired_range_bands,
                    key=lambda item: (str(item.target_unit_id), str(item.trigger_kind), float(item.priority)),
                )
            ],
            "avoid_becoming_shooting_ineligible": bool(self.avoid_becoming_shooting_ineligible),
            "intentionally_accept_shooting_ineligible": bool(self.intentionally_accept_shooting_ineligible),
            "metadata": _sorted_metadata(self.metadata),
        }
        if self.charge_staging_target_unit_id is not None:
            data["charge_staging_target_unit_id"] = str(self.charge_staging_target_unit_id)
        return data


@dataclass(frozen=True)
class TargetFirePlan:
    target_unit_id: str
    threat_score: float
    remaining_wounds_estimate: float = 0.0
    desired_kill_probability: float = 0.0
    committed_expected_damage: float = 0.0
    committed_kill_probability: float = 0.0
    assigned_unit_ids: list[str] = field(default_factory=list)
    overkill_limit: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_unit_id": str(self.target_unit_id),
            "threat_score": float(self.threat_score),
            "remaining_wounds_estimate": float(self.remaining_wounds_estimate),
            "desired_kill_probability": float(self.desired_kill_probability),
            "committed_expected_damage": float(self.committed_expected_damage),
            "committed_kill_probability": float(self.committed_kill_probability),
            "assigned_unit_ids": _sorted_strings(self.assigned_unit_ids),
            "overkill_limit": float(self.overkill_limit),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class UnitFireAssignment:
    unit_id: str
    primary_target_unit_id: str | None = None
    backup_target_unit_ids: list[str] = field(default_factory=list)
    preferred_declarations: list[dict[str, Any]] = field(default_factory=list)
    expected_damage_by_target: dict[str, float] = field(default_factory=dict)
    requires_los: bool = False
    requires_half_range: bool = False
    requires_stationary: bool = False
    allows_split_fire: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "unit_id": str(self.unit_id),
            "backup_target_unit_ids": _sorted_strings(self.backup_target_unit_ids),
            "preferred_declarations": [
                _sorted_metadata(declaration)
                for declaration in sorted(
                    list(self.preferred_declarations or []),
                    key=lambda item: str(dict(item).get("action_id", "")) + str(dict(item).get("target_unit_id", "")),
                )
            ],
            "expected_damage_by_target": {
                str(key): float(value)
                for key, value in sorted(
                    dict(self.expected_damage_by_target or {}).items(),
                    key=lambda item: str(item[0]),
                )
            },
            "requires_los": bool(self.requires_los),
            "requires_half_range": bool(self.requires_half_range),
            "requires_stationary": bool(self.requires_stationary),
            "allows_split_fire": bool(self.allows_split_fire),
            "metadata": _sorted_metadata(self.metadata),
        }
        if self.primary_target_unit_id is not None:
            data["primary_target_unit_id"] = str(self.primary_target_unit_id)
        return data


@dataclass(frozen=True)
class ChargeTargetAssignment:
    unit_id: str
    primary_target_unit_id: str | None = None
    backup_target_unit_ids: list[str] = field(default_factory=list)
    desired_charge_probability: float = 0.0
    intentionally_skip_shooting: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "unit_id": str(self.unit_id),
            "backup_target_unit_ids": _sorted_strings(self.backup_target_unit_ids),
            "desired_charge_probability": float(self.desired_charge_probability),
            "intentionally_skip_shooting": bool(self.intentionally_skip_shooting),
            "metadata": _sorted_metadata(self.metadata),
        }
        if self.primary_target_unit_id is not None:
            data["primary_target_unit_id"] = str(self.primary_target_unit_id)
        return data


@dataclass(frozen=True)
class FightTargetAssignment:
    unit_id: str
    primary_target_unit_id: str | None = None
    backup_target_unit_ids: list[str] = field(default_factory=list)
    activation_priority: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "unit_id": str(self.unit_id),
            "backup_target_unit_ids": _sorted_strings(self.backup_target_unit_ids),
            "activation_priority": float(self.activation_priority),
            "metadata": _sorted_metadata(self.metadata),
        }
        if self.primary_target_unit_id is not None:
            data["primary_target_unit_id"] = str(self.primary_target_unit_id)
        return data


@dataclass(frozen=True)
class MovementPhasePlan:
    unit_positioning_tasks: dict[str, UnitPositioningTask] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_positioning_tasks": {
                str(unit_id): task.to_dict()
                for unit_id, task in sorted(self.unit_positioning_tasks.items(), key=lambda item: str(item[0]))
            }
        }


@dataclass(frozen=True)
class ShootingPhasePlan:
    target_fire_plans: dict[str, TargetFirePlan] = field(default_factory=dict)
    unit_fire_assignments: dict[str, UnitFireAssignment] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_fire_plans": {
                str(target_id): plan.to_dict()
                for target_id, plan in sorted(self.target_fire_plans.items(), key=lambda item: str(item[0]))
            },
            "unit_fire_assignments": {
                str(unit_id): assignment.to_dict()
                for unit_id, assignment in sorted(self.unit_fire_assignments.items(), key=lambda item: str(item[0]))
            },
        }


@dataclass(frozen=True)
class ChargePhasePlan:
    unit_charge_assignments: dict[str, ChargeTargetAssignment] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_charge_assignments": {
                str(unit_id): assignment.to_dict()
                for unit_id, assignment in sorted(self.unit_charge_assignments.items(), key=lambda item: str(item[0]))
            }
        }


@dataclass(frozen=True)
class FightPhasePlan:
    unit_fight_assignments: dict[str, FightTargetAssignment] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_fight_assignments": {
                str(unit_id): assignment.to_dict()
                for unit_id, assignment in sorted(self.unit_fight_assignments.items(), key=lambda item: str(item[0]))
            }
        }


@dataclass(frozen=True)
class PlanInvalidationState:
    created_at_generation: int = 0
    last_validated_generation: int = 0
    invalidated: bool = False
    reasons: list[str] = field(default_factory=list)
    repair_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_at_generation": int(self.created_at_generation),
            "last_validated_generation": int(self.last_validated_generation),
            "invalidated": bool(self.invalidated),
            "reasons": _sorted_strings(self.reasons),
            "repair_count": int(self.repair_count),
        }


@dataclass(frozen=True)
class BattleRoundPlan:
    plan_id: str
    player_id: str
    battle_round: int
    created_at_generation: int
    strategic_posture: str
    priority_targets: list[TargetPriority] = field(default_factory=list)
    unit_tasks: dict[str, UnitBattleTask] = field(default_factory=dict)
    movement_plan: MovementPhasePlan = field(default_factory=MovementPhasePlan)
    shooting_plan: ShootingPhasePlan = field(default_factory=ShootingPhasePlan)
    charge_plan: ChargePhasePlan = field(default_factory=ChargePhasePlan)
    fight_plan: FightPhasePlan = field(default_factory=FightPhasePlan)
    invalidation: PlanInvalidationState = field(default_factory=PlanInvalidationState)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": str(self.plan_id),
            "player_id": str(self.player_id),
            "battle_round": int(self.battle_round),
            "created_at_generation": int(self.created_at_generation),
            "strategic_posture": str(self.strategic_posture),
            "priority_targets": [
                target.to_dict()
                for target in sorted(
                    self.priority_targets,
                    key=lambda item: (-float(item.threat_score), str(item.target_unit_id)),
                )
            ],
            "unit_tasks": {
                str(unit_id): task.to_dict()
                for unit_id, task in sorted(self.unit_tasks.items(), key=lambda item: str(item[0]))
            },
            "movement_plan": self.movement_plan.to_dict(),
            "shooting_plan": self.shooting_plan.to_dict(),
            "charge_plan": self.charge_plan.to_dict(),
            "fight_plan": self.fight_plan.to_dict(),
            "invalidation": self.invalidation.to_dict(),
            "metadata": _sorted_metadata(self.metadata),
        }


def _resolve_player(game: object, player_id: str):
    for player in list(getattr(game, "players", []) or []):
        if str(getattr(player, "id", "") or "") == str(player_id or ""):
            return player
    return None


def _player_army(player: object):
    get_army = getattr(player, "get_army", None)
    if callable(get_army):
        return get_army()
    return getattr(player, "army", None)


def _alive(entity: object) -> bool:
    value = getattr(entity, "is_alive", True)
    return bool(value() if callable(value) else value)


def _unit_wounds_estimate(unit: object) -> float:
    total = 0.0
    for model in list(getattr(unit, "models", []) or []):
        if not _alive(model):
            continue
        wounds = getattr(model, "wounds", None)
        if wounds is None:
            wounds = getattr(model, "max_wounds", None)
        try:
            total += float(wounds if wounds is not None else 1.0)
        except (TypeError, ValueError):
            total += 1.0
    return float(total)


def _unit_numeric_estimate(unit: object, attribute_name: str, default: float) -> float:
    unit_attrs = getattr(unit, "__dict__", {}) or {}
    for key in (attribute_name, f"_{attribute_name}"):
        if key not in unit_attrs:
            continue
        value = unit_attrs.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    for model in list(getattr(unit, "models", []) or []):
        if not _alive(model):
            continue
        model_value = getattr(model, attribute_name, None)
        if model_value is None:
            continue
        try:
            return float(model_value)
        except (TypeError, ValueError):
            continue
    return float(default)


def _unit_objective_control_estimate(unit: object) -> float:
    total = 0.0
    for model in list(getattr(unit, "models", []) or []):
        if not _alive(model):
            continue
        value = getattr(model, "objective_control", None)
        try:
            total += float(value if value is not None else 0.0)
        except (TypeError, ValueError):
            continue
    if total > 0.0:
        return float(total)
    return _unit_numeric_estimate(unit, "objective_control", 0.0)


def _unit_keywords(unit: object) -> list[str]:
    keywords: list[object] = []
    keywords.extend(list(getattr(unit, "keywords", []) or []))
    keywords.extend(list(getattr(unit, "faction_keywords", []) or []))
    for model in list(getattr(unit, "models", []) or []):
        keywords.extend(list(getattr(model, "keywords", []) or []))
        keywords.extend(list(getattr(model, "faction_keywords", []) or []))
    if bool(getattr(unit, "is_vehicle", False)):
        keywords.append("VEHICLE")
    if bool(getattr(unit, "is_monster", False)):
        keywords.append("MONSTER")
    return _sorted_strings([str(keyword).upper() for keyword in keywords])


def _unit_has_any_keyword(unit: object, keywords: set[str]) -> bool:
    unit_keywords = set(_unit_keywords(unit))
    return bool(unit_keywords.intersection({keyword.upper() for keyword in keywords}))


def _floatish(value: object, default: float = 0.0) -> float:
    stat_average = getattr(value, "stat_average", None)
    if callable(stat_average):
        try:
            return float(stat_average())
        except (TypeError, ValueError):
            return float(default)
    if isinstance(value, str):
        cleaned = value.replace('"', "").replace("+", "").strip()
        if not cleaned or cleaned in {"-", "N/A"}:
            return float(default)
        try:
            return float(cleaned)
        except (TypeError, ValueError):
            return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(float(lower), min(float(upper), float(value)))


def _weapon_mode_matches(wargear: object, mode: str) -> bool:
    method = getattr(wargear, f"is_{mode}", None)
    if callable(method):
        return bool(method())
    return str(getattr(wargear, "type", "") or "").strip().lower() == str(mode)


def _iter_weapon_profiles(unit: object, mode: str) -> list[object]:
    profiles: list[object] = []
    for model in list(getattr(unit, "models", []) or []):
        if not _alive(model):
            continue
        for wargear in list(getattr(model, "wargear", []) or []):
            if wargear is None or not _weapon_mode_matches(wargear, mode):
                continue
            wargear_profiles = getattr(wargear, "profiles", {}) or {}
            if isinstance(wargear_profiles, dict):
                profiles.extend(list(wargear_profiles.values()))
            else:
                profiles.extend(list(wargear_profiles or []))
    return profiles


def _wound_probability(strength: float, toughness: float) -> float:
    if strength <= 0.0 or toughness <= 0.0:
        return 0.5
    if strength >= toughness * 2.0:
        return 5.0 / 6.0
    if strength > toughness:
        return 4.0 / 6.0
    if strength == toughness:
        return 3.0 / 6.0
    if strength * 2.0 <= toughness:
        return 1.0 / 6.0
    return 2.0 / 6.0


def _save_fail_probability(target_unit: object, ap: float) -> float:
    save = _unit_numeric_estimate(target_unit, "save", 7.0)
    if save <= 0.0:
        return 1.0
    save_needed = save - ap
    if save_needed <= 2.0:
        return 1.0 / 6.0
    if save_needed >= 7.0:
        return 1.0
    return _clamp((save_needed - 1.0) / 6.0)


def _profile_expected_damage(profile: object, target_unit: object | None) -> float:
    attacks = _floatish(getattr(profile, "attacks", None), 0.0)
    skill = _floatish(getattr(profile, "skill", None), 0.0)
    strength = _floatish(getattr(profile, "strength", None), 0.0)
    damage = _floatish(getattr(profile, "damage", None), 0.0)
    ap = _floatish(getattr(profile, "ap", None), 0.0)
    if attacks <= 0.0 or damage <= 0.0:
        return 0.0

    hit_probability = 1.0 if skill <= 0.0 else _clamp((7.0 - skill) / 6.0)
    wound_probability = 0.5
    save_fail_probability = 1.0
    if target_unit is not None:
        target_toughness = _unit_numeric_estimate(target_unit, "toughness", 4.0)
        wound_probability = _wound_probability(strength, target_toughness)
        save_fail_probability = _save_fail_probability(target_unit, ap)
    return float(attacks * hit_probability * wound_probability * save_fail_probability * damage)


def _unit_expected_damage(unit: object, target_unit: object | None, mode: str) -> float:
    return float(
        sum(
            _profile_expected_damage(profile, target_unit)
            for profile in _iter_weapon_profiles(unit, mode)
        )
    )


def _unit_max_ranged_range(unit: object) -> float:
    ranges: list[float] = []
    for profile in _iter_weapon_profiles(unit, "ranged"):
        profile_range = getattr(profile, "range", None)
        range_max = getattr(profile_range, "max", None)
        if range_max is None:
            range_max = getattr(profile, "range_inches", None)
        ranges.append(_floatish(range_max, 0.0))
    return float(max(ranges or [0.0]))


def _unit_distance_estimate(source_unit: object, target_unit: object) -> float:
    source_models = [model for model in list(getattr(source_unit, "models", []) or []) if _alive(model)]
    target_models = [model for model in list(getattr(target_unit, "models", []) or []) if _alive(model)]
    if not source_models or not target_models:
        return 0.0
    source_base = getattr(source_models[0], "model_base", None)
    target_base = getattr(target_models[0], "model_base", None)
    edge_distance = getattr(source_base, "edge_to_edge_distance", None)
    if callable(edge_distance) and target_base is not None:
        try:
            return float(edge_distance(target_base))
        except (TypeError, ValueError):
            pass
    sx = _floatish(getattr(source_base, "x", None), 0.0)
    sy = _floatish(getattr(source_base, "y", None), 0.0)
    sz = _floatish(getattr(source_base, "z", None), 0.0)
    tx = _floatish(getattr(target_base, "x", None), 0.0)
    ty = _floatish(getattr(target_base, "y", None), 0.0)
    tz = _floatish(getattr(target_base, "z", None), 0.0)
    return float(((sx - tx) ** 2 + (sy - ty) ** 2 + (sz - tz) ** 2) ** 0.5)


def _unit_survivability_score(unit: object) -> float:
    wounds = _unit_wounds_estimate(unit)
    toughness = _unit_numeric_estimate(unit, "toughness", 4.0)
    save = _unit_numeric_estimate(unit, "save", 7.0)
    save_quality = _clamp((7.0 - save) / 6.0)
    return float(wounds * (1.0 + toughness / 10.0) * (1.0 + save_quality))


def _target_threat_score(unit: object) -> float:
    wounds = _unit_wounds_estimate(unit)
    toughness = _unit_numeric_estimate(unit, "toughness", 4.0)
    objective_control = _unit_objective_control_estimate(unit)
    keyword_multiplier = 1.25 if _unit_has_any_keyword(unit, {"VEHICLE", "MONSTER", "CHARACTER"}) else 1.0
    return float((wounds + toughness * 0.35 + objective_control * 0.75) * keyword_multiplier)


def _friendly_units_for_player(player: object) -> list[object]:
    army = _player_army(player)
    return sorted(
        [
            unit
            for unit in list(getattr(army, "units", []) or [])
            if unit is not None and bool(getattr(unit, "deployed", True)) and _alive(unit)
        ],
        key=lambda unit: _entity_id(unit),
    )


def _enemy_units_for_player(game: object, player: object) -> list[object]:
    player_army = _player_army(player)
    enemies: list[object] = []
    for other in list(getattr(game, "players", []) or []):
        other_army = _player_army(other)
        if other_army is None or other_army is player_army:
            continue
        enemies.extend(
            unit
            for unit in list(getattr(other_army, "units", []) or [])
            if unit is not None and bool(getattr(unit, "deployed", True)) and _alive(unit)
        )
    return sorted(enemies, key=lambda unit: _entity_id(unit))


def _commander_target_analysis(unit: object) -> CommanderTargetAnalysis:
    wounds = _unit_wounds_estimate(unit)
    toughness = _unit_numeric_estimate(unit, "toughness", 4.0)
    save = _unit_numeric_estimate(unit, "save", 7.0)
    objective_control = _unit_objective_control_estimate(unit)
    threat_score = _target_threat_score(unit)
    return CommanderTargetAnalysis(
        target_unit_id=_entity_id(unit),
        threat_score=threat_score,
        scoring_value=objective_control,
        denial_value=float(objective_control + wounds * 0.1),
        wounds_estimate=wounds,
        toughness_estimate=toughness,
        save_estimate=save,
        objective_control_estimate=objective_control,
        keywords=_unit_keywords(unit),
        metadata={
            "is_high_durability": bool(wounds >= 6.0 or toughness >= 8.0),
            "is_vehicle_or_monster": _unit_has_any_keyword(unit, {"VEHICLE", "MONSTER"}),
        },
    )


def _commander_unit_capability(
    unit: object,
    tier2_bundle: Tier2TaskBundle,
) -> CommanderUnitCapability:
    unit_id = _entity_id(unit)
    task = tier2_bundle.tasks_by_unit_id.get(unit_id)
    movement = _unit_numeric_estimate(unit, "movement", 6.0)
    shooting_capability = _unit_expected_damage(unit, None, "ranged")
    melee_capability = _unit_expected_damage(unit, None, "melee")
    return CommanderUnitCapability(
        unit_id=unit_id,
        shooting_capability=shooting_capability,
        melee_capability=melee_capability,
        mobility_profile={
            "movement_inches": movement,
            "advance_inches_estimate": movement + 3.5,
            "charge_threat_inches_estimate": movement + 7.0,
        },
        survivability_score=_unit_survivability_score(unit),
        risk_profile=_risk_budget_for_tier(str(getattr(task, "compute_tier", "P1") or "P1")),
        keywords=_unit_keywords(unit),
        metadata={
            "ranged_profile_count": int(len(_iter_weapon_profiles(unit, "ranged"))),
            "melee_profile_count": int(len(_iter_weapon_profiles(unit, "melee"))),
            "tier2_task_type": str(getattr(task, "task_type", "") or ""),
        },
    )


def _commander_unit_target_analysis(
    unit: object,
    target_unit: object,
    target_analysis: CommanderTargetAnalysis,
) -> CommanderUnitTargetAnalysis:
    unit_id = _entity_id(unit)
    target_id = _entity_id(target_unit)
    movement = _unit_numeric_estimate(unit, "movement", 6.0)
    distance = _unit_distance_estimate(unit, target_unit)
    max_range = _unit_max_ranged_range(unit)
    half_range = max_range / 2.0 if max_range > 0.0 else 0.0
    shooting_damage = _unit_expected_damage(unit, target_unit, "ranged")
    melee_damage = _unit_expected_damage(unit, target_unit, "melee")
    movement_to_los = 0.0
    movement_to_half_range = 0.0
    if max_range > 0.0:
        movement_to_los = _clamp((movement + max_range - distance + 1.0) / max(1.0, max_range))
    if half_range > 0.0:
        movement_to_half_range = _clamp((movement + half_range - distance + 1.0) / max(1.0, half_range))
    charge_feasibility = 0.0
    if melee_damage > 0.0:
        charge_feasibility = _clamp((movement + 7.0 - distance + 6.0) / 12.0)
    priority_score = (
        shooting_damage
        + melee_damage
        + movement_to_los * 0.25
        + movement_to_half_range * 0.25
        + charge_feasibility * 0.5
        + target_analysis.threat_score * 0.05
    )
    return CommanderUnitTargetAnalysis(
        unit_id=unit_id,
        target_unit_id=target_id,
        expected_shooting_damage=shooting_damage,
        expected_melee_damage=melee_damage,
        movement_to_los_feasibility=movement_to_los,
        movement_to_half_range_feasibility=movement_to_half_range,
        charge_feasibility=charge_feasibility,
        priority_score=priority_score,
        metadata={
            "distance_estimate_inches": distance,
            "max_ranged_range_inches": max_range,
        },
    )


def _build_commander_analysis_snapshot(
    *,
    player: object,
    enemy_units: list[object],
    tier1_plan: Tier1Plan,
    tier2_bundle: Tier2TaskBundle,
    generation: int,
) -> CommanderAnalysisSnapshot:
    target_analysis = [
        _commander_target_analysis(unit)
        for unit in sorted(enemy_units, key=lambda enemy: _entity_id(enemy))
        if _entity_id(unit)
    ]
    target_analysis = sorted(
        target_analysis,
        key=lambda target: (-float(target.threat_score), str(target.target_unit_id)),
    )[:COMMANDER_ANALYSIS_MAX_TARGETS]

    target_units_by_id = {
        _entity_id(unit): unit
        for unit in list(enemy_units or [])
        if _entity_id(unit)
    }
    friendly_units = _friendly_units_for_player(player)[:COMMANDER_ANALYSIS_MAX_UNITS]
    unit_capabilities = {
        _entity_id(unit): _commander_unit_capability(unit, tier2_bundle)
        for unit in friendly_units
        if _entity_id(unit)
    }

    matrix_entries: list[CommanderUnitTargetAnalysis] = []
    for unit in friendly_units:
        unit_entries: list[CommanderUnitTargetAnalysis] = []
        for target in target_analysis:
            target_unit = target_units_by_id.get(str(target.target_unit_id))
            if target_unit is None:
                continue
            unit_entries.append(_commander_unit_target_analysis(unit, target_unit, target))
        matrix_entries.extend(
            sorted(
                unit_entries,
                key=lambda entry: (-float(entry.priority_score), str(entry.target_unit_id)),
            )[:COMMANDER_ANALYSIS_MAX_TARGETS_PER_UNIT]
        )

    return CommanderAnalysisSnapshot(
        player_id=str(tier1_plan.player_id),
        battle_round=int(tier1_plan.battle_round),
        map_generation=int(generation),
        target_analysis=target_analysis,
        unit_capabilities=unit_capabilities,
        unit_target_matrix=matrix_entries,
        metadata={
            "source": "battle_round_plan_build",
            "friendly_unit_candidates": int(len(friendly_units)),
            "enemy_target_candidates": int(len(enemy_units)),
        },
    )


def _task_role(task_type: str) -> str:
    task = str(task_type or "").strip().upper()
    if task == TASK_SCORE:
        return ROLE_SCORE
    if task == TASK_SCREEN:
        return ROLE_SCREEN
    if task == TASK_STAGE:
        return ROLE_STAGE
    if task == TASK_TRADE:
        return ROLE_TRADE
    if task == TASK_DENY:
        return ROLE_DENY
    if task == TASK_PROTECT:
        return ROLE_PROTECT
    if task == TASK_BAIT:
        return ROLE_SACRIFICE
    return ROLE_STAGE


def _movement_intent_label(task: Tier2Task) -> str:
    desired = _sorted_strings(list(getattr(task.movement_intent, "desired_affordances", []) or []))
    if desired:
        return "+".join(desired)
    return str(task.task_type or "").strip().lower() or ROLE_STAGE


def _risk_budget_for_tier(compute_tier: str) -> float:
    tier = str(compute_tier or "").strip().upper()
    if tier == "P0":
        return 0.7
    if tier == "P2":
        return 0.25
    return 0.45


def _regions_from_task(task: Tier2Task) -> list[PositionRegion]:
    return [
        PositionRegion(region_id=region_id, kind="tier2_target_region")
        for region_id in _sorted_strings(list(getattr(task.movement_intent, "target_region_ids", []) or []))
    ]


def _unit_battle_task(
    task: Tier2Task,
    *,
    priority_target_ids: list[str],
) -> UnitBattleTask:
    role = _task_role(task.task_type)
    melee_role = role in {ROLE_TRADE, ROLE_DENY, ROLE_SACRIFICE}
    allowed_actions = [
        MOVEMENT_ACTION_ADVANCE,
        MOVEMENT_ACTION_FALL_BACK,
        MOVEMENT_ACTION_NORMAL_MOVE,
        MOVEMENT_ACTION_STATIONARY,
    ]
    return UnitBattleTask(
        unit_id=task.unit_id,
        role=role,
        primary_target_unit_id=(
            priority_target_ids[0]
            if role in {ROLE_KILL, ROLE_TRADE, ROLE_DENY} and priority_target_ids
            else None
        ),
        backup_target_unit_ids=priority_target_ids,
        movement_intent=_movement_intent_label(task),
        shooting_intent="opportunistic" if not melee_role else "secondary",
        charge_intent="opportunistic" if not melee_role else "high_priority",
        fight_intent="opportunistic" if not melee_role else "high_priority",
        allowed_movement_actions=allowed_actions,
        forbidden_movement_actions=[],
        desired_weapon_bands={},
        required_position_features=[],
        risk_budget=_risk_budget_for_tier(task.compute_tier),
        compute_tier=task.compute_tier,
        metadata={"tier2_task_type": task.task_type},
    )


def build_battle_round_plan(
    game: object,
    tier1_plan: Tier1Plan,
    tier2_bundle: Tier2TaskBundle,
) -> BattleRoundPlan:
    player = _resolve_player(game, tier1_plan.player_id)
    if player is None:
        raise ValueError(f"Cannot build battle-round commander plan for unknown player_id: {tier1_plan.player_id}")

    game_map = getattr(game, "map", None)
    generation = int(getattr(game_map, "state_generation", 0) or 0)
    enemy_units = _enemy_units_for_player(game, player)
    analysis_snapshot = _build_commander_analysis_snapshot(
        player=player,
        enemy_units=enemy_units,
        tier1_plan=tier1_plan,
        tier2_bundle=tier2_bundle,
        generation=generation,
    )
    priority_targets: list[TargetPriority] = []
    for enemy in enemy_units:
        enemy_id = _entity_id(enemy)
        if not enemy_id:
            continue
        wounds = _unit_wounds_estimate(enemy)
        priority_targets.append(
            TargetPriority(
                target_unit_id=enemy_id,
                priority_kind="enemy_unit",
                threat_score=wounds,
                scoring_value=0.0,
                denial_value=0.0,
                metadata={"remaining_wounds_estimate": wounds},
            )
        )
    priority_targets.sort(key=lambda target: (-target.threat_score, target.target_unit_id))
    priority_target_ids = [target.target_unit_id for target in priority_targets]

    unit_tasks: dict[str, UnitBattleTask] = {}
    positioning_tasks: dict[str, UnitPositioningTask] = {}
    fire_assignments: dict[str, UnitFireAssignment] = {}
    charge_assignments: dict[str, ChargeTargetAssignment] = {}
    fight_assignments: dict[str, FightTargetAssignment] = {}

    for unit_id, task in sorted(tier2_bundle.tasks_by_unit_id.items(), key=lambda item: str(item[0])):
        battle_task = _unit_battle_task(task, priority_target_ids=priority_target_ids)
        unit_tasks[str(unit_id)] = battle_task
        role = str(battle_task.role)
        primary_target_id = battle_task.primary_target_unit_id
        intentionally_skip_shooting = role in {ROLE_TRADE, ROLE_DENY, ROLE_SACRIFICE}
        positioning_tasks[str(unit_id)] = UnitPositioningTask(
            unit_id=str(unit_id),
            desired_action=MOVEMENT_ACTION_NORMAL_MOVE,
            target_regions=_regions_from_task(task),
            required_los_to_unit_ids=(
                [primary_target_id]
                if primary_target_id and not intentionally_skip_shooting
                else []
            ),
            desired_range_bands=[],
            avoid_becoming_shooting_ineligible=not intentionally_skip_shooting,
            intentionally_accept_shooting_ineligible=intentionally_skip_shooting,
            charge_staging_target_unit_id=primary_target_id if intentionally_skip_shooting else None,
            metadata={"source": "tier2_task_bundle"},
        )
        fire_assignments[str(unit_id)] = UnitFireAssignment(
            unit_id=str(unit_id),
            primary_target_unit_id=primary_target_id if not intentionally_skip_shooting else None,
            backup_target_unit_ids=battle_task.backup_target_unit_ids,
            preferred_declarations=[],
            expected_damage_by_target={},
            requires_los=bool(primary_target_id and not intentionally_skip_shooting),
            requires_half_range=False,
            requires_stationary=False,
            allows_split_fire=True,
            metadata={"source": "battle_round_plan"},
        )
        charge_assignments[str(unit_id)] = ChargeTargetAssignment(
            unit_id=str(unit_id),
            primary_target_unit_id=primary_target_id if intentionally_skip_shooting else None,
            backup_target_unit_ids=battle_task.backup_target_unit_ids,
            desired_charge_probability=0.65 if intentionally_skip_shooting else 0.0,
            intentionally_skip_shooting=intentionally_skip_shooting,
            metadata={"source": "battle_round_plan"},
        )
        fight_assignments[str(unit_id)] = FightTargetAssignment(
            unit_id=str(unit_id),
            primary_target_unit_id=primary_target_id if intentionally_skip_shooting else None,
            backup_target_unit_ids=battle_task.backup_target_unit_ids,
            activation_priority=_risk_budget_for_tier(task.compute_tier),
            metadata={"source": "battle_round_plan"},
        )

    target_fire_plans = {
        target.target_unit_id: TargetFirePlan(
            target_unit_id=target.target_unit_id,
            threat_score=target.threat_score,
            remaining_wounds_estimate=float(target.metadata.get("remaining_wounds_estimate", 0.0) or 0.0),
            desired_kill_probability=0.0,
            committed_expected_damage=0.0,
            committed_kill_probability=0.0,
            assigned_unit_ids=[],
            overkill_limit=0.0,
            metadata={"priority_kind": target.priority_kind},
        )
        for target in priority_targets
    }

    posture = str(tier1_plan.risk_posture.aggression).strip().upper()
    return BattleRoundPlan(
        plan_id=f"{tier1_plan.plan_id}:battle_round",
        player_id=str(tier1_plan.player_id),
        battle_round=int(tier1_plan.battle_round),
        created_at_generation=generation,
        strategic_posture=posture,
        priority_targets=priority_targets,
        unit_tasks=unit_tasks,
        movement_plan=MovementPhasePlan(unit_positioning_tasks=positioning_tasks),
        shooting_plan=ShootingPhasePlan(
            target_fire_plans=target_fire_plans,
            unit_fire_assignments=fire_assignments,
        ),
        charge_plan=ChargePhasePlan(unit_charge_assignments=charge_assignments),
        fight_plan=FightPhasePlan(unit_fight_assignments=fight_assignments),
        invalidation=PlanInvalidationState(
            created_at_generation=generation,
            last_validated_generation=generation,
            invalidated=False,
            reasons=[],
            repair_count=0,
        ),
        metadata={
            "tier1_plan_id": tier1_plan.plan_id,
            "tier2_plan_id": tier2_bundle.plan_id,
            "analysis_snapshot": analysis_snapshot.to_dict(),
        },
    )


def build_phase_execution_report(
    *,
    phase_name: str,
    player_id: str,
    plan: BattleRoundPlan,
    dirty_flags: CommanderDirtyFlags,
) -> PhaseExecutionReport:
    return PhaseExecutionReport(
        phase_name=str(phase_name),
        player_id=str(player_id),
        plan_id=str(plan.plan_id),
        status=dirty_flags.status(),
        unit_reports=[],
        target_reports=[],
        objective_reports=[],
        recommended_replan_scope=dirty_flags.recommended_replan_scope(),
        metadata={"dirty_flags": dirty_flags.to_dict()},
    )
