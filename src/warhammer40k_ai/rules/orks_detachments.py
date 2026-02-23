from __future__ import annotations

import re

from .detachment_manager import DetachmentManagerBase


class OrksDetachmentManager(DetachmentManagerBase):
    faction_id = "ORK"
    _SECOND_WAAAGH_NAMED_UNITS = ("nobz", "meganobz")

    def is_war_horde(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("War Horde")

    def is_bully_boyz(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Bully Boyz")

    @staticmethod
    def _normalize_name(text: str) -> str:
        value = re.sub(r"[^a-z0-9 ]+", " ", str(text or "").lower())
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _unit_is_alive(unit) -> bool:
        if unit is None:
            return False
        is_alive_fn = getattr(unit, "is_alive", None)
        if callable(is_alive_fn):
            return bool(is_alive_fn())
        return bool(getattr(unit, "is_alive", True))

    @staticmethod
    def _unit_is_deployed_on_battlefield(unit) -> bool:
        if unit is None:
            return False
        if not bool(getattr(unit, "deployed", True)):
            return False
        status = str(getattr(unit, "reserve_status", "deployed") or "deployed").strip().lower()
        if status != "deployed":
            return False
        in_reserves_fn = getattr(unit, "is_in_reserves", None)
        if callable(in_reserves_fn):
            return not bool(in_reserves_fn())
        return True

    def _transport_is_on_battlefield(self, transport_unit) -> bool:
        if transport_unit is None:
            return False
        if not self._unit_is_alive(transport_unit):
            return False
        return self._unit_is_deployed_on_battlefield(transport_unit)

    def _unit_is_on_battlefield_or_embarked(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_is_alive(unit):
            return False
        embarked_in = getattr(unit, "embarked_in", None)
        if embarked_in is not None:
            return self._transport_is_on_battlefield(embarked_in)
        return self._unit_is_deployed_on_battlefield(unit)

    def _unit_contains_keyword(self, unit, keyword: str) -> bool:
        if unit is None:
            return False
        if self._unit_has_keyword(unit, keyword):
            return True
        members_fn = getattr(unit, "get_attached_unit_members", None)
        if not callable(members_fn):
            return False
        members = list(members_fn() or [])
        for member in members:
            if self._unit_has_keyword(member, keyword):
                return True
        return False

    def _unit_name_matches_any(self, unit, names: tuple[str, ...]) -> bool:
        if unit is None:
            return False
        unit_name = self._normalize_name(getattr(unit, "name", ""))
        if unit_name in names:
            return True
        members_fn = getattr(unit, "get_attached_unit_members", None)
        if not callable(members_fn):
            return False
        members = list(members_fn() or [])
        for member in members:
            member_name = self._normalize_name(getattr(member, "name", ""))
            if member_name in names:
                return True
        return False

    def _unit_contains_warboss_model(self, unit) -> bool:
        if unit is None:
            return False
        if self._unit_contains_keyword(unit, "WARBOSS"):
            return True
        members_fn = getattr(unit, "get_attached_unit_members", None)
        members = list(members_fn() or []) if callable(members_fn) else [unit]
        for member in members:
            models = list(getattr(member, "models", []) or [])
            for model in models:
                keywords = list(getattr(model, "keywords", []) or [])
                for token in keywords:
                    if str(token or "").strip().upper() == "WARBOSS":
                        return True
        return False

    def can_call_second_waaagh(self, *, game=None, player=None) -> bool:
        if not self.is_bully_boyz():
            return False
        army = self.army
        if army is None:
            return False
        if player is not None:
            army_player = getattr(army, "player", None)
            if army_player is not None and army_player is not player:
                return False
        units = list(getattr(army, "units", []) or [])
        for unit in units:
            if unit is None:
                continue
            if not self._unit_contains_warboss_model(unit):
                continue
            if self._unit_is_on_battlefield_or_embarked(unit):
                return True
        return False

    def bully_boyz_second_waaagh_unit_applies(self, unit) -> bool:
        if not self.is_bully_boyz():
            return False
        if unit is None:
            return False
        if self._unit_contains_keyword(unit, "WARBOSS"):
            return True
        if self._unit_contains_keyword(unit, "NOBZ"):
            return True
        if self._unit_contains_keyword(unit, "MEGANOBZ"):
            return True
        return self._unit_name_matches_any(unit, self._SECOND_WAAAGH_NAMED_UNITS)

    def war_horde_sustained_hits_value(self, unit, *, attack_type: str = "", keyword: str = "ORKS") -> int:
        if not self.is_war_horde():
            return 0
        if unit is None:
            return 0
        if str(attack_type or "").strip().lower() not in ("", "melee"):
            return 0
        if not self._unit_has_keyword_or_faction(unit, keyword, faction_id=self.faction_id):
            return 0
        return 1
