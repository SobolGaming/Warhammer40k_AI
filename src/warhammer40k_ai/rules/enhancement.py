from __future__ import annotations

from dataclasses import dataclass, field
from typing import Set, Tuple
import re

from ..utility.dice import get_roll


def _ensure_enhancement_fnp_entry(
    unit,
    value: int,
    *,
    condition: str | None = None,
    source: str | None = None,
    tag: str | None = None,
    source_model_id: str | None = None,
) -> bool:
    if unit is None:
        return False
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    entries = list(sr.get("enhancement_bearer_fnp_entries", []) or [])
    if tag:
        for entry in entries:
            if isinstance(entry, dict) and entry.get("tag") == tag:
                return False
    entry = {
        "value": int(value),
        "condition": str(condition) if condition else None,
        "source": str(source or "Enhancement"),
        "tag": str(tag or ""),
    }
    if source_model_id:
        entry["source_model_id"] = str(source_model_id)
    entries.append(entry)
    sr["enhancement_bearer_fnp_entries"] = entries
    unit.special_rules = sr
    return True


def _set_bearer_model_wounds_characteristic(model, desired_base: int) -> bool:
    if model is None:
        return False
    try:
        resolved_base = max(1, int(desired_base or 0))
    except (TypeError, ValueError):
        return False
    try:
        prev_base = int(getattr(model, "_base_wounds", resolved_base) or resolved_base)
    except (TypeError, ValueError):
        prev_base = resolved_base
    try:
        current = int(getattr(model, "_wounds", prev_base) or prev_base)
    except (TypeError, ValueError):
        current = prev_base
    missing = max(0, int(prev_base) - int(current))
    if int(current) == int(prev_base):
        model._wounds = int(resolved_base)
    else:
        model._wounds = max(0, int(resolved_base) - int(missing))
    model._base_wounds = int(resolved_base)
    model._base_wounds_unmodified = int(resolved_base)
    return True


def _current_unit_wounds(unit) -> int:
    total = 0
    for model in list(getattr(unit, "models", []) or []):
        alive = getattr(model, "is_alive", True)
        try:
            alive = alive() if callable(alive) else bool(alive)
        except Exception:
            alive = True
        if not alive:
            continue
        val = getattr(model, "wounds", None)
        if val is None:
            val = getattr(model, "_wounds", 0)
        try:
            total += int(val or 0)
        except Exception:
            continue
    return total


def maybe_upgrade_adaptive_biology(unit) -> bool:
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict) or not sr.get("enhancement_adaptive_biology"):
        return False
    if sr.get("enhancement_adaptive_biology_upgraded"):
        return False
    starting = int(getattr(unit, "starting_total_wounds", 0) or 0)
    if starting <= 0:
        return False
    current = _current_unit_wounds(unit)
    if current >= starting:
        return False
    _ensure_enhancement_fnp_entry(
        unit,
        4,
        source="Adaptive Biology",
        tag="adaptive_biology_upgrade",
    )
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    sr["enhancement_adaptive_biology_upgraded"] = True
    unit.special_rules = sr
    return True


def _normalize_weapon_name_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _weapon_name_matches(unit, expected_name: str, candidate_name: str) -> bool:
    expected = str(expected_name or "").strip()
    candidate = str(candidate_name or "").strip()
    if not expected or not candidate:
        return False
    if unit is not None and hasattr(unit, "_weapon_name_matches"):
        return bool(unit._weapon_name_matches([expected], candidate))
    exp_key = _normalize_weapon_name_key(expected)
    cand_key = _normalize_weapon_name_key(candidate)
    return bool(exp_key and cand_key and (exp_key == cand_key or exp_key in cand_key or cand_key in exp_key))


def _select_bearer_weapon(unit, bearer, *, weapon_name: str, require_ranged: bool) -> tuple[str, int]:
    if bearer is None:
        return "", -1
    desired_name = str(weapon_name or "").strip()
    for idx, wargear in enumerate(list(getattr(bearer, "wargear", []) or [])):
        if wargear is None:
            continue
        if require_ranged:
            is_ranged = getattr(wargear, "is_ranged", None)
            if not callable(is_ranged) or not bool(is_ranged()):
                continue
        name = str(getattr(wargear, "name", "") or "").strip()
        if not name:
            continue
        if desired_name and not _weapon_name_matches(unit, desired_name, name):
            continue
        return name, int(idx)
    return "", -1


def _coerce_int(value, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _coerce_float(value, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _descriptor_params(desc) -> dict:
    raw_params = getattr(desc, "effect_params", {}) if desc is not None else {}
    if isinstance(raw_params, dict):
        return dict(raw_params)
    try:
        return dict(raw_params or {})
    except (TypeError, ValueError):
        return {}


def _enhancement_cp_gain_unit_root(unit):
    if unit is None:
        return None
    root_fn = getattr(unit, "get_attached_unit_root", None)
    if callable(root_fn):
        root = root_fn()
        if root is not None:
            return root
    return unit


def _enhancement_cp_gain_unit_sort_key(unit) -> str:
    return str(get_entity_id(_enhancement_cp_gain_unit_root(unit)) or "")


def _enhancement_cp_gain_model_sort_key(model) -> str:
    return str(get_entity_id(model) or "")


def _enhancement_cp_gain_model_id(model) -> str:
    if model is None:
        return ""
    return str(getattr(model, "id", getattr(model, "_id", "")) or "")


def _enhancement_cp_gain_model_is_alive(model) -> bool:
    if model is None:
        return False
    is_alive_attr = getattr(model, "is_alive", True)
    if callable(is_alive_attr):
        return bool(is_alive_attr())
    return bool(is_alive_attr)


def _enhancement_cp_gain_unit_is_alive(unit) -> bool:
    if unit is None:
        return False
    is_alive_fn = getattr(unit, "is_alive", None)
    if callable(is_alive_fn):
        return bool(is_alive_fn())
    return bool(getattr(unit, "is_alive", True))


def _enhancement_cp_gain_unit_is_deployed_on_battlefield(unit) -> bool:
    if unit is None:
        return False
    if not _enhancement_cp_gain_unit_is_alive(unit):
        return False
    if not bool(getattr(unit, "deployed", False)):
        return False
    status = str(getattr(unit, "reserve_status", "deployed") or "deployed").strip().lower()
    if status != "deployed":
        return False
    in_reserves_fn = getattr(unit, "is_in_reserves", None)
    if callable(in_reserves_fn):
        return not bool(in_reserves_fn())
    return True


def _enhancement_cp_gain_unit_is_on_battlefield_or_embarked(unit) -> bool:
    root = _enhancement_cp_gain_unit_root(unit)
    if root is None:
        return False
    get_army = getattr(root, "get_parent_army", None)
    if callable(get_army):
        army = get_army()
    else:
        army = getattr(root, "parent_army", None)
    orks_mgr = getattr(army, "orks_detachments", None) if army is not None else None
    checker = getattr(orks_mgr, "_unit_is_on_battlefield_or_embarked", None) if orks_mgr is not None else None
    if callable(checker):
        return bool(checker(root))
    embarked_in = getattr(root, "embarked_in", None)
    if embarked_in is not None:
        return _enhancement_cp_gain_unit_is_deployed_on_battlefield(embarked_in)
    return _enhancement_cp_gain_unit_is_deployed_on_battlefield(root)


def _enhancement_cp_gain_member_units(root) -> list:
    if root is None:
        return []
    members_fn = getattr(root, "get_attached_unit_members", None)
    members = list(members_fn() or []) if callable(members_fn) else [root]
    if not members:
        members = [root]
    members.sort(key=_enhancement_cp_gain_unit_sort_key)
    return members


def _enhancement_cp_gain_model_matches_source_id(model, source_model_id: str) -> bool:
    if model is None:
        return False
    source_id = str(source_model_id or "").strip()
    if not source_id:
        return False
    entity_id = str(get_entity_id(model) or "").strip()
    if entity_id and entity_id == source_id:
        return True
    local_id = _enhancement_cp_gain_model_id(model)
    if local_id and local_id == source_id:
        return True
    return False


def _enhancement_cp_gain_find_source_model(member, *, source_model_id: str):
    models = list(getattr(member, "models", []) or [])
    models.sort(key=_enhancement_cp_gain_model_sort_key)
    source_id = str(source_model_id or "").strip()
    if source_id:
        for model in models:
            if _enhancement_cp_gain_model_matches_source_id(model, source_id):
                return model
    get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
    if callable(get_bearer):
        bearer = get_bearer()
        if bearer is not None:
            return bearer
    for model in models:
        if _enhancement_cp_gain_model_is_alive(model):
            return model
    return None


def _enhancement_cp_gain_model_parent_root(model, *, fallback_unit=None):
    parent = getattr(model, "parent_unit", None) if model is not None else None
    if parent is None:
        parent = fallback_unit
    return _enhancement_cp_gain_unit_root(parent)


def _enhancement_cp_gain_unit_effective_model_count(
    unit,
    *,
    scope: str,
    game=None,
) -> int:
    root = _enhancement_cp_gain_unit_root(unit)
    if root is None:
        return 0
    game_map = getattr(game, "map", None) if game is not None else None
    count_fn = getattr(root, "orks_effective_model_count_for_evaluation", None)
    if callable(count_fn):
        value = count_fn(str(scope or "enhancement"), game=game, game_map=game_map)
        return int(value or 0)
    total = 0
    for member in _enhancement_cp_gain_member_units(root):
        total += len(list(getattr(member, "models", []) or []))
    return int(total)


def _enhancement_cp_gain_enemy_units_for_player(player, *, game=None) -> list:
    if player is None or game is None:
        return []
    units = []
    seen_ids: set[str] = set()
    for other in list(getattr(game, "players", []) or []):
        if other is None or other is player:
            continue
        army = getattr(other, "army", None)
        for unit in list(getattr(army, "units", []) or []):
            root = _enhancement_cp_gain_unit_root(unit)
            if root is None:
                continue
            root_id = str(get_entity_id(root) or "").strip()
            if root_id and root_id in seen_ids:
                continue
            if root_id:
                seen_ids.add(root_id)
            if not _enhancement_cp_gain_unit_is_deployed_on_battlefield(root):
                continue
            if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
                continue
            units.append(root)
    units.sort(key=_enhancement_cp_gain_unit_sort_key)
    return units


def _enhancement_cp_gain_unit_has_enemy_within_distance(
    unit,
    *,
    distance_in: float,
    player,
    game=None,
) -> bool:
    root = _enhancement_cp_gain_unit_root(unit)
    if root is None:
        return False
    if not _enhancement_cp_gain_unit_is_deployed_on_battlefield(root):
        return False
    game_map = getattr(game, "map", None) if game is not None else None
    if game_map is None:
        return False
    max_distance = float(distance_in)
    for enemy in _enhancement_cp_gain_enemy_units_for_player(player, game=game):
        try:
            distance = float(game_map.get_distance_between_units(root, enemy))
        except (TypeError, ValueError, AttributeError):
            continue
        if distance <= max_distance + 1e-6:
            return True
    return False


def _register_enhancement_command_phase_cp_gain_roll_spec(
    unit,
    *,
    source_name: str,
    source_model_id: str,
    success_on: int,
    cp_gain: int,
    requires_bearer_on_battlefield_or_embarked_transport: bool,
    enemy_range_max: float | None = None,
    enemy_range_reference: str = "",
    roll_bonus_if_effective_model_count_at_least: int = 0,
    effective_model_count_threshold: int = 10,
    effective_model_count_scope: str = "enhancement",
) -> None:
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    specs = list(sr.get("enhancement_command_phase_cp_gain_roll_specs", []) or [])
    normalized_scope = str(effective_model_count_scope or "enhancement").strip().lower() or "enhancement"
    spec = {
        "type": "enhancement_command_phase_cp_gain_roll",
        "source": str(source_name or "Enhancement").strip() or "Enhancement",
        "source_model_id": str(source_model_id or "").strip(),
        "success_on": int(min(6, max(2, int(success_on)))),
        "cp_gain": int(max(1, int(cp_gain))),
        "requires_bearer_on_battlefield_or_embarked_transport": bool(
            requires_bearer_on_battlefield_or_embarked_transport
        ),
        "enemy_range_reference": str(enemy_range_reference or "").strip().lower(),
        "roll_bonus_if_effective_model_count_at_least": int(roll_bonus_if_effective_model_count_at_least or 0),
        "effective_model_count_threshold": int(max(0, int(effective_model_count_threshold or 0))),
        "effective_model_count_scope": normalized_scope,
    }
    if enemy_range_max is not None:
        spec["enemy_range_max"] = float(max(0.0, _coerce_float(enemy_range_max, default=0.0)))
    dedupe_key = (
        str(spec.get("source", "") or "").strip().lower(),
        str(spec.get("source_model_id", "") or "").strip(),
        int(spec.get("success_on", 0) or 0),
        int(spec.get("cp_gain", 0) or 0),
        bool(spec.get("requires_bearer_on_battlefield_or_embarked_transport", False)),
        _coerce_float(spec.get("enemy_range_max", -1.0) if "enemy_range_max" in spec else -1.0, default=-1.0),
        str(spec.get("enemy_range_reference", "") or "").strip().lower(),
        int(spec.get("roll_bonus_if_effective_model_count_at_least", 0) or 0),
        int(spec.get("effective_model_count_threshold", 0) or 0),
        str(spec.get("effective_model_count_scope", "") or "").strip().lower(),
    )
    seen = set()
    deduped: list[dict] = []
    for existing in specs:
        if not isinstance(existing, dict):
            continue
        existing_key = (
            str(existing.get("source", "") or "").strip().lower(),
            str(existing.get("source_model_id", "") or "").strip(),
            int(existing.get("success_on", 0) or 0),
            int(existing.get("cp_gain", 0) or 0),
            bool(existing.get("requires_bearer_on_battlefield_or_embarked_transport", False)),
            _coerce_float(
                existing.get("enemy_range_max", -1.0) if "enemy_range_max" in existing else -1.0,
                default=-1.0,
            ),
            str(existing.get("enemy_range_reference", "") or "").strip().lower(),
            int(existing.get("roll_bonus_if_effective_model_count_at_least", 0) or 0),
            int(existing.get("effective_model_count_threshold", 0) or 0),
            str(existing.get("effective_model_count_scope", "") or "").strip().lower(),
        )
        if existing_key in seen:
            continue
        seen.add(existing_key)
        deduped.append(existing)
    if dedupe_key not in seen:
        deduped.append(spec)
    deduped.sort(
        key=lambda entry: (
            str(entry.get("source_model_id", "") or ""),
            str(entry.get("source", "") or "").strip().lower(),
            int(entry.get("success_on", 0) or 0),
            int(entry.get("cp_gain", 0) or 0),
        )
    )
    sr["enhancement_command_phase_cp_gain_roll_specs"] = deduped
    unit.special_rules = sr


def resolve_enhancement_command_phase_cp_gain_roll_specs(
    root_unit,
    *,
    player,
    game=None,
) -> list[dict]:
    root = _enhancement_cp_gain_unit_root(root_unit)
    if root is None or player is None:
        return []
    gain_cp = getattr(player, "gain_command_points", None)
    if not callable(gain_cp):
        return []

    outcomes: list[dict] = []
    for member in _enhancement_cp_gain_member_units(root):
        sr = getattr(member, "special_rules", None)
        if not isinstance(sr, dict):
            continue
        specs = [dict(spec) for spec in list(sr.get("enhancement_command_phase_cp_gain_roll_specs", []) or []) if isinstance(spec, dict)]
        specs.sort(
            key=lambda spec: (
                str(spec.get("source_model_id", "") or ""),
                str(spec.get("source", "") or "").strip().lower(),
                int(spec.get("success_on", 0) or 0),
                int(spec.get("cp_gain", 0) or 0),
            )
        )
        for spec in specs:
            source_model_id = str(spec.get("source_model_id", "") or "").strip()
            source_name = str(spec.get("source", "") or "Enhancement").strip() or "Enhancement"
            source_model = _enhancement_cp_gain_find_source_model(member, source_model_id=source_model_id)
            if source_model_id and source_model is None:
                continue
            requires_bearer_on_battlefield = bool(
                spec.get("requires_bearer_on_battlefield_or_embarked_transport", False)
            )
            source_root = _enhancement_cp_gain_model_parent_root(source_model, fallback_unit=member)
            if source_root is None:
                continue
            if requires_bearer_on_battlefield and not _enhancement_cp_gain_unit_is_on_battlefield_or_embarked(source_root):
                continue

            enemy_range_max = spec.get("enemy_range_max", None)
            if enemy_range_max is not None:
                max_distance = float(max(0.0, _coerce_float(enemy_range_max, default=0.0)))
                range_reference = str(spec.get("enemy_range_reference", "") or "").strip().lower()
                range_root = source_root
                if range_reference in {"source_or_transport", "bearer_or_transport"}:
                    embarked_transport = getattr(source_root, "embarked_in", None)
                    if embarked_transport is not None:
                        range_root = _enhancement_cp_gain_unit_root(embarked_transport)
                if not _enhancement_cp_gain_unit_has_enemy_within_distance(
                    range_root,
                    distance_in=max_distance,
                    player=player,
                    game=game,
                ):
                    continue

            success_on = int(min(6, max(2, int(spec.get("success_on", 5) or 5))))
            cp_gain = int(max(1, int(spec.get("cp_gain", 1) or 1)))
            roll_bonus = int(spec.get("roll_bonus_if_effective_model_count_at_least", 0) or 0)
            modifier = 0
            if roll_bonus != 0:
                threshold = int(max(0, int(spec.get("effective_model_count_threshold", 10) or 10)))
                scope = str(spec.get("effective_model_count_scope", "enhancement") or "enhancement").strip().lower()
                count = _enhancement_cp_gain_unit_effective_model_count(
                    source_root,
                    scope=scope,
                    game=game,
                )
                if count >= threshold:
                    modifier += int(roll_bonus)

            roll = int(get_roll("D6") or 0)
            total = int(roll + modifier)
            gained = 0
            if total >= success_on:
                gained = int(gain_cp(cp_gain, reason=source_name) or 0)

            outcomes.append(
                {
                    "triggered": True,
                    "source": source_name,
                    "roll": int(roll),
                    "roll_modifier": int(modifier),
                    "total": int(total),
                    "success_on": int(success_on),
                    "cp_gain": int(cp_gain),
                    "gained": int(gained),
                    "source_unit_id": str(get_entity_id(source_root) or ""),
                    "source_model_id": str(get_entity_id(source_model) or "") if source_model is not None else "",
                    "source_member_unit_id": str(get_entity_id(member) or ""),
                }
            )
    return outcomes


def _register_enhancement_start_of_battle_roll_spec(
    unit,
    *,
    source_name: str,
    source_model_id: str,
    ability_key: str,
    roll_expr: str,
    effect: str,
    effect_params: dict | None = None,
    requires_bearer_alive: bool,
) -> None:
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    specs = list(sr.get("enhancement_start_of_battle_roll_specs", []) or [])
    spec = {
        "type": "enhancement_start_of_battle_roll",
        "source": str(source_name or "Enhancement").strip() or "Enhancement",
        "source_model_id": str(source_model_id or "").strip(),
        "ability_key": str(ability_key or "").strip().lower(),
        "roll_expr": str(roll_expr or "D3").strip().upper() or "D3",
        "effect": str(effect or "").strip().lower(),
        "effect_params": dict(effect_params or {}),
        "requires_bearer_alive": bool(requires_bearer_alive),
    }
    dedupe_key = (
        str(spec.get("source", "") or "").strip().lower(),
        str(spec.get("source_model_id", "") or "").strip(),
        str(spec.get("ability_key", "") or "").strip().lower(),
        str(spec.get("roll_expr", "") or "").strip().upper(),
        str(spec.get("effect", "") or "").strip().lower(),
    )
    seen: set[tuple[str, str, str, str, str]] = set()
    deduped: list[dict] = []
    for existing in specs:
        if not isinstance(existing, dict):
            continue
        existing_key = (
            str(existing.get("source", "") or "").strip().lower(),
            str(existing.get("source_model_id", "") or "").strip(),
            str(existing.get("ability_key", "") or "").strip().lower(),
            str(existing.get("roll_expr", "") or "").strip().upper(),
            str(existing.get("effect", "") or "").strip().lower(),
        )
        if existing_key in seen:
            continue
        seen.add(existing_key)
        deduped.append(existing)
    if dedupe_key not in seen:
        deduped.append(spec)
    deduped.sort(
        key=lambda entry: (
            str(entry.get("source_model_id", "") or ""),
            str(entry.get("source", "") or "").strip().lower(),
            str(entry.get("ability_key", "") or "").strip().lower(),
            str(entry.get("effect", "") or "").strip().lower(),
        )
    )
    sr["enhancement_start_of_battle_roll_specs"] = deduped
    unit.special_rules = sr


def resolve_enhancement_start_of_battle_roll_specs(
    root_unit,
    *,
    player,
    game=None,
) -> list[dict]:
    root = _enhancement_cp_gain_unit_root(root_unit)
    if root is None:
        return []

    outcomes: list[dict] = []
    for member in _enhancement_cp_gain_member_units(root):
        sr = getattr(member, "special_rules", None)
        if not isinstance(sr, dict):
            continue
        specs = [
            dict(spec)
            for spec in list(sr.get("enhancement_start_of_battle_roll_specs", []) or [])
            if isinstance(spec, dict)
        ]
        specs.sort(
            key=lambda spec: (
                str(spec.get("source_model_id", "") or ""),
                str(spec.get("source", "") or "").strip().lower(),
                str(spec.get("ability_key", "") or "").strip().lower(),
                str(spec.get("effect", "") or "").strip().lower(),
            )
        )
        for spec in specs:
            source_model_id = str(spec.get("source_model_id", "") or "").strip()
            source_name = str(spec.get("source", "") or "Enhancement").strip() or "Enhancement"
            ability_key = str(spec.get("ability_key", "") or "").strip().lower()
            effect = str(spec.get("effect", "") or "").strip().lower()
            if not ability_key or not effect:
                continue
            source_model = _enhancement_cp_gain_find_source_model(member, source_model_id=source_model_id)
            if source_model_id and source_model is None:
                continue
            if bool(spec.get("requires_bearer_alive", False)) and not _enhancement_cp_gain_model_is_alive(source_model):
                continue

            if effect == "bionik_workshop":
                get_choice = getattr(root, "get_bionik_workshop_choice", None)
                if callable(get_choice) and get_choice(ability_key=ability_key):
                    continue
                effect_params = dict(spec.get("effect_params", {}) or {})
                roll_expr = str(spec.get("roll_expr", "") or "D3").strip().upper() or "D3"
                roll = int(get_roll(roll_expr) or 0)
                branch_map = dict(effect_params.get("roll_branches", {}) or {})
                branch_data = branch_map.get(str(int(roll))) or {}
                if not isinstance(branch_data, dict):
                    branch_data = {}
                branch_key = str(branch_data.get("branch_key", "") or "").strip().lower()
                branch_label = str(branch_data.get("label", "") or branch_key.replace("_", " ").title()).strip()
                apply_choice = getattr(root, "apply_bionik_workshop_choice", None)
                applied = bool(
                    callable(apply_choice)
                    and branch_key
                    and apply_choice(
                        branch_key=branch_key,
                        source=source_name,
                        ability_key=ability_key,
                        source_model_id=source_model_id,
                    )
                )
                outcomes.append(
                    {
                        "triggered": True,
                        "source": source_name,
                        "ability_key": ability_key,
                        "effect": effect,
                        "roll_expr": roll_expr,
                        "roll": int(roll),
                        "branch_key": branch_key,
                        "branch_label": branch_label,
                        "applied": bool(applied),
                    }
                )
    return outcomes


def _normalize_enhancement_redeploy_keyword_list(values) -> list[str]:
    keywords: list[str] = []
    for value in list(values or ()):
        token = str(value or "").strip().upper()
        if token and token not in keywords:
            keywords.append(token)
    return keywords


def _normalize_enhancement_redeploy_filter_any_groups(values) -> list[list[str]]:
    groups: list[list[str]] = []
    for raw_group in list(values or ()):
        raw_values = [raw_group] if isinstance(raw_group, str) else list(raw_group or ())
        group = _normalize_enhancement_redeploy_keyword_list(raw_values)
        if group:
            groups.append(group)
    return groups


def _append_keyword_once(entity, keyword: str) -> bool:
    if entity is None:
        return False
    token = str(keyword or "").strip().upper()
    if not token:
        return False
    current = [str(value or "").strip().upper() for value in list(getattr(entity, "keywords", []) or [])]
    if token in current:
        return False
    current.append(token)
    entity.keywords = list(current)
    return True


def _register_enhancement_redeploy_spec(
    unit,
    *,
    source_name: str,
    source_model_id: str = "",
    max_units: int,
    can_place_in_reserves: bool,
    redeploy_filters=(),
    excluded_keywords=(),
    filter_any_groups=(),
    requires_source_on_battlefield: bool = False,
    allow_embarked_transport_on_battlefield: bool = False,
    exclude_source_unit: bool = False,
    must_include_source_unit: bool = False,
    require_exact_count: bool = False,
    army_once_per_ability: bool = False,
    strategic_reserves_ignore_current_unit_count_limit: bool = False,
) -> None:
    if unit is None:
        return
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    specs = [dict(spec) for spec in list(sr.get("enhancement_redeploy_specs", []) or ()) if isinstance(spec, dict)]
    normalized_filters = _normalize_enhancement_redeploy_keyword_list(redeploy_filters)
    normalized_excluded = _normalize_enhancement_redeploy_keyword_list(excluded_keywords)
    normalized_any_groups = _normalize_enhancement_redeploy_filter_any_groups(filter_any_groups)
    spec = {
        "source": str(source_name or "Redeploy").strip() or "Redeploy",
        "source_model_id": str(source_model_id or "").strip(),
        "max_units": int(max(1, int(max_units or 1))),
        "can_place_in_reserves": bool(can_place_in_reserves),
        "filters": list(normalized_filters),
        "excluded_keywords": list(normalized_excluded),
        "filter_any_groups": [list(group) for group in normalized_any_groups],
        "requires_source_on_battlefield": bool(requires_source_on_battlefield),
        "allow_embarked_transport_on_battlefield": bool(allow_embarked_transport_on_battlefield),
        "exclude_source_unit": bool(exclude_source_unit),
        "must_include_source_unit": bool(must_include_source_unit),
        "require_exact_count": bool(require_exact_count),
        "army_once_per_ability": bool(army_once_per_ability),
        "strategic_reserves_ignore_current_unit_count_limit": bool(
            strategic_reserves_ignore_current_unit_count_limit
        ),
    }
    dedupe_key = (
        str(spec.get("source", "") or "").strip().lower(),
        str(spec.get("source_model_id", "") or "").strip(),
        int(spec.get("max_units", 0) or 0),
        bool(spec.get("can_place_in_reserves", False)),
        tuple(spec.get("filters", ()) or ()),
        tuple(spec.get("excluded_keywords", ()) or ()),
        tuple(tuple(group) for group in list(spec.get("filter_any_groups", ()) or ())),
        bool(spec.get("requires_source_on_battlefield", False)),
        bool(spec.get("allow_embarked_transport_on_battlefield", False)),
        bool(spec.get("exclude_source_unit", False)),
        bool(spec.get("must_include_source_unit", False)),
        bool(spec.get("require_exact_count", False)),
        bool(spec.get("army_once_per_ability", False)),
        bool(spec.get("strategic_reserves_ignore_current_unit_count_limit", False)),
    )
    deduped: list[dict] = []
    seen: set[tuple] = set()
    for existing in specs:
        existing_key = (
            str(existing.get("source", "") or "").strip().lower(),
            str(existing.get("source_model_id", "") or "").strip(),
            int(existing.get("max_units", 0) or 0),
            bool(existing.get("can_place_in_reserves", False)),
            tuple(
                str(value or "").strip().upper()
                for value in list(existing.get("filters", ()) or ())
                if str(value or "").strip()
            ),
            tuple(
                str(value or "").strip().upper()
                for value in list(existing.get("excluded_keywords", ()) or ())
                if str(value or "").strip()
            ),
            tuple(
                tuple(
                    str(value or "").strip().upper()
                    for value in ([group] if isinstance(group, str) else list(group or ()))
                    if str(value or "").strip()
                )
                for group in list(existing.get("filter_any_groups", ()) or ())
            ),
            bool(existing.get("requires_source_on_battlefield", False)),
            bool(existing.get("allow_embarked_transport_on_battlefield", False)),
            bool(existing.get("exclude_source_unit", False)),
            bool(existing.get("must_include_source_unit", False)),
            bool(existing.get("require_exact_count", False)),
            bool(existing.get("army_once_per_ability", False)),
            bool(existing.get("strategic_reserves_ignore_current_unit_count_limit", False)),
        )
        if existing_key in seen:
            continue
        seen.add(existing_key)
        deduped.append(existing)
    if dedupe_key not in seen:
        deduped.append(spec)
    deduped.sort(
        key=lambda entry: (
            str(entry.get("source_model_id", "") or ""),
            str(entry.get("source", "") or "").strip().lower(),
            int(entry.get("max_units", 0) or 0),
            tuple(str(value or "").strip().upper() for value in list(entry.get("filters", ()) or ())),
        )
    )
    sr["enhancement_redeploy_specs"] = deduped
    unit.special_rules = sr


def _normalize_enhancement_local_passive_attack_type(attack_type: str) -> str:
    token = str(attack_type or "any").strip().lower() or "any"
    return token if token in ("any", "ranged", "melee") else "any"


def _normalize_enhancement_local_passive_target_scope(target_scope: str) -> str:
    token = str(target_scope or "bearer_unit").strip().lower() or "bearer_unit"
    return token if token in ("bearer", "bearer_unit") else "bearer_unit"


def _append_enhancement_local_passive_rule(
    unit,
    *,
    storage_key: str,
    entry: dict,
    dedupe_key,
    sort_key,
) -> None:
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    entries = [dict(existing) for existing in list(sr.get(storage_key, []) or []) if isinstance(existing, dict)]
    if any(dedupe_key(existing) == dedupe_key(entry) for existing in entries):
        return
    entries.append(dict(entry))
    entries.sort(key=sort_key)
    sr[storage_key] = entries
    unit.special_rules = sr
    invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
    if callable(invalidate_cache):
        invalidate_cache()


def _append_enhancement_weapon_keyword_rule(
    unit,
    *,
    target_scope: str,
    attack_type: str,
    keywords: tuple[str, ...] | list[str],
    source: str,
    requires_bearer_leading: bool = False,
    source_model_id: str = "",
) -> None:
    normalized_keywords = []
    for keyword in list(keywords or []):
        token = str(keyword or "").strip().upper()
        if token and token not in normalized_keywords:
            normalized_keywords.append(token)
    if not normalized_keywords:
        return
    entry = {
        "target_scope": _normalize_enhancement_local_passive_target_scope(target_scope),
        "attack_type": _normalize_enhancement_local_passive_attack_type(attack_type),
        "keywords": list(normalized_keywords),
        "source": str(source or "Enhancement").strip() or "Enhancement",
        "requires_bearer_leading": bool(requires_bearer_leading),
    }
    if source_model_id:
        entry["source_model_id"] = str(source_model_id)
    _append_enhancement_local_passive_rule(
        unit,
        storage_key="enhancement_weapon_keyword_rules",
        entry=entry,
        dedupe_key=lambda value: (
            str(value.get("target_scope", "bearer_unit") or "bearer_unit").strip().lower(),
            str(value.get("attack_type", "any") or "any").strip().lower(),
            tuple(
                str(token or "").strip().upper()
                for token in list(value.get("keywords", []) or [])
                if str(token or "").strip()
            ),
            str(value.get("source", "") or "").strip().lower(),
            bool(value.get("requires_bearer_leading", False)),
            str(value.get("source_model_id", "") or ""),
        ),
        sort_key=lambda value: (
            str(value.get("target_scope", "bearer_unit") or "bearer_unit").strip().lower(),
            str(value.get("attack_type", "any") or "any").strip().lower(),
            str(value.get("source_model_id", "") or ""),
            str(value.get("source", "") or "").strip().lower(),
            tuple(
                str(token or "").strip().upper()
                for token in list(value.get("keywords", []) or [])
                if str(token or "").strip()
            ),
        ),
    )


def _append_enhancement_bearer_weapon_keyword_rule(
    unit,
    *,
    attack_type: str,
    keywords: tuple[str, ...] | list[str],
    source: str,
    requires_bearer_leading: bool = False,
    source_model_id: str = "",
) -> None:
    _append_enhancement_weapon_keyword_rule(
        unit,
        target_scope="bearer",
        attack_type=attack_type,
        keywords=keywords,
        source=source,
        requires_bearer_leading=requires_bearer_leading,
        source_model_id=source_model_id,
    )


def _append_enhancement_bearer_unit_weapon_keyword_rule(
    unit,
    *,
    attack_type: str,
    keywords: tuple[str, ...] | list[str],
    source: str,
    requires_bearer_leading: bool = False,
    source_model_id: str = "",
) -> None:
    _append_enhancement_weapon_keyword_rule(
        unit,
        target_scope="bearer_unit",
        attack_type=attack_type,
        keywords=keywords,
        source=source,
        requires_bearer_leading=requires_bearer_leading,
        source_model_id=source_model_id,
    )


def _append_enhancement_attack_roll_modifier_rule(
    unit,
    *,
    target_scope: str,
    attack_type: str,
    roll: str,
    modifier: int,
    source: str,
    requires_bearer_leading: bool = False,
    source_model_id: str = "",
) -> None:
    modifier_value = int(modifier or 0)
    if modifier_value == 0:
        return
    roll_name = str(roll or "hit").strip().lower() or "hit"
    if roll_name not in ("hit", "wound"):
        roll_name = "hit"
    entry = {
        "target_scope": _normalize_enhancement_local_passive_target_scope(target_scope),
        "attack_type": _normalize_enhancement_local_passive_attack_type(attack_type),
        "roll": roll_name,
        "modifier": modifier_value,
        "source": str(source or "Enhancement").strip() or "Enhancement",
        "requires_bearer_leading": bool(requires_bearer_leading),
    }
    if source_model_id:
        entry["source_model_id"] = str(source_model_id)
    _append_enhancement_local_passive_rule(
        unit,
        storage_key="enhancement_attack_roll_modifier_rules",
        entry=entry,
        dedupe_key=lambda value: (
            str(value.get("target_scope", "bearer_unit") or "bearer_unit").strip().lower(),
            str(value.get("attack_type", "any") or "any").strip().lower(),
            str(value.get("roll", "hit") or "hit").strip().lower(),
            int(value.get("modifier", 0) or 0),
            str(value.get("source", "") or "").strip().lower(),
            bool(value.get("requires_bearer_leading", False)),
            str(value.get("source_model_id", "") or ""),
        ),
        sort_key=lambda value: (
            str(value.get("target_scope", "bearer_unit") or "bearer_unit").strip().lower(),
            str(value.get("attack_type", "any") or "any").strip().lower(),
            str(value.get("roll", "hit") or "hit").strip().lower(),
            str(value.get("source_model_id", "") or ""),
            str(value.get("source", "") or "").strip().lower(),
            int(value.get("modifier", 0) or 0),
        ),
    )


def _append_enhancement_bearer_unit_attack_roll_modifier_rule(
    unit,
    *,
    attack_type: str,
    roll: str,
    modifier: int,
    source: str,
    requires_bearer_leading: bool = False,
    source_model_id: str = "",
) -> None:
    _append_enhancement_attack_roll_modifier_rule(
        unit,
        target_scope="bearer_unit",
        attack_type=attack_type,
        roll=roll,
        modifier=modifier,
        source=source,
        requires_bearer_leading=requires_bearer_leading,
        source_model_id=source_model_id,
    )


def _append_enhancement_fall_back_shoot_rule(
    unit,
    *,
    target_scope: str,
    attack_type: str,
    source: str,
    requires_bearer_leading: bool = False,
    source_model_id: str = "",
) -> None:
    entry = {
        "target_scope": _normalize_enhancement_local_passive_target_scope(target_scope),
        "attack_type": _normalize_enhancement_local_passive_attack_type(attack_type),
        "source": str(source or "Enhancement").strip() or "Enhancement",
        "requires_bearer_leading": bool(requires_bearer_leading),
    }
    if source_model_id:
        entry["source_model_id"] = str(source_model_id)
    _append_enhancement_local_passive_rule(
        unit,
        storage_key="enhancement_fall_back_shoot_rules",
        entry=entry,
        dedupe_key=lambda value: (
            str(value.get("target_scope", "bearer_unit") or "bearer_unit").strip().lower(),
            str(value.get("attack_type", "any") or "any").strip().lower(),
            str(value.get("source", "") or "").strip().lower(),
            bool(value.get("requires_bearer_leading", False)),
            str(value.get("source_model_id", "") or ""),
        ),
        sort_key=lambda value: (
            str(value.get("target_scope", "bearer_unit") or "bearer_unit").strip().lower(),
            str(value.get("attack_type", "any") or "any").strip().lower(),
            str(value.get("source_model_id", "") or ""),
            str(value.get("source", "") or "").strip().lower(),
        ),
    )


def _append_enhancement_bearer_unit_fall_back_shoot_rule(
    unit,
    *,
    attack_type: str,
    source: str,
    requires_bearer_leading: bool = False,
    source_model_id: str = "",
) -> None:
    _append_enhancement_fall_back_shoot_rule(
        unit,
        target_scope="bearer_unit",
        attack_type=attack_type,
        source=source,
        requires_bearer_leading=requires_bearer_leading,
        source_model_id=source_model_id,
    )


def _normalize_enhancement_sticky_objective_source_scope(scope: str) -> str:
    value = str(scope or "unit").strip().lower()
    if value in ("bearer", "model", "source_model"):
        return "bearer"
    return "unit"


def _append_enhancement_sticky_objective_rule(
    unit,
    *,
    source_scope: str,
    source: str,
    allow_embarked_transport: bool = False,
    requires_bearer_leading: bool = False,
    source_model_id: str = "",
) -> None:
    entry = {
        "source_scope": _normalize_enhancement_sticky_objective_source_scope(source_scope),
        "source": str(source or "unit_sticky_objective").strip() or "unit_sticky_objective",
        "allow_embarked_transport": bool(allow_embarked_transport),
        "requires_bearer_leading": bool(requires_bearer_leading),
    }
    if source_model_id:
        entry["source_model_id"] = str(source_model_id)
    _append_enhancement_local_passive_rule(
        unit,
        storage_key="enhancement_sticky_objective_rules",
        entry=entry,
        dedupe_key=lambda value: (
            str(value.get("source_scope", "unit") or "unit").strip().lower(),
            str(value.get("source_model_id", "") or ""),
            str(value.get("source", "unit_sticky_objective") or "unit_sticky_objective").strip().lower(),
            bool(value.get("allow_embarked_transport", False)),
            bool(value.get("requires_bearer_leading", False)),
        ),
        sort_key=lambda value: (
            str(value.get("source_scope", "unit") or "unit").strip().lower(),
            str(value.get("source_model_id", "") or ""),
            str(value.get("source", "unit_sticky_objective") or "unit_sticky_objective").strip().lower(),
            int(bool(value.get("allow_embarked_transport", False))),
            int(bool(value.get("requires_bearer_leading", False))),
        ),
    )


def _apply_enhancement_sticky_objective_control(
    unit,
    *,
    source_scope: str,
    source: str,
    allow_embarked_transport: bool = False,
    requires_bearer_leading: bool = False,
    source_model_id: str = "",
) -> None:
    unit.special_rules["sticky_objectives"] = True
    if allow_embarked_transport:
        unit.special_rules["sticky_objectives_allow_embarked_transport"] = True
    _append_enhancement_sticky_objective_rule(
        unit,
        source_scope=source_scope,
        source=source,
        allow_embarked_transport=allow_embarked_transport,
        requires_bearer_leading=requires_bearer_leading,
        source_model_id=source_model_id,
    )


def _apply_selected_ranged_weapon_bonus_enhancement(
    unit,
    *,
    special_rule_flag: str,
    descriptor_params: dict,
    bearer,
    bearer_id: str,
    default_weapon_name: str,
    default_attacks_bonus: int,
    default_melta_bonus: int,
    default_strength_bonus: int,
    default_ap_bonus: int,
    default_damage_bonus: int,
    source_name: str,
) -> None:
    unit.special_rules[str(special_rule_flag)] = True
    selected_weapon_name = str(descriptor_params.get("weapon_name", default_weapon_name) or default_weapon_name).strip()
    selected_weapon_slot = -1
    if bearer is not None:
        chosen_name, chosen_slot = _select_bearer_weapon(
            unit,
            bearer,
            weapon_name=selected_weapon_name,
            require_ranged=True,
        )
        if chosen_name:
            selected_weapon_name = chosen_name
        selected_weapon_slot = int(chosen_slot)
    attacks_bonus = _coerce_int(
        descriptor_params.get("attacks_bonus", default_attacks_bonus) or default_attacks_bonus,
        default=default_attacks_bonus,
    )
    melta_bonus = _coerce_int(
        descriptor_params.get("melta_bonus", default_melta_bonus) or default_melta_bonus,
        default=default_melta_bonus,
    )
    strength_bonus = _coerce_int(
        descriptor_params.get("strength_bonus", default_strength_bonus) or default_strength_bonus,
        default=default_strength_bonus,
    )
    ap_bonus = _coerce_int(
        descriptor_params.get("ap_bonus", default_ap_bonus) or default_ap_bonus,
        default=default_ap_bonus,
    )
    damage_bonus = _coerce_int(
        descriptor_params.get("damage_bonus", default_damage_bonus) or default_damage_bonus,
        default=default_damage_bonus,
    )

    prefix = str(special_rule_flag)
    unit.special_rules[f"{prefix}_weapon_name"] = selected_weapon_name
    unit.special_rules[f"{prefix}_weapon_slot_index"] = int(selected_weapon_slot)
    unit.special_rules[f"{prefix}_attacks_bonus"] = int(max(0, attacks_bonus))
    unit.special_rules[f"{prefix}_melta_bonus"] = int(max(0, melta_bonus))
    unit.special_rules[f"{prefix}_strength_bonus"] = int(max(0, strength_bonus))
    unit.special_rules[f"{prefix}_ap_bonus"] = int(max(0, ap_bonus))
    unit.special_rules[f"{prefix}_damage_bonus"] = int(max(0, damage_bonus))
    unit.special_rules[f"{prefix}_source"] = str(source_name or "Enhancement").strip() or "Enhancement"
    if bearer_id:
        unit.special_rules["enhancement_bearer_model_id"] = bearer_id

from .enhancement_effects import (
    EnhancementEffectSpec,
    apply_enhancement_effects,
    normalize_enhancement_token,
    parse_enhancement_eligibility,
    parse_enhancement_effects,
)
from .enhancement_descriptors import get_enhancement_tool_descriptor
from ..utility.entity_ids import get_entity_id


@dataclass(slots=True)
class Enhancement:
    """
    Rules/metadata container for a Detachment Enhancement (10e).

    Current engine usage:
    - Stored on a Character unit (`Unit.enhancement`)
    - Included in points cost (`Unit.get_unit_cost()`)
    - Displayed in UI panels

    Important: enhancement *rules effects* are not generally executed by the engine yet.
    """

    id: str
    name: str
    faction_id: str
    detachment: str
    detachment_id: str = ""
    points: int = 0
    legend: str = ""
    description: str = ""
    eligible_keywords: Set[str] = field(default_factory=set)
    eligibility_clause: str = ""
    eligibility_keyword_groups: Tuple[frozenset[str], ...] = field(default_factory=tuple)
    eligibility_name_options: Tuple[str, ...] = field(default_factory=tuple)
    _effects: Tuple[EnhancementEffectSpec, ...] = field(default_factory=tuple, repr=False)

    @classmethod
    def from_waha_dict(cls, data: dict) -> "Enhancement":
        # Wahapedia enhancements do not provide a structured eligibility keyword list.
        # We parse simple "model only" clauses into eligibility groups when possible.
        eligibility = parse_enhancement_eligibility(str(data.get("description", "") or ""))
        return cls(
            id=str(data.get("id", "") or ""),
            name=str(data.get("name", "") or ""),
            faction_id=str(data.get("faction_id", "") or ""),
            detachment=str(data.get("detachment", "") or ""),
            detachment_id=str(data.get("detachment_id", "") or ""),
            points=int(data.get("cost", 0) or 0),
            legend=str(data.get("legend", "") or ""),
            description=str(data.get("description", "") or ""),
            eligible_keywords=set(),
            eligibility_clause=str(getattr(eligibility, "clause", "") or ""),
            eligibility_keyword_groups=tuple(getattr(eligibility, "keyword_groups", ()) or ()),
            eligibility_name_options=tuple(getattr(eligibility, "name_options", ()) or ()),
            _effects=tuple(parse_enhancement_effects(str(data.get("description", "") or ""))),
        )

    def get_effects(self) -> Tuple[EnhancementEffectSpec, ...]:
        if self._effects:
            return self._effects
        return tuple(parse_enhancement_effects(self.description))

    def apply_to_unit(self, unit) -> None:
        """
        Apply supported enhancement effects to the bearer unit.

        This is intentionally narrow/safe: only a few common patterns are supported,
        and everything else remains "Partial" support.
        """
        try:
            apply_enhancement_effects(unit, list(self.get_effects()))
        except Exception:
            # Never hard-fail list loading / army parsing due to a rules parsing miss.
            pass

        # Custom enhancement hooks (small, explicit support for known rules).
        try:
            if getattr(unit, "special_rules", None) is None:
                unit.special_rules = {}
        except Exception:
            return

        try:
            name = (
                str(getattr(self, "name", "") or "")
                .replace("\u2019", "'")
                .replace("\u2018", "'")
                .replace("\u0192?T", "'")
                .strip()
                .lower()
            )
        except Exception:
            name = ""
        try:
            enh_id = str(getattr(self, "id", "") or "").strip()
        except Exception:
            enh_id = ""

        try:
            for eff in self.get_effects():
                if eff.kind == "bearer_fnp" and eff.supported:
                    tag = f"enhancement_fnp_{enh_id or name}"
                    _ensure_enhancement_fnp_entry(
                        unit,
                        int(eff.value),
                        source=str(getattr(self, "name", "") or "Enhancement"),
                        tag=tag,
                    )
        except Exception:
            pass

        try:
            if hasattr(unit, "_refresh_targeted_stratagem_cp_increase_flags"):
                unit._refresh_targeted_stratagem_cp_increase_flags()
        except Exception:
            pass

        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
        ae_mgr = getattr(army, "aeldari_detachments", None) if army is not None else None
        dg_mgr = getattr(army, "death_guard_detachments", None) if army is not None else None
        ac_mgr = getattr(army, "adeptus_custodes_detachments", None) if army is not None else None
        as_mgr = getattr(army, "adepta_sororitas_detachments", None) if army is not None else None
        orks_mgr = getattr(army, "orks_detachments", None) if army is not None else None
        sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        cd_mgr = getattr(army, "chaos_daemons_detachments", None) if army is not None else None
        csm_mgr = getattr(army, "chaos_space_marines_detachments", None) if army is not None else None
        lov_mgr = getattr(army, "leagues_of_votann_detachments", None) if army is not None else None
        tau_mgr = getattr(army, "tau_empire_detachments", None) if army is not None else None
        ne_mgr = getattr(army, "necrons_detachments", None) if army is not None else None
        ec_mgr = getattr(army, "emperors_children_detachments", None) if army is not None else None
        if ec_mgr is None and army is not None:
            ec_mgr = getattr(army, "emperors_children", None)
        try:
            is_berzerker_warband = bool(we_mgr and we_mgr.is_berzerker_warband())
        except Exception:
            is_berzerker_warband = False
        try:
            is_khorne_daemonkin = bool(we_mgr and we_mgr.is_khorne_daemonkin())
        except Exception:
            is_khorne_daemonkin = False
        try:
            is_goretrack_onslaught = bool(we_mgr and we_mgr.is_goretrack_onslaught())
        except Exception:
            is_goretrack_onslaught = False
        try:
            is_cult_of_blood = bool(we_mgr and we_mgr.is_cult_of_blood())
        except Exception:
            is_cult_of_blood = False
        try:
            is_possessed_slaughterband = bool(we_mgr and we_mgr.is_possessed_slaughterband())
        except Exception:
            is_possessed_slaughterband = False
        try:
            is_vessels_of_wrath = bool(we_mgr and we_mgr.is_vessels_of_wrath())
        except Exception:
            is_vessels_of_wrath = False
        try:
            is_warhost = bool(ae_mgr and ae_mgr.is_warhost_detachment())
        except Exception:
            is_warhost = False
        try:
            is_armoured_warhost = bool(ae_mgr and ae_mgr.is_armoured_warhost())
        except Exception:
            is_armoured_warhost = False
        try:
            is_aspect_host = bool(ae_mgr and ae_mgr.is_aspect_host())
        except Exception:
            is_aspect_host = False
        try:
            is_guardian_battlehost = bool(ae_mgr and ae_mgr.is_guardian_battlehost())
        except Exception:
            is_guardian_battlehost = False
        try:
            is_seer_council = bool(ae_mgr and ae_mgr.is_seer_council())
        except Exception:
            is_seer_council = False
        try:
            is_windrider_host = bool(ae_mgr and ae_mgr.is_windrider_host())
        except Exception:
            is_windrider_host = False
        try:
            is_ghosts_of_the_webway = bool(ae_mgr and ae_mgr.is_ghosts_of_the_webway())
        except Exception:
            is_ghosts_of_the_webway = False
        try:
            is_eldritch_raiders = bool(ae_mgr and ae_mgr.is_eldritch_raiders())
        except Exception:
            is_eldritch_raiders = False
        try:
            is_spirit_conclave = bool(ae_mgr and ae_mgr.is_spirit_conclave())
        except Exception:
            is_spirit_conclave = False
        try:
            is_devoted_of_ynnead = bool(ae_mgr and ae_mgr.is_devoted_of_ynnead())
        except Exception:
            is_devoted_of_ynnead = False
        try:
            is_serpents_brood = bool(ae_mgr and ae_mgr.is_serpents_brood())
        except Exception:
            is_serpents_brood = False
        try:
            is_corsair_veterans = bool(ae_mgr and ae_mgr.has_veterans_of_the_void())
        except Exception:
            is_corsair_veterans = False
        try:
            is_champions_of_contagion = bool(dg_mgr and dg_mgr.is_champions_of_contagion())
        except Exception:
            is_champions_of_contagion = False
        try:
            is_death_lords_chosen = bool(dg_mgr and dg_mgr.is_death_lords_chosen())
        except Exception:
            is_death_lords_chosen = False
        try:
            is_flyblown_host = bool(dg_mgr and dg_mgr.is_flyblown_host())
        except Exception:
            is_flyblown_host = False
        try:
            is_mortarions_hammer = bool(dg_mgr and dg_mgr.is_mortarions_hammer())
        except Exception:
            is_mortarions_hammer = False
        try:
            is_shamblerot_vectorium = bool(dg_mgr and dg_mgr.is_shamblerot_vectorium())
        except Exception:
            is_shamblerot_vectorium = False
        try:
            is_tallyband_summoners = bool(dg_mgr and dg_mgr.is_tallyband_summoners())
        except Exception:
            is_tallyband_summoners = False
        try:
            is_virulent_vectorium = bool(dg_mgr and dg_mgr.is_virulent_vectorium())
        except Exception:
            is_virulent_vectorium = False
        try:
            is_hallowed_martyrs = bool(as_mgr and as_mgr.is_hallowed_martyrs())
        except Exception:
            is_hallowed_martyrs = False
        try:
            is_army_of_faith = bool(as_mgr and as_mgr.is_army_of_faith())
        except Exception:
            is_army_of_faith = False
        try:
            is_bringers_of_flame = bool(as_mgr and as_mgr.is_bringers_of_flame())
        except Exception:
            is_bringers_of_flame = False
        try:
            is_champions_of_faith = bool(as_mgr and as_mgr.is_champions_of_faith())
        except Exception:
            is_champions_of_faith = False
        try:
            is_penitent_host = bool(as_mgr and as_mgr.is_penitent_host())
        except Exception:
            is_penitent_host = False
        is_1st_company_task_force = bool(
            sm_mgr and getattr(sm_mgr, "is_1st_company_task_force", lambda: False)()
        )
        is_angelic_inheritors = bool(
            sm_mgr and getattr(sm_mgr, "is_angelic_inheritors", lambda: False)()
        )
        is_the_angelic_host = bool(
            sm_mgr and getattr(sm_mgr, "is_the_angelic_host", lambda: False)()
        )
        is_the_lost_brethren = bool(
            sm_mgr and getattr(sm_mgr, "is_the_lost_brethren", lambda: False)()
        )
        is_unforgiven_task_force = bool(
            sm_mgr and getattr(sm_mgr, "is_unforgiven_task_force", lambda: False)()
        )
        is_anvil_siege_force = bool(
            sm_mgr and getattr(sm_mgr, "is_anvil_siege_force", lambda: False)()
        )
        is_gladius_task_force = bool(
            sm_mgr and getattr(sm_mgr, "is_gladius_task_force", lambda: False)()
        )
        is_godhammer_assault_force = bool(
            sm_mgr and getattr(sm_mgr, "is_godhammer_assault_force", lambda: False)()
        )
        is_hammer_of_avernii = bool(
            sm_mgr and getattr(sm_mgr, "is_hammer_of_avernii", lambda: False)()
        )
        is_inner_circle_task_force = bool(
            sm_mgr and getattr(sm_mgr, "is_inner_circle_task_force", lambda: False)()
        )
        is_wrath_of_the_rock = bool(
            sm_mgr and getattr(sm_mgr, "is_wrath_of_the_rock", lambda: False)()
        )
        is_wrathful_procession = bool(
            sm_mgr and getattr(sm_mgr, "is_wrathful_procession", lambda: False)()
        )
        is_firestorm_assault_force = bool(
            sm_mgr and getattr(sm_mgr, "is_firestorm_assault_force", lambda: False)()
        )
        is_forgefathers_seekers = bool(
            sm_mgr and getattr(sm_mgr, "is_forgefathers_seekers", lambda: False)()
        )
        is_ironstorm_spearhead = bool(
            sm_mgr and getattr(sm_mgr, "is_ironstorm_spearhead", lambda: False)()
        )
        is_liberator_assault_group = bool(
            sm_mgr and getattr(sm_mgr, "is_liberator_assault_group", lambda: False)()
        )
        is_librarius_conclave = bool(
            sm_mgr and getattr(sm_mgr, "is_librarius_conclave", lambda: False)()
        )
        is_lions_blade_task_force = bool(
            sm_mgr and getattr(sm_mgr, "is_lions_blade_task_force", lambda: False)()
        )
        is_orbital_assault_force = bool(
            sm_mgr and getattr(sm_mgr, "is_orbital_assault_force", lambda: False)()
        )
        is_reclamation_force = bool(
            sm_mgr and getattr(sm_mgr, "is_reclamation_force", lambda: False)()
        )
        is_bastion_task_force = bool(
            sm_mgr and getattr(sm_mgr, "is_bastion_task_force", lambda: False)()
        )
        is_blade_of_ultramar = bool(
            sm_mgr and getattr(sm_mgr, "is_blade_of_ultramar", lambda: False)()
        )
        is_champions_of_fenris = bool(
            sm_mgr and getattr(sm_mgr, "is_champions_of_fenris", lambda: False)()
        )
        is_saga_of_the_beastslayer = bool(
            sm_mgr and getattr(sm_mgr, "is_saga_of_the_beastslayer", lambda: False)()
        )
        is_saga_of_the_bold = bool(
            sm_mgr and getattr(sm_mgr, "is_saga_of_the_bold", lambda: False)()
        )
        is_saga_of_the_hunter = bool(
            sm_mgr and getattr(sm_mgr, "is_saga_of_the_hunter", lambda: False)()
        )
        is_saga_of_the_great_wolf = bool(
            sm_mgr and getattr(sm_mgr, "is_saga_of_the_great_wolf", lambda: False)()
        )
        is_stormlance_task_force = bool(
            sm_mgr and getattr(sm_mgr, "is_stormlance_task_force", lambda: False)()
        )
        is_vanguard_spearhead = bool(
            sm_mgr and getattr(sm_mgr, "is_vanguard_spearhead", lambda: False)()
        )
        is_vindication_task_force = bool(
            sm_mgr and getattr(sm_mgr, "is_vindication_task_force", lambda: False)()
        )
        is_company_of_hunters = bool(
            sm_mgr and getattr(sm_mgr, "is_company_of_hunters", lambda: False)()
        )
        is_spearpoint_task_force = bool(
            sm_mgr and getattr(sm_mgr, "is_spearpoint_task_force", lambda: False)()
        )
        is_shadowmark_talon = bool(
            sm_mgr and getattr(sm_mgr, "is_shadowmark_talon", lambda: False)()
        )
        is_companions_of_vehemence = bool(
            sm_mgr and getattr(sm_mgr, "is_companions_of_vehemence", lambda: False)()
        )
        is_emperors_shield = bool(
            sm_mgr and getattr(sm_mgr, "is_emperors_shield", lambda: False)()
        )
        is_black_spear_task_force = bool(
            sm_mgr and getattr(sm_mgr, "is_black_spear_task_force", lambda: False)()
        )
        is_lions = bool(ac_mgr and ac_mgr.is_lions_of_the_emperor())
        is_auric_champions = bool(ac_mgr and ac_mgr.is_auric_champions())
        is_null_maiden_vigil = bool(ac_mgr and ac_mgr.is_null_maiden_vigil())
        is_shield_host = bool(ac_mgr and ac_mgr.is_shield_host())
        is_solar_spearhead = bool(ac_mgr and ac_mgr.is_solar_spearhead())
        is_talons_of_the_emperor = bool(ac_mgr and ac_mgr.is_talons_of_the_emperor())
        is_war_horde = bool(
            orks_mgr and callable(getattr(orks_mgr, "is_war_horde", None)) and orks_mgr.is_war_horde()
        )
        is_bully_boyz = bool(
            orks_mgr and callable(getattr(orks_mgr, "is_bully_boyz", None)) and orks_mgr.is_bully_boyz()
        )
        is_da_big_hunt = bool(
            orks_mgr and callable(getattr(orks_mgr, "is_da_big_hunt", None)) and orks_mgr.is_da_big_hunt()
        )
        is_dread_mob = bool(
            orks_mgr and callable(getattr(orks_mgr, "is_dread_mob", None)) and orks_mgr.is_dread_mob()
        )
        is_freebooter_krew = bool(
            orks_mgr and callable(getattr(orks_mgr, "is_freebooter_krew", None)) and orks_mgr.is_freebooter_krew()
        )
        is_green_tide = bool(
            orks_mgr and callable(getattr(orks_mgr, "is_green_tide", None)) and orks_mgr.is_green_tide()
        )
        is_kult_of_speed = bool(
            orks_mgr and callable(getattr(orks_mgr, "is_kult_of_speed", None)) and orks_mgr.is_kult_of_speed()
        )
        is_more_dakka = bool(
            orks_mgr and callable(getattr(orks_mgr, "is_more_dakka", None)) and orks_mgr.is_more_dakka()
        )
        is_taktikal_brigade = bool(
            orks_mgr and callable(getattr(orks_mgr, "is_taktikal_brigade", None)) and orks_mgr.is_taktikal_brigade()
        )
        try:
            is_daemonic_incursion = bool(cd_mgr and cd_mgr.is_daemonic_incursion_detachment())
        except Exception:
            is_daemonic_incursion = False
        try:
            is_shadow_legion = bool(cd_mgr and cd_mgr.is_shadow_legion_detachment())
        except Exception:
            is_shadow_legion = False
        try:
            is_blood_legion = bool(cd_mgr and cd_mgr.is_blood_legion_detachment())
        except Exception:
            is_blood_legion = False
        try:
            is_legion_of_excess = bool(cd_mgr and cd_mgr.is_legion_of_excess_detachment())
        except Exception:
            is_legion_of_excess = False
        try:
            is_plague_legion = bool(cd_mgr and cd_mgr.is_plague_legion_detachment())
        except Exception:
            is_plague_legion = False
        try:
            is_scintillating_legion = bool(cd_mgr and cd_mgr.is_scintillating_legion_detachment())
        except Exception:
            is_scintillating_legion = False
        try:
            is_cabal_of_chaos = bool(csm_mgr and csm_mgr.is_cabal_of_chaos())
        except Exception:
            is_cabal_of_chaos = False
        is_chaos_cult = bool(csm_mgr and csm_mgr.is_chaos_cult())
        is_creations_of_bile = bool(csm_mgr and csm_mgr.is_creations_of_bile())
        try:
            is_deceptors = bool(csm_mgr and csm_mgr.is_deceptors())
        except Exception:
            is_deceptors = False
        is_dread_talons = bool(
            csm_mgr and callable(getattr(csm_mgr, "is_dread_talons", None)) and csm_mgr.is_dread_talons()
        )
        try:
            is_nightmare_hunt = bool(csm_mgr and csm_mgr.is_nightmare_hunt())
        except Exception:
            is_nightmare_hunt = False
        try:
            is_pactbound_zealots = bool(csm_mgr and csm_mgr.is_pactbound_zealots())
        except Exception:
            is_pactbound_zealots = False
        try:
            is_renegade_raiders = bool(csm_mgr and csm_mgr.is_renegade_raiders())
        except Exception:
            is_renegade_raiders = False
        try:
            is_renegade_warband = bool(csm_mgr and csm_mgr.is_renegade_warband())
        except Exception:
            is_renegade_warband = False
        try:
            is_veterans_of_the_long_war = bool(csm_mgr and csm_mgr.is_veterans_of_the_long_war())
        except Exception:
            is_veterans_of_the_long_war = False
        is_fellhammer_siege_host = bool(
            csm_mgr and getattr(csm_mgr, "is_fellhammer_siege_host", lambda: False)()
        )
        try:
            is_hurons_marauders = bool(csm_mgr and csm_mgr.is_hurons_marauders())
        except Exception:
            is_hurons_marauders = False
        try:
            is_soulforged_warpack = bool(csm_mgr and csm_mgr.is_soulforged_warpack())
        except Exception:
            is_soulforged_warpack = False
        try:
            is_hearthband = bool(lov_mgr and lov_mgr.is_hearthband())
        except Exception:
            is_hearthband = False
        try:
            is_needgaard_oathband = bool(lov_mgr and lov_mgr.is_needgaard_oathband())
        except Exception:
            is_needgaard_oathband = False
        try:
            is_experimental_prototype_cadre = bool(tau_mgr and tau_mgr.is_experimental_prototype_cadre())
        except Exception:
            is_experimental_prototype_cadre = False
        try:
            is_montka = bool(tau_mgr and tau_mgr.is_montka())
        except Exception:
            is_montka = False
        try:
            is_retaliation_cadre = bool(tau_mgr and tau_mgr.is_retaliation_cadre())
        except Exception:
            is_retaliation_cadre = False
        try:
            is_auxiliary_cadre = bool(tau_mgr and tau_mgr.is_auxiliary_cadre())
        except Exception:
            is_auxiliary_cadre = False
        try:
            is_kroot_hunting_pack = bool(tau_mgr and tau_mgr.is_kroot_hunting_pack())
        except Exception:
            is_kroot_hunting_pack = False
        try:
            is_kauyon = bool(tau_mgr and tau_mgr.is_kauyon())
        except Exception:
            is_kauyon = False
        try:
            is_awakened_dynasty = bool(ne_mgr and ne_mgr.detachment_matches("Awakened Dynasty"))
        except Exception:
            is_awakened_dynasty = False
        try:
            is_coterie_of_conceited = bool(ec_mgr and ec_mgr.is_coterie_of_conceited())
        except Exception:
            is_coterie_of_conceited = False
        try:
            is_carnival_of_excess = bool(ec_mgr and ec_mgr.is_carnival_of_excess())
        except Exception:
            is_carnival_of_excess = False
        try:
            is_court_of_the_phoenician = bool(ec_mgr and ec_mgr.is_court_of_the_phoenician())
        except Exception:
            is_court_of_the_phoenician = False
        try:
            is_mercurial_host = bool(ec_mgr and ec_mgr.is_mercurial_host())
        except Exception:
            is_mercurial_host = False
        try:
            is_rapid_evisceration = bool(ec_mgr and ec_mgr.is_rapid_evisceration())
        except Exception:
            is_rapid_evisceration = False
        try:
            is_slaaneshs_chosen = bool(ec_mgr and ec_mgr.is_slaaneshs_chosen())
        except Exception:
            is_slaaneshs_chosen = False
        is_court_or_mercurial_host = bool(is_court_of_the_phoenician or is_mercurial_host)
        adm_mgr = getattr(army, "adeptus_mechanicus_detachments", None) if army is not None else None
        try:
            is_rad_zone_corps = bool(adm_mgr and adm_mgr.is_rad_zone_corps())
        except Exception:
            is_rad_zone_corps = False
        try:
            is_cohort_cybernetica = bool(adm_mgr and adm_mgr.is_cohort_cybernetica())
        except Exception:
            is_cohort_cybernetica = False
        is_data_psalm_conclave = bool(
            adm_mgr and getattr(adm_mgr, "is_data_psalm_conclave", lambda: False)()
        )
        is_explorator_maniple = bool(
            adm_mgr and getattr(adm_mgr, "is_explorator_maniple", lambda: False)()
        )
        is_haloscreed_battle_clade = bool(
            adm_mgr and getattr(adm_mgr, "is_haloscreed_battle_clade", lambda: False)()
        )
        is_skitarii_hunter_cohort = bool(
            adm_mgr and getattr(adm_mgr, "is_skitarii_hunter_cohort", lambda: False)()
        )
        am_mgr = getattr(army, "astra_militarum_detachments", None) if army is not None else None
        try:
            is_bridgehead_strike = bool(am_mgr and am_mgr.is_bridgehead_strike())
        except Exception:
            is_bridgehead_strike = False
        try:
            is_combined_arms = bool(am_mgr and am_mgr.is_combined_arms())
        except Exception:
            is_combined_arms = False
        try:
            is_grizzled_company = bool(am_mgr and am_mgr.is_grizzled_company())
        except Exception:
            is_grizzled_company = False
        try:
            is_hammer_of_the_emperor = bool(am_mgr and am_mgr.is_hammer_of_the_emperor())
        except Exception:
            is_hammer_of_the_emperor = False
        try:
            is_mechanised_assault = bool(am_mgr and am_mgr.is_mechanised_assault())
        except Exception:
            is_mechanised_assault = False
        try:
            is_recon_element = bool(am_mgr and am_mgr.is_recon_element())
        except Exception:
            is_recon_element = False
        try:
            is_siege_regiment = bool(am_mgr and am_mgr.is_siege_regiment())
        except Exception:
            is_siege_regiment = False
        ck_mgr = getattr(army, "chaos_knights_detachments", None) if army is not None else None
        try:
            is_houndpack_lance = bool(ck_mgr and ck_mgr.is_houndpack_lance())
        except Exception:
            is_houndpack_lance = False
        try:
            is_infernal_lance = bool(ck_mgr and ck_mgr.is_infernal_lance())
        except Exception:
            is_infernal_lance = False
        try:
            is_iconoclast_fiefdom = bool(ck_mgr and ck_mgr.is_iconoclast_fiefdom())
        except Exception:
            is_iconoclast_fiefdom = False
        try:
            is_lords_of_dread = bool(ck_mgr and ck_mgr.is_lords_of_dread())
        except Exception:
            is_lords_of_dread = False
        try:
            is_traitoris_lance = bool(ck_mgr and ck_mgr.is_traitoris_lance())
        except Exception:
            is_traitoris_lance = False
        ik_mgr = getattr(army, "imperial_knights_detachments", None) if army is not None else None
        try:
            is_valourstrike_lance = bool(ik_mgr and ik_mgr.is_valourstrike_lance())
        except Exception:
            is_valourstrike_lance = False
        try:
            is_gate_warden_lance = bool(ik_mgr and ik_mgr.is_gate_warden_lance())
        except Exception:
            is_gate_warden_lance = False
        try:
            is_spearhead_at_arms = bool(ik_mgr and ik_mgr.is_spearhead_at_arms())
        except Exception:
            is_spearhead_at_arms = False
        gk_mgr = getattr(army, "grey_knights_detachments", None) if army is not None else None
        try:
            is_brotherhood_strike = bool(gk_mgr and gk_mgr.is_brotherhood_strike())
        except Exception:
            is_brotherhood_strike = False
        try:
            is_warpbane_task_force = bool(gk_mgr and gk_mgr.is_warpbane_task_force())
        except Exception:
            is_warpbane_task_force = False
        try:
            is_augurium_task_force = bool(gk_mgr and gk_mgr.is_augurium_task_force())
        except Exception:
            is_augurium_task_force = False
        try:
            is_hallowed_conclave = bool(gk_mgr and gk_mgr.is_hallowed_conclave())
        except Exception:
            is_hallowed_conclave = False
        ia_mgr = getattr(army, "imperial_agents_detachments", None) if army is not None else None
        try:
            is_veiled_blade_elimination_force = bool(ia_mgr and ia_mgr.is_veiled_blade_elimination_force())
        except Exception:
            is_veiled_blade_elimination_force = False
        is_ordo_malleus_daemon_hunters_fn = (
            getattr(ia_mgr, "is_ordo_malleus_daemon_hunters", None) if ia_mgr is not None else None
        )
        is_ordo_malleus_daemon_hunters = bool(
            callable(is_ordo_malleus_daemon_hunters_fn) and is_ordo_malleus_daemon_hunters_fn()
        )
        is_imperialis_fleet_fn = getattr(ia_mgr, "is_imperialis_fleet", None) if ia_mgr is not None else None
        is_imperialis_fleet = bool(callable(is_imperialis_fleet_fn) and is_imperialis_fleet_fn())
        dru_mgr = getattr(army, "drukhari_detachments", None) if army is not None else None
        try:
            is_covenite_coterie = bool(dru_mgr and dru_mgr.is_covenite_coterie())
        except Exception:
            is_covenite_coterie = False
        try:
            is_skysplinter_assault = bool(dru_mgr and dru_mgr.is_skysplinter_assault())
        except Exception:
            is_skysplinter_assault = False
        try:
            is_spectacle_of_spite = bool(dru_mgr and dru_mgr.is_spectacle_of_spite())
        except Exception:
            is_spectacle_of_spite = False
        try:
            is_kabalite_cartel = bool(dru_mgr and dru_mgr.is_kabalite_cartel())
        except Exception:
            is_kabalite_cartel = False
        try:
            is_reapers_wager = bool(dru_mgr and dru_mgr.is_reapers_wager())
        except Exception:
            is_reapers_wager = False
        is_realspace_raiders_fn = getattr(dru_mgr, "is_realspace_raiders", None) if dru_mgr is not None else None
        is_realspace_raiders = bool(callable(is_realspace_raiders_fn) and is_realspace_raiders_fn())
        ts_mgr = getattr(army, "thousand_sons_detachments", None) if army is not None else None
        gsc_mgr = getattr(army, "genestealer_cults_detachments", None) if army is not None else None
        tyr_mgr = getattr(army, "tyranids_detachments", None) if army is not None else None
        try:
            is_grand_coven = bool(ts_mgr and ts_mgr.is_grand_coven())
        except Exception:
            is_grand_coven = False
        try:
            is_rubricae_phalanx = bool(ts_mgr and ts_mgr.is_rubricae_phalanx())
        except Exception:
            is_rubricae_phalanx = False
        try:
            is_changehost_of_deceit = bool(ts_mgr and ts_mgr.is_changehost_of_deceit())
        except Exception:
            is_changehost_of_deceit = False
        try:
            is_hexwarp_thrallband = bool(ts_mgr and ts_mgr.is_hexwarp_thrallband())
        except Exception:
            is_hexwarp_thrallband = False
        try:
            is_warpforged_cabal = bool(ts_mgr and ts_mgr.is_warpforged_cabal())
        except Exception:
            is_warpforged_cabal = False
        try:
            is_warpmeld_pact = bool(ts_mgr and ts_mgr.is_warpmeld_pact())
        except Exception:
            is_warpmeld_pact = False
        try:
            is_host_of_ascension = bool(gsc_mgr and gsc_mgr.is_host_of_ascension())
        except Exception:
            is_host_of_ascension = False
        try:
            is_brood_brother_auxilia = bool(gsc_mgr and gsc_mgr.is_brood_brother_auxilia())
        except Exception:
            is_brood_brother_auxilia = False
        try:
            is_assimilation_swarm = bool(tyr_mgr and tyr_mgr.is_assimilation_swarm())
        except Exception:
            is_assimilation_swarm = False
        try:
            is_crusher_stampede = bool(tyr_mgr and tyr_mgr.is_crusher_stampede())
        except Exception:
            is_crusher_stampede = False
        try:
            is_subterranean_assault = bool(tyr_mgr and tyr_mgr.is_subterranean_assault())
        except Exception:
            is_subterranean_assault = False
        try:
            is_synaptic_nexus = bool(tyr_mgr and tyr_mgr.is_synaptic_nexus())
        except Exception:
            is_synaptic_nexus = False

        bearer = None
        bearer_id = ""
        get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
        if callable(get_bearer):
            bearer = get_bearer()
            if bearer is not None:
                bearer_id = str(getattr(bearer, "id", getattr(bearer, "_id", "")) or "")

        if name == "veil of darkness" or enh_id == "000008372002":
            if not is_awakened_dynasty:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            ability_key = str(params.get("once_per_battle_key", "veil_of_darkness") or "veil_of_darkness").strip().lower()
            if not ability_key:
                ability_key = "veil_of_darkness"
            trigger_phase = str(params.get("trigger_phase", "OPPONENT_TURN_END") or "OPPONENT_TURN_END").strip().upper()
            if not trigger_phase:
                trigger_phase = "OPPONENT_TURN_END"
            source_name = str(getattr(desc, "name", "") or "Veil of Darkness").strip() or "Veil of Darkness"
            unit.special_rules["enhancement_veil_of_darkness"] = True
            unit.special_rules["enhancement_veil_of_darkness_source"] = source_name
            unit.special_rules["enhancement_veil_of_darkness_ability_key"] = ability_key
            unit.special_rules["enhancement_veil_of_darkness_trigger_phase"] = trigger_phase
            unit.special_rules["enhancement_veil_of_darkness_once_per_battle"] = bool(
                params.get("once_per_battle", True)
            )
            unit.special_rules["enhancement_veil_of_darkness_requires_not_engagement_range"] = bool(
                params.get("requires_not_engagement_range", True)
            )
            unit.special_rules["enhancement_veil_of_darkness_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_veil_of_darkness_return_as_deep_strike"] = bool(
                params.get("return_as_deep_strike", True)
            )
            unit.special_rules["enhancement_veil_of_darkness_must_arrive_next_movement_phase"] = bool(
                params.get("must_arrive_next_movement_phase", True)
            )
            unit.special_rules["enhancement_veil_of_darkness_return_setup_min_enemy_distance_horiz"] = float(
                max(
                    0.0,
                    _coerce_float(
                        params.get("return_setup_min_enemy_distance_horiz", 9.0),
                        default=9.0,
                    ),
                )
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_veil_of_darkness_bearer_model_id"] = bearer_id
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("opponent_turn_strategic_reserves_ability", None)

        if name == "prowling agitant" or enh_id == "000009067002":
            if not is_host_of_ascension:
                return
            unit.special_rules["enhancement_prowling_agitant"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "a chink in their armour" or enh_id == "000009067003":
            if not is_host_of_ascension:
                return
            unit.special_rules["enhancement_a_chink_in_their_armour"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "our time is nigh" or enh_id == "000009067004":
            if not is_host_of_ascension:
                return
            unit.special_rules["enhancement_our_time_is_nigh"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                charge_bonus = int(params.get("charge_roll_bonus", 2) or 2)
            except Exception:
                charge_bonus = 2
            once_key = str(params.get("once_per_battle_key", "our_time_is_nigh") or "our_time_is_nigh").strip().lower()
            unit.special_rules["enhancement_our_time_is_nigh_bonus"] = int(max(0, charge_bonus))
            unit.special_rules["enhancement_our_time_is_nigh_once_key"] = once_key
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "assassination edict" or enh_id == "000009067005":
            if not is_host_of_ascension:
                return
            unit.special_rules["enhancement_assassination_edict"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "adaptive reprisal" or enh_id == "000009084003":
            if not is_brood_brother_auxilia:
                return
            unit.special_rules["enhancement_adaptive_reprisal"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                aura_range = float(params.get("range", 9.0) or 9.0)
            except Exception:
                aura_range = 9.0
            if aura_range <= 0.0:
                aura_range = 9.0
            usage_key = str(
                params.get("once_per_turn_key", "ADAPTIVE_REPRISAL_HEROIC_INTERVENTION")
                or "ADAPTIVE_REPRISAL_HEROIC_INTERVENTION"
            ).strip().upper()
            if not usage_key:
                usage_key = "ADAPTIVE_REPRISAL_HEROIC_INTERVENTION"
            unit.special_rules["enhancement_adaptive_reprisal_range"] = float(aura_range)
            unit.special_rules["enhancement_adaptive_reprisal_usage_key"] = usage_key
            unit.special_rules["enhancement_adaptive_reprisal_source"] = "Adaptive Reprisal"
            unit.special_rules["enhancement_adaptive_reprisal_requires_bearer_on_battlefield"] = bool(
                params.get("requires_bearer_on_battlefield", True)
            )
            configured_stratagems = tuple(
                str(v or "").strip().upper()
                for v in tuple(params.get("stratagem_names", ("HEROIC INTERVENTION",)) or ("HEROIC INTERVENTION",))
                if str(v or "").strip()
            )
            if not configured_stratagems:
                configured_stratagems = ("HEROIC INTERVENTION",)
            unit.special_rules["enhancement_adaptive_reprisal_stratagems"] = configured_stratagems
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "supernova launcher" or enh_id == "000009983002":
            if not is_experimental_prototype_cadre:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            _apply_selected_ranged_weapon_bonus_enhancement(
                unit,
                special_rule_flag="enhancement_supernova_launcher",
                descriptor_params=params,
                bearer=bearer,
                bearer_id=bearer_id,
                default_weapon_name="airbursting fragmentation projector",
                default_attacks_bonus=0,
                default_melta_bonus=0,
                default_strength_bonus=3,
                default_ap_bonus=1,
                default_damage_bonus=1,
                source_name="Supernova Launcher",
            )

        if name == "thermoneutronic projector" or enh_id == "000009983003":
            if not is_experimental_prototype_cadre:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            _apply_selected_ranged_weapon_bonus_enhancement(
                unit,
                special_rule_flag="enhancement_thermoneutronic_projector",
                descriptor_params=params,
                bearer=bearer,
                bearer_id=bearer_id,
                default_weapon_name="t'au flamer",
                default_attacks_bonus=0,
                default_melta_bonus=0,
                default_strength_bonus=2,
                default_ap_bonus=1,
                default_damage_bonus=1,
                source_name="Thermoneutronic Projector",
            )

        if name == "plasma accelerator rifle" or enh_id == "000009983004":
            if not is_experimental_prototype_cadre:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            _apply_selected_ranged_weapon_bonus_enhancement(
                unit,
                special_rule_flag="enhancement_plasma_accelerator_rifle",
                descriptor_params=params,
                bearer=bearer,
                bearer_id=bearer_id,
                default_weapon_name="plasma rifle",
                default_attacks_bonus=1,
                default_melta_bonus=0,
                default_strength_bonus=2,
                default_ap_bonus=1,
                default_damage_bonus=1,
                source_name="Plasma Accelerator Rifle",
            )

        if name == "fusion blades" or enh_id == "000009983005":
            if not is_experimental_prototype_cadre:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            _apply_selected_ranged_weapon_bonus_enhancement(
                unit,
                special_rule_flag="enhancement_fusion_blades",
                descriptor_params=params,
                bearer=bearer,
                bearer_id=bearer_id,
                default_weapon_name="fusion blaster",
                default_attacks_bonus=1,
                default_melta_bonus=4,
                default_strength_bonus=3,
                default_ap_bonus=0,
                default_damage_bonus=0,
                source_name="Fusion Blades",
            )

        if name == "coordinated exploitation" or enh_id == "000008811002":
            if not is_montka:
                return
            unit.special_rules["enhancement_coordinated_exploitation"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                sustained_value = int(params.get("sustained_hits_value", 1) or 1)
            except Exception:
                sustained_value = 1
            unit.special_rules["enhancement_coordinated_exploitation_sustained_hits_value"] = int(max(1, sustained_value))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "exemplar of the mont'ka" or enh_id == "000008811003":
            if not is_montka:
                return
            unit.special_rules["enhancement_exemplar_of_montka"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "strategic conqueror" or enh_id == "000008811004":
            if not is_montka:
                return
            unit.special_rules["enhancement_strategic_conqueror"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                oc_bonus = int(params.get("objective_control_bonus", 1) or 1)
            except Exception:
                oc_bonus = 1
            unit.special_rules["enhancement_strategic_conqueror_oc_bonus"] = int(max(0, oc_bonus))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "strike swiftly" or enh_id == "000008811005":
            if not is_montka:
                return
            unit.special_rules["enhancement_strike_swiftly"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                scout_distance = int(params.get("scouts_distance", 6) or 6)
            except Exception:
                scout_distance = 6
            try:
                selection_range = float(params.get("selection_range", 6.0) or 6.0)
            except Exception:
                selection_range = 6.0
            unit.special_rules["enhancement_strike_swiftly_scouts_distance"] = int(max(0, scout_distance))
            unit.special_rules["enhancement_strike_swiftly_selection_range"] = float(max(0.0, selection_range))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "starflare ignition system" or enh_id == "000008815005":
            if not is_retaliation_cadre:
                return
            unit.special_rules["enhancement_starflare_ignition_system"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(params.get("source_name", "") or str(getattr(self, "name", "") or "Starflare Ignition System")).strip()
            if not source:
                source = "Starflare Ignition System"
            ability_key = str(params.get("ability_key", "starflare_ignition_system") or "starflare_ignition_system").strip().lower()
            if not ability_key:
                ability_key = "starflare_ignition_system"
            trigger_phase = str(params.get("trigger_phase", "OPPONENT_TURN_END") or "OPPONENT_TURN_END").strip().upper()
            if not trigger_phase:
                trigger_phase = "OPPONENT_TURN_END"
            unit.special_rules["enhancement_starflare_ignition_system_source"] = source
            unit.special_rules["enhancement_starflare_ignition_system_ability_key"] = ability_key
            unit.special_rules["enhancement_starflare_ignition_system_trigger_phase"] = trigger_phase
            unit.special_rules["enhancement_starflare_ignition_system_requires_not_engagement_range"] = bool(
                params.get("requires_not_engagement_range", True)
            )
            unit.special_rules["enhancement_starflare_ignition_system_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_starflare_ignition_system_once_per_battle"] = bool(
                params.get("once_per_battle", False)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_starflare_ignition_system_bearer_model_id"] = bearer_id
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("opponent_turn_strategic_reserves_ability", None)

        if name == "internal grenade racks" or enh_id == "000008815002":
            if not is_retaliation_cadre:
                return
            unit.special_rules["enhancement_internal_grenade_racks"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_internal_grenade_racks_source"] = "Internal Grenade Racks"
            unit.special_rules["enhancement_internal_grenade_racks_dice"] = _coerce_int(
                params.get("dice", 6) or 6,
                default=6,
            )
            unit.special_rules["enhancement_internal_grenade_racks_threshold"] = _coerce_int(
                params.get("threshold", 4) or 4,
                default=4,
            )
            unit.special_rules["enhancement_internal_grenade_racks_mortal_per_success"] = _coerce_int(
                params.get("mortal_per_success", 1) or 1,
                default=1,
            )
            move_types = sorted(
                {
                    str(move_type or "").strip().lower()
                    for move_type in list(params.get("move_types", ["move"]) or ["move"])
                    if str(move_type or "").strip()
                }
                or {"move"}
            )
            unit.special_rules["enhancement_internal_grenade_racks_move_types"] = list(move_types)
            unit.special_rules["enhancement_internal_grenade_racks_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_internal_grenade_racks_optional"] = bool(params.get("optional", True))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_internal_grenade_racks_bearer_model_id"] = bearer_id
            if bearer is not None:
                keywords = list(getattr(bearer, "keywords", []) or [])
                if "GRENADES" not in {str(keyword or "").strip().upper() for keyword in keywords}:
                    keywords.append("GRENADES")
                    bearer.keywords = keywords

        if name == "prototype weapon system" or enh_id == "000008815003":
            if not is_retaliation_cadre:
                return
            unit.special_rules["enhancement_prototype_weapon_system"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_prototype_weapon_system_source"] = "Prototype Weapon System"
            ability_key = str(params.get("ability_key", "prototype_weapon_system") or "prototype_weapon_system").strip().lower()
            if not ability_key:
                ability_key = "prototype_weapon_system"
            unit.special_rules["enhancement_prototype_weapon_system_ability_key"] = ability_key
            keyword_options = [
                str(keyword or "").strip().upper()
                for keyword in list(params.get("keyword_options", ["LETHAL HITS", "SUSTAINED HITS 1"]) or [])
                if str(keyword or "").strip()
            ]
            if not keyword_options:
                keyword_options = ["LETHAL HITS", "SUSTAINED HITS 1"]
            unit.special_rules["enhancement_prototype_weapon_system_keyword_options"] = list(keyword_options)
            unit.special_rules["enhancement_prototype_weapon_system_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_prototype_weapon_system_bearer_model_id"] = bearer_id

        if name == "puretide engram neurochip" or enh_id == "000008815004":
            if not is_retaliation_cadre:
                return
            unit.special_rules["enhancement_puretide_engram_neurochip"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            roll_min = _coerce_int(params.get("roll_min", 4) or 4, default=4)
            cp_gain = _coerce_int(params.get("cp_gain", 1) or 1, default=1)
            source_name = "Puretide Engram Neurochip"
            unit.special_rules["enhancement_puretide_engram_neurochip_source"] = source_name
            specs = list(unit.special_rules.get("stratagem_target_cp_refund_specs", []) or [])
            spec = {
                "roll_min": int(max(2, roll_min)),
                "cp_gain": int(max(1, cp_gain)),
                "name": source_name,
                "description": str(getattr(self, "description", "") or ""),
            }
            if bearer_id:
                spec["source_model_id"] = bearer_id
            dedupe_key = (
                int(spec.get("roll_min", 0) or 0),
                int(spec.get("cp_gain", 0) or 0),
                str(spec.get("name", "") or "").strip().lower(),
                str(spec.get("source_model_id", "") or "").strip(),
            )
            seen_spec_keys = set()
            deduped_specs: list[dict] = []
            for existing in specs:
                key = (
                    int(existing.get("roll_min", 0) or 0),
                    int(existing.get("cp_gain", 0) or 0),
                    str(existing.get("name", "") or "").strip().lower(),
                    str(existing.get("source_model_id", "") or "").strip(),
                )
                if key in seen_spec_keys:
                    continue
                seen_spec_keys.add(key)
                deduped_specs.append(existing)
            if dedupe_key not in seen_spec_keys:
                deduped_specs.append(spec)
            unit.special_rules["stratagem_target_cp_refund_specs"] = deduped_specs
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_puretide_engram_neurochip_bearer_model_id"] = bearer_id

        if name == "radial suffusion" or enh_id == "000008385002":
            if not is_rad_zone_corps:
                return
            unit.special_rules["enhancement_radial_suffusion"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "malphonic susurrus" or enh_id == "000008385003":
            if not is_rad_zone_corps:
                return
            unit.special_rules["enhancement_malphonic_susurrus"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "peerless eradicator" or enh_id == "000008385004":
            if not is_rad_zone_corps:
                return
            unit.special_rules["enhancement_peerless_eradicator"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "autoclavic denunciation" or enh_id == "000008385005":
            if not is_rad_zone_corps:
                return
            unit.special_rules["enhancement_autoclavic_denunciation"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if enh_id == "000008560002" or (name == "cantic thrallnet" and is_skitarii_hunter_cohort):
            if not is_skitarii_hunter_cohort:
                return
            unit.special_rules["enhancement_skitarii_cantic_thrallnet"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                range_inches = float(params.get("range", 12.0) or 12.0)
            except (TypeError, ValueError):
                range_inches = 12.0
            required_target_keywords = [
                str(kw or "").strip().upper()
                for kw in list(params.get("required_target_keywords", ("SKITARII",)) or ("SKITARII",))
                if str(kw or "").strip()
            ]
            if not required_target_keywords:
                required_target_keywords = ["SKITARII"]
            unit.special_rules["enhancement_skitarii_cantic_thrallnet_range"] = float(max(0.0, range_inches))
            unit.special_rules["enhancement_skitarii_cantic_thrallnet_required_target_keywords"] = list(required_target_keywords)
            unit.special_rules["enhancement_skitarii_cantic_thrallnet_optional"] = bool(params.get("optional", True))
            unit.special_rules["enhancement_skitarii_cantic_thrallnet_source"] = "Cantic Thrallnet"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_skitarii_cantic_thrallnet_bearer_model_id"] = bearer_id

        if enh_id == "000008560003" or (name == "clandestine infiltrator" and is_skitarii_hunter_cohort):
            if not is_skitarii_hunter_cohort:
                return
            unit.special_rules["enhancement_skitarii_clandestine_infiltrator"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            scout_distance = _coerce_int(params.get("scouts_distance", 6) or 6, default=6)
            scout_distance = int(max(0, scout_distance))
            unit.special_rules["enhancement_scout_distance"] = max(
                int(unit.special_rules.get("enhancement_scout_distance", 0) or 0),
                int(scout_distance),
            )
            unit.special_rules["enhancement_skitarii_clandestine_infiltrator_scout_distance"] = int(scout_distance)
            unit.special_rules["enhancement_skitarii_clandestine_infiltrator_source"] = "Clandestine Infiltrator"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_skitarii_clandestine_infiltrator_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if enh_id == "000008560004" or (name == "veiled hunter" and is_skitarii_hunter_cohort):
            if not is_skitarii_hunter_cohort:
                return
            unit.special_rules["enhancement_skitarii_veiled_hunter"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            max_units = _coerce_int(params.get("max_units", 3) or 3, default=3)
            can_place_in_reserves = bool(params.get("can_place_in_reserves", True))
            raw_filters = list(params.get("redeploy_filters", ("SKITARII", "INFANTRY")) or ())
            redeploy_filters: list[str] = []
            for keyword in raw_filters:
                norm_keyword = str(keyword or "").strip().upper()
                if not norm_keyword or norm_keyword in redeploy_filters:
                    continue
                redeploy_filters.append(norm_keyword)
            if not redeploy_filters:
                redeploy_filters = ["SKITARII", "INFANTRY"]
            unit.special_rules["enhancement_skitarii_veiled_hunter_max_units"] = int(max(1, max_units))
            unit.special_rules["enhancement_skitarii_veiled_hunter_can_place_in_reserves"] = bool(can_place_in_reserves)
            unit.special_rules["enhancement_skitarii_veiled_hunter_filters"] = list(redeploy_filters)
            unit.special_rules["enhancement_skitarii_veiled_hunter_source"] = "Veiled Hunter"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_skitarii_veiled_hunter_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if enh_id == "000008560005" or (name == "battle-sphere uplink" and is_skitarii_hunter_cohort):
            if not is_skitarii_hunter_cohort:
                return
            unit.special_rules["enhancement_skitarii_battle_sphere_uplink"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            move_range = _coerce_int(params.get("move_range", 6) or 6, default=6)
            unit.special_rules["enhancement_skitarii_battle_sphere_uplink_move_range"] = int(max(1, move_range))
            unit.special_rules["enhancement_skitarii_battle_sphere_uplink_requires_not_engagement_range"] = bool(
                params.get("requires_not_engagement_range", True)
            )
            unit.special_rules["enhancement_skitarii_battle_sphere_uplink_source"] = "Battle-sphere Uplink"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_skitarii_battle_sphere_uplink_bearer_model_id"] = bearer_id

        if name == "necromechanic" or enh_id == "000008572002":
            if not is_cohort_cybernetica:
                return
            unit.special_rules["enhancement_necromechanic"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                range_inches = int(float(params.get("range", 12.0) or 12.0))
            except Exception:
                range_inches = 12
            usage = str(params.get("usage", "battle_round") or "battle_round").strip().lower()
            if usage not in {"battle_round", "battle"}:
                usage = "battle_round"
            unit.special_rules["enhancement_necromechanic_range"] = int(max(1, range_inches))
            unit.special_rules["enhancement_necromechanic_usage"] = usage
            unit.special_rules["enhancement_necromechanic_source"] = "Necromechanic"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_necromechanic_bearer_model_id"] = bearer_id

        if name == "lord of machines" or enh_id == "000008572003":
            if not is_cohort_cybernetica:
                return
            unit.special_rules["enhancement_lord_of_machines"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                range_inches = float(params.get("range", 12.0) or 12.0)
            except Exception:
                range_inches = 12.0
            required_keywords = [
                str(kw or "").strip().upper()
                for kw in list(params.get("required_target_keywords", ("VEHICLE",)) or ("VEHICLE",))
                if str(kw or "").strip()
            ]
            if not required_keywords:
                required_keywords = ["VEHICLE"]
            excluded_keywords = [
                str(kw or "").strip().upper()
                for kw in list(params.get("excluded_target_keywords", ()) or ())
                if str(kw or "").strip()
            ]
            resolution_mode = str(params.get("resolution_mode", "leadership_test") or "leadership_test").strip().lower()
            if not resolution_mode:
                resolution_mode = "leadership_test"
            unit.special_rules["enhancement_lord_of_machines_range"] = float(max(0.0, range_inches))
            unit.special_rules["enhancement_lord_of_machines_required_target_keywords"] = list(required_keywords)
            unit.special_rules["enhancement_lord_of_machines_excluded_target_keywords"] = list(excluded_keywords)
            unit.special_rules["enhancement_lord_of_machines_resolution_mode"] = resolution_mode
            unit.special_rules["enhancement_lord_of_machines_source"] = "Lord of Machines"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_lord_of_machines_bearer_model_id"] = bearer_id
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache_key = f"model_start_opponent_shooting_phase_disrupt:{bearer_id}"
                cache.pop(cache_key, None)

        if name == "emotionless clarity" or enh_id == "000008572004":
            if not is_cohort_cybernetica:
                return
            unit.special_rules["enhancement_emotionless_clarity"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                range_inches = int(float(params.get("range", 12.0) or 12.0))
            except Exception:
                range_inches = 12
            usage = str(params.get("usage", "turn") or "turn").strip().lower()
            if usage not in {"turn", "battle_round"}:
                usage = "turn"
            unit.special_rules["enhancement_emotionless_clarity_range"] = int(max(1, range_inches))
            unit.special_rules["enhancement_emotionless_clarity_usage"] = usage
            unit.special_rules["enhancement_emotionless_clarity_source"] = "Emotionless Clarity"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_emotionless_clarity_bearer_model_id"] = bearer_id

        if name == "arch-negator" or enh_id == "000008572005":
            if not is_cohort_cybernetica:
                return
            unit.special_rules["enhancement_arch_negator"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                anti_vehicle = int(params.get("anti_vehicle", 4) or 4)
            except Exception:
                anti_vehicle = 4
            unit.special_rules["enhancement_arch_negator_anti_vehicle"] = int(max(2, anti_vehicle))
            unit.special_rules["enhancement_arch_negator_source"] = "Arch-negator"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_arch_negator_bearer_model_id"] = bearer_id

        if name == "mechanicus locum" or enh_id == "000008564002":
            if not is_data_psalm_conclave:
                return
            unit.special_rules["enhancement_mechanicus_locum"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                range_inches = int(float(params.get("range", 12.0) or 12.0))
            except (TypeError, ValueError):
                range_inches = 12
            keyword_phrase = str(params.get("keyword_phrase", "CULT MECHANICUS") or "CULT MECHANICUS").strip()
            once_key = str(params.get("once_per_battle_key", "mechanicus_locum") or "mechanicus_locum").strip().lower()
            if not once_key:
                once_key = "mechanicus_locum"
            unit.special_rules["enhancement_mechanicus_locum_range"] = int(max(1, range_inches))
            unit.special_rules["enhancement_mechanicus_locum_keyword_phrase"] = keyword_phrase or "CULT MECHANICUS"
            unit.special_rules["enhancement_mechanicus_locum_once_key"] = once_key
            unit.special_rules["enhancement_mechanicus_locum_source"] = "Mechanicus Locum"
            unit.special_rules["enhancement_mechanicus_locum_bearer_leadership"] = 6
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_mechanicus_locum_bearer_model_id"] = bearer_id
            get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
            bearer_model = get_bearer() if callable(get_bearer) else None
            if bearer_model is not None:
                bearer_model.leadership = int(unit.special_rules.get("enhancement_mechanicus_locum_bearer_leadership", 6) or 6)
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("unit_start_any_phase_clear_battleshock_specs", None)

        if name == "mantle of the gnosticarch" or enh_id == "000008564003":
            if not is_data_psalm_conclave:
                return
            unit.special_rules["enhancement_mantle_of_the_gnosticarch"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                set_damage_to = int(params.get("set_damage_to", 1) or 1)
            except (TypeError, ValueError):
                set_damage_to = 1
            unit.special_rules["enhancement_mantle_of_the_gnosticarch_set_damage_to"] = int(max(0, set_damage_to))
            unit.special_rules["enhancement_mantle_of_the_gnosticarch_source"] = "Mantle of the Gnosticarch"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_mantle_of_the_gnosticarch_bearer_model_id"] = bearer_id

        if name == "data-blessed autosermon" or enh_id == "000008564004":
            if not is_data_psalm_conclave:
                return
            unit.special_rules["enhancement_data_blessed_autosermon"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            once_key = str(params.get("once_per_battle_key", "data_blessed_autosermon") or "data_blessed_autosermon").strip().lower()
            if not once_key:
                once_key = "data_blessed_autosermon"
            unit.special_rules["enhancement_data_blessed_autosermon_once_key"] = once_key
            unit.special_rules["enhancement_data_blessed_autosermon_source"] = "Data-blessed Autosermon"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_data_blessed_autosermon_bearer_model_id"] = bearer_id

        if name == "temporcopia" or enh_id == "000008564005":
            if not is_data_psalm_conclave:
                return
            unit.special_rules["enhancement_temporcopia"] = True
            unit.special_rules["enhancement_temporcopia_source"] = "Temporcopia"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_temporcopia_bearer_model_id"] = bearer_id

        if enh_id == "000008568002" or (name == "magos" and is_explorator_maniple):
            if not is_explorator_maniple:
                return
            unit.special_rules["enhancement_explorator_magos"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                roll_min = int(params.get("roll_min", 4) or 4)
            except (TypeError, ValueError):
                roll_min = 4
            try:
                cp_gain = int(params.get("cp_gain", 1) or 1)
            except (TypeError, ValueError):
                cp_gain = 1
            unit.special_rules["enhancement_explorator_magos_roll_min"] = int(max(2, min(6, roll_min)))
            unit.special_rules["enhancement_explorator_magos_cp_gain"] = int(max(0, cp_gain))
            unit.special_rules["enhancement_explorator_magos_source"] = "Magos"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_explorator_magos_bearer_model_id"] = bearer_id

        if enh_id == "000008568003" or (name == "genetor" and is_explorator_maniple):
            if not is_explorator_maniple:
                return
            unit.special_rules["enhancement_explorator_genetor"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                inv_value = int(params.get("invulnerable_save", 4) or 4)
            except (TypeError, ValueError):
                inv_value = 4
            unit.special_rules["enhancement_explorator_genetor_invulnerable_save"] = int(max(2, min(7, inv_value)))
            unit.special_rules["enhancement_explorator_genetor_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            unit.special_rules["enhancement_explorator_genetor_requires_unit_within_acquisition_objective"] = bool(
                params.get("requires_unit_within_acquisition_objective", True)
            )
            unit.special_rules["enhancement_explorator_genetor_source"] = "Genetor"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_explorator_genetor_bearer_model_id"] = bearer_id

        if enh_id == "000008568004" or (name == "logis" and is_explorator_maniple):
            if not is_explorator_maniple:
                return
            unit.special_rules["enhancement_explorator_logis"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                hit_bonus = int(params.get("hit_roll_bonus", 1) or 1)
            except (TypeError, ValueError):
                hit_bonus = 1
            unit.special_rules["enhancement_explorator_logis_hit_bonus"] = int(max(0, hit_bonus))
            unit.special_rules["enhancement_explorator_logis_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            unit.special_rules["enhancement_explorator_logis_requires_target_within_acquisition_objective"] = bool(
                params.get("requires_target_within_acquisition_objective", True)
            )
            unit.special_rules["enhancement_explorator_logis_source"] = "Logis"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_explorator_logis_bearer_model_id"] = bearer_id

        if enh_id == "000008568005" or (name == "artisan" and is_explorator_maniple):
            if not is_explorator_maniple:
                return
            unit.special_rules["enhancement_explorator_artisan"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            usage_limit = str(params.get("usage_limit", "phase") or "phase").strip().lower()
            if usage_limit not in {"phase", "turn"}:
                usage_limit = "phase"
            allowed_roll_types = tuple(
                sorted(
                    {
                        str(v or "").strip().lower()
                        for v in list(params.get("allowed_roll_types", ("hit", "wound", "save")) or ("hit", "wound", "save"))
                        if str(v or "").strip().lower() in {"hit", "wound", "save", "damage"}
                    }
                )
            )
            if not allowed_roll_types:
                allowed_roll_types = ("hit", "wound", "save")
            unit.special_rules["enhancement_explorator_artisan_usage"] = usage_limit
            unit.special_rules["enhancement_explorator_artisan_allowed_roll_types"] = allowed_roll_types
            unit.special_rules["enhancement_explorator_artisan_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            unit.special_rules["enhancement_explorator_artisan_requires_unit_within_acquisition_objective"] = bool(
                params.get("requires_unit_within_acquisition_objective", True)
            )
            unit.special_rules["enhancement_explorator_artisan_source"] = "Artisan"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_explorator_artisan_bearer_model_id"] = bearer_id
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("leading_unmodified_six_specs", None)

        if enh_id == "000009745002" or (name == "transoracular dyad wafers" and is_haloscreed_battle_clade):
            if not is_haloscreed_battle_clade:
                return
            unit.special_rules["enhancement_haloscreed_transoracular_dyad_wafers"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_haloscreed_transoracular_requires_bearer_attached_to_kastelan_robots"] = bool(
                params.get("requires_bearer_attached_to_kastelan_robots", True)
            )
            unit.special_rules["enhancement_haloscreed_transoracular_source"] = "Transoracular Dyad Wafers"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_haloscreed_transoracular_bearer_model_id"] = bearer_id

        if enh_id == "000009745003" or (name == "cognitive reinforcement" and is_haloscreed_battle_clade):
            if not is_haloscreed_battle_clade:
                return
            unit.special_rules["enhancement_haloscreed_cognitive_reinforcement"] = True
            unit.special_rules["enhancement_haloscreed_cognitive_reinforcement_source"] = "Cognitive Reinforcement"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_haloscreed_cognitive_reinforcement_bearer_model_id"] = bearer_id

        if enh_id == "000009745004" or (name == "sanctified ordnance" and is_haloscreed_battle_clade):
            if not is_haloscreed_battle_clade:
                return
            unit.special_rules["enhancement_haloscreed_sanctified_ordnance"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                range_bonus = int(params.get("range_bonus", 6) or 6)
            except (TypeError, ValueError):
                range_bonus = 6
            unit.special_rules["enhancement_haloscreed_sanctified_ordnance_range_bonus"] = int(max(0, range_bonus))
            unit.special_rules["enhancement_haloscreed_sanctified_ordnance_hazardous_reroll"] = bool(
                params.get("hazardous_reroll", True)
            )
            unit.special_rules["enhancement_haloscreed_sanctified_ordnance_source"] = "Sanctified Ordnance"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_haloscreed_sanctified_ordnance_bearer_model_id"] = bearer_id

        if enh_id == "000009745005" or (name == "inloaded lethality" and is_haloscreed_battle_clade):
            if not is_haloscreed_battle_clade:
                return
            unit.special_rules["enhancement_haloscreed_inloaded_lethality"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                attacks_bonus = int(params.get("melee_attacks_bonus", 3) or 3)
            except (TypeError, ValueError):
                attacks_bonus = 3
            try:
                damage_bonus = int(params.get("melee_damage_bonus", 1) or 1)
            except (TypeError, ValueError):
                damage_bonus = 1
            unit.special_rules["enhancement_haloscreed_inloaded_lethality_attacks_bonus"] = int(max(0, attacks_bonus))
            unit.special_rules["enhancement_haloscreed_inloaded_lethality_damage_bonus"] = int(max(0, damage_bonus))
            unit.special_rules["enhancement_haloscreed_inloaded_lethality_source"] = "Inloaded Lethality"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_haloscreed_inloaded_lethality_bearer_model_id"] = bearer_id

        if name == "decoy targets" or enh_id == "000009757002":
            if not is_veiled_blade_elimination_force:
                return
            unit.special_rules["enhancement_decoy_targets"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                max_uses = int(params.get("max_uses", 2) or 2)
            except Exception:
                max_uses = 2
            try:
                per_round_limit = int(params.get("per_battle_round_limit", 1) or 1)
            except Exception:
                per_round_limit = 1
            unit.special_rules["enhancement_decoy_targets_max_uses"] = int(max(1, max_uses))
            unit.special_rules["enhancement_decoy_targets_per_battle_round_limit"] = int(max(1, per_round_limit))
            if "enhancement_decoy_targets_used_count" not in unit.special_rules:
                unit.special_rules["enhancement_decoy_targets_used_count"] = 0
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "esoteric explosives" or enh_id == "000009757003":
            if not is_veiled_blade_elimination_force:
                return
            unit.special_rules["enhancement_esoteric_explosives"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                threshold = int(params.get("grenade_mortal_threshold", 3) or 3)
            except Exception:
                threshold = 3
            unit.special_rules["enhancement_esoteric_explosives_grenade_mortal_threshold"] = int(max(2, threshold))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "intraneural biotech" or enh_id == "000009757004":
            if not is_veiled_blade_elimination_force:
                return
            unit.special_rules["enhancement_intraneural_biotech"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            stratagems = [
                str(v or "").strip().upper()
                for v in list(params.get("stratagems", ("HEROIC INTERVENTION", "COUNTER-OFFENSIVE")) or ())
                if str(v or "").strip()
            ]
            if stratagems:
                unit.special_rules["enhancement_intraneural_biotech_stratagems"] = stratagems
            unit.special_rules["enhancement_intraneural_biotech_limit"] = str(
                params.get("limit", "battle_round") or "battle_round"
            ).strip().lower()
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "gift of the prescient" or enh_id == "000009134004":
            if not is_ordo_malleus_daemon_hunters:
                return
            unit.special_rules["enhancement_ordo_malleus_gift_of_the_prescient"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            usage_key = str(
                params.get("once_per_battle_key", "gift_of_the_prescient_rapid_ingress")
                or "gift_of_the_prescient_rapid_ingress"
            ).strip().lower()
            if not usage_key:
                usage_key = "gift_of_the_prescient_rapid_ingress"
            raw_stratagem_names = list(params.get("stratagem_names", ("RAPID INGRESS",)) or ())
            stratagem_names: list[str] = []
            for value in raw_stratagem_names:
                key = str(value or "").strip().upper()
                if not key or key in stratagem_names:
                    continue
                stratagem_names.append(key)
            if not stratagem_names:
                stratagem_names = ["RAPID INGRESS"]
            raw_target_patterns = list(
                params.get("required_target_unit_name_patterns", ("GREY KNIGHTS TERMINATOR SQUAD",))
                or ()
            )
            target_patterns: list[str] = []
            for value in raw_target_patterns:
                pattern = str(value or "").strip().upper()
                if not pattern or pattern in target_patterns:
                    continue
                target_patterns.append(pattern)
            if not target_patterns:
                target_patterns = ["GREY KNIGHTS TERMINATOR SQUAD"]
            unit.special_rules["enhancement_ordo_malleus_gift_of_the_prescient_usage_key"] = usage_key
            unit.special_rules["enhancement_ordo_malleus_gift_of_the_prescient_stratagem_names"] = list(stratagem_names)
            unit.special_rules["enhancement_ordo_malleus_gift_of_the_prescient_required_target_unit_name_patterns"] = list(
                target_patterns
            )
            unit.special_rules["enhancement_ordo_malleus_gift_of_the_prescient_requires_bearer_on_battlefield"] = bool(
                params.get("requires_bearer_on_battlefield", True)
            )
            unit.special_rules["enhancement_ordo_malleus_gift_of_the_prescient_deep_strike_min_distance"] = float(
                max(0.0, _coerce_float(params.get("deep_strike_min_distance", 3.0), default=3.0))
            )
            expires_phase = str(params.get("expires_phase", "MOVEMENT_PHASE") or "MOVEMENT_PHASE").strip().upper()
            if not expires_phase:
                expires_phase = "MOVEMENT_PHASE"
            unit.special_rules["enhancement_ordo_malleus_gift_of_the_prescient_expires_phase"] = expires_phase
            unit.special_rules["enhancement_ordo_malleus_gift_of_the_prescient_source"] = "Gift of the Prescient"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_ordo_malleus_gift_of_the_prescient_bearer_model_id"] = bearer_id

        if name == "fleetmaster" or enh_id == "000009138005":
            if not is_imperialis_fleet:
                return
            unit.special_rules["enhancement_imperialis_fleet_fleetmaster"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            usage_key = str(
                params.get("once_per_battle_round_key", "FLEETMASTER_FREE_STRATAGEM") or "FLEETMASTER_FREE_STRATAGEM"
            ).strip().upper()
            if not usage_key:
                usage_key = "FLEETMASTER_FREE_STRATAGEM"
            raw_stratagem_names = list(
                params.get(
                    "stratagem_names",
                    ("VIOLENT ACQUISITION", "MASTERS OF THE VOID", "CLOSE-QUARTERS BARRAGE"),
                )
                or ()
            )
            stratagem_names: list[str] = []
            for value in raw_stratagem_names:
                key = str(value or "").strip().upper()
                if not key or key in stratagem_names:
                    continue
                stratagem_names.append(key)
            if not stratagem_names:
                stratagem_names = ["VIOLENT ACQUISITION", "MASTERS OF THE VOID", "CLOSE-QUARTERS BARRAGE"]
            unit.special_rules["enhancement_imperialis_fleet_fleetmaster_usage_key"] = usage_key
            unit.special_rules["enhancement_imperialis_fleet_fleetmaster_stratagem_names"] = list(stratagem_names)
            unit.special_rules["enhancement_imperialis_fleet_fleetmaster_source"] = "Fleetmaster"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_imperialis_fleet_fleetmaster_bearer_model_id"] = bearer_id

        if name == "micromelta rounds" or enh_id == "000009757005":
            if not is_veiled_blade_elimination_force:
                return
            unit.special_rules["enhancement_micromelta_rounds"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            weapon_name = str(params.get("weapon_name", "exitus rifle") or "exitus rifle").strip() or "exitus rifle"
            try:
                anti_monster = int(params.get("anti_monster", 4) or 4)
            except Exception:
                anti_monster = 4
            try:
                anti_vehicle = int(params.get("anti_vehicle", 4) or 4)
            except Exception:
                anti_vehicle = 4
            unit.special_rules["enhancement_micromelta_rounds_weapon_name"] = weapon_name
            unit.special_rules["enhancement_micromelta_rounds_anti_monster"] = int(max(2, anti_monster))
            unit.special_rules["enhancement_micromelta_rounds_anti_vehicle"] = int(max(2, anti_vehicle))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "saintly example" or enh_id == "000008470002":
            if not is_hallowed_martyrs:
                return
            unit.special_rules["enhancement_saintly_example"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "through suffering, strength" or enh_id == "000008470003":
            if not is_hallowed_martyrs:
                return
            unit.special_rules["enhancement_through_suffering_strength"] = True
            unit.special_rules["enhancement_through_suffering_base_bonus"] = 1
            unit.special_rules["enhancement_through_suffering_wounded_bonus"] = 2
            # Generic parser support applies a unit-wide +1 A/S/D for this text; replace that
            # with bearer-specific runtime handling for the conditional +1/+2 effect.
            for key in (
                "enhancement_melee_attacks_bonus",
                "enhancement_melee_strength_bonus",
                "enhancement_melee_damage_bonus",
            ):
                current = int(unit.special_rules.get(key, 0) or 0)
                if current > 0:
                    unit.special_rules[key] = current - 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "chaplet of sacrifice" or enh_id == "000008470004":
            if not is_hallowed_martyrs:
                return
            unit.special_rules["enhancement_chaplet_of_sacrifice"] = True
            unit.special_rules["enhancement_chaplet_of_sacrifice_max_rerolls"] = 1
            unit.special_rules["enhancement_chaplet_of_sacrifice_max_rerolls_damaged"] = 3
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "mantle of ophelia" or enh_id == "000008470005":
            if not is_hallowed_martyrs:
                return
            unit.special_rules["enhancement_mantle_of_ophelia"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "litanies of faith" or enh_id == "000009037002":
            if not is_army_of_faith:
                return
            unit.special_rules["enhancement_litanies_of_faith"] = True
            unit.special_rules["enhancement_litanies_of_faith_source"] = "Litanies of Faith"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_litanies_of_faith_bearer_model_id"] = bearer_id

        if name == "blade of saint ellynor" or enh_id == "000009037003":
            if not is_army_of_faith:
                return
            unit.special_rules["enhancement_blade_of_saint_ellynor"] = True
            unit.special_rules["enhancement_blade_of_saint_ellynor_source"] = "Blade of Saint Ellynor"
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_melee_ap_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_ap_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_melee_precision"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_blade_of_saint_ellynor_bearer_model_id"] = bearer_id

        if name == "divine aspect" or enh_id == "000009037004":
            if not is_army_of_faith:
                return
            unit.special_rules["enhancement_divine_aspect"] = True
            unit.special_rules["enhancement_divine_aspect_range"] = 12.0
            unit.special_rules["enhancement_divine_aspect_source"] = "Divine Aspect"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_divine_aspect_bearer_model_id"] = bearer_id

        if name == "triptych of the macharian crusade" or enh_id == "000009037005":
            if not is_army_of_faith:
                return
            unit.special_rules["enhancement_triptych_of_macharian_crusade"] = True
            unit.special_rules["enhancement_triptych_of_macharian_crusade_source"] = "Triptych of the Macharian Crusade"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_triptych_of_macharian_crusade_bearer_model_id"] = bearer_id

        if name == "righteous rage" or enh_id == "000009033002":
            if not is_bringers_of_flame:
                return
            unit.special_rules["enhancement_righteous_rage"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                max_discard = int(params.get("max_discard_miracle_dice", 3) or 3)
            except (TypeError, ValueError):
                max_discard = 3
            try:
                bonus_per_discard = int(params.get("melee_attacks_strength_bonus_per_discard", 1) or 1)
            except (TypeError, ValueError):
                bonus_per_discard = 1
            unit.special_rules["enhancement_righteous_rage_max_discard"] = int(max(0, max_discard))
            unit.special_rules["enhancement_righteous_rage_bonus_per_discard"] = int(max(1, bonus_per_discard))
            unit.special_rules["enhancement_righteous_rage_source"] = "Righteous Rage"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_righteous_rage_bearer_model_id"] = bearer_id

        if name == "manual of saint griselda" or enh_id == "000009033003":
            if not is_bringers_of_flame:
                return
            unit.special_rules["enhancement_manual_of_saint_griselda"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                max_discard = int(params.get("max_discard_miracle_dice", 2) or 2)
            except (TypeError, ValueError):
                max_discard = 2
            try:
                result_max = int(params.get("result_value_max", 6) or 6)
            except (TypeError, ValueError):
                result_max = 6
            unit.special_rules["enhancement_manual_of_saint_griselda_max_discard"] = int(max(0, max_discard))
            unit.special_rules["enhancement_manual_of_saint_griselda_result_value_max"] = int(max(1, result_max))
            unit.special_rules["enhancement_manual_of_saint_griselda_source"] = "Manual of Saint Griselda"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_manual_of_saint_griselda_bearer_model_id"] = bearer_id

        if name == "fire and fury" or enh_id == "000009033004":
            if not is_bringers_of_flame:
                return
            unit.special_rules["enhancement_fire_and_fury"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                torrent_bonus = int(params.get("torrent_attacks_bonus", 1) or 1)
            except (TypeError, ValueError):
                torrent_bonus = 1
            try:
                sustained_hits = int(params.get("other_ranged_sustained_hits", 1) or 1)
            except (TypeError, ValueError):
                sustained_hits = 1
            unit.special_rules["enhancement_fire_and_fury_torrent_attacks_bonus"] = int(max(0, torrent_bonus))
            unit.special_rules["enhancement_fire_and_fury_other_ranged_sustained_hits"] = int(max(0, sustained_hits))
            unit.special_rules["enhancement_fire_and_fury_source"] = "Fire and Fury"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_fire_and_fury_bearer_model_id"] = bearer_id

        if name == "iron surplice of saint istalela" or enh_id == "000009033005":
            if not is_bringers_of_flame:
                return
            unit.special_rules["enhancement_iron_surplice_of_saint_istalela"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                save_characteristic = int(params.get("save_characteristic", 2) or 2)
            except (TypeError, ValueError):
                save_characteristic = 2
            try:
                feel_no_pain = int(params.get("feel_no_pain", 5) or 5)
            except (TypeError, ValueError):
                feel_no_pain = 5
            unit.special_rules["enhancement_iron_surplice_save_characteristic"] = int(max(2, min(6, save_characteristic)))
            unit.special_rules["enhancement_iron_surplice_feel_no_pain"] = int(max(2, min(6, feel_no_pain)))
            unit.special_rules["enhancement_iron_surplice_source"] = "Iron Surplice of Saint Istalela"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_iron_surplice_bearer_model_id"] = bearer_id
            tag = f"enhancement_fnp_{enh_id or name}"
            _ensure_enhancement_fnp_entry(
                unit,
                int(max(2, min(6, feel_no_pain))),
                source="Iron Surplice of Saint Istalela",
                tag=tag,
                source_model_id=str(bearer_id) if bearer_id else None,
            )
            if bearer_id:
                tag = f"enhancement_fnp_{enh_id or name}"
                entries = list(unit.special_rules.get("enhancement_bearer_fnp_entries", []) or [])
                changed = False
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    if str(entry.get("tag", "") or "") != tag:
                        continue
                    entry["source_model_id"] = str(bearer_id)
                    changed = True
                if changed:
                    unit.special_rules["enhancement_bearer_fnp_entries"] = entries
            try:
                remove_mods = getattr(unit, "remove_characteristic_modifiers_by_source", None)
                if callable(remove_mods):
                    remove_mods("enhancement:save_set")
            except Exception:
                pass

        if name == "triptych of judgement" or enh_id == "000009831002":
            if not is_champions_of_faith:
                return
            unit.special_rules["enhancement_triptych_of_judgement"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_triptych_of_judgement_ignore_hit_roll_modifiers"] = bool(
                params.get("ignore_hit_roll_modifiers", True)
            )
            unit.special_rules["enhancement_triptych_of_judgement_ignore_ballistic_skill_modifiers"] = bool(
                params.get("ignore_ballistic_skill_modifiers", True)
            )
            unit.special_rules["enhancement_triptych_of_judgement_ignore_weapon_skill_modifiers"] = bool(
                params.get("ignore_weapon_skill_modifiers", True)
            )
            unit.special_rules["enhancement_triptych_of_judgement_source"] = "Triptych of Judgement"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_triptych_of_judgement_bearer_model_id"] = bearer_id

        if name == "mark of devotion" or enh_id == "000009831003":
            if not is_champions_of_faith:
                return
            unit.special_rules["enhancement_mark_of_devotion"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                attacks_bonus = int(params.get("melee_attacks_bonus", 1) or 1)
            except (TypeError, ValueError):
                attacks_bonus = 1
            try:
                righteous_attacks_bonus = int(params.get("melee_attacks_bonus_if_righteous", 2) or 2)
            except (TypeError, ValueError):
                righteous_attacks_bonus = 2
            try:
                righteous_damage_bonus = int(params.get("melee_damage_bonus_if_righteous", 1) or 1)
            except (TypeError, ValueError):
                righteous_damage_bonus = 1
            unit.special_rules["enhancement_mark_of_devotion_attacks_bonus"] = int(max(0, attacks_bonus))
            unit.special_rules["enhancement_mark_of_devotion_attacks_bonus_if_righteous"] = int(max(0, righteous_attacks_bonus))
            unit.special_rules["enhancement_mark_of_devotion_damage_bonus_if_righteous"] = int(max(0, righteous_damage_bonus))
            unit.special_rules["enhancement_mark_of_devotion_source"] = "Mark of Devotion"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_mark_of_devotion_bearer_model_id"] = bearer_id

        if name == "eyes of the oracle" or enh_id == "000009831004":
            if not is_champions_of_faith:
                return
            unit.special_rules["enhancement_eyes_of_the_oracle"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                cp_gain = int(params.get("cp_gain", 1) or 1)
            except (TypeError, ValueError):
                cp_gain = 1
            unit.special_rules["enhancement_eyes_of_the_oracle_precision"] = True
            unit.special_rules["enhancement_eyes_of_the_oracle_cp_gain"] = int(max(0, cp_gain))
            unit.special_rules["enhancement_eyes_of_the_oracle_source"] = "Eyes of the Oracle"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_eyes_of_the_oracle_bearer_model_id"] = bearer_id

        if name == "sanctified amulet" or enh_id == "000009831005":
            if not is_champions_of_faith:
                return
            unit.special_rules["enhancement_sanctified_amulet"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                min_enemy_distance = float(params.get("min_enemy_distance", 12.0) or 12.0)
            except (TypeError, ValueError):
                min_enemy_distance = 12.0
            unit.special_rules["enhancement_sanctified_amulet_min_enemy_distance"] = float(max(0.0, min_enemy_distance))
            unit.special_rules["enhancement_sanctified_amulet_horizontal_only"] = bool(params.get("horizontal_only", False))
            unit.special_rules["enhancement_sanctified_amulet_source"] = "Sanctified Amulet"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_sanctified_amulet_bearer_model_id"] = bearer_id

        if name == "psalm of righteous judgement" or enh_id == "000009029002":
            if not is_penitent_host:
                return
            unit.special_rules["enhancement_psalm_of_righteous_judgement"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                discard_count = int(params.get("discard_miracle_dice", 1) or 1)
            except (TypeError, ValueError):
                discard_count = 1
            try:
                gained_value = int(params.get("gained_miracle_die_value", 6) or 6)
            except (TypeError, ValueError):
                gained_value = 6
            unit.special_rules["enhancement_psalm_of_righteous_judgement_discard_count"] = int(max(0, discard_count))
            unit.special_rules["enhancement_psalm_of_righteous_judgement_gained_value"] = int(max(1, min(6, gained_value)))
            unit.special_rules["enhancement_psalm_of_righteous_judgement_source"] = "Psalm of Righteous Judgement"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_psalm_of_righteous_judgement_bearer_model_id"] = bearer_id

        if name == "verse of holy piety" or enh_id == "000009029003":
            if not is_penitent_host:
                return
            unit.special_rules["enhancement_verse_of_holy_piety"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            vow_keys = [
                str(v or "").strip().lower()
                for v in list(
                    params.get(
                        "vow_keys",
                        ("path_of_the_penitent", "absolution_in_battle", "death_before_disgrace"),
                    )
                    or ()
                )
                if str(v or "").strip()
            ]
            if vow_keys:
                unit.special_rules["enhancement_verse_of_holy_piety_vow_keys"] = list(vow_keys)
            unit.special_rules["enhancement_verse_of_holy_piety_source"] = "Verse of Holy Piety"
            unit.special_rules["enhancement_verse_of_holy_piety_once_per_battle"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_verse_of_holy_piety_bearer_model_id"] = bearer_id

        if name == "refrain of enduring faith" or enh_id == "000009029004":
            if not is_penitent_host:
                return
            unit.special_rules["enhancement_refrain_of_enduring_faith"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                invulnerable_save = int(params.get("invulnerable_save", 5) or 5)
            except (TypeError, ValueError):
                invulnerable_save = 5
            unit.special_rules["enhancement_refrain_of_enduring_faith_invulnerable_save"] = int(
                max(2, min(7, invulnerable_save))
            )
            unit.special_rules["enhancement_refrain_of_enduring_faith_source"] = "Refrain of Enduring Faith"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_refrain_of_enduring_faith_bearer_model_id"] = bearer_id

        if name == "catechism of divine penitence" or enh_id == "000009029005":
            if not is_penitent_host:
                return
            unit.special_rules["enhancement_catechism_of_divine_penitence"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            attach_names = [
                str(v or "").strip()
                for v in list(params.get("attachment_override_unit_names_any", ("Repentia Squad",)) or ())
                if str(v or "").strip()
            ]
            if attach_names:
                unit.special_rules["enhancement_catechism_of_divine_penitence_attach_unit_names"] = list(attach_names)
            added_keywords = [
                str(v or "").strip().upper()
                for v in list(params.get("add_keywords", ("PENITENT",)) or ())
                if str(v or "").strip()
            ]
            if bearer is not None and added_keywords:
                current_keywords = [str(v or "").strip().upper() for v in list(getattr(bearer, "keywords", []) or [])]
                for keyword in list(added_keywords):
                    if keyword in current_keywords:
                        continue
                    current_keywords.append(keyword)
                bearer.keywords = list(current_keywords)
            unit.special_rules["enhancement_catechism_of_divine_penitence_source"] = "Catechism of Divine Penitence"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_catechism_of_divine_penitence_bearer_model_id"] = bearer_id

        if name == "abhuman detail" or enh_id == "000010637002":
            if not is_grizzled_company:
                return
            unit.special_rules["enhancement_abhuman_detail"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            extra_keywords = [
                str(v or "").strip().upper()
                for v in list(params.get("order_target_keyword_add", ("OGRYN",)) or ())
                if str(v or "").strip()
            ]
            extra_names = [
                str(v or "").strip()
                for v in list(params.get("attachment_override_unit_names_any", ("Ogryn Squad", "Bullgryn Squad")) or ())
                if str(v or "").strip()
            ]
            if extra_keywords:
                unit.special_rules["enhancement_abhuman_detail_order_target_keywords"] = extra_keywords
            if extra_names:
                unit.special_rules["enhancement_abhuman_detail_attach_unit_names"] = extra_names
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "aquilan eye" or enh_id == "000010637003":
            if not is_grizzled_company:
                return
            unit.special_rules["enhancement_aquilan_eye"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            order_key = str(params.get("extra_order_key", "TARGET_WEAK_SPOT") or "TARGET_WEAK_SPOT").strip().upper()
            try:
                ap_bonus = int(params.get("extra_order_ap_bonus", 1) or 1)
            except Exception:
                ap_bonus = 1
            try:
                order_range = float(params.get("extra_order_range", 12.0) or 12.0)
            except Exception:
                order_range = 12.0
            unit.special_rules["enhancement_aquilan_eye_order_key"] = order_key
            unit.special_rules["enhancement_aquilan_eye_ap_bonus"] = int(max(0, ap_bonus))
            unit.special_rules["enhancement_aquilan_eye_order_range"] = float(max(0.0, order_range))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "spec ops veteran" or enh_id == "000010637004":
            if not is_grizzled_company:
                return
            unit.special_rules["enhancement_spec_ops_veteran"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            order_key = str(params.get("extra_order_key", "MOVE_TO_SHADOWS") or "MOVE_TO_SHADOWS").strip().upper()
            unit.special_rules["enhancement_spec_ops_veteran_order_key"] = order_key
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "laud hailer" or enh_id == "000010637005":
            if not is_grizzled_company:
                return
            unit.special_rules["enhancement_laud_hailer"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            try:
                order_range = float(params.get("order_range", 12.0) or 12.0)
            except Exception:
                order_range = 12.0
            unit.special_rules["enhancement_laud_hailer_order_range"] = float(max(0.0, order_range))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name in ("bombast-class vox-array", "bombast class vox array") or enh_id == "000009801002":
            if not is_bridgehead_strike:
                return
            unit.special_rules["enhancement_bombast_class_vox_array"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            max_targets = _coerce_int(params.get("max_order_targets", 3) or 3, default=3)
            order_target_keyword = str(
                params.get("order_target_keyword", "REGIMENT") or "REGIMENT"
            ).strip().upper()
            if not order_target_keyword:
                order_target_keyword = "REGIMENT"
            unit.special_rules["enhancement_bombast_class_vox_array_max_targets"] = int(
                max(1, int(max_targets))
            )
            unit.special_rules["enhancement_bombast_class_vox_array_order_target_keyword"] = order_target_keyword
            unit.special_rules["enhancement_bombast_class_vox_array_requires_master_vox"] = bool(
                params.get("requires_master_vox", True)
            )
            unit.special_rules["enhancement_bombast_class_vox_array_source"] = "Bombast-class Vox-array"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_bombast_class_vox_array_bearer_model_id"] = bearer_id

        if name == "priority-drop beacon" or enh_id == "000009801003":
            if not is_bridgehead_strike:
                return
            unit.special_rules["enhancement_priority_drop_beacon"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            setup_round_bonus = _coerce_int(
                params.get("strategic_reserves_setup_round_bonus", 1) or 1,
                default=1,
            )
            unit.special_rules["enhancement_priority_drop_beacon_round_bonus"] = int(
                max(0, int(setup_round_bonus))
            )
            unit.special_rules["enhancement_priority_drop_beacon_requires_deep_strike"] = bool(
                params.get("requires_deep_strike", True)
            )
            unit.special_rules["enhancement_priority_drop_beacon_source"] = "Priority-drop Beacon"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_priority_drop_beacon_bearer_model_id"] = bearer_id

        if name == "student of kauyon" or enh_id == "000009839002":
            if not is_auxiliary_cadre:
                return
            unit.special_rules["enhancement_student_of_kauyon"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            max_units = _coerce_int(params.get("max_units", 3) or 3, default=3)
            unit.special_rules["enhancement_student_of_kauyon_max_units"] = int(max(0, max_units))
            patterns = [
                str(v or "").strip().lower()
                for v in list(params.get("target_unit_name_patterns", ("kroot carnivore", "kroot farstalker")) or ())
                if str(v or "").strip()
            ]
            if not patterns:
                patterns = ["kroot carnivore", "kroot farstalker"]
            unit.special_rules["enhancement_student_of_kauyon_target_unit_name_patterns"] = list(
                dict.fromkeys(patterns)
            )
            unit.special_rules["enhancement_student_of_kauyon_source"] = "Student of Kauyon"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_student_of_kauyon_bearer_model_id"] = bearer_id

        if name == "admired leader" or enh_id == "000009839003":
            if not is_auxiliary_cadre:
                return
            unit.special_rules["enhancement_admired_leader"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            selection_range = _coerce_float(params.get("selection_range", 12.0) or 12.0, default=12.0)
            leadership_bonus = _coerce_int(params.get("leadership_bonus", 1) or 1, default=1)
            oc_bonus = _coerce_int(params.get("objective_control_bonus", 1) or 1, default=1)
            target_keywords = [
                str(v or "").strip().upper()
                for v in list(params.get("target_keywords_any", ("KROOT", "VESPID STINGWINGS")) or ())
                if str(v or "").strip()
            ]
            if not target_keywords:
                target_keywords = ["KROOT", "VESPID STINGWINGS"]
            unit.special_rules["enhancement_admired_leader_selection_range"] = float(max(0.0, selection_range))
            unit.special_rules["enhancement_admired_leader_leadership_bonus"] = int(max(0, leadership_bonus))
            unit.special_rules["enhancement_admired_leader_objective_control_bonus"] = int(max(0, oc_bonus))
            unit.special_rules["enhancement_admired_leader_requires_not_battle_shocked_for_objective_control"] = bool(
                params.get("requires_not_battle_shocked_for_objective_control", True)
            )
            unit.special_rules["enhancement_admired_leader_target_keywords_any"] = list(dict.fromkeys(target_keywords))
            unit.special_rules["enhancement_admired_leader_source"] = "Admired Leader"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_admired_leader_bearer_model_id"] = bearer_id

        if name == "fanatical convert" or enh_id == "000009839004":
            if not is_auxiliary_cadre:
                return
            unit.special_rules["enhancement_fanatical_convert"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_fanatical_convert_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_fanatical_convert_source"] = "Fanatical Convert"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_fanatical_convert_bearer_model_id"] = bearer_id

        if name == "transponder lock module" or enh_id == "000009839005":
            if not is_auxiliary_cadre:
                return
            unit.special_rules["enhancement_transponder_lock_module"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            setup_round_bonus = _coerce_int(
                params.get("strategic_reserves_setup_round_bonus", 1) or 1,
                default=1,
            )
            unit.special_rules["enhancement_transponder_lock_module_round_bonus"] = int(
                max(0, int(setup_round_bonus))
            )
            unit.special_rules["enhancement_transponder_lock_module_requires_deep_strike"] = bool(
                params.get("requires_deep_strike", True)
            )
            spotter_range = _coerce_float(params.get("turn_one_spotter_range", 12.0) or 12.0, default=12.0)
            unit.special_rules["enhancement_transponder_lock_module_turn_one_spotter_range"] = float(
                max(0.0, float(spotter_range))
            )
            spotter_keywords = [
                str(v or "").strip().upper()
                for v in list(params.get("turn_one_spotter_keywords_any", ("KROOT", "VESPID STINGWINGS")) or ())
                if str(v or "").strip()
            ]
            if not spotter_keywords:
                spotter_keywords = ["KROOT", "VESPID STINGWINGS"]
            unit.special_rules["enhancement_transponder_lock_module_turn_one_spotter_keywords_any"] = list(
                dict.fromkeys(spotter_keywords)
            )
            unit.special_rules["enhancement_transponder_lock_module_source"] = "Transponder Lock Module"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_transponder_lock_module_bearer_model_id"] = bearer_id

        if name == "borthrod gland" or enh_id == "000008821002":
            if not is_kroot_hunting_pack:
                return
            unit.special_rules["enhancement_borthrod_gland"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            threshold = _coerce_int(params.get("crit_hit_threshold", 5) or 5, default=5)
            unit.special_rules["enhancement_borthrod_gland_crit_hit_threshold"] = int(max(2, int(threshold)))
            unit.special_rules["enhancement_borthrod_gland_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_borthrod_gland_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            unit.special_rules["enhancement_borthrod_gland_source"] = "Borthrod Gland"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_borthrod_gland_bearer_model_id"] = bearer_id

        if name == "kroothawk flock" or enh_id == "000008821003":
            if not is_kroot_hunting_pack:
                return
            unit.special_rules["enhancement_kroothawk_flock"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Kroothawk Flock").strip() or "Kroothawk Flock"
            keywords = tuple(
                str(v or "").strip().upper()
                for v in list(params.get("keywords", ("IGNORES COVER",)) or ())
                if str(v or "").strip()
            )
            unit.special_rules["enhancement_kroothawk_flock_source"] = source
            unit.special_rules["enhancement_kroothawk_flock_min_enemy_distance"] = float(
                max(0.0, _coerce_float(params.get("enemy_reserves_min_distance", 12.0) or 12.0, default=12.0))
            )
            unit.special_rules["enhancement_kroothawk_flock_horizontal_only"] = bool(
                params.get("horizontal_only", True)
            )
            unit.special_rules["enhancement_kroothawk_flock_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            _append_enhancement_bearer_unit_weapon_keyword_rule(
                unit,
                attack_type=str(params.get("attack_type", "ranged") or "ranged"),
                keywords=keywords,
                source=source,
                requires_bearer_leading=False,
                source_model_id=bearer_id,
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_kroothawk_flock_bearer_model_id"] = bearer_id

        if name == "nomadic hunter" or enh_id == "000008821004":
            if not is_kroot_hunting_pack:
                return
            unit.special_rules["enhancement_nomadic_hunter"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Nomadic Hunter").strip() or "Nomadic Hunter"
            keywords = tuple(
                str(v or "").strip().upper()
                for v in list(params.get("keywords", ("ASSAULT",)) or ())
                if str(v or "").strip()
            )
            move_bonus = _coerce_int(params.get("movement_bonus", 3) or 3, default=3)
            unit.special_rules["enhancement_nomadic_hunter_move_bonus"] = int(max(0, move_bonus))
            unit.special_rules["enhancement_nomadic_hunter_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_nomadic_hunter_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            unit.special_rules["enhancement_nomadic_hunter_source"] = source
            _append_enhancement_bearer_unit_weapon_keyword_rule(
                unit,
                attack_type=str(params.get("attack_type", "ranged") or "ranged"),
                keywords=keywords,
                source=source,
                requires_bearer_leading=bool(params.get("requires_bearer_leading", True)),
                source_model_id=bearer_id,
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_nomadic_hunter_bearer_model_id"] = bearer_id

        if name == "root-carved weapons" or enh_id == "000008821005":
            if not is_kroot_hunting_pack:
                return
            unit.special_rules["enhancement_root_carved_weapons"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Root-carved Weapons").strip() or "Root-carved Weapons"
            keywords = tuple(
                str(v or "").strip().upper()
                for v in list(params.get("keywords", ("PRECISION", "DEVASTATING WOUNDS")) or ())
                if str(v or "").strip()
            )
            unit.special_rules["enhancement_root_carved_weapons_source"] = source
            _append_enhancement_bearer_weapon_keyword_rule(
                unit,
                attack_type=str(params.get("attack_type", "any") or "any"),
                keywords=keywords,
                source=source,
                requires_bearer_leading=False,
                source_model_id=bearer_id,
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_root_carved_weapons_bearer_model_id"] = bearer_id

        if name == "exemplar of the kauyon" or enh_id == "000008442002":
            if not is_kauyon:
                return
            unit.special_rules["enhancement_exemplar_of_the_kauyon"] = True
            unit.special_rules["enhancement_exemplar_of_the_kauyon_source"] = "Exemplar of the Kauyon"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_exemplar_of_the_kauyon_bearer_model_id"] = bearer_id

        if name == "precision of the patient hunter" or enh_id == "000008442003":
            if not is_kauyon:
                return
            unit.special_rules["enhancement_precision_of_the_patient_hunter"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            hit_bonus = _coerce_int(params.get("hit_bonus", 1) or 1, default=1)
            wound_bonus = _coerce_int(params.get("wound_bonus", 1) or 1, default=1)
            wound_round = _coerce_int(params.get("wound_bonus_from_battle_round", 3) or 3, default=3)
            unit.special_rules["enhancement_precision_of_the_patient_hunter_hit_bonus"] = int(max(0, hit_bonus))
            unit.special_rules["enhancement_precision_of_the_patient_hunter_wound_bonus"] = int(max(0, wound_bonus))
            unit.special_rules["enhancement_precision_of_the_patient_hunter_wound_bonus_from_battle_round"] = int(
                max(1, wound_round)
            )
            unit.special_rules["enhancement_precision_of_the_patient_hunter_source"] = "Precision of the Patient Hunter"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_precision_of_the_patient_hunter_bearer_model_id"] = bearer_id

        if name == "through unity, devastation" or enh_id == "000008442005":
            if not is_kauyon:
                return
            unit.special_rules["enhancement_through_unity_devastation"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_through_unity_devastation_lethal_hits"] = bool(
                params.get("lethal_hits", True)
            )
            unit.special_rules["enhancement_through_unity_devastation_source"] = "Through Unity, Devastation"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_through_unity_devastation_bearer_model_id"] = bearer_id

        if name == "shroud projector" or enh_id == "000009801004":
            if not is_bridgehead_strike:
                return
            unit.special_rules["enhancement_shroud_projector"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_shroud_projector_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_shroud_projector_source"] = "Shroud Projector"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_shroud_projector_bearer_model_id"] = bearer_id

        if name == "advance augury" or enh_id == "000009801005":
            if not is_bridgehead_strike:
                return
            unit.special_rules["enhancement_advance_augury"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            max_units = _coerce_int(params.get("max_units", 3) or 3, default=3)
            allow_strategic = bool(params.get("allow_strategic_reserves", True))
            filters = [
                str(v or "").strip().upper()
                for v in list(params.get("redeploy_filters", ("REGIMENT",)) or ())
                if str(v or "").strip()
            ]
            if not filters:
                filters = ["REGIMENT"]
            unit.special_rules["enhancement_advance_augury_max_units"] = int(max(1, int(max_units)))
            unit.special_rules["enhancement_advance_augury_can_place_in_reserves"] = bool(allow_strategic)
            unit.special_rules["enhancement_advance_augury_filters"] = list(filters)
            unit.special_rules["enhancement_advance_augury_source"] = "Advance Augury"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_advance_augury_bearer_model_id"] = bearer_id

        if name == "bold leadership" or enh_id == "000009861002":
            if not is_mechanised_assault:
                return
            unit.special_rules["enhancement_bold_leadership"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            _apply_enhancement_sticky_objective_control(
                unit,
                source_scope=str(params.get("source_scope", "unit") or "unit"),
                source=str(params.get("sticky_source", "unit_sticky_objective") or "unit_sticky_objective"),
                allow_embarked_transport=bool(params.get("allow_embarked_transport", True)),
                requires_bearer_leading=bool(params.get("requires_bearer_leading", False)),
                source_model_id=bearer_id,
            )
            unit.special_rules["enhancement_bold_leadership_source"] = "Bold Leadership"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_bold_leadership_bearer_model_id"] = bearer_id

        if name == "sacred unguents" or enh_id == "000009861003":
            if not is_mechanised_assault:
                return
            unit.special_rules["enhancement_sacred_unguents"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            range_value = params.get("range", getattr(desc, "range_in", 3.0) if desc is not None else 3.0)
            try:
                selection_range = float(range_value or 3.0)
            except (TypeError, ValueError):
                selection_range = 3.0
            include_keywords = [
                str(v or "").strip().upper()
                for v in list(params.get("target_keywords_all", ("TRANSPORT",)) or ())
                if str(v or "").strip()
            ]
            if not include_keywords:
                include_keywords = ["TRANSPORT"]
            exclude_keywords = [
                str(v or "").strip().upper()
                for v in list(params.get("exclude_target_keywords_any", ("AIRCRAFT", "TITANIC")) or ())
                if str(v or "").strip()
            ]
            unit.special_rules["enhancement_sacred_unguents_range"] = float(max(0.0, selection_range))
            unit.special_rules["enhancement_sacred_unguents_target_keywords_all"] = list(include_keywords)
            unit.special_rules["enhancement_sacred_unguents_exclude_target_keywords_any"] = list(exclude_keywords)
            unit.special_rules["enhancement_sacred_unguents_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_sacred_unguents_source"] = "Sacred Unguents"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_sacred_unguents_bearer_model_id"] = bearer_id

        if name == "smoke grenades" or enh_id == "000009861004":
            if not is_mechanised_assault:
                return
            unit.special_rules["enhancement_smoke_grenades"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            range_value = params.get("range", getattr(desc, "range_in", 3.0) if desc is not None else 3.0)
            try:
                aura_range = float(range_value or 3.0)
            except (TypeError, ValueError):
                aura_range = 3.0
            unit.special_rules["enhancement_smoke_grenades_range"] = float(max(0.0, aura_range))
            unit.special_rules["enhancement_smoke_grenades_require_wholly_within"] = bool(
                params.get("require_wholly_within", True)
            )
            unit.special_rules["enhancement_smoke_grenades_require_friendly_transport"] = bool(
                params.get("require_friendly_transport", True)
            )
            unit.special_rules["enhancement_smoke_grenades_grants_benefit_of_cover"] = bool(
                params.get("grants_benefit_of_cover", True)
            )
            unit.special_rules["enhancement_smoke_grenades_grants_stealth"] = bool(
                params.get("grants_stealth", True)
            )
            unit.special_rules["enhancement_smoke_grenades_source"] = "Smoke Grenades"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_smoke_grenades_bearer_model_id"] = bearer_id

        if name == "vanguard honours" or enh_id == "000009861005":
            if not is_mechanised_assault:
                return
            unit.special_rules["enhancement_vanguard_honours"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_vanguard_honours_allow_after_advance"] = bool(
                params.get("allow_after_advance", True)
            )
            unit.special_rules["enhancement_vanguard_honours_force_cannot_charge_this_turn"] = bool(
                params.get("force_cannot_charge_this_turn", True)
            )
            unit.special_rules["enhancement_vanguard_honours_source"] = "Vanguard Honours"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_vanguard_honours_bearer_model_id"] = bearer_id

        if name == "guerrilla honours" or enh_id == "000009869002":
            if not is_recon_element:
                return
            unit.special_rules["enhancement_guerrilla_honours"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            max_units = _coerce_int(params.get("max_units", 3) or 3, default=3)
            allow_strategic = bool(params.get("allow_strategic_reserves", True))
            filters = [
                str(v or "").strip().upper()
                for v in list(params.get("redeploy_filters", ("ASTRA MILITARUM", "INFANTRY")) or ())
                if str(v or "").strip()
            ]
            if not filters:
                filters = ["ASTRA MILITARUM", "INFANTRY"]
            unit.special_rules["enhancement_guerrilla_honours_max_units"] = int(max(1, int(max_units)))
            unit.special_rules["enhancement_guerrilla_honours_can_place_in_reserves"] = bool(allow_strategic)
            unit.special_rules["enhancement_guerrilla_honours_filters"] = list(filters)
            unit.special_rules["enhancement_guerrilla_honours_exclude_source_unit"] = bool(
                params.get("exclude_source_unit", True)
            )
            unit.special_rules["enhancement_guerrilla_honours_source"] = "Guerrilla Honours"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_guerrilla_honours_bearer_model_id"] = bearer_id

        if name == "scare gas grenades" or enh_id == "000009869003":
            if not is_recon_element:
                return
            unit.special_rules["enhancement_scare_gas_grenades"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            range_value = params.get("range", getattr(desc, "range_in", 8.0) if desc is not None else 8.0)
            try:
                selection_range = float(range_value or 8.0)
            except (TypeError, ValueError):
                selection_range = 8.0
            exclude_keywords = [
                str(v or "").strip().upper()
                for v in list(params.get("exclude_target_keywords_any", ("MONSTER", "VEHICLE")) or ())
                if str(v or "").strip()
            ]
            ability_key = str(params.get("ability_key", "scare_gas_grenades") or "scare_gas_grenades").strip().lower()
            unit.special_rules["enhancement_scare_gas_grenades_range"] = float(max(0.0, selection_range))
            unit.special_rules["enhancement_scare_gas_grenades_exclude_target_keywords_any"] = list(exclude_keywords)
            unit.special_rules["enhancement_scare_gas_grenades_ability_key"] = ability_key
            unit.special_rules["enhancement_scare_gas_grenades_source"] = "Scare Gas Grenades"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_scare_gas_grenades_bearer_model_id"] = bearer_id

        if name == "survival gear" or enh_id == "000009869004":
            if not is_recon_element:
                return
            unit.special_rules["enhancement_survival_gear"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            scout_distance = params.get("scouts_distance", 6.0)
            try:
                scout_distance_val = float(scout_distance or 6.0)
            except (TypeError, ValueError):
                scout_distance_val = 6.0
            unit.special_rules["enhancement_survival_gear_scout_distance"] = float(max(0.0, scout_distance_val))
            unit.special_rules["enhancement_survival_gear_source"] = "Survival Gear"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_survival_gear_bearer_model_id"] = bearer_id

        if name == "tripwires" or enh_id == "000009869005":
            if not is_recon_element:
                return
            unit.special_rules["enhancement_tripwires"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            range_value = params.get("range", getattr(desc, "range_in", 9.0) if desc is not None else 9.0)
            try:
                trigger_range = float(range_value or 9.0)
            except (TypeError, ValueError):
                trigger_range = 9.0
            trigger_actions = [
                str(v or "").strip().lower()
                for v in list(params.get("trigger_actions", ("move", "advance", "charge", "fall_back")) or ())
                if str(v or "").strip()
            ]
            if not trigger_actions:
                trigger_actions = ["move", "advance", "charge", "fall_back"]
            target_keywords = [
                str(v or "").strip().upper()
                for v in list(params.get("target_keywords_any", ("INFANTRY", "MOUNTED")) or ())
                if str(v or "").strip()
            ]
            if not target_keywords:
                target_keywords = ["INFANTRY", "MOUNTED"]
            success_on = _coerce_int(params.get("success_on", 4) or 4, default=4)
            hit_roll_modifier = _coerce_int(params.get("hit_roll_modifier", -1) or -1, default=-1)
            unit.special_rules["enhancement_tripwires_range"] = float(max(0.0, trigger_range))
            unit.special_rules["enhancement_tripwires_trigger_actions"] = list(trigger_actions)
            unit.special_rules["enhancement_tripwires_target_keywords_any"] = list(target_keywords)
            unit.special_rules["enhancement_tripwires_success_on"] = int(max(2, min(6, int(success_on))))
            unit.special_rules["enhancement_tripwires_hit_roll_modifier"] = int(min(0, int(hit_roll_modifier)))
            unit.special_rules["enhancement_tripwires_source"] = "Tripwires"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_tripwires_bearer_model_id"] = bearer_id

        if name == "eager advance" or enh_id == "000009857002":
            if not is_siege_regiment:
                return
            unit.special_rules["enhancement_eager_advance"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            scout_distance = params.get("scouts_distance", 6.0)
            try:
                scout_distance_val = float(scout_distance or 6.0)
            except (TypeError, ValueError):
                scout_distance_val = 6.0
            target_keyword = str(params.get("target_keyword", "REGIMENT") or "REGIMENT").strip().upper()
            unit.special_rules["enhancement_eager_advance_scout_distance"] = float(max(0.0, scout_distance_val))
            unit.special_rules["enhancement_eager_advance_target_keyword"] = target_keyword if target_keyword else "REGIMENT"
            unit.special_rules["enhancement_eager_advance_requires_leading"] = bool(
                params.get("requires_leading", True)
            )
            unit.special_rules["enhancement_eager_advance_source"] = "Eager Advance"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_eager_advance_bearer_model_id"] = bearer_id

        if name == "flash grenades" or enh_id == "000009857003":
            if not is_siege_regiment:
                return
            unit.special_rules["enhancement_flash_grenades"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_flash_grenades_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_flash_grenades_source"] = "Flash Grenades"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_flash_grenades_bearer_model_id"] = bearer_id

        if name == "legacy sidearm" or enh_id == "000009857004":
            if not is_siege_regiment:
                return
            unit.special_rules["enhancement_legacy_sidearm"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            attacks_bonus = _coerce_int(params.get("attacks_bonus", 2) or 2, default=2)
            weapon_keyword = str(params.get("weapon_keyword", "PISTOL") or "PISTOL").strip().upper()
            unit.special_rules["enhancement_legacy_sidearm_attacks_bonus"] = int(max(0, int(attacks_bonus)))
            unit.special_rules["enhancement_legacy_sidearm_weapon_keyword"] = weapon_keyword if weapon_keyword else "PISTOL"
            unit.special_rules["enhancement_legacy_sidearm_bearer_only"] = bool(params.get("bearer_only", True))
            unit.special_rules["enhancement_legacy_sidearm_source"] = "Legacy Sidearm"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_legacy_sidearm_bearer_model_id"] = bearer_id

        if name in ("stalwart's honours", "stalwarts honours") or enh_id == "000009857005":
            if not is_siege_regiment:
                return
            unit.special_rules["enhancement_stalwarts_honours"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            add_order_key = str(params.get("additional_order_key", "TAKE_COVER") or "TAKE_COVER").strip().upper()
            unit.special_rules["enhancement_stalwarts_honours_additional_order_key"] = (
                add_order_key if add_order_key else "TAKE_COVER"
            )
            unit.special_rules["enhancement_stalwarts_honours_requires_leading"] = bool(
                params.get("requires_leading", True)
            )
            unit.special_rules["enhancement_stalwarts_honours_source"] = "Stalwart's Honours"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_stalwarts_honours_bearer_model_id"] = bearer_id

        if name == "calm under fire" or enh_id == "000009865002":
            if not is_hammer_of_the_emperor:
                return
            unit.special_rules["enhancement_calm_under_fire"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            additional_targets = _coerce_int(params.get("additional_targets", 1) or 1, default=1)
            order_target_keyword = str(params.get("order_target_keyword", "SQUADRON") or "SQUADRON").strip().upper()
            if not order_target_keyword:
                order_target_keyword = "SQUADRON"
            unit.special_rules["enhancement_calm_under_fire_additional_targets"] = int(max(0, int(additional_targets)))
            unit.special_rules["enhancement_calm_under_fire_order_target_keyword"] = order_target_keyword
            unit.special_rules["enhancement_calm_under_fire_once_per_turn"] = bool(params.get("once_per_turn", True))
            unit.special_rules["enhancement_calm_under_fire_source"] = "Calm Under Fire"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_calm_under_fire_bearer_model_id"] = bearer_id

        if name == "indomitable steed" or enh_id == "000009865003":
            if not is_hammer_of_the_emperor:
                return
            unit.special_rules["enhancement_indomitable_steed"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            feel_no_pain = _coerce_int(params.get("feel_no_pain", 6) or 6, default=6)
            feel_no_pain = int(max(2, min(6, feel_no_pain)))
            tag = f"enhancement_fnp_{enh_id or name}"
            _ensure_enhancement_fnp_entry(
                unit,
                feel_no_pain,
                source="Indomitable Steed",
                tag=tag,
            )
            unit.special_rules["enhancement_indomitable_steed_fnp"] = int(feel_no_pain)
            unit.special_rules["enhancement_indomitable_steed_source"] = "Indomitable Steed"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_indomitable_steed_bearer_model_id"] = bearer_id

        if name == "regimental banner" or enh_id == "000009865004":
            if not is_hammer_of_the_emperor:
                return
            unit.special_rules["enhancement_regimental_banner"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            objective_control_bonus = _coerce_int(params.get("objective_control_bonus", 3) or 3, default=3)
            unit.special_rules["enhancement_regimental_banner_objective_control_bonus"] = int(
                max(0, int(objective_control_bonus))
            )
            unit.special_rules["enhancement_regimental_banner_source"] = "Regimental Banner"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_regimental_banner_bearer_model_id"] = bearer_id

        if name == "veteran crew" or enh_id == "000009865005":
            if not is_hammer_of_the_emperor:
                return
            unit.special_rules["enhancement_veteran_crew"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            reroll_vals = []
            for raw in list(params.get("reroll_hit_values", (1,)) or (1,)):
                try:
                    reroll_vals.append(int(raw))
                except (TypeError, ValueError):
                    continue
            if not reroll_vals:
                reroll_vals = [1]
            deduped_vals = []
            for value in sorted(set(reroll_vals)):
                if value < 1 or value > 6:
                    continue
                deduped_vals.append(int(value))
            if not deduped_vals:
                deduped_vals = [1]
            attack_type = str(params.get("attack_type", "ranged") or "ranged").strip().lower()
            unit.special_rules["enhancement_veteran_crew_reroll_hit_values"] = list(deduped_vals)
            unit.special_rules["enhancement_veteran_crew_attack_type"] = attack_type if attack_type else "ranged"
            unit.special_rules["enhancement_veteran_crew_source"] = "Veteran Crew"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_veteran_crew_bearer_model_id"] = bearer_id

        if name == "death mask of ollanius" or enh_id == "000008380002":
            if not is_combined_arms:
                return
            unit.special_rules["enhancement_death_mask_of_ollanius"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            oc_penalty = _coerce_int(
                params.get("objective_control_penalty", 1) or 1,
                default=1,
            )
            unit.special_rules["enhancement_death_mask_of_ollanius_oc_penalty"] = int(max(0, int(oc_penalty)))
            unit.special_rules["enhancement_death_mask_of_ollanius_source"] = "Death Mask of Ollanius"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_death_mask_of_ollanius_bearer_model_id"] = bearer_id

        if name == "drill commander" or enh_id == "000008380003":
            if not is_combined_arms:
                return
            unit.special_rules["enhancement_drill_commander"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            threshold = _coerce_int(
                params.get("critical_hit_threshold", 5) or 5,
                default=5,
            )
            unit.special_rules["enhancement_drill_commander_crit_hit_threshold"] = int(max(2, min(6, int(threshold))))
            unit.special_rules["enhancement_drill_commander_attack_type"] = str(
                params.get("attack_type", "ranged") or "ranged"
            ).strip().lower()
            unit.special_rules["enhancement_drill_commander_requires_remained_stationary"] = bool(
                params.get("requires_remained_stationary", True)
            )
            unit.special_rules["enhancement_drill_commander_source"] = "Drill Commander"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_drill_commander_bearer_model_id"] = bearer_id

        if name == "grand strategist" or enh_id == "000008380004":
            if not is_combined_arms:
                return
            unit.special_rules["enhancement_grand_strategist"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            additional_orders = _coerce_int(
                params.get("additional_orders", 1) or 1,
                default=1,
            )
            unit.special_rules["enhancement_grand_strategist_additional_orders"] = int(max(0, int(additional_orders)))
            unit.special_rules["enhancement_grand_strategist_source"] = "Grand Strategist"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_grand_strategist_bearer_model_id"] = bearer_id

        if name == "reactive command" or enh_id == "000008380005":
            if not is_combined_arms:
                return
            unit.special_rules["enhancement_reactive_command"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            trigger_range = params.get("trigger_range", getattr(desc, "range_in", 9.0) if desc is not None else 9.0)
            try:
                trigger_range_val = float(trigger_range or 9.0)
            except (TypeError, ValueError):
                trigger_range_val = 9.0
            additional_orders = _coerce_int(
                params.get("additional_orders_per_trigger", 1) or 1,
                default=1,
            )
            unit.special_rules["enhancement_reactive_command_trigger_range"] = float(max(0.0, trigger_range_val))
            unit.special_rules["enhancement_reactive_command_additional_orders_per_trigger"] = int(
                max(1, int(additional_orders))
            )
            unit.special_rules["enhancement_reactive_command_does_not_count_towards_order_limit"] = bool(
                params.get("does_not_count_towards_order_limit", True)
            )
            unit.special_rules["enhancement_reactive_command_source"] = "Reactive Command"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_reactive_command_bearer_model_id"] = bearer_id

        if name == "berzerker glaive" or enh_id == "000008432002":
            if not is_berzerker_warband:
                return
            unit.special_rules["enhancement_melee_attacks_bonus_no_extra_attacks"] = int(
                unit.special_rules.get("enhancement_melee_attacks_bonus_no_extra_attacks", 0) or 0
            ) + 1
            unit.special_rules["enhancement_melee_damage_bonus_no_extra_attacks"] = int(
                unit.special_rules.get("enhancement_melee_damage_bonus_no_extra_attacks", 0) or 0
            ) + 1

        if name == "battle-lust" or enh_id == "000008432005":
            if not is_berzerker_warband:
                return
            unit.special_rules["enhancement_charge_reroll"] = True
            unit.special_rules["enhancement_battle_lust_bonus_if_unbridled"] = 1

        if name == "favoured of khorne" or enh_id == "000008432004":
            if not is_berzerker_warband:
                return
            unit.special_rules["enhancement_favoured_of_khorne_rerolls"] = 2

        if name in ("the imperium's sword", "the imperiums sword") or enh_id == "000008494002":
            if not is_1st_company_task_force:
                return
            unit.special_rules["enhancement_the_imperiums_sword"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            bearer_bonus = _coerce_int(params.get("bearer_melee_attacks_bonus", 1) or 1, default=1)
            other_models_bonus = _coerce_int(params.get("unit_other_models_melee_attacks_bonus", 1) or 1, default=1)
            once_key = str(params.get("once_per_battle_key", "the_imperiums_sword") or "the_imperiums_sword").strip().lower()
            existing_bearer_bonus = _coerce_int(
                unit.special_rules.get("enhancement_bearer_melee_attacks_bonus", 0) or 0,
                default=0,
            )
            unit.special_rules["enhancement_bearer_melee_attacks_bonus"] = int(
                max(existing_bearer_bonus, max(0, int(bearer_bonus)))
            )
            unit.special_rules["enhancement_the_imperiums_sword_other_models_bonus"] = int(max(0, int(other_models_bonus)))
            unit.special_rules["enhancement_the_imperiums_sword_once_key"] = once_key
            unit.special_rules["enhancement_the_imperiums_sword_source"] = "The Imperium's Sword"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "fear made manifest (aura)" or enh_id == "000008494003":
            if not is_1st_company_task_force:
                return
            unit.special_rules["enhancement_fear_made_manifest"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            range_raw = params.get("range", getattr(desc, "range_in", 6.0) if desc is not None else 6.0)
            try:
                aura_range = float(range_raw if range_raw is not None else 6.0)
            except Exception:
                aura_range = 6.0
            once_key = str(params.get("once_per_battle_key", "fear_made_manifest") or "fear_made_manifest").strip().lower()
            once_roll = str(params.get("once_per_battle_models_destroyed_roll", "D3") or "D3").strip().upper() or "D3"
            unit.special_rules["enhancement_fear_made_manifest_range"] = float(max(0.0, aura_range))
            unit.special_rules["enhancement_fear_made_manifest_once_key"] = once_key
            unit.special_rules["enhancement_fear_made_manifest_once_roll"] = once_roll
            unit.special_rules["enhancement_fear_made_manifest_source"] = "Fear Made Manifest (Aura)"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "rites of war" or enh_id == "000008494004":
            if not is_1st_company_task_force:
                return
            unit.special_rules["enhancement_rites_of_war"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            bearer_oc_bonus = _coerce_int(params.get("bearer_objective_control_bonus", 1) or 1, default=1)
            other_models_bonus = _coerce_int(params.get("unit_other_models_objective_control_bonus", 1) or 1, default=1)
            once_key = str(params.get("once_per_battle_key", "rites_of_war") or "rites_of_war").strip().lower()
            unit.special_rules["enhancement_rites_of_war_bearer_oc_bonus"] = int(max(0, int(bearer_oc_bonus)))
            unit.special_rules["enhancement_rites_of_war_other_models_bonus"] = int(max(0, int(other_models_bonus)))
            unit.special_rules["enhancement_rites_of_war_once_key"] = once_key
            unit.special_rules["enhancement_rites_of_war_source"] = "Rites of War"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "iron resolve" or enh_id == "000008494005":
            if not is_1st_company_task_force:
                return
            unit.special_rules["enhancement_iron_resolve"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            bearer_fnp = _coerce_int(params.get("bearer_fnp", 5) or 5, default=5)
            unit_fnp = _coerce_int(params.get("unit_fnp_on_trigger", 5) or 5, default=5)
            once_key = str(params.get("once_per_battle_key", "iron_resolve") or "iron_resolve").strip().lower()
            _ensure_enhancement_fnp_entry(
                unit,
                int(max(0, bearer_fnp)),
                source="Iron Resolve",
                tag="iron_resolve_bearer",
            )
            unit.special_rules["enhancement_iron_resolve_unit_fnp"] = int(max(0, int(unit_fnp)))
            unit.special_rules["enhancement_iron_resolve_once_key"] = once_key
            unit.special_rules["enhancement_iron_resolve_source"] = "Iron Resolve"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "prescient flash" or enh_id == "000009835002":
            if not is_angelic_inheritors:
                return
            unit.special_rules["enhancement_prescient_flash"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            scout_distance = _coerce_int(params.get("scouts_distance", 6) or 6, default=6)
            unit.special_rules["enhancement_scout_distance"] = max(
                int(unit.special_rules.get("enhancement_scout_distance", 0) or 0),
                int(max(0, scout_distance)),
            )
            unit.special_rules["enhancement_prescient_flash_source"] = "Prescient Flash"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "troubling visions" or enh_id == "000009835003":
            if not is_angelic_inheritors:
                return
            unit.special_rules["enhancement_troubling_visions"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            once_key = str(params.get("once_per_battle_key", "troubling_visions") or "troubling_visions").strip().lower()
            unit.special_rules["enhancement_troubling_visions_once_key"] = once_key
            unit.special_rules["enhancement_troubling_visions_source"] = "Troubling Visions"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_troubling_visions_bearer_model_id"] = bearer_id

        if name == "blazing icon" or enh_id == "000009835004":
            if not is_angelic_inheritors:
                return
            unit.special_rules["enhancement_blazing_icon"] = True
            unit.special_rules["enhancement_blazing_icon_source"] = "Blazing Icon"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "ordained sacrifice" or enh_id == "000009835005":
            if not is_angelic_inheritors:
                return
            unit.special_rules["enhancement_ordained_sacrifice"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            roll_min = _coerce_int(params.get("roll_min", 2) or 2, default=2)
            return_wounds = _coerce_int(params.get("wounds_on_return", 3) or 3, default=3)
            key = str(params.get("return_on_death_key", "ordained_sacrifice") or "ordained_sacrifice").strip().lower()
            unit.special_rules["enhancement_ordained_sacrifice_roll_min"] = int(max(2, roll_min))
            unit.special_rules["enhancement_ordained_sacrifice_wounds"] = int(max(1, return_wounds))
            unit.special_rules["enhancement_ordained_sacrifice_key"] = key if key else "ordained_sacrifice"
            unit.special_rules["enhancement_ordained_sacrifice_source"] = "Ordained Sacrifice"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_ordained_sacrifice_bearer_model_id"] = bearer_id
            refresh_return = getattr(unit, "_refresh_return_on_death_flags", None)
            if callable(refresh_return):
                refresh_return()

        if name == "incendiary animus" or enh_id == "000010392002":
            if not is_companions_of_vehemence:
                return
            unit.special_rules["enhancement_incendiary_animus"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            ap_bonus = _coerce_int(params.get("ap_bonus", 1) or 1, default=1)
            unit.special_rules["enhancement_incendiary_animus_ap_bonus"] = int(max(0, ap_bonus))
            unit.special_rules["enhancement_incendiary_animus_source"] = "Incendiary Animus"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_incendiary_animus_bearer_model_id"] = bearer_id

        if name == "oathbound exemplar" or enh_id == "000010392003":
            if not is_companions_of_vehemence:
                return
            unit.special_rules["enhancement_oathbound_exemplar"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            advance_bonus = _coerce_int(params.get("advance_bonus", 1) or 1, default=1)
            allow_action_after_advance = bool(params.get("allow_action_after_advance", True))
            unit.special_rules["enhancement_oathbound_exemplar_advance_bonus"] = int(max(0, advance_bonus))
            unit.special_rules["enhancement_oathbound_exemplar_allow_action_after_advance"] = bool(
                allow_action_after_advance
            )
            unit.special_rules["enhancement_oathbound_exemplar_source"] = "Oathbound Exemplar"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_oathbound_exemplar_bearer_model_id"] = bearer_id

        if name == "merciless denunciation" or enh_id == "000010392004":
            if not is_companions_of_vehemence:
                return
            unit.special_rules["enhancement_merciless_denunciation"] = True
            unit.special_rules["enhancement_merciless_denunciation_source"] = "Merciless Denunciation"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_merciless_denunciation_bearer_model_id"] = bearer_id

        if name == "zealous vanguard" or enh_id == "000010392005":
            if not is_companions_of_vehemence:
                return
            unit.special_rules["enhancement_zealous_vanguard"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            scout_distance = _coerce_int(params.get("scouts_distance", 6) or 6, default=6)
            unit.special_rules["enhancement_scout_distance"] = max(
                int(unit.special_rules.get("enhancement_scout_distance", 0) or 0),
                int(max(0, scout_distance)),
            )
            unit.special_rules["enhancement_zealous_vanguard_source"] = "Zealous Vanguard"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_zealous_vanguard_bearer_model_id"] = bearer_id

        if name == "indomitable fury" or enh_id == "000008474002":
            if not is_anvil_siege_force:
                return
            unit.special_rules["enhancement_indomitable_fury"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            roll_min = _coerce_int(params.get("roll_min", 2) or 2, default=2)
            wounds_on_return = params.get("wounds_on_return", "full")
            wounds_expr = str(wounds_on_return or "full").strip().lower() if isinstance(wounds_on_return, str) else wounds_on_return
            if isinstance(wounds_expr, str):
                if wounds_expr not in {"full", "d3", "d6"}:
                    wounds_expr = _coerce_int(wounds_expr, default=1)
            else:
                wounds_expr = _coerce_int(wounds_expr, default=1)
            key = str(params.get("return_on_death_key", "indomitable_fury") or "indomitable_fury").strip().lower()
            unit.special_rules["enhancement_indomitable_fury_roll_min"] = int(max(2, roll_min))
            unit.special_rules["enhancement_indomitable_fury_wounds"] = wounds_expr
            unit.special_rules["enhancement_indomitable_fury_key"] = key if key else "indomitable_fury"
            unit.special_rules["enhancement_indomitable_fury_source"] = "Indomitable Fury"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_indomitable_fury_bearer_model_id"] = bearer_id
            refresh_return = getattr(unit, "_refresh_return_on_death_flags", None)
            if callable(refresh_return):
                refresh_return()

        if name == "fleet commander" or enh_id == "000008474003":
            if not is_anvil_siege_force:
                return
            unit.special_rules["enhancement_fleet_commander"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            once_key = str(params.get("once_per_battle_key", "fleet_commander") or "fleet_commander").strip().lower()
            try:
                marker_range = float(params.get("marker_range", 12.0) or 12.0)
            except Exception:
                marker_range = 12.0
            roll_min = _coerce_int(params.get("roll_min", 3) or 3, default=3)
            mortal_roll = str(params.get("mortal_wounds_roll", "D3") or "D3").strip().upper() or "D3"
            unit.special_rules["enhancement_fleet_commander_once_key"] = once_key if once_key else "fleet_commander"
            unit.special_rules["enhancement_fleet_commander_marker_range"] = float(max(0.0, marker_range))
            unit.special_rules["enhancement_fleet_commander_roll_min"] = int(max(2, roll_min))
            unit.special_rules["enhancement_fleet_commander_mortal_wounds_roll"] = mortal_roll
            unit.special_rules["enhancement_fleet_commander_source"] = "Fleet Commander"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_fleet_commander_bearer_model_id"] = bearer_id

        if name == "stoic defender" or enh_id == "000008474004":
            if not is_anvil_siege_force:
                return
            unit.special_rules["enhancement_stoic_defender"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            fnp_value = _coerce_int(params.get("feel_no_pain", 6) or 6, default=6)
            oc_divisor = _coerce_int(params.get("battle_shock_objective_control_divisor", 2) or 2, default=2)
            unit.special_rules["enhancement_stoic_defender_fnp"] = int(max(2, fnp_value))
            unit.special_rules["enhancement_stoic_defender_oc_divisor"] = int(max(2, oc_divisor))
            unit.special_rules["enhancement_stoic_defender_source"] = "Stoic Defender"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "architect of war" or enh_id == "000008474005":
            if not is_anvil_siege_force:
                return
            unit.special_rules["enhancement_architect_of_war"] = True
            unit.special_rules["enhancement_architect_of_war_source"] = "Architect of War"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if enh_id == "000008482002" or (name == "champion of humanity" and is_firestorm_assault_force):
            if not is_firestorm_assault_force:
                return
            unit.special_rules["enhancement_firestorm_champion_of_humanity"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            requires_leading = bool(params.get("requires_bearer_leading", True))
            exclude_save_modifiers = bool(params.get("exclude_save_modifiers", True))
            unit.special_rules["enhancement_firestorm_champion_of_humanity_requires_bearer_leading"] = bool(
                requires_leading
            )
            unit.special_rules["enhancement_firestorm_champion_of_humanity_exclude_save_modifiers"] = bool(
                exclude_save_modifiers
            )
            unit.special_rules["enhancement_firestorm_champion_of_humanity_source"] = "Champion of Humanity"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_firestorm_champion_of_humanity_bearer_model_id"] = bearer_id

        if enh_id == "000010368002" or (name == "immolator" and is_forgefathers_seekers):
            if not is_forgefathers_seekers:
                return
            unit.special_rules["enhancement_forgefathers_immolator"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            attacks_bonus = _coerce_int(params.get("attacks_bonus", 1) or 1, default=1)
            requires_bearer_alive = bool(params.get("requires_bearer_alive", True))
            unit.special_rules["enhancement_forgefathers_immolator_torrent_attacks_bonus"] = int(
                max(0, attacks_bonus)
            )
            unit.special_rules["enhancement_forgefathers_immolator_requires_bearer_alive"] = bool(
                requires_bearer_alive
            )
            unit.special_rules["enhancement_forgefathers_immolator_source"] = "Immolator"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_forgefathers_immolator_bearer_model_id"] = bearer_id

        if enh_id in {"000008482003", "000010368003"} or (
            name == "war-tempered artifice" and (is_firestorm_assault_force or is_forgefathers_seekers)
        ):
            if not (is_firestorm_assault_force or is_forgefathers_seekers):
                return
            unit.special_rules["enhancement_firestorm_war_tempered_artifice"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            strength_bonus = _coerce_int(params.get("strength_bonus", 3) or 3, default=3)
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0) or 0
            ) + int(max(0, strength_bonus))
            unit.special_rules["enhancement_firestorm_war_tempered_artifice_strength_bonus"] = int(
                max(0, strength_bonus)
            )
            unit.special_rules["enhancement_firestorm_war_tempered_artifice_source"] = "War-tempered Artifice"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_firestorm_war_tempered_artifice_bearer_model_id"] = bearer_id

        if enh_id in {"000008482004", "000010368004"} or (
            name == "forged in battle" and (is_firestorm_assault_force or is_forgefathers_seekers)
        ):
            if not (is_firestorm_assault_force or is_forgefathers_seekers):
                return
            unit.special_rules["enhancement_firestorm_forged_in_battle"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            usage = str(params.get("usage", "turn") or "turn").strip().lower()
            if usage not in {"phase", "turn", "battle_round", "battle"}:
                usage = "turn"
            raw_roll_types = list(params.get("allowed_roll_types", ("hit", "save")) or ("hit", "save"))
            allowed_roll_types = []
            for value in raw_roll_types:
                key = str(value or "").strip().lower()
                if key in {"hit", "wound", "save", "damage"}:
                    allowed_roll_types.append(key)
            if not allowed_roll_types:
                allowed_roll_types = ["hit", "save"]
            requires_leading = bool(params.get("requires_bearer_leading", True))
            unit.special_rules["enhancement_firestorm_forged_in_battle_usage"] = usage
            unit.special_rules["enhancement_firestorm_forged_in_battle_allowed_roll_types"] = tuple(
                allowed_roll_types
            )
            unit.special_rules["enhancement_firestorm_forged_in_battle_requires_bearer_leading"] = bool(
                requires_leading
            )
            unit.special_rules["enhancement_firestorm_forged_in_battle_source"] = "Forged in Battle"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_firestorm_forged_in_battle_bearer_model_id"] = bearer_id

        if enh_id in {"000008482005", "000010368005"} or (
            name == "adamantine mantle" and (is_firestorm_assault_force or is_forgefathers_seekers)
        ):
            if not (is_firestorm_assault_force or is_forgefathers_seekers):
                return
            unit.special_rules["enhancement_firestorm_adamantine_mantle"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            damage_reduction = _coerce_int(params.get("damage_reduction", 1) or 1, default=1)
            set_damage_to = _coerce_int(params.get("set_damage_to", 1) or 1, default=1)
            raw_keywords = list(params.get("if_weapon_keywords_any", ("MELTA", "TORRENT")) or ("MELTA", "TORRENT"))
            required_keywords = tuple(
                sorted({str(value or "").strip().upper() for value in raw_keywords if str(value or "").strip()})
            )
            if not required_keywords:
                required_keywords = ("MELTA", "TORRENT")
            unit.special_rules["enhancement_firestorm_adamantine_mantle_damage_reduction"] = int(
                max(0, damage_reduction)
            )
            unit.special_rules["enhancement_firestorm_adamantine_mantle_set_damage_to"] = int(max(0, set_damage_to))
            unit.special_rules["enhancement_firestorm_adamantine_mantle_weapon_keywords"] = tuple(
                required_keywords
            )
            unit.special_rules["enhancement_firestorm_adamantine_mantle_source"] = "Adamantine Mantle"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_firestorm_adamantine_mantle_bearer_model_id"] = bearer_id

        if name == "target augury web" or enh_id == "000008478002":
            if not is_ironstorm_spearhead:
                return
            unit.special_rules["enhancement_target_augury_web"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            range_inches = _coerce_int(params.get("range", 6) or 6, default=6)
            unit.special_rules["enhancement_target_augury_web_range"] = int(max(1, range_inches))
            unit.special_rules["enhancement_target_augury_web_source"] = "Target Augury Web"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_target_augury_web_bearer_model_id"] = bearer_id

        if name == "the flesh is weak" or enh_id == "000008478003":
            if not is_ironstorm_spearhead:
                return
            unit.special_rules["enhancement_the_flesh_is_weak"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            fnp = _coerce_int(params.get("feel_no_pain", 4) or 4, default=4)
            _ensure_enhancement_fnp_entry(
                unit,
                int(max(2, fnp)),
                source="The Flesh is Weak",
                tag="the_flesh_is_weak_bearer",
                source_model_id=bearer_id,
            )
            unit.special_rules["enhancement_the_flesh_is_weak_fnp"] = int(max(2, fnp))
            unit.special_rules["enhancement_the_flesh_is_weak_source"] = "The Flesh is Weak"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_the_flesh_is_weak_bearer_model_id"] = bearer_id

        if name == "adept of the omnissiah" or enh_id == "000008478004":
            if not is_ironstorm_spearhead:
                return
            unit.special_rules["enhancement_adept_of_the_omnissiah"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            range_inches = _coerce_int(params.get("range", 6) or 6, default=6)
            usage = str(params.get("usage", "battle_round") or "battle_round").strip().lower()
            if usage not in {"battle_round", "battle"}:
                usage = "battle_round"
            unit.special_rules["enhancement_adept_of_the_omnissiah_range"] = int(max(1, range_inches))
            unit.special_rules["enhancement_adept_of_the_omnissiah_usage"] = usage
            unit.special_rules["enhancement_adept_of_the_omnissiah_source"] = "Adept of the Omnissiah"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_adept_of_the_omnissiah_bearer_model_id"] = bearer_id

        if name == "master of machine war" or enh_id == "000008478005":
            if not is_ironstorm_spearhead:
                return
            unit.special_rules["enhancement_master_of_machine_war"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            range_inches = _coerce_int(params.get("range", 6) or 6, default=6)
            unit.special_rules["enhancement_master_of_machine_war_range"] = int(max(1, range_inches))
            unit.special_rules["enhancement_master_of_machine_war_source"] = "Master of Machine War"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_master_of_machine_war_bearer_model_id"] = bearer_id

        if name == "speed of the primarch" or enh_id == "000008376002":
            if not is_liberator_assault_group:
                return
            unit.special_rules["enhancement_speed_of_the_primarch"] = True
            unit.special_rules["enhancement_fight_first_once_per_battle"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            once_key = str(params.get("once_per_battle_key", "speed_of_the_primarch") or "speed_of_the_primarch").strip().lower()
            unit.special_rules["enhancement_speed_of_the_primarch_once_key"] = once_key if once_key else "speed_of_the_primarch"
            unit.special_rules["enhancement_speed_of_the_primarch_source"] = "Speed of the Primarch"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_speed_of_the_primarch_bearer_model_id"] = bearer_id

        if name == "rage-fuelled warrior" or enh_id == "000008376003":
            if not is_liberator_assault_group:
                return
            unit.special_rules["enhancement_rage_fuelled_warrior"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            sustained_hits = _coerce_int(params.get("sustained_hits", 3) or 3, default=3)
            once_key = str(params.get("once_per_battle_key", "rage_fuelled_warrior") or "rage_fuelled_warrior").strip().lower()
            unit.special_rules["enhancement_rage_fuelled_warrior_sustained_hits"] = int(max(1, sustained_hits))
            unit.special_rules["enhancement_rage_fuelled_warrior_once_key"] = once_key if once_key else "rage_fuelled_warrior"
            unit.special_rules["enhancement_rage_fuelled_warrior_source"] = "Rage-fuelled Warrior"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_rage_fuelled_warrior_bearer_model_id"] = bearer_id

        if name == "icon of the angel" or enh_id == "000008376004":
            if not is_liberator_assault_group:
                return
            unit.special_rules["enhancement_icon_of_the_angel"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            excluded = {str(v or "").strip().upper() for v in list(params.get("exclude_target_keywords", ()) or [])}
            requires_exclude_mv = {"MONSTER", "VEHICLE"}.issubset(excluded)
            bs_penalty = _coerce_int(params.get("battleshock_penalty", 1) or 1, default=1)
            unit.special_rules["enemy_fallback_desperate_escape"] = True
            unit.special_rules["enemy_fallback_desperate_escape_exclude_monster_vehicle"] = bool(requires_exclude_mv)
            unit.special_rules["enemy_fallback_desperate_escape_bs_penalty"] = int(max(0, bs_penalty))
            unit.special_rules["enhancement_icon_of_the_angel_source"] = "Icon of the Angel"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_icon_of_the_angel_bearer_model_id"] = bearer_id

        if enh_id == "000008376005" or (name == "gift of foresight" and is_liberator_assault_group):
            if not is_liberator_assault_group:
                return
            unit.special_rules["enhancement_liberator_gift_of_foresight"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            usage = str(params.get("usage", "battle_round") or "battle_round").strip().lower()
            if usage not in {"battle_round", "battle"}:
                usage = "battle_round"
            unit.special_rules["enhancement_liberator_gift_of_foresight_usage"] = usage
            unit.special_rules["enhancement_liberator_gift_of_foresight_source"] = "Gift of Foresight"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_liberator_gift_of_foresight_bearer_model_id"] = bearer_id

        if name == "prescience" or enh_id == "000009785002":
            if not is_librarius_conclave:
                return
            unit.special_rules["enhancement_prescience"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            trigger_range = _coerce_int(params.get("trigger_range", 9) or 9, default=9)
            divination_distance = _coerce_int(params.get("divination_max_distance", 6) or 6, default=6)
            distance_roll = str(params.get("distance_roll", "D6") or "D6").strip().upper() or "D6"
            source_name = str(getattr(self, "name", "") or "Prescience").strip() or "Prescience"
            unit.special_rules["enhancement_prescience_trigger_range"] = int(max(1, trigger_range))
            unit.special_rules["enhancement_prescience_divination_max_distance"] = int(max(1, divination_distance))
            unit.special_rules["enhancement_prescience_distance_roll"] = distance_roll
            unit.special_rules["enhancement_prescience_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_prescience_bearer_model_id"] = bearer_id

        if name == "celerity" or enh_id == "000009785003":
            if not is_librarius_conclave:
                return
            unit.special_rules["enhancement_celerity"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_celerity_charge_after_advance"] = bool(
                params.get("charge_after_advance", True)
            )
            required = str(
                params.get("charge_after_fall_back_when_discipline_active", "BIOMANCY") or "BIOMANCY"
            ).strip().upper()
            unit.special_rules["enhancement_celerity_fall_back_discipline"] = required
            unit.special_rules["enhancement_celerity_source"] = str(getattr(self, "name", "") or "Celerity").strip() or "Celerity"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_celerity_bearer_model_id"] = bearer_id

        if name == "obfuscation" or enh_id == "000009785004":
            if not is_librarius_conclave:
                return
            unit.special_rules["enhancement_obfuscation"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                targeting_cap = int(params.get("telepathy_ranged_targeting_cap", 18) or 18)
            except (TypeError, ValueError):
                targeting_cap = 18
            unit.special_rules["enhancement_obfuscation_telepathy_targeting_cap"] = int(max(1, targeting_cap))
            unit.special_rules["enhancement_obfuscation_source"] = str(getattr(self, "name", "") or "Obfuscation").strip() or "Obfuscation"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_obfuscation_bearer_model_id"] = bearer_id

        if name == "fusillade" or enh_id == "000009785005":
            if not is_librarius_conclave:
                return
            unit.special_rules["enhancement_fusillade"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            anti_monster = _coerce_int(params.get("anti_monster", 5) or 5, default=5)
            anti_vehicle = _coerce_int(params.get("anti_vehicle", 5) or 5, default=5)
            sustained_hits = _coerce_int(params.get("pyromancy_sustained_hits", 1) or 1, default=1)
            range_bonus = _coerce_int(params.get("telekinesis_range_bonus", 6) or 6, default=6)
            unit.special_rules["enhancement_fusillade_anti_monster"] = int(max(2, anti_monster))
            unit.special_rules["enhancement_fusillade_anti_vehicle"] = int(max(2, anti_vehicle))
            unit.special_rules["enhancement_fusillade_pyromancy_sustained_hits"] = int(max(1, sustained_hits))
            unit.special_rules["enhancement_fusillade_telekinesis_range_bonus"] = int(max(1, range_bonus))
            unit.special_rules["enhancement_fusillade_source"] = str(getattr(self, "name", "") or "Fusillade").strip() or "Fusillade"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_fusillade_bearer_model_id"] = bearer_id

        if name == "calibanite armaments" or enh_id == "000009733002":
            if not is_lions_blade_task_force:
                return
            unit.special_rules["enhancement_calibanite_armaments"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            dmg_bonus = _coerce_int(params.get("melee_damage_bonus", 1) or 1, default=1)
            unit.special_rules["enhancement_bearer_melee_damage_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_damage_bonus", 0) or 0
            ) + int(max(0, dmg_bonus))
            unit.special_rules["enhancement_calibanite_armaments_source"] = (
                str(getattr(self, "name", "") or "Calibanite Armaments").strip() or "Calibanite Armaments"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_calibanite_armaments_bearer_model_id"] = bearer_id

        if name == "lord of the hunt" or enh_id == "000009733003":
            if not is_lions_blade_task_force:
                return
            unit.special_rules["enhancement_lord_of_the_hunt"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_lord_of_the_hunt_shoot_after_fall_back"] = bool(
                params.get("shoot_after_fall_back", True)
            )
            unit.special_rules["enhancement_lord_of_the_hunt_charge_after_fall_back"] = bool(
                params.get("charge_after_fall_back", True)
            )
            unit.special_rules["enhancement_lord_of_the_hunt_reroll_desperate_escape"] = bool(
                params.get("reroll_desperate_escape_tests", True)
            )
            unit.special_rules["enhancement_lord_of_the_hunt_source"] = (
                str(getattr(self, "name", "") or "Lord of the Hunt").strip() or "Lord of the Hunt"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_lord_of_the_hunt_bearer_model_id"] = bearer_id

        if name == "stalwart champion" or enh_id == "000009733004":
            if not is_lions_blade_task_force:
                return
            unit.special_rules["enhancement_stalwart_champion"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            oc_bonus = _coerce_int(params.get("objective_control_bonus", 1) or 1, default=1)
            unit.special_rules["enhancement_stalwart_champion_objective_control_bonus"] = int(max(0, oc_bonus))
            unit.special_rules["enhancement_stalwart_champion_requires_not_battle_shocked"] = bool(
                params.get("requires_not_battle_shocked", True)
            )
            unit.special_rules["enhancement_stalwart_champion_source"] = (
                str(getattr(self, "name", "") or "Stalwart Champion").strip() or "Stalwart Champion"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_stalwart_champion_bearer_model_id"] = bearer_id

        if name == "fulgus magna" or enh_id == "000009733005":
            if not is_lions_blade_task_force:
                return
            unit.special_rules["enhancement_fulgus_magna"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            once_key = str(params.get("once_per_battle_key", "fulgus_magna") or "fulgus_magna").strip().lower()
            if not once_key:
                once_key = "fulgus_magna"
            unit.special_rules["enhancement_fulgus_magna_once_key"] = once_key
            unit.special_rules["enhancement_fulgus_magna_requires_not_engagement_range"] = bool(
                params.get("requires_not_engagement_range", True)
            )
            unit.special_rules["enhancement_fulgus_magna_source"] = (
                str(getattr(self, "name", "") or "Fulgus Magna").strip() or "Fulgus Magna"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_fulgus_magna_bearer_model_id"] = bearer_id
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("opponent_turn_strategic_reserves_ability", None)

        if name == "laurels of thunder" or enh_id == "000010680002":
            if not is_orbital_assault_force:
                return
            unit.special_rules["enhancement_laurels_of_thunder"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_laurels_of_thunder_charge_reroll_on_setup_turn"] = bool(
                params.get("charge_reroll_on_setup_turn", True)
            )
            unit.special_rules["enhancement_laurels_of_thunder_source"] = (
                str(getattr(self, "name", "") or "Laurels of Thunder").strip() or "Laurels of Thunder"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_laurels_of_thunder_bearer_model_id"] = bearer_id

        if name == "veteran of the vanguard" or enh_id == "000010680003":
            if not is_orbital_assault_force:
                return
            unit.special_rules["enhancement_veteran_of_the_vanguard"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            scout_distance = _coerce_int(params.get("scouts_distance", 6) or 6, default=6)
            unit.special_rules["enhancement_scout_distance"] = max(
                int(unit.special_rules.get("enhancement_scout_distance", 0) or 0),
                int(max(0, scout_distance)),
            )
            unit.special_rules["enhancement_veteran_of_the_vanguard_source"] = (
                str(getattr(self, "name", "") or "Veteran of the Vanguard").strip() or "Veteran of the Vanguard"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_veteran_of_the_vanguard_bearer_model_id"] = bearer_id

        if name == "orbital uplink reliquary" or enh_id == "000010680004":
            if not is_orbital_assault_force:
                return
            unit.special_rules["enhancement_orbital_uplink_reliquary"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            max_units = _coerce_int(params.get("max_units", 3) or 3, default=3)
            can_place_in_reserves = bool(params.get("can_place_in_reserves", True))
            raw_filters = list(params.get("redeploy_filters", ("ADEPTUS ASTARTES",)) or ())
            redeploy_filters: list[str] = []
            for keyword in raw_filters:
                key = str(keyword or "").strip().upper()
                if not key:
                    continue
                if key in redeploy_filters:
                    continue
                redeploy_filters.append(key)
            source_name = (
                str(getattr(self, "name", "") or "Orbital Uplink Reliquary").strip()
                or "Orbital Uplink Reliquary"
            )
            unit.special_rules["enhancement_orbital_uplink_reliquary_max_units"] = int(max(1, max_units))
            unit.special_rules["enhancement_orbital_uplink_reliquary_can_place_in_reserves"] = bool(
                can_place_in_reserves
            )
            if redeploy_filters:
                unit.special_rules["enhancement_orbital_uplink_reliquary_filters"] = list(redeploy_filters)
            unit.special_rules["enhancement_orbital_uplink_reliquary_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_orbital_uplink_reliquary_bearer_model_id"] = bearer_id

        if name == "dedicated gunship" or enh_id == "000010680005":
            if not is_orbital_assault_force:
                return
            unit.special_rules["enhancement_dedicated_gunship"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            once_key = str(params.get("once_per_battle_key", "dedicated_gunship") or "dedicated_gunship").strip().lower()
            if not once_key:
                once_key = "dedicated_gunship"
            unit.special_rules["enhancement_dedicated_gunship_once_key"] = once_key
            unit.special_rules["enhancement_dedicated_gunship_requires_not_engagement_range"] = bool(
                params.get("requires_not_engagement_range", True)
            )
            unit.special_rules["enhancement_dedicated_gunship_source"] = (
                str(getattr(self, "name", "") or "Dedicated Gunship").strip() or "Dedicated Gunship"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_dedicated_gunship_bearer_model_id"] = bearer_id
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("opponent_turn_strategic_reserves_ability", None)

        if name == "seals of reconquest" or enh_id == "000010684002":
            if not is_reclamation_force:
                return
            unit.special_rules["enhancement_seals_of_reconquest"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            invuln = _coerce_int(params.get("invulnerable_save", 5) or 5, default=5)
            invuln = int(max(2, min(7, invuln)))
            source_name = (
                str(getattr(self, "name", "") or "Seals of Reconquest").strip() or "Seals of Reconquest"
            )
            entries = list(unit.special_rules.get("bearer_unit_invulnerable_save", []) or [])
            entry = {"value": int(invuln), "source": source_name}
            found = False
            for existing in entries:
                if not isinstance(existing, dict):
                    continue
                try:
                    val = int(existing.get("value"))
                except (TypeError, ValueError):
                    continue
                src = str(existing.get("source", "") or "").strip()
                if val == int(invuln) and src == source_name:
                    found = True
                    break
            if not found:
                entries.append(entry)
            unit.special_rules["bearer_unit_invulnerable_save"] = entries
            unit.special_rules["enhancement_seals_of_reconquest_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_seals_of_reconquest_bearer_model_id"] = bearer_id

        if name == "avenging avatar (aura)" or enh_id == "000010684003":
            if not is_reclamation_force:
                return
            unit.special_rules["enhancement_avenging_avatar"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            aura_range = float(getattr(desc, "range_in", 0.0) or 0.0)
            if aura_range <= 0:
                aura_range = float(_coerce_int(params.get("range", 9) or 9, default=9))
            unit.special_rules["enhancement_avenging_avatar_range"] = float(max(0.0, aura_range))
            unit.special_rules["enhancement_avenging_avatar_source"] = (
                str(getattr(self, "name", "") or "Avenging Avatar (Aura)").strip() or "Avenging Avatar (Aura)"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_avenging_avatar_bearer_model_id"] = bearer_id

        if name == "scroll of proclamation" or enh_id == "000010684004":
            if not is_reclamation_force:
                return
            unit.special_rules["enhancement_scroll_of_proclamation"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_charge_reroll_if_target_on_objective"] = bool(
                params.get("charge_reroll_if_target_on_objective", True)
            )
            unit.special_rules["enhancement_scroll_of_proclamation_source"] = (
                str(getattr(self, "name", "") or "Scroll of Proclamation").strip() or "Scroll of Proclamation"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_scroll_of_proclamation_bearer_model_id"] = bearer_id

        if name == "liberatum" or enh_id == "000010684005":
            if not is_reclamation_force:
                return
            unit.special_rules["enhancement_liberatum"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_liberatum_reroll_hit"] = bool(params.get("reroll_hit", True))
            unit.special_rules["enhancement_liberatum_reroll_wound"] = bool(params.get("reroll_wound", True))
            unit.special_rules["enhancement_liberatum_requires_target_within_objective_range"] = bool(
                params.get("requires_target_within_objective_range", True)
            )
            unit.special_rules["enhancement_liberatum_source"] = (
                str(getattr(self, "name", "") or "Liberatum").strip() or "Liberatum"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_liberatum_bearer_model_id"] = bearer_id

        if name == "eye of the primarch" or enh_id == "000010676002":
            if not is_bastion_task_force:
                return
            unit.special_rules["enhancement_eye_of_the_primarch"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            keywords: list[str] = []
            seen_keywords: set[str] = set()
            for keyword in list(params.get("keywords", ("PRECISION",)) or []):
                kw = str(keyword or "").strip().upper()
                if not kw or kw in seen_keywords:
                    continue
                seen_keywords.add(kw)
                keywords.append(kw)
            if keywords:
                unit.special_rules["enhancement_eye_of_the_primarch_keywords"] = keywords
            unit.special_rules["enhancement_eye_of_the_primarch_source"] = "Eye of the Primarch"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "hero of the chapter" or enh_id == "000010676003":
            if not is_bastion_task_force:
                return
            unit.special_rules["enhancement_hero_of_the_chapter"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            keyword = str(params.get("keyword", "BATTLELINE") or "BATTLELINE").strip().upper()
            if keyword:
                unit.special_rules["enhancement_hero_of_the_chapter_keyword"] = keyword
            unit.special_rules["enhancement_hero_of_the_chapter_source"] = "Hero of the Chapter"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "blades of valour" or enh_id == "000010676004":
            if not is_bastion_task_force:
                return
            unit.special_rules["enhancement_blades_of_valour"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            ap_bonus = _coerce_int(params.get("ap_bonus", 1) or 1, default=1)
            unit.special_rules["enhancement_blades_of_valour_ap_bonus"] = int(max(0, ap_bonus))
            unit.special_rules["enhancement_blades_of_valour_source"] = "Blades of Valour"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "bombast omnivox" or enh_id == "000010676005":
            if not is_bastion_task_force:
                return
            unit.special_rules["enhancement_bombast_omnivox"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            roll_min = _coerce_int(params.get("roll_min", 4) or 4, default=4)
            cp_gain = _coerce_int(params.get("cp_gain", 1) or 1, default=1)
            roll_bonus = _coerce_int(params.get("roll_bonus", 1) or 1, default=1)
            bonus_keyword = str(
                params.get("roll_bonus_if_target_has_keyword", "BATTLELINE") or "BATTLELINE"
            ).strip().upper()
            source_name = "Bombast Omnivox"
            unit.special_rules["enhancement_bombast_omnivox_source"] = source_name
            specs = list(unit.special_rules.get("stratagem_target_cp_refund_specs", []) or [])
            spec = {
                "roll_min": int(max(2, roll_min)),
                "cp_gain": int(max(1, cp_gain)),
                "name": source_name,
                "description": str(getattr(self, "description", "") or ""),
            }
            if roll_bonus > 0 and bonus_keyword:
                spec["roll_bonus"] = int(roll_bonus)
                spec["roll_bonus_if_target_has_keyword"] = bonus_keyword
            if bearer_id:
                spec["source_model_id"] = bearer_id
            dedupe_key = (
                int(spec.get("roll_min", 0) or 0),
                int(spec.get("cp_gain", 0) or 0),
                str(spec.get("name", "") or "").strip().lower(),
                int(spec.get("roll_bonus", 0) or 0),
                str(spec.get("roll_bonus_if_target_has_keyword", "") or "").strip().upper(),
                str(spec.get("source_model_id", "") or "").strip(),
            )
            seen_spec_keys = set()
            deduped_specs: list[dict] = []
            for existing in specs:
                key = (
                    int(existing.get("roll_min", 0) or 0),
                    int(existing.get("cp_gain", 0) or 0),
                    str(existing.get("name", "") or "").strip().lower(),
                    int(existing.get("roll_bonus", 0) or 0),
                    str(existing.get("roll_bonus_if_target_has_keyword", "") or "").strip().upper(),
                    str(existing.get("source_model_id", "") or "").strip(),
                )
                if key in seen_spec_keys:
                    continue
                seen_spec_keys.add(key)
                deduped_specs.append(existing)
            if dedupe_key not in seen_spec_keys:
                deduped_specs.append(spec)
            unit.special_rules["stratagem_target_cp_refund_specs"] = deduped_specs
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if (
            name in ("armour of antoninus", "artificer armour")
            or enh_id in ("000010633002", "000008353002")
        ):
            if not (is_blade_of_ultramar or is_gladius_task_force):
                return
            source_name = "Armour of Antoninus"
            if name == "artificer armour" or enh_id == "000008353002":
                source_name = "Artificer Armour"
            unit.special_rules["enhancement_armour_of_antoninus"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            save_value = _coerce_int(params.get("save_characteristic", 2) or 2, default=2)
            fnp_value = _coerce_int(params.get("feel_no_pain", 5) or 5, default=5)
            unit.special_rules["enhancement_armour_of_antoninus_save"] = int(max(2, save_value))
            _ensure_enhancement_fnp_entry(
                unit,
                int(max(2, fnp_value)),
                source=source_name,
                tag="armour_of_antoninus_bearer",
                source_model_id=bearer_id,
            )
            unit.special_rules["enhancement_armour_of_antoninus_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_armour_of_antoninus_bearer_model_id"] = bearer_id

        if (
            name in ("oath of macragge", "the honour vehement")
            or enh_id in ("000010633003", "000008353003")
        ):
            if not (is_blade_of_ultramar or is_gladius_task_force):
                return
            source_name = "Oath of Macragge"
            if name == "the honour vehement" or enh_id == "000008353003":
                source_name = "The Honour Vehement"
            unit.special_rules["enhancement_oath_of_macragge"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            base_bonus = _coerce_int(params.get("base_bonus", 1) or 1, default=1)
            assault_bonus = _coerce_int(params.get("assault_doctrine_bonus", 2) or 2, default=2)
            base_bonus = int(max(0, base_bonus))
            assault_bonus = int(max(base_bonus, assault_bonus))
            unit.special_rules["enhancement_oath_of_macragge_base_bonus"] = int(base_bonus)
            unit.special_rules["enhancement_oath_of_macragge_assault_bonus"] = int(assault_bonus)
            unit.special_rules["enhancement_oath_of_macragge_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_oath_of_macragge_bearer_model_id"] = bearer_id

        if (
            name in ("student of the codex", "adept of the codex")
            or enh_id in ("000010633004", "000008353004")
        ):
            if not (is_blade_of_ultramar or is_gladius_task_force):
                return
            source_name = "Student of the Codex"
            if name == "adept of the codex" or enh_id == "000008353004":
                source_name = "Adept of the Codex"
            unit.special_rules["enhancement_student_of_the_codex"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            doctrine = str(params.get("doctrine", "TACTICAL") or "TACTICAL").strip().upper() or "TACTICAL"
            unit.special_rules["enhancement_student_of_the_codex_doctrine"] = doctrine
            unit.special_rules["enhancement_student_of_the_codex_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_student_of_the_codex_bearer_model_id"] = bearer_id

        if (
            name in ("veteran of behemoth", "fire discipline")
            or enh_id in ("000010633005", "000008353005")
        ):
            if not (is_blade_of_ultramar or is_gladius_task_force):
                return
            source_name = "Veteran of Behemoth"
            if name == "fire discipline" or enh_id == "000008353005":
                source_name = "Fire Discipline"
            unit.special_rules["enhancement_veteran_of_behemoth"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            sustained_hits = _coerce_int(params.get("sustained_hits", 1) or 1, default=1)
            advance_reroll_doctrine = str(
                params.get("advance_reroll_requires_doctrine", "DEVASTATOR") or "DEVASTATOR"
            ).strip().upper()
            if not advance_reroll_doctrine:
                advance_reroll_doctrine = "DEVASTATOR"
            unit.special_rules["enhancement_veteran_of_behemoth_sustained_hits_value"] = int(
                max(0, sustained_hits)
            )
            unit.special_rules["enhancement_veteran_of_behemoth_requires_leading"] = bool(
                params.get("requires_leading", True)
            )
            unit.special_rules["enhancement_veteran_of_behemoth_advance_reroll_doctrine"] = (
                advance_reroll_doctrine
            )
            unit.special_rules["enhancement_veteran_of_behemoth_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_veteran_of_behemoth_bearer_model_id"] = bearer_id

        if name == "paragon of fury" or enh_id == "000010400002":
            if not is_godhammer_assault_force:
                return
            unit.special_rules["enhancement_paragon_of_fury"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            strength_bonus = _coerce_int(params.get("strength_bonus", 2) or 2, default=2)
            disembark_damage_bonus = _coerce_int(
                params.get("disembarked_from_transport_damage_bonus", 1) or 1,
                default=1,
            )
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0) or 0
            ) + int(max(0, strength_bonus))
            unit.special_rules["enhancement_paragon_of_fury_disembark_damage_bonus"] = int(
                max(0, disembark_damage_bonus)
            )
            unit.special_rules["enhancement_paragon_of_fury_source"] = "Paragon of Fury"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_paragon_of_fury_bearer_model_id"] = bearer_id

        if name in ("battle-psalm precentor", "battle psalm precentor") or enh_id == "000010400003":
            if not is_godhammer_assault_force:
                return
            unit.special_rules["enhancement_battle_psalm_precentor"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            test_modifier = _coerce_int(params.get("battleshock_test_modifier", -1) or -1, default=-1)
            unit.special_rules["enhancement_battle_psalm_precentor_battleshock_test_modifier"] = int(test_modifier)
            unit.special_rules["enhancement_battle_psalm_precentor_source"] = "Battle-psalm Precentor"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_battle_psalm_precentor_bearer_model_id"] = bearer_id

        if name in ("augury servo-host", "augury servo host") or enh_id == "000010400004":
            if not is_godhammer_assault_force:
                return
            unit.special_rules["enhancement_augury_servo_host"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            range_val = _coerce_int(params.get("range", 12) or 12, default=12)
            unit.special_rules["enhancement_augury_servo_host_range"] = int(max(1, range_val))
            unit.special_rules["enhancement_augury_servo_host_source"] = "Augury Servo-host"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_augury_servo_host_bearer_model_id"] = bearer_id

        if name == "herald of sacred slaughter" or enh_id == "000010400005":
            if not is_godhammer_assault_force:
                return
            unit.special_rules["enhancement_herald_of_sacred_slaughter"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            scouts_distance = _coerce_int(params.get("scouts_distance", 9) or 9, default=9)
            unit.special_rules["enhancement_herald_of_sacred_slaughter_scouts_distance"] = int(
                max(0, scouts_distance)
            )
            unit.special_rules["enhancement_herald_of_sacred_slaughter_source"] = "Herald of Sacred Slaughter"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_herald_of_sacred_slaughter_bearer_model_id"] = bearer_id

        if name == "spiritus ferrum" or enh_id == "000010623002":
            if not is_hammer_of_avernii:
                return
            unit.special_rules["enhancement_spiritus_ferrum"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            bearer_bonus = _coerce_int(params.get("bearer_melee_attacks_bonus", 1) or 1, default=1)
            other_models_bonus = _coerce_int(
                params.get("unit_other_models_melee_attacks_bonus", 1) or 1,
                default=1,
            )
            once_key = str(
                params.get("once_per_battle_key", "spiritus_ferrum") or "spiritus_ferrum"
            ).strip().lower()
            existing_bearer_bonus = _coerce_int(
                unit.special_rules.get("enhancement_bearer_melee_attacks_bonus", 0) or 0,
                default=0,
            )
            existing_other_bonus = _coerce_int(
                unit.special_rules.get("enhancement_the_imperiums_sword_other_models_bonus", 0) or 0,
                default=0,
            )
            unit.special_rules["enhancement_bearer_melee_attacks_bonus"] = int(
                max(existing_bearer_bonus, max(0, int(bearer_bonus)))
            )
            # Reuse existing once-per-battle start-of-phase helper for other models.
            unit.special_rules["enhancement_the_imperiums_sword"] = True
            unit.special_rules["enhancement_the_imperiums_sword_other_models_bonus"] = int(
                max(existing_other_bonus, max(0, int(other_models_bonus)))
            )
            unit.special_rules["enhancement_the_imperiums_sword_once_key"] = (
                once_key if once_key else "spiritus_ferrum"
            )
            unit.special_rules["enhancement_the_imperiums_sword_source"] = "Spiritus Ferrum"
            unit.special_rules["enhancement_spiritus_ferrum_source"] = "Spiritus Ferrum"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_spiritus_ferrum_bearer_model_id"] = bearer_id

        if (
            name in ("medusan roar (aura)", "medusan roar aura", "medusan roar")
            or enh_id == "000010623003"
        ):
            if not is_hammer_of_avernii:
                return
            unit.special_rules["enhancement_medusan_roar"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            range_raw = params.get("range", getattr(desc, "range_in", 6.0) if desc is not None else 6.0)
            try:
                aura_range = float(range_raw if range_raw is not None else 6.0)
            except Exception:
                aura_range = 6.0
            once_key = str(params.get("once_per_battle_key", "medusan_roar") or "medusan_roar").strip().lower()
            once_roll = (
                str(params.get("once_per_battle_models_destroyed_roll", "D3") or "D3").strip().upper()
                or "D3"
            )
            # Reuse existing battle-shock fail destroy-model machinery.
            unit.special_rules["enhancement_fear_made_manifest"] = True
            unit.special_rules["enhancement_fear_made_manifest_range"] = float(max(0.0, aura_range))
            unit.special_rules["enhancement_fear_made_manifest_once_key"] = once_key if once_key else "medusan_roar"
            unit.special_rules["enhancement_fear_made_manifest_once_roll"] = once_roll
            unit.special_rules["enhancement_fear_made_manifest_source"] = "Medusan Roar (Aura)"
            unit.special_rules["enhancement_medusan_roar_source"] = "Medusan Roar (Aura)"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_medusan_roar_bearer_model_id"] = bearer_id

        if name == "iron laurel" or enh_id == "000010623004":
            if not is_hammer_of_avernii:
                return
            unit.special_rules["enhancement_iron_laurel"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            bearer_oc_bonus = _coerce_int(params.get("bearer_objective_control_bonus", 1) or 1, default=1)
            other_models_bonus = _coerce_int(
                params.get("unit_other_models_objective_control_bonus", 1) or 1,
                default=1,
            )
            once_key = str(params.get("once_per_battle_key", "iron_laurel") or "iron_laurel").strip().lower()
            existing_other_bonus = _coerce_int(
                unit.special_rules.get("enhancement_rites_of_war_other_models_bonus", 0) or 0,
                default=0,
            )
            # Reuse existing start-of-phase Objective Control bonus machinery.
            unit.special_rules["enhancement_rites_of_war"] = True
            unit.special_rules["enhancement_rites_of_war_bearer_oc_bonus"] = int(max(0, int(bearer_oc_bonus)))
            unit.special_rules["enhancement_rites_of_war_other_models_bonus"] = int(
                max(existing_other_bonus, max(0, int(other_models_bonus)))
            )
            unit.special_rules["enhancement_rites_of_war_once_key"] = once_key if once_key else "iron_laurel"
            unit.special_rules["enhancement_rites_of_war_source"] = "Iron Laurel"
            unit.special_rules["enhancement_iron_laurel_source"] = "Iron Laurel"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_iron_laurel_bearer_model_id"] = bearer_id

        if name == "steel font" or enh_id == "000010623005":
            if not is_hammer_of_avernii:
                return
            unit.special_rules["enhancement_steel_font"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            return_amount = _coerce_int(
                params.get("command_phase_bodyguard_return_amount", 1) or 1,
                default=1,
            )
            ability_key = str(params.get("ability_key", "steel_font") or "steel_font").strip().lower()
            unit.special_rules["enhancement_steel_font_command_phase_return_amount"] = int(
                max(1, int(return_amount))
            )
            unit.special_rules["enhancement_steel_font_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            unit.special_rules["enhancement_steel_font_ability_key"] = ability_key if ability_key else "steel_font"
            unit.special_rules["enhancement_steel_font_source"] = "Steel Font"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_steel_font_bearer_model_id"] = bearer_id

        if name == "champion of the deathwing" or enh_id == "000008774002":
            if not is_inner_circle_task_force:
                return
            unit.special_rules["enhancement_champion_of_the_deathwing"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            crit_threshold = _coerce_int(
                params.get("critical_hit_threshold_within_vowed_objective", 5) or 5,
                default=5,
            )
            unit.special_rules["enhancement_champion_of_the_deathwing_crit_threshold"] = int(
                max(2, int(crit_threshold))
            )
            unit.special_rules["enhancement_champion_of_the_deathwing_source"] = "Champion of the Deathwing"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_champion_of_the_deathwing_bearer_model_id"] = bearer_id

        if name == "eye of the unseen" or enh_id == "000008774003":
            if not is_inner_circle_task_force:
                return
            unit.special_rules["enhancement_eye_of_the_unseen"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            roll_min = _coerce_int(params.get("roll_min", 5) or 5, default=5)
            cp_gain = _coerce_int(params.get("cp_gain", 1) or 1, default=1)
            roll_bonus = _coerce_int(
                params.get("roll_bonus_if_bearer_within_vowed_objective", 1) or 1,
                default=1,
            )
            source_name = "Eye of the Unseen"
            unit.special_rules["enhancement_eye_of_the_unseen_source"] = source_name
            specs = list(unit.special_rules.get("stratagem_target_cp_refund_specs", []) or [])
            spec = {
                "roll_min": int(max(2, roll_min)),
                "cp_gain": int(max(1, cp_gain)),
                "name": source_name,
                "description": str(getattr(self, "description", "") or ""),
            }
            if roll_bonus > 0:
                spec["roll_bonus"] = int(roll_bonus)
                spec["roll_bonus_if_source_model_within_vowed_objective"] = True
            if bearer_id:
                spec["source_model_id"] = bearer_id
            dedupe_key = (
                int(spec.get("roll_min", 0) or 0),
                int(spec.get("cp_gain", 0) or 0),
                str(spec.get("name", "") or "").strip().lower(),
                int(spec.get("roll_bonus", 0) or 0),
                bool(spec.get("roll_bonus_if_source_model_within_vowed_objective", False)),
                str(spec.get("source_model_id", "") or "").strip(),
            )
            seen_spec_keys = set()
            deduped_specs: list[dict] = []
            for existing in specs:
                key = (
                    int(existing.get("roll_min", 0) or 0),
                    int(existing.get("cp_gain", 0) or 0),
                    str(existing.get("name", "") or "").strip().lower(),
                    int(existing.get("roll_bonus", 0) or 0),
                    bool(existing.get("roll_bonus_if_source_model_within_vowed_objective", False)),
                    str(existing.get("source_model_id", "") or "").strip(),
                )
                if key in seen_spec_keys:
                    continue
                seen_spec_keys.add(key)
                deduped_specs.append(existing)
            if dedupe_key not in seen_spec_keys:
                deduped_specs.append(spec)
            unit.special_rules["stratagem_target_cp_refund_specs"] = deduped_specs
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_eye_of_the_unseen_bearer_model_id"] = bearer_id

        if name == "singular will" or enh_id == "000008774004":
            if not is_inner_circle_task_force:
                return
            unit.special_rules["enhancement_singular_will"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            pile_in_bonus = _coerce_int(params.get("pile_in_distance_bonus", 3) or 3, default=3)
            consolidate_bonus = _coerce_int(params.get("consolidate_distance_bonus", 3) or 3, default=3)
            unit.special_rules["enhancement_singular_will_pile_in_distance_bonus"] = int(
                max(0, int(pile_in_bonus))
            )
            unit.special_rules["enhancement_singular_will_consolidate_distance_bonus"] = int(
                max(0, int(consolidate_bonus))
            )
            unit.special_rules["enhancement_singular_will_source"] = "Singular Will"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_singular_will_bearer_model_id"] = bearer_id

        if enh_id == "000008774005" or (name == "deathwing assault" and is_inner_circle_task_force):
            if not is_inner_circle_task_force:
                return
            unit.special_rules["enhancement_inner_circle_deathwing_assault"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            round_bonus = _coerce_int(
                params.get("strategic_reserves_setup_round_bonus", 1) or 1,
                default=1,
            )
            unit.special_rules["enhancement_inner_circle_deathwing_assault_round_bonus"] = int(
                max(0, int(round_bonus))
            )
            unit.special_rules["enhancement_inner_circle_deathwing_assault_requires_deep_strike"] = bool(
                params.get("requires_deep_strike", True)
            )
            unit.special_rules["enhancement_inner_circle_deathwing_assault_source"] = "Deathwing Assault"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_inner_circle_deathwing_assault_bearer_model_id"] = bearer_id

        if name in ("tempered in battle (aura)", "tempered in battle aura", "tempered in battle") or enh_id == "000010155002":
            if not is_wrath_of_the_rock:
                return
            unit.special_rules["enhancement_tempered_in_battle"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            range_raw = params.get("range", getattr(desc, "range_in", 6.0) if desc is not None else 6.0)
            try:
                aura_range = float(range_raw if range_raw is not None else 6.0)
            except Exception:
                aura_range = 6.0
            reroll_tests = {
                str(value or "").strip().lower()
                for value in list(params.get("reroll_tests", ("battle_shock", "leadership")) or ())
                if str(value or "").strip()
            }
            if not reroll_tests:
                reroll_tests = {"battle_shock", "leadership"}
            unit.special_rules["enhancement_tempered_in_battle_range"] = float(max(0.0, aura_range))
            unit.special_rules["enhancement_tempered_in_battle_reroll_battle_shock"] = bool(
                "battle_shock" in reroll_tests
            )
            unit.special_rules["enhancement_tempered_in_battle_reroll_leadership"] = bool(
                "leadership" in reroll_tests
            )
            unit.special_rules["enhancement_tempered_in_battle_source"] = "Tempered in Battle (Aura)"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_tempered_in_battle_bearer_model_id"] = bearer_id

        if name == "ancient weapons" or enh_id == "000010155003":
            if not is_wrath_of_the_rock:
                return
            unit.special_rules["enhancement_ancient_weapons"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            strength_bonus = _coerce_int(params.get("bearer_melee_strength_bonus", 2) or 2, default=2)
            ap_bonus = _coerce_int(params.get("bearer_melee_ap_bonus", 1) or 1, default=1)
            damage_bonus = _coerce_int(params.get("bearer_melee_damage_bonus", 1) or 1, default=1)
            strength_bonus = int(max(0, strength_bonus))
            ap_bonus = int(max(0, ap_bonus))
            damage_bonus = int(max(0, damage_bonus))
            existing_strength = _coerce_int(unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0), default=0)
            existing_ap = _coerce_int(unit.special_rules.get("enhancement_bearer_melee_ap_bonus", 0), default=0)
            existing_damage = _coerce_int(unit.special_rules.get("enhancement_bearer_melee_damage_bonus", 0), default=0)
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(max(existing_strength, strength_bonus))
            unit.special_rules["enhancement_bearer_melee_ap_bonus"] = int(max(existing_ap, ap_bonus))
            unit.special_rules["enhancement_bearer_melee_damage_bonus"] = int(max(existing_damage, damage_bonus))
            unit.special_rules["enhancement_ancient_weapons_strength_bonus"] = int(strength_bonus)
            unit.special_rules["enhancement_ancient_weapons_ap_bonus"] = int(ap_bonus)
            unit.special_rules["enhancement_ancient_weapons_damage_bonus"] = int(damage_bonus)
            unit.special_rules["enhancement_ancient_weapons_source"] = "Ancient Weapons"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_ancient_weapons_bearer_model_id"] = bearer_id

        if enh_id == "000010155004" or (name == "deathwing assault" and is_wrath_of_the_rock):
            if not is_wrath_of_the_rock:
                return
            unit.special_rules["enhancement_wrath_of_the_rock_deathwing_assault"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            round_bonus = _coerce_int(
                params.get("strategic_reserves_setup_round_bonus", 1) or 1,
                default=1,
            )
            unit.special_rules["enhancement_wrath_of_the_rock_deathwing_assault_round_bonus"] = int(
                max(0, int(round_bonus))
            )
            unit.special_rules["enhancement_wrath_of_the_rock_deathwing_assault_requires_deep_strike"] = bool(
                params.get("requires_deep_strike", True)
            )
            unit.special_rules["enhancement_wrath_of_the_rock_deathwing_assault_source"] = "Deathwing Assault"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_wrath_of_the_rock_deathwing_assault_bearer_model_id"] = bearer_id

        if name == "lord of the ravenwing" or enh_id == "000010155005":
            if not is_wrath_of_the_rock:
                return
            unit.special_rules["enhancement_lord_of_the_ravenwing"] = True
            unit.special_rules["enhancement_reroll_advance"] = True
            unit.special_rules["enhancement_charge_reroll"] = True
            unit.special_rules["enhancement_lord_of_the_ravenwing_source"] = "Lord of the Ravenwing"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_lord_of_the_ravenwing_bearer_model_id"] = bearer_id

        if name == "pyrebrand" or enh_id == "000009843002":
            if not is_wrathful_procession:
                return
            unit.special_rules["enhancement_pyrebrand"] = True
            unit.special_rules["enhancement_pyrebrand_source"] = "Pyrebrand"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_pyrebrand_bearer_model_id"] = bearer_id

        if name == "sacred rage" or enh_id == "000009843003":
            if not is_wrathful_procession:
                return
            unit.special_rules["enhancement_fight_first_once_per_battle"] = True
            unit.special_rules["enhancement_sacred_rage_source"] = "Sacred Rage"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_sacred_rage_bearer_model_id"] = bearer_id

        if name in ("taramond's censer", "taramonds censer", "taramond s censer") or enh_id == "000009843004":
            if not is_wrathful_procession:
                return
            unit.special_rules["enhancement_taramonds_censer"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            test_modifier = _coerce_int(
                params.get("battle_shock_test_modifier", -1) or -1,
                default=-1,
            )
            if test_modifier > 0:
                test_modifier = -int(test_modifier)
            unit.special_rules["enhancement_taramonds_censer_battle_shock_test_modifier"] = int(test_modifier)
            unit.special_rules["enhancement_taramonds_censer_source"] = "Taramond's Censer"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_taramonds_censer_bearer_model_id"] = bearer_id

        if name == "benediction of fury" or enh_id == "000009843005":
            if not is_wrathful_procession:
                return
            unit.special_rules["enhancement_benediction_of_fury"] = True
            unit.special_rules["enhancement_benediction_of_fury_source"] = "Benediction of Fury"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_benediction_of_fury_bearer_model_id"] = bearer_id

        if name in ("wolves' wisdom", "wolves wisdom") or enh_id == "000009851002":
            if not is_champions_of_fenris:
                return
            unit.special_rules["enhancement_wolves_wisdom"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            base_range = _coerce_int(params.get("base_range", 3) or 3, default=3)
            enhanced_range = _coerce_int(params.get("enhanced_range", 6) or 6, default=6)
            base_range = int(max(0, base_range))
            enhanced_range = int(max(base_range, enhanced_range))
            unit.special_rules["enhancement_wolves_wisdom_base_range"] = int(base_range)
            unit.special_rules["enhancement_wolves_wisdom_range"] = int(enhanced_range)
            unit.special_rules["enhancement_wolves_wisdom_source"] = "Wolves' Wisdom"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_wolves_wisdom_bearer_model_id"] = bearer_id

        if name in ("foes' fate", "foes fate") or enh_id == "000009851003":
            if not is_champions_of_fenris:
                return
            unit.special_rules["enhancement_foes_fate"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            exclude_mv = bool(params.get("exclude_monsters_vehicles", True))
            bs_penalty = _coerce_int(params.get("battleshock_penalty", 1) or 1, default=1)
            unit.special_rules["enhancement_foes_fate_exclude_monster_vehicle"] = bool(exclude_mv)
            unit.special_rules["enhancement_foes_fate_battleshock_penalty"] = int(max(0, bs_penalty))
            unit.special_rules["enhancement_foes_fate_source"] = "Foes' Fate"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_foes_fate_bearer_model_id"] = bearer_id

        if name == "fangrune pendant" or enh_id == "000009851004":
            if not is_champions_of_fenris:
                return
            unit.special_rules["enhancement_fangrune_pendant"] = True
            unit.special_rules["enhancement_fangrune_pendant_source"] = "Fangrune Pendant"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_fangrune_pendant_bearer_model_id"] = bearer_id

        if name == "longstrider" or enh_id == "000009851005":
            if not is_champions_of_fenris:
                return
            unit.special_rules["enhancement_longstrider"] = True
            unit.special_rules["enhancement_charge_reroll"] = True
            unit.special_rules["enhancement_longstrider_source"] = "Longstrider"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_longstrider_bearer_model_id"] = bearer_id

        if name == "wolf-touched" or enh_id == "000010269002":
            if not is_saga_of_the_beastslayer:
                return
            unit.special_rules["enhancement_wolf_touched"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            move_bonus = _coerce_int(params.get("bearer_move_bonus", 2) or 2, default=2)
            move_bonus = int(max(0, move_bonus))
            source_name = str(getattr(self, "name", "") or "Wolf-touched").strip() or "Wolf-touched"
            unit.special_rules["enhancement_wolf_touched_bearer_move_bonus"] = int(move_bonus)
            unit.special_rules["enhancement_wolf_touched_source"] = source_name
            if move_bonus > 0 and bearer is not None:
                effects = getattr(bearer, "_temporary_effects", None)
                if not isinstance(effects, dict):
                    effects = {}
                    bearer._temporary_effects = effects
                effects["enhancement_wolf_touched_move_bonus"] = {
                    "movement_bonus": int(move_bonus),
                    "movement_bonus_source": source_name,
                }
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_wolf_touched_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if name in ("hunter's guile", "hunters guile") or enh_id == "000010269003":
            if not is_saga_of_the_beastslayer:
                return
            unit.special_rules["enhancement_hunters_guile"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            max_units = _coerce_int(params.get("max_units", 3) or 3, default=3)
            can_place_in_reserves = bool(params.get("can_place_in_reserves", True))
            raw_any_groups = list(params.get("redeploy_filter_any_groups", ()) or ())
            filter_any_groups: list[list[str]] = []
            for raw_group in raw_any_groups:
                if isinstance(raw_group, str):
                    group_values = [raw_group]
                else:
                    group_values = list(raw_group or [])
                normalized_group: list[str] = []
                for keyword in group_values:
                    norm_kw = str(keyword or "").strip().upper()
                    if not norm_kw or norm_kw in normalized_group:
                        continue
                    normalized_group.append(norm_kw)
                if normalized_group:
                    filter_any_groups.append(normalized_group)
            source_name = str(getattr(self, "name", "") or "Hunter's Guile").strip() or "Hunter's Guile"
            unit.special_rules["enhancement_hunters_guile_max_units"] = int(max(1, max_units))
            unit.special_rules["enhancement_hunters_guile_can_place_in_reserves"] = bool(can_place_in_reserves)
            if filter_any_groups:
                unit.special_rules["enhancement_hunters_guile_filter_any_groups"] = [
                    list(group) for group in filter_any_groups
                ]
            unit.special_rules["enhancement_hunters_guile_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_hunters_guile_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if name in ("elder's guidance", "elders guidance") or enh_id == "000010269004":
            if not is_saga_of_the_beastslayer:
                return
            unit.special_rules["enhancement_elders_guidance"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            once_key = str(params.get("once_per_battle_key", "elders_guidance") or "elders_guidance").strip().lower()
            if not once_key:
                once_key = "elders_guidance"
            ap_bonus = _coerce_int(params.get("melee_ap_bonus", 1) or 1, default=1)
            unit.special_rules["enhancement_elders_guidance_once_key"] = once_key
            unit.special_rules["enhancement_elders_guidance_ap_bonus"] = int(max(0, ap_bonus))
            unit.special_rules["enhancement_elders_guidance_requires_bearer_leading_blood_claws"] = bool(
                params.get("requires_bearer_leading_blood_claws", True)
            )
            unit.special_rules["enhancement_elders_guidance_source"] = (
                str(getattr(self, "name", "") or "Elder's Guidance").strip() or "Elder's Guidance"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_elders_guidance_bearer_model_id"] = bearer_id

        if name == "helm of the beastslayer" or enh_id == "000010269005":
            if not is_saga_of_the_beastslayer:
                return
            unit.special_rules["enhancement_helm_of_the_beastslayer"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            ap_worsen = _coerce_int(params.get("ap_worsen", 1) or 1, default=1)
            attacker_keywords: list[str] = []
            for value in list(params.get("attacker_keywords_any", ("CHARACTER", "MONSTER", "VEHICLE")) or []):
                kw = str(value or "").strip().upper()
                if not kw or kw in attacker_keywords:
                    continue
                attacker_keywords.append(kw)
            unit.special_rules["enhancement_helm_of_the_beastslayer_ap_worsen"] = int(max(0, ap_worsen))
            if attacker_keywords:
                unit.special_rules["enhancement_helm_of_the_beastslayer_attacker_keywords_any"] = attacker_keywords
            unit.special_rules["enhancement_helm_of_the_beastslayer_source"] = (
                str(getattr(self, "name", "") or "Helm of the Beastslayer").strip()
                or "Helm of the Beastslayer"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_helm_of_the_beastslayer_bearer_model_id"] = bearer_id

        if name in ("braggart's steel", "braggarts steel") or enh_id == "000010265002":
            if not is_saga_of_the_bold:
                return
            unit.special_rules["enhancement_braggarts_steel"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            strength_bonus = _coerce_int(params.get("strength_bonus", 2) or 2, default=2)
            damage_bonus_if_boast = _coerce_int(
                params.get("damage_bonus_if_unit_has_boast", 1) or 1,
                default=1,
            )
            existing_strength_bonus = _coerce_int(
                unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0) or 0,
                default=0,
            )
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(
                max(existing_strength_bonus, max(0, int(strength_bonus)))
            )
            unit.special_rules["enhancement_braggarts_steel_damage_bonus_on_boast"] = int(
                max(0, int(damage_bonus_if_boast))
            )
            unit.special_rules["enhancement_braggarts_steel_source"] = "Braggart's Steel"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_braggarts_steel_bearer_model_id"] = bearer_id

        if name == "skjald" or enh_id == "000010265003":
            if not is_saga_of_the_bold:
                return
            unit.special_rules["enhancement_skjald"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            cp_gain = _coerce_int(params.get("cp_gain", 1) or 1, default=1)
            unit.special_rules["enhancement_skjald_cp_gain"] = int(max(0, int(cp_gain)))
            unit.special_rules["enhancement_skjald_source"] = "Skjald"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_skjald_bearer_model_id"] = bearer_id

        if name == "hordeslayer" or enh_id == "000010265004":
            if not is_saga_of_the_bold:
                return
            unit.special_rules["enhancement_hordeslayer"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                trigger_range = float(params.get("range", 6) or 6)
            except Exception:
                trigger_range = 6.0
            attacks_bonus = _coerce_int(params.get("attacks_bonus", 2) or 2, default=2)
            attacks_bonus_with_boast = _coerce_int(
                params.get("attacks_bonus_with_boast", 3) or 3,
                default=3,
            )
            base_bonus = int(max(0, int(attacks_bonus)))
            boosted_bonus = int(max(base_bonus, int(attacks_bonus_with_boast)))
            unit.special_rules["enhancement_hordeslayer_range"] = float(max(0.0, trigger_range))
            unit.special_rules["enhancement_hordeslayer_attacks_bonus"] = base_bonus
            unit.special_rules["enhancement_hordeslayer_attacks_bonus_with_boast"] = boosted_bonus
            unit.special_rules["enhancement_hordeslayer_source"] = "Hordeslayer"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_hordeslayer_bearer_model_id"] = bearer_id

        if name in ("thunderwolf's fortitude", "thunderwolfs fortitude") or enh_id == "000010265005":
            if not is_saga_of_the_bold:
                return
            unit.special_rules["enhancement_thunderwolfs_fortitude"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            roll_min = _coerce_int(params.get("roll_min", 2) or 2, default=2)
            return_wounds = _coerce_int(params.get("wounds_on_return", 3) or 3, default=3)
            key = str(
                params.get("return_on_death_key", "thunderwolfs_fortitude") or "thunderwolfs_fortitude"
            ).strip().lower()
            if not key:
                key = "thunderwolfs_fortitude"
            # Reuse the existing return-on-death enhancement path consumed by Unit return specs.
            unit.special_rules["enhancement_indomitable_champion"] = True
            unit.special_rules["enhancement_indomitable_champion_roll_min"] = int(max(2, roll_min))
            unit.special_rules["enhancement_indomitable_champion_wounds"] = int(max(1, return_wounds))
            unit.special_rules["enhancement_indomitable_champion_key"] = key
            unit.special_rules["enhancement_indomitable_champion_source"] = "Thunderwolf's Fortitude"
            unit.special_rules["enhancement_thunderwolfs_fortitude_source"] = "Thunderwolf's Fortitude"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_thunderwolfs_fortitude_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_indomitable_champion_bearer_model_id"] = bearer_id
            refresh_return = getattr(unit, "_refresh_return_on_death_flags", None)
            if callable(refresh_return):
                refresh_return()

        if name == "swift hunter" or enh_id == "000010261002":
            if not is_saga_of_the_hunter:
                return
            unit.special_rules["enhancement_swift_hunter"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            scout_distance = _coerce_int(params.get("scouts_distance", 7) or 7, default=7)
            unit.special_rules["enhancement_scout_distance"] = max(
                int(unit.special_rules.get("enhancement_scout_distance", 0) or 0),
                int(max(0, scout_distance)),
            )
            unit.special_rules["enhancement_swift_hunter_source"] = "Swift Hunter"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_swift_hunter_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if name == "fenrisian grit" or enh_id == "000010261003":
            if not is_saga_of_the_hunter:
                return
            unit.special_rules["enhancement_fenrisian_grit"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            fnp_value = _coerce_int(params.get("feel_no_pain", 4) or 4, default=4)
            _ensure_enhancement_fnp_entry(
                unit,
                value=int(max(2, fnp_value)),
                source="Fenrisian Grit",
                tag="enhancement_fenrisian_grit",
                source_model_id=bearer_id or None,
            )
            unit.special_rules["enhancement_fenrisian_grit_fnp"] = int(max(2, fnp_value))
            unit.special_rules["enhancement_fenrisian_grit_source"] = "Fenrisian Grit"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_fenrisian_grit_bearer_model_id"] = bearer_id

        if name == "wolf master" or enh_id == "000010261004":
            if not is_saga_of_the_hunter:
                return
            unit.special_rules["enhancement_wolf_master"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            range_value = _coerce_int(params.get("range", 9) or 9, default=9)
            raw_weapon_names = list(params.get("weapon_names", ("teeth and claws", "tyrnak and fenrir")) or ())
            weapon_names: list[str] = []
            for raw_name in raw_weapon_names:
                normalized = str(raw_name or "").strip()
                if not normalized or normalized in weapon_names:
                    continue
                weapon_names.append(normalized)
            if not weapon_names:
                weapon_names = ["teeth and claws", "tyrnak and fenrir"]
            unit.special_rules["enhancement_wolf_master_range"] = int(max(1, range_value))
            unit.special_rules["enhancement_wolf_master_weapon_names"] = list(weapon_names)
            unit.special_rules["enhancement_wolf_master_source"] = "Wolf Master"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_wolf_master_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if name == "feral rage" or enh_id == "000010261005":
            if not is_saga_of_the_hunter:
                return
            unit.special_rules["enhancement_feral_rage"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            base_attacks_bonus = _coerce_int(
                params.get("bearer_melee_attacks_bonus", 1) or 1,
                default=1,
            )
            charge_attacks_bonus = _coerce_int(
                params.get("bearer_melee_attacks_bonus_on_charge", 1) or 1,
                default=1,
            )
            unit.special_rules["enhancement_bearer_melee_attacks_bonus"] = int(
                max(
                    _coerce_int(unit.special_rules.get("enhancement_bearer_melee_attacks_bonus", 0) or 0, default=0),
                    max(0, int(base_attacks_bonus)),
                )
            )
            unit.special_rules["enhancement_feral_rage_charge_bonus"] = int(max(0, int(charge_attacks_bonus)))
            unit.special_rules["enhancement_feral_rage_source"] = "Feral Rage"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_feral_rage_bearer_model_id"] = bearer_id

        if name in ("grimnar's mark", "grimnars mark") or enh_id == "000010660002":
            if not is_saga_of_the_great_wolf:
                return
            unit.special_rules["enhancement_grimnars_mark"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            min_battle_round = _coerce_int(params.get("min_battle_round", 2) or 2, default=2)
            usage_key = str(
                params.get("once_per_battle_round_key", "grimnars_mark_free_stratagem")
                or "grimnars_mark_free_stratagem"
            ).strip().upper()
            if not usage_key:
                usage_key = "GRIMNARS_MARK_FREE_STRATAGEM"
            raw_stratagem_names = list(params.get("stratagem_names", ("RAPID INGRESS", "HEROIC INTERVENTION")) or ())
            stratagem_names: list[str] = []
            for value in raw_stratagem_names:
                key = str(value or "").strip().upper()
                if not key or key in stratagem_names:
                    continue
                stratagem_names.append(key)
            if not stratagem_names:
                stratagem_names = ["RAPID INGRESS", "HEROIC INTERVENTION"]
            raw_attach_names = list(params.get("attach_override_unit_names_any", ("Wolf Guard Terminators",)) or ())
            attach_names: list[str] = []
            for value in raw_attach_names:
                text = str(value or "").strip()
                if not text or text in attach_names:
                    continue
                attach_names.append(text)
            if not attach_names:
                attach_names = ["Wolf Guard Terminators"]
            unit.special_rules["enhancement_grimnars_mark_min_battle_round"] = int(max(1, min_battle_round))
            unit.special_rules["enhancement_grimnars_mark_usage_key"] = usage_key
            unit.special_rules["enhancement_grimnars_mark_stratagem_names"] = list(stratagem_names)
            unit.special_rules["enhancement_grimnars_mark_attach_unit_names"] = list(attach_names)
            unit.special_rules["enhancement_grimnars_mark_source"] = "Grimnar's Mark"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_grimnars_mark_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if name == "howlmaw" or enh_id == "000010660003":
            if not is_saga_of_the_great_wolf:
                return
            unit.special_rules["enhancement_howlmaw"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                range_value = float(params.get("range", 6) or 6)
            except (TypeError, ValueError):
                range_value = 6.0
            test_modifier = _coerce_int(params.get("battleshock_test_modifier", -1) or -1, default=-1)
            if test_modifier > 0:
                test_modifier = -int(test_modifier)
            unit.special_rules["enhancement_howlmaw_range"] = float(max(0.0, range_value))
            unit.special_rules["enhancement_howlmaw_battleshock_test_modifier"] = int(test_modifier)
            unit.special_rules["enhancement_howlmaw_source"] = "Howlmaw"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_howlmaw_bearer_model_id"] = bearer_id

        if name == "chariots of the storm" or enh_id == "000010660004":
            if not is_saga_of_the_great_wolf:
                return
            unit.special_rules["enhancement_chariots_of_the_storm"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            max_units = _coerce_int(params.get("max_units", 3) or 3, default=3)
            can_place_in_reserves = bool(params.get("can_place_in_reserves", True))
            raw_filters = list(params.get("redeploy_filters", ("ADEPTUS ASTARTES",)) or ())
            redeploy_filters: list[str] = []
            for keyword in raw_filters:
                key = str(keyword or "").strip().upper()
                if not key or key in redeploy_filters:
                    continue
                redeploy_filters.append(key)
            if not redeploy_filters:
                redeploy_filters = ["ADEPTUS ASTARTES"]
            unit.special_rules["enhancement_chariots_of_the_storm_max_units"] = int(max(1, max_units))
            unit.special_rules["enhancement_chariots_of_the_storm_can_place_in_reserves"] = bool(can_place_in_reserves)
            unit.special_rules["enhancement_chariots_of_the_storm_filters"] = list(redeploy_filters)
            unit.special_rules["enhancement_chariots_of_the_storm_source"] = "Chariots of the Storm"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_chariots_of_the_storm_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if name in ("skjald's foretelling", "skjalds foretelling") or enh_id == "000010660005":
            if not is_saga_of_the_great_wolf:
                return
            unit.special_rules["enhancement_skjalds_foretelling"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_skjalds_foretelling_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            unit.special_rules["enhancement_skjalds_foretelling_source"] = "Skjald's Foretelling"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_skjalds_foretelling_bearer_model_id"] = bearer_id

        if name == "artisan of war" or enh_id == "000009190002":
            if not is_the_angelic_host:
                return
            unit.special_rules["enhancement_artisan_of_war"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            ap_bonus = _coerce_int(params.get("bearer_weapon_ap_bonus", 1) or 1, default=1)
            save_value = _coerce_int(params.get("save_characteristic", 2) or 2, default=2)
            ap_bonus = int(max(0, ap_bonus))
            save_value = int(max(2, save_value))
            unit.special_rules["enhancement_artisan_of_war_bearer_ap_bonus"] = int(ap_bonus)
            unit.special_rules["enhancement_artisan_of_war_save"] = int(save_value)
            unit.special_rules["enhancement_bearer_melee_ap_bonus"] = int(
                max(
                    _coerce_int(unit.special_rules.get("enhancement_bearer_melee_ap_bonus", 0), default=0),
                    ap_bonus,
                )
            )
            unit.special_rules["enhancement_bearer_ranged_ap_bonus"] = int(
                max(
                    _coerce_int(unit.special_rules.get("enhancement_bearer_ranged_ap_bonus", 0), default=0),
                    ap_bonus,
                )
            )
            unit.special_rules["enhancement_artisan_of_war_source"] = "Artisan of War"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_artisan_of_war_bearer_model_id"] = bearer_id

        if name == "visage of death" or enh_id == "000009190003":
            if not is_the_angelic_host:
                return
            unit.special_rules["enhancement_visage_of_death"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            excluded = [
                str(v or "").strip().upper()
                for v in list(params.get("exclude_keywords_any", ("MONSTER", "VEHICLE")) or ())
                if str(v or "").strip()
            ]
            if not excluded:
                excluded = ["MONSTER", "VEHICLE"]
            unit.special_rules["enhancement_visage_of_death_exclude_keywords_any"] = list(excluded)
            unit.special_rules["enhancement_visage_of_death_source"] = "Visage of Death"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_visage_of_death_bearer_model_id"] = bearer_id

        if name == "archangel's shard" or enh_id == "000009190004":
            if not is_the_angelic_host:
                return
            unit.special_rules["enhancement_archangels_shard"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            anti_keyword = str(params.get("anti_keyword", "CHAOS") or "CHAOS").strip().upper() or "CHAOS"
            anti_value = _coerce_int(params.get("anti_value", 5) or 5, default=5)
            unit.special_rules["enhancement_archangels_shard_anti_keyword"] = anti_keyword
            unit.special_rules["enhancement_archangels_shard_anti_value"] = int(max(2, anti_value))
            unit.special_rules["enhancement_archangels_shard_lance"] = bool(
                "LANCE"
                in {
                    str(v or "").strip().upper()
                    for v in list(params.get("keywords", ("LANCE",)) or ())
                    if str(v or "").strip()
                }
            )
            unit.special_rules["enhancement_archangels_shard_source"] = "Archangel's Shard"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_archangels_shard_bearer_model_id"] = bearer_id

        if name == "gleaming pinions" or enh_id == "000009190005":
            if not is_the_angelic_host:
                return
            unit.special_rules["enhancement_gleaming_pinions"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            trigger_range = _coerce_int(params.get("trigger_range", 9) or 9, default=9)
            max_distance = _coerce_int(params.get("max_reactive_move_distance", 6) or 6, default=6)
            trigger_actions: list[str] = []
            for value in list(params.get("trigger_actions", ("move", "advance", "fall_back")) or ()):
                action_key = str(value or "").strip().lower()
                if not action_key or action_key in trigger_actions:
                    continue
                trigger_actions.append(action_key)
            if not trigger_actions:
                trigger_actions = ["move", "advance", "fall_back"]
            unit.special_rules["enhancement_gleaming_pinions_trigger_range"] = int(max(1, trigger_range))
            unit.special_rules["enhancement_gleaming_pinions_max_reactive_move_distance"] = int(max(1, max_distance))
            unit.special_rules["enhancement_gleaming_pinions_trigger_actions"] = list(trigger_actions)
            unit.special_rules["enhancement_gleaming_pinions_requires_not_engaged"] = bool(
                params.get("requires_not_engaged", True)
            )
            unit.special_rules["enhancement_gleaming_pinions_once_per_turn"] = bool(
                params.get("once_per_turn", True)
            )
            unit.special_rules["enhancement_gleaming_pinions_source"] = "Gleaming Pinions"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_gleaming_pinions_bearer_model_id"] = bearer_id

        if name in ("sanguinius' grace", "sanguinius grace") or enh_id == "000009186002":
            if not is_the_lost_brethren:
                return
            unit.special_rules["enhancement_sanguinius_grace"] = True
            # Reuse existing bonus-fight UI/decision flow.
            unit.special_rules["enhancement_rise_to_challenge"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            once_key = str(params.get("once_per_battle_key", "sanguinius_grace") or "sanguinius_grace").strip().lower()
            min_enemy_models = _coerce_int(
                params.get("min_enemy_models_in_engagement_range", 3) or 3,
                default=3,
            )
            unit.special_rules["enhancement_sanguinius_grace_once_key"] = once_key if once_key else "sanguinius_grace"
            unit.special_rules["enhancement_sanguinius_grace_min_enemy_models_in_engagement_range"] = int(
                max(1, min_enemy_models)
            )
            unit.special_rules["enhancement_sanguinius_grace_source"] = "Sanguinius' Grace"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_sanguinius_grace_bearer_model_id"] = bearer_id

        if name == "blood shard" or enh_id == "000009186003":
            if not is_the_lost_brethren:
                return
            unit.special_rules["enhancement_blood_shard"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            roll_min = _coerce_int(params.get("roll_min", 2) or 2, default=2)
            return_wounds = _coerce_int(params.get("wounds_on_return", 3) or 3, default=3)
            key = str(params.get("return_on_death_key", "blood_shard") or "blood_shard").strip().lower()
            unit.special_rules["enhancement_blood_shard_roll_min"] = int(max(2, roll_min))
            unit.special_rules["enhancement_blood_shard_wounds"] = int(max(1, return_wounds))
            unit.special_rules["enhancement_blood_shard_key"] = key if key else "blood_shard"
            unit.special_rules["enhancement_blood_shard_source"] = "Blood Shard"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_blood_shard_bearer_model_id"] = bearer_id
            refresh_return = getattr(unit, "_refresh_return_on_death_flags", None)
            if callable(refresh_return):
                refresh_return()

        if name == "to slay the warmaster" or enh_id == "000009186004":
            if not is_the_lost_brethren:
                return
            unit.special_rules["enhancement_to_slay_the_warmaster"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            once_key = str(
                params.get("once_per_battle_key", "to_slay_the_warmaster") or "to_slay_the_warmaster"
            ).strip().lower()
            dice_count = _coerce_int(params.get("dice_count", 6) or 6, default=6)
            success_on = _coerce_int(params.get("success_on", 4) or 4, default=4)
            unit.special_rules["enhancement_to_slay_the_warmaster_once_key"] = (
                once_key if once_key else "to_slay_the_warmaster"
            )
            unit.special_rules["enhancement_to_slay_the_warmaster_dice_count"] = int(max(1, dice_count))
            unit.special_rules["enhancement_to_slay_the_warmaster_success_on"] = int(max(2, min(6, success_on)))
            unit.special_rules["enhancement_to_slay_the_warmaster_source"] = "To Slay the Warmaster"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_to_slay_the_warmaster_bearer_model_id"] = bearer_id

        if name == "vengeful onslaught" or enh_id == "000009186005":
            if not is_the_lost_brethren:
                return
            unit.special_rules["enhancement_vengeful_onslaught"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            hit_bonus = _coerce_int(params.get("hit_bonus", 1) or 1, default=1)
            unit.special_rules["enhancement_vengeful_onslaught_hit_bonus"] = int(max(0, hit_bonus))
            unit.special_rules["enhancement_vengeful_onslaught_source"] = "Vengeful Onslaught"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_vengeful_onslaught_bearer_model_id"] = bearer_id

        if name == "shroud of heroes" or enh_id == "000008771002":
            if not is_unforgiven_task_force:
                return
            unit.special_rules["enhancement_shroud_of_heroes"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            roll_min = _coerce_int(params.get("roll_min", 2) or 2, default=2)
            return_wounds = _coerce_int(params.get("wounds_on_return", 3) or 3, default=3)
            key = str(params.get("return_on_death_key", "shroud_of_heroes") or "shroud_of_heroes").strip().lower()
            battle_shocked_wounds = str(
                params.get("wounds_on_return_if_battle_shocked", "full")
                or "full"
            ).strip().lower()
            if battle_shocked_wounds not in {"full", "d3", "d6"}:
                battle_shocked_wounds = "full"
            unit.special_rules["enhancement_shroud_of_heroes_roll_min"] = int(max(2, roll_min))
            unit.special_rules["enhancement_shroud_of_heroes_wounds"] = int(max(1, return_wounds))
            unit.special_rules["enhancement_shroud_of_heroes_key"] = key if key else "shroud_of_heroes"
            unit.special_rules["enhancement_shroud_of_heroes_battle_shocked_wounds"] = battle_shocked_wounds
            unit.special_rules["enhancement_shroud_of_heroes_source"] = "Shroud of Heroes"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_shroud_of_heroes_bearer_model_id"] = bearer_id
            refresh_return = getattr(unit, "_refresh_return_on_death_flags", None)
            if callable(refresh_return):
                refresh_return()

        if name == "stubborn tenacity" or enh_id == "000008771003":
            if not is_unforgiven_task_force:
                return
            unit.special_rules["enhancement_stubborn_tenacity"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            hit_bonus = _coerce_int(params.get("hit_bonus", 1) or 1, default=1)
            wound_bonus_bs = _coerce_int(params.get("wound_bonus_if_battle_shocked", 1) or 1, default=1)
            unit.special_rules["enhancement_stubborn_tenacity_hit_bonus"] = int(max(0, hit_bonus))
            unit.special_rules["enhancement_stubborn_tenacity_wound_bonus_if_battle_shocked"] = int(
                max(0, wound_bonus_bs)
            )
            unit.special_rules["enhancement_stubborn_tenacity_requires_below_starting_strength"] = bool(
                params.get("requires_below_starting_strength", True)
            )
            unit.special_rules["enhancement_stubborn_tenacity_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            unit.special_rules["enhancement_stubborn_tenacity_source"] = "Stubborn Tenacity"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_stubborn_tenacity_bearer_model_id"] = bearer_id

        if name == "weapons of the first legion" or enh_id == "000008771004":
            if not is_unforgiven_task_force:
                return
            unit.special_rules["enhancement_weapons_of_the_first_legion"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            base_bonus = _coerce_int(params.get("base_bonus", 1) or 1, default=1)
            battle_shocked_bonus = _coerce_int(
                params.get("battle_shocked_bonus", 2) or 2,
                default=2,
            )
            base_bonus = int(max(0, base_bonus))
            battle_shocked_bonus = int(max(base_bonus, battle_shocked_bonus))
            unit.special_rules["enhancement_bearer_melee_attacks_bonus"] = int(
                max(
                    _coerce_int(unit.special_rules.get("enhancement_bearer_melee_attacks_bonus", 0) or 0, default=0),
                    base_bonus,
                )
            )
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(
                max(
                    _coerce_int(unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0) or 0, default=0),
                    base_bonus,
                )
            )
            unit.special_rules["enhancement_bearer_melee_damage_bonus"] = int(
                max(
                    _coerce_int(unit.special_rules.get("enhancement_bearer_melee_damage_bonus", 0) or 0, default=0),
                    base_bonus,
                )
            )
            extra_bonus = int(max(0, battle_shocked_bonus - base_bonus))
            unit.special_rules["enhancement_weapons_of_the_first_legion_battle_shocked_extra_bonus"] = extra_bonus
            unit.special_rules["enhancement_weapons_of_the_first_legion_source"] = "Weapons of the First Legion"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_weapons_of_the_first_legion_bearer_model_id"] = bearer_id

        if name == "pennant of remembrance" or enh_id == "000008771005":
            if not is_unforgiven_task_force:
                return
            unit.special_rules["enhancement_pennant_of_remembrance"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            fnp_base = _coerce_int(params.get("feel_no_pain", 6) or 6, default=6)
            fnp_battle_shocked = _coerce_int(
                params.get("feel_no_pain_if_battle_shocked", 4) or 4,
                default=4,
            )
            unit.special_rules["enhancement_pennant_of_remembrance_fnp"] = int(max(2, fnp_base))
            unit.special_rules["enhancement_pennant_of_remembrance_fnp_if_battle_shocked"] = int(
                max(2, fnp_battle_shocked)
            )
            unit.special_rules["enhancement_pennant_of_remembrance_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            unit.special_rules["enhancement_pennant_of_remembrance_source"] = "Pennant of Remembrance"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_pennant_of_remembrance_bearer_model_id"] = bearer_id

        if name == "fury of the storm" or enh_id == "000008486002":
            if not is_stormlance_task_force:
                return
            unit.special_rules["enhancement_fury_of_the_storm"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            base_strength_bonus = _coerce_int(
                params.get("base_bearer_melee_strength_bonus", 1) or 1,
                default=1,
            )
            base_ap_bonus = _coerce_int(
                params.get("base_bearer_melee_ap_bonus", 1) or 1,
                default=1,
            )
            charged_strength_bonus = _coerce_int(
                params.get("charged_bearer_melee_strength_bonus", 2) or 2,
                default=2,
            )
            charged_ap_bonus = _coerce_int(
                params.get("charged_bearer_melee_ap_bonus", 2) or 2,
                default=2,
            )
            base_strength_bonus = int(max(0, base_strength_bonus))
            base_ap_bonus = int(max(0, base_ap_bonus))
            charged_strength_bonus = int(max(base_strength_bonus, charged_strength_bonus))
            charged_ap_bonus = int(max(base_ap_bonus, charged_ap_bonus))
            existing_strength = _coerce_int(unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0), default=0)
            existing_ap = _coerce_int(unit.special_rules.get("enhancement_bearer_melee_ap_bonus", 0), default=0)
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(max(existing_strength, base_strength_bonus))
            unit.special_rules["enhancement_bearer_melee_ap_bonus"] = int(max(existing_ap, base_ap_bonus))
            unit.special_rules["enhancement_fury_of_the_storm_charge_extra_strength_bonus"] = int(
                max(0, charged_strength_bonus - base_strength_bonus)
            )
            unit.special_rules["enhancement_fury_of_the_storm_charge_extra_ap_bonus"] = int(
                max(0, charged_ap_bonus - base_ap_bonus)
            )
            unit.special_rules["enhancement_fury_of_the_storm_source"] = "Fury of the Storm"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_fury_of_the_storm_bearer_model_id"] = bearer_id

        if name == "portents of wisdom" or enh_id == "000008486003":
            if not is_stormlance_task_force:
                return
            unit.special_rules["enhancement_portents_of_wisdom"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_portents_of_wisdom_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            unit.special_rules["enhancement_portents_of_wisdom_source"] = "Portents of Wisdom"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_portents_of_wisdom_bearer_model_id"] = bearer_id

        if name == "feinting withdrawal" or enh_id == "000008486004":
            if not is_stormlance_task_force:
                return
            unit.special_rules["enhancement_feinting_withdrawal"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_feinting_withdrawal_shoot_after_fall_back"] = bool(
                params.get("shoot_after_fall_back", True)
            )
            unit.special_rules["enhancement_feinting_withdrawal_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            unit.special_rules["enhancement_feinting_withdrawal_source"] = "Feinting Withdrawal"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_feinting_withdrawal_bearer_model_id"] = bearer_id

        if enh_id == "000008486005" or ((name in ("hunter's instincts", "hunters instincts")) and is_stormlance_task_force):
            if not is_stormlance_task_force:
                return
            unit.special_rules["enhancement_stormlance_hunters_instincts"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            round_bonus = _coerce_int(
                params.get("strategic_reserves_setup_round_bonus", 1) or 1,
                default=1,
            )
            unit.special_rules["enhancement_stormlance_hunters_instincts_round_bonus"] = int(max(0, round_bonus))
            unit.special_rules["enhancement_stormlance_hunters_instincts_source"] = "Hunter's Instincts"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_stormlance_hunters_instincts_bearer_model_id"] = bearer_id

        if name == "the blade driven deep" or enh_id == "000008490002":
            if not is_vanguard_spearhead:
                return
            unit.special_rules["enhancement_the_blade_driven_deep"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_the_blade_driven_deep_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            unit.special_rules["enhancement_the_blade_driven_deep_source"] = "The Blade Driven Deep"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_the_blade_driven_deep_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if name == "ghostweave cloak" or enh_id == "000008490003":
            if not is_vanguard_spearhead:
                return
            unit.special_rules["enhancement_ghostweave_cloak"] = True
            unit.special_rules["enhancement_ghostweave_cloak_stealth"] = True
            unit.special_rules["enhancement_ghostweave_cloak_lone_operative"] = True
            unit.special_rules["enhancement_ghostweave_cloak_source"] = "Ghostweave Cloak"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_ghostweave_cloak_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if name == "execute and redeploy" or enh_id == "000008490004":
            if not is_vanguard_spearhead:
                return
            unit.special_rules["enhancement_execute_and_redeploy"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            move_range = _coerce_int(params.get("move_range", 6) or 6, default=6)
            unit.special_rules["enhancement_execute_and_redeploy_move_range"] = int(max(1, move_range))
            unit.special_rules["enhancement_execute_and_redeploy_requires_not_engagement_range"] = bool(
                params.get("requires_not_engagement_range", True)
            )
            unit.special_rules["enhancement_execute_and_redeploy_requires_bearer_phobos"] = bool(
                params.get("requires_bearer_phobos", True)
            )
            unit.special_rules["enhancement_execute_and_redeploy_once_per_shooting_phase"] = bool(
                params.get("once_per_shooting_phase", True)
            )
            unit.special_rules["enhancement_execute_and_redeploy_source"] = "Execute and Redeploy"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_execute_and_redeploy_bearer_model_id"] = bearer_id

        if name == "shadow war veteran" or enh_id == "000008490005":
            if not is_vanguard_spearhead:
                return
            unit.special_rules["enhancement_shadow_war_veteran"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            aura_range = _coerce_int(params.get("range", 0), default=0)
            if aura_range <= 0:
                try:
                    aura_range = int(getattr(desc, "range_in", 12) or 12)
                except Exception:
                    aura_range = 12
            cp_increase = _coerce_int(params.get("cp_increase", 1) or 1, default=1)
            ability_name = str(params.get("ability_name", "Lord of Deceit (Aura)") or "Lord of Deceit (Aura)").strip()
            if not ability_name:
                ability_name = "Lord of Deceit (Aura)"
            unit.special_rules["enhancement_shadow_war_veteran_range"] = int(max(1, aura_range))
            unit.special_rules["enhancement_shadow_war_veteran_cp_increase"] = int(max(1, cp_increase))
            unit.special_rules["enhancement_shadow_war_veteran_source"] = "Shadow War Veteran"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_shadow_war_veteran_bearer_model_id"] = bearer_id
            try:
                if hasattr(unit, "_refresh_targeted_stratagem_cp_increase_flags"):
                    unit._refresh_targeted_stratagem_cp_increase_flags()
            except Exception:
                pass
            usage_key = "STRATAGEM_CP_INCREASE:SHADOW_WAR_VETERAN"
            spec = {
                "range": int(max(1, aura_range)),
                "keyword": "",
                "name": ability_name,
                "description": str(getattr(self, "description", "") or ""),
                "optional": False,
                "limit": "",
                "max_cp": None,
                "cp_increase": int(max(1, cp_increase)),
                "usage_key": usage_key,
            }
            if bearer_id:
                spec["source_model_id"] = bearer_id
            existing_specs = list(unit.special_rules.get("stratagem_target_cp_increase_aura", []) or [])
            deduped_specs: list[dict] = []
            seen_spec_keys: set[tuple[str, str]] = set()
            for existing_spec in existing_specs + [spec]:
                if not isinstance(existing_spec, dict):
                    continue
                key = (
                    str(existing_spec.get("usage_key", "") or "").strip().upper(),
                    str(existing_spec.get("source_model_id", "") or "").strip().lower(),
                )
                if key in seen_spec_keys:
                    continue
                seen_spec_keys.add(key)
                deduped_specs.append(existing_spec)
            unit.special_rules["stratagem_target_cp_increase_aura"] = deduped_specs

        if name == "imperialis of the eternal crusade" or enh_id == "000010396002":
            if not is_vindication_task_force:
                return
            unit.special_rules["enhancement_imperialis_of_the_eternal_crusade"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            penalty = _coerce_int(params.get("charge_roll_penalty", 2) or 2, default=2)
            unit.special_rules["enhancement_imperialis_of_the_eternal_crusade_charge_roll_penalty"] = int(
                max(0, penalty)
            )
            unit.special_rules["enhancement_imperialis_of_the_eternal_crusade_non_cumulative"] = bool(
                params.get("not_cumulative_with_other_negative_modifiers", True)
            )
            unit.special_rules["enhancement_imperialis_of_the_eternal_crusade_source"] = (
                str(getattr(self, "name", "") or "Imperialis of the Eternal Crusade").strip()
                or "Imperialis of the Eternal Crusade"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_imperialis_of_the_eternal_crusade_bearer_model_id"] = bearer_id

        if name == "consecrating aura" or enh_id == "000010396003":
            if not is_vindication_task_force:
                return
            unit.special_rules["enhancement_consecrating_aura"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            invuln = _coerce_int(params.get("invulnerable_save", 5) or 5, default=5)
            invuln = int(max(2, min(7, invuln)))
            source_name = (
                str(getattr(self, "name", "") or "Consecrating Aura").strip() or "Consecrating Aura"
            )
            entries = list(unit.special_rules.get("bearer_unit_invulnerable_save", []) or [])
            entry = {"value": int(invuln), "source": source_name}
            found = False
            for existing in entries:
                if not isinstance(existing, dict):
                    continue
                try:
                    val = int(existing.get("value"))
                except (TypeError, ValueError):
                    continue
                src = str(existing.get("source", "") or "").strip()
                if val == int(invuln) and src == source_name:
                    found = True
                    break
            if not found:
                entries.append(entry)
            unit.special_rules["bearer_unit_invulnerable_save"] = entries
            unit.special_rules["enhancement_consecrating_aura_source"] = source_name
            unit.special_rules["enhancement_consecrating_aura_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_consecrating_aura_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if (
            enh_id == "000010396004"
            or name in ("orb of the emperor's aegis", "orb of the emperor’s aegis")
        ):
            if not is_vindication_task_force:
                return
            unit.special_rules["enhancement_orb_of_the_emperors_aegis"] = True
            unit.special_rules["bearer_unit_deep_strike"] = True
            unit.special_rules["enhancement_orb_of_the_emperors_aegis_source"] = (
                str(getattr(self, "name", "") or "Orb of the Emperor's Aegis").strip()
                or "Orb of the Emperor's Aegis"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_orb_of_the_emperors_aegis_bearer_model_id"] = bearer_id
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("deep_strike", None)
                cache.pop("opponent_turn_strategic_reserves_ability", None)

        if name == "warden of honour" or enh_id == "000010396005":
            if not is_vindication_task_force:
                return
            unit.special_rules["enhancement_warden_of_honour"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            roll_bonus = _coerce_int(params.get("vengeful_exhortation_roll_bonus", 1) or 1, default=1)
            unit.special_rules["enhancement_warden_of_honour_vengeful_exhortation_roll_bonus"] = int(
                max(0, roll_bonus)
            )
            unit.special_rules["enhancement_warden_of_honour_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            unit.special_rules["enhancement_warden_of_honour_source"] = (
                str(getattr(self, "name", "") or "Warden of Honour").strip() or "Warden of Honour"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_warden_of_honour_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if name in ("master-crafted weapon", "master crafted weapon") or enh_id == "000008778002":
            if not is_company_of_hunters:
                return
            unit.special_rules["enhancement_master_crafted_weapon"] = True
            unit.special_rules["enhancement_bearer_melee_precision"] = True
            unit.special_rules["enhancement_master_crafted_weapon_source"] = "Master-crafted Weapon"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_master_crafted_weapon_bearer_model_id"] = bearer_id

        if name == "mounted strategist" or enh_id == "000008778003":
            if not is_company_of_hunters:
                return
            unit.special_rules["enhancement_mounted_strategist"] = True
            unit.special_rules["enhancement_mounted_strategist_source"] = "Mounted Strategist"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_mounted_strategist_bearer_model_id"] = bearer_id

        if name in ("master of manoeuvre", "master of maneuver") or enh_id == "000008778004":
            if not is_company_of_hunters:
                return
            unit.special_rules["enhancement_master_of_manoeuvre"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            ignore_strategic_points_limit = bool(params.get("ignore_strategic_reserve_points_limit", True))
            setup_round_bonus = _coerce_int(
                params.get("strategic_reserves_setup_round_bonus", 1) or 1,
                default=1,
            )
            unit.special_rules["enhancement_master_of_manoeuvre_ignore_strategic_reserve_points"] = bool(
                ignore_strategic_points_limit
            )
            unit.special_rules["enhancement_master_of_manoeuvre_round_bonus"] = int(max(0, setup_round_bonus))
            unit.special_rules["enhancement_master_of_manoeuvre_source"] = "Master of Manoeuvre"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_master_of_manoeuvre_bearer_model_id"] = bearer_id

        if name == "recon hunter" or enh_id == "000008778005":
            if not is_company_of_hunters:
                return
            unit.special_rules["enhancement_recon_hunter"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            scout_distance = _coerce_int(params.get("scouts_distance", 9) or 9, default=9)
            unit.special_rules["enhancement_scout_distance"] = max(
                int(unit.special_rules.get("enhancement_scout_distance", 0) or 0),
                int(max(0, scout_distance)),
            )
            unit.special_rules["enhancement_recon_hunter_source"] = "Recon Hunter"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_recon_hunter_bearer_model_id"] = bearer_id

        if name == "spearpoint paragon" or enh_id == "000010629002":
            if not is_spearpoint_task_force:
                return
            unit.special_rules["enhancement_spearpoint_paragon"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            base_strength_bonus = _coerce_int(
                params.get("base_bearer_melee_strength_bonus", 1) or 1,
                default=1,
            )
            base_ap_bonus = _coerce_int(
                params.get("base_bearer_melee_ap_bonus", 1) or 1,
                default=1,
            )
            charged_strength_bonus = _coerce_int(
                params.get("charged_bearer_melee_strength_bonus", 2) or 2,
                default=2,
            )
            charged_ap_bonus = _coerce_int(
                params.get("charged_bearer_melee_ap_bonus", 2) or 2,
                default=2,
            )
            base_strength_bonus = int(max(0, base_strength_bonus))
            base_ap_bonus = int(max(0, base_ap_bonus))
            charged_strength_bonus = int(max(base_strength_bonus, charged_strength_bonus))
            charged_ap_bonus = int(max(base_ap_bonus, charged_ap_bonus))

            existing_strength = _coerce_int(unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0), default=0)
            existing_ap = _coerce_int(unit.special_rules.get("enhancement_bearer_melee_ap_bonus", 0), default=0)
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(max(existing_strength, base_strength_bonus))
            unit.special_rules["enhancement_bearer_melee_ap_bonus"] = int(max(existing_ap, base_ap_bonus))
            unit.special_rules["enhancement_spearpoint_paragon_charge_extra_strength_bonus"] = int(
                max(0, charged_strength_bonus - base_strength_bonus)
            )
            unit.special_rules["enhancement_spearpoint_paragon_charge_extra_ap_bonus"] = int(
                max(0, charged_ap_bonus - base_ap_bonus)
            )
            unit.special_rules["enhancement_spearpoint_paragon_source"] = "Spearpoint Paragon"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_spearpoint_paragon_bearer_model_id"] = bearer_id

        if name in ("stormseers' wisdom", "stormseers wisdom") or enh_id == "000010629003":
            if not is_spearpoint_task_force:
                return
            unit.special_rules["enhancement_stormseers_wisdom"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_stormseers_wisdom_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            unit.special_rules["enhancement_stormseers_wisdom_source"] = "Stormseers' Wisdom"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_stormseers_wisdom_bearer_model_id"] = bearer_id

        if name in ("hunter's eye", "hunters eye") or enh_id == "000010629004":
            if not is_spearpoint_task_force:
                return
            unit.special_rules["enhancement_hunters_eye"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            keywords = [
                str(v or "").strip().upper()
                for v in list(params.get("keywords", ("SUSTAINED HITS 1", "IGNORES COVER")) or ())
                if str(v or "").strip()
            ]
            if keywords:
                unit.special_rules["enhancement_hunters_eye_keywords"] = keywords
            unit.special_rules["enhancement_hunters_eye_source"] = "Hunter's Eye"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_hunters_eye_bearer_model_id"] = bearer_id

        if name == "chogorian huntmaster" or enh_id == "000010629005":
            if not is_spearpoint_task_force:
                return
            unit.special_rules["enhancement_chogorian_huntmaster"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            round_bonus = _coerce_int(
                params.get("strategic_reserves_setup_round_bonus", 1) or 1,
                default=1,
            )
            unit.special_rules["enhancement_chogorian_huntmaster_round_bonus"] = int(max(0, round_bonus))
            unit.special_rules["enhancement_chogorian_huntmaster_source"] = "Chogorian Huntmaster"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_chogorian_huntmaster_bearer_model_id"] = bearer_id

        if name == "blackwing shroud" or enh_id == "000010466002":
            if not is_shadowmark_talon:
                return
            unit.special_rules["enhancement_blackwing_shroud"] = True
            unit.special_rules["enhancement_blackwing_shroud_source"] = "Blackwing Shroud"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_blackwing_shroud_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if name == "coronal susurrant" or enh_id == "000010466003":
            if not is_shadowmark_talon:
                return
            unit.special_rules["enhancement_coronal_susurrant"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            aura_range = _coerce_int(params.get("range", 0), default=0)
            if aura_range <= 0:
                try:
                    aura_range = int(getattr(desc, "range_in", 12) or 12)
                except Exception:
                    aura_range = 12
            unit.special_rules["enhancement_coronal_susurrant_range"] = int(max(1, aura_range))
            unit.special_rules["enhancement_coronal_susurrant_source"] = "Coronal Susurrant"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_coronal_susurrant_bearer_model_id"] = bearer_id
            try:
                if hasattr(unit, "_refresh_targeted_stratagem_cp_increase_flags"):
                    unit._refresh_targeted_stratagem_cp_increase_flags()
            except Exception:
                pass
            cp_increase = _coerce_int(params.get("cp_increase", 1) or 1, default=1)
            ability_name = str(params.get("ability_name", "Lord of Deceit (Aura)") or "Lord of Deceit (Aura)").strip()
            if not ability_name:
                ability_name = "Lord of Deceit (Aura)"
            usage_key = "STRATAGEM_CP_INCREASE:CORONAL_SUSURRANT"
            spec = {
                "range": int(max(1, aura_range)),
                "keyword": "",
                "name": ability_name,
                "description": str(getattr(self, "description", "") or ""),
                "optional": False,
                "limit": "",
                "max_cp": None,
                "cp_increase": int(max(1, cp_increase)),
                "usage_key": usage_key,
            }
            if bearer_id:
                spec["source_model_id"] = bearer_id
            existing_specs = list(unit.special_rules.get("stratagem_target_cp_increase_aura", []) or [])
            deduped_specs: list[dict] = []
            seen_spec_keys: set[tuple[str, str]] = set()
            for existing_spec in existing_specs + [spec]:
                if not isinstance(existing_spec, dict):
                    continue
                key = (
                    str(existing_spec.get("usage_key", "") or "").strip().upper(),
                    str(existing_spec.get("source_model_id", "") or "").strip().lower(),
                )
                if key in seen_spec_keys:
                    continue
                seen_spec_keys.add(key)
                deduped_specs.append(existing_spec)
            unit.special_rules["stratagem_target_cp_increase_aura"] = deduped_specs

        if name == "umbral raptor" or enh_id == "000010466004":
            if not is_shadowmark_talon:
                return
            unit.special_rules["enhancement_umbral_raptor"] = True
            unit.special_rules["enhancement_umbral_raptor_stealth"] = True
            unit.special_rules["enhancement_umbral_raptor_lone_operative"] = True
            unit.special_rules["enhancement_umbral_raptor_source"] = "Umbral Raptor"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_umbral_raptor_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if enh_id == "000010466005" or ((name in ("hunter's instincts", "hunters instincts")) and is_shadowmark_talon):
            if not is_shadowmark_talon:
                return
            unit.special_rules["enhancement_hunters_instincts"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            round_bonus = _coerce_int(
                params.get("strategic_reserves_setup_round_bonus", 1) or 1,
                default=1,
            )
            unit.special_rules["enhancement_hunters_instincts_round_bonus"] = int(max(0, round_bonus))
            unit.special_rules["enhancement_hunters_instincts_source"] = "Hunter's Instincts"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_hunters_instincts_bearer_model_id"] = bearer_id

        if name == "champion of the feast" or enh_id == "000010460002":
            if not is_emperors_shield:
                return
            unit.special_rules["enhancement_champion_of_the_feast"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            bearer_bonus = _coerce_int(params.get("bearer_melee_attacks_bonus", 1) or 1, default=1)
            other_models_bonus = _coerce_int(params.get("unit_other_models_melee_attacks_bonus", 1) or 1, default=1)
            once_key = str(params.get("once_per_battle_key", "champion_of_the_feast") or "champion_of_the_feast").strip().lower()
            existing_bearer_bonus = _coerce_int(
                unit.special_rules.get("enhancement_bearer_melee_attacks_bonus", 0) or 0,
                default=0,
            )
            unit.special_rules["enhancement_bearer_melee_attacks_bonus"] = int(
                max(existing_bearer_bonus, max(0, int(bearer_bonus)))
            )
            # Reuse the existing start-of-phase optional activation path for other models.
            unit.special_rules["enhancement_the_imperiums_sword"] = True
            unit.special_rules["enhancement_the_imperiums_sword_other_models_bonus"] = int(max(0, int(other_models_bonus)))
            unit.special_rules["enhancement_the_imperiums_sword_once_key"] = once_key if once_key else "champion_of_the_feast"
            unit.special_rules["enhancement_the_imperiums_sword_source"] = "Champion of the Feast"
            unit.special_rules["enhancement_champion_of_the_feast_source"] = "Champion of the Feast"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_champion_of_the_feast_bearer_model_id"] = bearer_id

        if name == "disciple of rhetoricus" or enh_id == "000010460003":
            if not is_emperors_shield:
                return
            unit.special_rules["enhancement_disciple_of_rhetoricus"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            bearer_oc_bonus = _coerce_int(params.get("bearer_objective_control_bonus", 1) or 1, default=1)
            other_models_bonus = _coerce_int(params.get("unit_other_models_objective_control_bonus", 1) or 1, default=1)
            once_key = str(params.get("once_per_battle_key", "disciple_of_rhetoricus") or "disciple_of_rhetoricus").strip().lower()
            # Reuse the existing start-of-phase optional activation path for Objective Control.
            unit.special_rules["enhancement_rites_of_war"] = True
            unit.special_rules["enhancement_rites_of_war_bearer_oc_bonus"] = int(max(0, int(bearer_oc_bonus)))
            unit.special_rules["enhancement_rites_of_war_other_models_bonus"] = int(max(0, int(other_models_bonus)))
            unit.special_rules["enhancement_rites_of_war_once_key"] = once_key if once_key else "disciple_of_rhetoricus"
            unit.special_rules["enhancement_rites_of_war_source"] = "Disciple of Rhetoricus"
            unit.special_rules["enhancement_disciple_of_rhetoricus_source"] = "Disciple of Rhetoricus"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_disciple_of_rhetoricus_bearer_model_id"] = bearer_id

        if name == "indomitable champion" or enh_id == "000010460004":
            if not is_emperors_shield:
                return
            unit.special_rules["enhancement_indomitable_champion"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            roll_min = _coerce_int(params.get("roll_min", 2) or 2, default=2)
            return_wounds = _coerce_int(params.get("wounds_on_return", 3) or 3, default=3)
            key = str(params.get("return_on_death_key", "indomitable_champion") or "indomitable_champion").strip().lower()
            unit.special_rules["enhancement_indomitable_champion_roll_min"] = int(max(2, roll_min))
            unit.special_rules["enhancement_indomitable_champion_wounds"] = int(max(1, return_wounds))
            unit.special_rules["enhancement_indomitable_champion_key"] = key if key else "indomitable_champion"
            unit.special_rules["enhancement_indomitable_champion_source"] = "Indomitable Champion"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_indomitable_champion_bearer_model_id"] = bearer_id
            refresh_return = getattr(unit, "_refresh_return_on_death_flags", None)
            if callable(refresh_return):
                refresh_return()

        if name == "malodraxian standard" or enh_id == "000010460005":
            if not is_emperors_shield:
                return
            unit.special_rules["enhancement_malodraxian_standard"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            penalty = _coerce_int(params.get("wound_roll_penalty", 1) or 1, default=1)
            unit.special_rules["enhancement_malodraxian_standard_wound_roll_penalty"] = int(max(0, int(penalty)))
            unit.special_rules["enhancement_malodraxian_standard_requires_strength_gt_toughness"] = bool(
                params.get("requires_strength_gt_toughness", True)
            )
            unit.special_rules["enhancement_malodraxian_standard_source"] = "Malodraxian Standard"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_malodraxian_standard_bearer_model_id"] = bearer_id

        if name == "thief of secrets" or enh_id == "000008522002":
            if not is_black_spear_task_force:
                return
            unit.special_rules["enhancement_thief_of_secrets"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            base_bonus = _coerce_int(params.get("base_bonus", 1) or 1, default=1)
            upgraded_bonus = _coerce_int(params.get("upgraded_bonus", 2) or 2, default=2)
            base_bonus = int(max(0, base_bonus))
            upgraded_bonus = int(max(base_bonus, upgraded_bonus))
            unit.special_rules["enhancement_thief_of_secrets_base_bonus"] = int(base_bonus)
            unit.special_rules["enhancement_thief_of_secrets_upgraded_bonus"] = int(upgraded_bonus)
            unit.special_rules["enhancement_thief_of_secrets_upgraded"] = False
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(base_bonus)
            unit.special_rules["enhancement_bearer_melee_damage_bonus"] = int(base_bonus)
            unit.special_rules["enhancement_bearer_melee_ap_bonus"] = int(base_bonus)
            unit.special_rules["enhancement_thief_of_secrets_source"] = "Thief of Secrets"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_thief_of_secrets_bearer_model_id"] = bearer_id

        if name == "osseus key" or enh_id == "000008522003":
            if not is_black_spear_task_force:
                return
            unit.special_rules["enhancement_osseus_key"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                key_range = float(params.get("range", 12.0) or 12.0)
            except Exception:
                key_range = 12.0
            required_keywords: list[str] = []
            seen_required: set[str] = set()
            for kw in list(params.get("required_target_keywords", ("VEHICLE",)) or []):
                norm_kw = str(kw or "").strip().upper()
                if not norm_kw or norm_kw in seen_required:
                    continue
                seen_required.add(norm_kw)
                required_keywords.append(norm_kw)
            excluded_keywords: list[str] = []
            seen_excluded: set[str] = set()
            for kw in list(params.get("excluded_target_keywords", ("TITANIC",)) or []):
                norm_kw = str(kw or "").strip().upper()
                if not norm_kw or norm_kw in seen_excluded:
                    continue
                seen_excluded.add(norm_kw)
                excluded_keywords.append(norm_kw)
            resolution_mode = str(params.get("resolution_mode", "leadership_test") or "leadership_test").strip().lower()
            if not resolution_mode:
                resolution_mode = "leadership_test"
            unit.special_rules["enhancement_osseus_key_range"] = float(max(0.0, key_range))
            unit.special_rules["enhancement_osseus_key_required_target_keywords"] = required_keywords
            unit.special_rules["enhancement_osseus_key_excluded_target_keywords"] = excluded_keywords
            unit.special_rules["enhancement_osseus_key_resolution_mode"] = resolution_mode
            unit.special_rules["enhancement_osseus_key_source"] = "Osseus Key"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_osseus_key_bearer_model_id"] = bearer_id
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache_key = f"model_start_opponent_shooting_phase_disrupt:{bearer_id}"
                cache.pop(cache_key, None)

        if name == "beacon angelis" or enh_id == "000008522004":
            if not is_black_spear_task_force:
                return
            unit.special_rules["enhancement_beacon_angelis"] = True
            unit.special_rules["enhancement_beacon_angelis_source"] = "Beacon Angelis"
            unit.special_rules["enhancement_beacon_angelis_rapid_ingress_discount"] = True
            unit.special_rules["bearer_unit_deep_strike"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_beacon_angelis_bearer_model_id"] = bearer_id
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("deep_strike", None)
                cache.pop("opponent_turn_strategic_reserves_ability", None)

        if name == "the tome of ectoclades" or enh_id == "000008522005":
            if not is_black_spear_task_force:
                return
            unit.special_rules["enhancement_tome_of_ectoclades"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            once_key = str(params.get("once_per_battle_key", "tome_of_ectoclades") or "tome_of_ectoclades").strip().lower()
            if not once_key:
                once_key = "tome_of_ectoclades"
            unit.special_rules["enhancement_tome_of_ectoclades_once_key"] = once_key
            unit.special_rules["enhancement_tome_of_ectoclades_source"] = "The Tome of Ectoclades"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_tome_of_ectoclades_bearer_model_id"] = bearer_id

        if name == "gift of foresight" and enh_id == "000009899004":
            if not is_warhost:
                return
            unit.special_rules["enhancement_free_command_reroll_once_per_battle_round"] = True

        if name == "phoenix gem" or enh_id == "000009899002":
            if not is_warhost:
                return
            unit.special_rules["enhancement_phoenix_gem"] = True

        if name == "psychic destroyer" or enh_id == "000009899005":
            if not is_warhost:
                return
            unit.special_rules["enhancement_psychic_destroyer_damage_bonus"] = int(
                unit.special_rules.get("enhancement_psychic_destroyer_damage_bonus", 0) or 0
            ) + 1

        if name == "craftworld's champion" or enh_id == "000009911002":
            if not is_guardian_battlehost:
                return
            unit.special_rules["enhancement_craftworlds_champion"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            try:
                oc_value = int(params.get("objective_control", 5) or 5)
            except Exception:
                oc_value = 5
            unit.special_rules["enhancement_craftworlds_champion_objective_control"] = int(max(1, oc_value))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "ethereal pathway" or enh_id == "000009911003":
            if not is_guardian_battlehost:
                return
            unit.special_rules["enhancement_ethereal_pathway"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "protector of the paths" or enh_id == "000009911004":
            if not is_guardian_battlehost:
                return
            unit.special_rules["enhancement_protector_of_paths"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            try:
                base_threshold = int(params.get("base_overwatch_hit_threshold", 5) or 5)
            except Exception:
                base_threshold = 5
            try:
                controlled_threshold = int(params.get("controlled_objective_hit_threshold", 4) or 4)
            except Exception:
                controlled_threshold = 4
            unit.special_rules["enhancement_protector_of_paths_base_threshold"] = int(max(2, base_threshold))
            unit.special_rules["enhancement_protector_of_paths_controlled_threshold"] = int(max(2, controlled_threshold))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "breath of vaul" or enh_id == "000009911005":
            if not is_guardian_battlehost:
                return
            unit.special_rules["enhancement_breath_of_vaul"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            flamer_names = tuple(str(v or "").strip() for v in list(params.get("flamer_weapon_names", ("flamer",))) if str(v or "").strip())
            fusion_names = tuple(str(v or "").strip() for v in list(params.get("fusion_weapon_names", ("fusion gun",))) if str(v or "").strip())
            if flamer_names:
                unit.special_rules["enhancement_breath_of_vaul_flamer_weapon_names"] = list(flamer_names)
            if fusion_names:
                unit.special_rules["enhancement_breath_of_vaul_fusion_weapon_names"] = list(fusion_names)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "infamy (aura)" or enh_id == "000010704002":
            if not is_corsair_veterans:
                return
            unit.special_rules["enhancement_infamy_aura"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            try:
                aura_range = float(params.get("range", 3.0) or 3.0)
            except Exception:
                aura_range = 3.0
            try:
                oc_penalty = int(params.get("objective_control_penalty", 1) or 1)
            except Exception:
                oc_penalty = 1
            try:
                oc_minimum = int(params.get("objective_control_minimum", 1) or 1)
            except Exception:
                oc_minimum = 1
            unit.special_rules["enhancement_infamy_aura_range"] = float(max(0.0, aura_range))
            unit.special_rules["enhancement_infamy_aura_oc_penalty"] = int(max(0, oc_penalty))
            unit.special_rules["enhancement_infamy_aura_oc_minimum"] = int(max(0, oc_minimum))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "webway pathstone" or enh_id == "000010704003":
            if not is_corsair_veterans:
                return
            unit.special_rules["enhancement_webway_pathstone"] = True
            unit.special_rules["bearer_unit_deep_strike"] = True
            unit.special_rules["enhancement_webway_pathstone_once_key"] = "webway_pathstone"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("deep_strike", None)
                cache.pop("opponent_turn_strategic_reserves_ability", None)

        if enh_id == "000010704004" or (name == "archraider" and is_corsair_veterans):
            if not is_corsair_veterans:
                return
            unit.special_rules["enhancement_archraider"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                aura_range = float(getattr(desc, "range_in", 12.0) or 12.0)
            except Exception:
                aura_range = 12.0
            unit.special_rules["enhancement_archraider_aura_range"] = float(max(0.0, aura_range))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
            try:
                if hasattr(unit, "_refresh_targeted_stratagem_cp_increase_flags"):
                    unit._refresh_targeted_stratagem_cp_increase_flags()
            except Exception:
                pass

        if name == "voidstone" or enh_id == "000010704005":
            if not is_corsair_veterans:
                return
            unit.special_rules["enhancement_voidstone"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            try:
                invuln = int(params.get("invulnerable_save", 5) or 5)
            except Exception:
                invuln = 5
            invuln = int(max(2, min(7, invuln)))
            entries = list(unit.special_rules.get("bearer_unit_invulnerable_save", []) or [])
            source_name = str(getattr(self, "name", "") or "Voidstone").strip() or "Voidstone"
            entry = {"value": int(invuln), "source": source_name}
            found = False
            for existing in entries:
                if not isinstance(existing, dict):
                    continue
                try:
                    val = int(existing.get("value"))
                except Exception:
                    continue
                src = str(existing.get("source", "") or "").strip()
                if val == int(invuln) and src == source_name:
                    found = True
                    break
            if not found:
                entries.append(entry)
            unit.special_rules["bearer_unit_invulnerable_save"] = entries
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "lord of forbidden lore" or enh_id == "000010193002":
            if not is_grand_coven:
                return
            unit.special_rules["enhancement_lord_of_forbidden_lore"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "incandaeum" or enh_id == "000010193003":
            if not is_grand_coven:
                return
            unit.special_rules["enhancement_incandaeum"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "umbralefic crystal" or enh_id == "000010193004":
            if not is_grand_coven:
                return
            unit.special_rules["enhancement_umbralefic_crystal"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "eldritch vortex of e'taph" or enh_id == "000010193005":
            if not is_grand_coven:
                return
            unit.special_rules["enhancement_eldritch_vortex_of_etaph"] = True
            unit.special_rules["enhancement_bearer_psychic_strength_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_psychic_strength_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_psychic_damage_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_psychic_damage_bonus", 0) or 0
            ) + 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "nethershriek mind-eater" or enh_id == "000010197002":
            if not is_changehost_of_deceit:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Nethershriek Mind-eater").strip() or "Nethershriek Mind-eater"
            trigger_range = float(max(0.0, _coerce_float(params.get("range", getattr(desc, "range_in", 12.0)) or 12.0, default=12.0)))
            fail_mortal_wounds = int(max(0, _coerce_int(params.get("fail_mortal_wounds", 3) or 3, default=3)))
            unit.special_rules["enhancement_nethershriek_mind_eater"] = True
            unit.special_rules["enhancement_nethershriek_mind_eater_source"] = source
            unit.special_rules["enhancement_nethershriek_mind_eater_range"] = float(trigger_range)
            unit.special_rules["enhancement_nethershriek_mind_eater_fail_mortal_wounds"] = int(fail_mortal_wounds)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_nethershriek_mind_eater_bearer_model_id"] = bearer_id

        if name == "diabolic savant" or enh_id == "000010197003":
            if not is_changehost_of_deceit:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Diabolic Savant").strip() or "Diabolic Savant"
            aura_range = float(max(0.0, _coerce_float(params.get("range", getattr(desc, "range_in", 6.0)) or 6.0, default=6.0)))
            channel_bonus = int(max(0, _coerce_int(params.get("ritual_test_bonus", 1) or 1, default=1)))
            unit.special_rules["enhancement_diabolic_savant"] = True
            unit.special_rules["enhancement_diabolic_savant_source"] = source
            unit.special_rules["enhancement_diabolic_savant_range"] = float(aura_range)
            unit.special_rules["enhancement_diabolic_savant_channel_bonus"] = int(channel_bonus)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_diabolic_savant_bearer_model_id"] = bearer_id

        if name == "tome of true names" or enh_id == "000010197005":
            if not is_changehost_of_deceit:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Tome of True Names").strip() or "Tome of True Names"
            invuln = int(min(7, max(2, _coerce_int(params.get("invulnerable_save", 2) or 2, default=2))))
            once_key = str(
                params.get("once_per_battle_key", "start_any_phase_invuln:tome_of_true_names")
                or "start_any_phase_invuln:tome_of_true_names"
            ).strip().lower()
            unit.special_rules["enhancement_tome_of_true_names"] = True
            unit.special_rules["enhancement_tome_of_true_names_source"] = source
            unit.special_rules["enhancement_tome_of_true_names_invulnerable_save"] = int(invuln)
            unit.special_rules["enhancement_tome_of_true_names_once_key"] = once_key
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_tome_of_true_names_bearer_model_id"] = bearer_id

        if name == "arcane might" or enh_id == "000009741002":
            if not is_hexwarp_thrallband:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Arcane Might").strip() or "Arcane Might"
            base_bonus = int(max(0, _coerce_int(params.get("base_strength_bonus", 1) or 1, default=1)))
            flow_bonus = int(max(0, _coerce_int(params.get("flow_strength_bonus", 2) or 2, default=2)))
            unit.special_rules["enhancement_arcane_might"] = True
            unit.special_rules["enhancement_arcane_might_source"] = source
            unit.special_rules["enhancement_arcane_might_base_strength_bonus"] = int(base_bonus)
            unit.special_rules["enhancement_arcane_might_flow_strength_bonus"] = int(flow_bonus)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_arcane_might_bearer_model_id"] = bearer_id

        if name == "empowered manifestation" or enh_id == "000009741003":
            if not is_hexwarp_thrallband:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Empowered Manifestation").strip() or "Empowered Manifestation"
            ritual_range_bonus = int(max(0, _coerce_int(params.get("ritual_range_bonus", 6) or 6, default=6)))
            unit.special_rules["enhancement_empowered_manifestation"] = True
            unit.special_rules["enhancement_empowered_manifestation_source"] = source
            unit.special_rules["enhancement_empowered_manifestation_ritual_range_bonus"] = int(ritual_range_bonus)
            unit.special_rules["enhancement_empowered_manifestation_hazardous_reroll"] = bool(
                params.get("hazardous_reroll", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_empowered_manifestation_bearer_model_id"] = bearer_id

        if name == "empyric onslaught" or enh_id == "000009741004":
            if not is_hexwarp_thrallband:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Empyric Onslaught").strip() or "Empyric Onslaught"
            attacks_bonus = int(max(0, _coerce_int(params.get("attacks_bonus", 3) or 3, default=3)))
            unit.special_rules["enhancement_empyric_onslaught"] = True
            unit.special_rules["enhancement_empyric_onslaught_source"] = source
            unit.special_rules["enhancement_empyric_onslaught_attacks_bonus"] = int(attacks_bonus)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_empyric_onslaught_bearer_model_id"] = bearer_id

        if name == "noctilith mantle" or enh_id == "000009741005":
            if not is_hexwarp_thrallband:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            source = str(getattr(desc, "name", "") or "Noctilith Mantle").strip() or "Noctilith Mantle"
            unit.special_rules["enhancement_noctilith_mantle"] = True
            unit.special_rules["enhancement_noctilith_mantle_source"] = source
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_noctilith_mantle_bearer_model_id"] = bearer_id

        if name == "warpmeld dagger" or enh_id == "000010201002":
            if not is_warpmeld_pact:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Warpmeld Dagger").strip() or "Warpmeld Dagger"
            self_mortal_roll = str(params.get("self_mortal_roll", "D3") or "D3").strip().upper() or "D3"
            unit.special_rules["enhancement_warpmeld_dagger"] = True
            unit.special_rules["enhancement_warpmeld_dagger_source"] = source
            unit.special_rules["enhancement_warpmeld_dagger_self_mortal_roll"] = self_mortal_roll
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_warpmeld_dagger_bearer_model_id"] = bearer_id

        if name == "diamond of distortion" or enh_id == "000010201003":
            if not is_warpmeld_pact:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Diamond of Distortion").strip() or "Diamond of Distortion"
            penalty = int(max(0, _coerce_int(params.get("target_hit_roll_penalty", 1) or 1, default=1)))
            unit.special_rules["enhancement_diamond_of_distortion"] = True
            unit.special_rules["enhancement_diamond_of_distortion_source"] = source
            unit.special_rules["enhancement_diamond_of_distortion_target_hit_roll_penalty"] = int(penalty)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_diamond_of_distortion_bearer_model_id"] = bearer_id

        if name == "bray lord" or enh_id == "000010201004":
            if not is_warpmeld_pact:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Bray Lord").strip() or "Bray Lord"
            scout_distance = float(max(0.0, _coerce_float(params.get("scouts_distance", 6) or 6, default=6.0)))
            attach_names = [
                str(value).strip()
                for value in list(params.get("attachment_override_unit_names_any", ("Tzaangors",)) or ())
                if str(value or "").strip()
            ]
            unit.special_rules["enhancement_bray_lord"] = True
            unit.special_rules["enhancement_bray_lord_source"] = source
            unit.special_rules["enhancement_bray_lord_scout_distance"] = float(scout_distance)
            unit.special_rules["enhancement_bray_lord_attach_unit_names"] = list(attach_names)
            try:
                current_scout = float(unit.special_rules.get("enhancement_scout_distance", 0.0) or 0.0)
            except (TypeError, ValueError):
                current_scout = 0.0
            unit.special_rules["enhancement_scout_distance"] = float(max(current_scout, scout_distance))
            allowed_names = [
                str(value).strip()
                for value in list(getattr(unit, "can_be_attached_to_names", []) or [])
                if str(value or "").strip()
            ]
            allowed_name_set = {str(value).casefold() for value in allowed_names}
            for attach_name in attach_names:
                if attach_name.casefold() in allowed_name_set:
                    continue
                allowed_names.append(attach_name)
                allowed_name_set.add(attach_name.casefold())
            unit.can_be_attached_to_names = list(allowed_names)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_bray_lord_bearer_model_id"] = bearer_id

        if name == "flowing flesh" or enh_id == "000010201005":
            if not is_warpmeld_pact:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Flowing Flesh").strip() or "Flowing Flesh"
            wounds_characteristic = int(
                max(1, _coerce_int(params.get("wounds_characteristic", 5) or 5, default=5))
            )
            unit.special_rules["enhancement_flowing_flesh"] = True
            unit.special_rules["enhancement_flowing_flesh_source"] = source
            unit.special_rules["enhancement_flowing_flesh_wounds_characteristic"] = int(wounds_characteristic)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_flowing_flesh_bearer_model_id"] = bearer_id
            if bearer is not None and not bool(unit.special_rules.get("enhancement_flowing_flesh_bearer_wounds_applied", False)):
                if _set_bearer_model_wounds_characteristic(bearer, int(wounds_characteristic)):
                    unit.special_rules["enhancement_flowing_flesh_bearer_wounds_applied"] = True
                    try:
                        unit.starting_total_wounds = sum(
                            int(getattr(model, "_base_wounds", 0) or 0)
                            for model in list(getattr(unit, "models", []) or [])
                        )
                    except (TypeError, ValueError):
                        pass
            tag = f"enhancement_fnp_{enh_id or name}"
            _ensure_enhancement_fnp_entry(
                unit,
                4,
                source=source,
                tag=tag,
                source_model_id=str(bearer_id) if bearer_id else None,
            )
            if bearer_id:
                entries = list(unit.special_rules.get("enhancement_bearer_fnp_entries", []) or [])
                changed = False
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    if str(entry.get("tag", "") or "") != tag:
                        continue
                    entry["source_model_id"] = str(bearer_id)
                    changed = True
                if changed:
                    unit.special_rules["enhancement_bearer_fnp_entries"] = entries

        if name == "warp syphon" or enh_id == "000010209002":
            if not is_warpforged_cabal:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Warp Syphon").strip() or "Warp Syphon"
            aura_range = float(max(0.0, _coerce_float(params.get("range", getattr(desc, "range_in", 6.0)) or 6.0, default=6.0)))
            self_mortal_wounds = int(max(0, _coerce_int(params.get("self_mortal_wounds", 1) or 1, default=1)))
            unit.special_rules["enhancement_warp_syphon"] = True
            unit.special_rules["enhancement_warp_syphon_source"] = source
            unit.special_rules["enhancement_warp_syphon_range"] = float(aura_range)
            unit.special_rules["enhancement_warp_syphon_self_mortal_wounds"] = int(self_mortal_wounds)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_warp_syphon_bearer_model_id"] = bearer_id

        if name == "the perplexing cloak" or enh_id == "000010209003":
            if not is_warpforged_cabal:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "The Perplexing Cloak").strip() or "The Perplexing Cloak"
            aura_range = float(max(0.0, _coerce_float(params.get("range", getattr(desc, "range_in", 3.0)) or 3.0, default=3.0)))
            unit.special_rules["enhancement_perplexing_cloak"] = True
            unit.special_rules["enhancement_perplexing_cloak_source"] = source
            unit.special_rules["enhancement_perplexing_cloak_range"] = float(aura_range)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_perplexing_cloak_bearer_model_id"] = bearer_id

        if name == "biomechanical mutation" or enh_id == "000010209004":
            if not is_warpforged_cabal:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Biomechanical Mutation").strip() or "Biomechanical Mutation"
            aura_range = float(max(0.0, _coerce_float(params.get("range", getattr(desc, "range_in", 6.0)) or 6.0, default=6.0)))
            heal_roll = str(params.get("heal_roll", "D3") or "D3").strip().upper() or "D3"
            unit.special_rules["enhancement_biomechanical_mutation"] = True
            unit.special_rules["enhancement_biomechanical_mutation_source"] = source
            unit.special_rules["enhancement_biomechanical_mutation_range"] = float(aura_range)
            unit.special_rules["enhancement_biomechanical_mutation_heal_roll"] = heal_roll
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_biomechanical_mutation_bearer_model_id"] = bearer_id

        if name == "warp-cursed runemaster" or enh_id == "000010209005":
            if not is_warpforged_cabal:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Warp-cursed Runemaster").strip() or "Warp-cursed Runemaster"
            aura_range = float(max(0.0, _coerce_float(params.get("range", getattr(desc, "range_in", 6.0)) or 6.0, default=6.0)))
            ritual_range_bonus = int(max(0, _coerce_int(params.get("ritual_range_bonus", 6) or 6, default=6)))
            unit.special_rules["enhancement_warp_cursed_runemaster"] = True
            unit.special_rules["enhancement_warp_cursed_runemaster_source"] = source
            unit.special_rules["enhancement_warp_cursed_runemaster_range"] = float(aura_range)
            unit.special_rules["enhancement_warp_cursed_runemaster_ritual_range_bonus"] = int(ritual_range_bonus)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_warp_cursed_runemaster_bearer_model_id"] = bearer_id

        if name == "risen rubricae" or enh_id == "000010205002":
            if not is_rubricae_phalanx:
                return
            unit.special_rules["enhancement_risen_rubricae"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "arcane thralls (aura)" or enh_id == "000010205003":
            if not is_rubricae_phalanx:
                return
            unit.special_rules["enhancement_arcane_thralls"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "lord of the rubricae" or enh_id == "000010205004":
            if not is_rubricae_phalanx:
                return
            unit.special_rules["enhancement_lord_of_the_rubricae"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "the stave abominus" or enh_id == "000010205005":
            if not is_rubricae_phalanx:
                return
            unit.special_rules["enhancement_the_stave_abominus"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "master regenesist" or enh_id == "000010584002":
            if not is_covenite_coterie:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Master Regenesist").strip() or "Master Regenesist"
            unit.special_rules["enhancement_master_regenesist"] = True
            unit.special_rules["enhancement_master_regenesist_source"] = source
            unit.special_rules["enhancement_master_regenesist_fleshcraft_roll"] = str(
                params.get("enhanced_return_roll", "D3+3") or "D3+3"
            ).strip().upper()
            unit.special_rules["enhancement_master_regenesist_base_fleshcraft_roll"] = str(
                params.get("base_return_roll", "D3+1") or "D3+1"
            ).strip().upper()
            unit.special_rules["enhancement_master_regenesist_optional"] = bool(params.get("optional", True))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_master_regenesist_bearer_model_id"] = bearer_id

        if name == "master nemesine" or enh_id == "000010584003":
            if not is_covenite_coterie:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Master Nemesine").strip() or "Master Nemesine"
            unit.special_rules["enhancement_master_nemesine"] = True
            unit.special_rules["enhancement_master_nemesine_source"] = source
            unit.special_rules["enhancement_master_nemesine_anti_beast"] = int(
                min(6, max(2, _coerce_int(params.get("anti_beast", 2) or 2, default=2)))
            )
            unit.special_rules["enhancement_master_nemesine_anti_monster"] = int(
                min(6, max(2, _coerce_int(params.get("anti_monster", 4) or 4, default=4)))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_master_nemesine_bearer_model_id"] = bearer_id

        if name == "master artisan" or enh_id == "000010584004":
            if not is_covenite_coterie:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Master Artisan").strip() or "Master Artisan"
            unit.special_rules["enhancement_master_artisan"] = True
            unit.special_rules["enhancement_master_artisan_source"] = source
            wounds_bonus = int(max(0, _coerce_int(params.get("bearer_wounds_bonus", 1) or 1, default=1)))
            toughness_bonus = int(max(0, _coerce_int(params.get("bearer_unit_toughness_bonus", 1) or 1, default=1)))
            unit.special_rules["enhancement_master_artisan_bearer_wounds_bonus"] = int(wounds_bonus)
            unit.special_rules["enhancement_master_artisan_toughness_bonus"] = int(toughness_bonus)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_master_artisan_bearer_model_id"] = bearer_id
            if not bool(unit.special_rules.get("enhancement_master_artisan_wounds_corrected", False)):
                applied_kinds = getattr(unit, "_enhancement_effect_kinds_applied", set())
                wounds_add_applied = bool(isinstance(applied_kinds, set) and "wounds_add" in applied_kinds)
                for model in list(getattr(unit, "models", []) or []):
                    if model is None:
                        continue
                    if not wounds_add_applied:
                        break
                    try:
                        model._base_wounds = max(1, int(getattr(model, "_base_wounds", 1) or 1) - int(wounds_bonus))
                        model._wounds = max(1, int(getattr(model, "_wounds", 1) or 1) - int(wounds_bonus))
                        base_unmod = getattr(model, "_base_wounds_unmodified", None)
                        if base_unmod is not None:
                            model._base_wounds_unmodified = max(1, int(base_unmod or 1) - int(wounds_bonus))
                    except (TypeError, ValueError):
                        continue
                unit.special_rules["enhancement_master_artisan_wounds_corrected"] = True
            if bearer is not None and not bool(unit.special_rules.get("enhancement_master_artisan_bearer_wounds_applied", False)):
                try:
                    bearer._base_wounds = int(getattr(bearer, "_base_wounds", 0) or 0) + int(wounds_bonus)
                    bearer._wounds = int(getattr(bearer, "_wounds", 0) or 0) + int(wounds_bonus)
                    base_unmod = getattr(bearer, "_base_wounds_unmodified", None)
                    if base_unmod is not None:
                        bearer._base_wounds_unmodified = int(base_unmod or 0) + int(wounds_bonus)
                    unit.special_rules["enhancement_master_artisan_bearer_wounds_applied"] = True
                except (TypeError, ValueError):
                    pass
            try:
                unit.starting_total_wounds = sum(
                    int(getattr(model, "_base_wounds", 0) or 0)
                    for model in list(getattr(unit, "models", []) or [])
                )
            except (TypeError, ValueError):
                pass

        if name in {"master repugnomancer (aura)", "master repugnomancer"} or enh_id == "000010584005":
            if not is_covenite_coterie:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Master Repugnomancer (Aura)").strip() or "Master Repugnomancer (Aura)"
            unit.special_rules["enhancement_master_repugnomancer"] = True
            unit.special_rules["enhancement_master_repugnomancer_source"] = source
            unit.special_rules["enhancement_master_repugnomancer_fear_incarnate_range_bonus"] = int(
                max(0, _coerce_int(params.get("fear_incarnate_range_bonus", 3) or 3, default=3))
            )
            unit.special_rules["enhancement_master_repugnomancer_trigger_range"] = float(
                max(0.0, _coerce_float(params.get("trigger_range", 9.0) or 9.0, default=9.0))
            )
            unit.special_rules["enhancement_master_repugnomancer_success_on"] = int(
                min(6, max(2, _coerce_int(params.get("success_on", 4) or 4, default=4)))
            )
            unit.special_rules["enhancement_master_repugnomancer_pain_tokens_gained"] = int(
                max(1, _coerce_int(params.get("pain_tokens_gained", 1) or 1, default=1))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_master_repugnomancer_bearer_model_id"] = bearer_id

        if name == "dark vitality" or enh_id == "000010574002":
            if not is_realspace_raiders:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            source = str(getattr(desc, "name", "") or "Dark Vitality").strip() or "Dark Vitality"
            unit.special_rules["enhancement_dark_vitality"] = True
            unit.special_rules["enhancement_dark_vitality_source"] = source
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_dark_vitality_bearer_model_id"] = bearer_id

        if name == "labyrinthine cunning" or enh_id == "000010574003":
            if not is_realspace_raiders:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Labyrinthine Cunning").strip() or "Labyrinthine Cunning"
            unit.special_rules["enhancement_labyrinthine_cunning"] = True
            unit.special_rules["enhancement_labyrinthine_cunning_source"] = source
            unit.special_rules["enhancement_labyrinthine_cunning_ability_key"] = "labyrinthine_cunning"
            unit.special_rules["enhancement_labyrinthine_cunning_pain_token_cost"] = int(
                max(1, _coerce_int(params.get("pain_token_cost", 1) or 1, default=1))
            )
            unit.special_rules["enhancement_labyrinthine_cunning_cp_gain"] = int(
                max(0, _coerce_int(params.get("cp_gain", 1) or 1, default=1))
            )
            unit.special_rules["enhancement_labyrinthine_cunning_success_on"] = int(
                min(6, max(2, _coerce_int(params.get("success_on", 4) or 4, default=4)))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_labyrinthine_cunning_bearer_model_id"] = bearer_id

        if name == "eye of spite" or enh_id == "000010574004":
            if not is_realspace_raiders:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Eye of Spite").strip() or "Eye of Spite"
            base_attacks_bonus = int(max(0, _coerce_int(params.get("base_attacks_bonus", 1) or 1, default=1)))
            base_ap_bonus = int(max(0, _coerce_int(params.get("base_ap_bonus", 1) or 1, default=1)))
            pain_token_cost = int(max(1, _coerce_int(params.get("pain_token_cost", 1) or 1, default=1)))
            unit.special_rules["enhancement_eye_of_spite"] = True
            unit.special_rules["enhancement_eye_of_spite_source"] = source
            unit.special_rules["enhancement_eye_of_spite_pain_token_cost"] = int(pain_token_cost)
            unit.special_rules["enhancement_eye_of_spite_base_attacks_bonus"] = int(base_attacks_bonus)
            unit.special_rules["enhancement_eye_of_spite_base_ap_bonus"] = int(base_ap_bonus)
            if base_attacks_bonus:
                unit.special_rules["enhancement_bearer_melee_attacks_bonus"] = int(
                    unit.special_rules.get("enhancement_bearer_melee_attacks_bonus", 0) or 0
                ) + int(base_attacks_bonus)
            if base_ap_bonus:
                unit.special_rules["enhancement_bearer_melee_ap_bonus"] = int(
                    unit.special_rules.get("enhancement_bearer_melee_ap_bonus", 0) or 0
                ) + int(base_ap_bonus)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_eye_of_spite_bearer_model_id"] = bearer_id

        if name == "crucible of malediction" or enh_id == "000010574005":
            if not is_realspace_raiders:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Crucible of Malediction").strip() or "Crucible of Malediction"
            unit.special_rules["enhancement_crucible_of_malediction"] = True
            unit.special_rules["enhancement_crucible_of_malediction_source"] = source
            unit.special_rules["enhancement_crucible_of_malediction_ability_key"] = "crucible_of_malediction"
            unit.special_rules["enhancement_crucible_of_malediction_once_key"] = "crucible_of_malediction"
            unit.special_rules["enhancement_crucible_of_malediction_range"] = float(
                max(0.0, _coerce_float(params.get("range", 12.0) or 12.0, default=12.0))
            )
            unit.special_rules["enhancement_crucible_of_malediction_pain_token_cost"] = int(
                max(1, _coerce_int(params.get("pain_token_cost", 1) or 1, default=1))
            )
            unit.special_rules["enhancement_crucible_of_malediction_battleshock_modifier_if_spent"] = int(
                _coerce_int(params.get("battle_shock_test_modifier_if_spent", -1) or -1, default=-1)
            )
            unit.special_rules["enhancement_crucible_of_malediction_psyker_fail_mortal_wounds"] = int(
                max(0, _coerce_int(params.get("psyker_fail_mortal_wounds", 3) or 3, default=3))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_crucible_of_malediction_bearer_model_id"] = bearer_id

        if enh_id == "000009781002" or (name == "archraider" and is_reapers_wager):
            if not is_reapers_wager:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Archraider").strip() or "Archraider"
            unit.special_rules["enhancement_reapers_wager_archraider"] = True
            unit.special_rules["enhancement_reapers_wager_archraider_source"] = source
            unit.special_rules["enhancement_reapers_wager_archraider_scouts_distance"] = float(
                max(0.0, _coerce_float(params.get("scouts_distance", 9.0) or 9.0, default=9.0))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_reapers_wager_archraider_bearer_model_id"] = bearer_id

        if name == "webway walker" or enh_id == "000009781003":
            if not is_reapers_wager:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Webway Walker").strip() or "Webway Walker"
            unit.special_rules["enhancement_webway_walker"] = True
            unit.special_rules["enhancement_webway_walker_source"] = source
            unit.special_rules["enhancement_webway_walker_ability_key"] = "webway_walker"
            unit.special_rules["bearer_unit_deep_strike"] = bool(params.get("grants_deep_strike", True))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_webway_walker_bearer_model_id"] = bearer_id
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("deep_strike", None)

        if name in {"reaper's cowl", "reapers cowl"} or enh_id == "000009781004":
            if not is_reapers_wager:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            source = str(getattr(desc, "name", "") or "Reaper's Cowl").strip() or "Reaper's Cowl"
            unit.special_rules["enhancement_reapers_cowl"] = True
            unit.special_rules["enhancement_reapers_cowl_source"] = source
            unit.special_rules["enhancement_reapers_cowl_stealth"] = True
            unit.special_rules["enhancement_reapers_cowl_infiltrators"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_reapers_cowl_bearer_model_id"] = bearer_id
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("infiltrate", None)
                cache.pop("stealth", None)

        if name == "conductor of torment" or enh_id == "000009781005":
            if not is_reapers_wager:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Conductor of Torment").strip() or "Conductor of Torment"
            unit.special_rules["enhancement_conductor_of_torment"] = True
            unit.special_rules["enhancement_conductor_of_torment_source"] = source
            unit.special_rules["enhancement_conductor_of_torment_ability_key"] = "conductor_of_torment"
            unit.special_rules["enhancement_conductor_of_torment_gain_pain_tokens"] = int(
                max(0, _coerce_int(params.get("gain_pain_tokens_if_drukhari_losing", 1) or 1, default=1))
            )
            unit.special_rules["enhancement_conductor_of_torment_spend_pain_token_cost"] = int(
                max(1, _coerce_int(params.get("spend_pain_token_cost_if_drukhari_winning", 1) or 1, default=1))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_conductor_of_torment_bearer_model_id"] = bearer_id

        if name == "leechbite plate" or enh_id == "000010588002":
            if not is_kabalite_cartel:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Leechbite Plate").strip() or "Leechbite Plate"
            unit.special_rules["enhancement_leechbite_plate"] = True
            unit.special_rules["enhancement_leechbite_plate_source"] = source
            unit.special_rules["enhancement_leechbite_plate_ability_key"] = "leechbite_plate"
            unit.special_rules["enhancement_leechbite_plate_save_characteristic"] = int(
                min(6, max(2, _coerce_int(params.get("save_characteristic", 3) or 3, default=3)))
            )
            unit.special_rules["enhancement_leechbite_plate_pain_token_cost"] = int(
                max(1, _coerce_int(params.get("pain_token_cost", 1) or 1, default=1))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_leechbite_plate_bearer_model_id"] = bearer_id
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("save", None)
                cache.pop("model_save_characteristic", None)
                if bearer_id:
                    cache.pop(f"model_save_characteristic:{bearer_id}", None)

        if name == "webway awl" or enh_id == "000010588003":
            if not is_kabalite_cartel:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Webway Awl").strip() or "Webway Awl"
            unit.special_rules["enhancement_webway_awl"] = True
            unit.special_rules["enhancement_webway_awl_source"] = source
            unit.special_rules["enhancement_webway_awl_rapid_ingress_discount"] = True
            unit.special_rules["enhancement_webway_awl_stratagem_name"] = str(
                params.get("stratagem_name", "RAPID INGRESS") or "RAPID INGRESS"
            ).strip().upper()
            unit.special_rules["bearer_unit_deep_strike"] = bool(params.get("grants_deep_strike", True))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_webway_awl_bearer_model_id"] = bearer_id
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("deep_strike", None)
                cache.pop("opponent_turn_strategic_reserves_ability", None)

        if name == "informant network" or enh_id == "000010588004":
            if not is_kabalite_cartel:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Informant Network").strip() or "Informant Network"
            unit.special_rules["enhancement_informant_network"] = True
            unit.special_rules["enhancement_informant_network_source"] = source
            unit.special_rules["enhancement_informant_network_selection_ability"] = "informant_network_selection"
            unit.special_rules["enhancement_informant_network_max_units"] = int(
                max(0, _coerce_int(params.get("max_units", 3) or 3, default=3))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_informant_network_bearer_model_id"] = bearer_id

        if name == "towering arrogance" or enh_id == "000010588005":
            if not is_kabalite_cartel:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Towering Arrogance").strip() or "Towering Arrogance"
            unit.special_rules["enhancement_towering_arrogance"] = True
            unit.special_rules["enhancement_towering_arrogance_source"] = source
            unit.special_rules["enhancement_towering_arrogance_leadership_improvement"] = int(
                max(1, _coerce_int(params.get("leadership_improvement", 1) or 1, default=1))
            )
            unit.special_rules["enhancement_towering_arrogance_objective_control_bonus"] = int(
                max(1, _coerce_int(params.get("objective_control_bonus", 1) or 1, default=1))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_towering_arrogance_bearer_model_id"] = bearer_id

        if name == "phantasmal smoke" or enh_id == "000010576002":
            if not is_skysplinter_assault:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Phantasmal Smoke").strip() or "Phantasmal Smoke"
            unit.special_rules["enhancement_phantasmal_smoke"] = True
            unit.special_rules["enhancement_phantasmal_smoke_source"] = source
            unit.special_rules["enhancement_phantasmal_smoke_requires_friendly_transport"] = bool(
                params.get("requires_friendly_transport", True)
            )
            unit.special_rules["enhancement_phantasmal_smoke_requires_wholly_within"] = bool(
                params.get("requires_wholly_within", True)
            )
            unit.special_rules["enhancement_phantasmal_smoke_range"] = float(
                max(0.0, _coerce_float(params.get("range", 6.0) or 6.0, default=6.0))
            )
            unit.special_rules["enhancement_phantasmal_smoke_stealth"] = bool(params.get("grants_stealth", True))
            unit.special_rules["enhancement_phantasmal_smoke_benefit_of_cover"] = bool(
                params.get("grants_benefit_of_cover_vs_ranged", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_phantasmal_smoke_bearer_model_id"] = bearer_id
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("stealth", None)

        if name == "sadistic fulcrum" or enh_id == "000010576003":
            if not is_skysplinter_assault:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Sadistic Fulcrum").strip() or "Sadistic Fulcrum"
            unit.special_rules["enhancement_sadistic_fulcrum"] = True
            unit.special_rules["enhancement_sadistic_fulcrum_source"] = source
            unit.special_rules["enhancement_sadistic_fulcrum_trigger_phase"] = str(
                params.get("trigger_phase", "shooting") or "shooting"
            ).strip().upper()
            unit.special_rules["enhancement_sadistic_fulcrum_transport_range"] = float(
                max(0.0, _coerce_float(params.get("range", 6.0) or 6.0, default=6.0))
            )
            unit.special_rules["enhancement_sadistic_fulcrum_requires_friendly_transport"] = bool(
                params.get("requires_friendly_transport", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_sadistic_fulcrum_bearer_model_id"] = bearer_id

        if name == "spiteful raider" or enh_id == "000010576004":
            if not is_skysplinter_assault:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Spiteful Raider").strip() or "Spiteful Raider"
            unit.special_rules["enhancement_spiteful_raider"] = True
            unit.special_rules["enhancement_spiteful_raider_source"] = source
            unit.special_rules["enhancement_spiteful_raider_pain_tokens_gained"] = int(
                max(1, _coerce_int(params.get("pain_tokens_gained", 1) or 1, default=1))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_spiteful_raider_bearer_model_id"] = bearer_id

        if name == "nightmare shroud" or enh_id == "000010576005":
            if not is_skysplinter_assault:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            source = str(getattr(desc, "name", "") or "Nightmare Shroud").strip() or "Nightmare Shroud"
            unit.special_rules["enhancement_nightmare_shroud"] = True
            unit.special_rules["enhancement_nightmare_shroud_source"] = source
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "pharmacophex" or enh_id == "000010580002":
            if not is_spectacle_of_spite:
                return
            unit.special_rules["enhancement_pharmacophex"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "chronoshard" or enh_id == "000010580003":
            if not is_spectacle_of_spite:
                return
            unit.special_rules["enhancement_chronoshard"] = True
            unit.special_rules["enhancement_fight_first_once_per_battle"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "periapt of torments" or enh_id == "000010580004":
            if not is_spectacle_of_spite:
                return
            unit.special_rules["enhancement_periapt_of_torments"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "morghenna's curse" or enh_id == "000010580005":
            if not is_spectacle_of_spite:
                return
            unit.special_rules["enhancement_morghennas_curse"] = True
            unit.special_rules["enhancement_bearer_melee_ap_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_ap_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_melee_damage_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_damage_bonus", 0) or 0
            ) + 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "touched by the warp" or enh_id == "000010151002":
            if not is_cabal_of_chaos:
                return
            unit.special_rules["enhancement_touched_by_the_warp"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
            if bearer is not None:
                try:
                    keywords = list(getattr(bearer, "keywords", []) or [])
                    if "psyker" not in {str(k or "").strip().lower() for k in keywords}:
                        keywords.append("PSYKER")
                        bearer.keywords = keywords
                except Exception:
                    pass

        if name == "eyes of z'desh" or name == "eyes of z’desh" or enh_id == "000010151003":
            if not is_cabal_of_chaos:
                return
            unit.special_rules["enhancement_eyes_of_zdesh"] = True
            unit.special_rules["enhancement_scout_distance"] = max(
                int(unit.special_rules.get("enhancement_scout_distance", 0) or 0),
                6,
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "mind blade" or enh_id == "000010151004":
            if not is_cabal_of_chaos:
                return
            unit.special_rules["enhancement_mind_blade"] = True
            unit.special_rules["enhancement_mind_blade_source"] = "Mind Blade"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "infernal avatar" or enh_id == "000010151005":
            if not is_cabal_of_chaos:
                return
            unit.special_rules["enhancement_infernal_avatar"] = True
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0) or 0
            ) + 2
            unit.special_rules["enhancement_bearer_melee_ap_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_ap_bonus", 0) or 0
            ) + 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "amulet of tainted vigour" or enh_id == "000008981002":
            if not is_chaos_cult:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Amulet of Tainted Vigour").strip() or "Amulet of Tainted Vigour"
            unit.special_rules["enhancement_amulet_of_tainted_vigour"] = True
            unit.special_rules["enhancement_amulet_of_tainted_vigour_source"] = source
            unit.special_rules["enhancement_amulet_of_tainted_vigour_ability_key"] = "amulet_of_tainted_vigour"
            unit.special_rules["enhancement_amulet_of_tainted_vigour_return_roll"] = str(
                params.get("return_roll", "D3") or "D3"
            ).strip().upper()
            unit.special_rules["enhancement_amulet_of_tainted_vigour_required_model_keyword"] = str(
                params.get("required_model_keyword", "DAMNED") or "DAMNED"
            ).strip().upper()
            unit.special_rules["enhancement_amulet_of_tainted_vigour_exclude_character"] = bool(
                params.get("exclude_character", True)
            )
            unit.special_rules["enhancement_amulet_of_tainted_vigour_allow_skip"] = bool(
                params.get("optional", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name in {"cultist's brand", "cultist’s brand"} or enh_id == "000008981003":
            if not is_chaos_cult:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Cultist's Brand").strip() or "Cultist's Brand"
            required_keyword = str(params.get("requires_all_other_models_keyword", "DAMNED") or "DAMNED").strip().upper()
            excluded_names = list(params.get("exclude_model_names", ("Dark Disciple", "Dark Disciples")) or ())
            excluded_names = [str(v or "").strip() for v in excluded_names if str(v or "").strip()]
            unit.special_rules["enhancement_cultists_brand"] = True
            unit.special_rules["enhancement_cultists_brand_source"] = source
            unit.special_rules["enhancement_cultists_brand_required_keyword"] = required_keyword
            unit.special_rules["enhancement_cultists_brand_excluded_model_names"] = tuple(excluded_names)
            unit.special_rules["enhancement_cultists_brand_reroll_advance"] = bool(params.get("reroll_advance", True))
            unit.special_rules["enhancement_cultists_brand_reroll_charge"] = bool(params.get("reroll_charge", True))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "incendiary goad" or enh_id == "000008981004":
            if not is_chaos_cult:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Incendiary Goad").strip() or "Incendiary Goad"
            unit.special_rules["enhancement_incendiary_goad"] = True
            unit.special_rules["enhancement_incendiary_goad_source"] = source
            unit.special_rules["enhancement_incendiary_goad_required_model_keyword"] = str(
                params.get("required_model_keyword", "DAMNED") or "DAMNED"
            ).strip().upper()
            unit.special_rules["enhancement_incendiary_goad_requires_below_starting_strength"] = bool(
                params.get("requires_unit_below_starting_strength", True)
            )
            unit.special_rules["enhancement_incendiary_goad_requires_below_half_strength_for_attacks"] = bool(
                params.get("requires_unit_below_half_strength_for_attacks_bonus", True)
            )
            unit.special_rules["enhancement_incendiary_goad_melee_strength_bonus"] = int(
                max(0, _coerce_int(params.get("melee_strength_bonus", 1), default=1))
            )
            unit.special_rules["enhancement_incendiary_goad_melee_attacks_bonus"] = int(
                max(0, _coerce_int(params.get("melee_attacks_bonus", 1), default=1))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "warped foresight" or enh_id == "000008981005":
            if not is_chaos_cult:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Warped Foresight").strip() or "Warped Foresight"
            unit.special_rules["enhancement_warped_foresight"] = True
            unit.special_rules["enhancement_warped_foresight_source"] = source
            unit.special_rules["enhancement_warped_foresight_required_scout_distance"] = int(
                max(1, _coerce_int(params.get("required_led_unit_scouts_distance", 6), default=6))
            )
            unit.special_rules["enhancement_warped_foresight_scout_distance"] = 0
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
            if bool(getattr(unit, "is_leader", False)) and getattr(unit, "attached_to", None) is not None:
                apply_attached_scouts = getattr(unit, "_apply_attached_unit_bodyguard_leader_scouts", None)
                if callable(apply_attached_scouts):
                    apply_attached_scouts(unit.attached_to)
                invalidate = getattr(unit, "_invalidate_ability_cache", None)
                if callable(invalidate):
                    invalidate()
                invalidate_root = getattr(unit.attached_to, "_invalidate_ability_cache", None)
                if callable(invalidate_root):
                    invalidate_root()

        if name == "cursed fang" or enh_id == "000008964002":
            if not is_deceptors:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_cursed_fang"] = True
            unit.special_rules["enhancement_cursed_fang_source"] = "Cursed Fang"
            ap_bonus = _coerce_int(params.get("melee_ap_bonus", 1), default=1)
            unit.special_rules["enhancement_bearer_melee_ap_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_ap_bonus", 0) or 0
            ) + int(max(0, ap_bonus))
            if bool(params.get("precision", True)):
                unit.special_rules["enhancement_bearer_melee_precision"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "falsehood" or enh_id == "000008964003":
            if not is_deceptors:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_falsehood"] = True
            unit.special_rules["enhancement_falsehood_source"] = "Falsehood"
            unit.special_rules["enhancement_falsehood_optional"] = bool(params.get("optional", True))
            unit.special_rules["enhancement_falsehood_declare_resolved"] = False
            unit.special_rules["enhancement_falsehood_in_reserves"] = False
            unit.special_rules["enhancement_falsehood_reinforcements_available"] = False
            unit.special_rules["enhancement_falsehood_reinforcements_used"] = False
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "shroud of obfuscation" or enh_id == "000008964004":
            if not is_deceptors:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_shroud_of_obfuscation"] = True
            unit.special_rules["enhancement_shroud_of_obfuscation_source"] = "Shroud of Obfuscation"
            unit.special_rules["enhancement_shroud_of_obfuscation_stealth"] = bool(params.get("grants_stealth", True))
            unit.special_rules["enhancement_shroud_of_obfuscation_lone_operative"] = bool(
                params.get("grants_lone_operative", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "soul link" or enh_id == "000008964005":
            if not is_deceptors:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_soul_link"] = True
            unit.special_rules["enhancement_soul_link_source"] = "Soul Link"
            unit.special_rules["enhancement_soul_link_optional"] = bool(params.get("optional", True))
            unit.special_rules["enhancement_soul_link_active"] = False
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "eye of tzeentch" or enh_id == "000008357002":
            if not is_pactbound_zealots:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Eye of Tzeentch").strip() or "Eye of Tzeentch"
            unit.special_rules["enhancement_eye_of_tzeentch"] = True
            unit.special_rules["enhancement_eye_of_tzeentch_source"] = source
            unit.special_rules["enhancement_eye_of_tzeentch_modified_roll_threshold"] = int(
                min(12, max(2, _coerce_int(params.get("modified_roll_threshold", 8), default=8)))
            )
            unit.special_rules["enhancement_eye_of_tzeentch_cp_gain"] = int(
                max(1, _coerce_int(params.get("cp_gain", 1), default=1))
            )
            unit.special_rules["enhancement_eye_of_tzeentch_requires_dark_pact_passed"] = bool(
                params.get("requires_dark_pact_passed", True)
            )
            unit.special_rules["enhancement_eye_of_tzeentch_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_eye_of_tzeentch_requires_bearer_on_battlefield"] = bool(
                params.get("requires_bearer_on_battlefield", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_eye_of_tzeentch_bearer_model_id"] = bearer_id

        if name == "intoxicating elixir" or enh_id == "000008357003":
            if not is_pactbound_zealots:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Intoxicating Elixir").strip() or "Intoxicating Elixir"
            unit.special_rules["enhancement_intoxicating_elixir"] = True
            unit.special_rules["enhancement_intoxicating_elixir_source"] = source
            unit.special_rules["enhancement_intoxicating_elixir_requires_dark_pact_passed"] = bool(
                params.get("requires_dark_pact_passed", True)
            )
            unit.special_rules["enhancement_intoxicating_elixir_applies_after_fight"] = bool(
                params.get("applies_after_fight", True)
            )
            unit.special_rules["enhancement_intoxicating_elixir_requires_bearer_hit_target"] = bool(
                params.get("requires_bearer_hit_target", True)
            )
            fnp_value = int(min(6, max(2, _coerce_int(params.get("fnp", 5), default=5))))
            tag = f"enhancement_fnp_{enh_id or name}"
            _ensure_enhancement_fnp_entry(
                unit,
                fnp_value,
                source=source,
                tag=tag,
                source_model_id=str(bearer_id) if bearer_id else None,
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_intoxicating_elixir_bearer_model_id"] = bearer_id
                entries = list(unit.special_rules.get("enhancement_bearer_fnp_entries", []) or [])
                changed = False
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    if str(entry.get("tag", "") or "") != tag:
                        continue
                    entry["source_model_id"] = str(bearer_id)
                    changed = True
                if changed:
                    unit.special_rules["enhancement_bearer_fnp_entries"] = entries

        if name == "orbs of unlife" or enh_id == "000008357004":
            if not is_pactbound_zealots:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Orbs of Unlife").strip() or "Orbs of Unlife"
            unit.special_rules["enhancement_orbs_of_unlife"] = True
            unit.special_rules["enhancement_orbs_of_unlife_source"] = source
            unit.special_rules["enhancement_orbs_of_unlife_range"] = float(
                max(0.0, _coerce_float(params.get("range_in", 3.0), default=3.0))
            )
            unit.special_rules["enhancement_orbs_of_unlife_threshold"] = int(
                min(6, max(2, _coerce_int(params.get("base_threshold", 4), default=4)))
            )
            unit.special_rules["enhancement_orbs_of_unlife_threshold_if_dark_pact_passed"] = int(
                min(6, max(2, _coerce_int(params.get("threshold_if_dark_pact_passed", 3), default=3)))
            )
            mortal_raw = str(params.get("mortal_wounds", "D3") or "D3").strip().lower()
            unit.special_rules["enhancement_orbs_of_unlife_mortal_wounds"] = "d3" if mortal_raw not in {"d3", "d6"} else mortal_raw
            unit.special_rules["enhancement_orbs_of_unlife_requires_dark_pact_passed_for_threshold_bonus"] = bool(
                params.get("requires_dark_pact_passed_for_threshold_bonus", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_orbs_of_unlife_bearer_model_id"] = bearer_id

        if name == "talisman of burning blood" or enh_id == "000008357005":
            if not is_pactbound_zealots:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = (
                str(getattr(desc, "name", "") or "Talisman of Burning Blood").strip()
                or "Talisman of Burning Blood"
            )
            unit.special_rules["enhancement_talisman_of_burning_blood"] = True
            unit.special_rules["enhancement_talisman_of_burning_blood_source"] = source
            unit.special_rules["enhancement_talisman_of_burning_blood_base_attacks_bonus"] = int(
                max(0, _coerce_int(params.get("base_attacks_bonus", 1), default=1))
            )
            unit.special_rules["enhancement_talisman_of_burning_blood_base_strength_bonus"] = int(
                max(0, _coerce_int(params.get("base_strength_bonus", 1), default=1))
            )
            unit.special_rules["enhancement_talisman_of_burning_blood_dark_pact_roll"] = str(
                params.get("dark_pact_roll", "D3") or "D3"
            ).strip().upper()
            unit.special_rules["enhancement_talisman_of_burning_blood_requires_dark_pact_passed"] = bool(
                params.get("requires_dark_pact_passed", True)
            )
            for key in (
                "enhancement_talisman_of_burning_blood_dark_pact_bonus",
                "enhancement_talisman_of_burning_blood_dark_pact_expires_phase",
                "enhancement_talisman_of_burning_blood_dark_pact_turn",
                "enhancement_talisman_of_burning_blood_dark_pact_owner",
            ):
                unit.special_rules.pop(key, None)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_talisman_of_burning_blood_bearer_model_id"] = bearer_id

        if name in {"voice of the tyrant", "voice of tyrant"} or enh_id == "000010688002":
            if not is_hurons_marauders:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Voice of the Tyrant").strip() or "Voice of the Tyrant"
            unit.special_rules["enhancement_voice_of_the_tyrant"] = True
            unit.special_rules["enhancement_voice_of_the_tyrant_source"] = source
            unit.special_rules["enhancement_voice_of_the_tyrant_grant_hurons_elite"] = bool(
                params.get("grant_hurons_elite", True)
            )
            unit.special_rules["enhancement_voice_of_the_tyrant_grant_mobile_marauders"] = bool(
                params.get("grant_mobile_marauders", True)
            )
            unit.special_rules["enhancement_voice_of_the_tyrant_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_voice_of_the_tyrant_requires_bearer_on_battlefield"] = bool(
                params.get("requires_bearer_on_battlefield", False)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_voice_of_the_tyrant_bearer_model_id"] = bearer_id

        if name == "raid leader" or enh_id == "000010688003":
            if not is_hurons_marauders:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Raid Leader").strip() or "Raid Leader"
            unit.special_rules["enhancement_raid_leader"] = True
            unit.special_rules["enhancement_raid_leader_source"] = source
            unit.special_rules["enhancement_raid_leader_allow_charge_after_normal_move"] = bool(
                params.get("allow_charge_after_normal_move", True)
            )
            unit.special_rules["enhancement_raid_leader_requires_disembarked_from_moved_transport"] = bool(
                params.get("requires_disembarked_from_moved_transport", True)
            )
            unit.special_rules["enhancement_raid_leader_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_raid_leader_requires_bearer_on_battlefield"] = bool(
                params.get("requires_bearer_on_battlefield", False)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_raid_leader_bearer_model_id"] = bearer_id

        if name == "dread reputation" or enh_id == "000010688004":
            if not is_hurons_marauders:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Dread Reputation").strip() or "Dread Reputation"
            unit.special_rules["enhancement_dread_reputation"] = True
            unit.special_rules["enhancement_dread_reputation_source"] = source
            unit.special_rules["enhancement_dread_reputation_range_in"] = float(
                max(0.0, _coerce_float(params.get("range_in", 6.0), default=6.0))
            )
            unit.special_rules["enhancement_dread_reputation_deep_strike_range_in"] = float(
                max(0.0, _coerce_float(params.get("deep_strike_range_in", 12.0), default=12.0))
            )
            unit.special_rules["enhancement_dread_reputation_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_dread_reputation_requires_bearer_on_battlefield"] = bool(
                params.get("requires_bearer_on_battlefield", False)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_dread_reputation_bearer_model_id"] = bearer_id

        if name == "eager for bloodshed" or enh_id == "000010688005":
            if not is_hurons_marauders:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Eager for Bloodshed").strip() or "Eager for Bloodshed"
            unit.special_rules["enhancement_eager_for_bloodshed"] = True
            unit.special_rules["enhancement_eager_for_bloodshed_source"] = source
            unit.special_rules["enhancement_eager_for_bloodshed_grants_infiltrators"] = bool(
                params.get("grants_infiltrators", True)
            )
            unit.special_rules["enhancement_eager_for_bloodshed_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_eager_for_bloodshed_requires_bearer_on_battlefield"] = bool(
                params.get("requires_bearer_on_battlefield", False)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_eager_for_bloodshed_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if name in {"despot's claim", "despot’s claim"} or enh_id == "000008968002":
            if not is_renegade_raiders:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Despot's Claim").strip() or "Despot's Claim"
            unit.special_rules["enhancement_despots_claim"] = True
            unit.special_rules["enhancement_despots_claim_source"] = source
            unit.special_rules["enhancement_despots_claim_requires_bearer_on_battlefield"] = bool(
                params.get("requires_bearer_on_battlefield", True)
            )
            unit.special_rules["enhancement_despots_claim_success_on"] = int(
                min(6, max(2, _coerce_int(params.get("success_on", 5), default=5)))
            )
            unit.special_rules["enhancement_despots_claim_cp_gain"] = int(
                max(1, _coerce_int(params.get("cp_gain", 1), default=1))
            )
            unit.special_rules["enhancement_despots_claim_enemy_deployment_zone_bonus"] = int(
                max(0, _coerce_int(params.get("enemy_deployment_zone_bonus_if_wholly_within_distance", 1), default=1))
            )
            unit.special_rules["enhancement_despots_claim_enemy_deployment_zone_distance_in"] = float(
                max(0.0, _coerce_float(params.get("enemy_deployment_zone_distance_in", 12.0), default=12.0))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "dread reaver" or enh_id == "000008968003":
            if not is_renegade_raiders:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Dread Reaver").strip() or "Dread Reaver"
            unit.special_rules["enhancement_dread_reaver"] = True
            unit.special_rules["enhancement_dread_reaver_source"] = source
            unit.special_rules["enhancement_dread_reaver_reroll_hit"] = bool(params.get("reroll_hit", True))
            unit.special_rules["enhancement_dread_reaver_reroll_wound"] = bool(params.get("reroll_wound", True))
            unit.special_rules["enhancement_dread_reaver_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_dread_reaver_requires_bearer_on_battlefield"] = bool(
                params.get("requires_bearer_on_battlefield", True)
            )
            unit.special_rules["enhancement_dread_reaver_enemy_deployment_zone_distance_in"] = float(
                max(0.0, _coerce_float(params.get("distance_in", 12.0), default=12.0))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "mark of the hound" or enh_id == "000008968004":
            if not is_renegade_raiders:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Mark of the Hound").strip() or "Mark of the Hound"
            unit.special_rules["enhancement_mark_of_the_hound"] = True
            unit.special_rules["enhancement_mark_of_the_hound_source"] = source
            unit.special_rules["enhancement_mark_of_the_hound_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_mark_of_the_hound_scout_distance"] = int(
                max(0, _coerce_int(params.get("scout_distance", 6), default=6))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name in {"tyrant's lash", "tyrant’s lash"} or enh_id == "000008968005":
            if not is_renegade_raiders:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Tyrant's Lash").strip() or "Tyrant's Lash"
            unit.special_rules["enhancement_tyrants_lash"] = True
            unit.special_rules["enhancement_tyrants_lash_source"] = source
            unit.special_rules["enhancement_tyrants_lash_reroll_advance"] = bool(params.get("reroll_advance", True))
            unit.special_rules["enhancement_tyrants_lash_allow_shoot_after_fall_back"] = bool(
                params.get("allow_shoot_after_fall_back", True)
            )
            unit.special_rules["enhancement_tyrants_lash_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_tyrants_lash_requires_bearer_on_battlefield"] = bool(
                params.get("requires_bearer_on_battlefield", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "weaponised hatred" or enh_id == "000010694002":
            if not is_renegade_warband:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Weaponised Hatred").strip() or "Weaponised Hatred"
            unit.special_rules["enhancement_weaponised_hatred"] = True
            unit.special_rules["enhancement_weaponised_hatred_source"] = source
            unit.special_rules["enhancement_weaponised_hatred_optional"] = bool(params.get("optional", False))
            unit.special_rules["enhancement_weaponised_hatred_requires_vendetta_target"] = bool(
                params.get("requires_vendetta_target", True)
            )
            unit.special_rules["enhancement_weaponised_hatred_requires_bearer_on_battlefield"] = bool(
                params.get("requires_bearer_on_battlefield", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "eyes of the hunter" or enh_id == "000010694003":
            if not is_renegade_warband:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Eyes of the Hunter").strip() or "Eyes of the Hunter"
            unit.special_rules["enhancement_eyes_of_the_hunter"] = True
            unit.special_rules["enhancement_eyes_of_the_hunter_source"] = source
            unit.special_rules["enhancement_eyes_of_the_hunter_ignores_cover_ranged"] = bool(
                "IGNORES COVER" in {
                    str(keyword or "").strip().upper()
                    for keyword in list(params.get("keywords", ("IGNORES COVER",)) or ("IGNORES COVER",))
                    if str(keyword or "").strip()
                }
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "fratricidal trophies" or enh_id == "000010694004":
            if not is_renegade_warband:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Fratricidal Trophies").strip() or "Fratricidal Trophies"
            unit.special_rules["enhancement_fratricidal_trophies"] = True
            unit.special_rules["enhancement_fratricidal_trophies_source"] = source
            unit.special_rules["enhancement_fratricidal_trophies_reroll_hit"] = bool(params.get("reroll_hit", True))
            unit.special_rules["enhancement_fratricidal_trophies_requires_default_to_doctrine"] = bool(
                params.get("requires_default_to_doctrine", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "empyric symbiote" or enh_id == "000010694005":
            if not is_renegade_warband:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Empyric Symbiote").strip() or "Empyric Symbiote"
            unit.special_rules["enhancement_empyric_symbiote"] = True
            unit.special_rules["enhancement_empyric_symbiote_source"] = source
            unit.special_rules["enhancement_empyric_symbiote_advance_roll_bonus"] = int(
                max(0, _coerce_int(params.get("advance_roll_bonus", 1), default=1))
            )
            unit.special_rules["enhancement_empyric_symbiote_charge_roll_bonus"] = int(
                max(0, _coerce_int(params.get("charge_roll_bonus", 1), default=1))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name in {"forge's blessing", "forge’s blessing"} or enh_id == "000008985002":
            if not is_soulforged_warpack:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Forge's Blessing").strip() or "Forge's Blessing"
            unit.special_rules["enhancement_forges_blessing"] = True
            unit.special_rules["enhancement_forges_blessing_source"] = source
            unit.special_rules["enhancement_forges_blessing_range"] = float(
                max(0.0, _coerce_float(params.get("range_in", 12.0), default=12.0))
            )
            unit.special_rules["enhancement_forges_blessing_fnp"] = int(
                min(6, max(2, _coerce_int(params.get("fnp", 6), default=6)))
            )
            unit.special_rules["enhancement_forges_blessing_target_requires_keyword"] = str(
                params.get("required_target_keyword", "VEHICLE") or "VEHICLE"
            ).strip().upper()
            unit.special_rules["enhancement_forges_blessing_target_requires_faction_keyword"] = str(
                params.get("required_target_faction_keyword", "HERETIC ASTARTES") or "HERETIC ASTARTES"
            ).strip().upper()
            unit.special_rules["enhancement_forges_blessing_ability_key"] = "soulforged_warpack_forges_blessing_target"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "tempting addendum" or enh_id == "000008985004":
            if not is_soulforged_warpack:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Tempting Addendum").strip() or "Tempting Addendum"
            unit.special_rules["enhancement_tempting_addendum"] = True
            unit.special_rules["enhancement_tempting_addendum_source"] = source
            unit.special_rules["enhancement_tempting_addendum_range"] = float(
                max(0.0, _coerce_float(params.get("range_in", 3.0), default=3.0))
            )
            unit.special_rules["enhancement_tempting_addendum_dark_pact_failure_mortal_wound_bonus"] = int(
                max(0, _coerce_int(params.get("dark_pact_failure_mortal_wound_bonus", 1), default=1))
            )
            unit.special_rules["enhancement_tempting_addendum_reroll_hit"] = bool(params.get("reroll_hit", True))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "soul harvester" or enh_id == "000008985005":
            if not is_soulforged_warpack:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Soul Harvester").strip() or "Soul Harvester"
            unit.special_rules["enhancement_soul_harvester"] = True
            unit.special_rules["enhancement_soul_harvester_source"] = source
            unit.special_rules["enhancement_soul_harvester_range"] = float(
                max(0.0, _coerce_float(params.get("range_in", 12.0), default=12.0))
            )
            unit.special_rules["enhancement_soul_harvester_success_on"] = int(
                min(6, max(2, _coerce_int(params.get("success_on", 5), default=5)))
            )
            unit.special_rules["enhancement_soul_harvester_cp_gain"] = int(
                max(1, _coerce_int(params.get("cp_gain", 1), default=1))
            )
            unit.special_rules["enhancement_soul_harvester_requires_bearer_on_battlefield"] = bool(
                params.get("requires_bearer_on_battlefield", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "eater of dread" or enh_id == "000008972002":
            if not is_dread_talons:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Eater of Dread").strip() or "Eater of Dread"
            unit.special_rules["enhancement_eater_of_dread"] = True
            unit.special_rules["enhancement_eater_of_dread_source"] = source
            unit.special_rules["enhancement_eater_of_dread_requires_bearer_on_battlefield"] = bool(
                params.get("requires_bearer_on_battlefield", True)
            )
            unit.special_rules["enhancement_eater_of_dread_success_on"] = int(
                min(6, max(2, _coerce_int(params.get("success_on", 5), default=5)))
            )
            unit.special_rules["enhancement_eater_of_dread_cp_gain"] = int(
                max(1, _coerce_int(params.get("cp_gain", 1), default=1))
            )
            unit.special_rules["enhancement_eater_of_dread_enemy_battleshocked_roll_bonus"] = int(
                max(0, _coerce_int(params.get("enemy_battleshocked_roll_bonus", 1), default=1))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_eater_of_dread_bearer_model_id"] = bearer_id

        if name == "greyveil hex" or enh_id == "000010641002":
            if not is_nightmare_hunt:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Greyveil Hex").strip() or "Greyveil Hex"
            unit.special_rules["enhancement_greyveil_hex"] = True
            unit.special_rules["enhancement_greyveil_hex_source"] = source
            unit.special_rules["enhancement_greyveil_hex_stealth"] = bool(params.get("grants_stealth", True))
            unit.special_rules["enhancement_greyveil_hex_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_greyveil_hex_requires_within_controlled_objective_range"] = bool(
                params.get("requires_bearer_unit_within_controlled_objective_range", True)
            )
            unit.special_rules["enhancement_greyveil_hex_ranged_targeting_max_distance"] = float(
                max(0.0, _coerce_float(params.get("ranged_targeting_max_distance", 18.0), default=18.0))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_greyveil_hex_bearer_model_id"] = bearer_id

        if name in {"night's shroud", "nights shroud", "night’s shroud"} or enh_id == "000008972003":
            if not is_dread_talons:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            source = str(getattr(desc, "name", "") or "Night's Shroud").strip() or "Night's Shroud"
            unit.special_rules["enhancement_nights_shroud"] = True
            unit.special_rules["enhancement_nights_shroud_source"] = source
            unit.special_rules["enhancement_nights_shroud_stealth"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_nights_shroud_bearer_model_id"] = bearer_id

        if name == "warp-fuelled thrusters" or enh_id in {"000008972004", "000010641003"}:
            if not (is_dread_talons or is_nightmare_hunt):
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Warp-fuelled Thrusters").strip() or "Warp-fuelled Thrusters"
            trigger_phase = str(params.get("trigger_phase", "OPPONENT_TURN_END") or "OPPONENT_TURN_END").strip().upper()
            if not trigger_phase:
                trigger_phase = "OPPONENT_TURN_END"
            unit.special_rules["enhancement_warp_fuelled_thrusters"] = True
            unit.special_rules["enhancement_warp_fuelled_thrusters_source"] = source
            unit.special_rules["enhancement_warp_fuelled_thrusters_requires_not_engagement_range"] = bool(
                params.get("requires_not_engagement_range", True)
            )
            unit.special_rules["enhancement_warp_fuelled_thrusters_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_warp_fuelled_thrusters_once_per_battle"] = bool(
                params.get("once_per_battle", False)
            )
            unit.special_rules["enhancement_warp_fuelled_thrusters_ability_key"] = (
                str(params.get("ability_key", "warp_fuelled_thrusters") or "warp_fuelled_thrusters").strip().lower()
            )
            unit.special_rules["enhancement_warp_fuelled_thrusters_trigger_phase"] = trigger_phase
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_warp_fuelled_thrusters_bearer_model_id"] = bearer_id

        if name == "terrorglut parasite" or enh_id == "000010641004":
            if not is_nightmare_hunt:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Terrorglut Parasite").strip() or "Terrorglut Parasite"
            modifier = _coerce_int(params.get("battle_shock_test_modifier", -1), default=-1)
            if modifier > 0:
                modifier = -modifier
            if modifier == 0:
                modifier = -1
            unit.special_rules["enhancement_terrorglut_parasite"] = True
            unit.special_rules["enhancement_terrorglut_parasite_source"] = source
            unit.special_rules["enhancement_terrorglut_parasite_battle_shock_test_modifier"] = int(modifier)
            unit.special_rules["enhancement_terrorglut_parasite_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_terrorglut_parasite_bearer_model_id"] = bearer_id

        if name == "sorrowscent vulture" or enh_id == "000010641005":
            if not is_nightmare_hunt:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Sorrowscent Vulture").strip() or "Sorrowscent Vulture"
            scout_distance = _coerce_int(params.get("scouts_distance", 6), default=6)
            attach_names = [
                str(v).strip()
                for v in list(params.get("attachment_override_unit_names_any", ("Warp Talons",)) or ())
                if str(v or "").strip()
            ]
            attach_ids = [
                str(v).strip()
                for v in list(params.get("attachment_override_unit_datasheet_ids_any", ("000000959",)) or ())
                if str(v or "").strip()
            ]
            unit.special_rules["enhancement_sorrowscent_vulture"] = True
            unit.special_rules["enhancement_sorrowscent_vulture_source"] = source
            unit.special_rules["enhancement_sorrowscent_vulture_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_sorrowscent_vulture_scout_distance"] = int(max(0, scout_distance))
            unit.special_rules["enhancement_sorrowscent_vulture_attach_unit_names"] = list(attach_names)
            unit.special_rules["enhancement_sorrowscent_vulture_attach_unit_datasheet_ids"] = list(attach_ids)
            allowed_attach = [str(v).strip() for v in list(getattr(unit, "can_be_attached_to", []) or []) if str(v).strip()]
            allowed_set = set(allowed_attach)
            for attach_id in attach_ids:
                if attach_id not in allowed_set:
                    allowed_attach.append(attach_id)
                    allowed_set.add(attach_id)
            unit.can_be_attached_to = list(allowed_attach)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_sorrowscent_vulture_bearer_model_id"] = bearer_id

        if name == "willbreaker" or enh_id == "000008972005":
            if not is_dread_talons:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Willbreaker").strip() or "Willbreaker"
            unit.special_rules["enhancement_willbreaker"] = True
            unit.special_rules["enhancement_willbreaker_source"] = source
            unit.special_rules["enhancement_willbreaker_applies_after_fight"] = bool(
                params.get("applies_after_fight", True)
            )
            unit.special_rules["enhancement_willbreaker_requires_bearer_hit_target"] = bool(
                params.get("requires_bearer_hit_target", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_willbreaker_bearer_model_id"] = bearer_id

        if name == "bastion plate" or enh_id == "000008976002":
            if not is_fellhammer_siege_host:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Bastion Plate").strip() or "Bastion Plate"
            unit.special_rules["enhancement_bastion_plate"] = True
            unit.special_rules["enhancement_bastion_plate_source"] = source
            unit.special_rules["enhancement_bastion_plate_set_damage_to"] = int(
                max(0, _coerce_int(params.get("set_damage_to", 0), default=0))
            )
            unit.special_rules["enhancement_bastion_plate_usage_scope"] = str(
                params.get("usage_scope", "battle_round") or "battle_round"
            ).strip().lower()
            unit.special_rules["enhancement_bastion_plate_optional"] = bool(params.get("optional", True))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_bastion_plate_bearer_model_id"] = bearer_id

        if name == "iron artifice" or enh_id == "000008976003":
            if not is_fellhammer_siege_host:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Iron Artifice").strip() or "Iron Artifice"
            unit.special_rules["enhancement_iron_artifice"] = True
            unit.special_rules["enhancement_iron_artifice_source"] = source
            unit.special_rules["enhancement_iron_artifice_anti_vehicle"] = int(
                min(6, max(2, _coerce_int(params.get("anti_vehicle", 4), default=4)))
            )
            unit.special_rules["enhancement_iron_artifice_anti_fortification"] = int(
                min(6, max(2, _coerce_int(params.get("anti_fortification", 4), default=4)))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_iron_artifice_bearer_model_id"] = bearer_id

        if name == "ironbound enmity" or enh_id == "000008976004":
            if not is_fellhammer_siege_host:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Ironbound Enmity").strip() or "Ironbound Enmity"
            unit.special_rules["enhancement_ironbound_enmity"] = True
            unit.special_rules["enhancement_ironbound_enmity_source"] = source
            unit.special_rules["enhancement_ironbound_enmity_wound_roll_bonus"] = int(
                max(0, _coerce_int(params.get("wound_roll_bonus", 1), default=1))
            )
            unit.special_rules["enhancement_ironbound_enmity_requires_within_objective_range"] = bool(
                params.get("requires_within_objective_range", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_ironbound_enmity_bearer_model_id"] = bearer_id

        if name == "warp tracer" or enh_id == "000008976005":
            if not is_fellhammer_siege_host:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Warp Tracer").strip() or "Warp Tracer"
            unit.special_rules["enhancement_warp_tracer"] = True
            unit.special_rules["enhancement_warp_tracer_source"] = source
            unit.special_rules["enhancement_warp_tracer_attack_type"] = str(
                params.get("attack_type", "ranged") or "ranged"
            ).strip().lower()
            unit.special_rules["enhancement_warp_tracer_requires_bearer_hit_target"] = bool(
                params.get("requires_bearer_hit_target", True)
            )
            unit.special_rules["enhancement_warp_tracer_expires_timing"] = str(
                params.get("expires_timing", "phase_end") or "phase_end"
            ).strip().lower()
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_warp_tracer_bearer_model_id"] = bearer_id

        if name == "eager for vengeance" or enh_id == "000008960002":
            if not is_veterans_of_the_long_war:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Eager for Vengeance").strip() or "Eager for Vengeance"
            unit.special_rules["enhancement_eager_for_vengeance"] = True
            unit.special_rules["enhancement_eager_for_vengeance_source"] = source
            unit.special_rules["enhancement_eager_for_vengeance_allow_shoot_after_fall_back"] = bool(
                params.get("allow_shoot_after_fall_back", True)
            )
            unit.special_rules["enhancement_eager_for_vengeance_allow_charge_after_fall_back"] = bool(
                params.get("allow_charge_after_fall_back", True)
            )
            unit.special_rules["enhancement_eager_for_vengeance_requires_focus_of_hatred_target"] = bool(
                params.get("requires_focus_of_hatred_target", True)
            )
            unit.special_rules["enhancement_eager_for_vengeance_requires_fell_back_this_turn"] = bool(
                params.get("requires_unit_fell_back_this_turn_for_hit_bonus", True)
            )
            unit.special_rules["enhancement_eager_for_vengeance_hit_roll_bonus"] = int(
                max(0, _coerce_int(params.get("focus_hit_roll_bonus", 1), default=1))
            )
            unit.special_rules["enhancement_eager_for_vengeance_charge_roll_bonus"] = int(
                max(0, _coerce_int(params.get("focus_charge_roll_bonus", 1), default=1))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "eye of abaddon" or enh_id == "000008960003":
            if not is_veterans_of_the_long_war:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Eye of Abaddon").strip() or "Eye of Abaddon"
            unit.special_rules["enhancement_eye_of_abaddon"] = True
            unit.special_rules["enhancement_eye_of_abaddon_source"] = source
            unit.special_rules["enhancement_eye_of_abaddon_requires_bearer_on_battlefield"] = bool(
                params.get("requires_bearer_on_battlefield", True)
            )
            unit.special_rules["enhancement_eye_of_abaddon_success_on"] = int(
                min(6, max(2, _coerce_int(params.get("success_on", 4), default=4)))
            )
            unit.special_rules["enhancement_eye_of_abaddon_cp_gain"] = int(
                max(1, _coerce_int(params.get("cp_gain", 1), default=1))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "mark of legend" or enh_id == "000008960004":
            if not is_veterans_of_the_long_war:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Mark of Legend").strip() or "Mark of Legend"
            unit.special_rules["enhancement_mark_of_legend"] = True
            unit.special_rules["enhancement_mark_of_legend_source"] = source
            unit.special_rules["enhancement_mark_of_legend_once_per_turn"] = bool(params.get("once_per_turn", True))
            unit.special_rules["enhancement_mark_of_legend_allow_hit_reroll"] = bool(params.get("allow_hit_reroll", True))
            unit.special_rules["enhancement_mark_of_legend_allow_wound_reroll"] = bool(
                params.get("allow_wound_reroll", True)
            )
            unit.special_rules["enhancement_mark_of_legend_allow_save_reroll"] = bool(params.get("allow_save_reroll", True))
            unit.special_rules["enhancement_mark_of_legend_last_used_turn"] = int(
                unit.special_rules.get("enhancement_mark_of_legend_last_used_turn", 0) or 0
            )
            unit.special_rules["enhancement_mark_of_legend_last_used_turn_owner"] = str(
                unit.special_rules.get("enhancement_mark_of_legend_last_used_turn_owner", "") or ""
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name in {"warmaster's gift", "warmasters gift", "warmaster’s gift"} or enh_id == "000008960005":
            if not is_veterans_of_the_long_war:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Warmaster's Gift").strip() or "Warmaster's Gift"
            unit.special_rules["enhancement_warmasters_gift"] = True
            unit.special_rules["enhancement_warmasters_gift_source"] = source
            unit.special_rules["enhancement_warmasters_gift_crit_wound_threshold"] = int(
                min(6, max(2, _coerce_int(params.get("critical_wound_threshold", 5), default=5)))
            )
            unit.special_rules["enhancement_warmasters_gift_requires_focus_of_hatred_target"] = bool(
                params.get("requires_focus_of_hatred_target", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "surgical precision" or enh_id == "000009773002":
            if not is_creations_of_bile:
                return
            unit.special_rules["enhancement_surgical_precision"] = True
            unit.special_rules["enhancement_bearer_melee_precision"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_surgical_precision_bearer_model_id"] = bearer_id

        if name == "living carapace" or enh_id == "000009773003":
            if not is_creations_of_bile:
                return
            unit.special_rules["enhancement_living_carapace"] = True
            unit.special_rules["enhancement_living_carapace_source"] = "Living Carapace"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_living_carapace_bearer_model_id"] = bearer_id
            if bearer is not None and not bool(unit.special_rules.get("enhancement_living_carapace_bearer_wounds_applied", False)):
                try:
                    bearer._base_wounds = int(getattr(bearer, "_base_wounds", 0) or 0) + 1
                    bearer._wounds = int(getattr(bearer, "_wounds", 0) or 0) + 1
                    base_unmod = getattr(bearer, "_base_wounds_unmodified", None)
                    if base_unmod is not None:
                        bearer._base_wounds_unmodified = int(base_unmod or 0) + 1
                    unit.special_rules["enhancement_living_carapace_bearer_wounds_applied"] = True
                except (TypeError, ValueError):
                    pass
            if not bool(unit.special_rules.get("enhancement_living_carapace_wounds_corrected", False)):
                applied_kinds = getattr(unit, "_enhancement_effect_kinds_applied", set())
                wounds_add_applied = bool(isinstance(applied_kinds, set) and "wounds_add" in applied_kinds)
                bearer_entity_id = str(get_entity_id(bearer) or "") if bearer is not None else ""
                for model in list(getattr(unit, "models", []) or []):
                    if model is None:
                        continue
                    model_id = str(get_entity_id(model) or "")
                    is_bearer_model = bool(bearer_entity_id and model_id == bearer_entity_id)
                    if not is_bearer_model and bearer_id:
                        local_id = str(getattr(model, "id", getattr(model, "_id", "")) or "")
                        is_bearer_model = local_id == str(bearer_id)
                    if is_bearer_model:
                        continue
                    if not wounds_add_applied:
                        continue
                    try:
                        model._base_wounds = max(1, int(getattr(model, "_base_wounds", 1) or 1) - 1)
                        model._wounds = max(1, int(getattr(model, "_wounds", 1) or 1) - 1)
                        base_unmod = getattr(model, "_base_wounds_unmodified", None)
                        if base_unmod is not None:
                            model._base_wounds_unmodified = max(1, int(base_unmod or 1) - 1)
                    except (TypeError, ValueError):
                        continue
                unit.special_rules["enhancement_living_carapace_wounds_corrected"] = True
                try:
                    unit.starting_total_wounds = sum(
                        int(getattr(model, "_base_wounds", 0) or 0)
                        for model in list(getattr(unit, "models", []) or [])
                    )
                except (TypeError, ValueError):
                    pass
            tag = f"enhancement_fnp_{enh_id or name}"
            _ensure_enhancement_fnp_entry(
                unit,
                5,
                source="Living Carapace",
                tag=tag,
                source_model_id=str(bearer_id) if bearer_id else None,
            )
            if bearer_id:
                entries = list(unit.special_rules.get("enhancement_bearer_fnp_entries", []) or [])
                changed = False
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    if str(entry.get("tag", "") or "") != tag:
                        continue
                    entry["source_model_id"] = str(bearer_id)
                    changed = True
                if changed:
                    unit.special_rules["enhancement_bearer_fnp_entries"] = entries

        if name in ("helm of all-seeing", "helm of all seeing") or enh_id == "000009773004":
            if not is_creations_of_bile:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                min_enemy_distance = float(params.get("min_enemy_distance", 12.0) or 12.0)
            except (TypeError, ValueError):
                min_enemy_distance = 12.0
            unit.special_rules["enhancement_helm_of_all_seeing"] = True
            unit.special_rules["enhancement_helm_of_all_seeing_source"] = "Helm of All-seeing"
            unit.special_rules["enhancement_helm_of_all_seeing_min_enemy_distance"] = float(max(0.0, min_enemy_distance))
            unit.special_rules["enhancement_helm_of_all_seeing_horizontal_only"] = bool(params.get("horizontal_only", False))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_helm_of_all_seeing_bearer_model_id"] = bearer_id

        if name == "prime test subject" or enh_id == "000009773005":
            if not is_creations_of_bile:
                return
            unit.special_rules["enhancement_prime_test_subject"] = True
            unit.special_rules["enhancement_prime_test_subject_source"] = "Prime Test Subject"
            unit.special_rules["enhancement_prime_test_subject_melee_reroll_hit"] = True
            unit.special_rules["enhancement_bearer_melee_damage_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_damage_bonus", 0) or 0
            ) + 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_prime_test_subject_bearer_model_id"] = bearer_id

        if name == "blood-forged armour" or enh_id == "000010078003":
            if not is_khorne_daemonkin:
                return
            unit.special_rules["enhancement_blood_forged_armour"] = True

        if name == "icon of war" or enh_id == "000010078002":
            if not is_khorne_daemonkin:
                return
            unit.special_rules["enhancement_icon_of_war"] = True

        if name == "blade of endless bloodshed" or enh_id == "000010078005":
            if not is_khorne_daemonkin:
                return
            unit.special_rules["enhancement_blade_of_endless_bloodshed"] = True

        if name == "disciple of khorne" or enh_id == "000010078004":
            if not is_khorne_daemonkin:
                return
            unit.special_rules["enhancement_disciple_of_khorne"] = True

        if name == "murderous onslaught" or enh_id == "000010086002":
            if not is_goretrack_onslaught:
                return
            unit.special_rules["enhancement_murderous_onslaught"] = True

        if name == "aggressive deployment" or enh_id == "000010086003":
            if not is_goretrack_onslaught:
                return
            unit.special_rules["enhancement_aggressive_deployment"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            if desc is not None:
                scouts_distance = float(desc.effect_params.get("scouts_distance", 0) or 0)
                if scouts_distance > 0:
                    unit.special_rules["enhancement_aggressive_deployment_scouts_distance"] = scouts_distance

        if name == "unleash hell" or enh_id == "000010086004":
            if not is_goretrack_onslaught:
                return
            unit.special_rules["enhancement_unleash_hell"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "infernal infusion" or enh_id == "000010086005":
            if not is_goretrack_onslaught:
                return
            unit.special_rules["enhancement_infernal_infusion"] = True

        if name == "chosen of the blood god" or enh_id == "000010074002":
            if not is_cult_of_blood:
                return
            unit.special_rules["enhancement_chosen_of_blood_god"] = True
            unit.special_rules["enhancement_chosen_of_blood_god_aura_range_bonus"] = int(
                unit.special_rules.get("enhancement_chosen_of_blood_god_aura_range_bonus", 0) or 0
            ) + 3
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "butcher lord" or enh_id == "000010074003":
            if not is_cult_of_blood:
                return
            unit.special_rules["enhancement_butcher_lord"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "brazen form" or enh_id == "000010074004":
            if not is_cult_of_blood:
                return
            unit.special_rules["enhancement_brazen_form"] = True
            _ensure_enhancement_fnp_entry(
                unit,
                5,
                source="Brazen Form",
                tag="brazen_form",
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
            if bearer is not None:
                try:
                    bearer._base_toughness = int(getattr(bearer, "_base_toughness", 0)) + 1
                    bearer._toughness = int(getattr(bearer, "_toughness", 0)) + 1
                except Exception:
                    pass

        if name == "strategic slaughter" or enh_id == "000010074005":
            if not is_cult_of_blood:
                return
            unit.special_rules["enhancement_strategic_slaughter"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "malicious vigour" or enh_id == "000010082002":
            if not is_possessed_slaughterband:
                return
            unit.special_rules["enhancement_malicious_vigour"] = True
            unit.special_rules["enhancement_malicious_vigour_brazen_fury_distance"] = int(
                unit.special_rules.get("enhancement_malicious_vigour_brazen_fury_distance", 0) or 6
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "killing clarity" or enh_id == "000010082003":
            if not is_possessed_slaughterband:
                return
            unit.special_rules["enhancement_killing_clarity"] = True
            unit.special_rules["enhancement_killing_clarity_success_on"] = int(
                unit.special_rules.get("enhancement_killing_clarity_success_on", 0) or 4
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "frenzied focus" or enh_id == "000010082004":
            if not is_possessed_slaughterband:
                return
            unit.special_rules["enhancement_frenzied_focus"] = True
            unit.special_rules["enhancement_frenzied_focus_crit_hit_threshold"] = int(
                unit.special_rules.get("enhancement_frenzied_focus_crit_hit_threshold", 0) or 5
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "violent demise" or enh_id == "000010082005":
            if not is_possessed_slaughterband:
                return
            unit.special_rules["enhancement_violent_demise"] = True
            unit.special_rules["enhancement_violent_demise_trigger_threshold"] = int(
                unit.special_rules.get("enhancement_violent_demise_trigger_threshold", 0) or 2
            )
            unit.special_rules["enhancement_violent_demise_damage_dice"] = str(
                unit.special_rules.get("enhancement_violent_demise_damage_dice", "") or "D3+1"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "archslaughterer" or enh_id == "000009847002":
            if not is_vessels_of_wrath:
                return
            unit.special_rules["enhancement_archslaughterer"] = True
            unit.special_rules["enhancement_bearer_melee_ap_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_ap_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_archslaughterer_vessel_melee_damage_bonus"] = 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "vox-diabolus" or enh_id == "000009847003":
            if not is_vessels_of_wrath:
                return
            unit.special_rules["enhancement_vox_diabolus"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "avenger's crown" or enh_id == "000009847004":
            if not is_vessels_of_wrath:
                return
            unit.special_rules["enhancement_avengers_crown"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "gateways to glory" or enh_id == "000009847005":
            if not is_vessels_of_wrath:
                return
            unit.special_rules["enhancement_gateways_to_glory"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "bastion shield" or enh_id == "000009823002":
            if not is_hearthband:
                return
            unit.special_rules["enhancement_bastion_shield"] = True
            unit.special_rules["enhancement_bastion_shield_base_range"] = 12
            unit.special_rules["enhancement_bastion_shield_extended_range"] = 18
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "quake multigenerator" or enh_id == "000009823003":
            if not is_hearthband:
                return
            unit.special_rules["enhancement_quake_multigenerator"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "high kahl" or enh_id == "000009823005":
            if not is_hearthband:
                return
            unit.special_rules["enhancement_high_kahl"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "oathbound speculator" or enh_id == "000010435002":
            if not is_needgaard_oathband:
                return
            unit.special_rules["enhancement_oathbound_speculator"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "dead reckoning" or enh_id == "000010435003":
            if not is_needgaard_oathband:
                return
            unit.special_rules["enhancement_dead_reckoning"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "iron ambassador" or enh_id == "000010435004":
            if not is_needgaard_oathband:
                return
            unit.special_rules["enhancement_iron_ambassador"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "ancestral crest" or enh_id == "000010435005":
            if not is_needgaard_oathband:
                return
            unit.special_rules["enhancement_ancestral_crest"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "carmine reliquary" or enh_id == "000010645002":
            unit.special_rules["enhancement_carmine_reliquary"] = True
            unit.special_rules["enhancement_scout_distance"] = max(
                int(unit.special_rules.get("enhancement_scout_distance", 0) or 0),
                6,
            )

        if name == "angel's fang" or enh_id == "000010645005":
            unit.special_rules["enhancement_angels_fang"] = True

        if name == "timeless strategist" or enh_id == "000009899003":
            if not is_warhost:
                return
            unit.special_rules["enhancement_timeless_strategist_battle_focus_bonus"] = int(
                unit.special_rules.get("enhancement_timeless_strategist_battle_focus_bonus", 0) or 0
            ) + 1

        if name == "pirate prince" or enh_id == "000010699002":
            if not is_eldritch_raiders:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            refund_threshold = _coerce_int(params.get("refund_roll_threshold", 3) or 3, default=3)
            refund_tokens = _coerce_int(params.get("refund_tokens", 1) or 1, default=1)
            source_name = str(getattr(self, "name", "") or "Pirate Prince").strip() or "Pirate Prince"
            unit.special_rules["enhancement_pirate_prince"] = True
            unit.special_rules["enhancement_pirate_prince_refund_roll_threshold"] = int(max(2, refund_threshold))
            unit.special_rules["enhancement_pirate_prince_refund_tokens"] = int(max(1, refund_tokens))
            unit.special_rules["enhancement_pirate_prince_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "alacritous assault" or enh_id == "000010699003":
            if not is_eldritch_raiders:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            keywords = tuple(str(v or "").strip().upper() for v in list(params.get("keywords", ("LANCE",))) if str(v or "").strip())
            has_lance = any(v == "LANCE" for v in keywords)
            source_name = str(getattr(self, "name", "") or "Alacritous Assault").strip() or "Alacritous Assault"
            unit.special_rules["enhancement_alacritous_assault"] = bool(has_lance)
            unit.special_rules["enhancement_alacritous_assault_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "exotic munitions" or enh_id == "000010699004":
            if not is_eldritch_raiders:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            anti_monster = 5
            anti_vehicle = 5
            for raw in list(params.get("keywords", ()) or ()):
                token = str(raw or "").strip().upper()
                if not token:
                    continue
                m = re.search(r"ANTI-MONSTER\s+(\d)\+", token)
                if m:
                    anti_monster = _coerce_int(m.group(1), default=5)
                m = re.search(r"ANTI-VEHICLE\s+(\d)\+", token)
                if m:
                    anti_vehicle = _coerce_int(m.group(1), default=5)
            source_name = str(getattr(self, "name", "") or "Exotic Munitions").strip() or "Exotic Munitions"
            unit.special_rules["enhancement_exotic_munitions"] = True
            unit.special_rules["enhancement_exotic_munitions_anti_monster"] = int(max(2, anti_monster))
            unit.special_rules["enhancement_exotic_munitions_anti_vehicle"] = int(max(2, anti_vehicle))
            unit.special_rules["enhancement_exotic_munitions_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "adrenal infusions" or enh_id == "000010699005":
            if not is_eldritch_raiders:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source_name = str(getattr(self, "name", "") or "Adrenal Infusions").strip() or "Adrenal Infusions"
            unit.special_rules["enhancement_adrenal_infusions"] = True
            unit.special_rules["enhancement_adrenal_infusions_free_fade_back"] = bool(
                params.get("free_fade_back", True)
            )
            unit.special_rules["enhancement_adrenal_infusions_ignore_phase_fade_back_limit"] = bool(
                params.get("ignore_phase_fade_back_limit", True)
            )
            unit.special_rules["enhancement_adrenal_infusions_no_phase_fade_back_consumption"] = bool(
                params.get("does_not_consume_phase_fade_back_limit", True)
            )
            unit.special_rules["enhancement_adrenal_infusions_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "firstdrawn blade" or enh_id == "000009903002":
            if not is_windrider_host:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            scout_distance = _coerce_int(params.get("scouts_distance", 9) or 9, default=9)
            unit.special_rules["enhancement_firstdrawn_blade"] = True
            unit.special_rules["enhancement_scout_distance"] = max(
                int(unit.special_rules.get("enhancement_scout_distance", 0) or 0),
                int(max(0, scout_distance)),
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "mirage field" or enh_id == "000009903003":
            if not is_windrider_host:
                return
            unit.special_rules["enhancement_mirage_field"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "seersight strike" or enh_id == "000009903004":
            if not is_windrider_host:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            anti_monster = _coerce_int(params.get("anti_monster", 2) or 2, default=2)
            anti_vehicle = _coerce_int(params.get("anti_vehicle", 2) or 2, default=2)
            unit.special_rules["enhancement_seersight_strike"] = True
            unit.special_rules["enhancement_seersight_strike_anti_monster"] = int(max(2, anti_monster))
            unit.special_rules["enhancement_seersight_strike_anti_vehicle"] = int(max(2, anti_vehicle))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "echoes of ulthanesh" or enh_id == "000009903005":
            if not is_windrider_host:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            success_on = _coerce_int(params.get("success_on", 5) or 5, default=5)
            cp_gain = _coerce_int(params.get("cp_gain", 1) or 1, default=1)
            outside_bonus = _coerce_int(params.get("outside_own_zone_bonus", 1) or 1, default=1)
            enemy_bonus = _coerce_int(params.get("enemy_zone_additional_bonus", 1) or 1, default=1)
            unit.special_rules["enhancement_echoes_of_ulthanesh"] = True
            unit.special_rules["enhancement_echoes_of_ulthanesh_success_on"] = int(max(2, success_on))
            unit.special_rules["enhancement_echoes_of_ulthanesh_cp_gain"] = int(max(0, cp_gain))
            unit.special_rules["enhancement_echoes_of_ulthanesh_outside_own_zone_bonus"] = int(max(0, outside_bonus))
            unit.special_rules["enhancement_echoes_of_ulthanesh_enemy_zone_bonus"] = int(max(0, enemy_bonus))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "cegorach's coil" or enh_id == "000009915002":
            if not is_ghosts_of_the_webway:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            threshold = _coerce_int(params.get("roll_threshold", 4) or 4, default=4)
            mortal_per_success = _coerce_int(params.get("mortal_per_success", 1) or 1, default=1)
            max_mortal_wounds = _coerce_int(params.get("max_mortal_wounds", 6) or 6, default=6)
            source_name = str(getattr(self, "name", "") or "Cegorach's Coil").strip() or "Cegorach's Coil"
            unit.special_rules["enhancement_cegorachs_coil"] = True
            unit.special_rules["enhancement_cegorachs_coil_roll_threshold"] = int(max(2, threshold))
            unit.special_rules["enhancement_cegorachs_coil_mortal_per_success"] = int(max(1, mortal_per_success))
            unit.special_rules["enhancement_cegorachs_coil_max_mortal_wounds"] = int(max(1, max_mortal_wounds))
            unit.special_rules["enhancement_cegorachs_coil_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "mask of secrets" or enh_id == "000009915003":
            if not is_ghosts_of_the_webway:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            bs_penalty = abs(
                _coerce_int(
                    params.get("battle_shock_test_modifier", -1) or -1,
                    default=-1,
                )
            )
            source_name = str(getattr(self, "name", "") or "Mask of Secrets").strip() or "Mask of Secrets"
            unit.special_rules["enhancement_mask_of_secrets"] = True
            unit.special_rules["enhancement_mask_of_secrets_exclude_monster_vehicle"] = bool(
                params.get("exclude_monster_vehicle", True)
            )
            unit.special_rules["enhancement_mask_of_secrets_battleshock_penalty"] = int(max(0, bs_penalty))
            unit.special_rules["enhancement_mask_of_secrets_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "murder's jest" or enh_id == "000009915004":
            if not is_ghosts_of_the_webway:
                return
            source_name = str(getattr(self, "name", "") or "Murder's Jest").strip() or "Murder's Jest"
            unit.special_rules["enhancement_murders_jest"] = True
            unit.special_rules["enhancement_murders_jest_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "mistweave" or enh_id == "000009915005":
            if not is_ghosts_of_the_webway:
                return
            source_name = str(getattr(self, "name", "") or "Mistweave").strip() or "Mistweave"
            unit.special_rules["enhancement_mistweave"] = True
            unit.special_rules["enhancement_mistweave_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "light of clarity" or enh_id == "000009907002":
            if not is_spirit_conclave:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            infantry_bonus = _coerce_int(
                params.get("infantry_objective_control_bonus", 1) or 1,
                default=1,
            )
            monster_bonus = _coerce_int(
                params.get("monster_objective_control_bonus", 3) or 3,
                default=3,
            )
            source_name = str(getattr(self, "name", "") or "Light of Clarity").strip() or "Light of Clarity"
            unit.special_rules["enhancement_light_of_clarity"] = True
            unit.special_rules["enhancement_light_of_clarity_range"] = 12
            unit.special_rules["enhancement_light_of_clarity_infantry_oc_bonus"] = int(max(0, infantry_bonus))
            unit.special_rules["enhancement_light_of_clarity_monster_oc_bonus"] = int(max(0, monster_bonus))
            unit.special_rules["enhancement_light_of_clarity_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "stave of kurnous" or enh_id == "000009907003":
            if not is_spirit_conclave:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source_name = str(getattr(self, "name", "") or "Stave of Kurnous").strip() or "Stave of Kurnous"
            unit.special_rules["enhancement_stave_of_kurnous"] = True
            unit.special_rules["enhancement_stave_of_kurnous_range"] = 12
            unit.special_rules["enhancement_stave_of_kurnous_exclude_titanic"] = bool(
                params.get("exclude_titanic", True)
            )
            unit.special_rules["enhancement_stave_of_kurnous_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "rune of mists" or enh_id == "000009907004":
            if not is_spirit_conclave:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            threshold = _coerce_int(
                params.get("minimum_attacker_distance_for_cover", 18) or 18,
                default=18,
            )
            source_name = str(getattr(self, "name", "") or "Rune of Mists").strip() or "Rune of Mists"
            unit.special_rules["enhancement_rune_of_mists"] = True
            unit.special_rules["enhancement_rune_of_mists_range"] = 12
            unit.special_rules["enhancement_rune_of_mists_min_attacker_distance_for_cover"] = int(max(1, threshold))
            unit.special_rules["enhancement_rune_of_mists_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "higher duty" or enh_id == "000009907005":
            if not is_spirit_conclave:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            trigger_range = _coerce_int(params.get("trigger_range", 9) or 9, default=9)
            normal_move = _coerce_int(params.get("normal_move_distance", 6) or 6, default=6)
            source_name = str(getattr(self, "name", "") or "Higher Duty").strip() or "Higher Duty"
            unit.special_rules["enhancement_higher_duty"] = True
            unit.special_rules["enhancement_higher_duty_trigger_range"] = int(max(1, trigger_range))
            unit.special_rules["enhancement_higher_duty_normal_move_distance"] = int(max(1, normal_move))
            unit.special_rules["enhancement_higher_duty_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "key of ghosts" or enh_id == "000010649002":
            if not is_serpents_brood:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            scout_distance = _coerce_int(params.get("scouts_distance", 6) or 6, default=6)
            unit.special_rules["enhancement_key_of_ghosts"] = True
            unit.special_rules["enhancement_scout_distance"] = max(
                int(unit.special_rules.get("enhancement_scout_distance", 0) or 0),
                int(max(0, scout_distance)),
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name in ("weavers' wail", "weavers’ wail") or enh_id == "000010649003":
            if not is_serpents_brood:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            strength_bonus = _coerce_int(params.get("strength_bonus", 3) or 3, default=3)
            attacks_bonus = _coerce_int(params.get("attacks_bonus", 1) or 1, default=1)
            unit.special_rules["enhancement_weavers_wail"] = True
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0) or 0
            ) + int(max(0, strength_bonus))
            unit.special_rules["enhancement_bearer_melee_attacks_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_attacks_bonus", 0) or 0
            ) + int(max(0, attacks_bonus))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "fanged leer" or enh_id == "000010649004":
            if not is_serpents_brood:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            max_selected = _coerce_int(params.get("max_selected_abilities", 2) or 2, default=2)
            unit.special_rules["enhancement_fanged_leer"] = True
            unit.special_rules["enhancement_fanged_leer_select_count"] = int(max(1, max_selected))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "shedskin raiment" or enh_id == "000010649005":
            if not is_serpents_brood:
                return
            unit.special_rules["enhancement_shedskin_raiment"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "gaze of ynnead" or enh_id == "000009919002":
            if not is_devoted_of_ynnead:
                return
            source_name = str(getattr(self, "name", "") or "Gaze of Ynnead").strip() or "Gaze of Ynnead"
            unit.special_rules["enhancement_gaze_of_ynnead"] = True
            unit.special_rules["enhancement_gaze_of_ynnead_weapon_name"] = "eldritch storm"
            unit.special_rules["enhancement_gaze_of_ynnead_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "storm of whispers" or enh_id == "000009919003":
            if not is_devoted_of_ynnead:
                return
            source_name = str(getattr(self, "name", "") or "Storm of Whispers").strip() or "Storm of Whispers"
            unit.special_rules["enhancement_storm_of_whispers"] = True
            unit.special_rules["enhancement_storm_of_whispers_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "borrowed vigour" or enh_id == "000009919004":
            if not is_devoted_of_ynnead:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            attacks_bonus = _coerce_int(params.get("attacks_bonus", 2) or 2, default=2)
            unit.special_rules["enhancement_borrowed_vigour"] = True
            unit.special_rules["enhancement_bearer_melee_attacks_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_attacks_bonus", 0) or 0
            ) + int(max(0, attacks_bonus))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "morbid might" or enh_id == "000009919005":
            if not is_devoted_of_ynnead:
                return
            source_name = str(getattr(self, "name", "") or "Morbid Might").strip() or "Morbid Might"
            unit.special_rules["enhancement_morbid_might"] = True
            unit.special_rules["enhancement_morbid_might_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "guiding presence" or enh_id == "000009769002":
            if not is_armoured_warhost:
                return
            unit.special_rules["enhancement_guiding_presence"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "harmonisation matrix" or enh_id == "000009769003":
            if not is_armoured_warhost:
                return
            unit.special_rules["enhancement_harmonisation_matrix"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "spirit stone of raelyth" or enh_id == "000009769004":
            if not is_armoured_warhost:
                return
            unit.special_rules["enhancement_spirit_stone_of_raelyth"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "guileful strategist" or enh_id == "000009769005":
            if not is_armoured_warhost:
                return
            unit.special_rules["enhancement_guileful_strategist"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "lucid eye" or enh_id == "000009923002":
            if not is_seer_council:
                return
            unit.special_rules["enhancement_lucid_eye"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "runes of warding" or enh_id == "000009923003":
            if not is_seer_council:
                return
            unit.special_rules["enhancement_runes_of_warding"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "stone of eldritch fury" or enh_id == "000009923004":
            if not is_seer_council:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            bonus = _coerce_int(params.get("range_bonus", 12) or 12, default=12)
            unit.special_rules["enhancement_stone_of_eldritch_fury"] = True
            unit.special_rules["enhancement_bearer_psychic_ranged_range_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_psychic_ranged_range_bonus", 0) or 0
            ) + int(max(0, bonus))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "aspect of murder" or enh_id == "000009927002":
            if not is_aspect_host:
                return
            unit.special_rules["enhancement_aspect_of_murder"] = True
            unit.special_rules["enhancement_bearer_melee_damage_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_damage_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_melee_precision"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "mantle of wisdom" or enh_id == "000009927003":
            if not is_aspect_host:
                return
            unit.special_rules["enhancement_mantle_of_wisdom"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "shimmerstone" or enh_id == "000009927004":
            if not is_aspect_host:
                return
            unit.special_rules["enhancement_shimmerstone"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "strategic savant" or enh_id == "000009927005":
            if not is_aspect_host:
                return
            unit.special_rules["enhancement_strategic_savant"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "faultless opportunist" or enh_id == "000010002002":
            unit.special_rules["enhancement_faultless_opportunist"] = True

        if name == "rise to the challenge" or enh_id == "000010002005":
            unit.special_rules["enhancement_rise_to_challenge"] = True

        if name == "pledge of eternal servitude" or enh_id == "000010014002":
            if not is_coterie_of_conceited:
                return
            unit.special_rules["enhancement_pledge_of_eternal_servitude"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
            refresh_return = getattr(unit, "_refresh_return_on_death_flags", None)
            if callable(refresh_return):
                refresh_return()

        if name == "pledge of dark glory" or enh_id == "000010014003":
            if not is_coterie_of_conceited:
                return
            unit.special_rules["enhancement_pledge_of_dark_glory"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "pledge of mortal pain" or enh_id == "000010014004":
            if not is_coterie_of_conceited:
                return
            unit.special_rules["enhancement_pledge_of_mortal_pain"] = True
            unit.special_rules["enhancement_pledge_of_mortal_pain_range"] = 12
            unit.special_rules["enhancement_pledge_of_mortal_pain_fail_mortal_wounds"] = 3
            unit.special_rules["enhancement_pledge_of_mortal_pain_battleshocked_test_modifier"] = -2
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "pledge of unholy fortune" or enh_id == "000010014005":
            if not is_coterie_of_conceited:
                return
            unit.special_rules["enhancement_pledge_of_unholy_fortune"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "steeped in suffering" or enh_id == "000009998002":
            if not is_court_or_mercurial_host:
                return
            unit.special_rules["enhancement_steeped_in_suffering"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "intoxicating musk" or enh_id == "000009998003":
            if not is_court_or_mercurial_host:
                return
            unit.special_rules["enhancement_intoxicating_musk"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "tactical perfection" or enh_id == "000009998004":
            if not is_court_or_mercurial_host:
                return
            unit.special_rules["enhancement_tactical_perfection"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "loathsome dexterity" or enh_id == "000009998005":
            if not is_court_or_mercurial_host:
                return
            unit.special_rules["enhancement_loathsome_dexterity"] = True
            unit.special_rules["enhancement_loathsome_dexterity_move_types"] = ["move", "advance", "fall_back"]
            unit.special_rules["enhancement_loathsome_dexterity_auto_pass_desperate_escape"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "tears of the phoenix" or enh_id == "000010654002":
            if not is_court_of_the_phoenician:
                return
            unit.special_rules["enhancement_tears_of_the_phoenix"] = True
            unit.special_rules["enhancement_tears_of_the_phoenix_ignore_weapon_skill_modifiers"] = True
            unit.special_rules["enhancement_tears_of_the_phoenix_ignore_hit_roll_modifiers"] = True
            unit.special_rules["enhancement_tears_of_the_phoenix_ignore_wound_roll_modifiers"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "exalted patron" or enh_id == "000010654003":
            if not is_court_of_the_phoenician:
                return
            unit.special_rules["enhancement_exalted_patron"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "soulstain made manifest" or enh_id == "000010654004":
            if not is_court_of_the_phoenician:
                return
            unit.special_rules["enhancement_soulstain_made_manifest"] = True
            unit.special_rules["enhancement_soulstain_battleshock_test_modifier"] = -1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "spiritsliver" or enh_id == "000010654005":
            if not is_court_of_the_phoenician:
                return
            unit.special_rules["enhancement_spiritsliver"] = True
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_melee_attacks_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_attacks_bonus", 0) or 0
            ) + 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "empyric suffusion" or enh_id == "000010010002":
            if not is_carnival_of_excess:
                return
            unit.special_rules["enhancement_empyric_suffusion"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "dark blessings" or enh_id == "000010010003":
            if not is_carnival_of_excess:
                return
            unit.special_rules["enhancement_dark_blessings"] = True
            unit.special_rules["enhancement_dark_blessings_invulnerable_save"] = 3
            unit.special_rules["enhancement_dark_blessings_once_key"] = "dark_blessings"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "possessed blade" or enh_id == "000010010004":
            if not is_carnival_of_excess:
                return
            unit.special_rules["enhancement_possessed_blade"] = True
            unit.special_rules["enhancement_possessed_blade_attacks_bonus"] = 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "warp walker" or enh_id == "000010010005":
            if not is_carnival_of_excess:
                return
            unit.special_rules["enhancement_warp_walker"] = True
            unit.special_rules["enhancement_warp_walker_advance_distance"] = 6
            unit.special_rules["enhancement_warp_walker_move_types"] = ["move", "advance", "fall_back"]
            unit.special_rules["enhancement_warp_walker_auto_pass_desperate_escape"] = True
            existing_effects = list(unit.special_rules.get("advance_no_roll_effects", []) or [])
            existing_effects = [
                entry
                for entry in existing_effects
                if not (isinstance(entry, dict) and str(entry.get("tag", "") or "") == "enhancement:warp_walker")
            ]
            existing_effects.append(
                {
                    "distance": 6,
                    "source": "Warp Walker",
                    "tag": "enhancement:warp_walker",
                }
            )
            unit.special_rules["advance_no_roll_effects"] = existing_effects
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "sublime prescience" or enh_id == "000010006002":
            if not is_rapid_evisceration:
                return
            unit.special_rules["enhancement_sublime_prescience"] = True
            unit.special_rules["enhancement_sublime_prescience_round_bonus"] = 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "spearhead striker" or enh_id == "000010006003":
            if not is_rapid_evisceration:
                return
            unit.special_rules["enhancement_spearhead_striker"] = True
            # Keep reroll conditional on disembark trigger; parser may set an unconditional flag.
            unit.special_rules.pop("enhancement_charge_reroll", None)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "accomplished tactician" or enh_id == "000010006004":
            if not is_rapid_evisceration:
                return
            unit.special_rules["enhancement_accomplished_tactician"] = True
            unit.special_rules["enhancement_accomplished_tactician_range"] = 9
            unit.special_rules["enhancement_accomplished_tactician_embark_range"] = 6
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "heretek adept" or enh_id == "000010006005":
            if not is_rapid_evisceration:
                return
            unit.special_rules["enhancement_heretek_adept"] = True
            unit.special_rules["enhancement_heretek_adept_range"] = 6
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "eager to prove" or enh_id == "000010018002":
            if not is_slaaneshs_chosen:
                return
            unit.special_rules["enhancement_eager_to_prove"] = True
            unit.special_rules["enhancement_charge_reroll"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            try:
                move_bonus = int(params.get("favoured_move_bonus", 2) or 2)
            except Exception:
                move_bonus = 2
            unit.special_rules["enhancement_eager_to_prove_favoured_move_bonus"] = int(max(0, move_bonus))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "repulsed by weakness" or enh_id == "000010018003":
            if not is_slaaneshs_chosen:
                return
            unit.special_rules["enhancement_repulsed_by_weakness"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            exclude_mv = bool(params.get("exclude_monsters_vehicles", True))
            try:
                favoured_penalty = int(params.get("favoured_desperate_escape_penalty", 1) or 1)
            except Exception:
                favoured_penalty = 1
            if exclude_mv:
                unit.special_rules["enhancement_repulsed_by_weakness_exclude_monster_vehicle"] = True
                # Keep the generic desperate-escape marker for existing movement hooks.
                unit.special_rules["enemy_fallback_desperate_escape_exclude_monster_vehicle"] = True
            unit.special_rules["enhancement_repulsed_by_weakness_favoured_penalty"] = int(max(0, favoured_penalty))
            # Keep the generic desperate-escape marker for existing movement hooks.
            unit.special_rules["enemy_fallback_desperate_escape"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "proud and vainglorious" or enh_id == "000010018004":
            if not is_slaaneshs_chosen:
                return
            unit.special_rules["enhancement_proud_and_vainglorious"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            try:
                oc_bonus = int(params.get("favoured_objective_control_bonus", 1) or 1)
            except Exception:
                oc_bonus = 1
            unit.special_rules["enhancement_proud_and_vainglorious_oc_bonus"] = int(max(0, oc_bonus))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "slayer of champions" or enh_id == "000010018005":
            if not is_slaaneshs_chosen:
                return
            unit.special_rules["enhancement_slayer_of_champions"] = True
            unit.special_rules["enhancement_bearer_melee_precision"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            try:
                s_bonus = int(params.get("character_target_strength_bonus", 1) or 1)
            except Exception:
                s_bonus = 1
            try:
                ap_bonus = int(params.get("character_target_ap_bonus", 1) or 1)
            except Exception:
                ap_bonus = 1
            unit.special_rules["enhancement_slayer_of_champions_character_strength_bonus"] = int(max(0, s_bonus))
            unit.special_rules["enhancement_slayer_of_champions_character_ap_bonus"] = int(max(0, ap_bonus))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "adaptive biology" or enh_id == "000008348005":
            unit.special_rules["enhancement_adaptive_biology"] = True
            _ensure_enhancement_fnp_entry(
                unit,
                5,
                source="Adaptive Biology",
                tag="adaptive_biology_base",
            )

        if name == "perfectly adapted" or enh_id == "000008348003":
            unit.special_rules["enhancement_perfectly_adapted"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "synaptic linchpin" or enh_id == "000008348004":
            unit.special_rules["enhancement_synaptic_linchpin"] = True
            unit.special_rules["enhancement_synaptic_linchpin_range"] = 9.0
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "synaptic strategy" or enh_id == "000010147002":
            if not is_subterranean_assault:
                return
            unit.special_rules["enhancement_synaptic_strategy"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source_name = str(getattr(desc, "name", "") or "Synaptic Strategy").strip() or "Synaptic Strategy"
            configured_stratagems = tuple(
                str(v or "").strip().upper()
                for v in tuple(params.get("stratagem_names", ("RAPID INGRESS",)) or ("RAPID INGRESS",))
                if str(v or "").strip()
            )
            if not configured_stratagems:
                configured_stratagems = ("RAPID INGRESS",)
            usage_key = str(params.get("usage_key", "synaptic_strategy_rapid_ingress") or "synaptic_strategy_rapid_ingress").strip().lower()
            if not usage_key:
                usage_key = "synaptic_strategy_rapid_ingress"
            unit.special_rules["enhancement_synaptic_strategy_source"] = source_name
            unit.special_rules["enhancement_synaptic_strategy_usage_key"] = usage_key
            unit.special_rules["enhancement_synaptic_strategy_stratagems"] = configured_stratagems
            unit.special_rules["enhancement_synaptic_strategy_repeat_bypass"] = bool(
                params.get("repeat_bypass", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_synaptic_strategy_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if name == "tremor senses" or enh_id == "000010147003":
            if not is_subterranean_assault:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Tremor Senses").strip() or "Tremor Senses"
            unit.special_rules["enhancement_tremor_senses"] = True
            unit.special_rules["enhancement_tremor_senses_source"] = source
            _register_enhancement_redeploy_spec(
                unit,
                source_name=source,
                source_model_id=bearer_id,
                max_units=_coerce_int(params.get("max_units", 3) or 3, default=3),
                can_place_in_reserves=bool(params.get("allow_strategic_reserves", True)),
                redeploy_filters=list(params.get("redeploy_filters", ("TYRANIDS",)) or ()),
                strategic_reserves_ignore_current_unit_count_limit=bool(
                    params.get("strategic_reserves_ignore_current_unit_count_limit", True)
                ),
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_tremor_senses_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if name == "vanguard intellect" or enh_id == "000010147004":
            if not is_subterranean_assault:
                return
            unit.special_rules["enhancement_vanguard_intellect"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_vanguard_intellect_source"] = (
                str(getattr(desc, "name", "") or "Vanguard Intellect").strip() or "Vanguard Intellect"
            )
            unit.special_rules["enhancement_vanguard_intellect_round_bonus"] = int(
                max(0, _coerce_int(params.get("strategic_reserves_setup_round_bonus", 1) or 1, default=1))
            )
            unit.special_rules["enhancement_vanguard_intellect_requires_deep_strike"] = bool(
                params.get("requires_deep_strike", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_vanguard_intellect_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if name == "trygon prime" or enh_id == "000010147005":
            if not is_subterranean_assault:
                return
            unit.special_rules["enhancement_trygon_prime"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source_name = str(getattr(desc, "name", "") or "Trygon Prime").strip() or "Trygon Prime"
            unit.special_rules["enhancement_trygon_prime_source"] = source_name
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(
                max(0, _coerce_int(params.get("strength_bonus", 1) or 1, default=1))
            )
            unit.special_rules["enhancement_bearer_melee_strength_bonus_source"] = source_name
            unit.special_rules["enhancement_bearer_melee_weapon_skill_bonus"] = int(
                max(0, _coerce_int(params.get("weapon_skill_bonus", 1) or 1, default=1))
            )
            unit.special_rules["enhancement_bearer_melee_weapon_skill_bonus_source"] = source_name
            _append_keyword_once(unit, "SYNAPSE")
            if bearer is not None:
                _append_keyword_once(bearer, "SYNAPSE")
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_trygon_prime_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if name == "power of the hive mind" or enh_id == "000008421002":
            if not is_synaptic_nexus:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source_name = str(getattr(desc, "name", "") or "Power of the Hive Mind").strip() or "Power of the Hive Mind"
            psychic_strength_bonus = int(max(0, _coerce_int(params.get("psychic_strength_bonus", 1) or 1, default=1)))
            psychic_ap_bonus = int(max(0, _coerce_int(params.get("psychic_ap_bonus", 1) or 1, default=1)))
            unit.special_rules["enhancement_power_of_the_hive_mind"] = True
            unit.special_rules["enhancement_power_of_the_hive_mind_source"] = source_name
            if psychic_strength_bonus:
                unit.special_rules["enhancement_bearer_psychic_strength_bonus"] = int(
                    unit.special_rules.get("enhancement_bearer_psychic_strength_bonus", 0) or 0
                ) + int(psychic_strength_bonus)
                unit.special_rules["enhancement_bearer_psychic_strength_bonus_source"] = source_name
            if psychic_ap_bonus:
                unit.special_rules["enhancement_bearer_psychic_ap_bonus"] = int(
                    unit.special_rules.get("enhancement_bearer_psychic_ap_bonus", 0) or 0
                ) + int(psychic_ap_bonus)
                unit.special_rules["enhancement_bearer_psychic_ap_bonus_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_power_of_the_hive_mind_bearer_model_id"] = bearer_id

        if name == "psychostatic disruption" or enh_id == "000008421003":
            if not is_synaptic_nexus:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source_name = (
                str(getattr(desc, "name", "") or "Psychostatic Disruption").strip() or "Psychostatic Disruption"
            )
            min_enemy_distance = float(
                max(
                    0.0,
                    _coerce_float(
                        params.get("min_enemy_distance", getattr(desc, "range_in", 12.0)) or 12.0,
                        default=12.0,
                    ),
                )
            )
            success_on = int(min(6, max(2, _coerce_int(params.get("success_on", 4) or 4, default=4))))
            raw_trigger_rounds = list(params.get("trigger_rounds", (1, 2)) or (1, 2))
            trigger_rounds: list[int] = []
            for round_value in raw_trigger_rounds:
                resolved_round = int(max(1, _coerce_int(round_value, default=0)))
                if resolved_round not in trigger_rounds:
                    trigger_rounds.append(resolved_round)
            once_key = str(
                params.get("once_per_battle_key", "psychostatic_disruption") or "psychostatic_disruption"
            ).strip().lower()
            if not once_key:
                once_key = "psychostatic_disruption"
            unit.special_rules["enhancement_psychostatic_disruption"] = True
            unit.special_rules["enhancement_psychostatic_disruption_source"] = source_name
            unit.special_rules["enhancement_psychostatic_disruption_min_enemy_distance"] = float(min_enemy_distance)
            unit.special_rules["enhancement_psychostatic_disruption_success_on"] = int(success_on)
            unit.special_rules["enhancement_psychostatic_disruption_trigger_rounds"] = list(trigger_rounds or [1, 2])
            unit.special_rules["enhancement_psychostatic_disruption_once_key"] = once_key
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_psychostatic_disruption_bearer_model_id"] = bearer_id

        if name in ("the dirgeheart of kharis aura", "the dirgeheart of kharis (aura)") or enh_id == "000008421005":
            if not is_synaptic_nexus:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source_name = (
                str(getattr(desc, "name", "") or "The Dirgeheart of Kharis (Aura)").strip()
                or "The Dirgeheart of Kharis (Aura)"
            )
            aura_range = float(
                max(
                    0.0,
                    _coerce_float(params.get("range", getattr(desc, "range_in", 9.0)) or 9.0, default=9.0),
                )
            )
            leadership_penalty = int(max(0, _coerce_int(params.get("leadership_penalty", 1) or 1, default=1)))
            unit.special_rules["enhancement_dirgeheart_of_kharis_aura"] = True
            unit.special_rules["enhancement_dirgeheart_of_kharis_aura_source"] = source_name
            unit.special_rules["enhancement_dirgeheart_of_kharis_aura_range"] = float(aura_range)
            unit.special_rules["enhancement_dirgeheart_of_kharis_aura_penalty"] = int(leadership_penalty)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_dirgeheart_of_kharis_bearer_model_id"] = bearer_id

        if name == "ominous presence" or enh_id == "000008404002":
            if not is_crusher_stampede:
                return
            unit.special_rules["enhancement_ominous_presence"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_ominous_presence_objective_control_bonus"] = int(
                max(0, _coerce_int(params.get("objective_control_bonus", 3) or 3, default=3))
            )
            unit.special_rules["enhancement_ominous_presence_source"] = (
                str(getattr(desc, "name", "") or "Ominous Presence").strip() or "Ominous Presence"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "enraged reserves" or enh_id == "000008404003":
            if not is_crusher_stampede:
                return
            unit.special_rules["enhancement_enraged_reserves"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_enraged_reserves_threshold"] = int(
                max(2, min(6, _coerce_int(params.get("success_on", 3) or 3, default=3)))
            )
            unit.special_rules["enhancement_enraged_reserves_source"] = (
                str(getattr(desc, "name", "") or "Enraged Reserves").strip() or "Enraged Reserves"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "null nodules" or enh_id == "000008404004":
            if not is_crusher_stampede:
                return
            unit.special_rules["enhancement_null_nodules"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_null_nodules_fnp_value"] = int(
                max(0, _coerce_int(params.get("feel_no_pain", 5) or 5, default=5))
            )
            unit.special_rules["enhancement_null_nodules_condition"] = (
                str(params.get("condition", "against psychic attacks") or "against psychic attacks").strip()
                or "against psychic attacks"
            )
            unit.special_rules["enhancement_null_nodules_once_per_battle_key"] = (
                str(params.get("once_per_battle_key", "null_nodules") or "null_nodules").strip().lower()
                or "null_nodules"
            )
            unit.special_rules["enhancement_null_nodules_source"] = (
                str(getattr(desc, "name", "") or "Null Nodules").strip() or "Null Nodules"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "monstrous nemesis" or enh_id == "000008404005":
            if not is_crusher_stampede:
                return
            unit.special_rules["enhancement_monstrous_nemesis"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_monstrous_nemesis_wound_bonus"] = int(
                max(0, _coerce_int(params.get("wound_bonus", 1) or 1, default=1))
            )
            unit.special_rules["enhancement_monstrous_nemesis_source"] = (
                str(getattr(desc, "name", "") or "Monstrous Nemesis").strip() or "Monstrous Nemesis"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "instinctive defence" or enh_id == "000008412003":
            if not is_assimilation_swarm:
                return
            unit.special_rules["enhancement_instinctive_defence"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                harvester_range = float(params.get("harvester_range", 6.0) or 6.0)
            except Exception:
                harvester_range = 6.0
            if harvester_range <= 0.0:
                harvester_range = 6.0
            source_name = str(getattr(desc, "name", "") or "Instinctive Defence").strip() or "Instinctive Defence"
            configured_stratagems = tuple(
                str(v or "").strip().upper()
                for v in tuple(params.get("stratagem_names", ("HEROIC INTERVENTION",)) or ("HEROIC INTERVENTION",))
                if str(v or "").strip()
            )
            if not configured_stratagems:
                configured_stratagems = ("HEROIC INTERVENTION",)
            unit.special_rules["enhancement_instinctive_defence_source"] = source_name
            unit.special_rules["enhancement_instinctive_defence_harvester_range"] = float(harvester_range)
            unit.special_rules["enhancement_instinctive_defence_required_keyword"] = str(
                params.get("required_friendly_keyword", "HARVESTER") or "HARVESTER"
            ).strip().upper() or "HARVESTER"
            unit.special_rules["enhancement_instinctive_defence_stratagems"] = configured_stratagems
            unit.special_rules["enhancement_instinctive_defence_grants_fights_first"] = bool(
                params.get("grants_fights_first", True)
            )
            unit.special_rules["enhancement_instinctive_defence_requires_bearer_on_battlefield"] = bool(
                params.get("requires_bearer_on_battlefield", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "parasitic biomorphology" or enh_id == "000008412005":
            if not is_assimilation_swarm:
                return
            unit.special_rules["enhancement_parasitic_biomorphology"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            strength_bonus = _coerce_int(params.get("melee_strength_bonus", 1) or 1, default=1)
            attacks_bonus = _coerce_int(params.get("melee_attacks_bonus", 1) or 1, default=1)
            try:
                harvester_range = float(params.get("harvester_range", 6.0) or 6.0)
            except Exception:
                harvester_range = 6.0
            if harvester_range <= 0.0:
                harvester_range = 6.0
            source_name = str(getattr(desc, "name", "") or "Parasitic Biomorphology").strip() or "Parasitic Biomorphology"
            unit.special_rules["enhancement_parasitic_biomorphology_source"] = source_name
            unit.special_rules["enhancement_parasitic_biomorphology_harvester_range"] = float(harvester_range)
            unit.special_rules["enhancement_parasitic_biomorphology_melee_strength_bonus"] = int(max(0, strength_bonus))
            unit.special_rules["enhancement_parasitic_biomorphology_melee_attacks_bonus"] = int(max(0, attacks_bonus))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "slaughterthirst (aura)" or enh_id == "000009815002":
            if not is_blood_legion:
                return
            unit.special_rules["enhancement_slaughterthirst_aura"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            range_val = params.get("range", getattr(desc, "range_in", 6.0) if desc is not None else 6.0)
            try:
                aura_range = float(range_val if range_val is not None else 6.0)
            except Exception:
                aura_range = 6.0
            unit.special_rules["enhancement_slaughterthirst_aura_range"] = float(max(0.0, aura_range))
            unit.special_rules["enhancement_slaughterthirst_aura_source"] = "Slaughterthirst (Aura)"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "fury's cage" or enh_id == "000009815003":
            if not is_blood_legion:
                return
            unit.special_rules["enhancement_furys_cage"] = True
            unit.special_rules["enhancement_furys_cage_source"] = "Fury's Cage"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "brazenmaw" or enh_id == "000009815004":
            if not is_blood_legion:
                return
            unit.special_rules["enhancement_brazenmaw"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            bonus = _coerce_int(params.get("charge_roll_bonus", 2) or 2, default=2)
            bonus = int(max(0, bonus))
            if bonus:
                mods = list(unit.special_rules.get("charge_roll_modifiers", []) or [])
                tag = "enhancement:brazenmaw"
                exists = False
                for item in mods:
                    if isinstance(item, dict) and str(item.get("tag", "") or "") == tag:
                        exists = True
                        break
                if not exists:
                    mods.append(
                        {
                            "value": int(bonus),
                            "source": "Brazenmaw",
                            "tag": tag,
                        }
                    )
                unit.special_rules["charge_roll_modifiers"] = mods
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "gateway unto damnation" or enh_id == "000009815005":
            if not is_blood_legion:
                return
            unit.special_rules["enhancement_gateway_unto_damnation"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            trigger_threshold = _coerce_int(params.get("success_on", 2) or 2, default=2)
            damage_dice = str(params.get("base_damage_after_kill", "") or "D3+3").strip().upper() or "D3+3"
            unit.special_rules["enhancement_gateway_unto_damnation_trigger_threshold"] = int(
                max(2, min(6, trigger_threshold))
            )
            unit.special_rules["enhancement_gateway_unto_damnation_damage_dice"] = damage_dice
            unit.special_rules["enhancement_gateway_unto_damnation_source"] = "Gateway Unto Damnation"
            if "enhancement_gateway_unto_damnation_destroyed_enemy_units_this_battle" not in unit.special_rules:
                unit.special_rules["enhancement_gateway_unto_damnation_destroyed_enemy_units_this_battle"] = 0
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "leaping shadows" or enh_id == "000009980002":
            if not is_shadow_legion:
                return
            unit.special_rules["enhancement_leaping_shadows"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            scout_distance = _coerce_int(params.get("scouts_distance", 9) or 9, default=9)
            unit.special_rules["enhancement_scout_distance"] = max(
                int(unit.special_rules.get("enhancement_scout_distance", 0) or 0),
                int(max(0, scout_distance)),
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "mantle of gloom (aura)" or enh_id == "000009980003":
            if not is_shadow_legion:
                return
            unit.special_rules["enhancement_mantle_of_gloom"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            penalty = _coerce_int(params.get("objective_control_penalty", 1) or 1, default=1)
            unit.special_rules["enhancement_mantle_of_gloom_oc_penalty"] = int(max(0, penalty))
            unit.special_rules["enhancement_mantle_of_gloom_source"] = "Mantle of Gloom (Aura)"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "fade to darkness" or enh_id == "000009980004":
            if not is_shadow_legion:
                return
            unit.special_rules["enhancement_fade_to_darkness"] = True
            unit.special_rules["enhancement_fade_to_darkness_source"] = "Fade to Darkness"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("fight_phase_destroyed_strategic_reserves_ability", None)

        if name == "malice made manifest" or enh_id == "000009980005":
            if not is_shadow_legion:
                return
            unit.special_rules["enhancement_malice_made_manifest"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            low_min = _coerce_int(params.get("threshold_mid_min", 2) or 2, default=2)
            low_max = _coerce_int(params.get("threshold_mid_max", 5) or 5, default=5)
            high_threshold = _coerce_int(params.get("threshold_high", 6) or 6, default=6)
            mortal_mid = str(params.get("mortal_mid", "D3") or "D3").strip().upper() or "D3"
            high_raw = params.get("mortal_high", 3)
            mortal_high = _coerce_int(high_raw, default=3)
            unit.special_rules["enhancement_malice_made_manifest_low_min"] = int(max(0, low_min))
            unit.special_rules["enhancement_malice_made_manifest_low_max"] = int(max(0, low_max))
            unit.special_rules["enhancement_malice_made_manifest_high_threshold"] = int(max(0, high_threshold))
            unit.special_rules["enhancement_malice_made_manifest_mortal_mid"] = mortal_mid
            unit.special_rules["enhancement_malice_made_manifest_mortal_high"] = int(max(0, mortal_high))
            unit.special_rules["enhancement_malice_made_manifest_source"] = "Malice Made Manifest"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "false majesty (aura)" or enh_id == "000009806002":
            if not is_legion_of_excess:
                return
            unit.special_rules["enhancement_false_majesty_aura"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            range_val = params.get("range", getattr(desc, "range_in", 6.0) if desc is not None else 6.0)
            try:
                aura_range = float(range_val if range_val is not None else 6.0)
            except Exception:
                aura_range = 6.0
            unit.special_rules["enhancement_false_majesty_aura_range"] = float(max(0.0, aura_range))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "dreaming crown (aura)" or enh_id == "000009806003":
            if not is_legion_of_excess:
                return
            unit.special_rules["enhancement_dreaming_crown_aura"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            range_val = params.get("range", getattr(desc, "range_in", 6.0) if desc is not None else 6.0)
            try:
                aura_range = float(range_val if range_val is not None else 6.0)
            except Exception:
                aura_range = 6.0
            unit.special_rules["enhancement_dreaming_crown_aura_range"] = float(max(0.0, aura_range))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "avatar of perfection" or enh_id == "000009806004":
            if not is_legion_of_excess:
                return
            unit.special_rules["enhancement_avatar_of_perfection"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            range_val = params.get("isolation_range", getattr(desc, "range_in", 6.0) if desc is not None else 6.0)
            try:
                isolation_range = float(range_val if range_val is not None else 6.0)
            except Exception:
                isolation_range = 6.0
            unit.special_rules["enhancement_avatar_of_perfection_range"] = float(max(0.0, isolation_range))
            unit.special_rules["enhancement_avatar_of_perfection_reroll_advance"] = bool(
                params.get("reroll_advance", True)
            )
            unit.special_rules["enhancement_avatar_of_perfection_reroll_charge"] = bool(
                params.get("reroll_charge", True)
            )
            unit.special_rules["enhancement_avatar_of_perfection_ignore_move_modifiers"] = bool(
                params.get("ignore_move_modifiers", True)
            )
            unit.special_rules["enhancement_avatar_of_perfection_ignore_advance_modifiers"] = bool(
                params.get("ignore_advance_modifiers", True)
            )
            unit.special_rules["enhancement_avatar_of_perfection_ignore_charge_modifiers"] = bool(
                params.get("ignore_charge_modifiers", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "soul glutton" or enh_id == "000009806005":
            if not is_legion_of_excess:
                return
            unit.special_rules["enhancement_soul_glutton"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "a'rgath, the king of blades" or enh_id == "000008438002":
            if not is_daemonic_incursion:
                return
            unit.special_rules["enhancement_argath_king_of_blades"] = True
            unit.special_rules["enhancement_bearer_melee_attacks_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_attacks_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_melee_attacks_bonus_shadow_extra"] = int(
                unit.special_rules.get("enhancement_bearer_melee_attacks_bonus_shadow_extra", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_melee_strength_bonus_shadow_extra"] = int(
                unit.special_rules.get("enhancement_bearer_melee_strength_bonus_shadow_extra", 0) or 0
            ) + 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "soulstealer" or enh_id == "000008438003":
            if not is_daemonic_incursion:
                return
            unit.special_rules["enhancement_soulstealer"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "the endless gift" or enh_id == "000008438004":
            if not is_daemonic_incursion:
                return
            unit.special_rules["enhancement_endless_gift"] = True

        if name == "the everstave" or enh_id == "000008438005":
            if not is_daemonic_incursion:
                return
            unit.special_rules["enhancement_everstave"] = True
            unit.special_rules["enhancement_bearer_ranged_strength_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_ranged_strength_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_ranged_range_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_ranged_range_bonus", 0) or 0
            ) + 3
            unit.special_rules["enhancement_bearer_ranged_strength_bonus_shadow_extra"] = int(
                unit.special_rules.get("enhancement_bearer_ranged_strength_bonus_shadow_extra", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_ranged_range_bonus_shadow_extra"] = int(
                unit.special_rules.get("enhancement_bearer_ranged_range_bonus_shadow_extra", 0) or 0
            ) + 3
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "cankerblight" or enh_id == "000009819002":
            if not is_plague_legion:
                return
            unit.special_rules["enhancement_cankerblight"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "maggot maws" or enh_id == "000009819003":
            if not is_plague_legion:
                return
            unit.special_rules["enhancement_maggot_maws"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "droning shroud (aura)" or enh_id == "000009819004":
            if not is_plague_legion:
                return
            unit.special_rules["enhancement_droning_shroud_aura"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            range_val = params.get("range", getattr(desc, "range_in", 6.0) if desc is not None else 6.0)
            try:
                aura_range = float(range_val if range_val is not None else 6.0)
            except Exception:
                aura_range = 6.0
            try:
                targeting_cap = float(params.get("ranged_targeting_max_distance", 18) or 18)
            except Exception:
                targeting_cap = 18.0
            unit.special_rules["enhancement_droning_shroud_aura_range"] = float(max(0.0, aura_range))
            unit.special_rules["enhancement_droning_shroud_targeting_cap"] = float(max(0.0, targeting_cap))
            unit.special_rules["enhancement_droning_shroud_aura_source"] = "Droning Shroud (Aura)"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "font of spores (aura)" or enh_id == "000009819005":
            if not is_plague_legion:
                return
            unit.special_rules["enhancement_font_of_spores_aura"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            range_val = params.get("range", getattr(desc, "range_in", 6.0) if desc is not None else 6.0)
            try:
                aura_range = float(range_val if range_val is not None else 6.0)
            except Exception:
                aura_range = 6.0
            try:
                ap_bonus = int(params.get("ap_bonus", 1) or 1)
            except Exception:
                ap_bonus = 1
            unit.special_rules["enhancement_font_of_spores_aura_range"] = float(max(0.0, aura_range))
            unit.special_rules["enhancement_font_of_spores_aura_ap_bonus"] = int(max(0, ap_bonus))
            unit.special_rules["enhancement_font_of_spores_aura_source"] = "Font of Spores (Aura)"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "inescapable eye" or enh_id == "000009810002":
            if not is_scintillating_legion:
                return
            unit.special_rules["enhancement_inescapable_eye"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "infernal puppeteer" or enh_id == "000009810003":
            if not is_scintillating_legion:
                return
            unit.special_rules["enhancement_infernal_puppeteer"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "neverblade" or enh_id == "000009810004":
            if not is_scintillating_legion:
                return
            unit.special_rules["enhancement_neverblade"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = getattr(desc, "effect_params", {}) if desc is not None else {}
            except Exception:
                params = {}
            try:
                s_bonus = int(params.get("strength_bonus", 2) or 2)
            except Exception:
                s_bonus = 2
            try:
                a_bonus = int(params.get("attacks_bonus", 1) or 1)
            except Exception:
                a_bonus = 1
            try:
                ap_bonus = int(params.get("ap_bonus", 1) or 1)
            except Exception:
                ap_bonus = 1
            try:
                hit_bonus = int(params.get("hit_bonus", 1) or 1)
            except Exception:
                hit_bonus = 1
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0) or 0
            ) + s_bonus
            unit.special_rules["enhancement_bearer_melee_attacks_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_attacks_bonus", 0) or 0
            ) + a_bonus
            unit.special_rules["enhancement_bearer_melee_ap_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_ap_bonus", 0) or 0
            ) + ap_bonus
            unit.special_rules["enhancement_bearer_melee_hit_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_hit_bonus", 0) or 0
            ) + hit_bonus
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "improbable shield (aura)" or enh_id == "000009810005":
            if not is_scintillating_legion:
                return
            unit.special_rules["enhancement_improbable_shield"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "final ingredient" or enh_id == "000010131002":
            if not is_champions_of_contagion:
                return
            unit.special_rules["enhancement_final_ingredient"] = True
            unit.special_rules["enhancement_final_ingredient_source"] = "Final Ingredient"
            unit.special_rules["enhancement_final_ingredient_once_key"] = "final_ingredient"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_final_ingredient_bearer_model_id"] = bearer_id

        if name == "visions of virulence" or enh_id == "000010131003":
            if not is_champions_of_contagion:
                return
            unit.special_rules["enhancement_visions_of_virulence"] = True
            unit.special_rules["enhancement_visions_of_virulence_source"] = "Visions of Virulence"
            unit.special_rules["enhancement_visions_of_virulence_required_source_name"] = "Pestilent Fallout"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_visions_of_virulence_bearer_model_id"] = bearer_id

        if name == "needle of nurgle" or enh_id == "000010131004":
            if not is_champions_of_contagion:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            amount_roll = str(params.get("command_phase_bodyguard_return_amount_roll", "D3") or "D3").strip().upper()
            max_return = _coerce_int(params.get("command_phase_bodyguard_return_max", 3) or 3, default=3)
            ability_key = str(params.get("ability_key", "needle_of_nurgle") or "needle_of_nurgle").strip().lower()
            requires_leading = bool(params.get("requires_bearer_leading", True))
            unit.special_rules["enhancement_needle_of_nurgle"] = True
            unit.special_rules["enhancement_needle_of_nurgle_source"] = "Needle of Nurgle"
            unit.special_rules["enhancement_needle_of_nurgle_command_phase_return_amount_roll"] = (
                amount_roll if amount_roll else "D3"
            )
            unit.special_rules["enhancement_needle_of_nurgle_command_phase_return_max"] = int(max(1, int(max_return)))
            unit.special_rules["enhancement_needle_of_nurgle_requires_bearer_leading"] = bool(requires_leading)
            unit.special_rules["enhancement_needle_of_nurgle_ability_key"] = (
                ability_key if ability_key else "needle_of_nurgle"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_needle_of_nurgle_bearer_model_id"] = bearer_id

        if name == "cornucophagus" or enh_id == "000010131005":
            if not is_champions_of_contagion:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source_name = str(params.get("source_name", "Cornucophagus") or "Cornucophagus").strip()
            if not source_name:
                source_name = "Cornucophagus"
            unit.special_rules["enhancement_cornucophagus"] = True
            unit.special_rules["enhancement_cornucophagus_source"] = source_name
            unit.special_rules["enhancement_cornucophagus_requires_contagion_range"] = bool(
                params.get("requires_contagion_range", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_cornucophagus_bearer_model_id"] = bearer_id

        if name == "face of death" or enh_id == "000010143002":
            if not is_death_lords_chosen:
                return
            unit.special_rules["enhancement_face_of_death"] = True
            unit.special_rules["enhancement_face_of_death_source"] = "Face of Death"
            unit.special_rules["enhancement_face_of_death_requires_bearer_alive"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_face_of_death_bearer_model_id"] = bearer_id

        if name == "vile vigour" or enh_id == "000010143003":
            if not is_death_lords_chosen:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_vile_vigour"] = True
            unit.special_rules["enhancement_vile_vigour_source"] = "Vile Vigour"
            unit.special_rules["enhancement_vile_vigour_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_vile_vigour_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            unit.special_rules["enhancement_vile_vigour_reroll_advance"] = bool(
                params.get("reroll_advance_roll", True)
            )
            unit.special_rules["enhancement_vile_vigour_move_bonus"] = int(
                max(0, _coerce_int(params.get("movement_bonus", 1) or 1, default=1))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_vile_vigour_bearer_model_id"] = bearer_id

        if name == "warprot talisman" or enh_id == "000010143004":
            if not is_death_lords_chosen:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            ability_key = str(params.get("ability_key", "warprot_talisman") or "warprot_talisman").strip().lower()
            if not ability_key:
                ability_key = "warprot_talisman"
            unit.special_rules["enhancement_warprot_talisman"] = True
            unit.special_rules["enhancement_warprot_talisman_source"] = "Warprot Talisman"
            unit.special_rules["enhancement_warprot_talisman_once_per_battle"] = bool(
                params.get("once_per_battle", True)
            )
            unit.special_rules["enhancement_warprot_talisman_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_warprot_talisman_trigger_phase"] = str(
                params.get("trigger_phase", "OPPONENT_TURN_END") or "OPPONENT_TURN_END"
            ).strip().upper()
            unit.special_rules["enhancement_warprot_talisman_ability_key"] = ability_key
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_warprot_talisman_bearer_model_id"] = bearer_id
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("opponent_turn_strategic_reserves_ability", None)

        if name == "helm of the fly king" or enh_id == "000010143005":
            if not is_death_lords_chosen:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_helm_of_the_fly_king"] = True
            unit.special_rules["enhancement_helm_of_the_fly_king_source"] = "Helm of the Fly King"
            unit.special_rules["enhancement_helm_of_the_fly_king_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_helm_of_the_fly_king_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            unit.special_rules["enhancement_helm_of_the_fly_king_ranged_targeting_max_distance"] = float(
                max(0.0, _coerce_float(params.get("ranged_targeting_max_distance", 18.0), default=18.0))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_helm_of_the_fly_king_bearer_model_id"] = bearer_id

        if name == "droning chorus" or enh_id == "000009729002":
            if not is_flyblown_host:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_droning_chorus"] = True
            unit.special_rules["enhancement_droning_chorus_source"] = "Droning Chorus"
            unit.special_rules["enhancement_droning_chorus_assault_ranged"] = bool(params.get("assault_ranged", True))
            unit.special_rules["enhancement_droning_chorus_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_droning_chorus_bearer_model_id"] = bearer_id

        if name == "insectile murmuration" or enh_id == "000009729003":
            if not is_flyblown_host:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_insectile_murmuration"] = True
            unit.special_rules["enhancement_insectile_murmuration_source"] = "Insectile Murmuration"
            unit.special_rules["enhancement_insectile_murmuration_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_insectile_murmuration_requires_target_within_friendly_contagion_range"] = bool(
                params.get("requires_target_within_friendly_contagion_range", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_insectile_murmuration_bearer_model_id"] = bearer_id

        if name == "rejuvenating swarm" or enh_id == "000009729004":
            if not is_flyblown_host:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_rejuvenating_swarm"] = True
            unit.special_rules["enhancement_rejuvenating_swarm_source"] = "Rejuvenating Swarm"
            unit.special_rules["enhancement_rejuvenating_swarm_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_rejuvenating_swarm_regain_all_lost_wounds"] = bool(
                params.get("regain_all_lost_wounds", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_rejuvenating_swarm_bearer_model_id"] = bearer_id

        if name == "plagueveil" or enh_id == "000009729005":
            if not is_flyblown_host:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_plagueveil"] = True
            unit.special_rules["enhancement_plagueveil_source"] = "Plagueveil"
            unit.special_rules["enhancement_plagueveil_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_plagueveil_requires_within_controlled_objective_range"] = bool(
                params.get("requires_within_controlled_objective_range", True)
            )
            unit.special_rules["enhancement_plagueveil_ranged_targeting_max_distance"] = float(
                max(0.0, _coerce_float(params.get("ranged_targeting_max_distance", 18.0), default=18.0))
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_plagueveil_bearer_model_id"] = bearer_id

        if name == "eye of affliction" or enh_id == "000010127002":
            if not is_mortarions_hammer:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_eye_of_affliction"] = True
            unit.special_rules["enhancement_eye_of_affliction_source"] = "Eye of Affliction"
            unit.special_rules["enhancement_eye_of_affliction_requires_target_afflicted"] = bool(
                params.get("requires_target_afflicted", True)
            )
            unit.special_rules["enhancement_eye_of_affliction_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_eye_of_affliction_bearer_model_id"] = bearer_id

        if name == "bilemaw blight" or enh_id == "000010127003":
            if not is_mortarions_hammer:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_bilemaw_blight"] = True
            unit.special_rules["enhancement_bilemaw_blight_source"] = "Bilemaw Blight"
            unit.special_rules["enhancement_bilemaw_blight_weapon_name"] = str(
                params.get("weapon_name", "Plague Wind") or "Plague Wind"
            ).strip() or "Plague Wind"
            unit.special_rules["enhancement_bilemaw_blight_range_bonus"] = int(
                max(0, _coerce_int(params.get("range_bonus", 12) or 12, default=12))
            )
            unit.special_rules["enhancement_bilemaw_blight_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_bilemaw_blight_bearer_model_id"] = bearer_id

        if name == "shriekworm familiar" or enh_id == "000010127004":
            if not is_mortarions_hammer:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_shriekworm_familiar"] = True
            unit.special_rules["enhancement_shriekworm_familiar_source"] = "Shriekworm Familiar"
            unit.special_rules["enhancement_shriekworm_familiar_once_per_battle_round"] = bool(
                params.get("once_per_battle_round", True)
            )
            stratagem_names = [
                str(v or "").strip().upper()
                for v in list(params.get("stratagem_names", ["OVERWATCH", "FIRE OVERWATCH"]) or [])
                if str(v or "").strip()
            ]
            if stratagem_names:
                unit.special_rules["enhancement_shriekworm_familiar_stratagem_names"] = list(stratagem_names)
            unit.special_rules["enhancement_shriekworm_familiar_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_shriekworm_familiar_bearer_model_id"] = bearer_id
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("shriekworm_familiar_overwatch_rule", None)

        if name == "tendrilous emissions" or enh_id == "000010127005":
            if not is_mortarions_hammer:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_tendrilous_emissions"] = True
            unit.special_rules["enhancement_tendrilous_emissions_source"] = "Tendrilous Emissions"
            unit.special_rules["enhancement_tendrilous_emissions_vehicle_aura_range"] = float(
                max(0.0, _coerce_float(params.get("vehicle_aura_range", 3.0), default=3.0))
            )
            unit.special_rules["enhancement_tendrilous_emissions_grant_lone_operative_to_bearer"] = bool(
                params.get("grant_lone_operative_to_bearer", True)
            )
            unit.special_rules["enhancement_tendrilous_emissions_vehicle_reroll_wound_ones"] = bool(
                params.get("vehicle_reroll_wound_ones", True)
            )
            unit.special_rules["enhancement_tendrilous_emissions_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_tendrilous_emissions_bearer_model_id"] = bearer_id

        if name == "beckoning blight" or enh_id == "000010135002":
            if not is_tallyband_summoners:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_beckoning_blight"] = True
            unit.special_rules["enhancement_beckoning_blight_source"] = "Beckoning Blight"
            unit.special_rules["enhancement_beckoning_blight_bearer_range"] = float(
                max(0.0, _coerce_float(params.get("bearer_range", 12.0) or 12.0, default=12.0))
            )
            unit.special_rules["enhancement_beckoning_blight_min_enemy_distance"] = float(
                max(0.0, _coerce_float(params.get("min_enemy_distance", 6.0) or 6.0, default=6.0))
            )
            unit.special_rules["enhancement_beckoning_blight_requires_unit_keyword"] = str(
                params.get("requires_unit_keyword", "PLAGUE LEGIONS") or "PLAGUE LEGIONS"
            ).strip().upper() or "PLAGUE LEGIONS"
            unit.special_rules["enhancement_beckoning_blight_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_beckoning_blight_bearer_model_id"] = bearer_id

        if name == "fell harvester" or enh_id == "000010135003":
            if not is_tallyband_summoners:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_fell_harvester"] = True
            unit.special_rules["enhancement_fell_harvester_source"] = "Fell Harvester"
            attacks_bonus = int(max(0, _coerce_int(params.get("melee_attacks_bonus", 2) or 2, default=2)))
            unit.special_rules["enhancement_bearer_melee_attacks_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_attacks_bonus", 0) or 0
            ) + int(attacks_bonus)
            unit.special_rules["enhancement_fell_harvester_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_fell_harvester_bearer_model_id"] = bearer_id

        if name == "entropic knell" or enh_id == "000010135004":
            if not is_tallyband_summoners:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_entropic_knell"] = True
            unit.special_rules["enhancement_entropic_knell_source"] = "Entropic Knell"
            unit.special_rules["enhancement_entropic_knell_range"] = float(
                max(0.0, _coerce_float(params.get("range", 6.0) or 6.0, default=6.0))
            )
            unit.special_rules["enhancement_entropic_knell_battle_shock_test_modifier"] = int(
                _coerce_int(params.get("battle_shock_test_modifier", -1) or -1, default=-1)
            )
            unit.special_rules["enhancement_entropic_knell_requires_target_below_starting_strength"] = bool(
                params.get("requires_target_below_starting_strength", True)
            )
            unit.special_rules["enhancement_entropic_knell_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_entropic_knell_bearer_model_id"] = bearer_id

        if name == "tome of bounteous blessings" or enh_id == "000010135005":
            if not is_tallyband_summoners:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_tome_of_bounteous_blessings"] = True
            unit.special_rules["enhancement_tome_of_bounteous_blessings_source"] = "Tome of Bounteous Blessings"
            unit.special_rules["enhancement_tome_of_bounteous_blessings_range"] = float(
                max(0.0, _coerce_float(params.get("range", 12.0) or 12.0, default=12.0))
            )
            unit.special_rules["enhancement_tome_of_bounteous_blessings_battle_shock_test_modifier"] = int(
                _coerce_int(params.get("battle_shock_test_modifier", 1) or 1, default=1)
            )
            unit.special_rules["enhancement_tome_of_bounteous_blessings_restore_die"] = str(
                params.get("restore_die", "D3") or "D3"
            ).strip().upper() or "D3"
            unit.special_rules["enhancement_tome_of_bounteous_blessings_requires_target_keyword"] = str(
                params.get("requires_target_keyword", "PLAGUE LEGIONS") or "PLAGUE LEGIONS"
            ).strip().upper() or "PLAGUE LEGIONS"
            unit.special_rules["enhancement_tome_of_bounteous_blessings_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_tome_of_bounteous_blessings_bearer_model_id"] = bearer_id

        if name == "witherbone pipes" or enh_id == "000010139002":
            if not is_shamblerot_vectorium:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_witherbone_pipes"] = True
            unit.special_rules["enhancement_witherbone_pipes_source"] = "Witherbone Pipes"
            unit.special_rules["enhancement_witherbone_pipes_objective_control_bonus"] = int(
                max(0, _coerce_int(params.get("objective_control_bonus", 1) or 1, default=1))
            )
            unit.special_rules["enhancement_witherbone_pipes_leadership_test_modifier"] = int(
                _coerce_int(params.get("leadership_test_modifier", 1) or 1, default=1)
            )
            unit.special_rules["enhancement_witherbone_pipes_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_witherbone_pipes_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            unit.special_rules["enhancement_witherbone_pipes_requires_led_unit_name"] = str(
                params.get("requires_led_unit_name", "Poxwalkers") or "Poxwalkers"
            ).strip() or "Poxwalkers"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_witherbone_pipes_bearer_model_id"] = bearer_id

        if name == "lord of the walking pox" or enh_id == "000010139003":
            if not is_shamblerot_vectorium:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_lord_of_the_walking_pox"] = True
            unit.special_rules["enhancement_lord_of_the_walking_pox_source"] = "Lord of the Walking Pox"
            unit.special_rules["enhancement_lord_of_the_walking_pox_strategic_reserves_setup_treat_as_round"] = int(
                max(1, _coerce_int(params.get("strategic_reserves_setup_treat_as_round", 3) or 3, default=3))
            )
            unit.special_rules["enhancement_lord_of_the_walking_pox_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_lord_of_the_walking_pox_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            unit.special_rules["enhancement_lord_of_the_walking_pox_requires_led_unit_name"] = str(
                params.get("requires_led_unit_name", "Poxwalkers") or "Poxwalkers"
            ).strip() or "Poxwalkers"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_lord_of_the_walking_pox_bearer_model_id"] = bearer_id

        if name == "sorrowsyphon" or enh_id == "000010139004":
            if not is_shamblerot_vectorium:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_sorrowsyphon"] = True
            unit.special_rules["enhancement_sorrowsyphon_source"] = "Sorrowsyphon"
            unit.special_rules["enhancement_sorrowsyphon_weapon_name"] = str(
                params.get("weapon_name", "Plague Wind") or "Plague Wind"
            ).strip() or "Plague Wind"
            unit.special_rules["enhancement_sorrowsyphon_plague_wind_damage_bonus"] = int(
                max(0, _coerce_int(params.get("plague_wind_damage_bonus", 1) or 1, default=1))
            )
            unit.special_rules["enhancement_sorrowsyphon_bodyguard_loss_die"] = str(
                params.get("bodyguard_loss_die", "D3") or "D3"
            ).strip().upper() or "D3"
            unit.special_rules["enhancement_sorrowsyphon_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_sorrowsyphon_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            unit.special_rules["enhancement_sorrowsyphon_requires_led_unit_name"] = str(
                params.get("requires_led_unit_name", "Poxwalkers") or "Poxwalkers"
            ).strip() or "Poxwalkers"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_sorrowsyphon_bearer_model_id"] = bearer_id

        if name == "talisman of burgeoning" or enh_id == "000010139005":
            if not is_shamblerot_vectorium:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_talisman_of_burgeoning"] = True
            unit.special_rules["enhancement_talisman_of_burgeoning_source"] = "Talisman of Burgeoning"
            unit.special_rules["enhancement_talisman_of_burgeoning_toughness_bonus"] = int(
                max(0, _coerce_int(params.get("toughness_bonus", 1) or 1, default=1))
            )
            unit.special_rules["enhancement_talisman_of_burgeoning_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_talisman_of_burgeoning_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            unit.special_rules["enhancement_talisman_of_burgeoning_requires_led_unit_name"] = str(
                params.get("requires_led_unit_name", "Poxwalkers") or "Poxwalkers"
            ).strip() or "Poxwalkers"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_talisman_of_burgeoning_bearer_model_id"] = bearer_id

        if name == "daemon weapon of nurgle" or enh_id == "000010123002":
            if not is_virulent_vectorium:
                return
            unit.special_rules["enhancement_daemon_weapon_of_nurgle"] = True

        if name == "furnace of plagues" or enh_id == "000010123003":
            if not is_virulent_vectorium:
                return
            unit.special_rules["enhancement_melee_strength_bonus"] = int(
                unit.special_rules.get("enhancement_melee_strength_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_melee_attacks_bonus"] = int(
                unit.special_rules.get("enhancement_melee_attacks_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_furnace_of_plagues"] = True

        if name == "arch contaminator" or enh_id == "000010123004":
            if not is_virulent_vectorium:
                return
            unit.special_rules["enhancement_arch_contaminator"] = True

        if name == "revolting regeneration" or enh_id == "000010123005":
            if not is_virulent_vectorium:
                return
            unit.special_rules["enhancement_revolting_regeneration"] = True
            _ensure_enhancement_fnp_entry(
                unit,
                5,
                source="Revolting Regeneration",
                tag="revolting_regeneration",
            )

        if name == "blade imperator" or enh_id == "000008930002":
            if not is_auric_champions:
                return
            unit.special_rules["enhancement_blade_imperator"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            threshold = _coerce_int(params.get("roll_threshold", 4) or 4, default=4)
            mw_die = str(params.get("mortal_wounds_die", "D3") or "D3").strip().upper() or "D3"
            trigger_range = _coerce_int(params.get("battleshock_range", 6) or 6, default=6)
            charge_once_key = str(
                params.get("charge_mortal_once_per_battle_key", "blade_imperator_charge_mortal")
                or "blade_imperator_charge_mortal"
            ).strip().lower()
            if not charge_once_key:
                charge_once_key = "blade_imperator_charge_mortal"
            battleshock_once_key = str(
                params.get("battleshock_once_per_battle_key", "blade_imperator_battleshock")
                or "blade_imperator_battleshock"
            ).strip().lower()
            if not battleshock_once_key:
                battleshock_once_key = "blade_imperator_battleshock"
            unit.special_rules["enhancement_blade_imperator_roll_threshold"] = int(max(2, min(6, threshold)))
            unit.special_rules["enhancement_blade_imperator_mortal_wounds_die"] = mw_die
            unit.special_rules["enhancement_blade_imperator_battleshock_range"] = int(max(1, trigger_range))
            unit.special_rules["enhancement_blade_imperator_charge_mortal_once_key"] = charge_once_key
            unit.special_rules["enhancement_blade_imperator_battleshock_once_key"] = battleshock_once_key
            unit.special_rules["enhancement_blade_imperator_source"] = "Blade Imperator"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_blade_imperator_bearer_model_id"] = bearer_id
            refresh_charge_end = getattr(unit, "_refresh_charge_end_mortal_wounds_flags", None)
            if callable(refresh_charge_end):
                refresh_charge_end()

        if name == "inspirational exemplar" or enh_id == "000008930003":
            if not is_auric_champions:
                return
            unit.special_rules["enhancement_inspirational_exemplar"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            range_inches = _coerce_int(params.get("range", 12) or 12, default=12)
            once_key = str(
                params.get("once_per_battle_key", "inspirational_exemplar")
                or "inspirational_exemplar"
            ).strip().lower()
            if not once_key:
                once_key = "inspirational_exemplar"
            keyword_phrase = str(params.get("keyword_phrase", "ADEPTUS CUSTODES") or "ADEPTUS CUSTODES").strip()
            if not keyword_phrase:
                keyword_phrase = "ADEPTUS CUSTODES"
            unit.special_rules["enhancement_inspirational_exemplar_range"] = int(max(1, range_inches))
            unit.special_rules["enhancement_inspirational_exemplar_keyword_phrase"] = keyword_phrase
            unit.special_rules["enhancement_inspirational_exemplar_once_key"] = once_key
            unit.special_rules["enhancement_inspirational_exemplar_source"] = "Inspirational Exemplar"
            unit.special_rules["enhancement_inspirational_exemplar_bearer_leadership"] = 5
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_inspirational_exemplar_bearer_model_id"] = bearer_id
            if bearer is not None:
                bearer.leadership = int(
                    unit.special_rules.get("enhancement_inspirational_exemplar_bearer_leadership", 5) or 5
                )
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("unit_start_any_phase_clear_battleshock_specs", None)

        if name == "martial philosopher" or enh_id == "000008930004":
            if not is_auric_champions:
                return
            unit.special_rules["enhancement_martial_philosopher"] = True
            unit.special_rules["enhancement_martial_philosopher_shoot_after_fall_back"] = True
            unit.special_rules["enhancement_martial_philosopher_charge_after_fall_back"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            trigger_range = _coerce_int(params.get("trigger_range", 9) or 9, default=9)
            max_distance = _coerce_int(params.get("max_distance", 6) or 6, default=6)
            once_key = str(
                params.get("once_per_battle_key", "martial_philosopher")
                or "martial_philosopher"
            ).strip().lower()
            if not once_key:
                once_key = "martial_philosopher"
            trigger_actions = [
                str(v or "").strip().lower()
                for v in list(params.get("trigger_actions", ("move", "advance", "fall_back")) or ())
                if str(v or "").strip()
            ]
            if not trigger_actions:
                trigger_actions = ["move", "advance", "fall_back"]
            unit.special_rules["enhancement_martial_philosopher_trigger_range"] = int(max(1, trigger_range))
            unit.special_rules["enhancement_martial_philosopher_max_reactive_move_distance"] = int(max(1, max_distance))
            unit.special_rules["enhancement_martial_philosopher_trigger_actions"] = list(dict.fromkeys(trigger_actions))
            unit.special_rules["enhancement_martial_philosopher_requires_not_engaged"] = bool(
                params.get("requires_not_engaged", True)
            )
            unit.special_rules["enhancement_martial_philosopher_once_per_battle"] = bool(
                params.get("once_per_battle", True)
            )
            unit.special_rules["enhancement_martial_philosopher_once_key"] = once_key
            unit.special_rules["enhancement_martial_philosopher_source"] = "Martial Philosopher"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_martial_philosopher_bearer_model_id"] = bearer_id

        if name == "veiled blade" or enh_id == "000008930005":
            if not is_auric_champions:
                return
            unit.special_rules["enhancement_veiled_blade"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            attacks_bonus = _coerce_int(params.get("melee_attacks_bonus", 2) or 2, default=2)
            oc_multiplier = _coerce_int(params.get("objective_control_multiplier", 3) or 3, default=3)
            once_key = str(params.get("once_per_battle_key", "veiled_blade") or "veiled_blade").strip().lower()
            if not once_key:
                once_key = "veiled_blade"
            unit.special_rules["enhancement_bearer_melee_attacks_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_attacks_bonus", 0) or 0
            ) + int(max(0, attacks_bonus))
            unit.special_rules["enhancement_veiled_blade_melee_attacks_bonus"] = int(max(0, attacks_bonus))
            unit.special_rules["enhancement_veiled_blade_objective_control_multiplier"] = int(max(2, oc_multiplier))
            unit.special_rules["enhancement_veiled_blade_once_key"] = once_key
            unit.special_rules["enhancement_veiled_blade_source"] = "Veiled Blade"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_veiled_blade_bearer_model_id"] = bearer_id

        if name == "castellan's mark" or enh_id == "000008395003":
            if not is_shield_host:
                return
            unit.special_rules["enhancement_castellans_mark"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            max_units = _coerce_int(params.get("max_units", 2) or 2, default=2)
            can_place_in_reserves = bool(params.get("can_place_in_reserves", True))
            filters = [
                str(v or "").strip().upper()
                for v in list(params.get("redeploy_filters", ("ADEPTUS CUSTODES",)) or ())
                if str(v or "").strip()
            ]
            if not filters:
                filters = ["ADEPTUS CUSTODES"]
            excluded_keywords = [
                str(v or "").strip().upper()
                for v in list(params.get("redeploy_excluded_keywords", ("ANATHEMA PSYKANA",)) or ())
                if str(v or "").strip()
            ]
            unit.special_rules["enhancement_castellans_mark_max_units"] = int(max(1, max_units))
            unit.special_rules["enhancement_castellans_mark_can_place_in_reserves"] = bool(
                can_place_in_reserves
            )
            unit.special_rules["enhancement_castellans_mark_filters"] = list(dict.fromkeys(filters))
            unit.special_rules["enhancement_castellans_mark_excluded_keywords"] = list(
                dict.fromkeys(excluded_keywords)
            )
            unit.special_rules["enhancement_castellans_mark_source"] = "Castellan's Mark"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_castellans_mark_bearer_model_id"] = bearer_id

        if name == "from the hall of armouries" or enh_id == "000008395004":
            if not is_shield_host:
                return
            unit.special_rules["enhancement_from_the_hall_of_armouries"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            strength_bonus = _coerce_int(params.get("melee_strength_bonus", 1) or 1, default=1)
            damage_bonus = _coerce_int(params.get("melee_damage_bonus", 1) or 1, default=1)
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0) or 0
            ) + int(max(0, strength_bonus))
            unit.special_rules["enhancement_bearer_melee_damage_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_damage_bonus", 0) or 0
            ) + int(max(0, damage_bonus))
            unit.special_rules["enhancement_from_the_hall_of_armouries_source"] = "From the Hall of Armouries"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_from_the_hall_of_armouries_bearer_model_id"] = bearer_id

        if name == "panoptispex" or enh_id == "000008395005":
            if not is_shield_host:
                return
            unit.special_rules["enhancement_panoptispex"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            unit.special_rules["enhancement_panoptispex_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            keywords = [
                str(v or "").strip().upper()
                for v in list(params.get("keywords", ("IGNORES COVER",)) or ())
                if str(v or "").strip()
            ]
            if not keywords:
                keywords = ["IGNORES COVER"]
            unit.special_rules["enhancement_panoptispex_keywords"] = list(dict.fromkeys(keywords))
            unit.special_rules["enhancement_panoptispex_source"] = "Panoptispex"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_panoptispex_bearer_model_id"] = bearer_id

        if name == "honoured fallen (aura)" or enh_id == "000009753004":
            if not is_solar_spearhead:
                return
            unit.special_rules["enhancement_honoured_fallen_aura"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                range_in = float(params.get("range", getattr(desc, "range_in", 6.0) or 6.0) or 6.0)
            except (TypeError, ValueError):
                range_in = 6.0
            target_keywords = [
                str(v or "").strip().upper()
                for v in list(params.get("required_target_keywords_any", ("INFANTRY", "MOUNTED")) or ())
                if str(v or "").strip()
            ]
            if not target_keywords:
                target_keywords = ["INFANTRY", "MOUNTED"]
            unit.special_rules["enhancement_honoured_fallen_aura_range"] = float(max(0.0, range_in))
            unit.special_rules["enhancement_honoured_fallen_required_target_keywords_any"] = list(
                dict.fromkeys(target_keywords)
            )
            unit.special_rules["enhancement_honoured_fallen_required_target_faction_keyword"] = str(
                params.get("required_target_faction_keyword", "ADEPTUS CUSTODES") or "ADEPTUS CUSTODES"
            ).strip().upper() or "ADEPTUS CUSTODES"
            unit.special_rules["enhancement_honoured_fallen_source"] = "Honoured Fallen (Aura)"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_honoured_fallen_bearer_model_id"] = bearer_id

        if name == "veteran of the kataphraktoi" or enh_id == "000009753005":
            if not is_solar_spearhead:
                return
            unit.special_rules["enhancement_veteran_of_the_kataphraktoi"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                range_in = float(params.get("range", getattr(desc, "range_in", 6.0) or 6.0) or 6.0)
            except (TypeError, ValueError):
                range_in = 6.0
            target_keywords = [
                str(v or "").strip().upper()
                for v in list(params.get("required_target_keywords_any", ("VEHICLE", "MOUNTED")) or ())
                if str(v or "").strip()
            ]
            if not target_keywords:
                target_keywords = ["VEHICLE", "MOUNTED"]
            unit.special_rules["enhancement_veteran_of_the_kataphraktoi_range"] = float(max(0.0, range_in))
            unit.special_rules["enhancement_veteran_of_the_kataphraktoi_required_target_keywords_any"] = list(
                dict.fromkeys(target_keywords)
            )
            unit.special_rules["enhancement_veteran_of_the_kataphraktoi_required_target_faction_keyword"] = str(
                params.get("required_target_faction_keyword", "ADEPTUS CUSTODES") or "ADEPTUS CUSTODES"
            ).strip().upper() or "ADEPTUS CUSTODES"
            unit.special_rules["enhancement_veteran_of_the_kataphraktoi_shoot_after_fall_back"] = bool(
                params.get("shoot_after_fall_back", True)
            )
            unit.special_rules["enhancement_veteran_of_the_kataphraktoi_optional"] = bool(
                params.get("optional", True)
            )
            unit.special_rules["enhancement_veteran_of_the_kataphraktoi_source"] = "Veteran of the Kataphraktoi"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_veteran_of_the_kataphraktoi_bearer_model_id"] = bearer_id

        if name == "aegis projector" or enh_id == "000008921002":
            if not is_talons_of_the_emperor:
                return
            unit.special_rules["enhancement_aegis_projector"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            usage_scope = str(params.get("usage_scope", "turn") or "turn").strip().lower()
            if usage_scope not in {"turn", "battle_round", "battle"}:
                usage_scope = "turn"
            unit.special_rules["enhancement_aegis_projector_usage_scope"] = usage_scope
            unit.special_rules["enhancement_aegis_projector_source"] = "Aegis Projector"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_aegis_projector_bearer_model_id"] = bearer_id
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("first_failed_save_damage_zero_sources", None)

        if name == "champion of the imperium" or enh_id == "000008921003":
            if not is_talons_of_the_emperor:
                return
            unit.special_rules["enhancement_champion_of_the_imperium"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                aura_range = float(params.get("aura_range", getattr(desc, "range_in", 9.0) or 9.0) or 9.0)
            except (TypeError, ValueError):
                aura_range = 9.0
            unit.special_rules["enhancement_champion_of_the_imperium_aura_range"] = float(max(0.0, aura_range))
            unit.special_rules["enhancement_champion_of_the_imperium_source"] = "Champion of the Imperium"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_champion_of_the_imperium_bearer_model_id"] = bearer_id

        if name == "gift of terran artifice" or enh_id == "000008921004":
            if not is_talons_of_the_emperor:
                return
            unit.special_rules["enhancement_gift_of_terran_artifice"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            wound_bonus = _coerce_int(params.get("melee_wound_bonus", 1) or 1, default=1)
            unit.special_rules["enhancement_gift_of_terran_artifice_melee_wound_bonus"] = int(max(0, wound_bonus))
            unit.special_rules["enhancement_gift_of_terran_artifice_source"] = "Gift of Terran Artifice"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_gift_of_terran_artifice_bearer_model_id"] = bearer_id

        if name == "radiant mantle" or enh_id == "000008921005":
            if not is_talons_of_the_emperor:
                return
            unit.special_rules["enhancement_radiant_mantle"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                range_in = float(params.get("range", getattr(desc, "range_in", 12.0) or 12.0) or 12.0)
            except (TypeError, ValueError):
                range_in = 12.0
            hit_penalty = _coerce_int(params.get("target_hit_roll_penalty", 1) or 1, default=1)
            unit.special_rules["enhancement_radiant_mantle_range"] = float(max(0.0, range_in))
            unit.special_rules["enhancement_radiant_mantle_target_hit_roll_penalty"] = int(max(0, hit_penalty))
            unit.special_rules["enhancement_radiant_mantle_source"] = "Radiant Mantle"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_radiant_mantle_bearer_model_id"] = bearer_id

        if name == "enhanced voidsheen cloak" or enh_id == "000008926002":
            if not is_null_maiden_vigil:
                return
            unit.special_rules["enhancement_enhanced_voidsheen_cloak"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            damage_reduction = _coerce_int(params.get("damage_reduction", 1) or 1, default=1)
            set_damage_to = _coerce_int(params.get("set_damage_to", 1) or 1, default=1)
            attacker_keywords = [
                str(v or "").strip().upper()
                for v in list(params.get("conditional_attacker_keywords_any", ("PSYKER",)) or ("PSYKER",))
                if str(v or "").strip()
            ]
            if not attacker_keywords:
                attacker_keywords = ["PSYKER"]
            unit.special_rules["enhancement_enhanced_voidsheen_cloak_damage_reduction"] = int(
                max(0, damage_reduction)
            )
            unit.special_rules["enhancement_enhanced_voidsheen_cloak_set_damage_to"] = int(max(0, set_damage_to))
            unit.special_rules["enhancement_enhanced_voidsheen_cloak_attacker_keywords_any"] = list(
                dict.fromkeys(attacker_keywords)
            )
            unit.special_rules["enhancement_enhanced_voidsheen_cloak_attacker_battle_shocked"] = bool(
                params.get("conditional_attacker_battle_shocked", True)
            )
            unit.special_rules["enhancement_enhanced_voidsheen_cloak_source"] = "Enhanced Voidsheen Cloak"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_enhanced_voidsheen_cloak_bearer_model_id"] = bearer_id

        if name == "huntress' eye" or enh_id == "000008926003":
            if not is_null_maiden_vigil:
                return
            unit.special_rules["enhancement_huntress_eye"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            try:
                range_in = float(params.get("range", getattr(desc, "range_in", 12.0) or 12.0) or 12.0)
            except (TypeError, ValueError):
                range_in = 12.0
            unit.special_rules["enhancement_huntress_eye_range"] = float(max(0.0, range_in))
            unit.special_rules["enhancement_huntress_eye_source"] = "Huntress' Eye"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_huntress_eye_bearer_model_id"] = bearer_id

        if name == "oblivion knight" or enh_id == "000008926004":
            if not is_null_maiden_vigil:
                return
            unit.special_rules["enhancement_oblivion_knight"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            hit_bonus = _coerce_int(params.get("hit_roll_bonus", 1) or 1, default=1)
            wound_bonus = _coerce_int(params.get("wound_roll_bonus_vs_psyker", 1) or 1, default=1)
            unit.special_rules["enhancement_oblivion_knight_requires_bearer_leading"] = bool(
                params.get("requires_bearer_leading", True)
            )
            unit.special_rules["enhancement_oblivion_knight_hit_roll_bonus"] = int(max(0, hit_bonus))
            unit.special_rules["enhancement_oblivion_knight_wound_roll_bonus_vs_psyker"] = int(
                max(0, wound_bonus)
            )
            unit.special_rules["enhancement_oblivion_knight_target_keywords_any"] = ["PSYKER"]
            unit.special_rules["enhancement_oblivion_knight_source"] = "Oblivion Knight"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_oblivion_knight_bearer_model_id"] = bearer_id

        if name == "raptor blade" or enh_id == "000008926005":
            if not is_null_maiden_vigil:
                return
            unit.special_rules["enhancement_raptor_blade"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            base_bonus = _coerce_int(params.get("base_melee_attacks_bonus", 1) or 1, default=1)
            strength_base_bonus = _coerce_int(params.get("base_melee_strength_bonus", base_bonus) or base_bonus, default=base_bonus)
            damage_base_bonus = _coerce_int(params.get("base_melee_damage_bonus", base_bonus) or base_bonus, default=base_bonus)
            conditional_extra = _coerce_int(params.get("conditional_extra_bonus", 1) or 1, default=1)
            conditional_enemy_keyword = str(
                params.get("conditional_enemy_keyword", "PSYKER") or "PSYKER"
            ).strip().upper()
            if not conditional_enemy_keyword:
                conditional_enemy_keyword = "PSYKER"

            # Neutralize generic parsed unit-wide melee bonuses; Raptor Blade is bearer-only.
            unit.special_rules["enhancement_melee_attacks_bonus"] = int(
                max(
                    0,
                    _coerce_int(unit.special_rules.get("enhancement_melee_attacks_bonus", 0) or 0, default=0)
                    - max(0, base_bonus),
                )
            )
            unit.special_rules["enhancement_melee_strength_bonus"] = int(
                max(
                    0,
                    _coerce_int(unit.special_rules.get("enhancement_melee_strength_bonus", 0) or 0, default=0)
                    - max(0, strength_base_bonus),
                )
            )
            unit.special_rules["enhancement_melee_damage_bonus"] = int(
                max(
                    0,
                    _coerce_int(unit.special_rules.get("enhancement_melee_damage_bonus", 0) or 0, default=0)
                    - max(0, damage_base_bonus),
                )
            )

            unit.special_rules["enhancement_bearer_melee_attacks_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_attacks_bonus", 0) or 0
            ) + int(max(0, base_bonus))
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0) or 0
            ) + int(max(0, strength_base_bonus))
            unit.special_rules["enhancement_bearer_melee_damage_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_damage_bonus", 0) or 0
            ) + int(max(0, damage_base_bonus))
            unit.special_rules["enhancement_raptor_blade_conditional_extra_bonus"] = int(
                max(0, conditional_extra)
            )
            unit.special_rules["enhancement_raptor_blade_conditional_enemy_keyword"] = conditional_enemy_keyword
            unit.special_rules["enhancement_raptor_blade_conditional_enemy_battle_shocked"] = bool(
                params.get("conditional_enemy_battle_shocked", True)
            )
            unit.special_rules["enhancement_raptor_blade_source"] = "Raptor Blade"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_raptor_blade_bearer_model_id"] = bearer_id

        if name == "superior creation" or enh_id == "000009987002":
            if not is_lions:
                return
            unit.special_rules["enhancement_superior_creation"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
            refresh_return = getattr(unit, "_refresh_return_on_death_flags", None)
            if callable(refresh_return):
                refresh_return()

        if name == "praesidius" or enh_id == "000009987003":
            if not is_lions:
                return
            unit.special_rules["enhancement_praesidius_lone_operative"] = True
            unit.special_rules["enhancement_praesidius_stealth"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "fierce conqueror" or enh_id == "000009987004":
            if not is_lions:
                return
            unit.special_rules["enhancement_fierce_conqueror"] = True
            if bearer_id:
                unit.special_rules["enhancement_fierce_conqueror_bearer_id"] = bearer_id
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "admonimortis" or enh_id == "000009987005":
            if not is_lions:
                return
            unit.special_rules["enhancement_admonimortis"] = True
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0) or 0
            ) + 3
            unit.special_rules["enhancement_bearer_melee_ap_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_ap_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_melee_damage_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_damage_bonus", 0) or 0
            ) + 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "bloodthirsty belligerence" or enh_id == "000008881002":
            if not is_green_tide:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            source = str(getattr(desc, "name", "") or "Bloodthirsty Belligerence").strip() or "Bloodthirsty Belligerence"
            unit.special_rules["enhancement_green_tide_bloodthirsty_belligerence"] = True
            unit.special_rules["enhancement_green_tide_bloodthirsty_belligerence_source"] = source
            unit.special_rules.pop("enhancement_reroll_advance", None)
            unit.special_rules.pop("enhancement_charge_reroll", None)
            unit.special_rules.pop("enhancement_reroll_advance_charge", None)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_green_tide_bloodthirsty_belligerence_bearer_model_id"] = bearer_id

        if name in ("brutal but kunnin'", "brutal but kunnin") or enh_id == "000008881003":
            if not is_green_tide:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Brutal But Kunnin'").strip() or "Brutal But Kunnin'"
            success_on = _coerce_int(params.get("success_on", 5) or 5, default=5)
            cp_gain = _coerce_int(params.get("cp_gain", 1) or 1, default=1)
            roll_bonus = _coerce_int(
                params.get("roll_bonus_if_effective_model_count_at_least", 2) or 2,
                default=2,
            )
            count_threshold = _coerce_int(
                params.get("effective_model_count_threshold", 10) or 10,
                default=10,
            )
            count_scope = str(params.get("effective_model_count_scope", "enhancement") or "enhancement").strip().lower()
            if not count_scope:
                count_scope = "enhancement"
            unit.special_rules["enhancement_green_tide_brutal_but_kunnin"] = True
            unit.special_rules["enhancement_green_tide_brutal_but_kunnin_source"] = source
            unit.special_rules["enhancement_green_tide_brutal_but_kunnin_success_on"] = int(
                min(6, max(2, success_on))
            )
            unit.special_rules["enhancement_green_tide_brutal_but_kunnin_cp_gain"] = int(max(1, cp_gain))
            unit.special_rules["enhancement_green_tide_brutal_but_kunnin_roll_bonus_if_effective_model_count_at_least"] = int(
                roll_bonus
            )
            unit.special_rules["enhancement_green_tide_brutal_but_kunnin_effective_model_count_threshold"] = int(
                max(0, count_threshold)
            )
            unit.special_rules["enhancement_green_tide_brutal_but_kunnin_effective_model_count_scope"] = count_scope
            _register_enhancement_command_phase_cp_gain_roll_spec(
                unit,
                source_name=source,
                source_model_id=bearer_id,
                success_on=int(min(6, max(2, success_on))),
                cp_gain=int(max(1, cp_gain)),
                requires_bearer_on_battlefield_or_embarked_transport=bool(
                    params.get("requires_bearer_on_battlefield_or_embarked_transport", True)
                ),
                roll_bonus_if_effective_model_count_at_least=int(roll_bonus),
                effective_model_count_threshold=int(max(0, count_threshold)),
                effective_model_count_scope=count_scope,
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_green_tide_brutal_but_kunnin_bearer_model_id"] = bearer_id

        if name == "ferocious show off" or enh_id == "000008881004":
            if not is_green_tide:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Ferocious Show Off").strip() or "Ferocious Show Off"
            base_bonus = _coerce_int(params.get("base_melee_strength_bonus", 1), default=1)
            enhanced_bonus = _coerce_int(params.get("enhanced_melee_strength_bonus", 3), default=3)
            unit.special_rules["enhancement_green_tide_ferocious_show_off"] = True
            unit.special_rules["enhancement_green_tide_ferocious_show_off_source"] = source
            unit.special_rules["enhancement_green_tide_ferocious_show_off_base_bonus"] = int(max(0, base_bonus))
            unit.special_rules["enhancement_green_tide_ferocious_show_off_enhanced_bonus"] = int(max(0, enhanced_bonus))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_green_tide_ferocious_show_off_bearer_model_id"] = bearer_id

        if name == "raucous warcaller" or enh_id == "000008881005":
            if not is_green_tide:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Raucous Warcaller").strip() or "Raucous Warcaller"
            raw_scopes = list(params.get("effective_model_count_scopes", ("detachment", "stratagem")) or ())
            scopes = []
            for entry in raw_scopes:
                token = str(entry or "").strip().lower()
                if token and token not in scopes:
                    scopes.append(token)
            if not scopes:
                scopes = ["detachment", "stratagem"]
            floor = _coerce_int(params.get("effective_model_floor", 10), default=10)
            unit.special_rules["enhancement_green_tide_raucous_warcaller"] = True
            unit.special_rules["enhancement_green_tide_raucous_warcaller_source"] = source
            unit.special_rules["enhancement_green_tide_raucous_warcaller_effective_model_scopes"] = list(scopes)
            unit.special_rules["enhancement_green_tide_effective_model_floor"] = int(max(0, floor))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_green_tide_raucous_warcaller_bearer_model_id"] = bearer_id

        if name == "follow me ladz" or enh_id == "000008367002":
            if not is_war_horde:
                return
            unit.special_rules["enhancement_follow_me_ladz"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "headwoppa's killchoppa" or enh_id == "000008367003":
            if not is_war_horde:
                return
            unit.special_rules["enhancement_headwoppas_killchoppa"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "kunnin' but brutal" or enh_id == "000008367004":
            if not is_war_horde:
                return
            unit.special_rules["enhancement_kunnin_but_brutal"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "supa-cybork body" or enh_id == "000008367005":
            if not is_war_horde:
                return
            unit.special_rules["enhancement_supa_cybork_body"] = True
            _ensure_enhancement_fnp_entry(
                unit,
                4,
                source="Supa-Cybork Body",
                tag="supa_cybork_body",
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "fasta than yooz" or enh_id == "000008872002":
            if not is_kult_of_speed:
                return
            has_any_keyword = getattr(unit, "has_any_keyword", None)
            if not callable(has_any_keyword) or not bool(has_any_keyword("INFANTRY")):
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Fasta Than Yooz").strip() or "Fasta Than Yooz"
            unit.special_rules["enhancement_kult_of_speed_fasta_than_yooz"] = True
            unit.special_rules["enhancement_kult_of_speed_fasta_than_yooz_source"] = source
            unit.special_rules["enhancement_kult_of_speed_fasta_than_yooz_allow_charge_after_normal_move_disembark"] = bool(
                params.get("allow_charge_after_normal_move", True)
            )
            unit.special_rules["enhancement_kult_of_speed_fasta_than_yooz_requires_disembarked_from_moved_transport"] = bool(
                params.get("requires_disembarked_from_moved_transport", True)
            )
            unit.special_rules["enhancement_kult_of_speed_fasta_than_yooz_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_kult_of_speed_fasta_than_yooz_bearer_model_id"] = bearer_id

        if name == "speed makes right" or enh_id == "000008872003":
            if not is_kult_of_speed:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Speed Makes Right").strip() or "Speed Makes Right"
            success_on = _coerce_int(params.get("success_on", 3) or 3, default=3)
            cp_gain = _coerce_int(params.get("cp_gain", 1) or 1, default=1)
            range_in = _coerce_float(
                params.get("enemy_range_max", params.get("enemy_within", 9.0)) or 9.0,
                default=9.0,
            )
            unit.special_rules["enhancement_kult_of_speed_speed_makes_right"] = True
            unit.special_rules["enhancement_kult_of_speed_speed_makes_right_source"] = source
            unit.special_rules["enhancement_kult_of_speed_speed_makes_right_success_on"] = int(
                min(6, max(2, success_on))
            )
            unit.special_rules["enhancement_kult_of_speed_speed_makes_right_cp_gain"] = int(max(1, cp_gain))
            unit.special_rules["enhancement_kult_of_speed_speed_makes_right_enemy_range"] = float(max(0.0, range_in))
            _register_enhancement_command_phase_cp_gain_roll_spec(
                unit,
                source_name=source,
                source_model_id=bearer_id,
                success_on=int(min(6, max(2, success_on))),
                cp_gain=int(max(1, cp_gain)),
                requires_bearer_on_battlefield_or_embarked_transport=bool(
                    params.get("requires_bearer_on_battlefield_or_embarked_transport", True)
                ),
                enemy_range_max=float(max(0.0, range_in)),
                enemy_range_reference=str(
                    params.get("enemy_range_reference", "bearer_or_transport")
                    or "bearer_or_transport"
                ).strip().lower(),
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_kult_of_speed_speed_makes_right_bearer_model_id"] = bearer_id

        if name == "squig-hide tyres" or enh_id == "000008872004":
            if not is_kult_of_speed:
                return
            unit_name = normalize_enhancement_token(getattr(unit, "name", "") or "")
            if unit_name != "deffkilla wartrike":
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Squig-hide Tyres").strip() or "Squig-hide Tyres"
            distance = _coerce_int(params.get("consolidate_distance_override", 6) or 6, default=6)
            unit.special_rules["enhancement_kult_of_speed_squig_hide_tyres"] = True
            unit.special_rules["enhancement_kult_of_speed_squig_hide_tyres_source"] = source
            unit.special_rules["enhancement_kult_of_speed_squig_hide_tyres_consolidate_distance_override"] = int(
                max(3, distance)
            )
            unit.special_rules["enhancement_kult_of_speed_squig_hide_tyres_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_kult_of_speed_squig_hide_tyres_bearer_model_id"] = bearer_id

        if name == "wazblasta" or enh_id == "000008872005":
            if not is_kult_of_speed:
                return
            unit_name = normalize_enhancement_token(getattr(unit, "name", "") or "")
            if unit_name != "deffkilla wartrike":
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Wazblasta").strip() or "Wazblasta"
            move_range = _coerce_int(params.get("move_range", 6) or 6, default=6)
            unit.special_rules["enhancement_kult_of_speed_wazblasta"] = True
            unit.special_rules["enhancement_kult_of_speed_wazblasta_source"] = source
            unit.special_rules["enhancement_kult_of_speed_wazblasta_post_shoot_move_range"] = int(max(1, move_range))
            unit.special_rules["enhancement_kult_of_speed_wazblasta_requires_not_engagement_range"] = bool(
                params.get("requires_not_engagement_range", True)
            )
            unit.special_rules["enhancement_kult_of_speed_wazblasta_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_kult_of_speed_wazblasta_bearer_model_id"] = bearer_id

        if name == "big gob" or enh_id == "000008885002":
            if not is_bully_boyz:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Big Gob").strip() or "Big Gob"
            test_modifier = _coerce_int(params.get("battle_shock_test_modifier", -1), default=-1)
            if test_modifier == 0:
                test_modifier = -1
            unit.special_rules["enhancement_big_gob"] = True
            unit.special_rules["enhancement_big_gob_source"] = source
            unit.special_rules["enhancement_big_gob_test_penalty"] = int(abs(int(test_modifier)))
            unit.special_rules["enhancement_big_gob_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_big_gob_ability_key"] = str(
                params.get("ability_key", "big_gob") or "big_gob"
            ).strip().lower() or "big_gob"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_big_gob_bearer_model_id"] = bearer_id

        if name == "eadstompa" or enh_id == "000008885004":
            if not is_bully_boyz:
                return
            has_any_keyword = getattr(unit, "has_any_keyword", None)
            if not callable(has_any_keyword):
                return
            if not bool(has_any_keyword("INFANTRY")) or not bool(has_any_keyword("WARBOSS")):
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "’Eadstompa").strip() or "’Eadstompa"
            reroll_values = tuple(int(value) for value in tuple(params.get("reroll_values_vs_below_starting_strength", (1,))) if int(value) > 0)
            unit.special_rules["enhancement_eadstompa"] = True
            unit.special_rules["enhancement_eadstompa_source"] = source
            unit.special_rules["enhancement_eadstompa_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_eadstompa_reroll_values_vs_below_starting_strength"] = reroll_values or (1,)
            unit.special_rules["enhancement_eadstompa_reroll_full_vs_below_half_strength"] = bool(
                params.get("reroll_full_vs_below_half_strength", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_eadstompa_bearer_model_id"] = bearer_id

        if name == "tellyporta" or enh_id == "000008885005":
            if not is_bully_boyz:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            source = str(getattr(desc, "name", "") or "Tellyporta").strip() or "Tellyporta"
            unit.special_rules["enhancement_tellyporta"] = True
            unit.special_rules["enhancement_tellyporta_source"] = source
            unit.special_rules["bearer_unit_deep_strike"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_tellyporta_bearer_model_id"] = bearer_id

        if name == "glory hog" or enh_id == "000008868002":
            if not is_da_big_hunt:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            scout_distance = _coerce_int(params.get("scouts_distance", 9), default=9)
            source = str(getattr(desc, "name", "") or "Glory Hog").strip() or "Glory Hog"
            unit.special_rules["enhancement_glory_hog"] = True
            unit.special_rules["enhancement_glory_hog_source"] = source
            unit.special_rules["enhancement_scout_distance"] = int(
                max(
                    int(unit.special_rules.get("enhancement_scout_distance", 0) or 0),
                    max(0, int(scout_distance)),
                )
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_glory_hog_bearer_model_id"] = bearer_id

        if name == "proper killy" or enh_id == "000008868003":
            if not is_da_big_hunt:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            damage_bonus = _coerce_int(params.get("melee_damage_bonus", 1), default=1)
            source = str(getattr(desc, "name", "") or "Proper Killy").strip() or "Proper Killy"
            unit.special_rules["enhancement_proper_killy"] = True
            unit.special_rules["enhancement_proper_killy_source"] = source
            unit.special_rules["enhancement_bearer_melee_damage_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_damage_bonus", 0) or 0
            ) + int(max(0, damage_bonus))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_proper_killy_bearer_model_id"] = bearer_id

        if name == "skrag every stash!" or enh_id == "000008868004":
            if not is_da_big_hunt:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Skrag Every Stash!").strip() or "Skrag Every Stash!"
            unit.special_rules["enhancement_skrag_every_stash"] = True
            unit.special_rules["enhancement_skrag_every_stash_source"] = source
            _apply_enhancement_sticky_objective_control(
                unit,
                source_scope=str(params.get("source_scope", "bearer") or "bearer"),
                source=str(params.get("sticky_source", "unit_sticky_objective") or "unit_sticky_objective"),
                allow_embarked_transport=bool(params.get("allow_embarked_transport", False)),
                requires_bearer_leading=bool(params.get("requires_bearer_leading", False)),
                source_model_id=bearer_id,
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_skrag_every_stash_bearer_model_id"] = bearer_id

        if name == "surly as a squiggoth" or enh_id == "000008868005":
            if not is_da_big_hunt:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            source = str(getattr(desc, "name", "") or "Surly as a Squiggoth").strip() or "Surly as a Squiggoth"
            unit.special_rules["enhancement_surly_as_a_squiggoth"] = True
            unit.special_rules["enhancement_surly_as_a_squiggoth_source"] = source
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_surly_as_a_squiggoth_bearer_model_id"] = bearer_id

        if name == "gitfinder googlez" or enh_id == "000008877002":
            if not is_dread_mob:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Gitfinder Googlez").strip() or "Gitfinder Googlez"
            keywords = tuple(
                str(v or "").strip().upper()
                for v in list(params.get("keywords", ("IGNORES COVER",)) or ())
                if str(v or "").strip()
            )
            unit.special_rules["enhancement_gitfinder_googlez"] = True
            unit.special_rules["enhancement_gitfinder_googlez_source"] = source
            _append_enhancement_bearer_unit_weapon_keyword_rule(
                unit,
                attack_type="ranged",
                keywords=keywords,
                source=source,
                requires_bearer_leading=False,
                source_model_id=bearer_id,
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_gitfinder_googlez_bearer_model_id"] = bearer_id

        if name == "press it fasta" or enh_id == "000008877003":
            if not is_dread_mob:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Press It Fasta!").strip() or "Press It Fasta!"
            extra_rolls = _coerce_int(params.get("extra_rolls", 1), default=1)
            if extra_rolls <= 0:
                extra_rolls = 1
            unit.special_rules["enhancement_press_it_fasta"] = True
            unit.special_rules["enhancement_press_it_fasta_source"] = source
            unit.special_rules["enhancement_press_it_fasta_extra_rolls"] = int(extra_rolls)
            unit.special_rules["enhancement_press_it_fasta_trigger"] = str(
                params.get("trigger", "shooting") or "shooting"
            ).strip().lower()
            unit.special_rules["enhancement_press_it_fasta_detachment_ability"] = str(
                params.get("detachment_ability", "try_dat_button") or "try_dat_button"
            ).strip().lower()
            unit.special_rules["enhancement_press_it_fasta_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_press_it_fasta_bearer_model_id"] = bearer_id

        if name == "smoky gubbinz" or enh_id == "000008877004":
            if not is_dread_mob:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            source = str(getattr(desc, "name", "") or "Smoky Gubbinz").strip() or "Smoky Gubbinz"
            unit.special_rules["enhancement_smoky_gubbinz"] = True
            unit.special_rules["enhancement_smoky_gubbinz_source"] = source
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_smoky_gubbinz_bearer_model_id"] = bearer_id

        if name == "supa-glowy fing" or enh_id == "000008877005":
            if not is_dread_mob:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Supa-glowy Fing").strip() or "Supa-glowy Fing"
            range_value = _coerce_float(
                params.get("range_in", getattr(desc, "range_in", 18.0)) or getattr(desc, "range_in", 18.0),
                default=18.0,
            )
            if range_value <= 0:
                range_value = 18.0
            ability_key = str(params.get("ability_key", "supa_glowy_fing") or "supa_glowy_fing").strip().lower()
            if not ability_key:
                ability_key = "supa_glowy_fing"
            unit.special_rules["enhancement_supa_glowy_fing"] = True
            unit.special_rules["enhancement_supa_glowy_fing_source"] = source
            unit.special_rules["enhancement_supa_glowy_fing_range"] = float(range_value)
            unit.special_rules["enhancement_supa_glowy_fing_requires_visibility"] = bool(
                params.get("requires_visibility", True)
            )
            unit.special_rules["enhancement_supa_glowy_fing_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_supa_glowy_fing_ability_key"] = ability_key
            unit.special_rules["enhancement_supa_glowy_fing_selection_prompt"] = (
                f"{source}: select one visible enemy unit within {int(range_value)}\" to resolve the roll table."
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_supa_glowy_fing_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if name == "da kaptin" or enh_id == "000010712002":
            if not is_freebooter_krew:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Da Kaptin").strip() or "Da Kaptin"
            range_value = _coerce_float(
                params.get("range_in", getattr(desc, "range_in", 12.0)) or getattr(desc, "range_in", 12.0),
                default=12.0,
            )
            if range_value <= 0:
                range_value = 12.0
            keyword_phrase = str(
                params.get("required_target_faction_keyword", params.get("keyword_phrase", "ORKS")) or "ORKS"
            ).strip()
            if not keyword_phrase:
                keyword_phrase = "ORKS"
            ability_key = str(params.get("ability_key", "da_kaptin") or "da_kaptin").strip().lower()
            if not ability_key:
                ability_key = "da_kaptin"
            mortal_wounds_roll = str(params.get("mortal_wounds_roll", "D3") or "D3").strip().upper() or "D3"
            unit.special_rules["enhancement_da_kaptin"] = True
            unit.special_rules["enhancement_da_kaptin_source"] = source
            unit.special_rules["enhancement_da_kaptin_range"] = float(range_value)
            unit.special_rules["enhancement_da_kaptin_keyword_phrase"] = keyword_phrase
            unit.special_rules["enhancement_da_kaptin_mortal_wounds_roll"] = mortal_wounds_roll
            unit.special_rules["enhancement_da_kaptin_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_da_kaptin_requires_target_battle_shocked"] = bool(
                params.get("requires_target_battle_shocked", True)
            )
            unit.special_rules["enhancement_da_kaptin_once_per_battle_round"] = bool(
                params.get("once_per_battle_round", True)
            )
            unit.special_rules["enhancement_da_kaptin_ability_key"] = ability_key
            unit.special_rules["enhancement_da_kaptin_selection_prompt"] = (
                f"{source}: select one Battle-shocked friendly {keyword_phrase} unit within {int(range_value)}\" "
                f"to suffer {mortal_wounds_roll} mortal wounds, then clear Battle-shock (or None)."
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_da_kaptin_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if name == "git-spotter squig" or enh_id == "000010712003":
            if not is_freebooter_krew:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Git-spotter Squig").strip() or "Git-spotter Squig"
            keywords = tuple(
                str(v or "").strip().upper()
                for v in list(params.get("keywords", ("IGNORES COVER",)) or ())
                if str(v or "").strip()
            )
            unit.special_rules["enhancement_git_spotter_squig"] = True
            unit.special_rules["enhancement_git_spotter_squig_source"] = source
            _append_enhancement_bearer_unit_weapon_keyword_rule(
                unit,
                attack_type="ranged",
                keywords=keywords,
                source=source,
                requires_bearer_leading=False,
                source_model_id=bearer_id,
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_git_spotter_squig_bearer_model_id"] = bearer_id

        if name == "bionik workshop" or enh_id == "000010712004":
            if not is_freebooter_krew:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Bionik Workshop").strip() or "Bionik Workshop"
            ability_key = str(params.get("ability_key", "bionik_workshop") or "bionik_workshop").strip().lower()
            if not ability_key:
                ability_key = "bionik_workshop"
            roll_expr = str(params.get("roll", "D3") or "D3").strip().upper() or "D3"
            roll_branches = dict(params.get("roll_branches", {}) or {})
            unit.special_rules["enhancement_bionik_workshop"] = True
            unit.special_rules["enhancement_bionik_workshop_source"] = source
            unit.special_rules["enhancement_bionik_workshop_ability_key"] = ability_key
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_bionik_workshop_bearer_model_id"] = bearer_id
            _register_enhancement_start_of_battle_roll_spec(
                unit,
                source_name=source,
                source_model_id=bearer_id,
                ability_key=ability_key,
                roll_expr=roll_expr,
                effect="bionik_workshop",
                effect_params={"roll_branches": roll_branches},
                requires_bearer_alive=bool(params.get("requires_bearer_alive", True)),
            )
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if name == "razgit's magik map" or enh_id == "000010712005":
            if not is_freebooter_krew:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Razgit's Magik Map").strip() or "Razgit's Magik Map"
            unit.special_rules["enhancement_razgits_magik_map"] = True
            unit.special_rules["enhancement_razgits_magik_map_source"] = source
            _register_enhancement_redeploy_spec(
                unit,
                source_name=source,
                source_model_id=bearer_id,
                max_units=_coerce_int(params.get("max_units", 3) or 3, default=3),
                can_place_in_reserves=bool(params.get("allow_strategic_reserves", True)),
                redeploy_filters=list(params.get("redeploy_filters", ("ORKS", "INFANTRY")) or ()),
                strategic_reserves_ignore_current_unit_count_limit=bool(
                    params.get("strategic_reserves_ignore_current_unit_count_limit", False)
                ),
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_razgits_magik_map_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if name == "da gobshot thunderbuss" or enh_id == "000009991002":
            if not is_more_dakka:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Da Gobshot Thunderbuss").strip() or "Da Gobshot Thunderbuss"
            keywords = tuple(
                str(value or "").strip().upper()
                for value in list(params.get("keywords", ("DEVASTATING WOUNDS", "HAZARDOUS")) or ())
                if str(value or "").strip()
            )
            attack_type = str(params.get("attack_type", "ranged") or "ranged").strip().lower() or "ranged"
            unit.special_rules["enhancement_da_gobshot_thunderbuss"] = True
            unit.special_rules["enhancement_da_gobshot_thunderbuss_source"] = source
            _append_enhancement_bearer_weapon_keyword_rule(
                unit,
                attack_type=attack_type,
                keywords=keywords,
                source=source,
                requires_bearer_leading=False,
                source_model_id=bearer_id,
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_da_gobshot_thunderbuss_bearer_model_id"] = bearer_id

        if name == "dead shiny shootas" or enh_id == "000009991003":
            if not is_more_dakka:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Dead Shiny Shootas").strip() or "Dead Shiny Shootas"
            keywords = tuple(
                str(value or "").strip().upper()
                for value in list(params.get("keywords", ("RAPID FIRE 1",)) or ())
                if str(value or "").strip()
            )
            attack_type = str(params.get("attack_type", "ranged") or "ranged").strip().lower() or "ranged"
            unit.special_rules["enhancement_dead_shiny_shootas"] = True
            unit.special_rules["enhancement_dead_shiny_shootas_source"] = source
            _append_enhancement_bearer_unit_weapon_keyword_rule(
                unit,
                attack_type=attack_type,
                keywords=keywords,
                source=source,
                requires_bearer_leading=False,
                source_model_id=bearer_id,
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_dead_shiny_shootas_bearer_model_id"] = bearer_id

        if name == "targetin' squigs" or enh_id == "000009991004":
            if not is_more_dakka:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Targetin' Squigs").strip() or "Targetin' Squigs"
            attack_type = str(params.get("attack_type", "ranged") or "ranged").strip().lower() or "ranged"
            hit_bonus = _coerce_int(
                params.get("modifier", params.get("hit_roll_bonus", 1)) or 1,
                default=1,
            )
            unit.special_rules["enhancement_targetin_squigs"] = True
            unit.special_rules["enhancement_targetin_squigs_source"] = source
            _append_enhancement_bearer_unit_attack_roll_modifier_rule(
                unit,
                attack_type=attack_type,
                roll="hit",
                modifier=int(hit_bonus),
                source=source,
                requires_bearer_leading=False,
                source_model_id=bearer_id,
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_targetin_squigs_bearer_model_id"] = bearer_id

        if name == "zog off and eat dakka!" or enh_id == "000009991005":
            if not is_more_dakka:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Zog Off and Eat Dakka!").strip() or "Zog Off and Eat Dakka!"
            attack_type = str(params.get("attack_type", "ranged") or "ranged").strip().lower() or "ranged"
            if bool(params.get("shoot_after_fall_back", params.get("allow_shoot_after_fall_back", True))):
                _append_enhancement_bearer_unit_fall_back_shoot_rule(
                    unit,
                    attack_type=attack_type,
                    source=source,
                    requires_bearer_leading=False,
                    source_model_id=bearer_id,
                )
            unit.special_rules["enhancement_zog_off_and_eat_dakka"] = True
            unit.special_rules["enhancement_zog_off_and_eat_dakka_source"] = source
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_zog_off_and_eat_dakka_bearer_model_id"] = bearer_id

        if name == "skwad leader" or enh_id == "000009795002":
            if not is_taktikal_brigade:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Skwad Leader").strip() or "Skwad Leader"
            attach_names = [
                str(v).strip()
                for v in list(params.get("attachment_override_unit_names_any", ("Kommandos",)) or ())
                if str(v or "").strip()
            ]
            unit.special_rules["enhancement_skwad_leader"] = True
            unit.special_rules["enhancement_skwad_leader_source"] = source
            unit.special_rules["enhancement_skwad_leader_attach_unit_names"] = list(attach_names)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_skwad_leader_bearer_model_id"] = bearer_id

        if name == "mek kaptin" or enh_id == "000009795003":
            if not is_taktikal_brigade:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Mek Kaptin").strip() or "Mek Kaptin"
            attach_names = [
                str(v).strip()
                for v in list(params.get("attachment_override_unit_names_any", ("Flash Gitz",)) or ())
                if str(v or "").strip()
            ]
            unit.special_rules["enhancement_mek_kaptin"] = True
            unit.special_rules["enhancement_mek_kaptin_source"] = source
            unit.special_rules["enhancement_mek_kaptin_attach_unit_names"] = list(attach_names)
            unit.special_rules["enhancement_mek_kaptin_ranged_hit_reroll_full"] = bool(
                params.get("reroll_hit_full", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_mek_kaptin_bearer_model_id"] = bearer_id

        if name == "mork's kunnin'" or enh_id == "000009795004":
            if not is_taktikal_brigade:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Mork's Kunnin'").strip() or "Mork's Kunnin'"
            unit.special_rules["enhancement_morks_kunnin"] = True
            unit.special_rules["enhancement_morks_kunnin_source"] = source
            _register_enhancement_redeploy_spec(
                unit,
                source_name=source,
                source_model_id=bearer_id,
                max_units=_coerce_int(params.get("max_units", 3) or 3, default=3),
                can_place_in_reserves=bool(params.get("allow_strategic_reserves", True)),
                redeploy_filters=list(params.get("redeploy_filters", ("ORKS",)) or ()),
                strategic_reserves_ignore_current_unit_count_limit=bool(
                    params.get("strategic_reserves_ignore_current_unit_count_limit", False)
                ),
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_morks_kunnin_bearer_model_id"] = bearer_id
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()

        if name == "gob boomer" or enh_id == "000009795005":
            if not is_taktikal_brigade:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            source = str(getattr(desc, "name", "") or "Gob Boomer").strip() or "Gob Boomer"
            issue_range = _coerce_float(params.get("taktik_issue_range", 18.0), default=18.0)
            if issue_range <= 0:
                issue_range = 18.0
            unit.special_rules["enhancement_gob_boomer"] = True
            unit.special_rules["enhancement_gob_boomer_source"] = source
            unit.special_rules["enhancement_taktikal_issue_range"] = float(issue_range)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_gob_boomer_bearer_model_id"] = bearer_id

        if name == "preyslayer's mantle" or enh_id == "000010312002":
            if not is_houndpack_lance:
                return
            unit.special_rules["enhancement_houndpack_preyslayers_mantle"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "final howl (aura)" or enh_id == "000010312003":
            if not is_houndpack_lance:
                return
            unit.special_rules["enhancement_houndpack_final_howl"] = True
            unit.special_rules["enhancement_houndpack_final_howl_range"] = 6.0
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "loping predator" or enh_id == "000010312004":
            if not is_houndpack_lance:
                return
            unit.special_rules["enhancement_houndpack_loping_predator"] = True
            unit.special_rules["bearer_unit_assault_ranged"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "panoply of the cursed knight" or enh_id == "000010312005":
            if not is_houndpack_lance:
                return
            unit.special_rules["enhancement_houndpack_panoply_of_the_cursed_knight"] = True
            unit.special_rules["enhancement_houndpack_panoply_ap_worsen"] = 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "knight diabolus" or enh_id == "000010304002":
            if not is_infernal_lance:
                return
            unit.special_rules["enhancement_knight_diabolus"] = True
            unit.special_rules["enhancement_knight_diabolus_ws_bonus"] = 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "blasphemous engine" or enh_id == "000010304003":
            if not is_infernal_lance:
                return
            unit.special_rules["enhancement_blasphemous_engine"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "fleshmetal fusion" or enh_id == "000010304004":
            if not is_infernal_lance:
                return
            unit.special_rules["enhancement_fleshmetal_fusion"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
            if bearer is not None:
                try:
                    bearer._base_toughness = int(getattr(bearer, "_base_toughness", 0)) + 1
                    bearer._toughness = int(getattr(bearer, "_toughness", 0)) + 1
                except Exception:
                    pass

        if name == "bestial aspect" or enh_id == "000010304005":
            if not is_infernal_lance:
                return
            unit.special_rules["enhancement_bestial_aspect"] = True
            unit.special_rules["bearer_unit_assault_ranged"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "nightmare's master" or enh_id == "000008516002":
            if not is_traitoris_lance:
                return
            unit.special_rules["enhancement_traitoris_nightmares_master"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "tyrant's shadow" or enh_id == "000008516003":
            if not is_traitoris_lance:
                return
            unit.special_rules["enhancement_traitoris_tyrants_shadow"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "malevolent heraldry" or enh_id == "000008516004":
            if not is_traitoris_lance:
                return
            unit.special_rules["enhancement_traitoris_malevolent_heraldry"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "veil of medrengard" or enh_id == "000008516005":
            if not is_traitoris_lance:
                return
            unit.special_rules["enhancement_traitoris_veil_of_medrengard"] = True
            unit.special_rules["enhancement_traitoris_veil_ranged_invulnerable"] = 4
            unit.special_rules["enhancement_traitoris_veil_melee_invulnerable"] = 5
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "profane altar" or enh_id == "000009765002":
            if not is_iconoclast_fiefdom:
                return
            unit.special_rules["enhancement_iconoclast_profane_altar"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "pave the way" or enh_id == "000009765003":
            if not is_iconoclast_fiefdom:
                return
            unit.special_rules["enhancement_iconoclast_pave_the_way"] = True
            unit.special_rules["enhancement_iconoclast_pave_the_way_scouts_distance"] = 6
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "tyrant's banner" or enh_id == "000009765004":
            if not is_iconoclast_fiefdom:
                return
            unit.special_rules["enhancement_iconoclast_tyrants_banner"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "diabolical resilience" or enh_id == "000009765005":
            if not is_iconoclast_fiefdom:
                return
            unit.special_rules["enhancement_iconoclast_diabolical_resilience"] = True
            unit.special_rules["enhancement_diabolical_resilience_ignore_move_modifiers"] = True
            unit.special_rules["enhancement_diabolical_resilience_ignore_advance_modifiers"] = True
            unit.special_rules["enhancement_diabolical_resilience_ignore_charge_modifiers"] = True
            _ensure_enhancement_fnp_entry(
                unit,
                6,
                source="Diabolical Resilience",
                tag="diabolical_resilience",
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "throne mechanicum of skulls" or enh_id == "000010308002":
            if not is_lords_of_dread:
                return
            unit.special_rules["enhancement_lords_throne_mechanicum_of_skulls"] = True
            unit.special_rules["enhancement_charge_reroll"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            once_key = str(
                params.get("once_per_battle_key", "throne_mechanicum_of_skulls") or "throne_mechanicum_of_skulls"
            ).strip().lower()
            if not once_key:
                once_key = "throne_mechanicum_of_skulls"
            source_name = str(getattr(self, "name", "") or "Throne Mechanicum of Skulls").strip()
            if not source_name:
                source_name = "Throne Mechanicum of Skulls"
            unit.special_rules["enhancement_charge_after_advance_once_per_battle"] = True
            unit.special_rules["enhancement_charge_after_advance_once_key"] = once_key
            unit.special_rules["enhancement_charge_after_advance_source"] = source_name
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_lords_throne_mechanicum_of_skulls_bearer_model_id"] = bearer_id

        if name == "blade of celerity" or enh_id == "000010308003":
            if not is_lords_of_dread:
                return
            unit.special_rules["enhancement_lords_blade_of_celerity"] = True
            unit.special_rules["bearer_unit_assault_ranged"] = True
            unit.special_rules["enhancement_fight_first_once_per_battle"] = True
            unit.special_rules["enhancement_lords_blade_of_celerity_source"] = (
                str(getattr(self, "name", "") or "Blade of Celerity").strip() or "Blade of Celerity"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_lords_blade_of_celerity_bearer_model_id"] = bearer_id

        if name == "warp-borne stalker" or enh_id == "000010308004":
            if not is_lords_of_dread:
                return
            unit.special_rules["enhancement_warp_borne_stalker"] = True
            unit.special_rules["bearer_unit_deep_strike"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            once_key = str(params.get("once_per_battle_key", "warp_borne_stalker") or "warp_borne_stalker").strip().lower()
            if not once_key:
                once_key = "warp_borne_stalker"
            unit.special_rules["enhancement_warp_borne_stalker_once_key"] = once_key
            unit.special_rules["enhancement_warp_borne_stalker_source"] = (
                str(getattr(self, "name", "") or "Warp-borne Stalker").strip() or "Warp-borne Stalker"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_warp_borne_stalker_bearer_model_id"] = bearer_id
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("deep_strike", None)
                cache.pop("opponent_turn_strategic_reserves_ability", None)

        if name == "putrid carapace" or enh_id == "000010308005":
            if not is_lords_of_dread:
                return
            unit.special_rules["enhancement_putrid_carapace"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            save_value = _coerce_int(params.get("save_characteristic", 2) or 2, default=2)
            unit.special_rules["enhancement_putrid_carapace_save_characteristic"] = int(max(2, min(7, save_value)))
            once_key = str(params.get("once_per_battle_key", "putrid_carapace") or "putrid_carapace").strip().lower()
            if not once_key:
                once_key = "putrid_carapace"
            unit.special_rules["enhancement_putrid_carapace_once_key"] = once_key
            unit.special_rules["enhancement_putrid_carapace_source"] = (
                str(getattr(self, "name", "") or "Putrid Carapace").strip() or "Putrid Carapace"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_putrid_carapace_bearer_model_id"] = bearer_id

        if name == "mirror of fates" or enh_id == "000010308006":
            if not is_lords_of_dread:
                return
            unit.special_rules["enhancement_mirror_of_fates"] = True
            unit.special_rules["enhancement_mirror_of_fates_free_command_reroll_once_per_battle_round"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            aura_range = _coerce_int(params.get("aura_range", 12) or params.get("range", 12), default=12)
            cp_increase = _coerce_int(params.get("cp_increase", 1) or 1, default=1)
            ability_name = str(params.get("ability_name", "Lord of Deceit (Aura)") or "Lord of Deceit (Aura)").strip()
            if not ability_name:
                ability_name = "Lord of Deceit (Aura)"
            unit.special_rules["enhancement_mirror_of_fates_range"] = int(max(1, aura_range))
            unit.special_rules["enhancement_mirror_of_fates_cp_increase"] = int(max(1, cp_increase))
            unit.special_rules["enhancement_mirror_of_fates_source"] = (
                str(getattr(self, "name", "") or "Mirror of Fates").strip() or "Mirror of Fates"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_mirror_of_fates_bearer_model_id"] = bearer_id
            spec = {
                "range": int(max(1, aura_range)),
                "keyword": "",
                "name": ability_name,
                "description": str(getattr(self, "description", "") or ""),
                "optional": False,
                "limit": "",
                "max_cp": None,
                "cp_increase": int(max(1, cp_increase)),
                "usage_key": "STRATAGEM_CP_INCREASE:MIRROR_OF_FATES",
            }
            if bearer_id:
                spec["source_model_id"] = bearer_id
            existing_specs = list(unit.special_rules.get("stratagem_target_cp_increase_aura", []) or [])
            deduped_specs: list[dict] = []
            seen_spec_keys: set[tuple[str, str]] = set()
            for existing_spec in existing_specs + [spec]:
                if not isinstance(existing_spec, dict):
                    continue
                key = (
                    str(existing_spec.get("usage_key", "") or "").strip().upper(),
                    str(existing_spec.get("source_model_id", "") or "").strip().lower(),
                )
                if key in seen_spec_keys:
                    continue
                seen_spec_keys.add(key)
                deduped_specs.append(existing_spec)
            unit.special_rules["stratagem_target_cp_increase_aura"] = deduped_specs

        if name == "blessing of the dark master" or enh_id == "000010308007":
            if not is_lords_of_dread:
                return
            unit.special_rules["enhancement_blessing_of_the_dark_master"] = True
            unit.special_rules["enhancement_blessing_of_the_dark_master_stealth"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            usage = str(params.get("damage_zero_usage", "battle") or "battle").strip().lower()
            if usage not in {"battle", "battle_round"}:
                usage = "battle"
            unit.special_rules["enhancement_blessing_of_the_dark_master_damage_zero_usage"] = usage
            unit.special_rules["enhancement_blessing_of_the_dark_master_source"] = (
                str(getattr(self, "name", "") or "Blessing of the Dark Master").strip() or "Blessing of the Dark Master"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_blessing_of_the_dark_master_bearer_model_id"] = bearer_id
            cache = getattr(unit, "_ability_cache", None)
            if isinstance(cache, dict):
                cache.pop("stealth", None)
                for cache_key in list(cache.keys()):
                    if str(cache_key).startswith("model_allocated_damage_zero_specs:"):
                        cache.pop(cache_key, None)

        if name == "vengeful tread" or enh_id == "000010497005":
            if not is_gate_warden_lance:
                return
            unit.special_rules["enhancement_vengeful_tread"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            usage_key = str(
                params.get("once_per_turn_key", "VENGEFUL_TREAD_TANK_SHOCK") or "VENGEFUL_TREAD_TANK_SHOCK"
            ).strip().upper()
            if not usage_key:
                usage_key = "VENGEFUL_TREAD_TANK_SHOCK"
            configured_stratagems = tuple(
                str(v or "").strip().upper()
                for v in tuple(params.get("stratagem_names", ("TANK SHOCK",)) or ("TANK SHOCK",))
                if str(v or "").strip()
            )
            if not configured_stratagems:
                configured_stratagems = ("TANK SHOCK",)
            source_name = str(getattr(desc, "name", "") or "Vengeful Tread").strip() or "Vengeful Tread"
            unit.special_rules["enhancement_vengeful_tread_usage_key"] = usage_key
            unit.special_rules["enhancement_vengeful_tread_stratagems"] = configured_stratagems
            unit.special_rules["enhancement_vengeful_tread_source"] = source_name
            unit.special_rules["enhancement_vengeful_tread_requires_bearer_on_battlefield"] = bool(
                params.get("requires_bearer_on_battlefield", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "martial tuition" or enh_id == "000010506005":
            if not is_spearhead_at_arms:
                return
            unit.special_rules["enhancement_martial_tuition"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            usage_key = str(
                params.get("once_per_turn_key", "MARTIAL_TUITION_COUNTER_OFFENSIVE")
                or "MARTIAL_TUITION_COUNTER_OFFENSIVE"
            ).strip().upper()
            if not usage_key:
                usage_key = "MARTIAL_TUITION_COUNTER_OFFENSIVE"
            configured_stratagems = tuple(
                str(v or "").strip().upper()
                for v in tuple(
                    params.get("stratagem_names", ("COUNTER-OFFENSIVE",))
                    or ("COUNTER-OFFENSIVE",)
                )
                if str(v or "").strip()
            )
            if not configured_stratagems:
                configured_stratagems = ("COUNTER-OFFENSIVE",)
            required_keyword = str(params.get("required_target_keyword", "ARMIGER") or "ARMIGER").strip().upper()
            if not required_keyword:
                required_keyword = "ARMIGER"
            min_targets = _coerce_int(params.get("required_min_bondsman_targets", 2) or 2, default=2)
            source_name = str(getattr(desc, "name", "") or "Martial Tuition").strip() or "Martial Tuition"
            unit.special_rules["enhancement_martial_tuition_usage_key"] = usage_key
            unit.special_rules["enhancement_martial_tuition_stratagems"] = configured_stratagems
            unit.special_rules["enhancement_martial_tuition_required_target_keyword"] = required_keyword
            unit.special_rules["enhancement_martial_tuition_required_min_bondsman_targets"] = int(max(1, min_targets))
            unit.special_rules["enhancement_martial_tuition_source"] = source_name
            unit.special_rules["enhancement_martial_tuition_requires_bearer_on_battlefield"] = bool(
                params.get("requires_bearer_on_battlefield", True)
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "bearer of the iron chalice" or enh_id == "000010493002":
            if not is_valourstrike_lance:
                return
            unit.special_rules["enhancement_iron_chalice"] = True
            unit.special_rules["enhancement_iron_chalice_range"] = 12
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "bearer of the evanescent ion" or enh_id == "000010493003":
            if not is_valourstrike_lance:
                return
            unit.special_rules["enhancement_evanescent_ion"] = True
            unit.special_rules["enhancement_evanescent_ion_range"] = 12
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "bearer of the judicant's helm" or enh_id == "000010493004":
            if not is_valourstrike_lance:
                return
            unit.special_rules["enhancement_judicants_helm"] = True
            unit.special_rules["enhancement_judicants_helm_range"] = 12
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "bearer of the lancer's sigil" or enh_id == "000010493005":
            if not is_valourstrike_lance:
                return
            unit.special_rules["enhancement_lancers_sigil"] = True
            unit.special_rules["enhancement_lancers_sigil_range"] = 12
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "mandulian reliquary" or enh_id == "000009777002":
            if not is_warpbane_task_force:
                return
            unit.special_rules["enhancement_mandulian_reliquary"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "radiant champion" or enh_id == "000009777003":
            if not is_warpbane_task_force:
                return
            unit.special_rules["enhancement_radiant_champion"] = True
            unit.special_rules["enhancement_bearer_melee_precision"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "phial of the abyss" or enh_id == "000009777004":
            if not is_warpbane_task_force:
                return
            unit.special_rules["enhancement_phial_of_the_abyss"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "paragon of sanctity" or enh_id == "000009777005":
            if not is_warpbane_task_force:
                return
            unit.special_rules["enhancement_paragon_of_sanctity"] = True
            unit.special_rules["enhancement_paragon_of_sanctity_once_key"] = "paragon_of_sanctity"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "tome of forbidden ways" or enh_id == "000010348005":
            if not is_brotherhood_strike:
                return
            unit.special_rules["enhancement_tome_of_forbidden_ways"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            additional_max_units = _coerce_int(params.get("additional_max_units", 1) or 1, default=1)
            unit.special_rules["enhancement_tome_of_forbidden_ways_additional_max_units"] = int(
                max(0, additional_max_units)
            )
            unit.special_rules["enhancement_tome_of_forbidden_ways_requires_bearer_on_battlefield_or_strategic_reserves"] = bool(
                params.get("requires_bearer_on_battlefield_or_strategic_reserves", True)
            )
            unit.special_rules["enhancement_tome_of_forbidden_ways_source"] = "Tome of Forbidden Ways"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_tome_of_forbidden_ways_bearer_model_id"] = bearer_id

        if name == "a foot in the future" or enh_id == "000010364004":
            if not is_augurium_task_force:
                return
            unit.special_rules["enhancement_a_foot_in_the_future"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            move_roll = str(params.get("move_roll", "D6") or "D6").strip().upper()
            if not move_roll:
                move_roll = "D6"
            unit.special_rules["enhancement_a_foot_in_the_future_move_roll"] = move_roll
            unit.special_rules["enhancement_a_foot_in_the_future_no_charge_this_turn"] = bool(
                params.get("no_charge_this_turn", True)
            )
            unit.special_rules["enhancement_a_foot_in_the_future_requires_bearer_alive"] = bool(
                params.get("requires_bearer_alive", True)
            )
            unit.special_rules["enhancement_a_foot_in_the_future_optional"] = bool(params.get("optional", True))
            unit.special_rules["enhancement_a_foot_in_the_future_source"] = "A Foot in the Future"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_a_foot_in_the_future_bearer_model_id"] = bearer_id

        if name == "eye of the augurium" or enh_id == "000010352002":
            if not is_hallowed_conclave:
                return
            unit.special_rules["enhancement_eye_of_the_augurium"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            stratagems = [
                str(v or "").strip().upper()
                for v in list(
                    params.get("stratagems", ("OVERWATCH", "FIRE OVERWATCH", "HEROIC INTERVENTION")) or ()
                )
                if str(v or "").strip()
            ]
            if stratagems:
                unit.special_rules["enhancement_eye_of_the_augurium_stratagems"] = stratagems
            unit.special_rules["enhancement_eye_of_the_augurium_limit"] = str(
                params.get("limit", "battle_round") or "battle_round"
            ).strip().lower()
            unit.special_rules["enhancement_eye_of_the_augurium_source"] = "Eye of the Augurium"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
                unit.special_rules["enhancement_eye_of_the_augurium_bearer_model_id"] = bearer_id

        invalidate_fn = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate_fn):
            invalidate_fn()
        refresh_fn = getattr(unit, "_refresh_bearer_unit_common_modifiers", None)
        if callable(refresh_fn):
            refresh_fn()

    def is_unit_eligible(self, unit) -> bool:
        if not self.eligibility_keyword_groups and not self.eligibility_name_options:
            return True
        try:
            unit_name = normalize_enhancement_token(getattr(unit, "name", "") or "")
        except Exception:
            unit_name = ""
        if unit_name and unit_name in set(self.eligibility_name_options or ()):
            return True

        keywords = []
        get_effective = getattr(unit, "get_effective_keywords", None)
        if callable(get_effective):
            keywords.extend(list(get_effective() or []))
        else:
            keywords.extend(list(getattr(unit, "keywords", []) or []))
        get_effective_faction = getattr(unit, "get_effective_faction_keywords", None)
        if callable(get_effective_faction):
            keywords.extend(list(get_effective_faction() or []))
        else:
            keywords.extend(list(getattr(unit, "faction_keywords", []) or []))

        norm_keywords = {normalize_enhancement_token(k) for k in keywords if str(k or "").strip()}
        for group in self.eligibility_keyword_groups or ():
            if not group:
                continue
            if set(group).issubset(norm_keywords):
                return True
        return False

    def __str__(self) -> str:
        return f"{self.name} ({self.points}pts) [{self.faction_id} / {self.detachment}]\n{self.description}"
