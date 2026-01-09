from __future__ import annotations

from .detachment_manager import DetachmentManagerBase


CODEX_SPACE_MARINES_DETACHMENTS = {
    "gladius task force",
    "anvil siege force",
    "ironstorm spearhead",
    "firestorm assault force",
    "stormlance task force",
    "vanguard spearhead",
    "1st company task force",
    "boarding strike",
    "pilum strike team",
    "terminator assault",
}

DIVERGENT_CHAPTER_KEYWORDS = {
    "black templars",
    "blood angels",
    "dark angels",
    "deathwatch",
    "space wolves",
}


class SpaceMarinesDetachmentManager(DetachmentManagerBase):
    faction_id = "SM"

    def _simple_norm(self, text: str) -> str:
        return (text or "").strip().lower()

    def is_codex_detachment(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        det = self._simple_norm(self._get_detachment_type())
        if not det:
            return False
        return det in CODEX_SPACE_MARINES_DETACHMENTS

    def has_divergent_chapter_keywords(self) -> bool:
        army = self.army
        if army is None:
            return False
        for unit in list(getattr(army, "units", []) or []):
            for kw in DIVERGENT_CHAPTER_KEYWORDS:
                try:
                    if unit.has_any_keyword(kw):
                        return True
                except Exception:
                    continue
        return False
