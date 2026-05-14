from __future__ import annotations

import time
from typing import Any

from .decision_kinds import (
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_DECLARE_RESERVES,
    DECISION_MOVE_UNIT,
    DECISION_SCOUT_MOVE,
    DECISION_SELECT_NEXT_DEPLOY_UNIT,
)
from .decisions import CandidateAction, DecisionOption, DecisionRequest
from .deployment_intent import DeploymentIntent
from .time_manager import WorkBudget
from ..utility.profiling_sections import profiled_section


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _round6(value: float) -> float:
    return float(round(float(value), 6))


def _clamp(value: float, *, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))


def _weight(intent: DeploymentIntent, key: str, default: float) -> float:
    return max(0.0, _safe_float(dict(intent.weights or {}).get(key), default))


def _resolve_unit(game: object, unit_id: str):
    resolver = getattr(game, "_resolve_unit_by_id", None)
    if callable(resolver):
        unit = resolver(unit_id)
        if unit is not None:
            return unit
    for player in list(getattr(game, "players", []) or []):
        army = getattr(player, "army", None)
        for unit in list(getattr(army, "units", []) or []):
            uid = str(getattr(unit, "id", "") or getattr(unit, "_id", "") or "")
            if uid == str(unit_id or ""):
                return unit
    return None


def _resolve_army(game: object, army_id: str):
    army_key = str(army_id or "")
    if not army_key:
        return None
    entity_registry = getattr(game, "entity_registry", None)
    if entity_registry is not None:
        get_from_registry = getattr(entity_registry, "get", None)
        if callable(get_from_registry):
            army = get_from_registry(army_key, kind="army")
            if army is not None:
                return army
    for player in list(getattr(game, "players", []) or []):
        army = getattr(player, "army", None)
        if army is None:
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else None
        if army is None:
            continue
        resolved_id = str(getattr(army, "id", "") or getattr(army, "_id", "") or "")
        if resolved_id == army_key:
            return army
    return None


def _unit_scout_distance(unit: object) -> float:
    if unit is None:
        return 0.0
    has_scout = getattr(unit, "has_scout", None)
    if callable(has_scout):
        value = has_scout()
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return _safe_float(value[1], 0.0) if bool(value[0]) else 0.0
        if bool(value):
            return _safe_float(getattr(unit, "scout_move_distance", 0.0), 0.0)
    return _safe_float(getattr(unit, "scout_move_distance", 0.0), 0.0)


def _unit_point_cost(unit: object) -> float:
    if unit is None:
        return 0.0
    get_cost = getattr(unit, "get_unit_cost", None)
    if callable(get_cost):
        return max(0.0, _safe_float(get_cost(), 0.0))
    return 0.0


def _option_payload(option: DecisionOption) -> dict[str, Any]:
    payload = dict(getattr(option, "payload", {}) or {})
    payload.pop("action_id", None)
    return payload


def _copy_request_candidates(request: DecisionRequest, *, fallback_mode: bool) -> tuple[list[CandidateAction], list[bool]]:
    copied: list[CandidateAction] = []
    for candidate in list(request.candidates or []):
        metadata = dict(candidate.metadata or {})
        metadata["fallback_mode"] = bool(fallback_mode)
        copied.append(
            CandidateAction(
                action_id=str(candidate.action_id),
                params=dict(candidate.params or {}),
                metadata=metadata,
            )
        )
    mask = [bool(v) for v in list(request.mask or [])]
    if len(mask) != len(copied):
        mask = [True] * len(copied)
    return copied, mask


_DEFAULT_LOOKAHEAD_CANDIDATE_KINDS: tuple[str, ...] = (
    "deployment_zone",
    "deployment_commit_order",
    "deployment_reserves",
    "deployment_scout",
    "deployment_move",
)

_LOOKAHEAD_BRANCH_PROFILES: tuple[tuple[str, float, float, float, float], ...] = (
    ("enemy_alpha", 1.0, 0.75, 0.6, 0.88),
    ("enemy_reserve_flank", 0.9, 1.15, 0.8, 0.82),
    ("enemy_staged_trade", 0.72, 0.68, 1.05, 0.95),
)


def _safe_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, (int, float)):
        return bool(value)
    token = str(value or "").strip().lower()
    if not token:
        return bool(default)
    if token in {"1", "true", "yes", "on", "enabled"}:
        return True
    if token in {"0", "false", "no", "off", "disabled"}:
        return False
    return bool(default)


def _as_string_set(values: object) -> set[str]:
    if isinstance(values, str):
        token = str(values or "").strip()
        return {token} if token else set()
    if isinstance(values, (list, tuple, set)):
        result: set[str] = set()
        for value in list(values):
            token = str(value or "").strip()
            if token:
                result.add(token)
        return result
    return set()


def _lookahead_config(context: dict[str, Any], intent: DeploymentIntent) -> dict[str, Any]:
    toggles = dict(intent.constraint_toggles or {})
    raw = context.get("deployment_lookahead")
    cfg: dict[str, Any] = {}
    if isinstance(raw, dict):
        cfg = dict(raw or {})
    elif raw is not None:
        cfg = {"enabled": raw}

    enabled = _safe_bool(
        cfg.get("enabled", toggles.get("deployment_lookahead_enabled", False)),
        default=False,
    )
    depth = max(
        1,
        min(
            3,
            _safe_int(
                cfg.get("depth", toggles.get("deployment_lookahead_depth", 2)),
                2,
            ),
        ),
    )
    branch_count = max(
        1,
        min(
            len(_LOOKAHEAD_BRANCH_PROFILES),
            _safe_int(
                cfg.get(
                    "branch_count",
                    toggles.get("deployment_lookahead_branch_count", 2),
                ),
                2,
            ),
        ),
    )
    discount = _clamp(
        _safe_float(
            cfg.get("discount", toggles.get("deployment_lookahead_discount", 0.62)),
            0.62,
        ),
        low=0.2,
        high=0.95,
    )
    continuation_decay = _clamp(
        _safe_float(
            cfg.get(
                "continuation_decay",
                toggles.get("deployment_lookahead_continuation_decay", 0.7),
            ),
            0.7,
        ),
        low=0.25,
        high=0.95,
    )
    score_blend = _clamp(
        _safe_float(
            cfg.get("score_blend", toggles.get("deployment_lookahead_score_blend", 0.2)),
            0.2,
        ),
        low=0.0,
        high=0.8,
    )
    raw_kinds = cfg.get(
        "candidate_kinds",
        toggles.get("deployment_lookahead_candidate_kinds", _DEFAULT_LOOKAHEAD_CANDIDATE_KINDS),
    )
    candidate_kinds = _as_string_set(raw_kinds)
    if not candidate_kinds:
        candidate_kinds = set(_DEFAULT_LOOKAHEAD_CANDIDATE_KINDS)
    return {
        "enabled": bool(enabled),
        "depth": int(depth),
        "branch_count": int(branch_count),
        "discount": float(discount),
        "continuation_decay": float(continuation_decay),
        "score_blend": float(score_blend),
        "candidate_kinds": candidate_kinds,
    }


def _lookahead_immediate_value(metadata: dict[str, Any], *, intent: DeploymentIntent) -> float:
    score_weight = _weight(intent, "score", 0.3)
    deny_weight = _weight(intent, "deny", 0.2)
    safety_weight = _weight(intent, "safety", 0.3)
    staging_weight = _weight(intent, "staging", 0.2)
    reserve_deny_weight = _weight(intent, "reserve_deny", 0.2)
    screen_weight = _weight(intent, "screen", 0.2)
    countercharge_weight = _weight(intent, "countercharge", 0.15)
    cover_weight = _weight(intent, "cover", 0.2)
    los_weight = _weight(intent, "los", 0.1)
    aura_weight = _weight(intent, "aura", 0.1)

    projected_score_next = _safe_float(metadata.get("projected_score_delta_next_window"), 0.0)
    projected_score_round = _safe_float(metadata.get("projected_score_delta_round"), 0.0)
    projected_deny_next = _safe_float(metadata.get("projected_deny_delta_next_window"), 0.0)
    projected_control = _safe_float(metadata.get("projected_control_delta"), 0.0)
    projected_action = _safe_float(metadata.get("projected_action_enablement_delta"), 0.0)
    projected_trade = _safe_float(metadata.get("projected_trade_ev"), 0.0)
    projected_exposure = _safe_float(metadata.get("projected_exposure_delta"), 0.0)
    exposure_enemy_first = _safe_float(metadata.get("projected_exposure_delta_if_enemy_goes_first"), 0.0)
    reserve_denial = _safe_float(metadata.get("reserve_denial_delta"), 0.0)
    screen_integrity = _safe_float(metadata.get("screen_integrity_delta"), 0.0)
    countercharge = _safe_float(metadata.get("countercharge_coverage_delta"), 0.0)
    aura = _safe_float(metadata.get("aura_connectivity_delta"), 0.0)
    melee_staging = _safe_float(metadata.get("projected_melee_staging_delta"), 0.0)
    cover = _safe_float(metadata.get("cover_delta"), 0.0)
    los = _safe_float(metadata.get("los_delta"), 0.0)
    resource = _safe_float(metadata.get("resource_delta"), 0.0)

    return float(
        projected_score_next * (0.45 + score_weight * 0.55)
        + projected_score_round * (0.16 + score_weight * 0.2)
        + projected_deny_next * (0.38 + deny_weight * 0.52)
        + projected_control * 0.33
        + projected_action * (0.23 + staging_weight * 0.28)
        + projected_trade * 0.28
        + reserve_denial * (0.16 + reserve_deny_weight * 0.22)
        + screen_integrity * (0.14 + screen_weight * 0.24)
        + countercharge * (0.12 + countercharge_weight * 0.21)
        + aura * (0.08 + aura_weight * 0.16)
        + melee_staging * (0.11 + staging_weight * 0.24)
        + cover * (0.11 + cover_weight * 0.2)
        + los * (0.07 + los_weight * 0.18)
        + resource * 0.05
        - exposure_enemy_first * (0.52 + safety_weight * 0.48)
        + projected_exposure * 0.05
    )


