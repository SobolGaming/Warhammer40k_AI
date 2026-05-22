from __future__ import annotations

from typing import List

from .aura_utils import distance_between_models_bases_3d
from .unit_models import alive_unit_group_models


def compute_embark_candidates(transport_unit, game_map) -> List[object]:
    """Return friendly units that can embark into the given transport right now."""
    if transport_unit is None or not getattr(transport_unit, "is_transport", False):
        return []
    if game_map is None:
        return []
    transport_models = alive_unit_group_models(transport_unit, include_pending=False)
    if not transport_models:
        return []
    t_model = transport_models[0]

    candidates = []
    for unit in list(getattr(game_map, "units", []) or []):
        if unit is None or unit == transport_unit:
            continue
        if not unit.is_alive():
            continue
        if unit.get_parent_army() != transport_unit.get_parent_army():
            continue
        if not transport_unit.can_transport(unit):
            continue
        if getattr(unit.round_state, "remained_stationary_this_round", False):
            continue
        if (
            getattr(unit.round_state, "reinforced_this_round", False)
            and not getattr(unit.round_state, "moved_this_round", False)
            and not getattr(unit.round_state, "advanced_this_round", False)
            and not getattr(unit.round_state, "fell_back_this_round", False)
        ):
            continue
        if getattr(unit.round_state, "disembarked_this_round", False):
            continue
        ok = True
        for model in alive_unit_group_models(unit, include_pending=False):
            if float(distance_between_models_bases_3d(model, t_model)) > 3.0 + 1e-6:
                ok = False
                break
        if not ok:
            continue
        candidates.append(unit)
    return candidates
