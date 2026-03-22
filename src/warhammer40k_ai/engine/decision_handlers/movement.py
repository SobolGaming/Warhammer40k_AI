from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Iterable, Sequence

from ..decision_dispatcher import register_decision_handler
from ..decision_kinds import (
    DECISION_DISEMBARK,
    DECISION_EMBARK,
    DECISION_MOVE_UNIT,
    DECISION_PICK_OBJECTIVE,
    DECISION_PICK_POINT,
    DECISION_RESOLVE_COHERENCY,
    DECISION_SELECT_FLOOR,
    DECISION_SELECT_MOVEMENT_ACTION,
)
from ..decisions import DecisionOption, DecisionRequest, DecisionResult
from ..path_witness import (
    current_model_positions,
    detect_normal_move_engagement_crossing,
    detect_terrain_sweep_collisions,
    detect_tight_clearance_orientation_violations,
    validate_witness_contiguity,
)
from ._helpers import (
    apply_model_positions,
    find_option,
    get_model,
    get_objective,
    get_unit,
    is_skip_choice,
    validate_model_positions,
    validate_option_choice,
)
from ...utility.deployment_special_rules import (
    is_convergence_of_dominion_deployment_unit,
    validate_convergence_of_dominion_deployment,
)
from ...utility.dice import get_roll
from ...utility.entity_ids import get_entity_id
from ...utility.constants import ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL


def _movement_members(unit) -> list:
    try:
        members = list(unit.get_attached_unit_members() or [])
    except Exception:
        members = []
    return members or [unit]


def _clear_battle_focus_reactive_flags(unit) -> None:
    for member in _movement_members(unit):
        sr = getattr(member, "special_rules", None)
        if not isinstance(sr, dict):
            continue
        for key in (
            "battle_focus_reactive_move_max",
            "battle_focus_reactive_move_source",
            "battle_focus_reactive_move_kind",
            "battle_focus_reactive_move_allow_engagement_range",
            "battle_focus_reactive_move_expires_phase",
        ):
            sr.pop(key, None)


