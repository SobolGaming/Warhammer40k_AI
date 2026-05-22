from __future__ import annotations

from dataclasses import dataclass, field, replace
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
from .orchestration_guardrails import (
    COMMANDER_PLAN_BUILD_BUDGET_MS,
    COMMANDER_REPAIR_BUDGET_MS,
    ORCHESTRATION_CONTEXT_PAYLOAD_WARNING_BYTES,
)
from .strategic_intent_compiler import (
    CommanderOrderBundle,
    DeploymentOrderBundle,
    PreBattleOrderBundle,
    compile_general_intent_to_commander_orders,
)
from ..utility.entity_ids import get_entity_id
from ..utility.unit_models import alive_unit_group_models, unit_group_models


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
ROLE_SHOOTING_FIRST = "shooting_first"
ROLE_MELEE_FIRST = "melee_first"
ROLE_MIXED = "mixed"
ROLE_SCORER = "scorer"
ROLE_PRESERVE = "preserve"

MOVEMENT_ACTION_STATIONARY = "stationary"
MOVEMENT_ACTION_NORMAL_MOVE = "normal_move"
MOVEMENT_ACTION_ADVANCE = "advance"
MOVEMENT_ACTION_FALL_BACK = "fall_back"

TRANSPORT_INTENT_STAY_EMBARKED = "stay_embarked"
TRANSPORT_INTENT_DISEMBARK_THIS_ROUND = "disembark_this_round"
TRANSPORT_INTENT_EMBARK_AFTER_ACTION = "embark_after_action"
TRANSPORT_INTENT_DELIVER_TO_STAGING_REGION = "deliver_to_staging_region"
TRANSPORT_INTENT_SCREEN_AFTER_DELIVERY = "transport_screen_after_delivery"

COMMANDER_ANALYSIS_MAX_TARGETS = 6
COMMANDER_ANALYSIS_MAX_UNITS = 24
COMMANDER_ANALYSIS_MAX_TARGETS_PER_UNIT = 4
COMMANDER_ANALYSIS_MAX_MATRIX_ENTRIES = (
    COMMANDER_ANALYSIS_MAX_UNITS * COMMANDER_ANALYSIS_MAX_TARGETS_PER_UNIT
)
COMMANDER_ASSIGNMENT_KILL_DAMAGE_FRACTION = 0.85
COMMANDER_ASSIGNMENT_OVERKILL_LIMIT = 1.5


def _sorted_strings(values: list[object] | tuple[object, ...] | set[object] | None) -> list[str]:
    return sorted({str(value) for value in list(values or []) if str(value)})


def _ordered_unique_strings(values: list[object] | tuple[object, ...] | set[object] | None) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in list(values or []):
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


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
                "max_unit_target_entries": int(self.max_units * self.max_targets_per_unit),
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
class TransportAssignment:
    unit_id: str
    transport_unit_id: str | None = None
    intent: str = ""
    desired_round: int | None = None
    desired_phase: str = "MOVEMENT_PHASE"
    destination_region_ids: list[str] = field(default_factory=list)
    protected_until_round: int | None = None
    disembark_trigger: str = ""
    embark_trigger: str = ""
    priority: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "unit_id": str(self.unit_id),
            "intent": str(self.intent),
            "desired_phase": str(self.desired_phase),
            "destination_region_ids": _sorted_strings(self.destination_region_ids),
            "disembark_trigger": str(self.disembark_trigger),
            "embark_trigger": str(self.embark_trigger),
            "priority": float(self.priority),
            "metadata": _sorted_metadata(self.metadata),
        }
        if self.transport_unit_id is not None:
            data["transport_unit_id"] = str(self.transport_unit_id)
        if self.desired_round is not None:
            data["desired_round"] = int(self.desired_round)
        if self.protected_until_round is not None:
            data["protected_until_round"] = int(self.protected_until_round)
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
    transport_assignments: dict[str, TransportAssignment] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_positioning_tasks": {
                str(unit_id): task.to_dict()
                for unit_id, task in sorted(self.unit_positioning_tasks.items(), key=lambda item: str(item[0]))
            },
            "transport_assignments": {
                str(unit_id): assignment.to_dict()
                for unit_id, assignment in sorted(self.transport_assignments.items(), key=lambda item: str(item[0]))
            },
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
    for model in alive_unit_group_models(unit, include_pending=False):
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
    for model in alive_unit_group_models(unit, include_pending=False):
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
    for model in alive_unit_group_models(unit, include_pending=False):
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
    for model in unit_group_models(unit, include_pending=False):
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


def _iter_weapon_profile_entries(unit: object, mode: str) -> list[tuple[object, str, object]]:
    entries: list[tuple[object, str, object]] = []
    for model in alive_unit_group_models(unit, include_pending=False):
        for wargear in list(getattr(model, "wargear", []) or []):
            if wargear is None or not _weapon_mode_matches(wargear, mode):
                continue
            wargear_profiles = getattr(wargear, "profiles", {}) or {}
            if isinstance(wargear_profiles, dict):
                for profile_name, profile in sorted(wargear_profiles.items(), key=lambda item: str(item[0])):
                    if profile is not None:
                        entries.append((wargear, str(profile_name), profile))
            else:
                for profile in list(wargear_profiles or []):
                    if profile is not None:
                        entries.append((wargear, str(getattr(profile, "name", "") or ""), profile))
    return entries


def _iter_weapon_profiles(unit: object, mode: str) -> list[object]:
    return [profile for _wargear, _profile_name, profile in _iter_weapon_profile_entries(unit, mode)]


def _profile_text_blob(unit: object, wargear: object, profile_name: str, profile: object) -> str:
    del unit
    parts: list[str] = [
        str(getattr(wargear, "name", "") or getattr(wargear, "id", "") or ""),
        str(getattr(wargear, "type", "") or ""),
        str(profile_name or ""),
        str(getattr(profile, "name", "") or ""),
        str(getattr(profile, "type", "") or ""),
    ]
    for source in (wargear, profile):
        for attr_name in ("keywords", "faction_keywords", "abilities", "special_rules", "metadata"):
            value = getattr(source, attr_name, None)
            if isinstance(value, dict):
                parts.extend(str(item) for pair in value.items() for item in pair)
            elif isinstance(value, (list, tuple, set)):
                parts.extend(str(item) for item in value)
            elif value is not None:
                parts.append(str(value))
    return " ".join(parts).lower()


def _profile_range_inches(profile: object) -> float:
    profile_range = getattr(profile, "range", None)
    range_max = getattr(profile_range, "max", None)
    if range_max is None:
        range_max = getattr(profile, "range_inches", None)
    return _floatish(range_max, 0.0)


def _profile_identifier(unit: object, wargear: object, profile_name: str, profile: object) -> str:
    profile_id = str(getattr(profile, "id", "") or getattr(profile, "_id", "") or "")
    if profile_id:
        return profile_id
    return ":".join(
        part
        for part in (
            _entity_id(unit),
            str(getattr(wargear, "id", "") or getattr(wargear, "_id", "") or getattr(wargear, "name", "") or ""),
            str(profile_name or getattr(profile, "name", "") or ""),
        )
        if part
    )


