from __future__ import annotations

import colorsys
import hashlib
from itertools import combinations
import json
import re
from typing import Any, Iterable, List, Optional

from .board_affordances import compute_board_affordance_summary, deployment_zone_from_player
from .decisions import DecisionOption, DecisionRequest
from .decision_kinds import (
    DECISION_ATTACH_LEADER,
    DECISION_ATTACH_SUPPORT_ARTILLERY,
    DECISION_ALLOCATE_MELEE_TARGETS,
    DECISION_ASSIGN_TRANSPORT,
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_CHOOSE_PLAYER_COLOR,
    DECISION_CHOOSE_QUARRY,
    DECISION_CONFIRM_YES_NO,
    DECISION_DECLARE_CHARGE,
    DECISION_DECLARE_FIRING_DECK,
    DECISION_DECLARE_MELEE_WEAPONS,
    DECISION_DECLARE_RESERVES,
    DECISION_DECLARE_SHOTS,
    DECISION_MOVE_UNIT,
    DECISION_RESOLVE_COHERENCY,
    DECISION_SELECT_NEXT_DEPLOY_UNIT,
    DECISION_SELECT_MOVEMENT_ACTION,
    DECISION_SELECT_UNIT,
    DECISION_SHADOW_ASSIGNMENT,
    DECISION_SCOUT_MOVE,
)
from ..rules.imperial_agents_shadow_assignment import (
    army_supports_shadow_assignment,
    shadow_assignment_options_for_unit,
    unit_has_shadow_assignment,
)
from ..utility.entity_ids import get_entity_id, maybe_entity_id

PLAYER_COLOR_HUE_STEP_DEGREES = 15
PLAYER_COLOR_SATURATION = 0.85
PLAYER_COLOR_VALUE = 0.95


def _iter_units(units: Iterable[object] | None) -> List[object]:
    return [u for u in list(units or []) if u is not None]


def _unit_stable_sort_key(unit: object) -> tuple[object, ...]:
    name = str(getattr(unit, "name", "") or "")
    datasheet_id = str(getattr(unit, "datasheet_id", "") or getattr(unit, "datasheet_key", "") or "")
    faction = str(getattr(unit, "faction", "") or "")
    keywords = tuple(sorted(str(value or "") for value in list(getattr(unit, "keywords", []) or [])))
    models = list(getattr(unit, "models", []) or [])
    get_cost = getattr(unit, "get_unit_cost", None)
    try:
        points = int(get_cost()) if callable(get_cost) else 0
    except (TypeError, ValueError):
        points = 0
    return (
        faction,
        name,
        datasheet_id,
        int(points),
        int(len(models)),
        bool(getattr(unit, "is_leader", False)),
        bool(getattr(unit, "is_transport", False)),
        keywords,
    )


def _stable_sorted_units(units: Iterable[object] | None) -> List[object]:
    entries = list(enumerate(_iter_units(units)))
    entries.sort(key=lambda entry: (_unit_stable_sort_key(entry[1]), int(entry[0])))
    return [unit for _index, unit in entries]


def _iter_players(players: Iterable[object] | None) -> List[object]:
    return [p for p in list(players or []) if p is not None]


def _hsv_to_rgb_triplet(hue_degrees: int, *, saturation: float, value: float) -> list[int]:
    h = float(hue_degrees % 360) / 360.0
    r, g, b = colorsys.hsv_to_rgb(h, float(saturation), float(value))
    return [int(round(r * 255.0)), int(round(g * 255.0)), int(round(b * 255.0))]


def _player_sort_key(player: object) -> str:
    return str(get_entity_id(player) or "")


def _player_color_options(player: object) -> List[DecisionOption]:
    player_id = str(get_entity_id(player) or "")
    if not player_id:
        return []
    options: List[DecisionOption] = []
    for hue in range(0, 360, PLAYER_COLOR_HUE_STEP_DEGREES):
        rgb = _hsv_to_rgb_triplet(
            hue,
            saturation=PLAYER_COLOR_SATURATION,
            value=PLAYER_COLOR_VALUE,
        )
        options.append(
            DecisionOption.create(
                f"Hue {hue:03d}",
                payload={
                    "player_id": player_id,
                    "rgb": rgb,
                    "hue_degrees": int(hue),
                    "action_id": f"{DECISION_CHOOSE_PLAYER_COLOR}:{player_id}:{int(hue):03d}",
                },
            )
        )
    return options


def _player_id_for_unit(unit: object) -> Optional[str]:
    try:
        army = unit.get_parent_army()
    except Exception:
        army = getattr(unit, "parent_army", None)
    if army is None:
        return None
    try:
        player = getattr(army, "player", None)
    except Exception:
        player = None
    return getattr(player, "id", None) if player is not None else None


def _player_for_unit(unit: object):
    try:
        army = unit.get_parent_army()
    except Exception:
        army = getattr(unit, "parent_army", None)
    if army is None:
        return None
    return getattr(army, "player", None)


def _army_for_unit(unit: object):
    if unit is None:
        return None
    getter = getattr(unit, "get_parent_army", None)
    if callable(getter):
        return getter()
    return getattr(unit, "parent_army", None)


def _army_key(army: object) -> str:
    if army is None:
        return ""
    army_id = str(get_entity_id(army) or "").strip()
    if army_id:
        return army_id
    player = getattr(army, "player", None)
    player_id = str(getattr(player, "id", "") or "").strip()
    if player_id:
        return f"player:{player_id}"
    return f"obj:{id(army)}"


def _unit_has_special_rule_flag(unit: object, flag_key: str) -> bool:
    sr = getattr(unit, "special_rules", None)
    return bool(isinstance(sr, dict) and sr.get(flag_key))


def _unit_has_enhancement(unit: object, *, flag_key: str, enhancement_id: str, enhancement_name: str) -> bool:
    if _unit_has_special_rule_flag(unit, flag_key):
        return True
    enh = getattr(unit, "enhancement", None)
    if enh is None:
        return False
    try:
        if str(getattr(enh, "id", "") or "").strip() == str(enhancement_id or "").strip():
            return True
    except Exception:
        pass
    try:
        lhs = str(getattr(enh, "name", "") or "").strip().lower()
        rhs = str(enhancement_name or "").strip().lower()
        return bool(lhs and rhs and lhs == rhs)
    except Exception:
        return False


def _unit_is_rubricae(unit: object) -> bool:
    if unit is None:
        return False
    has_any = getattr(unit, "has_any_keyword", None)
    if callable(has_any):
        try:
            return bool(has_any("RUBRICAE"))
        except Exception:
            return False
    return False


def _unit_is_battleline(unit: object) -> bool:
    if unit is None:
        return False
    fn = getattr(unit, "is_battleline", None)
    if callable(fn):
        try:
            return bool(fn())
        except Exception:
            return False
    has_any = getattr(unit, "has_any_keyword", None)
    if callable(has_any):
        try:
            return bool(has_any("BATTLELINE"))
        except Exception:
            return False
    return False


def _unit_is_guardians(unit: object) -> bool:
    if unit is None:
        return False
    has_any = getattr(unit, "has_any_keyword", None)
    if callable(has_any):
        try:
            if bool(has_any("GUARDIANS")) or bool(has_any("GUARDIAN")):
                return True
        except Exception:
            pass
    name = str(getattr(unit, "name", "") or "").strip().lower()
    return "guardian" in name


def _unique_army_root_units(units: Iterable[object]) -> list[object]:
    roots: dict[str, object] = {}
    for unit in _iter_units(units):
        if bool(getattr(unit, "is_attached_leader", False)):
            continue
        if bool(getattr(unit, "is_joined_support", False)):
            continue
        root = unit
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            try:
                root = get_root() or unit
            except Exception:
                root = unit
        if root is None:
            continue
        root_id = str(get_entity_id(root) or "")
        if not root_id:
            continue
        roots[root_id] = root
    return [roots[k] for k in sorted(roots.keys())]


def _unit_is_alive(unit: object) -> bool:
    alive_attr = getattr(unit, "is_alive", None)
    if callable(alive_attr):
        return bool(alive_attr())
    return bool(alive_attr) if alive_attr is not None else True


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
    return getattr(unit, "embarked_in", None) is not None


def _unit_has_consumed_normal_shooting(unit: object) -> bool:
    round_state = getattr(unit, "round_state", None)
    if round_state is None:
        return False
    if not bool(getattr(round_state, "shot_this_round", False)):
        return False
    action_shoot_exception_available = bool(
        getattr(round_state, "action_locked_until_turn_end", False)
        and not bool(getattr(round_state, "action_permitted_shoot_used", False))
    )
    return not action_shoot_exception_available


def _unit_has_resolved_round_movement(unit: object) -> bool:
    round_state = getattr(unit, "round_state", None)
    if round_state is None:
        return False
    return bool(
        getattr(round_state, "moved_this_round", False)
        or getattr(round_state, "advanced_this_round", False)
        or getattr(round_state, "fell_back_this_round", False)
        or getattr(round_state, "reinforced_this_round", False)
    )


def _eligible_units_for_phase_step(
    units: Iterable[object] | None,
    *,
    require_in_reserves: bool | None = None,
) -> list[object]:
    eligible: list[object] = []
    for unit in _unique_army_root_units(units or []):
        if unit is None or not _unit_is_alive(unit):
            continue
        in_reserves = _unit_is_in_reserves(unit)
        if require_in_reserves is True and not in_reserves:
            continue
        if require_in_reserves is False and in_reserves:
            continue
        eligible.append(unit)
    return eligible


def _eligible_units_for_move_units_step(units: Iterable[object] | None) -> list[object]:
    return _eligible_units_for_phase_step(units, require_in_reserves=False)


def _eligible_units_for_reinforcements_step(units: Iterable[object] | None) -> list[object]:
    return _eligible_units_for_phase_step(units, require_in_reserves=True)


def _select_unit_prompt(*, prompt: str, phase_name: str, phase_step: str) -> str:
    text = str(prompt or "").strip()
    if text:
        return text
    phase_label = str(phase_name or "").strip().replace("_", " ").title() or "Phase"
    step_label = str(phase_step or "").strip().replace("_", " ").title()
    if step_label:
        return f"Select a unit to act in {phase_label} / {step_label}."
    return f"Select a unit to act in {phase_label}."


def build_select_unit_request(
    units: Iterable[object] | None,
    *,
    prompt: str = "",
    player_id: Optional[str] = None,
    phase_name: str = "",
    phase_step: str = "",
    selection_purpose: str = "",
    allow_pass: bool = False,
    context: Optional[dict[str, Any]] = None,
) -> Optional[DecisionRequest]:
    eligible_units = _unique_army_root_units(units or [])
    if not eligible_units and not bool(allow_pass):
        return None

    options: list[DecisionOption] = []
    allowed_unit_ids: list[str] = []
    for unit in eligible_units:
        unit_id = str(get_entity_id(unit) or "").strip()
        if not unit_id:
            continue
        allowed_unit_ids.append(unit_id)
        label = str(getattr(unit, "name", "") or "Unit").strip() or "Unit"
        action_id = (
            f"{DECISION_SELECT_UNIT}:"
            f"{str(phase_name or '').strip().upper()}:"
            f"{str(phase_step or '').strip().upper()}:"
            f"{str(selection_purpose or '').strip().upper()}:"
            f"{unit_id}"
        )
        options.append(
            DecisionOption.create(
                label,
                payload={
                    "unit_id": unit_id,
                    "action_id": action_id,
                },
            )
        )

    if not options and not bool(allow_pass):
        return None

    if bool(allow_pass):
        pass_action_id = (
            f"{DECISION_SELECT_UNIT}:"
            f"{str(phase_name or '').strip().upper()}:"
            f"{str(phase_step or '').strip().upper()}:"
            f"{str(selection_purpose or '').strip().upper()}:PASS"
        )
        options.append(
            DecisionOption.create(
                "Pass",
                payload={
                    "action": "pass",
                    "action_id": pass_action_id,
                },
            )
        )

    if player_id is None and eligible_units:
        player_id = _player_id_for_unit(eligible_units[0])

    request_context = dict(context or {})
    request_context.setdefault("phase_name", str(phase_name or "").strip().upper())
    request_context.setdefault("phase_step", str(phase_step or "").strip().upper())
    request_context.setdefault("selection_purpose", str(selection_purpose or "").strip().upper())
    request_context["allow_pass"] = bool(allow_pass)
    request_context["allowed_unit_ids"] = list(allowed_unit_ids)

    return DecisionRequest.create(
        DECISION_SELECT_UNIT,
        _select_unit_prompt(prompt=prompt, phase_name=phase_name, phase_step=phase_step),
        player_id=player_id,
        options=options,
        context=request_context,
    )


def queue_select_unit_request(
    game: object,
    units: Iterable[object] | None,
    *,
    prompt: str = "",
    player_id: Optional[str] = None,
    phase_name: str = "",
    phase_step: str = "",
    selection_purpose: str = "",
    allow_pass: bool = False,
    context: Optional[dict[str, Any]] = None,
) -> Optional[DecisionRequest]:
    request = build_select_unit_request(
        units,
        prompt=prompt,
        player_id=player_id,
        phase_name=phase_name,
        phase_step=phase_step,
        selection_purpose=selection_purpose,
        allow_pass=allow_pass,
        context=context,
    )
    if request is None:
        return None
    request_decision = getattr(game, "request_decision", None)
    if not callable(request_decision):
        raise RuntimeError("Game does not support request_decision().")
    request_decision(request)
    return request


def _select_movement_action_prompt(*, prompt: str, unit: object) -> str:
    text = str(prompt or "").strip()
    if text:
        return text
    label = str(getattr(unit, "name", "") or "Unit").strip() or "Unit"
    return f"Select movement action for {label}"


def _available_move_action_names(unit: object, *, game_map: object | None = None) -> list[str]:
    if unit is None or _unit_has_resolved_round_movement(unit) or _unit_is_in_reserves(unit) or _unit_is_embarked(unit):
        return []
    try:
        engagement_state = unit.get_engagement_state(game_map)
        available = list(unit.get_available_move_actions(getattr(engagement_state, "value", engagement_state)) or [])
    except Exception:
        available = []
    try:
        from warhammer40k_ai.units.unit import MovementAction
    except Exception:
        return []
    action_map = {
        "move": MovementAction.MOVE.value,
        "advance": MovementAction.ADVANCE.value,
        "fall_back": MovementAction.FALL_BACK.value,
        "stationary": MovementAction.REMAIN_STATIONARY.value,
    }
    actions = [name for name, action_value in action_map.items() if action_value in available]
    deduped: list[str] = []
    for action in actions:
        text = str(action or "").strip().lower()
        if text and text not in deduped:
            deduped.append(text)
    return deduped


def build_select_movement_action_request(
    unit: object,
    *,
    prompt: str = "",
    player_id: Optional[str] = None,
    phase_name: str = "",
    phase_step: str = "",
    selection_purpose: str = "",
    game_map: object | None = None,
    context: Optional[dict[str, Any]] = None,
) -> Optional[DecisionRequest]:
    if unit is None:
        return None
    unit_id = str(get_entity_id(unit) or "").strip()
    if not unit_id:
        return None
    action_names = _available_move_action_names(unit, game_map=game_map)
    if not action_names:
        return None
    if player_id is None:
        player_id = _player_id_for_unit(unit)
    options: list[DecisionOption] = []
    for action_name in action_names:
        action_id = (
            f"{DECISION_SELECT_MOVEMENT_ACTION}:"
            f"{str(phase_name or '').strip().upper()}:"
            f"{str(phase_step or '').strip().upper()}:"
            f"{unit_id}:"
            f"{str(action_name or '').strip().upper()}"
        )
        options.append(
            DecisionOption.create(
                str(action_name or "").replace("_", " ").title(),
                payload={
                    "unit_id": unit_id,
                    "action_type": action_name,
                    "action_id": action_id,
                },
            )
        )
    request_context = dict(context or {})
    request_context.setdefault("unit_id", unit_id)
    request_context.setdefault("phase_name", str(phase_name or "").strip().upper())
    request_context.setdefault("phase_step", str(phase_step or "").strip().upper())
    request_context.setdefault("selection_purpose", str(selection_purpose or "").strip().upper())
    request_context["allowed_action_types"] = list(action_names)
    return DecisionRequest.create(
        DECISION_SELECT_MOVEMENT_ACTION,
        _select_movement_action_prompt(prompt=prompt, unit=unit),
        player_id=player_id,
        options=options,
        context=request_context,
    )


