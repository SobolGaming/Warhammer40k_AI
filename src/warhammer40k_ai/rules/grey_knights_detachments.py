from __future__ import annotations

from .detachment_manager import DetachmentManagerBase


class GreyKnightsDetachmentManager(DetachmentManagerBase):
    faction_id = "GK"

    def is_brotherhood_strike(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Brotherhood Strike")

    def is_hallowed_conclave(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Hallowed Conclave")

    def _unit_has_keyword(self, unit, keyword: str) -> bool:
        if unit is None:
            return False
        try:
            return bool(unit.has_any_keyword(keyword))
        except Exception:
            pass
        kw = (keyword or "").strip().lower()
        if not kw:
            return False
        try:
            if kw in [k.lower() for k in (getattr(unit, "keywords", []) or [])]:
                return True
        except Exception:
            pass
        try:
            if kw in [k.lower() for k in (getattr(unit, "faction_keywords", []) or [])]:
                return True
        except Exception:
            pass
        return False

    def _attached_unit_has_keyword(self, unit, keyword: str) -> bool:
        if unit is None:
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        for u in members:
            if self._unit_has_keyword(u, keyword):
                return True
        return False

    def duty_before_all_applies(self, unit) -> bool:
        if not self.is_hallowed_conclave():
            return False
        if unit is None:
            return False
        return self._attached_unit_has_keyword(unit, "GREY KNIGHTS") and self._attached_unit_has_keyword(unit, "TERMINATOR")

    def fury_of_titan_applies(self, unit, *, used_deep_strike: bool = False) -> bool:
        if not self.is_brotherhood_strike():
            return False
        if unit is None or not used_deep_strike:
            return False
        return True

    def apply_fury_of_titan(self, unit) -> bool:
        if unit is None:
            return False
        if not self.is_brotherhood_strike():
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        for member in members:
            try:
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["fury_of_titan_active"] = True
                sr["fury_of_titan_expires_phase"] = "FIGHT_PHASE"
                member.special_rules = sr
            except Exception:
                continue
        return True
