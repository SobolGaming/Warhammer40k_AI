from __future__ import annotations

import html
import json
import re
from functools import lru_cache
from pathlib import Path

from .detachment_manager import DetachmentManagerBase


CODEX_SPACE_MARINES_DETACHMENTS = {
    "gladius task force",
    "anvil siege force",
    "ironstorm spearhead",
    "firestorm assault force",
    "stormlance task force",
    "vanguard spearhead",
    "1st company task force",
    "librarius conclave",
}

DIVERGENT_CHAPTER_KEYWORDS = {
    "black templars",
    "blood angels",
    "dark angels",
    "deathwatch",
    "space wolves",
}

CHAPTER_KEYWORD_MAP = {
    "black templars": "BLACK TEMPLARS",
    "blood angels": "BLOOD ANGELS",
    "dark angels": "DARK ANGELS",
    "deathwatch": "DEATHWATCH",
    "space wolves": "SPACE WOLVES",
    "ultramarines": "ULTRAMARINES",
    "imperial fists": "IMPERIAL FISTS",
    "salamanders": "SALAMANDERS",
    "raven guard": "RAVEN GUARD",
    "iron hands": "IRON HANDS",
    "white scars": "WHITE SCARS",
}

DETACHMENT_CHAPTER_OVERRIDES = {
    "lion's blade task force": "DARK ANGELS",
}

_CHAPTER_RESTRICTION_RE = re.compile(
    r"\byour army can include\s+(.+?)\s+units?\s*,?\s*but it cannot include\s+(?:any\s+)?"
    r"adeptus astartes units drawn from any other chapter",
    flags=re.IGNORECASE,
)


