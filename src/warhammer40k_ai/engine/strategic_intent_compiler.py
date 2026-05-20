from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from ..utility.entity_ids import get_entity_id


POSTURE_STAGE = "stage"
POSTURE_PUSH = "push"
POSTURE_PRESERVE = "preserve"

POSTURE_BUDGETS: dict[str, dict[str, float | str]] = {
    POSTURE_STAGE: {
        "aggression_budget": 0.25,
        "exposure_budget": 0.25,
        "trade_budget": 0.20,
        "resource_budget": 0.20,
        "primary_phase_focus": "movement",
    },
    POSTURE_PUSH: {
        "aggression_budget": 0.75,
        "exposure_budget": 0.55,
        "trade_budget": 0.70,
        "resource_budget": 0.70,
        "primary_phase_focus": "shooting",
    },
    POSTURE_PRESERVE: {
        "aggression_budget": 0.20,
        "exposure_budget": 0.15,
        "trade_budget": 0.10,
        "resource_budget": 0.10,
        "primary_phase_focus": "score",
    },
}

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
DEFAULT_COVER_REGIONS = (
    "left_forward_cover",
    "center_forward_cover",
    "right_forward_cover",
)


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


def _sorted_metadata_list(values: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None) -> list[dict[str, Any]]:
    return [
        _sorted_metadata(dict(value))
        for value in sorted(
            [dict(item) for item in list(values or []) if isinstance(item, dict)],
            key=lambda item: (
                str(item.get("target_unit_id", "")),
                str(item.get("trigger_kind", "")),
                str(item.get("resource_kind", "")),
                str(item.get("id", "")),
            ),
        )
    ]


def _entity_id(entity: object) -> str:
    return str(get_entity_id(entity) or getattr(entity, "id", "") or getattr(entity, "_id", "") or "")


def _to_dict(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return dict(to_dict())
    return {}


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


def _clamp(value: object, minimum: float = 0.0, maximum: float = 1.0) -> float:
    numeric = _floatish(value, minimum)
    return max(float(minimum), min(float(maximum), numeric))


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
        [unit for unit in list(getattr(army, "units", []) or []) if unit is not None],
        key=lambda unit: _entity_id(unit),
    )


def _opponent_units(game: object, player_id: str) -> list[object]:
    units: list[object] = []
    for player in list(getattr(game, "players", []) or []):
        if str(getattr(player, "id", "") or "") == str(player_id or ""):
            continue
        units.extend(_player_units(player))
    return sorted([unit for unit in units if unit is not None], key=lambda unit: _entity_id(unit))


def _unit_keywords(unit: object) -> set[str]:
    keywords: list[object] = []
    keywords.extend(list(getattr(unit, "keywords", []) or []))
    keywords.extend(list(getattr(unit, "faction_keywords", []) or []))
    for model in list(getattr(unit, "models", []) or []):
        keywords.extend(list(getattr(model, "keywords", []) or []))
        keywords.extend(list(getattr(model, "faction_keywords", []) or []))
    return {str(keyword).strip().upper() for keyword in keywords if str(keyword).strip()}


def _unit_text_blob(unit: object) -> str:
    parts: list[str] = [
        str(getattr(unit, "name", "") or ""),
        str(getattr(unit, "id", "") or getattr(unit, "_id", "") or ""),
    ]
    parts.extend(str(keyword) for keyword in _unit_keywords(unit))
    for attr_name in ("abilities", "special_rules", "metadata"):
        value = getattr(unit, attr_name, None)
        if isinstance(value, dict):
            parts.extend(str(key) for key in value.keys())
            parts.extend(str(item) for item in value.values())
        elif isinstance(value, (list, tuple, set)):
            parts.extend(str(item) for item in value)
        elif value is not None:
            parts.append(str(value))
    for model in list(getattr(unit, "models", []) or []):
        parts.append(str(getattr(model, "name", "") or ""))
        for wargear in list(getattr(model, "wargear", []) or []):
            parts.append(str(getattr(wargear, "name", "") or getattr(wargear, "id", "") or ""))
    return " ".join(parts).lower()


def _is_deployed(unit: object) -> bool:
    return bool(getattr(unit, "deployed", True))


def _reserve_status(unit: object) -> str:
    return str(getattr(unit, "reserve_status", "") or "").strip().lower()


def _is_reserve(unit: object) -> bool:
    status = _reserve_status(unit)
    return status in {"reserve", "reserves", "strategic_reserve", "strategic reserves", "deep_strike"}


def _is_embarked(unit: object) -> bool:
    return getattr(unit, "embarked_in", None) is not None or _reserve_status(unit) == "embarked"


def _is_transport_unit(unit: object) -> bool:
    keywords = _unit_keywords(unit)
    capacity = _floatish(getattr(unit, "transport_capacity", 0), 0.0)
    return bool(getattr(unit, "is_transport", False)) or "TRANSPORT" in keywords or capacity > 0.0


def _has_infiltrate(unit: object) -> bool:
    if bool(getattr(unit, "infiltrate", False)):
        return True
    keywords = _unit_keywords(unit)
    if "INFILTRATORS" in keywords or "INFILTRATE" in keywords:
        return True
    return "infiltrat" in _unit_text_blob(unit)


def _scout_distance(unit: object) -> float:
    for attr_name in ("scout_distance_inches", "scout_distance"):
        value = getattr(unit, attr_name, None)
        distance = _floatish(value, 0.0)
        if distance > 0.0:
            return distance
    text = _unit_text_blob(unit)
    if "scouts" in text or "scout" in text:
        return 6.0
    return 0.0


def _has_scout(unit: object) -> bool:
    return _scout_distance(unit) > 0.0


def _wounds(unit: object) -> float:
    total = 0.0
    models = list(getattr(unit, "models", []) or [])
    if models:
        for model in models:
            total += max(0.0, _floatish(getattr(model, "wounds", 1), 1.0))
    else:
        total = _floatish(dict(getattr(unit, "__dict__", {}) or {}).get("wounds", 1), 1.0)
    return max(1.0, total)


def _objective_control(unit: object) -> float:
    total = 0.0
    models = list(getattr(unit, "models", []) or [])
    if models:
        for model in models:
            total += max(0.0, _floatish(getattr(model, "objective_control", 1), 1.0))
    else:
        total = _floatish(dict(getattr(unit, "__dict__", {}) or {}).get("objective_control", 1), 1.0)
    return max(0.0, total)


def _profile_value(profile: object) -> float:
    attacks = _floatish(getattr(profile, "attacks", 1), 1.0)
    strength = _floatish(getattr(profile, "strength", 4), 4.0)
    ap = abs(_floatish(getattr(profile, "ap", 0), 0.0))
    damage = _floatish(getattr(profile, "damage", 1), 1.0)
    return max(0.0, attacks) * max(0.0, damage) * (1.0 + max(0.0, strength - 4.0) / 12.0 + ap / 6.0)


def _unit_weapon_value(unit: object, *, ranged: bool) -> float:
    total = 0.0
    wargear_items: list[object] = []
    wargear_items.extend(list(getattr(unit, "wargear", []) or []))
    for model in list(getattr(unit, "models", []) or []):
        wargear_items.extend(list(getattr(model, "wargear", []) or []))
    for wargear in wargear_items:
        is_ranged = getattr(wargear, "is_ranged", None)
        is_melee = getattr(wargear, "is_melee", None)
        if ranged and callable(is_ranged) and not bool(is_ranged()):
            continue
        if not ranged and callable(is_melee) and not bool(is_melee()):
            continue
        if not callable(is_ranged) and not callable(is_melee):
            wtype = str(getattr(wargear, "type", "") or "").strip().lower()
            if ranged and wtype != "ranged":
                continue
            if not ranged and wtype != "melee":
                continue
        for profile in dict(getattr(wargear, "profiles", {}) or {}).values():
            total += _profile_value(profile)
    return float(total)


def _selected_mission_info(game: object) -> dict[str, str]:
    selected = dict(getattr(game, "selected_mission_info", {}) or {})
    secondary_mode = str(
        selected.get("secondary_mission_mode")
        or getattr(game, "secondary_mission_mode", "")
        or "unknown"
    ).strip().lower()
    if secondary_mode not in {"fixed", "tactical"}:
        secondary_mode = "unknown"
    return {
        "mission_id": str(selected.get("mission_id") or selected.get("primary_mission_id") or "unknown"),
        "deployment_map_id": str(selected.get("deployment_definition_id") or selected.get("deployment_map_id") or "unknown"),
        "terrain_layout_id": str(selected.get("layout") or selected.get("terrain_layout_id") or "unknown"),
        "secondary_mode": secondary_mode,
    }


def _first_turn_unknown(game: object) -> bool:
    for attr_name in ("first_turn_player", "first_player", "goes_first_player_id"):
        if getattr(game, attr_name, None):
            return False
    return True


def _map_generation(game: object) -> int:
    game_map = getattr(game, "map", None)
    return int(getattr(game_map, "state_generation", 0) or 0)


def _objective_ids(game: object) -> list[str]:
    game_map = getattr(game, "map", None)
    objectives = list(getattr(game_map, "objectives", []) or [])
    ids = [_entity_id(objective) or str(getattr(objective, "id", "") or "") for objective in objectives]
    if ids:
        return _sorted_strings(ids)
    return ["objective:center"]


def _default_posture_for_round(battle_round: int) -> str:
    if int(battle_round) <= 1:
        return POSTURE_STAGE
    if int(battle_round) <= 3:
        return POSTURE_PUSH
    return POSTURE_PRESERVE


def _round_directive(general_plan: object, battle_round: int):
    directives = dict(getattr(general_plan, "battle_round_directives", {}) or {})
    return directives.get(int(battle_round)) or directives.get(str(int(battle_round)))


def _policy_value(policy: object, key: str, default: Any = None) -> Any:
    if isinstance(policy, dict):
        return policy.get(key, default)
    return getattr(policy, key, default)


