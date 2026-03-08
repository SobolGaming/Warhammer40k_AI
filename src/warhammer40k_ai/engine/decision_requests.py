from __future__ import annotations

import colorsys
import hashlib
from itertools import combinations
import json
import re
from typing import Iterable, List, Optional

from .decisions import DecisionOption, DecisionRequest
from .decision_kinds import (
    DECISION_ATTACH_LEADER,
    DECISION_ATTACH_SUPPORT_ARTILLERY,
    DECISION_ASSIGN_TRANSPORT,
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_CHOOSE_PLAYER_COLOR,
    DECISION_CHOOSE_QUARRY,
    DECISION_CONFIRM_YES_NO,
    DECISION_DECLARE_RESERVES,
    DECISION_SELECT_NEXT_DEPLOY_UNIT,
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
    all_units = _iter_units(units)
    leaders = [u for u in all_units if bool(getattr(u, "is_leader", False))]
    bodyguards = [
        u for u in all_units
        if not bool(getattr(u, "is_leader", False))
        and not bool(getattr(u, "is_joined_support", False))
    ]
    requests: List[DecisionRequest] = []
    for leader in leaders:
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
    all_units = _iter_units(units)
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
    all_units = _iter_units(units)
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
    zone_entries: list[tuple[str, str, str, int, dict]] = []
    for idx, zone in enumerate(list(available_zones or [])):
        if not isinstance(zone, dict):
            continue
        zone_data = dict(zone or {})
        zone_key = canonical_deployment_zone_key(zone_data)
        zone_type = str(zone_data.get("zone_type", "") or "")
        zone_name = str(zone_data.get("name", "") or "")
        zone_area = _deployment_zone_area_estimate(zone_data)
        zone_frontage, zone_depth = _deployment_zone_frontage_depth(zone_data)
        zone_entries.append((zone_type, zone_name, zone_key, int(idx), zone_data, zone_area, zone_frontage, zone_depth))
    if not zone_entries:
        return None

    zone_entries.sort(key=lambda entry: (entry[0], entry[1], entry[2], entry[3]))
    player_id = getattr(player, "id", None) if player is not None else None
    options: list[DecisionOption] = []
    choice_refs: list[dict[str, object]] = []
    for order_idx, (zone_type, zone_name, zone_key, source_index, _zone_data, zone_area, zone_frontage, zone_depth) in enumerate(zone_entries):
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
    unit_entries: list[tuple[str, object]] = []
    for unit in _iter_units(units):
        unit_id = str(maybe_entity_id(unit) or "")
        if not unit_id:
            continue
        unit_entries.append((unit_id, unit))
    if not unit_entries:
        return None

    unit_entries.sort(key=lambda entry: entry[0])
    player_id = getattr(player, "id", None) if player is not None else None
    options: list[DecisionOption] = []
    for unit_id, unit in unit_entries:
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
        "unit_ids": [unit_id for unit_id, _unit in unit_entries],
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
    queue_requests: bool = True,
) -> Optional[DecisionRequest]:
    if army is None:
        return None
    player = getattr(army, "player", None)
    player_id = getattr(player, "id", None) if player is not None else None
    option = DecisionOption.create("Confirm reserves")
    request = DecisionRequest.create(
        DECISION_DECLARE_RESERVES,
        "Allocate reserves for this army.",
        player_id=player_id,
        options=[option],
        context={"army_id": get_entity_id(army)},
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
        if not _unit_has_ability_name(unit, "PATROL SQUAD"):
            continue
        if bool(getattr(unit, "is_attached_leader", False)):
            continue
        if bool(getattr(unit, "is_joined_support", False)):
            continue
        if _unit_alive_model_count(unit) != 10:
            continue
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict) and bool(sr.get("patrol_squad_declared", False)):
            continue

        unit_id = str(get_entity_id(unit) or "")
        if not unit_id:
            continue
        player = _player_for_unit(unit)
        player_id = _player_id_for_unit(unit)
        player_name = str(getattr(player, "name", "Player") or "Player")
        unit_name = str(getattr(unit, "name", "Unit") or "Unit")

        token_abilities: list[str] = []
        if _unit_has_ability_name(unit, "Bomb Squigs"):
            token_abilities.append("Bomb Squigs")
        if _unit_has_ability_name(unit, "Distraction Grot"):
            token_abilities.append("Distraction Grot")
        token_note = ""
        if token_abilities:
            joined = " and ".join(token_abilities)
            token_note = (
                f"\n\nIf split, only one of the two new units can use {joined}; "
                "the first split unit is assigned those uses."
            )

        message = (
            f"Use Patrol Squad for {unit_name} ({player_name})?\n\n"
            "Split into two units of five models each."
            f"{token_note}"
        )
        options = [
            DecisionOption.create(
                "Split",
                payload={"choice": True, "unit_id": unit_id, "action": "split_patrol_squad"},
            ),
            DecisionOption.create(
                "Keep Together",
                payload={"choice": False, "unit_id": unit_id, "action": "skip_patrol_squad"},
            ),
        ]
        request = DecisionRequest.create(
            DECISION_CONFIRM_YES_NO,
            "Patrol Squad",
            player_id=player_id,
            options=options,
            context={
                "ability": "patrol_squad",
                "ability_name": "Patrol Squad",
                "unit_id": unit_id,
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


def build_scout_move_request(game: object, unit: object) -> Optional[DecisionRequest]:
    if unit is None:
        return None
    unit_id = get_entity_id(unit)
    options = [
        DecisionOption.create(
            "Scout move",
            payload={"unit_id": unit_id, "action": "scout"},
        ),
        DecisionOption.create(
            "Skip scout move",
            payload={"unit_id": unit_id, "action": "skip"},
        ),
    ]
    prompt = f"Scout move for {getattr(unit, 'name', 'Unit')}"
    request = DecisionRequest.create(
        DECISION_SCOUT_MOVE,
        prompt,
        player_id=_player_id_for_unit(unit),
        options=options,
        context={"unit_id": unit_id},
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
