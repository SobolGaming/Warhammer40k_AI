from __future__ import annotations

from typing import Optional

from ..utility.entity_ids import get_entity_id


ROD_OF_THE_WAR_FORGE_NAME = "Rod of the War Forge"
FANATICAL_DEVOTION_NAME = "Fanatical Devotion"
ADAPTIVE_TACTICS_NAME = "Adaptive Tactics"
THE_FIRES_OF_MARS_NAME = "The Fires of Mars"

MODE_FANATICAL_DEVOTION = "fanatical_devotion"
MODE_ADAPTIVE_TACTICS = "adaptive_tactics"
MODE_THE_FIRES_OF_MARS = "the_fires_of_mars"

MODE_KEY_FANATICAL_DEVOTION = "FANATICAL_DEVOTION"
MODE_KEY_ADAPTIVE_TACTICS = "ADAPTIVE_TACTICS"
MODE_KEY_THE_FIRES_OF_MARS = "THE_FIRES_OF_MARS"

ACTIVE_MODE_KEY = "thulia_ghuld_rod_of_the_war_forge_selected_mode"
ACTIVE_MODE_TOKEN_KEY = "thulia_ghuld_rod_of_the_war_forge_selected_mode_key"
ACTIVE_TARGET_UNIT_ID_KEY = "thulia_ghuld_icon_of_war_target_unit_id"

FANATICAL_DEVOTION_ACTIVE_KEY = "thulia_ghuld_fanatical_devotion_active"
ADAPTIVE_TACTICS_ACTIVE_KEY = "thulia_ghuld_adaptive_tactics_active"
THE_FIRES_OF_MARS_ACTIVE_KEY = "thulia_ghuld_fires_of_mars_active"


MODE_TO_KEY = {
    MODE_FANATICAL_DEVOTION: MODE_KEY_FANATICAL_DEVOTION,
    MODE_ADAPTIVE_TACTICS: MODE_KEY_ADAPTIVE_TACTICS,
    MODE_THE_FIRES_OF_MARS: MODE_KEY_THE_FIRES_OF_MARS,
}

MODE_TO_NAME = {
    MODE_FANATICAL_DEVOTION: FANATICAL_DEVOTION_NAME,
    MODE_ADAPTIVE_TACTICS: ADAPTIVE_TACTICS_NAME,
    MODE_THE_FIRES_OF_MARS: THE_FIRES_OF_MARS_NAME,
}

_EFFECT_PREFIXES = (
    "thulia_ghuld_fanatical_devotion",
    "thulia_ghuld_adaptive_tactics",
    "thulia_ghuld_fires_of_mars",
)


def _norm_name(text: str) -> str:
    return (text or "").replace("\u2019", "'").replace("\u00e2\u20ac\u2122", "'").strip().lower()


def _attached_root(unit):
    if unit is None:
        return None
    get_root = getattr(unit, "get_attached_unit_root", None)
    return get_root() if callable(get_root) else unit


def _attached_members(unit) -> list:
    root = _attached_root(unit)
    if root is None:
        return []
    get_members = getattr(root, "get_attached_unit_members", None)
    members = list(get_members() or []) if callable(get_members) else [root]
    if not members:
        members = [root]
    deduped: list = []
    seen: set[str] = set()
    for member in list(members or []):
        if member is None:
            continue
        member_id = str(get_entity_id(member) or "")
        if member_id and member_id in seen:
            continue
        if member_id:
            seen.add(member_id)
        deduped.append(member)
    return deduped


def _invalidate_activity_cache(unit) -> None:
    if unit is None:
        return
    invalidate = getattr(unit, "_invalidate_ability_activity_cache", None)
    if callable(invalidate):
        invalidate()
        return
    cache = getattr(unit, "_ability_cache", None)
    if isinstance(cache, dict):
        cache.clear()


def _member_has_named_ability(member, ability_name: str) -> bool:
    target = _norm_name(ability_name)
    if not target or member is None:
        return False
    for ability in list(getattr(member, "possible_abilities", []) or []):
        if _norm_name(getattr(ability, "name", "")) == target:
            return True
    return False


def _root_or_member_has_keyword(unit, keyword: str) -> bool:
    root = _attached_root(unit)
    key = str(keyword or "").strip()
    if root is None or not key:
        return False
    has_any_keyword = getattr(root, "has_any_keyword", None)
    if callable(has_any_keyword) and bool(has_any_keyword(key)):
        return True
    for member in _attached_members(root):
        has_any_keyword = getattr(member, "has_any_keyword", None)
        if callable(has_any_keyword) and bool(has_any_keyword(key)):
            return True
    return False


def unit_has_rod_of_the_war_forge_ability(unit) -> bool:
    return get_rod_of_the_war_forge_source_unit(unit) is not None


def get_rod_of_the_war_forge_source_unit(unit):
    for member in _attached_members(unit):
        if _member_has_named_ability(member, ROD_OF_THE_WAR_FORGE_NAME):
            return member
    return None


def get_rod_of_the_war_forge_source_model(unit):
    source_unit = get_rod_of_the_war_forge_source_unit(unit)
    if source_unit is None:
        return None
    models = list(getattr(source_unit, "models", []) or [])
    models.sort(key=lambda model: str(get_entity_id(model) or ""))
    for model in list(models or []):
        alive = getattr(model, "is_alive", True)
        if bool(alive() if callable(alive) else alive):
            return model
    return None


def unit_matches_icon_of_war_target(unit) -> bool:
    root = _attached_root(unit)
    if root is None:
        return False
    return _root_or_member_has_keyword(root, "SKITARII") or _root_or_member_has_keyword(root, "THULIA GHULD")