def _weapon_trigger_bands(unit: object) -> list[WeaponTriggerBand]:
    bands: list[WeaponTriggerBand] = []
    for wargear, profile_name, profile in _iter_weapon_profile_entries(unit, "ranged"):
        text = _profile_text_blob(unit, wargear, profile_name, profile)
        max_range = _profile_range_inches(profile)
        if max_range <= 0.0:
            continue
        profile_id = _profile_identifier(unit, wargear, profile_name, profile)
        damage = max(0.0, _floatish(getattr(profile, "damage", None), 0.0))
        attacks = max(0.0, _floatish(getattr(profile, "attacks", None), 0.0))
        half_range = max_range / 2.0
        if "melta" in text:
            bands.append(
                WeaponTriggerBand(
                    weapon_profile_id=profile_id,
                    trigger_kind="melta_half_range_damage_bonus",
                    range_threshold_inches=half_range,
                    value_delta=max(0.5, damage * 0.5),
                )
            )
        if "rapid fire" in text or "rapid_fire" in text:
            bands.append(
                WeaponTriggerBand(
                    weapon_profile_id=profile_id,
                    trigger_kind="rapid_fire_half_range_extra_attacks",
                    range_threshold_inches=half_range,
                    value_delta=max(0.4, attacks * 0.35),
                )
            )
        if "assault" in text:
            bands.append(
                WeaponTriggerBand(
                    weapon_profile_id=profile_id,
                    trigger_kind="advance_and_shoot_enabled",
                    range_threshold_inches=max_range,
                    value_delta=0.45,
                )
            )
        if "heavy" in text:
            bands.append(
                WeaponTriggerBand(
                    weapon_profile_id=profile_id,
                    trigger_kind="stationary_shooting_bonus",
                    range_threshold_inches=max_range,
                    value_delta=0.35,
                    requires_stationary=True,
                )
            )
        if "torrent" in text:
            bands.append(
                WeaponTriggerBand(
                    weapon_profile_id=profile_id,
                    trigger_kind="torrent_auto_hit_close_pressure",
                    range_threshold_inches=max_range,
                    value_delta=0.5,
                )
            )
        if "pistol" in text:
            bands.append(
                WeaponTriggerBand(
                    weapon_profile_id=profile_id,
                    trigger_kind="pistol_engaged_shooting_relevance",
                    range_threshold_inches=max_range,
                    value_delta=0.25,
                )
            )
    return sorted(
        bands,
        key=lambda band: (str(band.weapon_profile_id), str(band.trigger_kind), float(band.range_threshold_inches)),
    )


def _object_text_blob(*sources: object) -> str:
    parts: list[str] = []
    for source in sources:
        parts.extend(
            [
                str(_entity_id(source)),
                str(getattr(source, "name", "") or ""),
                str(getattr(source, "id", "") or getattr(source, "_id", "") or ""),
            ]
        )
        for attr_name in ("keywords", "faction_keywords", "abilities", "special_rules", "metadata"):
            value = getattr(source, attr_name, None)
            if isinstance(value, dict):
                parts.extend(str(item) for pair in value.items() for item in pair)
            elif isinstance(value, (list, tuple, set)):
                parts.extend(str(item) for item in value)
            elif value is not None:
                parts.append(str(value))
    return " ".join(parts).lower()


def _unit_ability_trigger_metadata(unit: object) -> dict[str, bool]:
    text = _object_text_blob(unit)
    return {
        "advance_and_charge": bool("advance and charge" in text or "advance-and-charge" in text),
        "fall_back_and_shoot": bool("fall back and shoot" in text or "fallback and shoot" in text),
    }


def _trigger_band_summary(trigger_bands: list[WeaponTriggerBand]) -> dict[str, Any]:
    kinds = _sorted_strings([band.trigger_kind for band in list(trigger_bands or [])])
    half_range_value = sum(
        float(band.value_delta)
        for band in list(trigger_bands or [])
        if str(band.trigger_kind) in {"melta_half_range_damage_bonus", "rapid_fire_half_range_extra_attacks"}
    )
    stationary_value = sum(
        float(band.value_delta)
        for band in list(trigger_bands or [])
        if bool(band.requires_stationary) or str(band.trigger_kind) == "stationary_shooting_bonus"
    )
    return {
        "trigger_band_count": int(len(trigger_bands or [])),
        "trigger_band_kinds": kinds,
        "has_half_range_trigger": bool(half_range_value > 0.0),
        "half_range_trigger_value": float(half_range_value),
        "has_assault_trigger": "advance_and_shoot_enabled" in kinds,
        "has_heavy_stationary_trigger": bool(stationary_value > 0.0),
        "stationary_trigger_value": float(stationary_value),
        "has_torrent_trigger": "torrent_auto_hit_close_pressure" in kinds,
        "has_pistol_trigger": "pistol_engaged_shooting_relevance" in kinds,
    }


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
        ranges.append(_profile_range_inches(profile))
    return float(max(ranges or [0.0]))


def _unit_distance_estimate(source_unit: object, target_unit: object) -> float:
    source_models = alive_unit_group_models(source_unit, include_pending=False)
    target_models = alive_unit_group_models(target_unit, include_pending=False)
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
    trigger_bands = _weapon_trigger_bands(unit)
    trigger_summary = _trigger_band_summary(trigger_bands)
    ability_triggers = _unit_ability_trigger_metadata(unit)
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
            "weapon_trigger_bands": [band.to_dict() for band in trigger_bands],
            **trigger_summary,
            **ability_triggers,
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
    trigger_bands = _weapon_trigger_bands(unit)
    trigger_summary = _trigger_band_summary(trigger_bands)
    shooting_damage = _unit_expected_damage(unit, target_unit, "ranged")
    melee_damage = _unit_expected_damage(unit, target_unit, "melee")
    movement_to_los = 0.0
    movement_to_half_range = 0.0
    if max_range > 0.0:
        movement_to_los = _clamp((movement + max_range - distance + 1.0) / max(1.0, max_range))
    if half_range > 0.0:
        movement_to_half_range = _clamp((movement + half_range - distance + 1.0) / max(1.0, half_range))
    trigger_half_range_value = float(trigger_summary.get("half_range_trigger_value", 0.0) or 0.0)
    trigger_stationary_value = float(trigger_summary.get("stationary_trigger_value", 0.0) or 0.0)
    trigger_reachable_value = trigger_half_range_value * movement_to_half_range
    if max_range > 0.0 and distance <= max_range:
        trigger_reachable_value += trigger_stationary_value
        if bool(trigger_summary.get("has_torrent_trigger", False)):
            trigger_reachable_value += 0.25
        if bool(trigger_summary.get("has_pistol_trigger", False)):
            trigger_reachable_value += 0.1
    shooting_damage = float(shooting_damage + trigger_reachable_value * 0.25)
    charge_feasibility = 0.0
    if melee_damage > 0.0:
        charge_feasibility = _clamp((movement + 7.0 - distance + 6.0) / 12.0)
    priority_score = (
        shooting_damage
        + melee_damage
        + movement_to_los * 0.25
        + movement_to_half_range * (0.25 + min(0.35, trigger_half_range_value * 0.05))
        + charge_feasibility * 0.5
        + trigger_reachable_value * 0.2
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
            "weapon_trigger_bands": [band.to_dict() for band in trigger_bands],
            "trigger_reachable_value": float(trigger_reachable_value),
            **trigger_summary,
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
    enemy_unit_count = int(len(enemy_units or []))
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
    all_friendly_units = _friendly_units_for_player(player)
    friendly_unit_count = int(len(all_friendly_units))
    friendly_units = all_friendly_units[:COMMANDER_ANALYSIS_MAX_UNITS]
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

    unbounded_matrix_entries = int(friendly_unit_count * min(enemy_unit_count, len(target_analysis)))
    max_matrix_entries = int(COMMANDER_ANALYSIS_MAX_MATRIX_ENTRIES)
    actual_matrix_entries = int(len(matrix_entries))
    reduction_fraction = 0.0
    if unbounded_matrix_entries > 0:
        reduction_fraction = max(
            0.0,
            float(unbounded_matrix_entries - actual_matrix_entries) / float(unbounded_matrix_entries),
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
            "friendly_unit_candidate_count": friendly_unit_count,
            "enemy_target_candidates": enemy_unit_count,
            "performance_guardrails": {
                "max_targets": int(COMMANDER_ANALYSIS_MAX_TARGETS),
                "max_units": int(COMMANDER_ANALYSIS_MAX_UNITS),
                "max_targets_per_unit": int(COMMANDER_ANALYSIS_MAX_TARGETS_PER_UNIT),
                "max_unit_target_entries": max_matrix_entries,
                "target_analysis_truncated": bool(enemy_unit_count > COMMANDER_ANALYSIS_MAX_TARGETS),
                "unit_analysis_truncated": bool(friendly_unit_count > COMMANDER_ANALYSIS_MAX_UNITS),
                "matrix_entry_limit_hit": bool(actual_matrix_entries >= max_matrix_entries),
            },
            "phase_work_reduction_estimate": {
                "unbounded_unit_target_entries": unbounded_matrix_entries,
                "bounded_unit_target_entries": actual_matrix_entries,
                "avoided_unit_target_entries": max(0, unbounded_matrix_entries - actual_matrix_entries),
                "unit_target_reduction_fraction": reduction_fraction,
            },
        },
    )


