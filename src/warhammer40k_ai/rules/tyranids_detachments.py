from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from .detachment_manager import DetachmentManagerBase
from ..utility.aura_utils import horizontal_distance_point_to_model_base_2d, unit_within_range_of_unit
from ..utility.dice import get_roll
from ..utility.entity_ids import get_entity_id


@dataclass(frozen=True)
class HyperAdaptation:
    key: str
    name: str
    summary: str
    target_keywords: tuple[str, ...]
    sustained_hits_value: int = 0
    lethal_hits: bool = False
    precision_on_crit: bool = False


SWARMING_INSTINCTS = HyperAdaptation(
    key="SWARMING_INSTINCTS",
    name="Swarming Instincts",
    summary="Attacks vs INFANTRY or SWARM gain Sustained Hits 1.",
    target_keywords=("INFANTRY", "SWARM"),
    sustained_hits_value=1,
)
HYPER_AGGRESSION = HyperAdaptation(
    key="HYPER_AGGRESSION",
    name="Hyper-aggression",
    summary="Attacks vs MONSTER or VEHICLE gain Lethal Hits.",
    target_keywords=("MONSTER", "VEHICLE"),
    lethal_hits=True,
)
HIVE_PREDATORS = HyperAdaptation(
    key="HIVE_PREDATORS",
    name="Hive Predators",
    summary="On critical hits vs CHARACTER units, attacks gain Precision.",
    target_keywords=("CHARACTER",),
    precision_on_crit=True,
)

HYPER_ADAPTATIONS: tuple[HyperAdaptation, ...] = (
    SWARMING_INSTINCTS,
    HYPER_AGGRESSION,
    HIVE_PREDATORS,
)
HYPER_ADAPTATION_BY_KEY = {h.key: h for h in HYPER_ADAPTATIONS}

_LEADER_BEASTS_TYRANID_WARRIOR_UNIT_NAMES = {
    "tyranid warriors with ranged bio weapons",
    "tyranid warriors with melee bio weapons",
}
_ENRAGED_BEHEMOTHS_SOURCE = "Enraged Behemoths"
_SURPRISE_ASSAULT_SOURCE = "Surprise Assault"
_SUBTERRANEAN_ASSAULT_TRYGON_SELECTION_ABILITY = "subterranean_assault_trygon_character_selection"
_SUBTERRANEAN_ASSAULT_TUNNEL_MARKER_PLACEMENT_ABILITY = "subterranean_assault_tunnel_marker_placement"
_TUNNEL_MARKER_HORIZONTAL_RANGE = 9.0
_TUNNEL_MARKER_ENEMY_DISTANCE = 6.0
_TUNNEL_MARKER_REMOVAL_DISTANCE = 3.0
_TUNNEL_MARKER_PLACE_WITHIN_UNIT_DISTANCE = 1.0


@dataclass
class TunnelMarker:
    marker_id: str
    x: float
    y: float
    z: float = 0.0
    active: bool = True

    @property
    def id(self) -> str:
        return self.marker_id