@dataclass(frozen=True)
class RoundCommanderDirective:
    directive_id: str
    player_id: str
    battle_round: int
    posture: str
    aggression_budget: float
    exposure_budget: float
    trade_budget: float
    resource_budget: float
    cp_reserve_target: float
    preserve_unit_ids: list[str] = field(default_factory=list)
    primary_phase_focus: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "directive_id": str(self.directive_id),
            "player_id": str(self.player_id),
            "battle_round": int(self.battle_round),
            "posture": str(self.posture),
            "aggression_budget": float(self.aggression_budget),
            "exposure_budget": float(self.exposure_budget),
            "trade_budget": float(self.trade_budget),
            "resource_budget": float(self.resource_budget),
            "cp_reserve_target": float(self.cp_reserve_target),
            "preserve_unit_ids": _sorted_strings(self.preserve_unit_ids),
            "primary_phase_focus": str(self.primary_phase_focus),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class DeploymentDoctrineOrder:
    first_turn_unknown: bool = True
    secondary_mode: str = "unknown"
    go_first_posture: str = "stage"
    go_second_posture: str = "hide_counterpunch"
    tactical_flexibility_weight: float = 0.5
    fixed_secondary_specificity_weight: float = 0.5
    alpha_exposure_risk_weight: float = 1.0
    preserve_high_value_units: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "first_turn_unknown": bool(self.first_turn_unknown),
            "secondary_mode": str(self.secondary_mode),
            "go_first_posture": str(self.go_first_posture),
            "go_second_posture": str(self.go_second_posture),
            "tactical_flexibility_weight": float(self.tactical_flexibility_weight),
            "fixed_secondary_specificity_weight": float(self.fixed_secondary_specificity_weight),
            "alpha_exposure_risk_weight": float(self.alpha_exposure_risk_weight),
            "preserve_high_value_units": bool(self.preserve_high_value_units),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class DeploymentInformationOrder:
    own_deployed_unit_ids: list[str] = field(default_factory=list)
    enemy_deployed_unit_ids: list[str] = field(default_factory=list)
    own_unplaced_unit_ids: list[str] = field(default_factory=list)
    enemy_unplaced_unit_ids: list[str] = field(default_factory=list)
    own_reserve_unit_ids: list[str] = field(default_factory=list)
    enemy_reserve_unit_ids: list[str] = field(default_factory=list)
    own_embarked_unit_ids: list[str] = field(default_factory=list)
    enemy_embarked_unit_ids: list[str] = field(default_factory=list)
    known_enemy_attachment_unit_ids: list[str] = field(default_factory=list)
    known_enemy_transport_unit_ids: list[str] = field(default_factory=list)
    enemy_scout_unit_ids_known: list[str] = field(default_factory=list)
    enemy_infiltrate_unit_ids_known: list[str] = field(default_factory=list)
    own_scout_unit_ids_unplaced: list[str] = field(default_factory=list)
    own_infiltrate_unit_ids_unplaced: list[str] = field(default_factory=list)
    contested_forward_region_ids: list[str] = field(default_factory=list)
    blocked_scout_lane_ids: list[str] = field(default_factory=list)
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
            "known_enemy_attachment_unit_ids": _sorted_strings(self.known_enemy_attachment_unit_ids),
            "known_enemy_transport_unit_ids": _sorted_strings(self.known_enemy_transport_unit_ids),
            "enemy_scout_unit_ids_known": _sorted_strings(self.enemy_scout_unit_ids_known),
            "enemy_infiltrate_unit_ids_known": _sorted_strings(self.enemy_infiltrate_unit_ids_known),
            "own_scout_unit_ids_unplaced": _sorted_strings(self.own_scout_unit_ids_unplaced),
            "own_infiltrate_unit_ids_unplaced": _sorted_strings(self.own_infiltrate_unit_ids_unplaced),
            "contested_forward_region_ids": _sorted_strings(self.contested_forward_region_ids),
            "blocked_scout_lane_ids": _sorted_strings(self.blocked_scout_lane_ids),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class DeploymentUnitOrder:
    unit_id: str
    role: str
    preferred_region_ids: list[str] = field(default_factory=list)
    forbidden_region_ids: list[str] = field(default_factory=list)
    needs_obscuring: bool = False
    avoid_alpha_exposure: bool = True
    preserve_for_late_game: bool = False
    supports_transport_plan: bool = False
    go_first_value: float = 0.0
    go_second_safety: float = 0.0
    tactical_flexibility: float = 0.0
    deployment_sequence_priority: float = 0.0
    preferred_drop_window: str = "any"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": str(self.unit_id),
            "role": str(self.role),
            "preferred_region_ids": _sorted_strings(self.preferred_region_ids),
            "forbidden_region_ids": _sorted_strings(self.forbidden_region_ids),
            "needs_obscuring": bool(self.needs_obscuring),
            "avoid_alpha_exposure": bool(self.avoid_alpha_exposure),
            "preserve_for_late_game": bool(self.preserve_for_late_game),
            "supports_transport_plan": bool(self.supports_transport_plan),
            "go_first_value": float(self.go_first_value),
            "go_second_safety": float(self.go_second_safety),
            "tactical_flexibility": float(self.tactical_flexibility),
            "deployment_sequence_priority": float(self.deployment_sequence_priority),
            "preferred_drop_window": str(self.preferred_drop_window),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class DeploymentTransportOrder:
    transport_unit_id: str
    passenger_unit_ids: list[str] = field(default_factory=list)
    initial_deployment_role: str = "hidden_delivery"
    delivery_round: int | None = None
    delivery_region_ids: list[str] = field(default_factory=list)
    preserve_passengers: bool = True
    post_delivery_role: str = "screen_objective"
    preferred_region_ids: list[str] = field(default_factory=list)
    needs_obscuring: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "transport_unit_id": str(self.transport_unit_id),
            "passenger_unit_ids": _sorted_strings(self.passenger_unit_ids),
            "initial_deployment_role": str(self.initial_deployment_role),
            "delivery_region_ids": _sorted_strings(self.delivery_region_ids),
            "preserve_passengers": bool(self.preserve_passengers),
            "post_delivery_role": str(self.post_delivery_role),
            "preferred_region_ids": _sorted_strings(self.preferred_region_ids),
            "needs_obscuring": bool(self.needs_obscuring),
            "metadata": _sorted_metadata(self.metadata),
        }
        if self.delivery_round is not None:
            data["delivery_round"] = int(self.delivery_round)
        return data


@dataclass(frozen=True)
class DeploymentSequenceOrder:
    unit_id: str
    preferred_drop_window: str = "any"
    sequence_priority: float = 0.0
    reveal_risk: float = 0.0
    counter_deploy_value: float = 0.0
    reason_codes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": str(self.unit_id),
            "preferred_drop_window": str(self.preferred_drop_window),
            "sequence_priority": float(self.sequence_priority),
            "reveal_risk": float(self.reveal_risk),
            "counter_deploy_value": float(self.counter_deploy_value),
            "reason_codes": _sorted_strings(self.reason_codes),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class DeploymentContingencyOrder:
    branch_id: str
    trigger: str
    posture: str
    priority: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch_id": str(self.branch_id),
            "trigger": str(self.trigger),
            "posture": str(self.posture),
            "priority": float(self.priority),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class DeploymentTempoOrder:
    unit_id: str
    has_scout: bool = False
    scout_distance_inches: float = 0.0
    has_infiltrate: bool = False
    early_drop_priority: float = 0.0
    late_drop_priority: float = 0.0
    reveal_risk: float = 0.0
    scout_lane_target_ids: list[str] = field(default_factory=list)
    no_mans_land_pressure_region_ids: list[str] = field(default_factory=list)
    counter_scout_region_ids: list[str] = field(default_factory=list)
    infiltrate_screen_region_ids: list[str] = field(default_factory=list)
    enemy_forward_deny_region_ids: list[str] = field(default_factory=list)
    blocks_enemy_scout_lanes: bool = False
    screens_enemy_infiltrate: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": str(self.unit_id),
            "has_scout": bool(self.has_scout),
            "scout_distance_inches": float(self.scout_distance_inches),
            "has_infiltrate": bool(self.has_infiltrate),
            "early_drop_priority": float(self.early_drop_priority),
            "late_drop_priority": float(self.late_drop_priority),
            "reveal_risk": float(self.reveal_risk),
            "scout_lane_target_ids": _ordered_unique_strings(self.scout_lane_target_ids),
            "no_mans_land_pressure_region_ids": _ordered_unique_strings(self.no_mans_land_pressure_region_ids),
            "counter_scout_region_ids": _ordered_unique_strings(self.counter_scout_region_ids),
            "infiltrate_screen_region_ids": _ordered_unique_strings(self.infiltrate_screen_region_ids),
            "enemy_forward_deny_region_ids": _ordered_unique_strings(self.enemy_forward_deny_region_ids),
            "blocks_enemy_scout_lanes": bool(self.blocks_enemy_scout_lanes),
            "screens_enemy_infiltrate": bool(self.screens_enemy_infiltrate),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class ScoutProjectionOrder:
    unit_id: str
    deployment_region_id: str
    scout_distance_inches: float
    projected_region_ids_after_scout: list[str] = field(default_factory=list)
    can_reach_cover: bool = False
    can_threaten_objective_ids: list[str] = field(default_factory=list)
    can_screen_lane_ids: list[str] = field(default_factory=list)
    value_if_go_first: float = 0.0
    value_if_go_second: float = 0.0
    exposure_if_go_second: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": str(self.unit_id),
            "deployment_region_id": str(self.deployment_region_id),
            "scout_distance_inches": float(self.scout_distance_inches),
            "projected_region_ids_after_scout": _ordered_unique_strings(self.projected_region_ids_after_scout),
            "can_reach_cover": bool(self.can_reach_cover),
            "can_threaten_objective_ids": _sorted_strings(self.can_threaten_objective_ids),
            "can_screen_lane_ids": _ordered_unique_strings(self.can_screen_lane_ids),
            "value_if_go_first": float(self.value_if_go_first),
            "value_if_go_second": float(self.value_if_go_second),
            "exposure_if_go_second": float(self.exposure_if_go_second),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class InfiltrateProjectionOrder:
    unit_id: str
    infiltrate_region_id: str
    blocks_enemy_scout_lane_ids: list[str] = field(default_factory=list)
    screens_objective_ids: list[str] = field(default_factory=list)
    denies_enemy_forward_region_ids: list[str] = field(default_factory=list)
    preserves_own_scout_lane_ids: list[str] = field(default_factory=list)
    counter_deploy_value: float = 0.0
    exposure_if_go_second: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": str(self.unit_id),
            "infiltrate_region_id": str(self.infiltrate_region_id),
            "blocks_enemy_scout_lane_ids": _ordered_unique_strings(self.blocks_enemy_scout_lane_ids),
            "screens_objective_ids": _sorted_strings(self.screens_objective_ids),
            "denies_enemy_forward_region_ids": _ordered_unique_strings(self.denies_enemy_forward_region_ids),
            "preserves_own_scout_lane_ids": _ordered_unique_strings(self.preserves_own_scout_lane_ids),
            "counter_deploy_value": float(self.counter_deploy_value),
            "exposure_if_go_second": float(self.exposure_if_go_second),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class DeploymentOrderBundle:
    order_bundle_id: str
    player_id: str
    general_plan_id: str
    deployment_plan_id: str | None = None
    doctrine: DeploymentDoctrineOrder = field(default_factory=DeploymentDoctrineOrder)
    information_state: DeploymentInformationOrder = field(default_factory=DeploymentInformationOrder)
    unit_orders: dict[str, DeploymentUnitOrder] = field(default_factory=dict)
    transport_orders: dict[str, DeploymentTransportOrder] = field(default_factory=dict)
    sequence_orders: dict[str, DeploymentSequenceOrder] = field(default_factory=dict)
    tempo_orders: dict[str, DeploymentTempoOrder] = field(default_factory=dict)
    scout_projection_orders: dict[str, ScoutProjectionOrder] = field(default_factory=dict)
    infiltrate_projection_orders: dict[str, InfiltrateProjectionOrder] = field(default_factory=dict)
    contingency_branches: list[DeploymentContingencyOrder] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "order_bundle_id": str(self.order_bundle_id),
            "player_id": str(self.player_id),
            "general_plan_id": str(self.general_plan_id),
            "doctrine": self.doctrine.to_dict(),
            "information_state": self.information_state.to_dict(),
            "unit_orders": {
                str(unit_id): order.to_dict()
                for unit_id, order in sorted(self.unit_orders.items(), key=lambda item: str(item[0]))
            },
            "transport_orders": {
                str(unit_id): order.to_dict()
                for unit_id, order in sorted(self.transport_orders.items(), key=lambda item: str(item[0]))
            },
            "sequence_orders": {
                str(unit_id): order.to_dict()
                for unit_id, order in sorted(self.sequence_orders.items(), key=lambda item: str(item[0]))
            },
            "tempo_orders": {
                str(unit_id): order.to_dict()
                for unit_id, order in sorted(self.tempo_orders.items(), key=lambda item: str(item[0]))
            },
            "scout_projection_orders": {
                str(unit_id): order.to_dict()
                for unit_id, order in sorted(self.scout_projection_orders.items(), key=lambda item: str(item[0]))
            },
            "infiltrate_projection_orders": {
                str(unit_id): order.to_dict()
                for unit_id, order in sorted(self.infiltrate_projection_orders.items(), key=lambda item: str(item[0]))
            },
            "contingency_branches": [
                branch.to_dict()
                for branch in sorted(self.contingency_branches, key=lambda item: (str(item.trigger), str(item.branch_id)))
            ],
            "metadata": _sorted_metadata(self.metadata),
        }
        if self.deployment_plan_id is not None:
            data["deployment_plan_id"] = str(self.deployment_plan_id)
        return data