def _target_assignment_score(target: CommanderTargetAnalysis) -> float:
    return float(target.threat_score + target.scoring_value + target.denial_value)


def _entry_target_assignment_score(
    entry: CommanderUnitTargetAnalysis,
    target_by_id: dict[str, CommanderTargetAnalysis],
) -> float:
    target = target_by_id.get(str(entry.target_unit_id))
    return _target_assignment_score(target) if target is not None else 0.0


def _target_wounds_from_analysis(target: CommanderTargetAnalysis | None) -> float:
    if target is None:
        return 0.0
    return float(target.wounds_estimate or 0.0)


def _ranked_targets_from_analysis(snapshot: CommanderAnalysisSnapshot) -> list[CommanderTargetAnalysis]:
    return sorted(
        list(snapshot.target_analysis or []),
        key=lambda target: (-_target_assignment_score(target), str(target.target_unit_id)),
    )


def _matrix_entries_by_unit(
    snapshot: CommanderAnalysisSnapshot,
) -> dict[str, list[CommanderUnitTargetAnalysis]]:
    by_unit: dict[str, list[CommanderUnitTargetAnalysis]] = {}
    for entry in list(snapshot.unit_target_matrix or []):
        by_unit.setdefault(str(entry.unit_id), []).append(entry)
    return {
        unit_id: sorted(
            entries,
            key=lambda entry: (-float(entry.priority_score), str(entry.target_unit_id)),
        )
        for unit_id, entries in sorted(by_unit.items(), key=lambda item: str(item[0]))
    }


def _target_analysis_by_id(
    snapshot: CommanderAnalysisSnapshot,
) -> dict[str, CommanderTargetAnalysis]:
    return {
        str(target.target_unit_id): target
        for target in list(snapshot.target_analysis or [])
    }


def _unit_commander_role(
    task: Tier2Task,
    capability: CommanderUnitCapability | None,
) -> str:
    task_type = str(task.task_type or "").strip().upper()
    shooting = float(getattr(capability, "shooting_capability", 0.0) or 0.0)
    melee = float(getattr(capability, "melee_capability", 0.0) or 0.0)
    if task_type == TASK_SCORE and shooting <= 0.0 and melee <= 0.0:
        return ROLE_SCORER
    if task_type == TASK_SCREEN and shooting <= 0.0 and melee <= 0.0:
        return ROLE_SCREEN
    if task_type == TASK_PROTECT and shooting <= 0.0 and melee <= 0.0:
        return ROLE_PRESERVE

    if task_type in {TASK_TRADE, TASK_DENY, TASK_BAIT} and melee > 0.0:
        return ROLE_MELEE_FIRST
    if shooting > 0.0 and melee > 0.0:
        if shooting >= melee * 1.2:
            return ROLE_SHOOTING_FIRST
        if melee >= shooting * 1.2:
            return ROLE_MELEE_FIRST
        return ROLE_MIXED
    if shooting > 0.0:
        return ROLE_SHOOTING_FIRST
    if melee > 0.0:
        return ROLE_MELEE_FIRST
    if task_type == TASK_STAGE:
        return ROLE_PRESERVE
    return _task_role(task.task_type)


def _assignment_target_backups(
    entries: list[CommanderUnitTargetAnalysis],
    ranked_target_ids: list[str],
    primary_target_id: str | None,
) -> list[str]:
    candidate_ids = [
        str(entry.target_unit_id)
        for entry in sorted(
            entries,
            key=lambda entry: (-float(entry.priority_score), str(entry.target_unit_id)),
        )
    ]
    candidate_ids.extend(list(ranked_target_ids or []))
    return [
        target_id
        for target_id in _ordered_unique_strings(candidate_ids)
        if target_id and target_id != str(primary_target_id or "")
    ]


def _best_melee_target_assignment(
    entries: list[CommanderUnitTargetAnalysis],
    target_by_id: dict[str, CommanderTargetAnalysis],
) -> CommanderUnitTargetAnalysis | None:
    candidates = [
        entry
        for entry in list(entries or [])
        if float(entry.expected_melee_damage or 0.0) > 0.0
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda entry: (
            -float(entry.expected_melee_damage),
            -float(entry.charge_feasibility),
            -_entry_target_assignment_score(entry, target_by_id),
            str(entry.target_unit_id),
        ),
    )[0]


def _shooting_entry_score(
    entry: CommanderUnitTargetAnalysis,
    target: CommanderTargetAnalysis | None,
    committed_damage: dict[str, float],
) -> float:
    target_id = str(entry.target_unit_id)
    target_score = _target_assignment_score(target) if target is not None else 0.0
    wounds = max(1.0, _target_wounds_from_analysis(target))
    commitment_pressure = float(committed_damage.get(target_id, 0.0) or 0.0) / wounds
    return float(
        target_score
        + float(entry.expected_shooting_damage) * 1.5
        + float(entry.movement_to_los_feasibility) * 0.25
        + float(entry.movement_to_half_range_feasibility) * 0.1
        - commitment_pressure * 2.0
    )


def _choose_shooting_assignment(
    *,
    unit_id: str,
    entries: list[CommanderUnitTargetAnalysis],
    target_by_id: dict[str, CommanderTargetAnalysis],
    committed_damage: dict[str, float],
) -> CommanderUnitTargetAnalysis | None:
    candidates: list[CommanderUnitTargetAnalysis] = []
    for entry in list(entries or []):
        damage = float(entry.expected_shooting_damage or 0.0)
        if damage <= 0.0:
            continue
        target = target_by_id.get(str(entry.target_unit_id))
        wounds = max(1.0, _target_wounds_from_analysis(target))
        desired_damage = max(1.0, wounds * COMMANDER_ASSIGNMENT_KILL_DAMAGE_FRACTION)
        max_commitment = desired_damage + COMMANDER_ASSIGNMENT_OVERKILL_LIMIT
        if float(committed_damage.get(str(entry.target_unit_id), 0.0) or 0.0) >= max_commitment:
            continue
        candidates.append(entry)
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda entry: (
            -_shooting_entry_score(
                entry,
                target_by_id.get(str(entry.target_unit_id)),
                committed_damage,
            ),
            str(unit_id),
            str(entry.target_unit_id),
        ),
    )[0]


def _entry_for_target(
    entries: list[CommanderUnitTargetAnalysis],
    target_unit_id: str | None,
) -> CommanderUnitTargetAnalysis | None:
    wanted = str(target_unit_id or "")
    if not wanted:
        return None
    for entry in list(entries or []):
        if str(entry.target_unit_id) == wanted:
            return entry
    return None


def _compiled_unit_order_metadata(order: object | None) -> dict[str, Any]:
    if order is None:
        return {}
    return dict(getattr(order, "metadata", {}) or {})


def _compiled_unit_order_is_explicit(order: object | None) -> bool:
    metadata = _compiled_unit_order_metadata(order)
    if bool(metadata.get("explicit_general_override", False)):
        return True
    source_kinds = {str(kind) for kind in list(metadata.get("source_intent_kinds", []) or [])}
    return "explicit_general_unit_order" in source_kinds


