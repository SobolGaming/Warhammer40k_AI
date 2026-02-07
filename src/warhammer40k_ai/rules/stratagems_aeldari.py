from __future__ import annotations

from typing import Any, List

from ..utility.entity_ids import get_entity_id


class AeldariStratagemMixin:
    def _is_warhost_detachment(self) -> bool:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        mgr = getattr(army, "aeldari_detachments", None) if army is not None else None
        if mgr is None:
            return False
        return bool(mgr.is_warhost_detachment())

    def _blitzing_firepower_candidates(self) -> List[Any]:
        if not self._is_warhost_detachment():
            return []
        army = self.player.get_army()
        units = list(getattr(army, "units", []) or []) if army is not None else []
        candidates: List[Any] = []
        seen = set()
        for unit in units:
            if unit is None:
                continue
            root = unit.get_attached_unit_root()
            uid = get_entity_id(root)
            if uid in seen:
                continue
            seen.add(uid)
            if not root.is_alive():
                continue
            if not getattr(root, "deployed", False):
                continue
            if getattr(root, "is_in_reserves", lambda: False)():
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not root.has_any_keyword("ASURYANI"):
                continue
            if getattr(getattr(root, "round_state", None), "shot_this_round", False):
                continue
            candidates.append(root)
        return candidates