def _parse_xy_point(value: object) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        return (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None


def _validate_heresy_begets_retribution_positions(
    game: object,
    unit: object,
    model_positions: object,
    *,
    ctx: dict | None = None,
) -> Sequence[str]:
    context = dict(ctx or {})
    reactive_kind = str(context.get("reactive_move_kind", "") or "").strip().lower()
    reactive_move_type = str(context.get("reactive_move_movement_type", "") or "").strip().lower()
    if reactive_kind != "heresy_begets_retribution" and reactive_move_type != "retribution_move":
        return ()
    if unit is None:
        return ("Move unit: Heresy Begets Retribution requires a valid unit.",)
    game_map = getattr(game, "map", None)
    if game_map is None:
        return ("Move unit: Heresy Begets Retribution requires a game map.",)

    try:
        from ...utility.calcs import MovementType, get_validation_rules, validate_final_position
    except Exception:
        return ("Move unit: Heresy Begets Retribution validation rules are unavailable.",)

    validation_rules = get_validation_rules(MovementType.BESTIAL_RAGE, moving_unit=unit)
    validation_rules["closest_enemy_unit_reason"] = "Heresy Begets Retribution"

    positions_by_id: dict[str, tuple[float, float, float]] = {}
    for entry in list(model_positions or []):
        model_id = str(entry.get("model_id", "") or "").strip()
        pos = entry.get("position") or []
        if not model_id or not isinstance(pos, (list, tuple)) or len(pos) < 2:
            continue
        try:
            positions_by_id[model_id] = (
                float(pos[0]),
                float(pos[1]),
                float(pos[2]) if len(pos) > 2 else 0.0,
            )
        except (TypeError, ValueError):
            continue

    get_models = getattr(unit, "get_attached_unit_models", None)
    models = list(get_models() or []) if callable(get_models) else list(getattr(unit, "models", []) or [])
    for model in list(models or []):
        if model is None:
            continue
        alive_value = getattr(model, "is_alive", True)
        alive = bool(alive_value() if callable(alive_value) else alive_value)
        if not alive:
            continue
        model_id = str(get_entity_id(model) or "").strip()
        if not model_id or model_id not in positions_by_id:
            continue
        validation = validate_final_position(model, positions_by_id[model_id], validation_rules, game_map)
        if not bool((validation or {}).get("valid", False)):
            reason = str((validation or {}).get("reason", "") or "invalid final position")
            return (f"Move unit: Heresy Begets Retribution {reason}.",)
    return ()


def _validate_predatory_pursuit_positions(
    game: object,
    unit: object,
    model_positions: object,
    *,
    ctx: dict | None = None,
) -> Sequence[str]:
    context = dict(ctx or {})
    reactive_kind = str(context.get("reactive_move_kind", "") or "").strip().lower()
    if reactive_kind != "predatory_pursuit":
        return ()
    if unit is None:
        return ("Move unit: Predatory Pursuit requires a valid unit.",)

    target_unit_id = str(context.get("predatory_pursuit_target_unit_id", "") or "").strip()
    if not target_unit_id:
        return ("Move unit: Predatory Pursuit target unit is missing.",)
    target_unit = get_unit(game, target_unit_id)
    if target_unit is None:
        return ("Move unit: Predatory Pursuit target unit could not be resolved.",)

    try:
        from ...utility.aura_utils import distance_between_bases_3d
        from ...utility.model_base import clone_base
    except Exception:
        return ("Move unit: Predatory Pursuit distance helpers are unavailable.",)

    moving_models = []
    get_models = getattr(unit, "get_attached_unit_models", None)
    models = list(get_models() or []) if callable(get_models) else list(getattr(unit, "models", []) or [])
    for model in list(models or []):
        if model is None:
            continue
        alive_value = getattr(model, "is_alive", True)
        alive = bool(alive_value() if callable(alive_value) else alive_value)
        if not alive or getattr(model, "model_base", None) is None:
            continue
        moving_models.append(model)
    if not moving_models:
        return ()

    target_models = []
    get_target_models = getattr(target_unit, "get_attached_unit_models", None)
    raw_target_models = (
        list(get_target_models() or [])
        if callable(get_target_models)
        else list(getattr(target_unit, "models", []) or [])
    )
    for target_model in list(raw_target_models or []):
        if target_model is None:
            continue
        alive_value = getattr(target_model, "is_alive", True)
        alive = bool(alive_value() if callable(alive_value) else alive_value)
        if not alive or getattr(target_model, "model_base", None) is None:
            continue
        target_models.append(target_model)
    if not target_models:
        return ()

    try:
        max_distance = float(context.get("max_distance", 0) or 0)
    except (TypeError, ValueError):
        max_distance = 0.0
    if max_distance <= 0:
        max_distance = 6.0
    tolerance = 0.05

    positions_by_id: dict[str, tuple[float, float, float]] = {}
    for entry in list(model_positions or []):
        model_id = str(entry.get("model_id", "") or "").strip()
        position = entry.get("position") or []
        if not model_id or not isinstance(position, (list, tuple)) or len(position) < 2:
            continue
        try:
            positions_by_id[model_id] = (
                float(position[0]),
                float(position[1]),
                float(position[2]) if len(position) > 2 else 0.0,
            )
        except (TypeError, ValueError):
            continue

    current_distance: float | None = None
    final_distance: float | None = None
    for model in moving_models:
        current_base = getattr(model, "model_base", None)
        if current_base is None:
            continue
        try:
            current_min = min(float(distance_between_bases_3d(current_base, enemy_model.model_base)) for enemy_model in target_models)
        except Exception:
            continue
        if current_distance is None or current_min < current_distance:
            current_distance = current_min

        model_id = str(get_entity_id(model) or "").strip()
        end_position = positions_by_id.get(model_id)
        if end_position is None:
            continue
        try:
            new_base = clone_base(current_base)
            new_base.set_position(end_position[0], end_position[1], end_position[2])
            final_min = min(float(distance_between_bases_3d(new_base, enemy_model.model_base)) for enemy_model in target_models)
        except Exception:
            continue
        if final_distance is None or final_min < final_distance:
            final_distance = final_min

    if current_distance is None or final_distance is None:
        return ()

    min_possible = max(0.0, float(current_distance) - float(max_distance))
    if final_distance > (min_possible + tolerance):
        target_name = str(getattr(target_unit, "name", "") or "target unit")
        return (
            f'Move unit: Predatory Pursuit must end as close as possible to {target_name}: '
            f'{final_distance:.2f}" > {min_possible:.2f}".',
        )
    return ()


def _masters_of_the_void_enemy_dz_override_active(unit: object, game: object) -> bool:
    if unit is None or game is None:
        return False
    get_root = getattr(unit, "get_attached_unit_root", None)
    root = get_root() if callable(get_root) else unit
    if root is None:
        return False
    sr = getattr(root, "special_rules", None)
    if not isinstance(sr, dict):
        return False
    if not bool(sr.get("imperial_agents_masters_of_the_void_enemy_dz_override_active")):
        return False

    owner_id = str(sr.get("imperial_agents_masters_of_the_void_enemy_dz_override_turn_owner", "") or "")
    turn_value = sr.get("imperial_agents_masters_of_the_void_enemy_dz_override_turn", 0)
    try:
        effect_turn = int(turn_value or 0)
    except (TypeError, ValueError):
        effect_turn = 0
    try:
        current_turn = int(getattr(game, "turn", 0) or 0)
    except (TypeError, ValueError):
        current_turn = 0
    if effect_turn and current_turn and effect_turn != current_turn:
        return False

    current_player = getattr(game, "get_current_player", lambda: None)()
    current_owner_id = str(getattr(current_player, "id", "") or "")
    if owner_id and current_owner_id and owner_id != current_owner_id:
        return False

    expires_phase = str(
        sr.get("imperial_agents_masters_of_the_void_enemy_dz_override_expires_phase", "") or ""
    ).strip().upper()
    phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
    if expires_phase and phase_name and expires_phase != phase_name:
        return False
    return True


def _maybe_queue_post_fall_back_destroyed_strategic_reserves(
    game: object,
    unit: object,
    *,
    context: dict | None = None,
) -> None:
    if game is None or unit is None:
        return
    phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
    if phase_name != "FIGHT_PHASE":
        return
    get_root = getattr(unit, "get_attached_unit_root", None)
    root = get_root() if callable(get_root) else unit
    if root is None:
        return
    is_alive_fn = getattr(root, "is_alive", None)
    if callable(is_alive_fn) and not bool(is_alive_fn()):
        return
    if not bool(getattr(root, "deployed", True)):
        return
    is_in_reserves_fn = getattr(root, "is_in_reserves", None)
    if callable(is_in_reserves_fn) and bool(is_in_reserves_fn()):
        return
    if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
        return
    round_state = getattr(root, "round_state", None)
    if not bool(getattr(round_state, "fought_this_phase", False)):
        return
    unit_id = str(get_entity_id(root) or "").strip()
    if not unit_id:
        return
    ctx = dict(context or {})
    destroyed_enemy_this_phase = bool(ctx.get("fight_phase_destroyed_strategic_reserves_eligible", False))
    if not destroyed_enemy_this_phase:
        sr = getattr(root, "special_rules", None)
        current_player = getattr(game, "get_current_player", lambda: None)()
        current_owner_id = str(getattr(current_player, "id", "") or "")
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        if isinstance(sr, dict) and bool(sr.get("fight_phase_destroyed_strategic_reserves_pending", False)):
            marker_owner_id = str(sr.get("fight_phase_destroyed_strategic_reserves_turn_owner", "") or "")
            try:
                marker_turn = int(sr.get("fight_phase_destroyed_strategic_reserves_turn", 0) or 0)
            except Exception:
                marker_turn = 0
            destroyed_enemy_this_phase = marker_turn == current_turn and (
                not marker_owner_id or not current_owner_id or marker_owner_id == current_owner_id
            )
    if not destroyed_enemy_this_phase:
        tracked = {
            str(value or "").strip()
            for value in list(getattr(game, "_phase_enemy_unit_destroyers", {}).get("FIGHT_PHASE", set()) or set())
            if str(value or "").strip()
        }
        if unit_id not in tracked:
            return
    ability = root.get_end_of_fight_phase_destroyed_strategic_reserves_ability()
    if not ability:
        return
    game_map = getattr(game, "map", None)
    if game_map is None:
        return
    for enemy in list(game_map.get_enemy_units(root) or []):
        if enemy is None:
            continue
        enemy_alive_fn = getattr(enemy, "is_alive", None)
        if callable(enemy_alive_fn) and not bool(enemy_alive_fn()):
            continue
        if not bool(getattr(enemy, "deployed", True)):
            continue
        if game_map.is_within_engagement_range(root, enemy):
            return
    queue_confirmation = getattr(game, "_queue_optional_ability_confirmation", None)
    if not callable(queue_confirmation):
        return
    get_army = getattr(root, "get_parent_army", None)
    army = get_army() if callable(get_army) else None
    player = getattr(army, "player", None) if army is not None else None
    if player is None:
        return
    ability_name = str(ability.get("name", "") or "Strategic Reserves").strip() or "Strategic Reserves"
    queue_confirmation(
        player=player,
        ability_key="fight_phase_destroyed_strategic_reserves",
        ability_name=ability_name,
        message=(
            f"{getattr(root, 'name', 'Unit')} can enter Strategic Reserves at the end of the Fight phase.\n\n"
            "Use this ability?"
        ),
        context={
            "ability_name": ability_name,
            "unit": getattr(root, "name", "") or "",
            "phase": "End of Fight phase",
            "unit_id": unit_id,
        },
        payload={"unit_id": unit_id},
        instance_key=str(unit_id or ""),
    )


def _transponder_lock_module_turn_one_spotter_requirement_satisfied(
    unit: object,
    prospective: list[tuple[float, float, float, float]],
    *,
    pending_deep_strike: bool,
    game: object,
) -> bool:
    if unit is None or game is None or not bool(pending_deep_strike):
        return True
    get_root = getattr(unit, "get_attached_unit_root", None)
    root = get_root() if callable(get_root) else unit
    if root is None:
        return True
    sr = getattr(root, "special_rules", None)
    if not isinstance(sr, dict) or not bool(sr.get("enhancement_transponder_lock_module")):
        return True
    try:
        current_turn = int(getattr(game, "turn", 0) or 0)
    except (TypeError, ValueError):
        current_turn = 0
    if current_turn != 1:
        return True

    try:
        max_range = float(sr.get("enhancement_transponder_lock_module_turn_one_spotter_range", 12.0) or 12.0)
    except (TypeError, ValueError):
        max_range = 12.0
    if max_range <= 0.0:
        return False

    required_keywords = [
        str(v or "").strip().upper()
        for v in list(
            sr.get(
                "enhancement_transponder_lock_module_turn_one_spotter_keywords_any",
                ("KROOT", "VESPID STINGWINGS"),
            )
            or ()
        )
        if str(v or "").strip()
    ]
    if not required_keywords:
        required_keywords = ["KROOT", "VESPID STINGWINGS"]

    army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
    game_map = getattr(game, "map", None)
    if army is None or game_map is None:
        return False

    from ...utility.aura_utils import distance_between_bases_3d

    def _unit_has_required_keyword(candidate_unit: object) -> bool:
        if candidate_unit is None:
            return False
        has_any_keyword = getattr(candidate_unit, "has_any_keyword", None)
        if callable(has_any_keyword):
            for keyword in required_keywords:
                if bool(has_any_keyword(keyword)):
                    return True
        pool: list[str] = []
        pool.extend([str(v or "").strip().upper() for v in list(getattr(candidate_unit, "keywords", []) or [])])
        pool.extend([str(v or "").strip().upper() for v in list(getattr(candidate_unit, "faction_keywords", []) or [])])
        return any(keyword in pool for keyword in required_keywords)

    friendly_units: list[object] = []
    seen_ids: set[str] = set()
    for candidate in list(getattr(game_map, "units", []) or []):
        if candidate is None:
            continue
        get_candidate_root = getattr(candidate, "get_attached_unit_root", None)
        candidate_root = get_candidate_root() if callable(get_candidate_root) else candidate
        if candidate_root is None:
            continue
        candidate_id = str(get_entity_id(candidate_root) or "")
        if candidate_id and candidate_id in seen_ids:
            continue
        if candidate_id:
            seen_ids.add(candidate_id)
        if candidate_root is root:
            continue
        candidate_army = candidate_root.get_parent_army() if hasattr(candidate_root, "get_parent_army") else None
        if candidate_army is not army:
            continue
        is_alive_fn = getattr(candidate_root, "is_alive", None)
        alive = bool(is_alive_fn()) if callable(is_alive_fn) else bool(getattr(candidate_root, "is_alive", True))
        if not alive:
            continue
        if not bool(getattr(candidate_root, "deployed", False)):
            continue
        if str(getattr(candidate_root, "reserve_status", "deployed") or "deployed") != "deployed":
            continue
        if bool(getattr(candidate_root, "is_embarked", False)) or getattr(candidate_root, "embarked_in", None) is not None:
            continue
        if not _unit_has_required_keyword(candidate_root):
            continue
        friendly_units.append(candidate_root)

    if not friendly_units:
        return False

    for idx, (x, y, z, facing) in enumerate(prospective):
        if idx >= len(getattr(root, "models", []) or []):
            break
        try:
            base = root._create_potential_base(x, y, z, facing, model=root.models[idx])
        except Exception:
            continue
        for spotter in list(friendly_units or []):
            for model in list(getattr(spotter, "models", []) or []):
                model_alive_attr = getattr(model, "is_alive", True)
                model_alive = bool(model_alive_attr() if callable(model_alive_attr) else model_alive_attr)
                if not model_alive:
                    continue
                if float(distance_between_bases_3d(base, model.model_base)) <= float(max_range) + 1e-6:
                    return True
    return False


def _fleet_commander_effect_roll(token: object) -> int:
    text = str(token or "D3").strip().upper() or "D3"
    if text == "D3":
        return int(get_roll("D3") or 0)
    if text == "D6":
        return int(get_roll("D6") or 0)
    if text == "D3+3":
        return int(get_roll("D3") or 0) + 3
    try:
        return max(0, int(text))
    except (TypeError, ValueError):
        return 0


def _iter_active_battlefield_roots(game: object) -> list[object]:
    game_map = getattr(game, "map", None)
    if game_map is None:
        return []
    roots_by_id: dict[str, object] = {}
    for entry in list(getattr(game_map, "units", []) or []):
        if entry is None:
            continue
        get_root = getattr(entry, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else entry
        if root is None:
            continue
        root_id = str(get_entity_id(root) or "")
        if not root_id:
            root_id = f"anon:{str(getattr(root, 'name', '') or '')}:{id(root)}"
        if root_id in roots_by_id:
            continue
        is_alive_fn = getattr(root, "is_alive", None)
        if callable(is_alive_fn):
            if not bool(is_alive_fn()):
                continue
        elif bool(getattr(root, "is_alive", True)) is False:
            continue
        if not bool(getattr(root, "deployed", True)):
            continue
        if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
            continue
        is_in_reserves = getattr(root, "is_in_reserves", None)
        if callable(is_in_reserves) and bool(is_in_reserves()):
            continue
        reserve_status = str(getattr(root, "reserve_status", "deployed") or "deployed").strip().lower()
        if reserve_status and reserve_status != "deployed":
            continue
        roots_by_id[root_id] = root
    return [roots_by_id[k] for k in sorted(roots_by_id.keys())]


def _unit_line_intersects(root: object, *, start_xy: tuple[float, float], end_xy: tuple[float, float]) -> bool:
    if root is None:
        return False
    if float(start_xy[0]) == float(end_xy[0]) and float(start_xy[1]) == float(end_xy[1]):
        return False
    try:
        from shapely.geometry import LineString, Point
    except ImportError:
        return False
    line = LineString([tuple(start_xy), tuple(end_xy)])
    get_models = getattr(root, "get_attached_unit_models", None)
    models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
    models.sort(key=lambda m: str(get_entity_id(m) or ""))
    for model in models:
        if model is None:
            continue
        alive_attr = getattr(model, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if not alive:
            continue
        model_base = getattr(model, "model_base", None)
        get_shape = getattr(model_base, "get_base_shape", None) if model_base is not None else None
        if callable(get_shape):
            shape = get_shape()
            if shape is not None and bool(getattr(line, "intersects", lambda _shape: False)(shape)):
                return True
        get_location = getattr(model, "get_location", None)
        if callable(get_location):
            loc = get_location()
            if isinstance(loc, tuple) and len(loc) >= 2:
                point = Point(float(loc[0]), float(loc[1]))
                if bool(line.distance(point) <= 1e-6):
                    return True
    return False


def _maybe_request_move_modifier_choice(game: object, unit: object, *, action_type: str) -> None:
    if unit is None or not bool(getattr(game, "is_authoritative", True)):
        return
    try:
        from ..decision_kinds import DECISION_CHOOSE_MOVE_MODIFIER_IGNORES
        from ..decisions import DecisionOption, DecisionRequest
        from ...rules.wrathful_presence import driven_by_ultimate_rage_applies, DRIVEN_BY_ULTIMATE_RAGE_NAME
        from ...rules.emperors_children import INTERNAL_RIVALRIES_NAME
        from ...utility.modifier_choice import CHOICE_LABELS, options_for_numeric_modifiers
    except Exception:
        return
    army = unit.get_parent_army() if hasattr(unit, "get_parent_army") else None
    mgr = None
    if army is not None:
        mgr = getattr(army, "emperors_children", None)
        if mgr is None:
            mgr = getattr(army, "emperors_children_detachments", None)
    internal_rivalries = bool(mgr and getattr(mgr, "internal_rivalries_applies", lambda _u: False)(unit))
    driven_by_rage = bool(driven_by_ultimate_rage_applies(unit, game_map=getattr(game, "map", None)))
    bestial_aspect = False
    try:
        if hasattr(unit, "_bestial_aspect_unholy_hunger_active"):
            bestial_aspect = bool(unit._bestial_aspect_unholy_hunger_active(game_map=getattr(game, "map", None)))
    except Exception:
        bestial_aspect = False
    avatar_of_perfection = False
    try:
        active_fn = getattr(unit, "_avatar_of_perfection_ignore_modifiers_active", None)
        if callable(active_fn):
            avatar_of_perfection = bool(active_fn(kind="move"))
    except Exception:
        avatar_of_perfection = False
    diabolical_resilience = False
    try:
        active_fn = getattr(unit, "_diabolical_resilience_ignore_modifiers_active", None)
        if callable(active_fn):
            diabolical_resilience = bool(active_fn(kind="move"))
    except Exception:
        diabolical_resilience = False
    champion_of_humanity = False
    try:
        active_fn = getattr(unit, "_firestorm_champion_of_humanity_ignore_modifiers_active", None)
        if callable(active_fn):
            champion_of_humanity = bool(active_fn(kind="move"))
    except Exception:
        champion_of_humanity = False
    move_advance_charge_ignore = False
    move_advance_charge_source = ""
    try:
        rule_fn = getattr(unit, "get_move_advance_charge_modifier_ignore_rule", None)
        rule = rule_fn() if callable(rule_fn) else None
        if isinstance(rule, dict):
            move_advance_charge_ignore = True
            move_advance_charge_source = str(rule.get("source", "") or "").strip()
    except Exception:
        move_advance_charge_ignore = False
        move_advance_charge_source = ""
    if (
        not internal_rivalries
        and not driven_by_rage
        and not bestial_aspect
        and not diabolical_resilience
        and not champion_of_humanity
        and not avatar_of_perfection
        and not move_advance_charge_ignore
    ):
        return
    if internal_rivalries:
        ability_name = INTERNAL_RIVALRIES_NAME
    elif driven_by_rage:
        ability_name = DRIVEN_BY_ULTIMATE_RAGE_NAME
    elif bestial_aspect:
        ability_name = "Bestial Aspect"
    elif diabolical_resilience:
        ability_name = "Diabolical Resilience"
    elif champion_of_humanity:
        ability_name = "Champion of Humanity"
    elif move_advance_charge_ignore:
        ability_name = move_advance_charge_source or "Move/Advance/Charge modifier ignore"
    else:
        ability_name = "Avatar of Perfection"
    try:
        if getattr(unit.round_state, "move_modifier_choice", None):
            return
    except Exception:
        pass
    queue = getattr(game, "decision_queue", None)
    if queue is not None and hasattr(queue, "list"):
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_MOVE_MODIFIER_IGNORES:
                continue
            ctx = getattr(req, "context", {}) or {}
            if str(ctx.get("unit_id", "")) == str(get_entity_id(unit)):
                return

    try:
        model = next((m for m in list(getattr(unit, "models", []) or []) if getattr(m, "is_alive", True)), None)
    except Exception:
        model = None
    if model is None:
        return
    try:
        base_val = int(getattr(model, "_movement", getattr(model, "movement", 0)) or 0)
    except Exception:
        base_val = 0
    try:
        mods, _scabrous, _map = unit._collect_characteristic_modifiers(
            model,
            "movement",
            base_val=base_val,
            base_raw=getattr(model, "_movement_raw", None),
            game_map=getattr(game, "map", None),
        )
    except Exception:
        mods = []
    options = options_for_numeric_modifiers(mods, base_val=base_val)
    if not options:
        return
    req_options = [DecisionOption.create(CHOICE_LABELS.get(opt, str(opt)), payload={"choice": opt}) for opt in options]
    request = DecisionRequest.create(
        DECISION_CHOOSE_MOVE_MODIFIER_IGNORES,
        "Choose which modifiers to ignore.",
        player_id=getattr(getattr(unit.get_parent_army(), "player", None), "id", None),
        options=req_options,
        context={
            "unit_id": get_entity_id(unit),
            "action_type": str(action_type or ""),
            "ability_name": ability_name,
        },
    )
    if hasattr(game, "request_decision"):
        game.request_decision(request)
    try:
        unit.round_state.move_modifier_choice_pending = True
    except Exception:
        pass


def _validate_select_movement_action(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit_id = str(payload.get("unit_id", "") or "")
    action = str(payload.get("action_type", "") or "")
    if not unit_id:
        return ("Movement action requires unit_id.",)
    if not action:
        return ("Movement action requires action_type.",)
    unit = get_unit(game, unit_id)
    if unit is None:
        return ("Movement action unit not found.",)
    round_state = getattr(unit, "round_state", None)
    if bool(getattr(round_state, "moved_this_round", False)):
        return ("Movement action unavailable: unit already moved this phase.",)
    if bool(getattr(round_state, "advanced_this_round", False)):
        return ("Movement action unavailable: unit already advanced this phase.",)
    if bool(getattr(round_state, "fell_back_this_round", False)):
        return ("Movement action unavailable: unit already fell back this phase.",)
    return ()


def _apply_select_movement_action(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    action = str(payload.get("action_type", "") or "")
    unit = get_unit(game, str(payload.get("unit_id", "") or ""))
    if unit is None:
        raise RuntimeError("Movement action unit missing.")
    if action == "stationary":
        try:
            from ...units.unit import MovementAction

            unit._execute_action(MovementAction.REMAIN_STATIONARY.value, (0, 0, 0), getattr(game, "map", None))
        except Exception as exc:
            raise RuntimeError(f"Stationary action failed: {exc}") from exc
    elif action == "advance":
        _maybe_request_move_modifier_choice(game, unit, action_type=action)
        queue_fn = getattr(game, "_queue_chaos_cult_desperate_devotion", None)
        if callable(queue_fn):
            queue_fn(unit=unit, action="advance")
        queued_redeploy_prompt = False
        try:
            army = unit.get_parent_army() if hasattr(unit, "get_parent_army") else None
            player = getattr(army, "player", None) if army is not None else None
        except Exception:
            player = None
        try:
            queue_fn = getattr(game, "_queue_movement_phase_advance_redeploy", None)
            if callable(queue_fn):
                queued_redeploy_prompt = queue_fn(player=player, unit=unit) is not None
        except Exception:
            queued_redeploy_prompt = False
        try:
            army = unit.get_parent_army() if hasattr(unit, "get_parent_army") else None
            mgr = getattr(army, "chaos_knights_detachments", None) if army is not None else None
            if mgr is not None:
                mgr.queue_malefic_surge_choice(unit, trigger="movement", game=game)
        except Exception:
            pass
        if bool(getattr(game, "is_authoritative", True)):
            if queued_redeploy_prompt:
                return None
            try:
                unit.prepare_advance()
            except Exception as exc:
                raise RuntimeError(f"Advance roll request failed: {exc}") from exc
    elif action in ("move", "fall_back"):
        _maybe_request_move_modifier_choice(game, unit, action_type=action)
        if action == "move":
            try:
                player = getattr(getattr(unit, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            queue_fn = getattr(game, "_queue_chaos_cult_desperate_devotion", None)
            if callable(queue_fn):
                queue_fn(unit=unit, action="move")
            try:
                queue_fn = getattr(game, "_queue_movement_phase_normal_move_redeploy", None)
                if callable(queue_fn):
                    queue_fn(player=player, unit=unit)
            except Exception:
                pass
            try:
                queue_fn = getattr(game, "_queue_movement_phase_normal_move_weapon_attacks_bonus", None)
                if callable(queue_fn):
                    queue_fn(player=player, unit=unit)
            except Exception:
                pass
            try:
                queue_fn = getattr(game, "_queue_movement_phase_flickerjump", None)
                if callable(queue_fn):
                    queue_fn(player=player, unit=unit)
            except Exception:
                pass
        try:
            army = unit.get_parent_army() if hasattr(unit, "get_parent_army") else None
            mgr = getattr(army, "chaos_knights_detachments", None) if army is not None else None
            if mgr is not None:
                mgr.queue_malefic_surge_choice(unit, trigger="movement", game=game)
        except Exception:
            pass
    return None


def _resolve_charge_targets(game: object, ctx: dict | None) -> list[object]:
    context = dict(ctx or {})
    resolved: list[object] = []
    seen: set[str] = set()
    for raw_value in list(context.get("target_unit_ids", []) or []):
        target_id = str(raw_value or "").strip()
        if not target_id or target_id in seen:
            continue
        seen.add(target_id)
        target = get_unit(game, target_id)
        if target is None:
            continue
        get_root = getattr(target, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else target
        if root is None:
            continue
        resolved.append(root)
    return resolved


def _validate_move_unit(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit_id = str(payload.get("unit_id", "") or request.context.get("unit_id", "") or "")
    if not unit_id:
        return ("Move unit requires unit_id.",)
    unit = get_unit(game, unit_id)
    if unit is None:
        return ("Move unit: unit not found.",)
    ctx = dict(getattr(request, "context", {}) or {})
    allow_skip = bool(ctx.get("allow_skip", True))
    if is_skip_choice(request, result):
        if not allow_skip:
            return ("Move unit: skipping is not allowed for this placement.",)
        return ()
    model_positions = result.payload.get("model_positions")
    errors = validate_model_positions(game, unit, model_positions, context="Move unit")
    if errors:
        return errors
    allowed_ids = ctx.get("allowed_model_ids")
    placement_kind = str(ctx.get("placement_kind", "") or "")
    if allowed_ids is not None:
        allowed_set = {str(v) for v in list(allowed_ids or []) if v is not None}
        if not allowed_set:
            return ("Move unit: allowed_model_ids is empty.",)
        seen: set[str] = set()
        for entry in list(model_positions or []):
            mid = str(entry.get("model_id", "") or "")
            if not mid:
                return ("Move unit: model_positions missing model_id.",)
            if mid in seen:
                return ("Move unit: duplicate model_id in model_positions.",)
            seen.add(mid)
        if seen != allowed_set:
            return ("Move unit: model_positions must include all and only allowed_model_ids.",)
    if placement_kind or allowed_ids is not None:
        placement_errors = _validate_placement_positions(
            game,
            unit,
            model_positions,
            allowed_ids=allowed_ids,
            placement_kind=placement_kind,
            ctx=ctx,
        )
        if placement_errors:
            return placement_errors
    movement_type = str(payload.get("movement_type", "") or ctx.get("movement_type", "") or "move").strip().lower()
    reactive_movement_type = str(ctx.get("reactive_move_movement_type", "") or "").strip().lower()
    validate_normal_move_sweep = movement_type == "move" or (
        movement_type == "reactive" and reactive_movement_type == "move"
    )
    if movement_type == "advance":
        advance_denial_errors = _validate_advance_start_end_denial(game, unit, model_positions)
        if advance_denial_errors:
            return advance_denial_errors
    path_witness_ref = str(result.payload.get("path_witness_ref", "") or payload.get("path_witness_ref", "") or "")
    if path_witness_ref:
        store = getattr(game, "path_witness_store", None)
        if store is None:
            return ("Move unit: path witness store missing.",)
        witness = store.get(path_witness_ref)
        if witness is None:
            return ("Move unit: path witness_ref not found.",)
        witness_errors = validate_witness_contiguity(witness, list(model_positions or []))
        if witness_errors:
            return tuple(witness_errors)
    if validate_normal_move_sweep:
        start_positions = current_model_positions(unit)
        end_positions: list[dict] = []
        for entry in list(model_positions or []):
            enriched = dict(entry or {})
            model = get_model(game, str(enriched.get("model_id", "") or ""))
            base = getattr(model, "model_base", None) if model is not None else None
            radius = list(getattr(base, "radius", []) or [])
            if len(radius) < 2:
                r = float(getattr(base, "get_radius", lambda: 0.0)()) if base is not None else 0.0
                radius = [r, r]
            base_type = str(getattr(getattr(base, "base_type", None), "name", "CIRCULAR"))
            enriched["radius"] = [float(radius[0]), float(radius[1])]
            enriched["base_type"] = base_type
            end_positions.append(enriched)
        game_map = getattr(game, "map", None)
        enemy_bases: list[dict] = []
        own_army_getter = getattr(unit, "get_parent_army", None)
        own_army = own_army_getter() if callable(own_army_getter) else getattr(unit, "parent_army", None)
        for other_unit in list(getattr(game_map, "units", []) or []):
            if other_unit is unit:
                continue
            other_army_getter = getattr(other_unit, "get_parent_army", None)
            other_army = other_army_getter() if callable(other_army_getter) else getattr(other_unit, "parent_army", None)
            if own_army is not None and other_army is own_army:
                continue
            for other_model in list(getattr(other_unit, "models", []) or []):
                other_alive_value = getattr(other_model, "is_alive", True)
                other_alive = bool(other_alive_value() if callable(other_alive_value) else other_alive_value)
                if not other_alive:
                    continue
                other_base = getattr(other_model, "model_base", None)
                if other_base is None:
                    continue
                enemy_bases.append(
                    {
                        "x": float(getattr(other_base, "x", 0.0)),
                        "y": float(getattr(other_base, "y", 0.0)),
                        "z": float(getattr(other_base, "z", 0.0)),
                        "radius": float(getattr(other_base, "get_radius", lambda: 0.0)()),
                    }
                )
        crossing_errors = detect_normal_move_engagement_crossing(
            start_positions=start_positions,
            end_positions=end_positions,
            enemy_bases=enemy_bases,
        )
        if crossing_errors:
            return tuple(crossing_errors)
        tight_errors, _profiles = detect_tight_clearance_orientation_violations(
            start_positions=start_positions,
            end_positions=end_positions,
            enemy_bases=enemy_bases,
            yaw_band_deg=15.0,
        )
        if tight_errors:
            return tuple(tight_errors)
        blocking_terrain_polygons = []
        terrain_features = list(getattr(game_map, "terrain_features", []) or [])
        if terrain_features:
            from ...utility.calcs import MovementType, get_terrain_blocking_polygons

            for terrain_feature in terrain_features:
                blocking_terrain_polygons.extend(
                    get_terrain_blocking_polygons(unit, terrain_feature, movement_type=MovementType.MOVE)
                )
        terrain_errors = detect_terrain_sweep_collisions(
            start_positions=start_positions,
            end_positions=end_positions,
            blocking_terrain_polygons=blocking_terrain_polygons,
        )
        if terrain_errors:
            return tuple(terrain_errors)
    tactica_mode = str(ctx.get("tactica_obliqua_mode", "") or "").strip().lower()
    if tactica_mode == "battleline_6":
        tactica_errors = _validate_tactica_obliqua_battleline_positions(
            game,
            unit,
            model_positions,
            ctx=ctx,
        )
        if tactica_errors:
            return tactica_errors
    wraithlike_errors = _validate_wraithlike_retreat_end_positions(
        game,
        unit,
        model_positions,
        ctx=ctx,
    )
    if wraithlike_errors:
        return wraithlike_errors
    heresy_errors = _validate_heresy_begets_retribution_positions(
        game,
        unit,
        model_positions,
        ctx=ctx,
    )
    if heresy_errors:
        return heresy_errors
    predatory_pursuit_errors = _validate_predatory_pursuit_positions(
        game,
        unit,
        model_positions,
        ctx=ctx,
    )
    if predatory_pursuit_errors:
        return predatory_pursuit_errors
    if movement_type == "charge":
        target_units = _resolve_charge_targets(game, ctx)
        if not target_units:
            return ("Move unit: charge movement requires declared target_unit_ids.",)
        game_map = getattr(game, "map", None)
        if game_map is None:
            return ("Move unit: charge movement requires an active game map.",)
        validate_charge_end_state = getattr(unit, "validate_charge_end_state", None)
        if not callable(validate_charge_end_state):
            return ("Move unit: charge movement requires validate_charge_end_state().",)
        ok, reason = validate_charge_end_state(target_units, game_map)
        if not ok:
            return (str(reason or "Move unit: charge must end in a legal engagement state."),)
    return ()


def _wraithlike_retreat_transport_requirement(
    game: object,
    unit: object,
    model_positions: object,
    *,
    ctx: dict | None = None,
) -> dict:
    context = dict(ctx or {})
    if not bool(context.get("wraithlike_retreat_require_embark", False)):
        return {"required": False, "valid": True, "transport": None}
    if unit is None:
        return {"required": True, "valid": False, "reason": "Move unit: Wraithlike Retreat requires a valid unit."}

    transport_ids = []
    for value in list(context.get("wraithlike_retreat_transport_ids", []) or []):
        key = str(value or "").strip()
        if key:
            transport_ids.append(key)
    if not transport_ids:
        return {
            "required": True,
            "valid": False,
            "reason": "Move unit: Wraithlike Retreat requires a friendly Drukhari Transport to embark.",
        }

    moving_army_getter = getattr(unit, "get_parent_army", None)
    moving_army = moving_army_getter() if callable(moving_army_getter) else getattr(unit, "parent_army", None)
    transports: list[object] = []
    seen_transport_ids: set[str] = set()
    for transport_id in sorted(transport_ids):
        transport = get_unit(game, transport_id)
        if transport is None:
            continue
        get_root = getattr(transport, "get_attached_unit_root", None)
        transport_root = get_root() if callable(get_root) else transport
        if transport_root is None:
            continue
        root_id = str(get_entity_id(transport_root) or "")
        if root_id and root_id in seen_transport_ids:
            continue
        if root_id:
            seen_transport_ids.add(root_id)
        transport_army_getter = getattr(transport_root, "get_parent_army", None)
        transport_army = (
            transport_army_getter() if callable(transport_army_getter) else getattr(transport_root, "parent_army", None)
        )
        if moving_army is not None and transport_army is not moving_army:
            continue
        is_alive = getattr(transport_root, "is_alive", None)
        if callable(is_alive):
            if not bool(is_alive()):
                continue
        elif bool(getattr(transport_root, "is_alive", True)) is False:
            continue
        if not bool(getattr(transport_root, "deployed", True)):
            continue
        if bool(getattr(transport_root, "is_embarked", False)) or getattr(transport_root, "embarked_in", None) is not None:
            continue
        reserve_status = str(getattr(transport_root, "reserve_status", "deployed") or "deployed").strip().lower()
        if reserve_status and reserve_status != "deployed":
            continue
        is_in_reserves = getattr(transport_root, "is_in_reserves", None)
        if callable(is_in_reserves) and bool(is_in_reserves()):
            continue
        can_transport = getattr(transport_root, "can_transport", None)
        if not callable(can_transport) or not bool(can_transport(unit)):
            continue
        transports.append(transport_root)
    if not transports:
        return {
            "required": True,
            "valid": False,
            "reason": "Move unit: Wraithlike Retreat requires ending wholly within 3\" horizontal and 5\" vertical of a transport that can embark this unit.",
        }

    try:
        from ...utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
    except ImportError:
        return {
            "required": True,
            "valid": False,
            "reason": "Move unit: Wraithlike Retreat transport-distance validation is unavailable.",
        }

    positions_by_id: dict[str, tuple[float, float, float, float]] = {}
    for entry in list(model_positions or []):
        model_id = str(entry.get("model_id", "") or "")
        if not model_id:
            continue
        pos = entry.get("position") or []
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            continue
        try:
            x = float(pos[0])
            y = float(pos[1])
            z = float(pos[2]) if len(pos) > 2 else 0.0
        except (TypeError, ValueError):
            continue
        facing_raw = entry.get("facing", 0.0)
        try:
            facing = float(facing_raw if facing_raw is not None else 0.0)
        except (TypeError, ValueError):
            facing = 0.0
        positions_by_id[model_id] = (x, y, z, facing)

    get_models = getattr(unit, "get_attached_unit_models", None)
    moving_models = list(get_models() or []) if callable(get_models) else list(getattr(unit, "models", []) or [])
    moving_bases: list[object] = []
    create_base = getattr(unit, "_create_potential_base", None)
    for model in list(moving_models or []):
        if model is None:
            continue
        alive_value = getattr(model, "is_alive", True)
        alive = bool(alive_value() if callable(alive_value) else alive_value)
        if not alive:
            continue
        model_id = str(get_entity_id(model) or "")
        base = None
        if model_id in positions_by_id and callable(create_base):
            x, y, z, facing = positions_by_id[model_id]
            try:
                base = create_base(x, y, z, facing, model=model)
            except (AttributeError, TypeError, ValueError):
                base = None
        if base is None:
            base = getattr(model, "model_base", None)
        if base is None:
            return {
                "required": True,
                "valid": False,
                "reason": "Move unit: Wraithlike Retreat could not resolve model bases for embark validation.",
            }
        moving_bases.append(base)
    if not moving_bases:
        return {"required": True, "valid": False, "reason": "Move unit: Wraithlike Retreat requires alive models to move."}

    for transport in sorted(transports, key=lambda item: str(get_entity_id(item) or "")):
        transport_models_getter = getattr(transport, "get_attached_unit_models", None)
        transport_models = (
            list(transport_models_getter() or [])
            if callable(transport_models_getter)
            else list(getattr(transport, "models", []) or [])
        )
        transport_bases: list[object] = []
        for model in list(transport_models or []):
            if model is None:
                continue
            alive_value = getattr(model, "is_alive", True)
            alive = bool(alive_value() if callable(alive_value) else alive_value)
            if not alive:
                continue
            base = getattr(model, "model_base", None)
            if base is not None:
                transport_bases.append(base)
        if not transport_bases:
            continue
        all_within = True
        for moving_base in moving_bases:
            model_within = False
            for transport_base in transport_bases:
                try:
                    horizontal = float(horizontal_distance_between_bases_2d(moving_base, transport_base))
                    vertical = float(vertical_distance_between_bases(moving_base, transport_base))
                except (AttributeError, TypeError, ValueError):
                    continue
                if horizontal <= 3.0 + 1e-6 and vertical <= 5.0 + 1e-6:
                    model_within = True
                    break
            if not model_within:
                all_within = False
                break
        if all_within:
            return {"required": True, "valid": True, "transport": transport}

    return {
        "required": True,
        "valid": False,
        "reason": "Move unit: Wraithlike Retreat move must end wholly within 3\" horizontal and 5\" vertical of a friendly Drukhari Transport that can embark this unit.",
    }


def _validate_wraithlike_retreat_end_positions(
    game: object,
    unit: object,
    model_positions: object,
    *,
    ctx: dict | None = None,
) -> Sequence[str]:
    check = _wraithlike_retreat_transport_requirement(
        game,
        unit,
        model_positions,
        ctx=ctx,
    )
    if not bool(check.get("required", False)):
        return ()
    if bool(check.get("valid", False)):
        return ()
    return (str(check.get("reason", "") or "Move unit: Wraithlike Retreat embark requirement failed."),)


def _validate_placement_positions(
    game: object,
    unit: object,
    model_positions: object,
    *,
    allowed_ids: object = None,
    placement_kind: str | None = None,
    ctx: dict | None = None,
) -> Sequence[str]:
    if not isinstance(model_positions, list) or not model_positions:
        return ("Move unit: placement requires model_positions.",)
    game_map = getattr(game, "map", None)
    if game_map is None:
        return ()

    from ...battlefield.map import validate_ruins_placement
    from ...utility.placement_validation import bases_overlap_3d
    from ...utility.calcs import validate_unit_coherency_after_movement
    from ...utility.entity_ids import get_entity_id

    allowed_set = None
    if allowed_ids is not None:
        allowed_set = {str(v) for v in list(allowed_ids or []) if v is not None}

    positions_by_id: dict[str, tuple[float, float, float, float]] = {}
    candidate_bases: dict[str, object] = {}

    collision_fn = getattr(game_map, "check_collision_with_obstacles", None)
    if not callable(collision_fn):
        collision_fn = getattr(game_map, "check_collision_with_terrain", None)

    for entry in list(model_positions or []):
        mid = str(entry.get("model_id", "") or "")
        if not mid:
            return ("Move unit: model_positions missing model_id.",)
        model = get_model(game, mid)
        if model is None:
            return (f"Move unit: model not found: {mid}",)
        pos = entry.get("position") or []
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            return ("Move unit: model_positions missing position.",)
        x = float(pos[0])
        y = float(pos[1])
        z = float(pos[2]) if len(pos) > 2 else float(getattr(model.model_base, "z", 0.0))
        facing = entry.get("facing", None)
        if facing is None:
            facing = float(getattr(model.model_base, "facing", 0.0))
        else:
            facing = float(facing)
        positions_by_id[mid] = (x, y, z, facing)

        if hasattr(game_map, "is_within_boundary") and not game_map.is_within_boundary(model, destination=(x, y)):
            return ("Move unit: placement outside battlefield boundary.",)
        if callable(collision_fn) and collision_fn(model, destination=(x, y)):
            return ("Move unit: placement collides with terrain.",)
        ruins_validation = validate_ruins_placement(unit, (x, y, z), game_map.terrain_features, moving_model=model)
        if not ruins_validation.get("valid", False):
            return (f"Move unit: RUINS placement invalid: {ruins_validation.get('reason', 'invalid')}",)
        surface_validation_fn = getattr(game_map, "validate_model_surface_placement", None)
        if callable(surface_validation_fn):
            surface_validation = surface_validation_fn(model, (x, y, z))
            if not surface_validation.get("valid", False):
                return (f"Move unit: {surface_validation.get('reason', 'invalid elevated-surface placement')}",)

        if hasattr(unit, "_create_potential_base"):
            base = unit._create_potential_base(x, y, z, facing, model=model)
        else:
            base = getattr(model, "model_base", None)
        if base is None:
            return ("Move unit: unable to resolve model base for placement.",)
        candidate_bases[mid] = base

    # Check overlap against existing models in this unit (excluding pending/placed models)
    for other in list(getattr(unit, "models", []) or []):
        if not getattr(other, "is_alive", True):
            continue
        if getattr(other, "_pending_placement", False):
            continue
        other_id = str(get_entity_id(other))
        if other_id in candidate_bases:
            continue
        other_base = getattr(other, "model_base", None)
        if other_base is None:
            continue
        for base in candidate_bases.values():
            if bases_overlap_3d(base, other_base):
                return ("Move unit: placement overlaps another model in the unit.",)

    # Check overlap among newly placed models
    ids = list(candidate_bases.keys())
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if bases_overlap_3d(candidate_bases[ids[i]], candidate_bases[ids[j]]):
                return ("Move unit: placement overlaps between placed models.",)

    # Check overlap against other units on the battlefield
    for other_unit in list(getattr(game_map, "units", []) or []):
        if other_unit is unit:
            continue
        try:
            other_models = list(other_unit.get_models_for_collision() or [])
        except Exception:
            other_models = list(getattr(other_unit, "models", []) or [])
        for other in list(other_models or []):
            if not getattr(other, "is_alive", True):
                continue
            other_base = getattr(other, "model_base", None)
            if other_base is None:
                continue
            for base in candidate_bases.values():
                if bases_overlap_3d(base, other_base):
                    return ("Move unit: placement overlaps another unit.",)

    deployment_special_chain = (
        str(placement_kind or "") == "deployment"
        and is_convergence_of_dominion_deployment_unit(unit)
    )
    if deployment_special_chain:
        chain_entries: list[tuple[str, object]] = []
        for model in list(getattr(unit, "models", []) or []):
            if not getattr(model, "is_alive", True):
                continue
            model_id = str(get_entity_id(model))
            base = candidate_bases.get(model_id)
            if base is None:
                base = getattr(model, "model_base", None)
            label = str(getattr(model, "name", "") or f"Model {model_id}")
            chain_entries.append((label, base))
        chain_valid, chain_reason = validate_convergence_of_dominion_deployment(chain_entries)
        if not chain_valid:
            return (f"Move unit: deployment invalid: {chain_reason}",)
    else:
        # Coherency validation (placements must end in coherency)
        final_positions: list[tuple[float, float, float]] = []
        for model in list(getattr(unit, "models", []) or []):
            mid = str(get_entity_id(model))
            if mid in positions_by_id:
                x, y, z, _f = positions_by_id[mid]
                final_positions.append((x, y, z))
            else:
                try:
                    pos = model.get_location()
                    final_positions.append((float(pos[0]), float(pos[1]), float(pos[2])))
                except Exception:
                    final_positions.append((0.0, 0.0, 0.0))

        is_coherent, _non_coherent = validate_unit_coherency_after_movement(
            unit, final_positions, ignore_pending=False
        )
        if not is_coherent:
            return ("Move unit: placement breaks unit coherency.",)

    # Ensure only allowed ids are placed (if provided)
    if allowed_set is not None:
        if set(candidate_bases.keys()) != allowed_set:
            return ("Move unit: placement must include all allowed models.",)

    if str(placement_kind or "") == "deployment":
        deployment_errors = _validate_deployment_positions(game, unit, model_positions)
        if deployment_errors:
            return deployment_errors
    if str(placement_kind or "") == "reserves_arrival":
        reserves_errors = _validate_reserves_arrival_positions(game, unit, model_positions, ctx=ctx)
        if reserves_errors:
            return reserves_errors
    if str(placement_kind or "") in ("aeldari_unshrouded_truth", "advance_redeploy_9h", "normal_move_redeploy_9h"):
        unshrouded_errors = _validate_aeldari_unshrouded_truth_positions(
            game,
            unit,
            candidate_bases,
            placement_kind=str(placement_kind or ""),
            ctx=ctx,
        )
        if unshrouded_errors:
            return unshrouded_errors

    return ()


def _validate_aeldari_unshrouded_truth_positions(
    game: object,
    unit: object,
    candidate_bases: dict[str, object],
    *,
    placement_kind: str = "",
    ctx: dict | None = None,
) -> Sequence[str]:
    if not candidate_bases:
        return ()
    game_map = getattr(game, "map", None)
    if game_map is None:
        return ()

    try:
        from ...utility.aura_utils import horizontal_distance_between_bases_2d
    except Exception:
        return ()

    own_army_getter = getattr(unit, "get_parent_army", None)
    own_army = own_army_getter() if callable(own_army_getter) else getattr(unit, "parent_army", None)

    min_enemy_distance = 9.0
    context = dict(ctx or {})
    try:
        requested_distance = float(context.get("min_enemy_distance_horiz", 9.0) or 9.0)
    except Exception:
        requested_distance = 9.0
    if requested_distance > 0:
        min_enemy_distance = float(requested_distance)

    for enemy in list(getattr(game_map, "units", []) or []):
        if enemy is unit:
            continue
        enemy_getter = getattr(enemy, "get_attached_unit_root", None)
        enemy_root = enemy_getter() if callable(enemy_getter) else enemy
        if enemy_root is None:
            continue
        enemy_army_getter = getattr(enemy_root, "get_parent_army", None)
        enemy_army = enemy_army_getter() if callable(enemy_army_getter) else getattr(enemy_root, "parent_army", None)
        if own_army is not None and enemy_army is own_army:
            continue
        if not bool(getattr(enemy_root, "deployed", True)):
            continue
        if bool(getattr(enemy_root, "is_embarked", False)) or getattr(enemy_root, "embarked_in", None) is not None:
            continue
        reserve_status = str(getattr(enemy_root, "reserve_status", "deployed") or "deployed")
        if reserve_status != "deployed":
            continue

        enemy_models = list(getattr(enemy_root, "models", []) or [])
        for enemy_model in enemy_models:
            enemy_alive_value = getattr(enemy_model, "is_alive", True)
            enemy_alive = bool(enemy_alive_value() if callable(enemy_alive_value) else enemy_alive_value)
            if not enemy_alive:
                continue
            enemy_base = getattr(enemy_model, "model_base", None)
            if enemy_base is None:
                continue
            for base in candidate_bases.values():
                try:
                    horizontal = float(horizontal_distance_between_bases_2d(base, enemy_base))
                except Exception:
                    continue
                if horizontal <= float(min_enemy_distance) + 1e-6:
                    distance_text = (
                        str(int(min_enemy_distance))
                        if abs(float(min_enemy_distance) - round(float(min_enemy_distance))) <= 1e-6
                        else str(min_enemy_distance)
                    )
                    if placement_kind == "aeldari_unshrouded_truth":
                        return (
                            f"Move unit: Unshrouded Truth placement must be more than {distance_text}\" horizontally from enemy models.",
                        )
                    return (f"Move unit: placement must be more than {distance_text}\" horizontally from enemy models.",)

    return ()


def _validate_advance_start_end_denial(
    game: object,
    unit: object,
    model_positions: object,
) -> Sequence[str]:
    if unit is None:
        return ()
    if not isinstance(model_positions, list) or not model_positions:
        return ()
    game_map = getattr(game, "map", None)
    if game_map is None:
        return ()

    try:
        from ...utility.aura_utils import distance_between_bases_3d
    except Exception:
        return ()

    positions_by_id: dict[str, tuple[float, float, float, float]] = {}
    for entry in list(model_positions or []):
        mid = str(entry.get("model_id", "") or "")
        if not mid:
            continue
        pos = entry.get("position") or []
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            continue
        try:
            x = float(pos[0])
            y = float(pos[1])
            z = float(pos[2]) if len(pos) > 2 else 0.0
        except (TypeError, ValueError):
            continue
        facing_raw = entry.get("facing", 0.0)
        try:
            facing = float(facing_raw if facing_raw is not None else 0.0)
        except (TypeError, ValueError):
            facing = 0.0
        positions_by_id[mid] = (x, y, z, facing)

    if not positions_by_id:
        return ()

    moving_army = None
    try:
        moving_army = unit.get_parent_army()
    except Exception:
        moving_army = None

    moving_model_bases: list[tuple[object, object]] = []
    for moving_model in list(getattr(unit, "models", []) or []):
        if moving_model is None:
            continue
        moving_alive_attr = getattr(moving_model, "is_alive", True)
        moving_alive = bool(moving_alive_attr() if callable(moving_alive_attr) else moving_alive_attr)
        if not moving_alive:
            continue
        mid = str(get_entity_id(moving_model) or "")
        if not mid or mid not in positions_by_id:
            continue
        start_base = getattr(moving_model, "model_base", None)
        if start_base is None:
            continue
        x, y, z, facing = positions_by_id[mid]
        end_base = None
        if hasattr(unit, "_create_potential_base"):
            try:
                end_base = unit._create_potential_base(x, y, z, facing, model=moving_model)
            except Exception:
                end_base = None
        if end_base is None:
            continue
        moving_model_bases.append((start_base, end_base))
    if not moving_model_bases:
        return ()

    def _first_advance_denial_violation(specs: list[dict], source_bases: list[object]) -> str:
        for spec in specs:
            try:
                range_value = float(spec.get("range", 0) or 0)
            except Exception:
                range_value = 0.0
            if range_value <= 0:
                continue
            source = str(spec.get("source", "") or "Advance denial").strip() or "Advance denial"
            for source_base in source_bases:
                if source_base is None:
                    continue
                for start_base, end_base in moving_model_bases:
                    try:
                        start_dist = float(distance_between_bases_3d(start_base, source_base))
                    except Exception:
                        start_dist = float("inf")
                    try:
                        end_dist = float(distance_between_bases_3d(end_base, source_base))
                    except Exception:
                        end_dist = float("inf")
                    if start_dist <= range_value or end_dist <= range_value:
                        return f"Advance move cannot start or end within {int(range_value)}\" of {source}."
        return ""

    for enemy in list(getattr(game_map, "units", []) or []):
        if enemy is None:
            continue
        try:
            enemy_root = enemy.get_attached_unit_root() if hasattr(enemy, "get_attached_unit_root") else enemy
        except Exception:
            enemy_root = enemy
        if enemy_root is None:
            continue
        try:
            if enemy_root.get_parent_army() is moving_army:
                continue
        except Exception:
            pass
        try:
            if not enemy_root.is_alive():
                continue
        except Exception:
            continue
        if not bool(getattr(enemy_root, "deployed", True)):
            continue
        try:
            if enemy_root.is_in_reserves() or enemy_root.is_embarked:
                continue
        except Exception:
            pass

        try:
            enemy_models = list(enemy_root.get_attached_unit_models() or [])
        except Exception:
            enemy_models = list(getattr(enemy_root, "models", []) or [])
        alive_enemy_models: list[object] = []
        for enemy_model in enemy_models:
            if enemy_model is None:
                continue
            enemy_alive_attr = getattr(enemy_model, "is_alive", True)
            enemy_alive = bool(enemy_alive_attr() if callable(enemy_alive_attr) else enemy_alive_attr)
            if enemy_alive:
                alive_enemy_models.append(enemy_model)
        if not alive_enemy_models:
            continue

        get_unit_specs = getattr(enemy_root, "unit_no_advance_start_or_end_within_specs", None)
        if callable(get_unit_specs):
            try:
                unit_specs = list(get_unit_specs() or [])
            except Exception:
                unit_specs = []
            if unit_specs:
                unit_bases = [getattr(model, "model_base", None) for model in alive_enemy_models]
                violation = _first_advance_denial_violation(unit_specs, unit_bases)
                if violation:
                    return (violation,)

        get_model_specs = getattr(enemy_root, "model_no_advance_start_or_end_within_specs", None)
        if not callable(get_model_specs):
            continue
        for enemy_model in alive_enemy_models:
            try:
                model_specs = list(get_model_specs(enemy_model) or [])
            except Exception:
                model_specs = []
            if not model_specs:
                continue
            enemy_base = getattr(enemy_model, "model_base", None)
            if enemy_base is None:
                continue
            violation = _first_advance_denial_violation(model_specs, [enemy_base])
            if violation:
                return (violation,)

    return ()


def _validate_tactica_obliqua_battleline_positions(
    game: object,
    unit: object,
    model_positions: object,
    *,
    ctx: dict | None = None,
) -> Sequence[str]:
    if unit is None:
        return ()
    if not isinstance(model_positions, list) or not model_positions:
        return ("Move unit: Tactica Obliqua requires model_positions.",)
    game_map = getattr(game, "map", None)
    if game_map is None:
        return ()
    try:
        from ...utility.aura_utils import model_wholly_within_range_of_unit
    except Exception:
        return ()

    context = dict(ctx or {})
    try:
        required_range = float(context.get("tactica_obliqua_battleline_range", 6) or 6)
    except Exception:
        required_range = 6.0
    if required_range <= 0:
        required_range = 6.0

    positions_by_id: dict[str, tuple[float, float, float, float]] = {}
    for entry in list(model_positions or []):
        model_id = str(entry.get("model_id", "") or "")
        if not model_id:
            continue
        pos = entry.get("position") or []
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            continue
        try:
            x = float(pos[0])
            y = float(pos[1])
            z = float(pos[2]) if len(pos) > 2 else 0.0
        except (TypeError, ValueError):
            continue
        facing_raw = entry.get("facing", 0.0)
        try:
            facing = float(facing_raw if facing_raw is not None else 0.0)
        except (TypeError, ValueError):
            facing = 0.0
        positions_by_id[model_id] = (x, y, z, facing)

    get_root = getattr(unit, "get_attached_unit_root", None)
    moving_root = get_root() if callable(get_root) else unit
    if moving_root is None:
        return ("Move unit: Tactica Obliqua requires a valid unit.",)
    get_army = getattr(moving_root, "get_parent_army", None)
    moving_army = get_army() if callable(get_army) else getattr(moving_root, "parent_army", None)
    if moving_army is None:
        return ("Move unit: Tactica Obliqua requires a parent army.",)

    battleline_sources: list[object] = []
    seen_roots: set[str] = set()
    for candidate in list(getattr(game_map, "units", []) or []):
        if candidate is None:
            continue
        cand_get_root = getattr(candidate, "get_attached_unit_root", None)
        cand_root = cand_get_root() if callable(cand_get_root) else candidate
        if cand_root is None:
            continue
        root_id = str(get_entity_id(cand_root) or "")
        if root_id and root_id in seen_roots:
            continue
        if root_id:
            seen_roots.add(root_id)
        cand_get_army = getattr(cand_root, "get_parent_army", None)
        cand_army = cand_get_army() if callable(cand_get_army) else getattr(cand_root, "parent_army", None)
        if cand_army is not moving_army:
            continue
        alive_fn = getattr(cand_root, "is_alive", None)
        if callable(alive_fn):
            if not bool(alive_fn()):
                continue
        elif bool(getattr(cand_root, "is_alive", True)) is False:
            continue
        if not bool(getattr(cand_root, "deployed", True)):
            continue
        is_in_reserves = getattr(cand_root, "is_in_reserves", None)
        if callable(is_in_reserves) and bool(is_in_reserves()):
            continue
        if bool(getattr(cand_root, "is_embarked", False)) or getattr(cand_root, "embarked_in", None) is not None:
            continue
        has_any_keyword = getattr(cand_root, "has_any_keyword", None)
        if not callable(has_any_keyword):
            continue
        if not bool(has_any_keyword("ADEPTUS MECHANICUS")):
            continue
        if not bool(has_any_keyword("BATTLELINE")):
            continue
        battleline_sources.append(cand_root)

    if not battleline_sources:
        return (
            "Move unit: Tactica Obliqua battleline move requires at least one friendly ADEPTUS MECHANICUS BATTLELINE unit.",
        )

    create_base = getattr(unit, "_create_potential_base", None)
    for model in list(getattr(unit, "models", []) or []):
        if model is None:
            continue
        alive_value = getattr(model, "is_alive", True)
        alive = bool(alive_value() if callable(alive_value) else alive_value)
        if not alive:
            continue
        model_id = str(get_entity_id(model) or "")
        if not model_id:
            continue
        candidate_base = None
        placement = positions_by_id.get(model_id)
        if placement is not None and callable(create_base):
            x, y, z, facing = placement
            try:
                candidate_base = create_base(x, y, z, facing, model=model)
            except Exception:
                candidate_base = None
        if candidate_base is None:
            candidate_base = getattr(model, "model_base", None)
        if candidate_base is None:
            return ("Move unit: Tactica Obliqua could not resolve a model base.",)
        proxy_model = SimpleNamespace(model_base=candidate_base, is_alive=True)
        within_any = False
        for source in list(battleline_sources):
            if model_wholly_within_range_of_unit(
                source,
                proxy_model,
                float(required_range),
                use_attached_aggregate=True,
            ):
                within_any = True
                break
        if not within_any:
            return (
                f"Move unit: Tactica Obliqua requires every model to end wholly within {int(required_range)}\" of one or more friendly ADEPTUS MECHANICUS BATTLELINE units.",
            )
    return ()


def _validate_deployment_positions(
    game: object,
    unit: object,
    model_positions: object,
) -> Sequence[str]:
    validate_fn = getattr(game, "is_valid_single_model_deployment", None)
    if not callable(validate_fn):
        return ()
    player_id = None
    army = getattr(unit, "get_parent_army", None)
    if callable(army):
        army = army()
    else:
        army = getattr(unit, "parent_army", None)
    if army is not None:
        player = getattr(army, "player", None)
        player_id = getattr(player, "id", None) if player is not None else None
    if not player_id:
        return ("Move unit: deployment requires player_id.",)
    for entry in list(model_positions or []):
        model_id = str(entry.get("model_id", "") or "")
        if not model_id:
            return ("Move unit: deployment missing model_id.",)
        model = get_model(game, model_id)
        if model is None:
            return (f"Move unit: deployment model not found: {model_id}",)
        pos = entry.get("position") or []
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            return ("Move unit: deployment position missing coordinates.",)
        x = float(pos[0])
        y = float(pos[1])
        z = float(pos[2]) if len(pos) > 2 else float(getattr(model.model_base, "z", 0.0))
        check = validate_fn(model, x, y, z, player_id)
        if not bool(check.get("valid", False)):
            reason = str(check.get("reason", "") or "invalid")
            return (f"Move unit: deployment invalid: {reason}",)
    return ()


def _validate_reserves_arrival_positions(
    game: object,
    unit: object,
    model_positions: object,
    *,
    ctx: dict | None = None,
) -> Sequence[str]:
    evaluation = _evaluate_reserves_arrival_positions(game, unit, model_positions, ctx=ctx)
    if evaluation.get("errors"):
        return tuple(evaluation.get("errors") or [])
    return ()


def _evaluate_reserves_arrival_positions(
    game: object,
    unit: object,
    model_positions: object,
    *,
    ctx: dict | None = None,
) -> dict:
    errors: list[str] = []
    context = dict(ctx or {})
    if unit is None:
        return {"errors": ["Reserves arrival requires a unit."]}
    if not bool(getattr(unit, "is_in_reserves", lambda: False)()):
        return {"errors": ["Unit is not in reserves."]}
    ignore_turn_requirement = bool(context.get("reserves_arrival_ignore_turn_requirement", False))
    if not ignore_turn_requirement:
        try:
            if not unit.can_arrive_from_reserves(getattr(game, "turn", 0)):
                return {"errors": ["Unit cannot arrive from reserves this turn."]}
        except Exception:
            return {"errors": ["Reserves arrival eligibility check failed."]}

    if not isinstance(model_positions, list) or not model_positions:
        return {"errors": ["Reserves arrival requires model positions."]}

    from ...utility.entity_ids import get_entity_id

    positions_by_id: dict[str, tuple[float, float, float, float]] = {}
    for entry in list(model_positions or []):
        model_id = str(entry.get("model_id", "") or "")
        if not model_id:
            return {"errors": ["Reserves arrival missing model_id."]}
        pos = entry.get("position") or []
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            return {"errors": ["Reserves arrival missing position coordinates."]}
        try:
            x = float(pos[0])
            y = float(pos[1])
            z = float(pos[2]) if len(pos) > 2 else 0.0
        except (TypeError, ValueError):
            return {"errors": ["Reserves arrival position coordinates must be numeric."]}
        facing = entry.get("facing")
        if facing is None:
            facing = 0.0
        try:
            facing_val = float(facing)
        except (TypeError, ValueError):
            facing_val = 0.0
        positions_by_id[model_id] = (x, y, z, facing_val)

    prospective: list[tuple[float, float, float, float]] = []
    for model in list(getattr(unit, "models", []) or []):
        mid = str(get_entity_id(model))
        if mid not in positions_by_id:
            return {"errors": ["Reserves arrival missing positions for all models."]}
        prospective.append(positions_by_id[mid])

    game_map = getattr(game, "map", None)
    battlefield = getattr(game, "battlefield", None)
    width = None
    height = None
    if battlefield is not None:
        try:
            width = float(getattr(battlefield, "width", None))
            height = float(getattr(battlefield, "height", None))
        except Exception:
            width = None
            height = None
    if (width is None or height is None) and game_map is not None:
        try:
            width = float(getattr(game_map, "width", None))
            height = float(getattr(game_map, "height", None))
        except Exception:
            width = None
            height = None
    if width is None or height is None:
        return {"errors": errors}

    try:
        effective_turn = int(getattr(game, "turn", 0) or 0)
    except Exception:
        effective_turn = 0
    try:
        if hasattr(unit, "get_strategic_reserves_setup_turn"):
            effective_turn = int(unit.get_strategic_reserves_setup_turn(game=game, current_turn=effective_turn))
    except Exception:
        pass
    player_id = None
    try:
        army = unit.get_parent_army()
        player_id = getattr(getattr(army, "player", None), "id", None)
    except Exception:
        player_id = None

    def _model_radius(model) -> float:
        mb = getattr(model, "model_base", None)
        if mb is None:
            return 1.0
        if hasattr(mb, "get_longest_radius"):
            return float(mb.get_longest_radius())
        if hasattr(mb, "get_radius"):
            return float(mb.get_radius())
        r = getattr(mb, "radius", None)
        if isinstance(r, (list, tuple)) and r:
            return float(r[0])
        return float(r) if r is not None else 1.0

    def _center_dist_to_edge(x: float, y: float, edge: str) -> float:
        if edge == "own":
            return float(y)
        if edge == "enemy":
            return float(height - y)
        if edge == "left":
            return float(x)
        if edge == "right":
            return float(width - x)
        return float("inf")

    strategic_ok = False
    strategic_used_edge_touch = False
    selected_edge: str | None = None

    if bool(getattr(unit, "is_in_strategic_reserves", lambda: False)()):
        for edge in ("own", "left", "right", "enemy"):
            if hasattr(game, "is_valid_strategic_reserves_edge"):
                try:
                    if not bool(game.is_valid_strategic_reserves_edge(edge, turn=effective_turn)):
                        continue
                except Exception:
                    pass
            allow_enemy_dz_turn2 = _masters_of_the_void_enemy_dz_override_active(unit, game)
            if (
                effective_turn == 2
                and player_id
                and not allow_enemy_dz_turn2
                and hasattr(game, "is_position_in_enemy_deployment_zone")
            ):
                any_in_enemy_dz = False
                for (_mx, _my, _mz, _f) in prospective:
                    try:
                        if game.is_position_in_enemy_deployment_zone(float(_mx), float(_my), player_id):
                            any_in_enemy_dz = True
                            break
                    except Exception:
                        continue
                if any_in_enemy_dz:
                    continue
            ok_all = True
            used_touch = False
            for model, (x, y, _z, _facing) in zip(list(getattr(unit, "models", []) or []), prospective):
                r = float(_model_radius(model))
                d = _center_dist_to_edge(x, y, edge)
                max_center = 6.0 - r
                if max_center >= 0.0:
                    if d > max_center + 1e-6:
                        ok_all = False
                        break
                else:
                    if abs(d - float(r)) > 0.25:
                        ok_all = False
                        break
                    used_touch = True
            if ok_all:
                strategic_ok = True
                strategic_used_edge_touch = bool(used_touch)
                selected_edge = edge
                break

    tunnel_marker = None
    try:
        army = unit.get_parent_army()
    except Exception:
        army = None
    tyr_mgr = getattr(army, "tyranids_detachments", None) if army is not None else None
    marker_fn = getattr(tyr_mgr, "subterranean_assault_arrival_marker_for_positions", None) if tyr_mgr is not None else None
    if callable(marker_fn):
        tunnel_marker = marker_fn(unit, list(prospective), game=game)

    deep_strike_ok = True
    if bool(getattr(unit, "is_in_strategic_reserves", lambda: False)()):
        try:
            deep_strike_ok = bool(getattr(unit, "has_deep_strike", lambda: False)())
        except Exception:
            deep_strike_ok = False
        if not deep_strike_ok:
            sr = getattr(unit, "special_rules", None)
            if isinstance(sr, dict) and (
                bool(sr.get("cosmic_precision_temp_deep_strike", False))
                or bool(sr.get("dread_talons_screaming_descent_temp_deep_strike", False))
            ):
                deep_strike_ok = True
        if not strategic_ok and not deep_strike_ok and tunnel_marker is None:
            has_tunnel_rule = bool(tyr_mgr is not None and getattr(tyr_mgr, "is_subterranean_assault", lambda: False)())
            if has_tunnel_rule:
                return {"errors": ["Reserves arrival must be within 6\" of a battlefield edge or wholly within 9\" of a Tunnel Marker."]}
            return {"errors": ["Reserves arrival must be within 6\" of a battlefield edge."]}

    battlefield_edge = selected_edge if strategic_ok else None

    anchor_unit_id = str(context.get("reserves_arrival_anchor_unit_id", "") or "").strip()
    anchor_source_name = str(context.get("reserves_arrival_anchor_source", "") or "").strip()
    try:
        anchor_range = float(context.get("reserves_arrival_anchor_range", 0.0) or 0.0)
    except (TypeError, ValueError):
        anchor_range = 0.0
    anchor_wholly_within = bool(context.get("reserves_arrival_anchor_wholly_within", False))
    if anchor_unit_id and anchor_range > 0.0:
        anchor_unit = get_unit(game, anchor_unit_id)
        anchor_root = (
            anchor_unit.get_attached_unit_root()
            if anchor_unit is not None and hasattr(anchor_unit, "get_attached_unit_root")
            else anchor_unit
        )
        if anchor_root is None:
            return {"errors": ["Reserves arrival anchor unit was not found."]}
        if not bool(getattr(anchor_root, "deployed", True)):
            return {"errors": ["Reserves arrival anchor unit is not on the battlefield."]}
        if str(getattr(anchor_root, "reserve_status", "deployed") or "deployed") != "deployed":
            return {"errors": ["Reserves arrival anchor unit is not on the battlefield."]}
        if bool(getattr(anchor_root, "embarked_in", None)) or bool(getattr(anchor_root, "is_embarked", False)):
            return {"errors": ["Reserves arrival anchor unit is not on the battlefield."]}
        try:
            from ...utility.aura_utils import model_wholly_within_range_of_unit, model_within_range_of_unit
        except Exception:
            model_wholly_within_range_of_unit = None
            model_within_range_of_unit = None
        if not callable(model_wholly_within_range_of_unit) or not callable(model_within_range_of_unit):
            return {"errors": ["Reserves arrival anchor validation is unavailable."]}
        create_base = getattr(unit, "_create_potential_base", None)
        for model, (x, y, z, facing) in zip(list(getattr(unit, "models", []) or []), prospective):
            if not getattr(model, "is_alive", True):
                continue
            candidate_base = None
            if callable(create_base):
                try:
                    candidate_base = create_base(x, y, z, facing, model=model)
                except Exception:
                    candidate_base = None
            if candidate_base is None:
                continue
            proxy_model = SimpleNamespace(model_base=candidate_base, is_alive=True)
            if anchor_wholly_within:
                in_range = bool(
                    model_wholly_within_range_of_unit(
                        anchor_root,
                        proxy_model,
                        float(anchor_range),
                        use_attached_aggregate=True,
                    )
                )
            else:
                in_range = bool(
                    model_within_range_of_unit(
                        proxy_model,
                        anchor_root,
                        float(anchor_range),
                        use_attached_aggregate=True,
                    )
                )
            if not in_range:
                source_label = anchor_source_name or "Anchor ability"
                if anchor_wholly_within:
                    return {
                        "errors": [
                            f"{source_label}: reserves arrival must be wholly within {int(anchor_range)}\" of the source unit."
                        ]
                    }
                return {
                    "errors": [
                        f"{source_label}: reserves arrival must be within {int(anchor_range)}\" of the source unit."
                    ]
                }

    try:
        min_enemy_distance = float(getattr(game, "_warp_rifts_min_distance")(unit) or 9.0)
    except Exception:
        min_enemy_distance = 9.0
    if tunnel_marker is not None:
        min_enemy_distance = 6.0
    min_enemy_distance_override = context.get("reserves_arrival_min_enemy_distance_override")
    if min_enemy_distance_override is not None:
        try:
            min_enemy_distance = max(0.0, float(min_enemy_distance_override))
        except (TypeError, ValueError):
            min_enemy_distance = 0.0

    if battlefield_edge is None and tunnel_marker is None:
        try:
            if hasattr(unit, "get_deep_strike_min_distance_override"):
                override = unit.get_deep_strike_min_distance_override()
            else:
                override = None
        except Exception:
            override = None
        if override:
            min_enemy_distance = min(float(min_enemy_distance), float(override))
        try:
            checker = getattr(unit, "is_dark_apparitions_arrival_valid", None)
            if callable(checker):
                if not bool(
                    checker(
                        prospective,
                        game=game,
                        game_map=game_map,
                    )
                ):
                    return {
                        "errors": [
                            "Dark Apparitions: reserves Deep Strike setup must be wholly within 9\" of one or more friendly EMPEROR'S CHILDREN units."
                        ]
                    }
        except Exception:
            return {
                "errors": [
                    "Dark Apparitions: reserves Deep Strike setup validation failed."
                ]
            }

    try:
        from ...utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
    except Exception:
        horizontal_distance_between_bases_2d = None
        vertical_distance_between_bases = None
    enemy_units = []
    try:
        player = unit.get_parent_army().player
        enemy_units = list(getattr(game, "get_enemy_units", lambda _p: [])(player) or [])
    except Exception:
        enemy_units = []
    enemy_models: list[tuple[object, object]] = []
    for enemy in list(enemy_units or []):
        try:
            enemy_root = enemy.get_attached_unit_root() if hasattr(enemy, "get_attached_unit_root") else enemy
        except Exception:
            enemy_root = enemy
        if enemy_root is None:
            continue
        try:
            if not getattr(enemy_root, "is_alive", lambda: True)():
                continue
        except Exception:
            if not getattr(enemy_root, "is_alive", True):
                continue
        if not bool(getattr(enemy_root, "deployed", False)):
            continue
        if str(getattr(enemy_root, "reserve_status", "deployed")) != "deployed":
            continue
        if getattr(enemy_root, "embarked_in", None) is not None:
            continue
        if bool(getattr(enemy_root, "is_embarked", False)):
            continue
        for em in list(getattr(enemy_root, "models", []) or []):
            if not getattr(em, "is_alive", True):
                continue
            enemy_models.append((enemy_root, em))

    if callable(horizontal_distance_between_bases_2d):
        for model, (x, y, z, facing) in zip(list(getattr(unit, "models", []) or []), prospective):
            try:
                base = unit._create_potential_base(x, y, z, facing, model=model)
            except Exception:
                base = None
            if base is None:
                continue
            for enemy_root, em in list(enemy_models or []):
                try:
                    dist = float(horizontal_distance_between_bases_2d(base, em.model_base))
                except Exception:
                    continue
                required_distance = float(min_enemy_distance)
                if (
                    min_enemy_distance_override is None
                    and battlefield_edge is None
                    and tunnel_marker is None
                ):
                    try:
                        per_enemy = None
                        if hasattr(unit, "get_deep_strike_min_distance_vs_enemy"):
                            per_enemy = unit.get_deep_strike_min_distance_vs_enemy(
                                enemy_root,
                                game=game,
                                game_map=game_map,
                            )
                    except Exception:
                        per_enemy = None
                    if per_enemy:
                        required_distance = float(per_enemy)
                if required_distance > 0.0 and dist < float(required_distance):
                    return {"errors": [f"Reserves arrival must be more than {int(required_distance)}\" from enemy models."]}
                if bool(context.get("reserves_arrival_require_not_engagement", False)):
                    if not callable(vertical_distance_between_bases):
                        return {"errors": ["Reserves arrival engagement-range validation is unavailable."]}
                    try:
                        vert = float(vertical_distance_between_bases(base, em.model_base))
                    except Exception:
                        continue
                    if dist <= float(ENGAGEMENT_RANGE_HORIZONTAL) and vert <= float(ENGAGEMENT_RANGE_VERTICAL):
                        return {"errors": ["Reserves arrival must not be within Engagement Range of enemy models."]}

    try:
        if bool(getattr(game, "_reserves_denial_violated")(unit, prospective)):
            return {"errors": ["Reserves arrival position is denied by an enemy ability."]}
    except Exception:
        pass

    pending_deep_strike = False
    if bool(getattr(unit, "is_in_strategic_reserves", lambda: False)()):
        pending_deep_strike = bool(deep_strike_ok and not strategic_ok and tunnel_marker is None)
    else:
        pending_deep_strike = bool(tunnel_marker is None)
    if not _transponder_lock_module_turn_one_spotter_requirement_satisfied(
        unit,
        list(prospective),
        pending_deep_strike=pending_deep_strike,
        game=game,
    ):
        return {
            "errors": [
                "Transponder Lock Module: first-turn Deep Strike setup must be within 12\" of a friendly KROOT or VESPID STINGWINGS unit."
            ]
        }

    return {
        "errors": errors,
        "prospective": prospective,
        "battlefield_edge": battlefield_edge,
        "edge_touch": bool(strategic_ok and strategic_used_edge_touch),
        "pending_deep_strike": bool(pending_deep_strike),
        "tunnel_marker_id": str(getattr(tunnel_marker, "marker_id", "") or ""),
    }


def _apply_move_unit(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    ctx = dict(getattr(request, "context", {}) or {})
    unit_id = str(payload.get("unit_id", "") or ctx.get("unit_id", "") or "")
    unit = get_unit(game, unit_id)
    if unit is None:
        raise RuntimeError("Move unit: unit not found.")
    movement_type = str(payload.get("movement_type", "") or request.context.get("movement_type", "") or "")
    placement_kind = str(ctx.get("placement_kind", "") or "")
    if bool(result.payload.get("skipped", False)):
        if movement_type == "reactive":
            _clear_battle_focus_reactive_flags(unit)
        if placement_kind == "reserves_arrival":
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            for k in (
                "cloudstrider_deep_strike_min_distance",
                "cloudstrider_choice_turn",
                "cloudstrider_choice_turn_owner",
                "cloudstrider_no_charge_turn",
                "cloudstrider_no_charge_turn_owner",
                "cosmic_precision_active",
                "cosmic_precision_expires_phase",
                "cosmic_precision_deep_strike_min_distance",
                "cosmic_precision_temp_deep_strike",
                "cosmic_precision_turn_owner",
                "cosmic_precision_turn",
                "cosmic_precision_no_charge_turn_owner",
                "cosmic_precision_no_charge_turn",
                "cosmic_precision_source",
                "dread_talons_screaming_descent_active",
                "dread_talons_screaming_descent_phase",
                "dread_talons_screaming_descent_turn_owner",
                "dread_talons_screaming_descent_turn",
                "dread_talons_screaming_descent_source",
                "dread_talons_screaming_descent_deep_strike_min_distance",
                "dread_talons_screaming_descent_temp_deep_strike",
                "dread_talons_screaming_descent_post_setup_battleshock_pending",
                "dread_talons_screaming_descent_no_charge_turn_owner",
                "dread_talons_screaming_descent_no_charge_turn",
                "dread_talons_screaming_descent_no_charge_source",
                "eternity_gate_no_charge_turn_owner",
                "eternity_gate_no_charge_turn",
                "eternity_gate_no_charge_source",
            ):
                sr.pop(k, None)
            unit.special_rules = sr
            for attr in (
                "_pending_reserves_edge_touch",
                "_pending_reserves_deep_strike",
                "_pending_reserves_tunnel_marker_id",
            ):
                if hasattr(unit, attr):
                    delattr(unit, attr)
        return None
    model_positions = list(result.payload.get("model_positions") or [])
    apply_model_positions(game, model_positions)

    allowed_ids = {str(v) for v in list(ctx.get("allowed_model_ids") or []) if v is not None}
    if placement_kind or allowed_ids:
        for entry in list(model_positions or []):
            model_id = str(entry.get("model_id", "") or "")
            model = get_model(game, model_id)
            if model is None:
                continue
            model._pending_placement = False
            model._pending_placement_source = None
        if hasattr(unit, "update_coherency"):
            unit.update_coherency()
    if placement_kind == "deployment":
        _finalize_deployment_move(game, unit, model_positions)
    if placement_kind == "reserves_arrival":
        _finalize_reserves_arrival_move(game, unit, model_positions, ctx=ctx)
    if placement_kind in ("advance_redeploy_9h", "normal_move_redeploy_9h"):
        event_system = getattr(game, "event_system", None)
        if event_system is not None:
            event_system.publish(
                "unit_set_up",
                unit=unit,
                set_up_as_reinforcements=False,
            )
    if bool(ctx.get("redeploy_followup", False)):
        try:
            unit_id = str(ctx.get("redeploy_unit_id", "") or unit_id)
            followup = getattr(game, "_on_redeploy_placement_resolved", None)
            if callable(followup):
                followup(unit_id)
        except Exception:
            pass

    members = _movement_members(unit)
    for member in members:
        if movement_type == "advance":
            member.round_state.advanced_this_round = True
            member.round_state.moved_this_round = True
            member.round_state.remained_stationary_this_round = False
        elif movement_type == "fall_back":
            member.round_state.fell_back_this_round = True
            member.round_state.moved_this_round = True
            member.round_state.remained_stationary_this_round = False
        elif movement_type in ("move", "pile_in", "consolidate", "charge"):
            member.round_state.moved_this_round = True
            member.round_state.remained_stationary_this_round = False
        try:
            if movement_type in ("move", "advance", "fall_back"):
                member.round_state.move_modifier_choice = None
                member.round_state.move_modifier_choice_pending = False
            if movement_type == "advance":
                member.round_state.advance_modifier_choice = None
                member.round_state.advance_modifier_choice_pending = False
            if movement_type == "charge":
                member.round_state.charge_modifier_choice = None
                member.round_state.charge_modifier_choice_pending = False
                member.round_state.charge_modifier_choice_targets = []
        except Exception:
            pass
        if movement_type == "loping_speed":
            member.mark_loping_speed_used(game)
        if movement_type == "blood_surge":
            member.mark_blood_surge_used(game)
        if movement_type == "brazen_fury":
            member.mark_brazen_fury_used(game)
        if movement_type == "horde_move":
            member.mark_horde_move_used(game)
            clear_go_get_em = getattr(member, "clear_go_get_em_horde_move", None)
            if callable(clear_go_get_em):
                clear_go_get_em()
        if movement_type == "unhinged_vengeance":
            member.mark_unhinged_vengeance_used(game)
        if movement_type == "blistering_assault":
            member.mark_blistering_assault_used(game)
        if movement_type == "bestial_rage":
            member.mark_bestial_rage_used(game)
        if movement_type == "aggressive_leader_beast":
            member.mark_aggressive_leader_beast_used(game)
    if movement_type == "reactive":
        _clear_battle_focus_reactive_flags(unit)
        if str(ctx.get("reactive_move_kind", "") or "").strip() in (
            "tactical_acumen",
            "post_shoot_no_charge",
            "execute_and_redeploy",
        ):
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            player = None
            try:
                player = unit.get_parent_army().player
            except Exception:
                player = None
            if player is None:
                try:
                    player = getattr(game, "get_current_player", lambda: None)()
                except Exception:
                    player = None
            sr["tactical_acumen_no_charge_turn_owner"] = str(getattr(player, "id", "") or "")
            try:
                sr["tactical_acumen_no_charge_turn"] = int(getattr(game, "turn", 0) or 0)
            except Exception:
                sr["tactical_acumen_no_charge_turn"] = 0
            unit.special_rules = sr
    reactive_kind = str(ctx.get("reactive_move_kind", "") or "").strip()
    reactive_movement_type = str(ctx.get("reactive_move_movement_type", "") or "").strip().lower()
    if reactive_kind == "opportunistic_raiders" and reactive_movement_type == "fall_back":
        _maybe_queue_post_fall_back_destroyed_strategic_reserves(game, unit, context=ctx)
    if movement_type == "reactive" and reactive_kind == "execute_and_redeploy":
        try:
            army = unit.get_parent_army() if hasattr(unit, "get_parent_army") else None
        except Exception:
            army = None
        sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        mark_used_fn = (
            getattr(sm_mgr, "mark_vanguard_execute_and_redeploy_used", None)
            if sm_mgr is not None
            else None
        )
        if callable(mark_used_fn):
            try:
                mark_used_fn(unit, game=game)
            except Exception:
                pass
    if movement_type == "gleaming_pinions" or reactive_kind == "gleaming_pinions":
        try:
            army = unit.get_parent_army() if hasattr(unit, "get_parent_army") else None
        except Exception:
            army = None
        sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        mark_used_fn = getattr(sm_mgr, "mark_the_angelic_host_gleaming_pinions_used", None) if sm_mgr is not None else None
        if callable(mark_used_fn):
            try:
                mark_used_fn(unit, game=game)
            except Exception:
                pass
    if movement_type == "charge":
        finalize_charge = getattr(game, "_finalize_successful_charge_move", None)
        if not callable(finalize_charge):
            raise RuntimeError("Move unit: game missing _finalize_successful_charge_move().")
        target_units = _resolve_charge_targets(game, ctx)
        if not target_units:
            raise RuntimeError("Move unit: charge movement requires declared targets.")
        finalize_charge(
            unit,
            target_units,
            count_as_charged=bool(ctx.get("count_as_charged", True)),
        )
    wraithlike_check = _wraithlike_retreat_transport_requirement(
        game,
        unit,
        model_positions,
        ctx=ctx,
    )
    if bool(wraithlike_check.get("required", False)):
        if not bool(wraithlike_check.get("valid", False)):
            reason = str(wraithlike_check.get("reason", "") or "Wraithlike Retreat embark requirement failed.")
            raise RuntimeError(reason)
        transport = wraithlike_check.get("transport")
        game_map = getattr(game, "map", None)
        if transport is None or game_map is None:
            raise RuntimeError("Wraithlike Retreat requires a transport and active game map.")
        add_passenger = getattr(transport, "add_passenger", None)
        if not callable(add_passenger):
            raise RuntimeError("Wraithlike Retreat transport cannot embark units.")
        if not bool(add_passenger(unit, game_map=game_map)):
            raise RuntimeError("Wraithlike Retreat failed: transport could not embark unit at move end.")
    return None


def _finalize_deployment_move(game: object, unit: object, model_positions: list[dict]) -> None:
    if unit is None:
        return
    unit.deployed = True
    leaders = list(getattr(unit, "attached_leaders", []) or [])
    supports = list(getattr(unit, "attached_support_units", []) or [])
    for member in leaders + supports:
        member.deployed = True
        member.reserve_status = getattr(unit, "reserve_status", "deployed")
        member.reserve_turn_deployed = getattr(unit, "reserve_turn_deployed", None)

    game_map = getattr(game, "map", None)
    if game_map is not None:
        units_list = getattr(game_map, "units", None)
        if isinstance(units_list, list) and unit not in units_list:
            units_list.append(unit)

    positions = []
    for entry in list(model_positions or []):
        pos = entry.get("position") or []
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            continue
        try:
            x = float(pos[0])
            y = float(pos[1])
            z = float(pos[2]) if len(pos) > 2 else 0.0
        except (TypeError, ValueError):
            continue
        positions.append((x, y, z))
    if positions:
        ux = sum(p[0] for p in positions) / len(positions)
        uy = sum(p[1] for p in positions) / len(positions)
        uz = sum(p[2] for p in positions) / len(positions)
        unit.position = (ux, uy, uz)

    if is_convergence_of_dominion_deployment_unit(unit):
        from ...utility.unit_split import split_unit_into_single_model_units

        split_units = split_unit_into_single_model_units(unit, game=game, game_map=game_map)
        for split_unit in list(split_units or []):
            alive_models = [m for m in list(getattr(split_unit, "models", []) or []) if getattr(m, "is_alive", True)]
            if not alive_models:
                continue
            loc = alive_models[0].get_location()
            if isinstance(loc, (list, tuple)) and len(loc) >= 3:
                split_unit.position = (float(loc[0]), float(loc[1]), float(loc[2]))

    army = getattr(unit, "get_parent_army", None)
    if callable(army):
        army = army()
    else:
        army = getattr(unit, "parent_army", None)
    player = getattr(army, "player", None) if army is not None else None
    if player is not None and hasattr(game, "record_deployment_action"):
        game.record_deployment_action(player, unit, "deployed", getattr(unit, "position", None))
    if hasattr(game, "advance_deployment_turn"):
        game.advance_deployment_turn(unit)


def _queue_drop_pod_assault_disembark_requests(
    game: object,
    transport: object,
    *,
    ability_name: str,
    min_enemy_distance: float,
) -> None:
    if game is None or transport is None:
        return
    request_decision = getattr(game, "request_decision", None)
    if not callable(request_decision):
        return
    transport_id = str(get_entity_id(transport) or "")
    if not transport_id:
        return
    player_id = None
    army = transport.get_parent_army() if hasattr(transport, "get_parent_army") else None
    if army is not None:
        player = getattr(army, "player", None)
        player_id = getattr(player, "id", None) if player is not None else None

    pending_unit_ids: set[str] = set()
    queue = getattr(game, "decision_queue", None)
    if queue is not None and hasattr(queue, "list"):
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_DISEMBARK:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != "drop_pod_assault_disembark":
                continue
            if str(ctx.get("transport_id", "") or "") != transport_id:
                continue
            unit_id = str(ctx.get("unit_id", "") or "")
            if unit_id:
                pending_unit_ids.add(unit_id)

    passengers = []
    for passenger in list(getattr(transport, "transport_passengers", []) or []):
        if passenger is None:
            continue
        if getattr(passenger, "embarked_in", None) is not transport:
            continue
        passenger_id = str(get_entity_id(passenger) or "")
        if not passenger_id or passenger_id in pending_unit_ids:
            continue
        passengers.append(passenger)
    passengers.sort(key=lambda item: str(get_entity_id(item) or ""))
    if not passengers:
        return

    distance = float(max(0.0, min_enemy_distance))
    for passenger in passengers:
        passenger_id = str(get_entity_id(passenger) or "")
        if not passenger_id:
            continue
        request = DecisionRequest.create(
            DECISION_DISEMBARK,
            f"{ability_name}: disembark {getattr(passenger, 'name', 'Unit')}.",
            player_id=player_id,
            options=[
                DecisionOption.create(
                    "Disembark",
                    payload={"unit_id": passenger_id, "transport_id": transport_id},
                ),
            ],
            context={
                "ability": "drop_pod_assault_disembark",
                "ability_name": str(ability_name or "Drop Pod Assault").strip() or "Drop Pod Assault",
                "transport_id": transport_id,
                "unit_id": passenger_id,
                "mandatory_disembark": True,
                "disembark_source": str(ability_name or "Drop Pod Assault").strip() or "Drop Pod Assault",
                "disembark_min_enemy_horizontal_distance": float(distance),
            },
        )
        request_decision(request)


def _finalize_reserves_arrival_move(
    game: object,
    unit: object,
    model_positions: list[dict],
    *,
    ctx: dict | None = None,
) -> None:
    if unit is None:
        return
    context = dict(ctx or {})
    evaluation = _evaluate_reserves_arrival_positions(game, unit, model_positions, ctx=context)
    errors = list(evaluation.get("errors") or [])
    if errors:
        raise RuntimeError("; ".join(str(e) for e in errors if e))
    apply_model_positions(game, list(model_positions or []))

    # Track special arrival flags (edge touch / deep strike) for downstream rules.
    try:
        if evaluation.get("edge_touch"):
            setattr(unit, "_pending_reserves_edge_touch", True)
        elif hasattr(unit, "_pending_reserves_edge_touch"):
            delattr(unit, "_pending_reserves_edge_touch")
    except Exception:
        pass
    try:
        setattr(unit, "_pending_reserves_deep_strike", bool(evaluation.get("pending_deep_strike", False)))
    except Exception:
        pass
    tunnel_marker_id = str(evaluation.get("tunnel_marker_id", "") or "")
    try:
        if tunnel_marker_id:
            setattr(unit, "_pending_reserves_tunnel_marker_id", tunnel_marker_id)
        elif hasattr(unit, "_pending_reserves_tunnel_marker_id"):
            delattr(unit, "_pending_reserves_tunnel_marker_id")
    except Exception:
        pass

    # Update unit centroid position for convenience.
    positions = []
    for entry in list(model_positions or []):
        pos = entry.get("position") or []
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            continue
        try:
            x = float(pos[0])
            y = float(pos[1])
            z = float(pos[2]) if len(pos) > 2 else 0.0
        except (TypeError, ValueError):
            continue
        positions.append((x, y, z))
    if positions:
        ux = sum(p[0] for p in positions) / len(positions)
        uy = sum(p[1] for p in positions) / len(positions)
        uz = sum(p[2] for p in positions) / len(positions)
        unit.position = (ux, uy, uz)

    game_map = getattr(game, "map", None)
    if game_map is not None and hasattr(game_map, "units"):
        try:
            if unit not in game_map.units:
                game_map.units.append(unit)
        except Exception:
            pass

    try:
        turn = int(getattr(game, "turn", 0) or 0)
    except Exception:
        turn = 0
    try:
        unit._finalize_reserves_arrival(turn, game_map)
    except Exception as exc:
        raise RuntimeError(f"Reserves arrival finalize failed: {exc}") from exc

    owner_id = str(context.get("reserves_arrival_no_charge_turn_owner", "") or "")
    source = str(context.get("reserves_arrival_no_charge_source", "") or "")
    turn_raw = context.get("reserves_arrival_no_charge_turn", None)
    if owner_id:
        try:
            no_charge_turn = int(turn_raw or 0)
        except (TypeError, ValueError):
            no_charge_turn = 0
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["eternity_gate_no_charge_turn_owner"] = owner_id
        sr["eternity_gate_no_charge_turn"] = int(no_charge_turn)
        if source:
            sr["eternity_gate_no_charge_source"] = source
        unit.special_rules = sr

    get_drop_pod_rule = getattr(unit, "get_drop_pod_assault_rule", None)
    drop_pod_rule = get_drop_pod_rule() if callable(get_drop_pod_rule) else None
    if not isinstance(drop_pod_rule, dict):
        return

    ability_name = str(drop_pod_rule.get("source", "") or "Drop Pod Assault").strip() or "Drop Pod Assault"
    try:
        min_enemy_distance = float(drop_pod_rule.get("disembark_min_enemy_distance", 9.0) or 9.0)
    except (TypeError, ValueError):
        min_enemy_distance = 9.0
    if min_enemy_distance <= 0.0:
        min_enemy_distance = 9.0
    immediate_disembark = bool(drop_pod_rule.get("immediate_disembark", False))
    no_embark_after_setup = bool(drop_pod_rule.get("no_embark_after_setup", False))

    get_deployment_complete_rule = getattr(unit, "get_deployment_complete_embark_lock_rule", None)
    deployment_complete_rule = (
        get_deployment_complete_rule() if callable(get_deployment_complete_rule) else None
    )
    deployment_complete_active = isinstance(deployment_complete_rule, dict)
    deployment_complete_source = (
        str(deployment_complete_rule.get("source", "") or "Deployment Complete").strip()
        if deployment_complete_active
        else ""
    )
    if not deployment_complete_source and deployment_complete_active:
        deployment_complete_source = "Deployment Complete"

    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    sr["drop_pod_assault_set_up"] = True
    sr["drop_pod_assault_source"] = ability_name
    if min_enemy_distance > 0.0:
        sr["drop_pod_assault_disembark_min_enemy_distance"] = float(min_enemy_distance)

    passengers = [
        p
        for p in list(getattr(unit, "transport_passengers", []) or [])
        if p is not None and getattr(p, "embarked_in", None) is unit
    ]
    if no_embark_after_setup:
        sr["drop_pod_embark_locked"] = True
        sr["drop_pod_embark_lock_pending"] = False
        sr["drop_pod_embark_lock_source"] = ability_name
    elif deployment_complete_active:
        if passengers:
            sr["drop_pod_embark_lock_pending"] = True
            sr["drop_pod_embark_lock_source"] = deployment_complete_source
        else:
            sr["drop_pod_embark_locked"] = True
            sr["drop_pod_embark_lock_pending"] = False
            sr["drop_pod_embark_lock_source"] = deployment_complete_source
    unit.special_rules = sr

    if immediate_disembark and passengers:
        _queue_drop_pod_assault_disembark_requests(
            game,
            unit,
            ability_name=ability_name,
            min_enemy_distance=float(min_enemy_distance),
        )


def _validate_resolve_coherency(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit_id = str(payload.get("unit_id", "") or request.context.get("unit_id", "") or "")
    if not unit_id:
        return ("Coherency resolution requires unit_id.",)
    unit = get_unit(game, unit_id)
    if unit is None:
        return ("Coherency resolution: unit not found.",)
    to_remove = list(result.payload.get("model_ids") or [])
    if len(to_remove) != 1:
        return ("Coherency resolution requires exactly one model_id.",)
    selected_model_id = str(to_remove[0] or "")
    if not selected_model_id:
        return ("Coherency resolution requires model_ids list.",)
    allowed_model_ids = {
        str(value or "")
        for value in list(request.context.get("allowed_model_ids", []) or [])
        if str(value or "")
    }
    if allowed_model_ids and selected_model_id not in allowed_model_ids:
        return ("Selected model is not eligible for coherency removal.",)
    model = get_model(game, selected_model_id)
    if model is None:
        return (f"Model not found: {selected_model_id}",)
    get_models = getattr(unit, "get_attached_unit_models", None)
    if callable(get_models):
        unit_models = list(get_models() or [])
    else:
        unit_models = list(getattr(unit, "models", []) or [])
    if model not in unit_models:
        return ("Model does not belong to the unit.",)
    if not bool(getattr(model, "is_alive", True)):
        return ("Selected model is already destroyed.",)
    return ()


def _apply_resolve_coherency(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit_id = str(payload.get("unit_id", "") or request.context.get("unit_id", "") or "")
    unit = get_unit(game, unit_id)
    if unit is None:
        raise RuntimeError("Coherency resolution: unit not found.")
    to_remove = list(result.payload.get("model_ids") or [])
    model_id = str(to_remove[0] or "") if to_remove else ""
    model = get_model(game, model_id)
    if model is None:
        raise RuntimeError("Coherency resolution: model not found.")
    if hasattr(model, "wounds"):
        model.wounds = 0
    model.die(game_map=getattr(game, "map", None))
    return None


def _validate_embark(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit_id = str(payload.get("unit_id", "") or "")
    transport_id = payload.get("transport_id")
    if not unit_id:
        return ("Embark requires unit_id.",)
    unit = get_unit(game, unit_id)
    transport = get_unit(game, str(transport_id or "")) if transport_id is not None else None
    if unit is None:
        return ("Embark unit not found.",)
    if transport_id is None:
        return ()
    if transport is None:
        return ("Embark transport not found.",)
    if not bool(getattr(transport, "is_transport", False)):
        return ("Embark requires a transport unit.",)
    try:
        if not transport.can_transport(unit):
            return ("Transport cannot embark selected unit.",)
    except Exception:
        return ("Embark validation failed.",)
    return ()


def _apply_embark(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit = get_unit(game, str(payload.get("unit_id", "") or ""))
    transport_id = payload.get("transport_id")
    if unit is None:
        raise RuntimeError("Embark: unit missing.")
    if transport_id is None:
        return None
    transport = get_unit(game, str(transport_id or ""))
    if transport is None:
        raise RuntimeError("Embark: transport missing.")
    unit.embark(transport, game_map=getattr(game, "map", None))
    return None


def _validate_disembark(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    ctx = dict(getattr(request, "context", {}) or {})
    if is_skip_choice(request, result):
        if bool(ctx.get("mandatory_disembark", False)):
            return ("This disembarkation is mandatory and cannot be skipped.",)
        return ()
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit_id = str(payload.get("unit_id", "") or "")
    transport_id = payload.get("transport_id")
    if not unit_id:
        return ("Disembark requires unit_id.",)
    unit = get_unit(game, unit_id)
    if unit is None:
        return ("Disembark unit not found.",)
    if transport_id is None:
        if bool(ctx.get("mandatory_disembark", False)):
            return ("Disembark transport is required for this mandatory disembarkation.",)
        return ()
    transport = get_unit(game, str(transport_id or ""))
    if transport is None:
        return ("Disembark transport not found.",)
    model_positions = result.payload.get("model_positions")
    if model_positions is not None:
        try:
            max_distance = float(
                ctx.get("reactive_disembark_range", ctx.get("disembark_max_distance", 0)) or 0
            )
        except (TypeError, ValueError):
            max_distance = 0.0
        if max_distance <= 0:
            max_distance = 3.0
        min_enemy_horizontal_distance = None
        require_not_in_engagement = True
        if "disembark_min_enemy_horizontal_distance" in ctx:
            try:
                min_enemy_horizontal_distance = float(
                    ctx.get("disembark_min_enemy_horizontal_distance", 0) or 0
                )
            except (TypeError, ValueError):
                min_enemy_horizontal_distance = None
            if min_enemy_horizontal_distance is not None and min_enemy_horizontal_distance <= 0:
                min_enemy_horizontal_distance = None
        if "disembark_require_not_in_engagement" in ctx:
            require_not_in_engagement = bool(ctx.get("disembark_require_not_in_engagement", True))
        errors = validate_model_positions(game, unit, model_positions, context="Disembark")
        if errors:
            return errors
        game_map = getattr(game, "map", None)
        if game_map is None:
            return ("Disembark requires game map for manual positions.",)
        for entry in list(model_positions or []):
            model = get_model(game, str(entry.get("model_id", "") or ""))
            if model is None:
                continue
            pos = entry.get("position") or []
            if len(pos) < 2:
                continue
            x = float(pos[0])
            y = float(pos[1])
            z = float(pos[2]) if len(pos) > 2 else float(getattr(model.model_base, "z", 0.0))
            check = unit.validate_disembark_placement(
                model,
                x,
                y,
                z,
                transport_unit=transport,
                game_map=game_map,
                max_distance=float(max_distance),
                require_not_in_engagement=bool(require_not_in_engagement),
                min_enemy_horizontal_distance=min_enemy_horizontal_distance,
            )
            if not bool(check.get("valid", False)):
                reason = str(check.get("reason", "") or "Invalid disembark placement.")
                return (reason,)
    return ()


def _apply_disembark(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    if is_skip_choice(request, result):
        return None
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit = get_unit(game, str(payload.get("unit_id", "") or ""))
    transport_id = payload.get("transport_id")
    if unit is None:
        raise RuntimeError("Disembark: unit missing.")
    if transport_id is None:
        return None
    transport = get_unit(game, str(transport_id or ""))
    if transport is None:
        raise RuntimeError("Disembark: transport missing.")
    ctx = dict(getattr(request, "context", {}) or {})
    try:
        disembark_range = float(
            ctx.get("reactive_disembark_range", ctx.get("disembark_max_distance", 0)) or 0
        )
    except (TypeError, ValueError):
        disembark_range = 0.0
    disembark_source = str(
        ctx.get("reactive_disembark_source", "")
        or ctx.get("disembark_source", "")
        or "Reactive Disembark"
    ).strip() or "Reactive Disembark"
    try:
        disembark_min_enemy_horizontal_distance = float(
            ctx.get("disembark_min_enemy_horizontal_distance", 0) or 0
        )
    except (TypeError, ValueError):
        disembark_min_enemy_horizontal_distance = 0.0
    require_not_in_engagement = True
    if "disembark_require_not_in_engagement" in ctx:
        require_not_in_engagement = bool(ctx.get("disembark_require_not_in_engagement", True))
    model_positions = result.payload.get("model_positions")
    if model_positions is not None:
        apply_model_positions(game, list(model_positions or []))
        game_map = getattr(game, "map", None)
        if game_map is None:
            raise RuntimeError("Disembark requires an active game map.")
        finalized = bool(
            unit.finalize_manual_disembark(
                game_map=game_map,
                transport_unit=transport,
                destroyed_transport=False,
                emergency=False,
                current_turn=getattr(game, "turn", 1),
            )
        )
        if finalized:
            _maybe_queue_post_reactive_disembark_shooting(game, request, unit)
        return finalized
    override_keys = (
        "stratagem_disembark_override_active",
        "stratagem_disembark_override_transport_id",
        "stratagem_disembark_override_max_distance",
        "stratagem_disembark_override_require_not_in_engagement",
        "stratagem_disembark_override_min_enemy_horizontal_distance",
        "stratagem_disembark_override_source",
    )
    had_override = False
    prev_values: dict[str, object] = {}
    if disembark_range > 0 or disembark_min_enemy_horizontal_distance > 0:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        for key in override_keys:
            if key in sr:
                prev_values[key] = sr.get(key)
        sr["stratagem_disembark_override_active"] = True
        sr["stratagem_disembark_override_transport_id"] = str(get_entity_id(transport) or "")
        if disembark_range > 0:
            sr["stratagem_disembark_override_max_distance"] = float(disembark_range)
        else:
            sr.pop("stratagem_disembark_override_max_distance", None)
        sr["stratagem_disembark_override_require_not_in_engagement"] = bool(require_not_in_engagement)
        if disembark_min_enemy_horizontal_distance > 0:
            sr["stratagem_disembark_override_min_enemy_horizontal_distance"] = float(
                disembark_min_enemy_horizontal_distance
            )
        else:
            sr.pop("stratagem_disembark_override_min_enemy_horizontal_distance", None)
        sr["stratagem_disembark_override_source"] = disembark_source
        unit.special_rules = sr
        had_override = True
    try:
        unit.disembark(
            game_map=getattr(game, "map", None),
            transport_unit=transport,
            current_turn=getattr(game, "turn", 1),
        )
    finally:
        if had_override:
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            for key in override_keys:
                if key in prev_values:
                    sr[key] = prev_values[key]
                else:
                    sr.pop(key, None)
            unit.special_rules = sr
    _maybe_queue_post_reactive_disembark_shooting(game, request, unit)
    return None


def _maybe_queue_post_reactive_disembark_shooting(game: object, request: DecisionRequest, unit: object) -> None:
    if game is None or request is None or unit is None:
        return
    ctx = dict(getattr(request, "context", {}) or {})
    if not bool(ctx.get("reactive_disembark_then_shoot_enemy_only", False)):
        return
    if bool(getattr(unit, "is_embarked", False)) or getattr(unit, "embarked_in", None) is not None:
        return
    enemy_id = str(
        ctx.get("reactive_disembark_shoot_enemy_id", "")
        or ctx.get("reactive_disembark_enemy_unit_id", "")
        or ""
    )
    if not enemy_id:
        return
    enemy_unit = get_unit(game, enemy_id)
    if enemy_unit is None:
        return
    is_alive = getattr(enemy_unit, "is_alive", None)
    if callable(is_alive) and not bool(is_alive()):
        return
    queue_shooting = getattr(game, "_queue_setup_reactive_shooting_decision", None)
    if not callable(queue_shooting):
        return
    get_parent_army = getattr(unit, "get_parent_army", None)
    parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
    player = getattr(parent_army, "player", None)
    if player is None:
        return
    source = str(ctx.get("reactive_disembark_shoot_source", "") or "Reactive Disembark")
    queue_shooting(
        player=player,
        unit=unit,
        target_unit=enemy_unit,
        source=source,
    )


def _validate_pick_point(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    ctx = dict(getattr(request, "context", {}) or {})
    ability_key = str(ctx.get("ability", "") or "").strip().lower()
    if is_skip_choice(request, result):
        if ability_key == "subterranean_assault_tunnel_marker_placement":
            return ("Tunnel Marker placement cannot be skipped.",)
        if ability_key == "fleet_commander_marker_2":
            return ("Fleet Commander second marker placement cannot be skipped.",)
        return ()
    payload = dict(result.payload or {})
    point = payload.get("point")
    if not isinstance(point, (list, tuple)) or len(point) < 2:
        return ("Point selection requires point coordinates.",)
    try:
        float(point[0])
        float(point[1])
        if len(point) > 2:
            float(point[2])
    except (TypeError, ValueError):
        return ("Point coordinates must be numeric.",)
    if ability_key == "fleet_commander_marker_2":
        first_marker = _parse_xy_point(ctx.get("first_marker_point"))
        if first_marker is None:
            return ("Fleet Commander second marker requires a valid first marker point.",)
        try:
            marker_range = float(ctx.get("marker_range", 12.0) or 12.0)
        except (TypeError, ValueError):
            marker_range = 12.0
        point_xy = _parse_xy_point(point)
        if point_xy is None:
            return ("Fleet Commander second marker requires point coordinates.",)
        dx = float(point_xy[0]) - float(first_marker[0])
        dy = float(point_xy[1]) - float(first_marker[1])
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > float(max(0.0, marker_range)) + 1e-6:
            return (f"Fleet Commander second marker must be within {float(max(0.0, marker_range)):.1f}\" of the first marker.",)
    if ability_key == "teleport_homer_marker_placement":
        unit_id = str(ctx.get("unit_id", "") or "")
        unit = get_unit(game, unit_id)
        if unit is None:
            return ("Teleport Homer token placement requires a valid unit.",)
        can_place = getattr(unit, "can_place_teleport_homer_marker", None)
        if not callable(can_place) or not bool(can_place(game)):
            return ("Teleport Homer token cannot be placed by this unit right now.",)
        try:
            x = float(point[0])
            y = float(point[1])
        except (TypeError, ValueError):
            return ("Point coordinates must be numeric.",)

        width = None
        height = None
        battlefield = getattr(game, "battlefield", None)
        if battlefield is not None:
            try:
                width = float(getattr(battlefield, "width", None))
                height = float(getattr(battlefield, "height", None))
            except (TypeError, ValueError):
                width = None
                height = None
        if (width is None or height is None) and getattr(game, "map", None) is not None:
            game_map = getattr(game, "map", None)
            try:
                width = float(getattr(game_map, "width", None))
                height = float(getattr(game_map, "height", None))
            except (TypeError, ValueError):
                width = None
                height = None
        if width is not None and height is not None:
            if x < 0.0 or y < 0.0 or x > float(width) or y > float(height):
                return ("Teleport Homer token must be placed on the battlefield.",)

        forbidden_player_id = str(
            ctx.get("forbidden_deployment_zone_player_id", "")
            or ctx.get("opponent_player_id", "")
            or ""
        )
        if not forbidden_player_id:
            army = unit.get_parent_army() if hasattr(unit, "get_parent_army") else None
            owner = getattr(army, "player", None) if army is not None else None
            for candidate in list(getattr(game, "players", []) or []):
                if candidate is None or candidate is owner:
                    continue
                candidate_id = str(getattr(candidate, "id", "") or "")
                if candidate_id:
                    forbidden_player_id = candidate_id
                    break
        in_deployment_zone = getattr(game, "is_position_in_deployment_zone", None)
        if forbidden_player_id and callable(in_deployment_zone):
            if bool(in_deployment_zone(float(x), float(y), forbidden_player_id)):
                return ("Teleport Homer token must be outside your opponent's deployment zone.",)
    if ability_key == "subterranean_assault_tunnel_marker_placement":
        unit_id = str(ctx.get("unit_id", "") or "")
        unit = get_unit(game, unit_id)
        if unit is None:
            return ("Tunnel Marker placement requires a valid Burrower unit.",)
        army = unit.get_parent_army() if hasattr(unit, "get_parent_army") else None
        mgr = getattr(army, "tyranids_detachments", None) if army is not None else None
        validate_fn = getattr(mgr, "validate_subterranean_assault_tunnel_marker_point", None) if mgr is not None else None
        if not callable(validate_fn):
            return ("Tunnel Marker placement manager is unavailable.",)
        valid, reason = validate_fn(unit=unit, point=point, game=game)
        if not bool(valid):
            return (str(reason or "Tunnel Marker position is invalid."),)
    if ability_key == "parasitic_infection_spawn":
        validate_fn = getattr(game, "_validate_parasitic_infection_spawn_point", None)
        if not callable(validate_fn):
            return ("Parasitic Infection spawn validation is unavailable.",)
        valid, reason = validate_fn(ctx, point)
        if not bool(valid):
            return (str(reason or "Parasitic Infection spawn point is invalid."),)
    if ability_key == "summon_the_cult_marker_relocation":
        opt = find_option(request, result.option_id)
        option_payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
        marker_id = str(option_payload.get("marker_id", "") or "")
        if not marker_id:
            return ("Summon the Cult requires a threatened Cult Ambush marker.",)
        validate_fn = getattr(game, "_validate_summon_the_cult_marker_relocation", None)
        if not callable(validate_fn):
            return ("Summon the Cult validation is unavailable.",)
        valid, reason = validate_fn(ctx, marker_id=marker_id, point=point)
        if not bool(valid):
            return (str(reason or "Summon the Cult relocation point is invalid."),)
    if ability_key == "cult_infiltration_marker_relocation":
        opt = find_option(request, result.option_id)
        option_payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
        marker_id = str(option_payload.get("marker_id", "") or "")
        if not marker_id:
            return ("Cult Infiltration requires a Cult Ambush marker.",)
        validate_fn = getattr(game, "_validate_cult_infiltration_marker_relocation", None)
        if not callable(validate_fn):
            return ("Cult Infiltration validation is unavailable.",)
        valid, reason = validate_fn(ctx, marker_id=marker_id, point=point)
        if not bool(valid):
            return (str(reason or "Cult Infiltration relocation point is invalid."),)
    return ()


def _apply_pick_point(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    ctx = dict(getattr(request, "context", {}) or {})
    ability_key = str(ctx.get("ability", "") or "").strip().lower()
    if is_skip_choice(request, result):
        if ability_key == "fleet_commander_marker_1":
            source_member = get_unit(game, str(ctx.get("source_member_unit_id", "") or ""))
            if source_member is not None:
                sr = getattr(source_member, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr.pop("enhancement_fleet_commander_first_marker_point", None)
                sr.pop("enhancement_fleet_commander_pending_second_marker", None)
                source_member.special_rules = sr
        if ability_key == "teleport_homer_marker_placement":
            source_unit = get_unit(game, str(ctx.get("source_unit_id", "") or ctx.get("unit_id", "") or ""))
            if source_unit is not None:
                mark_declined = getattr(source_unit, "mark_teleport_homer_marker_declined", None)
                if callable(mark_declined):
                    mark_declined()
        if ability_key == "parasitic_infection_spawn":
            skip_fn = getattr(game, "_skip_parasitic_infection_spawn", None)
            if callable(skip_fn):
                skip_fn(ctx)
        if ability_key == "summon_the_cult_marker_relocation":
            skip_fn = getattr(game, "_skip_summon_the_cult_marker_relocation", None)
            if callable(skip_fn):
                skip_fn(ctx)
        if ability_key == "cult_infiltration_marker_relocation":
            skip_fn = getattr(game, "_skip_cult_infiltration_marker_relocation", None)
            if callable(skip_fn):
                skip_fn(ctx)
        return None
    opt = find_option(request, result.option_id)
    option_payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    payload = dict(result.payload or {})
    point = payload.get("point") or []
    if not isinstance(point, (list, tuple)) or len(point) < 2:
        return None
    x = float(point[0])
    y = float(point[1])
    if ability_key == "fleet_commander_marker_1":
        source_root = get_unit(game, str(ctx.get("source_unit_id", "") or ctx.get("unit_id", "") or ""))
        source_member = get_unit(game, str(ctx.get("source_member_unit_id", "") or ""))
        if source_member is None:
            source_member = source_root
        if source_member is None:
            return (x, y)
        source_sr = getattr(source_member, "special_rules", None)
        if not isinstance(source_sr, dict):
            source_sr = {}
        source_sr["enhancement_fleet_commander_first_marker_point"] = [x, y]
        source_sr["enhancement_fleet_commander_pending_second_marker"] = True
        source_member.special_rules = source_sr

        if source_root is not None:
            ability_key_name = str(ctx.get("ability_key", "fleet_commander") or "fleet_commander").strip().lower()
            if not ability_key_name:
                ability_key_name = "fleet_commander"
            mark_used = getattr(source_root, "mark_unit_once_per_battle_used", None)
            if callable(mark_used):
                ability_name = str(ctx.get("ability_name", "Fleet Commander") or "Fleet Commander").strip() or "Fleet Commander"
                mark_used(ability_key_name, ability_name=ability_name)
        return (x, y)
    if ability_key == "fleet_commander_marker_2":
        source_root = get_unit(game, str(ctx.get("source_unit_id", "") or ctx.get("unit_id", "") or ""))
        source_member = get_unit(game, str(ctx.get("source_member_unit_id", "") or ""))
        if source_member is None:
            source_member = source_root
        if source_member is None:
            return (x, y)
        source_sr = getattr(source_member, "special_rules", None)
        if not isinstance(source_sr, dict):
            source_sr = {}
        first_marker_point = _parse_xy_point(ctx.get("first_marker_point"))
        if first_marker_point is None:
            first_marker_point = _parse_xy_point(source_sr.get("enhancement_fleet_commander_first_marker_point"))
        if first_marker_point is None:
            source_sr["enhancement_fleet_commander_pending_second_marker"] = False
            source_sr.pop("enhancement_fleet_commander_first_marker_point", None)
            source_member.special_rules = source_sr
            return (x, y)

        try:
            roll_min = int(ctx.get("roll_min", source_sr.get("enhancement_fleet_commander_roll_min", 3)) or 3)
        except (TypeError, ValueError):
            roll_min = 3
        roll_min = max(2, int(roll_min))
        mortal_roll = str(
            ctx.get("mortal_wounds_roll", source_sr.get("enhancement_fleet_commander_mortal_wounds_roll", "D3"))
            or "D3"
        ).strip().upper() or "D3"

        affected: list[dict] = []
        for target_root in _iter_active_battlefield_roots(game):
            target_id = str(get_entity_id(target_root) or "")
            if not target_id:
                continue
            if not _unit_line_intersects(
                target_root,
                start_xy=(float(first_marker_point[0]), float(first_marker_point[1])),
                end_xy=(x, y),
            ):
                continue
            roll = int(get_roll("D6") or 0)
            mortals = 0
            if roll >= int(roll_min):
                mortals = int(max(0, _fleet_commander_effect_roll(mortal_roll)))
                if mortals > 0:
                    source_for_apply = source_root if source_root is not None else source_member
                    applier = getattr(source_for_apply, "_apply_mortal_wounds_to_unit", None)
                    if callable(applier):
                        applier(target_root, int(mortals), game_map=getattr(game, "map", None))
            affected.append(
                {
                    "unit_id": target_id,
                    "roll": int(roll),
                    "triggered": bool(roll >= int(roll_min)),
                    "mortal_wounds": int(max(0, mortals)),
                }
            )

        source_sr["enhancement_fleet_commander_last_resolution"] = list(affected)
        source_sr["enhancement_fleet_commander_last_first_marker_point"] = [
            float(first_marker_point[0]),
            float(first_marker_point[1]),
        ]
        source_sr["enhancement_fleet_commander_last_second_marker_point"] = [x, y]
        source_sr.pop("enhancement_fleet_commander_first_marker_point", None)
        source_sr["enhancement_fleet_commander_pending_second_marker"] = False
        source_member.special_rules = source_sr
        return (x, y)
    if ability_key == "subterranean_assault_tunnel_marker_placement":
        unit_id = str(ctx.get("unit_id", "") or "")
        unit = get_unit(game, unit_id)
        if unit is None:
            return None
        army = unit.get_parent_army() if hasattr(unit, "get_parent_army") else None
        mgr = getattr(army, "tyranids_detachments", None) if army is not None else None
        apply_fn = getattr(mgr, "apply_subterranean_assault_tunnel_marker_point", None) if mgr is not None else None
        if not callable(apply_fn):
            return None
        marker = apply_fn(unit=unit, point=point, game=game)
        if marker is None:
            return None
        return (float(getattr(marker, "x", x)), float(getattr(marker, "y", y)), float(getattr(marker, "z", 0.0)))
    if ability_key == "parasitic_infection_spawn":
        apply_fn = getattr(game, "_apply_parasitic_infection_spawn_point", None)
        if not callable(apply_fn):
            return None
        apply_fn(ctx, point)
        if len(point) > 2:
            return (x, y, float(point[2]))
        return (x, y)
    if ability_key == "summon_the_cult_marker_relocation":
        marker_id = str(option_payload.get("marker_id", "") or "")
        apply_fn = getattr(game, "_apply_summon_the_cult_marker_relocation", None)
        if not callable(apply_fn) or not marker_id:
            return None
        applied = bool(apply_fn(ctx, marker_id=marker_id, point=point))
        if not applied:
            return None
        if len(point) > 2:
            return (x, y, float(point[2]))
        return (x, y)
    if ability_key == "cult_infiltration_marker_relocation":
        marker_id = str(option_payload.get("marker_id", "") or "")
        apply_fn = getattr(game, "_apply_cult_infiltration_marker_relocation", None)
        if not callable(apply_fn) or not marker_id:
            return None
        applied = bool(apply_fn(ctx, marker_id=marker_id, point=point))
        if not applied:
            return None
        if len(point) > 2:
            return (x, y, float(point[2]))
        return (x, y)
    if ability_key == "teleport_homer_marker_placement":
        source_unit = get_unit(game, str(ctx.get("source_unit_id", "") or ctx.get("unit_id", "") or ""))
        if source_unit is None:
            return None
        source_name = str(ctx.get("ability_name", "") or "Teleport Homer").strip() or "Teleport Homer"
        set_marker = getattr(source_unit, "set_teleport_homer_marker_point", None)
        if not callable(set_marker):
            return None
        if not bool(set_marker((x, y, 0.0), source=source_name)):
            return None
        return (x, y, 0.0)
    if len(point) > 2:
        z = float(point[2])
        return (x, y, z)
    return (x, y)


def _validate_pick_objective(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = dict(result.payload or {})
    objective_id = payload.get("objective_id")
    if not objective_id:
        opt = find_option(request, result.option_id)
        opt_payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
        objective_id = opt_payload.get("objective_id")
    if not objective_id:
        return ("Objective selection requires objective_id.",)
    if get_objective(game, str(objective_id or "")) is None:
        return ("Objective not found.",)
    return ()


def _apply_pick_objective(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    if is_skip_choice(request, result):
        return None
    payload = dict(result.payload or {})
    objective_id = payload.get("objective_id")
    if not objective_id:
        opt = find_option(request, result.option_id)
        opt_payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
        objective_id = opt_payload.get("objective_id")
    if not objective_id:
        return None
    return get_objective(game, str(objective_id or ""))


def _validate_select_floor(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = dict(result.payload or {})
    floor = payload.get("floor")
    if floor is None:
        opt = find_option(request, result.option_id)
        opt_payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
        floor = opt_payload.get("floor")
    if floor is None:
        return ("Floor selection requires floor value.",)
    try:
        int(floor)
    except (TypeError, ValueError):
        return ("Floor value must be an integer.",)
    return ()


def _apply_select_floor(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    if is_skip_choice(request, result):
        return None
    payload = dict(result.payload or {})
    floor = payload.get("floor")
    if floor is None:
        opt = find_option(request, result.option_id)
        opt_payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
        floor = opt_payload.get("floor")
    if floor is None:
        return None
    try:
        return int(floor)
    except (TypeError, ValueError):
        return None


register_decision_handler(
    DECISION_SELECT_MOVEMENT_ACTION,
    validate=_validate_select_movement_action,
    apply=_apply_select_movement_action,
)
register_decision_handler(DECISION_MOVE_UNIT, validate=_validate_move_unit, apply=_apply_move_unit)
register_decision_handler(
    DECISION_RESOLVE_COHERENCY,
    validate=_validate_resolve_coherency,
    apply=_apply_resolve_coherency,
)
register_decision_handler(DECISION_EMBARK, validate=_validate_embark, apply=_apply_embark)
register_decision_handler(DECISION_DISEMBARK, validate=_validate_disembark, apply=_apply_disembark)
register_decision_handler(DECISION_PICK_POINT, validate=_validate_pick_point, apply=_apply_pick_point)
register_decision_handler(DECISION_PICK_OBJECTIVE, validate=_validate_pick_objective, apply=_apply_pick_objective)
register_decision_handler(DECISION_SELECT_FLOOR, validate=_validate_select_floor, apply=_apply_select_floor)