def get_active_rod_of_the_war_forge_mode(unit) -> str:
    root = _attached_root(unit)
    if root is None or not unit_has_rod_of_the_war_forge_ability(root):
        return ""
    special_rules = getattr(root, "special_rules", None)
    if not isinstance(special_rules, dict):
        return ""
    mode = str(special_rules.get(ACTIVE_MODE_KEY, "") or "").strip().lower()
    if mode not in MODE_TO_KEY:
        return ""
    return mode


def set_active_rod_of_the_war_forge_mode(unit, mode: str) -> bool:
    root = _attached_root(unit)
    mode_key = MODE_TO_KEY.get(str(mode or "").strip().lower())
    if root is None or not mode_key:
        return False
    special_rules = getattr(root, "special_rules", None)
    if not isinstance(special_rules, dict):
        special_rules = {}
    updated = dict(special_rules)
    updated[ACTIVE_MODE_KEY] = str(mode).strip().lower()
    updated[ACTIVE_MODE_TOKEN_KEY] = str(mode_key)
    updated.pop(ACTIVE_TARGET_UNIT_ID_KEY, None)
    root.special_rules = updated
    _invalidate_activity_cache(root)
    return True


def clear_active_rod_of_the_war_forge_mode(unit) -> None:
    root = _attached_root(unit)
    if root is None:
        return
    special_rules = getattr(root, "special_rules", None)
    if not isinstance(special_rules, dict):
        return
    updated = dict(special_rules)
    changed = False
    for key in (ACTIVE_MODE_KEY, ACTIVE_MODE_TOKEN_KEY, ACTIVE_TARGET_UNIT_ID_KEY):
        if key in updated:
            updated.pop(key, None)
            changed = True
    if changed:
        root.special_rules = updated
        _invalidate_activity_cache(root)


def clear_icon_of_war_effects(unit) -> None:
    root = _attached_root(unit)
    if root is None:
        return
    special_rules = getattr(root, "special_rules", None)
    if not isinstance(special_rules, dict):
        return
    updated = dict(special_rules)
    changed = False
    for prefix in _EFFECT_PREFIXES:
        for suffix in ("_active", "_source", "_source_unit_id"):
            key = f"{prefix}{suffix}"
            if key in updated:
                updated.pop(key, None)
                changed = True
    if changed:
        root.special_rules = updated
        _invalidate_activity_cache(root)


def clear_command_phase_state(unit) -> None:
    clear_active_rod_of_the_war_forge_mode(unit)
    clear_icon_of_war_effects(unit)


def _apply_target_effect(target_unit, *, effect_prefix: str, source_unit, source_name: str) -> dict:
    target_root = _attached_root(target_unit)
    source_root = _attached_root(source_unit)
    if target_root is None or source_root is None:
        return {}
    updated = dict(getattr(target_root, "special_rules", None) or {})
    updated[f"{effect_prefix}_active"] = True
    updated[f"{effect_prefix}_source"] = str(source_name or "").strip()
    updated[f"{effect_prefix}_source_unit_id"] = str(get_entity_id(source_root) or "")
    target_root.special_rules = updated
    _invalidate_activity_cache(target_root)
    source_rules = dict(getattr(source_root, "special_rules", None) or {})
    source_rules[ACTIVE_TARGET_UNIT_ID_KEY] = str(get_entity_id(target_root) or "")
    source_root.special_rules = source_rules
    _invalidate_activity_cache(source_root)
    return {
        "source_unit_id": str(get_entity_id(source_root) or ""),
        "target_unit_id": str(get_entity_id(target_root) or ""),
        "source": str(source_name or "").strip(),
    }


def apply_fanatical_devotion(source_unit, target_unit) -> dict:
    return _apply_target_effect(
        target_unit,
        effect_prefix="thulia_ghuld_fanatical_devotion",
        source_unit=source_unit,
        source_name=FANATICAL_DEVOTION_NAME,
    )


def apply_adaptive_tactics(source_unit, target_unit) -> dict:
    return _apply_target_effect(
        target_unit,
        effect_prefix="thulia_ghuld_adaptive_tactics",
        source_unit=source_unit,
        source_name=ADAPTIVE_TACTICS_NAME,
    )


def apply_the_fires_of_mars(source_unit, target_unit) -> dict:
    return _apply_target_effect(
        target_unit,
        effect_prefix="thulia_ghuld_fires_of_mars",
        source_unit=source_unit,
        source_name=THE_FIRES_OF_MARS_NAME,
    )


def fanatical_devotion_applies(unit) -> bool:
    root = _attached_root(unit)
    special_rules = getattr(root, "special_rules", None)
    return bool(isinstance(special_rules, dict) and special_rules.get(FANATICAL_DEVOTION_ACTIVE_KEY, False))


def adaptive_tactics_applies(unit) -> bool:
    root = _attached_root(unit)
    special_rules = getattr(root, "special_rules", None)
    return bool(isinstance(special_rules, dict) and special_rules.get(ADAPTIVE_TACTICS_ACTIVE_KEY, False))


def the_fires_of_mars_applies(unit) -> bool:
    root = _attached_root(unit)
    special_rules = getattr(root, "special_rules", None)
    return bool(isinstance(special_rules, dict) and special_rules.get(THE_FIRES_OF_MARS_ACTIVE_KEY, False))


def mode_name(mode: str) -> str:
    return str(MODE_TO_NAME.get(str(mode or "").strip().lower(), "") or "")


def mode_label(mode: str) -> str:
    name = mode_name(mode)
    return name or str(mode or "").strip().replace("_", " ").title()


def mode_from_ability_name(ability_name: str) -> str:
    target = _norm_name(ability_name)
    for mode, name in MODE_TO_NAME.items():
        if _norm_name(name) == target:
            return mode
    return ""
