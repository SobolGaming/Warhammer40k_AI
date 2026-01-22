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
        try:
            return str(getattr(self.army, "detachment_type", "") or "")
        except Exception:
            return ""

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

    def detachment_matches(self, detachment_name: str) -> bool:
        if self.faction_id and not self._army_faction_matches(self.faction_id):
            return False
        det = self._norm(self._get_detachment_type())
        target = self._norm(detachment_name)
        if not det or not target:
            return False
        if det == target:
            return True
        if det.endswith("s") and det[:-1] == target:
            return True
        if target.endswith("s") and target[:-1] == det:
            return True
        return det in target or target in det
