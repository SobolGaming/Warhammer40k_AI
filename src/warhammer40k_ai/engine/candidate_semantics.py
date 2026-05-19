from __future__ import annotations

import hashlib
from typing import Any, Mapping

from .decisions import CandidateAction, DecisionRequest
from .decision_kinds import (
    DECISION_ALLOCATE_DAMAGE,
    DECISION_ALLOCATE_MELEE_TARGETS,
    DECISION_ALLOCATE_TARGETS,
    DECISION_DECLARE_CHARGE,
    DECISION_DECLARE_MELEE_WEAPONS,
    DECISION_DECLARE_SHOTS,
    DECISION_MOVE_UNIT,
    DECISION_PICK_OBJECTIVE,
    DECISION_PICK_POINT,
    DECISION_REROLL_ROLL,
    DECISION_PICK_TERRAIN_FEATURE,
    DECISION_SELECT_DICE_REROLL,
    DECISION_SELECT_FIGHT_TARGETS,
    DECISION_SELECT_MOVEMENT_ACTION,
    DECISION_SELECT_UNIT,
    DECISION_SELECT_TARGET_MODEL,
    DECISION_SPLIT_ATTACKS,
)


SEMANTIC_NUMERIC_KEYS = (
    "projected_score_delta_next_window",
    "projected_score_delta_round",
    "projected_deny_delta_next_window",
    "projected_control_delta",
    "projected_action_enablement_delta",
    "projected_exposure_delta",
    "projected_trade_ev",
    "cover_delta",
    "los_delta",
    "resource_delta",
)

_MOVEMENT_DECISION_TYPES = frozenset(
    (
        DECISION_MOVE_UNIT,
        DECISION_SELECT_MOVEMENT_ACTION,
    )
)

_TARGETING_DECISION_TYPES = frozenset(
    (
        DECISION_DECLARE_SHOTS,
        DECISION_SELECT_TARGET_MODEL,
        DECISION_ALLOCATE_TARGETS,
        DECISION_PICK_OBJECTIVE,
        DECISION_PICK_POINT,
        DECISION_PICK_TERRAIN_FEATURE,
    )
)

_CHARGE_DECISION_TYPES = frozenset((DECISION_DECLARE_CHARGE,))

_FIGHT_DECISION_TYPES = frozenset(
    (
        DECISION_SELECT_UNIT,
        DECISION_SELECT_FIGHT_TARGETS,
        DECISION_DECLARE_MELEE_WEAPONS,
        DECISION_ALLOCATE_MELEE_TARGETS,
        DECISION_SPLIT_ATTACKS,
        DECISION_ALLOCATE_DAMAGE,
    )
)

_REROLL_DECISION_TYPES = frozenset(
    (
        DECISION_REROLL_ROLL,
        DECISION_SELECT_DICE_REROLL,
    )
)


def _round6(value: float) -> float:
    return float(round(float(value), 6))


def _clamp(value: float, *, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


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


def _count_items(value: object) -> int:
    if isinstance(value, (list, tuple, set, dict)):
        return int(len(value))
    if value is None:
        return 0
    return 1 if str(value).strip() else 0


def _is_non_noop_candidate(params: dict[str, Any], metadata: Mapping[str, Any] | None = None) -> bool:
    action = str(params.get("action", "") or "").strip().lower()
    if action in ("skip", "none", "noop", "pass"):
        return False
    if action:
        return True
    if metadata is not None and str(metadata.get("candidate_kind", "") or "").strip().lower() == "noop":
        return False
    if "choice" in params:
        return True
    return bool(params)


def _stable_scalar(seed: str, *, minimum: float = 0.85, maximum: float = 1.15) -> float:
    encoded = str(seed or "").encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    max_u64 = float(16**16 - 1)
    ratio = int(digest[:16], 16) / max_u64 if max_u64 > 0 else 0.0
    return float(minimum + (maximum - minimum) * ratio)


def _bundle_scalars(
    *,
    rules_bundle_id: str,
    rules_bundle: Mapping[str, Any] | None,
) -> dict[str, float]:
    bundle = dict(rules_bundle or {})
    core_id = str(bundle.get("core_rules_id", "") or rules_bundle_id or "unknown_core_rules")
    commentary_id = str(bundle.get("rules_commentary_id", "") or rules_bundle_id or "unknown_rules_commentary")
    mission_id = str(bundle.get("mission_pack_id", "") or rules_bundle_id or "unknown_mission_pack")
    terrain_id = str(bundle.get("terrain_pack_id", "") or rules_bundle_id or "unknown_terrain_pack")
    dataslate_id = str(bundle.get("dataslate_id", "") or rules_bundle_id or "unknown_dataslate")
    points_id = str(bundle.get("points_id", "") or rules_bundle_id or "unknown_points")
    faction_id = str(bundle.get("faction_pack_id", "") or rules_bundle_id or "unknown_faction_pack")
    detachment_id = str(bundle.get("detachment_pack_id", "") or rules_bundle_id or "unknown_detachment_pack")
    return {
        "score": _stable_scalar(f"{core_id}|{mission_id}"),
        "deny": _stable_scalar(f"{commentary_id}|{mission_id}"),
        "control": _stable_scalar(f"{mission_id}|{terrain_id}|{core_id}"),
        "combat": _stable_scalar(f"{dataslate_id}|{points_id}|{faction_id}"),
        "tool": _stable_scalar(f"{detachment_id}|{faction_id}|{commentary_id}"),
        "terrain": _stable_scalar(f"{terrain_id}|{core_id}"),
        "resource": _stable_scalar(f"{points_id}|{dataslate_id}"),
    }


def _extract_target_count(params: Mapping[str, Any], context: Mapping[str, Any]) -> int:
    target_ids: set[str] = set()
    for key in ("target_unit_ids", "allowed_target_unit_ids"):
        raw = params.get(key)
        if isinstance(raw, (list, tuple, set)):
            target_ids.update(str(item) for item in raw if str(item))
    single = params.get("target_unit_id")
    if single is not None and str(single):
        target_ids.add(str(single))
    allocations = params.get("target_allocations")
    if isinstance(allocations, dict):
        target_ids.update(str(key) for key in allocations.keys() if str(key))
    split_allocations = params.get("split_allocations")
    if isinstance(split_allocations, dict):
        target_ids.update(str(key) for key in split_allocations.keys() if str(key))
    if target_ids:
        return int(len(target_ids))
    ctx_allowed = context.get("allowed_target_unit_ids")
    if isinstance(ctx_allowed, (list, tuple, set)):
        return int(len([item for item in ctx_allowed if str(item)]))
    return 0


def _extract_weapon_bundle_count(params: Mapping[str, Any]) -> int:
    for key in ("weapon_bundles", "weapon_declarations", "attack_declarations"):
        value = params.get(key)
        if isinstance(value, list):
            return int(len(value))
    return 0


def _extract_attack_volume(params: Mapping[str, Any]) -> float:
    volume = 0.0
    split_allocations = params.get("split_allocations")
    if isinstance(split_allocations, dict):
        volume += float(sum(max(0, _safe_int(v, 0)) for v in split_allocations.values()))
    declarations = params.get("attack_declarations")
    if isinstance(declarations, list):
        for entry in declarations:
            if isinstance(entry, dict):
                volume += max(1, _safe_int(entry.get("attacks_override"), 1))
    if volume > 0:
        return float(volume)
    bundles = params.get("weapon_bundles")
    if isinstance(bundles, list):
        return float(len(bundles))
    return 0.0


def _extract_shot_volume(params: Mapping[str, Any]) -> float:
    declared = params.get("declared_shots")
    if isinstance(declared, list):
        shot_total = 0.0
        for entry in declared:
            if isinstance(entry, dict):
                shot_total += max(1.0, _safe_float(entry.get("shots"), 1.0))
        if shot_total > 0:
            return float(shot_total)
        return float(len(declared))
    explicit = params.get("shot_count")
    if explicit is not None:
        return float(max(0, _safe_int(explicit, 0)))
    return 0.0


def _extract_resource_cost(
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    context: Mapping[str, Any],
) -> float:
    for source in (params, metadata, context):
        for key in ("cp_cost", "command_points", "resource_cost", "cost"):
            if key in source:
                return max(0.0, _safe_float(source.get(key), 0.0))
    return 0.0


def _dictish(value: object) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _string_set(value: object) -> set[str]:
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value if str(item)}
    if value is None:
        return set()
    text = str(value)
    return {text} if text else set()


