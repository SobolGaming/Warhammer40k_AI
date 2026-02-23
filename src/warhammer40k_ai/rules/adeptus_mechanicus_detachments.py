from __future__ import annotations

import math
from itertools import combinations
from typing import Optional

from ..utility.dice import get_roll
from ..utility.entity_ids import get_entity_id
from .detachment_manager import DetachmentManagerBase


class AdeptusMechanicusDetachmentManager(DetachmentManagerBase):
    faction_id = "ADM"

    _COHORT_CYBERNETICA_NAME = "Cohort Cybernetica"
    _CYBER_PSALM_PROGRAMMING_SOURCE = "Cyber-Psalm Programming"
    _LEGIO_CYBERNETICA_KEYWORD = "LEGIO CYBERNETICA"
    _EXPLORATOR_MANIPLE_NAME = "Explorator Maniple"
    _ACQUISITION_ABILITY_KEY = "acquisition_at_any_cost"
    _ACQUISITION_SOURCE = "Acquisition At Any Cost"
    _HALOSCREED_BATTLE_CLADE_NAME = "Haloscreed Battle Clade"
    _NOOSPHERIC_UNITS_ABILITY_KEY = "noospheric_transference_units"
    _NOOSPHERIC_OVERRIDE_ABILITY_KEY = "noospheric_transference_override"
    _NOOSPHERIC_SOURCE = "Noospheric Transference"
    _NOOSPHERIC_ELECTROMOTIVE_KEY = "ELECTROMOTIVE_ENERGISATION"
    _NOOSPHERIC_MICROACTUATOR_KEY = "MICROACTUATOR_BRACING"
    _NOOSPHERIC_PREDATION_KEY = "PREDATION_PROTOCOLS"
    _NOOSPHERIC_MUTED_KEY = "MUTED_SERVOMOTORS"
    _NOOSPHERIC_ACTIVE_FLAG_KEY = "noospheric_transference_halo_override_active"
    _NOOSPHERIC_SOURCE_FLAG_KEY = "noospheric_transference_source"
    _NOOSPHERIC_OVERRIDE_FLAG_KEY = "noospheric_transference_override_key"
    _SKITARII_HUNTER_COHORT_NAME = "Skitarii Hunter Cohort"
    _STEALTH_OPTIMISATION_SOURCE = "Stealth Optimisation"
    _DATA_PSALM_CONCLAVE_NAME = "Data-Psalm Conclave"
    _DATA_PSALM_ABILITY_KEY = "data_psalm_benediction"
    _DATA_PSALM_SOURCE = "Benedictions Of The Omnissiah"
    _DATA_PSALM_PANEGYRIC_KEY = "PANEGYRIC_PROCESSION"
    _DATA_PSALM_CITATION_KEY = "CITATION_IN_SAVAGERY"
    _CULT_MECHANICUS_KEYWORD = "CULT MECHANICUS"

    _RAD_BOMBARDMENT_ABILITY_KEY = "rad_bombardment"
    _RAD_BOMBARDMENT_CHOICE_KEY = "rad_bombardment_choice"
    _RAD_BOMBARDMENT_TAKING_COVER_ROUND_KEY = "rad_bombardment_taking_cover_round"
    _RAD_BOMBARDMENT_TAKING_COVER_ADDED_KEY = "rad_bombardment_taking_cover_added_battleshock"
    _RAD_BOMBARDMENT_CHOICE_STAND_FIRM = "stand_firm"
    _RAD_BOMBARDMENT_CHOICE_TAKE_COVER = "take_cover"
    _RADIAL_SUFFUSION_FLAG_KEY = "enhancement_radial_suffusion"
    _RADIAL_SUFFUSION_ENHANCEMENT_ID = "000008385002"
    _RADIAL_SUFFUSION_ENHANCEMENT_NAME = "radial suffusion"
    _RADIAL_SUFFUSION_EXTRA_RANGE_IN = 6.0

    def __init__(self, army=None):
        super().__init__(army)
        self.active_acquisition_objective_id: str = ""
        self.acquisition_selected_round: int = 0
        self.active_noospheric_unit_ids: list[str] = []
        self.active_noospheric_override_key: str = ""
        self.noospheric_selected_round: int = 0
        self.active_data_psalm_benediction_key: Optional[str] = None
        self.data_psalm_selected_round: Optional[int] = None

    def is_rad_zone_corps(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Rad-Zone Corps")

    def is_data_psalm_conclave(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self._DATA_PSALM_CONCLAVE_NAME)

    def is_cohort_cybernetica(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self._COHORT_CYBERNETICA_NAME)

    def is_explorator_maniple(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self._EXPLORATOR_MANIPLE_NAME)

    def is_haloscreed_battle_clade(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self._HALOSCREED_BATTLE_CLADE_NAME)

    def is_skitarii_hunter_cohort(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self._SKITARII_HUNTER_COHORT_NAME)

    @classmethod
    def _normalize_data_psalm_choice_key(cls, choice_key: str) -> str:
        raw = str(choice_key or "").strip().upper()
        aliases = {
            "PANEGYRIC": cls._DATA_PSALM_PANEGYRIC_KEY,
            "PANEGYRIC_PROCESSION": cls._DATA_PSALM_PANEGYRIC_KEY,
            "CITATION": cls._DATA_PSALM_CITATION_KEY,
            "CITATION_IN_SAVAGERY": cls._DATA_PSALM_CITATION_KEY,
        }
        return aliases.get(raw, "")

    @classmethod
    def data_psalm_benedictions(cls) -> tuple[tuple[str, str], ...]:
        return (
            (cls._DATA_PSALM_PANEGYRIC_KEY, "Panegyric Procession"),
            (cls._DATA_PSALM_CITATION_KEY, "Citation in Savagery"),
        )

    def can_select_data_psalm_benediction(self, *, game=None, battle_round: Optional[int] = None) -> bool:
        if not self.is_data_psalm_conclave():
            return False
        if self.active_data_psalm_benediction_key:
            return False
        if battle_round is not None:
            try:
                return int(battle_round) == 1
            except (TypeError, ValueError):
                return False
        if game is None:
            return False
        try:
            return int(getattr(game, "turn", 0) or 0) == 1
        except (TypeError, ValueError):
            return False

    def select_data_psalm_benediction(self, choice_key: str, *, battle_round: Optional[int] = None) -> bool:
        if not self.can_select_data_psalm_benediction(battle_round=battle_round):
            return False
        normalized = self._normalize_data_psalm_choice_key(choice_key)
        if not normalized:
            return False
        self.active_data_psalm_benediction_key = normalized
        if battle_round is not None:
            try:
                self.data_psalm_selected_round = int(battle_round)
            except (TypeError, ValueError):
                self.data_psalm_selected_round = None
        return True

    def _data_psalm_benediction_active(self, choice_key: str) -> bool:
        if not self.is_data_psalm_conclave():
            return False
        if not self.active_data_psalm_benediction_key:
            return False
        return self.active_data_psalm_benediction_key == self._normalize_data_psalm_choice_key(choice_key)

    def _pending_data_psalm_benediction_request(self, game, army_id: str):
        if game is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "")) != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != self._DATA_PSALM_ABILITY_KEY:
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id or ""):
                continue
            return req
        return None

    def _build_data_psalm_benediction_request(self, game, *, battle_round: int):
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        if game is None:
            return None
        owner = getattr(self.army, "player", None)
        if owner is None:
            return None
        army_id = self._entity_id(self.army)
        options = [
            DecisionOption.create(
                label,
                payload={
                    "army_id": army_id,
                    "choice_key": key,
                },
            )
            for key, label in self.data_psalm_benedictions()
        ]
        if not options:
            return None
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Benedictions of the Omnissiah: select one Benediction to be active for the battle.",
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": self._DATA_PSALM_ABILITY_KEY,
                "ability_name": self._DATA_PSALM_SOURCE,
                "army_id": army_id,
                "battle_round": int(battle_round),
                "allowed_choice_keys": [key for key, _label in self.data_psalm_benedictions()],
                "optional": False,
            },
        )

    def _queue_data_psalm_benediction_request(self, game, *, battle_round: int) -> None:
        if not self.is_data_psalm_conclave():
            return
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        if not self.can_select_data_psalm_benediction(game=game, battle_round=battle_round):
            return
        army_id = self._entity_id(self.army)
        if self._pending_data_psalm_benediction_request(game, army_id) is not None:
            return
        request = self._build_data_psalm_benediction_request(game, battle_round=int(battle_round))
        request_decision = getattr(game, "request_decision", None)
        if callable(request_decision) and request is not None:
            request_decision(request)

    @staticmethod
    def _entity_id(entity) -> str:
        value = get_entity_id(entity)
        return str(value or "")

    @staticmethod
    def _attached_root(unit):
        if unit is None:
            return None
        getter = getattr(unit, "get_attached_unit_root", None)
        if callable(getter):
            root = getter()
            if root is not None:
                return root
        return unit

    @staticmethod
    def _is_model_alive(model) -> bool:
        alive_attr = getattr(model, "is_alive", True)
        return bool(alive_attr() if callable(alive_attr) else alive_attr)

    def _iter_unit_models(self, unit) -> list:
        if unit is None:
            return []
        get_models = getattr(unit, "get_attached_unit_models", None)
        if callable(get_models):
            models = list(get_models() or [])
        else:
            models = list(getattr(unit, "models", []) or [])
        return [model for model in models if model is not None and self._is_model_alive(model)]

    def _unit_in_army(self, unit) -> bool:
        root = self._attached_root(unit)
        if root is None:
            return False
        for own_unit in list(getattr(self.army, "units", []) or []):
            if self._attached_root(own_unit) is root:
                return True
        return False

    @staticmethod
    def _unit_is_battle_shocked(unit) -> bool:
        if unit is None:
            return False
        check = getattr(unit, "is_battle_shocked", None)
        return bool(check()) if callable(check) else False

    def _legio_cybernetica_root(self, unit):
        if not self.is_cohort_cybernetica():
            return None
        root = self._attached_root(unit)
        if root is None:
            return None
        if not self._unit_in_army(root):
            return None
        if not self._unit_has_keyword(root, self._LEGIO_CYBERNETICA_KEYWORD):
            return None
        return root

    def cyber_psalm_programming_movement_bonus(self, model, *, unit=None) -> tuple[int, str]:
        if model is None:
            return 0, ""
        source_unit = unit if unit is not None else getattr(model, "parent_unit", None)
        if self._legio_cybernetica_root(source_unit) is None:
            return 0, ""
        return 2, self._CYBER_PSALM_PROGRAMMING_SOURCE

    def cyber_psalm_programming_objective_control_bonus(self, model, *, unit=None) -> tuple[int, str]:
        if model is None:
            return 0, ""
        source_unit = unit if unit is not None else getattr(model, "parent_unit", None)
        root = self._legio_cybernetica_root(source_unit)
        if root is None:
            return 0, ""
        if self._unit_is_battle_shocked(root):
            return 0, ""
        return 1, self._CYBER_PSALM_PROGRAMMING_SOURCE

    def _data_psalm_cult_mechanicus_root(self, unit):
        if not self.is_data_psalm_conclave():
            return None
        root = self._attached_root(unit)
        if root is None:
            return None
        if not self._unit_in_army(root):
            return None
        if not self._unit_has_keyword(root, self._CULT_MECHANICUS_KEYWORD):
            return None
        return root

    @staticmethod
    def _weapon_is_attack_type(weapon_profile, attack_type: str) -> bool:
        if weapon_profile is None:
            return False
        parent = getattr(weapon_profile, "parent_wargear", None)
        if parent is None:
            return False
        checker = getattr(parent, f"is_{attack_type}", None)
        return bool(checker()) if callable(checker) else False

    @staticmethod
    def _weapon_effective_range_max(weapon_profile, attacker_model) -> float:
        if weapon_profile is None:
            return 0.0
        fn = getattr(weapon_profile, "_effective_range_max", None)
        if callable(fn):
            try:
                return float(fn(attacker_model) or 0.0)
            except (TypeError, ValueError):
                return 0.0
        range_obj = getattr(weapon_profile, "range", None)
        if range_obj is None:
            return 0.0
        try:
            return float(getattr(range_obj, "max", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _unit_made_charge_move_this_turn(self, unit, *, game=None) -> bool:
        root = self._attached_root(unit)
        if root is None:
            return False
        round_state = getattr(root, "round_state", None)
        if not bool(getattr(round_state, "charged_this_round", False)):
            return False
        charge_suppressed_fn = getattr(root, "charge_bonus_suppressed", None)
        if callable(charge_suppressed_fn) and bool(charge_suppressed_fn(game=game)):
            return False
        return True

    def data_psalm_panegyric_procession_ap_bonus(
        self,
        attacker_model,
        *,
        target_unit=None,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        if not self._data_psalm_benediction_active(self._DATA_PSALM_PANEGYRIC_KEY):
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        if not self._weapon_is_attack_type(weapon_profile, "ranged"):
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = self._data_psalm_cult_mechanicus_root(attacker_unit)
        if attacker_root is None:
            return 0, ""
        target_root = self._attached_root(target_unit)
        if target_root is None:
            return 0, ""
        if game is None:
            owner = getattr(self.army, "player", None)
            game = getattr(owner, "game", None) if owner is not None else None
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return 0, ""
        range_max = self._weapon_effective_range_max(weapon_profile, attacker_model)
        if range_max <= 0.0:
            return 0, ""
        distance_fn = getattr(game_map, "get_distance_between_units", None)
        if not callable(distance_fn):
            return 0, ""
        try:
            distance = float(distance_fn(attacker_root, target_root))
        except (TypeError, ValueError):
            return 0, ""
        if distance > (range_max / 2.0) + 1e-6:
            return 0, ""
        return 1, f"{self._DATA_PSALM_SOURCE} (Panegyric Procession)"

    def _data_psalm_citation_in_savagery_bonus(
        self,
        attacker_model,
        *,
        unit=None,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        if not self._data_psalm_benediction_active(self._DATA_PSALM_CITATION_KEY):
            return 0, ""
        if attacker_model is None:
            return 0, ""
        if not self._weapon_is_attack_type(weapon_profile, "melee"):
            return 0, ""
        source_unit = unit if unit is not None else getattr(attacker_model, "parent_unit", None)
        source_root = self._data_psalm_cult_mechanicus_root(source_unit)
        if source_root is None:
            return 0, ""
        if not self._unit_made_charge_move_this_turn(source_root, game=game):
            return 0, ""
        return 1, f"{self._DATA_PSALM_SOURCE} (Citation in Savagery)"

    def data_psalm_citation_in_savagery_melee_strength_bonus(
        self,
        attacker_model,
        *,
        unit=None,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        return self._data_psalm_citation_in_savagery_bonus(
            attacker_model,
            unit=unit,
            weapon_profile=weapon_profile,
            game=game,
        )

    def data_psalm_citation_in_savagery_melee_attacks_bonus(
        self,
        attacker_model,
        *,
        unit=None,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        return self._data_psalm_citation_in_savagery_bonus(
            attacker_model,
            unit=unit,
            weapon_profile=weapon_profile,
            game=game,
        )

    @staticmethod
    def _objective_point_for_entry(entry):
        point = getattr(entry, "location", None)
        if point is None:
            point = entry
        if point is None:
            return None
        if not hasattr(point, "x") or not hasattr(point, "y"):
            return None
        return point

    def _collect_objective_entries(self, *, game=None, game_map=None) -> list:
        if game_map is None and game is not None:
            game_map = getattr(game, "map", None)
        if game_map is None:
            owner = getattr(self.army, "player", None) if self.army is not None else None
            game_obj = getattr(owner, "game", None) if owner is not None else None
            if game is None:
                game = game_obj
            game_map = getattr(game_obj, "map", None) if game_obj is not None else None

        pool = []
        if game_map is not None:
            pool.extend(list(getattr(game_map, "objectives", []) or []))
        if game is not None:
            pool.extend(list(getattr(game, "objectives", []) or []))

        entries: list = []
        seen_ids: set[str] = set()
        for objective in pool:
            point = self._objective_point_for_entry(objective)
            if point is None or bool(getattr(point, "removed", False)):
                continue
            objective_id = str(get_entity_id(objective) or get_entity_id(point) or "")
            if not objective_id or objective_id in seen_ids:
                continue
            seen_ids.add(objective_id)
            entries.append((objective_id, objective, point))
        entries.sort(key=lambda item: str(item[0]))
        return entries

    def _objective_entry_by_id(self, objective_id: str, *, game=None, game_map=None):
        wanted = str(objective_id or "").strip()
        if not wanted:
            return None
        for entry in self._collect_objective_entries(game=game, game_map=game_map):
            if str(entry[0]) == wanted:
                return entry
        return None

    def clear_acquisition_objective(self) -> None:
        self.active_acquisition_objective_id = ""
        self.acquisition_selected_round = 0

    def can_select_acquisition_objective(self, *, game=None, battle_round: Optional[int] = None) -> bool:
        if not self.is_explorator_maniple():
            return False
        br = 0
        if battle_round is not None:
            try:
                br = int(battle_round or 0)
            except (TypeError, ValueError):
                br = 0
        elif game is not None:
            try:
                br = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                br = 0
        if br <= 0:
            return False
        if self.acquisition_selected_round == br and bool(str(self.active_acquisition_objective_id or "").strip()):
            return False
        return True

    def _pending_acquisition_request(self, game, army_id: str, *, battle_round: int):
        if game is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "")) != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != self._ACQUISITION_ABILITY_KEY:
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id or ""):
                continue
            try:
                req_round = int(ctx.get("battle_round", 0) or 0)
            except (TypeError, ValueError):
                req_round = 0
            if req_round != int(battle_round):
                continue
            return req
        return None

    def _build_acquisition_request(self, game, *, battle_round: int):
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        if game is None:
            return None
        owner = getattr(self.army, "player", None)
        if owner is None:
            return None
        entries = self._collect_objective_entries(game=game)
        if not entries:
            return None
        options = []
        objective_ids: list[str] = []
        for idx, (objective_id, objective, point) in enumerate(entries):
            objective_ids.append(str(objective_id))
            label = str(getattr(objective, "name", "") or f"Objective {idx + 1}")
            try:
                label = f"{label} ({float(getattr(point, 'x', 0.0)):.1f}, {float(getattr(point, 'y', 0.0)):.1f})"
            except (TypeError, ValueError):
                pass
            options.append(DecisionOption.create(label, payload={"objective_id": str(objective_id)}))
        if not options:
            return None

        army_id = self._entity_id(self.army)
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Acquisition At Any Cost: select one objective marker to be your Acquisition objective marker.",
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": self._ACQUISITION_ABILITY_KEY,
                "ability_name": self._ACQUISITION_SOURCE,
                "army_id": army_id,
                "battle_round": int(battle_round),
                "candidate_objective_ids": list(objective_ids),
                "optional": False,
            },
        )

    def _queue_acquisition_request(self, game, *, player, battle_round: int) -> None:
        if not self.is_explorator_maniple():
            return
        if game is None or player is None:
            return
        if player is not getattr(self.army, "player", None):
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return

        br = int(battle_round or 0)
        if br <= 0:
            return
        if self.acquisition_selected_round != br:
            self.clear_acquisition_objective()
        if not self.can_select_acquisition_objective(game=game, battle_round=br):
            return

        army_id = self._entity_id(self.army)
        if self._pending_acquisition_request(game, army_id, battle_round=br) is not None:
            return
        request = self._build_acquisition_request(game, battle_round=br)
        request_decision = getattr(game, "request_decision", None)
        if callable(request_decision) and request is not None:
            request_decision(request)

    def validate_acquisition_objective_choice(
        self,
        objective_id: str,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
    ) -> tuple[bool, str]:
        if not self.is_explorator_maniple():
            return False, "Acquisition At Any Cost requires an Explorator Maniple army."
        if self.army is None:
            return False, "Acquisition At Any Cost army not found."
        if player is not None:
            owner = getattr(self.army, "player", None)
            if owner is not None and owner is not player:
                return False, "Acquisition At Any Cost must be resolved by the owning player."
        objective_id = str(objective_id or "").strip()
        if not objective_id:
            return False, "Acquisition At Any Cost selection requires objective_id."
        if self._objective_entry_by_id(objective_id, game=game) is None:
            return False, "Acquisition At Any Cost selected objective marker was not found."

        expected_round = int(battle_round or 0)
        if expected_round and game is not None:
            try:
                current_round = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_round = 0
            if current_round and current_round != expected_round:
                return False, "Acquisition At Any Cost selection is no longer in the current battle round."
        if expected_round and self.acquisition_selected_round == expected_round and bool(
            str(self.active_acquisition_objective_id or "").strip()
        ):
            return False, "Acquisition At Any Cost has already been selected this Command phase."
        return True, ""

    def select_acquisition_objective(
        self,
        objective_id: str,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
    ):
        valid, reason = self.validate_acquisition_objective_choice(
            objective_id,
            game=game,
            player=player,
            battle_round=battle_round,
        )
        if not valid:
            return None
        entry = self._objective_entry_by_id(str(objective_id or "").strip(), game=game)
        if entry is None:
            return None
        objective_key, objective, _point = entry
        self.active_acquisition_objective_id = str(objective_key)
        if game is not None:
            try:
                self.acquisition_selected_round = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                self.acquisition_selected_round = int(battle_round or 0)
        else:
            self.acquisition_selected_round = int(battle_round or 0)
        return {
            "objective_id": str(objective_key),
            "objective_name": str(getattr(objective, "name", "") or "Objective marker"),
            "battle_round": int(self.acquisition_selected_round or 0),
            "source": self._ACQUISITION_SOURCE,
        }

    def _active_acquisition_objective_point(self, *, game=None, game_map=None):
        if not self.is_explorator_maniple():
            return None
        objective_id = str(self.active_acquisition_objective_id or "").strip()
        if not objective_id:
            return None
        entry = self._objective_entry_by_id(objective_id, game=game, game_map=game_map)
        if entry is None:
            return None
        _objective_id, objective, point = entry
        if point is None or bool(getattr(point, "removed", False)):
            return None
        return objective, point

    def acquisition_at_any_cost_wound_reroll_ones(
        self,
        attacker_model,
        *,
        target_unit=None,
        game=None,
        game_map=None,
    ) -> tuple[bool, str]:
        if not self.is_explorator_maniple():
            return False, ""
        if attacker_model is None or target_unit is None:
            return False, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = self._attached_root(attacker_unit)
        if attacker_root is None or not self._unit_in_army(attacker_root):
            return False, ""
        if not self._unit_has_keyword_or_faction(attacker_root, "ADEPTUS MECHANICUS", faction_id=self.faction_id):
            return False, ""
        active = self._active_acquisition_objective_point(game=game, game_map=game_map)
        if not isinstance(active, tuple):
            return False, ""
        _objective, objective_point = active
        attacker_within = False
        is_within_attacker = getattr(attacker_root, "is_within_objective_range", None)
        if callable(is_within_attacker):
            attacker_within = bool(is_within_attacker(objective_point))
        target_root = self._attached_root(target_unit)
        target_within = False
        if target_root is not None:
            is_within_target = getattr(target_root, "is_within_objective_range", None)
            if callable(is_within_target):
                target_within = bool(is_within_target(objective_point))
        if attacker_within or target_within:
            return True, f"{self._ACQUISITION_SOURCE} (Acquisition objective)"
        return False, ""

    @classmethod
    def _normalize_noospheric_override_choice_key(cls, choice_key: str) -> str:
        raw = str(choice_key or "").strip().upper()
        aliases = {
            "ELECTROMOTIVE": cls._NOOSPHERIC_ELECTROMOTIVE_KEY,
            "ELECTROMOTIVE_ENERGISATION": cls._NOOSPHERIC_ELECTROMOTIVE_KEY,
            "MICROACTUATOR": cls._NOOSPHERIC_MICROACTUATOR_KEY,
            "MICROACTUATOR_BRACING": cls._NOOSPHERIC_MICROACTUATOR_KEY,
            "PREDATION": cls._NOOSPHERIC_PREDATION_KEY,
            "PREDATION_PROTOCOLS": cls._NOOSPHERIC_PREDATION_KEY,
            "MUTED": cls._NOOSPHERIC_MUTED_KEY,
            "MUTED_SERVOMOTORS": cls._NOOSPHERIC_MUTED_KEY,
        }
        return aliases.get(raw, "")

    @classmethod
    def noospheric_override_choices(cls) -> tuple[tuple[str, str], ...]:
        return (
            (cls._NOOSPHERIC_ELECTROMOTIVE_KEY, "Electromotive Energisation"),
            (cls._NOOSPHERIC_MICROACTUATOR_KEY, "Microactuator Bracing"),
            (cls._NOOSPHERIC_PREDATION_KEY, "Predation Protocols"),
            (cls._NOOSPHERIC_MUTED_KEY, "Muted Servomotors"),
        )

    def _noospheric_max_selected_units(self, *, game=None) -> int:
        if game is None:
            owner = getattr(self.army, "player", None)
            game = getattr(owner, "game", None) if owner is not None else None
        size_value = getattr(getattr(game, "battlefield", None), "size", None) if game is not None else None
        size_key = str(getattr(size_value, "name", size_value) or "").strip().upper()
        if size_key == "INCURSION":
            return 1
        if size_key == "ONSLAUGHT":
            return 3
        return 2

    def _unit_is_on_battlefield_or_embarked(self, unit) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        if bool(getattr(unit, "is_embarked", False)):
            return True
        if getattr(unit, "embarked_in", None) is not None:
            return True
        if not bool(getattr(unit, "deployed", False)):
            return False
        return str(getattr(unit, "reserve_status", "deployed") or "deployed") == "deployed"

    def _iter_noospheric_candidate_roots(self) -> list:
        if self.army is None:
            return []
        seen: set[str] = set()
        roots: list = []
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._attached_root(unit)
            if root is None:
                continue
            root_id = self._entity_id(root) or str(id(root))
            if root_id in seen:
                continue
            seen.add(root_id)
            if not self._unit_has_keyword_or_faction(root, "ADEPTUS MECHANICUS", faction_id=self.faction_id):
                continue
            if not self._unit_is_on_battlefield_or_embarked(root):
                continue
            roots.append(root)
        roots.sort(key=lambda item: self._entity_id(item) or str(getattr(item, "name", "") or ""))
        return roots

    def _pending_noospheric_request(self, game, army_id: str, *, ability_key: str, battle_round: int):
        if game is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "")) != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != str(ability_key or ""):
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id or ""):
                continue
            try:
                req_round = int(ctx.get("battle_round", 0) or 0)
            except (TypeError, ValueError):
                req_round = 0
            if req_round != int(battle_round):
                continue
            return req
        return None

    def _clear_noospheric_flags_on_army_units(self) -> None:
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._attached_root(unit)
            if root is None:
                continue
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            updated = dict(sr)
            updated.pop(self._NOOSPHERIC_ACTIVE_FLAG_KEY, None)
            updated.pop(self._NOOSPHERIC_SOURCE_FLAG_KEY, None)
            updated.pop(self._NOOSPHERIC_OVERRIDE_FLAG_KEY, None)
            root.special_rules = updated

    def _apply_noospheric_flags_to_selected_units(self) -> None:
        self._clear_noospheric_flags_on_army_units()
        selected_ids = {str(uid or "").strip() for uid in list(self.active_noospheric_unit_ids or []) if str(uid or "").strip()}
        if not selected_ids:
            return
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._attached_root(unit)
            if root is None:
                continue
            root_id = str(self._entity_id(root) or "").strip()
            if not root_id or root_id not in selected_ids:
                continue
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            updated = dict(sr)
            updated[self._NOOSPHERIC_ACTIVE_FLAG_KEY] = True
            updated[self._NOOSPHERIC_SOURCE_FLAG_KEY] = self._NOOSPHERIC_SOURCE
            if str(self.active_noospheric_override_key or "").strip():
                updated[self._NOOSPHERIC_OVERRIDE_FLAG_KEY] = str(self.active_noospheric_override_key)
            else:
                updated.pop(self._NOOSPHERIC_OVERRIDE_FLAG_KEY, None)
            root.special_rules = updated

    def clear_noospheric_transference_state(self) -> None:
        self.active_noospheric_unit_ids = []
        self.active_noospheric_override_key = ""
        self.noospheric_selected_round = 0
        self._clear_noospheric_flags_on_army_units()

    def can_select_noospheric_units(self, *, game=None, battle_round: Optional[int] = None) -> bool:
        if not self.is_haloscreed_battle_clade():
            return False
        br = 0
        if battle_round is not None:
            try:
                br = int(battle_round or 0)
            except (TypeError, ValueError):
                br = 0
        elif game is not None:
            try:
                br = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                br = 0
        if br <= 0:
            return False
        if self.noospheric_selected_round == br and list(self.active_noospheric_unit_ids or []):
            return False
        return True

    def _build_noospheric_unit_selection_request(self, game, *, battle_round: int):
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        if game is None:
            return None
        owner = getattr(self.army, "player", None)
        if owner is None:
            return None
        candidates = self._iter_noospheric_candidate_roots()
        if not candidates:
            return None
        max_count = min(self._noospheric_max_selected_units(game=game), len(candidates))
        if max_count <= 0:
            return None
        options = []
        for count in range(1, max_count + 1):
            for combo in combinations(candidates, count):
                unit_ids = [self._entity_id(unit) for unit in combo]
                if any(not unit_id for unit_id in unit_ids):
                    continue
                label = " + ".join(str(getattr(unit, "name", "Unit") or "Unit") for unit in combo)
                options.append(DecisionOption.create(label, payload={"selected_unit_ids": list(unit_ids)}))
        if not options:
            return None
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            (
                "Noospheric Transference: select one or more friendly ADEPTUS MECHANICUS units "
                "to gain HALO OVERRIDE until your next Command phase."
            ),
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": self._NOOSPHERIC_UNITS_ABILITY_KEY,
                "ability_name": self._NOOSPHERIC_SOURCE,
                "army_id": self._entity_id(self.army),
                "battle_round": int(battle_round),
                "candidate_unit_ids": [self._entity_id(unit) for unit in candidates if self._entity_id(unit)],
                "max_selections": int(max_count),
                "optional": False,
            },
        )

    def queue_noospheric_unit_selection_request(self, *, game=None, player=None, battle_round: int = 0):
        if not self.is_haloscreed_battle_clade():
            return None
        if self.army is None:
            return None
        owner = getattr(self.army, "player", None)
        if player is None:
            player = owner
        if player is None or (owner is not None and player is not owner):
            return None
        if game is None:
            game = getattr(player, "game", None)
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return None
        br = int(battle_round or 0)
        if br <= 0:
            return None
        if self.noospheric_selected_round != br:
            self.clear_noospheric_transference_state()
        if not self.can_select_noospheric_units(game=game, battle_round=br):
            return None
        army_id = self._entity_id(self.army)
        if self._pending_noospheric_request(
            game,
            army_id,
            ability_key=self._NOOSPHERIC_UNITS_ABILITY_KEY,
            battle_round=br,
        ) is not None:
            return None
        request = self._build_noospheric_unit_selection_request(game, battle_round=br)
        request_fn = getattr(game, "request_decision", None)
        if callable(request_fn) and request is not None:
            request_fn(request)
        return request

    def validate_noospheric_unit_selection(
        self,
        selected_unit_ids: list[str] | tuple[str, ...] | None,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
    ) -> tuple[bool, str]:
        if not self.is_haloscreed_battle_clade():
            return False, "Noospheric Transference requires Haloscreed Battle Clade detachment."
        if self.army is None:
            return False, "Noospheric Transference army not found."
        owner = getattr(self.army, "player", None)
        if player is not None and owner is not None and player is not owner:
            return False, "Noospheric Transference must be resolved by the owning player."
        selected_ids = [
            str(unit_id or "").strip()
            for unit_id in list(selected_unit_ids or [])
            if str(unit_id or "").strip()
        ]
        selected_ids = list(dict.fromkeys(selected_ids))
        if not selected_ids:
            return False, "Noospheric Transference requires selecting at least one unit."
        max_count = self._noospheric_max_selected_units(game=game)
        if len(selected_ids) > int(max_count):
            return False, f"Noospheric Transference can select at most {int(max_count)} unit(s) this battle size."
        valid_by_id = {self._entity_id(unit): unit for unit in self._iter_noospheric_candidate_roots() if self._entity_id(unit)}
        if any(unit_id not in valid_by_id for unit_id in selected_ids):
            return False, "Noospheric Transference selection includes ineligible units."
        expected_round = int(battle_round or 0)
        if expected_round and game is not None:
            try:
                current_round = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_round = 0
            if current_round and current_round != expected_round:
                return False, "Noospheric Transference selection is no longer in the current battle round."
        if expected_round and self.noospheric_selected_round == expected_round and list(self.active_noospheric_unit_ids or []):
            return False, "Noospheric Transference units have already been selected this Command phase."
        return True, ""

    def select_noospheric_unit_selection(
        self,
        selected_unit_ids: list[str] | tuple[str, ...] | None,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
    ):
        valid, reason = self.validate_noospheric_unit_selection(
            selected_unit_ids,
            game=game,
            player=player,
            battle_round=battle_round,
        )
        if not valid:
            return None
        valid_by_id = {self._entity_id(unit): unit for unit in self._iter_noospheric_candidate_roots() if self._entity_id(unit)}
        selected_ids = sorted(
            {
                str(unit_id or "").strip()
                for unit_id in list(selected_unit_ids or [])
                if str(unit_id or "").strip() and str(unit_id or "").strip() in valid_by_id
            }
        )
        if not selected_ids:
            return None
        self.active_noospheric_unit_ids = list(selected_ids)
        self.active_noospheric_override_key = ""
        if game is not None:
            try:
                self.noospheric_selected_round = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                self.noospheric_selected_round = int(battle_round or 0)
        else:
            self.noospheric_selected_round = int(battle_round or 0)
        self._apply_noospheric_flags_to_selected_units()
        return {
            "selected_unit_ids": list(selected_ids),
            "selected_unit_names": [str(getattr(valid_by_id[unit_id], "name", "Unit") or "Unit") for unit_id in selected_ids],
            "battle_round": int(self.noospheric_selected_round or 0),
            "source": self._NOOSPHERIC_SOURCE,
        }

    def _build_noospheric_override_request(self, game, *, battle_round: int):
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        if game is None or not list(self.active_noospheric_unit_ids or []):
            return None
        owner = getattr(self.army, "player", None)
        if owner is None:
            return None
        options = [
            DecisionOption.create(label, payload={"choice_key": key})
            for key, label in self.noospheric_override_choices()
        ]
        if not options:
            return None
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Noospheric Transference: select one HALO OVERRIDE ability to apply until your next Command phase.",
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": self._NOOSPHERIC_OVERRIDE_ABILITY_KEY,
                "ability_name": self._NOOSPHERIC_SOURCE,
                "army_id": self._entity_id(self.army),
                "battle_round": int(battle_round),
                "allowed_choice_keys": [key for key, _label in self.noospheric_override_choices()],
                "optional": False,
            },
        )

    def queue_noospheric_override_request(self, *, game=None, player=None, battle_round: int = 0):
        if not self.is_haloscreed_battle_clade():
            return None
        if self.army is None:
            return None
        owner = getattr(self.army, "player", None)
        if player is None:
            player = owner
        if player is None or (owner is not None and player is not owner):
            return None
        if game is None:
            game = getattr(player, "game", None)
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return None
        br = int(battle_round or 0)
        if br <= 0 or self.noospheric_selected_round != br:
            return None
        if not list(self.active_noospheric_unit_ids or []):
            return None
        if str(self.active_noospheric_override_key or "").strip():
            return None
        army_id = self._entity_id(self.army)
        if self._pending_noospheric_request(
            game,
            army_id,
            ability_key=self._NOOSPHERIC_OVERRIDE_ABILITY_KEY,
            battle_round=br,
        ) is not None:
            return None
        request = self._build_noospheric_override_request(game, battle_round=br)
        request_fn = getattr(game, "request_decision", None)
        if callable(request_fn) and request is not None:
            request_fn(request)
        return request

    def validate_noospheric_override_choice(
        self,
        choice_key: str,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
    ) -> tuple[bool, str]:
        if not self.is_haloscreed_battle_clade():
            return False, "Noospheric Transference requires Haloscreed Battle Clade detachment."
        if self.army is None:
            return False, "Noospheric Transference army not found."
        owner = getattr(self.army, "player", None)
        if player is not None and owner is not None and player is not owner:
            return False, "Noospheric Transference must be resolved by the owning player."
        if not list(self.active_noospheric_unit_ids or []):
            return False, "Noospheric Transference override requires selected HALO OVERRIDE units."
        expected_round = int(battle_round or 0)
        if expected_round <= 0:
            return False, "Noospheric Transference override requires current battle round context."
        if self.noospheric_selected_round != expected_round:
            return False, "Noospheric Transference override must be selected in the same Command phase."
        normalized = self._normalize_noospheric_override_choice_key(choice_key)
        if not normalized:
            return False, "Noospheric Transference override choice is not supported."
        return True, ""

    def select_noospheric_override_choice(
        self,
        choice_key: str,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
    ):
        valid, reason = self.validate_noospheric_override_choice(
            choice_key,
            game=game,
            player=player,
            battle_round=battle_round,
        )
        if not valid:
            return None
        normalized = self._normalize_noospheric_override_choice_key(choice_key)
        self.active_noospheric_override_key = normalized
        self._apply_noospheric_flags_to_selected_units()
        labels = {key: label for key, label in self.noospheric_override_choices()}
        return {
            "choice_key": str(normalized),
            "choice_label": str(labels.get(normalized, normalized.replace("_", " ").title())),
            "battle_round": int(self.noospheric_selected_round or 0),
            "source": self._NOOSPHERIC_SOURCE,
        }

    def _unit_selected_for_noospheric(self, unit) -> bool:
        if not self.is_haloscreed_battle_clade():
            return False
        selected_ids = {str(uid or "").strip() for uid in list(self.active_noospheric_unit_ids or []) if str(uid or "").strip()}
        if not selected_ids:
            return False
        root = self._attached_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        root_id = str(self._entity_id(root) or "").strip()
        return bool(root_id and root_id in selected_ids)

    def _noospheric_override_active(self, choice_key: str) -> bool:
        if not self.is_haloscreed_battle_clade():
            return False
        normalized = self._normalize_noospheric_override_choice_key(choice_key)
        if not normalized:
            return False
        if not list(self.active_noospheric_unit_ids or []):
            return False
        return str(self.active_noospheric_override_key or "").strip().upper() == normalized

    def noospheric_transference_movement_bonus(self, model, *, unit=None) -> tuple[int, str]:
        if model is None:
            return 0, ""
        if not self._noospheric_override_active(self._NOOSPHERIC_ELECTROMOTIVE_KEY):
            return 0, ""
        source_unit = unit if unit is not None else getattr(model, "parent_unit", None)
        if not self._unit_selected_for_noospheric(source_unit):
            return 0, ""
        return 2, f"{self._NOOSPHERIC_SOURCE} (Electromotive Energisation)"

    def noospheric_transference_toughness_bonus(self, model, *, unit=None) -> tuple[int, str]:
        if model is None:
            return 0, ""
        if not self._noospheric_override_active(self._NOOSPHERIC_MICROACTUATOR_KEY):
            return 0, ""
        source_unit = unit if unit is not None else getattr(model, "parent_unit", None)
        if not self._unit_selected_for_noospheric(source_unit):
            return 0, ""
        return 1, f"{self._NOOSPHERIC_SOURCE} (Microactuator Bracing)"

    def noospheric_transference_charge_after_advance_applies(self, unit, *, game=None) -> bool:
        _ = game
        if not self._noospheric_override_active(self._NOOSPHERIC_PREDATION_KEY):
            return False
        return self._unit_selected_for_noospheric(unit)

    def noospheric_transference_stealth_applies(self, unit, *, game=None) -> bool:
        _ = game
        if not self._noospheric_override_active(self._NOOSPHERIC_MUTED_KEY):
            return False
        return self._unit_selected_for_noospheric(unit)

    def _unit_is_ironstrider_ballistarii(self, unit) -> bool:
        if unit is None:
            return False
        if self._unit_has_keyword(unit, "IRONSTRIDER BALLISTARII"):
            return True
        name = str(getattr(unit, "name", "") or "").strip().lower()
        return "ironstrider ballistarii" in name

    def _unit_is_skitarii_hunter_stealth_eligible(self, unit) -> bool:
        if unit is None:
            return False
        has_skitarii = self._unit_has_keyword(unit, "SKITARII")
        has_infantry_or_mounted = self._unit_has_keyword(unit, "INFANTRY") or self._unit_has_keyword(unit, "MOUNTED")
        if has_skitarii and has_infantry_or_mounted:
            return True
        return self._unit_is_ironstrider_ballistarii(unit)

    def stealth_optimisation_stealth_applies(self, unit) -> bool:
        if not self.is_skitarii_hunter_cohort():
            return False
        root = self._attached_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        return self._unit_is_skitarii_hunter_stealth_eligible(root)

    def stealth_optimisation_benefit_of_cover(
        self,
        target_model,
        *,
        attacker_model=None,
        attack_type: str = "",
        game=None,
    ) -> tuple[bool, str]:
        _ = game
        if not self.is_skitarii_hunter_cohort():
            return False, ""
        if str(attack_type or "").strip().lower() not in ("", "ranged"):
            return False, ""
        if target_model is None or attacker_model is None:
            return False, ""
        target_unit = getattr(target_model, "parent_unit", None)
        target_root = self._attached_root(target_unit)
        if target_root is None or not self._unit_in_army(target_root):
            return False, ""
        has_sicarian_keyword = self._unit_has_keyword(target_root, "SICARIAN")
        target_name = str(getattr(target_root, "name", "") or "").strip().lower()
        if not has_sicarian_keyword and "sicarian" not in target_name:
            return False, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = self._attached_root(attacker_unit)
        if attacker_root is not None and self._unit_in_army(attacker_root):
            return False, ""
        from ..utility.aura_utils import model_within_range_of_unit

        if model_within_range_of_unit(attacker_model, target_root, 12.0, use_attached_aggregate=True):
            return False, ""
        return True, f"{self._STEALTH_OPTIMISATION_SOURCE} (Sicarian cover beyond 12\")"

    def _iter_player_unit_roots(self, player) -> list:
        if player is None:
            return []
        get_army = getattr(player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(player, "army", None)
        if army is None:
            return []
        seen: set[str] = set()
        roots: list = []
        for unit in list(getattr(army, "units", []) or []):
            root = self._attached_root(unit)
            if root is None:
                continue
            root_id = self._entity_id(root) or str(id(root))
            if root_id in seen:
                continue
            seen.add(root_id)
            roots.append(root)
        roots.sort(key=lambda item: self._entity_id(item) or str(getattr(item, "name", "") or ""))
        return roots

    def _unit_is_on_battlefield(self, unit) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        if not bool(getattr(unit, "deployed", False)):
            return False
        if str(getattr(unit, "reserve_status", "deployed") or "deployed") != "deployed":
            return False
        if bool(getattr(unit, "is_embarked", False)):
            return False
        if getattr(unit, "embarked_in", None) is not None:
            return False
        return True

    def unit_within_player_deployment_zone(self, unit, player_id: str, *, game=None) -> bool:
        if unit is None or not player_id:
            return False
        if game is None:
            owner = getattr(self.army, "player", None)
            game = getattr(owner, "game", None) if owner is not None else None
        if game is None:
            return False
        in_zone = getattr(game, "is_position_in_deployment_zone", None)
        if not callable(in_zone):
            return False
        for model in self._iter_unit_models(unit):
            location = model.get_location()
            if not location or len(location) < 2:
                continue
            if in_zone(float(location[0]), float(location[1]), str(player_id)):
                return True
        return False

    def _opponent_player(self, game):
        if game is None:
            return None
        owner = getattr(self.army, "player", None)
        for player in list(getattr(game, "players", []) or []):
            if player is None or player is owner:
                continue
            return player
        return None

    def _enemy_units_in_player_deployment_zone(self, game, *, enemy_player) -> list:
        if game is None or enemy_player is None:
            return []
        enemy_id = str(getattr(enemy_player, "id", "") or "")
        if not enemy_id:
            return []
        eligible: list = []
        for root in self._iter_player_unit_roots(enemy_player):
            if not self._unit_is_on_battlefield(root):
                continue
            if not self.unit_within_player_deployment_zone(root, enemy_id, game=game):
                continue
            eligible.append(root)
        eligible.sort(key=lambda item: self._entity_id(item) or str(getattr(item, "name", "") or ""))
        return eligible

    def _unit_has_radial_suffusion(self, unit) -> bool:
        if unit is None:
            return False
        special_rules = getattr(unit, "special_rules", None)
        if isinstance(special_rules, dict) and bool(special_rules.get(self._RADIAL_SUFFUSION_FLAG_KEY, False)):
            return True
        enhancement = getattr(unit, "enhancement", None)
        if enhancement is None:
            return False
        enh_id = str(getattr(enhancement, "id", "") or "").strip()
        if enh_id == self._RADIAL_SUFFUSION_ENHANCEMENT_ID:
            return True
        enh_name = str(getattr(enhancement, "name", "") or "").strip().lower()
        return enh_name == self._RADIAL_SUFFUSION_ENHANCEMENT_NAME

    def _unit_has_active_radial_suffusion_bearer(self, unit) -> bool:
        if unit is None or not self._unit_has_radial_suffusion(unit):
            return False
        if not self._unit_is_on_battlefield(unit):
            return False
        special_rules = getattr(unit, "special_rules", None)
        bearer_id = str(special_rules.get("enhancement_bearer_model_id", "") or "") if isinstance(special_rules, dict) else ""
        if bearer_id:
            for model in list(getattr(unit, "models", []) or []):
                if str(getattr(model, "id", getattr(model, "_id", "")) or "") != bearer_id:
                    continue
                return self._is_model_alive(model)
            return False
        get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
        if callable(get_bearer):
            bearer = get_bearer()
            if bearer is None:
                return False
            return self._is_model_alive(bearer)
        for model in list(getattr(unit, "models", []) or []):
            if self._is_model_alive(model):
                return True
        return False

    def _radial_suffusion_active(self) -> bool:
        for unit in list(getattr(self.army, "units", []) or []):
            if self._unit_has_active_radial_suffusion_bearer(unit):
                return True
        return False

    def _distance_to_player_deployment_zone(self, game, *, player_id: str, x: float, y: float) -> float:
        if game is None or not player_id:
            return float("inf")
        zones = getattr(game, "deployment_zones", None)
        if not isinstance(zones, dict):
            return float("inf")
        zone_info = zones.get(str(player_id))
        if not isinstance(zone_info, dict):
            return float("inf")
        mission_zones = list(zone_info.get("mission_zones", []) or [])
        if not mission_zones:
            return float("inf")

        px = float(x)
        py = float(y)
        min_distance = float("inf")
        for mission_zone in mission_zones:
            contains_point = getattr(mission_zone, "contains_point", None)
            if callable(contains_point) and bool(contains_point(px, py)):
                return 0.0

            vertices = list(getattr(mission_zone, "vertices", []) or [])
            if len(vertices) >= 3:
                try:
                    from shapely.geometry import Point as _ShPoint
                    from shapely.geometry import Polygon as _ShPoly

                    dist = float(_ShPoint(px, py).distance(_ShPoly(vertices)))
                    if dist < min_distance:
                        min_distance = dist
                    continue
                except (ImportError, TypeError, ValueError):
                    pass

            has_rect_bounds = all(hasattr(mission_zone, attr) for attr in ("x_min", "x_max", "y_min", "y_max"))
            if has_rect_bounds:
                x_min = float(getattr(mission_zone, "x_min"))
                x_max = float(getattr(mission_zone, "x_max"))
                y_min = float(getattr(mission_zone, "y_min"))
                y_max = float(getattr(mission_zone, "y_max"))
                dx = max(x_min - px, 0.0, px - x_max)
                dy = max(y_min - py, 0.0, py - y_max)
                dist = float(math.hypot(dx, dy))
                if dist < min_distance:
                    min_distance = dist
        return min_distance

    def _unit_within_distance_of_player_deployment_zone(
        self,
        unit,
        player_id: str,
        *,
        game=None,
        distance_in: float = 0.0,
    ) -> bool:
        if unit is None or not player_id or game is None:
            return False
        threshold = float(distance_in or 0.0)
        if threshold < 0.0:
            return False
        for model in self._iter_unit_models(unit):
            location = model.get_location()
            if not location or len(location) < 2:
                continue
            dist = self._distance_to_player_deployment_zone(
                game,
                player_id=str(player_id),
                x=float(location[0]),
                y=float(location[1]),
            )
            if dist <= (threshold + 1e-6):
                return True
        return False

    def _enemy_units_for_fallout(self, game, *, enemy_player) -> list:
        targets = list(self._enemy_units_in_player_deployment_zone(game, enemy_player=enemy_player) or [])
        if not self._radial_suffusion_active():
            return targets

        enemy_id = str(getattr(enemy_player, "id", "") or "")
        if not enemy_id:
            return targets
        known_ids: set[str] = {self._entity_id(unit) or str(id(unit)) for unit in targets}
        for root in self._iter_player_unit_roots(enemy_player):
            if not self._unit_is_on_battlefield(root):
                continue
            root_id = self._entity_id(root) or str(id(root))
            if root_id in known_ids:
                continue
            if not self._unit_within_distance_of_player_deployment_zone(
                root,
                enemy_id,
                game=game,
                distance_in=self._RADIAL_SUFFUSION_EXTRA_RANGE_IN,
            ):
                continue
            known_ids.add(root_id)
            targets.append(root)
        targets.sort(key=lambda item: self._entity_id(item) or str(getattr(item, "name", "") or ""))
        return targets

    def _pending_rad_bombardment_request(self, game, *, target_unit, battle_round: int):
        if game is None or target_unit is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        target_id = self._entity_id(target_unit)
        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "")) != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != self._RAD_BOMBARDMENT_ABILITY_KEY:
                continue
            if str(ctx.get("target_unit_id", "") or "") != target_id:
                continue
            if int(ctx.get("battle_round", 0) or 0) != int(battle_round):
                continue
            return req
        return None

    def _build_rad_bombardment_request(self, game, *, target_unit, battle_round: int):
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        opponent = self._opponent_player(game)
        if opponent is None or target_unit is None:
            return None
        target_id = self._entity_id(target_unit)
        source_army_id = self._entity_id(self.army)
        options = [
            DecisionOption.create(
                "Stand Firm",
                payload={
                    "army_id": source_army_id,
                    "target_unit_id": target_id,
                    self._RAD_BOMBARDMENT_CHOICE_KEY: self._RAD_BOMBARDMENT_CHOICE_STAND_FIRM,
                },
            ),
            DecisionOption.create(
                "Take Cover",
                payload={
                    "army_id": source_army_id,
                    "target_unit_id": target_id,
                    self._RAD_BOMBARDMENT_CHOICE_KEY: self._RAD_BOMBARDMENT_CHOICE_TAKE_COVER,
                },
            ),
        ]
        prompt = (
            f"Rad-bombardment: choose how {getattr(target_unit, 'name', 'this unit')} responds "
            "in your deployment zone."
        )
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            prompt,
            player_id=getattr(opponent, "id", None),
            options=options,
            context={
                "ability": self._RAD_BOMBARDMENT_ABILITY_KEY,
                "ability_name": "Rad-bombardment",
                "army_id": source_army_id,
                "target_unit_id": target_id,
                "battle_round": int(battle_round),
            },
        )

    def _queue_rad_bombardment_requests(self, game, *, battle_round: int) -> None:
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        opponent = self._opponent_player(game)
        if opponent is None:
            return
        targets = self._enemy_units_in_player_deployment_zone(game, enemy_player=opponent)
        request_decision = getattr(game, "request_decision", None)
        if not callable(request_decision):
            return
        for target in targets:
            if self._pending_rad_bombardment_request(game, target_unit=target, battle_round=int(battle_round)) is not None:
                continue
            request = self._build_rad_bombardment_request(game, target_unit=target, battle_round=int(battle_round))
            if request is not None:
                request_decision(request)

    def _clear_expired_taking_cover_state(self, game, *, battle_round: int) -> None:
        if game is None or int(battle_round or 0) <= 1:
            return
        owner = getattr(self.army, "player", None)
        for player in list(getattr(game, "players", []) or []):
            if player is None or player is owner:
                continue
            for unit in self._iter_player_unit_roots(player):
                special_rules = getattr(unit, "special_rules", None)
                if not isinstance(special_rules, dict):
                    continue
                applied_round = int(special_rules.get(self._RAD_BOMBARDMENT_TAKING_COVER_ROUND_KEY, 0) or 0)
                if applied_round <= 0 or applied_round >= int(battle_round):
                    continue
                added_battleshock = bool(special_rules.get(self._RAD_BOMBARDMENT_TAKING_COVER_ADDED_KEY, False))
                special_rules = dict(special_rules)
                special_rules.pop(self._RAD_BOMBARDMENT_TAKING_COVER_ROUND_KEY, None)
                special_rules.pop(self._RAD_BOMBARDMENT_TAKING_COVER_ADDED_KEY, None)
                unit.special_rules = special_rules
                if added_battleshock:
                    clear_battleshock = getattr(unit, "clear_battle_shock", None)
                    if callable(clear_battleshock):
                        clear_battleshock()

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if game is None:
            owner = getattr(self.army, "player", None)
            game = getattr(owner, "game", None) if owner is not None else None
        br = int(battle_round or 0)
        if self.is_rad_zone_corps():
            self._clear_expired_taking_cover_state(game, battle_round=br)
            if br == 1:
                self._queue_rad_bombardment_requests(game, battle_round=br)
        if self.is_data_psalm_conclave():
            self._queue_data_psalm_benediction_request(game, battle_round=br)

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        if game is None or player is None:
            return
        if player is not getattr(self.army, "player", None):
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        battle_round = int(getattr(game, "turn", 0) or 0)
        if self.is_haloscreed_battle_clade():
            self.queue_noospheric_unit_selection_request(
                game=game,
                player=player,
                battle_round=int(battle_round),
            )
        if self.is_explorator_maniple():
            self._queue_acquisition_request(game, player=player, battle_round=int(battle_round))
        if not self.is_rad_zone_corps():
            return
        if battle_round < 2 or battle_round > 5:
            return
        opponent = self._opponent_player(game)
        if opponent is None:
            return
        targets = self._enemy_units_for_fallout(game, enemy_player=opponent)
        for target in targets:
            roll = int(get_roll("D6") or 0)
            if roll < 3:
                continue
            apply_mortal_wounds = getattr(target, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortal_wounds):
                apply_mortal_wounds(target, 1, game_map=getattr(game, "map", None))
            take_battle_shock_test = getattr(target, "take_battle_shock_test", None)
            if callable(take_battle_shock_test):
                take_battle_shock_test(int(battle_round))