def _compiled_unit_order_constraint_mode(order: object | None) -> str:
    mode = str(getattr(order, "constraint_mode", "hint") or "hint").strip().lower()
    return mode if mode in {"hint", "constrain", "replace", "override"} else "hint"


def _compiled_unit_order_delays_commit(order: object | None) -> bool:
    metadata = _compiled_unit_order_metadata(order)
    if str(metadata.get("directive_commit_status", "") or "").strip().lower() == "staging":
        return True
    source_kinds = {str(kind) for kind in list(metadata.get("source_intent_kinds", []) or [])}
    if "round_posture_delay" in source_kinds:
        return True
    for attr_name in ("movement_order", "shooting_order", "charge_order", "fight_order"):
        suborder = getattr(order, attr_name, None)
        sub_metadata = dict(getattr(suborder, "metadata", {}) or {})
        if str(sub_metadata.get("directive_commit_status", "") or "").strip().lower() == "staging":
            return True
    return False


def _compiled_shooting_primary_target(order: object | None) -> str | None:
    shooting_order = getattr(order, "shooting_order", None)
    target_id = str(getattr(shooting_order, "primary_target_unit_id", "") or "")
    return target_id or None


def _compiled_charge_primary_target(order: object | None) -> str | None:
    charge_order = getattr(order, "charge_order", None)
    target_id = str(getattr(charge_order, "primary_target_unit_id", "") or "")
    return target_id or None


def _remove_shooting_assignment_commitment(
    *,
    unit_id: str,
    shooting_assignments: dict[str, CommanderUnitTargetAnalysis],
    committed_damage: dict[str, float],
    target_assigned_units: dict[str, list[str]],
) -> None:
    old = shooting_assignments.pop(str(unit_id), None)
    if old is None:
        return
    old_target_id = str(old.target_unit_id)
    committed_damage[old_target_id] = max(
        0.0,
        float(committed_damage.get(old_target_id, 0.0) or 0.0) - float(old.expected_shooting_damage or 0.0),
    )
    target_assigned_units[old_target_id] = [
        assigned_unit_id
        for assigned_unit_id in list(target_assigned_units.get(old_target_id, []) or [])
        if str(assigned_unit_id) != str(unit_id)
    ]


def _compiled_target_commitment_allowed(
    *,
    mode: str,
    target_order: object | None,
    target_analysis: CommanderTargetAnalysis | None,
    committed_damage: dict[str, float],
    entry: CommanderUnitTargetAnalysis,
) -> bool:
    if mode in {"replace", "override"}:
        return True
    target_id = str(entry.target_unit_id)
    wounds = max(1.0, _target_wounds_from_analysis(target_analysis))
    desired_kill_probability = float(getattr(target_order, "desired_kill_probability", 0.75) or 0.75)
    max_overkill_wounds = float(getattr(target_order, "max_overkill_wounds", COMMANDER_ASSIGNMENT_OVERKILL_LIMIT) or 0.0)
    desired_damage = max(1.0, wounds * max(0.1, min(1.0, desired_kill_probability)))
    max_commitment = desired_damage + max_overkill_wounds
    return float(committed_damage.get(target_id, 0.0) or 0.0) < max_commitment


def _apply_compiled_commander_assignment_constraints(
    *,
    commander_unit_orders: dict[str, object],
    commander_target_orders: dict[str, object],
    matrix_by_unit: dict[str, list[CommanderUnitTargetAnalysis]],
    target_by_id: dict[str, CommanderTargetAnalysis],
    unit_roles: dict[str, str],
    shooting_assignments: dict[str, CommanderUnitTargetAnalysis],
    charge_assignments: dict[str, CommanderUnitTargetAnalysis],
    committed_damage: dict[str, float],
    target_assigned_units: dict[str, list[str]],
) -> dict[str, dict[str, Any]]:
    statuses: dict[str, dict[str, Any]] = {}
    for unit_id, order in sorted(commander_unit_orders.items(), key=lambda item: str(item[0])):
        uid = str(unit_id)
        explicit = _compiled_unit_order_is_explicit(order)
        mode = _compiled_unit_order_constraint_mode(order)
        status: dict[str, Any] = {
            "explicit_general_override": bool(explicit),
            "constraint_mode": mode,
            "shooting_constraint_status": "not_requested",
            "charge_constraint_status": "not_requested",
        }
        if not explicit or mode == "hint":
            statuses[uid] = status
            continue
        if bool(getattr(order, "preserve", False)):
            _remove_shooting_assignment_commitment(
                unit_id=uid,
                shooting_assignments=shooting_assignments,
                committed_damage=committed_damage,
                target_assigned_units=target_assigned_units,
            )
            charge_assignments.pop(uid, None)
            unit_roles[uid] = ROLE_PRESERVE
            status["shooting_constraint_status"] = "preserve_removed"
            status["charge_constraint_status"] = "preserve_removed"
            statuses[uid] = status
            continue

        if _compiled_unit_order_delays_commit(order):
            _remove_shooting_assignment_commitment(
                unit_id=uid,
                shooting_assignments=shooting_assignments,
                committed_damage=committed_damage,
                target_assigned_units=target_assigned_units,
            )
            charge_assignments.pop(uid, None)
            status["shooting_constraint_status"] = "staged_hold"
            status["charge_constraint_status"] = "staged_hold"
            statuses[uid] = status
            continue

        entries = list(matrix_by_unit.get(uid, []) or [])
        shooting_target_id = _compiled_shooting_primary_target(order)
        if shooting_target_id:
            shooting_entry = _entry_for_target(entries, shooting_target_id)
            if shooting_entry is None or float(shooting_entry.expected_shooting_damage or 0.0) <= 0.0:
                status["shooting_constraint_status"] = "target_not_in_current_analysis"
            elif not _compiled_target_commitment_allowed(
                mode=mode,
                target_order=commander_target_orders.get(str(shooting_target_id)),
                target_analysis=target_by_id.get(str(shooting_target_id)),
                committed_damage=committed_damage,
                entry=shooting_entry,
            ):
                status["shooting_constraint_status"] = "overkill_guard_rejected"
            else:
                _remove_shooting_assignment_commitment(
                    unit_id=uid,
                    shooting_assignments=shooting_assignments,
                    committed_damage=committed_damage,
                    target_assigned_units=target_assigned_units,
                )
                shooting_assignments[uid] = shooting_entry
                committed_damage[str(shooting_entry.target_unit_id)] = float(
                    committed_damage.get(str(shooting_entry.target_unit_id), 0.0) or 0.0
                ) + float(shooting_entry.expected_shooting_damage or 0.0)
                assigned_units = list(target_assigned_units.get(str(shooting_entry.target_unit_id), []) or [])
                if uid not in assigned_units:
                    assigned_units.append(uid)
                target_assigned_units[str(shooting_entry.target_unit_id)] = _sorted_strings(assigned_units)
                status["shooting_constraint_status"] = "applied"

        charge_target_id = _compiled_charge_primary_target(order)
        if charge_target_id:
            charge_entry = _entry_for_target(entries, charge_target_id)
            if charge_entry is None or float(charge_entry.expected_melee_damage or 0.0) <= 0.0:
                status["charge_constraint_status"] = "target_not_in_current_analysis"
            else:
                charge_assignments[uid] = charge_entry
                status["charge_constraint_status"] = "applied"

        statuses[uid] = status
    return statuses


