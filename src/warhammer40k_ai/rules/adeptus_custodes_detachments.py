from __future__ import annotations

from typing import Iterable, Optional

from ..utility import aura_utils
from ..utility.entity_ids import maybe_entity_id
from .detachment_manager import DetachmentManagerBase


class AdeptusCustodesDetachmentManager(DetachmentManagerBase):
    faction_id = "AC"

    _AGAINST_ALL_ODDS_RANGE = 6.0
    _ASSEMBLAGE_OF_MIGHT_SOURCE = "Assemblage of Might"
    _AURIC_ARMOUR_SOURCE = "Auric Armour"
    _AURIC_ARMOUR_WALKER_SELECTION_ABILITY = "solar_spearhead_walker_character_selection"
    _CREEPING_DREAD_RANGE = 12.0
    _CREEPING_DREAD_SOURCE = "Creeping Dread"
    _MARTIAL_MASTERY_SOURCE = "Martial Mastery"
    _REVERED_COMPANIONS_SOURCE = "Revered Companions"
    _REVERED_COMPANIONS_RANGE = 6.0
    _REVERED_COMPANIONS_FNP_CONDITION = "against psychic attacks and mortal wounds"

    def __init__(self, army=None):
        super().__init__(army=army)
        self.assemblage_of_might_target_unit_id: str = ""
        self.assemblage_of_might_target_name: str = ""
        self.martial_mastery_mode: str = ""
        self.martial_mastery_active_round: Optional[int] = None
        self.martial_mastery_resolved_round: Optional[int] = None
        self.solar_spearhead_character_walker_unit_ids: tuple[str, ...] = tuple()
        self._solar_spearhead_walker_selection_resolved: bool = False

    def is_lions_of_the_emperor(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Lions of the Emperor")

    def is_auric_champions(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Auric Champions")

    def is_null_maiden_vigil(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Null Maiden Vigil")

    def is_shield_host(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Shield Host")

    def is_solar_spearhead(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Solar Spearhead")

    def is_talons_of_the_emperor(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Talons Of The Emperor")

    @staticmethod
    def _add_keyword_once(entity, keyword: str) -> None:
        if entity is None:
            return
        key = str(keyword or "").strip()
        if not key:
            return
        keywords = list(getattr(entity, "keywords", []) or [])
        if any(str(value or "").strip().lower() == key.lower() for value in keywords):
            return
        keywords.append(key)
        entity.keywords = keywords

    def _model_in_army(self, model) -> bool:
        if model is None or self.army is None:
            return False
        unit = getattr(model, "parent_unit", None)
        if unit is None or not hasattr(unit, "get_parent_army"):
            return False
        return unit.get_parent_army() is self.army

    def _model_is_custodes(self, model) -> bool:
        if model is None:
            return False
        unit = getattr(model, "parent_unit", None)
        return self._unit_has_keyword_or_faction(unit, "ADEPTUS CUSTODES", faction_id=self.faction_id)

    def _unit_is_vehicle(self, unit) -> bool:
        if unit is None:
            return False
        if bool(getattr(unit, "is_vehicle", False)):
            return True
        return self._unit_has_keyword(unit, "VEHICLE")

    def _unit_is_aircraft(self, unit) -> bool:
        if unit is None:
            return False
        if bool(getattr(unit, "is_aircraft", False)):
            return True
        return self._unit_has_keyword(unit, "AIRCRAFT")

    def _unit_is_walker(self, unit) -> bool:
        if unit is None:
            return False
        if bool(getattr(unit, "is_walker", False)):
            return True
        return self._unit_has_keyword(unit, "WALKER")

    def _root_unit(self, unit):
        if unit is None:
            return None
        if hasattr(unit, "get_attached_unit_root"):
            return unit.get_attached_unit_root()
        return unit

    def _unit_in_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        if not callable(get_parent_army):
            return False
        return get_parent_army() is self.army

    def _unit_is_character_unit(self, unit) -> bool:
        root = self._root_unit(unit)
        if root is None:
            return False
        if self._unit_has_keyword(root, "CHARACTER"):
            return True
        members = []
        get_members = getattr(root, "get_attached_unit_members", None)
        if callable(get_members):
            members = list(get_members() or [])
        if not members:
            members = [root] + list(getattr(root, "attached_leaders", []) or [])
        for member in list(members or []):
            if member is None:
                continue
            if self._unit_has_keyword(member, "CHARACTER"):
                return True
        return False

    def _unit_is_custodes(self, unit) -> bool:
        root = self._root_unit(unit)
        if root is None:
            return False
        return self._unit_has_keyword_or_faction(root, "ADEPTUS CUSTODES", faction_id=self.faction_id)

    def _unit_is_custodes_vehicle(self, unit) -> bool:
        root = self._root_unit(unit)
        if root is None:
            return False
        if not self._unit_is_custodes(root):
            return False
        return self._unit_is_vehicle(root)

    @staticmethod
    def _unit_is_below_starting_strength(unit) -> bool:
        if unit is None:
            return False
        checker = getattr(unit, "is_below_starting_strength", None)
        if not callable(checker):
            return False
        return bool(checker())

    @staticmethod
    def _unit_is_below_half_strength(unit) -> bool:
        if unit is None:
            return False
        checker = getattr(unit, "is_below_half_strength", None)
        if not callable(checker):
            return False
        return bool(checker())

    @staticmethod
    def _unit_is_battle_shocked(unit) -> bool:
        if unit is None:
            return False
        checker = getattr(unit, "is_battle_shocked", None)
        if not callable(checker):
            return False
        return bool(checker())

    def _unit_key(self, unit) -> Optional[str]:
        if unit is None:
            return None
        return maybe_entity_id(unit) or str(id(unit))

    def _iter_army_roots(self, army) -> list:
        if army is None:
            return []
        out: list = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._root_unit(unit)
            if root is None:
                continue
            root_id = str(maybe_entity_id(root) or id(root))
            if root_id in seen:
                continue
            seen.add(root_id)
            out.append(root)
        out.sort(key=lambda unit: str(maybe_entity_id(unit) or id(unit)))
        return out

    def _unit_is_active(self, unit) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        if not bool(getattr(unit, "deployed", True)):
            return False
        reserve_status = str(getattr(unit, "reserve_status", "deployed") or "deployed").strip().lower()
        if reserve_status != "deployed":
            return False
        is_in_reserves = getattr(unit, "is_in_reserves", None)
        if callable(is_in_reserves) and bool(is_in_reserves()):
            return False
        if bool(getattr(unit, "embarked_in", None)) or bool(getattr(unit, "is_embarked", False)):
            return False
        return True

    def _resolve_game_map(self, *, game=None, game_map=None):
        if game_map is not None:
            return game_map
        if game is not None:
            resolved = getattr(game, "map", None)
            if resolved is not None:
                return resolved
        player = getattr(self.army, "player", None) if self.army is not None else None
        game_obj = getattr(player, "game", None) if player is not None else None
        return getattr(game_obj, "map", None) if game_obj is not None else None

    def _iter_unique_friendly_roots(self, unit, game_map) -> Iterable:
        if unit is None or game_map is None or not hasattr(game_map, "get_friendly_units"):
            return ()
        source_root = self._root_unit(unit)
        source_key = self._unit_key(source_root)
        seen = {source_key} if source_key else set()
        for friendly in list(game_map.get_friendly_units(source_root) or []):
            root = self._root_unit(friendly)
            if root is source_root:
                continue
            key = self._unit_key(root)
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            if root is not None:
                yield root

    def _has_other_friendly_within_range(self, unit, *, radius: float, game_map) -> bool:
        source_root = self._root_unit(unit)
        if source_root is None or game_map is None:
            return False
        for other_root in self._iter_unique_friendly_roots(source_root, game_map):
            if aura_utils.unit_within_range_of_unit(
                source_root,
                other_root,
                radius,
                use_attached_aggregate=True,
            ):
                return True
        return False

    def against_all_odds_applies(self, model, target_unit=None, *, game=None, game_map=None) -> bool:
        if not self.is_lions_of_the_emperor():
            return False
        if model is None:
            return False
        if not self._model_in_army(model):
            return False
        if not self._model_is_custodes(model):
            return False
        unit = getattr(model, "parent_unit", None)
        if unit is None or self._unit_is_vehicle(unit):
            return False
        resolved_map = self._resolve_game_map(game=game, game_map=game_map)
        if resolved_map is None:
            return False
        return not self._has_other_friendly_within_range(
            unit,
            radius=self._AGAINST_ALL_ODDS_RANGE,
            game_map=resolved_map,
        )

    def against_all_odds_hit_bonus(self, model, target_unit=None, *, game=None, game_map=None) -> int:
        if not self.against_all_odds_applies(model, target_unit, game=game, game_map=game_map):
            return 0
        return 1

    def against_all_odds_wound_bonus(self, model, target_unit=None, *, game=None, game_map=None) -> int:
        if not self.against_all_odds_applies(model, target_unit, game=game, game_map=game_map):
            return 0
        return 1

    def clear_assemblage_of_might_target(self) -> None:
        self.assemblage_of_might_target_unit_id = ""
        self.assemblage_of_might_target_name = ""
        if self.army is not None:
            setattr(self.army, "assemblage_of_might_target_unit_id", "")
            setattr(self.army, "assemblage_of_might_target_name", "")

    def set_assemblage_of_might_target(self, target_unit) -> bool:
        if target_unit is None:
            return False
        root = self._root_unit(target_unit)
        if root is None:
            return False
        rid = str(maybe_entity_id(root) or "").strip()
        if not rid:
            return False
        self.assemblage_of_might_target_unit_id = rid
        self.assemblage_of_might_target_name = str(getattr(root, "name", "") or "")
        if self.army is not None:
            setattr(self.army, "assemblage_of_might_target_unit_id", self.assemblage_of_might_target_unit_id)
            setattr(self.army, "assemblage_of_might_target_name", self.assemblage_of_might_target_name)
        return True

    def is_assemblage_of_might_target(self, target_unit) -> bool:
        if target_unit is None:
            return False
        target_id = str(self.assemblage_of_might_target_unit_id or "").strip()
        if not target_id:
            return False
        root = self._root_unit(target_unit)
        if root is None:
            return False
        rid = str(maybe_entity_id(root) or "").strip()
        return bool(rid) and rid == target_id

    def _assemblage_of_might_attacker_eligible(self, attacker_model) -> bool:
        if not self.is_auric_champions():
            return False
        if attacker_model is None:
            return False
        if not self._model_in_army(attacker_model):
            return False
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        root = self._root_unit(attacker_unit)
        if root is None:
            return False
        if not self._unit_has_keyword_or_faction(root, "ADEPTUS CUSTODES", faction_id=self.faction_id):
            return False
        return self._unit_is_character_unit(root)

    def assemblage_of_might_wound_bonus(
        self,
        attacker_model,
        target_unit,
        *,
        game=None,
        weapon_profile=None,
        attack_instance=None,
    ) -> int:
        del game
        del weapon_profile
        del attack_instance
        if not self._assemblage_of_might_attacker_eligible(attacker_model):
            return 0
        if not self.is_assemblage_of_might_target(target_unit):
            return 0
        return 1

    def _unit_is_anathema_psykana(self, unit) -> bool:
        root = self._root_unit(unit)
        if root is None:
            return False
        if self._unit_has_keyword(root, "ANATHEMA PSYKANA"):
            return True
        members = []
        get_members = getattr(root, "get_attached_unit_members", None)
        if callable(get_members):
            members = list(get_members() or [])
        if not members:
            members = [root] + list(getattr(root, "attached_leaders", []) or [])
        for member in list(members or []):
            if member is None:
                continue
            if self._unit_has_keyword(member, "ANATHEMA PSYKANA"):
                return True
        return False

    def _model_is_anathema_psykana(self, model) -> bool:
        if model is None:
            return False
        unit = getattr(model, "parent_unit", None)
        if self._unit_is_anathema_psykana(unit):
            return True
        has_any_keyword = getattr(model, "has_any_keyword", None)
        if callable(has_any_keyword) and bool(has_any_keyword("ANATHEMA PSYKANA")):
            return True
        has_keyword = getattr(model, "has_keyword", None)
        return bool(callable(has_keyword) and has_keyword("ANATHEMA PSYKANA"))

    def _active_anathema_psykana_models(self) -> list:
        if self.army is None:
            return []
        out: list = []
        seen: set[str] = set()
        for root in self._iter_army_roots(self.army):
            if not self._unit_is_active(root):
                continue
            if not self._unit_is_anathema_psykana(root):
                continue
            get_models = getattr(root, "get_attached_unit_models", None)
            if callable(get_models):
                models = list(get_models() or [])
            else:
                models = list(getattr(root, "models", []) or [])
            models.sort(key=lambda model: str(maybe_entity_id(model) or id(model)))
            for model in models:
                if model is None or not bool(getattr(model, "is_alive", False)):
                    continue
                if not self._model_is_anathema_psykana(model):
                    continue
                model_id = str(maybe_entity_id(model) or id(model))
                if model_id in seen:
                    continue
                seen.add(model_id)
                out.append(model)
        out.sort(key=lambda model: str(maybe_entity_id(model) or id(model)))
        return out

    def _active_friendly_roots(self) -> list:
        if self.army is None:
            return []
        out: list = []
        for root in self._iter_army_roots(self.army):
            if not self._unit_is_active(root):
                continue
            out.append(root)
        return out

    def _revered_companions_target_unit(self, model_or_unit):
        if not self.is_talons_of_the_emperor():
            return None
        if model_or_unit is None:
            return None
        unit = getattr(model_or_unit, "parent_unit", None)
        if unit is None:
            unit = model_or_unit
        root = self._root_unit(unit)
        if root is None:
            return None
        if not self._unit_in_army(root):
            return None
        if not self._unit_is_custodes(root):
            return None
        return root

    def revered_companions_null_aegis_fnp(
        self,
        unit,
        *,
        target_model=None,
        game=None,
        game_map=None,
    ) -> tuple[int, str, str]:
        del target_model
        del game
        del game_map
        target_root = self._revered_companions_target_unit(unit)
        if target_root is None:
            return 0, "", ""
        for source_root in self._active_friendly_roots():
            if source_root is None:
                continue
            if not self._unit_is_anathema_psykana(source_root):
                continue
            if not aura_utils.unit_within_range_of_unit(
                source_root,
                target_root,
                self._REVERED_COMPANIONS_RANGE,
                use_attached_aggregate=True,
            ):
                continue
            return 5, self._REVERED_COMPANIONS_FNP_CONDITION, self._REVERED_COMPANIONS_SOURCE
        return 0, "", ""

    def revered_companions_deadly_unity_hit_bonus(
        self,
        attacker_model,
        target_unit=None,
        *,
        game=None,
        game_map=None,
    ) -> tuple[int, str]:
        del target_unit
        del game
        del game_map
        if not self.is_talons_of_the_emperor():
            return 0, ""
        if attacker_model is None:
            return 0, ""
        if not self._model_in_army(attacker_model):
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = self._root_unit(attacker_unit)
        if attacker_root is None:
            return 0, ""
        if not self._unit_in_army(attacker_root):
            return 0, ""
        if not self._unit_is_active(attacker_root):
            return 0, ""
        if not self._unit_is_anathema_psykana(attacker_root):
            return 0, ""
        for source_root in self._active_friendly_roots():
            if source_root is None or source_root is attacker_root:
                continue
            if not self._unit_is_custodes(source_root):
                continue
            if self._unit_is_anathema_psykana(source_root):
                continue
            if not aura_utils.unit_within_range_of_unit(
                source_root,
                attacker_root,
                self._REVERED_COMPANIONS_RANGE,
                use_attached_aggregate=True,
            ):
                continue
            return 1, self._REVERED_COMPANIONS_SOURCE
        return 0, ""

    def _solar_spearhead_walker_candidates(self) -> list:
        if not self.is_solar_spearhead():
            return []
        if self.army is None:
            return []
        out: list = []
        seen: set[str] = set()
        for root in self._iter_army_roots(self.army):
            if root is None:
                continue
            unit_id = str(maybe_entity_id(root) or "").strip()
            if not unit_id or unit_id in seen:
                continue
            if not self._unit_in_army(root):
                continue
            if not self._unit_is_custodes(root):
                continue
            if not self._unit_is_walker(root):
                continue
            out.append(root)
            seen.add(unit_id)
        out.sort(key=lambda unit: str(maybe_entity_id(unit) or ""))
        return out

    def _pending_solar_spearhead_walker_request(self, game, *, army_id: str) -> bool:
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
            ability = str(ctx.get("ability", "") or "").strip().lower()
            if ability != self._AURIC_ARMOUR_WALKER_SELECTION_ABILITY:
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id or ""):
                continue
            return True
        return False

    def queue_solar_spearhead_walker_character_selection_request(self, *, game=None, player=None) -> None:
        if not self.is_solar_spearhead():
            return
        if self.army is None:
            return
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        if self._solar_spearhead_walker_selection_resolved:
            return

        from ..engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
        from ..engine.decisions import DecisionOption, DecisionRequest

        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return
        candidates = list(self._solar_spearhead_walker_candidates() or [])
        if not candidates:
            self._solar_spearhead_walker_selection_resolved = True
            return

        army_id = str(maybe_entity_id(self.army) or "")
        if self._pending_solar_spearhead_walker_request(game, army_id=army_id):
            return

        candidate_ids = [str(maybe_entity_id(unit) or "") for unit in candidates if str(maybe_entity_id(unit) or "")]
        if not candidate_ids:
            self._solar_spearhead_walker_selection_resolved = True
            return

        request = DecisionRequest.create(
            DECISION_SELECT_REALM_OF_CHAOS_UNITS,
            "Auric Armour: select up to two ADEPTUS CUSTODES WALKER models to gain CHARACTER.",
            player_id=getattr(owner, "id", None),
            options=[
                DecisionOption.create("Confirm", payload={"action": "confirm"}),
                DecisionOption.create("None", payload={"action": "skip"}),
            ],
            context={
                "army_id": army_id,
                "ability": self._AURIC_ARMOUR_WALKER_SELECTION_ABILITY,
                "ability_name": self._AURIC_ARMOUR_SOURCE,
                "phase": "Muster Armies step",
                "max_units": 2,
                "allowed_unit_ids": list(candidate_ids),
                "title": self._AURIC_ARMOUR_SOURCE,
                "subtitle": "Select up to two ADEPTUS CUSTODES WALKER models.",
                "instruction": "Selected WALKER units gain the CHARACTER keyword.",
                "skip_label": "None (do not select WALKER units)",
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)

    def solar_spearhead_walker_selection_is_valid(self, unit_ids, *, game=None) -> tuple[bool, str]:
        del game
        if not self.is_solar_spearhead():
            return False, "Auric Armour is not active for this army."
        if unit_ids is None:
            return True, ""
        if not isinstance(unit_ids, list):
            return False, "Auric Armour selection requires unit_ids."
        unique_ids = sorted({str(unit_id or "").strip() for unit_id in list(unit_ids or []) if str(unit_id or "").strip()})
        if len(unique_ids) > 2:
            return False, "Auric Armour can select at most two WALKER units."
        candidates = {
            str(maybe_entity_id(unit) or ""): unit
            for unit in list(self._solar_spearhead_walker_candidates() or [])
            if str(maybe_entity_id(unit) or "")
        }
        for unit_id in unique_ids:
            if unit_id not in candidates:
                return False, "Auric Armour selection contains an ineligible unit."
        return True, ""

    def apply_solar_spearhead_walker_character_selection(self, unit_ids, *, game=None) -> list[str]:
        selected = list(unit_ids or [])
        valid, _reason = self.solar_spearhead_walker_selection_is_valid(selected, game=game)
        if not valid:
            return []
        candidate_by_id = {
            str(maybe_entity_id(unit) or ""): unit
            for unit in list(self._solar_spearhead_walker_candidates() or [])
            if str(maybe_entity_id(unit) or "")
        }
        applied_ids: list[str] = []
        selected_ids = sorted({str(unit_id or "").strip() for unit_id in list(selected or []) if str(unit_id or "").strip()})
        for unit_id in selected_ids:
            root = candidate_by_id.get(unit_id)
            if root is None:
                continue
            self._add_keyword_once(root, "Character")
            for model in list(getattr(root, "models", []) or []):
                self._add_keyword_once(model, "Character")
            applied_ids.append(unit_id)
        self.solar_spearhead_character_walker_unit_ids = tuple(applied_ids)
        if self.army is not None:
            setattr(self.army, "solar_spearhead_character_walker_unit_ids", list(applied_ids))
        self._solar_spearhead_walker_selection_resolved = True
        return list(applied_ids)

    def _auric_armour_vehicle_unit(self, model_or_unit):
        if not self.is_solar_spearhead():
            return None
        if model_or_unit is None:
            return None
        unit = getattr(model_or_unit, "parent_unit", None)
        if unit is None:
            unit = model_or_unit
        root = self._root_unit(unit)
        if root is None:
            return None
        if not self._unit_in_army(root):
            return None
        if not self._unit_is_custodes_vehicle(root):
            return None
        return root

    def _auric_armour_walker_unit(self, model_or_unit):
        if not self.is_solar_spearhead():
            return None
        if model_or_unit is None:
            return None
        unit = getattr(model_or_unit, "parent_unit", None)
        if unit is None:
            unit = model_or_unit
        root = self._root_unit(unit)
        if root is None:
            return None
        if not self._unit_in_army(root):
            return None
        if not self._unit_is_custodes(root):
            return None
        if not self._unit_is_walker(root):
            return None
        return root

    def auric_armour_objective_control_bonus(self, model, *, unit=None) -> tuple[int, str]:
        if unit is None:
            unit = getattr(model, "parent_unit", None)
        root = self._auric_armour_vehicle_unit(unit)
        if root is None:
            return 0, ""
        if self._unit_is_aircraft(root):
            return 0, ""
        if self._unit_is_battle_shocked(root):
            return 0, ""
        if self._unit_is_below_starting_strength(root):
            return 0, ""
        return 2, self._AURIC_ARMOUR_SOURCE

    def auric_armour_hit_reroll_ones(self, attacker_model, target_unit=None, *, game=None, weapon_profile=None, attack_instance=None) -> tuple[bool, str]:
        del target_unit
        del game
        del weapon_profile
        del attack_instance
        root = self._auric_armour_vehicle_unit(attacker_model)
        if root is None:
            return False, ""
        if not self._unit_is_below_starting_strength(root):
            return False, ""
        return True, self._AURIC_ARMOUR_SOURCE

    def auric_armour_wound_reroll_ones(self, attacker_model, target_unit=None, *, game=None, weapon_profile=None, attack_instance=None) -> tuple[bool, str]:
        del target_unit
        del game
        del weapon_profile
        del attack_instance
        root = self._auric_armour_vehicle_unit(attacker_model)
        if root is None:
            return False, ""
        if not self._unit_is_below_half_strength(root):
            return False, ""
        return True, self._AURIC_ARMOUR_SOURCE

    def auric_armour_move_bonus(self, model, *, unit=None) -> tuple[int, str]:
        if unit is None:
            unit = getattr(model, "parent_unit", None)
        if self._auric_armour_walker_unit(unit) is None:
            return 0, ""
        return 2, self._AURIC_ARMOUR_SOURCE

    def auric_armour_advance_roll_bonus(self, unit, *, game=None) -> tuple[int, str]:
        del game
        if self._auric_armour_walker_unit(unit) is None:
            return 0, ""
        return 1, self._AURIC_ARMOUR_SOURCE

    def auric_armour_charge_roll_bonus(self, unit, *, target_units=None, game=None) -> tuple[int, str]:
        del target_units
        del game
        if self._auric_armour_walker_unit(unit) is None:
            return 0, ""
        return 1, self._AURIC_ARMOUR_SOURCE

    def apply_creeping_dread_opponent_command_phase(self, *, game=None, current_player=None) -> list:
        if not self.is_null_maiden_vigil():
            return []
        if self.army is None:
            return []
        owner_player = getattr(self.army, "player", None)
        if owner_player is None or current_player is None or current_player is owner_player:
            return []
        get_army = getattr(current_player, "get_army", None)
        target_army = get_army() if callable(get_army) else None
        if target_army is None:
            return []

        source_models = self._active_anathema_psykana_models()
        if not source_models:
            return []

        try:
            turn = int(getattr(game, "turn", 0) or 1)
        except (TypeError, ValueError):
            turn = 1

        results: list[dict] = []
        for target_root in self._iter_army_roots(target_army):
            if not self._unit_is_active(target_root):
                continue
            is_psyker = self._unit_has_keyword(target_root, "PSYKER")
            is_below_starting = bool(getattr(target_root, "is_below_starting_strength", lambda: False)())
            if not (is_psyker or is_below_starting):
                continue
            in_range = any(
                aura_utils.model_within_range_of_unit(
                    source_model,
                    target_root,
                    self._CREEPING_DREAD_RANGE,
                    use_attached_aggregate=True,
                )
                for source_model in source_models
            )
            if not in_range:
                continue

            is_below_half = bool(getattr(target_root, "is_below_half_strength", lambda: False)())
            test_modifier = -1 if is_below_half else 0
            if test_modifier:
                special_rules = getattr(target_root, "special_rules", None)
                if not isinstance(special_rules, dict):
                    special_rules = {}
                current = int(special_rules.get("battle_shock_test_modifier", 0) or 0)
                special_rules["battle_shock_test_modifier"] = int(current + test_modifier)
                reasons = list(special_rules.get("battle_shock_test_modifier_reasons", []) or [])
                reasons.append(f"{self._CREEPING_DREAD_SOURCE}: -1 if Below Half-strength")
                special_rules["battle_shock_test_modifier_reasons"] = reasons
                target_root.special_rules = special_rules

            take_test = getattr(target_root, "take_battle_shock_test", None)
            if callable(take_test):
                take_test(int(turn or 1))
            results.append(
                {
                    "target_unit_id": str(maybe_entity_id(target_root) or ""),
                    "target_name": str(getattr(target_root, "name", "") or "Unit"),
                    "is_psyker": bool(is_psyker),
                    "below_starting_strength": bool(is_below_starting),
                    "below_half_strength": bool(is_below_half),
                    "battle_shock_test_modifier": int(test_modifier),
                }
            )
        return results

    def _assemblage_of_might_eligible_enemy_units(self, *, game=None, player=None) -> list:
        if not self.is_auric_champions():
            return []
        if game is None or player is None:
            return []
        get_enemy_units = getattr(game, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return []
        enemy_units = list(get_enemy_units(player) or [])
        if not enemy_units:
            return []

        out: list = []
        seen: set[str] = set()
        for enemy in enemy_units:
            root = self._root_unit(enemy)
            if root is None:
                continue
            rid = str(maybe_entity_id(root) or "").strip()
            if not rid or rid in seen:
                continue
            seen.add(rid)
            is_alive = getattr(root, "is_alive", None)
            if callable(is_alive) and not bool(is_alive()):
                continue
            if not bool(getattr(root, "deployed", True)):
                continue
            reserve_status = str(getattr(root, "reserve_status", "deployed") or "deployed").strip().lower()
            if reserve_status != "deployed":
                continue
            if bool(getattr(root, "embarked_in", None)) or bool(getattr(root, "is_embarked", False)):
                continue
            out.append(root)
        out.sort(key=lambda unit: str(maybe_entity_id(unit) or id(unit)))
        return out

    def _pending_assemblage_of_might_request(self, *, game=None, army_id: str = "", command_phase_owner_id: str = "") -> bool:
        queue = getattr(game, "decision_queue", None) if game is not None else None
        if queue is None or not hasattr(queue, "list"):
            return False
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != "assemblage_of_might":
                continue
            if army_id and str(ctx.get("army_id", "") or "") != str(army_id):
                continue
            if command_phase_owner_id and str(ctx.get("command_phase_owner_id", "") or "") != str(command_phase_owner_id):
                continue
            return True
        return False

    def build_assemblage_of_might_request(self, *, game=None, player=None):
        if not self.is_auric_champions():
            return None
        if game is None or player is None:
            return None
        if not bool(getattr(game, "is_authoritative", True)):
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        targets = self._assemblage_of_might_eligible_enemy_units(game=game, player=player)
        if not targets:
            return None

        army_id = str(maybe_entity_id(self.army) or "") if self.army is not None else ""
        player_id = str(getattr(player, "id", "") or "")
        if self._pending_assemblage_of_might_request(
            game=game,
            army_id=army_id,
            command_phase_owner_id=player_id,
        ):
            return None

        options = []
        for target in targets:
            target_id = str(maybe_entity_id(target) or "").strip()
            if not target_id:
                continue
            options.append(
                DecisionOption.create(
                    str(getattr(target, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": target_id},
                )
            )
        if not options:
            return None

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Assemblage of Might: select one enemy unit.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "assemblage_of_might",
                "ability_name": self._ASSEMBLAGE_OF_MIGHT_SOURCE,
                "army_id": army_id,
                "command_phase_owner_id": player_id,
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)
        return request

    def _resolve_battle_round(self, *, game=None, battle_round=None) -> Optional[int]:
        if battle_round is not None:
            try:
                return int(battle_round)
            except (TypeError, ValueError):
                return None
        if game is None:
            player = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(player, "game", None) if player is not None else None
        if game is None:
            return None
        try:
            return int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            return None

    def clear_martial_mastery(self) -> None:
        self.martial_mastery_mode = ""
        self.martial_mastery_active_round = None

    def get_martial_mastery_mode(self, *, game=None, battle_round: Optional[int] = None) -> str:
        if not self.is_shield_host():
            return ""
        mode = str(self.martial_mastery_mode or "").strip().upper()
        if not mode:
            return ""
        active_round = self.martial_mastery_active_round
        if active_round is None:
            return mode
        round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
        if round_value is None:
            return mode
        if int(active_round) != int(round_value):
            return ""
        return mode

    def can_select_martial_mastery(self, *, game=None, battle_round: Optional[int] = None) -> bool:
        if not self.is_shield_host():
            return False
        round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
        if round_value is None:
            return False
        resolved_round = self.martial_mastery_resolved_round
        if resolved_round is not None and int(resolved_round) == int(round_value):
            return False
        return True

    def select_martial_mastery(self, choice, *, battle_round: Optional[int] = None) -> bool:
        if not self.is_shield_host():
            return False
        round_value = self._resolve_battle_round(battle_round=battle_round)
        if round_value is None:
            return False
        if self.martial_mastery_resolved_round is not None and int(self.martial_mastery_resolved_round) == int(round_value):
            return False
        choice_key = str(choice or "").strip().upper()
        if choice_key in ("", "NONE", "SKIP"):
            self.martial_mastery_mode = ""
            self.martial_mastery_active_round = int(round_value)
            self.martial_mastery_resolved_round = int(round_value)
            return True
        normalized_choice = ""
        if choice_key in ("CRIT_5_PLUS", "CRIT5", "CRITICAL_HITS_5_PLUS", "CRITICALS"):
            normalized_choice = "CRIT_5_PLUS"
        elif choice_key in ("AP_PLUS_1", "AP1", "AP_PLUS_ONE"):
            normalized_choice = "AP_PLUS_1"
        if not normalized_choice:
            return False
        self.martial_mastery_mode = normalized_choice
        self.martial_mastery_active_round = int(round_value)
        self.martial_mastery_resolved_round = int(round_value)
        return True

    def _pending_martial_mastery_request(self, game, *, army_id: str, battle_round: int):
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
            if str(ctx.get("ability", "") or "").strip().lower() != "martial_mastery":
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id):
                continue
            if int(ctx.get("battle_round", 0) or 0) != int(battle_round):
                continue
            return req
        return None

    def build_martial_mastery_request(self, *, game=None, player=None, battle_round: Optional[int] = None):
        if not self.is_shield_host():
            return None
        if game is None or player is None:
            return None
        if not bool(getattr(game, "is_authoritative", True)):
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
        if round_value is None:
            return None
        if not self.can_select_martial_mastery(game=game, battle_round=round_value):
            return None
        army_id = str(maybe_entity_id(self.army) or "") if self.army is not None else ""
        if self._pending_martial_mastery_request(game, army_id=army_id, battle_round=int(round_value)):
            return None

        options = [
            DecisionOption.create(
                "None",
                payload={
                    "action": "skip",
                    "choice_key": "",
                    "army_id": army_id,
                    "battle_round": int(round_value),
                },
            ),
            DecisionOption.create(
                "Critical Hits on 5+ (Melee)",
                payload={
                    "choice_key": "CRIT_5_PLUS",
                    "army_id": army_id,
                    "battle_round": int(round_value),
                },
            ),
            DecisionOption.create(
                "+1 AP (Melee)",
                payload={
                    "choice_key": "AP_PLUS_1",
                    "army_id": army_id,
                    "battle_round": int(round_value),
                },
            ),
        ]

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Martial Mastery: select one mode for this battle round (or None).",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "martial_mastery",
                "ability_name": self._MARTIAL_MASTERY_SOURCE,
                "army_id": army_id,
                "battle_round": int(round_value),
                "allowed_choice_keys": ["CRIT_5_PLUS", "AP_PLUS_1"],
                "optional": True,
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)
        return request

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
        if round_value is None:
            return
        if (
            self.martial_mastery_active_round is not None
            and int(self.martial_mastery_active_round) != int(round_value)
        ):
            self.clear_martial_mastery()
        if not self.is_shield_host():
            self.martial_mastery_resolved_round = None
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        player = getattr(self.army, "player", None) if self.army is not None else None
        if player is None:
            return
        self.build_martial_mastery_request(game=game, player=player, battle_round=round_value)

    def _martial_mastery_attacker_eligible(self, attacker_model) -> bool:
        if attacker_model is None or not self.is_shield_host():
            return False
        if not self._model_in_army(attacker_model):
            return False
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._root_unit(unit)
        if root is None:
            return False
        if not self._unit_has_keyword_or_faction(root, "ADEPTUS CUSTODES", faction_id=self.faction_id):
            return False
        has_martial_katah = getattr(root, "attached_unit_has_martial_katah", None)
        return bool(callable(has_martial_katah) and has_martial_katah())

    def martial_mastery_crit_hit_threshold(self, attacker_model, *, game=None, weapon_profile=None) -> int:
        del weapon_profile
        if not self._martial_mastery_attacker_eligible(attacker_model):
            return 0
        mode = self.get_martial_mastery_mode(game=game)
        if mode != "CRIT_5_PLUS":
            return 0
        return 5

    def martial_mastery_melee_ap_bonus(self, attacker_model, target_unit=None, *, game=None, weapon_profile=None) -> int:
        del target_unit
        del weapon_profile
        if not self._martial_mastery_attacker_eligible(attacker_model):
            return 0
        mode = self.get_martial_mastery_mode(game=game)
        if mode != "AP_PLUS_1":
            return 0
        return 1

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        self.clear_assemblage_of_might_target()
        if self.army is None or player is None:
            return
        if player is not getattr(self.army, "player", None):
            return
        self.build_assemblage_of_might_request(game=game, player=player)
