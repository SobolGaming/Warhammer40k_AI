from __future__ import annotations

import re
import unicodedata

from .detachment_manager import DetachmentManagerBase


class LeaguesOfVotannDetachmentManager(DetachmentManagerBase):
    faction_id = "LOV"

    _METHODICAL_AP_UNIT_TOKENS = (
        "kahl",
        "uthar the destined",
        "einhyr hearthguard",
    )

    def is_hearthband(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Hearthband")

    def _normalize_text(self, text: str) -> str:
        t = unicodedata.normalize("NFKD", str(text or ""))
        t = t.encode("ascii", "ignore").decode("ascii")
        t = re.sub(r"[^a-z0-9 ]+", " ", t.lower())
        return re.sub(r"\s+", " ", t).strip()

    def _model_in_army(self, model) -> bool:
        if model is None or self.army is None:
            return False
        unit = getattr(model, "parent_unit", None)
        if unit is None:
            return False
        try:
            return unit.get_parent_army() is self.army
        except Exception:
            return False

    def _model_is_votann(self, model) -> bool:
        if model is None:
            return False
        unit = getattr(model, "parent_unit", None)
        return self._unit_has_keyword_or_faction(unit, "LEAGUES OF VOTANN", faction_id=self.faction_id)

    def _attached_unit_members(self, unit) -> list:
        if unit is None:
            return []
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        members = root.get_attached_unit_members() if hasattr(root, "get_attached_unit_members") else None
        if not members:
            members = [root]
        return list(members)

    def _unit_is_methodical_ap_unit(self, unit) -> bool:
        if unit is None:
            return False
        tokens = self._METHODICAL_AP_UNIT_TOKENS
        for member in self._attached_unit_members(unit):
            name = self._normalize_text(getattr(member, "name", ""))
            if name and any(tok in name for tok in tokens):
                return True
        return False

    def _target_within_engagement_range(self, model, target_unit, *, game_map=None) -> bool:
        if model is None or target_unit is None:
            return False
        unit = getattr(model, "parent_unit", None)
        if unit is None:
            return False
        source = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        target = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        if game_map is not None and hasattr(game_map, "is_within_engagement_range"):
            return bool(game_map.is_within_engagement_range(source, target))
        if hasattr(unit, "_model_within_engagement_range_of_unit"):
            return bool(unit._model_within_engagement_range_of_unit(model, target))
        return False

    def _target_is_closest_eligible(self, model, weapon_profile, target_unit, *, game_map=None) -> bool:
        if model is None or weapon_profile is None or target_unit is None or game_map is None:
            return False
        try:
            parent = getattr(weapon_profile, "parent_wargear", None)
            if parent is not None and getattr(parent, "is_melee", lambda: False)():
                return False
        except Exception:
            return False
        unit = getattr(model, "parent_unit", None)
        if unit is None or not hasattr(unit, "is_target_closest_eligible"):
            return False
        target = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        return bool(unit.is_target_closest_eligible(model, weapon_profile, target, game_map))

    def methodical_annihilation_applies(self, model, weapon_profile, target_unit, *, game_map=None) -> bool:
        if not self.is_hearthband():
            return False
        if model is None or weapon_profile is None or target_unit is None:
            return False
        if not self._model_in_army(model):
            return False
        if not self._model_is_votann(model):
            return False
        if self._target_within_engagement_range(model, target_unit, game_map=game_map):
            return True
        return self._target_is_closest_eligible(model, weapon_profile, target_unit, game_map=game_map)

    def methodical_annihilation_reroll_wound_ones(self, model, weapon_profile, target_unit, *, game_map=None) -> bool:
        return bool(self.methodical_annihilation_applies(model, weapon_profile, target_unit, game_map=game_map))

    def methodical_annihilation_ap_bonus(self, model, weapon_profile, target_unit, *, game_map=None) -> int:
        if not self.methodical_annihilation_applies(model, weapon_profile, target_unit, game_map=game_map):
            return 0
        unit = getattr(model, "parent_unit", None)
        if not self._unit_is_methodical_ap_unit(unit):
            return 0
        return 1