def queue_select_movement_action_request(
    game: object,
    unit: object,
    *,
    prompt: str = "",
    player_id: Optional[str] = None,
    phase_name: str = "",
    phase_step: str = "",
    selection_purpose: str = "",
    game_map: object | None = None,
    context: Optional[dict[str, Any]] = None,
) -> Optional[DecisionRequest]:
    request = build_select_movement_action_request(
        unit,
        prompt=prompt,
        player_id=player_id,
        phase_name=phase_name,
        phase_step=phase_step,
        selection_purpose=selection_purpose,
        game_map=game_map,
        context=context,
    )
    if request is None:
        return None
    request_decision = getattr(game, "request_decision", None)
    if not callable(request_decision):
        raise RuntimeError("Game does not support request_decision().")
    request_decision(request)
    return request


def build_move_unit_request(
    unit: object,
    *,
    movement_type: str,
    prompt: str = "",
    player_id: Optional[str] = None,
    max_distance: float | None = None,
    allow_skip: bool = True,
    context: Optional[dict[str, Any]] = None,
) -> Optional[DecisionRequest]:
    if unit is None:
        return None
    unit_id = str(get_entity_id(unit) or "").strip()
    move_kind = str(movement_type or "").strip().lower()
    if not unit_id or not move_kind:
        return None
    if player_id is None:
        player_id = _player_id_for_unit(unit)
    options = [
        DecisionOption.create(
            "Confirm",
            payload={"unit_id": unit_id, "movement_type": move_kind, "action": "confirm"},
        )
    ]
    if bool(allow_skip):
        options.append(
            DecisionOption.create(
                "Skip",
                payload={"unit_id": unit_id, "movement_type": move_kind, "action": "skip"},
            )
        )
    request_context = dict(context or {})
    request_context.setdefault("unit_id", unit_id)
    request_context.setdefault("movement_type", move_kind)
    request_context["allow_skip"] = bool(allow_skip)
    if max_distance is not None:
        request_context["max_distance"] = float(max_distance)
    request_prompt = str(prompt or "").strip() or f"Move {getattr(unit, 'name', 'Unit')} ({move_kind})"
    return DecisionRequest.create(
        DECISION_MOVE_UNIT,
        request_prompt,
        player_id=player_id,
        options=options,
        context=request_context,
    )


def queue_move_unit_request(
    game: object,
    unit: object,
    *,
    movement_type: str,
    prompt: str = "",
    player_id: Optional[str] = None,
    max_distance: float | None = None,
    allow_skip: bool = True,
    context: Optional[dict[str, Any]] = None,
) -> Optional[DecisionRequest]:
    request = build_move_unit_request(
        unit,
        movement_type=movement_type,
        prompt=prompt,
        player_id=player_id,
        max_distance=max_distance,
        allow_skip=allow_skip,
        context=context,
    )
    if request is None:
        return None
    request_decision = getattr(game, "request_decision", None)
    if not callable(request_decision):
        raise RuntimeError("Game does not support request_decision().")
    request_decision(request)
    return request


def _resolve_coherency_prompt(*, prompt: str, unit: object) -> str:
    text = str(prompt or "").strip()
    if text:
        return text
    label = str(getattr(unit, "name", "") or "Unit").strip() or "Unit"
    return f"Select one additional casualty to restore coherency for {label}"


def _coherency_resolution_models(unit: object) -> list[object]:
    if unit is None:
        return []
    get_models = getattr(unit, "get_attached_unit_models", None)
    if callable(get_models):
        models = list(get_models() or [])
    else:
        models = list(getattr(unit, "models", []) or [])
    alive_models: list[object] = []
    for model in models:
        if model is None:
            continue
        if not bool(getattr(model, "is_alive", True)):
            continue
        if bool(getattr(model, "_pending_placement", False)):
            continue
        model_id = str(get_entity_id(model) or "").strip()
        if not model_id:
            continue
        alive_models.append(model)
    alive_models.sort(key=lambda model: str(get_entity_id(model) or "").strip())
    return alive_models


