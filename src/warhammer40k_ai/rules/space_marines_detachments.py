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
    _LIBRARIUS_DISCIPLINE_BIOMANCY = "BIOMANCY"
    _LIBRARIUS_DISCIPLINE_DIVINATION = "DIVINATION"
    _LIBRARIUS_DISCIPLINE_PYROMANCY = "PYROMANCY"
    _LIBRARIUS_DISCIPLINE_TELEKINESIS = "TELEKINESIS"
    _LIBRARIUS_DISCIPLINE_TELEPATHY = "TELEPATHY"
    _LIBRARIUS_DISCIPLINE_KEYS = (
        _LIBRARIUS_DISCIPLINE_BIOMANCY,
        _LIBRARIUS_DISCIPLINE_DIVINATION,
        _LIBRARIUS_DISCIPLINE_PYROMANCY,
        _LIBRARIUS_DISCIPLINE_TELEKINESIS,
        _LIBRARIUS_DISCIPLINE_TELEPATHY,
    )
    _LIBRARIUS_DISCIPLINE_LABELS = {
        _LIBRARIUS_DISCIPLINE_BIOMANCY: "Biomancy Discipline",
        _LIBRARIUS_DISCIPLINE_DIVINATION: "Divination Discipline",
        _LIBRARIUS_DISCIPLINE_PYROMANCY: "Pyromancy Discipline",
        _LIBRARIUS_DISCIPLINE_TELEKINESIS: "Telekinesis Discipline",
        _LIBRARIUS_DISCIPLINE_TELEPATHY: "Telepathy Discipline",
    }
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
        self.librarius_psychic_discipline_key: str = ""
        self.librarius_psychic_discipline_round: int = 0
        self.librarius_psychic_discipline_player_id: str = ""
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
        self.armoured_wrath_used_phase_key_by_unit_id: dict[str, str] = {}
        self.vowed_target_mode: str = ""
        self.vowed_objective_ids: tuple[str, ...] = ()
        self.vowed_target_selected_round: int = 0
        self.vowed_target_selected_player_id: str = ""

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

    def is_librarius_conclave(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Librarius Conclave")

    def is_anvil_siege_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Anvil Siege Force")

    def is_ironstorm_spearhead(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Ironstorm Spearhead")

    def is_bastion_task_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Bastion Task Force")

    def is_lions_blade_task_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Lion's Blade Task Force")

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

    def is_champions_of_fenris(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Champions of Fenris")

    def is_forgefathers_seekers(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Forgefather's Seekers")

    def is_godhammer_assault_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Godhammer Assault Force")

    def is_inner_circle_task_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Inner Circle Task Force")

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

    def _unit_is_on_battlefield(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_has_models_or_is_alive(unit):
            return False
        if not bool(getattr(unit, "deployed", True)):
            return False
        in_reserves_fn = getattr(unit, "is_in_reserves", None)
        if callable(in_reserves_fn):
            try:
                if bool(in_reserves_fn()):
                    return False
            except Exception:
                return False
        if bool(getattr(unit, "is_embarked", False)):
            return False
        return True

    def _resolve_game_context(self, game=None):
        if game is not None:
            return game
        try:
            return getattr(getattr(self.army, "player", None), "game", None)
        except Exception:
            return None

    def _is_army_turn(self, *, game=None) -> bool:
        game_obj = self._resolve_game_context(game=game)
        if game_obj is None:
            return False
        owner_id = str(getattr(getattr(self.army, "player", None), "id", "") or "").strip()
        if not owner_id:
            return False
        try:
            current = game_obj.get_current_player()
        except Exception:
            current = None
        current_id = str(getattr(current, "id", "") or "").strip()
        return bool(current_id) and current_id == owner_id

    @classmethod
    def librarius_psychic_discipline_label(cls, key: str) -> str:
        norm = str(key or "").strip().upper()
        return cls._LIBRARIUS_DISCIPLINE_LABELS.get(norm, str(key or "").strip())

    @classmethod
    def _normalize_librarius_psychic_discipline_key(cls, value: str) -> str:
        raw = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
        if raw in cls._LIBRARIUS_DISCIPLINE_KEYS:
            return raw
        if raw in {"BIOMANCY_DISCIPLINE", "BIOMANCYDISCIPLINE"}:
            return cls._LIBRARIUS_DISCIPLINE_BIOMANCY
        if raw in {"DIVINATION_DISCIPLINE", "DIVINATIONDISCIPLINE"}:
            return cls._LIBRARIUS_DISCIPLINE_DIVINATION
        if raw in {"PYROMANCY_DISCIPLINE", "PYROMANCYDISCIPLINE"}:
            return cls._LIBRARIUS_DISCIPLINE_PYROMANCY
        if raw in {"TELEKINESIS_DISCIPLINE", "TELEKINESISDISCIPLINE"}:
            return cls._LIBRARIUS_DISCIPLINE_TELEKINESIS
        if raw in {"TELEPATHY_DISCIPLINE", "TELEPATHYDISCIPLINE"}:
            return cls._LIBRARIUS_DISCIPLINE_TELEPATHY
        return raw

    def _librarius_unit_is_eligible_psyker(self, unit) -> bool:
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
        return bool(self._attached_unit_has_keyword(root, "PSYKER"))

    def _librarius_model_is_eligible_psyker(self, model) -> bool:
        if model is None:
            return False
        unit = getattr(model, "parent_unit", None)
        if unit is None:
            return False
        return self._librarius_unit_is_eligible_psyker(unit)

    def _clear_librarius_biomancy_temporary_effects(self) -> None:
        if self.army is None:
            return
        for root in self._iter_unique_army_roots():
            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                members = [root]
            if not members:
                members = [root]
            for member in members:
                for model in list(getattr(member, "models", []) or []):
                    effects = getattr(model, "_temporary_effects", None)
                    if not isinstance(effects, dict):
                        continue
                    effects.pop("librarius_psychic_disciplines_biomancy", None)
                    model._temporary_effects = effects

    def _apply_librarius_biomancy_temporary_effects(self) -> None:
        if self.army is None:
            return
        for root in self._iter_unique_army_roots():
            if not self._librarius_unit_is_eligible_psyker(root):
                continue
            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                members = [root]
            if not members:
                members = [root]
            for member in members:
                for model in list(getattr(member, "models", []) or []):
                    effects = getattr(model, "_temporary_effects", None)
                    if not isinstance(effects, dict):
                        effects = {}
                    effects["librarius_psychic_disciplines_biomancy"] = {
                        "movement_bonus": 2,
                        "movement_bonus_source": "Psychic Disciplines (Biomancy)",
                    }
                    model._temporary_effects = effects

    def clear_librarius_psychic_discipline(self) -> None:
        self.librarius_psychic_discipline_key = ""
        self.librarius_psychic_discipline_round = 0
        self.librarius_psychic_discipline_player_id = ""
        self._clear_librarius_biomancy_temporary_effects()

    def get_available_librarius_psychic_disciplines(self) -> list[str]:
        return list(self._LIBRARIUS_DISCIPLINE_KEYS)

    def can_select_librarius_psychic_discipline(self, *, game=None) -> bool:
        if not self.is_librarius_conclave():
            return False
        if game is None:
            return True
        try:
            round_now = int(getattr(game, "turn", 0) or 0)
        except Exception:
            return False
        if round_now <= 0:
            return False
        owner_id = str(getattr(getattr(self.army, "player", None), "id", "") or "")
        if (
            int(getattr(self, "librarius_psychic_discipline_round", 0) or 0) == round_now
            and str(getattr(self, "librarius_psychic_discipline_player_id", "") or "") == owner_id
            and str(getattr(self, "librarius_psychic_discipline_key", "") or "").strip().upper() in self._LIBRARIUS_DISCIPLINE_KEYS
        ):
            return False
        return True

    def librarius_psychic_discipline_is_active(self, key: str, *, game=None, battle_round=None) -> bool:
        choice_key = self._normalize_librarius_psychic_discipline_key(key)
        active_key = str(getattr(self, "librarius_psychic_discipline_key", "") or "").strip().upper()
        if active_key != choice_key:
            return False
        try:
            selected_round = int(getattr(self, "librarius_psychic_discipline_round", 0) or 0)
        except Exception:
            return False
        if selected_round <= 0:
            return False
        if battle_round is None:
            game_obj = self._resolve_game_context(game=game)
            if game_obj is not None:
                try:
                    battle_round = int(getattr(game_obj, "turn", 0) or 0)
                except Exception:
                    battle_round = None
        if battle_round is None:
            return True
        try:
            return int(selected_round) == int(battle_round or 0)
        except Exception:
            return False

    def select_librarius_psychic_discipline(self, choice_key: str, *, battle_round=None, player_id: str = "") -> bool:
        if not self.is_librarius_conclave():
            return False
        key = self._normalize_librarius_psychic_discipline_key(choice_key)
        if key not in self._LIBRARIUS_DISCIPLINE_KEYS:
            return False
        self._clear_librarius_biomancy_temporary_effects()
        self.librarius_psychic_discipline_key = key
        if battle_round is not None:
            try:
                self.librarius_psychic_discipline_round = int(battle_round or 0)
            except Exception:
                self.librarius_psychic_discipline_round = 0
        self.librarius_psychic_discipline_player_id = str(player_id or "")
        if key == self._LIBRARIUS_DISCIPLINE_BIOMANCY:
            self._apply_librarius_biomancy_temporary_effects()
        return True

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if not self.is_librarius_conclave():
            self.clear_librarius_psychic_discipline()
            return
        self.clear_librarius_psychic_discipline()
        game_obj = self._resolve_game_context(game=game)
        if game_obj is None or not bool(getattr(game_obj, "is_authoritative", True)):
            return
        try:
            round_now = int(battle_round or getattr(game_obj, "turn", 0) or 0)
        except Exception:
            round_now = int(getattr(game_obj, "turn", 0) or 0)
        if round_now <= 0:
            return
        if not self.can_select_librarius_psychic_discipline(game=game_obj):
            return
        player = getattr(self.army, "player", None) if self.army is not None else None
        if player is None:
            return
        try:
            from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
            from ..engine.decisions import DecisionOption, DecisionRequest
        except Exception:
            return
        army_id = str(get_entity_id(self.army) or "")
        player_id = str(getattr(player, "id", "") or "")
        queue = getattr(game_obj, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            stale_ids: list[str] = []
            has_pending = False
            for request in list(queue.list() or []):
                if str(getattr(request, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                context = dict(getattr(request, "context", {}) or {})
                if str(context.get("ability", "") or "") != "librarius_psychic_disciplines":
                    continue
                if str(context.get("army_id", "") or "") != army_id:
                    continue
                request_round = int(context.get("battle_round", 0) or 0)
                if request_round == round_now:
                    has_pending = True
                    break
                stale_ids.append(str(getattr(request, "decision_id", "") or ""))
            for decision_id in stale_ids:
                if decision_id:
                    queue.pop(decision_id)
            if has_pending:
                return
        summaries = {
            self._LIBRARIUS_DISCIPLINE_BIOMANCY: 'Add 2" to Move for ADEPTUS ASTARTES PSYKER units.',
            self._LIBRARIUS_DISCIPLINE_DIVINATION: "Re-roll Hit roll of 1 and Wound roll of 1 for ADEPTUS ASTARTES PSYKER units.",
            self._LIBRARIUS_DISCIPLINE_PYROMANCY: 'Ranged attacks by ADEPTUS ASTARTES PSYKER units improve AP by 1 within 12".',
            self._LIBRARIUS_DISCIPLINE_TELEKINESIS: "Ranged attacks targeting ADEPTUS ASTARTES PSYKER units suffer -1 Strength.",
            self._LIBRARIUS_DISCIPLINE_TELEPATHY: "ADEPTUS ASTARTES PSYKER units can ignore Hit roll and WS/BS modifiers.",
        }
        options = []
        for key in self.get_available_librarius_psychic_disciplines():
            label = self.librarius_psychic_discipline_label(key)
            options.append(
                DecisionOption.create(
                    label,
                    payload={
                        "choice_key": key,
                        "choice_name": label,
                        "summary": str(summaries.get(key, label) or label),
                        "army_id": army_id,
                    },
                )
            )
        if not options:
            return
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Psychic Disciplines: select one discipline for this battle round.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "librarius_psychic_disciplines",
                "ability_name": "Psychic Disciplines",
                "army_id": army_id,
                "player_id": player_id,
                "battle_round": int(round_now),
                "allowed_choice_keys": list(self._LIBRARIUS_DISCIPLINE_KEYS),
            },
        )
        if hasattr(game_obj, "request_decision"):
            game_obj.request_decision(request)

    def librarius_divination_reroll_hit_wound_ones(self, attacker_model, *, game=None) -> tuple[bool, bool, str]:
        if not self.librarius_psychic_discipline_is_active(self._LIBRARIUS_DISCIPLINE_DIVINATION, game=game):
            return False, False, ""
        if not self._librarius_model_is_eligible_psyker(attacker_model):
            return False, False, ""
        return True, True, "Psychic Disciplines (Divination)"

    def librarius_pyromancy_ap_bonus(
        self,
        attacker_model,
        target_unit=None,
        *,
        weapon_profile=None,
        attack_instance=None,
        game=None,
    ) -> tuple[int, str]:
        if not self.librarius_psychic_discipline_is_active(self._LIBRARIUS_DISCIPLINE_PYROMANCY, game=game):
            return 0, ""
        if not self._librarius_model_is_eligible_psyker(attacker_model):
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            if parent is None or not bool(getattr(parent, "is_ranged", lambda: False)()):
                return 0, ""
        distance = 0.0
        try:
            distance = float((attack_instance or {}).get("distance_to_target", 0.0) or 0.0)
        except Exception:
            distance = 0.0
        if distance <= 0.0 and attacker_model is not None and target_unit is not None:
            attacker_unit = getattr(attacker_model, "parent_unit", None)
            if attacker_unit is not None:
                try:
                    attacker_root = attacker_unit.get_attached_unit_root()
                except Exception:
                    attacker_root = attacker_unit
                try:
                    target_root = target_unit.get_attached_unit_root()
                except Exception:
                    target_root = target_unit
                game_obj = self._resolve_game_context(game=game)
                game_map = getattr(game_obj, "map", None) if game_obj is not None else None
                if game_map is not None and attacker_root is not None and target_root is not None:
                    try:
                        distance = float(game_map.get_distance_between_units(attacker_root, target_root))
                    except Exception:
                        distance = 0.0
        if distance <= 0.0 or distance > 12.0 + 1e-6:
            return 0, ""
        return 1, "Psychic Disciplines (Pyromancy)"

    def librarius_telekinesis_strength_penalty(
        self,
        target_unit,
        *,
        attacker_model=None,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        if not self.librarius_psychic_discipline_is_active(self._LIBRARIUS_DISCIPLINE_TELEKINESIS, game=game):
            return 0, ""
        if not self._librarius_unit_is_eligible_psyker(target_unit):
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            if parent is None or not bool(getattr(parent, "is_ranged", lambda: False)()):
                return 0, ""
        return 1, "Psychic Disciplines (Telekinesis)"

    def librarius_telepathy_ignore_hit_modifiers_rule(self, attacker_model, *, game=None) -> dict | None:
        if not self.librarius_psychic_discipline_is_active(self._LIBRARIUS_DISCIPLINE_TELEPATHY, game=game):
            return None
        if not self._librarius_model_is_eligible_psyker(attacker_model):
            return None
        return {
            "name": "Psychic Disciplines (Telepathy)",
            "attack_type": "any",
            "skill_kinds": {"ballistic", "weapon"},
            "allow_hit": True,
            "default_choice": "ignore_negative",
        }

    def _attached_unit_name_contains(self, unit, name_fragment: str) -> bool:
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        unit_name = _normalize_detachment_name(getattr(root, "name", ""))
        target = _normalize_detachment_name(name_fragment)
        if not target:
            return False
        return target in unit_name

    def _attached_unit_disembarked_from_transport_this_round(self, unit) -> bool:
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        round_state = getattr(root, "round_state", None)
        if round_state is None:
            return False
        if not bool(getattr(round_state, "disembarked_this_round", False)):
            return False
        transport_id = str(getattr(round_state, "disembarked_from_transport_id", "") or "").strip()
        return bool(transport_id)

    def _attached_unit_is_terminator(self, unit) -> bool:
        if unit is None:
            return False
        if self._attached_unit_has_keyword(unit, "TERMINATOR"):
            return True
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        name = str(getattr(root, "name", "") or "").strip().lower()
        return "terminator" in name

    def great_wolf_watches_reacting_unit_is_eligible(self, unit, *, game=None) -> bool:
        if not self.is_champions_of_fenris():
            return False
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        try:
            if root.get_parent_army() is not self.army:
                return False
        except Exception:
            return False
        if not self._unit_is_on_battlefield(root):
            return False
        if not self.attached_unit_is_adeptus_astartes(root):
            return False
        has_infantry = self._attached_unit_has_keyword(root, "INFANTRY")
        has_walker = self._attached_unit_has_keyword(root, "WALKER")
        if not (has_infantry or has_walker):
            return False
        if game is not None:
            can_charge = getattr(root, "can_declare_charge", None)
            if callable(can_charge):
                try:
                    if not bool(can_charge(game, out_of_turn=True)):
                        return False
                except Exception:
                    return False
        return True

    def great_wolf_watches_charge_target_is_eligible(
        self,
        reacting_unit,
        target_unit,
        *,
        game=None,
        range_inches: float = 3.0,
    ) -> bool:
        if game is None:
            return False
        if not self.great_wolf_watches_reacting_unit_is_eligible(reacting_unit, game=game):
            return False
        game_map = getattr(game, "map", None)
        if game_map is None:
            return False
        reacting_root = self._attached_unit_root(reacting_unit)
        target_root = self._attached_unit_root(target_unit)
        if reacting_root is None or target_root is None:
            return False
        if not self._unit_is_on_battlefield(target_root):
            return False
        try:
            if target_root.get_parent_army() is self.army:
                return False
        except Exception:
            return False
        try:
            distance = float(game_map.get_distance_between_units(reacting_root, target_root))
        except Exception:
            return False
        if distance > float(range_inches) + 1e-6:
            return False
        can_target = getattr(reacting_root, "can_declare_charge_against", None)
        if not callable(can_target):
            return False
        try:
            return bool(can_target(target_root, game, out_of_turn=True))
        except Exception:
            return False

    def great_wolf_watches_charge_target_units(self, unit, *, game=None) -> list:
        if game is None:
            return []
        if not self.great_wolf_watches_reacting_unit_is_eligible(unit, game=game):
            return []
        reacting_root = self._attached_unit_root(unit)
        if reacting_root is None:
            return []
        game_map = getattr(game, "map", None)
        if game_map is None:
            return []
        try:
            enemies = list(game_map.get_enemy_units(reacting_root) or [])
        except Exception:
            enemies = []
        targets = []
        seen: set[str] = set()
        for enemy in list(enemies or []):
            enemy_root = self._attached_unit_root(enemy)
            if enemy_root is None:
                continue
            target_id = str(get_entity_id(enemy_root) or "")
            if target_id and target_id in seen:
                continue
            if not self.great_wolf_watches_charge_target_is_eligible(
                reacting_root,
                enemy_root,
                game=game,
            ):
                continue
            if target_id:
                seen.add(target_id)
            targets.append(enemy_root)
        targets.sort(key=lambda u: (str(getattr(u, "name", "") or ""), str(get_entity_id(u) or "")))
        return targets

    def get_great_wolf_watches_charge_options(self, *, game=None) -> list[tuple]:
        if not self.is_champions_of_fenris():
            return []
        options = []
        for root in self._iter_unique_army_roots():
            if not self.great_wolf_watches_reacting_unit_is_eligible(root, game=game):
                continue
            targets = self.great_wolf_watches_charge_target_units(root, game=game)
            if not targets:
                continue
            options.append((root, targets))
        options.sort(
            key=lambda entry: (
                str(getattr(entry[0], "name", "") or ""),
                str(get_entity_id(entry[0]) or ""),
            )
        )
        return options

    def great_wolf_watches_terminator_oc_bonus(self, unit) -> tuple[int, str]:
        if not self.is_champions_of_fenris():
            return 0, ""
        root = self._attached_unit_root(unit)
        if root is None:
            return 0, ""
        if not self.attached_unit_is_adeptus_astartes(root):
            return 0, ""
        if not self._attached_unit_is_terminator(root):
            return 0, ""
        is_bs_fn = getattr(root, "is_battle_shocked", None)
        if callable(is_bs_fn):
            try:
                if bool(is_bs_fn()):
                    return 0, ""
            except Exception:
                return 0, ""
        return 1, "The Great Wolf Watches"

    def has_vulkan_hestan_on_battlefield(self) -> bool:
        if self.army is None:
            return False
        for root in self._iter_unique_army_roots():
            if not self._unit_is_on_battlefield(root):
                continue
            if self._attached_unit_name_contains(root, "Vulkan He'Stan"):
                return True
        return False

    def _attached_unit_is_infernus_squad(self, unit) -> bool:
        return self._attached_unit_name_contains(unit, "Infernus Squad")

    def vulkans_quest_assault_applies(self, unit, weapon_profile=None) -> bool:
        if not self.is_forgefathers_seekers():
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

    def vulkans_quest_strength_bonus(
        self,
        attacker_model,
        target_unit=None,
        *,
        weapon_profile=None,
        attack_instance=None,
    ) -> tuple[int, str]:
        if not self.is_forgefathers_seekers():
            return 0, ""
        if attacker_model is None:
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        if attacker_unit is None:
            return 0, ""
        if not self.vulkans_quest_assault_applies(attacker_unit, weapon_profile):
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
        return 1, "Vulkan's Quest"

    def seekers_companions_active_for_unit(self, unit, *, game=None) -> bool:
        if not self.is_forgefathers_seekers():
            return False
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        if not self._unit_is_on_battlefield(root):
            return False
        if not self.attached_unit_is_adeptus_astartes(root):
            return False
        if not self._attached_unit_is_infernus_squad(root):
            return False
        if not self.has_vulkan_hestan_on_battlefield():
            return False
        return self._is_army_turn(game=game)

    def seekers_companions_allow_action_after_advance(self, unit, game) -> bool:
        if game is None:
            return False
        if not self.seekers_companions_active_for_unit(unit, game=game):
            return False
        for flag in ("actions_enabled", "mission_actions_enabled", "mission_has_actions"):
            try:
                enabled = getattr(game, flag)
            except Exception:
                continue
            if enabled is False:
                return False
        return True

    def seekers_companions_allow_shoot_while_action(self, unit, *, game=None, weapon_profile=None) -> bool:
        if not self.seekers_companions_active_for_unit(unit, game=game):
            return False
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            if parent is not None and not bool(getattr(parent, "is_ranged", lambda: False)()):
                return False
        round_state = getattr(root, "round_state", None)
        if round_state is None:
            return False
        if not bool(getattr(round_state, "action_locked_until_turn_end", False)):
            return False
        if not bool(getattr(round_state, "performing_action_name", None)):
            return False
        game_obj = self._resolve_game_context(game=game)
        if game_obj is None:
            return False
        try:
            started_turn = int(getattr(round_state, "action_started_turn", 0) or 0)
            battle_round = int(getattr(game_obj, "turn", 0) or 0)
        except Exception:
            return False
        return started_turn > 0 and started_turn == battle_round

    def _armoured_wrath_phase_key(self, *, game=None, unit=None) -> str:
        game_obj = self._resolve_game_context(game=game)
        if game_obj is None and unit is not None:
            try:
                game_obj = getattr(getattr(unit.get_parent_army(), "player", None), "game", None)
            except Exception:
                game_obj = None
        if game_obj is None:
            return ""
        try:
            battle_round = int(getattr(game_obj, "turn", 0) or 0)
        except (TypeError, ValueError):
            battle_round = 0
        phase_name = str(getattr(getattr(game_obj, "phase", None), "name", "") or "").strip().upper()
        current_player = getattr(game_obj, "get_current_player", lambda: None)()
        if current_player is None:
            current_player = getattr(self.army, "player", None) if self.army is not None else None
        owner_id = str(getattr(current_player, "id", "") or "")
        return f"{battle_round}:{phase_name}:{owner_id}"

    def armoured_wrath_reroll_is_available(self, unit, kind: str, *, game=None) -> bool:
        if not self.is_ironstorm_spearhead():
            return False
        kind_key = str(kind or "").strip().lower()
        if kind_key not in {"hit", "wound", "damage"}:
            return False
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        if not self.attached_unit_is_adeptus_astartes(root):
            return False
        phase_key = self._armoured_wrath_phase_key(game=game, unit=root)
        if not phase_key:
            return False
        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            return False
        return str(self.armoured_wrath_used_phase_key_by_unit_id.get(unit_id, "") or "") != phase_key

    def consume_armoured_wrath_reroll(self, unit, kind: str, *, game=None) -> bool:
        if not self.armoured_wrath_reroll_is_available(unit, kind, game=game):
            return False
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            return False
        phase_key = self._armoured_wrath_phase_key(game=game, unit=root)
        if not phase_key:
            return False
        self.armoured_wrath_used_phase_key_by_unit_id[unit_id] = phase_key
        return True

    def in_the_lions_claws_ravenwing_source_applies(self, source_unit, enemy_unit=None, *, game=None) -> bool:
        if not self.is_lions_blade_task_force():
            return False
        source_root = self._attached_unit_root(source_unit)
        if source_root is None:
            return False
        try:
            if source_root.get_parent_army() is not self.army:
                return False
        except Exception:
            return False
        if not self._unit_is_on_battlefield(source_root):
            return False
        if not self.attached_unit_is_adeptus_astartes(source_root):
            return False
        if not self._attached_unit_has_keyword(source_root, "RAVENWING"):
            return False
        if enemy_unit is not None:
            enemy_root = self._attached_unit_root(enemy_unit)
            if enemy_root is None:
                return False
            try:
                if enemy_root.get_parent_army() is self.army:
                    return False
            except Exception:
                return False
        return True

    def in_the_lions_claws_charge_roll_bonus(self, charging_unit, target_units=None, *, game=None) -> tuple[int, str]:
        if not self.is_lions_blade_task_force():
            return 0, ""
        charging_root = self._attached_unit_root(charging_unit)
        if charging_root is None:
            return 0, ""
        try:
            if charging_root.get_parent_army() is not self.army:
                return 0, ""
        except Exception:
            return 0, ""
        if not self._unit_is_on_battlefield(charging_root):
            return 0, ""
        if not self.attached_unit_is_adeptus_astartes(charging_root):
            return 0, ""
        if not self._attached_unit_has_keyword(charging_root, "DEATHWING"):
            return 0, ""
        if target_units is None:
            return 0, ""
        targets = list(target_units) if isinstance(target_units, (list, tuple, set)) else [target_units]
        targets = [t for t in targets if t is not None]
        if not targets:
            return 0, ""
        game_obj = self._resolve_game_context(game=game)
        if game_obj is None:
            return 0, ""
        game_map = getattr(game_obj, "map", None)
        if game_map is None or not hasattr(game_map, "is_within_engagement_range"):
            return 0, ""
        ravenwing_sources = []
        seen_source_ids: set[str] = set()
        for candidate in list(getattr(self.army, "units", []) or []):
            candidate_root = self._attached_unit_root(candidate)
            if candidate_root is None:
                continue
            candidate_id = str(get_entity_id(candidate_root) or "")
            if candidate_id and candidate_id in seen_source_ids:
                continue
            if candidate_id:
                seen_source_ids.add(candidate_id)
            if not self._unit_is_on_battlefield(candidate_root):
                continue
            if not self.attached_unit_is_adeptus_astartes(candidate_root):
                continue
            if not self._attached_unit_has_keyword(candidate_root, "RAVENWING"):
                continue
            ravenwing_sources.append(candidate_root)
        if not ravenwing_sources:
            return 0, ""
        for target in targets:
            target_root = self._attached_unit_root(target)
            if target_root is None:
                continue
            if not self._unit_is_on_battlefield(target_root):
                continue
            try:
                if target_root.get_parent_army() is self.army:
                    continue
            except Exception:
                continue
            for source_root in list(ravenwing_sources or []):
                try:
                    if bool(game_map.is_within_engagement_range(target_root, source_root)):
                        return 2, "In The Lion's Claws"
                except Exception:
                    continue
        return 0, ""

    def clear_vowed_target_selection(self) -> None:
        self.vowed_target_mode = ""
        self.vowed_objective_ids = ()
        self.vowed_target_selected_round = 0
        self.vowed_target_selected_player_id = ""

    def _vowed_target_objective_records(self, *, game=None) -> list[tuple[str, str, object, bool]]:
        game_obj = self._resolve_game_context(game=game)
        if game_obj is None:
            return []
        game_map = getattr(game_obj, "map", None)
        if game_map is None:
            return []
        owner = getattr(self.army, "player", None) if self.army is not None else None
        records = []
        seen_ids: set[str] = set()
        for objective in list(getattr(game_map, "objectives", []) or []):
            location = getattr(objective, "location", None) or objective
            if location is None or bool(getattr(location, "removed", False)):
                continue
            objective_id = str(get_entity_id(objective) or get_entity_id(location) or "").strip()
            if not objective_id or objective_id in seen_ids:
                continue
            seen_ids.add(objective_id)
            update_control = getattr(location, "update_control", None)
            if callable(update_control):
                update_control(game_obj)
            controlled = bool(owner is not None and getattr(location, "controlling_player", None) is owner)
            name = str(getattr(objective, "name", "") or getattr(location, "name", "")).strip()
            if not name:
                name = f"Objective {len(records) + 1}"
            records.append((objective_id, name, location, controlled))
        records.sort(key=lambda row: (str(row[1] or ""), str(row[0] or "")))
        return records

    def can_select_vowed_target(self, *, game=None) -> bool:
        if not self.is_inner_circle_task_force():
            return False
        if game is None:
            return True
        if not self._is_army_turn(game=game):
            return False
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_name and phase_name != "MOVEMENT_PHASE":
            return False
        try:
            battle_round = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            battle_round = 0
        if battle_round <= 0:
            return False
        player_id = str(getattr(getattr(self.army, "player", None), "id", "") or "")
        if (
            int(self.vowed_target_selected_round or 0) == int(battle_round)
            and str(self.vowed_target_selected_player_id or "") == player_id
            and bool(self.vowed_objective_ids)
        ):
            return False
        return bool(self._vowed_target_objective_records(game=game))

    def get_vowed_target_options(self, *, game=None) -> list[dict[str, object]]:
        game_obj = self._resolve_game_context(game=game)
        if game_obj is None:
            return []
        records = list(self._vowed_target_objective_records(game=game_obj) or [])
        if not records:
            return []
        controlled = [(oid, name) for oid, name, _loc, is_controlled in records if is_controlled]
        not_controlled = [(oid, name) for oid, name, _loc, is_controlled in records if not is_controlled]
        options: list[dict[str, object]] = []
        for objective_id, name in controlled:
            payload = {
                "mode": "defensive_footing",
                "objective_ids": [str(objective_id)],
            }
            payload["signature"] = f"{payload['mode']}:{objective_id}"
            options.append(
                {
                    "label": f"Defensive Footing: {name}",
                    "summary": f"Select {name} as your Vowed objective marker.",
                    "payload": payload,
                    "mode_sort": 0,
                    "count_sort": 1,
                }
            )
        sorted_uncontrolled = list(not_controlled)
        sorted_uncontrolled.sort(key=lambda row: (str(row[1] or ""), str(row[0] or "")))
        for count in range(1, len(sorted_uncontrolled) + 1):
            for combo in combinations(sorted_uncontrolled, count):
                objective_ids = [str(entry[0]) for entry in combo]
                names = [str(entry[1]) for entry in combo]
                joined_names = ", ".join(names)
                payload = {
                    "mode": "aggressive_push",
                    "objective_ids": list(objective_ids),
                }
                payload["signature"] = f"{payload['mode']}:{'|'.join(objective_ids)}"
                options.append(
                    {
                        "label": f"Aggressive Push: {joined_names}",
                        "summary": f"Select {joined_names} as your Vowed objective markers.",
                        "payload": payload,
                        "mode_sort": 1,
                        "count_sort": int(len(objective_ids)),
                    }
                )
        options.sort(
            key=lambda entry: (
                int(entry.get("mode_sort", 99) or 99),
                int(entry.get("count_sort", 99) or 99),
                str(entry.get("label", "") or ""),
                str((entry.get("payload", {}) or {}).get("signature", "") or ""),
            )
        )
        for entry in options:
            entry.pop("mode_sort", None)
            entry.pop("count_sort", None)
        return options

    def vowed_target_option_is_valid(self, mode: str, objective_ids, *, game=None) -> bool:
        normalized_mode = str(mode or "").strip().lower()
        if normalized_mode not in {"defensive_footing", "aggressive_push"}:
            return False
        objective_id_list = [str(v or "").strip() for v in list(objective_ids or []) if str(v or "").strip()]
        objective_id_list = list(dict.fromkeys(objective_id_list))
        if normalized_mode == "defensive_footing":
            if len(objective_id_list) != 1:
                return False
        else:
            if len(objective_id_list) <= 0:
                return False
        records = {str(oid): bool(controlled) for oid, _name, _loc, controlled in self._vowed_target_objective_records(game=game)}
        if not records:
            return False
        for objective_id in objective_id_list:
            if objective_id not in records:
                return False
            controlled = bool(records.get(objective_id))
            if normalized_mode == "defensive_footing" and not controlled:
                return False
            if normalized_mode == "aggressive_push" and controlled:
                return False
        return True

    def select_vowed_target(self, mode: str, objective_ids, *, game=None) -> bool:
        if not self.is_inner_circle_task_force():
            return False
        game_obj = self._resolve_game_context(game=game)
        if game_obj is not None and not self.can_select_vowed_target(game=game_obj):
            return False
        if not self.vowed_target_option_is_valid(mode, objective_ids, game=game_obj):
            return False
        normalized_mode = str(mode or "").strip().lower()
        objective_id_list = [str(v or "").strip() for v in list(objective_ids or []) if str(v or "").strip()]
        objective_id_list = list(dict.fromkeys(objective_id_list))
        objective_id_list.sort()
        self.vowed_target_mode = normalized_mode
        self.vowed_objective_ids = tuple(objective_id_list)
        if game_obj is not None:
            try:
                self.vowed_target_selected_round = int(getattr(game_obj, "turn", 0) or 0)
            except (TypeError, ValueError):
                self.vowed_target_selected_round = 0
        self.vowed_target_selected_player_id = str(getattr(getattr(self.army, "player", None), "id", "") or "")
        return True

    def vowed_target_objective_locations(self, *, game=None) -> list:
        selected_ids = {str(v or "").strip() for v in list(self.vowed_objective_ids or ()) if str(v or "").strip()}
        if not selected_ids:
            return []
        records = self._vowed_target_objective_records(game=game)
        out = []
        for objective_id, _name, location, _controlled in records:
            if str(objective_id or "").strip() not in selected_ids:
                continue
            out.append(location)
        return out

    def vowed_target_wound_bonus(
        self,
        attacker_model,
        target_unit=None,
        *,
        weapon_profile=None,
        attack_instance=None,
    ) -> tuple[int, str]:
        if not self.is_inner_circle_task_force():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        if not self.vowed_objective_ids:
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        if attacker_unit is None:
            return 0, ""
        if not self.attached_unit_is_adeptus_astartes(attacker_unit):
            return 0, ""
        if not self._attached_unit_has_keyword(attacker_unit, "DEATHWING"):
            return 0, ""
        if not self._attached_unit_has_keyword(attacker_unit, "INFANTRY"):
            return 0, ""
        target_root = self._attached_unit_root(target_unit)
        if target_root is None:
            return 0, ""
        within_objective = getattr(target_root, "is_within_objective_range", None)
        if not callable(within_objective):
            return 0, ""
        objective_locations = self.vowed_target_objective_locations()
        for location in list(objective_locations or []):
            if location is None:
                continue
            try:
                if bool(within_objective(location)):
                    return 1, "Vowed Target"
            except (AttributeError, TypeError, ValueError):
                continue
        return 0, ""

    def shock_and_awe_reacting_unit_is_eligible(self, unit, *, game=None) -> bool:
        if not self.is_godhammer_assault_force():
            return False
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        try:
            if root.get_parent_army() is not self.army:
                return False
        except Exception:
            return False
        if not self._unit_is_on_battlefield(root):
            return False
        if not self.attached_unit_is_adeptus_astartes(root):
            return False
        return self._attached_unit_disembarked_from_transport_this_round(root)

    def shock_and_awe_charge_target_is_eligible(self, charging_unit, target_unit, *, game=None) -> bool:
        if not self.shock_and_awe_reacting_unit_is_eligible(charging_unit, game=game):
            return False
        charging_root = self._attached_unit_root(charging_unit)
        target_root = self._attached_unit_root(target_unit)
        if charging_root is None or target_root is None:
            return False
        if not self._unit_is_on_battlefield(target_root):
            return False
        try:
            if target_root.get_parent_army() is self.army:
                return False
        except Exception:
            return False
        return True

    def shock_and_awe_charge_target_units(self, charging_unit, declared_targets=None, *, game=None) -> list:
        if not self.shock_and_awe_reacting_unit_is_eligible(charging_unit, game=game):
            return []
        targets = []
        seen_ids: set[str] = set()
        for target in list(declared_targets or []):
            target_root = self._attached_unit_root(target)
            if target_root is None:
                continue
            target_id = str(get_entity_id(target_root) or "")
            if target_id and target_id in seen_ids:
                continue
            if not self.shock_and_awe_charge_target_is_eligible(charging_unit, target_root, game=game):
                continue
            if target_id:
                seen_ids.add(target_id)
            targets.append(target_root)
        targets.sort(key=lambda u: (str(getattr(u, "name", "") or ""), str(get_entity_id(u) or "")))
        return targets

    def shock_and_awe_melee_hit_bonus(self, attacker_model, weapon_profile=None) -> tuple[int, str]:
        if not self.is_godhammer_assault_force():
            return 0, ""
        if attacker_model is None:
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        if attacker_unit is None:
            return 0, ""
        if not self.shock_and_awe_reacting_unit_is_eligible(attacker_unit):
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            if parent is not None and not bool(getattr(parent, "is_melee", lambda: False)()):
                return 0, ""
        return 1, "Shock and Awe"

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
