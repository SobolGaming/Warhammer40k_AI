from __future__ import annotations

from .detachment_manager import DetachmentManagerBase


class AstraMilitarumDetachmentManager(DetachmentManagerBase):
    faction_id = "AM"

    def is_grizzled_company(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Grizzled Company")

    def unit_is_astra_militarum(self, unit) -> bool:
        if unit is None:
            return False
        if self._unit_has_keyword(unit, "ASTRA MILITARUM"):
            return True
        has_keywords = bool(getattr(unit, "keywords", None)) or bool(getattr(unit, "faction_keywords", None))
        if has_keywords:
            return False
        return self._army_faction_matches(self.faction_id)

    def unit_is_officer(self, unit) -> bool:
        return self._unit_has_keyword(unit, "OFFICER")

    def _unit_has_order(self, unit) -> bool:
        if unit is None:
            return False
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict) and str(sr.get("voice_of_command_order_key", "") or "").strip():
            return True
        return False

    def _attached_unit_has_order(self, unit) -> bool:
        if unit is None:
            return False
        root = unit
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
        members = None
        get_members = getattr(root, "get_attached_unit_members", None)
        if callable(get_members):
            members = list(get_members() or [])
        if not members:
            members = [root]
        for member in members:
            if self._unit_has_order(member):
                return True
        return False

    def ruthless_discipline_orders_bonus(self, unit) -> int:
        if not self.is_grizzled_company():
            return 0
        if unit is None:
            return 0
        if not self.unit_is_astra_militarum(unit):
            return 0
        if not self.unit_is_officer(unit):
            return 0
        return 1

    def ruthless_discipline_reroll_hit_ones(self, unit) -> bool:
        if not self.is_grizzled_company():
            return False
        if unit is None:
            return False
        if not self.unit_is_astra_militarum(unit):
            return False
        return self._attached_unit_has_order(unit)
