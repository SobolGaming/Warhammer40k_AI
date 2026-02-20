from __future__ import annotations

import re
from typing import Iterable, Optional

from ..utility.aura_utils import _model_is_alive, _unit_is_alive, distance_between_models_bases_3d
from ..utility.entity_ids import get_entity_id

ABILITY_NAME = "Psychic Guidance"
RANGE_INCHES = 12.0

_MODEL_RULE_TEXT = (
    'While this model is within 12" of one or more friendly Aeldari Psyker models, '
    "improve the Ballistic Skill and Weapon Skill characteristics of weapons equipped by this model by 1 "
    "and it has a Leadership characteristic of 6+."
)
_UNIT_RULE_TEXT = (
    'While this unit is within 12" of one or more friendly Aeldari Psyker models, '
    "models in this unit have a Leadership characteristic of 6+ and each time a model in this unit makes "
    "an attack, add 1 to the Hit roll."
)


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


_ABILITY_NAME_NORM = _norm_name(ABILITY_NAME)
_MODEL_RULE_NORM = _norm_rules_text(_MODEL_RULE_TEXT)
_UNIT_RULE_NORM = _norm_rules_text(_UNIT_RULE_TEXT)


def _iter_active_unit_abilities(unit) -> Iterable[object]:
    if unit is None:
        return []
    iter_fn = getattr(unit, "_iter_active_possible_abilities", None)
    if callable(iter_fn):
        return iter_fn()
    return list(getattr(unit, "possible_abilities", []) or [])


def _unit_has_keyword_local(unit, keyword: str) -> bool:
    if unit is None:
        return False
    kw = str(keyword or "").strip()
    if not kw:
        return False
    fn = getattr(unit, "has_any_keyword_local", None)
    if callable(fn):
        return bool(fn(kw))
    fn = getattr(unit, "has_any_keyword", None)
    if callable(fn):
        return bool(fn(kw))
    raw = [str(k or "") for k in (getattr(unit, "keywords", []) or [])]
    raw += [str(k or "") for k in (getattr(unit, "faction_keywords", []) or [])]
    return kw.lower() in {k.lower() for k in raw if str(k).strip()}


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


def _iter_unit_models(unit, *, use_attached: bool) -> list:
    if unit is None:
        return []
    if use_attached:
        get_models = getattr(unit, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(unit, "models", []) or [])
    else:
        models = list(getattr(unit, "models", []) or [])
    return [m for m in models if _model_is_alive(m)]


def _models_within_range(source_models, target_models, range_inches: float) -> bool:
    if not source_models or not target_models:
        return False
    rng = float(range_inches)
    for sm in source_models:
        for tm in target_models:
            if distance_between_models_bases_3d(sm, tm) <= rng + 1e-6:
                return True
    return False


def psychic_guidance_variant(unit) -> Optional[str]:
    if unit is None:
        return None
    cache = getattr(unit, "_ability_cache", None)
    if isinstance(cache, dict) and "psychic_guidance_variant" in cache:
        return cache["psychic_guidance_variant"]

    variant = None
    for ab in _iter_active_unit_abilities(unit):
        name = ""
        desc = ""
        if isinstance(ab, str):
            name = ab
        else:
            name = str(getattr(ab, "name", "") or "")
            desc = str(getattr(ab, "description", "") or "")
        name_norm = _norm_name(name)
        if name_norm and name_norm != _ABILITY_NAME_NORM:
            continue
        desc_norm = _norm_rules_text(desc)
        if desc_norm == _MODEL_RULE_NORM:
            variant = "model"
            break
        if desc_norm == _UNIT_RULE_NORM:
            variant = "unit"
            break

    if isinstance(cache, dict):
        cache["psychic_guidance_variant"] = variant
    return variant


def unit_has_psychic_guidance(unit, *, variant: Optional[str] = None) -> bool:
    found = psychic_guidance_variant(unit)
    if variant is None:
        return found is not None
    return found == variant