def _strip_html(text: str) -> str:
    if not text:
        return ""
    t = html.unescape(str(text))
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _chapter_from_restriction(text: str) -> str | None:
    if not text:
        return None
    text = text.replace("\u2019", "'")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    matches = _CHAPTER_RESTRICTION_RE.findall(text)
    if not matches:
        return None
    chapters = set()
    for raw in matches:
        cleaned = re.sub(r"\badeptus astartes\b", "", raw, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if not cleaned:
            cleaned = raw.strip()
        cleaned = cleaned.strip(" .")
        if not cleaned:
            continue
        upper = cleaned.upper()
        if upper in ("ADEPTUS ASTARTES", "SPACE MARINES"):
            continue
        chapters.add(upper)
    if len(chapters) == 1:
        return next(iter(chapters))
    return None


@lru_cache(maxsize=1)
def _chapter_detachment_map() -> dict[str, str]:
    out: dict[str, str] = {
        _normalize_detachment_name(k): v for k, v in DETACHMENT_CHAPTER_OVERRIDES.items()
    }
    try:
        base = Path(__file__).resolve().parents[3]
        path = base / "wahapedia_data" / "Detachment_abilities.json"
        if not path.exists():
            return out
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return out

    for row in data:
        det = (row.get("detachment") or "").strip()
        if not det:
            continue
        desc = _strip_html(row.get("description") or "")
        if not desc:
            continue
        chapter = _chapter_from_restriction(desc)
        if chapter:
            det_key = _normalize_detachment_name(det)
            if det_key not in out:
                out[det_key] = chapter
            continue
        found = set()
        upper = desc.upper()
        for _key, keyword in CHAPTER_KEYWORD_MAP.items():
            if keyword in upper:
                found.add(keyword)
        if len(found) == 1:
            det_key = _normalize_detachment_name(det)
            if det_key not in out:
                out[det_key] = found.pop()

    return out


def _normalize_detachment_name(text: str) -> str:
    t = str(text or "").lower()
    t = t.replace("\u2019", "'")
    t = t.replace("'", "")
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


class SpaceMarinesDetachmentManager(DetachmentManagerBase):
    faction_id = "SM"

    def _simple_norm(self, text: str) -> str:
        return _normalize_detachment_name(text)

    def get_committed_chapter_keyword(self) -> str | None:
        if not self._army_faction_matches(self.faction_id):
            return None
        det = self._simple_norm(self._get_detachment_type())
        if not det:
            return None
        return _chapter_detachment_map().get(det)

    def is_black_templars_detachment(self) -> bool:
        return self.get_committed_chapter_keyword() == "BLACK TEMPLARS"

    def is_codex_detachment(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        det = self._simple_norm(self._get_detachment_type())
        if not det:
            return False
        return det in CODEX_SPACE_MARINES_DETACHMENTS

    def is_gladius_task_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Gladius Task Force")

    def is_blade_of_ultramar(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Blade of Ultramar")

    def is_rage_cursed_onslaught(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Rage-cursed Onslaught")

    def is_wrath_of_the_rock(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Wrath of the Rock")

    def is_1st_company_task_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("1st Company Task Force")

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
        for member in members:
            if self._unit_has_keyword(member, keyword):
                return True
        return False

    def unit_is_adeptus_astartes(self, unit) -> bool:
        return self._unit_has_keyword_or_faction(unit, "ADEPTUS ASTARTES", faction_id=self.faction_id)

    def attached_unit_is_adeptus_astartes(self, unit) -> bool:
        if unit is None:
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return False
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        for member in members:
            if self.unit_is_adeptus_astartes(member):
                return True
        return False

    def dutiful_tenacity_wound_roll_penalty(self, target_unit, *, strength=None, target_toughness=None) -> tuple[int, str]:
        if not self.is_wrath_of_the_rock():
            return 0, ""
        if target_unit is None:
            return 0, ""
        if not self.attached_unit_is_adeptus_astartes(target_unit):
            return 0, ""
        if not (self._attached_unit_has_keyword(target_unit, "INFANTRY") or self._attached_unit_has_keyword(target_unit, "MOUNTED")):
            return 0, ""
        if not isinstance(strength, int) or not isinstance(target_toughness, int):
            return 0, ""
        if strength <= target_toughness:
            return 0, ""
        return 1, "Dutiful Tenacity"

    def maddened_ferocity_applies(self, unit) -> bool:
        if unit is None:
            return False
        if not self.is_rage_cursed_onslaught():
            return False
        return self.attached_unit_is_adeptus_astartes(unit)

    def has_divergent_chapter_keywords(self) -> bool:
        army = self.army
        if army is None:
            return False
        committed = self.get_committed_chapter_keyword()
        if committed and committed.lower() in DIVERGENT_CHAPTER_KEYWORDS:
            return True
        for unit in list(getattr(army, "units", []) or []):
            for kw in DIVERGENT_CHAPTER_KEYWORDS:
                try:
                    if unit.has_any_keyword(kw):
                        return True
                except Exception:
                    continue
        return False

    def has_marneus_calgar_on_battlefield(self) -> bool:
        army = self.army
        if army is None:
            return False

        def _unit_matches(unit) -> bool:
            if unit is None:
                return False
            name = str(getattr(unit, "name", "") or "").strip().upper()
            if "MARNEUS CALGAR" not in name:
                return False
            reserve_status = str(getattr(unit, "reserve_status", "") or "").strip().lower()
            if reserve_status in {"reserves", "strategic_reserves"}:
                return False
            models = getattr(unit, "models", None)
            if isinstance(models, list) and len(models) > 0:
                return True
            is_alive_fn = getattr(unit, "is_alive", None)
            if callable(is_alive_fn):
                return bool(is_alive_fn())
            return False

        units = list(getattr(army, "units", []) or [])
        for unit in units:
            if _unit_matches(unit):
                return True
            root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
            members = root.get_attached_unit_members() if hasattr(root, "get_attached_unit_members") else [root]
            for member in members:
                if member is unit:
                    continue
                if _unit_matches(member):
                    return True
        return False
