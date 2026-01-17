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
