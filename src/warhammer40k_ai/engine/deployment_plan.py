from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any

from .orchestration_guardrails import (
    DEPLOYMENT_PLAN_BUILD_BUDGET_MS,
    DEPLOYMENT_REPAIR_BUDGET_MS,
    ORCHESTRATION_CONTEXT_PAYLOAD_WARNING_BYTES,
)
from .strategic_intent_compiler import (
    DeploymentOrderBundle,
    compile_general_intent_to_deployment_orders,
)
from ..utility.entity_ids import get_entity_id


DEPLOYMENT_STATUS_ON_PLAN = "on_plan"
DEPLOYMENT_STATUS_MINOR_VARIANCE = "minor_variance"
DEPLOYMENT_STATUS_MAJOR_VARIANCE = "major_variance"

DEPLOYMENT_REPLAN_SCOPE_NONE = "none"
DEPLOYMENT_REPLAN_SCOPE_REMAINING_DROPS = "remaining_drops"
DEPLOYMENT_REPLAN_SCOPE_TRANSPORT_ONLY = "transport_only"
DEPLOYMENT_REPLAN_SCOPE_RESERVES_ONLY = "reserves_only"
DEPLOYMENT_REPLAN_SCOPE_FULL_DEPLOYMENT = "full_deployment"

DEPLOYMENT_ROLE_HIDE = "hide"
DEPLOYMENT_ROLE_SCREEN = "screen"
DEPLOYMENT_ROLE_STAGE = "stage"
DEPLOYMENT_ROLE_ALPHA = "alpha"
DEPLOYMENT_ROLE_SCORE = "score"
DEPLOYMENT_ROLE_COUNTERPUNCH = "counterpunch"
DEPLOYMENT_ROLE_RESERVE = "reserve"
DEPLOYMENT_ROLE_TRANSPORTED = "transported"

DROP_WINDOW_EARLY = "early"
DROP_WINDOW_MIDDLE = "middle"
DROP_WINDOW_LATE = "late"
DROP_WINDOW_ANY = "any"

DEFAULT_SCOUT_LANES = (
    "left_no_mans_land_lane",
    "center_no_mans_land_lane",
    "right_no_mans_land_lane",
)
DEFAULT_FORWARD_REGIONS = (
    "left_forward_screen",
    "center_forward_screen",
    "right_forward_screen",
)


def _sorted_strings(values: list[object] | tuple[object, ...] | set[object] | None) -> list[str]:
    return sorted({str(value) for value in list(values or []) if str(value)})


def _sorted_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    return {str(key): value for key, value in sorted(dict(metadata or {}).items(), key=lambda item: str(item[0]))}


def _entity_id(entity: object) -> str:
    return str(get_entity_id(entity) or getattr(entity, "id", "") or getattr(entity, "_id", "") or "")


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


