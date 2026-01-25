from __future__ import annotations

from typing import List, Optional


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
