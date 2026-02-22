from __future__ import annotations

import html
import json
import re
from functools import lru_cache
from itertools import combinations
from pathlib import Path

from .detachment_manager import DetachmentManagerBase
from ..utility.entity_ids import get_entity_id


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
    _MISSION_TACTIC_FUROR = "FUROR_TACTICS"
    _MISSION_TACTIC_MALLEUS = "MALLEUS_TACTICS"
    _MISSION_TACTIC_PURGATUS = "PURGATUS_TACTICS"
    _MISSION_TACTIC_KEYS = (
        _MISSION_TACTIC_FUROR,
        _MISSION_TACTIC_MALLEUS,
        _MISSION_TACTIC_PURGATUS,
    )
    _MISSION_TACTIC_LABELS = {
        _MISSION_TACTIC_FUROR: "Furor Tactics",
        _MISSION_TACTIC_MALLEUS: "Malleus Tactics",
        _MISSION_TACTIC_PURGATUS: "Purgatus Tactics",
    }

    def __init__(self, army=None):
        super().__init__(army)
        self.angelic_legacy_selected_keys: tuple[str, ...] = ()
        self.angelic_legacy_selected_round: int = 0
        self.unparalleled_tactician_used_round: int = 0
        self.mission_tactics_selected_keys: tuple[str, ...] = ()
        self.mission_tactics_active_key: str = ""
        self.mission_tactics_active_round: int = 0
        self.mission_tactics_last_selection_round: int = 0
        self.grim_resolve_selected_unit_id: str = ""
        self.grim_resolve_selected_round: int = 0
        self.grim_resolve_selected_player_id: str = ""

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

    def is_stormlance_task_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Stormlance Task Force")

    def is_companions_of_vehemence(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Companions of Vehemence")

    def is_spearpoint_task_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Spearpoint Task Force")

    def is_company_of_hunters(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Company of Hunters")

    def is_firestorm_assault_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Firestorm Assault Force")

    def is_vanguard_spearhead(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Vanguard Spearhead")

    def is_black_spear_task_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Black Spear Task Force")

    def is_shadowmark_talon(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Shadowmark Talon")

    def is_liberator_assault_group(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Liberator Assault Group")

    def is_blade_of_ultramar(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Blade of Ultramar")

    def is_hammer_of_avernii(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Hammer of Avernii")

    def is_emperors_shield(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Emperor's Shield")

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

    def is_the_lost_brethren(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("The Lost Brethren")

    def is_1st_company_task_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("1st Company Task Force")

    def is_unforgiven_task_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Unforgiven Task Force")

    def _attached_unit_root(self, unit):
        if unit is None:
            return None
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        return root

    def _iter_unique_army_roots(self) -> list:
        army = self.army
        if army is None:
            return []
        roots = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._attached_unit_root(unit)
            if root is None:
                continue
            try:
                if root.get_parent_army() is not army:
                    continue
            except Exception:
                continue
            rid = str(get_entity_id(root) or "")
            if not rid or rid in seen:
                continue
            seen.add(rid)
            roots.append(root)
        roots.sort(key=lambda u: str(get_entity_id(u) or ""))
        return roots

    def _unit_has_models_or_is_alive(self, unit) -> bool:
        if unit is None:
            return False
        models = getattr(unit, "models", None)
        if isinstance(models, list) and len(models) > 0:
            return True
        is_alive_fn = getattr(unit, "is_alive", None)
        if callable(is_alive_fn):
            return bool(is_alive_fn())
        return False

    def grim_resolve_target_is_eligible(self, unit, *, game=None) -> bool:
        if not self.is_unforgiven_task_force():
            return False
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        try:
            if root.get_parent_army() is not self.army:
                return False
        except Exception:
            return False
        if not self.attached_unit_is_adeptus_astartes(root):
            return False
        if not self._unit_has_models_or_is_alive(root):
            return False
        return True

    def get_grim_resolve_target_units(self, *, game=None) -> list:
        if not self.is_unforgiven_task_force():
            return []
        roots = []
        for root in self._iter_unique_army_roots():
            if self.grim_resolve_target_is_eligible(root, game=game):
                roots.append(root)
        roots.sort(key=lambda u: (str(getattr(u, "name", "") or ""), str(get_entity_id(u) or "")))
        return roots

    def can_select_grim_resolve_target(self, *, game=None) -> bool:
        if not self.is_unforgiven_task_force():
            return False
        if not self.get_grim_resolve_target_units(game=game):
            return False
        if game is None:
            return True
        try:
            round_now = int(getattr(game, "turn", 0) or 0)
        except Exception:
            return False
        if round_now <= 0:
            return False
        army_player_id = str(getattr(getattr(self.army, "player", None), "id", "") or "")
        if (
            self.grim_resolve_selected_round == round_now
            and str(self.grim_resolve_selected_player_id or "") == army_player_id
            and str(self.grim_resolve_selected_unit_id or "")
        ):
            return False
        return True

    def clear_grim_resolve_bonus(self, *, game=None) -> None:
        self.grim_resolve_selected_unit_id = ""

    def select_grim_resolve_target_unit(self, unit, *, game=None) -> bool:
        if not self.is_unforgiven_task_force():
            return False
        if not self.grim_resolve_target_is_eligible(unit, game=game):
            return False
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            return False
        self.grim_resolve_selected_unit_id = unit_id
        if game is not None:
            try:
                self.grim_resolve_selected_round = int(getattr(game, "turn", 0) or 0)
            except Exception:
                self.grim_resolve_selected_round = 0
        self.grim_resolve_selected_player_id = str(
            getattr(getattr(self.army, "player", None), "id", "") or ""
        )
        return True

    def grim_resolve_battle_shock_oc_bonus(self, unit) -> tuple[int, str]:
        if not self.is_unforgiven_task_force():
            return 0, ""
        root = self._attached_unit_root(unit)
        if root is None:
            return 0, ""
        if not self.attached_unit_is_adeptus_astartes(root):
            return 0, ""
        is_bs_fn = getattr(root, "is_battle_shocked", None)
        if not callable(is_bs_fn) or not bool(is_bs_fn()):
            return 0, ""
        return 1, "Grim Resolve (Battle-shock)"

    def grim_resolve_command_phase_oc_bonus(self, unit) -> tuple[int, str]:
        if not self.is_unforgiven_task_force():
            return 0, ""
        selected_id = str(getattr(self, "grim_resolve_selected_unit_id", "") or "")
        if not selected_id:
            return 0, ""
        root = self._attached_unit_root(unit)
        if root is None:
            return 0, ""
        if str(get_entity_id(root) or "") != selected_id:
            return 0, ""
        if not self.attached_unit_is_adeptus_astartes(root):
            return 0, ""
        return 1, "Grim Resolve (Command phase)"

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

    @classmethod
    def mission_tactic_label(cls, key: str) -> str:
        return cls._MISSION_TACTIC_LABELS.get(str(key or "").strip().upper(), str(key or "").strip())

    @classmethod
    def _normalize_mission_tactic_key(cls, value: str) -> str:
        raw = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
        if raw in cls._MISSION_TACTIC_KEYS:
            return raw
        if raw in {"FUROR", "FURORTACTICS", "FUROR_TACTIC"}:
            return cls._MISSION_TACTIC_FUROR
        if raw in {"MALLEUS", "MALLEUSTACTICS", "MALLEUS_TACTIC"}:
            return cls._MISSION_TACTIC_MALLEUS
        if raw in {"PURGATUS", "PURGATUSTACTICS", "PURGATUS_TACTIC"}:
            return cls._MISSION_TACTIC_PURGATUS
        return raw

    def clear_active_mission_tactic(self, *, game=None) -> None:
        if not self.is_black_spear_task_force():
            self.mission_tactics_active_key = ""
            self.mission_tactics_active_round = 0
            return
        if game is None:
            self.mission_tactics_active_key = ""
            self.mission_tactics_active_round = 0
            return
        try:
            round_now = int(getattr(game, "turn", 0) or 0)
        except Exception:
            round_now = 0
        if int(self.mission_tactics_active_round or 0) < int(round_now or 0):
            self.mission_tactics_active_key = ""
            self.mission_tactics_active_round = 0

    def mark_mission_tactics_skipped_for_round(self, *, battle_round=None) -> None:
        if battle_round is None:
            return
        try:
            self.mission_tactics_last_selection_round = int(battle_round)
        except Exception:
            self.mission_tactics_last_selection_round = 0

    def get_available_mission_tactics(self) -> list[str]:
        selected = {str(v or "").strip().upper() for v in list(self.mission_tactics_selected_keys or ())}
        return [key for key in self._MISSION_TACTIC_KEYS if key not in selected]

    def can_select_mission_tactic(self, *, game=None) -> bool:
        if not self.is_black_spear_task_force():
            return False
        if not self.get_available_mission_tactics():
            return False
        if game is None:
            return True
        try:
            round_now = int(getattr(game, "turn", 0) or 0)
        except Exception:
            return False
        if round_now <= 0:
            return False
        return int(getattr(self, "mission_tactics_last_selection_round", 0) or 0) != round_now

    def select_mission_tactic(self, choice_key: str, *, battle_round=None) -> bool:
        if not self.is_black_spear_task_force():
            return False
        round_now = 0
        if battle_round is not None:
            try:
                round_now = int(battle_round)
            except Exception:
                round_now = 0
        if round_now > 0 and int(getattr(self, "mission_tactics_last_selection_round", 0) or 0) == round_now:
            return False
        key = self._normalize_mission_tactic_key(choice_key)
        if key not in self._MISSION_TACTIC_KEYS:
            return False
        selected = list(self.mission_tactics_selected_keys or ())
        if key in selected:
            return False
        selected.append(key)
        self.mission_tactics_selected_keys = tuple(selected)
        self.mission_tactics_active_key = key
        if battle_round is not None:
            self.mission_tactics_active_round = int(round_now or 0)
            self.mission_tactics_last_selection_round = int(round_now or 0)
        return True

    def _mission_tactics_recipient(self, unit) -> bool:
        if unit is None:
            return False
        if not self.is_black_spear_task_force():
            return False
        if not str(getattr(self, "mission_tactics_active_key", "") or "").strip():
            return False
        if not self.attached_unit_is_adeptus_astartes(unit):
            return False
        return True

    def mission_tactics_lethal_hits(self, attacker_model) -> tuple[bool, str]:
        if str(self.mission_tactics_active_key or "").strip().upper() != self._MISSION_TACTIC_MALLEUS:
            return False, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None) if attacker_model is not None else None
        if not self._mission_tactics_recipient(attacker_unit):
            return False, ""
        return True, self.mission_tactic_label(self._MISSION_TACTIC_MALLEUS)

    def mission_tactics_sustained_hits(self, attacker_model) -> tuple[int, str]:
        if str(self.mission_tactics_active_key or "").strip().upper() != self._MISSION_TACTIC_FUROR:
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None) if attacker_model is not None else None
        if not self._mission_tactics_recipient(attacker_unit):
            return 0, ""
        return 1, self.mission_tactic_label(self._MISSION_TACTIC_FUROR)

    def mission_tactics_precision_on_crit(self, attacker_model) -> tuple[bool, str]:
        if str(self.mission_tactics_active_key or "").strip().upper() != self._MISSION_TACTIC_PURGATUS:
            return False, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None) if attacker_model is not None else None
        if not self._mission_tactics_recipient(attacker_unit):
            return False, ""
        return True, self.mission_tactic_label(self._MISSION_TACTIC_PURGATUS)

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

    def lightning_assault_charge_after_advance_applies(self, unit) -> bool:
        if not self.is_stormlance_task_force():
            return False
        if unit is None:
            return False
        return self.attached_unit_is_adeptus_astartes(unit)

    def lightning_assault_charge_after_fall_back_applies(self, unit) -> bool:
        return self.lightning_assault_charge_after_advance_applies(unit)

    def righteous_fervour_reroll_advance_applies(self, unit) -> bool:
        if not self.is_companions_of_vehemence():
            return False
        if unit is None:
            return False
        return self.attached_unit_is_adeptus_astartes(unit)

    def righteous_fervour_reroll_charge_applies(self, unit) -> bool:
        return self.righteous_fervour_reroll_advance_applies(unit)

    def _unit_is_company_of_hunters_outrider(self, unit) -> bool:
        if unit is None:
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        name = str(getattr(root, "name", "") or "").strip().lower()
        return "outrider squad" in name

    def _unit_is_the_lost_brethren_battleline(self, unit) -> bool:
        if unit is None:
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        name = str(getattr(root, "name", "") or "").strip().lower()
        return name in {
            "death company marines",
            "death company marines with bolt rifles",
        }

    def _unit_is_death_company(self, unit) -> bool:
        if unit is None:
            return False
        if self._attached_unit_has_keyword(unit, "DEATH COMPANY"):
            return True
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        name = str(getattr(root, "name", "") or "").strip().upper()
        return "DEATH COMPANY" in name

    def apply_company_of_hunters_battleline_keywords(self, unit=None) -> None:
        if not self.is_company_of_hunters() or self.army is None:
            return
        if unit is None:
            units = list(getattr(self.army, "units", []) or [])
        else:
            units = [unit]
        for entry in units:
            if entry is None:
                continue
            root = entry.get_attached_unit_root() if hasattr(entry, "get_attached_unit_root") else entry
            if root is None:
                continue
            try:
                if root.get_parent_army() is not self.army:
                    continue
            except Exception:
                continue
            if not self._unit_is_company_of_hunters_outrider(root):
                continue
            keywords = list(getattr(root, "keywords", []) or [])
            if not any(str(k or "").strip().lower() == "battleline" for k in keywords):
                keywords.append("Battleline")
                root.keywords = keywords

    def apply_the_lost_brethren_battleline_keywords(self, unit=None) -> None:
        if not self.is_the_lost_brethren() or self.army is None:
            return
        if unit is None:
            units = list(getattr(self.army, "units", []) or [])
        else:
            units = [unit]
        for entry in units:
            if entry is None:
                continue
            root = entry.get_attached_unit_root() if hasattr(entry, "get_attached_unit_root") else entry
            if root is None:
                continue
            try:
                if root.get_parent_army() is not self.army:
                    continue
            except Exception:
                continue
            if not self._unit_is_the_lost_brethren_battleline(root):
                continue
            keywords = list(getattr(root, "keywords", []) or [])
            if not any(str(k or "").strip().lower() == "battleline" for k in keywords):
                keywords.append("Battleline")
                root.keywords = keywords

    def a_noble_death_in_combat_reroll_mode(self, unit) -> str:
        if unit is None:
            return ""
        if not self.is_the_lost_brethren():
            return ""
        if not self.attached_unit_is_adeptus_astartes(unit):
            return ""
        if not self._unit_is_death_company(unit):
            return ""
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return ""
        below_half_fn = getattr(root, "is_below_half_strength", None)
        if callable(below_half_fn) and bool(below_half_fn()):
            return "full"
        below_start_fn = getattr(root, "is_below_starting_strength", None)
        if callable(below_start_fn) and bool(below_start_fn()):
            return "ones"
        return ""

    def masters_of_manoeuvre_shoot_after_advance_applies(self, unit, weapon_profile=None) -> bool:
        if not self.is_company_of_hunters():
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

    def masters_of_manoeuvre_shoot_after_fall_back_applies(self, unit, weapon_profile=None) -> bool:
        return self.masters_of_manoeuvre_shoot_after_advance_applies(unit, weapon_profile)

    def masters_of_manoeuvre_charge_after_advance_applies(self, unit) -> bool:
        if not self.is_company_of_hunters():
            return False
        if unit is None:
            return False
        if not self.attached_unit_is_adeptus_astartes(unit):
            return False
        return self._attached_unit_has_keyword(unit, "MOUNTED")

    def masters_of_manoeuvre_charge_after_fall_back_applies(self, unit) -> bool:
        return self.masters_of_manoeuvre_charge_after_advance_applies(unit)

    def close_range_eradication_assault_applies(self, unit, weapon_profile=None) -> bool:
        if not self.is_firestorm_assault_force():
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

    def close_range_eradication_strength_bonus(
        self,
        attacker_model,
        target_unit=None,
        *,
        weapon_profile=None,
        attack_instance=None,
    ) -> tuple[int, str]:
        if not self.is_firestorm_assault_force():
            return 0, ""
        if attacker_model is None:
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        if attacker_unit is None:
            return 0, ""
        if not self.close_range_eradication_assault_applies(attacker_unit, weapon_profile):
            return 0, ""
        try:
            distance = float((attack_instance or {}).get("distance_to_target", 0.0) or 0.0)
        except Exception:
            distance = 0.0
        if distance <= 0.0 and target_unit is not None:
            game_map = None
            try:
                game_map = getattr(getattr(attacker_unit.get_parent_army(), "player", None), "game", None).map
            except Exception:
                game_map = None
            if game_map is not None:
                try:
                    distance = float(game_map.get_distance_between_units(attacker_unit, target_unit))
                except Exception:
                    distance = 0.0
        if distance <= 0.0 or distance > 12.0 + 1e-6:
            return 0, ""
        return 1, "Close-range Eradication"

    def _shadow_masters_attack_distance(
        self,
        target_unit,
        *,
        attacker_model=None,
        attack_instance=None,
    ) -> float:
        try:
            distance = float((attack_instance or {}).get("distance_to_target", 0.0) or 0.0)
        except Exception:
            distance = 0.0
        if distance > 0.0:
            return float(distance)
        if attacker_model is None or target_unit is None:
            return 0.0
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        if attacker_unit is None:
            return 0.0
        try:
            game_map = getattr(getattr(attacker_unit.get_parent_army(), "player", None), "game", None).map
        except Exception:
            game_map = None
        if game_map is None:
            return 0.0
        try:
            return float(game_map.get_distance_between_units(attacker_unit, target_unit))
        except Exception:
            return 0.0

    def shadow_masters_applies(self, target_unit) -> bool:
        if not (self.is_vanguard_spearhead() or self.is_shadowmark_talon()):
            return False
        if target_unit is None:
            return False
        return self.attached_unit_is_adeptus_astartes(target_unit)

    def _shadow_masters_source_name(self) -> str:
        if self.is_shadowmark_talon():
            return "Masters of Shadow"
        return "Shadow Masters"

    def shadow_masters_ranged_hit_penalty(
        self,
        target_unit,
        *,
        attacker_model=None,
        attack_instance=None,
    ) -> tuple[int, str]:
        if not self.shadow_masters_applies(target_unit):
            return 0, ""
        distance = self._shadow_masters_attack_distance(
            target_unit,
            attacker_model=attacker_model,
            attack_instance=attack_instance,
        )
        if distance <= 0.0 or distance <= 12.0 + 1e-6:
            return 0, ""
        return 1, self._shadow_masters_source_name()

    def shadow_masters_benefit_of_cover(
        self,
        target_unit,
        *,
        attacker_model=None,
        attack_instance=None,
    ) -> tuple[bool, str]:
        penalty, source = self.shadow_masters_ranged_hit_penalty(
            target_unit,
            attacker_model=attacker_model,
            attack_instance=attack_instance,
        )
        return bool(penalty > 0), source

    def storm_swift_onslaught_charge_after_advance_applies(self, unit) -> bool:
        if not self.is_spearpoint_task_force():
            return False
        if unit is None:
            return False
        return self.attached_unit_is_adeptus_astartes(unit)

    def storm_swift_onslaught_charge_after_fall_back_applies(self, unit) -> bool:
        return self.storm_swift_onslaught_charge_after_advance_applies(unit)

    def wrath_of_the_first_khan_applies(self, unit) -> bool:
        if not self.is_spearpoint_task_force():
            return False
        if unit is None:
            return False
        if not self.attached_unit_is_adeptus_astartes(unit):
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return False
        root_name = str(getattr(root, "name", "") or "").strip().upper()
        if "SUBODEN KHAN" in root_name:
            return True
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for model in models:
            model_name = str(getattr(model, "name", "") or "").strip().upper()
            if "SUBODEN KHAN" in model_name:
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

    def red_thirst_applies(self, unit) -> bool:
        if unit is None:
            return False
        if not self.is_liberator_assault_group():
            return False
        return self.attached_unit_is_adeptus_astartes(unit)

    def maddened_ferocity_applies(self, unit) -> bool:
        if unit is None:
            return False
        if not self.is_rage_cursed_onslaught():
            return False
        return self.attached_unit_is_adeptus_astartes(unit)

    def has_aethon_shaan_on_battlefield(self) -> bool:
        army = self.army
        if army is None:
            return False

        def _unit_matches(unit) -> bool:
            if unit is None:
                return False
            name = str(getattr(unit, "name", "") or "").strip().upper()
            if "AETHON SHAAN" not in name:
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

    def can_use_unparalleled_tactician_into_darkness_discount(self, *, game=None) -> bool:
        if not self.is_shadowmark_talon():
            return False
        if not self.has_aethon_shaan_on_battlefield():
            return False
        game_obj = game
        if game_obj is None:
            game_obj = getattr(getattr(self.army, "player", None), "game", None) if self.army is not None else None
        if game_obj is None:
            return False
        try:
            battle_round = int(getattr(game_obj, "turn", 0) or 0)
        except Exception:
            return False
        if battle_round <= 0:
            return False
        return int(getattr(self, "unparalleled_tactician_used_round", 0) or 0) != battle_round

    def mark_unparalleled_tactician_used(self, *, game=None) -> None:
        game_obj = game
        if game_obj is None:
            game_obj = getattr(getattr(self.army, "player", None), "game", None) if self.army is not None else None
        if game_obj is None:
            return
        try:
            battle_round = int(getattr(game_obj, "turn", 0) or 0)
        except Exception:
            return
        if battle_round <= 0:
            return
        self.unparalleled_tactician_used_round = battle_round

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
