from __future__ import annotations

import math
import uuid
from itertools import combinations
from dataclasses import dataclass
from typing import Any, Optional

from .detachment_manager import DetachmentManagerBase
from ..utility.aura_utils import (
    horizontal_distance_point_to_model_base_2d,
    model_within_range_of_unit,
    unit_within_range_of_unit,
)
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


@dataclass(frozen=True)
class SynapticImperative:
    key: str
    name: str
    summary: str
    invulnerable_save: int = 0
    advance_roll_bonus: int = 0
    charge_roll_bonus: int = 0
    melee_hit_bonus: int = 0


SYNAPTIC_AUGMENTATION = SynapticImperative(
    key="SYNAPTIC_AUGMENTATION",
    name="Synaptic Augmentation",
    summary="Units in Synapse Range gain a 5+ invulnerable save.",
    invulnerable_save=5,
)
SURGING_VITALITY = SynapticImperative(
    key="SURGING_VITALITY",
    name="Surging Vitality",
    summary="Units in Synapse Range gain +1 to Advance and Charge rolls.",
    advance_roll_bonus=1,
    charge_roll_bonus=1,
)
GOADED_TO_SLAUGHTER = SynapticImperative(
    key="GOADED_TO_SLAUGHTER",
    name="Goaded to Slaughter",
    summary="Units in Synapse Range gain +1 to melee hit rolls.",
    melee_hit_bonus=1,
)

