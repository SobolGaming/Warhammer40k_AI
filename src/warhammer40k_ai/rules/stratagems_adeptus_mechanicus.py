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
        if name_u == "CHANT OF THE REMORSELESS FIST":
            return self._use_data_psalm_chant_of_the_remorseless_fist(stratagem, **kwargs)
        if name_u == "INCANTATION OF THE IRON SOUL":
            return self._use_data_psalm_incantation_of_the_iron_soul(stratagem, **kwargs)
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
        if name_u == "TRIBUTE OF EMPHATIC VENERATION":
            return self._use_data_psalm_tribute_of_emphatic_veneration(stratagem, **kwargs)
        if name_u == "TRANSCENDENT COGITATION":
            return self._use_cohort_transcendent_cogitation(stratagem, **kwargs)
        if name_u == "VERSE OF VENGEANCE":
            return self._use_data_psalm_verse_of_vengeance(stratagem, **kwargs)
        return None

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