@dataclass(frozen=True)
class DeploymentDirtyFlags:
    remaining_drops_dirty: bool = False
    enemy_information_dirty: bool = False
    transport_plan_dirty: bool = False
    reserve_plan_dirty: bool = False
    full_replan_required: bool = False
    reasons: list[str] = field(default_factory=list)
    max_severity: float = 0.0

    def any_dirty(self) -> bool:
        return bool(
            self.remaining_drops_dirty
            or self.enemy_information_dirty
            or self.transport_plan_dirty
            or self.reserve_plan_dirty
            or self.full_replan_required
        )

    def status(self) -> str:
        if not self.any_dirty():
            return DEPLOYMENT_STATUS_ON_PLAN
        if self.full_replan_required or self.max_severity >= 0.65:
            return DEPLOYMENT_STATUS_MAJOR_VARIANCE
        return DEPLOYMENT_STATUS_MINOR_VARIANCE

    def recommended_replan_scope(self) -> str:
        if not self.any_dirty():
            return DEPLOYMENT_REPLAN_SCOPE_NONE
        if self.full_replan_required:
            return DEPLOYMENT_REPLAN_SCOPE_FULL_DEPLOYMENT
        if self.enemy_information_dirty or self.remaining_drops_dirty:
            return DEPLOYMENT_REPLAN_SCOPE_REMAINING_DROPS
        if self.transport_plan_dirty:
            return DEPLOYMENT_REPLAN_SCOPE_TRANSPORT_ONLY
        if self.reserve_plan_dirty:
            return DEPLOYMENT_REPLAN_SCOPE_RESERVES_ONLY
        return DEPLOYMENT_REPLAN_SCOPE_NONE

    def marked(
        self,
        *,
        remaining_drops_dirty: bool = False,
        enemy_information_dirty: bool = False,
        transport_plan_dirty: bool = False,
        reserve_plan_dirty: bool = False,
        full_replan_required: bool = False,
        reason: str = "",
        severity: float = 0.0,
    ) -> "DeploymentDirtyFlags":
        reasons = _sorted_strings(list(self.reasons or []) + ([reason] if str(reason or "") else []))
        return DeploymentDirtyFlags(
            remaining_drops_dirty=bool(self.remaining_drops_dirty or remaining_drops_dirty),
            enemy_information_dirty=bool(self.enemy_information_dirty or enemy_information_dirty),
            transport_plan_dirty=bool(self.transport_plan_dirty or transport_plan_dirty),
            reserve_plan_dirty=bool(self.reserve_plan_dirty or reserve_plan_dirty),
            full_replan_required=bool(self.full_replan_required or full_replan_required),
            reasons=reasons,
            max_severity=max(float(self.max_severity), float(severity or 0.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "remaining_drops_dirty": bool(self.remaining_drops_dirty),
            "enemy_information_dirty": bool(self.enemy_information_dirty),
            "transport_plan_dirty": bool(self.transport_plan_dirty),
            "reserve_plan_dirty": bool(self.reserve_plan_dirty),
            "full_replan_required": bool(self.full_replan_required),
            "reasons": _sorted_strings(self.reasons),
            "max_severity": float(self.max_severity),
            "status": self.status(),
            "recommended_replan_scope": self.recommended_replan_scope(),
        }


@dataclass(frozen=True)
class DeploymentInformationState:
    own_deployed_unit_ids: list[str] = field(default_factory=list)
    enemy_deployed_unit_ids: list[str] = field(default_factory=list)
    own_unplaced_unit_ids: list[str] = field(default_factory=list)
    enemy_unplaced_unit_ids: list[str] = field(default_factory=list)
    own_reserve_unit_ids: list[str] = field(default_factory=list)
    enemy_reserve_unit_ids: list[str] = field(default_factory=list)
    own_embarked_unit_ids: list[str] = field(default_factory=list)
    enemy_embarked_unit_ids: list[str] = field(default_factory=list)
    known_enemy_attachments: dict[str, str] = field(default_factory=dict)
    enemy_scout_unit_ids_known: list[str] = field(default_factory=list)
    enemy_infiltrate_unit_ids_known: list[str] = field(default_factory=list)
    own_scout_unit_ids_unplaced: list[str] = field(default_factory=list)
    own_infiltrate_unit_ids_unplaced: list[str] = field(default_factory=list)
    contested_forward_regions: list[str] = field(default_factory=list)
    scout_lanes: dict[str, Any] = field(default_factory=dict)
    infiltrate_deny_zones: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "own_deployed_unit_ids": _sorted_strings(self.own_deployed_unit_ids),
            "enemy_deployed_unit_ids": _sorted_strings(self.enemy_deployed_unit_ids),
            "own_unplaced_unit_ids": _sorted_strings(self.own_unplaced_unit_ids),
            "enemy_unplaced_unit_ids": _sorted_strings(self.enemy_unplaced_unit_ids),
            "own_reserve_unit_ids": _sorted_strings(self.own_reserve_unit_ids),
            "enemy_reserve_unit_ids": _sorted_strings(self.enemy_reserve_unit_ids),
            "own_embarked_unit_ids": _sorted_strings(self.own_embarked_unit_ids),
            "enemy_embarked_unit_ids": _sorted_strings(self.enemy_embarked_unit_ids),
            "known_enemy_attachments": {
                str(unit_id): str(root_id)
                for unit_id, root_id in sorted(
                    dict(self.known_enemy_attachments or {}).items(),
                    key=lambda item: str(item[0]),
                )
            },
            "enemy_scout_unit_ids_known": _sorted_strings(self.enemy_scout_unit_ids_known),
            "enemy_infiltrate_unit_ids_known": _sorted_strings(self.enemy_infiltrate_unit_ids_known),
            "own_scout_unit_ids_unplaced": _sorted_strings(self.own_scout_unit_ids_unplaced),
            "own_infiltrate_unit_ids_unplaced": _sorted_strings(self.own_infiltrate_unit_ids_unplaced),
            "contested_forward_regions": _sorted_strings(self.contested_forward_regions),
            "scout_lanes": _sorted_metadata(self.scout_lanes),
            "infiltrate_deny_zones": _sorted_metadata(self.infiltrate_deny_zones),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class DeploymentDoctrine:
    go_first_posture: str = "stage_alpha_lanes"
    go_second_posture: str = "hide_and_counterpunch"
    tactical_flexibility_weight: float = 0.5
    reserve_posture: str = "forced_or_late_scoring"
    transport_posture: str = "preserve_and_deliver"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "go_first_posture": str(self.go_first_posture),
            "go_second_posture": str(self.go_second_posture),
            "tactical_flexibility_weight": float(self.tactical_flexibility_weight),
            "reserve_posture": str(self.reserve_posture),
            "transport_posture": str(self.transport_posture),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class DeploymentTempoCapability:
    unit_id: str
    has_infiltrate: bool = False
    has_scout: bool = False
    scout_distance_inches: float = 0.0
    forward_deploy_distance_class: str = "deployment_zone"
    blocks_enemy_scout_lanes: bool = False
    screens_enemy_infiltrate: bool = False
    early_drop_priority: float = 0.0
    late_drop_priority: float = 0.0
    reveal_risk: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": str(self.unit_id),
            "has_infiltrate": bool(self.has_infiltrate),
            "has_scout": bool(self.has_scout),
            "scout_distance_inches": float(self.scout_distance_inches),
            "forward_deploy_distance_class": str(self.forward_deploy_distance_class),
            "blocks_enemy_scout_lanes": bool(self.blocks_enemy_scout_lanes),
            "screens_enemy_infiltrate": bool(self.screens_enemy_infiltrate),
            "early_drop_priority": float(self.early_drop_priority),
            "late_drop_priority": float(self.late_drop_priority),
            "reveal_risk": float(self.reveal_risk),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class ScoutProjection:
    unit_id: str
    deployment_region_id: str
    scout_distance_inches: float
    projected_regions_after_scout: list[str] = field(default_factory=list)
    can_reach_cover: bool = False
    can_threaten_objective_ids: list[str] = field(default_factory=list)
    can_screen_lane_ids: list[str] = field(default_factory=list)
    exposure_if_go_second: float = 0.0
    value_if_go_first: float = 0.0
    value_if_go_second: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": str(self.unit_id),
            "deployment_region_id": str(self.deployment_region_id),
            "scout_distance_inches": float(self.scout_distance_inches),
            "projected_regions_after_scout": _sorted_strings(self.projected_regions_after_scout),
            "can_reach_cover": bool(self.can_reach_cover),
            "can_threaten_objective_ids": _sorted_strings(self.can_threaten_objective_ids),
            "can_screen_lane_ids": _sorted_strings(self.can_screen_lane_ids),
            "exposure_if_go_second": float(self.exposure_if_go_second),
            "value_if_go_first": float(self.value_if_go_first),
            "value_if_go_second": float(self.value_if_go_second),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class InfiltrateProjection:
    unit_id: str
    infiltrate_region_id: str
    blocks_enemy_scout_lane_ids: list[str] = field(default_factory=list)
    screens_objective_ids: list[str] = field(default_factory=list)
    denies_enemy_forward_regions: list[str] = field(default_factory=list)
    preserves_own_scout_lane_ids: list[str] = field(default_factory=list)
    exposure_if_go_second: float = 0.0
    counter_deploy_value: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": str(self.unit_id),
            "infiltrate_region_id": str(self.infiltrate_region_id),
            "blocks_enemy_scout_lane_ids": _sorted_strings(self.blocks_enemy_scout_lane_ids),
            "screens_objective_ids": _sorted_strings(self.screens_objective_ids),
            "denies_enemy_forward_regions": _sorted_strings(self.denies_enemy_forward_regions),
            "preserves_own_scout_lane_ids": _sorted_strings(self.preserves_own_scout_lane_ids),
            "exposure_if_go_second": float(self.exposure_if_go_second),
            "counter_deploy_value": float(self.counter_deploy_value),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class UnitDeploymentTask:
    unit_id: str
    role: str
    preferred_regions: list[str] = field(default_factory=list)
    forbidden_regions: list[str] = field(default_factory=list)
    needs_obscuring: bool = False
    avoid_alpha_exposure: bool = False
    preserve_for_late_game: bool = False
    supports_transport_plan: bool = False
    go_first_value: float = 0.0
    go_second_safety: float = 0.0
    tactical_flexibility: float = 0.0
    deployment_sequence_priority: float = 0.0
    preferred_drop_window: str = DROP_WINDOW_ANY
    has_scout: bool = False
    has_infiltrate: bool = False
    scout_lane_targets: list[str] = field(default_factory=list)
    infiltrate_screen_regions: list[str] = field(default_factory=list)
    counter_scout_regions: list[str] = field(default_factory=list)
    no_mans_land_pressure_regions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": str(self.unit_id),
            "role": str(self.role),
            "preferred_regions": _sorted_strings(self.preferred_regions),
            "forbidden_regions": _sorted_strings(self.forbidden_regions),
            "needs_obscuring": bool(self.needs_obscuring),
            "avoid_alpha_exposure": bool(self.avoid_alpha_exposure),
            "preserve_for_late_game": bool(self.preserve_for_late_game),
            "supports_transport_plan": bool(self.supports_transport_plan),
            "go_first_value": float(self.go_first_value),
            "go_second_safety": float(self.go_second_safety),
            "tactical_flexibility": float(self.tactical_flexibility),
            "deployment_sequence_priority": float(self.deployment_sequence_priority),
            "preferred_drop_window": str(self.preferred_drop_window),
            "has_scout": bool(self.has_scout),
            "has_infiltrate": bool(self.has_infiltrate),
            "scout_lane_targets": _sorted_strings(self.scout_lane_targets),
            "infiltrate_screen_regions": _sorted_strings(self.infiltrate_screen_regions),
            "counter_scout_regions": _sorted_strings(self.counter_scout_regions),
            "no_mans_land_pressure_regions": _sorted_strings(self.no_mans_land_pressure_regions),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class TransportDeploymentTask:
    transport_unit_id: str
    passenger_unit_ids: list[str] = field(default_factory=list)
    initial_deployment_role: str = "deliver"
    delivery_round: int | None = None
    delivery_region_ids: list[str] = field(default_factory=list)
    preserve_passengers: bool = True
    post_delivery_role: str = "screen_objective"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "transport_unit_id": str(self.transport_unit_id),
            "passenger_unit_ids": _sorted_strings(self.passenger_unit_ids),
            "initial_deployment_role": str(self.initial_deployment_role),
            "delivery_region_ids": _sorted_strings(self.delivery_region_ids),
            "preserve_passengers": bool(self.preserve_passengers),
            "post_delivery_role": str(self.post_delivery_role),
            "metadata": _sorted_metadata(self.metadata),
        }
        if self.delivery_round is not None:
            data["delivery_round"] = int(self.delivery_round)
        return data


@dataclass(frozen=True)
class DeploymentContingencyBranch:
    branch_id: str
    trigger: str
    posture: str
    priority: float = 0.0
    unit_role_overrides: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch_id": str(self.branch_id),
            "trigger": str(self.trigger),
            "posture": str(self.posture),
            "priority": float(self.priority),
            "unit_role_overrides": {
                str(unit_id): str(role)
                for unit_id, role in sorted(
                    dict(self.unit_role_overrides or {}).items(),
                    key=lambda item: str(item[0]),
                )
            },
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class DeploymentPhaseReport:
    phase_name: str
    player_id: str
    plan_id: str
    status: str
    recommended_replan_scope: str = DEPLOYMENT_REPLAN_SCOPE_NONE
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase_name": str(self.phase_name),
            "player_id": str(self.player_id),
            "plan_id": str(self.plan_id),
            "status": str(self.status),
            "recommended_replan_scope": str(self.recommended_replan_scope),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class DeploymentPlan:
    plan_id: str
    player_id: str
    created_at_generation: int
    mission_id: str
    deployment_map_id: str
    terrain_layout_id: str
    first_turn_unknown: bool
    secondary_mode: str
    information_state: DeploymentInformationState
    doctrine: DeploymentDoctrine
    unit_tasks: dict[str, UnitDeploymentTask] = field(default_factory=dict)
    tempo_capabilities: dict[str, DeploymentTempoCapability] = field(default_factory=dict)
    scout_projections: dict[str, ScoutProjection] = field(default_factory=dict)
    infiltrate_projections: dict[str, InfiltrateProjection] = field(default_factory=dict)
    transport_tasks: dict[str, TransportDeploymentTask] = field(default_factory=dict)
    contingency_branches: list[DeploymentContingencyBranch] = field(default_factory=list)
    dirty_flags: DeploymentDirtyFlags = field(default_factory=DeploymentDirtyFlags)
    repair_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": str(self.plan_id),
            "player_id": str(self.player_id),
            "created_at_generation": int(self.created_at_generation),
            "mission_id": str(self.mission_id),
            "deployment_map_id": str(self.deployment_map_id),
            "terrain_layout_id": str(self.terrain_layout_id),
            "first_turn_unknown": bool(self.first_turn_unknown),
            "secondary_mode": str(self.secondary_mode),
            "information_state": self.information_state.to_dict(),
            "doctrine": self.doctrine.to_dict(),
            "unit_tasks": {
                str(unit_id): task.to_dict()
                for unit_id, task in sorted(self.unit_tasks.items(), key=lambda item: str(item[0]))
            },
            "tempo_capabilities": {
                str(unit_id): capability.to_dict()
                for unit_id, capability in sorted(self.tempo_capabilities.items(), key=lambda item: str(item[0]))
            },
            "scout_projections": {
                str(unit_id): projection.to_dict()
                for unit_id, projection in sorted(self.scout_projections.items(), key=lambda item: str(item[0]))
            },
            "infiltrate_projections": {
                str(unit_id): projection.to_dict()
                for unit_id, projection in sorted(self.infiltrate_projections.items(), key=lambda item: str(item[0]))
            },
            "transport_tasks": {
                str(unit_id): task.to_dict()
                for unit_id, task in sorted(self.transport_tasks.items(), key=lambda item: str(item[0]))
            },
            "contingency_branches": [
                branch.to_dict()
                for branch in sorted(
                    self.contingency_branches,
                    key=lambda item: (str(item.branch_id), str(item.trigger)),
                )
            ],
            "dirty_flags": self.dirty_flags.to_dict(),
            "repair_count": int(self.repair_count),
            "metadata": _sorted_metadata(self.metadata),
        }


