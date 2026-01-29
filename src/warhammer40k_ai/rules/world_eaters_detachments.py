from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional
import re

from .detachment_manager import DetachmentManagerBase
from ..utility.aura_utils import unit_within_range_of_unit
from ..utility.entity_ids import get_entity_id


@dataclass(frozen=True)
class BloodTitheAbility:
    key: str
    name: str
    cost: int
    summary: str


BLOOD_TITHE_ENRAGED_ABJURATION = BloodTitheAbility(
    key="ENRAGED_ABJURATION",
    name="Enraged Abjuration",
    cost=2,
    summary="FNP 5+ vs Psychic attacks and mortal wounds for BLOOD LEGIONS/WORLD EATERS.",
)
BLOOD_TITHE_DAEMONIC_RAGE = BloodTitheAbility(
    key="DAEMONIC_RAGE",
    name="Daemonic Rage",
    cost=3,
    summary="BLOOD LEGIONS melee weapons gain [LANCE].",
)
BLOOD_TITHE_BOON_OF_BLOOD = BloodTitheAbility(
    key="BOON_OF_BLOOD",
    name="Boon of Blood",
    cost=4,
    summary="BLOOD LEGIONS units gain a 4+ invulnerable save.",
)
BLOOD_TITHE_MIGHT_OF_KHORNE = BloodTitheAbility(
    key="MIGHT_OF_KHORNE",
    name="Might of Khorne",
    cost=5,
    summary="BLOOD LEGIONS units gain the Blessings of Khorne ability.",
)

BLOOD_TITHE_ABILITIES: tuple[BloodTitheAbility, ...] = (
    BLOOD_TITHE_ENRAGED_ABJURATION,
    BLOOD_TITHE_DAEMONIC_RAGE,
    BLOOD_TITHE_BOON_OF_BLOOD,
    BLOOD_TITHE_MIGHT_OF_KHORNE,
)


@dataclass(frozen=True)
class IdolOfKhorneAbility:
    key: str
    name: str
    summary: str


IDOL_OF_INFINITE_RAGE = IdolOfKhorneAbility(
    key="INFINITE_RAGE",
    name="Idol of Infinite Rage (Aura)",
    summary="JAKHALS/GOREMONGERS within 6\" (9\" if source is TITANIC) gain +1 to Hit and Wound rolls.",
)
IDOL_OF_BURNING_WRATH = IdolOfKhorneAbility(
    key="BURNING_WRATH",
    name="Idol of Burning Wrath (Aura)",
    summary="JAKHALS/GOREMONGERS within 6\" (9\" if source is TITANIC) gain +1\" Move and +1 to Advance/Charge rolls.",
)
IDOL_OF_BLESSED_BLOOD = IdolOfKhorneAbility(
    key="BLESSED_BLOOD",
    name="Idol of Blessed Blood (Aura)",
    summary="JAKHALS/GOREMONGERS within 6\" (9\" if source is TITANIC) gain a 4+ invulnerable save.",
)

IDOLS_OF_KHORNE_ABILITIES: tuple[IdolOfKhorneAbility, ...] = (
    IDOL_OF_INFINITE_RAGE,
    IDOL_OF_BURNING_WRATH,
    IDOL_OF_BLESSED_BLOOD,
)