def build_resolve_coherency_request(
    unit: object,
    *,
    prompt: str = "",
    player_id: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> Optional[DecisionRequest]:
    if unit is None:
        return None
    unit_id = str(get_entity_id(unit) or "").strip()
    if not unit_id:
        return None
    models = _coherency_resolution_models(unit)
    if not models:
        return None
    if player_id is None:
        player_id = _player_id_for_unit(unit)
    options: list[DecisionOption] = []
    allowed_model_ids: list[str] = []
    for model in models:
        model_id = str(get_entity_id(model) or "").strip()
        if not model_id:
            continue
        allowed_model_ids.append(model_id)
        model_label = str(getattr(model, "name", "") or "Model").strip() or "Model"
        options.append(
            DecisionOption.create(
                model_label,
                payload={
                    "unit_id": unit_id,
                    "model_id": model_id,
                    "model_ids": [model_id],
                    "action_id": f"{DECISION_RESOLVE_COHERENCY}:{unit_id}:{model_id}",
                },
            )
        )
    if not options:
        return None
    request_context = dict(context or {})
    request_context.setdefault("unit_id", unit_id)
    request_context.setdefault("coherency_failure_reason", "post_casualty")
    request_context.setdefault("required_until_coherent", True)
    request_context["allowed_model_ids"] = list(allowed_model_ids)
    return DecisionRequest.create(
        DECISION_RESOLVE_COHERENCY,
        _resolve_coherency_prompt(prompt=prompt, unit=unit),
        player_id=player_id,
        options=options,
        context=request_context,
    )


def queue_resolve_coherency_request(
    game: object,
    unit: object,
    *,
    prompt: str = "",
    player_id: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> Optional[DecisionRequest]:
    request = build_resolve_coherency_request(
        unit,
        prompt=prompt,
        player_id=player_id,
        context=context,
    )
    if request is None:
        return None
    request_decision = getattr(game, "request_decision", None)
    if not callable(request_decision):
        raise RuntimeError("Game does not support request_decision().")
    request_decision(request)
    return request


def _attached_alive_models(unit: object) -> list[object]:
    if unit is None:
        return []
    get_models = getattr(unit, "get_attached_unit_models", None)
    if callable(get_models):
        try:
            models = list(get_models() or [])
        except TypeError:
            models = list(getattr(unit, "models", []) or [])
    else:
        models = list(getattr(unit, "models", []) or [])
    alive_models = [
        model
        for model in models
        if model is not None
        and bool(getattr(model, "is_alive", True))
        and not bool(getattr(model, "_pending_placement", False))
    ]
    alive_models.sort(key=lambda model: str(get_entity_id(model) or "").strip())
    return alive_models


def _unit_has_ranged_weapon(unit: object) -> bool:
    for model in _attached_alive_models(unit):
        for wargear in list(getattr(model, "wargear", []) or []):
            try:
                if bool(wargear.is_ranged()):
                    return True
            except Exception:
                continue
    return False


def _shooting_enemy_units(game: object | None, unit: object) -> list[object]:
    if game is None or unit is None:
        return []
    game_map = getattr(game, "map", None)
    get_enemy_units = getattr(game_map, "get_enemy_units", None) if game_map is not None else None
    enemies: list[object] = []
    if callable(get_enemy_units):
        try:
            enemies = list(get_enemy_units(unit) or [])
        except (AttributeError, RuntimeError, TypeError, ValueError):
            enemies = []
    if not enemies:
        own_army = getattr(unit, "parent_army", None)
        get_army = getattr(unit, "get_parent_army", None)
        if own_army is None and callable(get_army):
            try:
                own_army = get_army()
            except (AttributeError, RuntimeError, TypeError, ValueError):
                own_army = None
        for player in list(getattr(game, "players", []) or []):
            army = getattr(player, "army", None)
            if army is None:
                getter = getattr(player, "get_army", None)
                if callable(getter):
                    try:
                        army = getter()
                    except (AttributeError, RuntimeError, TypeError, ValueError):
                        army = None
            if army is None or army is own_army:
                continue
            enemies.extend(list(getattr(army, "units", []) or []))
    by_id: dict[str, object] = {}
    for enemy in list(enemies or []):
        if enemy is None:
            continue
        root_getter = getattr(enemy, "get_attached_unit_root", None)
        if callable(root_getter):
            try:
                root = root_getter()
            except (AttributeError, RuntimeError, TypeError, ValueError):
                root = enemy
        else:
            root = enemy
        if root is None:
            continue
        target_id = str(get_entity_id(root) or "").strip()
        if not target_id or target_id in by_id:
            continue
        alive = getattr(root, "is_alive", True)
        try:
            is_alive = bool(alive() if callable(alive) else alive)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            is_alive = False
        if not is_alive:
            continue
        if not bool(getattr(root, "deployed", True)):
            continue
        reserve_check = getattr(root, "is_in_reserves", None)
        if callable(reserve_check):
            try:
                if bool(reserve_check()):
                    continue
            except (AttributeError, RuntimeError, TypeError, ValueError):
                continue
        if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
            continue
        by_id[target_id] = root
    return [by_id[target_id] for target_id in sorted(by_id.keys())]


def _profile_is_targetless(profile: object) -> bool:
    is_plasma_warhead = getattr(profile, "is_plasma_warhead", None)
    if callable(is_plasma_warhead):
        try:
            return bool(is_plasma_warhead())
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return False
    return False


def _shooting_profile_target_ids(
    game: object | None,
    unit: object,
    model: object,
    profile: object,
    targets: list[object],
) -> list[str]:
    validate = getattr(unit, "_validate_shooting_declaration", None)
    game_map = getattr(game, "map", None) if game is not None else None
    target_ids: list[str] = []
    for target in list(targets or []):
        target_id = str(get_entity_id(target) or "").strip()
        if not target_id:
            continue
        if callable(validate):
            try:
                validation = validate(profile, target, [model], game_map)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                validation = {"valid": False}
            if not bool(isinstance(validation, dict) and validation.get("valid", False)):
                continue
        target_ids.append(target_id)
    return target_ids


def _shooting_target_candidates(
    game: object | None,
    unit: object,
    *,
    force_target_unit_id: str = "",
) -> list[dict[str, object]]:
    if game is None or unit is None:
        return []
    targets = _shooting_enemy_units(game, unit)
    forced_target_id = str(force_target_unit_id or "").strip()
    if forced_target_id:
        targets = [target for target in targets if str(get_entity_id(target) or "").strip() == forced_target_id]
    candidates: list[dict[str, object]] = []
    for model in _attached_alive_models(unit):
        model_id = str(get_entity_id(model) or "").strip()
        if not model_id:
            continue
        wargear_items = sorted(
            list(getattr(model, "wargear", []) or []),
            key=lambda item: (str(get_entity_id(item) or ""), str(getattr(item, "name", "") or "")),
        )
        for wargear in wargear_items:
            is_ranged = getattr(wargear, "is_ranged", None)
            if not callable(is_ranged):
                continue
            try:
                if not bool(is_ranged()):
                    continue
            except (AttributeError, RuntimeError, TypeError, ValueError):
                continue
            wargear_id = str(get_entity_id(wargear) or "").strip()
            if not wargear_id:
                continue
            for profile_name, profile in sorted(
                dict(getattr(wargear, "profiles", {}) or {}).items(),
                key=lambda item: str(item[0]),
            ):
                if profile is None:
                    continue
                entry: dict[str, object] = {
                    "model_id": model_id,
                    "wargear_id": wargear_id,
                    "profile_name": str(profile_name or ""),
                }
                if _profile_is_targetless(profile):
                    entry["targetless"] = True
                    candidates.append(entry)
                    continue
                target_ids = _shooting_profile_target_ids(game, unit, model, profile, targets)
                if not target_ids:
                    continue
                entry["target_unit_ids"] = target_ids
                candidates.append(entry)
    candidates.sort(
        key=lambda entry: (
            str(entry.get("model_id", "") or ""),
            str(entry.get("wargear_id", "") or ""),
            str(entry.get("profile_name", "") or ""),
        )
    )
    return candidates


def _source_root_for_model(model: object) -> object | None:
    source_unit = getattr(model, "parent_unit", None)
    if source_unit is None:
        return None
    root_fn = getattr(source_unit, "get_attached_unit_root", None)
    if callable(root_fn):
        try:
            return root_fn()
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return source_unit
    return source_unit


def firing_deck_selection_entries(transport: object) -> list[dict[str, object]]:
    if transport is None:
        return []
    has_fd = False
    fd_x = 0
    has_fd_fn = getattr(transport, "has_firing_deck", None)
    if callable(has_fd_fn):
        try:
            has_fd, fd_x = has_fd_fn()
        except (AttributeError, RuntimeError, TypeError, ValueError):
            has_fd, fd_x = (False, 0)
    if not bool(has_fd) or int(fd_x or 0) <= 0:
        return []

    passengers = list(getattr(transport, "transport_passengers", []) or [])
    passengers.sort(key=lambda unit: str(maybe_entity_id(unit) or ""))
    entries: list[dict[str, object]] = []
    for passenger in passengers:
        root_fn = getattr(passenger, "get_attached_unit_root", None)
        if callable(root_fn):
            try:
                source_root = root_fn()
            except (AttributeError, RuntimeError, TypeError, ValueError):
                source_root = passenger
        else:
            source_root = passenger
        if source_root is None:
            continue
        if getattr(source_root, "embarked_in", None) is not transport and source_root not in passengers:
            continue
        if _unit_has_consumed_normal_shooting(source_root):
            continue
        source_unit_id = str(maybe_entity_id(source_root) or "")
        for model in _attached_alive_models(source_root):
            if _source_root_for_model(model) is not source_root:
                continue
            model_id = str(maybe_entity_id(model) or "")
            if not model_id:
                continue
            try:
                selection_cost = max(1, int(transport.get_firing_deck_selection_cost(model) or 1))
            except (AttributeError, RuntimeError, TypeError, ValueError):
                selection_cost = 1
            wargear_items = sorted(
                list(getattr(model, "wargear", []) or []),
                key=lambda item: (str(maybe_entity_id(item) or ""), str(getattr(item, "name", "") or "")),
            )
            for wargear in wargear_items:
                is_ranged = getattr(wargear, "is_ranged", None)
                if not callable(is_ranged):
                    continue
                try:
                    if not bool(is_ranged()):
                        continue
                except (AttributeError, RuntimeError, TypeError, ValueError):
                    continue
                wargear_id = str(maybe_entity_id(wargear) or "")
                if not wargear_id:
                    continue
                profiles = dict(getattr(wargear, "profiles", {}) or {})
                for profile_name, profile in sorted(profiles.items(), key=lambda item: str(item[0])):
                    if profile is None:
                        continue
                    is_one_shot = getattr(profile, "is_one_shot", None)
                    if callable(is_one_shot):
                        try:
                            if bool(is_one_shot()):
                                continue
                        except (AttributeError, RuntimeError, TypeError, ValueError):
                            continue
                    entries.append(
                        {
                            "model": model,
                            "wargear": wargear,
                            "profile": profile,
                            "profile_name": str(profile_name or ""),
                            "passenger_unit": source_root,
                            "source_unit_id": source_unit_id,
                            "selection_cost": int(selection_cost),
                        }
                    )
    entries.sort(
        key=lambda entry: (
            str(entry.get("source_unit_id", "") or ""),
            str(maybe_entity_id(entry.get("model")) or ""),
            str(maybe_entity_id(entry.get("wargear")) or ""),
            str(entry.get("profile_name", "") or ""),
        )
    )
    return entries


def _firing_deck_candidate_payload(entries: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    payload: list[dict[str, object]] = []
    for entry in list(entries or []):
        model_id = str(maybe_entity_id(entry.get("model")) or "")
        wargear_id = str(maybe_entity_id(entry.get("wargear")) or "")
        profile_name = str(entry.get("profile_name", "") or "")
        if not model_id or not wargear_id or not profile_name:
            continue
        payload.append(
            {
                "model_id": model_id,
                "wargear_id": wargear_id,
                "profile_name": profile_name,
                "source_unit_id": str(entry.get("source_unit_id", "") or ""),
                "selection_cost": int(entry.get("selection_cost", 1) or 1),
            }
        )
    return payload


def build_declare_firing_deck_request(
    transport: object,
    *,
    prompt: str = "",
    player_id: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> Optional[DecisionRequest]:
    if transport is None:
        return None
    transport_id = str(get_entity_id(transport) or "").strip()
    if not transport_id:
        return None
    entries = firing_deck_selection_entries(transport)
    if not entries:
        return None
    try:
        _has_fd, fd_x = transport.has_firing_deck()
    except (AttributeError, RuntimeError, TypeError, ValueError):
        fd_x = 0
    if int(fd_x or 0) <= 0:
        return None
    if player_id is None:
        player_id = _player_id_for_unit(transport)
    label = str(getattr(transport, "name", "") or "Transport").strip() or "Transport"
    request_context = dict(context or {})
    request_context.setdefault("transport_id", transport_id)
    request_context.setdefault("firing_deck_x", int(fd_x or 0))
    request_context.setdefault("candidate_entries", _firing_deck_candidate_payload(entries))
    options = [
        DecisionOption.create("Confirm", payload={"action": "confirm", "transport_id": transport_id}),
        DecisionOption.create("Skip", payload={"action": "skip", "transport_id": transport_id}),
    ]
    return DecisionRequest.create(
        DECISION_DECLARE_FIRING_DECK,
        str(prompt or "").strip() or f"Declare Firing Deck weapons for {label}",
        player_id=player_id,
        options=options,
        context=request_context,
    )


def queue_declare_firing_deck_request(
    game: object,
    transport: object,
    *,
    prompt: str = "",
    player_id: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> Optional[DecisionRequest]:
    request = build_declare_firing_deck_request(
        transport,
        prompt=prompt,
        player_id=player_id,
        context=context,
    )
    if request is None:
        return None
    request_decision = getattr(game, "request_decision", None)
    if not callable(request_decision):
        raise RuntimeError("Game does not support request_decision().")
    request_decision(request)
    return request


def _unit_has_melee_weapon(unit: object) -> bool:
    for model in _attached_alive_models(unit):
        for wargear in list(getattr(model, "wargear", []) or []):
            is_melee = getattr(wargear, "is_melee", None)
            if callable(is_melee) and bool(is_melee()):
                return True
    return False


def _sorted_target_units(target_units: Iterable[object] | None) -> list[object]:
    ordered: list[object] = []
    seen: set[str] = set()
    for target in list(target_units or []):
        if target is None:
            continue
        target_id = str(get_entity_id(target) or "").strip()
        if not target_id or target_id in seen:
            continue
        seen.add(target_id)
        ordered.append(target)
    ordered.sort(key=lambda target: str(get_entity_id(target) or "").strip())
    return ordered


def _fight_within_3_enabled(unit: object) -> bool:
    has_ability = getattr(unit, "has_fight_within_3_ability", None)
    if not callable(has_ability) or not bool(has_ability()):
        return False
    is_active = getattr(unit, "fight_within_3_active", None)
    return bool(callable(is_active) and bool(is_active()))


def _eligible_melee_models_for_targets(
    unit: object,
    target_units: Iterable[object] | None,
    *,
    game_map: object | None,
) -> list[object]:
    if unit is None:
        return []
    get_eligible = getattr(unit, "get_fight_eligible_models_for_target", None)
    if not callable(get_eligible):
        return _attached_alive_models(unit)
    allow_within_3 = _fight_within_3_enabled(unit)
    eligible_by_id: dict[str, object] = {}
    for target in _sorted_target_units(target_units):
        models = list(
            get_eligible(
                target,
                game_map=game_map,
                allow_within_3=allow_within_3,
            )
            or []
        )
        for model in models:
            model_id = str(get_entity_id(model) or "").strip()
            if model_id:
                eligible_by_id[model_id] = model
    return [eligible_by_id[model_id] for model_id in sorted(eligible_by_id.keys())]


def _default_melee_weapon_bundles(
    unit: object,
    *,
    eligible_models: Iterable[object] | None = None,
) -> list[dict[str, str]]:
    if unit is None:
        return []
    eligible_model_ids = {
        str(get_entity_id(model) or "").strip()
        for model in list(eligible_models or [])
        if str(get_entity_id(model) or "").strip()
    }
    bundles: list[dict[str, str]] = []
    for model in _attached_alive_models(unit):
        model_id = str(get_entity_id(model) or "").strip()
        if not model_id:
            continue
        if eligible_model_ids and model_id not in eligible_model_ids:
            continue
        primary_bundle: dict[str, str] | None = None
        extra_bundles: list[dict[str, str]] = []
        wargear_items = sorted(
            list(getattr(model, "wargear", []) or []),
            key=lambda item: str(get_entity_id(item) or "").strip(),
        )
        for wargear in wargear_items:
            is_melee = getattr(wargear, "is_melee", None)
            if not callable(is_melee) or not bool(is_melee()):
                continue
            wargear_id = str(get_entity_id(wargear) or "").strip()
            if not wargear_id:
                continue
            profiles = getattr(wargear, "profiles", {}) or {}
            for profile_name, profile in sorted(profiles.items(), key=lambda item: str(item[0])):
                is_extra_attacks = False
                is_extra_attacks_fn = getattr(profile, "is_extra_attacks", None)
                if callable(is_extra_attacks_fn):
                    is_extra_attacks = bool(is_extra_attacks_fn())
                elif hasattr(profile, "extra_attacks"):
                    is_extra_attacks = bool(getattr(profile, "extra_attacks", False))
                entry = {
                    "model_id": model_id,
                    "wargear_id": wargear_id,
                    "profile_name": str(profile_name or ""),
                }
                if is_extra_attacks:
                    extra_bundles.append(entry)
                    continue
                if primary_bundle is None:
                    primary_bundle = entry
        if primary_bundle is not None:
            bundles.append(primary_bundle)
        bundles.extend(extra_bundles)
    return bundles


def _default_attack_declarations(
    unit: object,
    *,
    target_units: Iterable[object] | None,
    weapon_declarations: Iterable[dict] | None,
    game_map: object | None,
) -> list[dict[str, object]]:
    if unit is None:
        return []
    targets = list(target_units or [])
    if not targets:
        return []
    allow_within_3 = _fight_within_3_enabled(unit)
    get_eligible = getattr(unit, "get_fight_eligible_models_for_target", None)
    eligible_by_target: dict[str, set[str]] = {}
    if callable(get_eligible):
        for target in targets:
            target_id = str(get_entity_id(target) or "").strip()
            if not target_id:
                continue
            models = list(
                get_eligible(
                    target,
                    game_map=game_map,
                    allow_within_3=allow_within_3,
                )
                or []
            )
            eligible_by_target[target_id] = {
                str(get_entity_id(model) or "").strip()
                for model in models
                if str(get_entity_id(model) or "").strip()
            }
    attack_declarations: list[dict[str, object]] = []
    for declaration in list(weapon_declarations or []):
        model = declaration.get("model")
        wargear = declaration.get("wargear")
        profile_name = str(declaration.get("profile_name", "") or "")
        model_id = str(get_entity_id(model) or "").strip()
        wargear_id = str(get_entity_id(wargear) or "").strip()
        if not model_id or not wargear_id or not profile_name:
            continue
        selected_target_id = ""
        for target in targets:
            target_id = str(get_entity_id(target) or "").strip()
            if not target_id:
                continue
            eligible_model_ids = eligible_by_target.get(target_id)
            if eligible_model_ids is not None and model_id not in eligible_model_ids:
                continue
            selected_target_id = target_id
            break
        if not selected_target_id:
            continue
        entry: dict[str, object] = {
            "model_id": model_id,
            "wargear_id": wargear_id,
            "profile_name": profile_name,
            "target_unit_id": selected_target_id,
        }
        if "attacks_override" in declaration:
            entry["attacks_override"] = int(declaration.get("attacks_override") or 0)
        if "attacks_override_modifiers" in declaration:
            entry["attacks_override_modifiers"] = list(declaration.get("attacks_override_modifiers") or [])
        if "attacks_override_note" in declaration:
            entry["attacks_override_note"] = str(declaration.get("attacks_override_note", "") or "")
        attack_declarations.append(entry)
    return attack_declarations


def _declare_shots_prompt(*, prompt: str, unit: object) -> str:
    text = str(prompt or "").strip()
    if text:
        return text
    label = str(getattr(unit, "name", "") or "Unit").strip() or "Unit"
    return f"Declare shots for {label}"


def build_declare_shots_request(
    unit: object,
    *,
    prompt: str = "",
    player_id: Optional[str] = None,
    out_of_phase: bool = False,
    context: Optional[dict[str, Any]] = None,
) -> Optional[DecisionRequest]:
    if unit is None:
        return None
    unit_id = str(get_entity_id(unit) or "").strip()
    if not unit_id:
        return None
    if not bool(getattr(unit, "deployed", True)):
        return None
    if bool(getattr(unit, "is_embarked", False)) or bool(getattr(unit, "embarked_in", None)):
        return None
    if not bool(out_of_phase) and _unit_has_consumed_normal_shooting(unit):
        return None
    reserve_fn = getattr(unit, "is_in_reserves", None)
    if callable(reserve_fn) and bool(reserve_fn()):
        return None
    if not _unit_has_ranged_weapon(unit):
        return None
    if player_id is None:
        player_id = _player_id_for_unit(unit)
    request_context = dict(context or {})
    request_context.setdefault("unit_id", unit_id)
    request_context.setdefault("out_of_phase", bool(out_of_phase))
    if not bool(out_of_phase):
        request_context.setdefault("phase_name", "SHOOTING_PHASE")
        request_context.setdefault("phase_step", "SHOOT_UNITS")
        request_context.setdefault("selection_purpose", "ACTIVATE_SHOOTING_UNIT")
    allowed_model_ids: list[str] = []
    allowed_wargear_ids: list[str] = []
    for model in _attached_alive_models(unit):
        model_id = str(get_entity_id(model) or "").strip()
        if model_id:
            allowed_model_ids.append(model_id)
        for wargear in list(getattr(model, "wargear", []) or []):
            try:
                if not bool(wargear.is_ranged()):
                    continue
            except Exception:
                continue
            wargear_id = str(get_entity_id(wargear) or "").strip()
            if wargear_id:
                allowed_wargear_ids.append(wargear_id)
    request_context.setdefault("allowed_model_ids", sorted(set(allowed_model_ids)))
    request_context.setdefault("allowed_wargear_ids", sorted(set(allowed_wargear_ids)))
    options = [
        DecisionOption.create("Confirm", payload={"action": "confirm", "unit_id": unit_id}),
        DecisionOption.create("Skip", payload={"action": "skip", "unit_id": unit_id}),
    ]
    return DecisionRequest.create(
        DECISION_DECLARE_SHOTS,
        _declare_shots_prompt(prompt=prompt, unit=unit),
        player_id=player_id,
        options=options,
        context=request_context,
    )


def queue_declare_shots_request(
    game: object,
    unit: object,
    *,
    prompt: str = "",
    player_id: Optional[str] = None,
    out_of_phase: bool = False,
    context: Optional[dict[str, Any]] = None,
) -> Optional[DecisionRequest]:
    request = build_declare_shots_request(
        unit,
        prompt=prompt,
        player_id=player_id,
        out_of_phase=out_of_phase,
        context=context,
    )
    if request is None:
        return None
    target_candidates = _shooting_target_candidates(
        game,
        unit,
        force_target_unit_id=str((context or {}).get("force_target_unit_id", "") or ""),
    )
    if target_candidates:
        request.context.setdefault("shooting_target_candidates", target_candidates)
        game_map = getattr(game, "map", None)
        try:
            state_generation = int(getattr(game_map, "state_generation", 0) or 0)
        except (TypeError, ValueError):
            state_generation = 0
        request.context.setdefault("shooting_target_candidates_state_generation", state_generation)
        allowed_target_ids = sorted(
            {
                str(target_id or "").strip()
                for candidate in target_candidates
                for target_id in list(candidate.get("target_unit_ids", []) or [])
                if str(target_id or "").strip()
            }
        )
        request.context.setdefault("allowed_target_unit_ids", allowed_target_ids)
    request_decision = getattr(game, "request_decision", None)
    if not callable(request_decision):
        raise RuntimeError("Game does not support request_decision().")
    request_decision(request)
    return request


def _declare_melee_weapons_prompt(*, prompt: str, unit: object) -> str:
    text = str(prompt or "").strip()
    if text:
        return text
    label = str(getattr(unit, "name", "") or "Unit").strip() or "Unit"
    return f"Declare melee weapons for {label}"


def build_declare_melee_weapons_request(
    game: object,
    unit: object,
    *,
    target_units: Iterable[object] | None,
    prompt: str = "",
    player_id: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> Optional[DecisionRequest]:
    if game is None or unit is None:
        return None
    unit_id = str(get_entity_id(unit) or "").strip()
    if not unit_id or not _unit_has_melee_weapon(unit):
        return None
    targets = _sorted_target_units(target_units)
    if not targets:
        return None
    eligible_models = _eligible_melee_models_for_targets(unit, targets, game_map=getattr(game, "map", None))
    weapon_bundles = _default_melee_weapon_bundles(unit, eligible_models=eligible_models)
    if not weapon_bundles:
        return None
    if player_id is None:
        player_id = _player_id_for_unit(unit)
    target_ids = [str(get_entity_id(target) or "").strip() for target in targets]
    request_context = dict(context or {})
    request_context.setdefault("unit_id", unit_id)
    request_context.setdefault("phase_name", "FIGHT_PHASE")
    request_context.setdefault("selection_purpose", "DECLARE_MELEE_WEAPONS")
    request_context["target_unit_ids"] = list(target_ids)
    if len(target_ids) == 1:
        request_context.setdefault("target_unit_id", target_ids[0])
    request_context["eligible_model_ids"] = [
        str(get_entity_id(model) or "").strip()
        for model in eligible_models
        if str(get_entity_id(model) or "").strip()
    ]
    options = [
        DecisionOption.create(
            "Confirm",
            payload={
                "action": "confirm",
                "unit_id": unit_id,
                "weapon_bundles": weapon_bundles,
            },
        )
    ]
    return DecisionRequest.create(
        DECISION_DECLARE_MELEE_WEAPONS,
        _declare_melee_weapons_prompt(prompt=prompt, unit=unit),
        player_id=player_id,
        options=options,
        context=request_context,
    )


def queue_declare_melee_weapons_request(
    game: object,
    unit: object,
    *,
    target_units: Iterable[object] | None,
    prompt: str = "",
    player_id: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> Optional[DecisionRequest]:
    request = build_declare_melee_weapons_request(
        game,
        unit,
        target_units=target_units,
        prompt=prompt,
        player_id=player_id,
        context=context,
    )
    if request is None:
        return None
    request_decision = getattr(game, "request_decision", None)
    if not callable(request_decision):
        raise RuntimeError("Game does not support request_decision().")
    request_decision(request)
    return request


def _allocate_melee_targets_prompt(*, prompt: str, unit: object) -> str:
    text = str(prompt or "").strip()
    if text:
        return text
    label = str(getattr(unit, "name", "") or "Unit").strip() or "Unit"
    return f"Allocate melee targets for {label}"


def build_allocate_melee_targets_request(
    game: object,
    unit: object,
    *,
    target_units: Iterable[object] | None,
    weapon_declarations: Iterable[dict] | None,
    prompt: str = "",
    player_id: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> Optional[DecisionRequest]:
    if game is None or unit is None:
        return None
    unit_id = str(get_entity_id(unit) or "").strip()
    if not unit_id:
        return None
    targets = _sorted_target_units(target_units)
    if len(targets) < 2:
        return None
    attack_declarations = _default_attack_declarations(
        unit,
        target_units=targets,
        weapon_declarations=weapon_declarations,
        game_map=getattr(game, "map", None),
    )
    if not attack_declarations:
        return None
    if player_id is None:
        player_id = _player_id_for_unit(unit)
    request_context = dict(context or {})
    request_context.setdefault("unit_id", unit_id)
    request_context.setdefault("phase_name", "FIGHT_PHASE")
    request_context.setdefault("selection_purpose", "ALLOCATE_MELEE_TARGETS")
    request_context["target_unit_ids"] = [str(get_entity_id(target) or "").strip() for target in targets]
    options = [
        DecisionOption.create(
            "Confirm",
            payload={
                "action": "confirm",
                "unit_id": unit_id,
                "attack_declarations": attack_declarations,
            },
        )
    ]
    return DecisionRequest.create(
        DECISION_ALLOCATE_MELEE_TARGETS,
        _allocate_melee_targets_prompt(prompt=prompt, unit=unit),
        player_id=player_id,
        options=options,
        context=request_context,
    )


def queue_allocate_melee_targets_request(
    game: object,
    unit: object,
    *,
    target_units: Iterable[object] | None,
    weapon_declarations: Iterable[dict] | None,
    prompt: str = "",
    player_id: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> Optional[DecisionRequest]:
    request = build_allocate_melee_targets_request(
        game,
        unit,
        target_units=target_units,
        weapon_declarations=weapon_declarations,
        prompt=prompt,
        player_id=player_id,
        context=context,
    )
    if request is None:
        return None
    request_decision = getattr(game, "request_decision", None)
    if not callable(request_decision):
        raise RuntimeError("Game does not support request_decision().")
    request_decision(request)
    return request


def _declare_charge_prompt(*, prompt: str, unit: object) -> str:
    text = str(prompt or "").strip()
    if text:
        return text
    label = str(getattr(unit, "name", "") or "Unit").strip() or "Unit"
    return f"Declare charge for {label}"


def build_declare_charge_request(
    game: object,
    unit: object,
    *,
    prompt: str = "",
    player_id: Optional[str] = None,
    out_of_turn: bool = False,
    context: Optional[dict[str, Any]] = None,
) -> Optional[DecisionRequest]:
    if game is None or unit is None:
        return None
    unit_id = str(get_entity_id(unit) or "").strip()
    if not unit_id:
        return None
    if not bool(getattr(unit, "deployed", True)):
        return None
    if bool(getattr(unit, "is_embarked", False)) or bool(getattr(unit, "embarked_in", None)):
        return None
    reserve_fn = getattr(unit, "is_in_reserves", None)
    if callable(reserve_fn) and bool(reserve_fn()):
        return None
    can_charge = getattr(unit, "can_declare_charge", None)
    if not callable(can_charge) or not bool(can_charge(game, out_of_turn=out_of_turn)):
        return None
    game_map = getattr(game, "map", None)
    if game_map is None:
        return None
    enemy_units = list(getattr(game_map, "get_enemy_units", lambda _unit: [])(unit) or [])
    valid_targets: list[object] = []
    seen_target_ids: set[str] = set()
    can_target = getattr(unit, "can_declare_charge_against", None)
    for target in list(enemy_units or []):
        if target is None:
            continue
        try:
            target_root = target.get_attached_unit_root()
        except Exception:
            target_root = target
        if target_root is None or not bool(getattr(target_root, "is_alive", lambda: True)()):
            continue
        target_id = str(get_entity_id(target_root) or "").strip()
        if not target_id or target_id in seen_target_ids:
            continue
        if not callable(can_target):
            continue
        try:
            if not bool(can_target(target_root, game, out_of_turn=out_of_turn)):
                continue
        except Exception:
            continue
        seen_target_ids.add(target_id)
        valid_targets.append(target_root)
    if not valid_targets:
        return None
    try:
        valid_targets.sort(key=lambda target: float(game_map.get_distance_between_units(unit, target)))
    except Exception:
        valid_targets.sort(key=lambda target: str(get_entity_id(target) or "").strip())
    if player_id is None:
        player_id = _player_id_for_unit(unit)
    options: list[DecisionOption] = []
    allowed_target_unit_ids: list[str] = []
    for target in valid_targets:
        target_id = str(get_entity_id(target) or "").strip()
        if not target_id:
            continue
        allowed_target_unit_ids.append(target_id)
        options.append(
            DecisionOption.create(
                str(getattr(target, "name", "") or "Target").strip() or "Target",
                payload={
                    "unit_id": unit_id,
                    "target_unit_id": target_id,
                    "action_id": f"{DECISION_DECLARE_CHARGE}:{unit_id}:{target_id}",
                    "out_of_turn": bool(out_of_turn),
                },
            )
        )
    if not options:
        return None
    request_context = dict(context or {})
    request_context.setdefault("unit_id", unit_id)
    request_context.setdefault("out_of_turn", bool(out_of_turn))
    request_context.setdefault("phase_name", "CHARGE_PHASE")
    request_context.setdefault("phase_step", "DECLARE_CHARGES")
    request_context.setdefault("selection_purpose", "ACTIVATE_CHARGING_UNIT")
    request_context["allowed_target_unit_ids"] = list(allowed_target_unit_ids)
    return DecisionRequest.create(
        DECISION_DECLARE_CHARGE,
        _declare_charge_prompt(prompt=prompt, unit=unit),
        player_id=player_id,
        options=options,
        context=request_context,
    )


def queue_declare_charge_request(
    game: object,
    unit: object,
    *,
    prompt: str = "",
    player_id: Optional[str] = None,
    out_of_turn: bool = False,
    context: Optional[dict[str, Any]] = None,
) -> Optional[DecisionRequest]:
    request = build_declare_charge_request(
        game,
        unit,
        prompt=prompt,
        player_id=player_id,
        out_of_turn=out_of_turn,
        context=context,
    )
    if request is None:
        return None
    request_decision = getattr(game, "request_decision", None)
    if not callable(request_decision):
        raise RuntimeError("Game does not support request_decision().")
    request_decision(request)
    return request


def _norm_ability_name(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def _iter_unit_ability_names(unit: object) -> Iterable[str]:
    if unit is None:
        return
    iter_entries = getattr(unit, "_iter_ability_entries_for_rules", None)
    if callable(iter_entries):
        entries = None
        try:
            entries = iter_entries(model=None)
        except TypeError:
            entries = iter_entries()
        if entries is not None:
            for name, _desc in entries:
                name_text = str(name or "").strip()
                if name_text:
                    yield name_text
            return
    for ability in list(getattr(unit, "possible_abilities", []) or []):
        if isinstance(ability, str):
            name_text = ability
        else:
            name_text = str(getattr(ability, "name", "") or "")
        if str(name_text or "").strip():
            yield str(name_text).strip()


def _unit_has_ability_name(unit: object, ability_name: str) -> bool:
    target = _norm_ability_name(ability_name)
    if not target:
        return False
    for name in _iter_unit_ability_names(unit):
        if _norm_ability_name(name) == target:
            return True
    return False


def _ability_name_and_description(ability: object) -> tuple[str, str]:
    if isinstance(ability, str):
        return "", str(ability or "")
    if isinstance(ability, dict):
        return (
            str(ability.get("name", "") or ""),
            str(ability.get("description", "") or ""),
        )
    return (
        str(getattr(ability, "name", "") or ""),
        str(getattr(ability, "description", "") or ""),
    )


def _ability_is_declare_selected_leading_infiltrators(ability: object) -> bool:
    name, desc = _ability_name_and_description(ability)
    text = str(f"{name} {desc}".strip() or "").lower()
    text = text.replace("\u2019", "'").replace("\u0192?T", "'")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return False
    if "if your army contains one or more units with this ability" not in text:
        return False
    if "during the declare battle formations step select one of those units" not in text:
        return False
    if "while the selected unit is leading a unit" not in text:
        return False
    return "models in that unit have the infiltrators ability" in text


def _unit_has_declare_selected_leading_infiltrators_ability(unit: object) -> bool:
    if unit is None:
        return False
    check_method = getattr(unit, "has_declare_battle_formations_selected_leading_infiltrators_ability", None)
    if callable(check_method):
        try:
            return bool(check_method())
        except Exception:
            pass
    for ability in list(getattr(unit, "possible_abilities", []) or []):
        if _ability_is_declare_selected_leading_infiltrators(ability):
            return True
    return False


def _unit_declare_selected_leading_infiltrators_ability_name(unit: object) -> str:
    if unit is None:
        return ""
    for ability in list(getattr(unit, "possible_abilities", []) or []):
        if not _ability_is_declare_selected_leading_infiltrators(ability):
            continue
        name, _desc = _ability_name_and_description(ability)
        label = str(name or "").strip()
        if label:
            return label
    return ""


def _unit_declare_selected_units_gain_scouts_specs(unit: object) -> list[dict]:
    if unit is None:
        return []
    get_specs = getattr(unit, "get_declare_battle_formations_selected_units_gain_scouts_specs", None)
    if callable(get_specs):
        try:
            return [dict(spec or {}) for spec in list(get_specs() or []) if isinstance(spec, dict)]
        except Exception:
            return []
    return []


def _unit_declare_selected_units_gain_deep_strike_specs(unit: object) -> list[dict]:
    if unit is None:
        return []
    get_specs = getattr(unit, "get_declare_battle_formations_selected_units_gain_deep_strike_specs", None)
    if callable(get_specs):
        try:
            return [dict(spec or {}) for spec in list(get_specs() or []) if isinstance(spec, dict)]
        except Exception:
            return []
    return []


def _unit_alive_model_count(unit: object) -> int:
    models = [
        model
        for model in list(getattr(unit, "models", []) or [])
        if model is not None and bool(getattr(model, "is_alive", True))
    ]
    return int(len(models))


def _leader_attachment_options(leader, bodyguards: List[object]) -> List[DecisionOption]:
    leader_id = get_entity_id(leader)
    options = [DecisionOption.create("Unattached", payload={"leader_id": leader_id, "bodyguard_id": None})]
    current = getattr(leader, "attached_to", None)
    for bg in bodyguards:
        try:
            if not leader.can_attach_to(bg):
                continue
        except Exception:
            continue
        if bg is not current:
            try:
                max_leaders = int(bg.max_attached_leaders())
            except Exception:
                max_leaders = 1
            try:
                current_leaders = list(getattr(bg, "attached_leaders", []) or [])
            except Exception:
                current_leaders = []
            if len(current_leaders) >= max_leaders:
                continue
        label = str(getattr(bg, "name", "Bodyguard"))
        options.append(
            DecisionOption.create(
                label,
                payload={"leader_id": leader_id, "bodyguard_id": get_entity_id(bg)},
            )
        )
    return options


def build_leader_attachment_requests(
    game: object,
    units: Iterable[object],
    *,
    queue_requests: bool = True,
) -> List[DecisionRequest]:
    all_units = _stable_sorted_units(units)
    leaders = [u for u in all_units if bool(getattr(u, "is_leader", False))]
    bodyguards = [
        u for u in all_units
        if not bool(getattr(u, "is_leader", False))
        and not bool(getattr(u, "is_joined_support", False))
    ]
    requests: List[DecisionRequest] = []
    for leader in leaders:
        authored_binding = getattr(leader, "has_build_authored_leader_attachment", None)
        if callable(authored_binding) and authored_binding():
            continue
        options = _leader_attachment_options(leader, bodyguards)
        prompt = f"Attach leader {getattr(leader, 'name', 'Leader')}"
        request = DecisionRequest.create(
            DECISION_ATTACH_LEADER,
            prompt,
            player_id=_player_id_for_unit(leader),
            options=options,
            context={"leader_id": get_entity_id(leader)},
        )
        requests.append(request)
        if queue_requests and hasattr(game, "request_decision"):
            game.request_decision(request)
    return requests


def _support_artillery_attachment_options(support_unit, bodyguards: List[object]) -> List[DecisionOption]:
    support_id = get_entity_id(support_unit)
    options: List[DecisionOption] = []
    requires_attach_fn = getattr(support_unit, "joined_support_requires_attachment", None)
    requires_attachment = bool(requires_attach_fn()) if callable(requires_attach_fn) else False
    if not requires_attachment:
        options.append(DecisionOption.create("Unattached", payload={"support_unit_id": support_id, "bodyguard_id": None}))
    current = getattr(support_unit, "support_joined_to", None)
    for bg in bodyguards:
        try:
            if not support_unit.can_join_support_artillery(bg):
                continue
        except Exception:
            continue
        if bg is not current:
            try:
                supports = list(getattr(bg, "attached_support_units", []) or [])
            except Exception:
                supports = []
            if supports:
                continue
        label = str(getattr(bg, "name", "Bodyguard"))
        options.append(
            DecisionOption.create(
                label,
                payload={"support_unit_id": support_id, "bodyguard_id": get_entity_id(bg)},
            )
        )
    return options


def build_support_artillery_attachment_requests(
    game: object,
    units: Iterable[object],
    *,
    queue_requests: bool = True,
) -> List[DecisionRequest]:
    all_units = _stable_sorted_units(units)
    supports = [
        u for u in all_units
        if bool(getattr(u, "has_joined_support_ability", lambda: False)())
    ]
    bodyguards = [
        u for u in all_units
        if not bool(getattr(u, "is_leader", False))
        and not bool(getattr(u, "is_joined_support", False))
    ]
    requests: List[DecisionRequest] = []
    for support_unit in supports:
        authored_binding = getattr(support_unit, "has_build_authored_support_attachment", None)
        if callable(authored_binding) and authored_binding():
            continue
        options = _support_artillery_attachment_options(support_unit, bodyguards)
        current = getattr(support_unit, "support_joined_to", None)
        has_target_options = any(
            opt.payload.get("bodyguard_id") is not None
            for opt in list(options or [])
        )
        if current is None and not has_target_options:
            continue
        prompt = f"Attach joined support unit {getattr(support_unit, 'name', 'Support Unit')}"
        request = DecisionRequest.create(
            DECISION_ATTACH_SUPPORT_ARTILLERY,
            prompt,
            player_id=_player_id_for_unit(support_unit),
            options=options,
            context={"support_unit_id": get_entity_id(support_unit)},
        )
        requests.append(request)
        if queue_requests and hasattr(game, "request_decision"):
            game.request_decision(request)
    return requests


def build_transport_assignment_requests(
    game: object,
    units: Iterable[object],
    *,
    queue_requests: bool = True,
) -> List[DecisionRequest]:
    all_units = _stable_sorted_units(units)
    transports = [u for u in all_units if bool(getattr(u, "is_transport", False))]
    requests: List[DecisionRequest] = []
    for unit in all_units:
        if bool(getattr(unit, "is_transport", False)):
            continue
        if bool(getattr(unit, "is_attached_leader", False)):
            continue
        if bool(getattr(unit, "is_joined_support", False)):
            continue
        if getattr(unit, "deployed", False):
            continue
        options = [
            DecisionOption.create(
                "No transport",
                payload={"unit_id": get_entity_id(unit), "transport_id": None},
            )
        ]
        for transport in transports:
            try:
                if not transport.can_transport(unit):
                    continue
            except Exception:
                continue
            label = str(getattr(transport, "name", "Transport"))
            options.append(
                DecisionOption.create(
                    label,
                    payload={"unit_id": get_entity_id(unit), "transport_id": get_entity_id(transport)},
                )
            )
        if len(options) <= 1:
            continue
        prompt = f"Assign transport for {getattr(unit, 'name', 'Unit')}"
        request = DecisionRequest.create(
            DECISION_ASSIGN_TRANSPORT,
            prompt,
            player_id=_player_id_for_unit(unit),
            options=options,
            context={"unit_id": get_entity_id(unit)},
        )
        requests.append(request)
        if queue_requests and hasattr(game, "request_decision"):
            game.request_decision(request)
    return requests


def build_shadow_assignment_requests(
    game: object,
    units: Iterable[object],
    *,
    queue_requests: bool = True,
) -> List[DecisionRequest]:
    all_units = _iter_units(units)
    units_by_army: dict[str, list[object]] = {}
    army_by_key: dict[str, object] = {}
    for unit in all_units:
        army = _army_for_unit(unit)
        if army is None:
            continue
        key = _army_key(army)
        if not key:
            continue
        units_by_army.setdefault(key, []).append(unit)
        army_by_key[key] = army

    requests: List[DecisionRequest] = []
    for key in sorted(units_by_army.keys()):
        army = army_by_key[key]
        if not army_supports_shadow_assignment(army):
            continue
        army_units = list(units_by_army[key] or [])
        sources = [unit for unit in army_units if unit_has_shadow_assignment(unit)]
        sources.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        for source_unit in sources:
            source_id = str(get_entity_id(source_unit) or "")
            if not source_id:
                continue
            option_defs = shadow_assignment_options_for_unit(source_unit, army_units)
            if len(option_defs) <= 1:
                continue
            options = [
                DecisionOption.create(str(label), payload=dict(payload or {}))
                for label, payload in option_defs
            ]
            request = DecisionRequest.create(
                DECISION_SHADOW_ASSIGNMENT,
                f"Shadow Assignment for {getattr(source_unit, 'name', 'Assassin')}",
                player_id=_player_id_for_unit(source_unit),
                options=options,
                context={
                    "ability": "shadow_assignment",
                    "ability_name": "Shadow Assignment",
                    "unit_id": source_id,
                },
            )
            requests.append(request)
            if queue_requests and hasattr(game, "request_decision"):
                game.request_decision(request)

    return requests


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _clamp(value: float, *, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))


def _reserve_group_roots(army: object) -> list[object]:
    if army is None:
        return []
    iter_roots = getattr(army, "_iter_reserve_group_roots", None)
    if callable(iter_roots):
        roots = [unit for unit in list(iter_roots() or []) if unit is not None]
    else:
        roots = []
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            if bool(getattr(unit, "is_attached_leader", False)):
                continue
            if bool(getattr(unit, "is_joined_support", False)):
                continue
            roots.append(unit)
    return _stable_sorted_units(roots)


def _unit_supports_standard_reserves(army: object, unit: object) -> bool:
    if unit is None:
        return False
    has_deep_strike = getattr(unit, "has_deep_strike", None)
    if callable(has_deep_strike) and bool(has_deep_strike()):
        return True
    allow_fn = getattr(army, "_ride_the_wind_allows_standard_reserves", None) if army is not None else None
    if callable(allow_fn):
        return bool(allow_fn(unit))
    return False


def _must_start_in_reserves(unit: object) -> bool:
    must_start_fn = getattr(unit, "must_start_in_reserves", None)
    return bool(must_start_fn()) if callable(must_start_fn) else False


def _reserve_status_choices(army: object, unit: object) -> list[str]:
    if _must_start_in_reserves(unit):
        return ["reserves"]
    choices = ["deploy"]
    if _unit_supports_standard_reserves(army, unit):
        choices.append("reserves")
    if not bool(getattr(unit, "is_fortification", False)):
        choices.append("strategic_reserves")
    return choices


def _forced_reserves_decisions(army: object) -> dict[str, str]:
    forced: dict[str, str] = {}
    for unit in _reserve_group_roots(army):
        unit_id = str(get_entity_id(unit) or "")
        if not unit_id:
            continue
        choices = _reserve_status_choices(army, unit)
        forced[unit_id] = choices[0] if choices else "deploy"
    return forced


def _reserve_unit_priority(army: object, unit: object) -> float:
    has_deep_strike = 1.0 if _unit_supports_standard_reserves(army, unit) else 0.0
    has_infiltrate = 0.0
    has_scout = 0.0
    has_infiltrate_fn = getattr(unit, "has_infiltrate", None)
    if callable(has_infiltrate_fn) and bool(has_infiltrate_fn()):
        has_infiltrate = 1.0
    has_scout_fn = getattr(unit, "has_scout", None)
    if callable(has_scout_fn):
        scout_value = has_scout_fn()
        if isinstance(scout_value, (list, tuple)):
            has_scout = 1.0 if bool(scout_value[0]) else 0.0
        else:
            has_scout = 1.0 if bool(scout_value) else 0.0
    get_cost = getattr(unit, "get_unit_cost", None)
    points = _safe_float(get_cost()) if callable(get_cost) else 0.0
    model_count = float(len(list(getattr(unit, "models", []) or [])))
    is_transport = 1.0 if bool(getattr(unit, "is_transport", False)) else 0.0
    is_titanic = 1.0 if bool(getattr(unit, "is_titanic", False)) else 0.0
    is_leader = 1.0 if bool(getattr(unit, "is_leader", False)) else 0.0
    score = 0.0
    score += points
    score += has_deep_strike * 120.0
    score += has_infiltrate * 45.0
    score += has_scout * 40.0
    score += min(20.0, model_count * 1.5)
    score += is_transport * 30.0
    score += is_titanic * 90.0
    score -= is_leader * 15.0
    tie_blob = json.dumps(_unit_stable_sort_key(unit), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    tie = int(hashlib.sha256(tie_blob.encode("utf-8")).hexdigest()[:8], 16)
    return float(score + (float(tie % 1000) / 10000.0))


def _normalize_reserves_decisions(army: object, decisions: dict[str, str] | None) -> dict[str, str]:
    normalized: dict[str, str] = {}
    roots = _reserve_group_roots(army)
    for unit in roots:
        unit_id = str(get_entity_id(unit) or "")
        if not unit_id:
            continue
        available = _reserve_status_choices(army, unit)
        raw_status = str(dict(decisions or {}).get(unit_id, "deploy") or "deploy")
        if raw_status not in available:
            raw_status = available[0] if available else "deploy"
        normalized[unit_id] = raw_status
    return normalized


def _reserves_validation(army: object, decisions: dict[str, str]) -> dict[str, object]:
    validate_fn = getattr(army, "validate_reserves_decisions", None) if army is not None else None
    if callable(validate_fn):
        return dict(validate_fn(dict(decisions or {})) or {})
    return {"valid": True}


def _reserves_apply_enforcement(army: object, decisions: dict[str, str]) -> dict[str, str]:
    enforce_fn = getattr(army, "enforce_reserves_limits", None) if army is not None else None
    if callable(enforce_fn):
        return dict(enforce_fn(dict(decisions or {})) or {})
    return dict(decisions or {})


def _reserves_buckets_from_decisions(decisions: dict[str, str]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {
        "deploy": [],
        "reserves": [],
        "strategic_reserves": [],
    }
    for unit_id, status in sorted((dict(decisions or {})).items()):
        bucket = str(status or "deploy")
        if bucket not in buckets:
            bucket = "deploy"
        buckets[bucket].append(str(unit_id))
    return buckets


def _reserves_greedy_decisions(
    army: object,
    *,
    base_decisions: dict[str, str],
    primary_status: str,
    secondary_status: str | None = None,
) -> dict[str, str]:
    decisions = dict(base_decisions or {})
    roots = _reserve_group_roots(army)
    ranked = sorted(
        [unit for unit in roots if not _must_start_in_reserves(unit)],
        key=lambda unit: (-_reserve_unit_priority(army, unit), _unit_stable_sort_key(unit)),
    )
    for unit in ranked:
        unit_id = str(get_entity_id(unit) or "")
        if not unit_id:
            continue
        available = _reserve_status_choices(army, unit)
        if primary_status in available:
            desired = primary_status
        elif secondary_status is not None and secondary_status in available:
            desired = secondary_status
        else:
            continue
        if decisions.get(unit_id, "deploy") == desired:
            continue
        trial = dict(decisions)
        trial[unit_id] = desired
        status = _reserves_validation(army, trial)
        if bool(status.get("valid", False)):
            decisions = trial
    return decisions


def _reserves_strategy_decisions(
    army: object,
    *,
    strategy_id: str,
    forced_decisions: dict[str, str],
) -> dict[str, str]:
    strategy = str(strategy_id or "").strip().lower()
    if strategy == "deep_strike_pressure":
        return _reserves_greedy_decisions(
            army,
            base_decisions=forced_decisions,
            primary_status="reserves",
            secondary_status="strategic_reserves",
        )
    if strategy == "strategic_pressure":
        return _reserves_greedy_decisions(
            army,
            base_decisions=forced_decisions,
            primary_status="strategic_reserves",
            secondary_status="reserves",
        )
    if strategy == "balanced_mix":
        mixed = dict(forced_decisions or {})
        roots = _reserve_group_roots(army)
        ranked = sorted(
            [unit for unit in roots if not _must_start_in_reserves(unit)],
            key=lambda unit: (-_reserve_unit_priority(army, unit), _unit_stable_sort_key(unit)),
        )
        flip = True
        for unit in ranked:
            unit_id = str(get_entity_id(unit) or "")
            if not unit_id:
                continue
            available = _reserve_status_choices(army, unit)
            primary = "reserves" if flip else "strategic_reserves"
            secondary = "strategic_reserves" if flip else "reserves"
            desired = None
            if primary in available:
                desired = primary
            elif secondary in available:
                desired = secondary
            if desired is None:
                continue
            trial = dict(mixed)
            trial[unit_id] = desired
            status = _reserves_validation(army, trial)
            if bool(status.get("valid", False)):
                mixed = trial
                flip = not flip
        return mixed
    return dict(forced_decisions or {})


def _reserves_option_payloads(
    army: object,
    *,
    player_id: str,
    preferred_decisions: Optional[dict[str, str]] = None,
    max_options: int = 6,
) -> list[dict[str, Any]]:
    roots = _reserve_group_roots(army)
    if not roots:
        return []
    forced = _forced_reserves_decisions(army)
    candidate_specs: list[tuple[str, str, dict[str, str]]] = []
    preferred_normalized = _normalize_reserves_decisions(army, preferred_decisions)
    if preferred_normalized:
        candidate_specs.append(("teacher", "Teacher allocation", preferred_normalized))
    candidate_specs.append(("forced_only", "Forced-only reserves", dict(forced)))
    candidate_specs.append(
        (
            "deep_strike_pressure",
            "Deep strike pressure",
            _reserves_strategy_decisions(
                army,
                strategy_id="deep_strike_pressure",
                forced_decisions=forced,
            ),
        )
    )
    candidate_specs.append(
        (
            "strategic_pressure",
            "Strategic pressure",
            _reserves_strategy_decisions(
                army,
                strategy_id="strategic_pressure",
                forced_decisions=forced,
            ),
        )
    )
    candidate_specs.append(
        (
            "balanced_mix",
            "Balanced reserves mix",
            _reserves_strategy_decisions(
                army,
                strategy_id="balanced_mix",
                forced_decisions=forced,
            ),
        )
    )

    entries: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    max_count = max(1, int(max_options))
    for strategy_id, label, decisions in candidate_specs:
        normalized = _normalize_reserves_decisions(army, decisions)
        validated = _reserves_validation(army, normalized)
        if not bool(validated.get("valid", False)):
            normalized = _reserves_apply_enforcement(army, normalized)
            validated = _reserves_validation(army, normalized)
        if not bool(validated.get("valid", False)):
            continue
        key = json.dumps(
            {k: normalized[k] for k in sorted(normalized.keys())},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        buckets = _reserves_buckets_from_decisions(normalized)
        reserve_units = _safe_int(validated.get("reserve_units"), default=0)
        reserve_points = _safe_int(validated.get("reserve_points"), default=0)
        strategic_points = _safe_int(validated.get("strategic_points"), default=0)
        limits = dict(validated.get("limits", {}) or {})
        max_units = max(1, _safe_int(limits.get("max_units"), default=max(1, len(roots))))
        max_points = max(1, _safe_int(limits.get("max_points"), default=1))
        max_strategic = max(1, _safe_int(limits.get("max_strategic_points"), default=1))
        payload = {
            "strategy_id": str(strategy_id),
            "unit_ids_by_bucket": buckets,
            "reserve_units": int(reserve_units),
            "reserve_points": int(reserve_points),
            "strategic_points": int(strategic_points),
            "reserve_unit_slots_ratio": float(round(float(reserve_units) / float(max_units), 6)),
            "reserve_points_ratio": float(round(float(reserve_points) / float(max_points), 6)),
            "strategic_points_ratio": float(round(float(strategic_points) / float(max_strategic), 6)),
        }
        entries.append({"label": str(label), "payload": payload})
        if len(entries) >= max_count:
            break
    return entries


def _no_legal_reserves_allocation_error(army: object) -> ValueError:
    forced = _forced_reserves_decisions(army)
    validated = _reserves_validation(army, forced)
    errors = [
        str(error or "").strip()
        for error in list(validated.get("errors", []) or [])
        if str(error or "").strip()
    ]
    detail = "; ".join(errors) if errors else "all generated reserve allocation candidates were illegal"
    army_label = str(getattr(army, "name", "") or getattr(army, "faction", "") or "army").strip()
    return ValueError(f"No legal reserves allocation options for {army_label}: {detail}")


def _normalized_zone_vertices(zone: dict) -> list[list[list[float]]]:
    mission_zones = list(zone.get("mission_zones", []) or [])
    normalized: list[list[list[float]]] = []
    for mission_zone in mission_zones:
        vertices: list[list[float]] = []
        for vertex in list(getattr(mission_zone, "vertices", []) or []):
            if not isinstance(vertex, (list, tuple)) or len(vertex) < 2:
                continue
            x = round(_safe_float(vertex[0]), 3)
            y = round(_safe_float(vertex[1]), 3)
            vertices.append([x, y])
        if vertices:
            normalized.append(vertices)
    normalized.sort(key=lambda verts: json.dumps(verts, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    return normalized


def _normalized_range_pair(value: object) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return []
    first = _safe_float(value[0])
    second = _safe_float(value[1])
    lo = round(min(first, second), 3)
    hi = round(max(first, second), 3)
    return [lo, hi]


def _polygon_area(vertices: list[list[float]]) -> float:
    if len(vertices) < 3:
        return 0.0
    area = 0.0
    for idx, current in enumerate(vertices):
        nxt = vertices[(idx + 1) % len(vertices)]
        area += _safe_float(current[0]) * _safe_float(nxt[1]) - _safe_float(nxt[0]) * _safe_float(current[1])
    return abs(area) * 0.5


def _deployment_zone_area_estimate(zone: dict) -> float:
    mission_verts = _normalized_zone_vertices(zone)
    if mission_verts:
        return float(sum(_polygon_area(vertices) for vertices in mission_verts))
    x_range = _normalized_range_pair(zone.get("x_range"))
    y_range = _normalized_range_pair(zone.get("y_range"))
    if len(x_range) == 2 and len(y_range) == 2:
        width = max(0.0, _safe_float(x_range[1]) - _safe_float(x_range[0]))
        depth = max(0.0, _safe_float(y_range[1]) - _safe_float(y_range[0]))
        return float(width * depth)
    return 0.0


def _deployment_zone_frontage_depth(zone: dict) -> tuple[float, float]:
    x_range = _normalized_range_pair(zone.get("x_range"))
    y_range = _normalized_range_pair(zone.get("y_range"))
    if len(x_range) == 2 and len(y_range) == 2:
        width = max(0.0, _safe_float(x_range[1]) - _safe_float(x_range[0]))
        depth = max(0.0, _safe_float(y_range[1]) - _safe_float(y_range[0]))
        return float(max(width, depth)), float(min(width, depth))
    mission_verts = _normalized_zone_vertices(zone)
    if not mission_verts:
        return 0.0, 0.0
    xs: list[float] = []
    ys: list[float] = []
    for polygon in mission_verts:
        for vertex in polygon:
            if len(vertex) < 2:
                continue
            xs.append(_safe_float(vertex[0]))
            ys.append(_safe_float(vertex[1]))
    if not xs or not ys:
        return 0.0, 0.0
    span_x = max(xs) - min(xs)
    span_y = max(ys) - min(ys)
    return float(max(span_x, span_y)), float(min(span_x, span_y))


def _default_deployment_intent(*, zone_type: str | None = None) -> dict[str, object]:
    zone = str(zone_type or "").strip().lower()
    score_weight = 0.28 if zone == "defender" else 0.32
    deny_weight = 0.24 if zone == "defender" else 0.18
    safety_weight = 0.33 if zone == "defender" else 0.27
    staging_weight = 0.16 if zone == "defender" else 0.24
    return {
        "desired_affordances": [
            "SAFE_STAGING",
            "SCREEN_DEPTH",
            "RESERVE_DENIAL",
            "COUNTERCHARGE_POCKET",
        ],
        "weights": {
            "score": score_weight,
            "deny": deny_weight,
            "safety": safety_weight,
            "staging": staging_weight,
            "reserve_deny": 0.22,
            "screen": 0.24,
            "countercharge": 0.18,
            "cover": 0.22,
            "los": 0.12,
            "aura": 0.12,
        },
    }


def canonical_deployment_zone_key(zone: dict) -> str:
    zone_data = dict(zone or {})
    payload = {
        "name": str(zone_data.get("name", "") or ""),
        "zone_type": str(zone_data.get("zone_type", "") or ""),
        "x_range": _normalized_range_pair(zone_data.get("x_range")),
        "y_range": _normalized_range_pair(zone_data.get("y_range")),
        "mission_zone_vertices": _normalized_zone_vertices(zone_data),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    return f"zone:{digest}"


def build_deployment_zone_request(
    game: object,
    player: object,
    available_zones: Iterable[dict] | None,
    *,
    deployment_intent: Optional[dict] = None,
    extra_context: Optional[dict] = None,
    queue_requests: bool = True,
) -> Optional[DecisionRequest]:
    zone_entries: list[tuple[str, str, str, int, dict, float, float, float, dict[str, object]]] = []
    for idx, zone in enumerate(list(available_zones or [])):
        if not isinstance(zone, dict):
            continue
        zone_data = dict(zone or {})
        zone_key = canonical_deployment_zone_key(zone_data)
        zone_type = str(zone_data.get("zone_type", "") or "")
        zone_name = str(zone_data.get("name", "") or "")
        zone_area = _deployment_zone_area_estimate(zone_data)
        zone_frontage, zone_depth = _deployment_zone_frontage_depth(zone_data)
        zone_affordances = compute_board_affordance_summary(game, deployment_zone=zone_data).to_dict()
        zone_entries.append(
            (
                zone_type,
                zone_name,
                zone_key,
                int(idx),
                zone_data,
                zone_area,
                zone_frontage,
                zone_depth,
                dict(zone_affordances or {}),
            )
        )
    if not zone_entries:
        return None

    zone_entries.sort(key=lambda entry: (entry[0], entry[1], entry[2], entry[3]))
    player_id = getattr(player, "id", None) if player is not None else None
    options: list[DecisionOption] = []
    choice_refs: list[dict[str, object]] = []
    for order_idx, (zone_type, zone_name, zone_key, source_index, _zone_data, zone_area, zone_frontage, zone_depth, zone_affordances) in enumerate(zone_entries):
        zone_choice_id = f"{zone_key}:{int(source_index)}"
        label = str(zone_name or "").strip()
        if not label:
            label = f"{zone_type.title()} Zone" if zone_type else f"Zone {int(order_idx) + 1}"
        options.append(
            DecisionOption.create(
                label,
                payload={
                    "zone_choice_id": zone_choice_id,
                    "zone_key": zone_key,
                    "zone_index": int(source_index),
                    "zone_type": zone_type,
                    "zone_name": zone_name,
                    "zone_area_estimate": float(round(zone_area, 6)),
                    "zone_frontage_estimate": float(round(zone_frontage, 6)),
                    "zone_depth_estimate": float(round(zone_depth, 6)),
                    "board_affordances": dict(zone_affordances or {}),
                    "action_id": f"{DECISION_CHOOSE_DEPLOYMENT_ZONE}:{str(player_id or '')}:{zone_choice_id}",
                },
            )
        )
        choice_refs.append(
            {
                "zone_choice_id": zone_choice_id,
                "zone_key": zone_key,
                "zone_index": int(source_index),
                "zone_type": zone_type,
                "zone_name": zone_name,
                "zone_area_estimate": float(round(zone_area, 6)),
                "zone_frontage_estimate": float(round(zone_frontage, 6)),
                "zone_depth_estimate": float(round(zone_depth, 6)),
                "board_affordances": dict(zone_affordances or {}),
            }
        )

    inferred_zone_type = ""
    zone_types = sorted({str(ref.get("zone_type", "") or "") for ref in choice_refs if str(ref.get("zone_type", "") or "")})
    if len(zone_types) == 1:
        inferred_zone_type = zone_types[0]
    context: dict[str, object] = {
        "selection_kind": "deployment_zone",
        "phase": "deploy_armies",
        "available_zone_choice_ids": [str(ref["zone_choice_id"]) for ref in choice_refs],
        "available_zone_keys": [str(ref["zone_key"]) for ref in choice_refs],
        "available_zone_choices": choice_refs,
        "deployment_intent": dict(deployment_intent or _default_deployment_intent(zone_type=inferred_zone_type)),
    }
    if isinstance(extra_context, dict):
        for key, value in dict(extra_context or {}).items():
            if key in context:
                continue
            context[str(key)] = value

    request = DecisionRequest.create(
        DECISION_CHOOSE_DEPLOYMENT_ZONE,
        "Choose deployment zone.",
        player_id=player_id,
        options=options,
        context=context,
    )
    if queue_requests and hasattr(game, "request_decision"):
        game.request_decision(request)
    return request


def build_select_next_deploy_unit_request(
    game: object,
    player: object,
    units: Iterable[object] | None,
    *,
    deployment_zone: Optional[dict] = None,
    already_deployed_units: Iterable[object] | None = None,
    deployment_intent: Optional[dict] = None,
    extra_context: Optional[dict] = None,
    queue_requests: bool = True,
) -> Optional[DecisionRequest]:
    unit_entries: list[tuple[tuple[object, ...], int, str, object]] = []
    for source_index, unit in enumerate(_iter_units(units)):
        unit_id = str(maybe_entity_id(unit) or "")
        if not unit_id:
            continue
        unit_entries.append((_unit_stable_sort_key(unit), int(source_index), unit_id, unit))
    if not unit_entries:
        return None

    unit_entries.sort(key=lambda entry: (entry[0], entry[1]))
    player_id = getattr(player, "id", None) if player is not None else None
    options: list[DecisionOption] = []
    for _sort_key, _source_index, unit_id, unit in unit_entries:
        unit_name = str(getattr(unit, "name", "Unit") or "Unit")
        options.append(
            DecisionOption.create(
                unit_name,
                payload={
                    "unit_id": unit_id,
                    "unit_name": unit_name,
                    "action_id": f"{DECISION_SELECT_NEXT_DEPLOY_UNIT}:{str(player_id or '')}:{unit_id}",
                },
            )
        )

    context: dict[str, object] = {
        "selection_kind": "deployment_next_unit",
        "phase": "deploy_armies",
        "unit_ids": [unit_id for _sort_key, _source_index, unit_id, _unit in unit_entries],
        "undeployed_count": int(len(unit_entries)),
    }
    deployed_ids: list[str] = []
    for unit in _iter_units(already_deployed_units):
        unit_id = str(maybe_entity_id(unit) or "")
        if unit_id:
            deployed_ids.append(unit_id)
    if deployed_ids:
        deployed_ids = sorted(set(deployed_ids))
        context["already_deployed_unit_ids"] = deployed_ids
        context["already_deployed_count"] = int(len(deployed_ids))
    if isinstance(deployment_zone, dict):
        zone_data = dict(deployment_zone or {})
        zone_type = str(zone_data.get("zone_type", "") or "")
        context["deployment_zone_key"] = canonical_deployment_zone_key(zone_data)
        context["deployment_zone_type"] = zone_type
        zone_name = str(zone_data.get("name", "") or "")
        if zone_name:
            context["deployment_zone_name"] = zone_name
        default_intent = _default_deployment_intent(zone_type=zone_type)
    else:
        default_intent = _default_deployment_intent()
    context["deployment_intent"] = dict(deployment_intent or default_intent)
    if isinstance(extra_context, dict):
        for key, value in dict(extra_context or {}).items():
            if key in context:
                continue
            context[str(key)] = value

    request = DecisionRequest.create(
        DECISION_SELECT_NEXT_DEPLOY_UNIT,
        "Select next unit to deploy.",
        player_id=player_id,
        options=options,
        context=context,
    )
    if queue_requests and hasattr(game, "request_decision"):
        game.request_decision(request)
    return request


def build_reserves_allocation_request(
    game: object,
    army: object,
    *,
    deployment_intent: Optional[dict] = None,
    extra_context: Optional[dict] = None,
    preferred_decisions: Optional[dict[str, str]] = None,
    max_options: int = 6,
    queue_requests: bool = True,
    strict_no_legal: bool = True,
) -> Optional[DecisionRequest]:
    if army is None:
        return None
    if not _reserve_group_roots(army):
        return None
    player = getattr(army, "player", None)
    player_id = getattr(player, "id", None) if player is not None else None
    player_key = str(player_id or "")
    option_entries = _reserves_option_payloads(
        army,
        player_id=player_key,
        preferred_decisions=preferred_decisions,
        max_options=max_options,
    )
    if not option_entries:
        if not bool(strict_no_legal):
            return None
        raise _no_legal_reserves_allocation_error(army)
    options: list[DecisionOption] = []
    option_refs: list[dict[str, object]] = []
    reserve_roots = _reserve_group_roots(army)
    reserve_root_order = {
        str(get_entity_id(unit) or ""): index
        for index, unit in enumerate(reserve_roots)
        if str(get_entity_id(unit) or "")
    }
    for idx, entry in enumerate(list(option_entries or [])):
        label = str(dict(entry or {}).get("label", "") or f"Allocation {int(idx) + 1}")
        payload = dict(dict(entry or {}).get("payload", {}) or {})
        buckets = dict(payload.get("unit_ids_by_bucket", {}) or {})
        buckets = {
            str(bucket): sorted(
                [str(unit_id) for unit_id in list(unit_ids or [])],
                key=lambda unit_id: (reserve_root_order.get(str(unit_id), 10**9), str(unit_id)),
            )
            for bucket, unit_ids in sorted(buckets.items())
        }
        payload["unit_ids_by_bucket"] = buckets
        bucket_key = json.dumps(
            {k: list(v or []) for k, v in sorted(buckets.items())},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        alloc_hash = hashlib.sha256(bucket_key.encode("utf-8")).hexdigest()[:12]
        allocation_id = f"reserve_alloc:{alloc_hash}"
        payload["allocation_id"] = allocation_id
        payload["action_id"] = f"{DECISION_DECLARE_RESERVES}:{player_key}:{allocation_id}"
        options.append(DecisionOption.create(label, payload=payload))
        option_refs.append(
            {
                "allocation_id": allocation_id,
                "label": label,
                "strategy_id": str(payload.get("strategy_id", "") or ""),
                "reserve_units": _safe_int(payload.get("reserve_units"), default=0),
                "reserve_points": _safe_int(payload.get("reserve_points"), default=0),
                "strategic_points": _safe_int(payload.get("strategic_points"), default=0),
                "reserve_unit_slots_ratio": float(payload.get("reserve_unit_slots_ratio", 0.0) or 0.0),
                "reserve_points_ratio": float(payload.get("reserve_points_ratio", 0.0) or 0.0),
                "strategic_points_ratio": float(payload.get("strategic_points_ratio", 0.0) or 0.0),
            }
        )
    zone_type = ""
    if isinstance(extra_context, dict):
        zone_type = str(dict(extra_context or {}).get("deployment_zone_type", "") or "")
    default_intent = _default_deployment_intent(zone_type=zone_type)
    root_unit_ids = [str(get_entity_id(unit) or "") for unit in reserve_roots]
    root_unit_ids = [unit_id for unit_id in root_unit_ids if unit_id]
    context: dict[str, object] = {
        "army_id": get_entity_id(army),
        "selection_kind": "reserves_allocation",
        "phase": "declare_battle_formations",
        "reserve_root_unit_ids": root_unit_ids,
        "reserve_allocation_option_ids": [str(ref.get("allocation_id", "") or "") for ref in option_refs],
        "reserve_allocation_options": option_refs,
        "deployment_intent": dict(deployment_intent or default_intent),
    }
    if isinstance(extra_context, dict):
        for key, value in dict(extra_context or {}).items():
            if key in context:
                continue
            context[str(key)] = value

    request = DecisionRequest.create(
        DECISION_DECLARE_RESERVES,
        "Allocate reserves for this army.",
        player_id=player_id,
        options=options,
        context=context,
    )
    if queue_requests and hasattr(game, "request_decision"):
        game.request_decision(request)
    return request


def build_hover_mode_requests(
    game: object,
    units: Iterable[object],
    *,
    queue_requests: bool = True,
) -> List[DecisionRequest]:
    all_units = _iter_units(units)
    requests: List[DecisionRequest] = []
    for unit in all_units:
        if bool(getattr(unit, "hover_declared", False)):
            continue
        has_hover = getattr(unit, "has_hover", None)
        if not callable(has_hover) or not has_hover():
            continue
        has_keyword = getattr(unit, "has_keyword", None)
        if not callable(has_keyword) or not has_keyword("Aircraft"):
            continue
        unit_id = get_entity_id(unit)
        player = _player_for_unit(unit)
        player_id = _player_id_for_unit(unit)
        player_name = str(getattr(player, "name", "Player") or "Player")
        unit_name = str(getattr(unit, "name", "Unit") or "Unit")
        message = (
            f"Enable Hover mode for {unit_name} ({player_name})?\n\n"
            "Hover removes the AIRCRAFT keyword and sets Move to 20\"."
        )
        options = [
            DecisionOption.create("Hover", payload={"choice": True, "unit_id": unit_id}),
            DecisionOption.create("Aircraft", payload={"choice": False, "unit_id": unit_id}),
        ]
        request = DecisionRequest.create(
            DECISION_CONFIRM_YES_NO,
            "Hover Mode",
            player_id=player_id,
            options=options,
            context={"ability": "hover_mode", "unit_id": unit_id, "message": message},
        )
        requests.append(request)
        if queue_requests and hasattr(game, "request_decision"):
            game.request_decision(request)
    return requests


def build_patrol_squad_requests(
    game: object,
    units: Iterable[object],
    *,
    queue_requests: bool = True,
) -> List[DecisionRequest]:
    all_units = _iter_units(units)
    requests: List[DecisionRequest] = []
    for unit in _unique_army_root_units(all_units):
        if unit is None:
            continue
        ability_key = ""
        ability_name = ""
        declared_flag = ""
        split_label = "Split"
        keep_label = "Keep Together"
        split_action = ""
        skip_action = ""
        if _unit_has_ability_name(unit, "PATROL SQUAD"):
            ability_key = "patrol_squad"
            ability_name = "Patrol Squad"
            declared_flag = "patrol_squad_declared"
            split_action = "split_patrol_squad"
            skip_action = "skip_patrol_squad"
        elif _unit_has_ability_name(unit, "Combat Squads"):
            ability_key = "combat_squads"
            ability_name = "Combat Squads"
            declared_flag = "combat_squads_declared"
            split_action = "split_combat_squads"
            skip_action = "skip_combat_squads"
        else:
            continue
        if bool(getattr(unit, "is_attached_leader", False)):
            continue
        if bool(getattr(unit, "is_joined_support", False)):
            continue
        if _unit_alive_model_count(unit) != 10:
            continue
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict) and bool(sr.get(declared_flag, False)):
            continue

        unit_id = str(get_entity_id(unit) or "")
        if not unit_id:
            continue
        player = _player_for_unit(unit)
        player_id = _player_id_for_unit(unit)
        player_name = str(getattr(player, "name", "Player") or "Player")
        unit_name = str(getattr(unit, "name", "Unit") or "Unit")

        token_abilities: list[str] = []
        if ability_key == "patrol_squad" and _unit_has_ability_name(unit, "Bomb Squigs"):
            token_abilities.append("Bomb Squigs")
        if ability_key == "patrol_squad" and _unit_has_ability_name(unit, "Distraction Grot"):
            token_abilities.append("Distraction Grot")
        token_note = ""
        if token_abilities:
            joined = " and ".join(token_abilities)
            token_note = (
                f"\n\nIf split, only one of the two new units can use {joined}; "
                "the first split unit is assigned those uses."
            )

        message = (
            f"Use {ability_name} for {unit_name} ({player_name})?\n\n"
            "Split into two units of five models each."
            f"{token_note}"
        )
        options = [
            DecisionOption.create(
                split_label,
                payload={"choice": True, "unit_id": unit_id, "action": split_action},
            ),
            DecisionOption.create(
                keep_label,
                payload={"choice": False, "unit_id": unit_id, "action": skip_action},
            ),
        ]
        request = DecisionRequest.create(
            DECISION_CONFIRM_YES_NO,
            ability_name,
            player_id=player_id,
            options=options,
            context={
                "ability": ability_key,
                "ability_name": ability_name,
                "unit_id": unit_id,
                "declared_flag": declared_flag,
                "message": message,
            },
        )
        requests.append(request)
        if queue_requests and hasattr(game, "request_decision"):
            game.request_decision(request)
    return requests


def build_rapid_drop_deployment_requests(
    game: object,
    units: Iterable[object],
    *,
    queue_requests: bool = True,
) -> List[DecisionRequest]:
    all_units = _iter_units(units)
    requests: List[DecisionRequest] = []
    if not all_units:
        return requests

    pending_army_ids: set[str] = set()
    queue = getattr(game, "decision_queue", None)
    if queue is not None and hasattr(queue, "list"):
        for req in list(queue.list() or []):
            if getattr(req, "decision_type", None) != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != "rapid_drop_deployment":
                continue
            army_id = str(ctx.get("army_id", "") or "")
            if army_id:
                pending_army_ids.add(army_id)

    units_by_army: dict[str, list[object]] = {}
    army_by_key: dict[str, object] = {}
    for unit in all_units:
        army = _army_for_unit(unit)
        if army is None:
            continue
        key = _army_key(army)
        if not key:
            continue
        units_by_army.setdefault(key, []).append(unit)
        army_by_key[key] = army

    for key in sorted(units_by_army.keys()):
        army = army_by_key[key]
        army_id = str(get_entity_id(army) or "")
        if army_id and army_id in pending_army_ids:
            continue
        mgr = getattr(army, "space_marines_detachments", None)
        if mgr is None or not bool(getattr(mgr, "is_orbital_assault_force", lambda: False)()):
            continue
        can_select = getattr(mgr, "can_select_rapid_drop_deployment", None)
        if not callable(can_select) or not bool(can_select(game=game)):
            continue
        get_eligible = getattr(mgr, "rapid_drop_deployment_eligible_units", None)
        if not callable(get_eligible):
            continue
        eligible = list(get_eligible(game=game) or [])
        eligible.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        if not eligible:
            continue
        get_cap = getattr(mgr, "rapid_drop_deployment_max_units", None)
        if not callable(get_cap):
            continue
        max_units = int(get_cap(game=game) or 0)
        if max_units <= 0:
            continue
        required = min(max_units, len(eligible))
        if required <= 0:
            continue
        options: List[DecisionOption] = []
        for combo in combinations(eligible, required):
            selected_ids = [str(get_entity_id(unit) or "") for unit in list(combo or []) if str(get_entity_id(unit) or "")]
            if len(selected_ids) != required:
                continue
            names = [str(getattr(unit, "name", "Unit") or "Unit") for unit in list(combo or [])]
            label = ", ".join(names)
            options.append(
                DecisionOption.create(
                    label,
                    payload={
                        "selected_unit_ids": list(selected_ids),
                        "selection_kind": "rapid_drop_units",
                        "required_count": int(required),
                        "army_id": army_id,
                    },
                )
            )
        if not options:
            continue
        player = getattr(army, "player", None)
        player_id = getattr(player, "id", None) if player is not None else None
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"Rapid-drop Deployment: select {required} unit(s) to gain Deep Strike.",
            player_id=player_id,
            options=options,
            context={
                "ability": "rapid_drop_deployment",
                "ability_name": "Rapid-drop Deployment",
                "army_id": army_id,
                "required_count": int(required),
                "candidate_unit_ids": [str(get_entity_id(unit) or "") for unit in list(eligible or []) if str(get_entity_id(unit) or "")],
            },
        )
        requests.append(request)
        if queue_requests and hasattr(game, "request_decision"):
            game.request_decision(request)
            if army_id:
                pending_army_ids.add(army_id)

    return requests


def build_risen_rubricae_requests(
    game: object,
    units: Iterable[object],
    *,
    queue_requests: bool = True,
) -> List[DecisionRequest]:
    all_units = _iter_units(units)
    requests: List[DecisionRequest] = []
    if not all_units:
        return requests

    pending_by_source: set[str] = set()
    queue = getattr(game, "decision_queue", None)
    if queue is not None and hasattr(queue, "list"):
        for req in list(queue.list() or []):
            if getattr(req, "decision_type", None) != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != "risen_rubricae":
                continue
            source_id = str(ctx.get("source_unit_id", "") or "")
            if source_id:
                pending_by_source.add(source_id)

    source_units = [
        u for u in all_units
        if _unit_has_enhancement(
            u,
            flag_key="enhancement_risen_rubricae",
            enhancement_id="000010205002",
            enhancement_name="Risen Rubricae",
        )
    ]
    source_units.sort(key=lambda u: str(get_entity_id(u) or ""))

    for source_unit in source_units:
        source_id = str(get_entity_id(source_unit) or "")
        if not source_id:
            continue
        if source_id in pending_by_source:
            continue
        if _unit_has_special_rule_flag(source_unit, "enhancement_risen_rubricae_used"):
            continue

        try:
            source_army = source_unit.get_parent_army()
        except Exception:
            source_army = None
        if source_army is None:
            continue
        mgr = getattr(source_army, "thousand_sons_detachments", None)
        if mgr is None or not bool(getattr(mgr, "is_rubricae_phalanx", lambda: False)()):
            continue

        army_units = [
            u for u in all_units
            if getattr(u, "get_parent_army", lambda: None)() is source_army
        ]
        roots = _unique_army_root_units(army_units)
        rubricae = [u for u in roots if _unit_is_rubricae(u)]
        battleline = [u for u in rubricae if _unit_is_battleline(u)]
        other = [u for u in rubricae if not _unit_is_battleline(u)]
        if len(battleline) < 2 and not other:
            continue

        options: List[DecisionOption] = []
        for first, second in combinations(battleline, 2):
            first_id = str(get_entity_id(first) or "")
            second_id = str(get_entity_id(second) or "")
            if not first_id or not second_id:
                continue
            if first_id > second_id:
                first, second = second, first
                first_id, second_id = second_id, first_id
            label = f"{getattr(first, 'name', 'Unit')} + {getattr(second, 'name', 'Unit')}"
            options.append(
                DecisionOption.create(
                    label,
                    payload={
                        "source_unit_id": source_id,
                        "selected_unit_ids": [first_id, second_id],
                        "selection_kind": "two_battleline",
                    },
                )
            )
        for unit in other:
            unit_id = str(get_entity_id(unit) or "")
            if not unit_id:
                continue
            options.append(
                DecisionOption.create(
                    str(getattr(unit, "name", "Unit") or "Unit"),
                    payload={
                        "source_unit_id": source_id,
                        "selected_unit_ids": [unit_id],
                        "selection_kind": "one_other",
                    },
                )
            )

        if not options:
            continue
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Risen Rubricae: select two Rubricae Battleline units or one other Rubricae unit.",
            player_id=_player_id_for_unit(source_unit),
            options=options,
            context={
                "ability": "risen_rubricae",
                "ability_name": "Risen Rubricae",
                "source_unit_id": source_id,
                "enhancement_id": "000010205002",
            },
        )
        requests.append(request)
        if queue_requests and hasattr(game, "request_decision"):
            game.request_decision(request)
            pending_by_source.add(source_id)

    return requests


def build_ethereal_pathway_requests(
    game: object,
    units: Iterable[object],
    *,
    queue_requests: bool = True,
) -> List[DecisionRequest]:
    all_units = _iter_units(units)
    requests: List[DecisionRequest] = []
    if not all_units:
        return requests

    pending_by_source: set[str] = set()
    queue = getattr(game, "decision_queue", None)
    if queue is not None and hasattr(queue, "list"):
        for req in list(queue.list() or []):
            if getattr(req, "decision_type", None) != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != "ethereal_pathway":
                continue
            source_id = str(ctx.get("source_unit_id", "") or "")
            if source_id:
                pending_by_source.add(source_id)

    source_units = [
        u for u in all_units
        if _unit_has_enhancement(
            u,
            flag_key="enhancement_ethereal_pathway",
            enhancement_id="000009911003",
            enhancement_name="Ethereal Pathway",
        )
    ]
    source_units.sort(key=lambda u: str(get_entity_id(u) or ""))

    for source_unit in source_units:
        source_id = str(get_entity_id(source_unit) or "")
        if not source_id:
            continue
        if source_id in pending_by_source:
            continue
        if _unit_has_special_rule_flag(source_unit, "enhancement_ethereal_pathway_used"):
            continue

        try:
            source_army = source_unit.get_parent_army()
        except Exception:
            source_army = None
        if source_army is None:
            continue
        mgr = getattr(source_army, "aeldari_detachments", None)
        if mgr is None or not bool(getattr(mgr, "is_guardian_battlehost", lambda: False)()):
            continue

        army_units = [
            u for u in all_units
            if getattr(u, "get_parent_army", lambda: None)() is source_army
        ]
        roots = _unique_army_root_units(army_units)
        guardians = [u for u in roots if _unit_is_guardians(u)]
        guardians.sort(key=lambda u: str(get_entity_id(u) or ""))
        if not guardians:
            continue

        options: List[DecisionOption] = [
            DecisionOption.create(
                "None",
                payload={
                    "action": "skip",
                    "source_unit_id": source_id,
                    "selected_unit_ids": [],
                    "selection_kind": "none",
                },
            )
        ]
        for unit in guardians:
            unit_id = str(get_entity_id(unit) or "")
            if not unit_id:
                continue
            options.append(
                DecisionOption.create(
                    str(getattr(unit, "name", "Unit") or "Unit"),
                    payload={
                        "source_unit_id": source_id,
                        "selected_unit_ids": [unit_id],
                        "selection_kind": "one_guardians_unit",
                    },
                )
            )
        for first, second in combinations(guardians, 2):
            first_id = str(get_entity_id(first) or "")
            second_id = str(get_entity_id(second) or "")
            if not first_id or not second_id:
                continue
            label = f"{getattr(first, 'name', 'Unit')} + {getattr(second, 'name', 'Unit')}"
            options.append(
                DecisionOption.create(
                    label,
                    payload={
                        "source_unit_id": source_id,
                        "selected_unit_ids": [first_id, second_id],
                        "selection_kind": "two_guardians_units",
                    },
                )
            )

        if len(options) <= 1:
            continue
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Ethereal Pathway: select up to two Guardians units to gain Infiltrators.",
            player_id=_player_id_for_unit(source_unit),
            options=options,
            context={
                "ability": "ethereal_pathway",
                "ability_name": "Ethereal Pathway",
                "source_unit_id": source_id,
                "enhancement_id": "000009911003",
            },
        )
        requests.append(request)
        if queue_requests and hasattr(game, "request_decision"):
            game.request_decision(request)
            pending_by_source.add(source_id)

    return requests


def build_army_selected_leading_infiltrators_requests(
    game: object,
    units: Iterable[object],
    *,
    queue_requests: bool = True,
) -> List[DecisionRequest]:
    all_units = _iter_units(units)
    requests: List[DecisionRequest] = []
    if not all_units:
        return requests

    pending_army_ids: set[str] = set()
    queue = getattr(game, "decision_queue", None)
    if queue is not None and hasattr(queue, "list"):
        for req in list(queue.list() or []):
            if getattr(req, "decision_type", None) != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != "army_selected_leading_infiltrators_declare":
                continue
            army_id = str(ctx.get("army_id", "") or "")
            if army_id:
                pending_army_ids.add(army_id)

    units_by_army: dict[str, list[object]] = {}
    army_by_key: dict[str, object] = {}
    for unit in all_units:
        army = _army_for_unit(unit)
        if army is None:
            continue
        key = _army_key(army)
        if not key:
            continue
        units_by_army.setdefault(key, []).append(unit)
        army_by_key[key] = army

    for key in sorted(units_by_army.keys()):
        army = army_by_key[key]
        army_id = str(get_entity_id(army) or "")
        if army_id and army_id in pending_army_ids:
            continue

        roots = _unique_army_root_units(units_by_army[key])
        source_units = [
            unit
            for unit in roots
            if _unit_has_declare_selected_leading_infiltrators_ability(unit)
        ]
        source_units.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        if not source_units:
            continue

        already_selected = False
        for unit in source_units:
            sr = getattr(unit, "special_rules", None)
            if isinstance(sr, dict) and bool(sr.get("declare_battle_formations_selected_leading_infiltrators")):
                already_selected = True
                break
        if already_selected:
            continue

        candidate_unit_ids: list[str] = []
        options: List[DecisionOption] = []
        for unit in source_units:
            unit_id = str(get_entity_id(unit) or "")
            if not unit_id:
                continue
            candidate_unit_ids.append(unit_id)
            options.append(
                DecisionOption.create(
                    str(getattr(unit, "name", "Unit") or "Unit"),
                    payload={
                        "selected_unit_id": unit_id,
                        "source_unit_id": unit_id,
                        "selection_kind": "declare_battle_formations_selected_leading_infiltrators",
                    },
                )
            )

        if not options:
            continue

        ability_name = ""
        for unit in source_units:
            ability_name = _unit_declare_selected_leading_infiltrators_ability_name(unit)
            if ability_name:
                break
        if not ability_name:
            ability_name = "Declare Battle Formations Selection"

        player = getattr(army, "player", None)
        player_id = getattr(player, "id", None) if player is not None else None
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select one of your units with this ability.",
            player_id=player_id,
            options=options,
            context={
                "ability": "army_selected_leading_infiltrators_declare",
                "ability_name": ability_name,
                "phase": "Declare Battle Formations step",
                "army_id": army_id,
                "candidate_unit_ids": list(candidate_unit_ids),
                "optional": False,
                "instruction": "Select one unit with this ability.",
            },
        )
        requests.append(request)
        if queue_requests and hasattr(game, "request_decision"):
            game.request_decision(request)
            if army_id:
                pending_army_ids.add(army_id)

    return requests


def build_declare_selected_units_gain_scouts_requests(
    game: object,
    units: Iterable[object],
    *,
    queue_requests: bool = True,
) -> List[DecisionRequest]:
    all_units = _iter_units(units)
    requests: List[DecisionRequest] = []
    if not all_units:
        return requests

    pending_by_source: set[str] = set()
    queue = getattr(game, "decision_queue", None)
    if queue is not None and hasattr(queue, "list"):
        for req in list(queue.list() or []):
            if getattr(req, "decision_type", None) != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != "declare_selected_unit_gain_scouts":
                continue
            source_id = str(ctx.get("source_unit_id", "") or "")
            if source_id:
                pending_by_source.add(source_id)

    units_by_army: dict[str, list[object]] = {}
    army_by_key: dict[str, object] = {}
    for unit in all_units:
        army = _army_for_unit(unit)
        if army is None:
            continue
        key = _army_key(army)
        if not key:
            continue
        units_by_army.setdefault(key, []).append(unit)
        army_by_key[key] = army

    for key in sorted(units_by_army.keys()):
        army = army_by_key[key]
        roots = _unique_army_root_units(units_by_army[key])
        roots.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        if not roots:
            continue

        for source_unit in roots:
            source_id = str(get_entity_id(source_unit) or "")
            if not source_id or source_id in pending_by_source:
                continue

            source_sr = getattr(source_unit, "special_rules", None)
            if isinstance(source_sr, dict) and bool(
                source_sr.get("declare_selected_unit_gain_scouts_resolved", False)
            ):
                continue

            specs = _unit_declare_selected_units_gain_scouts_specs(source_unit)
            if not specs:
                continue

            spec = dict(specs[0] or {})
            keyword_phrase = str(spec.get("keywords", "") or "").strip().upper()
            if not keyword_phrase:
                continue
            try:
                scout_distance = int(spec.get("scout_distance", 0) or 0)
            except (TypeError, ValueError):
                scout_distance = 0
            if scout_distance <= 0:
                continue

            matcher = getattr(source_unit, "_unit_matches_keyword_phrase", None)
            candidate_roots: list[object] = []
            for root in roots:
                if root is None:
                    continue
                if not callable(matcher):
                    continue
                try:
                    if not bool(matcher(root, keyword_phrase, use_effective=False)):
                        continue
                except Exception:
                    continue
                candidate_roots.append(root)

            candidate_roots.sort(key=lambda unit: str(get_entity_id(unit) or ""))
            candidate_ids = [str(get_entity_id(unit) or "") for unit in list(candidate_roots or []) if str(get_entity_id(unit) or "")]
            if not candidate_ids:
                continue

            ability_name = str(spec.get("ability_name", "") or "Declare Battle Formations Selection").strip()
            options: List[DecisionOption] = [
                DecisionOption.create(
                    "None",
                    payload={
                        "action": "skip",
                        "source_unit_id": source_id,
                        "selected_unit_id": "",
                        "selection_kind": "declare_selected_unit_gain_scouts_none",
                    },
                )
            ]
            for root in candidate_roots:
                target_id = str(get_entity_id(root) or "")
                if not target_id:
                    continue
                options.append(
                    DecisionOption.create(
                        str(getattr(root, "name", "Unit") or "Unit"),
                        payload={
                            "source_unit_id": source_id,
                            "selected_unit_id": target_id,
                            "selection_kind": "declare_selected_unit_gain_scouts",
                        },
                    )
                )

            if len(options) <= 1:
                continue

            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select one {keyword_phrase} unit to gain Scouts {int(scout_distance)}\" (or None).",
                player_id=_player_id_for_unit(source_unit),
                options=options,
                context={
                    "ability": "declare_selected_unit_gain_scouts",
                    "ability_name": ability_name,
                    "phase": "Declare Battle Formations step",
                    "source_unit_id": source_id,
                    "candidate_unit_ids": list(candidate_ids),
                    "unit_keyword_phrase": keyword_phrase,
                    "scout_distance": int(scout_distance),
                    "optional": True,
                    "instruction": f"Select up to one {keyword_phrase} unit to gain Scouts {int(scout_distance)}\".",
                },
            )
            requests.append(request)
            if queue_requests and hasattr(game, "request_decision"):
                game.request_decision(request)
                pending_by_source.add(source_id)

    return requests


def build_declare_selected_units_gain_deep_strike_requests(
    game: object,
    units: Iterable[object],
    *,
    queue_requests: bool = True,
) -> List[DecisionRequest]:
    all_units = _iter_units(units)
    requests: List[DecisionRequest] = []
    if not all_units:
        return requests

    pending_by_source: set[str] = set()
    queue = getattr(game, "decision_queue", None)
    if queue is not None and hasattr(queue, "list"):
        for req in list(queue.list() or []):
            if getattr(req, "decision_type", None) != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != "declare_selected_unit_gain_deep_strike":
                continue
            source_id = str(ctx.get("source_unit_id", "") or "")
            if source_id:
                pending_by_source.add(source_id)

    units_by_army: dict[str, list[object]] = {}
    army_by_key: dict[str, object] = {}
    for unit in all_units:
        army = _army_for_unit(unit)
        if army is None:
            continue
        key = _army_key(army)
        if not key:
            continue
        units_by_army.setdefault(key, []).append(unit)
        army_by_key[key] = army

    for key in sorted(units_by_army.keys()):
        army = army_by_key[key]
        roots = _unique_army_root_units(units_by_army[key])
        roots.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        if not roots:
            continue

        for source_unit in roots:
            source_id = str(get_entity_id(source_unit) or "")
            if not source_id or source_id in pending_by_source:
                continue

            source_sr = getattr(source_unit, "special_rules", None)
            if isinstance(source_sr, dict) and bool(
                source_sr.get("declare_selected_unit_gain_deep_strike_resolved", False)
            ):
                continue

            specs = _unit_declare_selected_units_gain_deep_strike_specs(source_unit)
            if not specs:
                continue

            spec = dict(specs[0] or {})
            selector_label = str(spec.get("selector_label", "") or spec.get("keyword_phrase", "") or "").strip().upper()
            if not selector_label:
                continue
            matcher = getattr(source_unit, "_unit_matches_declare_battle_formations_selector_spec", None)
            candidate_roots: list[object] = []
            for root in roots:
                if root is None or not callable(matcher):
                    continue
                try:
                    if not bool(matcher(root, spec)):
                        continue
                except Exception:
                    continue
                candidate_roots.append(root)

            candidate_roots.sort(key=lambda unit: str(get_entity_id(unit) or ""))
            candidate_ids = [
                str(get_entity_id(unit) or "")
                for unit in list(candidate_roots or [])
                if str(get_entity_id(unit) or "")
            ]
            if not candidate_ids:
                continue

            ability_name = str(spec.get("ability_name", "") or "Declare Battle Formations Selection").strip()
            options: List[DecisionOption] = []
            for root in candidate_roots:
                target_id = str(get_entity_id(root) or "")
                if not target_id:
                    continue
                options.append(
                    DecisionOption.create(
                        str(getattr(root, "name", "Unit") or "Unit"),
                        payload={
                            "source_unit_id": source_id,
                            "selected_unit_id": target_id,
                            "selection_kind": "declare_selected_unit_gain_deep_strike",
                        },
                    )
                )

            if not options:
                continue

            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select one {selector_label} unit to gain Deep Strike.",
                player_id=_player_id_for_unit(source_unit),
                options=options,
                context={
                    "ability": "declare_selected_unit_gain_deep_strike",
                    "ability_name": ability_name,
                    "phase": "Declare Battle Formations step",
                    "source_unit_id": source_id,
                    "candidate_unit_ids": list(candidate_ids),
                    "selector_label": selector_label,
                    "unit_keyword_phrase": str(spec.get("keyword_phrase", "") or "").strip().upper(),
                    "required_keyword_phrase": str(spec.get("required_keyword_phrase", "") or "").strip().upper(),
                    "any_keywords": [
                        str(keyword or "").strip().upper()
                        for keyword in list(spec.get("any_keywords", ()) or [])
                        if str(keyword or "").strip()
                    ],
                    "optional": False,
                    "instruction": f"Select one {selector_label} unit to gain Deep Strike.",
                },
            )
            requests.append(request)
            if queue_requests and hasattr(game, "request_decision"):
                game.request_decision(request)
                pending_by_source.add(source_id)

    return requests


def _unit_anchor_location(unit: object) -> tuple[float, float, float] | None:
    if unit is None:
        return None
    for model in list(getattr(unit, "models", []) or []):
        alive = getattr(model, "is_alive", True)
        if callable(alive):
            alive = bool(alive())
        if not bool(alive):
            continue
        get_location = getattr(model, "get_location", None)
        if not callable(get_location):
            continue
        location = get_location()
        if not isinstance(location, (list, tuple)) or len(location) < 2:
            continue
        x = _safe_float(location[0])
        y = _safe_float(location[1])
        z = _safe_float(location[2]) if len(location) > 2 else 0.0
        return (x, y, z)
    return None


def _unit_scout_distance(unit: object) -> float:
    if unit is None:
        return 0.0
    has_scout_fn = getattr(unit, "has_scout", None)
    if callable(has_scout_fn):
        value = has_scout_fn()
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return float(_safe_float(value[1]) if bool(value[0]) else 0.0)
        if bool(value):
            return float(_safe_float(getattr(unit, "scout_move_distance", 0.0)))
    return float(_safe_float(getattr(unit, "scout_move_distance", 0.0)))


def _board_dimensions_for_scout(game: object) -> tuple[float, float]:
    game_map = getattr(game, "map", None)
    width = _safe_float(getattr(game_map, "width", 60.0))
    height = _safe_float(getattr(game_map, "height", 44.0))
    return (max(1.0, width), max(1.0, height))


def _normalized_direction(dx: float, dy: float) -> tuple[float, float]:
    magnitude = float((float(dx) * float(dx) + float(dy) * float(dy)) ** 0.5)
    if magnitude <= 1e-9:
        return (0.0, 0.0)
    return (float(dx) / magnitude, float(dy) / magnitude)


def _scout_candidate_destinations(
    game: object,
    unit: object,
    *,
    scout_distance: float,
) -> list[tuple[float, float, float]]:
    origin = _unit_anchor_location(unit)
    if origin is None:
        return []
    ox, oy, oz = origin
    width, height = _board_dimensions_for_scout(game)
    center_x = float(width) * 0.5
    center_y = float(height) * 0.5
    forward_x, forward_y = _normalized_direction(center_x - ox, center_y - oy)
    if abs(forward_x) <= 1e-9 and abs(forward_y) <= 1e-9:
        forward_x, forward_y = (0.0, 1.0)
    side_x, side_y = (-forward_y, forward_x)

    primary = max(1.0, float(scout_distance) * 0.9)
    secondary = max(1.0, float(scout_distance) * 0.5)
    radii = [primary, secondary]
    directions = [
        (forward_x, forward_y),
        (forward_x + side_x * 0.65, forward_y + side_y * 0.65),
        (forward_x - side_x * 0.65, forward_y - side_y * 0.65),
        (side_x, side_y),
        (-side_x, -side_y),
        (-forward_x + side_x * 0.4, -forward_y + side_y * 0.4),
        (-forward_x - side_x * 0.4, -forward_y - side_y * 0.4),
        (-forward_x, -forward_y),
    ]
    destinations: list[tuple[float, float, float]] = []
    seen: set[tuple[float, float, float]] = set()
    for radius in radii:
        for dx, dy in directions:
            ndx, ndy = _normalized_direction(dx, dy)
            tx = _clamp(ox + ndx * float(radius), low=0.0, high=width)
            ty = _clamp(oy + ndy * float(radius), low=0.0, high=height)
            key = (round(float(tx), 3), round(float(ty), 3), round(float(oz), 3))
            if key in seen:
                continue
            seen.add(key)
            destinations.append((float(tx), float(ty), float(oz)))
            if len(destinations) >= 8:
                return destinations
    return destinations


def _scout_model_positions_for_destination(
    unit: object,
    destination: tuple[float, float, float],
) -> list[dict[str, object]]:
    origin = _unit_anchor_location(unit)
    if origin is None:
        return []
    dx = float(destination[0]) - float(origin[0])
    dy = float(destination[1]) - float(origin[1])
    dz = float(destination[2]) - float(origin[2])
    positions: list[dict[str, object]] = []
    for model in list(getattr(unit, "models", []) or []):
        model_id = str(get_entity_id(model) or "")
        if not model_id:
            continue
        get_location = getattr(model, "get_location", None)
        if not callable(get_location):
            continue
        location = get_location()
        if not isinstance(location, (list, tuple)) or len(location) < 2:
            continue
        x = _safe_float(location[0]) + dx
        y = _safe_float(location[1]) + dy
        z = (_safe_float(location[2]) if len(location) > 2 else 0.0) + dz
        facing = (
            _safe_float(location[3])
            if len(location) > 3
            else _safe_float(getattr(getattr(model, "model_base", None), "facing", 0.0))
        )
        positions.append(
            {
                "model_id": model_id,
                "position": [float(x), float(y), float(z)],
                "facing": float(facing),
            }
        )
    return positions


def build_scout_move_request(game: object, unit: object) -> Optional[DecisionRequest]:
    if unit is None:
        return None
    unit_id = get_entity_id(unit)
    player_id = _player_id_for_unit(unit)
    player_key = str(player_id or "")
    scout_distance = max(0.0, _unit_scout_distance(unit))
    destinations = _scout_candidate_destinations(
        game,
        unit,
        scout_distance=scout_distance,
    )

    options: list[DecisionOption] = []
    for idx, destination in enumerate(list(destinations or [])):
        x, y, z = destination
        model_positions = _scout_model_positions_for_destination(unit, destination)
        options.append(
            DecisionOption.create(
                f"Scout to ({float(x):.1f}, {float(y):.1f})",
                payload={
                    "unit_id": unit_id,
                    "action": "scout",
                    "destination": [float(x), float(y), float(z)],
                    "model_positions": model_positions,
                    "scout_candidate_index": int(idx),
                    "action_id": f"{DECISION_SCOUT_MOVE}:{player_key}:{unit_id}:scout:{int(idx):02d}",
                },
            )
        )
    options.append(
        DecisionOption.create(
            "Skip scout move",
            payload={
                "unit_id": unit_id,
                "action": "skip",
                "action_id": f"{DECISION_SCOUT_MOVE}:{player_key}:{unit_id}:skip",
            },
        )
    )

    deployment_zone = deployment_zone_from_player(game, player_key) if player_key else None
    zone_type = str(dict(deployment_zone or {}).get("zone_type", "") or "")
    context: dict[str, object] = {
        "unit_id": unit_id,
        "selection_kind": "scout_move",
        "phase": "resolve_prebattle_rules",
        "scout_distance": float(round(scout_distance, 6)),
        "deployment_intent": dict(_default_deployment_intent(zone_type=zone_type)),
    }
    origin = _unit_anchor_location(unit)
    if origin is not None:
        context["scout_origin"] = [float(origin[0]), float(origin[1]), float(origin[2])]
    if isinstance(deployment_zone, dict):
        zone_data = dict(deployment_zone or {})
        context["deployment_zone_key"] = canonical_deployment_zone_key(zone_data)
        context["deployment_zone_type"] = zone_type
        zone_name = str(zone_data.get("name", "") or "")
        if zone_name:
            context["deployment_zone_name"] = zone_name
        affordance_summary = compute_board_affordance_summary(game, deployment_zone=zone_data)
        context["board_affordances"] = affordance_summary.to_dict()
    prompt = f"Scout move for {getattr(unit, 'name', 'Unit')}"
    request = DecisionRequest.create(
        DECISION_SCOUT_MOVE,
        prompt,
        player_id=player_id,
        options=options,
        context=context,
    )
    if hasattr(game, "request_decision"):
        game.request_decision(request)
    return request


def build_player_color_selection_requests(
    game: object,
    players: Iterable[object],
    *,
    queue_requests: bool = True,
) -> List[DecisionRequest]:
    all_players = _iter_players(players)
    requests: List[DecisionRequest] = []
    if not all_players:
        return requests

    pending_player_ids: set[str] = set()
    queue = getattr(game, "decision_queue", None)
    if queue is not None and hasattr(queue, "list"):
        for req in list(queue.list() or []):
            if getattr(req, "decision_type", None) != DECISION_CHOOSE_PLAYER_COLOR:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            player_id = str(ctx.get("player_id", "") or "")
            if player_id:
                pending_player_ids.add(player_id)

    for player in sorted(all_players, key=_player_sort_key):
        player_id = str(get_entity_id(player) or "")
        if not player_id or player_id in pending_player_ids:
            continue
        if bool(getattr(player, "ui_color_selected", False)):
            continue
        options = _player_color_options(player)
        if not options:
            continue
        request = DecisionRequest.create(
            DECISION_CHOOSE_PLAYER_COLOR,
            f"Select color for {str(getattr(player, 'name', 'Player') or 'Player')}.",
            player_id=player_id,
            options=options,
            context={
                "player_id": player_id,
                "selection_kind": "player_color",
                "hue_step_degrees": PLAYER_COLOR_HUE_STEP_DEGREES,
            },
        )
        requests.append(request)
        if queue_requests and hasattr(game, "request_decision"):
            game.request_decision(request)
            pending_player_ids.add(player_id)
    return requests