def _iter_psyker_sources(army) -> Iterable[object]:
    if army is None:
        return []
    units = list(getattr(army, "units", []) or [])
    out = []
    for unit in units:
        if unit is None:
            continue
        if not _unit_on_battlefield(unit):
            continue
        if not (_unit_has_keyword_local(unit, "AELDARI") and _unit_has_keyword_local(unit, "PSYKER")):
            continue
        out.append(unit)
    return out


def _root_unit(unit):
    if unit is None:
        return None
    get_root = getattr(unit, "get_attached_unit_root", None)
    if callable(get_root):
        return get_root()
    return unit


def _has_active_soul_bridge_link(unit, *, army) -> bool:
    root = _root_unit(unit)
    if root is None or army is None:
        return False
    sr = getattr(root, "special_rules", None)
    if not isinstance(sr, dict):
        return False
    if not bool(sr.get("aeldari_soul_bridge_active")):
        return False
    owner_id = str(sr.get("aeldari_soul_bridge_owner", "") or "")
    player_id = str(getattr(getattr(army, "player", None), "id", "") or "")
    if owner_id and player_id and owner_id != player_id:
        return False
    source_id = str(sr.get("aeldari_soul_bridge_psyker_unit_id", "") or "")
    if not source_id:
        return False
    for candidate in list(getattr(army, "units", []) or []):
        source = _root_unit(candidate)
        if source is None:
            continue
        if str(get_entity_id(source) or "") != source_id:
            continue
        if not _unit_on_battlefield(source):
            continue
        if not (_unit_has_keyword_local(source, "AELDARI") and _unit_has_keyword_local(source, "PSYKER")):
            continue
        return True
    return False


def unit_within_psyker_range(unit, *, range_inches: float = RANGE_INCHES) -> bool:
    if unit is None:
        return False
    if not _unit_on_battlefield(unit):
        return False
    army = getattr(unit, "get_parent_army", None)
    army = army() if callable(army) else getattr(unit, "parent_army", None)
    if army is None:
        return False
    if _has_active_soul_bridge_link(unit, army=army):
        return True
    target_models = _iter_unit_models(unit, use_attached=True)
    if not target_models:
        return False
    for source in _iter_psyker_sources(army):
        source_models = _iter_unit_models(source, use_attached=False)
        if _models_within_range(source_models, target_models, range_inches):
            return True
    return False


def model_within_psyker_range(model, *, range_inches: float = RANGE_INCHES) -> bool:
    if model is None or not _model_is_alive(model):
        return False
    unit = getattr(model, "parent_unit", None)
    if unit is None or not _unit_on_battlefield(unit):
        return False
    army = getattr(unit, "get_parent_army", None)
    army = army() if callable(army) else getattr(unit, "parent_army", None)
    if army is None:
        return False
    if _has_active_soul_bridge_link(unit, army=army):
        return True
    target_models = [model]
    for source in _iter_psyker_sources(army):
        source_models = _iter_unit_models(source, use_attached=False)
        if _models_within_range(source_models, target_models, range_inches):
            return True
    return False


def psychic_guidance_skill_bonus(attacker_model, *, range_inches: float = RANGE_INCHES) -> int:
    if attacker_model is None:
        return 0
    unit = getattr(attacker_model, "parent_unit", None)
    if unit is None:
        return 0
    if psychic_guidance_variant(unit) != "model":
        return 0
    if not model_within_psyker_range(attacker_model, range_inches=range_inches):
        return 0
    return 1


def psychic_guidance_hit_bonus_applies(attacker_unit, *, range_inches: float = RANGE_INCHES) -> bool:
    if attacker_unit is None:
        return False
    if psychic_guidance_variant(attacker_unit) != "unit":
        return False
    return unit_within_psyker_range(attacker_unit, range_inches=range_inches)


def psychic_guidance_leadership_value(model, *, range_inches: float = RANGE_INCHES) -> Optional[int]:
    if model is None:
        return None
    unit = getattr(model, "parent_unit", None)
    if unit is None:
        return None
    variant = psychic_guidance_variant(unit)
    if variant == "model":
        if model_within_psyker_range(model, range_inches=range_inches):
            return 6
        return None
    if variant == "unit":
        if unit_within_psyker_range(unit, range_inches=range_inches):
            return 6
        return None
    return None