def _normalized_movement_action(value: object) -> str:
    action = str(value or "").strip().lower()
    aliases = {
        "normal": "move",
        "normal_move": "move",
        "remain_stationary": "stationary",
        "stationary": "stationary",
        "advance": "advance",
        "fall_back": "fall_back",
        "fallback": "fall_back",
        "move": "move",
    }
    return aliases.get(action, action)


def _candidate_movement_action(params: Mapping[str, Any], metadata: Mapping[str, Any]) -> str:
    for source in (params, metadata):
        for key in (
            "action_type",
            "planned_movement_type",
            "movement_type",
            "desired_action",
            "action",
        ):
            action = _normalized_movement_action(source.get(key))
            if action:
                return action
    kind = str(metadata.get("candidate_kind", "") or "").strip().lower()
    for suffix in ("advance", "fall_back", "stationary", "move"):
        if suffix in kind:
            return _normalized_movement_action(suffix)
    return ""


def _visible_unit_ids(params: Mapping[str, Any], metadata: Mapping[str, Any]) -> set[str] | None:
    for source in (metadata, params):
        for key in (
            "visible_target_unit_ids",
            "los_to_unit_ids",
            "line_of_sight_unit_ids",
            "commander_los_to_unit_ids",
        ):
            if key in source:
                return _string_set(source.get(key))
    return None


def _candidate_supports_required_los(
    *,
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    required_unit_ids: list[str],
) -> bool | None:
    if not required_unit_ids:
        return None
    explicit = metadata.get("commander_required_los_satisfied")
    if explicit is not None:
        return bool(explicit)
    visible = _visible_unit_ids(params, metadata)
    if visible is None:
        return None
    return set(required_unit_ids).issubset(visible)


def _range_by_target(params: Mapping[str, Any], metadata: Mapping[str, Any]) -> dict[str, float]:
    ranges: dict[str, float] = {}
    for source in (metadata, params):
        for key in (
            "range_to_unit_inches_by_id",
            "distance_to_unit_inches_by_id",
            "target_range_inches_by_id",
            "target_distance_inches_by_id",
        ):
            raw = source.get(key)
            if not isinstance(raw, dict):
                continue
            for target_id, distance in sorted(raw.items(), key=lambda item: str(item[0])):
                ranges[str(target_id)] = _safe_float(distance, 0.0)
    return ranges


def _candidate_satisfies_range_bands(
    *,
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    desired_range_bands: list[dict[str, Any]],
) -> bool | None:
    if not desired_range_bands:
        return None
    explicit = metadata.get("commander_desired_range_band_satisfied")
    if explicit is not None:
        return bool(explicit)
    ranges = _range_by_target(params, metadata)
    if not ranges:
        return None
    for band in desired_range_bands:
        target_id = str(band.get("target_unit_id", "") or "")
        if not target_id or target_id not in ranges:
            continue
        distance = float(ranges[target_id])
        minimum = band.get("minimum_inches")
        maximum = band.get("maximum_inches")
        if minimum is not None and distance < _safe_float(minimum, 0.0):
            continue
        if maximum is not None and distance > _safe_float(maximum, 0.0):
            continue
        return True
    return False


def _charge_lane_score(
    *,
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    target_unit_id: str,
) -> float:
    if not target_unit_id:
        return 0.0
    explicit = metadata.get("commander_charge_lane_score")
    if explicit is not None:
        return _clamp(_safe_float(explicit, 0.0), low=0.0, high=1.0)
    for source in (metadata, params):
        for key in (
            "charge_staging_target_unit_ids",
            "near_charge_target_unit_ids",
            "engaged_target_unit_ids",
        ):
            if target_unit_id in _string_set(source.get(key)):
                return 1.0
    distance = _range_by_target(params, metadata).get(target_unit_id)
    if distance is None:
        return 0.0
    return _clamp((12.0 - float(distance)) / 12.0, low=0.0, high=1.0)


def _commander_plan_stale(context: Mapping[str, Any]) -> bool:
    scope = str(context.get("commander_replan_scope", "") or "").strip().lower()
    if scope in {"movement_only", "phase", "full_round"}:
        return True
    dirty = _dictish(context.get("commander_dirty_flags"))
    return bool(
        dirty.get("movement_plan_dirty", False)
        or dirty.get("objective_priorities_dirty", False)
        or dirty.get("full_replan_required", False)
    )