def _build_greedy_commander_assignments(
    *,
    snapshot: CommanderAnalysisSnapshot,
    tier2_bundle: Tier2TaskBundle,
) -> dict[str, Any]:
    ranked_targets = _ranked_targets_from_analysis(snapshot)
    ranked_target_ids = [str(target.target_unit_id) for target in ranked_targets]
    target_by_id = _target_analysis_by_id(snapshot)
    matrix_by_unit = _matrix_entries_by_unit(snapshot)
    unit_capabilities = dict(snapshot.unit_capabilities or {})
    unit_roles: dict[str, str] = {}
    shooting_assignments: dict[str, CommanderUnitTargetAnalysis] = {}
    charge_assignments: dict[str, CommanderUnitTargetAnalysis] = {}
    committed_damage: dict[str, float] = {target_id: 0.0 for target_id in ranked_target_ids}
    target_assigned_units: dict[str, list[str]] = {target_id: [] for target_id in ranked_target_ids}

    for unit_id, task in sorted(tier2_bundle.tasks_by_unit_id.items(), key=lambda item: str(item[0])):
        capability = unit_capabilities.get(str(unit_id))
        unit_roles[str(unit_id)] = _unit_commander_role(task, capability)

    shooting_unit_ids = [
        unit_id
        for unit_id, role in sorted(unit_roles.items(), key=lambda item: str(item[0]))
        if role in {ROLE_SHOOTING_FIRST, ROLE_MIXED}
        and float(getattr(unit_capabilities.get(unit_id), "shooting_capability", 0.0) or 0.0) > 0.0
    ]
    shooting_unit_ids.sort(
        key=lambda unit_id: (
            -float(getattr(unit_capabilities.get(unit_id), "shooting_capability", 0.0) or 0.0),
            str(unit_id),
        )
    )

    for unit_id in shooting_unit_ids:
        chosen = _choose_shooting_assignment(
            unit_id=unit_id,
            entries=matrix_by_unit.get(unit_id, []),
            target_by_id=target_by_id,
            committed_damage=committed_damage,
        )
        if chosen is None:
            continue
        target_id = str(chosen.target_unit_id)
        shooting_assignments[unit_id] = chosen
        committed_damage[target_id] = float(committed_damage.get(target_id, 0.0) or 0.0) + float(
            chosen.expected_shooting_damage or 0.0
        )
        target_assigned_units.setdefault(target_id, []).append(unit_id)

    for unit_id, role in sorted(unit_roles.items(), key=lambda item: str(item[0])):
        if role not in {ROLE_MELEE_FIRST, ROLE_MIXED}:
            continue
        if role == ROLE_MIXED and unit_id in shooting_assignments:
            continue
        chosen = _best_melee_target_assignment(matrix_by_unit.get(unit_id, []), target_by_id)
        if chosen is not None:
            charge_assignments[unit_id] = chosen

    return {
        "ranked_target_ids": ranked_target_ids,
        "target_by_id": target_by_id,
        "matrix_by_unit": matrix_by_unit,
        "unit_capabilities": unit_capabilities,
        "unit_roles": unit_roles,
        "shooting_assignments": shooting_assignments,
        "charge_assignments": charge_assignments,
        "committed_damage": committed_damage,
        "target_assigned_units": target_assigned_units,
    }


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
    role: str,
    primary_target_unit_id: str | None,
    backup_target_unit_ids: list[str],
    shooting_intent: str,
    charge_intent: str,
    fight_intent: str,
    shooting_can_advance: bool = False,
    desired_weapon_bands: dict[str, float] | None = None,
    metadata: dict[str, Any] | None = None,
) -> UnitBattleTask:
    allowed_actions = [
        MOVEMENT_ACTION_ADVANCE,
        MOVEMENT_ACTION_FALL_BACK,
        MOVEMENT_ACTION_NORMAL_MOVE,
        MOVEMENT_ACTION_STATIONARY,
    ]
    forbidden_actions = [MOVEMENT_ACTION_ADVANCE] if role == ROLE_SHOOTING_FIRST and not shooting_can_advance else []
    task_metadata = {
        "assignment_source": "greedy_commander_assignment",
        "tier2_task_type": task.task_type,
        "shooting_can_advance": bool(shooting_can_advance),
    }
    task_metadata.update(dict(metadata or {}))
    return UnitBattleTask(
        unit_id=task.unit_id,
        role=role,
        primary_target_unit_id=primary_target_unit_id,
        backup_target_unit_ids=backup_target_unit_ids,
        movement_intent=_movement_intent_label(task),
        shooting_intent=shooting_intent,
        charge_intent=charge_intent,
        fight_intent=fight_intent,
        allowed_movement_actions=allowed_actions,
        forbidden_movement_actions=forbidden_actions,
        desired_weapon_bands=dict(desired_weapon_bands or {}),
        required_position_features=[],
        risk_budget=_risk_budget_for_tier(task.compute_tier),
        compute_tier=task.compute_tier,
        metadata=task_metadata,
    )


def _policy_value(policy: object, key: str, default: Any = None) -> Any:
    if isinstance(policy, dict):
        return policy.get(key, default)
    return getattr(policy, key, default)


def _policy_metadata(policy: object) -> dict[str, Any]:
    metadata = _policy_value(policy, "metadata", {})
    if isinstance(metadata, dict):
        return dict(metadata)
    return {}


def _policy_int(policy: object, key: str) -> int | None:
    value = _policy_value(policy, key, None)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_transport_assignments(
    *,
    general_transport_policy: dict[str, Any] | None,
    battle_round: int,
) -> dict[str, TransportAssignment]:
    assignments: dict[str, TransportAssignment] = {}
    for transport_id, policy in sorted(dict(general_transport_policy or {}).items(), key=lambda item: str(item[0])):
        tid = str(_policy_value(policy, "transport_unit_id", transport_id) or transport_id or "")
        if not tid:
            continue
        metadata = _policy_metadata(policy)
        passenger_ids = _sorted_strings(_policy_value(policy, "passenger_unit_ids", []))
        current_passenger_ids = set(_sorted_strings(metadata.get("current_passenger_unit_ids", [])))
        desired_round = _policy_int(policy, "desired_round")
        protected_until_round = _policy_int(policy, "protected_until_round")
        destination_region_ids = _sorted_strings(_policy_value(policy, "destination_region_ids", []))
        priority = _floatish(_policy_value(policy, "priority", 0.0), 0.0)
        preserve_passengers = bool(_policy_value(policy, "preserve_passengers", False))
        post_delivery_role = str(_policy_value(policy, "post_delivery_role", "") or "").strip()
        doctrine = str(_policy_value(policy, "doctrine", "") or "").strip()

        for passenger_id in passenger_ids:
            is_current_passenger = passenger_id in current_passenger_ids
            deliver_now = bool(
                is_current_passenger
                and desired_round is not None
                and int(battle_round) >= int(desired_round)
            )
            intent = (
                TRANSPORT_INTENT_DISEMBARK_THIS_ROUND
                if deliver_now
                else TRANSPORT_INTENT_STAY_EMBARKED
                if is_current_passenger
                else TRANSPORT_INTENT_EMBARK_AFTER_ACTION
            )
            assignments[passenger_id] = TransportAssignment(
                unit_id=passenger_id,
                transport_unit_id=tid,
                intent=intent,
                desired_round=desired_round,
                desired_phase="MOVEMENT_PHASE",
                destination_region_ids=destination_region_ids,
                protected_until_round=protected_until_round,
                disembark_trigger="delivery_round" if is_current_passenger else "",
                embark_trigger="after_unit_action" if not is_current_passenger else "",
                priority=priority,
                metadata={
                    "assignment_kind": "passenger",
                    "doctrine": doctrine,
                    "general_post_delivery_role": post_delivery_role,
                    "preserve_passenger": bool(preserve_passengers),
                    "source": "general_transport_doctrine",
                },
            )

        transport_intent = (
            TRANSPORT_INTENT_DELIVER_TO_STAGING_REGION
            if passenger_ids
            else TRANSPORT_INTENT_SCREEN_AFTER_DELIVERY
        )
        assignments[tid] = TransportAssignment(
            unit_id=tid,
            transport_unit_id=tid,
            intent=transport_intent,
            desired_round=desired_round,
            desired_phase="MOVEMENT_PHASE",
            destination_region_ids=destination_region_ids,
            protected_until_round=protected_until_round,
            disembark_trigger="delivery_round" if passenger_ids else "",
            embark_trigger="assigned_passenger_action" if passenger_ids and not current_passenger_ids else "",
            priority=priority,
            metadata={
                "assignment_kind": "transport",
                "doctrine": doctrine,
                "planned_passenger_unit_ids": passenger_ids,
                "current_passenger_unit_ids": _sorted_strings(current_passenger_ids),
                "post_delivery_role": post_delivery_role,
                "source": "general_transport_doctrine",
            },
        )
    return assignments


