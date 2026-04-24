from __future__ import annotations

from collections.abc import Mapping
from typing import List, Optional


def _require_callable(obj, attr_name: str):
    attr = getattr(obj, attr_name, None)
    if not callable(attr):
        raise TypeError(f"Hazardous profile object must provide callable {attr_name}()")
    return attr


def _coerce_roll_value(roll_value: Optional[int]) -> int:
    if roll_value is None:
        raise ValueError("Hazardous roll value is required")
    try:
        base = int(roll_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Hazardous roll value must be an integer D6 result, got {roll_value!r}") from exc
    if base < 1 or base > 6:
        raise ValueError(f"Hazardous roll value must be between 1 and 6, got {base}")
    return base


def hazardous_roll_modifier(profile) -> int:
    """Return the hazardous test roll modifier for a profile (e.g., Overcharge)."""
    if profile is None:
        raise TypeError("Hazardous profile object is required")
    is_overcharge = _require_callable(profile, "is_overcharge")
    if bool(is_overcharge()):
        return -2
    return 0


def apply_hazardous_roll_modifier(profile, roll_value: Optional[int]) -> int:
    """Apply hazardous roll modifiers to a raw D6 roll value."""
    base = _coerce_roll_value(roll_value)
    return int(base + hazardous_roll_modifier(profile))


def hazardous_fail_on_values(profile) -> List[int]:
    """Return the raw die values that fail a hazardous test for this profile."""
    modifier = int(hazardous_roll_modifier(profile) or 0)
    raw_fail_max = int(1 - modifier)
    if raw_fail_max < 1:
        return []
    if raw_fail_max > 6:
        raw_fail_max = 6
    return list(range(1, raw_fail_max + 1))


def is_hazardous_failure(profile, roll_value: Optional[int]) -> bool:
    """Return True if a hazardous test fails after applying modifiers."""
    return apply_hazardous_roll_modifier(profile, roll_value) <= 1


def _iter_models_for_hazardous(root_unit) -> list:
    if root_unit is None:
        raise TypeError("Hazardous eligibility requires a unit")
    get_models = getattr(root_unit, "get_models_for_collision", None)
    if callable(get_models):
        models = get_models()
    elif hasattr(root_unit, "models"):
        models = getattr(root_unit, "models")
    else:
        raise TypeError("Hazardous eligibility unit must expose get_models_for_collision() or models")
    if models is None:
        raise TypeError("Hazardous eligibility unit returned no model collection")
    return list(models)


def _model_is_alive(model) -> bool:
    alive_attr = getattr(model, "is_alive", True)
    if callable(alive_attr):
        return bool(alive_attr())
    return bool(alive_attr)


def _iter_wargear(model) -> list:
    if not hasattr(model, "wargear"):
        raise TypeError(f"Hazardous model {getattr(model, 'name', model)!r} is missing wargear collection")
    wargear = getattr(model, "wargear")
    if wargear is None:
        return []
    return list(wargear)


def _iter_profiles(wargear) -> list:
    profiles = getattr(wargear, "profiles", None)
    if profiles is None:
        raise TypeError(f"Hazardous wargear {getattr(wargear, 'name', wargear)!r} is missing profiles")
    if isinstance(profiles, Mapping):
        return list(profiles.values())
    return list(profiles)


def _wargear_has_hazardous_profile(wargear) -> bool:
    for profile in _iter_profiles(wargear):
        if profile is None:
            raise TypeError(f"Hazardous wargear {getattr(wargear, 'name', wargear)!r} contains a null profile")
        is_hazardous = _require_callable(profile, "is_hazardous")
        if bool(is_hazardous()):
            return True
    return False


def _wargear_matches_mode(wargear, method_name: str) -> bool:
    method = getattr(wargear, method_name, None)
    if not callable(method):
        raise TypeError(f"Hazardous wargear {getattr(wargear, 'name', wargear)!r} must provide {method_name}()")
    return bool(method())

def collect_hazardous_eligible_models(
    root_unit,
    *,
    include_melee_non_character: bool = False,
    include_melee_all: bool = False,
    include_ranged_all: bool = False,
) -> List:
    """Return alive models eligible to suffer Hazardous failures in the given unit."""
    all_models = _iter_models_for_hazardous(root_unit)
    eligible: List = []
    for model in list(all_models or []):
        if not _model_is_alive(model):
            continue
        has_hazardous = False
        for wg in _iter_wargear(model):
            if wg is None:
                raise TypeError(f"Hazardous model {getattr(model, 'name', model)!r} contains null wargear")
            if _wargear_has_hazardous_profile(wg):
                has_hazardous = True
                break
        if not has_hazardous and include_melee_all:
            for wg in _iter_wargear(model):
                if wg is None:
                    raise TypeError(f"Hazardous model {getattr(model, 'name', model)!r} contains null wargear")
                if _wargear_matches_mode(wg, "is_melee"):
                    has_hazardous = True
                    break
        if not has_hazardous and include_melee_non_character and not bool(getattr(model, "is_character", False)):
            for wg in _iter_wargear(model):
                if wg is None:
                    raise TypeError(f"Hazardous model {getattr(model, 'name', model)!r} contains null wargear")
                if _wargear_matches_mode(wg, "is_melee"):
                    has_hazardous = True
                    break
        if not has_hazardous and include_ranged_all:
            for wg in _iter_wargear(model):
                if wg is None:
                    raise TypeError(f"Hazardous model {getattr(model, 'name', model)!r} contains null wargear")
                if _wargear_matches_mode(wg, "is_ranged"):
                    has_hazardous = True
                    break
        if has_hazardous:
            eligible.append(model)
    return eligible
