from __future__ import annotations

from typing import Optional


TEMPLE_RELICS_NAME = "Temple Relics"
BANNER_OF_THE_EMPEROR_VICTORIOUS_NAME = "Banner of the Emperor Victorious"
COLUMN_FROM_THE_MAJOR_ALTAR_NAME = "Column from the Major Altar"
WATER_FROM_THE_STOUP_OF_ELUCIDATION_NAME = "Water from the Stoup of Elucidation"

KEY_BANNER_OF_THE_EMPEROR_VICTORIOUS = "BANNER_OF_THE_EMPEROR_VICTORIOUS"
KEY_COLUMN_FROM_THE_MAJOR_ALTAR = "COLUMN_FROM_THE_MAJOR_ALTAR"
KEY_WATER_FROM_THE_STOUP_OF_ELUCIDATION = "WATER_FROM_THE_STOUP_OF_ELUCIDATION"

ACTIVE_KEY = "space_marines_temple_relics_selected_mode_key"
ACTIVE_MODE = "space_marines_temple_relics_selected_mode"

MODE_BY_KEY = {
    KEY_BANNER_OF_THE_EMPEROR_VICTORIOUS: "banner_of_the_emperor_victorious",
    KEY_COLUMN_FROM_THE_MAJOR_ALTAR: "column_from_the_major_altar",
    KEY_WATER_FROM_THE_STOUP_OF_ELUCIDATION: "water_from_the_stoup_of_elucidation",
}
KEY_BY_MODE = {value: key for key, value in MODE_BY_KEY.items()}


def _norm_name(text: str) -> str:
    return (text or "").replace("\u2019", "'").replace("\u00e2\u20ac\u2122", "'").strip().lower()


def _resolve_root(unit):
    get_root = getattr(unit, "get_attached_unit_root", None)
    return get_root() if callable(get_root) else unit


def _get_members(unit) -> list:
    root = _resolve_root(unit)
    if root is None:
        return []
    get_members = getattr(root, "get_attached_unit_members", None)
    members = list(get_members() or []) if callable(get_members) else [root]
    return members or [root]


def _invalidate_temple_relics_caches(unit) -> None:
    root = _resolve_root(unit)
    if root is None:
        return
    invalidate = getattr(root, "_invalidate_ability_activity_cache", None)
    if callable(invalidate):
        invalidate()
        return
    cache = getattr(root, "_ability_cache", None)
    if isinstance(cache, dict):
        cache.clear()
        root._ability_cache = cache


def ability_name_to_key(name: str) -> Optional[str]:
    norm = _norm_name(name)
    if norm == _norm_name(BANNER_OF_THE_EMPEROR_VICTORIOUS_NAME):
        return KEY_BANNER_OF_THE_EMPEROR_VICTORIOUS
    if norm == _norm_name(COLUMN_FROM_THE_MAJOR_ALTAR_NAME):
        return KEY_COLUMN_FROM_THE_MAJOR_ALTAR
    if norm == _norm_name(WATER_FROM_THE_STOUP_OF_ELUCIDATION_NAME):
        return KEY_WATER_FROM_THE_STOUP_OF_ELUCIDATION
    return None


def unit_has_temple_relics_ability(unit) -> bool:
    if unit is None:
        return False
    for ability in list(getattr(unit, "possible_abilities", []) or []):
        if _norm_name(getattr(ability, "name", "")) == _norm_name(TEMPLE_RELICS_NAME):
            return True
    return False


def unit_has_temple_relics_sub_ability(unit) -> bool:
    if unit is None:
        return False
    valid_keys = {
        KEY_BANNER_OF_THE_EMPEROR_VICTORIOUS,
        KEY_COLUMN_FROM_THE_MAJOR_ALTAR,
        KEY_WATER_FROM_THE_STOUP_OF_ELUCIDATION,
    }
    for ability in list(getattr(unit, "possible_abilities", []) or []):
        key = ability_name_to_key(getattr(ability, "name", ""))
        if key in valid_keys:
            return True
    return False


def _source_model_alive(unit) -> bool:
    for member in _get_members(unit):
        if member is None:
            continue
        if not (unit_has_temple_relics_ability(member) or unit_has_temple_relics_sub_ability(member)):
            continue
        contains_named = getattr(member, "_unit_contains_model_named", None)
        if callable(contains_named) and bool(contains_named("Grimaldus")):
            return True
    return False


def get_active_temple_relics_key(unit) -> Optional[str]:
    root = _resolve_root(unit)
    if root is None:
        return None
    special_rules = getattr(root, "special_rules", None)
    if not isinstance(special_rules, dict):
        return None
    key = str(special_rules.get(ACTIVE_KEY, "") or "").strip().upper()
    if key not in MODE_BY_KEY:
        return None
    return key


def unit_has_active_temple_relics(unit, key: str) -> bool:
    choice_key = str(key or "").strip().upper()
    if not choice_key or not unit_has_temple_relics_sub_ability(unit):
        return False
    if not _source_model_alive(unit):
        return False
    return get_active_temple_relics_key(unit) == choice_key


def set_active_temple_relics(unit, key: str) -> None:
    root = _resolve_root(unit)
    if root is None:
        return
    key_token = str(key or "").strip().upper()
    mode = MODE_BY_KEY.get(key_token)
    if not mode:
        return
    special_rules = getattr(root, "special_rules", None)
    if not isinstance(special_rules, dict):
        special_rules = {}
    special_rules = dict(special_rules)
    special_rules[ACTIVE_KEY] = key_token
    special_rules[ACTIVE_MODE] = mode
    root.special_rules = special_rules
    _invalidate_temple_relics_caches(root)


def clear_active_temple_relics(unit) -> None:
    root = _resolve_root(unit)
    if root is None:
        return
    special_rules = getattr(root, "special_rules", None)
    if not isinstance(special_rules, dict):
        return
    if ACTIVE_KEY not in special_rules and ACTIVE_MODE not in special_rules:
        return
    special_rules = dict(special_rules)
    special_rules.pop(ACTIVE_KEY, None)
    special_rules.pop(ACTIVE_MODE, None)
    root.special_rules = special_rules
    _invalidate_temple_relics_caches(root)