def _player_for_id(game: object, player_id: str):
    for player in list(getattr(game, "players", []) or []):
        if str(getattr(player, "id", "") or "") == str(player_id or ""):
            return player
    return None


def _player_army(player: object):
    get_army = getattr(player, "get_army", None)
    if callable(get_army):
        return get_army()
    return getattr(player, "army", None)


def _player_units(player: object) -> list[object]:
    army = _player_army(player)
    return sorted(
        [unit for unit in list(getattr(army, "units", []) or []) if unit is not None and _entity_id(unit)],
        key=lambda unit: _entity_id(unit),
    )


def _opponent_units(game: object, player_id: str) -> list[object]:
    units: list[object] = []
    for player in list(getattr(game, "players", []) or []):
        if str(getattr(player, "id", "") or "") == str(player_id or ""):
            continue
        units.extend(_player_units(player))
    return sorted(units, key=lambda unit: _entity_id(unit))


def _unit_keywords(unit: object) -> set[str]:
    keywords: list[object] = []
    keywords.extend(list(getattr(unit, "keywords", []) or []))
    keywords.extend(list(getattr(unit, "faction_keywords", []) or []))
    for model in list(getattr(unit, "models", []) or []):
        keywords.extend(list(getattr(model, "keywords", []) or []))
        keywords.extend(list(getattr(model, "faction_keywords", []) or []))
    if bool(getattr(unit, "is_transport", False)):
        keywords.append("TRANSPORT")
    return {str(keyword).strip().upper() for keyword in keywords if str(keyword).strip()}


def _unit_name(unit: object) -> str:
    return str(getattr(unit, "name", "") or getattr(unit, "id", "") or getattr(unit, "_id", "") or "").lower()


def _unit_flag_from_method(unit: object, method_name: str) -> bool:
    method = getattr(unit, method_name, None)
    if not callable(method):
        return False
    value = method()
    if isinstance(value, (list, tuple)):
        if not value:
            return False
        return bool(value[0])
    return bool(value)


def _keyword_contains(keywords: set[str], token: str) -> bool:
    needle = str(token or "").strip().upper()
    return any(keyword == needle or keyword.startswith(f"{needle} ") for keyword in keywords)


def _scout_distance_from_text(values: list[str]) -> float:
    for value in values:
        match = re.search(r"SCOUTS?\s*(\d+(?:\.\d+)?)", str(value or "").upper())
        if match is not None:
            return _floatish(match.group(1), 6.0)
    return 6.0


def _unit_scout_capability(unit: object) -> tuple[bool, float]:
    method = getattr(unit, "has_scout", None)
    if callable(method):
        value = method()
        if isinstance(value, (list, tuple)):
            has_scout = bool(value[0]) if value else False
            distance = _floatish(value[1], 0.0) if len(value) > 1 else 0.0
            if has_scout:
                return True, max(0.0, distance)
        elif bool(value):
            return True, max(0.0, _floatish(getattr(unit, "scout_move_distance", 6.0), 6.0))
    if _unit_flag_from_method(unit, "has_scout_move"):
        return True, max(0.0, _floatish(getattr(unit, "scout_move_distance", 6.0), 6.0))
    explicit_distance = _floatish(getattr(unit, "scout_move_distance", 0.0), 0.0)
    if explicit_distance > 0.0:
        return True, explicit_distance

    keywords = _unit_keywords(unit)
    keyword_values = _sorted_strings(list(keywords))
    name = _unit_name(unit).upper()
    if _keyword_contains(keywords, "SCOUT") or _keyword_contains(keywords, "SCOUTS") or "SCOUT" in name:
        return True, _scout_distance_from_text(keyword_values + [name])
    return False, 0.0


def _unit_has_infiltrate(unit: object) -> bool:
    if _unit_flag_from_method(unit, "has_infiltrate"):
        return True
    keywords = _unit_keywords(unit)
    name = _unit_name(unit)
    return bool(
        _keyword_contains(keywords, "INFILTRATOR")
        or _keyword_contains(keywords, "INFILTRATORS")
        or "infiltrat" in name
    )


def deployment_tempo_capability_for_unit(
    unit: object,
    *,
    enemy_scout_pressure: bool = False,
    enemy_infiltrate_pressure: bool = False,
    first_turn_unknown: bool = False,
) -> DeploymentTempoCapability:
    """Build deterministic deployment-tempo metadata for one unit.

    This is intentionally approximate and non-authoritative. It exposes
    deployment-order pressure to future rankers without changing legality.
    """

    unit_id = _entity_id(unit)
    has_scout, scout_distance = _unit_scout_capability(unit)
    has_infiltrate = _unit_has_infiltrate(unit)

    early_priority = 0.0
    late_priority = 0.0
    if has_infiltrate:
        early_priority += 2.0
        if enemy_scout_pressure:
            early_priority += 1.0
        early_priority += 0.8
    if has_scout:
        early_priority += 1.5
        early_priority += 0.8
        if enemy_infiltrate_pressure:
            early_priority -= 0.7
    if not has_scout and not has_infiltrate:
        late_priority += 0.25

    reveal_risk = 0.0
    if first_turn_unknown and has_scout:
        reveal_risk += 0.25
    if first_turn_unknown and has_infiltrate:
        reveal_risk += 0.35
    if enemy_infiltrate_pressure and has_scout:
        reveal_risk += 0.15

    return DeploymentTempoCapability(
        unit_id=unit_id,
        has_infiltrate=has_infiltrate,
        has_scout=has_scout,
        scout_distance_inches=scout_distance,
        forward_deploy_distance_class="infiltrate" if has_infiltrate else "deployment_zone",
        blocks_enemy_scout_lanes=has_infiltrate,
        screens_enemy_infiltrate=bool(has_infiltrate or has_scout),
        early_drop_priority=max(0.0, early_priority),
        late_drop_priority=max(0.0, late_priority),
        reveal_risk=round(max(0.0, reveal_risk), 6),
        metadata={
            "source": "deployment_tempo_scaffold",
            "enemy_scout_pressure": bool(enemy_scout_pressure),
            "enemy_infiltrate_pressure": bool(enemy_infiltrate_pressure),
            "first_turn_unknown": bool(first_turn_unknown),
        },
    )


