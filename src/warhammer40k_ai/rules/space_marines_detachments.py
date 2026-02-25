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
    _HEROES_ALL_BOAST_HIDE_AS_TROPHY = "HIDE_AS_TROPHY"
    _HEROES_ALL_BOAST_SLAY_THEM_ALL = "SLAY_THEM_ALL"
    _HEROES_ALL_BOAST_OVERRUN_THEIR_POSITION = "OVERRUN_THEIR_POSITION"
    _HEROES_ALL_BOAST_HOLD_THE_LINE = "HOLD_THE_LINE"
    _HEROES_ALL_BOAST_KEYS = (
        _HEROES_ALL_BOAST_HIDE_AS_TROPHY,
        _HEROES_ALL_BOAST_SLAY_THEM_ALL,
        _HEROES_ALL_BOAST_OVERRUN_THEIR_POSITION,
        _HEROES_ALL_BOAST_HOLD_THE_LINE,
    )
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
    _ZEALOUS_LITANY_CHORUS_OF_RELENTLESS_HATE = "CHORUS_OF_RELENTLESS_HATE"
    _ZEALOUS_LITANY_RITE_OF_PERFERVID_WRATH = "RITE_OF_PERFERVID_WRATH"
    _ZEALOUS_LITANY_CHANT_OF_DEATHLESS_DEVOTION = "CHANT_OF_DEATHLESS_DEVOTION"
    _ZEALOUS_LITANY_KEYS = (
        _ZEALOUS_LITANY_CHORUS_OF_RELENTLESS_HATE,
        _ZEALOUS_LITANY_RITE_OF_PERFERVID_WRATH,
        _ZEALOUS_LITANY_CHANT_OF_DEATHLESS_DEVOTION,
    )
    _ZEALOUS_LITANY_LABELS = {
        _ZEALOUS_LITANY_CHORUS_OF_RELENTLESS_HATE: "Chorus of Relentless Hate",
        _ZEALOUS_LITANY_RITE_OF_PERFERVID_WRATH: "Rite of Perfervid Wrath",
        _ZEALOUS_LITANY_CHANT_OF_DEATHLESS_DEVOTION: "Chant of Deathless Devotion",
    }
    _MASTER_OF_WOLVES_PACK_ENCIRCLING_JAWS = "ENCIRCLING_JAWS"
    _MASTER_OF_WOLVES_PACK_HUNTERS_EYE = "HUNTERS_EYE"
    _MASTER_OF_WOLVES_PACK_FEROCIOUS_STRIKE = "FEROCIOUS_STRIKE"
    _MASTER_OF_WOLVES_PACK_KEYS = (
        _MASTER_OF_WOLVES_PACK_ENCIRCLING_JAWS,
        _MASTER_OF_WOLVES_PACK_HUNTERS_EYE,
        _MASTER_OF_WOLVES_PACK_FEROCIOUS_STRIKE,
    )
    _MASTER_OF_WOLVES_PACK_LABELS = {
        _MASTER_OF_WOLVES_PACK_ENCIRCLING_JAWS: "Encircling Jaws",
        _MASTER_OF_WOLVES_PACK_HUNTERS_EYE: "Hunter's Eye",
        _MASTER_OF_WOLVES_PACK_FEROCIOUS_STRIKE: "Ferocious Strike",
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
        self.wrathful_procession_active_litany_key: str = ""
        self.wrathful_procession_active_litany_round: int = 0
        self.wrathful_procession_active_litany_player_id: str = ""
        self.wrathful_procession_litany_selection_round: int = 0
        self.wrathful_procession_litany_selection_player_id: str = ""
        self.master_of_wolves_selected_pack_keys: tuple[str, ...] = ()
        self.master_of_wolves_active_pack_key: str = ""
        self.master_of_wolves_active_round: int = 0
        self.master_of_wolves_active_player_id: str = ""
        self.master_of_wolves_last_selection_round: int = 0
        self.master_of_wolves_howling_onslaught_used: bool = False
        self.grim_resolve_selected_unit_id: str = ""
        self.grim_resolve_selected_round: int = 0
        self.grim_resolve_selected_player_id: str = ""
        self.armoured_wrath_used_phase_key_by_unit_id: dict[str, str] = {}
        self.vowed_target_mode: str = ""
        self.vowed_objective_ids: tuple[str, ...] = ()
        self.vowed_target_selected_round: int = 0
        self.vowed_target_selected_player_id: str = ""
        self.rapid_drop_selected_unit_ids: tuple[str, ...] = ()
        self.rapid_drop_selected_player_id: str = ""
        self.upon_wings_of_fire_last_resolved_phase_key: str = ""
        self.reclamation_phase_key: str = ""
        self.reclamation_controlled_objective_ids: tuple[str, ...] = ()
        self.pack_quarry_tally: int = 0
        self.pack_quarry_target: int = 0
        self.pack_quarry_completed: bool = False
        self.pack_quarry_initialized: bool = False
        self.beastslayer_tally: int = 0
        self.beastslayer_target: int = 0
        self.beastslayer_completed: bool = False
        self.beastslayer_initialized: bool = False
        self.heroes_all_achieved_boast_keys: tuple[str, ...] = ()
        self.heroes_all_oath_target_destroyed_count_by_unit_id: dict[str, int] = {}
        self.heroes_all_selection_state_by_key: dict[str, dict[str, object]] = {}

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

    def is_orbital_assault_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Orbital Assault Force")

    def is_reclamation_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Reclamation Force")

    def is_saga_of_the_bold(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Saga of the Bold")

    def is_saga_of_the_beastslayer(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Saga of the Beastslayer")

    def is_saga_of_the_hunter(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Saga of the Hunter")

    def is_saga_of_the_great_wolf(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Saga of the Great Wolf")

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

    def is_the_angelic_host(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("The Angelic Host")

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

    def is_vindication_task_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Vindication Task Force")

    def is_wrathful_procession(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Wrathful Procession")

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

    def _normalize_zealous_litany_key(self, choice_key: str) -> str:
        return str(choice_key or "").strip().upper()

    def clear_wrathful_procession_active_litany(self) -> None:
        self.wrathful_procession_active_litany_key = ""
        self.wrathful_procession_active_litany_round = 0
        self.wrathful_procession_active_litany_player_id = ""

    def get_available_zealous_litanies(self) -> list[str]:
        return list(self._ZEALOUS_LITANY_KEYS)

    def zealous_litany_label(self, key: str) -> str:
        norm = self._normalize_zealous_litany_key(key)
        if norm in self._ZEALOUS_LITANY_LABELS:
            return str(self._ZEALOUS_LITANY_LABELS[norm])
        return str(key or "").strip()

    def can_select_zealous_litany(self, *, game=None) -> bool:
        if not self.is_wrathful_procession():
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
            int(getattr(self, "wrathful_procession_litany_selection_round", 0) or 0) == round_now
            and str(getattr(self, "wrathful_procession_litany_selection_player_id", "") or "") == owner_id
        ):
            return False
        return True

    def zealous_litany_is_active(self, key: str, *, game=None, battle_round=None) -> bool:
        norm = self._normalize_zealous_litany_key(key)
        active_key = str(getattr(self, "wrathful_procession_active_litany_key", "") or "").strip().upper()
        if active_key != norm:
            return False
        try:
            selected_round = int(getattr(self, "wrathful_procession_active_litany_round", 0) or 0)
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

    def select_zealous_litany(self, choice_key: str, *, battle_round=None, player_id: str = "") -> bool:
        if not self.is_wrathful_procession():
            return False
        key = self._normalize_zealous_litany_key(choice_key)
        if key and key not in self._ZEALOUS_LITANY_KEYS:
            return False
        round_now = 0
        if battle_round is not None:
            try:
                round_now = int(battle_round or 0)
            except Exception:
                round_now = 0
        player = str(player_id or "")
        self.wrathful_procession_litany_selection_round = int(round_now or 0)
        self.wrathful_procession_litany_selection_player_id = player
        if not key:
            self.clear_wrathful_procession_active_litany()
            return True
        self.wrathful_procession_active_litany_key = key
        self.wrathful_procession_active_litany_round = int(round_now or 0)
        self.wrathful_procession_active_litany_player_id = player
        return True

    def _wrathful_procession_litany_unit_is_eligible(self, unit) -> bool:
        if not self.is_wrathful_procession():
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
        return bool(
            self._attached_unit_has_keyword(root, "INFANTRY")
            or self._attached_unit_has_keyword(root, "MOUNTED")
        )

    def wrathful_procession_movement_bonus(self, unit, *, game=None) -> tuple[int, str]:
        if not self.zealous_litany_is_active(
            self._ZEALOUS_LITANY_CHORUS_OF_RELENTLESS_HATE,
            game=game,
        ):
            return 0, ""
        if not self._wrathful_procession_litany_unit_is_eligible(unit):
            return 0, ""
        return 2, "Zealous Litanies (Chorus of Relentless Hate)"

    def wrathful_procession_advance_roll_bonus(self, unit, *, game=None) -> tuple[int, str]:
        if not self.zealous_litany_is_active(
            self._ZEALOUS_LITANY_CHORUS_OF_RELENTLESS_HATE,
            game=game,
        ):
            return 0, ""
        if not self._wrathful_procession_litany_unit_is_eligible(unit):
            return 0, ""
        return 1, "Zealous Litanies (Chorus of Relentless Hate)"

    def wrathful_procession_melee_strength_bonus(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        if not self.zealous_litany_is_active(
            self._ZEALOUS_LITANY_RITE_OF_PERFERVID_WRATH,
            game=game,
        ):
            return 0, ""
        if attacker_model is None:
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            if parent is not None and not bool(getattr(parent, "is_melee", lambda: False)()):
                return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        if not self._wrathful_procession_litany_unit_is_eligible(attacker_unit):
            return 0, ""
        return 1, "Zealous Litanies (Rite of Perfervid Wrath)"

    def wrathful_procession_ranged_invulnerable_save(self, unit, *, attack_type: str = "", game=None) -> tuple[int, str]:
        if not self.zealous_litany_is_active(
            self._ZEALOUS_LITANY_CHANT_OF_DEATHLESS_DEVOTION,
            game=game,
        ):
            return 0, ""
        if str(attack_type or "").strip().lower() != "ranged":
            return 0, ""
        if not self._wrathful_procession_litany_unit_is_eligible(unit):
            return 0, ""
        return 5, "Zealous Litanies (Chant of Deathless Devotion)"

    def clear_legendary_slayers_state(self) -> None:
        self.beastslayer_tally = 0
        self.beastslayer_target = 0
        self.beastslayer_completed = False
        self.beastslayer_initialized = False

    def _legendary_slayers_target_has_required_keyword(self, unit) -> bool:
        if unit is None:
            return False
        return any(
            self._attached_unit_has_keyword(unit, keyword)
            for keyword in ("CHARACTER", "MONSTER", "VEHICLE")
        )

    def _legendary_slayers_attacker_is_eligible(self, attacker_unit) -> bool:
        attacker_root = self._attached_unit_root(attacker_unit)
        if attacker_root is None:
            return False
        try:
            if attacker_root.get_parent_army() is not self.army:
                return False
        except Exception:
            return False
        return self.attached_unit_is_adeptus_astartes(attacker_root)

    def _legendary_slayers_enemy_keyword_units(self, *, game=None) -> list:
        if self.army is None:
            return []
        game_obj = self._resolve_game_context(game=game)
        owner_player = getattr(self.army, "player", None)
        owners = []
        if game_obj is not None:
            owners = list(getattr(game_obj, "players", []) or [])
        elif owner_player is not None:
            owners = [owner_player]

        out = []
        seen_ids: set[str] = set()
        for player in owners:
            if player is owner_player:
                continue
            get_army = getattr(player, "get_army", None)
            enemy_army = get_army() if callable(get_army) else getattr(player, "army", None)
            if enemy_army is None:
                continue
            for unit in list(getattr(enemy_army, "units", []) or []):
                root = self._attached_unit_root(unit)
                if root is None:
                    continue
                unit_id = str(get_entity_id(root) or "")
                if not unit_id or unit_id in seen_ids:
                    continue
                if not self._unit_has_models_or_is_alive(root):
                    continue
                if not self._legendary_slayers_target_has_required_keyword(root):
                    continue
                seen_ids.add(unit_id)
                out.append(root)
        out.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return out

    def _legendary_slayers_update_completion(self) -> None:
        if not self.is_saga_of_the_beastslayer():
            self.beastslayer_completed = False
            return
        if not bool(self.beastslayer_initialized):
            self.beastslayer_completed = False
            return
        target = max(0, int(self.beastslayer_target or 0))
        tally = max(0, int(self.beastslayer_tally or 0))
        self.beastslayer_completed = bool(tally >= target)

    def _on_battle_round_start_legendary_slayers(self, battle_round: int, *, game=None) -> None:
        if not self.is_saga_of_the_beastslayer():
            self.clear_legendary_slayers_state()
            return
        try:
            round_now = int(battle_round or 0)
        except Exception:
            round_now = 0
        if round_now != 1:
            return
        self.beastslayer_tally = 0
        self.beastslayer_initialized = True
        enemy_units = self._legendary_slayers_enemy_keyword_units(game=game)
        self.beastslayer_target = (len(enemy_units) + 1) // 2
        self._legendary_slayers_update_completion()

    def legendary_slayers_saga_completed(self) -> bool:
        self._legendary_slayers_update_completion()
        return bool(self.beastslayer_completed)

    def _legendary_slayers_add_tally(self, value: int) -> int:
        if not self.is_saga_of_the_beastslayer():
            return 0
        try:
            amount = int(value or 0)
        except Exception:
            amount = 0
        if amount <= 0:
            return 0
        self.beastslayer_tally = int(self.beastslayer_tally or 0) + amount
        self._legendary_slayers_update_completion()
        return amount

    def _legendary_slayers_destroyed_keyword_targets_from_hits(self, attacker_unit, hits_by_target) -> list:
        if not self.is_saga_of_the_beastslayer():
            return []
        if not self._legendary_slayers_attacker_is_eligible(attacker_unit):
            return []
        if not isinstance(hits_by_target, dict):
            return []
        out = []
        seen_ids: set[str] = set()
        for target_unit, hits in list((hits_by_target or {}).items()):
            if target_unit is None:
                continue
            if int(hits or 0) <= 0:
                continue
            target_root = self._attached_unit_root(target_unit)
            if target_root is None:
                continue
            try:
                if target_root.get_parent_army() is self.army:
                    continue
            except Exception:
                continue
            if not self._legendary_slayers_target_has_required_keyword(target_root):
                continue
            if self._unit_has_models_or_is_alive(target_root):
                continue
            target_id = str(get_entity_id(target_root) or "")
            if not target_id or target_id in seen_ids:
                continue
            seen_ids.add(target_id)
            out.append(target_root)
        out.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return out

    def legendary_slayers_register_shooting_resolved(self, attacker_unit=None, hits_by_target=None, *, game=None) -> int:
        _ = game
        destroyed = self._legendary_slayers_destroyed_keyword_targets_from_hits(attacker_unit, hits_by_target)
        if not destroyed:
            return 0
        return self._legendary_slayers_add_tally(len(destroyed))

    def legendary_slayers_mark_fight_hit_targets(self, attacker_unit=None, hits_by_target=None, *, game=None) -> None:
        if not self.is_saga_of_the_beastslayer():
            return
        if not self._legendary_slayers_attacker_is_eligible(attacker_unit):
            return
        if not isinstance(hits_by_target, dict):
            return
        attacker_root = self._attached_unit_root(attacker_unit)
        if attacker_root is None:
            return
        pending_ids = []
        for target_unit, hits in list((hits_by_target or {}).items()):
            if target_unit is None:
                continue
            if int(hits or 0) <= 0:
                continue
            target_root = self._attached_unit_root(target_unit)
            if target_root is None:
                continue
            try:
                if target_root.get_parent_army() is self.army:
                    continue
            except Exception:
                continue
            if not self._legendary_slayers_target_has_required_keyword(target_root):
                continue
            target_id = str(get_entity_id(target_root) or "")
            if target_id:
                pending_ids.append(target_id)
        pending_ids = sorted(set(pending_ids))
        if not pending_ids:
            return

        game_obj = self._resolve_game_context(game=game)
        current_player = getattr(game_obj, "get_current_player", lambda: None)() if game_obj is not None else None
        owner_id = str(getattr(current_player, "id", "") or "")
        if not owner_id:
            owner_id = str(getattr(getattr(self.army, "player", None), "id", "") or "")
        try:
            turn_now = int(getattr(game_obj, "turn", 0) or 0) if game_obj is not None else 0
        except Exception:
            turn_now = 0

        sr = getattr(attacker_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        try:
            pending_turn = int(sr.get("legendary_slayers_pending_turn", 0) or 0)
        except Exception:
            pending_turn = 0
        pending_owner = str(sr.get("legendary_slayers_pending_owner", "") or "")
        if pending_turn != turn_now or pending_owner != owner_id:
            merged = set(pending_ids)
        else:
            merged = {
                str(value or "")
                for value in list(sr.get("legendary_slayers_pending_target_ids", []) or [])
                if str(value or "")
            }
            merged.update(pending_ids)
        sr["legendary_slayers_pending_turn"] = int(turn_now or 0)
        sr["legendary_slayers_pending_owner"] = owner_id
        sr["legendary_slayers_pending_target_ids"] = sorted(merged)
        attacker_root.special_rules = sr

    def _legendary_slayers_resolve_unit_by_id(self, unit_id: str, *, game=None):
        target = None
        game_obj = self._resolve_game_context(game=game)
        registry = getattr(game_obj, "entity_registry", None) if game_obj is not None else None
        if registry is not None and callable(getattr(registry, "get", None)):
            target = registry.get(unit_id, kind="unit")
        if target is not None:
            return target
        owner_player = getattr(self.army, "player", None)
        players = list(getattr(game_obj, "players", []) or []) if game_obj is not None else []
        for player in players:
            if player is owner_player:
                continue
            get_army = getattr(player, "get_army", None)
            enemy_army = get_army() if callable(get_army) else getattr(player, "army", None)
            if enemy_army is None:
                continue
            for unit in list(getattr(enemy_army, "units", []) or []):
                root = self._attached_unit_root(unit)
                if root is None:
                    continue
                if str(get_entity_id(root) or "") == str(unit_id or ""):
                    return root
        return None

    def legendary_slayers_resolve_fight_sequence(self, attacker_unit=None, *, game=None) -> int:
        if not self.is_saga_of_the_beastslayer():
            return 0
        if not self._legendary_slayers_attacker_is_eligible(attacker_unit):
            return 0
        attacker_root = self._attached_unit_root(attacker_unit)
        if attacker_root is None:
            return 0
        sr = getattr(attacker_root, "special_rules", None)
        if not isinstance(sr, dict):
            return 0
        pending_ids = [
            str(value or "")
            for value in list(sr.get("legendary_slayers_pending_target_ids", []) or [])
            if str(value or "")
        ]
        for key in (
            "legendary_slayers_pending_turn",
            "legendary_slayers_pending_owner",
            "legendary_slayers_pending_target_ids",
        ):
            sr.pop(key, None)
        attacker_root.special_rules = sr
        if not pending_ids:
            return 0

        destroyed_ids: set[str] = set()
        for target_id in pending_ids:
            target = self._legendary_slayers_resolve_unit_by_id(target_id, game=game)
            target_root = self._attached_unit_root(target)
            if target_root is None:
                continue
            try:
                if target_root.get_parent_army() is self.army:
                    continue
            except Exception:
                continue
            if not self._legendary_slayers_target_has_required_keyword(target_root):
                continue
            if self._unit_has_models_or_is_alive(target_root):
                continue
            resolved_id = str(get_entity_id(target_root) or "")
            if resolved_id:
                destroyed_ids.add(resolved_id)
        return self._legendary_slayers_add_tally(len(destroyed_ids))

    def legendary_slayers_lethal_hits(self, attacker_model, *, target_unit=None) -> tuple[bool, str]:
        if not self.is_saga_of_the_beastslayer():
            return False, ""
        if attacker_model is None:
            return False, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        if not self._legendary_slayers_attacker_is_eligible(attacker_unit):
            return False, ""
        if self.legendary_slayers_saga_completed():
            return True, "Legendary Slayers"
        if target_unit is None:
            return False, ""
        target_root = self._attached_unit_root(target_unit)
        if target_root is None:
            return False, ""
        try:
            if target_root.get_parent_army() is self.army:
                return False, ""
        except Exception:
            return False, ""
        if not self._legendary_slayers_target_has_required_keyword(target_root):
            return False, ""
        return True, "Legendary Slayers"

    def clear_pack_quarry_state(self) -> None:
        self.pack_quarry_tally = 0
        self.pack_quarry_target = 0
        self.pack_quarry_completed = False
        self.pack_quarry_initialized = False

    def _pack_quarry_target_for_battle_size(self, *, game=None) -> int:
        game_obj = self._resolve_game_context(game=game)
        size_name = ""
        if game_obj is not None:
            try:
                battlefield = getattr(game_obj, "battlefield", None)
                size = getattr(battlefield, "size", None) if battlefield is not None else None
                if size is not None:
                    size_name = str(getattr(size, "name", "") or getattr(size, "value", "") or "").strip().upper()
            except Exception:
                size_name = ""
        if "ONSLAUGHT" in size_name:
            return 4
        if "STRIKE" in size_name and "FORCE" in size_name:
            return 3
        if "INCURSION" in size_name:
            return 2
        points_limit = int(getattr(self.army, "points_limit", 0) or 0) if self.army is not None else 0
        if points_limit >= 3000:
            return 4
        if points_limit >= 2000:
            return 3
        return 2

    def _pack_quarry_update_completion(self) -> None:
        if not self.is_saga_of_the_hunter():
            self.pack_quarry_completed = False
            return
        if not bool(self.pack_quarry_initialized):
            self.pack_quarry_completed = False
            return
        target = max(0, int(self.pack_quarry_target or 0))
        tally = max(0, int(self.pack_quarry_tally or 0))
        self.pack_quarry_completed = bool(tally >= target)

    def _on_battle_round_start_pack_quarry(self, battle_round: int, *, game=None) -> None:
        if not self.is_saga_of_the_hunter():
            self.clear_pack_quarry_state()
            return
        try:
            round_now = int(battle_round or 0)
        except Exception:
            round_now = 0
        if round_now != 1:
            return
        self.pack_quarry_tally = 0
        self.pack_quarry_initialized = True
        self.pack_quarry_target = self._pack_quarry_target_for_battle_size(game=game)
        self._pack_quarry_update_completion()

    def pack_quarry_saga_completed(self) -> bool:
        self._pack_quarry_update_completion()
        return bool(self.pack_quarry_completed)

    def _pack_quarry_add_tally(self, value: int) -> int:
        if not self.is_saga_of_the_hunter():
            return 0
        try:
            amount = int(value or 0)
        except Exception:
            amount = 0
        if amount <= 0:
            return 0
        self.pack_quarry_tally = int(self.pack_quarry_tally or 0) + amount
        self._pack_quarry_update_completion()
        return amount

    def _pack_quarry_tally_attacker_is_eligible(self, attacker_unit) -> bool:
        attacker_root = self._attached_unit_root(attacker_unit)
        if attacker_root is None:
            return False
        try:
            if attacker_root.get_parent_army() is not self.army:
                return False
        except Exception:
            return False
        return self.attached_unit_is_adeptus_astartes(attacker_root)

    def _pack_quarry_unit_is_space_wolves(self, unit) -> bool:
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
        if self._attached_unit_has_keyword(root, "SPACE WOLVES"):
            return True
        return str(self.get_committed_chapter_keyword() or "").strip().upper() == "SPACE WOLVES"

    def _pack_quarry_alive_model_count(self, unit) -> int:
        root = self._attached_unit_root(unit)
        if root is None:
            return 0
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = []
        if not models:
            models = list(getattr(root, "models", []) or [])
        if not models:
            return 0
        count = 0
        for model in models:
            try:
                alive_attr = getattr(model, "is_alive", False)
                alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            except Exception:
                alive = False
            if alive:
                count += 1
        return int(count)

    def _pack_quarry_target_is_engaged_with_other_friendly_astartes(
        self,
        *,
        attacker_unit,
        target_unit,
        game=None,
    ) -> bool:
        attacker_root = self._attached_unit_root(attacker_unit)
        target_root = self._attached_unit_root(target_unit)
        if attacker_root is None or target_root is None:
            return False
        game_obj = self._resolve_game_context(game=game)
        game_map = getattr(game_obj, "map", None) if game_obj is not None else None
        if game_map is None:
            return False
        attacker_id = str(get_entity_id(attacker_root) or "")
        for friendly in self._iter_unique_army_roots():
            if friendly is None:
                continue
            if not self._unit_is_on_battlefield(friendly):
                continue
            if not self.attached_unit_is_adeptus_astartes(friendly):
                continue
            friendly_id = str(get_entity_id(friendly) or "")
            if attacker_id and friendly_id and attacker_id == friendly_id:
                continue
            try:
                if bool(game_map.is_within_engagement_range(friendly, target_root)):
                    return True
            except Exception:
                continue
        return False

    def _pack_quarry_attacker_outnumbers_target(self, *, attacker_unit, target_unit) -> bool:
        attacker_count = int(self._pack_quarry_alive_model_count(attacker_unit) or 0)
        target_count = int(self._pack_quarry_alive_model_count(target_unit) or 0)
        if attacker_count <= 0 or target_count <= 0:
            return False
        return attacker_count > target_count

    def _pack_quarry_melee_condition_met(self, *, attacker_unit, target_unit, game=None) -> bool:
        attacker_root = self._attached_unit_root(attacker_unit)
        target_root = self._attached_unit_root(target_unit)
        if attacker_root is None or target_root is None:
            return False
        try:
            if attacker_root.get_parent_army() is not self.army:
                return False
        except Exception:
            return False
        try:
            if target_root.get_parent_army() is self.army:
                return False
        except Exception:
            return False
        return bool(
            self._pack_quarry_target_is_engaged_with_other_friendly_astartes(
                attacker_unit=attacker_root,
                target_unit=target_root,
                game=game,
            )
            or self._pack_quarry_attacker_outnumbers_target(
                attacker_unit=attacker_root,
                target_unit=target_root,
            )
        )

    def pack_quarry_hit_bonus(
        self,
        attacker_model,
        target_unit=None,
        *,
        weapon_profile=None,
        attack_instance=None,
    ) -> tuple[int, str]:
        _ = attack_instance
        if not self.is_saga_of_the_hunter():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        if not self._pack_quarry_unit_is_space_wolves(attacker_unit):
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            if parent is not None and not bool(getattr(parent, "is_melee", lambda: False)()):
                return 0, ""
        game_obj = self._resolve_game_context(game=None)
        if not self._pack_quarry_melee_condition_met(
            attacker_unit=attacker_unit,
            target_unit=target_unit,
            game=game_obj,
        ):
            return 0, ""
        return 1, "Pack's Quarry"

    def pack_quarry_wound_bonus(
        self,
        attacker_model,
        target_unit=None,
        *,
        weapon_profile=None,
        attack_instance=None,
    ) -> tuple[int, str]:
        _ = attack_instance
        if not self.pack_quarry_saga_completed():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        if not self._pack_quarry_unit_is_space_wolves(attacker_unit):
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            if parent is not None and not bool(getattr(parent, "is_melee", lambda: False)()):
                return 0, ""
        game_obj = self._resolve_game_context(game=None)
        if not self._pack_quarry_melee_condition_met(
            attacker_unit=attacker_unit,
            target_unit=target_unit,
            game=game_obj,
        ):
            return 0, ""
        return 1, "Pack's Quarry"

    def pack_quarry_mark_fight_hit_targets(self, attacker_unit=None, hits_by_target=None, *, game=None) -> None:
        if not self.is_saga_of_the_hunter():
            return
        if not self._pack_quarry_tally_attacker_is_eligible(attacker_unit):
            return
        if not isinstance(hits_by_target, dict):
            return
        attacker_root = self._attached_unit_root(attacker_unit)
        if attacker_root is None:
            return
        pending_ids = []
        for target_unit, hits in list((hits_by_target or {}).items()):
            if target_unit is None:
                continue
            if int(hits or 0) <= 0:
                continue
            target_root = self._attached_unit_root(target_unit)
            if target_root is None:
                continue
            try:
                if target_root.get_parent_army() is self.army:
                    continue
            except Exception:
                continue
            target_id = str(get_entity_id(target_root) or "")
            if target_id:
                pending_ids.append(target_id)
        pending_ids = sorted(set(pending_ids))
        if not pending_ids:
            return

        game_obj = self._resolve_game_context(game=game)
        current_player = getattr(game_obj, "get_current_player", lambda: None)() if game_obj is not None else None
        owner_id = str(getattr(current_player, "id", "") or "")
        if not owner_id:
            owner_id = str(getattr(getattr(self.army, "player", None), "id", "") or "")
        try:
            turn_now = int(getattr(game_obj, "turn", 0) or 0) if game_obj is not None else 0
        except Exception:
            turn_now = 0

        sr = getattr(attacker_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        try:
            pending_turn = int(sr.get("pack_quarry_pending_turn", 0) or 0)
        except Exception:
            pending_turn = 0
        pending_owner = str(sr.get("pack_quarry_pending_owner", "") or "")
        if pending_turn != turn_now or pending_owner != owner_id:
            merged = set(pending_ids)
        else:
            merged = {
                str(value or "")
                for value in list(sr.get("pack_quarry_pending_target_ids", []) or [])
                if str(value or "")
            }
            merged.update(pending_ids)
        sr["pack_quarry_pending_turn"] = int(turn_now or 0)
        sr["pack_quarry_pending_owner"] = owner_id
        sr["pack_quarry_pending_target_ids"] = sorted(merged)
        attacker_root.special_rules = sr

    def pack_quarry_resolve_fight_sequence(self, attacker_unit=None, *, game=None) -> int:
        if not self.is_saga_of_the_hunter():
            return 0
        if not self._pack_quarry_tally_attacker_is_eligible(attacker_unit):
            return 0
        attacker_root = self._attached_unit_root(attacker_unit)
        if attacker_root is None:
            return 0
        sr = getattr(attacker_root, "special_rules", None)
        if not isinstance(sr, dict):
            return 0
        pending_ids = [
            str(value or "")
            for value in list(sr.get("pack_quarry_pending_target_ids", []) or [])
            if str(value or "")
        ]
        for key in (
            "pack_quarry_pending_turn",
            "pack_quarry_pending_owner",
            "pack_quarry_pending_target_ids",
        ):
            sr.pop(key, None)
        attacker_root.special_rules = sr
        if not pending_ids:
            return 0

        destroyed_ids: set[str] = set()
        for target_id in pending_ids:
            target = self._legendary_slayers_resolve_unit_by_id(target_id, game=game)
            target_root = self._attached_unit_root(target)
            if target_root is None:
                continue
            try:
                if target_root.get_parent_army() is self.army:
                    continue
            except Exception:
                continue
            if self._unit_has_models_or_is_alive(target_root):
                continue
            resolved_id = str(get_entity_id(target_root) or "")
            if resolved_id:
                destroyed_ids.add(resolved_id)
        return self._pack_quarry_add_tally(len(destroyed_ids))

    def _on_battle_round_start_librarius(self, battle_round: int, *, game=None) -> None:
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

    def _on_battle_round_start_wrathful_procession_litanies(self, battle_round: int, *, game=None) -> None:
        if not self.is_wrathful_procession():
            self.clear_wrathful_procession_active_litany()
            self.wrathful_procession_litany_selection_round = 0
            self.wrathful_procession_litany_selection_player_id = ""
            return
        self.clear_wrathful_procession_active_litany()
        game_obj = self._resolve_game_context(game=game)
        if game_obj is None or not bool(getattr(game_obj, "is_authoritative", True)):
            return
        try:
            round_now = int(battle_round or getattr(game_obj, "turn", 0) or 0)
        except Exception:
            round_now = int(getattr(game_obj, "turn", 0) or 0)
        if round_now <= 0:
            return
        if not self.can_select_zealous_litany(game=game_obj):
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
                if str(context.get("ability", "") or "") != "zealous_litanies":
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
            self._ZEALOUS_LITANY_CHORUS_OF_RELENTLESS_HATE: 'Add 2" Move and +1 to Advance rolls.',
            self._ZEALOUS_LITANY_RITE_OF_PERFERVID_WRATH: "Add 1 to melee weapon Strength.",
            self._ZEALOUS_LITANY_CHANT_OF_DEATHLESS_DEVOTION: "Models gain a 5+ invulnerable save against ranged attacks.",
        }
        options = [
            DecisionOption.create(
                "None",
                payload={
                    "skip": True,
                    "choice_key": "",
                    "choice_name": "None",
                    "summary": "No litany active this battle round.",
                    "army_id": army_id,
                },
            )
        ]
        for key in self.get_available_zealous_litanies():
            label = self.zealous_litany_label(key)
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
            "Zealous Litanies: select one litany for this battle round (or None).",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "zealous_litanies",
                "ability_name": "Zealous Litanies",
                "optional": True,
                "army_id": army_id,
                "player_id": player_id,
                "battle_round": int(round_now),
                "allowed_choice_keys": list(self._ZEALOUS_LITANY_KEYS),
            },
        )
        if hasattr(game_obj, "request_decision"):
            game_obj.request_decision(request)

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        self._on_battle_round_start_pack_quarry(battle_round, game=game)
        self._on_battle_round_start_legendary_slayers(battle_round, game=game)
        self._on_battle_round_start_librarius(battle_round, game=game)
        self._on_battle_round_start_wrathful_procession_litanies(battle_round, game=game)

    def on_phase_end(self, phase, active_player=None, *, game=None) -> None:
        self.heroes_all_handle_phase_end(phase=phase, active_player=active_player, game=game)

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

    def _attached_unit_disembarked_from_transport_name_this_round(
        self,
        unit,
        *,
        transport_name_fragment: str,
        game=None,
    ) -> bool:
        if not self._attached_unit_disembarked_from_transport_this_round(unit):
            return False
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        round_state = getattr(root, "round_state", None)
        if round_state is None:
            return False
        transport_id = str(getattr(round_state, "disembarked_from_transport_id", "") or "").strip()
        if not transport_id:
            return False
        transport = None
        game_obj = self._resolve_game_context(game=game)
        registry = getattr(game_obj, "entity_registry", None) if game_obj is not None else None
        if registry is not None:
            try:
                transport = registry.get(transport_id, kind="unit")
            except Exception:
                transport = None
        if transport is None:
            for unit_entry in list(getattr(self.army, "units", []) or []):
                unit_id = str(get_entity_id(unit_entry) or "")
                if unit_id != transport_id:
                    continue
                transport = unit_entry
                break
        if transport is None:
            return False
        return self._attached_unit_name_contains(transport, transport_name_fragment)

    def _attached_unit_was_set_up_this_turn(self, unit, *, game=None) -> bool:
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        was_set_up = getattr(root, "_was_set_up_this_turn", None)
        game_obj = self._resolve_game_context(game=game)
        if callable(was_set_up):
            try:
                return bool(was_set_up(game=game_obj))
            except Exception:
                return False
        try:
            if bool(getattr(root, "arrived_from_reserves_this_turn", False)):
                return True
        except Exception:
            pass
        try:
            round_state = getattr(root, "round_state", None)
            if bool(getattr(round_state, "reinforced_this_round", False)):
                return True
        except Exception:
            pass
        if game_obj is None:
            return False
        try:
            turn_now = int(getattr(game_obj, "turn", 0) or 0)
            return bool(turn_now > 0 and int(getattr(root, "reserve_turn_deployed", 0) or 0) == turn_now)
        except Exception:
            return False

    def rapid_drop_deployment_max_units(self, *, game=None) -> int:
        if not self.is_orbital_assault_force():
            return 0
        game_obj = self._resolve_game_context(game=game)
        size_name = ""
        if game_obj is not None:
            try:
                battlefield = getattr(game_obj, "battlefield", None)
                size = getattr(battlefield, "size", None) if battlefield is not None else None
                if size is not None:
                    size_name = str(getattr(size, "name", "") or getattr(size, "value", "") or "").strip().upper()
            except Exception:
                size_name = ""
        if "ONSLAUGHT" in size_name:
            return 4
        if "STRIKE" in size_name and "FORCE" in size_name:
            return 3
        return 2

    def rapid_drop_deployment_unit_is_eligible(self, unit, *, game=None) -> bool:
        if not self.is_orbital_assault_force():
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
        is_titanic = getattr(root, "is_titanic", None)
        if callable(is_titanic):
            try:
                if bool(is_titanic()):
                    return False
            except Exception:
                return False
        elif bool(getattr(root, "is_titanic", False)):
            return False
        return True

    def rapid_drop_deployment_eligible_units(self, *, game=None) -> list:
        if not self.is_orbital_assault_force():
            return []
        units = []
        for root in self._iter_unique_army_roots():
            if self.rapid_drop_deployment_unit_is_eligible(root, game=game):
                units.append(root)
        units.sort(key=lambda unit: (str(getattr(unit, "name", "") or ""), str(get_entity_id(unit) or "")))
        return units

    def can_select_rapid_drop_deployment(self, *, game=None) -> bool:
        if not self.is_orbital_assault_force():
            return False
        if bool(getattr(self, "rapid_drop_selected_unit_ids", ())):
            return False
        return bool(self.rapid_drop_deployment_eligible_units(game=game))

    def rapid_drop_deployment_option_is_valid(self, selected_unit_ids, *, game=None) -> bool:
        if not self.can_select_rapid_drop_deployment(game=game):
            return False
        selected = [str(unit_id or "").strip() for unit_id in list(selected_unit_ids or []) if str(unit_id or "").strip()]
        selected = list(dict.fromkeys(selected))
        candidates = self.rapid_drop_deployment_eligible_units(game=game)
        candidate_ids = [str(get_entity_id(unit) or "") for unit in list(candidates or []) if str(get_entity_id(unit) or "")]
        candidate_set = set(candidate_ids)
        if not candidate_set:
            return False
        for unit_id in selected:
            if unit_id not in candidate_set:
                return False
        max_units = int(self.rapid_drop_deployment_max_units(game=game) or 0)
        if max_units <= 0:
            return False
        required = min(max_units, len(candidate_ids))
        return len(selected) == required

    def select_rapid_drop_deployment_units(self, selected_unit_ids, *, game=None) -> bool:
        if not self.rapid_drop_deployment_option_is_valid(selected_unit_ids, game=game):
            return False
        selected = [str(unit_id or "").strip() for unit_id in list(selected_unit_ids or []) if str(unit_id or "").strip()]
        selected = sorted(set(selected))
        game_obj = self._resolve_game_context(game=game)
        registry = getattr(game_obj, "entity_registry", None) if game_obj is not None else None
        for unit_id in list(selected):
            unit = None
            if registry is not None:
                try:
                    unit = registry.get(unit_id, kind="unit")
                except Exception:
                    unit = None
            if unit is None:
                for army_unit in list(getattr(self.army, "units", []) or []):
                    if str(get_entity_id(army_unit) or "") != unit_id:
                        continue
                    unit = army_unit
                    break
            root = self._attached_unit_root(unit)
            if root is None:
                continue
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["bearer_unit_deep_strike"] = True
            root.special_rules = sr
            try:
                cache = getattr(root, "_ability_cache", None)
                if isinstance(cache, dict):
                    cache.pop("deep_strike", None)
            except Exception:
                pass
        self.rapid_drop_selected_unit_ids = tuple(selected)
        self.rapid_drop_selected_player_id = str(
            getattr(getattr(self.army, "player", None), "id", "") or ""
        )
        return True

    def rapid_drop_deployment_reroll_wound_ones(self, attacker_model, *, game=None) -> tuple[bool, str]:
        if not self.is_orbital_assault_force():
            return False, ""
        if attacker_model is None:
            return False, ""
        unit = getattr(attacker_model, "parent_unit", None)
        if unit is None:
            return False, ""
        if not self.attached_unit_is_adeptus_astartes(unit):
            return False, ""
        if not self._attached_unit_was_set_up_this_turn(unit, game=game):
            return False, ""
        return True, "Rapid-drop Deployment"

    def rapid_drop_deployment_reroll_hit_ones(self, attacker_model, *, game=None) -> tuple[bool, str]:
        if not self.is_orbital_assault_force():
            return False, ""
        if attacker_model is None:
            return False, ""
        unit = getattr(attacker_model, "parent_unit", None)
        if unit is None:
            return False, ""
        if not self.attached_unit_is_adeptus_astartes(unit):
            return False, ""
        if not self._attached_unit_disembarked_from_transport_name_this_round(
            unit,
            transport_name_fragment="Drop Pod",
            game=game,
        ):
            return False, ""
        return True, "Rapid-drop Deployment"

    def upon_wings_of_fire_end_of_opponent_turn_max_units(self, *, game=None) -> int:
        if not self.is_the_angelic_host():
            return 0
        game_obj = self._resolve_game_context(game=game)
        size_name = ""
        if game_obj is not None:
            try:
                battlefield = getattr(game_obj, "battlefield", None)
                size = getattr(battlefield, "size", None) if battlefield is not None else None
                if size is not None:
                    size_name = str(getattr(size, "name", "") or getattr(size, "value", "") or "").strip().upper()
            except Exception:
                size_name = ""
        if "ONSLAUGHT" in size_name:
            return 3
        if "STRIKE" in size_name and "FORCE" in size_name:
            return 2
        if "INCURSION" in size_name:
            return 1
        points_limit = int(getattr(self.army, "points_limit", 0) or 0) if self.army is not None else 0
        if points_limit >= 3000:
            return 3
        if points_limit >= 2000:
            return 2
        return 1

    def _upon_wings_of_fire_phase_key(self, *, game=None, turn_ending_player_id: str = "") -> str:
        game_obj = self._resolve_game_context(game=game)
        try:
            turn_now = int(getattr(game_obj, "turn", 0) or 0) if game_obj is not None else 0
        except Exception:
            turn_now = 0
        return f"{turn_now}:{str(turn_ending_player_id or '').strip()}"

    def upon_wings_of_fire_phase_already_resolved(self, *, game=None, turn_ending_player_id: str = "") -> bool:
        if not self.is_the_angelic_host():
            return False
        key = self._upon_wings_of_fire_phase_key(game=game, turn_ending_player_id=turn_ending_player_id)
        return bool(key) and key == str(self.upon_wings_of_fire_last_resolved_phase_key or "")

    def mark_upon_wings_of_fire_phase_resolved(self, *, game=None, turn_ending_player_id: str = "") -> None:
        if not self.is_the_angelic_host():
            self.upon_wings_of_fire_last_resolved_phase_key = ""
            return
        self.upon_wings_of_fire_last_resolved_phase_key = self._upon_wings_of_fire_phase_key(
            game=game,
            turn_ending_player_id=turn_ending_player_id,
        )

    def _upon_wings_of_fire_unit_is_jump_pack(self, unit) -> bool:
        return bool(self._attached_unit_has_keyword(unit, "JUMP PACK"))

    def upon_wings_of_fire_end_of_opponent_turn_candidates(
        self,
        *,
        game=None,
        turn_ending_player=None,
        game_map=None,
    ) -> list:
        if not self.is_the_angelic_host() or self.army is None:
            return []
        game_obj = self._resolve_game_context(game=game)
        if game_map is None and game_obj is not None:
            game_map = getattr(game_obj, "map", None)
        player = getattr(self.army, "player", None)
        if player is None:
            return []
        if turn_ending_player is not None and turn_ending_player is player:
            return []

        candidates: list = []
        for root in self._iter_unique_army_roots():
            if root is None:
                continue
            if not self.attached_unit_is_adeptus_astartes(root):
                continue
            if not self._upon_wings_of_fire_unit_is_jump_pack(root):
                continue
            if not self._unit_is_on_battlefield(root):
                continue
            if bool(getattr(root, "embarked_in", None)) or bool(getattr(root, "is_embarked", False)):
                continue
            if game_map is not None:
                engaged = False
                for enemy in list(getattr(game_map, "get_enemy_units", lambda _u: [])(root) or []):
                    if enemy is None:
                        continue
                    enemy_root = self._attached_unit_root(enemy)
                    if enemy_root is None:
                        continue
                    if not self._unit_is_on_battlefield(enemy_root):
                        continue
                    try:
                        if bool(game_map.is_within_engagement_range(root, enemy_root)):
                            engaged = True
                            break
                    except Exception:
                        continue
                if engaged:
                    continue
            candidates.append(root)
        candidates.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return candidates

    def on_phase_start_capture_reclamation_objective_control(self, *, phase=None, game=None) -> None:
        if not self.is_reclamation_force():
            self.reclamation_phase_key = ""
            self.reclamation_controlled_objective_ids = ()
            return
        game_obj = self._resolve_game_context(game=game)
        phase_key = self._armoured_wrath_phase_key(game=game_obj)
        if not phase_key:
            self.reclamation_phase_key = ""
            self.reclamation_controlled_objective_ids = ()
            return
        game_map = getattr(game_obj, "map", None) if game_obj is not None else None
        objectives = list(getattr(game_map, "objectives", []) or []) if game_map is not None else []
        player = getattr(self.army, "player", None) if self.army is not None else None
        controlled_ids: list[str] = []
        for objective in objectives:
            location = getattr(objective, "location", None) or objective
            controller = getattr(location, "controlling_player", None)
            if controller is None:
                controller = getattr(objective, "controlling_player", None)
            if controller is not player:
                continue
            objective_id = str(
                getattr(objective, "id", None)
                or get_entity_id(objective)
                or getattr(location, "id", None)
                or get_entity_id(location)
                or ""
            ).strip()
            if not objective_id:
                continue
            controlled_ids.append(objective_id)
        self.reclamation_phase_key = phase_key
        self.reclamation_controlled_objective_ids = tuple(sorted(set(controlled_ids)))

    def _reclamation_objective_ids_at_phase_start(self, *, game=None) -> set[str]:
        if not self.is_reclamation_force():
            return set()
        phase_key = self._armoured_wrath_phase_key(game=game)
        stored_key = str(getattr(self, "reclamation_phase_key", "") or "")
        if not phase_key or phase_key != stored_key:
            return set()
        return {
            str(objective_id or "").strip()
            for objective_id in list(getattr(self, "reclamation_controlled_objective_ids", ()) or ())
            if str(objective_id or "").strip()
        }

    def _unit_within_objective_ids(self, unit, objective_ids: set[str], *, game=None) -> bool:
        if not objective_ids:
            return False
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        checker = getattr(root, "is_within_objective_range", None)
        if not callable(checker):
            return False
        game_obj = self._resolve_game_context(game=game)
        game_map = getattr(game_obj, "map", None) if game_obj is not None else None
        objectives = list(getattr(game_map, "objectives", []) or []) if game_map is not None else []
        for objective in objectives:
            location = getattr(objective, "location", None) or objective
            objective_id = str(
                getattr(objective, "id", None)
                or get_entity_id(objective)
                or getattr(location, "id", None)
                or get_entity_id(location)
                or ""
            ).strip()
            if objective_id not in objective_ids:
                continue
            try:
                if bool(checker(location)):
                    return True
            except Exception:
                continue
        return False

    def oath_of_reclamation_melee_ap_bonus(
        self,
        attacker_model,
        target_unit=None,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        if not self.is_reclamation_force():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        if attacker_unit is None:
            return 0, ""
        if not self.attached_unit_is_adeptus_astartes(attacker_unit):
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            if parent is None or not bool(getattr(parent, "is_melee", lambda: False)()):
                return 0, ""
        target_root = self._attached_unit_root(target_unit)
        if target_root is None:
            return 0, ""
        game_obj = self._resolve_game_context(game=game)
        game_map = getattr(game_obj, "map", None) if game_obj is not None else None
        is_within_objective = getattr(target_root, "is_within_any_objective_range", None)
        if not callable(is_within_objective):
            return 0, ""
        try:
            if not bool(is_within_objective(game_map=game_map)):
                return 0, ""
        except Exception:
            return 0, ""
        return 1, "Oath of Reclamation"

    def oath_of_reclamation_wound_roll_penalty(
        self,
        target_unit,
        strength: int,
        *,
        game=None,
    ) -> tuple[int, str]:
        if not self.is_reclamation_force():
            return 0, ""
        target_root = self._attached_unit_root(target_unit)
        if target_root is None:
            return 0, ""
        if not self.attached_unit_is_adeptus_astartes(target_root):
            return 0, ""
        objective_ids = self._reclamation_objective_ids_at_phase_start(game=game)
        if not self._unit_within_objective_ids(target_root, objective_ids, game=game):
            return 0, ""
        toughness = None
        try:
            toughness = int(getattr(target_root, "toughness", 0) or 0)
        except Exception:
            toughness = None
        strength_gt_toughness = bool(
            isinstance(strength, int)
            and isinstance(toughness, int)
            and toughness > 0
            and strength > toughness
        )
        has_titus_keyword = self._attached_unit_has_keyword(target_root, "TITUS")
        if not (strength_gt_toughness or has_titus_keyword):
            return 0, ""
        return 1, "Oath of Reclamation"

    def _attached_unit_is_ancient(self, unit) -> bool:
        if unit is None:
            return False
        if self._attached_unit_has_keyword(unit, "ANCIENT"):
            return True
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        name = str(getattr(root, "name", "") or "").strip().lower()
        return "ancient" in name

    def _attached_unit_is_crusader_squad(self, unit) -> bool:
        if unit is None:
            return False
        if self._attached_unit_has_keyword(unit, "CRUSADER SQUAD"):
            return True
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        name = str(getattr(root, "name", "") or "").strip().lower()
        return "crusader squad" in name

    def purge_and_sanctify_wound_roll_penalty(
        self,
        target_unit,
        *,
        strength=None,
        target_toughness=None,
        game=None,
    ) -> tuple[int, str]:
        if not self.is_vindication_task_force():
            return 0, ""
        target_root = self._attached_unit_root(target_unit)
        if target_root is None:
            return 0, ""
        try:
            if target_root.get_parent_army() is not self.army:
                return 0, ""
        except Exception:
            return 0, ""
        if not self.attached_unit_is_adeptus_astartes(target_root):
            return 0, ""
        if not self._attached_unit_is_ancient(target_root):
            return 0, ""

        game_obj = self._resolve_game_context(game=game)
        game_map = getattr(game_obj, "map", None) if game_obj is not None else None
        within_any_objective = getattr(target_root, "is_within_any_objective_range", None)
        if callable(within_any_objective):
            try:
                if not bool(within_any_objective(game_map=game_map)):
                    return 0, ""
            except Exception:
                return 0, ""
        else:
            checker = getattr(target_root, "is_within_objective_range", None)
            if not callable(checker):
                return 0, ""
            in_range = False
            for objective in list(getattr(game_map, "objectives", []) or []):
                location = getattr(objective, "location", None) or objective
                if location is None or bool(getattr(location, "removed", False)):
                    continue
                try:
                    if bool(checker(location)):
                        in_range = True
                        break
                except Exception:
                    continue
            if not in_range:
                return 0, ""

        try:
            strength_value = int(strength)
        except (TypeError, ValueError):
            return 0, ""
        if isinstance(target_toughness, int):
            toughness_value = int(target_toughness)
        else:
            try:
                toughness_value = int(getattr(target_root, "toughness", 0) or 0)
            except Exception:
                toughness_value = 0
        if toughness_value <= 0 or strength_value <= toughness_value:
            return 0, ""
        return 1, "Purge and Sanctify"

    def purge_and_sanctify_righteous_zeal_objective_override_applies(self, unit) -> bool:
        if not self.is_vindication_task_force():
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
        return self._attached_unit_is_crusader_squad(root)

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

    def _champions_of_fenris_enhancement_source_member(self, unit, flag_key: str):
        root = self._attached_unit_root(unit)
        if root is None:
            return None, None, None
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        members.sort(key=lambda member: str(get_entity_id(member) or ""))
        for member in members:
            if member is None:
                continue
            sr = getattr(member, "special_rules", None)
            if isinstance(sr, dict) and bool(sr.get(flag_key, False)):
                return root, member, sr
        return root, None, None

    @staticmethod
    def _champions_of_fenris_member_has_live_bearer(member, sr) -> bool:
        if member is None or not isinstance(sr, dict):
            return False
        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "").strip()
        if bearer_id:
            for model in list(getattr(member, "models", []) or []):
                if str(get_entity_id(model) or "") != bearer_id:
                    continue
                alive_attr = getattr(model, "is_alive", True)
                return bool(alive_attr() if callable(alive_attr) else alive_attr)
            return False
        bearer = getattr(member, "_get_enhancement_bearer_model", lambda: None)()
        if bearer is None:
            return False
        alive_attr = getattr(bearer, "is_alive", True)
        return bool(alive_attr() if callable(alive_attr) else alive_attr)

    def champions_of_fenris_great_wolf_watches_trigger_range(self, unit) -> float:
        default_range = 3.0
        if not self.is_champions_of_fenris():
            return default_range
        root, member, sr = self._champions_of_fenris_enhancement_source_member(
            unit,
            "enhancement_wolves_wisdom",
        )
        if root is None:
            return default_range
        if not self.attached_unit_is_adeptus_astartes(root):
            return default_range
        if not self._champions_of_fenris_member_has_live_bearer(member, sr):
            return default_range
        try:
            base_range = float(sr.get("enhancement_wolves_wisdom_base_range", default_range) or default_range)
        except (TypeError, ValueError):
            base_range = default_range
        try:
            enhanced_range = float(sr.get("enhancement_wolves_wisdom_range", 6.0) or 6.0)
        except (TypeError, ValueError):
            enhanced_range = 6.0
        return float(max(base_range, enhanced_range))

    def champions_of_fenris_fangrune_pendant_applies(self, unit) -> bool:
        if not self.is_champions_of_fenris():
            return False
        root, member, sr = self._champions_of_fenris_enhancement_source_member(
            unit,
            "enhancement_fangrune_pendant",
        )
        if root is None:
            return False
        if not self.attached_unit_is_adeptus_astartes(root):
            return False
        return self._champions_of_fenris_member_has_live_bearer(member, sr)

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
        try:
            effective_range = float(range_inches)
        except (TypeError, ValueError):
            effective_range = 3.0
        effective_range = max(
            float(effective_range),
            float(self.champions_of_fenris_great_wolf_watches_trigger_range(reacting_root)),
        )
        if distance > float(effective_range) + 1e-6:
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

    def heroes_all_achieved_boasts(self) -> tuple[str, ...]:
        if not self.is_saga_of_the_bold():
            return ()
        return tuple(self.heroes_all_achieved_boast_keys or ())

    def heroes_all_saga_completed(self) -> bool:
        return len(self.heroes_all_achieved_boasts()) >= 3

    def _heroes_all_mark_boast(self, key: str) -> bool:
        if not self.is_saga_of_the_bold():
            return False
        boast_key = str(key or "").strip().upper()
        if boast_key not in set(self._HEROES_ALL_BOAST_KEYS):
            return False
        existing = set(self.heroes_all_achieved_boast_keys or ())
        if boast_key in existing:
            return False
        existing.add(boast_key)
        self.heroes_all_achieved_boast_keys = tuple(
            key_name for key_name in self._HEROES_ALL_BOAST_KEYS if key_name in existing
        )
        return True

    def _heroes_all_unit_is_space_wolves_character(self, unit) -> bool:
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        if not self.attached_unit_is_adeptus_astartes(root):
            return False
        if not self._attached_unit_has_keyword(root, "CHARACTER"):
            return False
        if self._attached_unit_has_keyword(root, "SPACE WOLVES"):
            return True
        return str(self.get_committed_chapter_keyword() or "").strip().upper() == "SPACE WOLVES"

    def _heroes_all_selection_key(self, unit, action: str) -> str:
        root = self._attached_unit_root(unit)
        if root is None:
            return ""
        unit_id = str(get_entity_id(root) or "")
        action_key = str(action or "").strip().lower()
        if not unit_id or action_key not in {"shoot", "fight"}:
            return ""
        return f"{unit_id}:{action_key}"

    def heroes_all_start_selection(self, unit, *, action: str, game=None) -> bool:
        if not self.is_saga_of_the_bold():
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
        selection_key = self._heroes_all_selection_key(root, action)
        if not selection_key:
            return False

        completed = self.heroes_all_saga_completed()
        is_character = self._heroes_all_unit_is_space_wolves_character(root)
        if not completed and not is_character:
            self.heroes_all_selection_state_by_key.pop(selection_key, None)
            return False

        if completed:
            state = {
                "mode": "one_each",
                "allow_hit": True,
                "allow_wound": True,
                "allow_damage": True,
                "hit_remaining": 1,
                "wound_remaining": 1,
                "damage_remaining": 1,
            }
        else:
            state = {
                "mode": "choice",
                "allow_hit": True,
                "allow_wound": True,
                "allow_damage": True,
                "remaining": 1,
            }
        self.heroes_all_selection_state_by_key[selection_key] = state
        return True

    def heroes_all_end_selection(self, unit, *, action: str) -> None:
        selection_key = self._heroes_all_selection_key(unit, action)
        if not selection_key:
            return
        self.heroes_all_selection_state_by_key.pop(selection_key, None)

    def heroes_all_reroll_is_available(self, unit, kind: str, *, action: str) -> bool:
        if not self.is_saga_of_the_bold():
            return False
        kind_key = str(kind or "").strip().lower()
        if kind_key not in {"hit", "wound", "damage"}:
            return False
        selection_key = self._heroes_all_selection_key(unit, action)
        if not selection_key:
            return False
        state = self.heroes_all_selection_state_by_key.get(selection_key)
        if not isinstance(state, dict):
            return False
        if not bool(state.get(f"allow_{kind_key}", False)):
            return False
        mode_key = str(state.get("mode", "choice") or "choice").strip().lower()
        if mode_key == "one_each":
            try:
                return int(state.get(f"{kind_key}_remaining", 0) or 0) > 0
            except (TypeError, ValueError):
                return False
        try:
            return int(state.get("remaining", 0) or 0) > 0
        except (TypeError, ValueError):
            return False

    def consume_heroes_all_reroll(self, unit, kind: str, *, action: str) -> bool:
        if not self.heroes_all_reroll_is_available(unit, kind, action=action):
            return False
        kind_key = str(kind or "").strip().lower()
        selection_key = self._heroes_all_selection_key(unit, action)
        if not selection_key:
            return False
        state = self.heroes_all_selection_state_by_key.get(selection_key)
        if not isinstance(state, dict):
            return False
        mode_key = str(state.get("mode", "choice") or "choice").strip().lower()
        if mode_key == "one_each":
            field = f"{kind_key}_remaining"
            state[field] = int(state.get(field, 0) or 0) - 1
        else:
            state["remaining"] = int(state.get("remaining", 0) or 0) - 1
        self.heroes_all_selection_state_by_key[selection_key] = state
        return True

    def heroes_all_on_unit_destroyed(self, destroyed_unit, *, destroyed_by_unit=None, game=None) -> bool:
        if not self.is_saga_of_the_bold():
            return False
        if destroyed_unit is None or destroyed_by_unit is None:
            return False
        destroyed_root = self._attached_unit_root(destroyed_unit)
        attacker_root = self._attached_unit_root(destroyed_by_unit)
        if destroyed_root is None or attacker_root is None:
            return False
        try:
            if attacker_root.get_parent_army() is not self.army:
                return False
        except Exception:
            return False
        try:
            if destroyed_root.get_parent_army() is self.army:
                return False
        except Exception:
            return False
        if not self._heroes_all_unit_is_space_wolves_character(attacker_root):
            return False
        oath_mgr = getattr(self.army, "oath_of_moment", None)
        is_oath_target = getattr(oath_mgr, "is_oath_target", None) if oath_mgr is not None else None
        if not callable(is_oath_target) or not bool(is_oath_target(destroyed_root)):
            return False
        attacker_id = str(get_entity_id(attacker_root) or "")
        if not attacker_id:
            return False
        current = int(self.heroes_all_oath_target_destroyed_count_by_unit_id.get(attacker_id, 0) or 0)
        new_count = current + 1
        self.heroes_all_oath_target_destroyed_count_by_unit_id[attacker_id] = new_count

        changed = self._heroes_all_mark_boast(self._HEROES_ALL_BOAST_HIDE_AS_TROPHY)
        if new_count >= 2:
            changed = self._heroes_all_mark_boast(self._HEROES_ALL_BOAST_SLAY_THEM_ALL) or changed
        return changed

    def _heroes_all_unit_wholly_in_opponent_deployment_zone(self, unit, *, game=None) -> bool:
        game_obj = self._resolve_game_context(game=game)
        if game_obj is None:
            return False
        owner = getattr(self.army, "player", None)
        if owner is None:
            return False
        opponent = None
        for player in list(getattr(game_obj, "players", []) or []):
            if player is None or player is owner:
                continue
            opponent = player
            break
        if opponent is None:
            return False
        opponent_id = str(getattr(opponent, "id", "") or "")
        if not opponent_id:
            return False
        if opponent_id not in dict(getattr(game_obj, "deployment_zones", {}) or {}):
            return False
        is_wholly = getattr(game_obj, "is_model_wholly_in_deployment_zone", None)
        if not callable(is_wholly):
            return False
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        get_models = getattr(root, "get_models_for_collision", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        alive_models = [model for model in models if model is not None and bool(getattr(model, "is_alive", True))]
        if not alive_models:
            return False
        for model in alive_models:
            if not bool(is_wholly(model, opponent_id)):
                return False
        return True

    def _heroes_all_unit_holds_non_home_objective(self, unit, *, game=None, owner_player=None) -> bool:
        game_obj = self._resolve_game_context(game=game)
        if game_obj is None:
            return False
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        is_within = getattr(root, "is_within_objective_range", None)
        if not callable(is_within):
            return False
        game_map = getattr(game_obj, "map", None)
        objectives = list(getattr(game_map, "objectives", []) or []) if game_map is not None else []
        if not objectives:
            return False
        owner = owner_player if owner_player is not None else getattr(self.army, "player", None)
        if owner is None:
            return False
        owner_id = str(getattr(owner, "id", "") or "")
        if not owner_id:
            return False
        in_home_zone = getattr(game_obj, "is_position_in_deployment_zone", None)
        for objective in objectives:
            location = getattr(objective, "location", None)
            if location is None or bool(getattr(location, "removed", False)):
                continue
            update_control = getattr(location, "update_control", None)
            if callable(update_control):
                update_control(game_obj)
            if getattr(location, "controlling_player", None) is not owner:
                continue
            if callable(in_home_zone) and bool(in_home_zone(float(location.x), float(location.y), owner_id)):
                continue
            if bool(is_within(location)):
                return True
        return False

    def heroes_all_handle_phase_end(self, phase, *, active_player=None, game=None) -> bool:
        if not self.is_saga_of_the_bold():
            return False
        game_obj = self._resolve_game_context(game=game)
        if game_obj is None:
            return False
        phase_name = str(getattr(phase, "name", "") or phase or "").strip().upper()
        if not phase_name:
            return False
        changed = False
        if phase_name == "FIGHT_PHASE":
            for root in self._iter_unique_army_roots():
                if not self._unit_is_on_battlefield(root):
                    continue
                if not self._heroes_all_unit_is_space_wolves_character(root):
                    continue
                if not self._heroes_all_unit_wholly_in_opponent_deployment_zone(root, game=game_obj):
                    continue
                changed = self._heroes_all_mark_boast(self._HEROES_ALL_BOAST_OVERRUN_THEIR_POSITION) or changed
                if changed:
                    break
        if phase_name == "COMMAND_PHASE":
            owner = getattr(self.army, "player", None)
            if owner is None or owner is not active_player:
                return changed
            battle_round = int(getattr(game_obj, "turn", 0) or 0)
            if battle_round < 2:
                return changed
            for root in self._iter_unique_army_roots():
                if not self._unit_is_on_battlefield(root):
                    continue
                if not self._heroes_all_unit_is_space_wolves_character(root):
                    continue
                if not self._heroes_all_unit_holds_non_home_objective(root, game=game_obj, owner_player=owner):
                    continue
                changed = self._heroes_all_mark_boast(self._HEROES_ALL_BOAST_HOLD_THE_LINE) or changed
                if changed:
                    break
        return changed

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

    @classmethod
    def master_of_wolves_pack_label(cls, key: str) -> str:
        return cls._MASTER_OF_WOLVES_PACK_LABELS.get(str(key or "").strip().upper(), str(key or "").strip())

    @classmethod
    def _normalize_master_of_wolves_pack_key(cls, value: str) -> str:
        raw = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
        if raw in cls._MASTER_OF_WOLVES_PACK_KEYS:
            return raw
        if raw in {"ENCIRCLING", "ENCIRCLINGJAWS", "JAWS"}:
            return cls._MASTER_OF_WOLVES_PACK_ENCIRCLING_JAWS
        if raw in {"HUNTERS_EYE", "HUNTERSEYE", "HUNTERS", "HUNTER"}:
            return cls._MASTER_OF_WOLVES_PACK_HUNTERS_EYE
        if raw in {"FEROCIOUS", "FEROCIOUSSTRIKE", "FEROCIOUS_STRIKE"}:
            return cls._MASTER_OF_WOLVES_PACK_FEROCIOUS_STRIKE
        return raw

    @staticmethod
    def _normalize_master_of_wolves_ferocious_choice(choice: str) -> str:
        raw = str(choice or "").strip().upper().replace("-", "_").replace(" ", "_")
        if raw in {"LETHAL", "LETHAL_HITS", "LETHALHITS"}:
            return "LETHAL_HITS"
        if raw in {"SUSTAINED", "SUSTAINED_HITS", "SUSTAINED_HITS_1", "SUSTAINEDHITS1"}:
            return "SUSTAINED_HITS_1"
        return raw

    def master_of_wolves_begin_command_phase(self, *, battle_round=None) -> None:
        if not self.is_saga_of_the_great_wolf():
            self.master_of_wolves_active_pack_key = ""
            self.master_of_wolves_active_round = 0
            self.master_of_wolves_active_player_id = ""
            return
        self.master_of_wolves_active_pack_key = ""
        self.master_of_wolves_active_round = 0
        self.master_of_wolves_active_player_id = ""
        if battle_round is not None:
            try:
                self.master_of_wolves_last_selection_round = int(self.master_of_wolves_last_selection_round or 0)
            except Exception:
                self.master_of_wolves_last_selection_round = 0

    def _master_of_wolves_logan_grimnar_on_battlefield(self) -> bool:
        if self.army is None:
            return False
        for root in self._iter_unique_army_roots():
            if not self._unit_is_on_battlefield(root):
                continue
            if self._attached_unit_name_contains(root, "Logan Grimnar"):
                return True
        return False

    def master_of_wolves_howling_onslaught_available(self, *, game=None) -> bool:
        _ = game
        if not self.is_saga_of_the_great_wolf():
            return False
        if bool(self.master_of_wolves_howling_onslaught_used):
            return False
        return self._master_of_wolves_logan_grimnar_on_battlefield()

    def get_available_master_of_wolves_packs(self, *, game=None) -> list[str]:
        if not self.is_saga_of_the_great_wolf():
            return []
        selected = {str(v or "").strip().upper() for v in list(self.master_of_wolves_selected_pack_keys or ())}
        if self.master_of_wolves_howling_onslaught_available(game=game):
            return list(self._MASTER_OF_WOLVES_PACK_KEYS)
        return [key for key in self._MASTER_OF_WOLVES_PACK_KEYS if key not in selected]

    def can_select_master_of_wolves_pack(self, *, game=None) -> bool:
        if not self.is_saga_of_the_great_wolf():
            return False
        if not self.get_available_master_of_wolves_packs(game=game):
            return False
        if game is None:
            return True
        try:
            round_now = int(getattr(game, "turn", 0) or 0)
        except Exception:
            return False
        if round_now <= 0:
            return False
        return int(getattr(self, "master_of_wolves_last_selection_round", 0) or 0) != round_now

    def mark_master_of_wolves_skipped_for_round(self, *, battle_round=None) -> None:
        if battle_round is None:
            return
        try:
            self.master_of_wolves_last_selection_round = int(battle_round)
        except Exception:
            self.master_of_wolves_last_selection_round = 0

    def master_of_wolves_pack_choice_is_valid(self, choice_key: str, *, game=None) -> bool:
        key = self._normalize_master_of_wolves_pack_key(choice_key)
        if key not in self._MASTER_OF_WOLVES_PACK_KEYS:
            return False
        return key in set(self.get_available_master_of_wolves_packs(game=game))

    def get_master_of_wolves_pack_options(self, *, game=None) -> list[dict[str, object]]:
        available = list(self.get_available_master_of_wolves_packs(game=game) or [])
        if not available:
            return []
        selected = {str(v or "").strip().upper() for v in list(self.master_of_wolves_selected_pack_keys or ())}
        summaries = {
            self._MASTER_OF_WOLVES_PACK_ENCIRCLING_JAWS: "Re-roll Advance and Charge rolls.",
            self._MASTER_OF_WOLVES_PACK_HUNTERS_EYE: "Add 1 to ranged Hit rolls.",
            self._MASTER_OF_WOLVES_PACK_FEROCIOUS_STRIKE: "When selected to fight, choose Lethal Hits or Sustained Hits 1 until end of phase.",
        }
        out: list[dict[str, object]] = []
        for key in available:
            pack_key = self._normalize_master_of_wolves_pack_key(key)
            if pack_key not in self._MASTER_OF_WOLVES_PACK_KEYS:
                continue
            reused = bool(pack_key in selected)
            label = self.master_of_wolves_pack_label(pack_key)
            payload = {
                "pack_key": pack_key,
                "pack_name": label,
                "reuse": bool(reused),
                "summary": str(summaries.get(pack_key, label) or label),
            }
            if reused:
                label = f"{label} (Howling Onslaught)"
            out.append(
                {
                    "label": label,
                    "summary": payload["summary"],
                    "payload": payload,
                }
            )
        return out

    def select_master_of_wolves_pack(
        self,
        choice_key: str,
        *,
        battle_round=None,
        player_id: str = "",
        game=None,
    ) -> bool:
        if not self.is_saga_of_the_great_wolf():
            return False
        key = self._normalize_master_of_wolves_pack_key(choice_key)
        if key not in self._MASTER_OF_WOLVES_PACK_KEYS:
            return False
        round_now = 0
        if battle_round is not None:
            try:
                round_now = int(battle_round)
            except Exception:
                round_now = 0
        elif game is not None:
            try:
                round_now = int(getattr(game, "turn", 0) or 0)
            except Exception:
                round_now = 0
        if round_now > 0 and int(getattr(self, "master_of_wolves_last_selection_round", 0) or 0) == round_now:
            return False

        selected = {str(v or "").strip().upper() for v in list(self.master_of_wolves_selected_pack_keys or ())}
        reused = key in selected
        if reused and not self.master_of_wolves_howling_onslaught_available(game=game):
            return False
        if not reused:
            selected.add(key)
        else:
            self.master_of_wolves_howling_onslaught_used = True

        self.master_of_wolves_selected_pack_keys = tuple(
            pack_key for pack_key in self._MASTER_OF_WOLVES_PACK_KEYS if pack_key in selected
        )
        self.master_of_wolves_active_pack_key = key
        self.master_of_wolves_active_round = int(round_now or 0)
        owner_id = str(player_id or "").strip()
        if not owner_id:
            owner_id = str(getattr(getattr(self.army, "player", None), "id", "") or "")
        self.master_of_wolves_active_player_id = owner_id
        if round_now > 0:
            self.master_of_wolves_last_selection_round = int(round_now)
        return True

    def _master_of_wolves_unit_is_eligible(self, unit) -> bool:
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        try:
            if root.get_parent_army() is not self.army:
                return False
        except Exception:
            return False
        return self.attached_unit_is_adeptus_astartes(root)

    def _master_of_wolves_recipient(self, unit) -> bool:
        if not self.is_saga_of_the_great_wolf():
            return False
        if str(getattr(self, "master_of_wolves_active_pack_key", "") or "").strip().upper() not in self._MASTER_OF_WOLVES_PACK_KEYS:
            return False
        return self._master_of_wolves_unit_is_eligible(unit)

    def master_of_wolves_reroll_advance_applies(self, unit) -> bool:
        if not self._master_of_wolves_recipient(unit):
            return False
        return str(self.master_of_wolves_active_pack_key or "").strip().upper() == self._MASTER_OF_WOLVES_PACK_ENCIRCLING_JAWS

    def master_of_wolves_reroll_charge_applies(self, unit) -> bool:
        return self.master_of_wolves_reroll_advance_applies(unit)

    def master_of_wolves_hunters_eye_hit_bonus(self, attacker_model, *, weapon_profile=None) -> tuple[int, str]:
        if str(self.master_of_wolves_active_pack_key or "").strip().upper() != self._MASTER_OF_WOLVES_PACK_HUNTERS_EYE:
            return 0, ""
        if attacker_model is None:
            return 0, ""
        unit = getattr(attacker_model, "parent_unit", None)
        if not self._master_of_wolves_recipient(unit):
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            if parent is None or not bool(getattr(parent, "is_ranged", lambda: False)()):
                return 0, ""
        return 1, "Hunter's Eye"

    def master_of_wolves_ferocious_strike_applies(self, unit, *, game=None) -> bool:
        _ = game
        if str(self.master_of_wolves_active_pack_key or "").strip().upper() != self._MASTER_OF_WOLVES_PACK_FEROCIOUS_STRIKE:
            return False
        return self._master_of_wolves_recipient(unit)

    def clear_master_of_wolves_ferocious_strike_choice(self, unit) -> None:
        root = self._attached_unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            "master_of_wolves_ferocious_choice",
            "master_of_wolves_ferocious_expires_phase",
            "master_of_wolves_ferocious_turn",
            "master_of_wolves_ferocious_turn_owner",
            "master_of_wolves_ferocious_source",
        ):
            sr.pop(key, None)
        root.special_rules = sr

    def set_master_of_wolves_ferocious_strike_choice(self, unit, choice: str, *, game=None) -> bool:
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        if not self.master_of_wolves_ferocious_strike_applies(root, game=game):
            return False
        choice_key = self._normalize_master_of_wolves_ferocious_choice(choice)
        if choice_key not in {"LETHAL_HITS", "SUSTAINED_HITS_1"}:
            return False
        game_obj = self._resolve_game_context(game=game)
        try:
            turn_now = int(getattr(game_obj, "turn", 0) or 0) if game_obj is not None else 0
        except Exception:
            turn_now = 0
        current_player = getattr(game_obj, "get_current_player", lambda: None)() if game_obj is not None else None
        owner_id = str(getattr(current_player, "id", "") or "")
        if not owner_id:
            owner_id = str(getattr(getattr(self.army, "player", None), "id", "") or "")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["master_of_wolves_ferocious_choice"] = choice_key
        sr["master_of_wolves_ferocious_expires_phase"] = "FIGHT_PHASE"
        sr["master_of_wolves_ferocious_turn"] = int(turn_now or 0)
        sr["master_of_wolves_ferocious_turn_owner"] = owner_id
        sr["master_of_wolves_ferocious_source"] = "Ferocious Strike"
        root.special_rules = sr
        return True

    def master_of_wolves_ferocious_strike_bonus(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[bool, int, str]:
        if attacker_model is None:
            return False, 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        root = self._attached_unit_root(attacker_unit)
        if root is None:
            return False, 0, ""
        if not self.master_of_wolves_ferocious_strike_applies(root, game=game):
            return False, 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            if parent is None or not bool(getattr(parent, "is_melee", lambda: False)()):
                return False, 0, ""
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False, 0, ""
        choice_key = self._normalize_master_of_wolves_ferocious_choice(str(sr.get("master_of_wolves_ferocious_choice", "") or ""))
        if choice_key not in {"LETHAL_HITS", "SUSTAINED_HITS_1"}:
            return False, 0, ""
        game_obj = self._resolve_game_context(game=game)
        if game_obj is not None:
            exp = str(sr.get("master_of_wolves_ferocious_expires_phase", "") or "").strip().upper()
            if exp:
                current_phase = str(getattr(getattr(game_obj, "phase", None), "name", "") or "").strip().upper()
                if current_phase and current_phase != exp:
                    return False, 0, ""
            owner_id = str(sr.get("master_of_wolves_ferocious_turn_owner", "") or "")
            if owner_id:
                current_player = getattr(game_obj, "get_current_player", lambda: None)()
                current_owner = str(getattr(current_player, "id", "") or "")
                if current_owner and current_owner != owner_id:
                    return False, 0, ""
            try:
                marked_turn = int(sr.get("master_of_wolves_ferocious_turn", 0) or 0)
            except Exception:
                marked_turn = 0
            try:
                current_turn = int(getattr(game_obj, "turn", 0) or 0)
            except Exception:
                current_turn = 0
            if marked_turn and current_turn and marked_turn != current_turn:
                return False, 0, ""
        source = str(sr.get("master_of_wolves_ferocious_source", "") or "Ferocious Strike").strip() or "Ferocious Strike"
        if choice_key == "LETHAL_HITS":
            return True, 0, source
        return False, 1, source

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

    def _blade_of_ultramar_enhancement_source_member(self, unit, flag_key: str):
        if unit is None:
            return None, None, {}
        root = self._attached_unit_root(unit)
        if root is None:
            return None, None, {}
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        try:
            members.sort(key=lambda member: str(get_entity_id(member) or ""))
        except Exception:
            pass
        for member in list(members or []):
            if member is None:
                continue
            sr = getattr(member, "special_rules", None)
            if isinstance(sr, dict) and bool(sr.get(flag_key, False)):
                return root, member, sr
        return root, None, {}

    def _blade_of_ultramar_member_has_live_bearer(self, member, sr, *, require_leading: bool = False) -> bool:
        if member is None or not isinstance(sr, dict):
            return False
        if require_leading and not bool(getattr(member, "is_attached_leader", False)):
            return False
        bearer = self._blade_of_ultramar_resolve_bearer_model(member, sr)
        if bearer is None:
            return False
        alive_attr = getattr(bearer, "is_alive", True)
        return bool(alive_attr() if callable(alive_attr) else alive_attr)

    @staticmethod
    def _blade_of_ultramar_resolve_bearer_model(member, sr):
        bearer = getattr(member, "_get_enhancement_bearer_model", lambda: None)()
        if bearer is None:
            bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "").strip()
            if bearer_id:
                for model in list(getattr(member, "models", []) or []):
                    if str(get_entity_id(model) or "") != bearer_id:
                        continue
                    bearer = model
                    break
        return bearer

    def _blade_of_ultramar_model_is_live_bearer(self, model, member, sr) -> bool:
        if model is None:
            return False
        bearer = self._blade_of_ultramar_resolve_bearer_model(member, sr)
        if bearer is None:
            return False
        alive_attr = getattr(bearer, "is_alive", True)
        is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if not is_alive:
            return False
        return str(get_entity_id(model) or "") == str(get_entity_id(bearer) or "")

    def blade_of_ultramar_student_of_the_codex_active_doctrine(self, unit, *, game=None) -> str:
        if not self.is_blade_of_ultramar():
            return ""
        root, member, sr = self._blade_of_ultramar_enhancement_source_member(
            unit,
            "enhancement_student_of_the_codex",
        )
        if root is None or member is None or not isinstance(sr, dict):
            return ""
        if not bool(sr.get("enhancement_student_of_the_codex_active", False)):
            return ""
        if not self._blade_of_ultramar_member_has_live_bearer(member, sr, require_leading=False):
            return ""
        doctrine = str(sr.get("enhancement_student_of_the_codex_doctrine", "TACTICAL") or "TACTICAL").strip().upper()
        if not doctrine:
            doctrine = "TACTICAL"
        game_obj = game
        if game_obj is None and self.army is not None:
            game_obj = getattr(getattr(self.army, "player", None), "game", None)
        if game_obj is not None:
            owner_id = str(sr.get("enhancement_student_of_the_codex_owner_id", "") or "")
            try:
                expires_round = int(sr.get("enhancement_student_of_the_codex_expires_round", 0) or 0)
            except Exception:
                expires_round = 0
            try:
                current_round = int(getattr(game_obj, "turn", 0) or 0)
            except Exception:
                current_round = 0
            current_player = getattr(game_obj, "get_current_player", lambda: None)()
            current_owner = str(getattr(current_player, "id", "") or "")
            phase_name = str(getattr(getattr(game_obj, "phase", None), "name", "") or "").strip().upper()
            if (
                expires_round > 0
                and current_round >= expires_round
                and owner_id
                and current_owner == owner_id
                and phase_name == "COMMAND_PHASE"
            ):
                return ""
        return doctrine

    def blade_of_ultramar_veteran_of_behemoth_sustained_hits(
        self,
        attacker_model,
        weapon_profile=None,
        *,
        game=None,
    ) -> tuple[int, str]:
        if not self.is_blade_of_ultramar():
            return 0, ""
        if attacker_model is None:
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        if attacker_unit is None:
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            if parent is not None and not bool(getattr(parent, "is_ranged", lambda: False)()):
                return 0, ""
        root, member, sr = self._blade_of_ultramar_enhancement_source_member(
            attacker_unit,
            "enhancement_veteran_of_behemoth",
        )
        if root is None or member is None or not isinstance(sr, dict):
            return 0, ""
        requires_leading = bool(sr.get("enhancement_veteran_of_behemoth_requires_leading", True))
        if not self._blade_of_ultramar_member_has_live_bearer(member, sr, require_leading=requires_leading):
            return 0, ""
        try:
            sustained_hits = int(sr.get("enhancement_veteran_of_behemoth_sustained_hits_value", 1) or 1)
        except Exception:
            sustained_hits = 1
        if sustained_hits <= 0:
            return 0, ""
        source = str(sr.get("enhancement_veteran_of_behemoth_source", "") or "Veteran of Behemoth").strip()
        if not source:
            source = "Veteran of Behemoth"
        return int(sustained_hits), source

    def blade_of_ultramar_armour_of_antoninus_save_override(
        self,
        model,
        *,
        game=None,
    ) -> tuple[int, str]:
        if not self.is_blade_of_ultramar():
            return 0, ""
        if model is None:
            return 0, ""
        unit = getattr(model, "parent_unit", None)
        if unit is None:
            return 0, ""
        _root, member, sr = self._blade_of_ultramar_enhancement_source_member(
            unit,
            "enhancement_armour_of_antoninus",
        )
        if member is None or not isinstance(sr, dict):
            return 0, ""
        if not self._blade_of_ultramar_model_is_live_bearer(model, member, sr):
            return 0, ""
        try:
            save_value = int(sr.get("enhancement_armour_of_antoninus_save", 2) or 2)
        except Exception:
            save_value = 2
        if save_value <= 0:
            return 0, ""
        source = str(sr.get("enhancement_armour_of_antoninus_source", "") or "Armour of Antoninus").strip()
        if not source:
            source = "Armour of Antoninus"
        return int(max(2, save_value)), source

    def blade_of_ultramar_oath_of_macragge_bonus(
        self,
        attacker_model,
        weapon_profile=None,
        *,
        game=None,
    ) -> tuple[int, str]:
        if not self.is_blade_of_ultramar():
            return 0, ""
        if attacker_model is None:
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        if attacker_unit is None:
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            if parent is not None and not bool(getattr(parent, "is_melee", lambda: False)()):
                return 0, ""
        root, member, sr = self._blade_of_ultramar_enhancement_source_member(
            attacker_unit,
            "enhancement_oath_of_macragge",
        )
        if root is None or member is None or not isinstance(sr, dict):
            return 0, ""
        if not self._blade_of_ultramar_model_is_live_bearer(attacker_model, member, sr):
            return 0, ""
        doctrine_mgr = getattr(self.army, "combat_doctrines", None) if self.army is not None else None
        if doctrine_mgr is None:
            return 0, ""
        game_obj = game
        if game_obj is None and self.army is not None:
            game_obj = getattr(getattr(self.army, "player", None), "game", None)
        active = getattr(doctrine_mgr, "get_active_doctrine_for_unit", lambda _u, game=None: None)(
            root,
            game=game_obj,
        )
        active_key = str(getattr(active, "key", "") or "").strip().upper() if active is not None else ""
        try:
            base_bonus = int(sr.get("enhancement_oath_of_macragge_base_bonus", 1) or 1)
        except Exception:
            base_bonus = 1
        try:
            assault_bonus = int(sr.get("enhancement_oath_of_macragge_assault_bonus", 2) or 2)
        except Exception:
            assault_bonus = 2
        bonus = int(assault_bonus if active_key == "ASSAULT" else base_bonus)
        if bonus <= 0:
            return 0, ""
        source = str(sr.get("enhancement_oath_of_macragge_source", "") or "Oath of Macragge").strip()
        if not source:
            source = "Oath of Macragge"
        return int(bonus), source

    def blade_of_ultramar_veteran_of_behemoth_reroll_advance_applies(self, unit, *, game=None) -> bool:
        if not self.is_blade_of_ultramar():
            return False
        root, member, sr = self._blade_of_ultramar_enhancement_source_member(
            unit,
            "enhancement_veteran_of_behemoth",
        )
        if root is None or member is None or not isinstance(sr, dict):
            return False
        requires_leading = bool(sr.get("enhancement_veteran_of_behemoth_requires_leading", True))
        if not self._blade_of_ultramar_member_has_live_bearer(member, sr, require_leading=requires_leading):
            return False
        doctrine_key = str(
            sr.get("enhancement_veteran_of_behemoth_advance_reroll_doctrine", "DEVASTATOR") or "DEVASTATOR"
        ).strip().upper()
        if not doctrine_key:
            doctrine_key = "DEVASTATOR"
        doctrine_mgr = getattr(self.army, "combat_doctrines", None) if self.army is not None else None
        if doctrine_mgr is None:
            return False
        game_obj = game
        if game_obj is None and self.army is not None:
            game_obj = getattr(getattr(self.army, "player", None), "game", None)
        active = getattr(doctrine_mgr, "get_active_doctrine_for_unit", lambda _u, game=None: None)(
            root,
            game=game_obj,
        )
        if active is None:
            return False
        active_key = str(getattr(active, "key", "") or "").strip().upper()
        return bool(active_key and active_key == doctrine_key)

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

    def _legacy_of_the_angel_troubling_visions_applies(self, unit) -> bool:
        if unit is None:
            return False
        if not self.is_angelic_inheritors():
            return False
        if not self.attached_unit_is_adeptus_astartes(unit):
            return False
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        try:
            members.sort(key=lambda member: str(get_entity_id(member) or ""))
        except Exception:
            pass
        game = None
        player = getattr(self.army, "player", None) if self.army is not None else None
        if player is not None:
            game = getattr(player, "game", None)
        current_round = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
        current_player_id = ""
        if game is not None:
            current_player = getattr(game, "get_current_player", lambda: None)()
            current_player_id = str(getattr(current_player, "id", "") or "")
        for member in list(members or []):
            if member is None:
                continue
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_troubling_visions_active", False)):
                continue
            bearer = getattr(member, "_get_enhancement_bearer_model", lambda: None)()
            if bearer is None or not bool(getattr(bearer, "is_alive", True)):
                continue
            owner_id = str(sr.get("enhancement_troubling_visions_owner_id", "") or "")
            try:
                expires_round = int(sr.get("enhancement_troubling_visions_expires_round", 0) or 0)
            except (TypeError, ValueError):
                expires_round = 0
            if (
                expires_round > 0
                and current_round >= expires_round
                and owner_id
                and current_player_id == owner_id
                and phase_name == "COMMAND_PHASE"
            ):
                continue
            return True
        return False

    def legacy_of_the_angel_sanguinary_grace_applies(self, unit) -> bool:
        if self._legacy_of_the_angel_recipient(unit):
            if self.angelic_legacy_option_active(self._ANGELIC_LEGACY_SANGUINARY_GRACE):
                return True
        return self._legacy_of_the_angel_troubling_visions_applies(unit)

    def legacy_of_the_angel_carmine_wrath_applies(self, unit) -> bool:
        if self._legacy_of_the_angel_recipient(unit):
            if self.angelic_legacy_option_active(self._ANGELIC_LEGACY_CARMINE_WRATH):
                return True
        return self._legacy_of_the_angel_troubling_visions_applies(unit)

    def legacy_of_the_angel_their_appointed_hour_applies(self, unit) -> bool:
        if self._legacy_of_the_angel_recipient(unit):
            if self.angelic_legacy_option_active(self._ANGELIC_LEGACY_THEIR_APPOINTED_HOUR):
                return True
        return self._legacy_of_the_angel_troubling_visions_applies(unit)

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