def build_battle_round_plan(
    game: object,
    tier1_plan: Tier1Plan,
    tier2_bundle: Tier2TaskBundle,
    *,
    general_plan: object | None = None,
    general_plan_id: str | None = None,
    general_transport_policy: dict[str, Any] | None = None,
    deployment_orders: DeploymentOrderBundle | None = None,
    prebattle_orders: PreBattleOrderBundle | None = None,
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
    commander_orders: CommanderOrderBundle | None = None
    if general_plan is not None:
        commander_orders = compile_general_intent_to_commander_orders(
            game,
            general_plan,
            deployment_orders,
            prebattle_orders,
            tier1_plan,
            tier2_bundle,
            analysis_snapshot,
            battle_round=int(tier1_plan.battle_round),
            player_id=str(tier1_plan.player_id),
        )
    commander_unit_orders = dict(getattr(commander_orders, "unit_orders", {}) or {})
    commander_target_orders = dict(getattr(commander_orders, "target_orders", {}) or {})
    target_analysis_by_id = {
        str(target.target_unit_id): target
        for target in list(analysis_snapshot.target_analysis or [])
    }
    for enemy in enemy_units:
        enemy_id = _entity_id(enemy)
        if enemy_id and enemy_id not in target_analysis_by_id:
            target_analysis_by_id[enemy_id] = _commander_target_analysis(enemy)
    priority_targets = [
        TargetPriority(
            target_unit_id=str(target.target_unit_id),
            priority_kind="enemy_unit",
            threat_score=float(target.threat_score),
            scoring_value=float(target.scoring_value),
            denial_value=float(target.denial_value),
            metadata={
                "objective_control_estimate": float(target.objective_control_estimate),
                "remaining_wounds_estimate": float(target.wounds_estimate),
                "source": "commander_analysis_snapshot",
            },
        )
        for target in target_analysis_by_id.values()
    ]
    priority_targets.sort(
        key=lambda target: (
            -float(target.threat_score + target.scoring_value + target.denial_value),
            str(target.target_unit_id),
        )
    )
    priority_target_ids = [target.target_unit_id for target in priority_targets]
    greedy_assignments = _build_greedy_commander_assignments(
        snapshot=analysis_snapshot,
        tier2_bundle=tier2_bundle,
    )
    target_by_id: dict[str, CommanderTargetAnalysis] = dict(greedy_assignments["target_by_id"])
    matrix_by_unit: dict[str, list[CommanderUnitTargetAnalysis]] = dict(greedy_assignments["matrix_by_unit"])
    unit_roles: dict[str, str] = dict(greedy_assignments["unit_roles"])
    shooting_assignments: dict[str, CommanderUnitTargetAnalysis] = dict(greedy_assignments["shooting_assignments"])
    charge_target_assignments: dict[str, CommanderUnitTargetAnalysis] = dict(greedy_assignments["charge_assignments"])
    committed_damage: dict[str, float] = dict(greedy_assignments["committed_damage"])
    target_assigned_units: dict[str, list[str]] = dict(greedy_assignments["target_assigned_units"])
    compiled_constraint_statuses = _apply_compiled_commander_assignment_constraints(
        commander_unit_orders=commander_unit_orders,
        commander_target_orders=commander_target_orders,
        matrix_by_unit=matrix_by_unit,
        target_by_id=target_by_id,
        unit_roles=unit_roles,
        shooting_assignments=shooting_assignments,
        charge_assignments=charge_target_assignments,
        committed_damage=committed_damage,
        target_assigned_units=target_assigned_units,
    )

    unit_tasks: dict[str, UnitBattleTask] = {}
    positioning_tasks: dict[str, UnitPositioningTask] = {}
    fire_assignments: dict[str, UnitFireAssignment] = {}
    charge_assignments: dict[str, ChargeTargetAssignment] = {}
    fight_assignments: dict[str, FightTargetAssignment] = {}
    transport_assignments = _build_transport_assignments(
        general_transport_policy=general_transport_policy,
        battle_round=int(tier1_plan.battle_round),
    )

    for unit_id, task in sorted(tier2_bundle.tasks_by_unit_id.items(), key=lambda item: str(item[0])):
        uid = str(unit_id)
        role = unit_roles.get(uid, _task_role(task.task_type))
        commander_unit_order = commander_unit_orders.get(uid)
        compiled_constraint_status = compiled_constraint_statuses.get(uid, {})
        if (
            commander_unit_order is not None
            and _compiled_unit_order_is_explicit(commander_unit_order)
            and _compiled_unit_order_constraint_mode(commander_unit_order) != "hint"
            and str(getattr(commander_unit_order, "role", "") or "")
        ):
            role = str(getattr(commander_unit_order, "role", "") or role)
        if commander_unit_order is not None and bool(getattr(commander_unit_order, "preserve", False)):
            commander_preserve_sources = set(
                dict(getattr(commander_unit_order, "metadata", {}) or {}).get("source_intent_kinds", []) or []
            )
            if "general_preserve_directive" in commander_preserve_sources:
                role = ROLE_PRESERVE
        unit_entries = matrix_by_unit.get(uid, [])
        shooting_entry = shooting_assignments.get(uid)
        charge_entry = charge_target_assignments.get(uid)
        fire_primary_target_id = str(shooting_entry.target_unit_id) if shooting_entry is not None else None
        charge_primary_target_id = str(charge_entry.target_unit_id) if charge_entry is not None else None
        primary_target_id = fire_primary_target_id or charge_primary_target_id
        backup_target_ids = _assignment_target_backups(
            unit_entries,
            priority_target_ids,
            primary_target_id,
        )
        intentionally_skip_shooting = bool(role == ROLE_MELEE_FIRST and charge_primary_target_id)
        shooting_intent = "planned_focus_fire" if fire_primary_target_id else "opportunistic"
        if intentionally_skip_shooting:
            shooting_intent = "skip_for_charge"
        charge_intent = "planned_charge" if charge_primary_target_id else "opportunistic"
        fight_intent = "planned_fight" if charge_primary_target_id else "opportunistic"
        shooting_metadata = dict(getattr(shooting_entry, "metadata", {}) or {}) if shooting_entry is not None else {}
        shooting_trigger_bands = [
            dict(band)
            for band in list(shooting_metadata.get("weapon_trigger_bands", []) or [])
            if isinstance(band, dict)
        ]
        shooting_can_advance = bool(shooting_metadata.get("has_assault_trigger", False))
        shooting_requires_stationary = bool(
            shooting_metadata.get("has_heavy_stationary_trigger", False)
            and float(shooting_metadata.get("distance_estimate_inches", 0.0) or 0.0)
            <= float(shooting_metadata.get("max_ranged_range_inches", 0.0) or 0.0)
        )
        desired_weapon_bands = {
            str(band.get("trigger_kind", "")): float(band.get("value_delta", 0.0) or 0.0)
            for band in shooting_trigger_bands
            if str(band.get("trigger_kind", "") or "")
        }
        battle_task = _unit_battle_task(
            task,
            role=role,
            primary_target_unit_id=primary_target_id,
            backup_target_unit_ids=backup_target_ids,
            shooting_intent=shooting_intent,
            charge_intent=charge_intent,
            fight_intent=fight_intent,
            shooting_can_advance=shooting_can_advance,
            desired_weapon_bands=desired_weapon_bands,
            metadata={
                "commander_order_bundle_id": str(getattr(commander_orders, "order_bundle_id", "") or ""),
                "commander_unit_order_id": uid if commander_unit_order is not None else "",
                "commander_unit_order_preserve": bool(getattr(commander_unit_order, "preserve", False)),
                "commander_constraint_status": compiled_constraint_status,
                "assignment_source": "strategic_intent_compiler_materialized",
            },
        )
        unit_tasks[str(unit_id)] = battle_task
        expected_damage_by_target = {
            str(entry.target_unit_id): float(entry.expected_shooting_damage)
            for entry in unit_entries
            if float(entry.expected_shooting_damage or 0.0) > 0.0
        }
        desired_range_bands: list[RangeBand] = []
        if shooting_entry is not None:
            max_range = float(dict(shooting_entry.metadata or {}).get("max_ranged_range_inches", 0.0) or 0.0)
            half_range_trigger_bands = [
                band
                for band in shooting_trigger_bands
                if str(band.get("trigger_kind", "")) in {
                    "melta_half_range_damage_bonus",
                    "rapid_fire_half_range_extra_attacks",
                }
            ]
            if half_range_trigger_bands:
                for band in half_range_trigger_bands:
                    desired_range_bands.append(
                        RangeBand(
                            target_unit_id=str(shooting_entry.target_unit_id),
                            minimum_inches=0.0,
                            maximum_inches=float(band.get("range_threshold_inches", 0.0) or 0.0),
                            trigger_kind=str(band.get("trigger_kind", "") or "half_range_trigger"),
                            priority=float(shooting_entry.movement_to_half_range_feasibility)
                            + min(1.0, float(band.get("value_delta", 0.0) or 0.0) / 4.0),
                        )
                    )
            elif max_range > 0.0:
                desired_range_bands.append(
                    RangeBand(
                        target_unit_id=str(shooting_entry.target_unit_id),
                        minimum_inches=0.0,
                        maximum_inches=max_range / 2.0,
                        trigger_kind="generic_half_range",
                        priority=float(shooting_entry.movement_to_half_range_feasibility),
                    )
                )
        requires_half_range = bool(
            shooting_entry is not None
            and (
                (
                    bool(shooting_metadata.get("has_half_range_trigger", False))
                    and float(shooting_entry.movement_to_half_range_feasibility or 0.0) >= 0.5
                )
                or float(shooting_entry.movement_to_half_range_feasibility or 0.0) >= 0.75
            )
        )
        positioning_tasks[str(unit_id)] = UnitPositioningTask(
            unit_id=str(unit_id),
            desired_action=(
                MOVEMENT_ACTION_ADVANCE
                if intentionally_skip_shooting
                else MOVEMENT_ACTION_STATIONARY if shooting_requires_stationary else MOVEMENT_ACTION_NORMAL_MOVE
            ),
            target_regions=_regions_from_task(task),
            required_los_to_unit_ids=(
                [fire_primary_target_id]
                if fire_primary_target_id and not intentionally_skip_shooting
                else []
            ),
            desired_range_bands=desired_range_bands,
            avoid_becoming_shooting_ineligible=bool(not intentionally_skip_shooting and not shooting_can_advance),
            intentionally_accept_shooting_ineligible=intentionally_skip_shooting,
            charge_staging_target_unit_id=charge_primary_target_id if intentionally_skip_shooting else None,
            metadata={
                "commander_role": role,
                "source": "strategic_intent_compiler_materialized",
                "commander_order_bundle_id": str(getattr(commander_orders, "order_bundle_id", "") or ""),
                "shooting_can_advance": bool(shooting_can_advance),
                "shooting_requires_stationary": bool(shooting_requires_stationary),
                "weapon_trigger_band_count": int(len(shooting_trigger_bands)),
                "commander_constraint_status": compiled_constraint_status,
            },
        )
        fire_assignments[str(unit_id)] = UnitFireAssignment(
            unit_id=str(unit_id),
            primary_target_unit_id=fire_primary_target_id if not intentionally_skip_shooting else None,
            backup_target_unit_ids=battle_task.backup_target_unit_ids,
            preferred_declarations=[],
            expected_damage_by_target=expected_damage_by_target,
            requires_los=bool(fire_primary_target_id and not intentionally_skip_shooting),
            requires_half_range=requires_half_range,
            requires_stationary=shooting_requires_stationary,
            allows_split_fire=True,
            metadata={
                "commander_role": role,
                "source": "strategic_intent_compiler_materialized",
                "commander_order_bundle_id": str(getattr(commander_orders, "order_bundle_id", "") or ""),
                "shooting_can_advance": bool(shooting_can_advance),
                "weapon_trigger_bands": shooting_trigger_bands,
                "commander_constraint_status": compiled_constraint_status,
                "trigger_band_kinds": _sorted_strings(
                    [band.get("trigger_kind", "") for band in shooting_trigger_bands]
                ),
            },
        )
        charge_assignments[str(unit_id)] = ChargeTargetAssignment(
            unit_id=str(unit_id),
            primary_target_unit_id=charge_primary_target_id,
            backup_target_unit_ids=battle_task.backup_target_unit_ids,
            desired_charge_probability=(
                float(charge_entry.charge_feasibility)
                if charge_entry is not None
                else 0.0
            ),
            intentionally_skip_shooting=intentionally_skip_shooting,
            metadata={
                "commander_role": role,
                "source": "strategic_intent_compiler_materialized",
                "commander_order_bundle_id": str(getattr(commander_orders, "order_bundle_id", "") or ""),
                "commander_constraint_status": compiled_constraint_status,
            },
        )
        fight_assignments[str(unit_id)] = FightTargetAssignment(
            unit_id=str(unit_id),
            primary_target_unit_id=charge_primary_target_id,
            backup_target_unit_ids=battle_task.backup_target_unit_ids,
            activation_priority=float(
                _risk_budget_for_tier(task.compute_tier)
                + (float(charge_entry.expected_melee_damage) if charge_entry is not None else 0.0)
            ),
            metadata={
                "commander_role": role,
                "source": "strategic_intent_compiler_materialized",
                "commander_order_bundle_id": str(getattr(commander_orders, "order_bundle_id", "") or ""),
                "commander_constraint_status": compiled_constraint_status,
            },
        )

    target_fire_plans = {
        target.target_unit_id: TargetFirePlan(
            target_unit_id=target.target_unit_id,
            threat_score=target.threat_score,
            remaining_wounds_estimate=float(target.metadata.get("remaining_wounds_estimate", 0.0) or 0.0),
            desired_kill_probability=float(
                getattr(commander_target_orders.get(str(target.target_unit_id)), "desired_kill_probability", 0.75)
                if commander_target_orders.get(str(target.target_unit_id)) is not None
                else 0.75
            ),
            committed_expected_damage=float(committed_damage.get(str(target.target_unit_id), 0.0) or 0.0),
            committed_kill_probability=_clamp(
                float(committed_damage.get(str(target.target_unit_id), 0.0) or 0.0)
                / max(1.0, float(target.metadata.get("remaining_wounds_estimate", 0.0) or 0.0))
            ),
            assigned_unit_ids=target_assigned_units.get(str(target.target_unit_id), []),
            overkill_limit=float(
                getattr(
                    commander_target_orders.get(str(target.target_unit_id)),
                    "max_overkill_wounds",
                    COMMANDER_ASSIGNMENT_OVERKILL_LIMIT,
                )
                or COMMANDER_ASSIGNMENT_OVERKILL_LIMIT
            ),
            metadata={
                "assignment_source": "strategic_intent_compiler_materialized",
                "priority_kind": target.priority_kind,
                "commander_order_bundle_id": str(getattr(commander_orders, "order_bundle_id", "") or ""),
                "commander_target_intent": str(
                    getattr(commander_target_orders.get(str(target.target_unit_id)), "intent", "") or ""
                ),
                "commander_target_preferred_phase": str(
                    getattr(commander_target_orders.get(str(target.target_unit_id)), "preferred_phase", "") or ""
                ),
                "commander_target_allowed_resource_kinds": _sorted_strings(
                    getattr(commander_target_orders.get(str(target.target_unit_id)), "allowed_resource_kinds", []) or []
                ),
            },
        )
        for target in priority_targets
    }

    posture = (
        str(getattr(getattr(commander_orders, "directive", None), "posture", "") or "").strip().upper()
        or str(tier1_plan.risk_posture.aggression).strip().upper()
    )
    return BattleRoundPlan(
        plan_id=f"{tier1_plan.plan_id}:battle_round",
        player_id=str(tier1_plan.player_id),
        battle_round=int(tier1_plan.battle_round),
        created_at_generation=generation,
        strategic_posture=posture,
        priority_targets=priority_targets,
        unit_tasks=unit_tasks,
        movement_plan=MovementPhasePlan(
            unit_positioning_tasks=positioning_tasks,
            transport_assignments=transport_assignments,
        ),
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
            "general_plan_id": str(general_plan_id or ""),
            "tier1_plan_id": tier1_plan.plan_id,
            "tier2_plan_id": tier2_bundle.plan_id,
            "deployment_order_bundle_id": str(getattr(deployment_orders, "order_bundle_id", "") or ""),
            "prebattle_order_bundle_id": str(getattr(prebattle_orders, "order_bundle_id", "") or ""),
            "commander_order_bundle_id": str(getattr(commander_orders, "order_bundle_id", "") or ""),
            "commander_order_bundle": commander_orders.to_dict() if commander_orders is not None else {},
            "general_transport_policy_count": int(len(dict(general_transport_policy or {}))),
            "analysis_snapshot": analysis_snapshot.to_dict(),
            "performance_guardrails": {
                "plan_build_budget_ms": int(COMMANDER_PLAN_BUILD_BUDGET_MS),
                "repair_budget_ms": int(COMMANDER_REPAIR_BUDGET_MS),
                "max_targets": int(COMMANDER_ANALYSIS_MAX_TARGETS),
                "max_units": int(COMMANDER_ANALYSIS_MAX_UNITS),
                "max_targets_per_unit": int(COMMANDER_ANALYSIS_MAX_TARGETS_PER_UNIT),
                "max_unit_target_entries": int(COMMANDER_ANALYSIS_MAX_MATRIX_ENTRIES),
                "context_payload_warning_bytes": int(ORCHESTRATION_CONTEXT_PAYLOAD_WARNING_BYTES),
            },
        },
    )