class WorldEatersDetachmentManager(DetachmentManagerBase):
    faction_id = "WE"

    def __init__(self, army=None):
        super().__init__(army)
        self.blood_tithe_points: int = 0
        self.blood_tithe_active: set[str] = set()
        self._blood_tithe_command_phase_key: Optional[tuple] = None
        self.idols_used: set[str] = set()
        self.active_idol_key: Optional[str] = None
        self._idols_command_phase_key: Optional[tuple] = None
        self._vessel_of_wrath_model_ids: set[str] = set()
        self._vessel_of_wrath_round: Optional[int] = None
        self._wrath_of_khorne_prompt_round: Optional[int] = None
        self._wrath_of_khorne_blessing_round: Optional[int] = None
        self._wrath_of_khorne_blessing_key: Optional[str] = None

    def is_berzerker_warband(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Berzerker Warband")

    def is_khorne_daemonkin(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Khorne Daemonkin")

    def is_goretrack_onslaught(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Goretrack Onslaught")

    def is_possessed_slaughterband(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Possessed Slaughterband")

    def is_cult_of_blood(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Cult of Blood")

    def is_vessels_of_wrath(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Vessels of Wrath")

    def _attached_unit_has_keyword(self, unit, keyword: str) -> bool:
        if unit is None:
            return False
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        members = (
            list(root.get_attached_unit_members() or [])
            if hasattr(root, "get_attached_unit_members")
            else [root]
        )
        for u in members:
            if self._unit_has_keyword(u, keyword):
                return True
        return False

    def unit_is_blood_legions(self, unit) -> bool:
        return self._attached_unit_has_keyword(unit, "BLOOD LEGIONS")

    def unit_is_world_eaters(self, unit) -> bool:
        return self._attached_unit_has_keyword(unit, "WORLD EATERS")

    @staticmethod
    def _norm_name(text: str) -> str:
        s = str(text or "").strip().lower()
        s = s.replace("\u2019", "'")
        s = re.sub(r"<[^>]+>", " ", s)
        s = re.sub(r"[^a-z0-9]+", " ", s)
        return re.sub(r"\s+", " ", s).strip()

    def _model_is_wrath_of_khorne_candidate(self, model) -> bool:
        if model is None:
            return False
        unit = getattr(model, "parent_unit", None)
        if unit is None:
            return False
        if not self.unit_is_world_eaters(unit):
            return False
        has_any_keyword = getattr(unit, "has_any_keyword", None)
        if callable(has_any_keyword):
            is_character = bool(has_any_keyword("CHARACTER"))
            is_epic = bool(has_any_keyword("EPIC HERO"))
        else:
            kws = [str(k).lower() for k in (getattr(unit, "keywords", []) or [])]
            is_character = "character" in kws
            is_epic = "epic hero" in kws
        if is_character and not is_epic:
            return True
        name = self._norm_name(getattr(model, "name", "") or "")
        if not name:
            return False
        if name in {
            "eightbound champion",
            "exalted eightbound champion",
            "khorne berzerkers champion",
            "khorne berzerker champion",
            "world eaters terminator champion",
            "terminator champion",
        }:
            return True
        return False

    def _iter_army_models(self) -> list:
        units = list(getattr(self.army, "units", []) or []) if self.army is not None else []
        models = []
        for unit in units:
            for model in list(getattr(unit, "models", []) or []):
                models.append(model)
        return models

    def get_wrath_of_khorne_max_models(self) -> int:
        points_limit = int(getattr(self.army, "points_limit", 0) or 0) if self.army is not None else 0
        if points_limit <= 1000:
            return 2
        if points_limit <= 2000:
            return 3
        return 4

    def get_wrath_of_khorne_candidates(self) -> list:
        if not self.is_vessels_of_wrath():
            return []
        candidates = []
        for model in self._iter_army_models():
            if hasattr(model, "is_alive") and not bool(getattr(model, "is_alive", True)):
                continue
            if self._model_is_wrath_of_khorne_candidate(model):
                candidates.append(model)
        return candidates

    def _clear_vessel_of_wrath_keywords(self, *, battle_round: int) -> None:
        if self._vessel_of_wrath_round is None:
            return
        if int(self._vessel_of_wrath_round) == int(battle_round):
            return
        ids = set(self._vessel_of_wrath_model_ids or set())
        if not ids:
            self._vessel_of_wrath_round = None
            return
        for model in self._iter_army_models():
            mid = get_entity_id(model)
            if str(mid) not in ids:
                continue
            kws = list(getattr(model, "keywords", []) or [])
            new_kws = [k for k in kws if str(k).strip().lower() != "vessel of wrath"]
            model.keywords = new_kws
        self._vessel_of_wrath_model_ids = set()
        self._vessel_of_wrath_round = None
        self._wrath_of_khorne_blessing_key = None
        self._wrath_of_khorne_blessing_round = None

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if not self.is_vessels_of_wrath():
            return
        self._clear_vessel_of_wrath_keywords(battle_round=int(battle_round))
        self._wrath_of_khorne_prompt_round = None

    def apply_wrath_of_khorne_models(self, model_ids: list[str], *, battle_round: int) -> bool:
        if not self.is_vessels_of_wrath():
            return False
        ids = [str(mid) for mid in list(model_ids or []) if str(mid or "")]
        if not ids:
            return False
        unique_ids = []
        seen = set()
        for mid in ids:
            if mid in seen:
                continue
            seen.add(mid)
            unique_ids.append(mid)
        self._clear_vessel_of_wrath_keywords(battle_round=int(battle_round))
        selected = []
        for model in self._iter_army_models():
            mid = str(get_entity_id(model))
            if mid in seen:
                selected.append(model)
        if not selected:
            return False
        for model in selected:
            kws = list(getattr(model, "keywords", []) or [])
            if not any(str(k).strip().lower() == "vessel of wrath" for k in kws):
                kws.append("Vessel of Wrath")
                model.keywords = kws
        self._vessel_of_wrath_model_ids = set(unique_ids)
        self._vessel_of_wrath_round = int(battle_round)
        return True

    def has_active_wrath_of_khorne_models(self, *, battle_round: int) -> bool:
        return bool(self._vessel_of_wrath_model_ids) and int(self._vessel_of_wrath_round or 0) == int(battle_round)

    def apply_wrath_of_khorne_blessing(self, blessing_key: str, *, battle_round: int) -> bool:
        if not self.is_vessels_of_wrath():
            return False
        if not self._vessel_of_wrath_model_ids:
            return False
        if int(self._vessel_of_wrath_round or 0) != int(battle_round):
            return False
        army = self.army
        mgr = getattr(army, "blessings_of_khorne", None) if army is not None else None
        if mgr is None:
            return False
        key = str(blessing_key or "").strip().upper()
        if not key:
            return False
        roots = []
        seen_units = set()
        for model in self._iter_army_models():
            mid = str(get_entity_id(model))
            if mid not in self._vessel_of_wrath_model_ids:
                continue
            unit = getattr(model, "parent_unit", None)
            if unit is None:
                continue
            root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
            rid = str(get_entity_id(root))
            if rid in seen_units:
                continue
            seen_units.add(rid)
            roots.append(root)
        if not roots:
            return False
        applied_any = False
        for unit in roots:
            if mgr.grant_unit_blessings(unit, blessing_keys=[key], battle_round=int(battle_round)):
                applied_any = True
        if applied_any:
            self._wrath_of_khorne_blessing_key = key
            self._wrath_of_khorne_blessing_round = int(battle_round)
        return applied_any

    def prompt_wrath_of_khorne_model_selection(
        self,
        *,
        game=None,
        player=None,
        battle_round: Optional[int] = None,
        source: str = "",
    ) -> bool:
        if game is None or player is None:
            return False
        if not self.is_vessels_of_wrath():
            return False
        if not bool(getattr(game, "is_authoritative", True)):
            return False
        if battle_round is None:
            battle_round = int(getattr(game, "turn", 0) or 0)
        if self._wrath_of_khorne_prompt_round == int(battle_round):
            return False
        candidates = list(self.get_wrath_of_khorne_candidates() or [])
        if not candidates:
            return False
        from ..engine.decision_kinds import DECISION_SELECT_VESSEL_OF_WRATH_MODELS
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.entity_ids import get_entity_id

        army_id = get_entity_id(self.army) if self.army is not None else None
        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_SELECT_VESSEL_OF_WRATH_MODELS:
                    continue
                ctx = getattr(req, "context", {}) or {}
                if str(ctx.get("army_id", "")) == str(army_id) and int(ctx.get("battle_round", 0) or 0) == int(battle_round):
                    return True

        allowed_model_ids = [str(get_entity_id(m)) for m in candidates]
        max_models = self.get_wrath_of_khorne_max_models()
        req = DecisionRequest.create(
            DECISION_SELECT_VESSEL_OF_WRATH_MODELS,
            "Select Vessels of Wrath models (optional).",
            player_id=getattr(player, "id", None),
            options=[
                DecisionOption.create("Confirm", payload={"action": "confirm", "army_id": army_id}),
                DecisionOption.create("None", payload={"action": "skip", "skip": True, "army_id": army_id}),
            ],
            context={
                "army_id": army_id,
                "battle_round": int(battle_round),
                "max_models": int(max_models),
                "allowed_model_ids": allowed_model_ids,
                "source": source,
            },
        )
        self._wrath_of_khorne_prompt_round = int(battle_round)
        if hasattr(game, "request_decision"):
            game.request_decision(req)
            return True
        return False

    def prompt_wrath_of_khorne_blessing_selection(
        self,
        *,
        game=None,
        player=None,
        battle_round: Optional[int] = None,
        source: str = "",
    ) -> bool:
        if game is None or player is None:
            return False
        if not self.is_vessels_of_wrath():
            return False
        if not bool(getattr(game, "is_authoritative", True)):
            return False
        if battle_round is None:
            battle_round = int(getattr(game, "turn", 0) or 0)
        army = self.army
        mgr = getattr(army, "blessings_of_khorne", None) if army is not None else None
        if mgr is None:
            return False
        active = set(str(k).strip().upper() for k in (mgr.active_blessing_keys or set()))
        available_defs = [d for d in list(getattr(mgr, "definitions", {}).values()) if d.key not in active]
        if not available_defs:
            return False
        from ..engine.decision_kinds import DECISION_CHOOSE_VESSEL_OF_WRATH_BLESSING
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.entity_ids import get_entity_id

        army_id = get_entity_id(self.army) if self.army is not None else None
        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_VESSEL_OF_WRATH_BLESSING:
                    continue
                ctx = getattr(req, "context", {}) or {}
                if str(ctx.get("army_id", "")) == str(army_id) and int(ctx.get("battle_round", 0) or 0) == int(battle_round):
                    return True

        options = []
        for d in available_defs:
            options.append(
                DecisionOption.create(
                    d.name,
                    payload={"blessing_key": d.key, "army_id": army_id, "summary": d.short_effect},
                )
            )
        if not options:
            return False
        req = DecisionRequest.create(
            DECISION_CHOOSE_VESSEL_OF_WRATH_BLESSING,
            "Select a Blessing of Khorne for Vessels of Wrath.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "army_id": army_id,
                "battle_round": int(battle_round),
                "source": source,
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(req)
            return True
        return False

    def _unit_is_jakhals_or_goremongers(self, unit) -> bool:
        if unit is None:
            return False
        if self._attached_unit_has_keyword(unit, "JAKHALS"):
            return True
        return self._attached_unit_has_keyword(unit, "GOREMONGERS")

    def _resolve_game_map(self, *, unit=None, game=None, game_map=None):
        if game_map is not None:
            return game_map
        if game is not None:
            return getattr(game, "map", None)
        if unit is not None and hasattr(unit, "get_parent_army"):
            army = unit.get_parent_army()
            game = getattr(getattr(army, "player", None), "game", None)
            return getattr(game, "map", None) if game is not None else None
        game = getattr(getattr(self.army, "player", None), "game", None)
        return getattr(game, "map", None) if game is not None else None

    def _unit_is_valid_idol_source(self, unit) -> bool:
        if unit is None:
            return False
        if self.army is not None:
            if not hasattr(unit, "get_parent_army"):
                return False
            if unit.get_parent_army() is not self.army:
                return False
        if not self.unit_is_world_eaters(unit):
            return False
        if not (bool(getattr(unit, "is_titanic", False)) or bool(getattr(unit, "is_monster", False))):
            return False
        if hasattr(unit, "is_alive") and callable(unit.is_alive):
            if not unit.is_alive():
                return False
        if hasattr(unit, "deployed") and not bool(getattr(unit, "deployed", True)):
            return False
        if str(getattr(unit, "reserve_status", "deployed")) != "deployed":
            return False
        return True

    def _idol_range_for_source(self, source_unit) -> float:
        return 9.0 if bool(getattr(source_unit, "is_titanic", False)) else 6.0

    def _idol_sources_for_unit(self, unit, idol_key: str, *, game_map=None) -> list:
        if unit is None:
            return []
        if not self.is_cult_of_blood():
            return []
        key = str(idol_key or "").strip().upper()
        if not key:
            return []
        if str(self.active_idol_key or "").strip().upper() != key:
            return []
        if not self._unit_is_jakhals_or_goremongers(unit):
            return []
        if not hasattr(unit, "get_parent_army"):
            return []
        if unit.get_parent_army() is not self.army:
            return []
        game_map = self._resolve_game_map(unit=unit, game_map=game_map)
        if game_map is None:
            return []
        sources = []
        for source in list(getattr(game_map, "get_friendly_units", lambda _u: [])(unit) or []):
            if not self._unit_is_valid_idol_source(source):
                continue
            rng = self._idol_range_for_source(source)
            if unit_within_range_of_unit(source, unit, rng, use_attached_aggregate=True):
                sources.append(source)
        return sources

    def idols_of_khorne_infinite_rage_sources_for_unit(self, unit, *, game_map=None) -> list:
        return self._idol_sources_for_unit(unit, "INFINITE_RAGE", game_map=game_map)

    def idols_of_khorne_burning_wrath_sources_for_unit(self, unit, *, game_map=None) -> list:
        return self._idol_sources_for_unit(unit, "BURNING_WRATH", game_map=game_map)

    def idols_of_khorne_blessed_blood_sources_for_unit(self, unit, *, game_map=None) -> list:
        return self._idol_sources_for_unit(unit, "BLESSED_BLOOD", game_map=game_map)

    def idols_of_khorne_infinite_rage_applies(self, unit, *, game_map=None) -> bool:
        return bool(self.idols_of_khorne_infinite_rage_sources_for_unit(unit, game_map=game_map))

    def idols_of_khorne_burning_wrath_applies(self, unit, *, game_map=None) -> bool:
        return bool(self.idols_of_khorne_burning_wrath_sources_for_unit(unit, game_map=game_map))

    def idols_of_khorne_blessed_blood_applies(self, unit, *, game_map=None) -> bool:
        return bool(self.idols_of_khorne_blessed_blood_sources_for_unit(unit, game_map=game_map))

    def apply_cult_of_blood_battleline_keywords(self, unit=None) -> None:
        if not self.is_cult_of_blood():
            return
        if unit is None:
            units = list(getattr(self.army, "units", []) or []) if self.army is not None else []
        else:
            units = [unit]
        for u in units:
            if u is None:
                continue
            root = u.get_attached_unit_root() if hasattr(u, "get_attached_unit_root") else u
            if not self._unit_is_jakhals_or_goremongers(root):
                continue
            kws = list(getattr(root, "keywords", []) or [])
            if not any(str(k).strip().lower() == "battleline" for k in kws):
                kws.append("Battleline")
                root.keywords = kws

    def goretrack_onslaught_applies(self, unit) -> bool:
        if not self.is_goretrack_onslaught():
            return False
        return self.unit_is_world_eaters(unit)

    def brazen_fury_applies(self, unit) -> bool:
        if not self.is_possessed_slaughterband():
            return False
        if unit is None:
            return False
        if not self.unit_is_world_eaters(unit):
            return False
        return self._attached_unit_has_keyword(unit, "POSSESSED")

    def unit_is_blood_tithe_eligible(self, unit) -> bool:
        return self.unit_is_blood_legions(unit) or self.unit_is_world_eaters(unit)

    def relentless_rage_applies(self, unit) -> bool:
        if not self.is_berzerker_warband():
            return False
        if unit is None:
            return False
        try:
            if unit.has_any_keyword("WORLD EATERS"):
                return True
            return False
        except Exception:
            return self._army_faction_matches(self.faction_id)

    def _command_phase_key(self, game, player) -> tuple:
        try:
            br = int(getattr(game, "turn", 0) or 0)
        except Exception:
            br = 0
        return (br, get_entity_id(player))

    def get_blood_tithe_abilities(self) -> tuple[BloodTitheAbility, ...]:
        return BLOOD_TITHE_ABILITIES

    def get_active_blood_tithe_abilities(self) -> list[BloodTitheAbility]:
        active = set(str(k or "").strip().upper() for k in (self.blood_tithe_active or set()))
        return [ab for ab in BLOOD_TITHE_ABILITIES if ab.key in active]

    def get_idols_of_khorne_abilities(self) -> tuple[IdolOfKhorneAbility, ...]:
        return IDOLS_OF_KHORNE_ABILITIES

    def get_active_idol_key(self) -> Optional[str]:
        if not self.is_cult_of_blood():
            return None
        key = str(self.active_idol_key or "").strip().upper()
        return key or None

    def is_idol_active(self, key: str) -> bool:
        kk = str(key or "").strip().upper()
        if not kk:
            return False
        return kk == str(self.active_idol_key or "").strip().upper()

    def get_available_idols_of_khorne(self) -> list[IdolOfKhorneAbility]:
        if not self.is_cult_of_blood():
            return []
        used = {str(k or "").strip().upper() for k in (self.idols_used or set()) if str(k or "").strip()}
        return [ab for ab in IDOLS_OF_KHORNE_ABILITIES if ab.key not in used]

    def activate_idol_of_khorne(self, key: str, *, game=None, player=None) -> bool:
        if not self.is_cult_of_blood():
            return False
        kk = str(key or "").strip().upper()
        if not kk:
            return False
        if kk not in {ab.key for ab in IDOLS_OF_KHORNE_ABILITIES}:
            return False
        used = {str(k or "").strip().upper() for k in (self.idols_used or set()) if str(k or "").strip()}
        if kk in used:
            return False
        self.active_idol_key = kk
        self.idols_used.add(kk)
        return True

    def clear_active_idol_of_khorne(self) -> None:
        self.active_idol_key = None

    def is_blood_tithe_active(self, key: str) -> bool:
        kk = str(key or "").strip().upper()
        return kk in (self.blood_tithe_active or set())

    def get_available_blood_tithe_abilities(self) -> list[BloodTitheAbility]:
        points = int(self.blood_tithe_points or 0)
        active = set(str(k or "").strip().upper() for k in (self.blood_tithe_active or set()))
        return [ab for ab in BLOOD_TITHE_ABILITIES if ab.key not in active and ab.cost <= points]

    def add_blood_tithe_points(self, amount: int) -> int:
        try:
            amt = int(amount or 0)
        except Exception:
            amt = 0
        if amt <= 0:
            return int(self.blood_tithe_points or 0)
        self.blood_tithe_points = int(self.blood_tithe_points or 0) + int(amt)
        return int(self.blood_tithe_points or 0)

    def _choice_from_name(self, name: str) -> Optional[BloodTitheAbility]:
        key = str(name or "").strip().lower()
        if not key:
            return None
        for ab in BLOOD_TITHE_ABILITIES:
            if ab.name.strip().lower() == key:
                return ab
        return None

    def can_activate_blood_tithe(
        self,
        ability_key: str,
        *,
        game=None,
        player=None,
        timing: str = "command_phase",
        ignore_command_phase_limit: bool = False,
    ) -> bool:
        kk = str(ability_key or "").strip().upper()
        if not kk:
            return False
        if not self.is_khorne_daemonkin():
            return False
        if self.is_blood_tithe_active(kk):
            return False
        ability = next((a for a in BLOOD_TITHE_ABILITIES if a.key == kk), None)
        if ability is None:
            return False
        if int(self.blood_tithe_points or 0) < int(ability.cost):
            return False
        if not ignore_command_phase_limit and str(timing or "").strip().lower() in ("command", "command_phase"):
            if game is not None and player is not None:
                key = self._command_phase_key(game, player)
                if self._blood_tithe_command_phase_key == key:
                    return False
        return True

    def activate_blood_tithe(
        self,
        ability_key: str,
        *,
        game=None,
        player=None,
        timing: str = "command_phase",
        ignore_command_phase_limit: bool = False,
    ) -> bool:
        if not self.can_activate_blood_tithe(
            ability_key,
            game=game,
            player=player,
            timing=timing,
            ignore_command_phase_limit=ignore_command_phase_limit,
        ):
            return False
        kk = str(ability_key or "").strip().upper()
        ability = next((a for a in BLOOD_TITHE_ABILITIES if a.key == kk), None)
        if ability is None:
            return False
        try:
            self.blood_tithe_points = int(self.blood_tithe_points or 0) - int(ability.cost)
        except Exception:
            return False
        if self.blood_tithe_points < 0:
            self.blood_tithe_points = 0
        self.blood_tithe_active.add(kk)
        if not ignore_command_phase_limit and str(timing or "").strip().lower() in ("command", "command_phase"):
            if game is not None and player is not None:
                self._blood_tithe_command_phase_key = self._command_phase_key(game, player)
        try:
            es = getattr(game, "event_system", None) if game is not None else None
            if es is not None:
                es.publish(
                    "blood_tithe_activated",
                    player=player,
                    ability=ability,
                    total=int(self.blood_tithe_points or 0),
                )
                es.publish(
                    "blood_tithe_updated",
                    player=player,
                    total=int(self.blood_tithe_points or 0),
                    active=[a.name for a in self.get_active_blood_tithe_abilities()],
                )
        except Exception:
            pass
        return True

    def blood_tithe_enraged_abjuration_applies(self, unit) -> bool:
        if not self.is_blood_tithe_active("ENRAGED_ABJURATION"):
            return False
        if not self.is_khorne_daemonkin():
            return False
        return self.unit_is_blood_tithe_eligible(unit)

    def blood_tithe_daemonic_rage_applies(self, unit) -> bool:
        if not self.is_blood_tithe_active("DAEMONIC_RAGE"):
            return False
        if not self.is_khorne_daemonkin():
            return False
        return self.unit_is_blood_legions(unit)

    def blood_tithe_boon_of_blood_applies(self, unit) -> bool:
        if not self.is_blood_tithe_active("BOON_OF_BLOOD"):
            return False
        if not self.is_khorne_daemonkin():
            return False
        return self.unit_is_blood_legions(unit)

    def blood_tithe_might_of_khorne_applies(self, unit) -> bool:
        if not self.is_blood_tithe_active("MIGHT_OF_KHORNE"):
            return False
        if not self.is_khorne_daemonkin():
            return False
        return self.unit_is_blood_legions(unit)

    def prompt_blood_tithe_activation(
        self,
        *,
        game=None,
        player=None,
        timing: str = "command_phase",
        source: str = "",
        ignore_command_phase_limit: bool = False,
    ) -> bool:
        if game is None or player is None:
            return False
        options = list(self.get_available_blood_tithe_abilities() or [])
        if not options:
            return False
        if not ignore_command_phase_limit and str(timing or "").strip().lower() in ("command", "command_phase"):
            key = self._command_phase_key(game, player)
            if self._blood_tithe_command_phase_key == key:
                return False
        if not bool(getattr(game, "is_authoritative", True)):
            return False
        try:
            from ..engine.decision_kinds import DECISION_CHOOSE_BLOOD_TITHE
            from ..engine.decisions import DecisionOption, DecisionRequest
            from ..utility.entity_ids import get_entity_id
        except Exception:
            return False

        army_id = get_entity_id(self.army) if self.army is not None else None
        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_BLOOD_TITHE:
                    continue
                ctx = getattr(req, "context", {}) or {}
                if str(ctx.get("army_id", "")) == str(army_id) and str(ctx.get("timing", "")) == str(timing or ""):
                    return True

        req_options = [DecisionOption.create("Skip", payload={"action": "skip", "army_id": army_id})]
        for choice in options:
            key = getattr(choice, "key", None) or getattr(choice, "choice_key", None)
            if not key:
                continue
            label = getattr(choice, "name", None) or str(choice)
            payload = {
                "ability_key": str(key),
                "army_id": army_id,
                "timing": timing,
                "cost": getattr(choice, "cost", None),
                "summary": getattr(choice, "summary", ""),
            }
            req_options.append(DecisionOption.create(label, payload=payload))
        if not req_options:
            return False
        req = DecisionRequest.create(
            DECISION_CHOOSE_BLOOD_TITHE,
            "Select a Blood Tithe ability.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={
                "army_id": army_id,
                "timing": timing,
                "source": source,
                "points": int(self.blood_tithe_points or 0),
                "ignore_command_phase_limit": bool(ignore_command_phase_limit),
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(req)
            return True
        return False

    def prompt_idols_of_khorne_selection(
        self,
        *,
        game=None,
        player=None,
        timing: str = "command_phase",
        source: str = "",
    ) -> bool:
        if game is None or player is None:
            return False
        if not self.is_cult_of_blood():
            return False
        options = list(self.get_available_idols_of_khorne() or [])
        if not options:
            return False
        phase_key = self._command_phase_key(game, player)
        if self._idols_command_phase_key == phase_key:
            return False
        if not bool(getattr(game, "is_authoritative", True)):
            return False
        from ..engine.decision_kinds import DECISION_CHOOSE_IDOL_OF_KHORNE
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.entity_ids import get_entity_id

        army_id = get_entity_id(self.army) if self.army is not None else None
        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_IDOL_OF_KHORNE:
                    continue
                ctx = getattr(req, "context", {}) or {}
                if str(ctx.get("army_id", "")) == str(army_id) and str(ctx.get("timing", "")) == str(timing or ""):
                    return True

        req_options = [
            DecisionOption.create(
                "None",
                payload={"action": "skip", "skip": True, "army_id": army_id, "summary": "Do not select an Idol this Command phase."},
            )
        ]
        for choice in options:
            choice_key = getattr(choice, "key", None)
            if not choice_key:
                continue
            label = getattr(choice, "name", None) or str(choice)
            payload = {
                "ability_key": str(choice_key),
                "army_id": army_id,
                "timing": timing,
                "summary": getattr(choice, "summary", ""),
            }
            req_options.append(DecisionOption.create(label, payload=payload))
        if not req_options:
            return False
        req = DecisionRequest.create(
            DECISION_CHOOSE_IDOL_OF_KHORNE,
            "Select an Idol of Khorne ability.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={
                "army_id": army_id,
                "timing": timing,
                "source": source,
            },
        )
        self._idols_command_phase_key = phase_key
        if hasattr(game, "request_decision"):
            game.request_decision(req)
            return True
        return False

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        if game is None or player is None:
            return
        if player is not getattr(self.army, "player", None):
            return

        if self.is_cult_of_blood():
            self.clear_active_idol_of_khorne()
            self.apply_cult_of_blood_battleline_keywords()
            self.prompt_idols_of_khorne_selection(game=game, player=player, timing="command_phase", source="Command phase")

        if self.is_khorne_daemonkin():
            if int(self.blood_tithe_points or 0) <= 0:
                return
            self.prompt_blood_tithe_activation(game=game, player=player, timing="command_phase", source="Command phase")

    def validate_detachment_rules(self) -> list[str]:
        errors: list[str] = []
        army = self.army
        if army is None:
            return errors
        if self.is_cult_of_blood():
            self.apply_cult_of_blood_battleline_keywords()
        if not self.is_khorne_daemonkin():
            return errors

        points_limit = int(getattr(army, "points_limit", 0) or 0)
        if points_limit <= 1000:
            cap = 500
            size_label = "Incursion"
        elif points_limit <= 2000:
            cap = 1000
            size_label = "Strike Force"
        else:
            cap = 1500
            size_label = "Onslaught"

        blood_legions_units = [u for u in list(getattr(army, "units", []) or []) if self.unit_is_blood_legions(u)]
        blood_legions_points = 0
        for u in blood_legions_units:
            try:
                blood_legions_points += int(u.get_unit_cost() or 0)
            except Exception:
                continue
        if blood_legions_points > cap:
            errors.append(
                f"Khorne Daemonkin: total BLOOD LEGIONS points ({blood_legions_points}) exceed {size_label} cap of {cap}."
            )

        warlord = None
        try:
            warlord = getattr(army, "warlord", None)
        except Exception:
            warlord = None
        if warlord is None:
            try:
                for u in list(getattr(army, "units", []) or []):
                    if getattr(u, "is_warlord", False):
                        warlord = u
                        break
            except Exception:
                warlord = None

        if warlord is not None and self.unit_is_blood_legions(warlord):
            errors.append("Khorne Daemonkin: BLOOD LEGIONS models cannot be your WARLORD.")

        try:
            enh = getattr(warlord, "enhancement", None) if warlord is not None else None
            enh_id = str(getattr(enh, "id", "") or "").strip()
        except Exception:
            enh_id = ""
        if enh_id == "000010078004":
            errors.append("Khorne Daemonkin: Disciple of Khorne cannot be your WARLORD.")

        return errors