@dataclass(frozen=True)
class ScoutMoveOrder:
    unit_id: str
    scout_distance_inches: float
    intent: str
    destination_region_ids: list[str] = field(default_factory=list)
    objective_threat_ids: list[str] = field(default_factory=list)
    cover_region_ids: list[str] = field(default_factory=list)
    lane_screen_ids: list[str] = field(default_factory=list)
    avoid_exposure_if_go_second: bool = True
    priority: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": str(self.unit_id),
            "scout_distance_inches": float(self.scout_distance_inches),
            "intent": str(self.intent),
            "destination_region_ids": _ordered_unique_strings(self.destination_region_ids),
            "objective_threat_ids": _sorted_strings(self.objective_threat_ids),
            "cover_region_ids": _ordered_unique_strings(self.cover_region_ids),
            "lane_screen_ids": _ordered_unique_strings(self.lane_screen_ids),
            "avoid_exposure_if_go_second": bool(self.avoid_exposure_if_go_second),
            "priority": float(self.priority),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class InfiltrateDeploymentOrder:
    unit_id: str
    intent: str
    infiltrate_region_ids: list[str] = field(default_factory=list)
    blocks_enemy_scout_lane_ids: list[str] = field(default_factory=list)
    denies_enemy_forward_region_ids: list[str] = field(default_factory=list)
    screens_objective_ids: list[str] = field(default_factory=list)
    avoid_exposure_if_go_second: bool = True
    priority: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": str(self.unit_id),
            "intent": str(self.intent),
            "infiltrate_region_ids": _ordered_unique_strings(self.infiltrate_region_ids),
            "blocks_enemy_scout_lane_ids": _ordered_unique_strings(self.blocks_enemy_scout_lane_ids),
            "denies_enemy_forward_region_ids": _ordered_unique_strings(self.denies_enemy_forward_region_ids),
            "screens_objective_ids": _sorted_strings(self.screens_objective_ids),
            "avoid_exposure_if_go_second": bool(self.avoid_exposure_if_go_second),
            "priority": float(self.priority),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class PreBattleScreenOrder:
    unit_id: str
    screen_region_ids: list[str] = field(default_factory=list)
    protects_unit_ids: list[str] = field(default_factory=list)
    denies_enemy_region_ids: list[str] = field(default_factory=list)
    priority: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": str(self.unit_id),
            "screen_region_ids": _ordered_unique_strings(self.screen_region_ids),
            "protects_unit_ids": _sorted_strings(self.protects_unit_ids),
            "denies_enemy_region_ids": _ordered_unique_strings(self.denies_enemy_region_ids),
            "priority": float(self.priority),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class PreBattleOrderBundle:
    order_bundle_id: str
    player_id: str
    general_plan_id: str
    deployment_order_bundle_id: str
    scout_orders: dict[str, ScoutMoveOrder] = field(default_factory=dict)
    infiltrate_orders: dict[str, InfiltrateDeploymentOrder] = field(default_factory=dict)
    prebattle_screen_orders: dict[str, PreBattleScreenOrder] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_bundle_id": str(self.order_bundle_id),
            "player_id": str(self.player_id),
            "general_plan_id": str(self.general_plan_id),
            "deployment_order_bundle_id": str(self.deployment_order_bundle_id),
            "scout_orders": {
                str(unit_id): order.to_dict()
                for unit_id, order in sorted(self.scout_orders.items(), key=lambda item: str(item[0]))
            },
            "infiltrate_orders": {
                str(unit_id): order.to_dict()
                for unit_id, order in sorted(self.infiltrate_orders.items(), key=lambda item: str(item[0]))
            },
            "prebattle_screen_orders": {
                str(unit_id): order.to_dict()
                for unit_id, order in sorted(self.prebattle_screen_orders.items(), key=lambda item: str(item[0]))
            },
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class CommanderConstraintSet:
    preserve_unit_ids: list[str] = field(default_factory=list)
    forbidden_resource_ids: list[str] = field(default_factory=list)
    reserved_resource_ids: list[str] = field(default_factory=list)
    conditionally_authorized_resource_ids: list[str] = field(default_factory=list)
    cp_reserve_target: float = 0.0
    max_exposure_by_unit: dict[str, float] = field(default_factory=dict)
    transport_constraints: dict[str, Any] = field(default_factory=dict)
    reserve_constraints: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "preserve_unit_ids": _sorted_strings(self.preserve_unit_ids),
            "forbidden_resource_ids": _sorted_strings(self.forbidden_resource_ids),
            "reserved_resource_ids": _sorted_strings(self.reserved_resource_ids),
            "conditionally_authorized_resource_ids": _sorted_strings(self.conditionally_authorized_resource_ids),
            "cp_reserve_target": float(self.cp_reserve_target),
            "max_exposure_by_unit": {
                str(unit_id): float(value)
                for unit_id, value in sorted(dict(self.max_exposure_by_unit or {}).items(), key=lambda item: str(item[0]))
            },
            "transport_constraints": _sorted_metadata(self.transport_constraints),
            "reserve_constraints": _sorted_metadata(self.reserve_constraints),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class TargetOrder:
    target_unit_id: str
    intent: str
    priority: float = 0.0
    desired_kill_probability: float = 0.0
    max_overkill_wounds: float = 1.5
    preferred_phase: str = "shooting"
    allowed_resource_kinds: list[str] = field(default_factory=list)
    forbidden_resource_ids: list[str] = field(default_factory=list)
    assigned_unit_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_unit_id": str(self.target_unit_id),
            "intent": str(self.intent),
            "priority": float(self.priority),
            "desired_kill_probability": float(self.desired_kill_probability),
            "max_overkill_wounds": float(self.max_overkill_wounds),
            "preferred_phase": str(self.preferred_phase),
            "allowed_resource_kinds": _sorted_strings(self.allowed_resource_kinds),
            "forbidden_resource_ids": _sorted_strings(self.forbidden_resource_ids),
            "assigned_unit_ids": _sorted_strings(self.assigned_unit_ids),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class MovementOrder:
    intent: str = "stage"
    desired_action: str = ""
    target_region_ids: list[str] = field(default_factory=list)
    required_los_to_unit_ids: list[str] = field(default_factory=list)
    desired_range_bands: list[dict[str, Any]] = field(default_factory=list)
    charge_staging_target_unit_id: str | None = None
    avoid_becoming_shooting_ineligible: bool = True
    intentionally_accept_shooting_ineligible: bool = False
    avoid_exposure: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "intent": str(self.intent),
            "desired_action": str(self.desired_action),
            "target_region_ids": _ordered_unique_strings(self.target_region_ids),
            "required_los_to_unit_ids": _sorted_strings(self.required_los_to_unit_ids),
            "desired_range_bands": _sorted_metadata_list(self.desired_range_bands),
            "avoid_becoming_shooting_ineligible": bool(self.avoid_becoming_shooting_ineligible),
            "intentionally_accept_shooting_ineligible": bool(self.intentionally_accept_shooting_ineligible),
            "avoid_exposure": bool(self.avoid_exposure),
            "metadata": _sorted_metadata(self.metadata),
        }
        if self.charge_staging_target_unit_id is not None:
            data["charge_staging_target_unit_id"] = str(self.charge_staging_target_unit_id)
        return data


@dataclass(frozen=True)
class ShootingOrder:
    intent: str = "opportunistic"
    primary_target_unit_id: str | None = None
    backup_target_unit_ids: list[str] = field(default_factory=list)
    expected_damage_by_target: dict[str, float] = field(default_factory=dict)
    requires_los: bool = False
    requires_half_range: bool = False
    requires_stationary: bool = False
    allows_split_fire: bool = True
    max_overkill_wounds: float = 1.5
    preferred_phase: str = "shooting"
    allowed_resource_kinds: list[str] = field(default_factory=list)
    resource_permissions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "intent": str(self.intent),
            "backup_target_unit_ids": _ordered_unique_strings(self.backup_target_unit_ids),
            "expected_damage_by_target": {
                str(target_id): float(value)
                for target_id, value in sorted(
                    dict(self.expected_damage_by_target or {}).items(),
                    key=lambda item: str(item[0]),
                )
            },
            "requires_los": bool(self.requires_los),
            "requires_half_range": bool(self.requires_half_range),
            "requires_stationary": bool(self.requires_stationary),
            "allows_split_fire": bool(self.allows_split_fire),
            "max_overkill_wounds": float(self.max_overkill_wounds),
            "preferred_phase": str(self.preferred_phase),
            "allowed_resource_kinds": _sorted_strings(self.allowed_resource_kinds),
            "resource_permissions": _sorted_strings(self.resource_permissions),
            "metadata": _sorted_metadata(self.metadata),
        }
        if self.primary_target_unit_id is not None:
            data["primary_target_unit_id"] = str(self.primary_target_unit_id)
        return data


@dataclass(frozen=True)
class ChargeOrder:
    intent: str = "opportunistic"
    primary_target_unit_id: str | None = None
    backup_target_unit_ids: list[str] = field(default_factory=list)
    desired_charge_probability: float = 0.0
    intentionally_skip_shooting: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "intent": str(self.intent),
            "backup_target_unit_ids": _ordered_unique_strings(self.backup_target_unit_ids),
            "desired_charge_probability": float(self.desired_charge_probability),
            "intentionally_skip_shooting": bool(self.intentionally_skip_shooting),
            "metadata": _sorted_metadata(self.metadata),
        }
        if self.primary_target_unit_id is not None:
            data["primary_target_unit_id"] = str(self.primary_target_unit_id)
        return data


@dataclass(frozen=True)
class FightOrder:
    intent: str = "opportunistic"
    primary_target_unit_id: str | None = None
    backup_target_unit_ids: list[str] = field(default_factory=list)
    activation_priority: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "intent": str(self.intent),
            "backup_target_unit_ids": _ordered_unique_strings(self.backup_target_unit_ids),
            "activation_priority": float(self.activation_priority),
            "metadata": _sorted_metadata(self.metadata),
        }
        if self.primary_target_unit_id is not None:
            data["primary_target_unit_id"] = str(self.primary_target_unit_id)
        return data