def _lookahead_enemy_pressure(
    metadata: dict[str, Any],
    *,
    intent: DeploymentIntent,
    aggressive_mul: float,
    reserve_mul: float,
    screen_mul: float,
) -> float:
    safety_weight = _weight(intent, "safety", 0.3)
    exposure_enemy_first = _safe_float(metadata.get("projected_exposure_delta_if_enemy_goes_first"), 0.0)
    forward_progress = max(0.0, _safe_float(metadata.get("forward_progress_norm"), 0.0))
    anchor_center_distance = _safe_float(metadata.get("anchor_center_distance_norm"), 0.0)
    reserve_denial = _safe_float(metadata.get("reserve_denial_delta"), 0.0)
    screen_integrity = _safe_float(metadata.get("screen_integrity_delta"), 0.0)
    countercharge = _safe_float(metadata.get("countercharge_coverage_delta"), 0.0)
    cover = _safe_float(metadata.get("cover_delta"), 0.0)
    los = _safe_float(metadata.get("los_delta"), 0.0)
    reserve_gap = max(0.0, 0.24 - reserve_denial)
    screen_gap = max(0.0, 0.2 - screen_integrity)
    counter_gap = max(0.0, 0.16 - countercharge)
    cover_gap = max(0.0, 0.14 - cover)
    los_vulnerability = max(0.0, -los)
    return float(
        exposure_enemy_first * (0.74 + safety_weight * 0.36) * float(aggressive_mul)
        + forward_progress * (0.12 + float(aggressive_mul) * 0.11)
        + anchor_center_distance * 0.07
        + reserve_gap * (0.55 + float(reserve_mul) * 0.35)
        + screen_gap * (0.48 + float(screen_mul) * 0.26)
        + counter_gap * 0.32
        + cover_gap * 0.28
        + los_vulnerability * 0.22
    )


def _lookahead_followup_value(
    metadata: dict[str, Any],
    *,
    intent: DeploymentIntent,
    followup_mul: float,
) -> float:
    staging_weight = _weight(intent, "staging", 0.2)
    action_enable = _safe_float(metadata.get("projected_action_enablement_delta"), 0.0)
    control = _safe_float(metadata.get("projected_control_delta"), 0.0)
    trade = max(0.0, _safe_float(metadata.get("projected_trade_ev"), 0.0))
    reserve_denial = max(0.0, _safe_float(metadata.get("reserve_denial_delta"), 0.0))
    screen_integrity = max(0.0, _safe_float(metadata.get("screen_integrity_delta"), 0.0))
    countercharge = max(0.0, _safe_float(metadata.get("countercharge_coverage_delta"), 0.0))
    aura = max(0.0, _safe_float(metadata.get("aura_connectivity_delta"), 0.0))
    melee_staging = max(0.0, _safe_float(metadata.get("projected_melee_staging_delta"), 0.0))
    resource_cost = max(0.0, -_safe_float(metadata.get("resource_delta"), 0.0))
    value = (
        action_enable * (0.3 + staging_weight * 0.2)
        + control * 0.24
        + trade * 0.18
        + reserve_denial * 0.14
        + screen_integrity * 0.14
        + countercharge * 0.12
        + aura * 0.08
        + melee_staging * 0.16
        - resource_cost * 0.08
    )
    return float(value * float(followup_mul))


def _lookahead_projection(
    metadata: dict[str, Any],
    *,
    intent: DeploymentIntent,
    config: dict[str, Any],
) -> dict[str, Any]:
    immediate = _lookahead_immediate_value(metadata, intent=intent)
    branch_count = int(config.get("branch_count", 1) or 1)
    considered_profiles = list(_LOOKAHEAD_BRANCH_PROFILES[: max(1, branch_count)])
    worst_branch_name = ""
    worst_branch_value = float("inf")
    followup_values: list[float] = []
    for branch_name, aggressive_mul, reserve_mul, screen_mul, followup_mul in considered_profiles:
        enemy_pressure = _lookahead_enemy_pressure(
            metadata,
            intent=intent,
            aggressive_mul=float(aggressive_mul),
            reserve_mul=float(reserve_mul),
            screen_mul=float(screen_mul),
        )
        followup = _lookahead_followup_value(
            metadata,
            intent=intent,
            followup_mul=float(followup_mul),
        )
        followup_values.append(float(followup))
        branch_value = float(immediate - enemy_pressure + followup * 0.5)
        if branch_value < worst_branch_value:
            worst_branch_value = float(branch_value)
            worst_branch_name = str(branch_name)

    if worst_branch_value == float("inf"):
        worst_branch_value = float(immediate)
    avg_followup = (
        float(sum(followup_values) / float(len(followup_values)))
        if followup_values
        else 0.0
    )
    discount = float(config.get("discount", 0.62) or 0.62)
    continuation_decay = float(config.get("continuation_decay", 0.7) or 0.7)
    depth = int(config.get("depth", 1) or 1)

    total_value = float(immediate)
    continuation_value = float(worst_branch_value)
    for step in range(max(1, depth)):
        total_value += (discount ** float(step + 1)) * continuation_value
        continuation_value = continuation_value * continuation_decay + avg_followup * (1.0 - continuation_decay) * 0.6

    enemy_pressure = float(max(0.0, immediate - worst_branch_value + avg_followup * 0.5))
    return {
        "lookahead_immediate_value": _round6(immediate),
        "lookahead_worst_branch_value": _round6(worst_branch_value),
        "lookahead_followup_value": _round6(avg_followup),
        "lookahead_enemy_pressure": _round6(enemy_pressure),
        "lookahead_total_value": _round6(total_value),
        "lookahead_worst_branch_name": str(worst_branch_name),
    }


def _apply_deployment_lookahead(
    candidates: list[CandidateAction],
    *,
    request: DecisionRequest,
    intent: DeploymentIntent,
) -> list[CandidateAction]:
    context = dict(getattr(request, "context", {}) or {})
    config = _lookahead_config(context, intent)
    if not bool(config.get("enabled", False)):
        return list(candidates or [])
    allowed_kinds = set(config.get("candidate_kinds", set()) or set())
    score_blend = float(config.get("score_blend", 0.0) or 0.0)
    depth = int(config.get("depth", 1) or 1)
    branch_count = int(config.get("branch_count", 1) or 1)
    discount = float(config.get("discount", 0.62) or 0.62)
    continuation_decay = float(config.get("continuation_decay", 0.7) or 0.7)

    updated: list[CandidateAction] = []
    for candidate in list(candidates or []):
        metadata = dict(candidate.metadata or {})
        candidate_kind = str(metadata.get("candidate_kind", "") or "")
        if allowed_kinds and candidate_kind and candidate_kind not in allowed_kinds:
            updated.append(candidate)
            continue
        lookahead = _lookahead_projection(metadata, intent=intent, config=config)
        metadata["lookahead_enabled"] = True
        metadata["lookahead_depth"] = int(depth)
        metadata["lookahead_branch_count"] = int(branch_count)
        metadata["lookahead_discount"] = _round6(discount)
        metadata["lookahead_continuation_decay"] = _round6(continuation_decay)
        metadata["lookahead_score_blend"] = _round6(score_blend)
        for key, value in lookahead.items():
            metadata[str(key)] = value

        base_round = _safe_float(metadata.get("projected_score_delta_round"), 0.0)
        base_trade = _safe_float(metadata.get("projected_trade_ev"), 0.0)
        metadata["lookahead_base_projected_score_delta_round"] = _round6(base_round)
        metadata["lookahead_base_projected_trade_ev"] = _round6(base_trade)
        adjusted_round = float(base_round + _safe_float(lookahead.get("lookahead_total_value"), 0.0) * score_blend)
        trade_adjustment = (
            _safe_float(lookahead.get("lookahead_worst_branch_value"), 0.0)
            - _safe_float(lookahead.get("lookahead_immediate_value"), 0.0)
        ) * (score_blend * 0.35)
        trade_adjustment += _safe_float(lookahead.get("lookahead_followup_value"), 0.0) * (score_blend * 0.1)
        adjusted_trade = float(base_trade + trade_adjustment)
        metadata["lookahead_adjusted_score_delta_round"] = _round6(adjusted_round)
        metadata["lookahead_adjusted_trade_ev"] = _round6(adjusted_trade)
        metadata["projected_score_delta_round"] = _round6(adjusted_round)
        metadata["projected_trade_ev"] = _round6(adjusted_trade)

        updated.append(
            CandidateAction(
                action_id=str(candidate.action_id),
                params=dict(candidate.params or {}),
                metadata=metadata,
            )
        )
    return updated


