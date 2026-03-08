from __future__ import annotations

import time
from typing import Any

from .decision_kinds import (
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_MOVE_UNIT,
    DECISION_SELECT_NEXT_DEPLOY_UNIT,
)
from .decisions import CandidateAction, DecisionOption, DecisionRequest
from .deployment_intent import DeploymentIntent


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
    zone_type_norm = str(zone_type or "").strip().lower()
    defender_bias = 0.08 if zone_type_norm == "defender" else 0.0
    attacker_bias = 0.07 if zone_type_norm == "attacker" else 0.0

    score_next = score_weight * (0.22 + area_norm * 0.23 + objective_count * 0.03 + staging_weight * 0.2 + defender_bias)
    deny_next = deny_weight * (0.16 + reserve_target_count * 0.04 + lane_count * 0.03 + reserve_deny_weight * 0.22 + defender_bias)
    control = (score_next + deny_next) * 0.72 + screen_weight * (0.06 + frontage_norm * 0.05)
    action_enable = staging_weight * (0.14 + depth_norm * 0.18 + affordance_count * 0.03 + attacker_bias * 0.5)

    exposure_if_enemy_first = _clamp(
        0.62
        - safety_weight * 0.35
        - cover_weight * 0.2
        - area_norm * 0.1
        - depth_norm * 0.08
        + attacker_bias * 0.45,
        low=0.0,
        high=1.4,
    )
    exposure = _clamp(-exposure_if_enemy_first + defender_bias - attacker_bias * 0.35, low=-2.0, high=2.0)
    trade = _clamp(score_next * 0.38 + deny_next * 0.3 + countercharge_weight * 0.22 - exposure_if_enemy_first * 0.28, low=-3.0, high=3.0)
    cover = _clamp(cover_weight * (0.14 + area_norm * 0.08 + defender_bias), low=-1.5, high=1.5)
    los = _clamp(los_weight * (0.05 + frontage_norm * 0.09 + attacker_bias * 0.6 - defender_bias * 0.35), low=-1.5, high=1.5)
    resource = _clamp(-(reserve_deny_weight * 0.04 + screen_weight * 0.03), low=-3.0, high=3.0)

    reserve_denial_delta = reserve_deny_weight * (0.2 + reserve_target_count * 0.05 + area_norm * 0.09)
    screen_integrity_delta = screen_weight * (0.19 + frontage_norm * 0.14 + lane_count * 0.03)
    countercharge_coverage_delta = countercharge_weight * (0.14 + depth_norm * 0.11)
    aura_connectivity_delta = aura_weight * (0.1 + area_norm * 0.05 + objective_count * 0.02)
    melee_staging_delta = staging_weight * (0.16 + depth_norm * 0.21 + attacker_bias * 0.45)

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
        projection = _zone_projection(
            intent=intent,
            zone_type=zone_type,
            area_estimate=area_estimate,
            frontage_estimate=frontage_estimate,
            depth_estimate=depth_estimate,
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


def _deployment_move_candidates(game: object, request: DecisionRequest, intent: DeploymentIntent) -> tuple[list[CandidateAction], list[bool]]:
    del game
    ctx = dict(getattr(request, "context", {}) or {})
    model_positions = list(ctx.get("deployment_model_positions", []) or [])
    if not model_positions:
        return _copy_request_candidates(request, fallback_mode=False)
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
        params = dict(payload)
        params["model_positions"] = model_positions
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
        score_next = score_weight * (0.2 + staging_weight * 0.25 + objective_targets * 0.03)
        deny_next = deny_weight * (0.14 + reserve_deny_weight * 0.2 + reserve_targets * 0.05 + threatened_lanes * 0.03)
        control = (score_next + deny_next) * 0.72 + screen_weight * 0.08
        action_enable = staging_weight * 0.25
        exposure_if_enemy_first = _clamp(0.55 - safety_weight * 0.35 - cover_weight * 0.2, low=0.0, high=1.4)
        exposure = _clamp(-exposure_if_enemy_first + 0.04, low=-2.0, high=2.0)
        trade = _clamp(score_next * 0.32 + deny_next * 0.28 + countercharge_weight * 0.16 - exposure_if_enemy_first * 0.26, low=-3.0, high=3.0)
        metadata = {
            "candidate_kind": "deployment_move",
            "solver_ms": 0,
            "fallback_mode": False,
            "intent_hash": intent.stable_hash(),
            "rules_provenance_refs": [str(ctx.get("rules_bundle_id", "") or "")] if str(ctx.get("rules_bundle_id", "") or "") else [],
            "projected_score_delta_next_window": _round6(score_next),
            "projected_score_delta_round": _round6(score_next * 1.2),
            "projected_deny_delta_next_window": _round6(deny_next),
            "projected_control_delta": _round6(control),
            "projected_action_enablement_delta": _round6(action_enable),
            "projected_exposure_delta": _round6(exposure),
            "projected_trade_ev": _round6(trade),
            "cover_delta": _round6(_clamp(cover_weight * 0.2, low=-1.5, high=1.5)),
            "los_delta": _round6(_clamp(los_weight * 0.1, low=-1.5, high=1.5)),
            "resource_delta": _round6(_clamp(-(reserve_deny_weight * 0.03 + screen_weight * 0.02), low=-3.0, high=3.0)),
            "reserve_denial_delta": _round6(reserve_deny_weight * (0.15 + reserve_targets * 0.05)),
            "screen_integrity_delta": _round6(screen_weight * (0.18 + threatened_lanes * 0.03)),
            "countercharge_coverage_delta": _round6(countercharge_weight * 0.18),
            "aura_connectivity_delta": _round6(aura_weight * 0.12),
            "projected_exposure_delta_if_enemy_goes_first": _round6(exposure_if_enemy_first),
            "projected_melee_staging_delta": _round6(staging_weight * 0.2),
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
    if decision_type == DECISION_MOVE_UNIT:
        placement_kind = str(dict(getattr(request, "context", {}) or {}).get("placement_kind", "") or "").strip().lower()
        if placement_kind == "deployment":
            return _deployment_move_candidates(game, request, intent)
    return _copy_request_candidates(request, fallback_mode=False)


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
        wall_clock_ms = int(round((time.perf_counter() - start) * 1000.0))
        return candidates, mask, wall_clock_ms, False

    def _action(_deadline: float):
        return _solver_candidates(game, request, intent)

    def _fallback():
        return _copy_request_candidates(request, fallback_mode=True)

    (candidates, mask), fallback_mode, wall_clock_ms = time_manager.run_with_time_budget(
        budget_ms=budget_ms,
        action=_action,
        fallback=_fallback,
    )
    return candidates, mask, int(wall_clock_ms), bool(fallback_mode)