@dataclass(frozen=True)
class UnitOrder:
    unit_id: str
    role: str
    preserve: bool = False
    primary_target_unit_id: str | None = None
    backup_target_unit_ids: list[str] = field(default_factory=list)
    constraint_mode: str = "hint"
    order_strength: float = 0.5
    movement_order: MovementOrder = field(default_factory=MovementOrder)
    shooting_order: ShootingOrder = field(default_factory=ShootingOrder)
    charge_order: ChargeOrder = field(default_factory=ChargeOrder)
    fight_order: FightOrder = field(default_factory=FightOrder)
    resource_permissions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": str(self.unit_id),
            "role": str(self.role),
            "preserve": bool(self.preserve),
            "backup_target_unit_ids": _ordered_unique_strings(self.backup_target_unit_ids),
            "constraint_mode": str(self.constraint_mode),
            "order_strength": float(self.order_strength),
            "movement_order": self.movement_order.to_dict(),
            "shooting_order": self.shooting_order.to_dict(),
            "charge_order": self.charge_order.to_dict(),
            "fight_order": self.fight_order.to_dict(),
            "resource_permissions": _sorted_strings(self.resource_permissions),
            "metadata": _sorted_metadata(self.metadata),
            **({"primary_target_unit_id": str(self.primary_target_unit_id)} if self.primary_target_unit_id else {}),
        }


@dataclass(frozen=True)
class ResourceAuthorization:
    resource_id: str
    resource_kind: str
    status: str
    owner_unit_id: str | None = None
    allowed_target_unit_ids: list[str] = field(default_factory=list)
    authorization_threshold: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "resource_id": str(self.resource_id),
            "resource_kind": str(self.resource_kind),
            "status": str(self.status),
            "allowed_target_unit_ids": _sorted_strings(self.allowed_target_unit_ids),
            "authorization_threshold": float(self.authorization_threshold),
            "metadata": _sorted_metadata(self.metadata),
        }
        if self.owner_unit_id is not None:
            data["owner_unit_id"] = str(self.owner_unit_id)
        return data


@dataclass(frozen=True)
class TransportRoundOrder:
    transport_unit_id: str
    passenger_unit_ids: list[str] = field(default_factory=list)
    intent: str = "deliver"
    delivery_round: int | None = None
    delivery_region_ids: list[str] = field(default_factory=list)
    preserve_passengers: bool = True
    post_delivery_role: str = "screen_objective"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "transport_unit_id": str(self.transport_unit_id),
            "passenger_unit_ids": _sorted_strings(self.passenger_unit_ids),
            "intent": str(self.intent),
            "delivery_region_ids": _ordered_unique_strings(self.delivery_region_ids),
            "preserve_passengers": bool(self.preserve_passengers),
            "post_delivery_role": str(self.post_delivery_role),
            "metadata": _sorted_metadata(self.metadata),
        }
        if self.delivery_round is not None:
            data["delivery_round"] = int(self.delivery_round)
        return data


@dataclass(frozen=True)
class CommanderOrderBundle:
    order_bundle_id: str
    player_id: str
    battle_round: int
    general_plan_id: str
    deployment_order_bundle_id: str | None = None
    prebattle_order_bundle_id: str | None = None
    directive: RoundCommanderDirective | None = None
    constraints: CommanderConstraintSet = field(default_factory=CommanderConstraintSet)
    target_orders: dict[str, TargetOrder] = field(default_factory=dict)
    unit_orders: dict[str, UnitOrder] = field(default_factory=dict)
    resource_authorizations: dict[str, ResourceAuthorization] = field(default_factory=dict)
    transport_orders: dict[str, TransportRoundOrder] = field(default_factory=dict)
    phase_priorities: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "order_bundle_id": str(self.order_bundle_id),
            "player_id": str(self.player_id),
            "battle_round": int(self.battle_round),
            "general_plan_id": str(self.general_plan_id),
            "constraints": self.constraints.to_dict(),
            "target_orders": {
                str(target_id): order.to_dict()
                for target_id, order in sorted(self.target_orders.items(), key=lambda item: str(item[0]))
            },
            "unit_orders": {
                str(unit_id): order.to_dict()
                for unit_id, order in sorted(self.unit_orders.items(), key=lambda item: str(item[0]))
            },
            "resource_authorizations": {
                str(resource_id): order.to_dict()
                for resource_id, order in sorted(self.resource_authorizations.items(), key=lambda item: str(item[0]))
            },
            "transport_orders": {
                str(unit_id): order.to_dict()
                for unit_id, order in sorted(self.transport_orders.items(), key=lambda item: str(item[0]))
            },
            "phase_priorities": {
                str(phase): float(value)
                for phase, value in sorted(dict(self.phase_priorities or {}).items(), key=lambda item: str(item[0]))
            },
            "metadata": _sorted_metadata(self.metadata),
        }
        if self.deployment_order_bundle_id is not None:
            data["deployment_order_bundle_id"] = str(self.deployment_order_bundle_id)
        if self.prebattle_order_bundle_id is not None:
            data["prebattle_order_bundle_id"] = str(self.prebattle_order_bundle_id)
        if self.directive is not None:
            data["directive"] = self.directive.to_dict()
        return data


def compile_round_commander_directive(
    general_plan: object,
    *,
    player_id: str,
    battle_round: int,
) -> RoundCommanderDirective:
    directive = _round_directive(general_plan, battle_round)
    posture = str(getattr(directive, "posture", "") or _default_posture_for_round(battle_round)).strip().lower()
    if posture not in POSTURE_BUDGETS:
        posture = _default_posture_for_round(battle_round)
    budgets = dict(POSTURE_BUDGETS[posture])
    general_plan_id = str(getattr(general_plan, "plan_id", "") or "")
    return RoundCommanderDirective(
        directive_id=f"{general_plan_id}:round:{int(battle_round)}:directive",
        player_id=str(player_id),
        battle_round=int(battle_round),
        posture=posture,
        aggression_budget=float(budgets["aggression_budget"]),
        exposure_budget=float(budgets["exposure_budget"]),
        trade_budget=float(budgets["trade_budget"]),
        resource_budget=float(budgets["resource_budget"]),
        cp_reserve_target=_floatish(getattr(directive, "cp_reserve_target", 0.0), 0.0),
        preserve_unit_ids=_sorted_strings(list(getattr(directive, "preserve_unit_ids", []) or [])),
        primary_phase_focus=str(budgets["primary_phase_focus"]),
        metadata={
            "general_plan_id": general_plan_id,
            "source_intent_kinds": ["round_posture"],
        },
    )


def _deployment_information_order(
    game: object,
    player_id: str,
    own_units: list[object],
    enemy_units: list[object],
) -> DeploymentInformationOrder:
    enemy_infiltrate_ids = [_entity_id(unit) for unit in enemy_units if _has_infiltrate(unit)]
    enemy_scout_ids = [_entity_id(unit) for unit in enemy_units if _has_scout(unit)]
    own_scout_unplaced = [_entity_id(unit) for unit in own_units if _has_scout(unit) and not _is_deployed(unit)]
    own_infiltrate_unplaced = [_entity_id(unit) for unit in own_units if _has_infiltrate(unit) and not _is_deployed(unit)]
    blocked_lanes = list(DEFAULT_SCOUT_LANES[:1]) if enemy_infiltrate_ids else []
    contested = list(DEFAULT_FORWARD_REGIONS[:2]) if enemy_scout_ids or enemy_infiltrate_ids else []
    return DeploymentInformationOrder(
        own_deployed_unit_ids=[_entity_id(unit) for unit in own_units if _entity_id(unit) and _is_deployed(unit)],
        enemy_deployed_unit_ids=[_entity_id(unit) for unit in enemy_units if _entity_id(unit) and _is_deployed(unit)],
        own_unplaced_unit_ids=[_entity_id(unit) for unit in own_units if _entity_id(unit) and not _is_deployed(unit)],
        enemy_unplaced_unit_ids=[_entity_id(unit) for unit in enemy_units if _entity_id(unit) and not _is_deployed(unit)],
        own_reserve_unit_ids=[_entity_id(unit) for unit in own_units if _entity_id(unit) and _is_reserve(unit)],
        enemy_reserve_unit_ids=[_entity_id(unit) for unit in enemy_units if _entity_id(unit) and _is_reserve(unit)],
        own_embarked_unit_ids=[_entity_id(unit) for unit in own_units if _entity_id(unit) and _is_embarked(unit)],
        enemy_embarked_unit_ids=[_entity_id(unit) for unit in enemy_units if _entity_id(unit) and _is_embarked(unit)],
        known_enemy_attachment_unit_ids=[
            _entity_id(unit)
            for unit in enemy_units
            if _entity_id(unit) and getattr(unit, "attached_to", None) is not None
        ],
        known_enemy_transport_unit_ids=[_entity_id(unit) for unit in enemy_units if _entity_id(unit) and _is_transport_unit(unit)],
        enemy_scout_unit_ids_known=enemy_scout_ids,
        enemy_infiltrate_unit_ids_known=enemy_infiltrate_ids,
        own_scout_unit_ids_unplaced=own_scout_unplaced,
        own_infiltrate_unit_ids_unplaced=own_infiltrate_unplaced,
        contested_forward_region_ids=contested,
        blocked_scout_lane_ids=blocked_lanes,
        metadata={
            "source": "strategic_intent_compiler",
            "player_id": str(player_id),
            "mission_objective_ids": _objective_ids(game),
        },
    )


