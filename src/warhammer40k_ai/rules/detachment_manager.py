from __future__ import annotations

import re
class DetachmentManagerBase:
    faction_id: str = ""

    def __init__(self, army=None):
        self.army = army

    def _norm(self, text: str) -> str:
        t = re.sub(r"[^a-z0-9 ]+", " ", str(text or "").lower())
        return re.sub(r"\s+", " ", t).strip()

    def _get_detachment_type(self) -> str:
        if self.army is None:
            return ""
        get_primary = getattr(self.army, "get_primary_detachment_type", None)
        if callable(get_primary):
            return str(get_primary(self.faction_id or "") or "")
        return ""

    def _get_detachment_instances(self) -> list:
        if self.army is None:
            return []
        get_instances = getattr(self.army, "get_detachment_instances_for_faction", None)
        if callable(get_instances):
            instances = list(get_instances(self.faction_id or getattr(self.army, "faction_id", "")) or [])
            if instances:
                return instances
        get_all = getattr(self.army, "get_detachment_instances", None)
        if callable(get_all):
            instances = list(get_all() or [])
            if instances:
                return instances
        return []

    def _detachment_name_matches(self, detachment_name: str, target_name: str) -> bool:
        det = self._norm(detachment_name)
        target = self._norm(target_name)
        if not det or not target:
            return False
        if det == target:
            return True
        if det.endswith("s") and det[:-1] == target:
            return True
        if target.endswith("s") and target[:-1] == det:
            return True
        return det in target or target in det

    def _unit_has_keyword(self, unit, keyword: str) -> bool:
        if unit is None:
            return False
        kw = (keyword or "").strip()
        if not kw:
            return False
        has_any = getattr(unit, "has_any_keyword", None)
        if callable(has_any):
            return bool(has_any(kw))
        raw = [str(k or "") for k in (getattr(unit, "keywords", []) or [])]
        raw += [str(k or "") for k in (getattr(unit, "faction_keywords", []) or [])]
        return kw.lower() in {k.lower() for k in raw if str(k).strip()}

    def _unit_has_keyword_or_faction(self, unit, keyword: str, *, faction_id: str = "") -> bool:
        if self._unit_has_keyword(unit, keyword):
            return True
        if unit is None:
            return False
        has_keywords = bool(getattr(unit, "keywords", None)) or bool(getattr(unit, "faction_keywords", None))
        if has_keywords:
            return False
        if faction_id:
            return self._army_faction_matches(faction_id)
        return False

    def _army_faction_matches(self, faction_id: str) -> bool:
        fid = ""
        try:
            fid = str(getattr(self.army, "faction_id", "") or "").strip().upper()
        except Exception:
            fid = ""
        if not fid:
            return True
        return fid == str(faction_id or "").strip().upper()

    def get_matching_detachment_instances(self, detachment_name: str) -> list:
        if self.faction_id and not self._army_faction_matches(self.faction_id):
            return []
        matches = []
        for detachment in self._get_detachment_instances():
            name = str(getattr(detachment, "detachment_type", "") or "")
            if self._detachment_name_matches(name, detachment_name):
                matches.append(detachment)
        return matches

    def detachment_matches(self, detachment_name: str) -> bool:
        return bool(self.get_matching_detachment_instances(detachment_name))