class TyranidsDetachmentManager(DetachmentManagerBase):
    faction_id = "TYR"

    def __init__(self, army=None):
        super().__init__(army)
        self.active_hyper_adaptation_key: Optional[str] = None
        self.hyper_adaptation_selected_round: Optional[int] = None
        self.tunnel_markers: list[TunnelMarker] = []
        self._subterranean_assault_trygon_selection_resolved: bool = False

    def is_invasion_fleet(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Invasion Fleet")

    def is_assimilation_swarm(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Assimilation Swarm")

    def is_crusher_stampede(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Crusher Stampede")

    def is_subterranean_assault(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Subterranean Assault")

    def is_synaptic_nexus(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Synaptic Nexus")

    def is_unending_swarm(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Unending Swarm")

    def is_vanguard_onslaught(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Vanguard Onslaught")

    def is_warrior_bioform_onslaught(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Warrior Bioform Onslaught")

    def _unit_in_army(self, unit) -> bool:
        if unit is None:
            return False
        army = self.army
        if army is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        if callable(get_parent_army):
            try:
                return get_parent_army() is army
            except Exception:
                return False
        return unit in list(getattr(army, "units", []) or [])

    def _leader_beasts_unit_name_norm(self, unit) -> str:
        root = self._unit_root(unit)
        if root is None:
            return ""
        return self._norm(str(getattr(root, "name", "") or ""))

    def _leader_beasts_unit_is_tyranid_warrior_datasheet(self, unit) -> bool:
        return self._leader_beasts_unit_name_norm(unit) in _LEADER_BEASTS_TYRANID_WARRIOR_UNIT_NAMES

    def _leader_beasts_unit_is_winged_tyranid_prime_datasheet(self, unit) -> bool:
        return self._leader_beasts_unit_name_norm(unit) == "winged tyranid prime"

    @staticmethod
    def _add_keyword_once(entity, keyword: str) -> None:
        if entity is None:
            return
        key = str(keyword or "").strip()
        if not key:
            return
        keywords = list(getattr(entity, "keywords", []) or [])
        if any(str(v or "").strip().lower() == key.lower() for v in keywords):
            return
        keywords.append(key)
        entity.keywords = keywords

    @staticmethod
    def _set_model_objective_control(model, value: int) -> None:
        if model is None:
            return
        oc = int(max(0, value))
        if hasattr(model, "_base_objective_control"):
            model._base_objective_control = int(oc)
        if hasattr(model, "_objective_control"):
            model._objective_control = int(oc)
        if hasattr(model, "_objective_control_raw"):
            model._objective_control_raw = str(int(oc))

    def _unit_datasheet_name_norm(self, unit) -> str:
        root = self._unit_root(unit)
        if root is None:
            return ""
        return self._norm(str(getattr(root, "name", "") or ""))

    def _unit_is_trygon_datasheet(self, unit) -> bool:
        name_norm = self._unit_datasheet_name_norm(unit)
        return bool(name_norm) and "trygon" in name_norm

    def _unit_is_mawloc_or_trygon_datasheet(self, unit) -> bool:
        name_norm = self._unit_datasheet_name_norm(unit)
        if not name_norm:
            return False
        return "mawloc" in name_norm or "trygon" in name_norm

    def _unit_is_burrower(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if self._unit_has_keyword(root, "BURROWER"):
            return True
        for model in list(getattr(root, "models", []) or []):
            if self._model_keyword(model, "BURROWER"):
                return True
        return False

    def apply_subterranean_assault_burrower_keywords(self, unit=None) -> None:
        """
        Subterranean Assault - Surprise Assault:
        Mawloc and Trygon units gain BURROWER.
        """
        if not self.is_subterranean_assault() or self.army is None:
            return
        if unit is None:
            units = list(getattr(self.army, "units", []) or [])
        else:
            units = [unit]
        seen: set[str] = set()
        for entry in units:
            root = self._unit_root(entry)
            if root is None:
                continue
            root_id = str(get_entity_id(root) or "").strip()
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            if not self._unit_in_army(root):
                continue
            if not self._unit_is_mawloc_or_trygon_datasheet(root):
                continue
            self._add_keyword_once(root, "Burrower")
            for model in list(getattr(root, "models", []) or []):
                self._add_keyword_once(model, "Burrower")

    def surprise_assault_reroll_hit_ones(self, model, *, unit=None, game=None) -> tuple[bool, str]:
        if not self.is_subterranean_assault():
            return False, ""
        if model is None:
            return False, ""
        source_unit = unit if unit is not None else getattr(model, "parent_unit", None)
        root = self._unit_root(source_unit)
        if root is None:
            return False, ""
        if not self._unit_in_army(root):
            return False, ""
        if not self._unit_is_tyranids(root) and not self._model_keyword(model, "TYRANIDS"):
            return False, ""
        return True, _SURPRISE_ASSAULT_SOURCE

    def apply_warrior_bioform_leader_beasts(self, unit=None) -> None:
        """
        Warrior Bioform Onslaught - Leader-beasts:
        - Tyranid Warriors with Ranged/Melee Bio-weapons gain TYRANID WARRIORS and BATTLELINE.
        - TYRANID WARRIORS models in those units have Objective Control 3.
        """
        if not self.is_warrior_bioform_onslaught() or self.army is None:
            return
        if unit is None:
            units = list(getattr(self.army, "units", []) or [])
        else:
            units = [unit]
        seen: set[str] = set()
        for entry in units:
            root = self._unit_root(entry)
            if root is None:
                continue
            root_id = str(get_entity_id(root) or "")
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            if not self._unit_in_army(root):
                continue
            if not self._leader_beasts_unit_is_tyranid_warrior_datasheet(root):
                continue
            self._add_keyword_once(root, "Tyranid Warriors")
            self._add_keyword_once(root, "Battleline")
            for model in list(getattr(root, "models", []) or []):
                self._add_keyword_once(model, "Tyranid Warriors")
                if self._model_keyword(model, "TYRANID WARRIORS"):
                    self._set_model_objective_control(model, 3)

    def leader_beasts_invulnerable_save(self, model, *, unit=None) -> tuple[int, str]:
        """
        Return (value, source) for Warrior Bioform Onslaught Leader-beasts invulnerable save.
        """
        if not self.is_warrior_bioform_onslaught():
            return 0, ""
        if model is None:
            return 0, ""
        source_unit = unit if unit is not None else getattr(model, "parent_unit", None)
        root = self._unit_root(source_unit)
        if root is None:
            return 0, ""
        if not self._unit_in_army(root):
            return 0, ""
        if self._leader_beasts_unit_is_tyranid_warrior_datasheet(root):
            return 5, "Leader-beasts"
        if self._leader_beasts_unit_is_winged_tyranid_prime_datasheet(root):
            return 5, "Leader-beasts"
        if self._attached_unit_has_keyword(root, "TYRANID WARRIORS"):
            return 5, "Leader-beasts"
        if self._attached_unit_has_keyword(root, "WINGED TYRANID PRIME"):
            return 5, "Leader-beasts"
        return 0, ""

    def _unit_root(self, unit):
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
            if root is not None:
                return root
        return unit

    def _iter_army_roots(self) -> list:
        roots: dict[str, Any] = {}
        no_id_roots: list[Any] = []
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._unit_root(unit)
            if root is None:
                continue
            root_id = str(get_entity_id(root) or "").strip()
            if root_id:
                if root_id not in roots:
                    roots[root_id] = root
                continue
            no_id_roots.append(root)
        out = list(roots.values()) + list(no_id_roots)
        out.sort(key=lambda item: (str(get_entity_id(item) or ""), str(getattr(item, "name", "") or "")))
        return out

    def _unit_on_battlefield(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        is_alive = getattr(root, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        if not bool(getattr(root, "deployed", True)):
            return False
        if str(getattr(root, "reserve_status", "deployed") or "deployed") != "deployed":
            return False
        if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
            return False
        in_reserves = getattr(root, "is_in_reserves", None)
        if callable(in_reserves) and bool(in_reserves()):
            return False
        return True

    def _unit_is_tyranids_monster(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_has_keyword_or_faction(root, "TYRANIDS", faction_id=self.faction_id):
            return False
        return self._unit_has_keyword(root, "MONSTER")

    def _attached_unit_has_keyword(self, unit, keyword: str) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        for member in members:
            if self._unit_has_keyword(member, keyword):
                return True
        return False

    @staticmethod
    def _model_is_alive(model) -> bool:
        if model is None:
            return False
        alive = getattr(model, "is_alive", True)
        return bool(alive() if callable(alive) else alive)

    @staticmethod
    def _model_keyword(model, keyword: str) -> bool:
        if model is None:
            return False
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any) and bool(has_any(keyword)):
            return True
        has_kw = getattr(model, "has_keyword", None)
        if callable(has_kw) and bool(has_kw(keyword)):
            return True
        kw = str(keyword or "").strip().lower()
        if not kw:
            return False
        raw = [str(k or "").strip().lower() for k in list(getattr(model, "keywords", []) or [])]
        return kw in raw

    @staticmethod
    def _model_is_character(model) -> bool:
        if model is None:
            return False
        if bool(getattr(model, "is_character", False)):
            return True
        if TyranidsDetachmentManager._model_keyword(model, "CHARACTER"):
            return True
        parent = getattr(model, "parent_unit", None)
        has_any = getattr(parent, "has_any_keyword", None) if parent is not None else None
        if callable(has_any) and bool(has_any("CHARACTER")):
            return True
        return False

    @staticmethod
    def _model_is_infantry(model) -> bool:
        if model is None:
            return False
        if TyranidsDetachmentManager._model_keyword(model, "INFANTRY"):
            return True
        parent = getattr(model, "parent_unit", None)
        has_any = getattr(parent, "has_any_keyword", None) if parent is not None else None
        if callable(has_any) and bool(has_any("INFANTRY")):
            return True
        return False

    @staticmethod
    def _model_is_monster(model) -> bool:
        if model is None:
            return False
        if TyranidsDetachmentManager._model_keyword(model, "MONSTER"):
            return True
        parent = getattr(model, "parent_unit", None)
        has_any = getattr(parent, "has_any_keyword", None) if parent is not None else None
        if callable(has_any) and bool(has_any("MONSTER")):
            return True
        return False

    def _enraged_behemoths_model_context(self, model, unit=None) -> tuple[bool, Any]:
        if not self.is_crusher_stampede():
            return False, None
        if model is None:
            return False, None
        source_unit = unit if unit is not None else getattr(model, "parent_unit", None)
        root = self._unit_root(source_unit)
        if root is None:
            return False, None
        if not self._unit_in_army(root):
            return False, None
        if not self._unit_is_tyranids_monster(root):
            return False, None
        if not self._model_is_monster(model):
            return False, None
        return True, root

    def enraged_behemoths_hit_bonus(self, model, unit=None) -> tuple[int, str]:
        applies, root = self._enraged_behemoths_model_context(model, unit=unit)
        if not applies or root is None:
            return 0, ""
        below_start = getattr(root, "is_below_starting_strength", None)
        if not callable(below_start) or not bool(below_start()):
            return 0, ""
        return 1, f"{_ENRAGED_BEHEMOTHS_SOURCE} (+1 to hit below Starting Strength)"

    def enraged_behemoths_wound_bonus(self, model, unit=None) -> tuple[int, str]:
        applies, root = self._enraged_behemoths_model_context(model, unit=unit)
        if not applies or root is None:
            return 0, ""
        below_half = getattr(root, "is_below_half_strength", None)
        if not callable(below_half) or not bool(below_half()):
            return 0, ""
        return 1, f"{_ENRAGED_BEHEMOTHS_SOURCE} (+1 to wound below Half-strength)"

    def enraged_behemoths_objective_control_bonus(self, model, *, unit=None) -> tuple[int, str]:
        if not self.is_crusher_stampede():
            return 0, ""
        if model is None:
            return 0, ""
        source_unit = unit if unit is not None else getattr(model, "parent_unit", None)
        root = self._unit_root(source_unit)
        if root is None:
            return 0, ""
        if not self._unit_in_army(root):
            return 0, ""
        if not self._unit_is_tyranids_monster(root):
            return 0, ""
        is_bs = getattr(root, "is_battle_shocked", None)
        if callable(is_bs) and bool(is_bs()):
            return 0, ""
        below_start = getattr(root, "is_below_starting_strength", None)
        if callable(below_start) and bool(below_start()):
            return 0, ""
        return 2, f"{_ENRAGED_BEHEMOTHS_SOURCE} (+2 OC at Starting Strength)"

    @staticmethod
    def _wounds_snapshot(model) -> tuple[int, int]:
        current = int(getattr(model, "wounds", getattr(model, "_wounds", 0)) or 0)
        base = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", current)) or current)
        return max(0, current), max(1, base)

    @staticmethod
    def _feed_the_swarm_phase_stamp(*, game=None, player=None) -> tuple[int, str]:
        turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        owner = player
        if owner is None and game is not None:
            get_current = getattr(game, "get_current_player", None)
            owner = get_current() if callable(get_current) else None
        owner_id = str(getattr(owner, "id", "") or "")
        return int(turn), owner_id

    def _feed_the_swarm_source_used_this_phase(self, source_unit, *, game=None, player=None) -> bool:
        root = self._unit_root(source_unit)
        if root is None:
            return True
        turn, owner_id = self._feed_the_swarm_phase_stamp(game=game, player=player)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        used_turn = int(sr.get("feed_the_swarm_used_turn", 0) or 0)
        used_owner_id = str(sr.get("feed_the_swarm_used_turn_owner", "") or "")
        return bool(used_turn == turn and used_owner_id == owner_id)

    def _feed_the_swarm_mark_source_used(self, source_unit, *, game=None, player=None) -> None:
        root = self._unit_root(source_unit)
        if root is None:
            return
        turn, owner_id = self._feed_the_swarm_phase_stamp(game=game, player=player)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["feed_the_swarm_used_turn"] = int(turn)
        sr["feed_the_swarm_used_turn_owner"] = str(owner_id)
        root.special_rules = sr

    def _feed_the_swarm_target_regens_this_phase(self, target_unit, *, game=None, player=None) -> int:
        root = self._unit_root(target_unit)
        if root is None:
            return 0
        turn, owner_id = self._feed_the_swarm_phase_stamp(game=game, player=player)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return 0
        tracked_turn = int(sr.get("feed_the_swarm_regen_turn", 0) or 0)
        tracked_owner = str(sr.get("feed_the_swarm_regen_turn_owner", "") or "")
        if tracked_turn != turn or tracked_owner != owner_id:
            return 0
        return max(0, int(sr.get("feed_the_swarm_regen_count", 0) or 0))

    def _feed_the_swarm_target_regen_limit(self, target_unit) -> int:
        root = self._unit_root(target_unit)
        if root is None:
            return 1
        checker = getattr(root, "_attached_unit_has_active_enhancement", None)
        if callable(checker):
            if bool(
                checker(
                    "enhancement_regenerating_monstrosity",
                    enhancement_id="000008412002",
                    enhancement_name="Regenerating Monstrosity",
                )
            ):
                return 2
        return 1

    def _feed_the_swarm_increment_target_regens(self, target_unit, *, game=None, player=None) -> None:
        root = self._unit_root(target_unit)
        if root is None:
            return
        turn, owner_id = self._feed_the_swarm_phase_stamp(game=game, player=player)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        tracked_turn = int(sr.get("feed_the_swarm_regen_turn", 0) or 0)
        tracked_owner = str(sr.get("feed_the_swarm_regen_turn_owner", "") or "")
        if tracked_turn != turn or tracked_owner != owner_id:
            current = 0
        else:
            current = max(0, int(sr.get("feed_the_swarm_regen_count", 0) or 0))
        sr["feed_the_swarm_regen_turn"] = int(turn)
        sr["feed_the_swarm_regen_turn_owner"] = str(owner_id)
        sr["feed_the_swarm_regen_count"] = int(current + 1)
        root.special_rules = sr

    def _feed_the_swarm_range_for_source(self, source_unit, *, game_map=None) -> float:
        source_root = self._unit_root(source_unit)
        if source_root is None:
            return 6.0
        best = 6.0
        for candidate in self._iter_army_roots():
            candidate_root = self._unit_root(candidate)
            if candidate_root is None:
                continue
            if not self._unit_on_battlefield(candidate_root):
                continue
            checker = getattr(candidate_root, "_attached_unit_has_active_enhancement", None)
            if not callable(checker):
                continue
            if not bool(
                checker(
                    "enhancement_biophagic_flow",
                    enhancement_id="000008412004",
                    enhancement_name="Biophagic Flow (Aura)",
                )
            ):
                continue
            if unit_within_range_of_unit(candidate_root, source_root, 12.0, use_attached_aggregate=True):
                best = max(best, 9.0)
        return float(best)

    def _feed_the_swarm_wounded_models(self, target_unit) -> list:
        root = self._unit_root(target_unit)
        if root is None:
            return []
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        wounded = []
        for model in models:
            if not self._model_is_alive(model):
                continue
            current, base = self._wounds_snapshot(model)
            if current >= base:
                continue
            wounded.append(model)
        wounded.sort(key=lambda item: (str(get_entity_id(item) or ""), str(getattr(item, "name", "") or "")))
        return wounded

    def _feed_the_swarm_returnable_models(self, target_unit) -> list:
        root = self._unit_root(target_unit)
        if root is None:
            return []
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        can_return = getattr(root, "_horrors_can_return_model", None)
        out = []
        for member in members:
            for model in list(getattr(member, "models_lost", []) or []):
                if model is None:
                    continue
                if callable(can_return) and not bool(can_return(model)):
                    continue
                if self._model_is_character(model):
                    continue
                if not self._model_is_infantry(model):
                    continue
                out.append(model)
        out.sort(key=lambda item: (str(get_entity_id(item) or ""), str(getattr(item, "name", "") or "")))
        return out

    def _feed_the_swarm_max_return_count(self, target_unit) -> int:
        root = self._unit_root(target_unit)
        if root is None:
            return 1
        if self._attached_unit_has_keyword(root, "ENDLESS MULTITUDE"):
            return 3
        return 1

    def _feed_the_swarm_option_key_from_payload(self, payload: dict) -> str:
        action = str(payload.get("action", "") or "").strip().lower()
        target_id = str(payload.get("target_unit_id", payload.get("unit_id", "")) or "").strip()
        if action == "heal":
            model_id = str(payload.get("target_model_id", payload.get("model_id", "")) or "").strip()
            if not target_id or not model_id:
                return ""
            return f"heal:{target_id}:{model_id}"
        if action == "return":
            try:
                amount = int(payload.get("return_count", payload.get("returns", 0)) or 0)
            except (TypeError, ValueError):
                amount = 0
            if not target_id or amount <= 0:
                return ""
            return f"return:{target_id}:{int(amount)}"
        return ""

    def _feed_the_swarm_target_eligible(
        self,
        source_unit,
        target_unit,
        *,
        range_value: float,
        game=None,
        player=None,
    ) -> bool:
        source_root = self._unit_root(source_unit)
        target_root = self._unit_root(target_unit)
        if source_root is None or target_root is None:
            return False
        if not self._unit_on_battlefield(target_root):
            return False
        if not self._unit_is_tyranids(target_root):
            return False
        if not unit_within_range_of_unit(
            source_root,
            target_root,
            float(range_value),
            use_attached_aggregate=True,
        ):
            return False
        if self._feed_the_swarm_target_regens_this_phase(target_root, game=game, player=player) >= self._feed_the_swarm_target_regen_limit(target_root):
            return False
        return True

    def feed_the_swarm_source_can_act(self, source_unit, *, game=None, player=None) -> bool:
        if not self.is_assimilation_swarm():
            return False
        source_root = self._unit_root(source_unit)
        if source_root is None:
            return False
        if not self._unit_on_battlefield(source_root):
            return False
        if not self._attached_unit_has_keyword(source_root, "HARVESTER"):
            return False
        if self._feed_the_swarm_source_used_this_phase(source_root, game=game, player=player):
            return False
        return True

    def feed_the_swarm_options_for_source(self, source_unit, *, game=None, player=None) -> list[dict]:
        source_root = self._unit_root(source_unit)
        if not self.feed_the_swarm_source_can_act(source_root, game=game, player=player):
            return []
        options: list[dict] = []
        range_value = self._feed_the_swarm_range_for_source(source_root)
        source_id = str(get_entity_id(source_root) or "").strip()
        for target_root in self._iter_army_roots():
            target_id = str(get_entity_id(target_root) or "").strip()
            if not target_id:
                continue
            if not self._feed_the_swarm_target_eligible(
                source_root,
                target_root,
                range_value=range_value,
                game=game,
                player=player,
            ):
                continue

            for model in self._feed_the_swarm_wounded_models(target_root):
                model_id = str(get_entity_id(model) or "").strip()
                if not model_id:
                    continue
                option_key = f"heal:{target_id}:{model_id}"
                options.append(
                    {
                        "option_key": option_key,
                        "action": "heal",
                        "source_unit": source_root,
                        "target_unit": target_root,
                        "target_model": model,
                        "return_models": [],
                        "return_count": 0,
                        "range": float(range_value),
                        "label": (
                            f"{getattr(target_root, 'name', 'Unit')}: "
                            f"heal {getattr(model, 'name', 'Model')}"
                        ),
                        "payload": {
                            "action": "heal",
                            "source_unit_id": source_id,
                            "target_unit_id": target_id,
                            "target_model_id": model_id,
                            "option_key": option_key,
                        },
                    }
                )

            returnable = self._feed_the_swarm_returnable_models(target_root)
            if returnable:
                return_count = min(len(returnable), self._feed_the_swarm_max_return_count(target_root))
                if return_count > 0:
                    selected = list(returnable[:return_count])
                    option_key = f"return:{target_id}:{int(return_count)}"
                    options.append(
                        {
                            "option_key": option_key,
                            "action": "return",
                            "source_unit": source_root,
                            "target_unit": target_root,
                            "target_model": None,
                            "return_models": selected,
                            "return_count": int(return_count),
                            "range": float(range_value),
                            "label": (
                                f"{getattr(target_root, 'name', 'Unit')}: "
                                f"return {int(return_count)} model(s)"
                            ),
                            "payload": {
                                "action": "return",
                                "source_unit_id": source_id,
                                "target_unit_id": target_id,
                                "return_count": int(return_count),
                                "option_key": option_key,
                            },
                        }
                    )
        options.sort(key=lambda item: str(item.get("option_key", "") or ""))
        return options

    def feed_the_swarm_payload_is_valid(self, source_unit, payload: dict, *, game=None, player=None) -> tuple[bool, str]:
        if not isinstance(payload, dict):
            return False, "Feed the Swarm payload is missing."
        source_root = self._unit_root(source_unit)
        if source_root is None:
            return False, "Feed the Swarm source unit was not found."
        option_key = str(payload.get("option_key", "") or "").strip()
        if not option_key:
            option_key = self._feed_the_swarm_option_key_from_payload(payload)
        if not option_key:
            return False, "Feed the Swarm choice is missing an option key."
        valid_keys = {
            str(option.get("option_key", "") or "")
            for option in self.feed_the_swarm_options_for_source(source_root, game=game, player=player)
        }
        if option_key not in valid_keys:
            return False, "Feed the Swarm choice is not currently eligible."
        return True, ""

    def apply_feed_the_swarm_payload(self, source_unit, payload: dict, *, game=None, player=None) -> Optional[dict]:
        if not isinstance(payload, dict):
            return None
        source_root = self._unit_root(source_unit)
        if source_root is None:
            return None
        option_key = str(payload.get("option_key", "") or "").strip()
        if not option_key:
            option_key = self._feed_the_swarm_option_key_from_payload(payload)
        if not option_key:
            return None
        selected_option = None
        for option in self.feed_the_swarm_options_for_source(source_root, game=game, player=player):
            if str(option.get("option_key", "") or "") == option_key:
                selected_option = option
                break
        if selected_option is None:
            return None

        target_root = self._unit_root(selected_option.get("target_unit"))
        if target_root is None:
            return None
        source_id = str(get_entity_id(source_root) or "")
        target_id = str(get_entity_id(target_root) or "")
        action = str(selected_option.get("action", "") or "").strip().lower()

        if action == "heal":
            model = selected_option.get("target_model")
            if model is None or not self._model_is_alive(model):
                return None
            before, _base = self._wounds_snapshot(model)
            heal_roll = max(0, int(get_roll("D3") or 0)) + 1
            heal_fn = getattr(model, "heal", None)
            if callable(heal_fn):
                heal_fn(int(heal_roll))
            else:
                new_wounds = before + int(heal_roll)
                setattr(model, "wounds", int(new_wounds))
            check_profile = getattr(model, "_check_damaged_profile", None)
            if callable(check_profile):
                check_profile()
            after, _ = self._wounds_snapshot(model)
            healed = max(0, int(after - before))
            self._feed_the_swarm_mark_source_used(source_root, game=game, player=player)
            self._feed_the_swarm_increment_target_regens(target_root, game=game, player=player)
            return {
                "action": "heal",
                "source_unit_id": source_id,
                "source_unit_name": str(getattr(source_root, "name", "") or "Unit"),
                "target_unit_id": target_id,
                "target_unit_name": str(getattr(target_root, "name", "") or "Unit"),
                "target_model_id": str(get_entity_id(model) or ""),
                "target_model_name": str(getattr(model, "name", "") or "Model"),
                "heal_roll": int(heal_roll),
                "healed_wounds": int(healed),
            }

        if action == "return":
            return_models = [m for m in list(selected_option.get("return_models", []) or []) if m is not None]
            if not return_models:
                return None
            requested = int(selected_option.get("return_count", 0) or 0)
            if requested <= 0:
                return None
            game_map = getattr(game, "map", None) if game is not None else None
            return_fn = getattr(target_root, "return_destroyed_bodyguard_models", None)
            if not callable(return_fn):
                return None
            returned = int(
                return_fn(
                    int(requested),
                    game_map=game_map,
                    chosen_models=list(return_models[:requested]),
                    placement_source="feed_the_swarm",
                )
                or 0
            )
            if returned <= 0:
                return None
            self._feed_the_swarm_mark_source_used(source_root, game=game, player=player)
            self._feed_the_swarm_increment_target_regens(target_root, game=game, player=player)
            return {
                "action": "return",
                "source_unit_id": source_id,
                "source_unit_name": str(getattr(source_root, "name", "") or "Unit"),
                "target_unit_id": target_id,
                "target_unit_name": str(getattr(target_root, "name", "") or "Unit"),
                "return_count_requested": int(requested),
                "return_count": int(returned),
            }
        return None

    def queue_feed_the_swarm_requests(self, *, game=None, player=None) -> None:
        if game is None:
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        if not self.is_assimilation_swarm():
            return
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return
        army = self.army
        army_id = str(get_entity_id(army) or "") if army is not None else ""
        turn, owner_id = self._feed_the_swarm_phase_stamp(game=game, player=owner)
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        pending_source_ids: set[str] = set()
        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "feed_the_swarm":
                    continue
                if str(ctx.get("turn_owner_id", "") or "") != owner_id:
                    continue
                if int(ctx.get("turn", 0) or 0) != int(turn):
                    continue
                sid = str(ctx.get("source_unit_id", "") or "")
                if sid:
                    pending_source_ids.add(sid)

        for source_root in self._iter_army_roots():
            source_id = str(get_entity_id(source_root) or "").strip()
            if not source_id or source_id in pending_source_ids:
                continue
            options = self.feed_the_swarm_options_for_source(source_root, game=game, player=owner)
            if not options:
                continue
            req_options = [DecisionOption.create("None", payload={"action": "skip", "army_id": army_id, "source_unit_id": source_id})]
            option_keys = []
            for entry in options:
                option_key = str(entry.get("option_key", "") or "")
                if not option_key:
                    continue
                option_keys.append(option_key)
                payload = dict(entry.get("payload", {}) or {})
                payload["army_id"] = army_id
                payload["source_unit_id"] = source_id
                req_options.append(DecisionOption.create(str(entry.get("label", "") or "Regenerate"), payload=payload))
            if len(req_options) <= 1:
                continue
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"Feed the Swarm: select regeneration for {getattr(source_root, 'name', 'unit')}.",
                player_id=getattr(owner, "id", None),
                options=req_options,
                context={
                    "army_id": army_id,
                    "ability": "feed_the_swarm",
                    "ability_name": "Feed the Swarm",
                    "phase": "Command phase",
                    "source_unit_id": source_id,
                    "source_unit_name": str(getattr(source_root, "name", "") or "Unit"),
                    "turn_owner_id": owner_id,
                    "turn": int(turn),
                    "option_keys": list(option_keys),
                },
            )
            if hasattr(game, "request_decision"):
                game.request_decision(request)

    def get_active_tunnel_markers(self) -> list[TunnelMarker]:
        markers = [marker for marker in list(self.tunnel_markers or []) if bool(getattr(marker, "active", False))]
        return sorted(markers, key=lambda marker: str(getattr(marker, "marker_id", "") or ""))

    def _subterranean_assault_trygon_candidates(self) -> list:
        if not self.is_subterranean_assault():
            return []
        candidates = []
        seen: set[str] = set()
        for root in self._iter_army_roots():
            if root is None:
                continue
            root_id = str(get_entity_id(root) or "").strip()
            if not root_id or root_id in seen:
                continue
            if not self._unit_in_army(root):
                continue
            if not self._unit_is_tyranids(root):
                continue
            if not self._unit_is_trygon_datasheet(root):
                continue
            candidates.append(root)
            seen.add(root_id)
        candidates.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return candidates

    def _pending_subterranean_assault_trygon_request(self, game, *, army_id: str) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        from ..engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS

        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_SELECT_REALM_OF_CHAOS_UNITS:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != _SUBTERRANEAN_ASSAULT_TRYGON_SELECTION_ABILITY:
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id or ""):
                continue
            return True
        return False

    def queue_subterranean_assault_trygon_character_selection_request(self, *, game=None, player=None) -> None:
        if not self.is_subterranean_assault():
            return
        if self.army is None:
            return
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        if self._subterranean_assault_trygon_selection_resolved:
            return

        from ..engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
        from ..engine.decisions import DecisionOption, DecisionRequest

        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return
        candidates = list(self._subterranean_assault_trygon_candidates() or [])
        if not candidates:
            self._subterranean_assault_trygon_selection_resolved = True
            return
        army_id = str(get_entity_id(self.army) or "")
        if self._pending_subterranean_assault_trygon_request(game, army_id=army_id):
            return

        candidate_ids = [str(get_entity_id(unit) or "") for unit in candidates if str(get_entity_id(unit) or "")]
        if not candidate_ids:
            self._subterranean_assault_trygon_selection_resolved = True
            return
        request = DecisionRequest.create(
            DECISION_SELECT_REALM_OF_CHAOS_UNITS,
            "Surprise Assault: select up to two TRYGON models to gain CHARACTER.",
            player_id=getattr(owner, "id", None),
            options=[
                DecisionOption.create("Confirm", payload={"action": "confirm"}),
                DecisionOption.create("None", payload={"action": "skip"}),
            ],
            context={
                "army_id": army_id,
                "ability": _SUBTERRANEAN_ASSAULT_TRYGON_SELECTION_ABILITY,
                "ability_name": "Surprise Assault",
                "phase": "Muster Armies step",
                "max_units": 2,
                "allowed_unit_ids": list(candidate_ids),
                "title": "Surprise Assault",
                "subtitle": "Select up to two TRYGON units.",
                "instruction": "Selected TRYGON units gain the CHARACTER keyword.",
                "skip_label": "None (do not select TRYGON units)",
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)

    def subterranean_assault_trygon_selection_is_valid(self, unit_ids, *, game=None) -> tuple[bool, str]:
        if not self.is_subterranean_assault():
            return False, "Surprise Assault is not active for this army."
        if unit_ids is None:
            return True, ""
        if not isinstance(unit_ids, list):
            return False, "Surprise Assault selection requires unit_ids."
        unique_ids = sorted({str(uid or "").strip() for uid in list(unit_ids or []) if str(uid or "").strip()})
        if len(unique_ids) > 2:
            return False, "Surprise Assault can select at most two TRYGON units."
        candidates = {
            str(get_entity_id(unit) or ""): unit
            for unit in list(self._subterranean_assault_trygon_candidates() or [])
            if str(get_entity_id(unit) or "")
        }
        for uid in unique_ids:
            if uid not in candidates:
                return False, "Surprise Assault selection contains an ineligible unit."
        return True, ""

    def apply_subterranean_assault_trygon_character_selection(self, unit_ids, *, game=None) -> list[str]:
        selected = list(unit_ids or [])
        valid, _reason = self.subterranean_assault_trygon_selection_is_valid(selected, game=game)
        if not valid:
            return []
        candidate_by_id = {
            str(get_entity_id(unit) or ""): unit
            for unit in list(self._subterranean_assault_trygon_candidates() or [])
            if str(get_entity_id(unit) or "")
        }
        applied_ids: list[str] = []
        for unit_id in sorted({str(uid or "").strip() for uid in selected if str(uid or "").strip()}):
            root = candidate_by_id.get(unit_id)
            if root is None:
                continue
            self._add_keyword_once(root, "Character")
            for model in list(getattr(root, "models", []) or []):
                self._add_keyword_once(model, "Character")
            applied_ids.append(unit_id)
        self._subterranean_assault_trygon_selection_resolved = True
        return list(applied_ids)

    def _pending_subterranean_assault_tunnel_marker_request(self, game, *, unit_id: str) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        from ..engine.decision_kinds import DECISION_PICK_POINT

        target_id = str(unit_id or "")
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_PICK_POINT:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != _SUBTERRANEAN_ASSAULT_TUNNEL_MARKER_PLACEMENT_ABILITY:
                continue
            if str(ctx.get("unit_id", "") or "") != target_id:
                continue
            return True
        return False

    def _marker_within_burrower_unit_distance(self, unit, *, x: float, y: float) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if not self._model_is_alive(model):
                continue
            if float(horizontal_distance_point_to_model_base_2d(model, x, y)) <= _TUNNEL_MARKER_PLACE_WITHIN_UNIT_DISTANCE + 1e-6:
                return True
        return False

    def _iter_enemy_models_on_battlefield(self, game, *, owner_player=None) -> list:
        if game is None:
            return []
        owner = owner_player if owner_player is not None else getattr(self.army, "player", None)
        if owner is None:
            return []
        try:
            enemy_units = list(getattr(game, "get_enemy_units", lambda _p: [])(owner) or [])
        except Exception:
            enemy_units = []
        enemy_models = []
        for enemy in list(enemy_units or []):
            root = self._unit_root(enemy)
            if root is None:
                continue
            if not self._unit_on_battlefield(root):
                continue
            for model in list(getattr(root, "models", []) or []):
                if not self._model_is_alive(model):
                    continue
                enemy_models.append(model)
        enemy_models.sort(key=lambda model: str(get_entity_id(model) or ""))
        return enemy_models

    def _tunnel_marker_position_valid(self, game, unit, *, x: float, y: float) -> tuple[bool, str]:
        if game is None:
            return False, "Game context is required for Tunnel Marker placement."
        try:
            width = float(getattr(getattr(game, "battlefield", None), "width", 0.0) or 0.0)
            height = float(getattr(getattr(game, "battlefield", None), "height", 0.0) or 0.0)
        except Exception:
            return False, "Battlefield dimensions are unavailable."
        if x < 0.0 or y < 0.0 or x > width or y > height:
            return False, "Tunnel Marker must be within battlefield bounds."
        if not self._marker_within_burrower_unit_distance(unit, x=x, y=y):
            return False, "Tunnel Marker must be within 1\" of the arriving Burrower unit."
        for enemy_model in self._iter_enemy_models_on_battlefield(game):
            if float(horizontal_distance_point_to_model_base_2d(enemy_model, x, y)) <= _TUNNEL_MARKER_REMOVAL_DISTANCE + 1e-6:
                return False, "Tunnel Marker must be more than 3\" from enemy units."
        return True, ""

    def validate_subterranean_assault_tunnel_marker_point(self, *, unit, point, game=None) -> tuple[bool, str]:
        if not self.is_subterranean_assault():
            return False, "Surprise Assault is not active for this army."
        root = self._unit_root(unit)
        if root is None:
            return False, "Tunnel Marker placement requires an arriving unit."
        if not self._unit_in_army(root):
            return False, "Tunnel Marker unit is not part of this army."
        if not self._unit_is_burrower(root):
            return False, "Tunnel Marker placement requires a Burrower unit."
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return False, "Tunnel Marker point is missing coordinates."
        try:
            x = float(point[0])
            y = float(point[1])
        except (TypeError, ValueError):
            return False, "Tunnel Marker coordinates must be numeric."
        return self._tunnel_marker_position_valid(game, root, x=x, y=y)

    def _publish_tunnel_markers_updated(self, game) -> None:
        if game is None:
            return
        event_system = getattr(game, "event_system", None)
        if event_system is None:
            return
        event_system.publish(
            "subterranean_assault_tunnel_markers_updated",
            army=self.army,
            markers=self.get_active_tunnel_markers(),
        )

    def place_tunnel_marker_at(self, *, game=None, unit=None, x: float, y: float) -> Optional[TunnelMarker]:
        root = self._unit_root(unit)
        valid, _reason = self.validate_subterranean_assault_tunnel_marker_point(
            unit=root,
            point=(x, y),
            game=game,
        )
        if not valid:
            return None
        z = 0.0
        map_obj = getattr(game, "map", None) if game is not None else None
        height_fn = getattr(map_obj, "get_height_at_point", None) if map_obj is not None else None
        if callable(height_fn):
            z = float(height_fn(float(x), float(y)))
        marker = TunnelMarker(
            marker_id=str(uuid.uuid4()),
            x=float(x),
            y=float(y),
            z=float(z),
            active=True,
        )
        self.tunnel_markers.append(marker)
        self._publish_tunnel_markers_updated(game)
        return marker

    def remove_tunnel_marker(self, marker: TunnelMarker) -> None:
        if marker is None:
            return
        marker.active = False

    @staticmethod
    def _base_longest_radius(base, *, fallback_model=None) -> float:
        if base is None and fallback_model is not None:
            base = getattr(fallback_model, "model_base", None)
        if base is None:
            return 0.0
        if hasattr(base, "get_longest_radius"):
            return float(base.get_longest_radius())
        if hasattr(base, "get_radius"):
            return float(base.get_radius())
        radius = getattr(base, "radius", None)
        if isinstance(radius, (list, tuple)) and radius:
            return float(radius[0])
        return float(radius) if radius is not None else 0.0

    def _placements_wholly_within_tunnel_marker(
        self,
        unit,
        placements: list[tuple[float, float, float, float]],
        *,
        marker: TunnelMarker,
        max_distance: float,
    ) -> bool:
        models = list(getattr(unit, "models", []) or [])
        for idx, placement in enumerate(list(placements or [])):
            if idx >= len(models):
                break
            model = models[idx]
            x, y, z, facing = placement
            if hasattr(unit, "_create_potential_base"):
                try:
                    base = unit._create_potential_base(x, y, z, facing, model=model)
                except Exception:
                    base = None
            else:
                base = None
            if base is None:
                base = getattr(model, "model_base", None)
            if base is None:
                return False
            try:
                bx = float(getattr(base, "x", x))
                by = float(getattr(base, "y", y))
            except Exception:
                bx = float(x)
                by = float(y)
            radius = float(self._base_longest_radius(base, fallback_model=model))
            center_dist = float(math.hypot(bx - float(marker.x), by - float(marker.y)))
            if center_dist + radius > float(max_distance) + 1e-6:
                return False
        return True

    def subterranean_assault_arrival_marker_for_positions(
        self,
        unit,
        placements: list[tuple[float, float, float, float]],
        *,
        game=None,
    ) -> Optional[TunnelMarker]:
        if not self.is_subterranean_assault():
            return None
        if unit is None:
            return None
        if not placements:
            return None
        root = self._unit_root(unit)
        if root is None:
            return None
        if not self._unit_in_army(root):
            return None
        if not self._unit_is_tyranids(root):
            return None
        for marker in list(self.get_active_tunnel_markers() or []):
            if self._placements_wholly_within_tunnel_marker(
                root,
                list(placements),
                marker=marker,
                max_distance=_TUNNEL_MARKER_HORIZONTAL_RANGE,
            ):
                return marker
        return None

    def on_unit_set_up(self, *, unit=None, game=None, set_up_as_reinforcements: bool = False) -> None:
        if not self.is_subterranean_assault():
            return
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        if not bool(set_up_as_reinforcements):
            return
        root = self._unit_root(unit)
        if root is None:
            return
        if not self._unit_in_army(root):
            return
        if not self._unit_is_tyranids(root):
            return
        if not self._unit_is_burrower(root):
            return
        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            return
        if self._pending_subterranean_assault_tunnel_marker_request(game, unit_id=unit_id):
            return

        from ..engine.decision_kinds import DECISION_PICK_POINT
        from ..engine.decisions import DecisionOption, DecisionRequest

        owner = getattr(self.army, "player", None)
        if owner is None:
            return
        request = DecisionRequest.create(
            DECISION_PICK_POINT,
            f"Surprise Assault: place a Tunnel Marker for {getattr(root, 'name', 'Burrower unit')}.",
            player_id=getattr(owner, "id", None),
            options=[DecisionOption.create("Confirm", payload={"action": "confirm"})],
            context={
                "ability": _SUBTERRANEAN_ASSAULT_TUNNEL_MARKER_PLACEMENT_ABILITY,
                "ability_name": "Surprise Assault",
                "phase": "Movement phase - Reinforcements step",
                "army_id": str(get_entity_id(self.army) or ""),
                "unit_id": unit_id,
                "unit_name": str(getattr(root, "name", "") or "Burrower unit"),
                "place_within_unit_distance": _TUNNEL_MARKER_PLACE_WITHIN_UNIT_DISTANCE,
                "min_enemy_distance": _TUNNEL_MARKER_REMOVAL_DISTANCE,
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)

    def apply_subterranean_assault_tunnel_marker_point(self, *, unit=None, point=None, game=None) -> Optional[TunnelMarker]:
        root = self._unit_root(unit)
        valid, _reason = self.validate_subterranean_assault_tunnel_marker_point(
            unit=root,
            point=point,
            game=game,
        )
        if not valid:
            return None
        x = float(point[0])
        y = float(point[1])
        return self.place_tunnel_marker_at(game=game, unit=root, x=x, y=y)

    def on_enemy_unit_move_ended(self, enemy_unit, *, game=None) -> None:
        if not self.is_subterranean_assault():
            return
        root = self._unit_root(enemy_unit)
        if root is None:
            return
        enemy_army = getattr(root, "get_parent_army", lambda: None)()
        if enemy_army is self.army:
            return
        if self._unit_has_keyword(root, "AIRCRAFT"):
            return
        if not self._unit_on_battlefield(root):
            return
        removed_any = False
        for marker in list(self.get_active_tunnel_markers() or []):
            for model in list(getattr(root, "models", []) or []):
                if not self._model_is_alive(model):
                    continue
                if float(horizontal_distance_point_to_model_base_2d(model, marker.x, marker.y)) <= _TUNNEL_MARKER_REMOVAL_DISTANCE + 1e-6:
                    self.remove_tunnel_marker(marker)
                    removed_any = True
                    break
        if removed_any:
            self._publish_tunnel_markers_updated(game)

    def _army_has_hyper_adaptations(self) -> bool:
        return self.is_invasion_fleet()

    def validate_detachment_rules(self) -> list[str]:
        if self.is_subterranean_assault():
            self.apply_subterranean_assault_burrower_keywords()
        if self.is_warrior_bioform_onslaught():
            self.apply_warrior_bioform_leader_beasts()
        return []

    def _unit_is_tyranids(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword_or_faction(unit, "TYRANIDS", faction_id=self.faction_id)

    def get_available_hyper_adaptations(self) -> list[HyperAdaptation]:
        if not self._army_has_hyper_adaptations():
            return []
        return list(HYPER_ADAPTATIONS)

    def get_active_hyper_adaptation(self, *, game=None) -> Optional[HyperAdaptation]:
        if not self._army_has_hyper_adaptations():
            return None
        if not self.active_hyper_adaptation_key:
            return None
        return HYPER_ADAPTATION_BY_KEY.get(str(self.active_hyper_adaptation_key).strip().upper())

    def get_active_hyper_adaptation_for_unit(self, unit, *, game=None) -> Optional[HyperAdaptation]:
        if unit is None:
            return None
        if not self._army_has_hyper_adaptations():
            return None
        if not self.active_hyper_adaptation_key:
            return None
        if not self._unit_is_tyranids(unit):
            return None
        army = self.army
        try:
            if army is not None and hasattr(unit, "get_parent_army"):
                if unit.get_parent_army() is not army:
                    return None
        except Exception:
            return None
        return HYPER_ADAPTATION_BY_KEY.get(str(self.active_hyper_adaptation_key).strip().upper())

    def can_select_hyper_adaptation(self, *, game=None, battle_round: Optional[int] = None) -> bool:
        if not self._army_has_hyper_adaptations():
            return False
        if self.active_hyper_adaptation_key:
            return False
        br = None
        if battle_round is not None:
            try:
                br = int(battle_round)
            except Exception:
                br = None
        if br is None and game is not None:
            try:
                br = int(getattr(game, "turn", 0) or 0)
            except Exception:
                br = None
        if br is None:
            return False
        return br == 1

    def select_hyper_adaptation(self, adaptation, *, battle_round: Optional[int] = None) -> bool:
        if not self._army_has_hyper_adaptations():
            return False
        key = getattr(adaptation, "key", adaptation)
        key = str(key or "").strip().upper()
        if key not in HYPER_ADAPTATION_BY_KEY:
            return False
        if self.active_hyper_adaptation_key:
            return False
        self.active_hyper_adaptation_key = key
        if battle_round is not None:
            try:
                self.hyper_adaptation_selected_round = int(battle_round)
            except Exception:
                pass
        return True

    def _pending_hyper_adaptation_request(self, game, army_id: str):
        if game is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "")) != "CHOOSE_HYPER_ADAPTATION":
                continue
            ctx = getattr(req, "context", {}) or {}
            if str(ctx.get("army_id", "")) == str(army_id):
                return req
        return None

    def _build_hyper_adaptation_request(self, game, player, battle_round: int):
        if game is None:
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_HYPER_ADAPTATION
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.entity_ids import get_entity_id

        army = self.army
        army_id = get_entity_id(army) if army is not None else None
        options = []
        for opt in self.get_available_hyper_adaptations():
            key = getattr(opt, "key", None)
            if not key:
                continue
            name = getattr(opt, "name", None) or str(opt)
            summary = getattr(opt, "summary", "") or getattr(opt, "effect", "")
            options.append(
                DecisionOption.create(
                    name,
                    payload={"choice_key": str(key), "summary": summary, "army_id": army_id},
                )
            )
        if not options:
            return None
        return DecisionRequest.create(
            DECISION_CHOOSE_HYPER_ADAPTATION,
            "Select Hyper-adaptation.",
            player_id=getattr(player, "id", None),
            options=options,
            context={"army_id": army_id, "battle_round": int(battle_round)},
        )

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if not self._army_has_hyper_adaptations():
            return
        try:
            br = int(battle_round or 0)
        except Exception:
            return
        if br != 1:
            return
        if self.active_hyper_adaptation_key:
            return

        player = None
        try:
            player = getattr(self.army, "player", None)
        except Exception:
            player = None

        if game is None:
            return

        if not bool(getattr(game, "is_authoritative", True)):
            return

        from ..utility.entity_ids import get_entity_id

        army_id = get_entity_id(self.army) if self.army is not None else None
        if self._pending_hyper_adaptation_request(game, army_id):
            return
        request = self._build_hyper_adaptation_request(game, player, br)
        if request is None:
            return
        if hasattr(game, "request_decision"):
            game.request_decision(request)
