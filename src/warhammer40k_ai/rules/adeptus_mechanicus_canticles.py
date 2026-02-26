from __future__ import annotations

from typing import Optional


CANTICLES_OF_THE_OMNISSIAH_NAME = "Canticles of the Omnissiah"
INVOCATION_OF_MACHINE_VENGEANCE_NAME = "Invocation of Machine Vengeance"
MANTRA_OF_DISCIPLINE_NAME = "Mantra of Discipline"
SHROUDPSALM_NAME = "Shroudpsalm (Aura)"

KEY_INVOCATION_OF_MACHINE_VENGEANCE = "INVOCATION_OF_MACHINE_VENGEANCE"
KEY_MANTRA_OF_DISCIPLINE = "MANTRA_OF_DISCIPLINE"
KEY_SHROUDPSALM = "SHROUDPSALM"

ACTIVE_KEY = "canticles_of_the_omnissiah_selected_mode_key"


def _norm_name(text: str) -> str:
    return (text or "").replace("\u2019", "'").replace("\u00e2\u20ac\u2122", "'").strip().lower()


def _invalidate_canticles_caches(unit) -> None:
    try:
        root = unit.get_attached_unit_root()
    except Exception:
        root = unit
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
    if norm == _norm_name(INVOCATION_OF_MACHINE_VENGEANCE_NAME):
        return KEY_INVOCATION_OF_MACHINE_VENGEANCE
    if norm == _norm_name(MANTRA_OF_DISCIPLINE_NAME):
        return KEY_MANTRA_OF_DISCIPLINE
    if norm == _norm_name(SHROUDPSALM_NAME):
        return KEY_SHROUDPSALM
    return None


def unit_has_canticles_of_the_omnissiah_ability(unit) -> bool:
    if unit is None:
        return False
    for ability in list(getattr(unit, "possible_abilities", []) or []):
        if _norm_name(getattr(ability, "name", "")) == _norm_name(CANTICLES_OF_THE_OMNISSIAH_NAME):
            return True
    return False


def unit_has_canticles_sub_ability(unit) -> bool:
    if unit is None:
        return False
    valid_keys = {
        KEY_INVOCATION_OF_MACHINE_VENGEANCE,
        KEY_MANTRA_OF_DISCIPLINE,
        KEY_SHROUDPSALM,
    }
    for ability in list(getattr(unit, "possible_abilities", []) or []):
        key = ability_name_to_key(getattr(ability, "name", ""))
        if key in valid_keys:
            return True
    return False


def get_active_canticles_key(unit) -> Optional[str]:
    if unit is None:
        return None
    if not unit_has_canticles_of_the_omnissiah_ability(unit):
        return None
    special_rules = getattr(unit, "special_rules", None)
    if not isinstance(special_rules, dict):
        return None
    key = str(special_rules.get(ACTIVE_KEY, "") or "").strip().upper()
    if key not in {
        KEY_INVOCATION_OF_MACHINE_VENGEANCE,
        KEY_MANTRA_OF_DISCIPLINE,
        KEY_SHROUDPSALM,
    }:
        return None
    return key


def unit_has_active_canticles(unit, key: str) -> bool:
    choice_key = str(key or "").strip().upper()
    if not choice_key:
        return False
    return get_active_canticles_key(unit) == choice_key


def set_active_canticles(unit, key: str) -> None:
    if unit is None or not unit_has_canticles_of_the_omnissiah_ability(unit):
        return
    key_token = str(key or "").strip().upper()
    if key_token not in {
        KEY_INVOCATION_OF_MACHINE_VENGEANCE,
        KEY_MANTRA_OF_DISCIPLINE,
        KEY_SHROUDPSALM,
    }:
        return
    special_rules = getattr(unit, "special_rules", None)
    if not isinstance(special_rules, dict):
        special_rules = {}
    special_rules = dict(special_rules)
    special_rules[ACTIVE_KEY] = key_token
    unit.special_rules = special_rules
    _invalidate_canticles_caches(unit)


def clear_active_canticles(unit) -> None:
    if unit is None:
        return
    special_rules = getattr(unit, "special_rules", None)
    if not isinstance(special_rules, dict):
        return
    if ACTIVE_KEY not in special_rules:
        return
    special_rules = dict(special_rules)
    special_rules.pop(ACTIVE_KEY, None)
    unit.special_rules = special_rules
    _invalidate_canticles_caches(unit)