def build_phase_execution_report(
    *,
    phase_name: str,
    player_id: str,
    plan: BattleRoundPlan,
    dirty_flags: CommanderDirtyFlags,
    repair_metadata: dict[str, Any] | None = None,
) -> PhaseExecutionReport:
    metadata: dict[str, Any] = {"dirty_flags": dirty_flags.to_dict()}
    if repair_metadata is not None:
        metadata["repair"] = _sorted_metadata(repair_metadata)
    return PhaseExecutionReport(
        phase_name=str(phase_name),
        player_id=str(player_id),
        plan_id=str(plan.plan_id),
        status=dirty_flags.status(),
        unit_reports=[],
        target_reports=[],
        objective_reports=[],
        recommended_replan_scope=dirty_flags.recommended_replan_scope(),
        metadata=metadata,
    )


def consume_commander_dirty_flags(
    flags: CommanderDirtyFlags,
    consumed_scope: str,
) -> CommanderDirtyFlags:
    scope = str(consumed_scope or REPLAN_SCOPE_NONE)
    if scope == REPLAN_SCOPE_NONE:
        return flags

    movement_plan_dirty = bool(flags.movement_plan_dirty)
    shooting_plan_dirty = bool(flags.shooting_plan_dirty)
    charge_plan_dirty = bool(flags.charge_plan_dirty)
    fight_plan_dirty = bool(flags.fight_plan_dirty)
    target_priorities_dirty = bool(flags.target_priorities_dirty)
    objective_priorities_dirty = bool(flags.objective_priorities_dirty)
    cp_policy_dirty = bool(flags.cp_policy_dirty)
    full_replan_required = bool(flags.full_replan_required)

    if scope in {REPLAN_SCOPE_FULL_ROUND, REPLAN_SCOPE_PHASE}:
        movement_plan_dirty = False
        shooting_plan_dirty = False
        charge_plan_dirty = False
        fight_plan_dirty = False
        target_priorities_dirty = False
        objective_priorities_dirty = False
        cp_policy_dirty = False
        full_replan_required = False
    elif scope == REPLAN_SCOPE_MOVEMENT_ONLY:
        movement_plan_dirty = False
    elif scope == REPLAN_SCOPE_SHOOTING_ONLY:
        shooting_plan_dirty = False
    elif scope == REPLAN_SCOPE_CHARGE_ONLY:
        charge_plan_dirty = False
    elif scope == REPLAN_SCOPE_FIGHT_ONLY:
        fight_plan_dirty = False

    remaining = CommanderDirtyFlags(
        movement_plan_dirty=movement_plan_dirty,
        shooting_plan_dirty=shooting_plan_dirty,
        charge_plan_dirty=charge_plan_dirty,
        fight_plan_dirty=fight_plan_dirty,
        target_priorities_dirty=target_priorities_dirty,
        objective_priorities_dirty=objective_priorities_dirty,
        cp_policy_dirty=cp_policy_dirty,
        full_replan_required=full_replan_required,
        reasons=_sorted_strings(flags.reasons),
        max_severity=float(flags.max_severity),
    )
    if remaining.any_dirty():
        return remaining
    return CommanderDirtyFlags()