def _is_transport_unit(unit: object) -> bool:
    keywords = _unit_keywords(unit)
    transport_capacity = getattr(unit, "transport_capacity", 0)
    try:
        capacity = int(transport_capacity or 0)
    except (TypeError, ValueError):
        capacity = 0
    return bool(getattr(unit, "is_transport", False)) or "TRANSPORT" in keywords or capacity > 0


def _unit_is_in_reserves(unit: object) -> bool:
    reserve_fn = getattr(unit, "is_in_reserves", None)
    if callable(reserve_fn):
        return bool(reserve_fn())
    reserve_status = str(getattr(unit, "reserve_status", "") or "").strip().lower()
    return reserve_status in {"reserves", "strategic_reserves"}


def _unit_is_embarked(unit: object) -> bool:
    embarked_attr = getattr(unit, "is_embarked", None)
    if callable(embarked_attr):
        if bool(embarked_attr()):
            return True
    elif embarked_attr is not None and bool(embarked_attr):
        return True
    reserve_status = str(getattr(unit, "reserve_status", "") or "").strip().lower()
    return bool(getattr(unit, "embarked_in", None) is not None or reserve_status == "embarked")


def _split_deployment_state(units: list[object]) -> dict[str, list[str]]:
    deployed: list[str] = []
    unplaced: list[str] = []
    reserve: list[str] = []
    embarked: list[str] = []
    for unit in sorted(list(units or []), key=lambda candidate: _entity_id(candidate)):
        unit_id = _entity_id(unit)
        if not unit_id:
            continue
        if _unit_is_embarked(unit):
            embarked.append(unit_id)
        elif _unit_is_in_reserves(unit):
            reserve.append(unit_id)
        elif bool(getattr(unit, "deployed", True)):
            deployed.append(unit_id)
        else:
            unplaced.append(unit_id)
    return {
        "deployed": _sorted_strings(deployed),
        "unplaced": _sorted_strings(unplaced),
        "reserve": _sorted_strings(reserve),
        "embarked": _sorted_strings(embarked),
    }


def _known_attachments(units: list[object]) -> dict[str, str]:
    attachments: dict[str, str] = {}
    for unit in sorted(list(units or []), key=lambda candidate: _entity_id(candidate)):
        unit_id = _entity_id(unit)
        if not unit_id:
            continue
        root = None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
        if root is None:
            root = getattr(unit, "attached_to", None)
        if root is None:
            continue
        root_id = _entity_id(root)
        if root_id and root_id != unit_id:
            attachments[unit_id] = root_id
    return attachments


def _iter_weapon_profiles(unit: object, mode: str) -> list[object]:
    profiles: list[object] = []
    for model in list(getattr(unit, "models", []) or []):
        for wargear in list(getattr(model, "wargear", []) or []):
            if wargear is None:
                continue
            mode_method = getattr(wargear, f"is_{mode}", None)
            matches = bool(mode_method()) if callable(mode_method) else str(getattr(wargear, "type", "") or "") == mode
            if not matches:
                continue
            wargear_profiles = getattr(wargear, "profiles", {}) or {}
            if isinstance(wargear_profiles, dict):
                profiles.extend(list(wargear_profiles.values()))
            else:
                profiles.extend(list(wargear_profiles or []))
    return profiles


def _profile_output_score(profile: object) -> float:
    attacks = _floatish(getattr(profile, "attacks", 1.0), 1.0)
    strength = _floatish(getattr(profile, "strength", 4.0), 4.0)
    damage = _floatish(getattr(profile, "damage", 1.0), 1.0)
    ap = abs(_floatish(getattr(profile, "ap", 0.0), 0.0))
    return max(0.0, attacks * max(0.5, damage) * (1.0 + min(strength, 12.0) / 12.0) * (1.0 + min(ap, 4.0) * 0.15))


def _unit_mode_output(unit: object, mode: str) -> float:
    profiles = _iter_weapon_profiles(unit, mode)
    if not profiles:
        return 0.0
    return float(sum(_profile_output_score(profile) for profile in profiles))


def _unit_wounds_estimate(unit: object) -> float:
    total = 0.0
    for model in list(getattr(unit, "models", []) or []):
        wounds = getattr(model, "wounds", None)
        if wounds is None:
            wounds = getattr(model, "max_wounds", None)
        total += _floatish(wounds, 1.0)
    if total > 0.0:
        return total
    unit_attrs = getattr(unit, "__dict__", {}) or {}
    for key in ("wounds", "_wounds", "max_wounds", "_max_wounds"):
        if key in unit_attrs:
            return _floatish(unit_attrs.get(key), 1.0)
    return 1.0


def _unit_oc_estimate(unit: object) -> float:
    total = 0.0
    for model in list(getattr(unit, "models", []) or []):
        total += _floatish(getattr(model, "objective_control", 0.0), 0.0)
    if total > 0.0:
        return total
    unit_attrs = getattr(unit, "__dict__", {}) or {}
    for key in ("objective_control", "_objective_control"):
        if key in unit_attrs:
            return _floatish(unit_attrs.get(key), 0.0)
    return 0.0


def _unit_point_estimate(unit: object) -> float:
    unit_attrs = getattr(unit, "__dict__", {}) or {}
    for key in ("points", "_points"):
        if key in unit_attrs and unit_attrs.get(key) is not None:
            return max(0.0, _floatish(unit_attrs.get(key), 0.0))
    models_cost = getattr(unit, "models_cost", None)
    get_cost = getattr(unit, "get_unit_cost", None)
    if callable(get_cost) and isinstance(models_cost, dict):
        return max(0.0, _floatish(get_cost(), 0.0))
    return 0.0


