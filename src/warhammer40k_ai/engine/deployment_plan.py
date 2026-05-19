from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

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


def _unit_deployment_task(
    unit: object,
    *,
    first_turn_unknown: bool,
    passenger_transport_by_unit: dict[str, str],
) -> UnitDeploymentTask:
    unit_id = _entity_id(unit)
    keywords = _unit_keywords(unit)
    name = _unit_name(unit)
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
    if keywords.intersection({"SCOUT", "SCOUTS", "INFILTRATOR", "INFILTRATORS"}) or "screen" in name or "scout" in name:
        return UnitDeploymentTask(
            unit_id=unit_id,
            role=DEPLOYMENT_ROLE_SCREEN,
            preferred_regions=["forward_screen", "reserve_denial_lane"],
            forbidden_regions=["backfield_idle"],
            needs_obscuring=False,
            avoid_alpha_exposure=False,
            preserve_for_late_game=False,
            go_first_value=0.65,
            go_second_safety=0.45,
            tactical_flexibility=0.75,
            metadata=metadata,
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


def _information_state(game: object, player_id: str, own_units: list[object], enemy_units: list[object]) -> DeploymentInformationState:
    own = _split_deployment_state(own_units)
    enemy = _split_deployment_state(enemy_units)
    terrain_features = list(getattr(getattr(game, "map", None), "terrain_features", []) or [])
    objectives = list(getattr(game, "objectives", []) or [])
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
        metadata={
            "player_id": str(player_id),
            "terrain_feature_count": int(len(terrain_features)),
            "objective_count": int(len(objectives)),
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
    general_plan_id: str = "",
    general_transport_policy: dict[str, object] | None = None,
) -> DeploymentPlan:
    pid = str(player_id or "")
    if not pid:
        raise ValueError("Deployment plan requires player_id.")
    player = _player_for_id(game, pid)
    if player is None:
        raise ValueError(f"Cannot build deployment plan for unknown player_id: {pid}")

    game_map = getattr(game, "map", None)
    generation = int(getattr(game_map, "state_generation", 0) or 0)
    mission_info = _selected_mission_info(game)
    first_turn_unknown = _first_turn_unknown(game)
    own_units = _player_units(player)
    enemy_units = _opponent_units(game, pid)
    transport_policy = dict(general_transport_policy or {})
    passenger_transport_by_unit = _passenger_transport_lookup(transport_policy)
    unit_tasks = {
        _entity_id(unit): _unit_deployment_task(
            unit,
            first_turn_unknown=first_turn_unknown,
            passenger_transport_by_unit=passenger_transport_by_unit,
        )
        for unit in own_units
        if _entity_id(unit)
    }
    transport_tasks = _transport_deployment_tasks(transport_policy)
    secondary_mode = str(mission_info["secondary_mode"])
    return DeploymentPlan(
        plan_id=f"deployment:{pid}:setup",
        player_id=pid,
        created_at_generation=generation,
        mission_id=str(mission_info["mission_id"]),
        deployment_map_id=str(mission_info["deployment_map_id"]),
        terrain_layout_id=str(mission_info["terrain_layout_id"]),
        first_turn_unknown=first_turn_unknown,
        secondary_mode=secondary_mode,
        information_state=_information_state(game, pid, own_units, enemy_units),
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
        transport_tasks=transport_tasks,
        contingency_branches=_contingency_branches(first_turn_unknown, secondary_mode),
        dirty_flags=DeploymentDirtyFlags(),
        repair_count=0,
        metadata={
            "source": "deployment_commander_scaffold",
            "general_plan_id": str(general_plan_id),
            "own_unit_count": int(len(own_units)),
            "enemy_unit_count": int(len(enemy_units)),
            "transport_task_count": int(len(transport_tasks)),
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