def _zone_choice_lookup(context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    refs: dict[str, dict[str, Any]] = {}
    for entry in list(context.get("available_zone_choices", []) or []):
        if not isinstance(entry, dict):
            continue
        data = dict(entry or {})
        choice_id = str(data.get("zone_choice_id", "") or "")
        zone_key = str(data.get("zone_key", "") or "")
        if choice_id:
            refs[choice_id] = data
        if zone_key and zone_key not in refs:
            refs[zone_key] = data
    return refs


def _zone_projection(
    *,
    intent: DeploymentIntent,
    zone_type: str,
    area_estimate: float,
    frontage_estimate: float,
    depth_estimate: float,
    board_affordances: dict[str, Any] | None = None,
) -> dict[str, float]:
    score_weight = _weight(intent, "score", 0.3)
    deny_weight = _weight(intent, "deny", 0.2)
    safety_weight = _weight(intent, "safety", 0.3)
    staging_weight = _weight(intent, "staging", 0.2)
    reserve_deny_weight = _weight(intent, "reserve_deny", 0.2)
    screen_weight = _weight(intent, "screen", 0.2)
    countercharge_weight = _weight(intent, "countercharge", 0.15)
    cover_weight = _weight(intent, "cover", 0.2)
    los_weight = _weight(intent, "los", 0.1)
    aura_weight = _weight(intent, "aura", 0.1)

    affordance_count = float(len(list(intent.desired_affordances or [])))
    lane_count = float(len(list(intent.threatened_lane_ids or [])))
    reserve_target_count = float(len(list(intent.reserve_deny_targets or [])))
    objective_count = float(len(list(intent.target_objective_ids or [])))
    area_norm = _clamp(area_estimate / 900.0, low=0.2, high=1.8)
    frontage_norm = _clamp(frontage_estimate / 30.0, low=0.2, high=1.8)
    depth_norm = _clamp(depth_estimate / 20.0, low=0.2, high=1.8)
    affordances = dict(board_affordances or {})
    los_tunnel_count = _safe_float(affordances.get("los_tunnel_count"), 0.0)
    hidden_cell_count = _safe_float(affordances.get("hidden_staging_cell_count"), 0.0)
    must_expose_count = _safe_float(affordances.get("must_expose_to_advance_cell_count"), 0.0)
    infantry_approach_quality = _safe_float(affordances.get("infantry_objective_approach_quality"), 0.0)
    vehicle_approach_quality = _safe_float(affordances.get("vehicle_objective_approach_quality"), 0.0)
    reserve_lane_values = [
        _safe_float(value, 0.0)
        for value in dict(affordances.get("reserve_entry_lane_quality", {}) or {}).values()
    ]
    reserve_lane_quality_avg = (
        sum(reserve_lane_values) / float(len(reserve_lane_values))
        if reserve_lane_values
        else 0.0
    )
    zone_type_norm = str(zone_type or "").strip().lower()
    defender_bias = 0.08 if zone_type_norm == "defender" else 0.0
    attacker_bias = 0.07 if zone_type_norm == "attacker" else 0.0

    score_next = score_weight * (
        0.22
        + area_norm * 0.23
        + objective_count * 0.03
        + staging_weight * 0.2
        + defender_bias
        + infantry_approach_quality * 0.12
        + los_tunnel_count * 0.02
    )
    deny_next = deny_weight * (
        0.16
        + reserve_target_count * 0.04
        + lane_count * 0.03
        + reserve_deny_weight * 0.22
        + defender_bias
        + reserve_lane_quality_avg * 0.14
        + hidden_cell_count * 0.01
    )
    control = (score_next + deny_next) * 0.72 + screen_weight * (0.06 + frontage_norm * 0.05)
    action_enable = staging_weight * (
        0.14
        + depth_norm * 0.18
        + affordance_count * 0.03
        + attacker_bias * 0.5
        + infantry_approach_quality * 0.1
    )

    exposure_if_enemy_first = _clamp(
        0.62
        - safety_weight * 0.35
        - cover_weight * 0.2
        - area_norm * 0.1
        - depth_norm * 0.08
        - hidden_cell_count * 0.008
        + must_expose_count * 0.01
        + attacker_bias * 0.45,
        low=0.0,
        high=1.4,
    )
    exposure = _clamp(-exposure_if_enemy_first + defender_bias - attacker_bias * 0.35, low=-2.0, high=2.0)
    trade = _clamp(score_next * 0.38 + deny_next * 0.3 + countercharge_weight * 0.22 - exposure_if_enemy_first * 0.28, low=-3.0, high=3.0)
    cover = _clamp(
        cover_weight * (
            0.14
            + area_norm * 0.08
            + defender_bias
            + hidden_cell_count * 0.006
            - must_expose_count * 0.01
        ),
        low=-1.5,
        high=1.5,
    )
    los = _clamp(
        los_weight * (
            0.05
            + frontage_norm * 0.09
            + attacker_bias * 0.6
            - defender_bias * 0.35
            + los_tunnel_count * 0.05
            + infantry_approach_quality * 0.08
        ),
        low=-1.5,
        high=1.5,
    )
    resource = _clamp(-(reserve_deny_weight * 0.04 + screen_weight * 0.03), low=-3.0, high=3.0)

    reserve_denial_delta = reserve_deny_weight * (
        0.2
        + reserve_target_count * 0.05
        + area_norm * 0.09
        + reserve_lane_quality_avg * 0.08
    )
    screen_integrity_delta = screen_weight * (0.19 + frontage_norm * 0.14 + lane_count * 0.03)
    countercharge_coverage_delta = countercharge_weight * (
        0.14
        + depth_norm * 0.11
        + vehicle_approach_quality * 0.1
    )
    aura_connectivity_delta = aura_weight * (
        0.1
        + area_norm * 0.05
        + objective_count * 0.02
        + hidden_cell_count * 0.004
    )
    melee_staging_delta = staging_weight * (
        0.16
        + depth_norm * 0.21
        + attacker_bias * 0.45
        + los_tunnel_count * 0.03
    )

    return {
        "projected_score_delta_next_window": _round6(score_next),
        "projected_score_delta_round": _round6(score_next * 1.22),
        "projected_deny_delta_next_window": _round6(deny_next),
        "projected_control_delta": _round6(control),
        "projected_action_enablement_delta": _round6(action_enable),
        "projected_exposure_delta": _round6(exposure),
        "projected_trade_ev": _round6(trade),
        "cover_delta": _round6(cover),
        "los_delta": _round6(los),
        "resource_delta": _round6(resource),
        "reserve_denial_delta": _round6(reserve_denial_delta),
        "screen_integrity_delta": _round6(screen_integrity_delta),
        "countercharge_coverage_delta": _round6(countercharge_coverage_delta),
        "aura_connectivity_delta": _round6(aura_connectivity_delta),
        "projected_exposure_delta_if_enemy_goes_first": _round6(exposure_if_enemy_first),
        "projected_melee_staging_delta": _round6(melee_staging_delta),
    }


def _deployment_zone_candidates(game: object, request: DecisionRequest, intent: DeploymentIntent) -> tuple[list[CandidateAction], list[bool]]:
    del game
    ctx = dict(getattr(request, "context", {}) or {})
    lookup = _zone_choice_lookup(ctx)
    candidates: list[CandidateAction] = []
    for option in list(getattr(request, "options", []) or []):
        option_id = str(getattr(option, "option_id", "") or "")
        if not option_id:
            continue
        payload = _option_payload(option)
        action_id = request.action_id_for_option_id(option_id)
        zone_choice_id = str(payload.get("zone_choice_id", "") or "")
        zone_key = str(payload.get("zone_key", "") or "")
        zone_type = str(payload.get("zone_type", "") or "")
        ref = lookup.get(zone_choice_id) or lookup.get(zone_key) or {}
        area_estimate = _safe_float(payload.get("zone_area_estimate", ref.get("zone_area_estimate", 480.0)), 480.0)
        frontage_estimate = _safe_float(payload.get("zone_frontage_estimate", ref.get("zone_frontage_estimate", 24.0)), 24.0)
        depth_estimate = _safe_float(payload.get("zone_depth_estimate", ref.get("zone_depth_estimate", 20.0)), 20.0)
        board_affordances = dict(payload.get("board_affordances", ref.get("board_affordances", {})) or {})
        projection = _zone_projection(
            intent=intent,
            zone_type=zone_type,
            area_estimate=area_estimate,
            frontage_estimate=frontage_estimate,
            depth_estimate=depth_estimate,
            board_affordances=board_affordances,
        )
        metadata = {
            "candidate_kind": "deployment_zone",
            "solver_ms": 0,
            "fallback_mode": False,
            "intent_hash": intent.stable_hash(),
            "zone_type": zone_type,
            "zone_area_estimate": _round6(area_estimate),
            "zone_frontage_estimate": _round6(frontage_estimate),
            "zone_depth_estimate": _round6(depth_estimate),
            "los_tunnel_count": _safe_int(board_affordances.get("los_tunnel_count", 0), 0),
            "hidden_staging_cell_count": _safe_int(board_affordances.get("hidden_staging_cell_count", 0), 0),
            "must_expose_to_advance_cell_count": _safe_int(board_affordances.get("must_expose_to_advance_cell_count", 0), 0),
            "infantry_objective_approach_quality": _round6(
                _safe_float(board_affordances.get("infantry_objective_approach_quality"), 0.0)
            ),
            "vehicle_objective_approach_quality": _round6(
                _safe_float(board_affordances.get("vehicle_objective_approach_quality"), 0.0)
            ),
            "rules_provenance_refs": [str(ctx.get("rules_bundle_id", "") or "")] if str(ctx.get("rules_bundle_id", "") or "") else [],
        }
        metadata.update(projection)
        candidates.append(
            CandidateAction(
                action_id=str(action_id),
                params=payload,
                metadata=metadata,
            )
        )

    candidates.sort(key=lambda candidate: str(candidate.action_id))
    top_k = _safe_int(ctx.get("deployment_top_k", len(candidates)), len(candidates))
    if top_k > 0:
        candidates = candidates[:top_k]
    mask = [True] * len(candidates)
    return candidates, mask


def _unit_keywords(unit: object) -> set[str]:
    pool: set[str] = set()
    for key in ("keywords", "faction_keywords"):
        for value in list(getattr(unit, key, []) or []):
            token = str(value or "").strip().upper()
            if token:
                pool.add(token)
    return pool


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


def _unit_profile(unit: object) -> dict[str, float]:
    keywords = _unit_keywords(unit)
    infiltrator = _unit_flag_from_method(unit, "has_infiltrate") or ("INFILTRATORS" in keywords)
    scout = (
        _unit_flag_from_method(unit, "has_scout")
        or _unit_flag_from_method(unit, "has_scout_move")
        or bool(_safe_float(getattr(unit, "scout_move_distance", 0.0), 0.0) > 0.0)
        or ("SCOUT" in keywords)
    )
    reserve_capable = _unit_flag_from_method(unit, "has_deep_strike") or ("DEEP STRIKE" in keywords)
    titanic = bool(getattr(unit, "is_titanic", False))
    transport = bool(getattr(unit, "is_transport", False))
    leader = bool(getattr(unit, "is_leader", False))
    aura_source = 1.0 if (leader or "CHARACTER" in keywords or "LEADER" in keywords) else 0.0
    model_count = float(len(list(getattr(unit, "models", []) or [])))
    durable = _clamp(model_count / 10.0, low=0.15, high=1.25)
    if titanic:
        durable = max(durable, 1.2)
    screen_value = 1.0 if (infiltrator or scout) else 0.0
    anchor_value = 1.0 if (titanic or transport or durable >= 0.9) else 0.35
    threat_value = 1.0 if reserve_capable else 0.45
    return {
        "infiltrator": 1.0 if infiltrator else 0.0,
        "scout": 1.0 if scout else 0.0,
        "reserve_capable": 1.0 if reserve_capable else 0.0,
        "titanic": 1.0 if titanic else 0.0,
        "transport": 1.0 if transport else 0.0,
        "aura_source": aura_source,
        "durable": durable,
        "screen_value": screen_value,
        "anchor_value": anchor_value,
        "threat_value": threat_value,
    }


def _next_unit_projection(
    *,
    intent: DeploymentIntent,
    unit_profile: dict[str, float],
    already_deployed_count: int,
    remaining_count: int,
) -> dict[str, float]:
    score_weight = _weight(intent, "score", 0.3)
    deny_weight = _weight(intent, "deny", 0.2)
    safety_weight = _weight(intent, "safety", 0.3)
    staging_weight = _weight(intent, "staging", 0.2)
    reserve_deny_weight = _weight(intent, "reserve_deny", 0.2)
    screen_weight = _weight(intent, "screen", 0.2)
    countercharge_weight = _weight(intent, "countercharge", 0.15)
    cover_weight = _weight(intent, "cover", 0.2)
    los_weight = _weight(intent, "los", 0.1)
    aura_weight = _weight(intent, "aura", 0.1)

    deployed = max(0, int(already_deployed_count))
    remaining = max(1, int(remaining_count))
    progress = _clamp(float(deployed) / float(deployed + remaining), low=0.0, high=1.0)
    early_phase = 1.0 - progress

    screen = _safe_float(unit_profile.get("screen_value"), 0.0)
    anchor = _safe_float(unit_profile.get("anchor_value"), 0.0)
    threat = _safe_float(unit_profile.get("threat_value"), 0.0)
    durable = _safe_float(unit_profile.get("durable"), 0.5)
    aura_source = _safe_float(unit_profile.get("aura_source"), 0.0)
    reserve_capable = _safe_float(unit_profile.get("reserve_capable"), 0.0)

    score_next = score_weight * (0.08 + anchor * (0.18 + early_phase * 0.08) + threat * (0.06 + progress * 0.12))
    deny_next = deny_weight * (0.06 + screen * (0.22 + early_phase * 0.12) + reserve_deny_weight * reserve_capable * 0.15)
    control = (score_next + deny_next) * 0.7 + screen_weight * (0.04 + screen * 0.08)
    action_enable = staging_weight * (0.1 + threat * (0.06 + progress * 0.12) + anchor * 0.06)

    exposure_if_enemy_first = _clamp(
        0.58 + (1.0 - durable) * 0.25 - safety_weight * 0.3 - cover_weight * 0.15 - screen * early_phase * 0.15,
        low=0.0,
        high=1.6,
    )
    exposure = _clamp(-exposure_if_enemy_first + durable * 0.08, low=-2.0, high=2.0)
    trade = _clamp(score_next * 0.32 + deny_next * 0.28 + threat * 0.16 + countercharge_weight * anchor * 0.2 - exposure_if_enemy_first * 0.28, low=-3.0, high=3.0)
    cover = _clamp(cover_weight * (0.08 + durable * 0.12 + screen * 0.07), low=-1.5, high=1.5)
    los = _clamp(los_weight * (0.04 + threat * 0.09 + progress * 0.05 - screen * 0.03), low=-1.5, high=1.5)
    resource = _clamp(-(screen_weight * screen * 0.04 + reserve_deny_weight * reserve_capable * 0.03), low=-3.0, high=3.0)

    reserve_denial_delta = reserve_deny_weight * (0.09 + screen * 0.24 + reserve_capable * 0.11)
    screen_integrity_delta = screen_weight * (0.1 + screen * 0.4 + early_phase * 0.15)
    countercharge_coverage_delta = countercharge_weight * (0.08 + anchor * 0.22 + durable * 0.06)
    aura_connectivity_delta = aura_weight * (0.08 + aura_source * 0.25 + anchor * 0.1)
    melee_staging_delta = staging_weight * (0.1 + threat * (0.14 + progress * 0.16) + anchor * 0.05)

    return {
        "projected_score_delta_next_window": _round6(score_next),
        "projected_score_delta_round": _round6(score_next * 1.2),
        "projected_deny_delta_next_window": _round6(deny_next),
        "projected_control_delta": _round6(control),
        "projected_action_enablement_delta": _round6(action_enable),
        "projected_exposure_delta": _round6(exposure),
        "projected_trade_ev": _round6(trade),
        "cover_delta": _round6(cover),
        "los_delta": _round6(los),
        "resource_delta": _round6(resource),
        "reserve_denial_delta": _round6(reserve_denial_delta),
        "screen_integrity_delta": _round6(screen_integrity_delta),
        "countercharge_coverage_delta": _round6(countercharge_coverage_delta),
        "aura_connectivity_delta": _round6(aura_connectivity_delta),
        "projected_exposure_delta_if_enemy_goes_first": _round6(exposure_if_enemy_first),
        "projected_melee_staging_delta": _round6(melee_staging_delta),
    }


def _next_deploy_unit_candidates(game: object, request: DecisionRequest, intent: DeploymentIntent) -> tuple[list[CandidateAction], list[bool]]:
    ctx = dict(getattr(request, "context", {}) or {})
    already_deployed_count = _safe_int(ctx.get("already_deployed_count", 0), 0)
    undeployed_count = max(1, _safe_int(ctx.get("undeployed_count", len(list(getattr(request, "options", []) or [])),)))
    candidates: list[CandidateAction] = []
    for option in list(getattr(request, "options", []) or []):
        option_id = str(getattr(option, "option_id", "") or "")
        if not option_id:
            continue
        action_id = request.action_id_for_option_id(option_id)
        payload = _option_payload(option)
        unit_id = str(payload.get("unit_id", "") or "")
        unit = _resolve_unit(game, unit_id)
        unit_profile = _unit_profile(unit) if unit is not None else {
            "screen_value": 0.0,
            "anchor_value": 0.5,
            "threat_value": 0.5,
            "durable": 0.5,
            "reserve_capable": 0.0,
            "aura_source": 0.0,
        }
        projection = _next_unit_projection(
            intent=intent,
            unit_profile=unit_profile,
            already_deployed_count=already_deployed_count,
            remaining_count=max(1, undeployed_count),
        )
        metadata = {
            "candidate_kind": "deployment_commit_order",
            "solver_ms": 0,
            "fallback_mode": False,
            "intent_hash": intent.stable_hash(),
            "unit_profile": unit_profile,
            "rules_provenance_refs": [str(ctx.get("rules_bundle_id", "") or "")] if str(ctx.get("rules_bundle_id", "") or "") else [],
        }
        metadata.update(projection)
        candidates.append(
            CandidateAction(
                action_id=str(action_id),
                params=payload,
                metadata=metadata,
            )
        )

    candidates.sort(key=lambda candidate: str(candidate.action_id))
    top_k = _safe_int(ctx.get("deployment_top_k", len(candidates)), len(candidates))
    if top_k > 0:
        candidates = candidates[:top_k]
    mask = [True] * len(candidates)
    return candidates, mask


def _reserves_candidates(game: object, request: DecisionRequest, intent: DeploymentIntent) -> tuple[list[CandidateAction], list[bool]]:
    ctx = dict(getattr(request, "context", {}) or {})
    options = list(getattr(request, "options", []) or [])
    army = _resolve_army(game, str(ctx.get("army_id", "") or ""))
    limits_fn = getattr(army, "get_reserve_limits", None) if army is not None else None
    limits = dict(limits_fn() or {}) if callable(limits_fn) else {}
    max_units = max(1, _safe_int(limits.get("max_units"), 1))
    max_points = max(1, _safe_int(limits.get("max_points"), 1))
    max_strategic_points = max(1, _safe_int(limits.get("max_strategic_points"), 1))
    reserve_lane_quality = dict(dict(ctx.get("board_affordances", {}) or {}).get("reserve_entry_lane_quality", {}) or {})
    lane_values = [_safe_float(value, 0.0) for value in reserve_lane_quality.values()]
    lane_quality_avg = sum(lane_values) / float(len(lane_values)) if lane_values else 0.0
    root_unit_ids = [str(unit_id) for unit_id in list(ctx.get("reserve_root_unit_ids", []) or []) if str(unit_id)]

    candidates: list[CandidateAction] = []
    for option in options:
        option_id = str(getattr(option, "option_id", "") or "")
        if not option_id:
            continue
        action_id = request.action_id_for_option_id(option_id)
        payload = _option_payload(option)
        buckets = dict(payload.get("unit_ids_by_bucket", {}) or {})
        decisions: dict[str, str] = {unit_id: "deploy" for unit_id in root_unit_ids}
        for status in ("deploy", "reserves", "strategic_reserves"):
            for unit_id in list(buckets.get(status, []) or []):
                unit_key = str(unit_id or "")
                if not unit_key:
                    continue
                decisions[unit_key] = status

        reserve_units = 0
        reserve_points = 0.0
        strategic_points = 0.0
        deep_strike_reserve_count = 0.0
        reserve_capable_count = 0.0
        deploy_screen_count = 0.0
        deploy_anchor_count = 0.0
        for unit_id, status in sorted(decisions.items()):
            unit = _resolve_unit(game, unit_id)
            profile = _unit_profile(unit) if unit is not None else {
                "reserve_capable": 0.0,
                "screen_value": 0.0,
                "anchor_value": 0.0,
            }
            points = _unit_point_cost(unit)
            status_key = str(status or "deploy")
            if status_key in ("reserves", "strategic_reserves"):
                reserve_units += 1
                reserve_points += points
                if status_key == "strategic_reserves":
                    strategic_points += points
                reserve_capable_count += _safe_float(profile.get("reserve_capable"), 0.0)
                if _safe_float(profile.get("reserve_capable"), 0.0) > 0.0 and status_key == "reserves":
                    deep_strike_reserve_count += 1.0
            else:
                deploy_screen_count += _safe_float(profile.get("screen_value"), 0.0)
                deploy_anchor_count += _safe_float(profile.get("anchor_value"), 0.0)

        reserve_units_ratio = _clamp(float(reserve_units) / float(max_units), low=0.0, high=2.0)
        reserve_points_ratio = _clamp(float(reserve_points) / float(max_points), low=0.0, high=2.0)
        strategic_points_ratio = _clamp(float(strategic_points) / float(max_strategic_points), low=0.0, high=2.0)

        score_weight = _weight(intent, "score", 0.3)
        deny_weight = _weight(intent, "deny", 0.2)
        safety_weight = _weight(intent, "safety", 0.3)
        reserve_deny_weight = _weight(intent, "reserve_deny", 0.2)
        screen_weight = _weight(intent, "screen", 0.2)
        staging_weight = _weight(intent, "staging", 0.2)
        cover_weight = _weight(intent, "cover", 0.2)
        los_weight = _weight(intent, "los", 0.1)
        countercharge_weight = _weight(intent, "countercharge", 0.15)
        aura_weight = _weight(intent, "aura", 0.1)

        objective_count = float(len(list(intent.target_objective_ids or [])))
        lane_count = float(len(list(intent.threatened_lane_ids or [])))
        deep_strike_pressure_delta = reserve_deny_weight * (
            0.08 + deep_strike_reserve_count * 0.18 + reserve_capable_count * 0.06
        )
        reserve_entry_lane_delta = reserve_deny_weight * (
            0.06 + lane_quality_avg * 0.65 + lane_count * 0.03
        )
        reserve_denial_delta = reserve_deny_weight * (
            0.12 + deploy_screen_count * 0.14 + deploy_anchor_count * 0.05
        )
        screen_integrity_delta = screen_weight * (0.1 + deploy_screen_count * 0.22)
        countercharge_coverage_delta = countercharge_weight * (0.08 + deploy_anchor_count * 0.12)
        aura_connectivity_delta = aura_weight * (0.05 + deploy_anchor_count * 0.09)

        score_next = score_weight * (
            0.05 + deep_strike_pressure_delta * 0.45 + reserve_entry_lane_delta * 0.35 + objective_count * 0.01
        )
        deny_next = deny_weight * (
            0.07 + reserve_denial_delta * 0.6 + screen_integrity_delta * 0.25 + lane_count * 0.02
        )
        control = (score_next + deny_next) * 0.7 + screen_weight * deploy_anchor_count * 0.03
        action_enable = staging_weight * (
            0.07 + deep_strike_reserve_count * 0.08 + reserve_entry_lane_delta * 0.25
        )
        exposure_if_enemy_first = _clamp(
            0.52 - safety_weight * 0.28 - cover_weight * 0.16 + reserve_units_ratio * 0.08 - deploy_screen_count * 0.05,
            low=0.0,
            high=1.6,
        )
        exposure = _clamp(-exposure_if_enemy_first + reserve_units_ratio * 0.02, low=-2.0, high=2.0)
        trade = _clamp(
            score_next * 0.32
            + deny_next * 0.28
            + deep_strike_pressure_delta * 0.22
            + reserve_entry_lane_delta * 0.2
            - exposure_if_enemy_first * 0.25,
            low=-3.0,
            high=3.0,
        )
        cover = _clamp(cover_weight * (0.03 + deploy_anchor_count * 0.08), low=-1.5, high=1.5)
        los = _clamp(los_weight * (0.02 + deep_strike_pressure_delta * 0.2), low=-1.5, high=1.5)
        resource = _clamp(
            -(reserve_points_ratio * 0.18 + strategic_points_ratio * 0.14 + reserve_units_ratio * 0.08),
            low=-3.0,
            high=3.0,
        )

        metadata = {
            "candidate_kind": "deployment_reserves",
            "solver_ms": 0,
            "fallback_mode": False,
            "intent_hash": intent.stable_hash(),
            "strategy_id": str(payload.get("strategy_id", "") or ""),
            "reserve_units": int(reserve_units),
            "reserve_points": int(round(reserve_points)),
            "strategic_points": int(round(strategic_points)),
            "reserve_unit_slots_ratio": _round6(reserve_units_ratio),
            "reserve_points_ratio": _round6(reserve_points_ratio),
            "strategic_points_ratio": _round6(strategic_points_ratio),
            "deep_strike_pressure_delta": _round6(deep_strike_pressure_delta),
            "reserve_entry_lane_delta": _round6(reserve_entry_lane_delta),
            "rules_provenance_refs": [str(ctx.get("rules_bundle_id", "") or "")] if str(ctx.get("rules_bundle_id", "") or "") else [],
            "projected_score_delta_next_window": _round6(score_next),
            "projected_score_delta_round": _round6(score_next * 1.18),
            "projected_deny_delta_next_window": _round6(deny_next),
            "projected_control_delta": _round6(control),
            "projected_action_enablement_delta": _round6(action_enable),
            "projected_exposure_delta": _round6(exposure),
            "projected_trade_ev": _round6(trade),
            "cover_delta": _round6(cover),
            "los_delta": _round6(los),
            "resource_delta": _round6(resource),
            "reserve_denial_delta": _round6(reserve_denial_delta),
            "screen_integrity_delta": _round6(screen_integrity_delta),
            "countercharge_coverage_delta": _round6(countercharge_coverage_delta),
            "aura_connectivity_delta": _round6(aura_connectivity_delta),
            "projected_exposure_delta_if_enemy_goes_first": _round6(exposure_if_enemy_first),
            "projected_melee_staging_delta": _round6(staging_weight * (0.06 + deep_strike_pressure_delta * 0.2)),
        }
        candidates.append(
            CandidateAction(
                action_id=str(action_id),
                params=payload,
                metadata=metadata,
            )
        )
    candidates.sort(key=lambda candidate: str(candidate.action_id))
    top_k = _safe_int(ctx.get("deployment_top_k", len(candidates)), len(candidates))
    if top_k > 0:
        candidates = candidates[:top_k]
    mask = [True] * len(candidates)
    return candidates, mask


def _scout_move_candidates(game: object, request: DecisionRequest, intent: DeploymentIntent) -> tuple[list[CandidateAction], list[bool]]:
    ctx = dict(getattr(request, "context", {}) or {})
    options = list(getattr(request, "options", []) or [])
    unit_id = str(ctx.get("unit_id", "") or "")
    unit = _resolve_unit(game, unit_id)
    unit_profile = _unit_profile(unit) if unit is not None else {
        "screen_value": 0.0,
        "infiltrator": 0.0,
        "scout": 0.0,
        "anchor_value": 0.0,
        "reserve_capable": 0.0,
    }
    scout_distance = _safe_float(ctx.get("scout_distance", _unit_scout_distance(unit)), 0.0)
    origin_data = list(ctx.get("scout_origin", []) or [])
    origin_x = _safe_float(origin_data[0], 0.0) if len(origin_data) >= 1 else 0.0
    origin_y = _safe_float(origin_data[1], 0.0) if len(origin_data) >= 2 else 0.0
    board_affordances = dict(ctx.get("board_affordances", {}) or {})
    reserve_lane_quality = dict(board_affordances.get("reserve_entry_lane_quality", {}) or {})
    lane_quality_values = [_safe_float(value, 0.0) for value in reserve_lane_quality.values()]
    lane_quality_avg = sum(lane_quality_values) / float(len(lane_quality_values)) if lane_quality_values else 0.0
    map_obj = getattr(game, "map", None)
    board_width = _safe_float(getattr(map_obj, "width", 60.0), 60.0)
    board_height = _safe_float(getattr(map_obj, "height", 44.0), 44.0)
    center_x = board_width * 0.5
    center_y = board_height * 0.5
    origin_center_dist = ((origin_x - center_x) ** 2 + (origin_y - center_y) ** 2) ** 0.5

    score_weight = _weight(intent, "score", 0.3)
    deny_weight = _weight(intent, "deny", 0.2)
    safety_weight = _weight(intent, "safety", 0.3)
    reserve_deny_weight = _weight(intent, "reserve_deny", 0.2)
    screen_weight = _weight(intent, "screen", 0.2)
    staging_weight = _weight(intent, "staging", 0.2)
    cover_weight = _weight(intent, "cover", 0.2)
    los_weight = _weight(intent, "los", 0.1)
    countercharge_weight = _weight(intent, "countercharge", 0.15)
    aura_weight = _weight(intent, "aura", 0.1)

    candidates: list[CandidateAction] = []
    for option in options:
        option_id = str(getattr(option, "option_id", "") or "")
        if not option_id:
            continue
        payload = _option_payload(option)
        action_id = request.action_id_for_option_id(option_id)
        action = str(payload.get("action", "") or "").strip().lower()
        if action == "skip":
            metadata = {
                "candidate_kind": "noop",
                "solver_ms": 0,
                "fallback_mode": False,
                "intent_hash": intent.stable_hash(),
                "rules_provenance_refs": [str(ctx.get("rules_bundle_id", "") or "")] if str(ctx.get("rules_bundle_id", "") or "") else [],
                "projected_score_delta_next_window": _round6(0.0),
                "projected_score_delta_round": _round6(0.0),
                "projected_deny_delta_next_window": _round6(0.0),
                "projected_control_delta": _round6(0.0),
                "projected_action_enablement_delta": _round6(0.0),
                "projected_exposure_delta": _round6(0.0),
                "projected_trade_ev": _round6(0.0),
                "cover_delta": _round6(0.0),
                "los_delta": _round6(0.0),
                "resource_delta": _round6(0.0),
                "reserve_denial_delta": _round6(0.0),
                "screen_integrity_delta": _round6(0.0),
                "countercharge_coverage_delta": _round6(0.0),
                "aura_connectivity_delta": _round6(0.0),
                "projected_exposure_delta_if_enemy_goes_first": _round6(0.0),
                "projected_melee_staging_delta": _round6(0.0),
            }
            candidates.append(CandidateAction(action_id=str(action_id), params=payload, metadata=metadata))
            continue

        if action != "scout":
            continue
        destination = list(payload.get("destination", []) or [])
        model_positions = list(payload.get("model_positions", []) or [])
        if len(destination) < 2 and not model_positions:
            continue
        dest_x = _safe_float(destination[0], origin_x) if len(destination) >= 1 else origin_x
        dest_y = _safe_float(destination[1], origin_y) if len(destination) >= 2 else origin_y
        travel = ((dest_x - origin_x) ** 2 + (dest_y - origin_y) ** 2) ** 0.5
        travel_ratio = _clamp(travel / max(1.0, scout_distance), low=0.0, high=1.5)
        dest_center_dist = ((dest_x - center_x) ** 2 + (dest_y - center_y) ** 2) ** 0.5
        center_delta = _clamp((origin_center_dist - dest_center_dist) / max(1.0, scout_distance), low=-1.5, high=1.5)
        screen_value = _safe_float(unit_profile.get("screen_value"), 0.0)
        infiltrator = _safe_float(unit_profile.get("infiltrator"), 0.0)
        scout_value = _safe_float(unit_profile.get("scout"), 0.0)
        anchor_value = _safe_float(unit_profile.get("anchor_value"), 0.0)

        deep_strike_pressure_delta = reserve_deny_weight * (0.05 + (infiltrator + scout_value) * 0.22 + travel_ratio * 0.04)
        reserve_entry_lane_delta = reserve_deny_weight * (0.04 + lane_quality_avg * 0.7 + travel_ratio * 0.06)
        reserve_denial_delta = reserve_deny_weight * (0.09 + screen_value * 0.3 + travel_ratio * 0.1)
        screen_integrity_delta = screen_weight * (0.1 + screen_value * 0.28 + max(0.0, center_delta) * 0.08)
        countercharge_coverage_delta = countercharge_weight * (0.05 + anchor_value * 0.18 + travel_ratio * 0.04)
        aura_connectivity_delta = aura_weight * (0.03 + anchor_value * 0.08 - max(0.0, center_delta) * 0.05)

        score_next = score_weight * (0.04 + max(0.0, center_delta) * 0.28 + deep_strike_pressure_delta * 0.35)
        deny_next = deny_weight * (0.06 + reserve_denial_delta * 0.58 + reserve_entry_lane_delta * 0.28)
        control = (score_next + deny_next) * 0.68 + screen_weight * screen_value * 0.04
        action_enable = staging_weight * (0.05 + travel_ratio * 0.14 + max(0.0, center_delta) * 0.12)
        exposure_if_enemy_first = _clamp(
            0.48 - safety_weight * 0.26 - cover_weight * 0.16 + max(0.0, center_delta) * 0.15 - screen_value * 0.08,
            low=0.0,
            high=1.5,
        )
        exposure = _clamp(-exposure_if_enemy_first + screen_value * 0.04, low=-2.0, high=2.0)
        trade = _clamp(
            score_next * 0.31
            + deny_next * 0.29
            + deep_strike_pressure_delta * 0.24
            - exposure_if_enemy_first * 0.24,
            low=-3.0,
            high=3.0,
        )
        cover = _clamp(cover_weight * (0.02 + screen_value * 0.09), low=-1.5, high=1.5)
        los = _clamp(los_weight * (0.01 + max(0.0, center_delta) * 0.12 + travel_ratio * 0.05), low=-1.5, high=1.5)
        resource = _clamp(-(travel_ratio * 0.06), low=-3.0, high=3.0)

        metadata = {
            "candidate_kind": "deployment_scout",
            "solver_ms": 0,
            "fallback_mode": False,
            "intent_hash": intent.stable_hash(),
            "unit_profile": unit_profile,
            "scout_distance": _round6(scout_distance),
            "travel_distance": _round6(travel),
            "travel_ratio": _round6(travel_ratio),
            "center_delta": _round6(center_delta),
            "deep_strike_pressure_delta": _round6(deep_strike_pressure_delta),
            "reserve_entry_lane_delta": _round6(reserve_entry_lane_delta),
            "rules_provenance_refs": [str(ctx.get("rules_bundle_id", "") or "")] if str(ctx.get("rules_bundle_id", "") or "") else [],
            "projected_score_delta_next_window": _round6(score_next),
            "projected_score_delta_round": _round6(score_next * 1.16),
            "projected_deny_delta_next_window": _round6(deny_next),
            "projected_control_delta": _round6(control),
            "projected_action_enablement_delta": _round6(action_enable),
            "projected_exposure_delta": _round6(exposure),
            "projected_trade_ev": _round6(trade),
            "cover_delta": _round6(cover),
            "los_delta": _round6(los),
            "resource_delta": _round6(resource),
            "reserve_denial_delta": _round6(reserve_denial_delta),
            "screen_integrity_delta": _round6(screen_integrity_delta),
            "countercharge_coverage_delta": _round6(countercharge_coverage_delta),
            "aura_connectivity_delta": _round6(aura_connectivity_delta),
            "projected_exposure_delta_if_enemy_goes_first": _round6(exposure_if_enemy_first),
            "projected_melee_staging_delta": _round6(staging_weight * (0.05 + max(0.0, center_delta) * 0.2)),
        }
        candidates.append(
            CandidateAction(
                action_id=str(action_id),
                params=payload,
                metadata=metadata,
            )
        )

    candidates.sort(key=lambda candidate: str(candidate.action_id))
    top_k = _safe_int(ctx.get("deployment_top_k", len(candidates)), len(candidates))
    if top_k > 0:
        candidates = candidates[:top_k]
    mask = [True] * len(candidates)
    return candidates, mask


def _deployment_move_candidates(game: object, request: DecisionRequest, intent: DeploymentIntent) -> tuple[list[CandidateAction], list[bool]]:
    ctx = dict(getattr(request, "context", {}) or {})
    fallback_positions = list(ctx.get("deployment_model_positions", []) or [])
    if not fallback_positions and not list(getattr(request, "options", []) or []):
        return _copy_request_candidates(request, fallback_mode=False)

    desired_affordances = {str(value or "").strip().upper() for value in list(intent.desired_affordances or []) if str(value or "").strip()}
    forward_preference = 0.0
    if "LOS_TUNNEL_ADVANCE" in desired_affordances:
        forward_preference += 0.6
    if "MIDBOARD_STAGING" in desired_affordances:
        forward_preference += 0.45
    if "FORWARD_SCREEN" in desired_affordances:
        forward_preference += 0.5
    if "EXPOSURE_MINIMIZATION" in desired_affordances:
        forward_preference -= 0.75
    if "HOME_ANCHOR" in desired_affordances:
        forward_preference -= 0.4
    lateral_preference = 0.0
    if "SCREEN_DEPTH" in desired_affordances:
        lateral_preference += 0.45
    if "COUNTERCHARGE_POCKET" in desired_affordances:
        lateral_preference += 0.2
    if "SAFE_FIRING_POCKET" in desired_affordances:
        lateral_preference += 0.1
    retreat_preference = max(0.0, -forward_preference)

    map_obj = getattr(game, "map", None)
    board_width = max(1.0, _safe_float(getattr(map_obj, "width", 60.0), 60.0))
    board_height = max(1.0, _safe_float(getattr(map_obj, "height", 44.0), 44.0))
    board_center_x = board_width * 0.5
    board_center_y = board_height * 0.5
    anchor_tokens = dict(intent.anchors or {})
    zone_center_x = _safe_float(anchor_tokens.get("deployment_center_x"), board_center_x)
    zone_center_y = _safe_float(anchor_tokens.get("deployment_center_y"), board_center_y)
    forward_dx = board_center_x - zone_center_x
    forward_dy = board_center_y - zone_center_y
    forward_mag = float((forward_dx * forward_dx + forward_dy * forward_dy) ** 0.5)
    if forward_mag <= 1e-9:
        forward_vec = (0.0, 1.0)
    else:
        forward_vec = (forward_dx / forward_mag, forward_dy / forward_mag)
    side_vec = (-forward_vec[1], forward_vec[0])
    anchor_norm_scale = max(6.0, max(board_width, board_height) * 0.5)
    candidate_count = max(1, _safe_int(ctx.get("deployment_candidate_count", len(list(getattr(request, "options", []) or []))), 1))

    candidates: list[CandidateAction] = []
    for option in list(getattr(request, "options", []) or []):
        payload = _option_payload(option)
        action = str(payload.get("action", "") or "").strip().lower()
        option_id = str(getattr(option, "option_id", "") or "")
        if not option_id:
            continue
        action_id = request.action_id_for_option_id(option_id)
        if action == "skip":
            candidates.append(
                CandidateAction(
                    action_id=str(action_id),
                    params=payload,
                    metadata={
                        "candidate_kind": "noop",
                        "solver_ms": 0,
                        "fallback_mode": False,
                        "intent_hash": intent.stable_hash(),
                    },
                )
            )
            continue
        model_positions = list(payload.get("model_positions", []) or fallback_positions or [])
        if not model_positions:
            continue
        params = dict(payload)
        params["model_positions"] = model_positions
        raw_anchor = list(payload.get("deployment_anchor", []) or [])
        if len(raw_anchor) >= 2:
            anchor_x = _safe_float(raw_anchor[0], zone_center_x)
            anchor_y = _safe_float(raw_anchor[1], zone_center_y)
        else:
            sample_points = [
                list(dict(entry or {}).get("position", []) or [])
                for entry in list(model_positions or [])
                if isinstance(entry, dict)
            ]
            sample_points = [point for point in sample_points if len(point) >= 2]
            if sample_points:
                anchor_x = sum(_safe_float(point[0], zone_center_x) for point in sample_points) / float(len(sample_points))
                anchor_y = sum(_safe_float(point[1], zone_center_y) for point in sample_points) / float(len(sample_points))
            else:
                anchor_x = zone_center_x
                anchor_y = zone_center_y
        params["deployment_anchor"] = [float(anchor_x), float(anchor_y)]

        relative_dx = float(anchor_x - zone_center_x)
        relative_dy = float(anchor_y - zone_center_y)
        forward_progress = float(relative_dx * forward_vec[0] + relative_dy * forward_vec[1])
        lateral_offset = float(abs(relative_dx * side_vec[0] + relative_dy * side_vec[1]))
        center_distance = float((relative_dx * relative_dx + relative_dy * relative_dy) ** 0.5)
        forward_norm = _clamp(forward_progress / anchor_norm_scale, low=-1.5, high=1.5)
        lateral_norm = _clamp(lateral_offset / anchor_norm_scale, low=0.0, high=1.5)
        center_norm = _clamp(center_distance / anchor_norm_scale, low=0.0, high=2.0)

        placement_index = max(0, _safe_int(payload.get("placement_candidate_index", 0), 0))
        rank_bonus = _clamp(float(candidate_count - min(candidate_count, placement_index + 1)) / float(candidate_count), low=0.0, high=1.0)
        intent_alignment = (
            forward_norm * forward_preference
            + lateral_norm * lateral_preference
            - center_norm * retreat_preference * 0.5
        )
        score_weight = _weight(intent, "score", 0.3)
        deny_weight = _weight(intent, "deny", 0.2)
        safety_weight = _weight(intent, "safety", 0.3)
        staging_weight = _weight(intent, "staging", 0.2)
        reserve_deny_weight = _weight(intent, "reserve_deny", 0.2)
        screen_weight = _weight(intent, "screen", 0.2)
        countercharge_weight = _weight(intent, "countercharge", 0.15)
        cover_weight = _weight(intent, "cover", 0.2)
        los_weight = _weight(intent, "los", 0.1)
        aura_weight = _weight(intent, "aura", 0.1)
        reserve_targets = float(len(list(intent.reserve_deny_targets or [])))
        threatened_lanes = float(len(list(intent.threatened_lane_ids or [])))
        objective_targets = float(len(list(intent.target_objective_ids or [])))
        score_next = score_weight * (0.18 + staging_weight * 0.24 + objective_targets * 0.03)
        score_next += score_weight * (intent_alignment * 0.14 + rank_bonus * 0.04)
        deny_next = deny_weight * (0.12 + reserve_deny_weight * 0.2 + reserve_targets * 0.05 + threatened_lanes * 0.03)
        deny_next += deny_weight * (max(0.0, forward_norm) * 0.09 + lateral_norm * (0.05 + lateral_preference * 0.04))
        control = (score_next + deny_next) * 0.72 + screen_weight * (0.08 + lateral_norm * 0.04)
        action_enable = staging_weight * (0.23 + max(0.0, forward_norm) * (0.16 + max(0.0, forward_preference) * 0.08))
        exposure_if_enemy_first = _clamp(
            0.55
            - safety_weight * 0.35
            - cover_weight * 0.2
            + max(0.0, forward_norm) * (0.22 + max(0.0, forward_preference) * 0.1)
            + center_norm * 0.08
            - retreat_preference * max(0.0, -forward_norm) * 0.12,
            low=0.0,
            high=1.6,
        )
        exposure = _clamp(
            -exposure_if_enemy_first + 0.04 + retreat_preference * max(0.0, -forward_norm) * 0.08,
            low=-2.0,
            high=2.0,
        )
        trade = _clamp(
            score_next * 0.32 + deny_next * 0.28 + countercharge_weight * 0.16 - exposure_if_enemy_first * 0.26,
            low=-3.0,
            high=3.0,
        )
        cover = _clamp(
            cover_weight * (0.18 - max(0.0, forward_norm) * 0.07 + retreat_preference * 0.03),
            low=-1.5,
            high=1.5,
        )
        los = _clamp(
            los_weight * (0.08 + max(0.0, forward_norm) * (0.1 + max(0.0, forward_preference) * 0.06) - retreat_preference * 0.04),
            low=-1.5,
            high=1.5,
        )
        resource = _clamp(
            -(reserve_deny_weight * (0.03 + max(0.0, forward_norm) * 0.03) + screen_weight * (0.02 + lateral_norm * 0.02)),
            low=-3.0,
            high=3.0,
        )
        reserve_denial_delta = reserve_deny_weight * (0.15 + reserve_targets * 0.05 + max(0.0, forward_norm) * 0.08 + lateral_norm * 0.05)
        screen_integrity_delta = screen_weight * (0.18 + threatened_lanes * 0.03 + lateral_norm * 0.08)
        countercharge_coverage_delta = countercharge_weight * (0.17 + max(0.0, forward_norm) * 0.06 + lateral_norm * 0.03)
        aura_connectivity_delta = aura_weight * (0.12 + _clamp(1.0 - center_norm, low=0.0, high=1.0) * 0.06)
        melee_staging_delta = staging_weight * (0.2 + max(0.0, forward_norm) * (0.2 + max(0.0, forward_preference) * 0.1))
        metadata = {
            "candidate_kind": "deployment_move",
            "solver_ms": 0,
            "fallback_mode": False,
            "intent_hash": intent.stable_hash(),
            "placement_candidate_id": str(payload.get("placement_candidate_id", "") or ""),
            "placement_candidate_index": int(placement_index),
            "candidate_count": int(candidate_count),
            "deployment_anchor_x": _round6(anchor_x),
            "deployment_anchor_y": _round6(anchor_y),
            "forward_progress_norm": _round6(forward_norm),
            "lateral_offset_norm": _round6(lateral_norm),
            "anchor_center_distance_norm": _round6(center_norm),
            "intent_alignment": _round6(intent_alignment),
            "rules_provenance_refs": [str(ctx.get("rules_bundle_id", "") or "")] if str(ctx.get("rules_bundle_id", "") or "") else [],
            "projected_score_delta_next_window": _round6(score_next),
            "projected_score_delta_round": _round6(score_next * 1.2),
            "projected_deny_delta_next_window": _round6(deny_next),
            "projected_control_delta": _round6(control),
            "projected_action_enablement_delta": _round6(action_enable),
            "projected_exposure_delta": _round6(exposure),
            "projected_trade_ev": _round6(trade),
            "cover_delta": _round6(cover),
            "los_delta": _round6(los),
            "resource_delta": _round6(resource),
            "reserve_denial_delta": _round6(reserve_denial_delta),
            "screen_integrity_delta": _round6(screen_integrity_delta),
            "countercharge_coverage_delta": _round6(countercharge_coverage_delta),
            "aura_connectivity_delta": _round6(aura_connectivity_delta),
            "projected_exposure_delta_if_enemy_goes_first": _round6(exposure_if_enemy_first),
            "projected_melee_staging_delta": _round6(melee_staging_delta),
        }
        candidates.append(
            CandidateAction(
                action_id=str(action_id),
                params=params,
                metadata=metadata,
            )
        )
    candidates.sort(key=lambda candidate: str(candidate.action_id))
    mask = [True] * len(candidates)
    return candidates, mask


def _solver_candidates(game: object, request: DecisionRequest, intent: DeploymentIntent) -> tuple[list[CandidateAction], list[bool]]:
    decision_type = str(getattr(request, "decision_type", "") or "")
    if decision_type == DECISION_CHOOSE_DEPLOYMENT_ZONE:
        return _deployment_zone_candidates(game, request, intent)
    if decision_type == DECISION_SELECT_NEXT_DEPLOY_UNIT:
        return _next_deploy_unit_candidates(game, request, intent)
    if decision_type == DECISION_DECLARE_RESERVES:
        return _reserves_candidates(game, request, intent)
    if decision_type == DECISION_SCOUT_MOVE:
        return _scout_move_candidates(game, request, intent)
    if decision_type == DECISION_MOVE_UNIT:
        placement_kind = str(dict(getattr(request, "context", {}) or {}).get("placement_kind", "") or "").strip().lower()
        if placement_kind == "deployment":
            return _deployment_move_candidates(game, request, intent)
    return _copy_request_candidates(request, fallback_mode=False)


@profiled_section("deployment.generate_candidates")
def generate_deployment_candidates(
    game: object,
    request: DecisionRequest,
    intent: DeploymentIntent,
) -> tuple[list[CandidateAction], list[bool], int, bool]:
    ctx = dict(getattr(request, "context", {}) or {})
    budget_ms = _safe_int(ctx.get("time_budget_ms", 0), 0)
    time_manager = getattr(game, "time_manager", None)
    if time_manager is None or budget_ms <= 0:
        start = time.perf_counter()
        candidates, mask = _solver_candidates(game, request, intent)
        candidates = _apply_deployment_lookahead(
            candidates,
            request=request,
            intent=intent,
        )
        wall_clock_ms = int(round((time.perf_counter() - start) * 1000.0))
        return candidates, mask, wall_clock_ms, False

    work_budget = time_manager.create_work_budget(
        str(getattr(request, "decision_type", "") or ""),
        context=ctx,
        fallback_units=budget_ms,
    )

    def _action(_budget: WorkBudget):
        candidates, mask = _solver_candidates(game, request, intent)
        candidates = _apply_deployment_lookahead(
            candidates,
            request=request,
            intent=intent,
        )
        return candidates, mask

    def _fallback():
        return _copy_request_candidates(request, fallback_mode=True)

    (candidates, mask), fallback_mode, wall_clock_ms = time_manager.run_with_time_budget(
        budget_ms=budget_ms,
        action=_action,
        fallback=_fallback,
        work_budget=work_budget,
    )
    if hasattr(request, "context"):
        request.context.update(work_budget.to_context())
    return candidates, mask, int(wall_clock_ms), bool(fallback_mode)
