from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SectionAbilityOption:
    parent_key: str
    key: str
    parent_name: str
    name: str
    summary: str


KEY_HERO_OF_HADES_HIVE = "HERO_OF_HADES_HIVE"
KEY_COUNTERSTRATEGIST = "COUNTERSTRATEGIST"
KEY_DECISIVE_COMMAND = "DECISIVE_COMMAND"
KEY_INSPIRING_HERO = "INSPIRING_HERO"

KEY_THROTTLEROKKIT_SHOKKA_ENGINE = "THROTTLEROKKIT_SHOKKA_ENGINE"
KEY_TURBO_ENGINE = "TURBO_ENGINE"
KEY_SHOKK_ATTACK_ENGINE = "SHOKK_ATTACK_ENGINE"
KEY_PULSE_JET = "PULSE_JET"


SECTION_OPTIONS: tuple[SectionAbilityOption, ...] = (
    SectionAbilityOption(
        parent_key=KEY_HERO_OF_HADES_HIVE,
        key=KEY_COUNTERSTRATEGIST,
        parent_name="Hero of Hades Hive",
        name="Counterstrategist",
        summary="End of opponent Movement phase reaction against a nearby enemy that moved or was set up.",
    ),
    SectionAbilityOption(
        parent_key=KEY_HERO_OF_HADES_HIVE,
        key=KEY_DECISIVE_COMMAND,
        parent_name="Hero of Hades Hive",
        name="Decisive Command",
        summary="Next Order reaches farther and can splash to another eligible unit.",
    ),
    SectionAbilityOption(
        parent_key=KEY_HERO_OF_HADES_HIVE,
        key=KEY_INSPIRING_HERO,
        parent_name="Hero of Hades Hive",
        name="Inspiring Hero (Aura)",
        summary="Nearby Astra Militarum units re-roll Battle-shock and Leadership tests.",
    ),
    SectionAbilityOption(
        parent_key=KEY_THROTTLEROKKIT_SHOKKA_ENGINE,
        key=KEY_TURBO_ENGINE,
        parent_name="Throttlerokkit Shokka Engine",
        name="Turbo Engine",
        summary="This unit is eligible to declare a charge after it Advanced or Fell Back.",
    ),
    SectionAbilityOption(
        parent_key=KEY_THROTTLEROKKIT_SHOKKA_ENGINE,
        key=KEY_SHOKK_ATTACK_ENGINE,
        parent_name="Throttlerokkit Shokka Engine",
        name="Shokk Attack Engine",
        summary="Command phase Strategic Reserves redeploy mode while not within Engagement Range.",
    ),
    SectionAbilityOption(
        parent_key=KEY_THROTTLEROKKIT_SHOKKA_ENGINE,
        key=KEY_PULSE_JET,
        parent_name="Throttlerokkit Shokka Engine",
        name="Pulse Jet",
        summary='Advance without rolling, add 6" Move, and move through models and terrain.',
    ),
)

SECTION_OPTIONS_BY_KEY = {option.key: option for option in SECTION_OPTIONS}
SECTION_OPTIONS_BY_PARENT = {
    parent_key: tuple(option for option in SECTION_OPTIONS if option.parent_key == parent_key)
    for parent_key in {option.parent_key for option in SECTION_OPTIONS}
}

_ACTIVE_KEY_BY_PARENT = {
    KEY_HERO_OF_HADES_HIVE: "section_ability_hero_of_hades_hive_active_key",
    KEY_THROTTLEROKKIT_SHOKKA_ENGINE: "section_ability_throttlerokkit_shokka_engine_active_key",
}
_ACTIVE_START_ROUND_BY_PARENT = {
    KEY_HERO_OF_HADES_HIVE: "section_ability_hero_of_hades_hive_start_round",
    KEY_THROTTLEROKKIT_SHOKKA_ENGINE: "section_ability_throttlerokkit_shokka_engine_start_round",
}
_ACTIVE_UNTIL_ROUND_BY_PARENT = {
    KEY_HERO_OF_HADES_HIVE: "section_ability_hero_of_hades_hive_until_round",
    KEY_THROTTLEROKKIT_SHOKKA_ENGINE: "section_ability_throttlerokkit_shokka_engine_until_round",
}
_ACTIVE_OWNER_BY_PARENT = {
    KEY_HERO_OF_HADES_HIVE: "section_ability_hero_of_hades_hive_owner_id",
    KEY_THROTTLEROKKIT_SHOKKA_ENGINE: "section_ability_throttlerokkit_shokka_engine_owner_id",
}


def _norm_name(text: str) -> str:
    return str(text or "").replace("\u2019", "'").strip().lower()


def _ensure_special_rules(unit) -> dict:
    special_rules = getattr(unit, "special_rules", None)
    if not isinstance(special_rules, dict):
        special_rules = {}
    return special_rules


def _invalidate_caches(unit) -> None:
    get_root = getattr(unit, "get_attached_unit_root", None)
    root = get_root() if callable(get_root) else unit
    invalidate = getattr(root, "_invalidate_ability_activity_cache", None)
    if callable(invalidate):
        invalidate()
        return
    cache = getattr(root, "_ability_cache", None)
    if isinstance(cache, dict):
        cache.clear()
        root._ability_cache = cache


def _remove_pulse_jet_move_types(special_rules: dict) -> None:
    added = set(special_rules.get("pulse_jet_added_phase_move_types") or [])
    if added:
        current = [str(item) for item in list(special_rules.get("bearer_unit_phase_move_types") or [])]
        kept = [item for item in current if item not in added]
        if kept:
            special_rules["bearer_unit_phase_move_types"] = kept
        else:
            special_rules.pop("bearer_unit_phase_move_types", None)
    special_rules.pop("pulse_jet_added_phase_move_types", None)


