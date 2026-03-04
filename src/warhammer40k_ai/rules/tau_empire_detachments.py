from __future__ import annotations

from .detachment_manager import DetachmentManagerBase


class TauEmpireDetachmentManager(DetachmentManagerBase):
    faction_id = "TAU"
    _TAU_EMPIRE_KEYWORDS = ("T'AU EMPIRE", "TAU EMPIRE")
    _EXEMPLAR_OF_MONTKA_FLAG = "enhancement_exemplar_of_montka"
    _EXEMPLAR_OF_MONTKA_ID = "000008811003"
    _EXEMPLAR_OF_MONTKA_NAME = "exemplar of the mont'ka"
    _STRATEGIC_CONQUEROR_FLAG = "enhancement_strategic_conqueror"
    _STRATEGIC_CONQUEROR_ID = "000008811004"
    _STRATEGIC_CONQUEROR_NAME = "strategic conqueror"
    _STRATEGIC_CONQUEROR_OBJECTIVE_ID_KEY = "enhancement_strategic_conqueror_selected_objective_id"
    _STRATEGIC_CONQUEROR_OC_BONUS_KEY = "enhancement_strategic_conqueror_oc_bonus"
    _STRIKE_SWIFTLY_FLAG = "enhancement_strike_swiftly"
    _STRIKE_SWIFTLY_ID = "000008811005"
    _STRIKE_SWIFTLY_NAME = "strike swiftly"
    _STRIKE_SWIFTLY_SELECTED_UNIT_IDS_KEY = "enhancement_strike_swiftly_selected_unit_ids"
    _STRIKE_SWIFTLY_SCOUT_DISTANCE_KEY = "enhancement_strike_swiftly_scouts_distance"
    _STRIKE_SWIFTLY_SELECTION_RANGE_KEY = "enhancement_strike_swiftly_selection_range"
    _STRIKE_SWIFTLY_RESOLVED_KEY = "enhancement_strike_swiftly_resolved"
    _STUDENT_OF_KAUYON_FLAG = "enhancement_student_of_kauyon"
    _STUDENT_OF_KAUYON_ID = "000009839002"
    _STUDENT_OF_KAUYON_NAME = "student of kauyon"
    _STUDENT_OF_KAUYON_SELECTED_UNIT_IDS_KEY = "enhancement_student_of_kauyon_selected_unit_ids"
    _STUDENT_OF_KAUYON_MAX_UNITS_KEY = "enhancement_student_of_kauyon_max_units"
    _STUDENT_OF_KAUYON_RESOLVED_KEY = "enhancement_student_of_kauyon_resolved"

    def is_experimental_prototype_cadre(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Experimental Prototype Cadre")

    def is_auxiliary_cadre(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Auxiliary Cadre")

    def is_kauyon(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Kauyon")

    def is_kroot_hunting_pack(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Kroot Hunting Pack")

    def is_retaliation_cadre(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Retaliation Cadre")

    def _model_in_army(self, model) -> bool:
        if model is None or self.army is None:
            return False
        unit = getattr(model, "parent_unit", None)
        if unit is None:
            return False
        return self._unit_in_army(unit)

    def _unit_in_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        if not callable(get_parent_army):
            return False
        return get_parent_army() is self.army

    def _unit_is_tau_empire(self, unit) -> bool:
        if unit is None:
            return False
        return (
            self._unit_has_keyword_or_faction(unit, "T'AU EMPIRE", faction_id=self.faction_id)
            or self._unit_has_keyword_or_faction(unit, "TAU EMPIRE", faction_id=self.faction_id)
        )

    def _unit_is_kroot(self, unit) -> bool:
        return bool(unit is not None and self._unit_has_keyword_or_faction(unit, "KROOT", faction_id=self.faction_id))

    def _unit_is_vespid_stingwings(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword_or_faction(unit, "VESPID STINGWINGS", faction_id=self.faction_id)

    def _unit_is_kroot_or_vespid(self, unit) -> bool:
        return bool(self._unit_is_kroot(unit) or self._unit_is_vespid_stingwings(unit))

    def _unit_is_kroot_carnivores(self, unit) -> bool:
        if unit is None:
            return False
        root = self._attached_root(unit)
        if root is None:
            return False
        name = str(getattr(root, "name", "") or "").strip().lower()
        return "kroot carnivore" in name

    def _unit_is_kroot_farstalkers(self, unit) -> bool:
        if unit is None:
            return False
        root = self._attached_root(unit)
        if root is None:
            return False
        name = str(getattr(root, "name", "") or "").strip().lower()
        return "kroot farstalker" in name

    def _unit_is_student_of_kauyon_target(self, unit) -> bool:
        root = self._attached_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        return bool(
            self._unit_is_kroot_carnivores(root)
            or self._unit_is_kroot_farstalkers(root)
        )

    def _model_is_tau_empire(self, model) -> bool:
        if model is None:
            return False
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any):
            for keyword in self._TAU_EMPIRE_KEYWORDS:
                if has_any(keyword):
                    return True

        unit = getattr(model, "parent_unit", None)
        if unit is None:
            return False
        return self._unit_is_tau_empire(unit)

    def _model_has_keyword(self, model, keyword: str) -> bool:
        if model is None:
            return False
        kw = str(keyword or "").strip()
        if not kw:
            return False
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any):
            if has_any(kw):
                return True
        unit = getattr(model, "parent_unit", None)
        if unit is None:
            return False
        return self._unit_has_keyword_or_faction(unit, kw, faction_id=self.faction_id)

    def _model_is_kroot_or_vespid(self, model) -> bool:
        if model is None:
            return False
        if self._model_has_keyword(model, "KROOT"):
            return True
        return self._model_has_keyword(model, "VESPID STINGWINGS")

    def _model_is_kroot(self, model) -> bool:
        return bool(self._model_has_keyword(model, "KROOT"))

    def _model_is_titanic(self, model) -> bool:
        return bool(self._model_has_keyword(model, "TITANIC"))

    def _weapon_is_ranged(self, weapon_profile) -> bool:
        if weapon_profile is None:
            return False
        parent = getattr(weapon_profile, "parent_wargear", None)
        return bool(parent is not None and callable(getattr(parent, "is_ranged", None)) and parent.is_ranged())

    def _resolve_game_map_for_unit(self, unit, *, game_map=None):
        if game_map is not None:
            return game_map
        if unit is None:
            return None
        get_parent_army = getattr(unit, "get_parent_army", None)
        if not callable(get_parent_army):
            return None
        army = get_parent_army()
        player = getattr(army, "player", None) if army is not None else None
        game = getattr(player, "game", None) if player is not None else None
        return getattr(game, "map", None) if game is not None else None

    @staticmethod
    def _alive_models_for_unit(unit) -> list:
        if unit is None:
            return []
        get_models = getattr(unit, "get_attached_unit_models", None)
        if callable(get_models):
            models = list(get_models() or [])
        else:
            models = list(getattr(unit, "models", []) or [])
        out = []
        for model in models:
            alive_attr = getattr(model, "is_alive", True)
            alive = alive_attr() if callable(alive_attr) else bool(alive_attr)
            if alive:
                out.append(model)
        return out

    def _unit_visible_to_unit(self, source_unit, target_unit, *, game_map=None) -> bool:
        if source_unit is None or target_unit is None:
            return False
        game_map = self._resolve_game_map_for_unit(source_unit, game_map=game_map)
        if game_map is None:
            return True
        can_see = getattr(game_map, "can_model_see_model", None)
        if not callable(can_see):
            return True

        source_models = self._alive_models_for_unit(source_unit)
        target_models = self._alive_models_for_unit(target_unit)
        if not source_models or not target_models:
            return False

        for source_model in source_models:
            for target_model in target_models:
                if can_see(source_model, target_model):
                    return True
        return False

    def _iter_unique_army_roots(self) -> list:
        army = self.army
        if army is None:
            return []
        unique_by_id = {}
        for unit in list(getattr(army, "units", []) or []):
            root = self._attached_root(unit)
            if root is None:
                continue
            root_id = self._entity_id(root)
            if not root_id or root_id in unique_by_id:
                continue
            unique_by_id[root_id] = root
        return [unique_by_id[k] for k in sorted(unique_by_id.keys())]

    def integrated_command_structure_ap_bonus(
        self,
        attacker_model,
        *,
        target_unit=None,
        weapon_profile=None,
        game_map=None,
    ) -> int:
        if not self.is_auxiliary_cadre():
            return 0
        if attacker_model is None or target_unit is None:
            return 0
        if not self._weapon_is_ranged(weapon_profile):
            return 0
        if not self._model_in_army(attacker_model):
            return 0
        if not self._model_is_tau_empire(attacker_model):
            return 0
        if self._model_is_kroot_or_vespid(attacker_model):
            return 0
        if self._model_is_titanic(attacker_model):
            return 0

        from ..utility.aura_utils import unit_within_range_of_unit

        target_root = self._attached_root(target_unit)
        if target_root is None:
            return 0

        for source in self._iter_unique_army_roots():
            if not self._unit_is_on_battlefield(source):
                continue
            if not self._unit_is_kroot_or_vespid(source):
                continue
            if not unit_within_range_of_unit(source, target_root, 9.0, use_attached_aggregate=True):
                continue
            if not self._unit_visible_to_unit(source, target_root, game_map=game_map):
                continue
            return 1
        return 0

    def auxiliary_cadre_localised_stealth_projectors_range_limit(
        self,
        target_unit,
        *,
        game_map=None,
    ) -> tuple[float, str]:
        if not self.is_auxiliary_cadre():
            return 0.0, ""
        if target_unit is None:
            return 0.0, ""
        target_root = self._attached_root(target_unit)
        if target_root is None:
            return 0.0, ""
        if not self._unit_in_army(target_root):
            return 0.0, ""
        if not self._unit_is_on_battlefield(target_root):
            return 0.0, ""
        if not self._unit_is_kroot_or_vespid(target_root):
            return 0.0, ""

        from ..utility.aura_utils import unit_wholly_within_range_of_unit

        for source in self._iter_unique_army_roots():
            if not self._unit_is_on_battlefield(source):
                continue
            if not self._unit_is_tau_empire(source):
                continue
            if self._unit_is_kroot_or_vespid(source):
                continue
            if not unit_wholly_within_range_of_unit(source, target_root, 6.0, use_attached_aggregate=True):
                continue
            if not self._unit_visible_to_unit(source, target_root, game_map=game_map):
                continue
            return 18.0, "Integrated Command Structure: Localised Stealth Projectors"
        return 0.0, ""

    def hunters_instincts_hit_bonus(
        self,
        attacker_model,
        target_unit,
        *,
        weapon_profile=None,
        attack_instance=None,
    ) -> tuple[int, str]:
        del weapon_profile, attack_instance
        if not self.is_kroot_hunting_pack():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        if not self._model_in_army(attacker_model):
            return 0, ""
        if not self._model_is_kroot(attacker_model):
            return 0, ""
        target_root = self._attached_root(target_unit)
        if target_root is None:
            return 0, ""
        below_starting = getattr(target_root, "is_below_starting_strength", None)
        if not callable(below_starting) or not bool(below_starting()):
            return 0, ""
        return 1, "Hunter's Instincts"

    def hunters_instincts_wound_bonus(
        self,
        attacker_model,
        target_unit,
        *,
        weapon_profile=None,
        attack_instance=None,
    ) -> tuple[int, str]:
        del weapon_profile, attack_instance
        if not self.is_kroot_hunting_pack():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        if not self._model_in_army(attacker_model):
            return 0, ""
        if not self._model_is_kroot(attacker_model):
            return 0, ""
        target_root = self._attached_root(target_unit)
        if target_root is None:
            return 0, ""
        below_half = getattr(target_root, "is_below_half_strength", None)
        if not callable(below_half) or not bool(below_half()):
            return 0, ""
        return 1, "Hunter's Instincts"

    def skirmish_fighters_invulnerable_save(self, target_model, *, attack_type: str = "") -> tuple[int, str]:
        if not self.is_kroot_hunting_pack():
            return 0, ""
        if target_model is None:
            return 0, ""
        if not self._model_in_army(target_model):
            return 0, ""
        if not self._model_is_kroot(target_model):
            return 0, ""
        attack = str(attack_type or "").strip().lower()
        if attack == "melee":
            return 6, "Skirmish Fighters"
        if attack == "ranged":
            return 5, "Skirmish Fighters"
        return 0, ""

    def apply_kroot_hunting_pack_battleline_keywords(self, unit=None) -> None:
        if not self.is_kroot_hunting_pack() or self.army is None:
            return
        if unit is None:
            units = list(getattr(self.army, "units", []) or [])
        else:
            units = [unit]
        for entry in units:
            if entry is None:
                continue
            root = self._attached_root(entry)
            if root is None:
                continue
            get_parent_army = getattr(root, "get_parent_army", None)
            if not callable(get_parent_army):
                continue
            if get_parent_army() is not self.army:
                continue
            if not self._unit_is_kroot_carnivores(root):
                continue
            keywords = list(getattr(root, "keywords", []) or [])
            if not any(str(k or "").strip().lower() == "battleline" for k in keywords):
                keywords.append("Battleline")
                root.keywords = keywords

    def bonded_heroes_strength_ap_bonus(
        self,
        attacker_model,
        target_unit,
        *,
        weapon_profile=None,
        attack_instance=None,
    ) -> tuple[int, int, str]:
        del attack_instance
        if not self.is_retaliation_cadre():
            return 0, 0, ""
        if attacker_model is None or target_unit is None:
            return 0, 0, ""
        if not self._model_in_army(attacker_model):
            return 0, 0, ""
        if not self._model_is_tau_empire(attacker_model):
            return 0, 0, ""
        if not self._model_has_keyword(attacker_model, "BATTLESUIT"):
            return 0, 0, ""
        if not self._weapon_is_ranged(weapon_profile):
            return 0, 0, ""
        target_root = self._attached_root(target_unit)
        if target_root is None:
            return 0, 0, ""

        from ..utility.aura_utils import model_within_range_of_unit

        if model_within_range_of_unit(attacker_model, target_root, 9.0, use_attached_aggregate=True):
            return 1, 1, "Bonded Heroes"
        if model_within_range_of_unit(attacker_model, target_root, 12.0, use_attached_aggregate=True):
            return 1, 0, "Bonded Heroes"
        return 0, 0, ""

    @staticmethod
    def _battle_round_from_game(game) -> int:
        if game is None:
            return 0
        try:
            return int(getattr(game, "turn", 0) or 0)
        except Exception:
            return 0

    def is_montka(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Mont'ka")

    def _patient_hunter_round_active_for_unit(self, unit, *, game=None) -> bool:
        if not self.is_kauyon():
            return False
        if unit is None:
            return False
        if game is None:
            player = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(player, "game", None)
        battle_round = self._battle_round_from_game(game)
        return 3 <= battle_round <= 5

    def patient_hunter_sustained_hits_value(self, model, weapon_profile=None, *, game=None) -> tuple[int, str]:
        if model is None:
            return 0, ""
        if not self._model_in_army(model):
            return 0, ""
        if not self._model_is_tau_empire(model):
            return 0, ""
        if not self._weapon_is_ranged(weapon_profile):
            return 0, ""
        unit = getattr(model, "parent_unit", None)
        if not self._patient_hunter_round_active_for_unit(unit, game=game):
            return 0, ""
        return 1, "Patient Hunter"

    def patient_hunter_ignore_hit_modifiers_rule(
        self,
        attacker_model,
        *,
        target_unit=None,
        weapon_profile=None,
        game=None,
    ) -> dict | None:
        if attacker_model is None or target_unit is None:
            return None
        if not self._model_in_army(attacker_model):
            return None
        if not self._model_is_tau_empire(attacker_model):
            return None
        if not self._weapon_is_ranged(weapon_profile):
            return None
        unit = getattr(attacker_model, "parent_unit", None)
        if unit is None:
            return None
        if not self._patient_hunter_round_active_for_unit(unit, game=game):
            return None
        if not self._unit_is_guided_against_target(unit, target_unit, game=game):
            return None
        return {
            "name": "Patient Hunter",
            "attack_type": "ranged",
            "skill_kinds": {"ballistic"},
            "allow_hit": True,
        }

    @staticmethod
    def _attached_root(unit):
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
            if root is not None:
                return root
        return unit

    @staticmethod
    def _has_attached_leaders(unit) -> bool:
        if unit is None:
            return False
        try:
            leaders = list(getattr(unit, "attached_leaders", []) or [])
        except Exception:
            return False
        return bool(leaders)

    def _unit_has_active_exemplar_of_montka(self, unit) -> bool:
        root = self._attached_root(unit)
        if root is None:
            return False
        if not self._has_attached_leaders(root):
            return False

        checker = getattr(root, "_attached_unit_has_active_enhancement", None)
        if callable(checker):
            return bool(
                checker(
                    self._EXEMPLAR_OF_MONTKA_FLAG,
                    enhancement_id=self._EXEMPLAR_OF_MONTKA_ID,
                    enhancement_name=self._EXEMPLAR_OF_MONTKA_NAME,
                )
            )

        for leader in list(getattr(root, "attached_leaders", []) or []):
            sr = getattr(leader, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not sr.get(self._EXEMPLAR_OF_MONTKA_FLAG):
                continue
            bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
            if bearer_id:
                for model in list(getattr(leader, "models", []) or []):
                    if str(getattr(model, "id", getattr(model, "_id", "")) or "") != bearer_id:
                        continue
                    alive_attr = getattr(model, "is_alive", True)
                    alive = alive_attr() if callable(alive_attr) else bool(alive_attr)
                    if alive:
                        return True
                continue
            get_bearer = getattr(leader, "_get_enhancement_bearer_model", None)
            if callable(get_bearer) and get_bearer() is not None:
                return True
        return False

    @staticmethod
    def _enhancement_bearer_alive(unit) -> bool:
        if unit is None:
            return False
        sr = getattr(unit, "special_rules", None)
        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "") if isinstance(sr, dict) else ""
        if bearer_id:
            for model in list(getattr(unit, "models", []) or []):
                model_id = str(getattr(model, "id", getattr(model, "_id", "")) or "")
                if model_id != bearer_id:
                    continue
                alive_attr = getattr(model, "is_alive", True)
                return bool(alive_attr() if callable(alive_attr) else alive_attr)
            return False
        get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
        if callable(get_bearer):
            return get_bearer() is not None
        return False

    @staticmethod
    def _enhancement_bearer_model(unit):
        if unit is None:
            return None
        get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
        if callable(get_bearer):
            bearer = get_bearer()
            if bearer is not None:
                return bearer
        sr = getattr(unit, "special_rules", None)
        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "") if isinstance(sr, dict) else ""
        if bearer_id:
            for model in list(getattr(unit, "models", []) or []):
                model_id = str(getattr(model, "id", getattr(model, "_id", "")) or "")
                if model_id != bearer_id:
                    continue
                alive_attr = getattr(model, "is_alive", True)
                alive = alive_attr() if callable(alive_attr) else bool(alive_attr)
                if alive:
                    return model
            return None
        for model in list(getattr(unit, "models", []) or []):
            alive_attr = getattr(model, "is_alive", True)
            alive = alive_attr() if callable(alive_attr) else bool(alive_attr)
            if alive:
                return model
        return None

    def _unit_is_on_battlefield(self, unit) -> bool:
        root = self._attached_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        alive_fn = getattr(root, "is_alive", None)
        if callable(alive_fn) and not bool(alive_fn()):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        try:
            if bool(getattr(root, "is_embarked", False)):
                return False
        except Exception:
            pass
        try:
            is_in_reserves = getattr(root, "is_in_reserves", None)
            if callable(is_in_reserves) and bool(is_in_reserves()):
                return False
        except Exception:
            pass
        if getattr(root, "embarked_in", None) is not None:
            return False
        return True

    @staticmethod
    def _entity_id(entity) -> str:
        if entity is None:
            return ""
        value = getattr(entity, "id", None)
        if value:
            return str(value)
        value = getattr(entity, "_id", None)
        if value:
            return str(value)
        return ""

    def _unit_has_student_of_kauyon(self, unit) -> bool:
        if unit is None:
            return False
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict) and bool(sr.get(self._STUDENT_OF_KAUYON_FLAG)):
            return True
        enhancement = getattr(unit, "enhancement", None)
        if enhancement is None:
            return False
        enh_id = str(getattr(enhancement, "id", "") or "").strip()
        enh_name = str(getattr(enhancement, "name", "") or "").strip().lower()
        return bool(enh_id == self._STUDENT_OF_KAUYON_ID or enh_name == self._STUDENT_OF_KAUYON_NAME)

    def _iter_student_of_kauyon_sources(self) -> list:
        army = self.army
        if army is None:
            return []
        unique_by_id = {}
        for unit in list(getattr(army, "units", []) or []):
            if not self._unit_has_student_of_kauyon(unit):
                continue
            unit_id = self._entity_id(unit)
            if not unit_id:
                continue
            if unit_id in unique_by_id:
                continue
            unique_by_id[unit_id] = unit
        return [unique_by_id[k] for k in sorted(unique_by_id.keys())]

    def student_of_kauyon_selectable_units(self, source_unit, *, game=None) -> list:
        if source_unit is None:
            return []
        source_root = self._attached_root(source_unit)
        if source_root is None:
            return []
        if not self._unit_in_army(source_root):
            return []
        if not self._unit_has_student_of_kauyon(source_unit):
            return []
        if not self._enhancement_bearer_alive(source_unit):
            return []

        del game  # Selection only depends on army roster composition.
        unique_roots = {}
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._attached_root(unit)
            root_id = self._entity_id(root)
            if not root_id:
                continue
            if root_id in unique_roots:
                continue
            unique_roots[root_id] = root

        selectable = []
        for root_id in sorted(unique_roots.keys()):
            root = unique_roots[root_id]
            if not self._unit_is_student_of_kauyon_target(root):
                continue
            selectable.append(root)
        return selectable

    def _queue_student_of_kauyon_selection_requests(self, *, game=None) -> None:
        if not self.is_auxiliary_cadre():
            return
        army = self.army
        player = getattr(army, "player", None) if army is not None else None
        if game is None:
            game = getattr(player, "game", None)
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return

        from itertools import combinations

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        queue = getattr(game, "decision_queue", None)
        request_fn = getattr(game, "request_decision", None)
        for source_unit in self._iter_student_of_kauyon_sources():
            sr = getattr(source_unit, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if bool(sr.get(self._STUDENT_OF_KAUYON_RESOLVED_KEY)):
                continue
            source_unit_id = self._entity_id(source_unit)
            if not source_unit_id:
                continue

            duplicate = False
            if queue is not None and hasattr(queue, "list"):
                for pending in list(queue.list() or []):
                    if str(getattr(pending, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                        continue
                    pending_ctx = dict(getattr(pending, "context", {}) or {})
                    if str(pending_ctx.get("ability", "") or "") != "student_of_kauyon":
                        continue
                    if str(pending_ctx.get("source_unit_id", "") or "") != source_unit_id:
                        continue
                    duplicate = True
                    break
            if duplicate:
                continue

            selectable = self.student_of_kauyon_selectable_units(source_unit, game=game)
            try:
                max_units = int(sr.get(self._STUDENT_OF_KAUYON_MAX_UNITS_KEY, 3) or 3)
            except Exception:
                max_units = 3
            max_units = max(0, int(max_units))

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
                target_id = self._entity_id(target)
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
                        target_id = self._entity_id(target)
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
                sr[self._STUDENT_OF_KAUYON_SELECTED_UNIT_IDS_KEY] = []
                sr[self._STUDENT_OF_KAUYON_RESOLVED_KEY] = True
                source_unit.special_rules = sr
                continue

            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                "Student of Kauyon: select up to three friendly Kroot Carnivores or Kroot Farstalkers units.",
                player_id=getattr(player, "id", None),
                options=options,
                context={
                    "ability": "student_of_kauyon",
                    "ability_name": "Student of Kauyon",
                    "source_unit_id": source_unit_id,
                    "unit_id": source_unit_id,
                    "optional": True,
                    "max_selections": int(max_units),
                },
            )
            if callable(request_fn):
                request_fn(request)

    def _unit_has_strike_swiftly(self, unit) -> bool:
        if unit is None:
            return False
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict) and bool(sr.get(self._STRIKE_SWIFTLY_FLAG)):
            return True
        enhancement = getattr(unit, "enhancement", None)
        if enhancement is None:
            return False
        enh_id = str(getattr(enhancement, "id", "") or "").strip()
        enh_name = str(getattr(enhancement, "name", "") or "").strip().lower()
        return bool(enh_id == self._STRIKE_SWIFTLY_ID or enh_name == self._STRIKE_SWIFTLY_NAME)

    def _iter_strike_swiftly_sources(self) -> list:
        army = self.army
        if army is None:
            return []
        unique_by_id = {}
        for unit in list(getattr(army, "units", []) or []):
            if not self._unit_has_strike_swiftly(unit):
                continue
            unit_id = self._entity_id(unit)
            if not unit_id:
                continue
            if unit_id in unique_by_id:
                continue
            unique_by_id[unit_id] = unit
        return [unique_by_id[k] for k in sorted(unique_by_id.keys())]

    def strike_swiftly_selectable_units(self, source_unit, *, game=None) -> list:
        if source_unit is None:
            return []
        source_root = self._attached_root(source_unit)
        if source_root is None:
            return []
        if not self._unit_in_army(source_root):
            return []
        if not self._unit_has_strike_swiftly(source_unit):
            return []
        if not self._enhancement_bearer_alive(source_unit):
            return []
        if not self._unit_is_on_battlefield(source_unit):
            return []

        bearer_model = self._enhancement_bearer_model(source_unit)
        if bearer_model is None:
            return []

        sr = getattr(source_unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        try:
            selection_range = float(sr.get(self._STRIKE_SWIFTLY_SELECTION_RANGE_KEY, 6.0) or 6.0)
        except Exception:
            selection_range = 6.0
        if selection_range <= 0:
            return []

        del game  # The selector depends on current unit state/positions.
        from ..utility.aura_utils import model_within_range_of_unit

        unique_roots = {}
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._attached_root(unit)
            root_id = self._entity_id(root)
            if not root_id:
                continue
            if root_id in unique_roots:
                continue
            unique_roots[root_id] = root

        selectable = []
        for root_id in sorted(unique_roots.keys()):
            root = unique_roots[root_id]
            if not self._unit_in_army(root):
                continue
            if not self._unit_is_tau_empire(root):
                continue
            if not self._unit_is_on_battlefield(root):
                continue
            has_scout, _dist = root.has_scout()
            if has_scout:
                continue
            if not model_within_range_of_unit(bearer_model, root, float(selection_range), use_attached_aggregate=True):
                continue
            selectable.append(root)
        return selectable

    def _queue_strike_swiftly_selection_requests(self, *, game=None) -> None:
        if not self.is_montka():
            return
        army = self.army
        player = getattr(army, "player", None) if army is not None else None
        if game is None:
            game = getattr(player, "game", None)
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        if int(self._battle_round_from_game(game) or 0) != 1:
            return

        from itertools import combinations

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        queue = getattr(game, "decision_queue", None)
        request_fn = getattr(game, "request_decision", None)
        for source_unit in self._iter_strike_swiftly_sources():
            sr = getattr(source_unit, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if bool(sr.get(self._STRIKE_SWIFTLY_RESOLVED_KEY)):
                continue
            source_unit_id = self._entity_id(source_unit)
            if not source_unit_id:
                continue

            duplicate = False
            if queue is not None and hasattr(queue, "list"):
                for pending in list(queue.list() or []):
                    if str(getattr(pending, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                        continue
                    pending_ctx = dict(getattr(pending, "context", {}) or {})
                    if str(pending_ctx.get("ability", "") or "") != "strike_swiftly":
                        continue
                    if str(pending_ctx.get("source_unit_id", "") or "") != source_unit_id:
                        continue
                    duplicate = True
                    break
            if duplicate:
                continue

            selectable = self.strike_swiftly_selectable_units(source_unit, game=game)
            try:
                scout_distance = int(sr.get(self._STRIKE_SWIFTLY_SCOUT_DISTANCE_KEY, 6) or 6)
            except Exception:
                scout_distance = 6
            try:
                selection_range = float(sr.get(self._STRIKE_SWIFTLY_SELECTION_RANGE_KEY, 6.0) or 6.0)
            except Exception:
                selection_range = 6.0

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
                target_id = self._entity_id(target)
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
            for first, second in combinations(selectable, 2):
                first_id = self._entity_id(first)
                second_id = self._entity_id(second)
                if not first_id or not second_id:
                    continue
                options.append(
                    DecisionOption.create(
                        f"{getattr(first, 'name', 'Unit')} + {getattr(second, 'name', 'Unit')}",
                        payload={
                            "selected_unit_ids": [first_id, second_id],
                            "selection_kind": "two_units",
                        },
                    )
                )

            if len(options) <= 1:
                sr[self._STRIKE_SWIFTLY_SELECTED_UNIT_IDS_KEY] = []
                sr[self._STRIKE_SWIFTLY_RESOLVED_KEY] = True
                source_unit.special_rules = sr
                continue

            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                "Strike Swiftly: select up to two friendly T'AU EMPIRE units within 6\" of the bearer that do not have Scouts.",
                player_id=getattr(player, "id", None),
                options=options,
                context={
                    "ability": "strike_swiftly",
                    "ability_name": "Strike Swiftly",
                    "source_unit_id": source_unit_id,
                    "unit_id": source_unit_id,
                    "optional": True,
                    "max_selections": 2,
                    "selection_range": float(max(0.0, selection_range)),
                    "scout_distance": int(max(0, scout_distance)),
                },
            )
            if callable(request_fn):
                request_fn(request)

    def _unit_has_strategic_conqueror(self, unit) -> bool:
        if unit is None:
            return False
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict) and bool(sr.get(self._STRATEGIC_CONQUEROR_FLAG)):
            return True
        enhancement = getattr(unit, "enhancement", None)
        if enhancement is None:
            return False
        enh_id = str(getattr(enhancement, "id", "") or "").strip()
        enh_name = str(getattr(enhancement, "name", "") or "").strip().lower()
        return bool(enh_id == self._STRATEGIC_CONQUEROR_ID or enh_name == self._STRATEGIC_CONQUEROR_NAME)

    def _iter_strategic_conqueror_sources(self) -> list:
        army = self.army
        if army is None:
            return []
        unique_by_id = {}
        for unit in list(getattr(army, "units", []) or []):
            if not self._unit_has_strategic_conqueror(unit):
                continue
            unit_id = self._entity_id(unit)
            if not unit_id:
                continue
            if unit_id in unique_by_id:
                continue
            unique_by_id[unit_id] = unit
        return [unique_by_id[k] for k in sorted(unique_by_id.keys())]

    @staticmethod
    def _model_within_objective_marker(model, objective_point) -> bool:
        if model is None or objective_point is None:
            return False
        try:
            from shapely.geometry import Point as _ShPoint

            area = _ShPoint(objective_point.x, objective_point.y).buffer(
                float(getattr(objective_point, "control_radius", 0.0) or 0.0)
            )
        except Exception:
            area = None
        try:
            if area is not None:
                base = model.model_base.get_base_shape()
                if base.intersects(area):
                    return True
        except Exception:
            pass
        try:
            pos = model.get_location()
        except Exception:
            pos = None
        if not pos:
            return False
        try:
            dx = float(pos[0]) - float(getattr(objective_point, "x", 0.0))
            dy = float(pos[1]) - float(getattr(objective_point, "y", 0.0))
            radius = float(getattr(objective_point, "control_radius", 0.0) or 0.0)
            base_r = float(getattr(model.model_base, "get_radius", lambda: 1.0)())
            return (dx * dx + dy * dy) ** 0.5 <= (radius + base_r)
        except Exception:
            return False

    def _objective_by_id(self, objective_id: str, *, game=None, game_map=None):
        objective_id = str(objective_id or "").strip()
        if not objective_id:
            return None
        if game_map is None and game is not None:
            game_map = getattr(game, "map", None)
        for objective in list(getattr(game_map, "objectives", []) or []):
            if self._entity_id(objective) == objective_id:
                return objective
        for objective in list(getattr(game, "objectives", []) or []):
            if self._entity_id(objective) == objective_id:
                return objective
        return None

    def strategic_conqueror_objective_control_bonus(self, model, *, game=None, game_map=None) -> int:
        if not self.is_montka():
            return 0
        if model is None or not self._model_in_army(model):
            return 0
        if not self._model_is_tau_empire(model):
            return 0
        if game is None:
            player = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(player, "game", None)
        if game_map is None and game is not None:
            game_map = getattr(game, "map", None)
        if game_map is None and game is None:
            return 0

        bonus_total = 0
        for source_unit in self._iter_strategic_conqueror_sources():
            if not self._enhancement_bearer_alive(source_unit):
                continue
            if not self._unit_is_on_battlefield(source_unit):
                continue
            sr = getattr(source_unit, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            objective_id = str(sr.get(self._STRATEGIC_CONQUEROR_OBJECTIVE_ID_KEY, "") or "").strip()
            if not objective_id:
                continue
            objective = self._objective_by_id(objective_id, game=game, game_map=game_map)
            if objective is None:
                continue
            objective_point = getattr(objective, "location", None)
            if objective_point is None or bool(getattr(objective_point, "removed", False)):
                continue
            if not self._model_within_objective_marker(model, objective_point):
                continue
            try:
                bonus = int(sr.get(self._STRATEGIC_CONQUEROR_OC_BONUS_KEY, 1) or 1)
            except Exception:
                bonus = 1
            bonus_total += max(0, int(bonus))
        return int(bonus_total)

    def _queue_strategic_conqueror_selection_requests(self, *, game=None) -> None:
        if not self.is_montka():
            return
        army = self.army
        player = getattr(army, "player", None) if army is not None else None
        if game is None:
            game = getattr(player, "game", None)
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        objective_pool = list(getattr(game, "objectives", []) or [])
        if not objective_pool:
            objective_pool = list(getattr(getattr(game, "map", None), "objectives", []) or [])
        objectives = []
        for objective in objective_pool:
            objective_id = self._entity_id(objective)
            if not objective_id:
                continue
            objective_point = getattr(objective, "location", None)
            if objective_point is None or bool(getattr(objective_point, "removed", False)):
                continue
            objectives.append((objective_id, objective))
        objectives.sort(key=lambda item: str(item[0]))
        if not objectives:
            return

        queue = getattr(game, "decision_queue", None)
        for source_unit in self._iter_strategic_conqueror_sources():
            if not self._enhancement_bearer_alive(source_unit):
                continue
            sr = getattr(source_unit, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if str(sr.get(self._STRATEGIC_CONQUEROR_OBJECTIVE_ID_KEY, "") or "").strip():
                continue
            source_unit_id = self._entity_id(source_unit)
            if not source_unit_id:
                continue

            duplicate = False
            if queue is not None and hasattr(queue, "list"):
                for pending in list(queue.list() or []):
                    if str(getattr(pending, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                        continue
                    pending_ctx = dict(getattr(pending, "context", {}) or {})
                    if str(pending_ctx.get("ability", "") or "") != "strategic_conqueror":
                        continue
                    if str(pending_ctx.get("source_unit_id", "") or "") != source_unit_id:
                        continue
                    duplicate = True
                    break
            if duplicate:
                continue

            options = []
            for idx, (objective_id, objective) in enumerate(objectives):
                label = str(getattr(objective, "name", "") or f"Objective {idx + 1}")
                objective_point = getattr(objective, "location", None)
                try:
                    if objective_point is not None:
                        label = (
                            f"{label} "
                            f"({float(getattr(objective_point, 'x', 0.0)):.1f}, "
                            f"{float(getattr(objective_point, 'y', 0.0)):.1f})"
                        )
                except Exception:
                    pass
                options.append(DecisionOption.create(label, payload={"objective_id": objective_id}))
            if not options:
                continue

            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                "Strategic Conqueror: select one objective marker on the battlefield.",
                player_id=getattr(player, "id", None),
                options=options,
                context={
                    "ability": "strategic_conqueror",
                    "ability_name": "Strategic Conqueror",
                    "source_unit_id": source_unit_id,
                    "unit_id": source_unit_id,
                    "optional": False,
                },
            )
            request_fn = getattr(game, "request_decision", None)
            if callable(request_fn):
                request_fn(request)

    def on_prebattle_rules_start(self, *, game=None) -> None:
        self._queue_student_of_kauyon_selection_requests(game=game)
        self._queue_strike_swiftly_selection_requests(game=game)

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if int(battle_round or 0) != 1:
            return
        self._queue_strategic_conqueror_selection_requests(game=game)

    def _killing_blow_round_active(self, *, game=None) -> bool:
        if not self.is_montka():
            return False
        battle_round = self._battle_round_from_game(game)
        return 1 <= battle_round <= 3

    def _killing_blow_round_active_for_unit(self, unit, *, game=None) -> bool:
        if not self.is_montka():
            return False
        battle_round = self._battle_round_from_game(game)
        if 1 <= battle_round <= 3:
            return True
        if battle_round != 4:
            return False
        return self._unit_has_active_exemplar_of_montka(unit)

    def killing_blow_assault_applies(self, unit, weapon_profile=None, *, game=None) -> bool:
        if not self._killing_blow_round_active_for_unit(unit, game=game):
            return False
        if unit is None or not self._unit_in_army(unit):
            return False
        if not self._unit_is_tau_empire(unit):
            return False
        if weapon_profile is None:
            return True
        return self._weapon_is_ranged(weapon_profile)

    def _unit_is_guided_against_target(self, unit, target_unit, *, game=None) -> bool:
        if unit is None or target_unit is None:
            return False
        army = self.army
        if army is None:
            return False
        ftgg_mgr = getattr(army, "for_the_greater_good", None)
        if ftgg_mgr is None:
            return False
        bonus = ftgg_mgr.guided_attack_bonus(unit, target_unit)
        if not isinstance(bonus, dict):
            return False
        try:
            return int(bonus.get("bs_improve", 0) or 0) > 0
        except Exception:
            return bool(bonus.get("bs_improve"))

    def killing_blow_lethal_hits_applies(self, model, weapon_profile=None, *, target_unit=None, game=None) -> bool:
        if model is None or not self._model_in_army(model):
            return False
        if not self._model_is_tau_empire(model):
            return False
        if not self._weapon_is_ranged(weapon_profile):
            return False
        unit = getattr(model, "parent_unit", None)
        if unit is None:
            return False
        if not self._killing_blow_round_active_for_unit(unit, game=game):
            return False
        return self._unit_is_guided_against_target(unit, target_unit, game=game)

    def superior_craftsmanship_range_bonus(self, model, weapon_profile=None, *, game=None) -> int:
        del game  # Future-proofed signature; no phase/turn dependence for this rule.
        if not self.is_experimental_prototype_cadre():
            return 0
        if model is None or weapon_profile is None:
            return 0
        if not self._model_in_army(model):
            return 0
        if not self._model_is_tau_empire(model):
            return 0
        if not self._weapon_is_ranged(weapon_profile):
            return 0
        return 6
