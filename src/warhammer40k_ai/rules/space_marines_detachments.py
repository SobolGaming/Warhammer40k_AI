from __future__ import annotations

import html
import json
import re
from functools import lru_cache
from itertools import combinations
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
    _ANGELIC_LEGACY_SANGUINARY_GRACE = "SANGUINARY_GRACE"
    _ANGELIC_LEGACY_CARMINE_WRATH = "CARMINE_WRATH"
    _ANGELIC_LEGACY_THEIR_APPOINTED_HOUR = "THEIR_APPOINTED_HOUR"
    _ANGELIC_LEGACY_KEYS = (
        _ANGELIC_LEGACY_SANGUINARY_GRACE,
        _ANGELIC_LEGACY_CARMINE_WRATH,
        _ANGELIC_LEGACY_THEIR_APPOINTED_HOUR,
    )
    _ANGELIC_LEGACY_LABELS = {
        _ANGELIC_LEGACY_SANGUINARY_GRACE: "Sanguinary Grace",
        _ANGELIC_LEGACY_CARMINE_WRATH: "Carmine Wrath",
        _ANGELIC_LEGACY_THEIR_APPOINTED_HOUR: "Their Appointed Hour",
    }

    def __init__(self, army=None):
        super().__init__(army)
        self.angelic_legacy_selected_keys: tuple[str, ...] = ()
        self.angelic_legacy_selected_round: int = 0

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

    def is_anvil_siege_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Anvil Siege Force")

    def is_bastion_task_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Bastion Task Force")

    def is_blade_of_ultramar(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Blade of Ultramar")

    def is_angelic_inheritors(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Angelic Inheritors")

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

    @classmethod
    def angelic_legacy_label(cls, key: str) -> str:
        return cls._ANGELIC_LEGACY_LABELS.get(str(key or "").strip().upper(), str(key or "").strip())

    @classmethod
    def _normalize_angelic_legacy_key(cls, value: str) -> str:
        raw = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
        if raw in cls._ANGELIC_LEGACY_KEYS:
            return raw
        if raw in {"SANGUINARYGRACE", "SANGUINARY"}:
            return cls._ANGELIC_LEGACY_SANGUINARY_GRACE
        if raw in {"CARMINEWRATH", "CARMINE"}:
            return cls._ANGELIC_LEGACY_CARMINE_WRATH
        if raw in {"THEIRAPPOINTEDHOUR", "APPOINTED_HOUR", "APPOINTEDHOUR"}:
            return cls._ANGELIC_LEGACY_THEIR_APPOINTED_HOUR
        return raw

    def can_select_angelic_legacy(self, *, game=None) -> bool:
        if not self.is_angelic_inheritors():
            return False
        if bool(self.angelic_legacy_selected_keys):
            return False
        if game is None:
            return True
        try:
            return int(getattr(game, "turn", 0) or 0) == 1
        except Exception:
            return False

    def get_angelic_legacy_pair_options(self) -> list[tuple[str, str]]:
        return list(combinations(self._ANGELIC_LEGACY_KEYS, 2))

    def select_angelic_legacy_options(self, choice_keys, *, battle_round=None) -> bool:
        if not self.is_angelic_inheritors():
            return False
        raw_choices = list(choice_keys or [])
        if len(raw_choices) != 2:
            return False
        normalized = [self._normalize_angelic_legacy_key(v) for v in raw_choices]
        if len(set(normalized)) != 2:
            return False
        if any(v not in self._ANGELIC_LEGACY_KEYS for v in normalized):
            return False
        self.angelic_legacy_selected_keys = tuple(sorted(set(normalized)))
        if battle_round is not None:
            try:
                self.angelic_legacy_selected_round = int(battle_round)
            except Exception:
                self.angelic_legacy_selected_round = 0
        return True

    def angelic_legacy_option_active(self, key: str) -> bool:
        choice = self._normalize_angelic_legacy_key(key)
        return choice in set(self.angelic_legacy_selected_keys)

    def _legacy_of_the_angel_recipient(self, unit) -> bool:
        if unit is None:
            return False
        if not self.is_angelic_inheritors():
            return False
        if not bool(self.angelic_legacy_selected_keys):
            return False
        if not self.attached_unit_is_adeptus_astartes(unit):
            return False
        return self._attached_unit_has_keyword(unit, "CHARACTER")

    def legacy_of_the_angel_sanguinary_grace_applies(self, unit) -> bool:
        if not self._legacy_of_the_angel_recipient(unit):
            return False
        return self.angelic_legacy_option_active(self._ANGELIC_LEGACY_SANGUINARY_GRACE)

    def legacy_of_the_angel_carmine_wrath_applies(self, unit) -> bool:
        if not self._legacy_of_the_angel_recipient(unit):
            return False
        return self.angelic_legacy_option_active(self._ANGELIC_LEGACY_CARMINE_WRATH)

    def legacy_of_the_angel_their_appointed_hour_applies(self, unit) -> bool:
        if not self._legacy_of_the_angel_recipient(unit):
            return False
        return self.angelic_legacy_option_active(self._ANGELIC_LEGACY_THEIR_APPOINTED_HOUR)

    def shield_of_the_imperium_heavy_applies(self, unit, weapon_profile=None) -> bool:
        if not self.is_anvil_siege_force():
            return False
        if unit is None:
            return False
        if not self.attached_unit_is_adeptus_astartes(unit):
            return False
        if weapon_profile is None:
            return True
        parent = getattr(weapon_profile, "parent_wargear", None)
        if parent is None:
            return False
        return bool(getattr(parent, "is_ranged", lambda: False)())

    def shield_of_the_imperium_wound_bonus(self, attacker_model, weapon_profile=None) -> tuple[int, str]:
        if not self.is_anvil_siege_force():
            return 0, ""
        if attacker_model is None:
            return 0, ""
        unit = getattr(attacker_model, "parent_unit", None)
        if unit is None:
            return 0, ""
        if not self.shield_of_the_imperium_heavy_applies(unit, weapon_profile):
            return 0, ""
        if weapon_profile is None or not bool(getattr(weapon_profile, "is_heavy", lambda: False)()):
            return 0, ""
        remained_stationary = bool(
            getattr(getattr(unit, "round_state", None), "remained_stationary_this_round", False)
        )
        if not remained_stationary:
            return 0, ""
        return 1, "Shield of the Imperium"

    def interlocking_tactics_battleline_applies(self, unit) -> bool:
        if unit is None:
            return False
        if not self.is_bastion_task_force():
            return False
        if not self.attached_unit_is_adeptus_astartes(unit):
            return False
        return self._attached_unit_has_keyword(unit, "BATTLELINE")

    def interlocking_tactics_shoot_after_advance_applies(self, unit, weapon_profile=None) -> bool:
        if not self.interlocking_tactics_battleline_applies(unit):
            return False
        if weapon_profile is None:
            return True
        parent = getattr(weapon_profile, "parent_wargear", None)
        if parent is None:
            return False
        return bool(getattr(parent, "is_ranged", lambda: False)())

    def interlocking_tactics_shoot_after_fall_back_applies(self, unit, weapon_profile=None) -> bool:
        return self.interlocking_tactics_shoot_after_advance_applies(unit, weapon_profile)

    def interlocking_tactics_charge_after_advance_applies(self, unit) -> bool:
        return self.interlocking_tactics_battleline_applies(unit)

    def interlocking_tactics_charge_after_fall_back_applies(self, unit) -> bool:
        return self.interlocking_tactics_battleline_applies(unit)

    def interlocking_tactics_allow_action_after_advance_or_fall_back(self, unit, game) -> bool:
        if not self.interlocking_tactics_battleline_applies(unit):
            return False
        if game is None:
            return False
        for flag in ("actions_enabled", "mission_actions_enabled", "mission_has_actions"):
            try:
                enabled = getattr(game, flag)
            except Exception:
                continue
            if enabled is False:
                return False
        return True

    def interlocking_tactics_target_is_auspex_scanned_for(self, attacker_unit, target_unit, *, game=None) -> bool:
        if not self.is_bastion_task_force():
            return False
        if attacker_unit is None or target_unit is None:
            return False
        if not self.attached_unit_is_adeptus_astartes(attacker_unit):
            return False
        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not bool(sr.get("interlocking_tactics_auspex_scanned_active", False)):
            return False
        owner_ids = list(sr.get("interlocking_tactics_auspex_scanned_owner_ids", []) or [])
        owner_ids = [str(v or "").strip() for v in owner_ids if str(v or "").strip()]
        if not owner_ids:
            single_owner = str(sr.get("interlocking_tactics_auspex_scanned_owner", "") or "").strip()
            if single_owner:
                owner_ids = [single_owner]
        owner_id = str(getattr(getattr(self.army, "player", None), "id", "") or "").strip()
        if owner_id and owner_ids and owner_id not in owner_ids:
            return False
        game_obj = game
        if game_obj is None:
            game_obj = getattr(getattr(self.army, "player", None), "game", None)
        if game_obj is not None:
            try:
                current_turn = int(getattr(game_obj, "turn", 0) or 0)
            except Exception:
                current_turn = 0
            try:
                marked_turn = int(sr.get("interlocking_tactics_auspex_scanned_turn", 0) or 0)
            except Exception:
                marked_turn = 0
            if current_turn and marked_turn and current_turn != marked_turn:
                return False
        return True

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
