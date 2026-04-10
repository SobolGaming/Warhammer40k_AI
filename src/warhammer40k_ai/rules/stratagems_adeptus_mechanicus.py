from __future__ import annotations

from typing import Any, Optional

import logging

from ..utility import dice as dice_module
from ..utility.aura_utils import unit_within_range_of_point_3d
from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class AdeptusMechanicusStratagemMixin:
    @staticmethod
    def _admech_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        return get_root() if callable(get_root) else unit

    @staticmethod
    def _admech_sort_key(unit: Any) -> str:
        return str(get_entity_id(unit) or "")

    def _get_adeptus_mechanicus_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        return getattr(army, "adeptus_mechanicus_detachments", None) if army is not None else None

    def _is_rad_zone_corps(self) -> bool:
        mgr = self._get_adeptus_mechanicus_mgr()
        checker = getattr(mgr, "is_rad_zone_corps", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_cohort_cybernetica(self) -> bool:
        mgr = self._get_adeptus_mechanicus_mgr()
        checker = getattr(mgr, "is_cohort_cybernetica", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_data_psalm_conclave(self) -> bool:
        mgr = self._get_adeptus_mechanicus_mgr()
        checker = getattr(mgr, "is_data_psalm_conclave", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_explorator_maniple(self) -> bool:
        mgr = self._get_adeptus_mechanicus_mgr()
        checker = getattr(mgr, "is_explorator_maniple", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_haloscreed_battle_clade(self) -> bool:
        mgr = self._get_adeptus_mechanicus_mgr()
        checker = getattr(mgr, "is_haloscreed_battle_clade", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_skitarii_hunter_cohort(self) -> bool:
        mgr = self._get_adeptus_mechanicus_mgr()
        checker = getattr(mgr, "is_skitarii_hunter_cohort", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _admech_owned_by_player(self, unit: Any) -> bool:
        if unit is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(parent_army, "player", None) is self.player

    def _admech_on_battlefield(self, unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        if not bool(getattr(unit, "deployed", False)):
            return False
        is_in_reserves = getattr(unit, "is_in_reserves", None)
        if callable(is_in_reserves):
            if bool(is_in_reserves()):
                return False
        elif bool(getattr(unit, "is_in_reserves", False)):
            return False
        if bool(getattr(unit, "is_embarked", False)) or bool(getattr(unit, "embarked_in", None)):
            return False
        return True

    @staticmethod
    def _admech_has_any_keyword(unit: Any, keyword: str) -> bool:
        if unit is None or not keyword:
            return False
        has_any_keyword = getattr(unit, "has_any_keyword", None)
        if callable(has_any_keyword):
            return bool(has_any_keyword(keyword))
        has_keyword = getattr(unit, "has_keyword", None)
        if callable(has_keyword):
            return bool(has_keyword(keyword))
        return False

    def _is_adeptus_mechanicus_unit(self, unit: Any) -> bool:
        root = self._admech_root(unit)
        if root is None:
            return False
        if not self._admech_owned_by_player(root):
            return False
        if self._admech_has_any_keyword(root, "ADEPTUS MECHANICUS"):
            return True
        faction_id = str(getattr(root, "faction_id", "") or "").strip().upper()
        return faction_id == "ADM"

    def _is_skitarii_unit(self, unit: Any) -> bool:
        root = self._admech_root(unit)
        if root is None:
            return False
        return self._admech_has_any_keyword(root, "SKITARII")

    def _is_battleline_unit(self, unit: Any) -> bool:
        root = self._admech_root(unit)
        if root is None:
            return False
        return self._admech_has_any_keyword(root, "BATTLELINE")

    @staticmethod
    def _admech_selected_to_move_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(
            getattr(round_state, "moved_this_round", False)
            or getattr(round_state, "advanced_this_round", False)
            or getattr(round_state, "fell_back_this_round", False)
        )

    def _admech_battlefield_units(
        self,
        *,
        require_not_shot: bool = False,
        require_not_moved: bool = False,
        require_not_fought: bool = False,
        require_skitarii: bool = False,
        exclude_battleline: bool = False,
    ) -> list[Any]:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._admech_root(unit)
            if root is None:
                continue
            uid = self._admech_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._admech_on_battlefield(root):
                continue
            if not self._admech_owned_by_player(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_adeptus_mechanicus_unit(root):
                continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if require_not_moved and self._admech_selected_to_move_this_phase(root):
                continue
            if require_not_fought and bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            if require_skitarii and not self._is_skitarii_unit(root):
                continue
            if exclude_battleline and self._is_battleline_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._admech_sort_key)

    def _rad_zone_lethal_dosage_primary_candidates(self) -> list[Any]:
        return self._admech_battlefield_units(require_not_shot=True)

    def _rad_zone_pre_calibrated_purge_solution_primary_candidates(self) -> list[Any]:
        return self._admech_battlefield_units(require_not_shot=True)

    def _rad_zone_aggressor_imperative_primary_candidates(self) -> list[Any]:
        return self._admech_battlefield_units(require_not_moved=True, require_skitarii=True)

    def _cohort_cybernetica_primary_candidates(
        self,
        *,
        require_vehicle: bool = False,
        allow_legio: bool = True,
        require_below_starting: bool = False,
    ) -> list[Any]:
        if not self._is_cohort_cybernetica():
            return []
        mgr = self._get_adeptus_mechanicus_mgr()
        eligible_fn = getattr(mgr, "_cohort_cybernetica_eligible_root", None) if mgr is not None else None
        if not callable(eligible_fn):
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._admech_root(unit)
            if root is None:
                continue
            uid = self._admech_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._admech_on_battlefield(root):
                continue
            if not self._admech_owned_by_player(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            candidate = eligible_fn(root, require_vehicle=require_vehicle, allow_legio=allow_legio)
            if candidate is None:
                continue
            if require_below_starting:
                below_starting_fn = getattr(candidate, "is_below_starting_strength", None)
                if not callable(below_starting_fn) or not bool(below_starting_fn()):
                    continue
            out.append(candidate)
        return sorted(out, key=self._admech_sort_key)

    def _cohort_auto_divinatory_primary_candidates(self) -> list[Any]:
        return self._cohort_cybernetica_primary_candidates(require_vehicle=False, allow_legio=True)

    def _cohort_benevolence_primary_candidates(self) -> list[Any]:
        return self._cohort_cybernetica_primary_candidates(require_vehicle=False, allow_legio=True)

    def _cohort_machine_spirit_primary_candidates(self) -> list[Any]:
        return self._cohort_cybernetica_primary_candidates(
            require_vehicle=False,
            allow_legio=True,
            require_below_starting=True,
        )

    def _cohort_machine_superiority_primary_candidates(self) -> list[Any]:
        return self._cohort_cybernetica_primary_candidates(require_vehicle=False, allow_legio=True)

    def _cohort_motive_imperative_primary_candidates(self) -> list[Any]:
        return self._cohort_cybernetica_primary_candidates(require_vehicle=True, allow_legio=False)

    def _cohort_transcendent_cogitation_primary_candidates(self) -> list[Any]:
        return self._cohort_cybernetica_primary_candidates(require_vehicle=False, allow_legio=True)

    def _cohort_auto_divinatory_objective_candidates(self, source_unit: Any) -> list[Any]:
        if not self._is_cohort_cybernetica():
            return []
        mgr = self._get_adeptus_mechanicus_mgr()
        eligible_fn = getattr(mgr, "_cohort_cybernetica_eligible_root", None) if mgr is not None else None
        if not callable(eligible_fn):
            return []
        source_root = self._admech_root(source_unit)
        if eligible_fn(source_root, require_vehicle=False, allow_legio=True) is None:
            return []
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for objective in list(getattr(game_map, "objectives", []) or []):
            if objective is None or getattr(objective, "location", None) is None:
                continue
            oid = self._admech_sort_key(objective)
            if oid and oid in seen:
                continue
            if oid:
                seen.add(oid)
            out.append(objective)
        return sorted(out, key=self._admech_sort_key)

    @staticmethod
    def _admech_unit_models(unit: Any) -> list[Any]:
        if unit is None:
            return []
        get_models = getattr(unit, "get_attached_unit_models", None)
        if callable(get_models):
            models = list(get_models() or [])
            if models:
                return models
        return list(getattr(unit, "models", []) or [])

    def _admech_distance_between_units(self, first: Any, second: Any) -> float | None:
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        distance_fn = getattr(game_map, "get_distance_between_units", None) if game_map is not None else None
        if not callable(distance_fn):
            return None
        try:
            return float(distance_fn(first, second))
        except (TypeError, ValueError):
            return None

    def _data_psalm_cult_mechanicus_primary_candidates(self, *, require_not_fought: bool = False) -> list[Any]:
        if not self._is_data_psalm_conclave():
            return []
        candidates = self._admech_battlefield_units(require_not_fought=require_not_fought)
        out = [unit for unit in list(candidates or []) if self._admech_has_any_keyword(unit, "CULT MECHANICUS")]
        return sorted(out, key=self._admech_sort_key)

    def _data_psalm_reactive_cult_mechanicus_candidates(
        self,
        *,
        target_units: list[Any] | None = None,
        require_not_fought: bool = False,
    ) -> list[Any]:
        if not self._is_data_psalm_conclave():
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._admech_root(unit)
            if root is None:
                continue
            uid = self._admech_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._admech_on_battlefield(root):
                continue
            if not self._admech_owned_by_player(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._admech_has_any_keyword(root, "CULT MECHANICUS"):
                continue
            if require_not_fought and bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            out.append(root)
        return sorted(out, key=self._admech_sort_key)

    def _data_psalm_mortal_wound_reaction_candidates(self, target_unit: Any) -> list[Any]:
        return self._data_psalm_reactive_cult_mechanicus_candidates(target_units=[target_unit])

    def _data_psalm_tribute_enemy_candidates(self, source_unit: Any) -> list[Any]:
        if not self._is_data_psalm_conclave():
            return []
        source_root = self._admech_root(source_unit)
        if source_root not in self._data_psalm_cult_mechanicus_primary_candidates():
            return []
        out: list[Any] = []
        for enemy in self._admech_enemy_battlefield_units():
            distance = self._admech_distance_between_units(source_root, enemy)
            if distance is None or distance > 18.0 + 1e-6:
                continue
            out.append(enemy)
        return sorted(out, key=self._admech_sort_key)

    def _data_psalm_electromancer_enemy_candidates(self, source_unit: Any) -> list[Any]:
        if not self._is_data_psalm_conclave():
            return []
        source_root = self._admech_root(source_unit)
        if source_root not in self._data_psalm_cult_mechanicus_primary_candidates():
            return []
        out: list[Any] = []
        for enemy in self._admech_enemy_battlefield_units():
            distance = self._admech_distance_between_units(source_root, enemy)
            if distance is None or distance > 6.0 + 1e-6:
                continue
            out.append(enemy)
        return sorted(out, key=self._admech_sort_key)

    def _explorator_auto_oracular_primary_candidates(self) -> list[Any]:
        if not self._is_explorator_maniple():
            return []
        out: list[Any] = []
        for unit in list(self._admech_battlefield_units() or []):
            round_state = getattr(unit, "round_state", None)
            if not bool(getattr(round_state, "disembarked_this_round", False)):
                continue
            out.append(unit)
        return sorted(out, key=self._admech_sort_key)

    def _explorator_infoslave_tech_priest_candidates(self) -> list[Any]:
        if not self._is_explorator_maniple():
            return []
        out = [unit for unit in list(self._admech_battlefield_units() or []) if self._admech_has_any_keyword(unit, "TECH-PRIEST")]
        return sorted(out, key=self._admech_sort_key)

    def _explorator_infoslave_objective_candidates(self, source_unit: Any) -> list[Any]:
        if not self._is_explorator_maniple():
            return []
        source_root = self._admech_root(source_unit)
        if source_root is None or source_root not in self._explorator_infoslave_tech_priest_candidates():
            return []
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None:
            return []
        mgr = self._get_adeptus_mechanicus_mgr()
        active_ids_fn = getattr(mgr, "explorator_active_acquisition_objective_ids", None) if mgr is not None else None
        active_ids = set(active_ids_fn(game=self.game, game_map=game_map) or []) if callable(active_ids_fn) else set()
        out: list[Any] = []
        seen: set[str] = set()
        for objective in list(getattr(game_map, "objectives", []) or []):
            if objective is None:
                continue
            objective_id = self._admech_sort_key(objective)
            if objective_id and objective_id in seen:
                continue
            if objective_id:
                seen.add(objective_id)
            if objective_id in active_ids:
                continue
            loc = getattr(objective, "location", None)
            if loc is None or bool(getattr(loc, "removed", False)):
                continue
            point = (float(getattr(loc, "x", 0.0) or 0.0), float(getattr(loc, "y", 0.0) or 0.0))
            if not unit_within_range_of_point_3d(source_root, point, 24.0, use_attached_aggregate=True):
                continue
            out.append(objective)
        return sorted(out, key=self._admech_sort_key)

    def _explorator_incense_primary_candidates(self, *, target_units: list[Any] | None = None) -> list[Any]:
        if not self._is_explorator_maniple():
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._admech_root(unit)
            if root is None:
                continue
            uid = self._admech_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._admech_on_battlefield(root):
                continue
            if not self._admech_owned_by_player(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_adeptus_mechanicus_unit(root):
                continue
            if not self._admech_has_any_keyword(root, "INFANTRY"):
                continue
            out.append(root)
        return sorted(out, key=self._admech_sort_key)

    def _explorator_incense_support_candidates(self, primary_unit: Any) -> list[Any]:
        if not self._is_explorator_maniple():
            return []
        primary_root = self._admech_root(primary_unit)
        if primary_root is None or primary_root not in self._admech_battlefield_units():
            return []
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        distance_fn = getattr(game_map, "get_distance_between_units", None) if game_map is not None else None
        if not callable(distance_fn):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for candidate in list(self._admech_battlefield_units() or []):
            uid = self._admech_sort_key(candidate)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._admech_has_any_keyword(candidate, "SMOKE"):
                continue
            try:
                distance = float(distance_fn(primary_root, candidate))
            except (TypeError, ValueError):
                continue
            if distance > 6.0 + 1e-6:
                continue
            out.append(candidate)
        return sorted(out, key=self._admech_sort_key)

    def _explorator_cached_acquisition_objective_candidates(self, destroyed_unit: Any, *, last_model: Any = None) -> list[Any]:
        if not self._is_explorator_maniple():
            return []
        root = self._admech_root(destroyed_unit)
        if root is None or not self._admech_owned_by_player(root) or not self._is_adeptus_mechanicus_unit(root):
            return []
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return []
        mgr = self._get_adeptus_mechanicus_mgr()
        model_within_fn = getattr(mgr, "_model_within_objective_range", None) if mgr is not None else None
        snapshot = getattr(game, "_objective_control_snapshot", {}) if game is not None else {}
        out: list[Any] = []
        seen: set[str] = set()
        for objective in list(getattr(game_map, "objectives", []) or []):
            if objective is None:
                continue
            objective_id = self._admech_sort_key(objective)
            if objective_id and objective_id in seen:
                continue
            if objective_id:
                seen.add(objective_id)
            loc = getattr(objective, "location", None)
            if loc is None or bool(getattr(loc, "removed", False)):
                continue
            controller = snapshot.get(loc)
            if controller is not self.player and getattr(loc, "sticky_controller", None) is not self.player:
                continue
            within = False
            is_within = getattr(root, "is_within_objective_range", None)
            if callable(is_within):
                within = bool(is_within(loc))
            if not within and last_model is not None and callable(model_within_fn):
                within = bool(model_within_fn(last_model, loc))
            if within:
                out.append(objective)
        return sorted(out, key=self._admech_sort_key)

    def _explorator_priority_reclamation_candidates(self, unit: Any) -> list[Any]:
        if not self._is_explorator_maniple():
            return []
        root = self._admech_root(unit)
        if root is None:
            return []
        if not self._admech_on_battlefield(root):
            return []
        if not self._admech_owned_by_player(root):
            return []
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            return []
        if not self._is_adeptus_mechanicus_unit(root):
            return []
        mgr = self._get_adeptus_mechanicus_mgr()
        active_ids_fn = getattr(mgr, "explorator_active_acquisition_objective_ids", None) if mgr is not None else None
        active_ids = list(active_ids_fn(game=self.game, game_map=getattr(self.game, "map", None)) or []) if callable(active_ids_fn) else []
        if not active_ids:
            return []
        return [root]

    def _explorator_reactive_safeguard_candidates(
        self,
        *,
        charging_unit: Any = None,
        target_units: list[Any] | None = None,
    ) -> list[Any]:
        if not self._is_explorator_maniple():
            return []
        attacker_root = self._admech_root(charging_unit)
        if attacker_root is None or self._admech_owned_by_player(attacker_root):
            return []
        mgr = self._get_adeptus_mechanicus_mgr()
        within_fn = getattr(mgr, "explorator_unit_within_acquisition_objective", None) if mgr is not None else None
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._admech_root(unit)
            if root is None:
                continue
            uid = self._admech_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._admech_on_battlefield(root):
                continue
            if not self._admech_owned_by_player(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_adeptus_mechanicus_unit(root):
                continue
            if not self._admech_has_any_keyword(root, "INFANTRY"):
                continue
            if callable(within_fn) and not bool(within_fn(root, game=self.game, game_map=getattr(self.game, "map", None))):
                continue
            out.append(root)
        return sorted(out, key=self._admech_sort_key)

    def _explorator_reactive_safeguard_transport_candidates(self, primary_unit: Any) -> list[Any]:
        if not self._is_explorator_maniple():
            return []
        primary_root = self._admech_root(primary_unit)
        if primary_root is None:
            return []
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None:
            return []
        from ..utility.aura_utils import unit_wholly_within_range_of_unit

        enemies = list(game_map.get_enemy_units(primary_root) or [])
        if any(enemy is not None and game_map.is_within_engagement_range(primary_root, enemy) for enemy in enemies):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for transport in list(self._admech_battlefield_units() or []):
            tid = self._admech_sort_key(transport)
            if tid and tid in seen:
                continue
            if tid:
                seen.add(tid)
            if transport is primary_root:
                continue
            if not self._admech_has_any_keyword(transport, "TRANSPORT"):
                continue
            if not bool(unit_wholly_within_range_of_unit(transport, primary_root, 3.0, use_attached_aggregate=True)):
                continue
            can_transport = getattr(transport, "can_transport", None)
            if not callable(can_transport) or not bool(can_transport(primary_root)):
                continue
            out.append(transport)
        return sorted(out, key=self._admech_sort_key)

    @staticmethod
    def _admech_unit_name(unit: Any) -> str:
        return str(getattr(unit, "name", "") or "").strip().upper()

    def _haloscreed_phase_buff_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
    ) -> list[Any]:
        if not self._is_haloscreed_battle_clade():
            return []
        return self._admech_battlefield_units(
            require_not_shot=require_not_shot,
            require_not_fought=require_not_fought,
        )

    def _haloscreed_neural_overload_candidates(self) -> list[Any]:
        if not self._is_haloscreed_battle_clade():
            return []
        return self._admech_battlefield_units()

    def _haloscreed_aggressive_impulse_candidates(self) -> list[Any]:
        if not self._is_haloscreed_battle_clade():
            return []
        out = [
            unit
            for unit in list(self._admech_battlefield_units(require_not_moved=True) or [])
            if self._admech_unit_name(unit) == "SKORPIUS DUNERIDER"
        ]
        return sorted(out, key=self._admech_sort_key)

    def _haloscreed_guided_retreat_candidates(self, *, unit: Any = None, action: str = "") -> list[Any]:
        if not self._is_haloscreed_battle_clade():
            return []
        action_key = str(action or "").strip().lower().replace("-", "_").replace(" ", "_")
        if action_key != "fall_back":
            return []
        root = self._admech_root(unit)
        if root is None:
            return []
        if not self._admech_on_battlefield(root) or not self._admech_owned_by_player(root):
            return []
        if bool(self._unit_cannot_be_target_of_stratagem(root)) or not self._is_adeptus_mechanicus_unit(root):
            return []
        if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
            return []
        return [root]

    def _haloscreed_analytical_divination_candidates(self, *, moving_unit: Any = None) -> list[Any]:
        if not self._is_haloscreed_battle_clade():
            return []
        enemy_root = self._admech_root(moving_unit)
        if enemy_root is None or self._admech_owned_by_player(enemy_root):
            return []
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None:
            return []
        out: list[Any] = []
        for root in list(self._admech_battlefield_units() or []):
            if not self._admech_has_any_keyword(root, "INFANTRY"):
                continue
            if self._admech_has_any_keyword(root, "KATAPHRON") or "KATAPHRON" in self._admech_unit_name(root):
                continue
            distance = self._admech_distance_between_units(root, enemy_root)
            if distance is None or distance > 9.0 + 1e-6:
                continue
            enemies = list(game_map.get_enemy_units(root) or [])
            if any(
                enemy is not None and game_map.is_within_engagement_range(root, enemy)
                for enemy in enemies
            ):
                continue
            out.append(root)
        return sorted(out, key=self._admech_sort_key)

    def _queue_explorator_incense_exhausts_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any] | None = None,
    ) -> None:
        if not self._is_explorator_maniple():
            return
        if attacking_unit is None:
            return
        stratagem = self.get_by_name("INCENSE EXHAUSTS")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        primary_candidates = self._explorator_incense_primary_candidates(target_units=target_units)
        eligible_primary = [
            candidate
            for candidate in list(primary_candidates or [])
            if self._explorator_incense_support_candidates(candidate)
            and self._admech_effective_cp_cost(stratagem, target_unit=candidate) <= int(getattr(self.player, "command_points", 0) or 0)
        ]
        if not eligible_primary:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "shooting_targets_selected"
                and reaction.get("stratagem") == stratagem.name
                and reaction.get("attacking_unit") is attacking_unit
            ):
                return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": eligible_primary,
        }
        if len(eligible_primary) == 1:
            support_candidates = self._explorator_incense_support_candidates(eligible_primary[0])
            payload["target_unit"] = eligible_primary[0]
            payload["unit"] = eligible_primary[0]
            if len(support_candidates) == 1:
                payload["support_unit"] = support_candidates[0]
                payload["secondary_unit"] = support_candidates[0]
        self._queue_reaction(payload)

    def _queue_explorator_cached_acquisition_reactions(self, *, destroyed_unit: Any, last_model: Any = None) -> None:
        if not self._is_explorator_maniple():
            return
        root = self._admech_root(destroyed_unit)
        if root is None:
            return
        stratagem = self.get_by_name("CACHED ACQUISITION")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        objective_candidates = self._explorator_cached_acquisition_objective_candidates(root, last_model=last_model)
        if not objective_candidates:
            return
        if self._admech_effective_cp_cost(stratagem, target_unit=root) > int(getattr(self.player, "command_points", 0) or 0):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "unit_destroyed"
                and reaction.get("stratagem") == stratagem.name
                and self._admech_root(reaction.get("unit")) is root
            ):
                return
        payload = {
            "event": "unit_destroyed",
            "phase_name": str(self._current_phase_name or ""),
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "destroyed_unit": root,
            "last_model": last_model,
            "objective_candidates": objective_candidates,
        }
        if len(objective_candidates) == 1:
            payload["objective"] = objective_candidates[0]
        self._queue_reaction(payload)

    def _queue_explorator_priority_reclamation_reactions(self, *, unit: Any, target_unit: Any = None) -> None:
        if not self._is_explorator_maniple():
            return
        root = self._admech_root(unit)
        if root is None:
            return
        stratagem = self.get_by_name("PRIORITY RECLAMATION")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._explorator_priority_reclamation_candidates(root)
        if not candidates:
            return
        if self._admech_effective_cp_cost(stratagem, target_unit=root) > int(getattr(self.player, "command_points", 0) or 0):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "before_consolidate"
                and reaction.get("stratagem") == stratagem.name
                and self._admech_root(reaction.get("unit")) is root
            ):
                return
        self._queue_reaction(
            {
                "event": "before_consolidate",
                "phase_name": "Fight phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": root,
                "target_unit": root,
                "last_target_unit": target_unit,
                "candidates": candidates,
            }
        )

    def _queue_explorator_reactive_safeguard_reactions(
        self,
        *,
        charging_unit: Any,
        target_units: list[Any] | None = None,
    ) -> None:
        if not self._is_explorator_maniple():
            return
        attacker_root = self._admech_root(charging_unit)
        if attacker_root is None:
            return
        stratagem = self.get_by_name("REACTIVE SAFEGUARD")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        primary_candidates = self._explorator_reactive_safeguard_candidates(
            charging_unit=attacker_root,
            target_units=target_units,
        )
        eligible_primary = [
            candidate
            for candidate in list(primary_candidates or [])
            if self._explorator_reactive_safeguard_transport_candidates(candidate)
            and self._admech_effective_cp_cost(stratagem, target_unit=candidate) <= int(getattr(self.player, "command_points", 0) or 0)
        ]
        if not eligible_primary:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "charge_declared"
                and reaction.get("stratagem") == stratagem.name
                and reaction.get("attacking_unit") is attacker_root
            ):
                return
        payload = {
            "event": "charge_declared",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "charging_unit": attacker_root,
            "attacking_unit": attacker_root,
            "enemy_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": eligible_primary,
        }
        if len(eligible_primary) == 1:
            transport_candidates = self._explorator_reactive_safeguard_transport_candidates(eligible_primary[0])
            payload["target_unit"] = eligible_primary[0]
            payload["unit"] = eligible_primary[0]
            if len(transport_candidates) == 1:
                payload["transport_unit"] = transport_candidates[0]
        self._queue_reaction(payload)

    def _queue_haloscreed_guided_retreat_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_haloscreed_battle_clade():
            return
        if self.game is None:
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        stratagem = self.get_by_name("GUIDED RETREAT")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._haloscreed_guided_retreat_candidates(unit=unit, action=action)
        if not candidates:
            return
        root = candidates[0]
        if self._admech_effective_cp_cost(stratagem, target_unit=root) > int(getattr(self.player, "command_points", 0) or 0):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "unit_move_ended"
                and reaction.get("stratagem") == stratagem.name
                and self._admech_root(reaction.get("unit")) is root
            ):
                return
        self._queue_reaction(
            {
                "event": "unit_move_ended",
                "phase_name": "Movement phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": root,
                "target_unit": root,
                "action": "fall_back",
                "candidates": candidates,
            }
        )

    def _queue_haloscreed_analytical_divination_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_haloscreed_battle_clade():
            return
        if self.game is None:
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        action_key = str(action or "").strip().lower().replace("-", "_").replace(" ", "_")
        if action_key not in {"move", "normal_move", "advance", "fall_back"}:
            return
        enemy_root = self._admech_root(unit)
        if enemy_root is None or self._admech_owned_by_player(enemy_root):
            return
        stratagem = self.get_by_name("ANALYTICAL DIVINATION")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._haloscreed_analytical_divination_candidates(moving_unit=enemy_root)
        if not candidates:
            return
        affordable = [
            candidate
            for candidate in list(candidates or [])
            if self._admech_effective_cp_cost(stratagem, target_unit=candidate) <= int(getattr(self.player, "command_points", 0) or 0)
        ]
        if not affordable:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "unit_move_ended"
                and reaction.get("stratagem") == stratagem.name
                and self._admech_root(reaction.get("moving_unit")) is enemy_root
            ):
                return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "moving_unit": enemy_root,
            "action": action_key,
            "candidates": affordable,
        }
        if len(affordable) == 1:
            payload["unit"] = affordable[0]
            payload["target_unit"] = affordable[0]
        self._queue_reaction(payload)

    def _queue_data_psalm_luminescent_blessing_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any] | None = None,
    ) -> None:
        if not self._is_data_psalm_conclave():
            return
        if attacking_unit is None:
            return
        stratagem = self.get_by_name("LUMINESCENT BLESSING")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._data_psalm_reactive_cult_mechanicus_candidates(target_units=target_units)
        if not candidates:
            return
        affordable = False
        for candidate in list(candidates):
            if self._admech_effective_cp_cost(stratagem, target_unit=candidate) <= int(getattr(self.player, "command_points", 0) or 0):
                affordable = True
                break
        if not affordable:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "shooting_targets_selected"
                and reaction.get("stratagem") == stratagem.name
                and reaction.get("attacking_unit") is attacking_unit
            ):
                return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_data_psalm_verse_of_vengeance_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any] | None = None,
    ) -> None:
        if not self._is_data_psalm_conclave():
            return
        if attacking_unit is None:
            return
        stratagem = self.get_by_name("VERSE OF VENGEANCE")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._data_psalm_reactive_cult_mechanicus_candidates(
            target_units=target_units,
            require_not_fought=True,
        )
        if not candidates:
            return
        affordable = False
        for candidate in list(candidates):
            if self._admech_effective_cp_cost(stratagem, target_unit=candidate) <= int(getattr(self.player, "command_points", 0) or 0):
                affordable = True
                break
        if not affordable:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "fight_targets_selected"
                and reaction.get("stratagem") == stratagem.name
                and reaction.get("attacking_unit") is attacking_unit
            ):
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_data_psalm_mortal_wound_reactions(
        self,
        *,
        target_unit: Any,
        attacker_unit: Any = None,
        target_model: Any = None,
        phase_name: str = "",
    ) -> None:
        if not self._is_data_psalm_conclave():
            return
        candidates = self._data_psalm_mortal_wound_reaction_candidates(target_unit)
        if not candidates:
            return
        stratagem = self.get_by_name("INCANTATION OF THE IRON SOUL")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        root = candidates[0]
        if self._admech_effective_cp_cost(stratagem, target_unit=root) > int(getattr(self.player, "command_points", 0) or 0):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "mortal_wound_allocated"
                and reaction.get("stratagem") == stratagem.name
                and self._admech_root(reaction.get("target_unit")) is root
            ):
                return
        self._queue_reaction(
            {
                "event": "mortal_wound_allocated",
                "phase_name": str(phase_name or self._current_phase_name or ""),
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "target_unit": root,
                "target_model": target_model,
                "attacker_unit": attacker_unit,
                "mortal_wound_allocated": True,
                "candidates": [root],
            }
        )

    def _rad_zone_baleful_halo_primary_candidates(self, *, target_units: list[Any] | None = None) -> list[Any]:
        if not self._is_rad_zone_corps():
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._admech_root(unit)
            if root is None:
                continue
            uid = self._admech_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._admech_on_battlefield(root):
                continue
            if not self._admech_owned_by_player(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_adeptus_mechanicus_unit(root):
                continue
            if bool(getattr(root, "is_vehicle", False)) or self._admech_has_any_keyword(root, "VEHICLE"):
                continue
            out.append(root)
        return sorted(out, key=self._admech_sort_key)

    def _rad_zone_bulwark_imperative_primary_candidates(self, *, target_units: list[Any] | None = None) -> list[Any]:
        if not self._is_rad_zone_corps():
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._admech_root(unit)
            if root is None:
                continue
            uid = self._admech_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._admech_on_battlefield(root):
                continue
            if not self._admech_owned_by_player(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_skitarii_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._admech_sort_key)

    def _rad_zone_optional_skitarii_support_candidates(self, primary_unit: Any) -> list[Any]:
        primary_root = self._admech_root(primary_unit)
        if primary_root is None or not self._is_battleline_unit(primary_root):
            return []
        candidates = self._admech_battlefield_units(require_skitarii=True, exclude_battleline=True)
        if not candidates:
            return []
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None:
            return []
        distance_fn = getattr(game_map, "get_distance_between_units", None)
        if not callable(distance_fn):
            return []
        out: list[Any] = []
        for candidate in list(candidates or []):
            if candidate is primary_root:
                continue
            try:
                distance = float(distance_fn(primary_root, candidate))
            except (TypeError, ValueError):
                continue
            if distance <= 6.0 + 1e-6:
                out.append(candidate)
        return sorted(out, key=self._admech_sort_key)

    def _rad_zone_aggressor_optional_skitarii_support_candidates(self, primary_unit: Any) -> list[Any]:
        candidates = self._rad_zone_optional_skitarii_support_candidates(primary_unit)
        out = [unit for unit in list(candidates or []) if not self._admech_selected_to_move_this_phase(unit)]
        return sorted(out, key=self._admech_sort_key)

    def _rad_zone_extinction_order_tech_priest_candidates(self) -> list[Any]:
        candidates = self._admech_battlefield_units()
        out = [unit for unit in list(candidates or []) if self._admech_has_any_keyword(unit, "TECH-PRIEST")]
        return sorted(out, key=self._admech_sort_key)

    def _rad_zone_extinction_order_objective_candidates(self, source_unit: Any) -> list[Any]:
        source_root = self._admech_root(source_unit)
        if source_root is None:
            return []
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for objective in list(getattr(game_map, "objectives", []) or []):
            if objective is None:
                continue
            oid = self._admech_sort_key(objective)
            if oid and oid in seen:
                continue
            if oid:
                seen.add(oid)
            loc = getattr(objective, "location", None)
            if loc is None or bool(getattr(loc, "removed", False)):
                continue
            point = (float(getattr(loc, "x", 0.0) or 0.0), float(getattr(loc, "y", 0.0) or 0.0))
            if not unit_within_range_of_point_3d(source_root, point, 24.0, use_attached_aggregate=True):
                continue
            out.append(objective)
        return sorted(out, key=self._admech_sort_key)

    def _admech_enemy_battlefield_units(self) -> list[Any]:
        game = getattr(self, "game", None)
        if game is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for other_player in list(getattr(game, "players", []) or []):
            if other_player is None or other_player is self.player:
                continue
            get_army = getattr(other_player, "get_army", None)
            enemy_army = get_army() if callable(get_army) else getattr(other_player, "army", None)
            if enemy_army is None:
                continue
            for enemy_unit in list(getattr(enemy_army, "units", []) or []):
                root = self._admech_root(enemy_unit)
                if root is None:
                    continue
                uid = self._admech_sort_key(root)
                if uid and uid in seen:
                    continue
                if uid:
                    seen.add(uid)
                if self._admech_owned_by_player(root):
                    continue
                if not self._admech_on_battlefield(root):
                    continue
                out.append(root)
        return sorted(out, key=self._admech_sort_key)

    def _rad_zone_extinction_order_enemy_units_for_objective(self, objective: Any) -> list[Any]:
        loc = getattr(objective, "location", None) if objective is not None else None
        if loc is None:
            return []
        out: list[Any] = []
        for enemy in self._admech_enemy_battlefield_units():
            in_range = getattr(enemy, "is_within_objective_range", None)
            if not callable(in_range):
                continue
            if not bool(in_range(loc)):
                continue
            out.append(enemy)
        return sorted(out, key=self._admech_sort_key)

    def _queue_rad_zone_bulwark_shooting_reactions(self, *, attacking_unit: Any, target_units: list[Any] | None = None) -> None:
        if not self._is_rad_zone_corps():
            return
        if attacking_unit is None:
            return
        stratagem = self.get_by_name("BULWARK IMPERATIVE")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._rad_zone_bulwark_imperative_primary_candidates(target_units=target_units)
        if not candidates:
            return
        affordable = False
        for candidate in list(candidates):
            if self._admech_effective_cp_cost(stratagem, target_unit=candidate) <= int(getattr(self.player, "command_points", 0) or 0):
                affordable = True
                break
        if not affordable:
            return
        for reaction in list(self._pending_reactions):
            if (
                reaction.get("event") == "shooting_targets_selected"
                and reaction.get("stratagem") == stratagem.name
                and reaction.get("attacking_unit") is attacking_unit
            ):
                return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_rad_zone_baleful_fight_reactions(self, *, attacking_unit: Any, target_units: list[Any] | None = None) -> None:
        if not self._is_rad_zone_corps():
            return
        if attacking_unit is None:
            return
        stratagem = self.get_by_name("BALEFUL HALO")
        if stratagem is None:
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._rad_zone_baleful_halo_primary_candidates(target_units=target_units)
        if not candidates:
            return
        affordable = False
        for candidate in list(candidates):
            if self._admech_effective_cp_cost(stratagem, target_unit=candidate) <= int(getattr(self.player, "command_points", 0) or 0):
                affordable = True
                break
        if not affordable:
            return
        for reaction in list(self._pending_reactions):
            if (
                reaction.get("event") == "fight_targets_selected"
                and reaction.get("stratagem") == stratagem.name
                and reaction.get("attacking_unit") is attacking_unit
            ):
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _admech_resolve_unit_from_kwargs(self, kwargs: dict[str, Any], *, key: str, fallback_key: str = "") -> Any:
        value = kwargs.get(key)
        if value is None and fallback_key:
            value = kwargs.get(fallback_key)
        if value is not None:
            return self._admech_root(value)
        key_id = f"{key}_id"
        value_id = str(kwargs.get(key_id, "") or "")
        if not value_id and fallback_key:
            fallback_id = f"{fallback_key}_id"
            value_id = str(kwargs.get(fallback_id, "") or "")
        if not value_id:
            return None
        resolver = getattr(self.game, "_resolve_unit_by_id", None) if self.game is not None else None
        if not callable(resolver):
            return None
        return self._admech_root(resolver(value_id))

    def _admech_resolve_objective_from_kwargs(self, kwargs: dict[str, Any]) -> Any:
        objective = kwargs.get("objective") or kwargs.get("objective_marker")
        if objective is not None:
            return objective
        objective_id = str(kwargs.get("objective_id", "") or "").strip()
        if not objective_id:
            return None
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None:
            return None
        for candidate in list(getattr(game_map, "objectives", []) or []):
            if str(get_entity_id(candidate) or "") == objective_id:
                return candidate
        return None

    def _admech_effective_cp_cost(self, stratagem: Any, *, target_unit: Any = None) -> int:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        preview = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(preview):
            data = preview(stratagem, target_unit=target_unit) or {}
            cp_cost = int(data.get("cost", cp_cost))
        return cp_cost

    def _admech_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        cp_cost = self._admech_effective_cp_cost(stratagem, target_unit=target_unit)
        return bool(
            self.player.spend_command_points(
                cp_cost,
                reason=f"Stratagem: {stratagem.name}",
                source="stratagem",
            )
        )

    def _admech_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())

    def _rad_zone_opponent_player_id(self) -> str:
        if self.game is None:
            return ""
        for player in list(getattr(self.game, "players", []) or []):
            if player is not None and player is not self.player:
                return str(getattr(player, "id", "") or "")
        return ""

    def _mark_rad_zone_lethal_dosage(self, unit: Any, *, source_name: str) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["rad_zone_lethal_dosage_active"] = True
        sr["rad_zone_lethal_dosage_expires_phase"] = "SHOOTING_PHASE"
        sr["rad_zone_lethal_dosage_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["rad_zone_lethal_dosage_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["rad_zone_lethal_dosage_source"] = source_name
        unit.special_rules = sr

    def _mark_rad_zone_pre_calibrated(self, unit: Any, *, source_name: str, enemy_player_id: str) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["rad_zone_pre_calibrated_purge_solution_active"] = True
        sr["rad_zone_pre_calibrated_purge_solution_expires_phase"] = "SHOOTING_PHASE"
        sr["rad_zone_pre_calibrated_purge_solution_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["rad_zone_pre_calibrated_purge_solution_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["rad_zone_pre_calibrated_purge_solution_source"] = source_name
        sr["rad_zone_pre_calibrated_purge_solution_enemy_player_id"] = str(enemy_player_id or "")
        unit.special_rules = sr

    def _mark_rad_zone_aggressor_imperative(self, unit: Any, *, source_name: str) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        effect_tag = "stratagem:rad_zone_aggressor_imperative"
        effects = [
            entry
            for entry in list(sr.get("advance_no_roll_effects", []) or [])
            if not (isinstance(entry, dict) and str(entry.get("tag", "") or "") == effect_tag)
        ]
        effects.append(
            {
                "distance": 6,
                "source": source_name,
                "tag": effect_tag,
                "expires_phase": "MOVEMENT_PHASE",
            }
        )
        sr["advance_no_roll_effects"] = effects
        sr["rad_zone_aggressor_imperative_active"] = True
        sr["rad_zone_aggressor_imperative_expires_phase"] = "MOVEMENT_PHASE"
        sr["rad_zone_aggressor_imperative_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["rad_zone_aggressor_imperative_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["rad_zone_aggressor_imperative_source"] = source_name
        unit.special_rules = sr

    def _mark_rad_zone_baleful_halo(self, unit: Any, *, source_name: str) -> None:
        self._append_defensive_effect(
            unit,
            "defensive_wound_mods",
            {
                "value": 1,
                "attack_type": "any",
                "attacker_key": "",
                "expires_phase": "FIGHT_PHASE",
                "source": source_name,
            },
        )

    def _mark_rad_zone_bulwark_imperative(self, unit: Any, *, source_name: str) -> None:
        self._append_defensive_effect(
            unit,
            "defensive_invuln_overrides",
            {
                "value": 4,
                "attack_type": "any",
                "attacker_key": "",
                "expires_phase": "SHOOTING_PHASE",
                "source": source_name,
            },
        )

    def _mark_data_psalm_phase_effect(
        self,
        unit: Any,
        *,
        prefix: str,
        source_name: str,
        phase_name: str,
        extra_rules: dict[str, Any] | None = None,
    ) -> None:
        root = self._admech_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        sr[f"{prefix}_active"] = True
        sr[f"{prefix}_turn_owner"] = str(getattr(active_player, "id", "") or getattr(self.player, "id", "") or "")
        sr[f"{prefix}_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr[f"{prefix}_expires_phase"] = str(phase_name or "").strip().upper()
        sr[f"{prefix}_source"] = source_name
        for key, value in dict(extra_rules or {}).items():
            sr[key] = value
        root.special_rules = sr

    def _mark_data_psalm_tribute_of_emphatic_veneration_pending(self, enemy_unit: Any, *, source_name: str) -> None:
        root = self._admech_root(enemy_unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["data_psalm_tribute_of_emphatic_veneration_pending"] = True
        sr["data_psalm_tribute_of_emphatic_veneration_owner"] = str(getattr(self.player, "id", "") or "")
        sr["data_psalm_tribute_of_emphatic_veneration_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["data_psalm_tribute_of_emphatic_veneration_source"] = source_name
        root.special_rules = sr

    def _mark_data_psalm_tribute_of_emphatic_veneration_active(self, enemy_unit: Any, *, source_name: str) -> None:
        root = self._admech_root(enemy_unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["data_psalm_tribute_of_emphatic_veneration_active"] = True
        sr["data_psalm_tribute_of_emphatic_veneration_owner"] = str(getattr(self.player, "id", "") or "")
        sr["data_psalm_tribute_of_emphatic_veneration_turn"] = current_turn
        sr["data_psalm_tribute_of_emphatic_veneration_expires_round"] = current_turn + 1
        sr["data_psalm_tribute_of_emphatic_veneration_source"] = source_name
        root.special_rules = sr

    def _resolve_data_psalm_battle_shock_effects(self, *, unit: Any, passed: bool) -> None:
        root = self._admech_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not sr.get("data_psalm_tribute_of_emphatic_veneration_pending"):
            return
        owner_id = str(sr.get("data_psalm_tribute_of_emphatic_veneration_owner", "") or "")
        current_owner_id = str(getattr(self.player, "id", "") or "")
        if owner_id and current_owner_id and owner_id != current_owner_id:
            return
        source_name = (
            str(sr.get("data_psalm_tribute_of_emphatic_veneration_source", "") or "TRIBUTE OF EMPHATIC VENERATION").strip()
            or "TRIBUTE OF EMPHATIC VENERATION"
        )
        sr.pop("data_psalm_tribute_of_emphatic_veneration_pending", None)
        root.special_rules = sr
        if passed:
            return
        self._mark_data_psalm_tribute_of_emphatic_veneration_active(root, source_name=source_name)

    def _mark_cohort_command_phase_effect(
        self,
        unit: Any,
        *,
        prefix: str,
        source_name: str,
        extra_rules: dict[str, Any] | None = None,
    ) -> None:
        root = self._admech_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr[f"{prefix}_active"] = True
        sr[f"{prefix}_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr[f"{prefix}_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr[f"{prefix}_source"] = source_name
        for key, value in dict(extra_rules or {}).items():
            sr[key] = value
        root.special_rules = sr

    def _mark_cohort_auto_divinatory_targeting(self, unit: Any, objective: Any, *, source_name: str) -> None:
        objective_id = str(get_entity_id(objective) or "") if objective is not None else ""
        self._mark_cohort_command_phase_effect(
            unit,
            prefix="cohort_auto_divinatory_targeting",
            source_name=source_name,
            extra_rules={"cohort_auto_divinatory_targeting_objective_id": objective_id},
        )

    def _mark_cohort_benevolence_of_the_omnissiah(self, unit: Any, *, source_name: str) -> None:
        root = self._admech_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        keep: list[Any] = []
        for entry in list(sr.get("bearer_unit_fnp") or []):
            if isinstance(entry, dict) and str(entry.get("source_key", "") or "") == "cohort_benevolence_of_the_omnissiah":
                continue
            keep.append(entry)
        keep.append(
            {
                "value": 6,
                "condition": None,
                "source": source_name,
                "source_key": "cohort_benevolence_of_the_omnissiah",
            }
        )
        keep.append(
            {
                "value": 5,
                "condition": "against mortal wounds",
                "source": source_name,
                "source_key": "cohort_benevolence_of_the_omnissiah",
            }
        )
        sr["bearer_unit_fnp"] = keep
        root.special_rules = sr
        self._mark_cohort_command_phase_effect(
            root,
            prefix="cohort_benevolence_of_the_omnissiah",
            source_name=source_name,
        )

    def _mark_cohort_machine_spirit_resurgent(self, unit: Any, *, source_name: str) -> None:
        self._mark_cohort_command_phase_effect(
            unit,
            prefix="cohort_machine_spirit_resurgent",
            source_name=source_name,
        )

    def _mark_cohort_machine_superiority(self, unit: Any, *, source_name: str) -> None:
        self._mark_cohort_command_phase_effect(
            unit,
            prefix="cohort_machine_superiority",
            source_name=source_name,
        )

    def _mark_cohort_motive_imperative(self, unit: Any, *, source_name: str) -> None:
        self._mark_cohort_command_phase_effect(
            unit,
            prefix="cohort_motive_imperative",
            source_name=source_name,
        )

    def _mark_cohort_transcendent_cogitation(self, unit: Any, *, source_name: str) -> None:
        self._mark_cohort_command_phase_effect(
            unit,
            prefix="cohort_transcendent_cogitation",
            source_name=source_name,
        )

    def _mark_explorator_auto_oracular_retrieval(self, unit: Any, *, source_name: str) -> None:
        root = self._admech_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["explorator_auto_oracular_retrieval_active"] = True
        sr["explorator_auto_oracular_retrieval_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["explorator_auto_oracular_retrieval_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["explorator_auto_oracular_retrieval_source"] = source_name
        root.special_rules = sr

    def _mark_explorator_incense_exhausts(self, unit: Any, *, source_name: str) -> None:
        root = self._admech_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        sr["opponent_shooting_phase_stealth_active"] = True
        sr["opponent_shooting_phase_stealth_owner"] = str(getattr(active_player, "id", "") or "")
        sr["opponent_shooting_phase_stealth_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["opponent_shooting_phase_stealth_source"] = source_name
        sr["opponent_shooting_phase_stealth_expires_phase"] = "SHOOTING_PHASE"
        root.special_rules = sr
        self._append_defensive_effect(
            root,
            "defensive_cover_bonuses",
            {
                "attack_type": "ranged",
                "expires_phase": "SHOOTING_PHASE",
                "source": source_name,
            },
        )

    def _mark_haloscreed_phase_effect(
        self,
        unit: Any,
        *,
        prefix: str,
        source_name: str,
        extra_rules: dict[str, Any] | None = None,
    ) -> None:
        root = self._admech_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        mgr = self._get_adeptus_mechanicus_mgr()
        normalize_phase = getattr(mgr, "_normalize_phase_key", None) if mgr is not None else None
        raw_phase_name = str(self._current_phase_name or getattr(getattr(self.game, "phase", None), "name", "") or "")
        if callable(normalize_phase):
            phase_name = normalize_phase(raw_phase_name)
        else:
            phase_name = raw_phase_name.strip().upper().replace("-", "_").replace(" ", "_")
        sr[f"{prefix}_active"] = True
        sr[f"{prefix}_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr[f"{prefix}_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr[f"{prefix}_expires_phase"] = phase_name
        sr[f"{prefix}_source"] = source_name
        for key, value in dict(extra_rules or {}).items():
            sr[key] = value
        root.special_rules = sr

    def _mark_haloscreed_turn_effect(
        self,
        unit: Any,
        *,
        prefix: str,
        source_name: str,
        extra_rules: dict[str, Any] | None = None,
    ) -> None:
        root = self._admech_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr[f"{prefix}_active"] = True
        sr[f"{prefix}_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr[f"{prefix}_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr[f"{prefix}_source"] = source_name
        for key, value in dict(extra_rules or {}).items():
            sr[key] = value
        root.special_rules = sr

    def _mark_haloscreed_aggressive_impulse(self, unit: Any, *, source_name: str) -> None:
        self._mark_haloscreed_phase_effect(
            unit,
            prefix="haloscreed_aggressive_impulse",
            source_name=source_name,
        )

    def _mark_haloscreed_guided_retreat(self, unit: Any, *, source_name: str) -> None:
        root = self._admech_root(unit)
        if root is None:
            return
        self._mark_haloscreed_turn_effect(
            root,
            prefix="haloscreed_guided_retreat",
            source_name=source_name,
        )
        mgr = self._get_adeptus_mechanicus_mgr()
        has_halo_fn = getattr(mgr, "_unit_has_halo_override_keyword", None) if mgr is not None else None
        if not callable(has_halo_fn) or not bool(has_halo_fn(root)):
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sources = [
            str(src or "").strip()
            for src in list(sr.get("unit_reroll_desperate_escape_sources", []) or [])
            if str(src or "").strip()
        ]
        if source_name not in sources:
            sources.append(source_name)
        sr["unit_reroll_desperate_escape_tests"] = True
        sr["unit_reroll_desperate_escape_sources"] = list(dict.fromkeys(sources))
        sr["haloscreed_guided_retreat_desperate_escape_reroll_granted"] = True
        root.special_rules = sr

    def _cleanup_adeptus_mechanicus_phase_end_effects(self, *, player=None, phase=None) -> None:
        army = getattr(self.player, "army", None)
        if army is None:
            return
        mgr = self._get_adeptus_mechanicus_mgr()
        normalize_phase = getattr(mgr, "_normalize_phase_key", None) if mgr is not None else None
        raw_phase_name = str(getattr(phase, "name", "") or phase or "")
        if callable(normalize_phase):
            phase_name = normalize_phase(raw_phase_name)
        else:
            phase_name = raw_phase_name.strip().upper().replace("-", "_").replace(" ", "_")
        if not phase_name:
            return
        clear_cache = getattr(mgr, "_clear_unit_ability_cache", None) if mgr is not None else None
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._admech_root(unit)
            if root is None:
                continue
            uid = self._admech_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            updated = dict(sr)
            changed = False
            for prefix in (
                "haloscreed_eradication_protocols",
                "haloscreed_targeting_override",
                "haloscreed_aggressive_impulse",
            ):
                raw_exp = str(updated.get(f"{prefix}_expires_phase", "") or "")
                if callable(normalize_phase):
                    exp = normalize_phase(raw_exp)
                else:
                    exp = raw_exp.strip().upper().replace("-", "_").replace(" ", "_")
                if bool(updated.get(f"{prefix}_active", False)) and (not exp or exp == phase_name):
                    for key in list(updated.keys()):
                        if key == f"{prefix}_active" or key.startswith(f"{prefix}_"):
                            updated.pop(key, None)
                    changed = True
            if phase_name == "FIGHT_PHASE" and player is self.player and bool(updated.get("haloscreed_guided_retreat_active", False)):
                source_name = str(updated.get("haloscreed_guided_retreat_source", "") or "GUIDED RETREAT").strip() or "GUIDED RETREAT"
                granted_reroll = bool(updated.get("haloscreed_guided_retreat_desperate_escape_reroll_granted", False))
                for key in list(updated.keys()):
                    if key == "haloscreed_guided_retreat_active" or key.startswith("haloscreed_guided_retreat_"):
                        updated.pop(key, None)
                if granted_reroll:
                    sources = [
                        str(src or "").strip()
                        for src in list(updated.get("unit_reroll_desperate_escape_sources", []) or [])
                        if str(src or "").strip() and str(src or "").strip().lower() != source_name.lower()
                    ]
                    if sources:
                        updated["unit_reroll_desperate_escape_sources"] = sources
                        updated["unit_reroll_desperate_escape_tests"] = True
                    else:
                        updated.pop("unit_reroll_desperate_escape_sources", None)
                        updated.pop("unit_reroll_desperate_escape_tests", None)
                changed = True
            if changed:
                root.special_rules = updated
                if callable(clear_cache):
                    clear_cache(root)
                else:
                    invalidate = getattr(root, "_invalidate_ability_cache", None)
                    if callable(invalidate):
                        invalidate()

    def _use_adeptus_mechanicus_rad_zone_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "BALEFUL HALO":
            return self._use_rad_zone_baleful_halo(stratagem, **kwargs)
        if name_u == "BULWARK IMPERATIVE":
            return self._use_rad_zone_bulwark_imperative(stratagem, **kwargs)
        if name_u == "AGGRESSOR IMPERATIVE":
            return self._use_rad_zone_aggressor_imperative(stratagem, **kwargs)
        if name_u == "EXTINCTION ORDER":
            return self._use_rad_zone_extinction_order(stratagem, **kwargs)
        if name_u == "LETHAL DOSAGE":
            return self._use_rad_zone_lethal_dosage(stratagem, **kwargs)
        if name_u == "PRE-CALIBRATED PURGE SOLUTION":
            return self._use_rad_zone_pre_calibrated_purge_solution(stratagem, **kwargs)
        if name_u == "AUTO-DIVINATORY TARGETING":
            return self._use_cohort_auto_divinatory_targeting(stratagem, **kwargs)
        if name_u == "BENEVOLENCE OF THE OMNISSIAH":
            return self._use_cohort_benevolence_of_the_omnissiah(stratagem, **kwargs)
        if name_u == "ERADICATION PROTOCOLS":
            return self._use_haloscreed_eradication_protocols(stratagem, **kwargs)
        if name_u == "AUTO-ORACULAR RETRIEVAL":
            return self._use_explorator_auto_oracular_retrieval(stratagem, **kwargs)
        if name_u == "AGGRESSIVE IMPULSE":
            return self._use_haloscreed_aggressive_impulse(stratagem, **kwargs)
        if name_u == "ANALYTICAL DIVINATION":
            return self._use_haloscreed_analytical_divination(stratagem, **kwargs)
        if name_u == "CACHED ACQUISITION":
            return self._use_explorator_cached_acquisition(stratagem, **kwargs)
        if name_u == "CHANT OF THE REMORSELESS FIST":
            return self._use_data_psalm_chant_of_the_remorseless_fist(stratagem, **kwargs)
        if name_u == "GUIDED RETREAT":
            return self._use_haloscreed_guided_retreat(stratagem, **kwargs)
        if name_u == "INCANTATION OF THE IRON SOUL":
            return self._use_data_psalm_incantation_of_the_iron_soul(stratagem, **kwargs)
        if name_u == "INCENSE EXHAUSTS":
            return self._use_explorator_incense_exhausts(stratagem, **kwargs)
        if name_u == "INFOSLAVE SKULL":
            return self._use_explorator_infoslave_skull(stratagem, **kwargs)
        if name_u == "LITANY OF THE ELECTROMANCER":
            return self._use_data_psalm_litany_of_the_electromancer(stratagem, **kwargs)
        if name_u == "LUMINESCENT BLESSING":
            return self._use_data_psalm_luminescent_blessing(stratagem, **kwargs)
        if name_u == "MACHINE SPIRIT RESURGENT":
            return self._use_cohort_machine_spirit_resurgent(stratagem, **kwargs)
        if name_u == "MACHINE SUPERIORITY":
            return self._use_cohort_machine_superiority(stratagem, **kwargs)
        if name_u == "MOTIVE IMPERATIVE":
            return self._use_cohort_motive_imperative(stratagem, **kwargs)
        if name_u == "NEURAL OVERLOAD":
            return self._use_haloscreed_neural_overload(stratagem, **kwargs)
        if name_u == "PRIORITY RECLAMATION":
            return self._use_explorator_priority_reclamation(stratagem, **kwargs)
        if name_u == "REACTIVE SAFEGUARD":
            return self._use_explorator_reactive_safeguard(stratagem, **kwargs)
        if name_u == "TARGETING OVERRIDE":
            return self._use_haloscreed_targeting_override(stratagem, **kwargs)
        if name_u == "TRIBUTE OF EMPHATIC VENERATION":
            return self._use_data_psalm_tribute_of_emphatic_veneration(stratagem, **kwargs)
        if name_u == "TRANSCENDENT COGITATION":
            return self._use_cohort_transcendent_cogitation(stratagem, **kwargs)
        if name_u == "VERSE OF VENGEANCE":
            return self._use_data_psalm_verse_of_vengeance(stratagem, **kwargs)
        return None

    def _use_haloscreed_eradication_protocols(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_haloscreed_battle_clade():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: ERADICATION PROTOCOLS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: ERADICATION PROTOCOLS: not your Shooting phase")
            return False
        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if primary is None and len(candidates) == 1:
            primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: ERADICATION PROTOCOLS: no unit selected")
            return False
        if phase_name == "shooting phase":
            eligible = self._haloscreed_phase_buff_candidates(require_not_shot=True)
            phase_label = "Shooting phase"
        else:
            eligible = self._haloscreed_phase_buff_candidates(require_not_fought=True)
            phase_label = "Fight phase"
        if primary not in eligible:
            logger.error("ERROR: ERADICATION PROTOCOLS: target must be an eligible ADEPTUS MECHANICUS unit")
            return False
        if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name=phase_label):
            logger.error("ERROR: ERADICATION PROTOCOLS: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False
        source_name = str(getattr(stratagem, "name", "") or "ERADICATION PROTOCOLS")
        self._mark_haloscreed_phase_effect(
            primary,
            prefix="haloscreed_eradication_protocols",
            source_name=source_name,
        )
        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ERADICATION PROTOCOLS: %s re-rolls Wound rolls of 1, and gains re-roll Hit rolls of 1 while it has HALO OVERRIDE, until end of phase.",
            getattr(primary, "name", "Unit"),
        )
        return True

    def _use_haloscreed_targeting_override(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_haloscreed_battle_clade():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: TARGETING OVERRIDE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: TARGETING OVERRIDE: not your Shooting phase")
            return False
        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if primary is None and len(candidates) == 1:
            primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: TARGETING OVERRIDE: no unit selected")
            return False
        if phase_name == "shooting phase":
            eligible = self._haloscreed_phase_buff_candidates(require_not_shot=True)
            phase_label = "Shooting phase"
        else:
            eligible = self._haloscreed_phase_buff_candidates(require_not_fought=True)
            phase_label = "Fight phase"
        if primary not in eligible:
            logger.error("ERROR: TARGETING OVERRIDE: target must be an eligible ADEPTUS MECHANICUS unit")
            return False
        if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name=phase_label):
            logger.error("ERROR: TARGETING OVERRIDE: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False
        source_name = str(getattr(stratagem, "name", "") or "TARGETING OVERRIDE")
        self._mark_haloscreed_phase_effect(
            primary,
            prefix="haloscreed_targeting_override",
            source_name=source_name,
        )
        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TARGETING OVERRIDE: %s scores a Critical Hit on an unmodified Hit roll of 5+ until end of phase.",
            getattr(primary, "name", "Unit"),
        )
        return True

    def _use_haloscreed_neural_overload(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_haloscreed_battle_clade():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: NEURAL OVERLOAD: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: NEURAL OVERLOAD: not your turn")
            return False
        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if primary is None and len(candidates) == 1:
            primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: NEURAL OVERLOAD: no unit selected")
            return False
        eligible = self._haloscreed_neural_overload_candidates()
        if primary not in eligible:
            logger.error("ERROR: NEURAL OVERLOAD: target must be an eligible ADEPTUS MECHANICUS unit")
            return False
        mgr = self._get_adeptus_mechanicus_mgr()
        normalize_choice = getattr(mgr, "_normalize_noospheric_override_choice_key", None) if mgr is not None else None
        raw_choice = kwargs.get("choice_key") or kwargs.get("override_key")
        choice_key = str(raw_choice or "").strip()
        if isinstance(raw_choice, dict):
            choice_key = str(raw_choice.get("choice_key", "") or raw_choice.get("override_key", "") or "").strip()
        choice_key = normalize_choice(choice_key) if callable(normalize_choice) else str(choice_key or "").strip().upper()
        if not choice_key:
            logger.error("ERROR: NEURAL OVERLOAD: no HALO OVERRIDE ability selected")
            return False
        if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name="Movement phase"):
            logger.error("ERROR: NEURAL OVERLOAD: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False
        source_name = str(getattr(stratagem, "name", "") or "NEURAL OVERLOAD")
        has_halo_fn = getattr(mgr, "_unit_has_halo_override_keyword", None) if mgr is not None else None
        if callable(has_halo_fn) and bool(has_halo_fn(primary)):
            mortal_wounds = max(1, int(dice_module.get_roll("D3") or 0))
            apply_mortal_wounds = getattr(primary, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortal_wounds):
                apply_mortal_wounds(primary, int(mortal_wounds), game_map=getattr(self.game, "map", None))
        is_alive = getattr(primary, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(
                "INFO: NEURAL OVERLOAD: %s was destroyed while resolving the overload.",
                getattr(primary, "name", "Unit"),
            )
            return True
        mark_fn = getattr(mgr, "haloscreed_mark_neural_overload", None) if mgr is not None else None
        outcome = mark_fn(primary, choice_key=choice_key, source_name=source_name, game=self.game) if callable(mark_fn) else None
        if outcome is None:
            logger.error("ERROR: NEURAL OVERLOAD: failed to record selected HALO OVERRIDE ability")
            return False
        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: NEURAL OVERLOAD: %s gains %s until your next Command phase.",
            getattr(primary, "name", "Unit"),
            str((outcome or {}).get("choice_label", "") or choice_key.replace("_", " ").title()),
        )
        return True

    def _use_haloscreed_aggressive_impulse(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_haloscreed_battle_clade():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: AGGRESSIVE IMPULSE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: AGGRESSIVE IMPULSE: not your turn")
            return False
        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if primary is None and len(candidates) == 1:
            primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: AGGRESSIVE IMPULSE: no transport selected")
            return False
        eligible = self._haloscreed_aggressive_impulse_candidates()
        if primary not in eligible:
            logger.error("ERROR: AGGRESSIVE IMPULSE: target must be an eligible Skorpius Dunerider")
            return False
        if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name="Movement phase"):
            logger.error("ERROR: AGGRESSIVE IMPULSE: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False
        source_name = str(getattr(stratagem, "name", "") or "AGGRESSIVE IMPULSE")
        self._mark_haloscreed_aggressive_impulse(primary, source_name=source_name)
        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: AGGRESSIVE IMPULSE: units disembarking from %s after it makes a Normal move can declare a charge this turn.",
            getattr(primary, "name", "Unit"),
        )
        return True

    def _use_haloscreed_guided_retreat(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_haloscreed_battle_clade():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: GUIDED RETREAT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: GUIDED RETREAT: not your turn")
            return False
        unit = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        action = kwargs.get("action")
        if (unit is None or not action) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "GUIDED RETREAT":
                    continue
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit")
                if not action:
                    action = reaction.get("action")
                break
        candidates = self._haloscreed_guided_retreat_candidates(unit=unit, action=str(action or ""))
        if not candidates:
            logger.error("ERROR: GUIDED RETREAT: target must be an ADEPTUS MECHANICUS unit that just fell back")
            return False
        primary = candidates[0]
        if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name="Movement phase"):
            logger.error("ERROR: GUIDED RETREAT: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False
        source_name = str(getattr(stratagem, "name", "") or "GUIDED RETREAT")
        self._mark_haloscreed_guided_retreat(primary, source_name=source_name)
        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: GUIDED RETREAT: %s can shoot and charge after Falling Back this turn.",
            getattr(primary, "name", "Unit"),
        )
        return True

    def _use_haloscreed_analytical_divination(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_haloscreed_battle_clade():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: ANALYTICAL DIVINATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: ANALYTICAL DIVINATION: not opponent's Movement phase")
            return False
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("moving_unit") or kwargs.get("attacking_unit")
        if enemy_unit is None and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "ANALYTICAL DIVINATION":
                    continue
                enemy_unit = reaction.get("moving_unit") or reaction.get("enemy_unit")
                if enemy_unit is not None:
                    break
        enemy_root = self._admech_root(enemy_unit)
        if enemy_root is None or self._admech_owned_by_player(enemy_root):
            logger.error("ERROR: ANALYTICAL DIVINATION: moving unit must be an enemy unit")
            return False
        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        candidates = list(kwargs.get("candidates") or self._haloscreed_analytical_divination_candidates(moving_unit=enemy_root))
        if primary is None and len(candidates) == 1:
            primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: ANALYTICAL DIVINATION: no friendly unit selected")
            return False
        eligible = self._haloscreed_analytical_divination_candidates(moving_unit=enemy_root)
        if primary not in eligible:
            logger.error("ERROR: ANALYTICAL DIVINATION: target must be an eligible ADEPTUS MECHANICUS INFANTRY unit within 9\" and not in Engagement Range")
            return False
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if not callable(queue_move):
            logger.error("ERROR: ANALYTICAL DIVINATION: reactive move queue unavailable")
            return False
        if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name="Movement phase"):
            logger.error("ERROR: ANALYTICAL DIVINATION: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False
        mgr = self._get_adeptus_mechanicus_mgr()
        has_halo_fn = getattr(mgr, "_unit_has_halo_override_keyword", None) if mgr is not None else None
        max_distance = 6 if callable(has_halo_fn) and bool(has_halo_fn(primary)) else max(0, int(dice_module.get_roll("D6") or 0))
        request = queue_move(
            player=self.player,
            unit=primary,
            max_distance=int(max_distance),
            kind="haloscreed_analytical_divination",
            movement_type="reactive",
            reactive_movement_type="move",
            source=str(getattr(stratagem, "name", "") or "ANALYTICAL DIVINATION"),
            moving_unit=enemy_root,
            attacker_unit=enemy_root,
        )
        if request is None:
            logger.error("ERROR: ANALYTICAL DIVINATION: failed to queue reactive move")
            return False
        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ANALYTICAL DIVINATION: %s can make a reactive Normal move of up to %d\".",
            getattr(primary, "name", "Unit"),
            int(max_distance),
        )
        return True

    def _use_explorator_auto_oracular_retrieval(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_explorator_maniple():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: AUTO-ORACULAR RETRIEVAL: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: AUTO-ORACULAR RETRIEVAL: not your Shooting phase")
            return False

        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        if primary is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: AUTO-ORACULAR RETRIEVAL: no unit selected")
            return False
        eligible_primary = self._explorator_auto_oracular_primary_candidates()
        if primary not in eligible_primary:
            logger.error(
                "ERROR: AUTO-ORACULAR RETRIEVAL: target must be an ADEPTUS MECHANICUS unit that disembarked from a transport this turn"
            )
            return False

        if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name="Shooting phase"):
            logger.error("ERROR: AUTO-ORACULAR RETRIEVAL: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False

        source_name = str(getattr(stratagem, "name", "") or "AUTO-ORACULAR RETRIEVAL")
        self._mark_explorator_auto_oracular_retrieval(primary, source_name=source_name)
        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: AUTO-ORACULAR RETRIEVAL: %s gains +1 to wound on ranged attacks against targets within an Acquisition objective this phase.",
            getattr(primary, "name", "Unit"),
        )
        return True

    def _use_explorator_cached_acquisition(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_explorator_maniple():
            return False
        unit = (
            self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
            or kwargs.get("destroyed_unit")
        )
        objective = self._admech_resolve_objective_from_kwargs(kwargs)
        objective_candidates = list(kwargs.get("objective_candidates") or [])
        if (unit is None or not objective_candidates) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "CACHED ACQUISITION":
                    continue
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit") or reaction.get("destroyed_unit")
                if not objective_candidates:
                    objective_candidates = list(reaction.get("objective_candidates") or [])
                break
        if unit is None:
            logger.error("ERROR: CACHED ACQUISITION: no destroyed unit provided")
            return False
        root = self._admech_root(unit)
        if root is None or not self._admech_owned_by_player(root) or not self._is_adeptus_mechanicus_unit(root):
            logger.error("ERROR: CACHED ACQUISITION: target must be a destroyed ADEPTUS MECHANICUS unit from your army")
            return False
        if not objective_candidates:
            objective_candidates = self._explorator_cached_acquisition_objective_candidates(
                root,
                last_model=kwargs.get("last_model"),
            )
        if objective is None:
            objective = objective_candidates[0] if objective_candidates else None
        if objective is None:
            logger.error("ERROR: CACHED ACQUISITION: no eligible objective marker was provided")
            return False
        if objective_candidates and objective not in objective_candidates:
            logger.error("ERROR: CACHED ACQUISITION: selected objective marker is not eligible")
            return False
        objective_location = getattr(objective, "location", None)
        if objective_location is None:
            logger.error("ERROR: CACHED ACQUISITION: objective marker location is unavailable")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=root):
            return False
        set_sticky = getattr(objective_location, "set_sticky_control", None)
        if callable(set_sticky):
            set_sticky(self.player, source="explorator_cached_acquisition")
        else:
            objective_location.sticky_controller = self.player
            objective_location.sticky_source = "explorator_cached_acquisition"
            objective_location.controlling_player = self.player
        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: CACHED ACQUISITION: selected objective remains under your control until your opponent takes it.")
        return True

    def _use_explorator_incense_exhausts(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_explorator_maniple():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: INCENSE EXHAUSTS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: INCENSE EXHAUSTS: not opponent's Shooting phase")
            return False

        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        target_units = list(kwargs.get("target_units") or [])
        candidates = list(kwargs.get("candidates") or [])
        if (attacking_unit is None or not target_units or not candidates) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "INCENSE EXHAUSTS":
                    continue
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        attacker_root = self._admech_root(attacking_unit)
        if attacker_root is None or self._admech_owned_by_player(attacker_root):
            logger.error("ERROR: INCENSE EXHAUSTS: attacking unit must be an enemy unit")
            return False

        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        eligible_primary = self._explorator_incense_primary_candidates(target_units=target_units)
        if not eligible_primary and candidates:
            eligible_primary = [candidate for candidate in list(candidates or []) if candidate in self._explorator_incense_primary_candidates(target_units=candidates)]
        if primary is None and len(eligible_primary) == 1:
            primary = eligible_primary[0]
        if primary is None and len(candidates) == 1:
            primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: INCENSE EXHAUSTS: no primary unit selected")
            return False
        if primary not in eligible_primary:
            logger.error("ERROR: INCENSE EXHAUSTS: primary target must be an eligible ADEPTUS MECHANICUS INFANTRY unit selected as a target")
            return False

        support = self._admech_resolve_unit_from_kwargs(kwargs, key="support_unit", fallback_key="secondary_unit")
        eligible_support = self._explorator_incense_support_candidates(primary)
        if support is None and len(eligible_support) == 1:
            support = eligible_support[0]
        if support is None:
            logger.error("ERROR: INCENSE EXHAUSTS: no SMOKE support unit selected")
            return False
        if support not in eligible_support:
            logger.error("ERROR: INCENSE EXHAUSTS: support unit must be a friendly ADEPTUS MECHANICUS SMOKE unit within 6\"")
            return False

        if not stratagem.can_use(
            self.player,
            self.game,
            unit=primary,
            target_unit=primary,
            attacking_unit=attacker_root,
            phase_name="Shooting phase",
        ):
            logger.error("ERROR: INCENSE EXHAUSTS: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False

        source_name = str(getattr(stratagem, "name", "") or "INCENSE EXHAUSTS")
        affected: list[Any] = []
        seen: set[str] = set()
        for unit in (primary, support):
            root = self._admech_root(unit)
            if root is None:
                continue
            uid = self._admech_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            affected.append(root)
        for unit in affected:
            self._mark_explorator_incense_exhausts(unit, source_name=source_name)
        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: INCENSE EXHAUSTS: %s and %s gain Stealth and Benefit of Cover until end of phase.",
            getattr(primary, "name", "Unit"),
            getattr(support, "name", "Support Unit"),
        )
        return True

    def _use_explorator_infoslave_skull(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_explorator_maniple():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: INFOSLAVE SKULL: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: INFOSLAVE SKULL: not your Command phase")
            return False

        source_unit = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        if source_unit is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                source_unit = self._admech_root(candidates[0])
        if source_unit is None:
            logger.error("ERROR: INFOSLAVE SKULL: no TECH-PRIEST selected")
            return False
        if source_unit not in self._explorator_infoslave_tech_priest_candidates():
            logger.error("ERROR: INFOSLAVE SKULL: selected unit must be an eligible TECH-PRIEST")
            return False

        objective = self._admech_resolve_objective_from_kwargs(kwargs)
        objective_candidates = list(kwargs.get("objective_candidates") or [])
        if not objective_candidates:
            objective_candidates = self._explorator_infoslave_objective_candidates(source_unit)
        if objective is None and len(objective_candidates) == 1:
            objective = objective_candidates[0]
        if objective is None:
            logger.error("ERROR: INFOSLAVE SKULL: no objective marker selected")
            return False
        if objective not in objective_candidates:
            logger.error("ERROR: INFOSLAVE SKULL: selected objective marker is not eligible")
            return False

        if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name="Command phase"):
            logger.error("ERROR: INFOSLAVE SKULL: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=source_unit):
            return False

        mgr = self._get_adeptus_mechanicus_mgr()
        add_fn = getattr(mgr, "add_additional_acquisition_objective", None) if mgr is not None else None
        if not callable(add_fn):
            logger.error("ERROR: INFOSLAVE SKULL: acquisition manager unavailable")
            return False
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        source_name = str(getattr(stratagem, "name", "") or "INFOSLAVE SKULL")
        selection = add_fn(
            str(get_entity_id(objective) or ""),
            game=self.game,
            player=self.player,
            expires_round=current_turn + 1,
            source=source_name,
        )
        if selection is None:
            logger.error("ERROR: INFOSLAVE SKULL: selected objective marker could not be added as an Acquisition objective")
            return False
        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: INFOSLAVE SKULL: %s is also an Acquisition objective until your next Command phase.",
            str(getattr(objective, "name", "") or "Objective marker"),
        )
        return True

    def _use_explorator_priority_reclamation(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_explorator_maniple():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: PRIORITY RECLAMATION: wrong phase")
            return False
        unit = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "PRIORITY RECLAMATION":
                    continue
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        if unit is None and len(candidates) == 1:
            unit = self._admech_root(candidates[0])
        if unit is None:
            logger.error("ERROR: PRIORITY RECLAMATION: no unit selected")
            return False
        root = self._admech_root(unit)
        if root not in self._explorator_priority_reclamation_candidates(root):
            logger.error("ERROR: PRIORITY RECLAMATION: target must be an eligible ADEPTUS MECHANICUS unit before it consolidates")
            return False

        if not stratagem.can_use(self.player, self.game, unit=root, target_unit=root, phase_name="Fight phase"):
            logger.error("ERROR: PRIORITY RECLAMATION: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_adeptus_mechanicus_mgr()
        active_ids_fn = getattr(mgr, "explorator_active_acquisition_objective_ids", None) if mgr is not None else None
        objective_ids = list(active_ids_fn(game=self.game, game_map=getattr(self.game, "map", None)) or []) if callable(active_ids_fn) else []
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        current_cons = float(sr.get("stratagem_consolidate_distance_override", 0.0) or 0.0)
        sr["stratagem_consolidate_distance_override"] = max(current_cons, 6.0)
        sr["stratagem_consolidate_expires_phase"] = "FIGHT_PHASE"
        sr["stratagem_consolidate_source"] = str(getattr(stratagem, "name", "") or "PRIORITY RECLAMATION")
        existing_ids = [str(value or "").strip() for value in list(sr.get("stratagem_consolidate_allowed_objective_ids", []) or []) if str(value or "").strip()]
        sr["stratagem_consolidate_allowed_objective_ids"] = sorted(set(existing_ids + [str(value or "").strip() for value in objective_ids if str(value or "").strip()]))
        root.special_rules = sr
        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PRIORITY RECLAMATION: %s can Consolidate up to 6\" this phase, but must end that move within an Acquisition objective.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_explorator_reactive_safeguard(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_explorator_maniple():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: REACTIVE SAFEGUARD: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: REACTIVE SAFEGUARD: not opponent's Charge phase")
            return False

        charging_unit = kwargs.get("charging_unit") or kwargs.get("attacking_unit") or kwargs.get("enemy_unit")
        target_units = list(kwargs.get("target_units") or [])
        candidates = list(kwargs.get("candidates") or [])
        if (charging_unit is None or not target_units or not candidates) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "REACTIVE SAFEGUARD":
                    continue
                if charging_unit is None:
                    charging_unit = reaction.get("charging_unit") or reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        attacker_root = self._admech_root(charging_unit)
        if attacker_root is None or self._admech_owned_by_player(attacker_root):
            logger.error("ERROR: REACTIVE SAFEGUARD: charging unit must be an enemy unit")
            return False

        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        eligible_primary = self._explorator_reactive_safeguard_candidates(
            charging_unit=attacker_root,
            target_units=target_units,
        )
        if primary is None and len(eligible_primary) == 1:
            primary = eligible_primary[0]
        if primary is None and len(candidates) == 1:
            primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: REACTIVE SAFEGUARD: no primary unit selected")
            return False
        if primary not in eligible_primary:
            logger.error(
                "ERROR: REACTIVE SAFEGUARD: primary target must be an eligible ADEPTUS MECHANICUS INFANTRY unit within an Acquisition objective"
            )
            return False

        transport = self._admech_resolve_unit_from_kwargs(kwargs, key="transport_unit")
        eligible_transports = self._explorator_reactive_safeguard_transport_candidates(primary)
        if transport is None and len(eligible_transports) == 1:
            transport = eligible_transports[0]
        if transport is None:
            logger.error("ERROR: REACTIVE SAFEGUARD: no transport selected")
            return False
        if transport not in eligible_transports:
            logger.error("ERROR: REACTIVE SAFEGUARD: transport must be an eligible friendly ADEPTUS MECHANICUS TRANSPORT within 3\"")
            return False

        if not stratagem.can_use(
            self.player,
            self.game,
            unit=primary,
            target_unit=primary,
            attacking_unit=attacker_root,
            phase_name="Charge phase",
        ):
            logger.error("ERROR: REACTIVE SAFEGUARD: cannot be used in current state")
            return False
        resolve_fn = getattr(self.game, "resolve_emergency_combat_embarkation", None) if self.game is not None else None
        if not callable(resolve_fn):
            logger.error("ERROR: REACTIVE SAFEGUARD: embarkation resolver unavailable")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False
        source_name = str(getattr(stratagem, "name", "") or "REACTIVE SAFEGUARD")
        target_unit_ids: list[str] = []
        seen_ids: set[str] = set()
        for unit in list(target_units or [primary]):
            root = self._admech_root(unit)
            uid = str(get_entity_id(root) or "")
            if not uid or uid in seen_ids:
                continue
            seen_ids.add(uid)
            target_unit_ids.append(uid)
        resolve_fn(
            transport,
            primary,
            {
                "source": source_name,
                "range": 3.0,
                "allow_existing_passengers": True,
            },
            charging_unit=attacker_root,
            original_target_unit_ids=target_unit_ids,
            out_of_turn=False,
            count_as_charged=True,
        )
        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: REACTIVE SAFEGUARD: %s embarks within %s before the charge is resolved.",
            getattr(primary, "name", "Unit"),
            getattr(transport, "name", "Transport"),
        )
        return True

    def _use_cohort_auto_divinatory_targeting(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_cohort_cybernetica():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: AUTO-DIVINATORY TARGETING: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: AUTO-DIVINATORY TARGETING: not your Command phase")
            return False

        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        if primary is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: AUTO-DIVINATORY TARGETING: no LEGIO CYBERNETICA or ADEPTUS MECHANICUS VEHICLE unit selected")
            return False

        eligible_primary = self._cohort_auto_divinatory_primary_candidates()
        if primary not in eligible_primary:
            logger.error(
                "ERROR: AUTO-DIVINATORY TARGETING: target must be an eligible LEGIO CYBERNETICA unit or ADEPTUS MECHANICUS VEHICLE"
            )
            return False

        objective = self._admech_resolve_objective_from_kwargs(kwargs)
        objective_candidates = list(kwargs.get("objective_candidates") or [])
        if not objective_candidates:
            objective_candidates = self._cohort_auto_divinatory_objective_candidates(primary)
        if objective is None and len(objective_candidates) == 1:
            objective = objective_candidates[0]
        if objective is None:
            logger.error("ERROR: AUTO-DIVINATORY TARGETING: no objective marker selected")
            return False
        if objective not in objective_candidates:
            logger.error("ERROR: AUTO-DIVINATORY TARGETING: selected objective marker is not eligible")
            return False

        if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, objective=objective, phase_name="Command phase"):
            logger.error("ERROR: AUTO-DIVINATORY TARGETING: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False

        source_name = str(getattr(stratagem, "name", "") or "AUTO-DIVINATORY TARGETING")
        self._mark_cohort_auto_divinatory_targeting(primary, objective, source_name=source_name)
        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: AUTO-DIVINATORY TARGETING: %s gains BS 3+, [IGNORES COVER], and objective-locked targeting until your next Command phase.",
            getattr(primary, "name", "Unit"),
        )
        return True

    def _use_cohort_benevolence_of_the_omnissiah(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_cohort_cybernetica():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: BENEVOLENCE OF THE OMNISSIAH: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: BENEVOLENCE OF THE OMNISSIAH: not your Command phase")
            return False

        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        if primary is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: BENEVOLENCE OF THE OMNISSIAH: no eligible target selected")
            return False

        eligible_primary = self._cohort_benevolence_primary_candidates()
        if primary not in eligible_primary:
            logger.error(
                "ERROR: BENEVOLENCE OF THE OMNISSIAH: target must be an eligible LEGIO CYBERNETICA unit or ADEPTUS MECHANICUS VEHICLE"
            )
            return False

        if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name="Command phase"):
            logger.error("ERROR: BENEVOLENCE OF THE OMNISSIAH: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False

        source_name = str(getattr(stratagem, "name", "") or "BENEVOLENCE OF THE OMNISSIAH")
        self._mark_cohort_benevolence_of_the_omnissiah(primary, source_name=source_name)
        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: BENEVOLENCE OF THE OMNISSIAH: %s gains Feel No Pain 6+ (5+ vs mortal wounds) until your next Command phase.",
            getattr(primary, "name", "Unit"),
        )
        return True

    def _use_cohort_machine_spirit_resurgent(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_cohort_cybernetica():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: MACHINE SPIRIT RESURGENT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: MACHINE SPIRIT RESURGENT: not your Command phase")
            return False

        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        if primary is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: MACHINE SPIRIT RESURGENT: no eligible target selected")
            return False

        eligible_primary = self._cohort_machine_spirit_primary_candidates()
        if primary not in eligible_primary:
            logger.error(
                "ERROR: MACHINE SPIRIT RESURGENT: target must be an eligible LEGIO CYBERNETICA unit or ADEPTUS MECHANICUS VEHICLE that is below Starting Strength"
            )
            return False

        if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name="Command phase"):
            logger.error("ERROR: MACHINE SPIRIT RESURGENT: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False

        source_name = str(getattr(stratagem, "name", "") or "MACHINE SPIRIT RESURGENT")
        self._mark_cohort_machine_spirit_resurgent(primary, source_name=source_name)
        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MACHINE SPIRIT RESURGENT: %s re-rolls Hit rolls until your next Command phase, and re-rolls Wound rolls while Below Half-strength.",
            getattr(primary, "name", "Unit"),
        )
        return True

    def _use_cohort_machine_superiority(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_cohort_cybernetica():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: MACHINE SUPERIORITY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: MACHINE SUPERIORITY: not your Command phase")
            return False

        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        if primary is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: MACHINE SUPERIORITY: no eligible target selected")
            return False

        eligible_primary = self._cohort_machine_superiority_primary_candidates()
        if primary not in eligible_primary:
            logger.error(
                "ERROR: MACHINE SUPERIORITY: target must be an eligible LEGIO CYBERNETICA unit or ADEPTUS MECHANICUS VEHICLE"
            )
            return False

        if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name="Command phase"):
            logger.error("ERROR: MACHINE SUPERIORITY: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False

        source_name = str(getattr(stratagem, "name", "") or "MACHINE SUPERIORITY")
        self._mark_cohort_machine_superiority(primary, source_name=source_name)
        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MACHINE SUPERIORITY: %s can shoot after Falling Back and can ignore non-save modifiers until end of turn.",
            getattr(primary, "name", "Unit"),
        )
        return True

    def _use_cohort_motive_imperative(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_cohort_cybernetica():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: MOTIVE IMPERATIVE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: MOTIVE IMPERATIVE: not your Command phase")
            return False

        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        if primary is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: MOTIVE IMPERATIVE: no eligible ADEPTUS MECHANICUS VEHICLE selected")
            return False

        eligible_primary = self._cohort_motive_imperative_primary_candidates()
        if primary not in eligible_primary:
            logger.error("ERROR: MOTIVE IMPERATIVE: target must be an eligible ADEPTUS MECHANICUS VEHICLE")
            return False

        if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name="Command phase"):
            logger.error("ERROR: MOTIVE IMPERATIVE: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False

        source_name = str(getattr(stratagem, "name", "") or "MOTIVE IMPERATIVE")
        self._mark_cohort_motive_imperative(primary, source_name=source_name)
        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MOTIVE IMPERATIVE: %s gains +3\" Move and +1 to Advance and Charge rolls until your next Command phase.",
            getattr(primary, "name", "Unit"),
        )
        return True

    def _use_cohort_transcendent_cogitation(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_cohort_cybernetica():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: TRANSCENDENT COGITATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: TRANSCENDENT COGITATION: not your Command phase")
            return False

        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        if primary is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: TRANSCENDENT COGITATION: no eligible target selected")
            return False

        eligible_primary = self._cohort_transcendent_cogitation_primary_candidates()
        if primary not in eligible_primary:
            logger.error(
                "ERROR: TRANSCENDENT COGITATION: target must be an eligible LEGIO CYBERNETICA unit or ADEPTUS MECHANICUS VEHICLE"
            )
            return False

        if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name="Command phase"):
            logger.error("ERROR: TRANSCENDENT COGITATION: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False

        source_name = str(getattr(stratagem, "name", "") or "TRANSCENDENT COGITATION")
        self._mark_cohort_transcendent_cogitation(primary, source_name=source_name)
        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TRANSCENDENT COGITATION: %s counts as affected by both Protector and Conqueror Imperatives until your next Command phase.",
            getattr(primary, "name", "Unit"),
        )
        return True

    def _use_data_psalm_chant_of_the_remorseless_fist(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_data_psalm_conclave():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: CHANT OF THE REMORSELESS FIST: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: CHANT OF THE REMORSELESS FIST: not your Fight phase")
            return False

        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        if primary is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: CHANT OF THE REMORSELESS FIST: no eligible CULT MECHANICUS unit selected")
            return False

        eligible_primary = self._data_psalm_cult_mechanicus_primary_candidates(require_not_fought=True)
        if primary not in eligible_primary:
            logger.error("ERROR: CHANT OF THE REMORSELESS FIST: target must be an eligible CULT MECHANICUS unit that has not fought")
            return False

        if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name="Fight phase"):
            logger.error("ERROR: CHANT OF THE REMORSELESS FIST: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False

        source_name = str(getattr(stratagem, "name", "") or "CHANT OF THE REMORSELESS FIST")
        self._mark_data_psalm_phase_effect(
            primary,
            prefix="data_psalm_remorseless_fist",
            source_name=source_name,
            phase_name="FIGHT_PHASE",
        )
        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CHANT OF THE REMORSELESS FIST: %s gains +1 to wound for melee attacks this phase.",
            getattr(primary, "name", "Unit"),
        )
        return True

    def _use_data_psalm_incantation_of_the_iron_soul(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_data_psalm_conclave():
            return False
        unit = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        candidates = list(kwargs.get("candidates") or [])
        from_pending = False
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "INCANTATION OF THE IRON SOUL":
                    continue
                from_pending = True
                unit = self._admech_root(reaction.get("target_unit") or reaction.get("unit"))
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                kwargs.setdefault("mortal_wound_allocated", reaction.get("mortal_wound_allocated"))
                break
        if unit is None and len(candidates) == 1:
            unit = self._admech_root(candidates[0])
        if unit is None:
            logger.error("ERROR: INCANTATION OF THE IRON SOUL: no eligible CULT MECHANICUS unit selected")
            return False

        eligible_primary = self._data_psalm_mortal_wound_reaction_candidates(unit)
        if unit not in eligible_primary:
            logger.error("ERROR: INCANTATION OF THE IRON SOUL: target must be the CULT MECHANICUS unit that just suffered a mortal wound")
            return False
        if not from_pending:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "INCANTATION OF THE IRON SOUL":
                    continue
                pending_root = self._admech_root(reaction.get("target_unit") or reaction.get("unit"))
                if pending_root is not unit:
                    continue
                from_pending = True
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                kwargs.setdefault("mortal_wound_allocated", reaction.get("mortal_wound_allocated"))
                break

        trigger_flag = bool(kwargs.get("mortal_wound_allocated", False))
        trigger_name = str(kwargs.get("trigger", "") or "").strip().lower()
        if not from_pending and not trigger_flag and trigger_name not in {"mortal_wound_allocated", "mortal_wound"}:
            logger.error("ERROR: INCANTATION OF THE IRON SOUL: missing mortal-wound trigger context")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip()
        phase_key = self._phase_key_from_name(phase_name) if phase_name else ""
        if not stratagem.can_use(self.player, self.game, unit=unit, target_unit=unit, phase_name=phase_name or self._current_phase_name):
            logger.error("ERROR: INCANTATION OF THE IRON SOUL: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=unit):
            return False

        source_name = str(getattr(stratagem, "name", "") or "INCANTATION OF THE IRON SOUL")
        for index, model in enumerate(self._admech_unit_models(unit)):
            is_alive_attr = getattr(model, "is_alive", True)
            is_alive = bool(is_alive_attr() if callable(is_alive_attr) else is_alive_attr)
            if not is_alive:
                continue
            effect_key = f"data_psalm_iron_soul:{get_entity_id(model) or index}"
            setter = getattr(model, "set_temporary_fnp", None)
            if callable(setter):
                setter(
                    key=effect_key,
                    value=4,
                    source=source_name,
                    condition="against mortal wounds",
                    expires_phase=phase_key,
                )

        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: INCANTATION OF THE IRON SOUL: %s gains FNP 4+ against mortal wounds this phase.",
            getattr(unit, "name", "Unit"),
        )
        return True

    def _use_data_psalm_litany_of_the_electromancer(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_data_psalm_conclave():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: LITANY OF THE ELECTROMANCER: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: LITANY OF THE ELECTROMANCER: not your Shooting phase")
            return False

        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        if primary is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: LITANY OF THE ELECTROMANCER: no eligible CULT MECHANICUS unit selected")
            return False

        eligible_primary = self._data_psalm_cult_mechanicus_primary_candidates()
        if primary not in eligible_primary:
            logger.error("ERROR: LITANY OF THE ELECTROMANCER: target must be an eligible CULT MECHANICUS unit")
            return False

        if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name="Shooting phase"):
            logger.error("ERROR: LITANY OF THE ELECTROMANCER: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False

        source_name = str(getattr(stratagem, "name", "") or "LITANY OF THE ELECTROMANCER")
        electro_bonus = 1 if self._admech_has_any_keyword(primary, "ELECTRO-PRIEST") else 0
        apply_mortals = getattr(primary, "_apply_mortal_wounds_to_unit", None)
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        affected_units = 0
        total_mortal_wounds = 0
        for enemy in self._data_psalm_electromancer_enemy_candidates(primary):
            roll = int(dice_module.get_roll("D6") or 0) + int(electro_bonus)
            if roll < 5:
                continue
            mortal_wounds = int(dice_module.get_roll("D3") or 0)
            if mortal_wounds <= 0:
                continue
            if callable(apply_mortals):
                apply_mortals(enemy, mortal_wounds, game_map=game_map)
            affected_units += 1
            total_mortal_wounds += int(mortal_wounds)

        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: LITANY OF THE ELECTROMANCER: resolved against %d nearby enemy unit(s) for %d mortal wound(s).",
            int(affected_units),
            int(total_mortal_wounds),
        )
        return True

    def _use_data_psalm_luminescent_blessing(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_data_psalm_conclave():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: LUMINESCENT BLESSING: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: LUMINESCENT BLESSING: not opponent's Shooting phase")
            return False

        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
        candidates = list(kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or [])
        if not target_units:
            target_units = list(candidates)
        if (attacking_unit is None or not target_units) and getattr(self, "_pending_reactions", None):
            for reaction in reversed(list(self._pending_reactions or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "LUMINESCENT BLESSING":
                    continue
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit")
                if not target_units:
                    target_units = list(reaction.get("target_units") or reaction.get("candidates") or [])
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        if attacking_unit is not None:
            get_parent_army = getattr(attacking_unit, "get_parent_army", None)
            parent_army = get_parent_army() if callable(get_parent_army) else getattr(attacking_unit, "parent_army", None)
            if getattr(parent_army, "player", None) is self.player:
                logger.error("ERROR: LUMINESCENT BLESSING: attacker is not enemy")
                return False

        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        eligible_primary = self._data_psalm_reactive_cult_mechanicus_candidates(target_units=target_units)
        if not eligible_primary and candidates:
            eligible_primary = self._data_psalm_reactive_cult_mechanicus_candidates(target_units=candidates)
        if primary is None and len(eligible_primary) == 1:
            primary = eligible_primary[0]
        if primary is None and len(candidates) == 1:
            primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: LUMINESCENT BLESSING: no eligible CULT MECHANICUS unit selected")
            return False
        if primary not in eligible_primary:
            logger.error("ERROR: LUMINESCENT BLESSING: target must be an eligible CULT MECHANICUS unit selected as a shooting target")
            return False

        if not stratagem.can_use(
            self.player,
            self.game,
            unit=primary,
            target_unit=primary,
            attacking_unit=attacking_unit,
            phase_name="Shooting phase",
        ):
            logger.error("ERROR: LUMINESCENT BLESSING: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False

        self._append_defensive_effect(
            primary,
            "defensive_invuln_overrides",
            {
                "value": 4,
                "attack_type": "any",
                "attacker_key": "",
                "expires_phase": "SHOOTING_PHASE",
                "source": str(getattr(stratagem, "name", "") or "LUMINESCENT BLESSING"),
            },
        )
        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: LUMINESCENT BLESSING: %s gains a 4+ invulnerable save this phase.",
            getattr(primary, "name", "Unit"),
        )
        return True

    def _use_data_psalm_tribute_of_emphatic_veneration(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_data_psalm_conclave():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: TRIBUTE OF EMPHATIC VENERATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: TRIBUTE OF EMPHATIC VENERATION: not your Movement phase")
            return False

        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        if primary is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: TRIBUTE OF EMPHATIC VENERATION: no eligible CULT MECHANICUS unit selected")
            return False

        eligible_primary = self._data_psalm_cult_mechanicus_primary_candidates()
        if primary not in eligible_primary:
            logger.error("ERROR: TRIBUTE OF EMPHATIC VENERATION: source must be an eligible CULT MECHANICUS unit")
            return False

        enemy_unit = self._admech_resolve_unit_from_kwargs(kwargs, key="enemy_unit")
        enemy_candidates = self._data_psalm_tribute_enemy_candidates(primary)
        if enemy_unit is None and len(enemy_candidates) == 1:
            enemy_unit = enemy_candidates[0]
        if enemy_unit is None:
            logger.error("ERROR: TRIBUTE OF EMPHATIC VENERATION: no enemy unit selected")
            return False
        if enemy_unit not in enemy_candidates:
            logger.error("ERROR: TRIBUTE OF EMPHATIC VENERATION: enemy must be within 18\" of the selected CULT MECHANICUS unit")
            return False

        if not stratagem.can_use(
            self.player,
            self.game,
            unit=primary,
            target_unit=primary,
            enemy_unit=enemy_unit,
            phase_name="Movement phase",
        ):
            logger.error("ERROR: TRIBUTE OF EMPHATIC VENERATION: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False

        source_name = str(getattr(stratagem, "name", "") or "TRIBUTE OF EMPHATIC VENERATION")
        self._mark_data_psalm_tribute_of_emphatic_veneration_pending(enemy_unit, source_name=source_name)
        take_test = getattr(enemy_unit, "take_battle_shock_test", None)
        if callable(take_test):
            take_test(int(getattr(self.game, "turn", 0) or 0))

        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TRIBUTE OF EMPHATIC VENERATION: %s takes a Battle-shock test; on failure its attacks suffer -1 to hit until your next Command phase.",
            getattr(enemy_unit, "name", "Enemy unit"),
        )
        return True

    def _use_data_psalm_verse_of_vengeance(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_data_psalm_conclave():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: VERSE OF VENGEANCE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: VERSE OF VENGEANCE: not opponent's Fight phase")
            return False

        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
        candidates = list(kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or [])
        if not target_units:
            target_units = list(candidates)
        if (attacking_unit is None or not target_units) and getattr(self, "_pending_reactions", None):
            for reaction in reversed(list(self._pending_reactions or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "VERSE OF VENGEANCE":
                    continue
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit")
                if not target_units:
                    target_units = list(reaction.get("target_units") or reaction.get("candidates") or [])
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        if attacking_unit is not None:
            get_parent_army = getattr(attacking_unit, "get_parent_army", None)
            parent_army = get_parent_army() if callable(get_parent_army) else getattr(attacking_unit, "parent_army", None)
            if getattr(parent_army, "player", None) is self.player:
                logger.error("ERROR: VERSE OF VENGEANCE: attacker is not enemy")
                return False

        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        eligible_primary = self._data_psalm_reactive_cult_mechanicus_candidates(
            target_units=target_units,
            require_not_fought=True,
        )
        if not eligible_primary and candidates:
            eligible_primary = self._data_psalm_reactive_cult_mechanicus_candidates(
                target_units=candidates,
                require_not_fought=True,
            )
        if primary is None and len(eligible_primary) == 1:
            primary = eligible_primary[0]
        if primary is None and len(candidates) == 1:
            primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: VERSE OF VENGEANCE: no eligible CULT MECHANICUS unit selected")
            return False
        if primary not in eligible_primary:
            logger.error("ERROR: VERSE OF VENGEANCE: target must be an eligible CULT MECHANICUS unit that has not fought and was selected as a fight target")
            return False

        if not stratagem.can_use(
            self.player,
            self.game,
            unit=primary,
            target_unit=primary,
            attacking_unit=attacking_unit,
            phase_name="Fight phase",
        ):
            logger.error("ERROR: VERSE OF VENGEANCE: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False

        source_name = str(getattr(stratagem, "name", "") or "VERSE OF VENGEANCE")
        self._mark_data_psalm_phase_effect(
            primary,
            prefix="data_psalm_verse_of_vengeance",
            source_name=source_name,
            phase_name="FIGHT_PHASE",
        )
        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: VERSE OF VENGEANCE: destroyed models in %s can fight on death on 4+ this phase if they have not fought.",
            getattr(primary, "name", "Unit"),
        )
        return True

    def _use_rad_zone_baleful_halo(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_rad_zone_corps():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: BALEFUL HALO: wrong phase")
            return False

        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
        candidates = list(kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or [])
        if not target_units:
            target_units = list(candidates)
        if (attacking_unit is None or not target_units) and getattr(self, "_pending_reactions", None):
            for reaction in reversed(list(self._pending_reactions or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "BALEFUL HALO":
                    continue
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit")
                if not target_units:
                    target_units = list(reaction.get("target_units") or reaction.get("candidates") or [])
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        if attacking_unit is not None:
            get_parent_army = getattr(attacking_unit, "get_parent_army", None)
            parent_army = get_parent_army() if callable(get_parent_army) else getattr(attacking_unit, "parent_army", None)
            if getattr(parent_army, "player", None) is self.player:
                logger.error("ERROR: BALEFUL HALO: attacker is not enemy")
                return False

        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        eligible_primary = self._rad_zone_baleful_halo_primary_candidates(target_units=target_units)
        if not eligible_primary and candidates:
            eligible_primary = self._rad_zone_baleful_halo_primary_candidates(target_units=candidates)
        if primary is None and len(eligible_primary) == 1:
            primary = eligible_primary[0]
        if primary is None and len(candidates) == 1:
            primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: BALEFUL HALO: no primary unit selected")
            return False
        if primary not in eligible_primary:
            logger.error(
                "ERROR: BALEFUL HALO: primary target must be an eligible non-VEHICLE ADEPTUS MECHANICUS unit selected as a target of the attacking unit"
            )
            return False

        secondary = self._admech_resolve_unit_from_kwargs(kwargs, key="secondary_unit", fallback_key="support_unit")
        eligible_secondary = self._rad_zone_optional_skitarii_support_candidates(primary)
        if secondary is not None and secondary not in eligible_secondary:
            logger.error("ERROR: BALEFUL HALO: optional support unit must be eligible SKITARII (excluding BATTLELINE) within 6\"")
            return False

        if not stratagem.can_use(
            self.player,
            self.game,
            unit=primary,
            target_unit=primary,
            attacking_unit=attacking_unit,
            phase_name="Fight phase",
        ):
            logger.error("ERROR: BALEFUL HALO: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False

        source_name = str(getattr(stratagem, "name", "") or "BALEFUL HALO")
        self._mark_rad_zone_baleful_halo(primary, source_name=source_name)
        if secondary is not None:
            self._mark_rad_zone_baleful_halo(secondary, source_name=source_name)

        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        if secondary is None:
            logger.info(
                "INFO: BALEFUL HALO: %s imposes -1 to wound against attacks that target it this Fight phase.",
                getattr(primary, "name", "Unit"),
            )
        else:
            logger.info(
                "INFO: BALEFUL HALO: %s and %s impose -1 to wound against attacks that target them this Fight phase.",
                getattr(primary, "name", "Unit"),
                getattr(secondary, "name", "Unit"),
            )
        return True

    def _use_rad_zone_lethal_dosage(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_rad_zone_corps():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: LETHAL DOSAGE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: LETHAL DOSAGE: not your Shooting phase")
            return False

        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        if primary is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: LETHAL DOSAGE: no primary unit selected")
            return False

        eligible_primary = self._rad_zone_lethal_dosage_primary_candidates()
        if primary not in eligible_primary:
            logger.error("ERROR: LETHAL DOSAGE: primary target must be an eligible ADEPTUS MECHANICUS unit that has not shot")
            return False

        secondary = self._admech_resolve_unit_from_kwargs(kwargs, key="secondary_unit", fallback_key="support_unit")
        eligible_secondary = self._rad_zone_optional_skitarii_support_candidates(primary)
        if secondary is not None and secondary not in eligible_secondary:
            logger.error("ERROR: LETHAL DOSAGE: optional support unit must be eligible SKITARII (excluding BATTLELINE) within 6\"")
            return False

        if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name="Shooting phase"):
            logger.error("ERROR: LETHAL DOSAGE: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False

        source_name = str(getattr(stratagem, "name", "") or "LETHAL DOSAGE")
        self._mark_rad_zone_lethal_dosage(primary, source_name=source_name)
        if secondary is not None:
            self._mark_rad_zone_lethal_dosage(secondary, source_name=source_name)

        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        if secondary is None:
            logger.info("INFO: LETHAL DOSAGE: %s gains Lethal Hits on ranged weapons this phase.", getattr(primary, "name", "Unit"))
        else:
            logger.info(
                "INFO: LETHAL DOSAGE: %s and %s gain Lethal Hits on ranged weapons this phase.",
                getattr(primary, "name", "Unit"),
                getattr(secondary, "name", "Unit"),
            )
        return True

    def _use_rad_zone_bulwark_imperative(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_rad_zone_corps():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: BULWARK IMPERATIVE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: BULWARK IMPERATIVE: not opponent's Shooting phase")
            return False

        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
        candidates = list(kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or [])
        if not target_units:
            target_units = list(candidates)
        if (attacking_unit is None or not target_units) and getattr(self, "_pending_reactions", None):
            for reaction in reversed(list(self._pending_reactions or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "BULWARK IMPERATIVE":
                    continue
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit")
                if not target_units:
                    target_units = list(reaction.get("target_units") or reaction.get("candidates") or [])
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        if attacking_unit is not None:
            get_parent_army = getattr(attacking_unit, "get_parent_army", None)
            parent_army = get_parent_army() if callable(get_parent_army) else getattr(attacking_unit, "parent_army", None)
            if getattr(parent_army, "player", None) is self.player:
                logger.error("ERROR: BULWARK IMPERATIVE: attacker is not enemy")
                return False

        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        eligible_primary = self._rad_zone_bulwark_imperative_primary_candidates(target_units=target_units)
        if not eligible_primary and candidates:
            eligible_primary = self._rad_zone_bulwark_imperative_primary_candidates(target_units=candidates)
        if primary is None and len(eligible_primary) == 1:
            primary = eligible_primary[0]
        if primary is None and len(candidates) == 1:
            primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: BULWARK IMPERATIVE: no primary unit selected")
            return False
        if primary not in eligible_primary:
            logger.error("ERROR: BULWARK IMPERATIVE: primary target must be an eligible SKITARII unit selected as a target of the attacking unit")
            return False

        secondary = self._admech_resolve_unit_from_kwargs(kwargs, key="secondary_unit", fallback_key="support_unit")
        eligible_secondary = self._rad_zone_optional_skitarii_support_candidates(primary)
        if secondary is not None and secondary not in eligible_secondary:
            logger.error("ERROR: BULWARK IMPERATIVE: optional support unit must be eligible SKITARII (excluding BATTLELINE) within 6\"")
            return False

        if not stratagem.can_use(
            self.player,
            self.game,
            unit=primary,
            target_unit=primary,
            attacking_unit=attacking_unit,
            phase_name="Shooting phase",
        ):
            logger.error("ERROR: BULWARK IMPERATIVE: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False

        source_name = str(getattr(stratagem, "name", "") or "BULWARK IMPERATIVE")
        self._mark_rad_zone_bulwark_imperative(primary, source_name=source_name)
        if secondary is not None:
            self._mark_rad_zone_bulwark_imperative(secondary, source_name=source_name)

        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        if secondary is None:
            logger.info(
                "INFO: BULWARK IMPERATIVE: %s gains a 4+ invulnerable save this phase.",
                getattr(primary, "name", "Unit"),
            )
        else:
            logger.info(
                "INFO: BULWARK IMPERATIVE: %s and %s gain a 4+ invulnerable save this phase.",
                getattr(primary, "name", "Unit"),
                getattr(secondary, "name", "Unit"),
            )
        return True

    def _use_rad_zone_aggressor_imperative(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_rad_zone_corps():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: AGGRESSOR IMPERATIVE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: AGGRESSOR IMPERATIVE: not your Movement phase")
            return False

        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        if primary is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: AGGRESSOR IMPERATIVE: no primary unit selected")
            return False

        eligible_primary = self._rad_zone_aggressor_imperative_primary_candidates()
        if primary not in eligible_primary:
            logger.error("ERROR: AGGRESSOR IMPERATIVE: primary target must be an eligible SKITARII unit that has not moved")
            return False

        secondary = self._admech_resolve_unit_from_kwargs(kwargs, key="secondary_unit", fallback_key="support_unit")
        eligible_secondary = self._rad_zone_aggressor_optional_skitarii_support_candidates(primary)
        if secondary is not None and secondary not in eligible_secondary:
            logger.error(
                "ERROR: AGGRESSOR IMPERATIVE: optional support unit must be eligible SKITARII (excluding BATTLELINE) within 6\" that has not moved"
            )
            return False

        if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name="Movement phase"):
            logger.error("ERROR: AGGRESSOR IMPERATIVE: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False

        source_name = str(getattr(stratagem, "name", "") or "AGGRESSOR IMPERATIVE")
        self._mark_rad_zone_aggressor_imperative(primary, source_name=source_name)
        if secondary is not None:
            self._mark_rad_zone_aggressor_imperative(secondary, source_name=source_name)

        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        if secondary is None:
            logger.info(
                "INFO: AGGRESSOR IMPERATIVE: %s adds 6\" to Move when it Advances this phase.",
                getattr(primary, "name", "Unit"),
            )
        else:
            logger.info(
                "INFO: AGGRESSOR IMPERATIVE: %s and %s add 6\" to Move when they Advance this phase.",
                getattr(primary, "name", "Unit"),
                getattr(secondary, "name", "Unit"),
            )
        return True

    def _use_rad_zone_extinction_order(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_rad_zone_corps():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: EXTINCTION ORDER: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: EXTINCTION ORDER: not your Command phase")
            return False

        source_unit = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        if source_unit is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                source_unit = self._admech_root(candidates[0])
        if source_unit is None:
            logger.error("ERROR: EXTINCTION ORDER: no TECH-PRIEST selected")
            return False
        if source_unit not in self._rad_zone_extinction_order_tech_priest_candidates():
            logger.error("ERROR: EXTINCTION ORDER: selected unit must be an eligible TECH-PRIEST model")
            return False

        objective = kwargs.get("objective") or kwargs.get("objective_marker")
        objective_candidates = list(kwargs.get("objective_candidates") or [])
        if not objective_candidates:
            objective_candidates = self._rad_zone_extinction_order_objective_candidates(source_unit)
        if objective is None and len(objective_candidates) == 1:
            objective = objective_candidates[0]
        if objective is None:
            logger.error("ERROR: EXTINCTION ORDER: no objective marker selected")
            return False
        if objective not in objective_candidates:
            logger.error("ERROR: EXTINCTION ORDER: selected objective marker is not eligible")
            return False
        if getattr(objective, "location", None) is None:
            logger.error("ERROR: EXTINCTION ORDER: objective marker has no location")
            return False

        if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name="Command phase"):
            logger.error("ERROR: EXTINCTION ORDER: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=source_unit):
            return False

        game_map = getattr(self.game, "map", None) if self.game is not None else None
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        affected_units = 0
        for enemy in self._rad_zone_extinction_order_enemy_units_for_objective(objective):
            roll = int(dice_module.get_roll("D6") or 0)
            if roll < 4:
                continue
            apply_mortals = getattr(source_unit, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortals):
                apply_mortals(enemy, 1, game_map=game_map)
            take_test = getattr(enemy, "take_battle_shock_test", None)
            if callable(take_test):
                take_test(current_turn)
            affected_units += 1

        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: EXTINCTION ORDER: resolved effects against %d enemy unit(s) within the selected objective marker.",
            affected_units,
        )
        return True

    def _use_rad_zone_pre_calibrated_purge_solution(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_rad_zone_corps():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: PRE-CALIBRATED PURGE SOLUTION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: PRE-CALIBRATED PURGE SOLUTION: not your Shooting phase")
            return False

        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        if primary is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: PRE-CALIBRATED PURGE SOLUTION: no primary unit selected")
            return False

        eligible_primary = self._rad_zone_pre_calibrated_purge_solution_primary_candidates()
        if primary not in eligible_primary:
            logger.error(
                "ERROR: PRE-CALIBRATED PURGE SOLUTION: primary target must be an eligible ADEPTUS MECHANICUS unit that has not shot"
            )
            return False

        secondary = self._admech_resolve_unit_from_kwargs(kwargs, key="secondary_unit", fallback_key="support_unit")
        eligible_secondary = self._rad_zone_optional_skitarii_support_candidates(primary)
        if secondary is not None and secondary not in eligible_secondary:
            logger.error(
                "ERROR: PRE-CALIBRATED PURGE SOLUTION: optional support unit must be eligible SKITARII (excluding BATTLELINE) within 6\""
            )
            return False

        if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name="Shooting phase"):
            logger.error("ERROR: PRE-CALIBRATED PURGE SOLUTION: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False

        enemy_player_id = self._rad_zone_opponent_player_id()
        source_name = str(getattr(stratagem, "name", "") or "PRE-CALIBRATED PURGE SOLUTION")
        self._mark_rad_zone_pre_calibrated(primary, source_name=source_name, enemy_player_id=enemy_player_id)
        if secondary is not None:
            self._mark_rad_zone_pre_calibrated(secondary, source_name=source_name, enemy_player_id=enemy_player_id)

        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        if secondary is None:
            logger.info(
                "INFO: PRE-CALIBRATED PURGE SOLUTION: %s re-rolls ranged Hit rolls vs targets in the opponent deployment zone this phase.",
                getattr(primary, "name", "Unit"),
            )
        else:
            logger.info(
                "INFO: PRE-CALIBRATED PURGE SOLUTION: %s and %s re-roll ranged Hit rolls vs targets in the opponent deployment zone this phase.",
                getattr(primary, "name", "Unit"),
                getattr(secondary, "name", "Unit"),
            )
        return True
