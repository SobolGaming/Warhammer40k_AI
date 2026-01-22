from __future__ import annotations

import re
from typing import Iterable, Optional

from ..utility.aura_utils import _model_is_alive, _unit_is_alive, distance_between_models_bases_3d
from ..utility.entity_ids import maybe_entity_id

ABILITY_KEY = "reverberating_summons"
ABILITY_NAME = "Reverberating Summons"
RANGE_INCHES = 12.0


def _norm_keyword(text: str) -> str:
    val = (text or "").replace("\u2019", "'").lower().strip()
    val = re.sub(r"[^a-z0-9]+", " ", val)
    return re.sub(r"\s+", " ", val).strip()


def weapon_profile_has_reverberating_summons(profile) -> bool:
    if profile is None:
        return False
    get_keywords = getattr(profile, "get_keywords", None)
    if callable(get_keywords):
        keywords = list(get_keywords() or [])
    else:
        keywords = list(getattr(profile, "keywords", []) or [])
    for kw in keywords:
        if _norm_keyword(str(kw)) == "reverberating summons":
            return True
    return False


def _unit_has_plaguebearers_keyword(unit) -> bool:
    if unit is None:
        return False
    show_any = getattr(unit, "has_any_keyword", None)
    if callable(show_any) and show_any("PLAGUEBEARERS"):
        return True
    get_effective = getattr(unit, "get_effective_keywords", None)
    if callable(get_effective):
        keywords = list(get_effective() or [])
    else:
        keywords = list(getattr(unit, "keywords", []) or [])
    return any(str(k).strip().upper() == "PLAGUEBEARERS" for k in keywords)


def _bearer_within_range_of_unit(bearer_model, unit, *, range_inches: float) -> bool:
    if bearer_model is None or unit is None:
        return False
    get_models = getattr(unit, "get_attached_unit_models", None)
    if callable(get_models):
        models = list(get_models() or [])
    else:
        models = list(getattr(unit, "models", []) or [])
    for model in models:
        if not _model_is_alive(model):
            continue
        if float(distance_between_models_bases_3d(bearer_model, model)) <= float(range_inches) + 1e-6:
            return True
    return False


def get_reverberating_summons_candidates(
    bearer_model,
    *,
    game_map,
    units: Optional[Iterable] = None,
    range_inches: float = RANGE_INCHES,
) -> list:
    if bearer_model is None or game_map is None:
        return []
    bearer_unit = getattr(bearer_model, "parent_unit", None)
    if bearer_unit is None:
        return []
    get_army = getattr(bearer_unit, "get_parent_army", None)
    if callable(get_army):
        army = get_army()
    else:
        army = getattr(bearer_unit, "parent_army", None)
    if army is None:
        return []

    pool = list(units) if units is not None else list(getattr(army, "units", []) or [])
    seen: set[str] = set()
    candidates = []
    for unit in pool:
        if unit is None:
            continue
        get_root = getattr(unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else unit
        if root is None:
            continue
        uid = maybe_entity_id(root)
        if uid in seen:
            continue
        if uid:
            seen.add(uid)
        if not _unit_is_alive(root):
            continue
        if not getattr(root, "deployed", True):
            continue
        is_in_reserves = getattr(root, "is_in_reserves", None)
        if callable(is_in_reserves) and is_in_reserves():
            continue
        if bool(getattr(root, "is_embarked", False)):
            continue
        if getattr(root, "embarked_in", None) is not None:
            continue
        get_root_army = getattr(root, "get_parent_army", None)
        root_army = get_root_army() if callable(get_root_army) else getattr(root, "parent_army", None)
        if root_army is not army:
            continue
        if not _unit_has_plaguebearers_keyword(root):
            continue
        destroyed = list(getattr(root, "models_lost", []) or [])
        if not destroyed:
            continue
        if not _bearer_within_range_of_unit(bearer_model, root, range_inches=range_inches):
            continue
        candidates.append(root)
    return candidates