def repair_battle_round_plan(
    existing_plan: BattleRoundPlan,
    fresh_plan: BattleRoundPlan,
    repair_scope: str,
) -> BattleRoundPlan:
    scope = str(repair_scope or REPLAN_SCOPE_NONE)
    if scope == REPLAN_SCOPE_NONE:
        return existing_plan

    repair_count = int(existing_plan.invalidation.repair_count) + 1
    invalidation = PlanInvalidationState(
        created_at_generation=(
            int(fresh_plan.created_at_generation)
            if scope == REPLAN_SCOPE_FULL_ROUND
            else int(existing_plan.invalidation.created_at_generation)
        ),
        last_validated_generation=int(fresh_plan.created_at_generation),
        invalidated=False,
        reasons=[],
        repair_count=repair_count,
    )
    metadata = _sorted_metadata(fresh_plan.metadata)
    metadata["last_repair_count"] = int(repair_count)
    metadata["last_repair_generation"] = int(fresh_plan.created_at_generation)
    metadata["last_repair_scope"] = scope

    if scope == REPLAN_SCOPE_FULL_ROUND:
        return replace(
            fresh_plan,
            invalidation=invalidation,
            metadata=metadata,
        )

    updates: dict[str, Any] = {
        "invalidation": invalidation,
        "metadata": metadata,
    }
    if scope == REPLAN_SCOPE_PHASE:
        updates.update(
            {
                "priority_targets": fresh_plan.priority_targets,
                "unit_tasks": fresh_plan.unit_tasks,
                "movement_plan": fresh_plan.movement_plan,
                "shooting_plan": fresh_plan.shooting_plan,
                "charge_plan": fresh_plan.charge_plan,
                "fight_plan": fresh_plan.fight_plan,
            }
        )
    elif scope == REPLAN_SCOPE_MOVEMENT_ONLY:
        updates["movement_plan"] = fresh_plan.movement_plan
    elif scope == REPLAN_SCOPE_SHOOTING_ONLY:
        updates["shooting_plan"] = fresh_plan.shooting_plan
    elif scope == REPLAN_SCOPE_CHARGE_ONLY:
        updates["charge_plan"] = fresh_plan.charge_plan
    elif scope == REPLAN_SCOPE_FIGHT_ONLY:
        updates["fight_plan"] = fresh_plan.fight_plan

    return replace(existing_plan, **updates)