def _apply_pulse_jet_move_types(special_rules: dict) -> None:
    current = set(special_rules.get("bearer_unit_phase_move_types") or [])
    added = [move_type for move_type in ("advance",) if move_type not in current]
    if added:
        current.update(added)
        special_rules["bearer_unit_phase_move_types"] = sorted(current)
        special_rules["pulse_jet_added_phase_move_types"] = added
    else:
        special_rules["pulse_jet_added_phase_move_types"] = []


def ability_name_to_key(name: str) -> Optional[str]:
    normalized = _norm_name(name)
    for option in SECTION_OPTIONS:
        if normalized == _norm_name(option.name):
            return option.key
    return None


def parent_name_to_key(name: str) -> Optional[str]:
    normalized = _norm_name(name)
    for option in SECTION_OPTIONS:
        if normalized == _norm_name(option.parent_name):
            return option.parent_key
    return None


def unit_has_section_parent_ability(unit, parent_key: str) -> bool:
    if unit is None:
        return False
    target_key = str(parent_key or "").strip().upper()
    if target_key not in SECTION_OPTIONS_BY_PARENT:
        return False
    parent_names = {_norm_name(option.parent_name) for option in SECTION_OPTIONS_BY_PARENT[target_key]}
    for ability in list(getattr(unit, "possible_abilities", []) or []):
        if _norm_name(getattr(ability, "name", "")) in parent_names:
            return True
    return False


def unit_has_selectable_section_sub_ability(unit) -> bool:
    if unit is None:
        return False
    valid_keys = set(SECTION_OPTIONS_BY_KEY)
    for ability in list(getattr(unit, "possible_abilities", []) or []):
        if ability_name_to_key(getattr(ability, "name", "")) in valid_keys:
            return True
    return False


def get_active_section_ability_key(unit, parent_key: str, *, battle_round: Optional[int] = None) -> Optional[str]:
    parent = str(parent_key or "").strip().upper()
    active_key_name = _ACTIVE_KEY_BY_PARENT.get(parent)
    if not active_key_name or unit is None:
        return None
    if not unit_has_section_parent_ability(unit, parent):
        return None
    special_rules = getattr(unit, "special_rules", None)
    if not isinstance(special_rules, dict):
        return None
    active = str(special_rules.get(active_key_name, "") or "").strip().upper()
    if not active:
        return None
    option = SECTION_OPTIONS_BY_KEY.get(active)
    if option is None or option.parent_key != parent:
        return None
    until_key = _ACTIVE_UNTIL_ROUND_BY_PARENT.get(parent, "")
    stored_until = special_rules.get(until_key) if until_key else None
    if battle_round is not None and stored_until is not None:
        try:
            if int(battle_round or 0) > int(stored_until or 0):
                return None
        except (TypeError, ValueError):
            return None
    return active


def unit_has_active_section_ability(unit, key: str, *, battle_round: Optional[int] = None) -> bool:
    choice_key = str(key or "").strip().upper()
    option = SECTION_OPTIONS_BY_KEY.get(choice_key)
    if option is None:
        return False
    return get_active_section_ability_key(unit, option.parent_key, battle_round=battle_round) == choice_key


def set_active_section_ability(
    unit,
    key: str,
    *,
    start_round: int,
    expires_round: int,
    player_id: Optional[str] = None,
) -> bool:
    choice_key = str(key or "").strip().upper()
    option = SECTION_OPTIONS_BY_KEY.get(choice_key)
    if option is None or unit is None:
        return False
    if not unit_has_section_parent_ability(unit, option.parent_key):
        return False
    special_rules = _ensure_special_rules(unit)
    if option.parent_key == KEY_THROTTLEROKKIT_SHOKKA_ENGINE:
        _remove_pulse_jet_move_types(special_rules)
    special_rules[_ACTIVE_KEY_BY_PARENT[option.parent_key]] = choice_key
    special_rules[_ACTIVE_START_ROUND_BY_PARENT[option.parent_key]] = int(start_round or 0)
    special_rules[_ACTIVE_UNTIL_ROUND_BY_PARENT[option.parent_key]] = int(expires_round or 0)
    special_rules[_ACTIVE_OWNER_BY_PARENT[option.parent_key]] = str(player_id or "")
    if choice_key == KEY_PULSE_JET:
        _apply_pulse_jet_move_types(special_rules)
    unit.special_rules = special_rules
    _invalidate_caches(unit)
    return True


def clear_active_section_ability(unit, parent_key: str) -> None:
    parent = str(parent_key or "").strip().upper()
    if unit is None or parent not in _ACTIVE_KEY_BY_PARENT:
        return
    special_rules = getattr(unit, "special_rules", None)
    if not isinstance(special_rules, dict):
        return
    if parent == KEY_THROTTLEROKKIT_SHOKKA_ENGINE:
        _remove_pulse_jet_move_types(special_rules)
    for mapping in (
        _ACTIVE_KEY_BY_PARENT,
        _ACTIVE_START_ROUND_BY_PARENT,
        _ACTIVE_UNTIL_ROUND_BY_PARENT,
        _ACTIVE_OWNER_BY_PARENT,
    ):
        key = mapping.get(parent)
        if key:
            special_rules.pop(key, None)
    unit.special_rules = special_rules
    _invalidate_caches(unit)
