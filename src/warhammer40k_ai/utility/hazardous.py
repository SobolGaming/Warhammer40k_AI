from __future__ import annotations

from typing import List, Optional


def hazardous_roll_modifier(profile) -> int:
    """Return the hazardous test roll modifier for a profile (e.g., Overcharge)."""
    if profile is None:
        return 0
    try:
        if bool(getattr(profile, "is_overcharge", None)) and profile.is_overcharge():
            return -2
    except Exception:
        return 0
    return 0


def apply_hazardous_roll_modifier(profile, roll_value: Optional[int]) -> int:
    """Apply hazardous roll modifiers to a raw D6 roll value."""
    try:
        base = int(roll_value or 0)
    except Exception:
        base = 0
    try:
        return int(base + hazardous_roll_modifier(profile))
    except Exception:
        return int(base)


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
    try:
        return apply_hazardous_roll_modifier(profile, roll_value) <= 1
    except Exception:
        return False

def collect_hazardous_eligible_models(root_unit, *, include_melee_non_character: bool = False) -> List:
    """Return alive models eligible to suffer Hazardous failures in the given unit."""
    if root_unit is None:
        return []
    try:
        all_models = root_unit.get_models_for_collision()
    except Exception:
        all_models = list(getattr(root_unit, "models", []) or [])
    eligible: List = []
    for model in list(all_models or []):
        try:
            if not getattr(model, "is_alive", True):
                continue
        except Exception:
            continue
        has_hazardous = False
        try:
            for wg in (getattr(model, "wargear", []) or []):
                for prof in (getattr(wg, "profiles", {}) or {}).values():
                    if prof is None:
                        continue
                    try:
                        if prof.is_hazardous():
                            has_hazardous = True
                            break
                    except Exception:
                        continue
                if has_hazardous:
                    break
        except Exception:
            has_hazardous = False
        if not has_hazardous and include_melee_non_character and not bool(getattr(model, "is_character", False)):
            try:
                for wg in (getattr(model, "wargear", []) or []):
                    if wg is None:
                        continue
                    try:
                        if wg.is_melee():
                            has_hazardous = True
                            break
                    except Exception:
                        continue
            except Exception:
                has_hazardous = False
        if has_hazardous:
            eligible.append(model)
    return eligible