SYNAPTIC_IMPERATIVES: tuple[SynapticImperative, ...] = (
    SYNAPTIC_AUGMENTATION,
    SURGING_VITALITY,
    GOADED_TO_SLAUGHTER,
)
SYNAPTIC_IMPERATIVE_BY_KEY = {imperative.key: imperative for imperative in SYNAPTIC_IMPERATIVES}

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
        self.active_synaptic_imperative_key: Optional[str] = None
        self.synaptic_imperative_active_round: Optional[int] = None
        self.synaptic_imperative_resolved_round: Optional[int] = None
        self.synaptic_imperatives_used_keys: list[str] = []
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

    def _unit_has_naturalised_camouflage(self, unit) -> bool:
        if unit is None:
            return False
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict) and bool(sr.get("enhancement_naturalised_camouflage")):
            return True
        enhancement = getattr(unit, "enhancement", None)
        if enhancement is None:
            return False
        enh_id = str(getattr(enhancement, "id", "") or "").strip()
        enh_name = self._norm(str(getattr(enhancement, "name", "") or ""))
        return bool(enh_id == "000008408003" or enh_name == "naturalisedcamouflage")

    def _iter_naturalised_camouflage_sources(self) -> list:
        army = self.army
        if army is None:
            return []
        unique_by_id = {}
        for unit in list(getattr(army, "units", []) or []):
            if not self._unit_has_naturalised_camouflage(unit):
                continue
            unit_id = str(get_entity_id(unit) or "").strip()
            if not unit_id or unit_id in unique_by_id:
                continue
            unique_by_id[unit_id] = unit
        return [unique_by_id[k] for k in sorted(unique_by_id.keys())]

    def is_vanguard_onslaught(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Vanguard Onslaught")

    def is_warrior_bioform_onslaught(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Warrior Bioform Onslaught")

    def _unending_swarm_unit_is_endless_multitude(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if self._unit_has_keyword(root, "ENDLESS MULTITUDE"):
            return True
        return self._attached_unit_has_keyword(root, "ENDLESS MULTITUDE")

    def insurmountable_odds_horde_move_applies(self, unit) -> bool:
        if not self.is_unending_swarm():
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_is_tyranids(root):
            return False
        return self._unending_swarm_unit_is_endless_multitude(root)

    def unending_swarm_relentless_hunger_movement_bonus(self, unit, *, game=None) -> tuple[int, str]:
        _ = game
        if not self.is_unending_swarm():
            return 0, ""
        root = self._unit_root(unit)
        if root is None:
            return 0, ""
        if not self._unit_in_army(root):
            return 0, ""
        if not self._unit_is_tyranids(root):
            return 0, ""
        for member, sr in self._attached_member_special_rules_with_flag(root, "enhancement_relentless_hunger"):
            if not self._enhancement_bearer_is_alive_for_member(member, sr):
                continue
            try:
                bonus = int(sr.get("enhancement_relentless_hunger_move_bonus", 2) or 2)
            except (TypeError, ValueError):
                bonus = 2
            if bonus <= 0:
                continue
            source = str(sr.get("enhancement_relentless_hunger_source", "") or "Relentless Hunger").strip()
            return int(bonus), source or "Relentless Hunger"
        return 0, ""

    def unending_swarm_piercing_talons_critical_wound_ap_bonus(
        self,
        attacker_model,
        attack_instance,
        *,
        game=None,
    ) -> tuple[int, str]:
        _ = game
        if not self.is_unending_swarm():
            return 0, ""
        if attacker_model is None:
            return 0, ""
        if not isinstance(attack_instance, dict) or not bool(attack_instance.get("crit_wound", False)):
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(attacker_unit)
        if root is None:
            return 0, ""
        if not self._unit_in_army(root):
            return 0, ""
        if not self._unit_is_tyranids(root):
            return 0, ""
        for member, sr in self._attached_member_special_rules_with_flag(root, "enhancement_piercing_talons"):
            if not self._enhancement_bearer_is_alive_for_member(member, sr):
                continue
            try:
                bonus = int(sr.get("enhancement_piercing_talons_critical_wound_ap_bonus", 1) or 1)
            except (TypeError, ValueError):
                bonus = 1
            if bonus <= 0:
                continue
            source = str(sr.get("enhancement_piercing_talons_source", "") or "Piercing Talons").strip()
            return int(bonus), source or "Piercing Talons"
        return 0, ""

    def naturalised_camouflage_selectable_units(self, source_unit, *, game=None) -> list:
        _ = game
        if not self.is_unending_swarm():
            return []
        source_root = self._unit_root(source_unit)
        if source_root is None:
            return []
        if not self._unit_in_army(source_root):
            return []
        if not self._unit_has_naturalised_camouflage(source_unit):
            return []
        if not self._unit_on_battlefield(source_root):
            return []
        source_sr = getattr(source_unit, "special_rules", None)
        if not isinstance(source_sr, dict):
            source_sr = {}
        bearer = self._enhancement_bearer_model_for_member(source_unit, source_sr)
        if bearer is None or not self._model_is_alive(bearer):
            return []
        try:
            range_in = float(source_sr.get("enhancement_naturalised_camouflage_range", 9.0) or 9.0)
        except (TypeError, ValueError):
            range_in = 9.0
        if range_in <= 0.0:
            return []
        selectable: list[Any] = []
        for root in self._iter_army_roots():
            if root is None:
                continue
            if not self._unit_in_army(root):
                continue
            if not self._unit_on_battlefield(root):
                continue
            if not self._unit_is_tyranids(root):
                continue
            if not self._unending_swarm_unit_is_endless_multitude(root):
                continue
            if not model_within_range_of_unit(bearer, root, float(range_in), use_attached_aggregate=True):
                continue
            selectable.append(root)
        selectable.sort(key=lambda item: (str(get_entity_id(item) or ""), str(getattr(item, "name", "") or "")))
        return selectable

    def _pending_naturalised_camouflage_request(self, game, *, source_unit_id: str, battle_round: int) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != "naturalised_camouflage":
                continue
            if str(ctx.get("source_unit_id", "") or "") != str(source_unit_id or ""):
                continue
            if int(ctx.get("battle_round", 0) or 0) != int(battle_round):
                continue
            return True
        return False

    def _clear_naturalised_camouflage_effects(self, source_unit_id: str = "") -> None:
        source_filter = str(source_unit_id or "").strip()
        for root in self._iter_army_roots():
            for member in self._iter_attached_members(root):
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                entries = list(sr.get("bearer_unit_benefit_of_cover", []) or [])
                if not entries:
                    continue
                kept_entries = []
                changed = False
                for entry in entries:
                    if not isinstance(entry, dict):
                        kept_entries.append(entry)
                        continue
                    entry_source_id = str(entry.get("source_unit_id", "") or "").strip()
                    enhancement_key = str(entry.get("enhancement_key", "") or "").strip().lower()
                    source_name = str(entry.get("source", "") or "").strip().lower()
                    if enhancement_key != "naturalised_camouflage" and source_name != "naturalised camouflage":
                        kept_entries.append(entry)
                        continue
                    if source_filter and entry_source_id != source_filter:
                        kept_entries.append(entry)
                        continue
                    changed = True
                if not changed:
                    continue
                if kept_entries:
                    sr["bearer_unit_benefit_of_cover"] = kept_entries
                else:
                    sr.pop("bearer_unit_benefit_of_cover", None)
                member.special_rules = sr
                invalidate_cache = getattr(member, "_invalidate_ability_cache", None)
                if callable(invalidate_cache):
                    invalidate_cache()

    def _queue_naturalised_camouflage_selection_requests(self, *, game=None, battle_round: int) -> None:
        if not self.is_unending_swarm():
            return
        army = self.army
        player = getattr(army, "player", None) if army is not None else None
        if game is None:
            game = getattr(player, "game", None)
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        if int(battle_round) != 1:
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        request_fn = getattr(game, "request_decision", None)
        for source_unit in self._iter_naturalised_camouflage_sources():
            sr = getattr(source_unit, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if bool(sr.get("enhancement_naturalised_camouflage_resolved")):
                continue
            source_unit_id = str(get_entity_id(source_unit) or "").strip()
            if not source_unit_id:
                continue
            if self._pending_naturalised_camouflage_request(
                game,
                source_unit_id=source_unit_id,
                battle_round=int(battle_round),
            ):
                continue

            selectable = list(self.naturalised_camouflage_selectable_units(source_unit, game=game) or [])
            try:
                max_units = int(sr.get("enhancement_naturalised_camouflage_max_units", 3) or 3)
            except (TypeError, ValueError):
                max_units = 3
            max_units = max(0, int(max_units))

            candidate_ids = [
                str(get_entity_id(target) or "")
                for target in selectable
                if str(get_entity_id(target) or "").strip()
            ]
            options = [
                DecisionOption.create(
                    "None",
                    payload={
                        "action": "skip",
                        "selected_unit_ids": [],
                        "selection_kind": "none",
                    },
                )
            ]
            for target in selectable:
                target_id = str(get_entity_id(target) or "").strip()
                if not target_id:
                    continue
                options.append(
                    DecisionOption.create(
                        str(getattr(target, "name", "Unit") or "Unit"),
                        payload={
                            "selected_unit_ids": [target_id],
                            "selection_kind": "one_unit",
                        },
                    )
                )
            for count in range(2, max_units + 1):
                for selected in combinations(selectable, count):
                    selected_ids = []
                    selected_names = []
                    for target in selected:
                        target_id = str(get_entity_id(target) or "").strip()
                        if not target_id:
                            selected_ids = []
                            break
                        selected_ids.append(target_id)
                        selected_names.append(str(getattr(target, "name", "Unit") or "Unit"))
                    if not selected_ids:
                        continue
                    options.append(
                        DecisionOption.create(
                            " + ".join(selected_names),
                            payload={
                                "selected_unit_ids": selected_ids,
                                "selection_kind": f"{count}_units",
                            },
                        )
                    )

            if len(options) <= 1:
                sr["enhancement_naturalised_camouflage_selected_unit_ids"] = []
                sr["enhancement_naturalised_camouflage_resolved"] = True
                source_unit.special_rules = sr
                continue

            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                "Naturalised Camouflage: select up to three friendly Endless Multitude units within 9\".",
                player_id=getattr(player, "id", None),
                options=options,
                context={
                    "ability": "naturalised_camouflage",
                    "ability_name": "Naturalised Camouflage",
                    "source_unit_id": source_unit_id,
                    "unit_id": source_unit_id,
                    "battle_round": int(battle_round),
                    "candidate_unit_ids": list(candidate_ids),
                    "max_selections": int(max_units),
                    "optional": True,
                },
            )
            if callable(request_fn):
                request_fn(request)

    def questing_tendrils_charge_after_fall_back_applies(self, unit, *, game=None) -> bool:
        _ = game
        if not self.is_vanguard_onslaught():
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        return self._unit_is_tyranids(root)

    def questing_tendrils_charge_after_advance_applies(self, unit, *, game=None) -> bool:
        if not self.questing_tendrils_charge_after_fall_back_applies(unit, game=game):
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        if self._unit_has_keyword(root, "VANGUARD INVADER"):
            return True
        return self._attached_unit_has_keyword(root, "VANGUARD INVADER")

    def vanguard_onslaught_chameleonic_stealth_applies(self, unit, *, game=None) -> bool:
        _ = game
        if not self.is_vanguard_onslaught():
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_is_tyranids(root):
            return False
        checker = getattr(root, "_attached_unit_has_active_enhancement", None)
        if not callable(checker):
            return False
        return bool(
            checker(
                "enhancement_chameleonic",
                enhancement_id="000008417003",
                enhancement_name="Chameleonic",
            )
        )

    def vanguard_onslaught_chameleonic_benefit_of_cover(
        self,
        target_model,
        *,
        attack_type: str = "",
        game=None,
    ) -> tuple[bool, str]:
        _ = game
        if not self.is_vanguard_onslaught():
            return False, ""
        if target_model is None:
            return False, ""
        if str(attack_type or "").strip().lower() == "melee":
            return False, ""
        target_unit = getattr(target_model, "parent_unit", None)
        if target_unit is None:
            return False, ""
        if not self.vanguard_onslaught_chameleonic_stealth_applies(target_unit):
            return False, ""
        return True, "Chameleonic"

    def override_instincts_shoot_charge_after_fall_back_applies(self, unit, *, game=None) -> bool:
        if not self.is_synaptic_nexus():
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_is_tyranids(root):
            return False
        if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not bool(sr.get("tyranids_override_instincts_active")):
            return False

        gm = game
        if gm is None:
            army = getattr(self, "army", None)
            gm = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        if gm is None:
            return True

        owner_id = str(sr.get("tyranids_override_instincts_turn_owner", "") or "")
        try:
            effect_turn = int(sr.get("tyranids_override_instincts_turn", 0) or 0)
        except Exception:
            effect_turn = 0
        try:
            current_player = gm.get_current_player()
        except Exception:
            current_player = None
        current_owner = str(getattr(current_player, "id", "") or "")
        try:
            current_turn = int(getattr(gm, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        if owner_id and current_owner and owner_id != current_owner:
            return False
        if effect_turn and current_turn and effect_turn != current_turn:
            return False
        return True

    def can_shoot_after_fall_back(self, unit, *, profile=None, game=None) -> bool:
        _ = profile
        return self.override_instincts_shoot_charge_after_fall_back_applies(unit, game=game)

    def can_charge_after_fall_back(self, unit, *, game=None) -> bool:
        if self.questing_tendrils_charge_after_fall_back_applies(unit, game=game):
            return True
        return self.override_instincts_shoot_charge_after_fall_back_applies(unit, game=game)

    def can_charge_after_advance(self, unit, *, game=None) -> bool:
        return self.questing_tendrils_charge_after_advance_applies(unit, game=game)

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
        for member in self._iter_attached_members(root):
            if self._unit_has_keyword(member, keyword):
                return True
        return False

    def _iter_attached_members(self, unit) -> list:
        root = self._unit_root(unit)
        if root is None:
            return []
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        members.sort(key=lambda item: (str(get_entity_id(item) or ""), str(getattr(item, "name", "") or "")))
        return members

    def _attached_member_special_rules_with_flag(self, unit, flag_key: str) -> list[tuple[Any, dict]]:
        out: list[tuple[Any, dict]] = []
        for member in self._iter_attached_members(unit):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get(flag_key)):
                continue
            out.append((member, sr))
        return out

    @staticmethod
    def _enhancement_bearer_is_alive_for_member(member, special_rules: Optional[dict] = None) -> bool:
        unit = member
        sr = special_rules if isinstance(special_rules, dict) else getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "").strip()
        if bearer_id:
            for model in list(getattr(unit, "models", []) or []):
                if str(get_entity_id(model) or "") != bearer_id:
                    continue
                return TyranidsDetachmentManager._model_is_alive(model)
            return False
        get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
        if callable(get_bearer):
            bearer = get_bearer()
            if bearer is not None:
                return TyranidsDetachmentManager._model_is_alive(bearer)
        for model in list(getattr(unit, "models", []) or []):
            if TyranidsDetachmentManager._model_is_alive(model):
                return True
        return False

    @staticmethod
    def _enhancement_bearer_model_for_member(member, special_rules: Optional[dict] = None):
        unit = member
        if unit is None:
            return None
        sr = special_rules if isinstance(special_rules, dict) else getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "").strip()
        if bearer_id:
            for model in list(getattr(unit, "models", []) or []):
                entity_id = str(get_entity_id(model) or "").strip()
                local_id = str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()
                if bearer_id in {entity_id, local_id}:
                    return model
            return None
        get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
        if callable(get_bearer):
            bearer = get_bearer()
            if bearer is not None:
                return bearer
        models = list(getattr(unit, "models", []) or [])
        if len(models) == 1:
            return models[0]
        for model in models:
            if TyranidsDetachmentManager._model_is_alive(model):
                return model
        return None

    def _timed_unit_effect_is_active(
        self,
        unit,
        flag_key: str,
        *,
        expires_phase_key: str,
        turn_key: str,
        owner_key: str,
        game=None,
    ) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get(flag_key)):
            return False
        gm = game
        if gm is None:
            army = getattr(root, "get_parent_army", lambda: None)()
            gm = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        if gm is None:
            return True
        expected_phase = str(sr.get(expires_phase_key, "") or "").strip().upper()
        if expected_phase:
            current_phase = str(getattr(getattr(gm, "phase", None), "name", "") or "").strip().upper()
            if current_phase and current_phase != expected_phase:
                return False
        effect_turn = int(sr.get(turn_key, 0) or 0)
        current_turn = int(getattr(gm, "turn", 0) or 0)
        if effect_turn and current_turn and effect_turn != current_turn:
            return False
        owner_id = str(sr.get(owner_key, "") or "").strip()
        if owner_id:
            current_player = getattr(gm, "get_current_player", lambda: None)()
            current_owner_id = str(getattr(current_player, "id", "") or "").strip()
            if current_owner_id and current_owner_id != owner_id:
                return False
        return True

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

    @staticmethod
    def _model_matches_enhancement_bearer(model, member, special_rules: Optional[dict] = None) -> bool:
        if model is None or member is None:
            return False
        sr = special_rules if isinstance(special_rules, dict) else getattr(member, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        model_id = str(get_entity_id(model) or "").strip()
        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "").strip()
        if bearer_id:
            return bool(model_id) and model_id == bearer_id
        get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
        if callable(get_bearer):
            bearer = get_bearer()
            if bearer is not None:
                if bearer is model:
                    return True
                bearer_model_id = str(get_entity_id(bearer) or "").strip()
                return bool(model_id) and bool(bearer_model_id) and model_id == bearer_model_id
        models = list(getattr(member, "models", []) or [])
        if len(models) != 1:
            return False
        only_model = models[0]
        if only_model is model:
            return True
        only_model_id = str(get_entity_id(only_model) or "").strip()
        return bool(model_id) and bool(only_model_id) and model_id == only_model_id

    def _crusher_bearer_entry_for_model(
        self,
        model,
        *,
        flag_key: str,
        unit=None,
        require_alive: bool = True,
    ) -> tuple[Any, Any, Optional[dict]]:
        if not self.is_crusher_stampede():
            return None, None, None
        if model is None:
            return None, None, None
        source_unit = unit if unit is not None else getattr(model, "parent_unit", None)
        root = self._unit_root(source_unit)
        if root is None:
            return None, None, None
        if not self._unit_in_army(root):
            return None, None, None
        if not self._unit_is_tyranids_monster(root):
            return None, None, None
        if not self._model_is_monster(model):
            return None, None, None
        if require_alive and not self._model_is_alive(model):
            return None, None, None
        for member, sr in self._attached_member_special_rules_with_flag(root, flag_key):
            if self._model_matches_enhancement_bearer(model, member, sr):
                return root, member, sr
        return root, None, None

    def _assimilation_parasitic_member(self, unit) -> tuple[Any, Optional[dict]]:
        if not self.is_assimilation_swarm():
            return None, None
        for member, sr in self._attached_member_special_rules_with_flag(unit, "enhancement_parasitic_biomorphology"):
            if self._enhancement_bearer_is_alive_for_member(member, sr):
                return member, sr
        return None, None

    def _assimilation_secure_biomass_state(self, unit, *, game=None) -> Optional[dict]:
        if not self.is_assimilation_swarm():
            return None
        root = self._unit_root(unit)
        if root is None:
            return None
        for member in self._iter_attached_members(root):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not self._timed_unit_effect_is_active(
                member,
                "tyranids_secure_biomass_active",
                expires_phase_key="tyranids_secure_biomass_expires_phase",
                turn_key="tyranids_secure_biomass_turn",
                owner_key="tyranids_secure_biomass_owner",
                game=game,
            ):
                continue
            return sr
        return None

    def _assimilation_bearer_within_harvester_range(self, bearer_unit, *, range_value: float = 6.0) -> bool:
        member, sr = self._assimilation_parasitic_member(bearer_unit)
        if member is None or sr is None:
            return False
        get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
        bearer = get_bearer() if callable(get_bearer) else None
        if bearer is None or not self._model_is_alive(bearer):
            return False
        base = getattr(bearer, "model_base", None)
        if base is None:
            return False
        x = float(getattr(base, "x", 0.0) or 0.0)
        y = float(getattr(base, "y", 0.0) or 0.0)
        max_range = float(range_value or 0.0)
        if max_range <= 0.0:
            return False
        for candidate_root in self._iter_army_roots():
            if candidate_root is None:
                continue
            if not self._unit_on_battlefield(candidate_root):
                continue
            if not self._unit_is_tyranids(candidate_root):
                continue
            if not self._attached_unit_has_keyword(candidate_root, "HARVESTER"):
                continue
            get_models = getattr(candidate_root, "get_attached_unit_models", None)
            models = list(get_models() or []) if callable(get_models) else list(getattr(candidate_root, "models", []) or [])
            for model in models:
                if not self._model_is_alive(model):
                    continue
                if float(horizontal_distance_point_to_model_base_2d(model, x, y)) <= max_range + 1e-6:
                    return True
        return False

    def parasitic_biomorphology_melee_bonus(self, attacker_model, *, weapon_profile=None, game=None) -> tuple[int, int, str]:
        _ = game
        if not self.is_assimilation_swarm():
            return 0, 0, ""
        if attacker_model is None:
            return 0, 0, ""
        is_melee = getattr(weapon_profile, "is_melee", None)
        if callable(is_melee) and not bool(is_melee()):
            return 0, 0, ""
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return 0, 0, ""
        member, sr = self._assimilation_parasitic_member(root)
        if member is None or sr is None:
            return 0, 0, ""
        strength_bonus = int(sr.get("enhancement_parasitic_biomorphology_melee_strength_bonus", 1) or 0)
        attacks_bonus = 0
        if bool(sr.get("enhancement_parasitic_biomorphology_attacks_unlocked")):
            attacks_bonus = int(sr.get("enhancement_parasitic_biomorphology_melee_attacks_bonus", 1) or 0)
        source = str(sr.get("enhancement_parasitic_biomorphology_source", "") or "Parasitic Biomorphology").strip()
        if not source:
            source = "Parasitic Biomorphology"
        return max(0, strength_bonus), max(0, attacks_bonus), source

    def broodguard_impulse_wound_bonus(self, attacker_model, target_unit=None, *, game=None) -> tuple[int, str]:
        _ = game
        if not self.is_assimilation_swarm():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        source_unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = self._unit_root(source_unit)
        target_root = self._unit_root(target_unit)
        if attacker_root is None or target_root is None:
            return 0, ""
        if not self._unit_in_army(attacker_root):
            return 0, ""
        if not self._unit_is_tyranids(attacker_root):
            return 0, ""
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("tyranids_broodguard_impulse_active")):
            return 0, ""
        owner_id = str(sr.get("tyranids_broodguard_impulse_owner_id", "") or "").strip()
        current_owner = str(getattr(getattr(self.army, "player", None), "id", "") or "").strip()
        if owner_id and current_owner and owner_id != current_owner:
            return 0, ""
        bonus = int(sr.get("tyranids_broodguard_impulse_wound_bonus", 1) or 0)
        source = str(sr.get("tyranids_broodguard_impulse_source", "") or "Broodguard Impulse").strip()
        if not source:
            source = "Broodguard Impulse"
        return max(0, bonus), source

    def secure_biomass_lethal_hits_applies(self, attacker_model, *, weapon_profile=None, game=None) -> bool:
        if not self.is_assimilation_swarm():
            return False
        if attacker_model is None:
            return False
        is_melee = getattr(weapon_profile, "is_melee", None)
        if callable(is_melee) and not bool(is_melee()):
            return False
        unit = getattr(attacker_model, "parent_unit", None)
        state = self._assimilation_secure_biomass_state(unit, game=game)
        return state is not None

    def secure_biomass_crit_hit_threshold(self, attacker_model, *, weapon_profile=None, game=None) -> tuple[int, str]:
        if not self.is_assimilation_swarm():
            return 0, ""
        if attacker_model is None:
            return 0, ""
        is_melee = getattr(weapon_profile, "is_melee", None)
        if callable(is_melee) and not bool(is_melee()):
            return 0, ""
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(unit)
        if root is None:
            return 0, ""
        state = self._assimilation_secure_biomass_state(root, game=game)
        if state is None:
            return 0, ""
        if not self._attached_unit_has_keyword(root, "HARVESTER"):
            return 0, ""
        threshold = int(state.get("tyranids_secure_biomass_crit_threshold", 5) or 0)
        if threshold <= 0:
            return 0, ""
        source = str(state.get("tyranids_secure_biomass_source", "") or "Secure Biomass").strip()
        if not source:
            source = "Secure Biomass"
        return threshold, source

    def unlock_parasitic_biomorphology_after_kill(self, destroyed_unit, *, destroyed_by_unit=None, game=None) -> bool:
        if not self.is_assimilation_swarm():
            return False
        if destroyed_unit is None or destroyed_by_unit is None:
            return False
        gm = game
        if gm is None:
            gm = getattr(getattr(self.army, "player", None), "game", None) if self.army is not None else None
        phase_name = str(getattr(getattr(gm, "phase", None), "name", "") or "").strip().upper() if gm is not None else ""
        if phase_name and phase_name != "FIGHT_PHASE":
            return False
        destroyed_root = self._unit_root(destroyed_unit)
        attacker_root = self._unit_root(destroyed_by_unit)
        if destroyed_root is None or attacker_root is None:
            return False
        if not self._unit_in_army(attacker_root):
            return False
        if destroyed_root.get_parent_army() is attacker_root.get_parent_army():
            return False
        member, sr = self._assimilation_parasitic_member(attacker_root)
        if member is None or sr is None:
            return False
        if bool(sr.get("enhancement_parasitic_biomorphology_attacks_unlocked")):
            return False
        range_value = float(sr.get("enhancement_parasitic_biomorphology_harvester_range", 6.0) or 6.0)
        if not self._assimilation_bearer_within_harvester_range(attacker_root, range_value=range_value):
            return False
        updated = dict(sr)
        updated["enhancement_parasitic_biomorphology_attacks_unlocked"] = True
        member.special_rules = updated
        return True

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

    def crusher_ominous_presence_objective_control_bonus(self, model, *, unit=None) -> tuple[int, str]:
        _root, _member, sr = self._crusher_bearer_entry_for_model(
            model,
            unit=unit,
            flag_key="enhancement_ominous_presence",
        )
        if sr is None:
            return 0, ""
        bonus = int(sr.get("enhancement_ominous_presence_objective_control_bonus", 3) or 0)
        if bonus <= 0:
            return 0, ""
        source = str(sr.get("enhancement_ominous_presence_source", "") or "Ominous Presence").strip()
        if not source:
            source = "Ominous Presence"
        return bonus, f"{source} (+{bonus} OC)"

    def crusher_monstrous_nemesis_wound_bonus(
        self,
        attacker_model,
        target_unit=None,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        _ = game
        if attacker_model is None or target_unit is None:
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            is_melee = getattr(parent, "is_melee", None) if parent is not None else None
            if callable(is_melee) and not bool(is_melee()):
                return 0, ""
        root, _member, sr = self._crusher_bearer_entry_for_model(
            attacker_model,
            flag_key="enhancement_monstrous_nemesis",
        )
        if root is None or sr is None:
            return 0, ""
        target_root = self._unit_root(target_unit)
        if target_root is None:
            return 0, ""
        if target_root.get_parent_army() is root.get_parent_army():
            return 0, ""
        if not (self._unit_has_keyword(target_root, "MONSTER") or self._unit_has_keyword(target_root, "VEHICLE")):
            return 0, ""
        bonus = int(sr.get("enhancement_monstrous_nemesis_wound_bonus", 1) or 0)
        if bonus <= 0:
            return 0, ""
        source = str(sr.get("enhancement_monstrous_nemesis_source", "") or "Monstrous Nemesis").strip()
        if not source:
            source = "Monstrous Nemesis"
        return bonus, source

    def crusher_enraged_reserves_fight_on_death_rule(self, unit, *, model=None, game=None) -> Optional[dict]:
        if model is None:
            return None
        root, _member, sr = self._crusher_bearer_entry_for_model(
            model,
            unit=unit,
            flag_key="enhancement_enraged_reserves",
            require_alive=False,
        )
        if root is None or sr is None:
            return None
        gm = game
        if gm is None:
            gm = getattr(getattr(self.army, "player", None), "game", None) if self.army is not None else None
        if gm is not None:
            phase_name = str(getattr(getattr(gm, "phase", None), "name", "") or "").strip().upper()
            if phase_name and phase_name != "FIGHT_PHASE":
                return None
        threshold = int(sr.get("enhancement_enraged_reserves_threshold", 3) or 0)
        if threshold < 2 or threshold > 6:
            return None
        source = str(sr.get("enhancement_enraged_reserves_source", "") or "Enraged Reserves").strip()
        if not source:
            source = "Enraged Reserves"
        return {"threshold": threshold, "source": source}

    def crusher_null_nodules_spec(self, model, *, unit=None) -> Optional[dict]:
        _root, _member, sr = self._crusher_bearer_entry_for_model(
            model,
            unit=unit,
            flag_key="enhancement_null_nodules",
        )
        if sr is None:
            return None
        source = str(sr.get("enhancement_null_nodules_source", "") or "Null Nodules").strip()
        if not source:
            source = "Null Nodules"
        fnp_value = int(sr.get("enhancement_null_nodules_fnp_value", 5) or 0)
        if fnp_value <= 0:
            return None
        ability_key = str(sr.get("enhancement_null_nodules_once_per_battle_key", "") or "null_nodules").strip().lower()
        if not ability_key:
            ability_key = "null_nodules"
        condition = str(sr.get("enhancement_null_nodules_condition", "") or "against psychic attacks").strip()
        if not condition:
            condition = "against psychic attacks"
        return {
            "ability_key": ability_key,
            "source": source,
            "fnp_value": fnp_value,
            "condition": condition,
        }

    def crusher_swarm_guided_salvoes_ignore_hit_modifiers_rule(
        self,
        attacker_model,
        *,
        game=None,
    ) -> Optional[dict]:
        if not self.is_crusher_stampede():
            return None
        if attacker_model is None:
            return None
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(attacker_unit)
        if root is None or not self._unit_in_army(root):
            return None
        if not self._unit_is_tyranids_monster(root):
            return None
        if not self._model_is_monster(attacker_model):
            return None
        sr = getattr(root, "special_rules", None)
        if not (isinstance(sr, dict) and bool(sr.get("tyranids_swarm_guided_salvoes_active"))):
            return None
        if not self._timed_unit_effect_is_active(
            root,
            "tyranids_swarm_guided_salvoes_active",
            expires_phase_key="tyranids_swarm_guided_salvoes_expires_phase",
            turn_key="tyranids_swarm_guided_salvoes_turn",
            owner_key="tyranids_swarm_guided_salvoes_turn_owner",
            game=game,
        ):
            return None
        source = str(sr.get("tyranids_swarm_guided_salvoes_source", "") or "Swarm-guided Salvoes").strip()
        if not source:
            source = "Swarm-guided Salvoes"
        return {
            "name": source,
            "attack_type": "ranged",
            "skill_kinds": {"ballistic", "weapon"},
            "allow_hit": True,
        }

    def _unit_in_synapse_range(self, unit, *, game=None) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_is_tyranids(root):
            return False
        synapse_mgr = getattr(self.army, "synapse", None) if self.army is not None else None
        if synapse_mgr is None:
            return False
        return bool(synapse_mgr.unit_in_synapse_range(root, game=game))

    def synaptic_imperatives_invulnerable_save(self, model, *, unit=None, game=None) -> tuple[int, str]:
        if model is None:
            return 0, ""
        source_unit = unit if unit is not None else getattr(model, "parent_unit", None)
        if source_unit is None:
            return 0, ""
        imperative = self.get_active_synaptic_imperative(game=game)
        if imperative is None or int(getattr(imperative, "invulnerable_save", 0) or 0) <= 0:
            return 0, ""
        if not self._unit_in_synapse_range(source_unit, game=game):
            return 0, ""
        value = int(getattr(imperative, "invulnerable_save", 0) or 0)
        return value, f"Synaptic Imperatives ({imperative.name})"

    def synaptic_imperatives_advance_roll_bonus(self, unit, *, game=None) -> tuple[int, str]:
        imperative = self.get_active_synaptic_imperative(game=game)
        if imperative is None:
            return 0, ""
        bonus = int(getattr(imperative, "advance_roll_bonus", 0) or 0)
        if bonus <= 0:
            return 0, ""
        if not self._unit_in_synapse_range(unit, game=game):
            return 0, ""
        return bonus, f"Synaptic Imperatives ({imperative.name})"

    def synaptic_imperatives_charge_roll_bonus(self, unit, *, game=None) -> tuple[int, str]:
        imperative = self.get_active_synaptic_imperative(game=game)
        if imperative is None:
            return 0, ""
        bonus = int(getattr(imperative, "charge_roll_bonus", 0) or 0)
        if bonus <= 0:
            return 0, ""
        if not self._unit_in_synapse_range(unit, game=game):
            return 0, ""
        return bonus, f"Synaptic Imperatives ({imperative.name})"

    def synaptic_imperatives_melee_hit_bonus(self, model, *, unit=None, game=None) -> tuple[int, str]:
        if model is None:
            return 0, ""
        source_unit = unit if unit is not None else getattr(model, "parent_unit", None)
        if source_unit is None:
            return 0, ""
        imperative = self.get_active_synaptic_imperative(game=game)
        if imperative is None:
            return 0, ""
        bonus = int(getattr(imperative, "melee_hit_bonus", 0) or 0)
        if bonus <= 0:
            return 0, ""
        if not self._unit_in_synapse_range(source_unit, game=game):
            return 0, ""
        return bonus, f"Synaptic Imperatives ({imperative.name})"

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

    def _feed_the_swarm_options_for_target(self, source_unit, target_unit, *, range_value: float) -> list[dict]:
        source_root = self._unit_root(source_unit)
        target_root = self._unit_root(target_unit)
        if source_root is None or target_root is None:
            return []
        source_id = str(get_entity_id(source_root) or "").strip()
        target_id = str(get_entity_id(target_root) or "").strip()
        if not target_id:
            return []
        options: list[dict] = []

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
            options.extend(self._feed_the_swarm_options_for_target(source_root, target_root, range_value=range_value))
        options.sort(key=lambda item: str(item.get("option_key", "") or ""))
        return options

    def assimilation_regeneration_options_for_unit(self, target_unit, *, game=None, player=None) -> list[dict]:
        target_root = self._unit_root(target_unit)
        if target_root is None:
            return []
        if not self._unit_on_battlefield(target_root):
            return []
        if not self._unit_is_tyranids(target_root):
            return []
        if self._feed_the_swarm_target_regens_this_phase(target_root, game=game, player=player) >= self._feed_the_swarm_target_regen_limit(target_root):
            return []
        return self._feed_the_swarm_options_for_target(target_root, target_root, range_value=0.0)

    def assimilation_regeneration_options_for_harvester(
        self,
        source_unit,
        *,
        game=None,
        player=None,
        exclude_target_ids: tuple[str, ...] = (),
    ) -> list[dict]:
        source_root = self._unit_root(source_unit)
        if source_root is None:
            return []
        if not self._unit_on_battlefield(source_root):
            return []
        if not self._attached_unit_has_keyword(source_root, "HARVESTER"):
            return []
        excluded = {str(item or "").strip() for item in tuple(exclude_target_ids or ()) if str(item or "").strip()}
        options: list[dict] = []
        for target_root in self._iter_army_roots():
            target_id = str(get_entity_id(target_root) or "").strip()
            if target_id and target_id in excluded:
                continue
            if not self._feed_the_swarm_target_eligible(
                source_root,
                target_root,
                range_value=6.0,
                game=game,
                player=player,
            ):
                continue
            options.extend(self._feed_the_swarm_options_for_target(source_root, target_root, range_value=6.0))
        options.sort(key=lambda item: str(item.get("option_key", "") or ""))
        return options

    def _apply_regeneration_option(
        self,
        selected_option: dict,
        *,
        game=None,
        player=None,
        mark_source_used: bool = True,
        heal_amount_override: Optional[int] = None,
        placement_source: str = "feed_the_swarm",
    ) -> Optional[dict]:
        if not isinstance(selected_option, dict):
            return None
        source_root = self._unit_root(selected_option.get("source_unit"))
        target_root = self._unit_root(selected_option.get("target_unit"))
        if target_root is None:
            return None
        source_id = str(get_entity_id(source_root) or "") if source_root is not None else ""
        target_id = str(get_entity_id(target_root) or "")
        action = str(selected_option.get("action", "") or "").strip().lower()

        if action == "heal":
            model = selected_option.get("target_model")
            if model is None or not self._model_is_alive(model):
                return None
            before, _base = self._wounds_snapshot(model)
            if heal_amount_override is None:
                heal_roll = max(0, int(get_roll("D3") or 0)) + 1
            else:
                heal_roll = max(0, int(heal_amount_override))
            heal_fn = getattr(model, "heal", None)
            if callable(heal_fn):
                heal_fn(int(heal_roll))
            else:
                setattr(model, "wounds", int(before + int(heal_roll)))
            check_profile = getattr(model, "_check_damaged_profile", None)
            if callable(check_profile):
                check_profile()
            after, _ = self._wounds_snapshot(model)
            healed = max(0, int(after - before))
            if source_root is not None and mark_source_used:
                self._feed_the_swarm_mark_source_used(source_root, game=game, player=player)
            self._feed_the_swarm_increment_target_regens(target_root, game=game, player=player)
            return {
                "action": "heal",
                "source_unit_id": source_id,
                "source_unit_name": str(getattr(source_root, "name", "") or "Unit") if source_root is not None else "",
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
                    placement_source=str(placement_source or "feed_the_swarm"),
                )
                or 0
            )
            if returned <= 0:
                return None
            if source_root is not None and mark_source_used:
                self._feed_the_swarm_mark_source_used(source_root, game=game, player=player)
            self._feed_the_swarm_increment_target_regens(target_root, game=game, player=player)
            return {
                "action": "return",
                "source_unit_id": source_id,
                "source_unit_name": str(getattr(source_root, "name", "") or "Unit") if source_root is not None else "",
                "target_unit_id": target_id,
                "target_unit_name": str(getattr(target_root, "name", "") or "Unit"),
                "return_count_requested": int(requested),
                "return_count": int(returned),
            }
        return None

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
        return self._apply_regeneration_option(
            selected_option,
            game=game,
            player=player,
            mark_source_used=True,
            placement_source="feed_the_swarm",
        )

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

    def get_tunnel_marker_by_id(self, marker_id: str) -> Optional[TunnelMarker]:
        target = str(marker_id or "").strip()
        if not target:
            return None
        for marker in list(self.get_active_tunnel_markers() or []):
            if str(getattr(marker, "marker_id", "") or "").strip() == target:
                return marker
        return None

    def subterranean_assault_tunnel_marker_ids_for_unit(self, unit) -> list[str]:
        if not self.is_subterranean_assault():
            return []
        root = self._unit_root(unit)
        if root is None:
            return []
        if not self._unit_in_army(root):
            return []
        if not self._unit_on_battlefield(root):
            return []
        placements: list[tuple[float, float, float, float]] = []
        for model in list(getattr(root, "models", []) or []):
            if not self._model_is_alive(model):
                continue
            get_location = getattr(model, "get_location", None)
            if not callable(get_location):
                continue
            try:
                location = get_location()
            except Exception:
                continue
            if not isinstance(location, (list, tuple)) or len(location) < 2:
                continue
            try:
                x = float(location[0])
                y = float(location[1])
                z = float(location[2]) if len(location) > 2 else 0.0
                facing = float(location[3]) if len(location) > 3 else 0.0
            except (TypeError, ValueError):
                continue
            placements.append((x, y, z, facing))
        if not placements:
            return []
        marker_ids: list[str] = []
        for marker in list(self.get_active_tunnel_markers() or []):
            if self._placements_wholly_within_tunnel_marker(
                root,
                list(placements),
                marker=marker,
                max_distance=_TUNNEL_MARKER_HORIZONTAL_RANGE,
            ):
                marker_id = str(getattr(marker, "marker_id", "") or "").strip()
                if marker_id:
                    marker_ids.append(marker_id)
        return sorted(set(marker_ids))

    def subterranean_assault_swarming_assault_reroll_charge_applies(self, unit, *, game=None) -> bool:
        if not self.is_subterranean_assault():
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        game_obj = game
        if game_obj is None:
            army = getattr(self, "army", None)
            game_obj = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        current_player_id = str(getattr(getattr(self.army, "player", None), "id", "") or "").strip()
        if game_obj is not None:
            active_player = getattr(game_obj, "get_current_player", lambda: None)()
            active_player_id = str(getattr(active_player, "id", "") or "").strip()
            if current_player_id and active_player_id and active_player_id != current_player_id:
                return False
            current_phase = str(getattr(getattr(game_obj, "phase", None), "name", "") or "").strip().upper()
            if current_phase and current_phase != "CHARGE_PHASE":
                return False
        for source_root in list(self._iter_army_roots() or []):
            if source_root is None:
                continue
            sr = getattr(source_root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get("tyranids_subterranean_swarming_assault_active", False)):
                continue
            owner_id = str(sr.get("tyranids_subterranean_swarming_assault_turn_owner", "") or "").strip()
            if current_player_id and owner_id and owner_id != current_player_id:
                continue
            if game_obj is not None:
                current_turn = int(getattr(game_obj, "turn", 0) or 0)
                effect_turn = int(sr.get("tyranids_subterranean_swarming_assault_turn", 0) or 0)
                if current_turn and effect_turn and effect_turn != current_turn:
                    continue
            if not self._unit_on_battlefield(source_root):
                continue
            if unit_within_range_of_unit(source_root, root, 6.0, use_attached_aggregate=True):
                return True
        return False

    def subterranean_assault_arrival_marker_for_positions(
        self,
        unit,
        placements: list[tuple[float, float, float, float]],
        *,
        game=None,
        allowed_marker_ids: tuple[str, ...] = (),
        excluded_marker_ids: tuple[str, ...] = (),
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
        allowed = {str(item or "").strip() for item in tuple(allowed_marker_ids or ()) if str(item or "").strip()}
        excluded = {str(item or "").strip() for item in tuple(excluded_marker_ids or ()) if str(item or "").strip()}
        for marker in list(self.get_active_tunnel_markers() or []):
            marker_id = str(getattr(marker, "marker_id", "") or "").strip()
            if allowed and marker_id not in allowed:
                continue
            if excluded and marker_id in excluded:
                continue
            if self._placements_wholly_within_tunnel_marker(
                root,
                list(placements),
                marker=marker,
                max_distance=_TUNNEL_MARKER_HORIZONTAL_RANGE,
            ):
                return marker
        return None

    def _hunting_grounds_bearer_on_battlefield(self):
        if not self.is_vanguard_onslaught():
            return None
        for candidate in list(self._iter_army_roots() or []):
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
                    "enhancement_hunting_grounds",
                    enhancement_id="000008417002",
                    enhancement_name="Hunting Grounds",
                )
            ):
                continue
            return candidate_root
        return None

    def _maybe_apply_hunting_grounds(
        self,
        *,
        unit=None,
        game=None,
        set_up_as_reinforcements: bool = False,
    ) -> None:
        if not bool(set_up_as_reinforcements):
            return
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        enemy_root = self._unit_root(unit)
        if enemy_root is None:
            return
        if self._unit_in_army(enemy_root):
            return
        if not self._unit_on_battlefield(enemy_root):
            return
        bearer_root = self._hunting_grounds_bearer_on_battlefield()
        if bearer_root is None:
            return
        take_test = getattr(enemy_root, "take_battle_shock_test", None)
        if not callable(take_test):
            return
        try:
            roll = int(get_roll("D6") or 0)
        except Exception:
            roll = 0
        if int(roll) < 2:
            return
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        take_test(current_turn=max(1, int(current_turn)))

    def on_unit_set_up(self, *, unit=None, game=None, set_up_as_reinforcements: bool = False) -> None:
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        root = self._unit_root(unit)
        if root is None:
            return
        self._maybe_apply_hunting_grounds(
            unit=root,
            game=game,
            set_up_as_reinforcements=bool(set_up_as_reinforcements),
        )
        if not self.is_subterranean_assault():
            return
        if not bool(set_up_as_reinforcements):
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

    def _resolve_battle_round(self, *, game=None, battle_round: Optional[int] = None) -> Optional[int]:
        if battle_round is not None:
            try:
                return int(battle_round)
            except Exception:
                return None
        if game is None:
            return None
        try:
            return int(getattr(game, "turn", 0) or 0)
        except Exception:
            return None

    def _army_has_synaptic_imperatives(self) -> bool:
        return self.is_synaptic_nexus()

    def get_available_synaptic_imperatives(self) -> list[SynapticImperative]:
        if not self._army_has_synaptic_imperatives():
            return []
        used_keys = {
            str(key or "").strip().upper()
            for key in list(self.synaptic_imperatives_used_keys or [])
            if str(key or "").strip()
        }
        return [imperative for imperative in SYNAPTIC_IMPERATIVES if imperative.key not in used_keys]

    def get_active_synaptic_imperative(
        self,
        *,
        game=None,
        battle_round: Optional[int] = None,
    ) -> Optional[SynapticImperative]:
        if not self._army_has_synaptic_imperatives():
            return None
        key = str(self.active_synaptic_imperative_key or "").strip().upper()
        if not key:
            return None
        imperative = SYNAPTIC_IMPERATIVE_BY_KEY.get(key)
        if imperative is None:
            return None
        active_round = self.synaptic_imperative_active_round
        if active_round is not None:
            round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
            if round_value is not None and int(active_round) != int(round_value):
                return None
        return imperative

    def can_select_synaptic_imperative(self, *, game=None, battle_round: Optional[int] = None) -> bool:
        if not self._army_has_synaptic_imperatives():
            return False
        round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
        if round_value is None:
            return False
        if self.synaptic_imperative_resolved_round is not None and int(self.synaptic_imperative_resolved_round) == int(round_value):
            return False
        return bool(self.get_available_synaptic_imperatives())

    def select_synaptic_imperative(self, imperative, *, battle_round: Optional[int] = None) -> bool:
        if not self._army_has_synaptic_imperatives():
            return False
        round_value = self._resolve_battle_round(battle_round=battle_round)
        if round_value is None:
            return False
        if self.synaptic_imperative_resolved_round is not None and int(self.synaptic_imperative_resolved_round) == int(round_value):
            return False
        key = getattr(imperative, "key", imperative)
        key = str(key or "").strip().upper()
        if not key:
            self.active_synaptic_imperative_key = None
            self.synaptic_imperative_active_round = int(round_value)
            self.synaptic_imperative_resolved_round = int(round_value)
            return True
        if key not in SYNAPTIC_IMPERATIVE_BY_KEY:
            return False
        used_keys = {
            str(entry or "").strip().upper()
            for entry in list(self.synaptic_imperatives_used_keys or [])
            if str(entry or "").strip()
        }
        if key in used_keys:
            return False
        self.active_synaptic_imperative_key = key
        self.synaptic_imperative_active_round = int(round_value)
        self.synaptic_imperative_resolved_round = int(round_value)
        if key not in used_keys:
            self.synaptic_imperatives_used_keys.append(key)
        return True

    def _pending_synaptic_imperative_request(self, game, *, army_id: str, battle_round: int):
        if game is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != "synaptic_imperatives":
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id):
                continue
            if int(ctx.get("battle_round", 0) or 0) != int(battle_round):
                continue
            return req
        return None

    def _build_synaptic_imperative_request(self, game, player, battle_round: int):
        if game is None:
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.entity_ids import get_entity_id

        options = list(self.get_available_synaptic_imperatives() or [])
        if not options:
            return None
        army = self.army
        army_id = get_entity_id(army) if army is not None else None
        req_options = [
            DecisionOption.create(
                "None",
                payload={
                    "action": "skip",
                    "choice_key": "",
                    "army_id": army_id,
                    "battle_round": int(battle_round),
                },
            )
        ]
        choice_keys: list[str] = []
        for imperative in options:
            choice_keys.append(str(imperative.key))
            req_options.append(
                DecisionOption.create(
                    imperative.name,
                    payload={
                        "choice_key": str(imperative.key),
                        "summary": str(imperative.summary),
                        "army_id": army_id,
                        "battle_round": int(battle_round),
                    },
                )
            )
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Select Synaptic Imperative.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={
                "ability": "synaptic_imperatives",
                "ability_name": "Synaptic Imperatives",
                "army_id": army_id,
                "battle_round": int(battle_round),
                "allowed_choice_keys": list(choice_keys),
                "optional": True,
            },
        )

    def _queue_synaptic_imperatives_request(self, battle_round: int, *, game=None) -> None:
        if not self._army_has_synaptic_imperatives():
            return
        if game is None:
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        if self.synaptic_imperative_resolved_round is not None and int(self.synaptic_imperative_resolved_round) == int(battle_round):
            return
        if not self.get_available_synaptic_imperatives():
            self.synaptic_imperative_resolved_round = int(battle_round)
            return
        player = getattr(self.army, "player", None) if self.army is not None else None
        if player is None:
            return
        army_id = str(get_entity_id(self.army) or "") if self.army is not None else ""
        if self._pending_synaptic_imperative_request(game, army_id=army_id, battle_round=int(battle_round)):
            return
        request = self._build_synaptic_imperative_request(game, player, int(battle_round))
        if request is None:
            return
        if hasattr(game, "request_decision"):
            game.request_decision(request)

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
        br = self._resolve_battle_round(game=game, battle_round=battle_round)
        if br is None:
            return
        if self.synaptic_imperative_active_round is not None and int(self.synaptic_imperative_active_round) != int(br):
            self.active_synaptic_imperative_key = None
            self.synaptic_imperative_active_round = None
        self._queue_synaptic_imperatives_request(int(br), game=game)

        if self.is_unending_swarm():
            if int(br) == 1:
                self._queue_naturalised_camouflage_selection_requests(game=game, battle_round=int(br))
            else:
                self._clear_naturalised_camouflage_effects()

        if not self._army_has_hyper_adaptations():
            return
        if int(br) != 1:
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
        request = self._build_hyper_adaptation_request(game, player, int(br))
        if request is None:
            return
        if hasattr(game, "request_decision"):
            game.request_decision(request)