def _commander_movement_metadata(
    *,
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    movement_task = _dictish(context.get("commander_movement_task"))
    unit_task = _dictish(context.get("unit_battle_task"))
    fire_assignment = _dictish(context.get("commander_fire_assignment"))
    charge_assignment = _dictish(context.get("commander_charge_assignment"))
    if not any((movement_task, unit_task, fire_assignment, charge_assignment)):
        return {}

    action = _candidate_movement_action(params, metadata)
    desired_action = _normalized_movement_action(movement_task.get("desired_action"))
    forbidden_actions = {
        _normalized_movement_action(value)
        for value in list(unit_task.get("forbidden_movement_actions", []) or [])
        if _normalized_movement_action(value)
    }
    required_los_ids = [
        str(value)
        for value in list(movement_task.get("required_los_to_unit_ids", []) or [])
        if str(value)
    ]
    desired_range_bands = [
        dict(value)
        for value in list(movement_task.get("desired_range_bands", []) or [])
        if isinstance(value, dict)
    ]
    avoid_shooting_ineligible = bool(movement_task.get("avoid_becoming_shooting_ineligible", False))
    accept_shooting_ineligible = bool(movement_task.get("intentionally_accept_shooting_ineligible", False))
    charge_target_id = str(
        movement_task.get("charge_staging_target_unit_id")
        or charge_assignment.get("primary_target_unit_id")
        or ""
    )
    fire_target_id = str(fire_assignment.get("primary_target_unit_id") or "")

    alignment = 0.0
    action_violation = 0.0
    if desired_action and action:
        alignment += 0.4 if action == desired_action else -0.15
    if action and action in forbidden_actions:
        action_violation = 1.0
        alignment -= 0.8
    intentional_ineligible = 1.0 if accept_shooting_ineligible and action == "advance" else 0.0
    if avoid_shooting_ineligible and action == "advance" and not accept_shooting_ineligible:
        action_violation = 1.0
        alignment -= 0.8
    if intentional_ineligible:
        alignment += 0.55

    los_satisfied = _candidate_supports_required_los(
        params=params,
        metadata=metadata,
        required_unit_ids=required_los_ids,
    )
    if los_satisfied is True:
        alignment += 0.4
    elif los_satisfied is False:
        alignment -= 0.25

    range_satisfied = _candidate_satisfies_range_bands(
        params=params,
        metadata=metadata,
        desired_range_bands=desired_range_bands,
    )
    if range_satisfied is True:
        alignment += 0.35
    elif range_satisfied is False:
        alignment -= 0.15

    charge_lane = _charge_lane_score(
        params=params,
        metadata=metadata,
        target_unit_id=charge_target_id,
    )
    if charge_lane > 0.0:
        alignment += 0.35 * charge_lane

    expected_damage = 0.0
    damage_by_target = _dictish(fire_assignment.get("expected_damage_by_target"))
    if fire_target_id:
        expected_damage = _safe_float(damage_by_target.get(fire_target_id), 0.0)
        if fire_target_id in required_los_ids:
            alignment += 0.1
    desired_charge_probability = _safe_float(charge_assignment.get("desired_charge_probability"), 0.0)
    future_phase_ev = _clamp(
        expected_damage / 8.0 + desired_charge_probability + intentional_ineligible * 0.35,
        low=0.0,
        high=3.0,
    )
    alignment += min(0.25, future_phase_ev * 0.1)

    stale = _commander_plan_stale(context)
    if stale:
        alignment *= 0.25

    return {
        "commander_task_alignment": _round6(_clamp(alignment, low=-2.0, high=2.0)),
        "commander_action_violation": _round6(action_violation),
        "commander_required_los_satisfied": 1.0 if los_satisfied is True else 0.0,
        "commander_desired_range_band_satisfied": 1.0 if range_satisfied is True else 0.0,
        "commander_charge_lane_score": _round6(charge_lane),
        "commander_intentional_shooting_ineligible": _round6(intentional_ineligible),
        "commander_future_phase_ev": _round6(future_phase_ev),
        "commander_plan_stale_penalty": 1.0 if stale else 0.0,
    }


def _text_blob(*sources: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for source in sources:
        for key in (
            "ability_key",
            "ability_name",
            "choice",
            "effect_category",
            "semantic_tags",
            "tool_id",
            "tool_type",
            "source",
            "label",
        ):
            value = source.get(key)
            if isinstance(value, (list, tuple, set)):
                parts.extend(str(item) for item in value if str(item))
            elif value is not None and str(value):
                parts.append(str(value))
    return " ".join(parts).strip().lower()


def _contains_any(haystack: str, needles: tuple[str, ...]) -> bool:
    if not haystack:
        return False
    return any(token in haystack for token in needles)


def _tool_descriptor_ids(context: Mapping[str, Any]) -> list[str]:
    direct = context.get("tool_descriptor_ids")
    if isinstance(direct, list):
        return [str(item) for item in direct if str(item)]
    descriptor_ids = context.get("descriptor_ids")
    if isinstance(descriptor_ids, dict):
        nested = descriptor_ids.get("tool_descriptor_ids")
        if isinstance(nested, list):
            return [str(item) for item in nested if str(item)]
    return []


def _roll_state_data(context: Mapping[str, Any]) -> dict[str, Any]:
    state = context.get("roll_state")
    return dict(state or {}) if isinstance(state, dict) else {}


def _roll_spec_data(context: Mapping[str, Any]) -> dict[str, Any]:
    spec: dict[str, Any] = {}
    state = _roll_state_data(context)
    state_spec = state.get("spec")
    if isinstance(state_spec, dict):
        spec.update(dict(state_spec or {}))
    context_spec = context.get("roll_spec")
    if isinstance(context_spec, dict):
        for key, value in dict(context_spec or {}).items():
            spec.setdefault(str(key), value)
    return spec


def _base_roll_dice(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    state = _roll_state_data(context)
    dice = state.get("dice")
    if not isinstance(dice, list):
        return []
    result: list[dict[str, Any]] = []
    for entry in list(dice or []):
        if not isinstance(entry, dict):
            continue
        if bool(entry.get("is_derived", False)):
            continue
        result.append(dict(entry or {}))
    return result


def _die_directional_rank(die: Mapping[str, Any], *, higher_is_better: bool) -> float:
    value = _safe_float(die.get("value"), 0.0)
    return -value if higher_is_better else value


def _success_from_op(value: float, target: float, op: str) -> bool:
    operator = str(op or "gte").strip().lower()
    if operator == "gt":
        return float(value) > float(target)
    if operator == "gte":
        return float(value) >= float(target)
    if operator == "lt":
        return float(value) < float(target)
    if operator == "lte":
        return float(value) <= float(target)
    if operator == "eq":
        return float(value) == float(target)
    return False


def _higher_is_better_for_roll(spec: Mapping[str, Any]) -> bool:
    sum_op = str(spec.get("sum_op", "") or "").strip().lower()
    if sum_op in {"lt", "lte"}:
        return False
    if sum_op in {"gt", "gte"}:
        return True
    target_op = str(spec.get("target_op", "") or "").strip().lower()
    if target_op in {"lt", "lte"}:
        return False
    if target_op in {"gt", "gte"}:
        return True
    roll_type = str(spec.get("roll_type", "") or "").strip().lower()
    if roll_type in {"battle_shock", "desperate_escape"}:
        return False
    return True


def _selected_reroll_dice(
    params: Mapping[str, Any],
    context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    mode = str(params.get("mode", "") or "").strip().lower()
    source = str(params.get("source", "") or "").strip().lower()
    if mode in {"", "none"} or source == "none":
        return []
    dice = _base_roll_dice(context)
    if not dice:
        return []
    dice_by_id = {
        str(die.get("die_id", "") or ""): die
        for die in dice
        if str(die.get("die_id", "") or "")
    }
    eligible_ids = [
        str(die_id or "")
        for die_id in list(params.get("eligible_die_ids", []) or [])
        if str(die_id or "")
    ]
    eligible_dice = [dice_by_id[die_id] for die_id in eligible_ids if die_id in dice_by_id]
    if not eligible_dice:
        eligible_dice = list(dice)
    if mode in {"all", "whole"}:
        return eligible_dice

    spec = _roll_spec_data(context)
    higher_is_better = _higher_is_better_for_roll(spec)
    per_die_success = dict(_roll_state_data(context).get("per_die_success", {}) or {})
    failed = [
        die
        for die in eligible_dice
        if per_die_success.get(str(die.get("die_id", "") or ""), None) is False
    ]
    candidate_pool = failed or eligible_dice
    if mode in {"values", "ones", "any"}:
        return sorted(candidate_pool, key=lambda die: _die_directional_rank(die, higher_is_better=higher_is_better))
    if mode in {"one", "single", "select"}:
        chosen = min(candidate_pool, key=lambda die: _die_directional_rank(die, higher_is_better=higher_is_better))
        return [chosen]
    return eligible_dice


def _expected_single_die_success_probability(faces: int, *, target: float, op: str) -> float:
    face_count = max(1, int(faces or 1))
    success = 0
    for value in range(1, face_count + 1):
        if _success_from_op(float(value), float(target), op):
            success += 1
    return float(success) / float(face_count)


def _expected_sum_success_probability(
    *,
    fixed_total: float,
    reroll_faces: list[int],
    target: float,
    op: str,
    modifier: float,
) -> float:
    if not reroll_faces:
        return 1.0 if _success_from_op(float(fixed_total + modifier), float(target), op) else 0.0
    distribution: dict[int, float] = {0: 1.0}
    for faces in list(reroll_faces or []):
        face_count = max(1, int(faces or 1))
        next_distribution: dict[int, float] = {}
        for subtotal, probability in distribution.items():
            for value in range(1, face_count + 1):
                new_total = int(subtotal + value)
                next_distribution[new_total] = float(next_distribution.get(new_total, 0.0) + probability / float(face_count))
        distribution = next_distribution
    success_probability = 0.0
    for subtotal, probability in distribution.items():
        final_total = float(fixed_total + subtotal + modifier)
        if _success_from_op(final_total, float(target), op):
            success_probability += float(probability)
    return float(success_probability)


def _normalized_progress(total: float, *, low: float, high: float, higher_is_better: bool) -> float:
    if float(high) <= float(low):
        return 0.0
    if higher_is_better:
        return _clamp((float(total) - float(low)) / (float(high) - float(low)), low=0.0, high=1.0)
    return _clamp((float(high) - float(total)) / (float(high) - float(low)), low=0.0, high=1.0)


def _projection_for_reroll(
    *,
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    context: Mapping[str, Any],
    scalars: Mapping[str, float],
) -> dict[str, float]:
    del metadata  # Reroll projection is driven by the concrete roll snapshot.
    mode = str(params.get("mode", "") or "").strip().lower()
    source = str(params.get("source", "") or "").strip().lower()
    cp_cost = max(0.0, _extract_resource_cost(params, {}, context))
    if mode in {"", "none"} or source == "none":
        return {
            "projected_score_delta_next_window": 0.0,
            "projected_score_delta_round": 0.0,
            "projected_deny_delta_next_window": 0.0,
            "projected_control_delta": 0.0,
            "projected_action_enablement_delta": 0.0,
            "projected_exposure_delta": 0.0,
            "projected_trade_ev": 0.0,
            "cover_delta": 0.0,
            "los_delta": 0.0,
            "resource_delta": 0.0,
        }

    spec = _roll_spec_data(context)
    roll_state = _roll_state_data(context)
    selected_dice = _selected_reroll_dice(params, context)
    if not selected_dice:
        return {
            "projected_score_delta_next_window": 0.0,
            "projected_score_delta_round": 0.0,
            "projected_deny_delta_next_window": 0.0,
            "projected_control_delta": 0.0,
            "projected_action_enablement_delta": 0.0,
            "projected_exposure_delta": 0.0,
            "projected_trade_ev": 0.0,
            "cover_delta": 0.0,
            "los_delta": 0.0,
            "resource_delta": _round6(_clamp(-cp_cost, low=-3.0, high=0.0)),
        }

    higher_is_better = _higher_is_better_for_roll(spec)
    sum_modifier = _safe_float(spec.get("sum_modifier"), 0.0)
    current_total = _safe_float(roll_state.get("total"), 0.0)
    if current_total == 0.0:
        current_total = sum(_safe_float(die.get("value"), 0.0) for die in _base_roll_dice(context))
    current_total_effective = float(current_total + sum_modifier)

    success_delta = 0.0
    progress_delta = 0.0
    sum_target = spec.get("sum_target")
    sum_op = str(spec.get("sum_op", "") or "").strip().lower()
    if sum_target is not None and sum_op:
        selected_ids = {str(die.get("die_id", "") or "") for die in list(selected_dice or [])}
        fixed_total = sum(
            _safe_float(die.get("value"), 0.0)
            for die in _base_roll_dice(context)
            if str(die.get("die_id", "") or "") not in selected_ids
        )
        reroll_faces = [max(1, _safe_int(die.get("faces"), 6)) for die in list(selected_dice or [])]
        expected_success = _expected_sum_success_probability(
            fixed_total=fixed_total,
            reroll_faces=reroll_faces,
            target=_safe_float(sum_target, 0.0),
            op=sum_op,
            modifier=sum_modifier,
        )
        current_success = roll_state.get("sum_success")
        if current_success is None:
            current_success = _success_from_op(current_total_effective, _safe_float(sum_target, 0.0), sum_op)
        success_delta = float(expected_success) - (1.0 if bool(current_success) else 0.0)
        expected_selected_total = sum((float(max(1, _safe_int(die.get("faces"), 6))) + 1.0) / 2.0 for die in list(selected_dice or []))
        expected_total = float(fixed_total + expected_selected_total + sum_modifier)
        min_total = float(fixed_total + len(reroll_faces) + sum_modifier)
        max_total = float(fixed_total + sum(reroll_faces) + sum_modifier)
        progress_delta = _normalized_progress(
            expected_total,
            low=min_total,
            high=max_total,
            higher_is_better=higher_is_better,
        ) - _normalized_progress(
            current_total_effective,
            low=min_total,
            high=max_total,
            higher_is_better=higher_is_better,
        )
    else:
        target = spec.get("target")
        target_op = str(spec.get("target_op", "") or "").strip().lower()
        current_successes = 0.0
        expected_successes = 0.0
        current_progress = 0.0
        expected_progress = 0.0
        for die in list(selected_dice or []):
            faces = max(1, _safe_int(die.get("faces"), 6))
            current_value = _safe_float(die.get("value"), 0.0)
            current_progress += _normalized_progress(
                current_value,
                low=1.0,
                high=float(faces),
                higher_is_better=higher_is_better,
            )
            expected_progress += _normalized_progress(
                (float(faces) + 1.0) / 2.0,
                low=1.0,
                high=float(faces),
                higher_is_better=higher_is_better,
            )
            if target is not None and target_op:
                current_successes += 1.0 if _success_from_op(current_value, _safe_float(target, 0.0), target_op) else 0.0
                expected_successes += _expected_single_die_success_probability(
                    faces,
                    target=_safe_float(target, 0.0),
                    op=target_op,
                )
        selected_count = float(max(1, len(selected_dice)))
        success_delta = float(expected_successes - current_successes) / selected_count
        progress_delta = float(expected_progress - current_progress) / selected_count

    benefit = _clamp(success_delta * 1.6 + progress_delta * 0.9, low=-2.0, high=2.0)
    roll_type = str(spec.get("roll_type", "") or "").strip().lower()
    action_enable = benefit * (0.7 if roll_type in {"advance", "charge"} else 0.25)
    control = benefit * (0.65 if roll_type == "battle_shock" else 0.15)
    deny = benefit * (0.45 if roll_type == "battle_shock" else 0.0)
    trade = benefit * (0.8 if roll_type in {"hit", "wound", "damage", "save", "charge"} else 0.45)
    score_next = benefit * (1.0 if roll_type != "battle_shock" else 0.8)
    score_round = benefit * 0.85
    resource = -cp_cost
    return {
        "projected_score_delta_next_window": _round6(_clamp(score_next, low=-3.0, high=3.0)),
        "projected_score_delta_round": _round6(_clamp(score_round, low=-3.0, high=3.0)),
        "projected_deny_delta_next_window": _round6(_clamp(deny, low=-3.0, high=3.0)),
        "projected_control_delta": _round6(_clamp(control, low=-3.0, high=3.0)),
        "projected_action_enablement_delta": _round6(_clamp(action_enable, low=-3.0, high=3.0)),
        "projected_exposure_delta": 0.0,
        "projected_trade_ev": _round6(_clamp(trade, low=-3.0, high=3.0)),
        "cover_delta": 0.0,
        "los_delta": 0.0,
        "resource_delta": _round6(_clamp(resource, low=-3.0, high=0.0)),
    }


def _projection_for_movement(
    *,
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    context: Mapping[str, Any],
    scalars: Mapping[str, float],
) -> dict[str, float]:
    active = 1.0 if _is_non_noop_candidate(dict(params), metadata) else 0.0
    intent = context.get("movement_intent")
    intent_data = dict(intent) if isinstance(intent, dict) else {}
    weights = dict(intent_data.get("weights", {}) or {})
    score_weight = max(0.0, _safe_float(weights.get("score"), 0.0))
    deny_weight = max(0.0, _safe_float(weights.get("deny"), 0.0))
    safety_weight = max(0.0, _safe_float(weights.get("safety"), 0.0))
    coherency_weight = max(0.0, _safe_float(weights.get("coherency"), 0.0))
    action_enable_weight = max(0.0, _safe_float(weights.get("action_enable"), 0.0))
    trade_weight = max(0.0, _safe_float(weights.get("trade"), 0.0))

    region_count = float(_count_items(intent_data.get("target_region_ids")))
    opportunity_count = float(_count_items(intent_data.get("target_opportunity_ids")))
    affordance_count = float(_count_items(intent_data.get("desired_affordances")))
    screen_count = float(_count_items(intent_data.get("screen_deny_targets")))
    score_window_state = context.get("score_window_state")
    score_window_data = dict(score_window_state) if isinstance(score_window_state, dict) else {}
    window_count = max(1.0, float(_count_items(score_window_data.get("windows"))))
    threat_hint = max(
        0.0,
        _safe_float(
            metadata.get(
                "threat_exposure_score",
                metadata.get("threat_score", 0.0),
            ),
            0.0,
        ),
    )
    tight_clearance_penalty = 0.05 if bool(metadata.get("tight_clearance", False)) else 0.0

    score_next = active * scalars["score"] * score_weight * (1.0 + region_count * 0.08 + opportunity_count * 0.05)
    deny_next = active * scalars["deny"] * deny_weight * (1.0 + screen_count * 0.07)
    control = active * scalars["control"] * ((score_weight + deny_weight) * 0.7 + region_count * 0.06)
    action_enable = active * scalars["score"] * action_enable_weight * (1.0 + affordance_count * 0.05)
    exposure = active * (
        -scalars["terrain"] * (safety_weight * 0.35 + coherency_weight * 0.05)
        + tight_clearance_penalty
        + threat_hint * 0.05
    )
    trade = active * scalars["combat"] * (trade_weight * 0.8 + score_weight * 0.15 + deny_weight * 0.1) - max(exposure, 0.0) * 0.35
    cover = active * scalars["terrain"] * (safety_weight * 0.5 + coherency_weight * 0.08)
    los = active * (scalars["terrain"] * score_weight * 0.2 - safety_weight * 0.15)
    resource = -active * scalars["resource"] * (action_enable_weight * 0.12 + trade_weight * 0.08)
    return {
        "projected_score_delta_next_window": _round6(score_next),
        "projected_score_delta_round": _round6(score_next * (1.15 + min(0.35, window_count * 0.05))),
        "projected_deny_delta_next_window": _round6(deny_next),
        "projected_control_delta": _round6(control),
        "projected_action_enablement_delta": _round6(action_enable),
        "projected_exposure_delta": _round6(_clamp(exposure, low=-2.0, high=2.0)),
        "projected_trade_ev": _round6(_clamp(trade, low=-3.0, high=3.0)),
        "cover_delta": _round6(_clamp(cover, low=-1.5, high=1.5)),
        "los_delta": _round6(_clamp(los, low=-1.5, high=1.5)),
        "resource_delta": _round6(_clamp(resource, low=-3.0, high=3.0)),
    }


def _projection_for_targeting(
    *,
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    context: Mapping[str, Any],
    scalars: Mapping[str, float],
) -> dict[str, float]:
    active = 1.0 if _is_non_noop_candidate(dict(params), metadata) else 0.0
    target_count = float(max(1, _extract_target_count(params, context)) if active else 0)
    shot_volume = float(max(1.0, _extract_shot_volume(params)) if active else 0.0)
    catalog = context.get("opportunity_catalog")
    catalog_data = dict(catalog) if isinstance(catalog, dict) else {}
    priority_count = float(_count_items(catalog_data.get("priority")))
    denial_count = float(_count_items(catalog_data.get("denial")))
    intensity = target_count * 0.5 + shot_volume * 0.15

    score_next = active * scalars["score"] * (target_count * 0.04 + priority_count * 0.01)
    deny_next = active * scalars["deny"] * (target_count * 0.03 + denial_count * 0.01)
    control = active * scalars["control"] * (target_count * 0.02 + priority_count * 0.01)
    action_enable = active * scalars["score"] * target_count * 0.015
    exposure = active * scalars["terrain"] * (-target_count * 0.03 + max(0.0, intensity - 2.5) * 0.015)
    trade = active * scalars["combat"] * (intensity * 0.09 + priority_count * 0.02)
    cover = active * scalars["terrain"] * (-target_count * 0.01)
    los = active * scalars["terrain"] * (target_count * 0.03 + shot_volume * 0.01)
    resource = -active * scalars["resource"] * (
        _extract_resource_cost(params, metadata, context) * 0.08 + shot_volume * 0.01
    )
    return {
        "projected_score_delta_next_window": _round6(score_next),
        "projected_score_delta_round": _round6(score_next * (1.1 + min(0.25, priority_count * 0.05))),
        "projected_deny_delta_next_window": _round6(deny_next),
        "projected_control_delta": _round6(control),
        "projected_action_enablement_delta": _round6(action_enable),
        "projected_exposure_delta": _round6(_clamp(exposure, low=-2.0, high=2.0)),
        "projected_trade_ev": _round6(_clamp(trade, low=-3.0, high=3.0)),
        "cover_delta": _round6(_clamp(cover, low=-1.5, high=1.5)),
        "los_delta": _round6(_clamp(los, low=-1.5, high=1.5)),
        "resource_delta": _round6(_clamp(resource, low=-3.0, high=3.0)),
    }


def _projection_for_charge(
    *,
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    context: Mapping[str, Any],
    scalars: Mapping[str, float],
) -> dict[str, float]:
    active = 1.0 if _is_non_noop_candidate(dict(params), metadata) else 0.0
    target_count = float(max(1, _extract_target_count(params, context)) if active else 0)
    out_of_turn = bool(params.get("out_of_turn", False) or context.get("out_of_turn", False))
    charge_distance = max(0.0, _safe_float(params.get("charge_distance", params.get("distance", 0.0)), 0.0))
    distance_bonus = max(0.0, 8.0 - charge_distance) * 0.02

    score_next = active * scalars["score"] * (target_count * 0.06 + distance_bonus)
    deny_next = active * scalars["deny"] * (target_count * 0.05)
    control = active * scalars["control"] * (target_count * 0.04 + 0.03)
    action_enable = active * scalars["score"] * (0.04 + target_count * 0.01)
    exposure = active * scalars["terrain"] * (-target_count * 0.08 + (0.03 if out_of_turn else 0.0))
    trade = active * scalars["combat"] * (target_count * 0.12 + distance_bonus)
    cover = active * scalars["terrain"] * (-target_count * 0.02)
    los = active * (-target_count * 0.01)
    resource = -active * scalars["resource"] * (0.03 + (0.02 if out_of_turn else 0.0))
    return {
        "projected_score_delta_next_window": _round6(score_next),
        "projected_score_delta_round": _round6(score_next * 1.25),
        "projected_deny_delta_next_window": _round6(deny_next),
        "projected_control_delta": _round6(control),
        "projected_action_enablement_delta": _round6(action_enable),
        "projected_exposure_delta": _round6(_clamp(exposure, low=-2.0, high=2.0)),
        "projected_trade_ev": _round6(_clamp(trade, low=-3.0, high=3.0)),
        "cover_delta": _round6(_clamp(cover, low=-1.5, high=1.5)),
        "los_delta": _round6(_clamp(los, low=-1.5, high=1.5)),
        "resource_delta": _round6(_clamp(resource, low=-3.0, high=3.0)),
    }


def _projection_for_fight(
    *,
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    context: Mapping[str, Any],
    scalars: Mapping[str, float],
) -> dict[str, float]:
    active = 1.0 if _is_non_noop_candidate(dict(params), metadata) else 0.0
    target_count = float(max(1, _extract_target_count(params, context)) if active else 0)
    weapon_count = float(max(1, _extract_weapon_bundle_count(params)) if active else 0)
    attack_volume = float(max(1.0, _extract_attack_volume(params)) if active else 0.0)

    score_next = active * scalars["score"] * (target_count * 0.03 + weapon_count * 0.01)
    deny_next = active * scalars["deny"] * (target_count * 0.04 + attack_volume * 0.01)
    control = active * scalars["control"] * (target_count * 0.05 + weapon_count * 0.015)
    action_enable = active * scalars["score"] * (0.02 + weapon_count * 0.01)
    exposure = active * scalars["terrain"] * (-(target_count * 0.05 + weapon_count * 0.02))
    trade = active * scalars["combat"] * (attack_volume * 0.1 + weapon_count * 0.05 + target_count * 0.03)
    cover = active * scalars["terrain"] * (-target_count * 0.015)
    los = active * (-target_count * 0.01)
    resource = -active * scalars["resource"] * (weapon_count * 0.02 + attack_volume * 0.01)
    return {
        "projected_score_delta_next_window": _round6(score_next),
        "projected_score_delta_round": _round6(score_next * (1.2 + min(0.2, attack_volume * 0.01))),
        "projected_deny_delta_next_window": _round6(deny_next),
        "projected_control_delta": _round6(control),
        "projected_action_enablement_delta": _round6(action_enable),
        "projected_exposure_delta": _round6(_clamp(exposure, low=-2.0, high=2.0)),
        "projected_trade_ev": _round6(_clamp(trade, low=-3.0, high=3.0)),
        "cover_delta": _round6(_clamp(cover, low=-1.5, high=1.5)),
        "los_delta": _round6(_clamp(los, low=-1.5, high=1.5)),
        "resource_delta": _round6(_clamp(resource, low=-3.0, high=3.0)),
    }


def _projection_for_tool(
    *,
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    context: Mapping[str, Any],
    scalars: Mapping[str, float],
) -> dict[str, float]:
    active = 1.0 if _is_non_noop_candidate(dict(params), metadata) else 0.0
    descriptor_count = float(_count_items(_tool_descriptor_ids(context)))
    text_blob = _text_blob(dict(params), dict(metadata), dict(context))
    score_bias = 1.0 if _contains_any(text_blob, ("score", "objective", "control", "action", "hold")) else 0.0
    deny_bias = 1.0 if _contains_any(text_blob, ("deny", "battleshock", "reserve", "suppression")) else 0.0
    damage_bias = 1.0 if _contains_any(text_blob, ("damage", "hit", "wound", "fight", "shoot")) else 0.0
    durable_bias = 1.0 if _contains_any(text_blob, ("save", "invulnerable", "durability", "fnp")) else 0.0
    move_bias = 1.0 if _contains_any(text_blob, ("move", "advance", "charge", "fallback", "reposition")) else 0.0
    cp_cost = _extract_resource_cost(params, metadata, context)

    score_next = active * scalars["score"] * (score_bias * 0.04 + move_bias * 0.01 + descriptor_count * 0.01)
    deny_next = active * scalars["deny"] * (deny_bias * 0.04 + descriptor_count * 0.01)
    control = active * scalars["control"] * ((score_bias + deny_bias) * 0.03 + descriptor_count * 0.01)
    action_enable = active * scalars["tool"] * (move_bias * 0.05 + score_bias * 0.03)
    exposure = active * scalars["terrain"] * (durable_bias * -0.04 + deny_bias * -0.015 + damage_bias * 0.015)
    trade = active * scalars["combat"] * (damage_bias * 0.06 + descriptor_count * 0.02 + move_bias * 0.02)
    cover = active * scalars["terrain"] * (durable_bias * 0.04 - damage_bias * 0.01)
    los = active * scalars["terrain"] * (damage_bias * 0.01 + move_bias * 0.01)
    resource = -active * scalars["resource"] * (cp_cost * 0.08 + descriptor_count * 0.02)
    return {
        "projected_score_delta_next_window": _round6(score_next),
        "projected_score_delta_round": _round6(score_next * (1.15 + score_bias * 0.05)),
        "projected_deny_delta_next_window": _round6(deny_next),
        "projected_control_delta": _round6(control),
        "projected_action_enablement_delta": _round6(action_enable),
        "projected_exposure_delta": _round6(_clamp(exposure, low=-2.0, high=2.0)),
        "projected_trade_ev": _round6(_clamp(trade, low=-3.0, high=3.0)),
        "cover_delta": _round6(_clamp(cover, low=-1.5, high=1.5)),
        "los_delta": _round6(_clamp(los, low=-1.5, high=1.5)),
        "resource_delta": _round6(_clamp(resource, low=-3.0, high=3.0)),
    }


def _projection_for_generic(
    *,
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    context: Mapping[str, Any],
    scalars: Mapping[str, float],
) -> dict[str, float]:
    active = 1.0 if _is_non_noop_candidate(dict(params), metadata) else 0.0
    catalog = context.get("opportunity_catalog")
    catalog_data = dict(catalog) if isinstance(catalog, dict) else {}
    priority_count = float(_count_items(catalog_data.get("priority")))
    denial_count = float(_count_items(catalog_data.get("denial")))
    score_next = active * scalars["score"] * (0.01 + priority_count * 0.005)
    deny_next = active * scalars["deny"] * (denial_count * 0.005)
    control = active * scalars["control"] * 0.01
    action_enable = active * scalars["tool"] * 0.005
    exposure = active * scalars["terrain"] * -0.01
    trade = active * scalars["combat"] * 0.01
    cover = active * scalars["terrain"] * 0.005
    los = active * scalars["terrain"] * 0.005
    resource = -active * scalars["resource"] * 0.005
    return {
        "projected_score_delta_next_window": _round6(score_next),
        "projected_score_delta_round": _round6(score_next * 1.1),
        "projected_deny_delta_next_window": _round6(deny_next),
        "projected_control_delta": _round6(control),
        "projected_action_enablement_delta": _round6(action_enable),
        "projected_exposure_delta": _round6(_clamp(exposure, low=-2.0, high=2.0)),
        "projected_trade_ev": _round6(_clamp(trade, low=-3.0, high=3.0)),
        "cover_delta": _round6(_clamp(cover, low=-1.5, high=1.5)),
        "los_delta": _round6(_clamp(los, low=-1.5, high=1.5)),
        "resource_delta": _round6(_clamp(resource, low=-3.0, high=3.0)),
    }


def _is_tool_decision(
    *,
    decision_type: str,
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    context: Mapping[str, Any],
) -> bool:
    dtype = str(decision_type or "").strip().upper()
    if dtype.startswith("USE_"):
        return True
    if _tool_descriptor_ids(context):
        return True
    tool_keys = {"stratagem_id", "enhancement_id", "tool_id", "cp_cost", "command_points", "ability_key"}
    if any(key in params for key in tool_keys):
        return True
    if any(key in metadata for key in tool_keys):
        return True
    return False


def _projection_kind(
    *,
    decision_type: str,
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    context: Mapping[str, Any],
) -> str:
    if decision_type in _MOVEMENT_DECISION_TYPES:
        return "movement"
    if decision_type in _TARGETING_DECISION_TYPES:
        return "targeting"
    if decision_type in _CHARGE_DECISION_TYPES:
        return "charge"
    if decision_type == DECISION_SELECT_UNIT:
        phase_key = " ".join(
            str(context.get(key, "") or "").strip().upper()
            for key in ("phase_step", "phase", "phase_name", "selection_purpose")
        )
        if "SHOOT" in phase_key:
            return "targeting"
        if "CHARGE" in phase_key:
            return "charge"
        if "FIGHT" in phase_key:
            return "fight"
        return "generic"
    if decision_type in _FIGHT_DECISION_TYPES:
        return "fight"
    if _is_tool_decision(
        decision_type=decision_type,
        params=params,
        metadata=metadata,
        context=context,
    ):
        return "tool"
    return "generic"


def _computed_projections(
    *,
    decision_type: str,
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    context: Mapping[str, Any],
    rules_bundle_id: str,
    rules_bundle: Mapping[str, Any] | None,
) -> tuple[dict[str, float], str]:
    scalars = _bundle_scalars(
        rules_bundle_id=rules_bundle_id,
        rules_bundle=rules_bundle,
    )
    kind = _projection_kind(
        decision_type=decision_type,
        params=params,
        metadata=metadata,
        context=context,
    )
    if kind == "movement":
        return (
            _projection_for_movement(
                params=params,
                metadata=metadata,
                context=context,
                scalars=scalars,
            ),
            kind,
        )
    if kind == "targeting":
        return (
            _projection_for_targeting(
                params=params,
                metadata=metadata,
                context=context,
                scalars=scalars,
            ),
            kind,
        )
    if kind == "charge":
        return (
            _projection_for_charge(
                params=params,
                metadata=metadata,
                context=context,
                scalars=scalars,
            ),
            kind,
        )
    if kind == "fight":
        return (
            _projection_for_fight(
                params=params,
                metadata=metadata,
                context=context,
                scalars=scalars,
            ),
            kind,
        )
    if decision_type in _REROLL_DECISION_TYPES:
        return (
            _projection_for_reroll(
                params=params,
                metadata=metadata,
                context=context,
                scalars=scalars,
            ),
            "tool",
        )
    if kind == "tool":
        return (
            _projection_for_tool(
                params=params,
                metadata=metadata,
                context=context,
                scalars=scalars,
            ),
            kind,
        )
    return (
        _projection_for_generic(
            params=params,
            metadata=metadata,
            context=context,
            scalars=scalars,
        ),
        kind,
    )


def _rules_provenance_refs(metadata: dict[str, Any], *, rules_bundle_id: str) -> list[str]:
    refs = metadata.get("rules_provenance_refs", [])
    if not isinstance(refs, list):
        refs = []
    normalized = {str(ref) for ref in refs if str(ref)}
    if str(rules_bundle_id or ""):
        normalized.add(str(rules_bundle_id))
    return sorted(normalized)


def normalize_candidate_semantic_metadata(
    *,
    decision_type: str,
    params: dict[str, Any],
    metadata: dict[str, Any],
    context: Mapping[str, Any] | None,
    rules_bundle_id: str,
    rules_bundle: Mapping[str, Any] | None = None,
    overwrite_existing: bool = False,
) -> dict[str, Any]:
    context_data = dict(context or {})
    metadata_data = dict(metadata or {})
    projections, projection_kind = _computed_projections(
        decision_type=str(decision_type or ""),
        params=dict(params or {}),
        metadata=metadata_data,
        context=context_data,
        rules_bundle_id=str(rules_bundle_id or ""),
        rules_bundle=rules_bundle,
    )
    for key in SEMANTIC_NUMERIC_KEYS:
        computed_value = _safe_float(projections.get(key, 0.0), 0.0)
        if overwrite_existing or key not in metadata_data:
            metadata_data[key] = computed_value
        else:
            metadata_data[key] = _safe_float(metadata_data.get(key), computed_value)
    if projection_kind == "movement":
        metadata_data.update(
            _commander_movement_metadata(
                params=dict(params or {}),
                metadata=metadata_data,
                context=context_data,
            )
        )
    metadata_data["semantic_projection_kind"] = str(projection_kind)
    metadata_data["rules_provenance_refs"] = _rules_provenance_refs(
        metadata_data,
        rules_bundle_id=str(rules_bundle_id or ""),
    )
    return metadata_data


def ensure_candidate_semantic_metadata(
    request: DecisionRequest,
    *,
    rules_bundle_id: str,
    rules_bundle: Mapping[str, Any] | None = None,
    overwrite_existing: bool = False,
) -> None:
    decision_type = str(getattr(request, "decision_type", "") or "")
    context = dict(getattr(request, "context", {}) or {})
    resolved_bundle = rules_bundle
    if resolved_bundle is None:
        context_bundle = context.get("rules_bundle")
        if isinstance(context_bundle, dict):
            resolved_bundle = dict(context_bundle)
    normalized_candidates: list[CandidateAction] = []
    for candidate in list(getattr(request, "candidates", []) or []):
        params = dict(candidate.params or {})
        metadata = dict(candidate.metadata or {})
        normalized_metadata = normalize_candidate_semantic_metadata(
            decision_type=decision_type,
            params=params,
            metadata=metadata,
            context=context,
            rules_bundle_id=rules_bundle_id,
            rules_bundle=resolved_bundle,
            overwrite_existing=overwrite_existing,
        )
        normalized_candidates.append(
            CandidateAction(
                action_id=str(candidate.action_id or ""),
                params=params,
                metadata=normalized_metadata,
            )
        )
    request.candidates = normalized_candidates
