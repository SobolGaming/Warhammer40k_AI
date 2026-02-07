from __future__ import annotations

from typing import Any


class OrksStratagemMixin:
    def _is_war_horde_detachment(self) -> bool:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        mgr = getattr(army, "orks_detachments", None) if army is not None else None
        if mgr is None:
            return False
        return bool(mgr.is_war_horde())

    def _is_orks_unit(self, unit: Any) -> bool:
        if unit is None:
            return False
        get_root = getattr(unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else unit
        if root is None:
            return False
        army = getattr(self.player, "army", None)
        if army is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(root, "parent_army", None)
        if parent_army is not None and parent_army is not army:
            return False
        has_any_kw = getattr(root, "has_any_keyword", None)
        has_orks_kw = bool(has_any_kw("ORKS")) if callable(has_any_kw) else False
        root_faction_id = str(getattr(root, "faction_id", "") or "").strip().upper()
        if not has_orks_kw and root_faction_id != "ORK":
            return False
        return True

    @staticmethod
    def _unit_is_grots(unit: Any) -> bool:
        if unit is None:
            return False
        has_any_keyword = getattr(unit, "has_any_keyword", None)
        if callable(has_any_keyword):
            if has_any_keyword("Grots") or has_any_keyword("Grot") or has_any_keyword("Gretchin"):
                return True
        return False