def _passenger_transport_lookup(transport_policy: dict[str, object]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for transport_id, doctrine in sorted(dict(transport_policy or {}).items(), key=lambda item: str(item[0])):
        for passenger_id in list(getattr(doctrine, "passenger_unit_ids", []) or []):
            pid = str(passenger_id or "")
            if pid:
                lookup[pid] = str(transport_id)
    return lookup


def _contested_forward_regions(enemy_tempo_capabilities: dict[str, DeploymentTempoCapability]) -> list[str]:
    enemy_forward_pressure = any(
        capability.has_scout or capability.has_infiltrate
        for capability in dict(enemy_tempo_capabilities or {}).values()
    )
    return _sorted_strings(DEFAULT_FORWARD_REGIONS if enemy_forward_pressure else [])


def _scout_lanes_metadata(enemy_tempo_capabilities: dict[str, DeploymentTempoCapability]) -> dict[str, Any]:
    enemy_scout_count = sum(
        1 for capability in dict(enemy_tempo_capabilities or {}).values() if capability.has_scout
    )
    enemy_infiltrate_count = sum(
        1 for capability in dict(enemy_tempo_capabilities or {}).values() if capability.has_infiltrate
    )
    blocked = bool(enemy_infiltrate_count > 0)
    lanes: dict[str, Any] = {}
    for idx, lane_id in enumerate(DEFAULT_SCOUT_LANES):
        lanes[str(lane_id)] = {
            "lane_id": str(lane_id),
            "sequence_index": int(idx),
            "enemy_scout_pressure": float(enemy_scout_count),
            "enemy_infiltrate_block_penalty": 0.35 if blocked else 0.0,
            "blocked_by_enemy_infiltrate": blocked,
        }
    return lanes


def _infiltrate_deny_zone_metadata(enemy_tempo_capabilities: dict[str, DeploymentTempoCapability]) -> dict[str, Any]:
    enemy_scout_count = sum(
        1 for capability in dict(enemy_tempo_capabilities or {}).values() if capability.has_scout
    )
    enemy_infiltrate_count = sum(
        1 for capability in dict(enemy_tempo_capabilities or {}).values() if capability.has_infiltrate
    )
    zones: dict[str, Any] = {}
    for idx, region_id in enumerate(DEFAULT_FORWARD_REGIONS):
        zones[str(region_id)] = {
            "region_id": str(region_id),
            "sequence_index": int(idx),
            "enemy_scout_pressure": float(enemy_scout_count),
            "enemy_infiltrate_pressure": float(enemy_infiltrate_count),
            "counter_scout_value": round(0.35 + min(1.0, enemy_scout_count * 0.4), 6),
        }
    return zones


def _scout_projections(
    tempo_capabilities: dict[str, DeploymentTempoCapability],
    information_state: DeploymentInformationState,
) -> dict[str, ScoutProjection]:
    lane_ids = _sorted_strings(list(dict(information_state.scout_lanes or {}).keys()) or list(DEFAULT_SCOUT_LANES))
    blocked_lane_count = sum(
        1
        for lane in dict(information_state.scout_lanes or {}).values()
        if bool(dict(lane or {}).get("blocked_by_enemy_infiltrate", False))
    )
    projections: dict[str, ScoutProjection] = {}
    for unit_id, capability in sorted(dict(tempo_capabilities or {}).items(), key=lambda item: str(item[0])):
        if not capability.has_scout:
            continue
        exposure = float(capability.reveal_risk) + min(0.35, blocked_lane_count * 0.1)
        projections[str(unit_id)] = ScoutProjection(
            unit_id=str(unit_id),
            deployment_region_id="deployment_zone_forward_edge",
            scout_distance_inches=float(capability.scout_distance_inches),
            projected_regions_after_scout=[
                f"{lane_id}:post_scout_cover"
                for lane_id in lane_ids
            ],
            can_reach_cover=True,
            can_threaten_objective_ids=["midfield_objective"],
            can_screen_lane_ids=lane_ids,
            exposure_if_go_second=round(exposure, 6),
            value_if_go_first=round(0.65 + min(0.4, len(lane_ids) * 0.08), 6),
            value_if_go_second=round(max(0.15, 0.55 - exposure), 6),
            metadata={
                "source": "deployment_tempo_scaffold",
                "blocked_lane_count": int(blocked_lane_count),
            },
        )
    return projections


def _infiltrate_projections(
    tempo_capabilities: dict[str, DeploymentTempoCapability],
    information_state: DeploymentInformationState,
) -> dict[str, InfiltrateProjection]:
    scout_lane_ids = _sorted_strings(
        list(dict(information_state.scout_lanes or {}).keys()) or list(DEFAULT_SCOUT_LANES)
    )
    forward_regions = _sorted_strings(information_state.contested_forward_regions or list(DEFAULT_FORWARD_REGIONS))
    enemy_scout_count = len(_sorted_strings(information_state.enemy_scout_unit_ids_known))
    projections: dict[str, InfiltrateProjection] = {}
    for unit_id, capability in sorted(dict(tempo_capabilities or {}).items(), key=lambda item: str(item[0])):
        if not capability.has_infiltrate:
            continue
        projections[str(unit_id)] = InfiltrateProjection(
            unit_id=str(unit_id),
            infiltrate_region_id="forward_counter_scout_screen",
            blocks_enemy_scout_lane_ids=scout_lane_ids,
            screens_objective_ids=["midfield_objective"],
            denies_enemy_forward_regions=forward_regions,
            preserves_own_scout_lane_ids=scout_lane_ids,
            exposure_if_go_second=float(capability.reveal_risk),
            counter_deploy_value=round(0.8 + min(1.2, enemy_scout_count * 0.45), 6),
            metadata={
                "source": "deployment_tempo_scaffold",
                "enemy_scout_count": int(enemy_scout_count),
            },
        )
    return projections


def _unit_deployment_task(
    unit: object,
    *,
    first_turn_unknown: bool,
    passenger_transport_by_unit: dict[str, str],
    tempo_capability: DeploymentTempoCapability | None = None,
    information_state: DeploymentInformationState | None = None,
) -> UnitDeploymentTask:
    unit_id = _entity_id(unit)
    keywords = _unit_keywords(unit)
    name = _unit_name(unit)
    capability = tempo_capability or deployment_tempo_capability_for_unit(
        unit,
        first_turn_unknown=first_turn_unknown,
    )
    state = information_state or DeploymentInformationState()
    scout_lanes = _sorted_strings(list(dict(state.scout_lanes or {}).keys()) or list(DEFAULT_SCOUT_LANES))
    forward_regions = _sorted_strings(state.contested_forward_regions or list(DEFAULT_FORWARD_REGIONS))
    infiltrate_regions = _sorted_strings(list(dict(state.infiltrate_deny_zones or {}).keys()) or list(DEFAULT_FORWARD_REGIONS))
    shooting = _unit_mode_output(unit, "ranged")
    melee = _unit_mode_output(unit, "melee")
    wounds = _unit_wounds_estimate(unit)
    oc = _unit_oc_estimate(unit)
    points = _unit_point_estimate(unit)
    supports_transport_plan = bool(unit_id in passenger_transport_by_unit)
    metadata = {
        "source": "deployment_commander_scaffold",
        "shooting_output": round(float(shooting), 6),
        "melee_output": round(float(melee), 6),
        "wounds_estimate": round(float(wounds), 6),
        "objective_control_estimate": round(float(oc), 6),
        "points_estimate": round(float(points), 6),
        "has_scout": bool(capability.has_scout),
        "has_infiltrate": bool(capability.has_infiltrate),
        "deployment_tempo_early_drop_priority": round(float(capability.early_drop_priority), 6),
        "deployment_tempo_late_drop_priority": round(float(capability.late_drop_priority), 6),
        "deployment_reveal_risk": round(float(capability.reveal_risk), 6),
    }

    if _unit_is_in_reserves(unit):
        return UnitDeploymentTask(
            unit_id=unit_id,
            role=DEPLOYMENT_ROLE_RESERVE,
            preferred_regions=["reserve_pool"],
            forbidden_regions=["alpha_exposed_lane"],
            preserve_for_late_game=True,
            go_first_value=0.25,
            go_second_safety=0.85,
            tactical_flexibility=0.8,
            metadata=metadata,
        )
    if _unit_is_embarked(unit) or supports_transport_plan:
        return UnitDeploymentTask(
            unit_id=unit_id,
            role=DEPLOYMENT_ROLE_TRANSPORTED,
            preferred_regions=["inside_transport", "protected_delivery_lane"],
            forbidden_regions=["unsupported_forward_drop"],
            needs_obscuring=True,
            avoid_alpha_exposure=True,
            preserve_for_late_game=True,
            supports_transport_plan=True,
            go_first_value=0.45,
            go_second_safety=0.8,
            tactical_flexibility=0.65,
            metadata={
                **metadata,
                "transport_unit_id": str(passenger_transport_by_unit.get(unit_id, "")),
            },
        )
    if _is_transport_unit(unit):
        return UnitDeploymentTask(
            unit_id=unit_id,
            role=DEPLOYMENT_ROLE_STAGE,
            preferred_regions=["protected_delivery_lane", "obscuring_staging"],
            forbidden_regions=["isolated_forward_lane"],
            needs_obscuring=True,
            avoid_alpha_exposure=True,
            preserve_for_late_game=True,
            supports_transport_plan=True,
            go_first_value=0.55,
            go_second_safety=0.75,
            tactical_flexibility=0.6,
            metadata=metadata,
        )
    if (
        capability.has_scout
        or capability.has_infiltrate
        or keywords.intersection({"SCOUT", "SCOUTS", "INFILTRATOR", "INFILTRATORS"})
        or "screen" in name
        or "scout" in name
    ):
        preferred_regions = ["forward_screen", "reserve_denial_lane"]
        preferred_regions.extend(forward_regions if capability.has_infiltrate else [])
        preferred_regions.extend(["deployment_zone_forward_edge"] if capability.has_scout else [])
        enemy_infiltrate_blocks = any(
            bool(dict(lane or {}).get("blocked_by_enemy_infiltrate", False))
            for lane in dict(state.scout_lanes or {}).values()
        )
        sequence_priority = float(capability.early_drop_priority)
        if capability.has_infiltrate and state.enemy_scout_unit_ids_known:
            sequence_priority += 0.35
        if capability.has_scout and enemy_infiltrate_blocks:
            sequence_priority = max(0.0, sequence_priority - 0.25)
        uncertainty_risk = float(capability.reveal_risk)
        return UnitDeploymentTask(
            unit_id=unit_id,
            role=DEPLOYMENT_ROLE_SCREEN,
            preferred_regions=preferred_regions,
            forbidden_regions=["backfield_idle"],
            needs_obscuring=False,
            avoid_alpha_exposure=bool(first_turn_unknown and uncertainty_risk >= 0.25),
            preserve_for_late_game=False,
            go_first_value=0.65,
            go_second_safety=max(0.15, round(0.45 - min(0.25, uncertainty_risk), 6)),
            tactical_flexibility=0.75,
            deployment_sequence_priority=round(sequence_priority, 6),
            preferred_drop_window=DROP_WINDOW_EARLY if sequence_priority >= 1.0 else DROP_WINDOW_ANY,
            has_scout=bool(capability.has_scout),
            has_infiltrate=bool(capability.has_infiltrate),
            scout_lane_targets=scout_lanes if capability.has_scout else [],
            infiltrate_screen_regions=infiltrate_regions if capability.has_infiltrate else [],
            counter_scout_regions=forward_regions if capability.has_infiltrate else [],
            no_mans_land_pressure_regions=forward_regions if capability.has_scout or capability.has_infiltrate else [],
            metadata={
                **metadata,
                "first_turn_uncertainty_risk": round(uncertainty_risk, 6),
                "enemy_infiltrate_blocks_scout_lane": bool(enemy_infiltrate_blocks),
                "enemy_scout_pressure_known": bool(state.enemy_scout_unit_ids_known),
            },
        )
    high_value_shooter = bool(shooting >= max(6.0, melee * 1.25) or points >= 120.0)
    if first_turn_unknown and high_value_shooter:
        return UnitDeploymentTask(
            unit_id=unit_id,
            role=DEPLOYMENT_ROLE_HIDE,
            preferred_regions=["obscuring_home", "protected_fire_lane"],
            forbidden_regions=["alpha_exposed_lane"],
            needs_obscuring=True,
            avoid_alpha_exposure=True,
            preserve_for_late_game=True,
            go_first_value=0.7,
            go_second_safety=0.9,
            tactical_flexibility=0.55,
            metadata=metadata,
        )
    if melee > shooting * 1.2 and melee > 0.0:
        return UnitDeploymentTask(
            unit_id=unit_id,
            role=DEPLOYMENT_ROLE_COUNTERPUNCH,
            preferred_regions=["counterpunch_stage", "obscuring_midboard"],
            forbidden_regions=["isolated_forward_lane"],
            needs_obscuring=True,
            avoid_alpha_exposure=True,
            preserve_for_late_game=False,
            go_first_value=0.55,
            go_second_safety=0.7,
            tactical_flexibility=0.55,
            metadata=metadata,
        )
    if oc >= 5.0 or "BATTLELINE" in keywords:
        return UnitDeploymentTask(
            unit_id=unit_id,
            role=DEPLOYMENT_ROLE_SCORE,
            preferred_regions=["home_objective", "safe_objective_access"],
            forbidden_regions=["unsupported_forward_drop"],
            needs_obscuring=False,
            avoid_alpha_exposure=bool(first_turn_unknown),
            preserve_for_late_game=True,
            go_first_value=0.5,
            go_second_safety=0.7,
            tactical_flexibility=0.8,
            metadata=metadata,
        )
    return UnitDeploymentTask(
        unit_id=unit_id,
        role=DEPLOYMENT_ROLE_STAGE,
        preferred_regions=["flexible_stage", "safe_objective_access"],
        forbidden_regions=["isolated_forward_lane"],
        needs_obscuring=bool(first_turn_unknown),
        avoid_alpha_exposure=bool(first_turn_unknown),
        preserve_for_late_game=False,
        go_first_value=0.5,
        go_second_safety=0.6,
        tactical_flexibility=0.65,
        metadata=metadata,
    )


def _transport_deployment_tasks(transport_policy: dict[str, object]) -> dict[str, TransportDeploymentTask]:
    tasks: dict[str, TransportDeploymentTask] = {}
    for transport_id, doctrine in sorted(dict(transport_policy or {}).items(), key=lambda item: str(item[0])):
        passenger_ids = _sorted_strings(list(getattr(doctrine, "passenger_unit_ids", []) or []))
        tasks[str(transport_id)] = TransportDeploymentTask(
            transport_unit_id=str(transport_id),
            passenger_unit_ids=passenger_ids,
            initial_deployment_role="deliver" if passenger_ids else "screen_or_reposition",
            delivery_round=getattr(doctrine, "desired_round", None),
            delivery_region_ids=_sorted_strings(list(getattr(doctrine, "destination_region_ids", []) or [])),
            preserve_passengers=bool(getattr(doctrine, "preserve_passengers", False)),
            post_delivery_role=str(getattr(doctrine, "post_delivery_role", "") or "screen_objective"),
            metadata={
                "source": "deployment_commander_transport_doctrine",
                "general_doctrine": str(getattr(doctrine, "doctrine", "") or ""),
            },
        )
    return tasks


def _materialize_deployment_unit_orders(
    unit_tasks: dict[str, UnitDeploymentTask],
    deployment_orders: DeploymentOrderBundle,
) -> dict[str, UnitDeploymentTask]:
    materialized = dict(unit_tasks)
    for unit_id, order in dict(deployment_orders.unit_orders or {}).items():
        uid = str(unit_id)
        existing = materialized.get(uid)
        metadata = dict(getattr(existing, "metadata", {}) or {}) if existing is not None else {}
        metadata.update(dict(order.metadata or {}))
        metadata["deployment_order_bundle_id"] = str(deployment_orders.order_bundle_id)
        tempo_order = dict(deployment_orders.tempo_orders or {}).get(uid)
        materialized[uid] = UnitDeploymentTask(
            unit_id=uid,
            role=str(order.role),
            preferred_regions=_sorted_strings(order.preferred_region_ids),
            forbidden_regions=_sorted_strings(order.forbidden_region_ids),
            needs_obscuring=bool(order.needs_obscuring),
            avoid_alpha_exposure=bool(order.avoid_alpha_exposure),
            preserve_for_late_game=bool(order.preserve_for_late_game),
            supports_transport_plan=bool(order.supports_transport_plan),
            go_first_value=float(order.go_first_value),
            go_second_safety=float(order.go_second_safety),
            tactical_flexibility=float(order.tactical_flexibility),
            deployment_sequence_priority=float(order.deployment_sequence_priority),
            preferred_drop_window=str(order.preferred_drop_window),
            has_scout=bool(getattr(tempo_order, "has_scout", False)),
            has_infiltrate=bool(getattr(tempo_order, "has_infiltrate", False)),
            scout_lane_targets=_sorted_strings(getattr(tempo_order, "scout_lane_target_ids", [])),
            infiltrate_screen_regions=_sorted_strings(getattr(tempo_order, "infiltrate_screen_region_ids", [])),
            counter_scout_regions=_sorted_strings(getattr(tempo_order, "counter_scout_region_ids", [])),
            no_mans_land_pressure_regions=_sorted_strings(
                getattr(tempo_order, "no_mans_land_pressure_region_ids", [])
            ),
            metadata=metadata,
        )
    return materialized


def _materialize_deployment_tempo_orders(
    tempo_capabilities: dict[str, DeploymentTempoCapability],
    deployment_orders: DeploymentOrderBundle,
) -> dict[str, DeploymentTempoCapability]:
    materialized = dict(tempo_capabilities)
    for unit_id, order in dict(deployment_orders.tempo_orders or {}).items():
        uid = str(unit_id)
        materialized[uid] = DeploymentTempoCapability(
            unit_id=uid,
            has_infiltrate=bool(order.has_infiltrate),
            has_scout=bool(order.has_scout),
            scout_distance_inches=float(order.scout_distance_inches),
            forward_deploy_distance_class="infiltrate" if order.has_infiltrate else "deployment_zone",
            blocks_enemy_scout_lanes=bool(order.blocks_enemy_scout_lanes),
            screens_enemy_infiltrate=bool(order.screens_enemy_infiltrate),
            early_drop_priority=float(order.early_drop_priority),
            late_drop_priority=float(order.late_drop_priority),
            reveal_risk=float(order.reveal_risk),
            metadata={
                **dict(order.metadata or {}),
                "deployment_order_bundle_id": str(deployment_orders.order_bundle_id),
                "scout_lane_target_ids": _sorted_strings(order.scout_lane_target_ids),
                "counter_scout_region_ids": _sorted_strings(order.counter_scout_region_ids),
                "infiltrate_screen_region_ids": _sorted_strings(order.infiltrate_screen_region_ids),
            },
        )
    return materialized


def _materialize_scout_projection_orders(
    scout_projections: dict[str, ScoutProjection],
    deployment_orders: DeploymentOrderBundle,
) -> dict[str, ScoutProjection]:
    materialized = dict(scout_projections)
    for unit_id, order in dict(deployment_orders.scout_projection_orders or {}).items():
        uid = str(unit_id)
        materialized[uid] = ScoutProjection(
            unit_id=uid,
            deployment_region_id=str(order.deployment_region_id),
            scout_distance_inches=float(order.scout_distance_inches),
            projected_regions_after_scout=_sorted_strings(order.projected_region_ids_after_scout),
            can_reach_cover=bool(order.can_reach_cover),
            can_threaten_objective_ids=_sorted_strings(order.can_threaten_objective_ids),
            can_screen_lane_ids=_sorted_strings(order.can_screen_lane_ids),
            exposure_if_go_second=float(order.exposure_if_go_second),
            value_if_go_first=float(order.value_if_go_first),
            value_if_go_second=float(order.value_if_go_second),
            metadata={
                **dict(order.metadata or {}),
                "deployment_order_bundle_id": str(deployment_orders.order_bundle_id),
            },
        )
    return materialized


def _materialize_infiltrate_projection_orders(
    infiltrate_projections: dict[str, InfiltrateProjection],
    deployment_orders: DeploymentOrderBundle,
) -> dict[str, InfiltrateProjection]:
    materialized = dict(infiltrate_projections)
    for unit_id, order in dict(deployment_orders.infiltrate_projection_orders or {}).items():
        uid = str(unit_id)
        materialized[uid] = InfiltrateProjection(
            unit_id=uid,
            infiltrate_region_id=str(order.infiltrate_region_id),
            blocks_enemy_scout_lane_ids=_sorted_strings(order.blocks_enemy_scout_lane_ids),
            screens_objective_ids=_sorted_strings(order.screens_objective_ids),
            denies_enemy_forward_regions=_sorted_strings(order.denies_enemy_forward_region_ids),
            preserves_own_scout_lane_ids=_sorted_strings(order.preserves_own_scout_lane_ids),
            exposure_if_go_second=float(order.exposure_if_go_second),
            counter_deploy_value=float(order.counter_deploy_value),
            metadata={
                **dict(order.metadata or {}),
                "deployment_order_bundle_id": str(deployment_orders.order_bundle_id),
            },
        )
    return materialized


def _materialize_transport_orders(
    transport_tasks: dict[str, TransportDeploymentTask],
    deployment_orders: DeploymentOrderBundle,
) -> dict[str, TransportDeploymentTask]:
    materialized = dict(transport_tasks)
    for transport_id, order in dict(deployment_orders.transport_orders or {}).items():
        tid = str(transport_id)
        materialized[tid] = TransportDeploymentTask(
            transport_unit_id=tid,
            passenger_unit_ids=_sorted_strings(order.passenger_unit_ids),
            initial_deployment_role=str(order.initial_deployment_role),
            delivery_round=order.delivery_round,
            delivery_region_ids=_sorted_strings(order.delivery_region_ids),
            preserve_passengers=bool(order.preserve_passengers),
            post_delivery_role=str(order.post_delivery_role),
            metadata={
                **dict(order.metadata or {}),
                "deployment_order_bundle_id": str(deployment_orders.order_bundle_id),
                "preferred_region_ids": _sorted_strings(order.preferred_region_ids),
                "needs_obscuring": bool(order.needs_obscuring),
            },
        )
    return materialized


def _selected_mission_info(game: object) -> dict[str, Any]:
    selected = dict(getattr(game, "selected_mission_info", {}) or {})
    mission_id = str(
        selected.get("mission_id", "")
        or selected.get("mission_definition_id", "")
        or selected.get("primary", "")
        or "unknown_mission"
    )
    deployment_map_id = str(
        selected.get("deployment_map_id", "")
        or selected.get("deployment_definition_id", "")
        or selected.get("deployment", "")
        or "unknown_deployment_map"
    )
    terrain_layout_id = str(
        selected.get("terrain_layout_id", "")
        or selected.get("layout", "")
        or selected.get("terrain_layout", "")
        or "unknown_terrain_layout"
    )
    secondary_mode = str(
        selected.get("secondary_mission_mode", "")
        or getattr(game, "secondary_mission_mode", "")
        or "unknown"
    ).strip().lower()
    if secondary_mode not in {"fixed", "tactical"}:
        secondary_mode = "unknown"
    return {
        "mission_id": mission_id,
        "deployment_map_id": deployment_map_id,
        "terrain_layout_id": terrain_layout_id,
        "secondary_mode": secondary_mode,
    }


def _first_turn_unknown(game: object) -> bool:
    if bool(getattr(game, "first_turn_decided", False)):
        return False
    if str(getattr(game, "first_turn_player_id", "") or "").strip():
        return False
    if getattr(game, "first_turn_player", None) is not None:
        return False
    return True


def _information_state(
    game: object,
    player_id: str,
    own_units: list[object],
    enemy_units: list[object],
    *,
    own_tempo_capabilities: dict[str, DeploymentTempoCapability],
    enemy_tempo_capabilities: dict[str, DeploymentTempoCapability],
) -> DeploymentInformationState:
    own = _split_deployment_state(own_units)
    enemy = _split_deployment_state(enemy_units)
    terrain_features = list(getattr(getattr(game, "map", None), "terrain_features", []) or [])
    objectives = list(getattr(game, "objectives", []) or [])
    own_unplaced_ids = set(_sorted_strings(own["unplaced"]))
    return DeploymentInformationState(
        own_deployed_unit_ids=own["deployed"],
        enemy_deployed_unit_ids=enemy["deployed"],
        own_unplaced_unit_ids=own["unplaced"],
        enemy_unplaced_unit_ids=enemy["unplaced"],
        own_reserve_unit_ids=own["reserve"],
        enemy_reserve_unit_ids=enemy["reserve"],
        own_embarked_unit_ids=own["embarked"],
        enemy_embarked_unit_ids=enemy["embarked"],
        known_enemy_attachments=_known_attachments(enemy_units),
        enemy_scout_unit_ids_known=[
            unit_id
            for unit_id, capability in sorted(
                dict(enemy_tempo_capabilities or {}).items(),
                key=lambda item: str(item[0]),
            )
            if capability.has_scout
        ],
        enemy_infiltrate_unit_ids_known=[
            unit_id
            for unit_id, capability in sorted(
                dict(enemy_tempo_capabilities or {}).items(),
                key=lambda item: str(item[0]),
            )
            if capability.has_infiltrate
        ],
        own_scout_unit_ids_unplaced=[
            unit_id
            for unit_id, capability in sorted(
                dict(own_tempo_capabilities or {}).items(),
                key=lambda item: str(item[0]),
            )
            if unit_id in own_unplaced_ids and capability.has_scout
        ],
        own_infiltrate_unit_ids_unplaced=[
            unit_id
            for unit_id, capability in sorted(
                dict(own_tempo_capabilities or {}).items(),
                key=lambda item: str(item[0]),
            )
            if unit_id in own_unplaced_ids and capability.has_infiltrate
        ],
        contested_forward_regions=_contested_forward_regions(enemy_tempo_capabilities),
        scout_lanes=_scout_lanes_metadata(enemy_tempo_capabilities),
        infiltrate_deny_zones=_infiltrate_deny_zone_metadata(enemy_tempo_capabilities),
        metadata={
            "player_id": str(player_id),
            "terrain_feature_count": int(len(terrain_features)),
            "objective_count": int(len(objectives)),
            "deployment_tempo_source": "scaffold",
        },
    )


def _contingency_branches(first_turn_unknown: bool, secondary_mode: str) -> list[DeploymentContingencyBranch]:
    branches = [
        DeploymentContingencyBranch(
            branch_id="go_first",
            trigger="wins_first_turn",
            posture="stage_alpha_lanes",
            priority=0.55,
            metadata={"source": "deployment_commander_scaffold"},
        ),
        DeploymentContingencyBranch(
            branch_id="go_second",
            trigger="loses_first_turn",
            posture="hide_and_counterpunch",
            priority=0.75 if first_turn_unknown else 0.5,
            metadata={"source": "deployment_commander_scaffold"},
        ),
    ]
    if secondary_mode == "tactical":
        branches.append(
            DeploymentContingencyBranch(
                branch_id="tactical_secondary_flex",
                trigger="unknown_tactical_secondary_draw",
                posture="preserve_flexible_actions",
                priority=0.6,
                metadata={"source": "deployment_commander_scaffold"},
            )
        )
    return branches


def build_deployment_plan(
    game: object,
    player_id: str,
    *,
    general_plan: object | None = None,
    general_plan_id: str = "",
    general_transport_policy: dict[str, object] | None = None,
    deployment_orders: DeploymentOrderBundle | None = None,
) -> DeploymentPlan:
    pid = str(player_id or "")
    if not pid:
        raise ValueError("Deployment plan requires player_id.")
    player = _player_for_id(game, pid)
    if player is None:
        raise ValueError(f"Cannot build deployment plan for unknown player_id: {pid}")

    game_map = getattr(game, "map", None)
    generation = int(getattr(game_map, "state_generation", 0) or 0)
    if deployment_orders is None and general_plan is not None:
        deployment_orders = compile_general_intent_to_deployment_orders(
            game,
            general_plan,
            player_id=pid,
        )
    mission_info = _selected_mission_info(game)
    first_turn_unknown = _first_turn_unknown(game)
    own_units = _player_units(player)
    enemy_units = _opponent_units(game, pid)
    transport_policy = dict(general_transport_policy or {})
    passenger_transport_by_unit = _passenger_transport_lookup(transport_policy)
    enemy_tempo_capabilities = {
        _entity_id(unit): deployment_tempo_capability_for_unit(
            unit,
            first_turn_unknown=first_turn_unknown,
        )
        for unit in enemy_units
        if _entity_id(unit)
    }
    enemy_scout_pressure = any(
        capability.has_scout
        for capability in dict(enemy_tempo_capabilities or {}).values()
    )
    enemy_infiltrate_pressure = any(
        capability.has_infiltrate
        for capability in dict(enemy_tempo_capabilities or {}).values()
    )
    tempo_capabilities = {
        _entity_id(unit): deployment_tempo_capability_for_unit(
            unit,
            enemy_scout_pressure=enemy_scout_pressure,
            enemy_infiltrate_pressure=enemy_infiltrate_pressure,
            first_turn_unknown=first_turn_unknown,
        )
        for unit in own_units
        if _entity_id(unit)
    }
    information_state = _information_state(
        game,
        pid,
        own_units,
        enemy_units,
        own_tempo_capabilities=tempo_capabilities,
        enemy_tempo_capabilities=enemy_tempo_capabilities,
    )
    unit_tasks = {
        _entity_id(unit): _unit_deployment_task(
            unit,
            first_turn_unknown=first_turn_unknown,
            passenger_transport_by_unit=passenger_transport_by_unit,
            tempo_capability=tempo_capabilities.get(_entity_id(unit)),
            information_state=information_state,
        )
        for unit in own_units
        if _entity_id(unit)
    }
    scout_projections = _scout_projections(tempo_capabilities, information_state)
    infiltrate_projections = _infiltrate_projections(tempo_capabilities, information_state)
    transport_tasks = _transport_deployment_tasks(transport_policy)
    if deployment_orders is not None:
        unit_tasks = _materialize_deployment_unit_orders(unit_tasks, deployment_orders)
        tempo_capabilities = _materialize_deployment_tempo_orders(tempo_capabilities, deployment_orders)
        scout_projections = _materialize_scout_projection_orders(scout_projections, deployment_orders)
        infiltrate_projections = _materialize_infiltrate_projection_orders(
            infiltrate_projections,
            deployment_orders,
        )
        transport_tasks = _materialize_transport_orders(transport_tasks, deployment_orders)
    secondary_mode = str(mission_info["secondary_mode"])
    deployment_order_bundle_id = str(getattr(deployment_orders, "order_bundle_id", "") or "")
    return DeploymentPlan(
        plan_id=f"deployment:{pid}:setup",
        player_id=pid,
        created_at_generation=generation,
        mission_id=str(mission_info["mission_id"]),
        deployment_map_id=str(mission_info["deployment_map_id"]),
        terrain_layout_id=str(mission_info["terrain_layout_id"]),
        first_turn_unknown=first_turn_unknown,
        secondary_mode=secondary_mode,
        information_state=information_state,
        doctrine=DeploymentDoctrine(
            go_first_posture="stage_alpha_lanes",
            go_second_posture="hide_and_counterpunch" if first_turn_unknown else "known_turn_order",
            tactical_flexibility_weight=0.75 if secondary_mode in {"tactical", "unknown"} else 0.45,
            reserve_posture="preserve_late_scoring_and_forced_reserves",
            transport_posture="preserve_and_deliver",
            metadata={
                "source": "deployment_commander_scaffold",
                "general_plan_id": str(general_plan_id),
            },
        ),
        unit_tasks=unit_tasks,
        tempo_capabilities=tempo_capabilities,
        scout_projections=scout_projections,
        infiltrate_projections=infiltrate_projections,
        transport_tasks=transport_tasks,
        contingency_branches=_contingency_branches(first_turn_unknown, secondary_mode),
        dirty_flags=DeploymentDirtyFlags(),
        repair_count=0,
        metadata={
            "source": "deployment_commander_scaffold",
            "general_plan_id": str(general_plan_id),
            "deployment_order_bundle_id": deployment_order_bundle_id,
            "deployment_order_bundle": deployment_orders.to_dict() if deployment_orders is not None else {},
            "own_unit_count": int(len(own_units)),
            "enemy_unit_count": int(len(enemy_units)),
            "transport_task_count": int(len(transport_tasks)),
            "tempo_capability_count": int(len(tempo_capabilities)),
            "scout_projection_count": int(len(scout_projections)),
            "infiltrate_projection_count": int(len(infiltrate_projections)),
            "performance_guardrails": {
                "plan_build_budget_ms": int(DEPLOYMENT_PLAN_BUILD_BUDGET_MS),
                "repair_budget_ms": int(DEPLOYMENT_REPAIR_BUDGET_MS),
                "context_payload_warning_bytes": int(ORCHESTRATION_CONTEXT_PAYLOAD_WARNING_BYTES),
                "unit_task_count": int(len(unit_tasks)),
                "transport_task_count": int(len(transport_tasks)),
                "tempo_capability_count": int(len(tempo_capabilities)),
            },
        },
    )


def consume_deployment_dirty_flags(flags: DeploymentDirtyFlags, consumed_scope: str) -> DeploymentDirtyFlags:
    scope = str(consumed_scope or DEPLOYMENT_REPLAN_SCOPE_NONE)
    if scope == DEPLOYMENT_REPLAN_SCOPE_NONE:
        return flags
    if scope == DEPLOYMENT_REPLAN_SCOPE_FULL_DEPLOYMENT:
        return DeploymentDirtyFlags()
    return DeploymentDirtyFlags(
        remaining_drops_dirty=(
            bool(flags.remaining_drops_dirty)
            and scope != DEPLOYMENT_REPLAN_SCOPE_REMAINING_DROPS
        ),
        enemy_information_dirty=(
            bool(flags.enemy_information_dirty)
            and scope != DEPLOYMENT_REPLAN_SCOPE_REMAINING_DROPS
        ),
        transport_plan_dirty=(
            bool(flags.transport_plan_dirty)
            and scope != DEPLOYMENT_REPLAN_SCOPE_TRANSPORT_ONLY
        ),
        reserve_plan_dirty=(
            bool(flags.reserve_plan_dirty)
            and scope != DEPLOYMENT_REPLAN_SCOPE_RESERVES_ONLY
        ),
        full_replan_required=bool(flags.full_replan_required),
        reasons=[] if scope != DEPLOYMENT_REPLAN_SCOPE_NONE else _sorted_strings(flags.reasons),
        max_severity=0.0 if scope != DEPLOYMENT_REPLAN_SCOPE_NONE else float(flags.max_severity),
    )


def repair_deployment_plan(existing_plan: DeploymentPlan, fresh_plan: DeploymentPlan, scope: str) -> DeploymentPlan:
    repair_scope = str(scope or DEPLOYMENT_REPLAN_SCOPE_NONE)
    if repair_scope == DEPLOYMENT_REPLAN_SCOPE_NONE:
        return existing_plan
    metadata = _sorted_metadata(fresh_plan.metadata)
    metadata["last_repair_scope"] = repair_scope
    metadata["last_repair_count"] = int(existing_plan.repair_count + 1)
    return replace(
        fresh_plan,
        plan_id=existing_plan.plan_id,
        dirty_flags=DeploymentDirtyFlags(),
        repair_count=int(existing_plan.repair_count + 1),
        metadata=metadata,
    )
