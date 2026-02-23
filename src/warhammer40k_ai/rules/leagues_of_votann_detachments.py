from __future__ import annotations

import re
import unicodedata

from ..utility.entity_ids import get_entity_id
from .detachment_manager import DetachmentManagerBase


class LeaguesOfVotannDetachmentManager(DetachmentManagerBase):
    faction_id = "LOV"

    _METHODICAL_AP_UNIT_TOKENS = (
        "kahl",
        "uthar the destined",
        "einhyr hearthguard",
    )
    _MOBILE_SENSOR_RELAYS_SOURCE = "Mobile Sensor Relays: Firebase Control"

    def is_brandfast_oathband(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Brandfast Oathband")

    def is_delve_assault_shift(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return (
            self._detachment_matches_normalized("Dêlve Assault Shift")
            or self._detachment_matches_normalized("Delve Assault Shift")
        )

    def is_hearthband(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Hearthband")

    def is_needgaard_oathband(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return (
            self._detachment_matches_normalized("Needgaârd Oathband")
            or self._detachment_matches_normalized("Needgaard Oathband")
        )

    def _normalize_text(self, text: str) -> str:
        t = unicodedata.normalize("NFKD", str(text or ""))
        t = t.encode("ascii", "ignore").decode("ascii")
        t = re.sub(r"[^a-z0-9 ]+", " ", t.lower())
        return re.sub(r"\s+", " ", t).strip()

    def _detachment_matches_normalized(self, detachment_name: str) -> bool:
        det = self._normalize_text(self._get_detachment_type())
        target = self._normalize_text(detachment_name)
        if not det or not target:
            return False
        if det == target:
            return True
        if det.endswith("s") and det[:-1] == target:
            return True
        if target.endswith("s") and target[:-1] == det:
            return True
        return det in target or target in det

    @staticmethod
    def _attached_root(unit):
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _entity_id(entity) -> str:
        try:
            return str(get_entity_id(entity) or "")
        except ValueError:
            return ""

    def _unit_in_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        if not callable(get_parent_army):
            return False
        return get_parent_army() is self.army

    @staticmethod
    def _unit_is_on_battlefield(unit) -> bool:
        if unit is None:
            return False
        active_for_rules = getattr(unit, "is_active_for_rules", None)
        if callable(active_for_rules):
            return bool(active_for_rules())
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        if hasattr(unit, "deployed") and not bool(getattr(unit, "deployed", True)):
            return False
        if bool(getattr(unit, "embarked_in", None)):
            return False
        return True

    def _iter_unique_army_roots(self) -> list:
        if self.army is None:
            return []
        roots = []
        seen = set()
        for idx, unit in enumerate(list(getattr(self.army, "units", []) or [])):
            root = self._attached_root(unit)
            if root is None:
                continue
            root_id = self._entity_id(root) or f"idx:{idx}"
            if root_id in seen:
                continue
            seen.add(root_id)
            roots.append(root)
        return roots

    def _unit_has_role_keyword(self, unit, keyword: str) -> bool:
        for member in self._attached_unit_members(unit):
            if self._unit_has_keyword(member, keyword):
                return True
        return False

    def _unit_is_transport(self, unit) -> bool:
        return bool(unit is not None and self._unit_has_role_keyword(unit, "TRANSPORT"))

    def _unit_is_infantry(self, unit) -> bool:
        return bool(unit is not None and self._unit_has_role_keyword(unit, "INFANTRY"))

    def _unit_matches_cthonian_beserks_keywords(self, unit) -> bool:
        if unit is None:
            return False
        texts = [getattr(unit, "name", "")]
        texts += list(getattr(unit, "keywords", []) or [])
        texts += list(getattr(unit, "faction_keywords", []) or [])
        for raw in texts:
            norm = self._normalize_text(raw)
            if "cthonian beserks" in norm:
                return True
            if "cthonian" in norm and ("beserks" in norm or "beserk" in norm):
                return True
        return False

    def _unit_is_cthonian_beserks(self, unit) -> bool:
        if unit is None:
            return False
        root = self._attached_root(unit)
        if root is None:
            return False
        if self._unit_matches_cthonian_beserks_keywords(root):
            return True
        for member in self._attached_unit_members(root):
            if self._unit_matches_cthonian_beserks_keywords(member):
                return True
        return False

    @staticmethod
    def _weapon_is_ranged(weapon_profile) -> bool:
        if weapon_profile is None:
            return False
        parent = getattr(weapon_profile, "parent_wargear", None)
        return bool(parent is not None and callable(getattr(parent, "is_ranged", None)) and parent.is_ranged())

    def _model_in_army(self, model) -> bool:
        if model is None or self.army is None:
            return False
        unit = getattr(model, "parent_unit", None)
        return self._unit_in_army(unit)

    def _unit_is_votann(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword_or_faction(unit, "LEAGUES OF VOTANN", faction_id=self.faction_id)

    def _model_is_votann(self, model) -> bool:
        if model is None:
            return False
        unit = getattr(model, "parent_unit", None)
        return self._unit_is_votann(unit)

    def mobile_sensor_relays_sustained_hits_value(self, model, weapon_profile=None, *, game_map=None) -> tuple[int, str]:
        del game_map
        if not self.is_brandfast_oathband():
            return 0, ""
        if model is None or not self._weapon_is_ranged(weapon_profile):
            return 0, ""
        if not self._model_in_army(model):
            return 0, ""
        if not self._model_is_votann(model):
            return 0, ""

        unit = getattr(model, "parent_unit", None)
        infantry_root = self._attached_root(unit)
        if infantry_root is None:
            return 0, ""
        if not self._unit_in_army(infantry_root):
            return 0, ""
        if not self._unit_is_on_battlefield(infantry_root):
            return 0, ""
        if not self._unit_is_votann(infantry_root):
            return 0, ""
        if not self._unit_is_infantry(infantry_root):
            return 0, ""

        from ..utility.aura_utils import unit_wholly_within_range_of_unit

        infantry_root_id = self._entity_id(infantry_root)
        for source in self._iter_unique_army_roots():
            if source is None:
                continue
            if not self._unit_is_on_battlefield(source):
                continue
            if not self._unit_is_votann(source):
                continue
            if not self._unit_is_transport(source):
                continue
            source_id = self._entity_id(source)
            if source_id and source_id == infantry_root_id:
                continue
            if unit_wholly_within_range_of_unit(source, infantry_root, 6.0, use_attached_aggregate=True):
                return 1, self._MOBILE_SENSOR_RELAYS_SOURCE
        return 0, ""

    def fury_from_the_delve_grants_deep_strike(self, unit) -> bool:
        if not self.is_delve_assault_shift():
            return False
        root = self._attached_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_is_votann(root):
            return False
        return self._unit_is_cthonian_beserks(root)

    def apply_delve_assault_shift_battleline_keywords(self, unit=None) -> None:
        if not self.is_delve_assault_shift() or self.army is None:
            return
        units = [unit] if unit is not None else list(getattr(self.army, "units", []) or [])
        for entry in units:
            root = self._attached_root(entry)
            if root is None:
                continue
            if not self._unit_in_army(root):
                continue
            if not self._unit_is_cthonian_beserks(root):
                continue
            keywords = list(getattr(root, "keywords", []) or [])
            if any(str(k or "").strip().lower() == "battleline" for k in keywords):
                continue
            keywords.append("Battleline")
            root.keywords = keywords

    def _get_yield_points_manager(self):
        try:
            return getattr(self.army, "prioritised_efficiency", None) if self.army is not None else None
        except Exception:
            return None

    def martial_leverage_on_unit_destroyed(self, destroyed_unit, *, game=None) -> int:
        if not self.is_needgaard_oathband():
            return 0
        if destroyed_unit is None or self.army is None:
            return 0
        try:
            destroyed_army = destroyed_unit.get_parent_army()
        except Exception:
            destroyed_army = None
        if destroyed_army is None or destroyed_army is self.army:
            return 0
        mgr = self._get_yield_points_manager()
        if mgr is None:
            return 0
        return int(mgr.add_yield_points(1, game=game) or 0)

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