def _transport_passenger_lookup(transport_policy: dict[str, object]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for transport_id, doctrine in sorted(transport_policy.items(), key=lambda item: str(item[0])):
        passenger_ids = list(_policy_value(doctrine, "passenger_unit_ids", []) or [])
        for passenger_id in passenger_ids:
            pid = str(passenger_id or "")
            if pid:
                lookup[pid] = str(transport_id)
    return lookup


def _deployment_tempo_order(
    unit: object,
    *,
    information: DeploymentInformationOrder,
    first_turn_unknown: bool,
) -> DeploymentTempoOrder | None:
    unit_id = _entity_id(unit)
    has_scout = _has_scout(unit)
    has_infiltrate = _has_infiltrate(unit)
    if not has_scout and not has_infiltrate:
        return None
    scout_distance = _scout_distance(unit)
    blocked_lanes = set(information.blocked_scout_lane_ids)
    available_lanes = [lane for lane in DEFAULT_SCOUT_LANES if lane not in blocked_lanes]
    scout_lanes = available_lanes if has_scout else []
    early = 0.0
    if has_scout:
        early += 1.5 + 0.2 * len(scout_lanes)
        if blocked_lanes:
            early -= 0.7
    if has_infiltrate:
        early += 2.0 + 0.6 * len(information.enemy_scout_unit_ids_known)
    reveal_risk = 0.35 if first_turn_unknown and (has_scout or has_infiltrate) else 0.15
    return DeploymentTempoOrder(
        unit_id=unit_id,
        has_scout=has_scout,
        scout_distance_inches=scout_distance,
        has_infiltrate=has_infiltrate,
        early_drop_priority=max(0.0, early),
        late_drop_priority=0.2 if has_scout else 0.1,
        reveal_risk=reveal_risk,
        scout_lane_target_ids=scout_lanes,
        no_mans_land_pressure_region_ids=list(DEFAULT_FORWARD_REGIONS) if has_scout else [],
        counter_scout_region_ids=list(DEFAULT_FORWARD_REGIONS[:2]) if has_infiltrate else [],
        infiltrate_screen_region_ids=list(DEFAULT_FORWARD_REGIONS) if has_infiltrate else [],
        enemy_forward_deny_region_ids=list(DEFAULT_FORWARD_REGIONS) if has_infiltrate else [],
        blocks_enemy_scout_lanes=has_infiltrate,
        screens_enemy_infiltrate=has_infiltrate,
        metadata={
            "source": "strategic_intent_compiler",
            "enemy_scout_pressure": bool(information.enemy_scout_unit_ids_known),
            "enemy_infiltrate_pressure": bool(information.enemy_infiltrate_unit_ids_known),
            "source_intent_kinds": ["scout_tempo"] if has_scout else ["infiltrate_screen"],
        },
    )


def _deployment_unit_role(
    unit: object,
    *,
    doctrine: DeploymentDoctrineOrder,
    passenger_transport_by_unit: dict[str, str],
    tempo_order: DeploymentTempoOrder | None,
) -> str:
    unit_id = _entity_id(unit)
    if unit_id in passenger_transport_by_unit or _is_embarked(unit):
        return "transported"
    if _is_reserve(unit):
        return "reserve"
    if _is_transport_unit(unit):
        return "stage"
    if tempo_order is not None and tempo_order.has_infiltrate:
        return "screen"
    if tempo_order is not None and tempo_order.has_scout:
        return "screen"
    shooting = _unit_weapon_value(unit, ranged=True)
    melee = _unit_weapon_value(unit, ranged=False)
    if doctrine.first_turn_unknown and shooting >= max(4.0, melee * 1.5):
        return "hide"
    if melee > shooting * 1.25 and _wounds(unit) >= 3.0:
        return "counterpunch"
    if _objective_control(unit) >= 3.0:
        return "score"
    return "stage"


def _deployment_unit_order(
    unit: object,
    *,
    doctrine: DeploymentDoctrineOrder,
    information: DeploymentInformationOrder,
    passenger_transport_by_unit: dict[str, str],
    tempo_order: DeploymentTempoOrder | None,
    deployment_order_bundle_id: str,
) -> DeploymentUnitOrder:
    unit_id = _entity_id(unit)
    role = _deployment_unit_role(
        unit,
        doctrine=doctrine,
        passenger_transport_by_unit=passenger_transport_by_unit,
        tempo_order=tempo_order,
    )
    preferred_regions = ["obscuring_home"] if role == "hide" else ["midboard_stage"]
    if role == "screen":
        preferred_regions = ["forward_screen", *list(DEFAULT_FORWARD_REGIONS)]
    if role == "transported":
        preferred_regions = [f"with_transport:{passenger_transport_by_unit.get(unit_id, '')}".rstrip(":")]
    forbidden_regions = ["alpha_exposed_lane"] if role == "hide" else []
    needs_obscuring = bool(role in {"hide", "transported"} or (role == "stage" and doctrine.first_turn_unknown))
    avoid_alpha = bool(doctrine.first_turn_unknown and role != "alpha")
    preserve = bool(role in {"hide", "transported", "reserve"} and doctrine.preserve_high_value_units)
    sequence_priority = float(getattr(tempo_order, "early_drop_priority", 0.0) or 0.0)
    preferred_window = "early" if sequence_priority > 0.0 else "late" if role in {"hide", "counterpunch"} else "middle"
    return DeploymentUnitOrder(
        unit_id=unit_id,
        role=role,
        preferred_region_ids=preferred_regions,
        forbidden_region_ids=forbidden_regions,
        needs_obscuring=needs_obscuring,
        avoid_alpha_exposure=avoid_alpha,
        preserve_for_late_game=preserve,
        supports_transport_plan=unit_id in passenger_transport_by_unit or _is_transport_unit(unit),
        go_first_value=0.65 if role in {"screen", "stage", "alpha"} else 0.35,
        go_second_safety=0.75 if needs_obscuring or preserve else 0.45,
        tactical_flexibility=float(doctrine.tactical_flexibility_weight),
        deployment_sequence_priority=sequence_priority,
        preferred_drop_window=preferred_window,
        metadata={
            "source": "strategic_intent_compiler",
            "deployment_order_bundle_id": deployment_order_bundle_id,
            "source_intent_kinds": ["deployment_doctrine"],
        },
    )


def compile_general_intent_to_deployment_orders(
    game: object,
    general_plan: object,
    *,
    player_id: str,
) -> DeploymentOrderBundle:
    pid = str(player_id or "")
    player = _player_for_id(game, pid)
    if player is None:
        raise ValueError(f"Cannot compile deployment orders for unknown player_id: {pid}")
    own_units = _player_units(player)
    enemy_units = _opponent_units(game, pid)
    mission_info = _selected_mission_info(game)
    first_turn_unknown = _first_turn_unknown(game)
    secondary_mode = str(mission_info["secondary_mode"])
    general_plan_id = str(getattr(general_plan, "plan_id", "") or "")
    bundle_id = f"{general_plan_id}:deployment_orders"
    doctrine = DeploymentDoctrineOrder(
        first_turn_unknown=first_turn_unknown,
        secondary_mode=secondary_mode,
        go_first_posture="stage_alpha_lanes",
        go_second_posture="hide_counterpunch" if first_turn_unknown else "known_turn_order",
        tactical_flexibility_weight=0.75 if secondary_mode in {"tactical", "unknown"} else 0.45,
        fixed_secondary_specificity_weight=0.8 if secondary_mode == "fixed" else 0.4,
        alpha_exposure_risk_weight=1.2 if first_turn_unknown else 0.6,
        preserve_high_value_units=True,
        metadata={
            "source": "strategic_intent_compiler",
            "general_plan_id": general_plan_id,
            "mission_id": mission_info["mission_id"],
            "deployment_map_id": mission_info["deployment_map_id"],
            "terrain_layout_id": mission_info["terrain_layout_id"],
            "source_intent_kinds": ["deployment_doctrine"],
        },
    )
    information = _deployment_information_order(game, pid, own_units, enemy_units)
    transport_policy = dict(getattr(general_plan, "transport_policy", {}) or {})
    passenger_transport_by_unit = _transport_passenger_lookup(transport_policy)

    tempo_orders: dict[str, DeploymentTempoOrder] = {}
    for unit in own_units:
        tempo = _deployment_tempo_order(unit, information=information, first_turn_unknown=first_turn_unknown)
        if tempo is not None:
            tempo_orders[tempo.unit_id] = tempo

    unit_orders = {
        _entity_id(unit): _deployment_unit_order(
            unit,
            doctrine=doctrine,
            information=information,
            passenger_transport_by_unit=passenger_transport_by_unit,
            tempo_order=tempo_orders.get(_entity_id(unit)),
            deployment_order_bundle_id=bundle_id,
        )
        for unit in own_units
        if _entity_id(unit)
    }
    sequence_orders = {
        unit_id: DeploymentSequenceOrder(
            unit_id=unit_id,
            preferred_drop_window=order.preferred_drop_window,
            sequence_priority=order.deployment_sequence_priority,
            reveal_risk=float(getattr(tempo_orders.get(unit_id), "reveal_risk", 0.0) or 0.0),
            counter_deploy_value=1.0 if unit_id in tempo_orders and tempo_orders[unit_id].has_infiltrate else 0.0,
            reason_codes=["tempo_capability"] if unit_id in tempo_orders else ["doctrine_role"],
            metadata={
                "source": "strategic_intent_compiler",
                "deployment_order_bundle_id": bundle_id,
            },
        )
        for unit_id, order in unit_orders.items()
    }

    scout_projection_orders: dict[str, ScoutProjectionOrder] = {}
    infiltrate_projection_orders: dict[str, InfiltrateProjectionOrder] = {}
    objectives = _objective_ids(game)
    for unit_id, tempo in tempo_orders.items():
        if tempo.has_scout:
            lane_ids = [lane for lane in tempo.scout_lane_target_ids if lane not in information.blocked_scout_lane_ids]
            deployment_region_id = lane_ids[0] if lane_ids else "home_safe_lane"
            scout_projection_orders[unit_id] = ScoutProjectionOrder(
                unit_id=unit_id,
                deployment_region_id=deployment_region_id,
                scout_distance_inches=tempo.scout_distance_inches,
                projected_region_ids_after_scout=list(DEFAULT_COVER_REGIONS[:1]) + lane_ids[:1],
                can_reach_cover=True,
                can_threaten_objective_ids=objectives[:1],
                can_screen_lane_ids=lane_ids[:2],
                value_if_go_first=0.75 if lane_ids else 0.35,
                value_if_go_second=0.65,
                exposure_if_go_second=tempo.reveal_risk,
                metadata={
                    "source": "strategic_intent_compiler",
                    "deployment_order_bundle_id": bundle_id,
                    "source_intent_kinds": ["scout_tempo"],
                },
            )
        if tempo.has_infiltrate:
            infiltrate_projection_orders[unit_id] = InfiltrateProjectionOrder(
                unit_id=unit_id,
                infiltrate_region_id=tempo.infiltrate_screen_region_ids[0]
                if tempo.infiltrate_screen_region_ids
                else "center_forward_screen",
                blocks_enemy_scout_lane_ids=list(DEFAULT_SCOUT_LANES[:2]),
                screens_objective_ids=objectives[:1],
                denies_enemy_forward_region_ids=tempo.enemy_forward_deny_region_ids,
                preserves_own_scout_lane_ids=list(DEFAULT_SCOUT_LANES[1:]),
                counter_deploy_value=0.75 if information.enemy_scout_unit_ids_known else 0.45,
                exposure_if_go_second=tempo.reveal_risk,
                metadata={
                    "source": "strategic_intent_compiler",
                    "deployment_order_bundle_id": bundle_id,
                    "source_intent_kinds": ["infiltrate_screen"],
                },
            )

    transport_orders: dict[str, DeploymentTransportOrder] = {}
    for transport_id, doctrine_obj in sorted(transport_policy.items(), key=lambda item: str(item[0])):
        doctrine_data = _to_dict(doctrine_obj)
        passengers = _sorted_strings(doctrine_data.get("passenger_unit_ids", []))
        delivery_round = doctrine_data.get("desired_round")
        transport_orders[str(transport_id)] = DeploymentTransportOrder(
            transport_unit_id=str(transport_id),
            passenger_unit_ids=passengers,
            initial_deployment_role="deliver" if passengers else "screen",
            delivery_round=int(delivery_round) if delivery_round is not None else None,
            delivery_region_ids=_sorted_strings(doctrine_data.get("destination_region_ids", ["midboard_stage"])),
            preserve_passengers=bool(doctrine_data.get("preserve_passengers", bool(passengers))),
            post_delivery_role=str(doctrine_data.get("post_delivery_role", "screen_objective")),
            preferred_region_ids=["home_obscuring_delivery_lane"] if first_turn_unknown else ["midboard_stage"],
            needs_obscuring=bool(first_turn_unknown and passengers),
            metadata={
                "source": "strategic_intent_compiler",
                "general_plan_id": general_plan_id,
                "deployment_order_bundle_id": bundle_id,
                "source_intent_kinds": ["transport_doctrine"],
            },
        )

    branches = [
        DeploymentContingencyOrder(
            branch_id="go_second_protection",
            trigger="first_turn_lost",
            posture="hide_counterpunch",
            priority=0.8 if first_turn_unknown else 0.2,
            metadata={"source": "strategic_intent_compiler", "deployment_order_bundle_id": bundle_id},
        ),
        DeploymentContingencyOrder(
            branch_id="tactical_secondary_flex",
            trigger="unknown_tactical_secondary_draw",
            posture="preserve_flexible_actions",
            priority=0.7 if secondary_mode in {"tactical", "unknown"} else 0.3,
            metadata={"source": "strategic_intent_compiler", "deployment_order_bundle_id": bundle_id},
        ),
    ]

    return DeploymentOrderBundle(
        order_bundle_id=bundle_id,
        player_id=pid,
        general_plan_id=general_plan_id,
        deployment_plan_id=f"deployment:{pid}:setup",
        doctrine=doctrine,
        information_state=information,
        unit_orders=unit_orders,
        transport_orders=transport_orders,
        sequence_orders=sequence_orders,
        tempo_orders=tempo_orders,
        scout_projection_orders=scout_projection_orders,
        infiltrate_projection_orders=infiltrate_projection_orders,
        contingency_branches=branches,
        metadata={
            "source": "strategic_intent_compiler",
            "general_plan_id": general_plan_id,
            "compiled_at_generation": _map_generation(game),
            "source_intent_kinds": ["deployment_doctrine", "transport_doctrine", "scout_tempo", "infiltrate_screen"],
        },
    )


def compile_deployment_to_prebattle_orders(
    game: object,
    general_plan: object,
    deployment_orders: DeploymentOrderBundle,
    *,
    player_id: str,
) -> PreBattleOrderBundle:
    general_plan_id = str(getattr(general_plan, "plan_id", "") or deployment_orders.general_plan_id)
    bundle_id = f"{deployment_orders.order_bundle_id}:prebattle_orders"
    blocked_lanes = set(deployment_orders.information_state.blocked_scout_lane_ids)
    scout_orders: dict[str, ScoutMoveOrder] = {}
    for unit_id, projection in sorted(deployment_orders.scout_projection_orders.items(), key=lambda item: str(item[0])):
        lanes = [lane for lane in projection.can_screen_lane_ids if lane not in blocked_lanes]
        cover_regions = list(DEFAULT_COVER_REGIONS[:1]) if projection.can_reach_cover else []
        if projection.exposure_if_go_second >= 0.3 and projection.can_reach_cover:
            intent = "move_to_cover"
        elif projection.can_threaten_objective_ids and projection.value_if_go_first >= 0.6:
            intent = "threaten_objective"
        elif lanes:
            intent = "screen_lane"
        else:
            intent = "preserve"
        objective_value = 1.0 if projection.can_threaten_objective_ids else 0.0
        cover_value = 1.0 if projection.can_reach_cover else 0.0
        screen_value = float(len(lanes)) / max(1.0, float(len(DEFAULT_SCOUT_LANES)))
        pressure_value = 1.0 if projection.projected_region_ids_after_scout else 0.0
        block_penalty = 1.0 if blocked_lanes else 0.0
        priority = (
            1.4 * objective_value
            + 1.1 * cover_value
            + 0.8 * screen_value
            + 0.6 * pressure_value
            - 1.2 * float(projection.exposure_if_go_second)
            - 0.9 * block_penalty
        )
        scout_orders[unit_id] = ScoutMoveOrder(
            unit_id=unit_id,
            scout_distance_inches=float(projection.scout_distance_inches),
            intent=intent,
            destination_region_ids=_ordered_unique_strings(cover_regions + lanes[:1]),
            objective_threat_ids=projection.can_threaten_objective_ids,
            cover_region_ids=cover_regions,
            lane_screen_ids=lanes,
            avoid_exposure_if_go_second=True,
            priority=max(0.0, priority),
            metadata={
                "source": "strategic_intent_compiler",
                "general_plan_id": general_plan_id,
                "deployment_order_bundle_id": deployment_orders.order_bundle_id,
                "prebattle_order_bundle_id": bundle_id,
                "source_intent_kinds": ["scout_tempo"],
            },
        )

    infiltrate_orders: dict[str, InfiltrateDeploymentOrder] = {}
    screen_orders: dict[str, PreBattleScreenOrder] = {}
    enemy_scout_pressure = bool(deployment_orders.information_state.enemy_scout_unit_ids_known)
    objectives = _objective_ids(game)
    for unit_id, projection in sorted(deployment_orders.infiltrate_projection_orders.items(), key=lambda item: str(item[0])):
        if enemy_scout_pressure and projection.blocks_enemy_scout_lane_ids:
            intent = "counter_scout"
        elif projection.screens_objective_ids:
            intent = "objective_screen"
        elif projection.denies_enemy_forward_region_ids:
            intent = "deny_forward_space"
        else:
            intent = "forward_screen"
        priority = (
            1.3 * (1.0 if projection.denies_enemy_forward_region_ids else 0.0)
            + 1.2 * (1.0 if projection.blocks_enemy_scout_lane_ids else 0.0)
            + 1.0 * (1.0 if projection.screens_objective_ids else 0.0)
            + 0.8 * (1.0 if projection.preserves_own_scout_lane_ids else 0.0)
            + 0.6 * float(projection.counter_deploy_value)
            - 1.0 * float(projection.exposure_if_go_second)
        )
        infiltrate_orders[unit_id] = InfiltrateDeploymentOrder(
            unit_id=unit_id,
            intent=intent,
            infiltrate_region_ids=[projection.infiltrate_region_id],
            blocks_enemy_scout_lane_ids=projection.blocks_enemy_scout_lane_ids,
            denies_enemy_forward_region_ids=projection.denies_enemy_forward_region_ids,
            screens_objective_ids=projection.screens_objective_ids,
            avoid_exposure_if_go_second=True,
            priority=max(0.0, priority),
            metadata={
                "source": "strategic_intent_compiler",
                "general_plan_id": general_plan_id,
                "deployment_order_bundle_id": deployment_orders.order_bundle_id,
                "prebattle_order_bundle_id": bundle_id,
                "source_intent_kinds": ["infiltrate_screen"],
            },
        )
        screen_orders[unit_id] = PreBattleScreenOrder(
            unit_id=unit_id,
            screen_region_ids=[projection.infiltrate_region_id],
            protects_unit_ids=[],
            denies_enemy_region_ids=projection.denies_enemy_forward_region_ids,
            priority=max(0.0, priority),
            metadata={
                "source": "strategic_intent_compiler",
                "objective_ids": objectives[:1],
                "prebattle_order_bundle_id": bundle_id,
            },
        )

    return PreBattleOrderBundle(
        order_bundle_id=bundle_id,
        player_id=str(player_id),
        general_plan_id=general_plan_id,
        deployment_order_bundle_id=deployment_orders.order_bundle_id,
        scout_orders=scout_orders,
        infiltrate_orders=infiltrate_orders,
        prebattle_screen_orders=screen_orders,
        metadata={
            "source": "strategic_intent_compiler",
            "general_plan_id": general_plan_id,
            "deployment_order_bundle_id": deployment_orders.order_bundle_id,
            "compiled_at_generation": _map_generation(game),
            "transport_order_count": int(len(deployment_orders.transport_orders)),
            "source_intent_kinds": ["scout_tempo", "infiltrate_screen"],
        },
    )


def _target_order_intent(posture: str, priority: float) -> tuple[str, float]:
    if posture == POSTURE_PUSH and priority >= 0.55:
        return "kill", 0.8
    if posture == POSTURE_PUSH:
        return "soften", 0.65
    if posture == POSTURE_STAGE and priority >= 0.55:
        return "soften", 0.55
    if posture == POSTURE_STAGE:
        return "delay", 0.35
    if priority >= 0.75:
        return "delay", 0.25
    return "avoid_unless_safe", 0.1


def _target_preferred_phase(intent: str, directive: RoundCommanderDirective) -> str:
    if str(intent) in {"kill", "soften"}:
        return "shooting" if directive.primary_phase_focus != "charge" else "charge"
    if str(intent) == "delay":
        return "movement"
    return "score"


def _target_allowed_resource_kinds(intent: str, priority: float, directive: RoundCommanderDirective) -> list[str]:
    if str(intent) == "kill" and float(priority) >= 0.75 and float(directive.resource_budget) >= 0.5:
        return ["one_shot_weapon", "once_per_battle_ability", "stratagem"]
    if str(intent) == "soften" and float(priority) >= 0.65 and float(directive.resource_budget) >= 0.65:
        return ["stratagem"]
    return []


def _target_max_overkill_wounds(intent: str, priority: float) -> float:
    if str(intent) == "kill":
        return 1.5
    if str(intent) == "soften":
        return 1.0
    if float(priority) >= 0.75:
        return 0.75
    return 0.5


def _target_priority_doctrine(general_plan: object) -> dict[str, Any]:
    doctrine = getattr(general_plan, "target_priority_doctrine", None)
    if isinstance(doctrine, dict):
        return dict(doctrine)
    return {}


def _target_order_overrides(general_plan: object) -> dict[str, dict[str, Any]]:
    doctrine = _target_priority_doctrine(general_plan)
    raw = doctrine.get("target_orders", doctrine.get("target_overrides", {}))
    if not isinstance(raw, dict):
        return {}
    return {
        str(target_id): dict(value)
        for target_id, value in sorted(raw.items(), key=lambda item: str(item[0]))
        if isinstance(value, dict)
    }


def _unit_order_overrides(general_plan: object) -> dict[str, dict[str, Any]]:
    doctrine = _target_priority_doctrine(general_plan)
    raw = doctrine.get("unit_orders", doctrine.get("unit_order_overrides", {}))
    if not isinstance(raw, dict):
        return {}
    return {
        str(unit_id): dict(value)
        for unit_id, value in sorted(raw.items(), key=lambda item: str(item[0]))
        if isinstance(value, dict)
    }


def _analysis_target_orders(
    commander_analysis: object,
    *,
    general_plan: object,
    directive: RoundCommanderDirective,
    commander_order_bundle_id: str,
) -> dict[str, TargetOrder]:
    targets = list(getattr(commander_analysis, "target_analysis", []) or [])
    if not targets and isinstance(commander_analysis, dict):
        targets = list(commander_analysis.get("target_analysis", []) or [])
    raw_scores: dict[str, float] = {}
    for target in targets:
        target_id = str(_policy_value(target, "target_unit_id", "") or "")
        if not target_id:
            continue
        score = (
            _floatish(_policy_value(target, "threat_score", 0.0), 0.0)
            + _floatish(_policy_value(target, "scoring_value", 0.0), 0.0)
            + _floatish(_policy_value(target, "denial_value", 0.0), 0.0)
        )
        raw_scores[target_id] = score
    max_score = max(raw_scores.values()) if raw_scores else 1.0
    orders: dict[str, TargetOrder] = {}
    overrides = _target_order_overrides(general_plan)
    for target_id, score in sorted(raw_scores.items(), key=lambda item: (-float(item[1]), str(item[0]))):
        priority = float(score) / max(1.0, float(max_score))
        intent, kill_prob = _target_order_intent(directive.posture, priority)
        override = overrides.get(target_id, {})
        if override:
            intent = str(override.get("intent", intent) or intent)
            priority = _clamp(override.get("priority", priority), 0.0, 1.0)
            kill_prob = _clamp(override.get("desired_kill_probability", kill_prob), 0.0, 1.0)
        preferred_phase = str(
            override.get("preferred_phase", "")
            or _target_preferred_phase(intent, directive)
        )
        allowed_resource_kinds = _sorted_strings(
            override.get(
                "allowed_resource_kinds",
                _target_allowed_resource_kinds(intent, priority, directive),
            )
        )
        orders[target_id] = TargetOrder(
            target_unit_id=target_id,
            intent=intent,
            priority=priority,
            desired_kill_probability=kill_prob,
            max_overkill_wounds=_floatish(
                override.get("max_overkill_wounds", _target_max_overkill_wounds(intent, priority)),
                _target_max_overkill_wounds(intent, priority),
            ),
            preferred_phase=preferred_phase,
            allowed_resource_kinds=allowed_resource_kinds,
            forbidden_resource_ids=_sorted_strings(override.get("forbidden_resource_ids", [])),
            metadata={
                "source": "strategic_intent_compiler",
                "commander_order_bundle_id": commander_order_bundle_id,
                "source_directive_id": directive.directive_id,
                "source_intent_kinds": ["round_posture", "target_priority_doctrine"],
                "explicit_general_override": bool(override),
            },
        )
    return orders


def _matrix_by_unit(commander_analysis: object) -> dict[str, list[object]]:
    entries = list(getattr(commander_analysis, "unit_target_matrix", []) or [])
    if not entries and isinstance(commander_analysis, dict):
        entries = list(commander_analysis.get("unit_target_matrix", []) or [])
    by_unit: dict[str, list[object]] = {}
    for entry in entries:
        unit_id = str(_policy_value(entry, "unit_id", "") or "")
        if not unit_id:
            continue
        by_unit.setdefault(unit_id, []).append(entry)
    for unit_id, unit_entries in list(by_unit.items()):
        by_unit[unit_id] = sorted(
            unit_entries,
            key=lambda item: (
                -_floatish(_policy_value(item, "priority_score", 0.0), 0.0),
                str(_policy_value(item, "target_unit_id", "") or ""),
            ),
        )
    return by_unit


def _resource_authorizations(
    general_plan: object,
    target_orders: dict[str, TargetOrder],
    directive: RoundCommanderDirective,
) -> dict[str, ResourceAuthorization]:
    authorizations: dict[str, ResourceAuthorization] = {}
    policies = dict(getattr(general_plan, "limited_resource_policy", {}) or {})
    for resource_id, policy in sorted(policies.items(), key=lambda item: str(item[0])):
        status = str(_policy_value(policy, "status", "available") or "available")
        kind = str(_policy_value(policy, "resource_kind", "") or "")
        threshold = _floatish(_policy_value(policy, "authorization_threshold", 0.0), 0.0)
        owner = _policy_value(policy, "owner_unit_id", None)
        reserved_round = _policy_value(policy, "reserved_for_round", None)
        reserved_target = _policy_value(policy, "reserved_for_target_unit_id", None)
        allowed_targets = [
            target_id
            for target_id, order in target_orders.items()
            if float(order.priority) >= threshold and order.intent in {"kill", "soften"}
            and (not order.allowed_resource_kinds or kind in set(order.allowed_resource_kinds))
            and (reserved_target is None or str(reserved_target) == str(target_id))
        ]
        auth_status = status
        if status == "forbidden":
            allowed_targets = []
        elif status == "spent":
            allowed_targets = []
        elif status == "authorized":
            auth_status = "authorized"
        elif reserved_round is not None and int(reserved_round) > int(directive.battle_round):
            auth_status = "reserved"
            allowed_targets = []
        elif allowed_targets and float(directive.resource_budget) >= 0.5:
            auth_status = "conditionally_authorized"
        else:
            auth_status = "reserved" if status == "reserved" else status
            allowed_targets = []
        authorizations[str(resource_id)] = ResourceAuthorization(
            resource_id=str(resource_id),
            resource_kind=kind,
            status=auth_status,
            owner_unit_id=str(owner) if owner is not None else None,
            allowed_target_unit_ids=allowed_targets,
            authorization_threshold=threshold,
            metadata={
                "source": "strategic_intent_compiler",
                "source_directive_id": directive.directive_id,
                "source_intent_kinds": ["resource_policy"],
            },
        )
    return authorizations


def _directive_delays_commit(directive: RoundCommanderDirective) -> bool:
    posture = str(directive.posture or "").strip().lower()
    if posture == POSTURE_STAGE:
        return True
    return float(directive.aggression_budget) < 0.5 and float(directive.resource_budget) < 0.5


def _constraint_mode_is_hard_override(mode: str) -> bool:
    return str(mode or "").strip().lower() in {"replace", "override"}


def compile_general_intent_to_commander_orders(
    game: object,
    general_plan: object,
    deployment_orders: DeploymentOrderBundle | None,
    prebattle_orders: PreBattleOrderBundle | None,
    tier1_plan: object,
    tier2_bundle: object,
    commander_analysis: object,
    *,
    battle_round: int,
    player_id: str,
) -> CommanderOrderBundle:
    pid = str(player_id or "")
    general_plan_id = str(getattr(general_plan, "plan_id", "") or "")
    directive = compile_round_commander_directive(general_plan, player_id=pid, battle_round=int(battle_round))
    deployment_bundle_id = deployment_orders.order_bundle_id if deployment_orders is not None else None
    prebattle_bundle_id = prebattle_orders.order_bundle_id if prebattle_orders is not None else None
    bundle_id = f"{general_plan_id}:round:{int(battle_round)}:commander_orders"

    target_orders = _analysis_target_orders(
        commander_analysis,
        general_plan=general_plan,
        directive=directive,
        commander_order_bundle_id=bundle_id,
    )
    resource_authorizations = _resource_authorizations(general_plan, target_orders, directive)
    reserved_resource_ids = [
        resource_id
        for resource_id, auth in resource_authorizations.items()
        if auth.status == "reserved"
    ]
    forbidden_resource_ids = [
        resource_id
        for resource_id, auth in resource_authorizations.items()
        if auth.status == "forbidden"
    ]
    conditional_resource_ids = [
        resource_id
        for resource_id, auth in resource_authorizations.items()
        if auth.status == "conditionally_authorized"
    ]
    max_exposure_by_unit: dict[str, float] = {}
    preserve_units = set(directive.preserve_unit_ids)
    exposure_limited_units = set(preserve_units)
    if deployment_orders is not None:
        for unit_id, order in deployment_orders.unit_orders.items():
            if order.preserve_for_late_game:
                exposure_limited_units.add(unit_id)
            max_exposure_by_unit[unit_id] = 0.25 if order.preserve_for_late_game else float(directive.exposure_budget)
    if prebattle_orders is not None:
        for unit_id, scout_order in prebattle_orders.scout_orders.items():
            if scout_order.avoid_exposure_if_go_second:
                max_exposure_by_unit[unit_id] = min(max_exposure_by_unit.get(unit_id, 1.0), 0.35)

    constraints = CommanderConstraintSet(
        preserve_unit_ids=_sorted_strings(exposure_limited_units),
        forbidden_resource_ids=forbidden_resource_ids,
        reserved_resource_ids=reserved_resource_ids,
        conditionally_authorized_resource_ids=conditional_resource_ids,
        cp_reserve_target=float(directive.cp_reserve_target),
        max_exposure_by_unit=max_exposure_by_unit,
        transport_constraints={
            unit_id: order.to_dict()
            for unit_id, order in sorted(
                dict(getattr(deployment_orders, "transport_orders", {}) or {}).items(),
                key=lambda item: str(item[0]),
            )
        },
        reserve_constraints=dict(getattr(general_plan, "reserve_policy", {}) or {}),
        metadata={
            "source": "strategic_intent_compiler",
            "general_plan_id": general_plan_id,
            "deployment_order_bundle_id": str(deployment_bundle_id or ""),
            "prebattle_order_bundle_id": str(prebattle_bundle_id or ""),
            "commander_order_bundle_id": bundle_id,
            "source_intent_kinds": ["resource_policy", "transport_doctrine", "deployment_doctrine"],
        },
    )

    matrix = _matrix_by_unit(commander_analysis)
    target_order_ids = list(target_orders.keys())
    unit_orders: dict[str, UnitOrder] = {}
    tasks = dict(getattr(tier2_bundle, "tasks_by_unit_id", {}) or {})
    auth_by_owner: dict[str, list[str]] = {}
    for resource_id, auth in resource_authorizations.items():
        if auth.owner_unit_id and auth.allowed_target_unit_ids:
            auth_by_owner.setdefault(auth.owner_unit_id, []).append(resource_id)
    unit_overrides = _unit_order_overrides(general_plan)
    deployment_unit_orders = dict(getattr(deployment_orders, "unit_orders", {}) or {})
    scout_orders = dict(getattr(prebattle_orders, "scout_orders", {}) or {})
    infiltrate_orders = dict(getattr(prebattle_orders, "infiltrate_orders", {}) or {})
    for unit_id, task in sorted(tasks.items(), key=lambda item: str(item[0])):
        uid = str(unit_id)
        entries = matrix.get(uid, [])
        entries_by_target = {
            str(_policy_value(entry, "target_unit_id", "") or ""): entry
            for entry in entries
            if str(_policy_value(entry, "target_unit_id", "") or "")
        }
        override = unit_overrides.get(uid, {})
        override_shooting = dict(override.get("shooting_order", {}) or {}) if isinstance(override.get("shooting_order"), dict) else {}
        override_movement = dict(override.get("movement_order", {}) or {}) if isinstance(override.get("movement_order"), dict) else {}
        override_charge = dict(override.get("charge_order", {}) or {}) if isinstance(override.get("charge_order"), dict) else {}
        override_fight = dict(override.get("fight_order", {}) or {}) if isinstance(override.get("fight_order"), dict) else {}
        constraint_mode = str(override.get("constraint_mode", "hint") or "hint").strip().lower()
        if constraint_mode not in {"hint", "constrain", "replace", "override"}:
            constraint_mode = "hint"
        explicit_override = bool(override)
        default_target = str(_policy_value(entries[0], "target_unit_id", "") or "") if entries else ""
        override_target = str(
            override.get("primary_target_unit_id", "")
            or override_shooting.get("primary_target_unit_id", "")
            or override_charge.get("primary_target_unit_id", "")
            or override_fight.get("primary_target_unit_id", "")
            or ""
        )
        best_target = override_target or default_target
        backup_targets = _ordered_unique_strings(
            list(override.get("backup_target_unit_ids", []) or [])
            or list(override_shooting.get("backup_target_unit_ids", []) or [])
            or [
                str(_policy_value(entry, "target_unit_id", "") or "")
                for entry in entries[1:4]
                if str(_policy_value(entry, "target_unit_id", "") or "")
            ]
        )
        expected_damage_by_target = {
            str(_policy_value(entry, "target_unit_id", "") or ""): _floatish(
                _policy_value(entry, "expected_shooting_damage", 0.0),
                0.0,
            )
            for entry in entries
            if str(_policy_value(entry, "target_unit_id", "") or "")
        }
        primary_entry = entries_by_target.get(best_target)
        primary_metadata = dict(_policy_value(primary_entry, "metadata", {}) or {}) if primary_entry is not None else {}
        target_order = target_orders.get(best_target)
        preserve = uid in preserve_units or bool(override.get("preserve", False))
        deployment_order = deployment_unit_orders.get(uid)
        scout_order = scout_orders.get(uid)
        infiltrate_order = infiltrate_orders.get(uid)
        role = str(
            override.get("role", "")
            or ("preserve" if preserve else "")
            or getattr(deployment_order, "role", "")
            or getattr(task, "task_type", "")
            or "stage"
        )
        shooting_intent = str(
            override_shooting.get("intent", "")
            or override.get("shooting_intent", "")
            or ("preserve" if preserve else "planned_focus_fire" if best_target else "opportunistic")
        )
        charge_intent = str(
            override_charge.get("intent", "")
            or override.get("charge_intent", "")
            or ("hold" if preserve else "planned_charge" if best_target and role in {"counterpunch", "screen"} else "opportunistic")
        )
        fight_intent = str(
            override_fight.get("intent", "")
            or override.get("fight_intent", "")
            or ("hold" if preserve else "planned_fight" if charge_intent == "planned_charge" else "opportunistic")
        )
        movement_intent = str(
            override_movement.get("intent", "")
            or override.get("movement_intent", "")
            or ("preserve_hidden" if preserve else "score_or_screen" if scout_order else "maintain_forward_screen" if infiltrate_order else "execute_tier2_task")
        )
        delay_commit = bool(
            _directive_delays_commit(directive)
            and not preserve
            and not _constraint_mode_is_hard_override(constraint_mode)
        )
        if delay_commit:
            movement_intent = str(override_movement.get("staging_intent", "") or "stage_for_commit")
            shooting_intent = "opportunistic"
            charge_intent = "hold"
            fight_intent = "hold"
        requires_half_range = bool(
            override_shooting.get("requires_half_range", False)
            or primary_metadata.get("has_half_range_trigger", False)
            or _floatish(_policy_value(primary_entry, "movement_to_half_range_feasibility", 0.0), 0.0) >= 0.75
        )
        requires_stationary = bool(
            override_shooting.get("requires_stationary", False)
            or primary_metadata.get("has_heavy_stationary_trigger", False)
        )
        requested_range_bands = list(override_movement.get("desired_range_bands", []) or [])
        if not requested_range_bands and best_target and requires_half_range and primary_metadata.get("max_ranged_range_inches", 0.0):
            requested_range_bands = [
                {
                    "target_unit_id": best_target,
                    "trigger_kind": "compiled_half_range",
                    "minimum_inches": 0.0,
                    "maximum_inches": float(primary_metadata.get("max_ranged_range_inches", 0.0) or 0.0) / 2.0,
                    "priority": _floatish(_policy_value(primary_entry, "movement_to_half_range_feasibility", 0.0), 0.0),
                }
            ]
        desired_range_bands = _sorted_metadata_list(requested_range_bands)
        if delay_commit:
            desired_range_bands = []
        charge_target = str(override_charge.get("primary_target_unit_id", "") or "") or (
            best_target if charge_intent == "planned_charge" else ""
        )
        fight_target = str(override_fight.get("primary_target_unit_id", "") or "") or (
            best_target if fight_intent == "planned_fight" else ""
        )
        if delay_commit:
            charge_target = ""
            fight_target = ""
        allowed_resource_kinds = list(getattr(target_order, "allowed_resource_kinds", []) or [])
        if override_shooting.get("allowed_resource_kinds"):
            allowed_resource_kinds = _sorted_strings(override_shooting.get("allowed_resource_kinds", []))
        permissions = _sorted_strings(auth_by_owner.get(uid, []))
        source_intent_kinds = [
            "round_posture",
            "deployment_doctrine",
            *(["general_preserve_directive"] if uid in preserve_units else []),
            *(["explicit_general_unit_order"] if explicit_override else []),
            *(["round_posture_delay"] if delay_commit else []),
        ]
        shooting_primary_target_id = None if shooting_intent == "preserve" or delay_commit else (best_target or None)
        unit_orders[uid] = UnitOrder(
            unit_id=uid,
            role=role,
            preserve=preserve,
            primary_target_unit_id=None if delay_commit else (best_target or None),
            backup_target_unit_ids=backup_targets,
            constraint_mode=constraint_mode,
            order_strength=_clamp(override.get("order_strength", 1.0 if explicit_override else 0.5), 0.0, 1.0),
            movement_order=MovementOrder(
                intent=movement_intent,
                desired_action=str(
                    (override_movement.get("staging_desired_action", "") or "normal_move")
                    if delay_commit
                    else (override_movement.get("desired_action", "") or "")
                ),
                target_region_ids=list(getattr(deployment_order, "preferred_region_ids", []) or []),
                required_los_to_unit_ids=_sorted_strings(
                    []
                    if delay_commit
                    else override_movement.get("required_los_to_unit_ids", [best_target] if best_target and shooting_intent == "planned_focus_fire" else [])
                ),
                desired_range_bands=desired_range_bands,
                charge_staging_target_unit_id=str(override_movement.get("charge_staging_target_unit_id", "") or "")
                or (charge_target if charge_intent == "planned_charge" and not delay_commit else None),
                avoid_becoming_shooting_ineligible=bool(
                    True
                    if delay_commit
                    else override_movement.get("avoid_becoming_shooting_ineligible", shooting_intent == "planned_focus_fire")
                ),
                intentionally_accept_shooting_ineligible=bool(
                    False
                    if delay_commit
                    else override_movement.get(
                        "intentionally_accept_shooting_ineligible",
                        charge_intent == "planned_charge" and shooting_intent != "planned_focus_fire",
                    )
                ),
                avoid_exposure=bool(delay_commit or preserve or uid in max_exposure_by_unit),
                metadata={
                    "source": "strategic_intent_compiler",
                    "source_intent_kinds": source_intent_kinds,
                    "directive_commit_status": "staging" if delay_commit else "commit",
                },
            ),
            shooting_order=ShootingOrder(
                intent=shooting_intent,
                primary_target_unit_id=shooting_primary_target_id,
                backup_target_unit_ids=backup_targets,
                expected_damage_by_target=expected_damage_by_target,
                requires_los=bool(False if delay_commit else override_shooting.get("requires_los", bool(best_target and shooting_intent == "planned_focus_fire"))),
                requires_half_range=bool(False if delay_commit else requires_half_range),
                requires_stationary=bool(False if delay_commit else requires_stationary),
                allows_split_fire=bool(override_shooting.get("allows_split_fire", True)),
                max_overkill_wounds=_floatish(
                    override_shooting.get(
                        "max_overkill_wounds",
                        getattr(target_order, "max_overkill_wounds", 1.5),
                    ),
                    1.5,
                ),
                preferred_phase=str(
                    override_shooting.get("preferred_phase", "")
                    or getattr(target_order, "preferred_phase", "shooting")
                ),
                allowed_resource_kinds=allowed_resource_kinds,
                resource_permissions=permissions,
                metadata={
                    "source": "strategic_intent_compiler",
                    "source_intent_kinds": [
                        "target_priority_doctrine",
                        "resource_policy",
                        *(["explicit_general_unit_order"] if explicit_override else []),
                        *(["round_posture_delay"] if delay_commit else []),
                    ],
                    "explicit_general_override": bool(explicit_override),
                    "directive_commit_status": "staging" if delay_commit else "commit",
                },
            ),
            charge_order=ChargeOrder(
                intent=charge_intent,
                primary_target_unit_id=charge_target or None,
                backup_target_unit_ids=backup_targets,
                desired_charge_probability=_floatish(_policy_value(primary_entry, "charge_feasibility", 0.0), 0.0),
                intentionally_skip_shooting=bool(
                    override_charge.get(
                        "intentionally_skip_shooting",
                        False if delay_commit else charge_intent == "planned_charge" and shooting_intent != "planned_focus_fire",
                    )
                ),
                metadata={
                    "source": "strategic_intent_compiler",
                    "explicit_general_override": bool(explicit_override),
                    "directive_commit_status": "staging" if delay_commit else "commit",
                },
            ),
            fight_order=FightOrder(
                intent=fight_intent,
                primary_target_unit_id=fight_target or None,
                backup_target_unit_ids=backup_targets,
                activation_priority=_floatish(_policy_value(primary_entry, "expected_melee_damage", 0.0), 0.0)
                + _floatish(_policy_value(primary_entry, "charge_feasibility", 0.0), 0.0),
                metadata={
                    "source": "strategic_intent_compiler",
                    "explicit_general_override": bool(explicit_override),
                    "directive_commit_status": "staging" if delay_commit else "commit",
                },
            ),
            resource_permissions=permissions,
            metadata={
                "source": "strategic_intent_compiler",
                "general_plan_id": general_plan_id,
                "deployment_order_bundle_id": str(deployment_bundle_id or ""),
                "prebattle_order_bundle_id": str(prebattle_bundle_id or ""),
                "commander_order_bundle_id": bundle_id,
                "source_directive_id": directive.directive_id,
                "source_intent_kinds": source_intent_kinds,
                "explicit_general_override": bool(explicit_override),
                "directive_commit_status": "staging" if delay_commit else "commit",
            },
        )

    assigned_units_by_target: dict[str, list[str]] = {target_id: [] for target_id in target_orders}
    for unit_id, order in sorted(unit_orders.items(), key=lambda item: str(item[0])):
        candidate_targets = [
            str(getattr(order, "primary_target_unit_id", "") or ""),
            str(getattr(order.shooting_order, "primary_target_unit_id", "") or ""),
            str(getattr(order.charge_order, "primary_target_unit_id", "") or ""),
            str(getattr(order.fight_order, "primary_target_unit_id", "") or ""),
        ]
        for target_id in _ordered_unique_strings(candidate_targets):
            if target_id in assigned_units_by_target:
                assigned_units_by_target[target_id].append(str(unit_id))
    target_orders = {
        target_id: replace(order, assigned_unit_ids=_ordered_unique_strings(assigned_units_by_target.get(target_id, [])))
        for target_id, order in sorted(target_orders.items(), key=lambda item: str(item[0]))
    }

    transport_orders: dict[str, TransportRoundOrder] = {}
    source_transport_orders = dict(getattr(deployment_orders, "transport_orders", {}) or {})
    for transport_id, order in sorted(source_transport_orders.items(), key=lambda item: str(item[0])):
        transport_orders[str(transport_id)] = TransportRoundOrder(
            transport_unit_id=str(transport_id),
            passenger_unit_ids=list(order.passenger_unit_ids),
            intent="deliver" if order.passenger_unit_ids else "screen",
            delivery_round=order.delivery_round,
            delivery_region_ids=order.delivery_region_ids,
            preserve_passengers=order.preserve_passengers,
            post_delivery_role=order.post_delivery_role,
            metadata={
                "source": "strategic_intent_compiler",
                "deployment_order_bundle_id": str(deployment_bundle_id or ""),
                "source_intent_kinds": ["transport_doctrine"],
            },
        )

    phase_priorities = {
        "movement": 0.7 if directive.primary_phase_focus == "movement" else 0.4,
        "shooting": 0.8 if directive.primary_phase_focus == "shooting" else 0.45,
        "charge": 0.6 if directive.posture == POSTURE_PUSH else 0.25,
        "fight": 0.6 if directive.posture == POSTURE_PUSH else 0.25,
        "score": 0.8 if directive.primary_phase_focus == "score" else 0.5,
    }
    return CommanderOrderBundle(
        order_bundle_id=bundle_id,
        player_id=pid,
        battle_round=int(battle_round),
        general_plan_id=general_plan_id,
        deployment_order_bundle_id=deployment_bundle_id,
        prebattle_order_bundle_id=prebattle_bundle_id,
        directive=directive,
        constraints=constraints,
        target_orders=target_orders,
        unit_orders=unit_orders,
        resource_authorizations=resource_authorizations,
        transport_orders=transport_orders,
        phase_priorities=phase_priorities,
        metadata={
            "source": "strategic_intent_compiler",
            "general_plan_id": general_plan_id,
            "deployment_order_bundle_id": str(deployment_bundle_id or ""),
            "prebattle_order_bundle_id": str(prebattle_bundle_id or ""),
            "commander_order_bundle_id": bundle_id,
            "compiled_at_generation": _map_generation(game),
            "source_intent_kinds": [
                "round_posture",
                "deployment_doctrine",
                "resource_policy",
                "transport_doctrine",
            ],
        },
    )
