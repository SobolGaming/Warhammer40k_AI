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


_NORM_CANTICLES_OF_THE_OMNISSIAH_NAME = _norm_name(CANTICLES_OF_THE_OMNISSIAH_NAME)
_ABILITY_NAME_TO_KEY = {
    _norm_name(INVOCATION_OF_MACHINE_VENGEANCE_NAME): KEY_INVOCATION_OF_MACHINE_VENGEANCE,
    _norm_name(MANTRA_OF_DISCIPLINE_NAME): KEY_MANTRA_OF_DISCIPLINE,
    _norm_name(SHROUDPSALM_NAME): KEY_SHROUDPSALM,
}
_VALID_CANTICLES_KEYS = frozenset(_ABILITY_NAME_TO_KEY.values())
_ADEPTUS_MECHANICUS_FACTION_TOKENS = {
    "adm",
    "adeptus mechanicus",
}
_ADEPTUS_MECHANICUS_CACHE_KEY = "adeptus_mechanicus_canticles_faction"


def _keyword_rows(source) -> list[str]:
    rows = []
    for attr in ("faction_keywords", "keywords"):
        rows.extend(str(value or "") for value in list(getattr(source, attr, []) or []))
    return rows


def _unit_is_adeptus_mechanicus(unit) -> bool:
    if unit is None:
        return False
    cache = getattr(unit, "_ability_cache", None)
    if isinstance(cache, dict) and _ADEPTUS_MECHANICUS_CACHE_KEY in cache:
        return bool(cache.get(_ADEPTUS_MECHANICUS_CACHE_KEY))

    result = False
    for attr in ("faction_id", "faction", "faction_name"):
        if _norm_name(str(getattr(unit, attr, "") or "")) in _ADEPTUS_MECHANICUS_FACTION_TOKENS:
            result = True
            break
    if not result:
        for keyword in _keyword_rows(unit):
            if _norm_name(keyword) == "adeptus mechanicus":
                result = True
                break
    if not result:
        for model in list(getattr(unit, "models", []) or []):
            if any(_norm_name(keyword) == "adeptus mechanicus" for keyword in _keyword_rows(model)):
                result = True
                break
    if not result:
        get_army = getattr(unit, "get_parent_army", None)
        if callable(get_army):
            try:
                army = get_army()
            except (AttributeError, RuntimeError, ValueError):
                army = None
            if army is not None:
                for attr in ("faction_id", "faction", "faction_name"):
                    if _norm_name(str(getattr(army, attr, "") or "")) in _ADEPTUS_MECHANICUS_FACTION_TOKENS:
                        result = True
                        break

    if isinstance(cache, dict):
        cache[_ADEPTUS_MECHANICUS_CACHE_KEY] = bool(result)
    else:
        try:
            unit._ability_cache = {_ADEPTUS_MECHANICUS_CACHE_KEY: bool(result)}
        except (AttributeError, TypeError):
            pass
    return bool(result)


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
    return _ABILITY_NAME_TO_KEY.get(_norm_name(name))


def unit_has_canticles_of_the_omnissiah_ability(unit) -> bool:
    if unit is None:
        return False
    if not _unit_is_adeptus_mechanicus(unit):
        return False
    for ability in list(getattr(unit, "possible_abilities", []) or []):
        if _norm_name(getattr(ability, "name", "")) == _NORM_CANTICLES_OF_THE_OMNISSIAH_NAME:
            return True
    return False


def unit_has_canticles_sub_ability(unit) -> bool:
    if unit is None:
        return False
    if not _unit_is_adeptus_mechanicus(unit):
        return False
    for ability in list(getattr(unit, "possible_abilities", []) or []):
        key = ability_name_to_key(getattr(ability, "name", ""))
        if key in _VALID_CANTICLES_KEYS:
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
    if key not in _VALID_CANTICLES_KEYS:
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
    if key_token not in _VALID_CANTICLES_KEYS:
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
