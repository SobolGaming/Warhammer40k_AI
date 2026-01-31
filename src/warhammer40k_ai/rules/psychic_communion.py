from __future__ import annotations

import re
from typing import Iterable, Optional

from ..utility.aura_utils import _model_is_alive, _unit_is_alive, distance_between_models_bases_3d

ABILITY_NAME = "Psychic Communion"
RANGE_INCHES = 6.0
MAX_BONUS = 2


def _strip_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", " ", text)


def _norm_name(text: str) -> str:
    t = str(text or "").replace("\u2019", "'")
    t = t.lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _norm_rules_text(text: str) -> str:
    t = str(text or "")
    t = t.replace("\u2019", "'")
    t = t.replace("\u2013", "-").replace("\u2014", "-")
    t = _strip_html(t)
    t = t.lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _unit_on_battlefield(unit) -> bool:
    if unit is None:
        return False
    if not _unit_is_alive(unit):
        return False
    get_root = getattr(unit, "get_attached_unit_root", None)
    root = get_root() if callable(get_root) else unit
    is_active = getattr(root, "is_active_for_rules", None)
    if callable(is_active):
        return bool(is_active())
    if not bool(getattr(root, "deployed", True)):
        return False
    if str(getattr(root, "reserve_status", "deployed") or "deployed") != "deployed":
        return False
    if bool(getattr(root, "is_embarked", False)):
        return False
    if getattr(root, "embarked_in", None) is not None:
        return False
    return True


def _iter_active_unit_abilities(unit) -> Iterable[object]:
    if unit is None:
        return []
    iter_fn = getattr(unit, "_iter_active_possible_abilities", None)
    if callable(iter_fn):
        return iter_fn()
    return list(getattr(unit, "possible_abilities", []) or [])


def _model_has_keyword(model, keyword: str) -> bool:
    if model is None:
        return False
    kw = str(keyword or "").strip().lower()
    if not kw:
        return False
    keys = []
    try:
        keys.extend(list(getattr(model, "keywords", []) or []))
    except Exception:
        pass
    try:
        keys.extend(list(getattr(model, "faction_keywords", []) or []))
    except Exception:
        pass
    return kw in {str(k or "").strip().lower() for k in keys if str(k or "").strip()}


def _entry_psychic_communion_variant(name: str, desc: str) -> Optional[str]:
    name_norm = _norm_name(name)
    desc_norm = _norm_rules_text(desc)
    if name_norm and "psychic communion" not in name_norm:
        if "psychic communion" not in desc_norm:
            return None
    if "selected to shoot" not in desc_norm:
        return None
    if "destructor weapon" not in desc_norm:
        return None
    if "aeldari psyker model" not in desc_norm:
        return None
    if "attacks and strength" not in desc_norm:
        return None
    if "warlock model in this unit" in desc_norm:
        return "unit"
    if "this model is selected to shoot" in desc_norm:
        return "model"
    return None


def unit_has_psychic_communion(unit) -> bool:
    return psychic_communion_variant(unit) is not None


def psychic_communion_variant(unit) -> Optional[str]:
    if unit is None:
        return None
    cache = getattr(unit, "_ability_cache", None)
    if isinstance(cache, dict) and "psychic_communion_variant" in cache:
        return cache["psychic_communion_variant"]

    variant = None
    for ab in _iter_active_unit_abilities(unit):
        name = ""
        desc = ""
        if isinstance(ab, str):
            name = ab
        else:
            name = str(getattr(ab, "name", "") or "")
            desc = str(getattr(ab, "description", "") or "")
        variant = _entry_psychic_communion_variant(name, desc)
        if variant == "unit":
            break

    if isinstance(cache, dict):
        cache["psychic_communion_variant"] = variant
    return variant


def model_has_psychic_communion(unit, model) -> bool:
    if unit is None or model is None:
        return False
    cache = getattr(unit, "_ability_cache", None)
    key = f"psychic_communion_model:{getattr(model, 'id', '')}"
    if isinstance(cache, dict) and key in cache:
        return bool(cache[key])

    found = False
    iter_fn = getattr(unit, "_iter_model_specific_ability_entries", None)
    if callable(iter_fn):
        for name, desc in iter_fn(model):
            if _entry_psychic_communion_variant(name, desc) == "model":
                found = True
                break

    if isinstance(cache, dict):
        cache[key] = bool(found)
    return bool(found)


def _iter_unit_models(unit, *, use_attached: bool) -> list:
    if unit is None:
        return []
    if use_attached:
        get_models = getattr(unit, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(unit, "models", []) or [])
    else:
        models = list(getattr(unit, "models", []) or [])
    return [m for m in models if _model_is_alive(m)]


def _iter_friendly_psyker_models(army) -> Iterable[object]:
    if army is None:
        return []
    units = list(getattr(army, "units", []) or [])
    for unit in units:
        if unit is None:
            continue
        if not _unit_on_battlefield(unit):
            continue
        for model in _iter_unit_models(unit, use_attached=False):
            if not _model_has_keyword(model, "AELDARI"):
                continue
            if not _model_has_keyword(model, "PSYKER"):
                continue
            yield model


def _psychic_communion_bonus_for_model(model) -> int:
    if model is None or not _model_is_alive(model):
        return 0
    unit = getattr(model, "parent_unit", None)
    if unit is None or not _unit_on_battlefield(unit):
        return 0
    army = getattr(unit, "get_parent_army", None)
    army = army() if callable(army) else getattr(unit, "parent_army", None)
    if army is None:
        return 0
    count = 0
    for other in _iter_friendly_psyker_models(army):
        if other is None or other is model:
            continue
        try:
            if not _model_is_alive(other):
                continue
        except Exception:
            continue
        if distance_between_models_bases_3d(model, other) <= RANGE_INCHES + 1e-6:
            count += 1
            if count >= MAX_BONUS:
                return MAX_BONUS
    return min(count, MAX_BONUS)


def apply_psychic_communion_on_selected_to_shoot(
    unit,
    *,
    selected_models: Optional[list] = None,
    phase_name: Optional[str] = None,
) -> None:
    if unit is None:
        return
    if selected_models is None:
        selected_models = []
    variant = psychic_communion_variant(unit)
    if variant is None and not selected_models:
        return

    if not phase_name:
        try:
            game = getattr(getattr(unit.get_parent_army(), "player", None), "game", None)
            phase = getattr(game, "phase", None)
            phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        except Exception:
            phase_name = ""
    if not phase_name:
        phase_name = "SHOOTING_PHASE"

    weapon_name = "Destructor"
    source = "Psychic Communion"

    if variant == "unit":
        models_to_apply = []
        for m in _iter_unit_models(unit, use_attached=True):
            if not _model_has_keyword(m, "WARLOCK"):
                continue
            models_to_apply.append(m)
    else:
        models_to_apply = []
        for m in list(selected_models or []):
            if m is None or not _model_is_alive(m):
                continue
            if not model_has_psychic_communion(unit, m):
                continue
            models_to_apply.append(m)

    if not models_to_apply:
        return

    for m in models_to_apply:
        key = f"psychic_communion:{getattr(m, 'id', '')}"
        try:
            bonus = int(_psychic_communion_bonus_for_model(m) or 0)
        except Exception:
            bonus = 0
        apply_fn = getattr(m, "set_temporary_weapon_bonus", None)
        if callable(apply_fn):
            apply_fn(
                key=key,
                weapon_name=weapon_name,
                attacks_bonus=bonus,
                strength_bonus=bonus,
                source=source,
                expires_phase=phase_name,
            )
