from __future__ import annotations

import logging
from typing import Any, Optional

from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
from ..engine.decisions import DecisionOption, DecisionRequest
from ..utility import dice as dice_module
from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class ChaosSpaceMarinesStratagemMixin:
    @staticmethod
    def _csm_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _csm_sort_key(unit: Any) -> str:
        return str(get_entity_id(unit) or "")

    @staticmethod
    def _csm_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(unit, "is_alive", True))

    @staticmethod
    def _csm_is_on_battlefield(unit: Any) -> bool:
        if unit is None:
            return False
        if not bool(getattr(unit, "deployed", False)):
            return False
        in_reserves = getattr(unit, "is_in_reserves", None)
        if callable(in_reserves) and bool(in_reserves()):
            return False
        if bool(getattr(unit, "is_embarked", False)) or getattr(unit, "embarked_in", None) is not None:
            return False
        return True

    @staticmethod
    def _csm_is_in_reserves(unit: Any) -> bool:
        if unit is None:
            return False
        in_reserves = getattr(unit, "is_in_reserves", None)
        if callable(in_reserves):
            return bool(in_reserves())
        reserve_status = str(getattr(unit, "reserve_status", "") or "").strip().lower()
        return reserve_status in {"reserves", "strategic_reserves"}

    @staticmethod
    def _csm_owned_by_player(unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(parent_army, "player", None) is player

    @staticmethod
    def _csm_has_keyword(entity: Any, keyword: str) -> bool:
        if entity is None:
            return False
        key = str(keyword or "").strip()
        if not key:
            return False
        has_any = getattr(entity, "has_any_keyword", None)
        if callable(has_any) and bool(has_any(key)):
            return True
        has_keyword = getattr(entity, "has_keyword", None)
        if callable(has_keyword) and bool(has_keyword(key)):
            return True
        return False

    def _get_chaos_space_marines_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        return getattr(army, "chaos_space_marines_detachments", None) if army is not None else None

    def _is_cabal_of_chaos_detachment(self) -> bool:
        mgr = self._get_chaos_space_marines_mgr()
        checker = getattr(mgr, "is_cabal_of_chaos", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_chaos_cult_detachment(self) -> bool:
        mgr = self._get_chaos_space_marines_mgr()
        checker = getattr(mgr, "is_chaos_cult", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_creations_of_bile_detachment(self) -> bool:
        mgr = self._get_chaos_space_marines_mgr()
        checker = getattr(mgr, "is_creations_of_bile", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_deceptors_detachment(self) -> bool:
        mgr = self._get_chaos_space_marines_mgr()
        checker = getattr(mgr, "is_deceptors", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_dread_talons_detachment(self) -> bool:
        mgr = self._get_chaos_space_marines_mgr()
        checker = getattr(mgr, "is_dread_talons", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_fellhammer_siege_host_detachment(self) -> bool:
        mgr = self._get_chaos_space_marines_mgr()
        checker = getattr(mgr, "is_fellhammer_siege_host", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_hurons_marauders_detachment(self) -> bool:
        mgr = self._get_chaos_space_marines_mgr()
        checker = getattr(mgr, "is_hurons_marauders", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_nightmare_hunt_detachment(self) -> bool:
        mgr = self._get_chaos_space_marines_mgr()
        checker = getattr(mgr, "is_nightmare_hunt", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_pactbound_zealots_detachment(self) -> bool:
        mgr = self._get_chaos_space_marines_mgr()
        checker = getattr(mgr, "is_pactbound_zealots", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_renegade_warband_detachment(self) -> bool:
        mgr = self._get_chaos_space_marines_mgr()
        checker = getattr(mgr, "is_renegade_warband", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_soulforged_warpack_detachment(self) -> bool:
        mgr = self._get_chaos_space_marines_mgr()
        checker = getattr(mgr, "is_soulforged_warpack", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_veterans_of_the_long_war_detachment(self) -> bool:
        mgr = self._get_chaos_space_marines_mgr()
        checker = getattr(mgr, "is_veterans_of_the_long_war", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_renegade_raiders_detachment(self) -> bool:
        mgr = self._get_chaos_space_marines_mgr()
        checker = getattr(mgr, "is_renegade_raiders", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_heretic_astartes_unit(self, unit: Any) -> bool:
        root = self._csm_root(unit)
        if root is None:
            return False
        mgr = self._get_chaos_space_marines_mgr()
        checker = getattr(mgr, "_unit_is_heretic_astartes", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        return self._csm_has_keyword(root, "HERETIC ASTARTES")

    def _is_heretic_astartes_infantry(self, unit: Any) -> bool:
        root = self._csm_root(unit)
        if root is None:
            return False
        if not self._is_heretic_astartes_unit(root):
            return False
        return self._csm_has_keyword(root, "INFANTRY")

    def _is_heretic_astartes_mounted(self, unit: Any) -> bool:
        root = self._csm_root(unit)
        if root is None:
            return False
        if not self._is_heretic_astartes_unit(root):
            return False
        return self._csm_has_keyword(root, "MOUNTED")

    def _is_damned_unit(self, unit: Any) -> bool:
        root = self._csm_root(unit)
        if root is None:
            return False
        mgr = self._get_chaos_space_marines_mgr()
        checker = getattr(mgr, "_unit_is_damned", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        return self._csm_has_keyword(root, "DAMNED")

    def _is_creations_eligible_unit(self, unit: Any) -> bool:
        root = self._csm_root(unit)
        if root is None:
            return False
        mgr = self._get_chaos_space_marines_mgr()
        checker = getattr(mgr, "_unit_is_creations_eligible", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        return bool(self._is_heretic_astartes_infantry(root) and not self._is_damned_unit(root))

    def _csm_model_is_character(self, model: Any) -> bool:
        if model is None:
            return False
        char_attr = getattr(model, "is_character", None)
        if bool(char_attr() if callable(char_attr) else char_attr):
            return True
        if self._csm_has_keyword(model, "CHARACTER"):
            return True
        parent = getattr(model, "parent_unit", None)
        return bool(parent is not None and self._csm_has_keyword(parent, "CHARACTER"))

    def _is_cabal_psyker_source_unit(self, unit: Any) -> bool:
        root = self._csm_root(unit)
        if root is None:
            return False
        if not self._is_heretic_astartes_unit(root):
            return False
        return self._csm_has_keyword(root, "PSYKER")

    def _is_cabal_daemon_prince_source_unit(self, unit: Any) -> bool:
        root = self._csm_root(unit)
        if root is None:
            return False
        if not self._is_heretic_astartes_unit(root):
            return False
        if self._csm_has_keyword(root, "DAEMON PRINCE") or self._csm_has_keyword(root, "DAEMON PRINCE WITH WINGS"):
            return True
        normalized_name = " ".join(str(getattr(root, "name", "") or "").strip().lower().split())
        return "daemon prince" in normalized_name

    def _is_cabal_shroud_source_unit(self, unit: Any) -> bool:
        return self._is_cabal_psyker_source_unit(unit) or self._is_cabal_daemon_prince_source_unit(unit)

    def _cabal_within_empyric_support(self, unit: Any, *, radius: float = 9.0) -> bool:
        root = self._csm_root(unit)
        if root is None:
            return False
        helper = getattr(root, "_friendly_empyric_source_within_range", None)
        if callable(helper):
            if bool(helper(choice="LEAPING_WARPFLAME", radius=float(radius))):
                return True
            if bool(helper(choice="MONSTROUS_MANIFESTATION", radius=float(radius))):
                return True

        from ..utility.aura_utils import unit_within_range_of_unit

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return False
        seen: set[str] = set()
        for candidate in list(getattr(army, "units", []) or []):
            source_root = self._csm_root(candidate)
            if source_root is None:
                continue
            uid = self._csm_sort_key(source_root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._is_cabal_shroud_source_unit(source_root):
                continue
            if not self._csm_is_alive(source_root) or not self._csm_is_on_battlefield(source_root):
                continue
            if unit_within_range_of_unit(source_root, root, float(radius), use_attached_aggregate=True):
                return True
        return False

    def _cabal_targetable_units(
        self,
        *,
        require_infantry: bool = False,
        require_not_shot: bool = False,
        require_not_attempted_charge: bool = False,
        require_psyker: bool = False,
        require_within_empyric_support: bool = False,
        require_shroud_source: bool = False,
    ) -> list[Any]:
        if not self._is_cabal_of_chaos_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_heretic_astartes_unit(root):
                continue
            if require_infantry and not self._is_heretic_astartes_infantry(root):
                continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if require_not_attempted_charge and bool(getattr(getattr(root, "round_state", None), "attempted_charge_this_round", False)):
                continue
            if require_psyker and not self._is_cabal_psyker_source_unit(root):
                continue
            if require_within_empyric_support and not self._cabal_within_empyric_support(root, radius=9.0):
                continue
            if require_shroud_source and not self._is_cabal_shroud_source_unit(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _cabal_baleful_blessing_candidates(self) -> list[Any]:
        return self._cabal_targetable_units()

    def _cabal_soulseekers_candidates(self) -> list[Any]:
        return self._cabal_targetable_units(require_not_shot=True)

    def _cabal_unholy_haste_candidates(self) -> list[Any]:
        return self._cabal_targetable_units(require_infantry=True, require_not_attempted_charge=True)

    def _cabal_no_rest_in_death_candidates(self) -> list[Any]:
        return self._cabal_targetable_units(require_within_empyric_support=True)

    def _cabal_mutations_curse_source_candidates(self) -> list[Any]:
        return self._cabal_targetable_units(require_psyker=True)

    def _cabal_shroud_of_chaos_candidates(self) -> list[Any]:
        return self._cabal_targetable_units(require_shroud_source=True)

    def _chaos_cult_targetable_units(
        self,
        *,
        require_damned: bool = False,
        require_heretic_astartes: bool = False,
        require_dark_pacts: bool = False,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_not_attempted_charge: bool = False,
    ) -> list[Any]:
        if not self._is_chaos_cult_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        mgr = self._get_chaos_space_marines_mgr()
        has_dark_pacts = getattr(mgr, "_unit_has_dark_pacts", None) if mgr is not None else None

        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if require_damned and not self._is_damned_unit(root):
                continue
            if require_heretic_astartes and not self._is_heretic_astartes_unit(root):
                continue
            if require_dark_pacts and callable(has_dark_pacts) and not bool(has_dark_pacts(root)):
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
                continue
            if require_not_attempted_charge and bool(getattr(round_state, "attempted_charge_this_round", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _chaos_cult_damned_shooting_candidates(self) -> list[Any]:
        return self._chaos_cult_targetable_units(
            require_damned=True,
            require_dark_pacts=True,
            require_not_shot=True,
        )

    def _chaos_cult_damned_fight_candidates(self) -> list[Any]:
        return self._chaos_cult_targetable_units(
            require_damned=True,
            require_dark_pacts=True,
            require_not_fought=True,
        )

    def _chaos_cult_reckless_haste_candidates(self) -> list[Any]:
        return self._chaos_cult_targetable_units(
            require_damned=True,
            require_not_attempted_charge=True,
        )

    def _creations_of_bile_targetable_units(
        self,
        *,
        require_infantry: bool = True,
        require_creations_eligible: bool = False,
        require_not_fought: bool = False,
        require_not_attempted_charge: bool = False,
        require_destroyed_non_character_model: bool = False,
    ) -> list[Any]:
        if not self._is_creations_of_bile_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if require_infantry and not self._is_heretic_astartes_infantry(root):
                continue
            if require_creations_eligible and not self._is_creations_eligible_unit(root):
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
                continue
            if require_not_attempted_charge and bool(getattr(round_state, "attempted_charge_this_round", False)):
                continue
            if require_destroyed_non_character_model:
                destroyed_pool = list(getattr(root, "models_lost", []) or [])
                eligible_destroyed = [model for model in destroyed_pool if not self._csm_model_is_character(model)]
                if not eligible_destroyed:
                    continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _creations_of_bile_autostimulants_candidates(self) -> list[Any]:
        return self._creations_of_bile_targetable_units(require_not_attempted_charge=True)

    def _creations_of_bile_delayed_mutations_candidates(self) -> list[Any]:
        return self._creations_of_bile_targetable_units(require_creations_eligible=True)

    def _creations_of_bile_diabolic_regeneration_candidates(self) -> list[Any]:
        return self._creations_of_bile_targetable_units(
            require_creations_eligible=True,
            require_destroyed_non_character_model=True,
        )

    def _creations_of_bile_specimens_for_the_spider_candidates(self) -> list[Any]:
        return self._creations_of_bile_targetable_units(require_not_fought=True)

    def _creations_of_bile_masters_are_watching_candidates(self, *, target_units: list[Any]) -> list[Any]:
        candidates: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._csm_root(target)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_heretic_astartes_infantry(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _csm_unit_is_engaged(self, unit: Any) -> bool:
        root = self._csm_root(unit)
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if root is None or game_map is None:
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        within_engagement = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(within_engagement):
            return False
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._csm_root(enemy)
            if enemy_root is None or not self._csm_is_alive(enemy_root):
                continue
            if not bool(getattr(enemy_root, "deployed", False)):
                continue
            if within_engagement(root, enemy_root):
                return True
        return False

    def _deceptors_targetable_units(
        self,
        *,
        require_not_shot: bool = False,
        require_fell_back: bool = False,
        require_character: bool = False,
        require_infantry_or_mounted: bool = False,
        require_not_engaged: bool = False,
    ) -> list[Any]:
        if not self._is_deceptors_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_heretic_astartes_unit(root):
                continue
            if require_character and not self._csm_has_keyword(root, "CHARACTER"):
                continue
            if require_infantry_or_mounted and not (
                self._is_heretic_astartes_infantry(root) or self._is_heretic_astartes_mounted(root)
            ):
                continue
            if require_not_engaged and self._csm_unit_is_engaged(root):
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
                continue
            if require_fell_back and not bool(getattr(round_state, "fell_back_this_round", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _deceptors_detonator_candidates(self, *, destroyed_model: Any) -> list[Any]:
        if destroyed_model is None:
            return []
        try:
            from ..utility.aura_utils import distance_between_models_bases_3d
        except ImportError:
            return []

        candidates: list[Any] = []
        for root in self._deceptors_targetable_units(require_character=True):
            get_models = getattr(root, "get_attached_unit_models", None)
            models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
            for model in list(models or []):
                if model is None or not bool(getattr(model, "is_alive", False)):
                    continue
                try:
                    distance = float(distance_between_models_bases_3d(model, destroyed_model))
                except (AttributeError, TypeError, ValueError):
                    continue
                if distance <= 18.0 + 1e-6:
                    candidates.append(root)
                    break
        return sorted(candidates, key=self._csm_sort_key)

    def _deceptors_relentless_pursuit_candidates(self, *, enemy_unit: Any) -> list[Any]:
        enemy_root = self._csm_root(enemy_unit)
        if enemy_root is None:
            return []
        try:
            from ..utility.aura_utils import unit_within_range_of_unit
        except ImportError:
            return []

        candidates: list[Any] = []
        for root in self._deceptors_targetable_units(
            require_infantry_or_mounted=True,
            require_not_engaged=True,
        ):
            if not unit_within_range_of_unit(root, enemy_root, 9.0, use_attached_aggregate=True):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _csm_unit_visible_to_unit(self, source_unit: Any, target_unit: Any) -> bool:
        source_root = self._csm_root(source_unit)
        target_root = self._csm_root(target_unit)
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if source_root is None or target_root is None or game_map is None:
            return False
        los_checker = getattr(source_root, "_attacking_unit_has_any_los_to_target_unit", None)
        return bool(callable(los_checker) and los_checker(target_root, game_map))

    def _dread_talons_targetable_units(
        self,
        *,
        require_infantry: bool = False,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_not_engaged: bool = False,
        require_fell_back: bool = False,
        require_jump_pack_reserves: bool = False,
    ) -> list[Any]:
        if not self._is_dread_talons_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root):
                continue
            if require_jump_pack_reserves:
                if not self._csm_is_in_reserves(root):
                    continue
            else:
                if not self._csm_is_on_battlefield(root):
                    continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_heretic_astartes_unit(root):
                continue
            if require_infantry and not self._is_heretic_astartes_infantry(root):
                continue
            if require_jump_pack_reserves and not self._csm_has_keyword(root, "JUMP PACK"):
                continue
            if require_not_engaged and self._csm_unit_is_engaged(root):
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
                continue
            if require_fell_back and not bool(getattr(round_state, "fell_back_this_round", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _fellhammer_targetable_units(
        self,
        *,
        require_infantry: bool = False,
        exclude_damned: bool = False,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_engaged: bool = False,
    ) -> list[Any]:
        if not self._is_fellhammer_siege_host_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_heretic_astartes_unit(root):
                continue
            if require_infantry and not self._is_heretic_astartes_infantry(root):
                continue
            if exclude_damned and self._is_damned_unit(root):
                continue
            if require_engaged and not self._csm_unit_is_engaged(root):
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _fellhammer_targeted_units(
        self,
        *,
        target_units: list[Any],
        require_infantry: bool = False,
        exclude_damned: bool = False,
        require_not_fought: bool = False,
    ) -> list[Any]:
        candidates: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._csm_root(target)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_heretic_astartes_unit(root):
                continue
            if require_infantry and not self._is_heretic_astartes_infantry(root):
                continue
            if exclude_damned and self._is_damned_unit(root):
                continue
            if require_not_fought and bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _nightmare_hunt_targetable_units(
        self,
        *,
        require_infantry: bool = False,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_fell_back: bool = False,
        require_arrived_from_reserves: bool = False,
    ) -> list[Any]:
        if not self._is_nightmare_hunt_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_heretic_astartes_unit(root):
                continue
            if require_infantry and not self._is_heretic_astartes_infantry(root):
                continue
            if require_arrived_from_reserves and not bool(getattr(root, "arrived_from_reserves_this_turn", False)):
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
                continue
            if require_fell_back and not bool(getattr(round_state, "fell_back_this_round", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _pactbound_mark_for_unit(self, unit: Any) -> str:
        mgr = self._get_chaos_space_marines_mgr()
        resolve_mark = getattr(mgr, "pactbound_mark_for_unit", None) if mgr is not None else None
        if not callable(resolve_mark):
            return ""
        return str(resolve_mark(unit, assign_default=True) or "").strip().upper()

    def _pactbound_targetable_units(
        self,
        *,
        required_mark: str = "",
        require_not_shot: bool = False,
        require_not_fought: bool = False,
    ) -> list[Any]:
        if not self._is_pactbound_zealots_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        expected_mark = str(required_mark or "").strip().upper()
        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_heretic_astartes_unit(root):
                continue
            if expected_mark and self._pactbound_mark_for_unit(root) != expected_mark:
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _pactbound_targeted_units(self, *, target_units: list[Any]) -> list[Any]:
        candidates: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._csm_root(target)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_heretic_astartes_unit(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _renegade_warband_targetable_units(
        self,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_infantry_or_mounted: bool = False,
        exclude_damned: bool = False,
        exclude_monster_vehicle: bool = False,
    ) -> list[Any]:
        if not self._is_renegade_warband_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_heretic_astartes_unit(root):
                continue
            if require_infantry_or_mounted and not (
                self._is_heretic_astartes_infantry(root) or self._is_heretic_astartes_mounted(root)
            ):
                continue
            if exclude_damned and self._is_damned_unit(root):
                continue
            if exclude_monster_vehicle and (
                self._csm_has_keyword(root, "MONSTER") or self._csm_has_keyword(root, "VEHICLE")
            ):
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _renegade_warband_controlled_objective_candidates(self, unit: Any) -> list[Any]:
        root = self._csm_root(unit)
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if root is None or game_map is None:
            return []
        is_within = getattr(root, "is_within_objective_range", None)
        if not callable(is_within):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for objective in list(getattr(game_map, "objectives", []) or []):
            location = getattr(objective, "location", None)
            if location is None or bool(getattr(location, "removed", False)):
                continue
            if not bool(is_within(location)):
                continue
            controller = getattr(location, "controlling_player", None)
            sticky_controller = getattr(location, "sticky_controller", None)
            if controller is not self.player and sticky_controller is not self.player:
                continue
            objective_id = str(getattr(objective, "id", "") or get_entity_id(objective) or "")
            if objective_id and objective_id in seen:
                continue
            if objective_id:
                seen.add(objective_id)
            out.append(objective)
        out.sort(key=lambda objective: str(getattr(objective, "id", "") or get_entity_id(objective) or ""))
        return out

    def _renegade_warband_selected_targets_include_vendetta(self, *, target_units: list[Any]) -> bool:
        mgr = self._get_chaos_space_marines_mgr()
        vendetta_target_id = str(getattr(mgr, "renegade_warband_vendetta_target_unit_id", "") or "").strip()
        if not vendetta_target_id:
            return False
        for target in list(target_units or []):
            root = self._csm_root(target)
            if root is None:
                continue
            if str(get_entity_id(root) or "").strip() == vendetta_target_id:
                return True
        return False

    @staticmethod
    def _renegade_warband_unit_in_candidates(root: Any, candidates: list[Any]) -> bool:
        if root is None:
            return False
        rid = str(get_entity_id(root) or "")
        for candidate in list(candidates or []):
            candidate_root = candidate.get_attached_unit_root() if hasattr(candidate, "get_attached_unit_root") else candidate
            if candidate_root is None:
                continue
            cid = str(get_entity_id(candidate_root) or "")
            if rid and cid and rid == cid:
                return True
            if candidate_root is root:
                return True
        return False

    @staticmethod
    def _renegade_warband_never_outgunned_choice_key(choice_payload: Any) -> str:
        text = str(choice_payload or "").strip().upper().replace(" ", "_")
        if text == "LETHAL_HITS":
            return "LETHAL_HITS"
        if text in {"SUSTAINED_HITS", "SUSTAINED_HITS_1"}:
            return "SUSTAINED_HITS_1"
        return ""

    @classmethod
    def _renegade_warband_never_outgunned_choice_label(cls, choice_key: str) -> str:
        choice = cls._renegade_warband_never_outgunned_choice_key(choice_key)
        if choice == "LETHAL_HITS":
            return "Lethal Hits"
        if choice == "SUSTAINED_HITS_1":
            return "Sustained Hits 1"
        return ""

    def apply_renegade_warband_never_outgunned(
        self,
        unit: Any,
        *,
        choice_key: str,
        phase_name: str,
        source: str = "Never Outgunned",
    ) -> dict:
        root = self._csm_root(unit)
        choice = self._renegade_warband_never_outgunned_choice_key(choice_key)
        phase_key = str(phase_name or "").strip().lower()
        if root is None:
            return {"ok": False, "reason": "Unit not found."}
        if choice not in {"LETHAL_HITS", "SUSTAINED_HITS_1"}:
            return {"ok": False, "reason": "Choice is invalid."}
        if phase_key not in {"shooting phase", "fight phase"}:
            return {"ok": False, "reason": "Phase is invalid."}

        keyword = "LETHAL HITS" if choice == "LETHAL_HITS" else "SUSTAINED HITS 1"
        attack_type = "ranged" if phase_key == "shooting phase" else "melee"
        expires_phase = "SHOOTING_PHASE" if attack_type == "ranged" else "FIGHT_PHASE"
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        if not models:
            models = list(getattr(root, "models", []) or [])

        applied = False
        for model in list(models or []):
            if model is None:
                continue
            is_alive_attr = getattr(model, "is_alive", True)
            is_alive = bool(is_alive_attr() if callable(is_alive_attr) else is_alive_attr)
            if not is_alive:
                continue
            model_id = str(get_entity_id(model) or "")
            for wargear in list(getattr(model, "wargear", []) or []):
                if wargear is None:
                    continue
                attack_check = getattr(wargear, "is_ranged" if attack_type == "ranged" else "is_melee", None)
                if not callable(attack_check) or not bool(attack_check()):
                    continue
                weapon_name = str(getattr(wargear, "name", "") or "").strip()
                if not weapon_name:
                    continue
                set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                if callable(set_keywords):
                    set_keywords(
                        key=f"renegade_warband_never_outgunned:{choice}:{attack_type}:{model_id}:{weapon_name}".lower(),
                        weapon_name=weapon_name,
                        keywords=[keyword],
                        source=str(source or "Never Outgunned").strip() or "Never Outgunned",
                        expires_phase=expires_phase,
                        attack_type=attack_type,
                    )
                    applied = True
        if not applied:
            return {"ok": False, "reason": "No eligible weapons found."}
        return {
            "ok": True,
            "choice_key": choice,
            "choice_name": keyword,
            "keyword": keyword,
            "attack_type": attack_type,
            "phase_name": "Shooting phase" if attack_type == "ranged" else "Fight phase",
        }

    def _renegade_raiders_targetable_units(
        self,
        *,
        require_infantry_or_mounted: bool = False,
        require_transport_or_mounted: bool = False,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_not_attempted_charge: bool = False,
        require_not_moved: bool = False,
        require_disembarked_this_round: bool = False,
        require_eligible_to_fight: bool = False,
    ) -> list[Any]:
        if not self._is_renegade_raiders_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_heretic_astartes_unit(root):
                continue
            if require_infantry_or_mounted and not (
                self._is_heretic_astartes_infantry(root) or self._is_heretic_astartes_mounted(root)
            ):
                continue
            if require_transport_or_mounted and not (
                self._is_heretic_astartes_mounted(root) or self._csm_has_keyword(root, "TRANSPORT")
            ):
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
                continue
            if require_not_attempted_charge and bool(getattr(round_state, "attempted_charge_this_round", False)):
                continue
            if require_not_moved and bool(getattr(round_state, "moved_this_round", False)):
                continue
            if require_disembarked_this_round and not bool(getattr(round_state, "disembarked_this_round", False)):
                continue
            if require_eligible_to_fight:
                was_eligible = bool(getattr(round_state, "eligible_to_fight_this_phase", False))
                if not was_eligible and bool(getattr(round_state, "fought_this_phase", False)):
                    was_eligible = True
                if not was_eligible:
                    continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _renegade_raiders_targeted_units(
        self,
        *,
        target_units: list[Any],
        exclude_damned: bool = False,
    ) -> list[Any]:
        candidates: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._csm_root(target)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_heretic_astartes_unit(root):
                continue
            if exclude_damned and self._is_damned_unit(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _veterans_targetable_units(
        self,
        *,
        require_character: bool = False,
        require_infantry_or_mounted: bool = False,
        exclude_damned: bool = False,
        exclude_tzeentch: bool = False,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_not_engaged: bool = False,
    ) -> list[Any]:
        if not self._is_veterans_of_the_long_war_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_heretic_astartes_unit(root):
                continue
            if require_character and not self._csm_has_keyword(root, "CHARACTER"):
                continue
            if require_infantry_or_mounted and not (
                self._is_heretic_astartes_infantry(root) or self._is_heretic_astartes_mounted(root)
            ):
                continue
            if exclude_damned and self._is_damned_unit(root):
                continue
            if exclude_tzeentch and self._csm_has_keyword(root, "TZEENTCH"):
                continue
            if require_not_engaged and self._csm_unit_is_engaged(root):
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _veterans_targeted_units(
        self,
        *,
        target_units: list[Any],
        exclude_damned: bool = False,
    ) -> list[Any]:
        candidates: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._csm_root(target)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_heretic_astartes_unit(root):
                continue
            if exclude_damned and self._is_damned_unit(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _veterans_bringers_of_despair_candidates(self) -> list[Any]:
        mgr = self._get_chaos_space_marines_mgr()
        focus_target_id = str(getattr(mgr, "veterans_focus_of_hatred_target_unit_id", "") or "").strip()
        if not focus_target_id or self.game is None:
            return []
        registry = getattr(self.game, "entity_registry", None)
        focus_target = registry.get(focus_target_id, kind="unit") if registry is not None and hasattr(registry, "get") else None
        focus_root = self._csm_root(focus_target)
        if focus_root is None or not self._csm_is_alive(focus_root) or not self._csm_is_on_battlefield(focus_root):
            return []
        game_map = getattr(self.game, "map", None)
        within_engagement = getattr(game_map, "is_within_engagement_range", None) if game_map is not None else None
        if not callable(within_engagement):
            return []

        candidates: list[Any] = []
        for root in self._veterans_targetable_units(exclude_damned=True):
            if not bool(within_engagement(root, focus_root)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    @staticmethod
    def _veterans_unit_in_candidates(root: Any, candidates: list[Any]) -> bool:
        if root is None:
            return False
        rid = str(get_entity_id(root) or "")
        for candidate in list(candidates or []):
            candidate_root = candidate.get_attached_unit_root() if hasattr(candidate, "get_attached_unit_root") else candidate
            if candidate_root is None:
                continue
            cid = str(get_entity_id(candidate_root) or "")
            if rid and cid and rid == cid:
                return True
            if candidate_root is root:
                return True
        return False

    def _veterans_millennia_of_experience_candidates(self, *, enemy_unit: Any) -> list[Any]:
        if not self._is_veterans_of_the_long_war_detachment():
            return []
        enemy_root = self._csm_root(enemy_unit)
        if enemy_root is None or self._csm_owned_by_player(enemy_root, self.player):
            return []
        if not self._csm_is_alive(enemy_root) or not self._csm_is_on_battlefield(enemy_root):
            return []
        try:
            from ..utility.aura_utils import unit_within_range_of_unit
        except ImportError:
            return []

        candidates: list[Any] = []
        for root in self._veterans_targetable_units(
            require_infantry_or_mounted=True,
            exclude_damned=True,
            require_not_engaged=True,
        ):
            if not unit_within_range_of_unit(root, enemy_root, 9.0, use_attached_aggregate=True):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    @staticmethod
    def _is_soulforged_unit_in_candidates(root: Any, candidates: list[Any]) -> bool:
        if root is None:
            return False
        rid = str(get_entity_id(root) or "")
        for candidate in list(candidates or []):
            candidate_root = candidate.get_attached_unit_root() if hasattr(candidate, "get_attached_unit_root") else candidate
            if candidate_root is None:
                continue
            cid = str(get_entity_id(candidate_root) or "")
            if rid and cid and rid == cid:
                return True
            if candidate_root is root:
                return True
        return False

    @classmethod
    def _is_vashtorr_unit(cls, unit: Any) -> bool:
        root = cls._csm_root(unit)
        if root is None:
            return False
        normalized_name = " ".join(str(getattr(root, "name", "") or "").strip().lower().split())
        return normalized_name == "vashtorr the arkifane" or normalized_name == "vashtorr"

    def _soulforged_targetable_units(
        self,
        *,
        require_vehicle: bool = False,
        require_daemon_vehicle: bool = False,
        allow_vashtorr: bool = False,
        exclude_daemon: bool = False,
        exclude_titanic: bool = False,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_not_moved: bool = False,
        require_not_attempted_charge: bool = False,
        require_not_engaged: bool = False,
    ) -> list[Any]:
        if not self._is_soulforged_warpack_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue

            is_vashtorr = self._is_vashtorr_unit(root)
            if not self._is_heretic_astartes_unit(root) and not is_vashtorr:
                continue
            if require_vehicle and not (self._csm_has_keyword(root, "VEHICLE") or (allow_vashtorr and is_vashtorr)):
                continue
            if require_daemon_vehicle and not (
                self._csm_has_keyword(root, "VEHICLE") and self._csm_has_keyword(root, "DAEMON")
            ):
                continue
            if exclude_daemon and self._csm_has_keyword(root, "DAEMON"):
                continue
            if exclude_titanic and self._csm_has_keyword(root, "TITANIC"):
                continue
            if require_not_engaged and self._csm_unit_is_engaged(root):
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
                continue
            if require_not_moved and bool(getattr(round_state, "moved_this_round", False)):
                continue
            if require_not_attempted_charge and bool(getattr(round_state, "attempted_charge_this_round", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _soulforged_feeding_frenzy_candidates(self, *, enemy_unit: Any) -> list[Any]:
        enemy_root = self._csm_root(enemy_unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        within_engagement = getattr(game_map, "is_within_engagement_range", None) if game_map is not None else None
        if enemy_root is None or not callable(within_engagement):
            return []
        if self._csm_has_keyword(enemy_root, "MONSTER") or self._csm_has_keyword(enemy_root, "VEHICLE"):
            return []

        candidates: list[Any] = []
        for root in self._soulforged_targetable_units(allow_vashtorr=True):
            if not (
                (self._csm_has_keyword(root, "VEHICLE") and self._csm_has_keyword(root, "DAEMON"))
                or self._is_vashtorr_unit(root)
            ):
                continue
            if not bool(within_engagement(root, enemy_root)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _soulforged_predatory_pursuit_candidates(self, *, enemy_unit: Any) -> list[Any]:
        enemy_root = self._csm_root(enemy_unit)
        if enemy_root is None:
            return []
        try:
            from ..utility.aura_utils import unit_within_range_of_unit
        except ImportError:
            return []

        candidates: list[Any] = []
        for root in self._soulforged_targetable_units(
            require_vehicle=True,
            allow_vashtorr=True,
            require_not_engaged=True,
        ):
            if not unit_within_range_of_unit(root, enemy_root, 9.0, use_attached_aggregate=True):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    @staticmethod
    def _renegade_raiders_unit_in_candidates(root: Any, candidates: list[Any]) -> bool:
        if root is None:
            return False
        rid = str(get_entity_id(root) or "")
        for candidate in list(candidates or []):
            candidate_root = candidate.get_attached_unit_root() if hasattr(candidate, "get_attached_unit_root") else candidate
            if candidate_root is None:
                continue
            cid = str(get_entity_id(candidate_root) or "")
            if rid and cid and rid == cid:
                return True
            if candidate_root is root:
                return True
        return False

    def _renegade_raiders_normal_move_distance(self, unit: Any) -> int:
        root = self._csm_root(unit)
        if root is None:
            return 0
        game_map = getattr(getattr(self, "game", None), "map", None)
        model = None
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        for member in list(models or []):
            try:
                alive = getattr(member, "is_alive", True)
                if callable(alive):
                    alive = alive()
            except (AttributeError, TypeError, ValueError):
                alive = True
            if bool(alive):
                model = member
                break
        get_effective = getattr(root, "get_effective_model_characteristic", None)
        if model is not None and callable(get_effective):
            try:
                distance = int(get_effective(model, "movement", game_map=game_map) or 0)
            except (AttributeError, TypeError, ValueError):
                distance = 0
            if distance > 0:
                return int(distance)
        try:
            distance = int(getattr(root, "movement", 0) or 0)
        except (AttributeError, TypeError, ValueError):
            distance = 0
        if distance > 0:
            return int(distance)
        if model is not None:
            try:
                distance = int(getattr(model, "movement", getattr(model, "_movement", 0)) or 0)
            except (AttributeError, TypeError, ValueError):
                distance = 0
            if distance > 0:
                return int(distance)
        return 0

    def _pactbound_attached_models(self, unit: Any) -> list[Any]:
        root = self._csm_root(unit)
        if root is None:
            return []
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        return list(models or [])

    def _pactbound_wounded_models(self, unit: Any) -> list[Any]:
        wounded: list[Any] = []
        for model in self._pactbound_attached_models(unit):
            if model is None:
                continue
            alive_attr = getattr(model, "is_alive", True)
            if not bool(alive_attr() if callable(alive_attr) else alive_attr):
                continue
            try:
                base_wounds = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)) or 0)
                current_wounds = int(getattr(model, "wounds", 0) or 0)
            except (TypeError, ValueError):
                continue
            if base_wounds > current_wounds:
                wounded.append(model)
        return sorted(wounded, key=lambda model: str(get_entity_id(model) or ""))

    def _pactbound_destroyed_non_character_models(self, unit: Any) -> list[Any]:
        root = self._csm_root(unit)
        if root is None:
            return []
        destroyed_pool = list(getattr(root, "models_lost", []) or [])
        can_return = getattr(root, "_horrors_can_return_model", None)
        candidates: list[Any] = []
        for model in destroyed_pool:
            if model is None:
                continue
            if self._csm_model_is_character(model):
                continue
            if callable(can_return) and not bool(can_return(model)):
                continue
            candidates.append(model)
        return sorted(candidates, key=lambda model: str(get_entity_id(model) or ""))

    def _pactbound_skinshift_candidates(self) -> list[Any]:
        candidates: list[Any] = []
        for root in self._pactbound_targetable_units():
            wounded_models = self._pactbound_wounded_models(root)
            mark = self._pactbound_mark_for_unit(root)
            below_starting_strength = bool(getattr(root, "is_below_starting_strength", lambda: False)())
            destroyed_models = self._pactbound_destroyed_non_character_models(root)
            if wounded_models or (mark == "TZEENTCH" and below_starting_strength and destroyed_models):
                candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _pactbound_eye_of_the_gods_character_models(self, unit: Any) -> list[Any]:
        mgr = self._get_chaos_space_marines_mgr()
        get_candidates = getattr(mgr, "pactbound_eye_of_the_gods_candidate_models", None) if mgr is not None else None
        if not callable(get_candidates):
            return []
        return list(get_candidates(unit) or [])

    def _hurons_marauders_targetable_units(
        self,
        *,
        require_damned: bool = False,
        require_non_monster_non_vehicle: bool = False,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_charged: bool = False,
        require_not_engaged: bool = False,
    ) -> list[Any]:
        if not self._is_hurons_marauders_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_heretic_astartes_unit(root):
                continue
            if require_damned and not self._is_damned_unit(root):
                continue
            if require_non_monster_non_vehicle and (
                self._csm_has_keyword(root, "MONSTER") or self._csm_has_keyword(root, "VEHICLE")
            ):
                continue
            if require_not_engaged and self._csm_unit_is_engaged(root):
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
                continue
            if require_charged and not bool(getattr(round_state, "charged_this_round", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _hurons_marauders_targeted_units(
        self,
        *,
        target_units: list[Any],
        require_non_monster_non_vehicle: bool = False,
    ) -> list[Any]:
        candidates: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._csm_root(target)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_heretic_astartes_unit(root):
                continue
            if require_non_monster_non_vehicle and (
                self._csm_has_keyword(root, "MONSTER") or self._csm_has_keyword(root, "VEHICLE")
            ):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    @staticmethod
    def _hurons_marauders_total_current_wounds(unit: Any) -> int:
        root = unit
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
        if root is None:
            return 0
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        total = 0
        for model in list(models or []):
            if model is None:
                continue
            alive_attr = getattr(model, "is_alive", True)
            if not bool(alive_attr() if callable(alive_attr) else alive_attr):
                continue
            total += int(getattr(model, "wounds", 0) or 0)
        return int(total)

    def _hurons_marauders_shooting_wounds_before(self) -> dict[str, dict[str, dict[str, Any]]]:
        snapshots = getattr(self, "_hurons_marauders_favoured_spoils_snapshots", None)
        if not isinstance(snapshots, dict):
            snapshots = {}
            self._hurons_marauders_favoured_spoils_snapshots = snapshots
        return snapshots

    def _record_hurons_marauders_favoured_spoils_snapshot(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        attacker_root = self._csm_root(attacking_unit)
        if attacker_root is None or self._csm_owned_by_player(attacker_root, self.player):
            return
        attacker_key = str(self._attacker_unit_key(attacker_root) or "").strip()
        if not attacker_key:
            return
        self._hurons_marauders_shooting_wounds_before()[attacker_key] = {
            self._csm_sort_key(root): {
                "unit_id": str(get_entity_id(root) or ""),
                "wounds_before": int(self._hurons_marauders_total_current_wounds(root) or 0),
            }
            for root in self._hurons_marauders_targeted_units(target_units=list(target_units or []))
            if str(get_entity_id(root) or "").strip()
        }

    def _hurons_marauders_resolve_unit_by_id(self, unit_id: str) -> Any:
        unit_key = str(unit_id or "").strip()
        if not unit_key:
            return None
        registry = getattr(getattr(self, "game", None), "entity_registry", None)
        if registry is not None and hasattr(registry, "get"):
            unit = registry.get(unit_key, kind="unit")
            root = self._csm_root(unit)
            if root is not None:
                return root
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            if str(get_entity_id(root) or "").strip() == unit_key:
                return root
        return None

    def _hurons_marauders_closest_non_aircraft_enemy(self, unit: Any) -> Any:
        root = self._csm_root(unit)
        if root is None or self.game is None:
            return None
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return None
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        get_distance = getattr(game_map, "get_distance_between_units", None)
        if not callable(get_enemy_units) or not callable(get_distance):
            return None

        closest = None
        closest_distance = None
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._csm_root(enemy)
            if enemy_root is None:
                continue
            if not self._csm_is_alive(enemy_root) or not self._csm_is_on_battlefield(enemy_root):
                continue
            if self._csm_has_keyword(enemy_root, "AIRCRAFT"):
                continue
            try:
                distance = float(get_distance(root, enemy_root))
            except (TypeError, ValueError):
                continue
            if closest_distance is None or distance < closest_distance:
                closest_distance = distance
                closest = enemy_root
        return closest

    @staticmethod
    def _hurons_marauders_unit_in_candidates(root: Any, candidates: list[Any]) -> bool:
        if root is None:
            return False
        rid = str(get_entity_id(root) or "")
        for candidate in list(candidates or []):
            candidate_root = candidate.get_attached_unit_root() if hasattr(candidate, "get_attached_unit_root") else candidate
            if candidate_root is None:
                continue
            cid = str(get_entity_id(candidate_root) or "")
            if rid and cid and rid == cid:
                return True
            if candidate_root is root:
                return True
        return False

    def _dread_talons_enemy_units_in_range_visible(
        self,
        source_unit: Any,
        *,
        radius: float,
        require_infantry_or_mounted: bool = False,
    ) -> list[Any]:
        source_root = self._csm_root(source_unit)
        if source_root is None or self.game is None:
            return []
        get_enemy_units = getattr(self.game, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return []
        try:
            from ..utility.aura_utils import unit_within_range_of_unit
        except ImportError:
            return []

        candidates: list[Any] = []
        seen: set[str] = set()
        for enemy in list(get_enemy_units(self.player) or []):
            enemy_root = self._csm_root(enemy)
            if enemy_root is None:
                continue
            enemy_id = self._csm_sort_key(enemy_root)
            if enemy_id and enemy_id in seen:
                continue
            if enemy_id:
                seen.add(enemy_id)
            if not self._csm_is_alive(enemy_root) or not self._csm_is_on_battlefield(enemy_root):
                continue
            if require_infantry_or_mounted and not (
                self._csm_has_keyword(enemy_root, "INFANTRY") or self._csm_has_keyword(enemy_root, "MOUNTED")
            ):
                continue
            if not unit_within_range_of_unit(source_root, enemy_root, float(radius), use_attached_aggregate=True):
                continue
            if not self._csm_unit_visible_to_unit(source_root, enemy_root):
                continue
            candidates.append(enemy_root)
        return sorted(candidates, key=self._csm_sort_key)

    def _nightmare_hunt_enemy_units_in_range_visible(
        self,
        source_unit: Any,
        *,
        radius: float,
        exclude_monster_vehicle: bool = False,
    ) -> list[Any]:
        if not self._is_nightmare_hunt_detachment():
            return []
        candidates = self._dread_talons_enemy_units_in_range_visible(source_unit, radius=float(radius))
        if not exclude_monster_vehicle:
            return candidates
        return [
            enemy
            for enemy in list(candidates or [])
            if not self._csm_has_keyword(enemy, "MONSTER") and not self._csm_has_keyword(enemy, "VEHICLE")
        ]

    def _dread_talons_merciless_pursuit_enemy_candidates_for_unit(self, unit: Any) -> list[Any]:
        root = self._csm_root(unit)
        if root is None or self.game is None:
            return []
        try:
            from ..utility.aura_utils import unit_within_range_of_unit
        except ImportError:
            return []

        candidates: list[Any] = []
        seen: set[str] = set()
        for enemy in list(getattr(self.game, "get_enemy_units", lambda _player: [])(self.player) or []):
            enemy_root = self._csm_root(enemy)
            if enemy_root is None:
                continue
            enemy_id = self._csm_sort_key(enemy_root)
            if enemy_id and enemy_id in seen:
                continue
            if enemy_id:
                seen.add(enemy_id)
            if not self._csm_is_alive(enemy_root) or not self._csm_is_on_battlefield(enemy_root):
                continue
            if not bool(getattr(getattr(enemy_root, "round_state", None), "fell_back_this_round", False)):
                continue
            if not unit_within_range_of_unit(root, enemy_root, 6.0, use_attached_aggregate=True):
                continue
            can_charge = getattr(root, "can_declare_charge_against", None)
            if not callable(can_charge) or not bool(can_charge(enemy_root, self.game, out_of_turn=True)):
                continue
            candidates.append(enemy_root)
        return sorted(candidates, key=self._csm_sort_key)

    def _dread_talons_merciless_pursuit_candidates(self) -> tuple[list[Any], dict[str, list[Any]]]:
        candidates: list[Any] = []
        enemy_candidates_by_unit: dict[str, list[Any]] = {}
        for root in self._dread_talons_targetable_units(require_infantry=True, require_not_engaged=True):
            enemy_candidates = self._dread_talons_merciless_pursuit_enemy_candidates_for_unit(root)
            if not enemy_candidates:
                continue
            candidates.append(root)
            enemy_candidates_by_unit[self._csm_sort_key(root)] = list(enemy_candidates)
        return sorted(candidates, key=self._csm_sort_key), enemy_candidates_by_unit

    def _csm_find_pending_reaction(self, stratagem_name: str, *, unit: Any = None):
        name_u = self._normalize_stratagem_name(stratagem_name)
        expected_root = self._csm_root(unit)
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if self._normalize_stratagem_name(reaction.get("stratagem", "") or "") != name_u:
                continue
            if expected_root is None:
                return reaction
            reaction_root = self._csm_root(reaction.get("unit") or reaction.get("target_unit"))
            if reaction_root is expected_root:
                return reaction
        return None

    def _chaos_cult_unit_visible_to_unit(self, source_unit: Any, target_unit: Any) -> bool:
        return self._csm_unit_visible_to_unit(source_unit, target_unit)

    def _chaos_cult_mortal_thralls_support_candidates(
        self,
        *,
        protected_unit: Any,
        attacking_unit: Any,
    ) -> list[Any]:
        protected_root = self._csm_root(protected_unit)
        attacker_root = self._csm_root(attacking_unit)
        if protected_root is None or attacker_root is None:
            return []
        from ..utility.aura_utils import unit_within_range_of_unit

        support_pool = self._chaos_cult_targetable_units(require_damned=True)
        candidates: list[Any] = []
        for support_root in list(support_pool or []):
            if not unit_within_range_of_unit(protected_root, support_root, 3.0, use_attached_aggregate=True):
                continue
            if not self._chaos_cult_unit_visible_to_unit(protected_root, support_root):
                continue
            if not self._chaos_cult_unit_visible_to_unit(attacker_root, support_root):
                continue
            candidates.append(support_root)
        return sorted(candidates, key=self._csm_sort_key)

    def _chaos_cult_mortal_thralls_candidate_map(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> dict[str, dict[str, Any]]:
        candidates: dict[str, dict[str, Any]] = {}
        seen: set[str] = set()
        for target in list(target_units or []):
            protected_root = self._csm_root(target)
            if protected_root is None:
                continue
            uid = self._csm_sort_key(protected_root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(protected_root, self.player):
                continue
            if not self._csm_is_alive(protected_root) or not self._csm_is_on_battlefield(protected_root):
                continue
            if self._unit_cannot_be_target_of_stratagem(protected_root):
                continue
            if not self._is_heretic_astartes_unit(protected_root):
                continue
            support_candidates = self._chaos_cult_mortal_thralls_support_candidates(
                protected_unit=protected_root,
                attacking_unit=attacking_unit,
            )
            if not support_candidates:
                continue
            candidates[uid] = {"unit": protected_root, "support_candidates": support_candidates}
        return candidates

    def _chaos_cult_selfless_demise_candidates(self, *, target_units: list[Any]) -> list[Any]:
        candidates: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._csm_root(target)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_damned_unit(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _cabal_mutations_curse_enemy_candidates(self, source_unit: Any, *, radius: float = 12.0) -> list[Any]:
        source_root = self._csm_root(source_unit)
        if source_root is None:
            return []
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return []

        from ..utility.aura_utils import unit_within_range_of_unit

        candidates: list[Any] = []
        seen: set[str] = set()
        los_checker = getattr(source_root, "_attacking_unit_has_any_los_to_target_unit", None)
        for enemy in list(getattr(game_map, "get_enemy_units", lambda _u: [])(source_root) or []):
            enemy_root = self._csm_root(enemy)
            if enemy_root is None:
                continue
            uid = self._csm_sort_key(enemy_root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_is_alive(enemy_root):
                continue
            if not bool(getattr(enemy_root, "deployed", False)):
                continue
            if not unit_within_range_of_unit(source_root, enemy_root, float(radius), use_attached_aggregate=True):
                continue
            if callable(los_checker) and not bool(los_checker(enemy_root, game_map)):
                continue
            candidates.append(enemy_root)
        return sorted(candidates, key=self._csm_sort_key)

    def _cabal_effective_cp_cost(self, stratagem: Any, *, target_unit: Any = None) -> int:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_cost = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_cost):
            preview = apply_cost(stratagem, target_unit=target_unit) or {}
            cp_cost = int(preview.get("cost", cp_cost))
        return cp_cost

    def _cabal_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        cp_cost = self._cabal_effective_cp_cost(stratagem, target_unit=target_unit)
        return bool(
            self.player.spend_command_points(
                cp_cost,
                reason=f"Stratagem: {stratagem.name}",
                source="stratagem",
            )
        )

    def _cabal_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())

    def _cabal_reaction_already_queued(
        self,
        *,
        event_name: str,
        stratagem_name: str,
        phase_name: str,
        target_unit: Any = None,
    ) -> bool:
        expected_name = self._normalize_stratagem_name(stratagem_name)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != str(event_name):
                continue
            if self._normalize_stratagem_name(reaction.get("stratagem", "") or "") != expected_name:
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() != str(phase_name or "").strip().lower():
                continue
            if target_unit is not None and reaction.get("target_unit") is not target_unit and reaction.get("unit") is not target_unit:
                continue
            return True
        return False

    def _queue_cabal_of_chaos_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_cabal_of_chaos_detachment():
            return
        if str(getattr(phase, "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        if player is self.player:
            return

        stratagem = self.get_by_name("SHROUD OF CHAOS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        candidates = self._cabal_shroud_of_chaos_candidates()
        if not candidates:
            return
        if self._cabal_reaction_already_queued(
            event_name="phase_start",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
        ):
            return

        payload = {
            "event": "phase_start",
            "phase": "Shooting phase",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
            payload["unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_cabal_of_chaos_mortal_wound_reaction(
        self,
        *,
        target_unit: Any,
        attacker_unit: Any = None,
        target_model: Any = None,
        phase_name: str = "",
    ) -> None:
        if not self._is_cabal_of_chaos_detachment():
            return
        root = self._csm_root(target_unit)
        if root is None:
            return
        if not self._csm_owned_by_player(root, self.player):
            return
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return
        if self._unit_cannot_be_target_of_stratagem(root):
            return
        if not self._is_heretic_astartes_unit(root):
            return

        stratagem = self.get_by_name("BALEFUL BLESSING")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        if not phase_name:
            phase_name = str(getattr(self, "_current_phase_name", "") or "")
        if not phase_name:
            phase_key = str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper()
            name_map = {
                "COMMAND_PHASE": "Command phase",
                "MOVEMENT_PHASE": "Movement phase",
                "SHOOTING_PHASE": "Shooting phase",
                "CHARGE_PHASE": "Charge phase",
                "FIGHT_PHASE": "Fight phase",
            }
            phase_name = name_map.get(phase_key, phase_key.title().replace("_", " ")) if phase_key else ""
        if not phase_name:
            phase_name = "Any phase"

        if self._cabal_reaction_already_queued(
            event_name="mortal_wound_allocated",
            stratagem_name=stratagem.name,
            phase_name=phase_name,
            target_unit=root,
        ):
            return

        payload = {
            "event": "mortal_wound_allocated",
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "target_unit": root,
            "unit": root,
            "attacking_unit": attacker_unit,
            "target_model": target_model,
            "candidates": [root],
            "mortal_wound_allocated": True,
        }
        self._queue_reaction(payload, use_timer=False)

    def _queue_chaos_cult_shooting_target_reactions(self, *, attacking_unit: Any, target_units: list[Any]) -> None:
        if not self._is_chaos_cult_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        attacker_root = self._csm_root(attacking_unit)
        if attacker_root is None:
            return
        if self._csm_owned_by_player(attacker_root, self.player):
            return
        stratagem = self.get_by_name("MORTAL THRALLS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidate_map = self._chaos_cult_mortal_thralls_candidate_map(
            attacking_unit=attacking_unit,
            target_units=list(target_units or []),
        )
        if not candidate_map:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "shooting_targets_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "MORTAL THRALLS":
                continue
            if self._csm_root(reaction.get("attacking_unit")) is attacker_root:
                return
        ordered_candidates = [entry["unit"] for entry in candidate_map.values()]
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": ordered_candidates,
            "support_candidates_by_unit": {
                key: list(entry["support_candidates"] or [])
                for key, entry in candidate_map.items()
            },
        }
        if len(ordered_candidates) == 1:
            protected_root = ordered_candidates[0]
            protected_key = self._csm_sort_key(protected_root)
            payload["unit"] = protected_root
            payload["target_unit"] = protected_root
            support_candidates = list(payload["support_candidates_by_unit"].get(protected_key, []) or [])
            if len(support_candidates) == 1:
                payload["support_unit"] = support_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_chaos_cult_fight_target_reactions(self, *, attacking_unit: Any, target_units: list[Any]) -> None:
        if not self._is_chaos_cult_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        attacker_root = self._csm_root(attacking_unit)
        if attacker_root is None:
            return
        if self._csm_owned_by_player(attacker_root, self.player):
            return
        stratagem = self.get_by_name("SELFLESS DEMISE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._chaos_cult_selfless_demise_candidates(target_units=list(target_units or []))
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "fight_targets_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "SELFLESS DEMISE":
                continue
            if self._csm_root(reaction.get("attacking_unit")) is attacker_root:
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_creations_of_bile_fight_target_reactions(self, *, attacking_unit: Any, target_units: list[Any]) -> None:
        if not self._is_creations_of_bile_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        attacker_root = self._csm_root(attacking_unit)
        if attacker_root is None:
            return
        if self._csm_owned_by_player(attacker_root, self.player):
            return
        stratagem = self.get_by_name("MASTERS ARE WATCHING")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._creations_of_bile_masters_are_watching_candidates(target_units=list(target_units or []))
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "fight_targets_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "MASTERS ARE WATCHING":
                continue
            if self._csm_root(reaction.get("attacking_unit")) is attacker_root:
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_deceptors_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_deceptors_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if player is not self.player:
            return

        if phase_key == "CHARGE_PHASE":
            stratagem = self.get_by_name("FROM ALL SIDES")
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
                return
            if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                return
            candidates = self._deceptors_targetable_units()
            if not candidates:
                return
            if self._cabal_reaction_already_queued(
                event_name="phase_start",
                stratagem_name=stratagem.name,
                phase_name="Charge phase",
            ):
                return
            payload = {
                "event": "phase_start",
                "phase": "Charge phase",
                "phase_name": "Charge phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)
            return

        if phase_key != "SHOOTING_PHASE":
            return
        stratagem = self.get_by_name("PICK THEM OFF")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._deceptors_targetable_units(require_not_shot=True)
        if not candidates:
            return
        if self._cabal_reaction_already_queued(
            event_name="phase_start",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
        ):
            return
        payload = {
            "event": "phase_start",
            "phase": "Shooting phase",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_deceptors_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_deceptors_detachment():
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        action_key = str(action or "").strip().lower().replace(" ", "_")
        moving_root = self._csm_root(unit)
        if moving_root is None:
            return

        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            if phase_name != "movement phase" or action_key not in {"fall_back", "fallback"}:
                return
            if not self._csm_owned_by_player(moving_root, self.player):
                return
            stratagem = self.get_by_name("COILS OF DECEPTION")
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem, target_unit=moving_root):
                return
            if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                return
            candidates = self._deceptors_targetable_units(require_fell_back=True)
            if moving_root not in candidates:
                return
            if self._cabal_reaction_already_queued(
                event_name="unit_move_ended",
                stratagem_name=stratagem.name,
                phase_name="Movement phase",
                target_unit=moving_root,
            ):
                return
            self._queue_reaction(
                {
                    "event": "unit_move_ended",
                    "phase_name": "Movement phase",
                    "stratagem": stratagem.name,
                    "cp_cost": stratagem.cp_cost,
                    "unit": moving_root,
                    "target_unit": moving_root,
                    "action": str(action or ""),
                    "candidates": [moving_root],
                },
                use_timer=False,
            )
            return

        if phase_name != "movement phase" or action_key not in {"move", "normal", "normal_move", "advance", "fall_back", "fallback"}:
            return
        if self._csm_owned_by_player(moving_root, self.player):
            return
        stratagem = self.get_by_name("RELENTLESS PURSUIT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._deceptors_relentless_pursuit_candidates(enemy_unit=moving_root)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_move_ended":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem.name or "").strip().upper():
                continue
            if self._csm_root(reaction.get("moving_unit")) is moving_root:
                return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "moving_unit": moving_root,
            "enemy_unit": moving_root,
            "action": str(action or ""),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_deceptors_model_destroyed_reactions(self, *, unit: Any, model: Any) -> None:
        if not self._is_deceptors_detachment():
            return
        destroyed_root = self._csm_root(unit)
        if destroyed_root is None or model is None:
            return
        if self._csm_owned_by_player(destroyed_root, self.player):
            return
        if self._csm_has_keyword(destroyed_root, "TITANIC"):
            return
        has_deadly_demise = getattr(destroyed_root, "has_deadly_demise", None)
        deadly_demise = has_deadly_demise() if callable(has_deadly_demise) else (False, None)
        if not bool(deadly_demise[0]):
            return

        stratagem = self.get_by_name("DETONATOR")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._deceptors_detonator_candidates(destroyed_model=model)
        if not candidates:
            return
        destroyed_model_id = str(get_entity_id(model) or "")
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "model_destroyed_before_removal":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem.name or "").strip().upper():
                continue
            if str(reaction.get("destroyed_model_id", "") or "") == destroyed_model_id:
                return
        payload = {
            "event": "model_destroyed_before_removal",
            "phase_name": str(getattr(self, "_current_phase_name", "") or ""),
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "destroyed_unit": destroyed_root,
            "destroyed_model": model,
            "destroyed_model_id": destroyed_model_id,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_deceptors_reinforcements_step_reactions(self, *, current_player: Any) -> None:
        if not self._is_deceptors_detachment():
            return
        if current_player is None or current_player is self.player:
            return
        if str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return
        stratagem = self.get_by_name("SCRAMBLED COORDINATES")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._deceptors_targetable_units()
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "reinforcements_step_start":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem.name or "").strip().upper():
                continue
            if str(reaction.get("current_player_id", "") or "") == str(getattr(current_player, "id", "") or ""):
                return
        payload = {
            "event": "reinforcements_step_start",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "current_player_id": str(getattr(current_player, "id", "") or ""),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _cleanup_cabal_of_chaos_phase_end_effects(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_name:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return

        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue

            if phase_name == "SHOOTING_PHASE":
                sr = getattr(root, "special_rules", None)
                if isinstance(sr, dict) and bool(sr.get("shroud_of_chaos_aura_active")):
                    for key in (
                        "shroud_of_chaos_aura_active",
                        "shroud_of_chaos_expires_phase",
                        "shroud_of_chaos_owner",
                        "shroud_of_chaos_turn",
                        "shroud_of_chaos_source",
                    ):
                        sr.pop(key, None)
                    root.special_rules = sr
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict):
                remove_prefixes = (
                    "chaos_cult_chosen_for_glory",
                    "chaos_cult_crazed_focus",
                    "chaos_cult_infernal_sacrifice",
                    "chaos_cult_selfless_demise",
                    "chaos_cult_mortal_thralls",
                    "creations_of_bile_masters_are_watching",
                    "creations_of_bile_specimens_for_the_spider",
                )
                remove_keys = [
                    key
                    for key in list(sr.keys())
                    if any(str(key).startswith(prefix) for prefix in remove_prefixes)
                ]
                if remove_keys:
                    for key in remove_keys:
                        sr.pop(key, None)
                    root.special_rules = sr

            models = []
            get_models = getattr(root, "get_attached_unit_models", None)
            if callable(get_models):
                models = list(get_models() or [])
            if not models:
                models = list(getattr(root, "models", []) or [])
            for model in models:
                effects = getattr(model, "_temporary_effects", None)
                if not isinstance(effects, dict) or not effects:
                    continue
                remove_keys: list[str] = []
                for key, value in list(effects.items()):
                    if not str(key or "").startswith("baleful_blessing:"):
                        continue
                    exp_phase = str(value.get("expires_phase", "") or "").strip().upper() if isinstance(value, dict) else ""
                    if not exp_phase or exp_phase == phase_name:
                        remove_keys.append(str(key))
                for key in remove_keys:
                    effects.pop(key, None)

    def _cleanup_deceptors_phase_end_effects(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_name:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        mgr = self._get_chaos_space_marines_mgr()
        if army is None or mgr is None:
            return

        prefix_by_phase = {
            "MOVEMENT_PHASE": (mgr._DECEPTORS_SCRAMBLED_COORDINATES_PREFIX,),
            "SHOOTING_PHASE": (mgr._DECEPTORS_PICK_THEM_OFF_PREFIX,),
            "CHARGE_PHASE": (mgr._DECEPTORS_FROM_ALL_SIDES_PREFIX,),
            "FIGHT_PHASE": (mgr._DECEPTORS_COILS_OF_DECEPTION_PREFIX,),
        }
        prefixes = prefix_by_phase.get(phase_name, ())
        if not prefixes:
            return
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            for prefix in prefixes:
                mgr._remove_special_rule_prefix(root, prefix)

    def _cleanup_soulforged_phase_end_effects(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_name:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        mgr = self._get_chaos_space_marines_mgr()
        if army is None or mgr is None:
            return

        prefix_by_phase = {
            "SHOOTING_PHASE": (mgr._SOULFORGED_WARPACK_DESPERATE_PLEDGE_PREFIX,),
            "FIGHT_PHASE": (
                mgr._SOULFORGED_WARPACK_DESPERATE_PLEDGE_PREFIX,
                mgr._SOULFORGED_WARPACK_GLUT_OF_SOULS_PREFIX,
            ),
        }
        prefixes = prefix_by_phase.get(phase_name, ())

        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            for prefix in prefixes:
                mgr._remove_special_rule_prefix(root, prefix)

            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue

            if str(sr.get(mgr._SOULFORGED_WARPACK_CONTRACT_EXPIRES_PHASE_KEY, "") or "").strip().upper() == phase_name:
                for key in (
                    mgr._SOULFORGED_WARPACK_CONTRACT_ACTIVE_KEY,
                    mgr._SOULFORGED_WARPACK_CONTRACT_EXPIRES_PHASE_KEY,
                    mgr._SOULFORGED_WARPACK_CONTRACT_TURN_KEY,
                    mgr._SOULFORGED_WARPACK_CONTRACT_OWNER_KEY,
                    mgr._SOULFORGED_WARPACK_CONTRACT_SOURCE_KEY,
                    mgr._SOULFORGED_WARPACK_CONTRACT_CHOICE_KEY,
                ):
                    sr.pop(key, None)
            if str(sr.get(mgr._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_EXPIRES_PHASE_KEY, "") or "").strip().upper() == phase_name:
                for key in (
                    mgr._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_ACTIVE_KEY,
                    mgr._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_EXPIRES_PHASE_KEY,
                    mgr._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_TURN_KEY,
                    mgr._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_OWNER_KEY,
                    mgr._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_SOURCE_KEY,
                ):
                    sr.pop(key, None)

            if phase_name == "MOVEMENT_PHASE" and bool(sr.get("enemy_fallback_desperate_escape")):
                source_name = self._normalize_stratagem_name(str(sr.get("enemy_fallback_desperate_escape_source", "") or ""))
                expires_phase = str(sr.get("enemy_fallback_desperate_escape_expires_phase", "") or "").strip().upper()
                if source_name == self._normalize_stratagem_name("FEEDING FRENZY") and (not expires_phase or expires_phase == phase_name):
                    for key in (
                        "enemy_fallback_desperate_escape",
                        "enemy_fallback_desperate_escape_exclude_monster_vehicle",
                        "enemy_fallback_desperate_escape_bs_penalty",
                        "enemy_fallback_desperate_escape_penalty",
                        "enemy_fallback_desperate_escape_target_enemy_id",
                        "enemy_fallback_desperate_escape_expires_phase",
                        "enemy_fallback_desperate_escape_turn_owner",
                        "enemy_fallback_desperate_escape_turn",
                        "enemy_fallback_desperate_escape_source",
                    ):
                        sr.pop(key, None)

            if bool(sr.get("soulforged_warpack_unstoppable_rampage_active")):
                expires_phase = str(sr.get("soulforged_warpack_unstoppable_rampage_expires_phase", "") or "").strip().upper()
                if not expires_phase or expires_phase == phase_name:
                    added = set(sr.get("soulforged_warpack_unstoppable_rampage_added_phase_move_terrain_only_types") or [])
                    if added:
                        current = list(sr.get("bearer_unit_phase_move_terrain_only_types") or [])
                        kept = [move_type for move_type in current if move_type not in added]
                        if kept:
                            sr["bearer_unit_phase_move_terrain_only_types"] = kept
                        else:
                            sr.pop("bearer_unit_phase_move_terrain_only_types", None)
                    for key in (
                        "soulforged_warpack_unstoppable_rampage_active",
                        "soulforged_warpack_unstoppable_rampage_expires_phase",
                        "soulforged_warpack_unstoppable_rampage_turn_owner",
                        "soulforged_warpack_unstoppable_rampage_turn",
                        "soulforged_warpack_unstoppable_rampage_source",
                        "soulforged_warpack_unstoppable_rampage_added_phase_move_terrain_only_types",
                    ):
                        sr.pop(key, None)

            root.special_rules = sr
            mgr._clear_unit_ability_cache(root)

    def _queue_dread_talons_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_dread_talons_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()

        if phase_key == "SHOOTING_PHASE":
            if player is not self.player:
                return
            stratagem = self.get_by_name("PITILESS HUNTERS")
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
                return
            if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                return
            candidates = self._dread_talons_targetable_units(require_infantry=True, require_not_shot=True)
            if not candidates:
                return
            if self._cabal_reaction_already_queued(
                event_name="phase_start",
                stratagem_name=stratagem.name,
                phase_name="Shooting phase",
            ):
                return
            payload = {
                "event": "phase_start",
                "phase": "Shooting phase",
                "phase_name": "Shooting phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)
            return

        if phase_key != "FIGHT_PHASE":
            return
        stratagem = self.get_by_name("DEPTHLESS CRUELTY")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._dread_talons_targetable_units(require_infantry=True, require_not_fought=True)
        if not candidates:
            return
        if self._cabal_reaction_already_queued(
            event_name="phase_start",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
        ):
            return
        payload = {
            "event": "phase_start",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_dread_talons_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_dread_talons_detachment():
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        action_key = str(action or "").strip().lower().replace(" ", "_")
        if phase_name != "movement phase" or action_key not in {"fall_back", "fallback"}:
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return
        moving_root = self._csm_root(unit)
        if moving_root is None or not self._csm_owned_by_player(moving_root, self.player):
            return
        stratagem = self.get_by_name("RELENTLESS TERROR")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem, target_unit=moving_root):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._dread_talons_targetable_units(require_infantry=True, require_fell_back=True)
        if moving_root not in candidates:
            return
        if self._cabal_reaction_already_queued(
            event_name="unit_move_ended",
            stratagem_name=stratagem.name,
            phase_name="Movement phase",
            target_unit=moving_root,
        ):
            return
        self._queue_reaction(
            {
                "event": "unit_move_ended",
                "phase_name": "Movement phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": moving_root,
                "target_unit": moving_root,
                "action": str(action or ""),
                "candidates": [moving_root],
            },
            use_timer=False,
        )

    def _queue_dread_talons_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_dread_talons_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "MOVEMENT_PHASE" or player is self.player:
            return
        stratagem = self.get_by_name("MERCILESS PURSUIT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates, enemy_map = self._dread_talons_merciless_pursuit_candidates()
        if not candidates:
            return
        if self._cabal_reaction_already_queued(
            event_name="phase_end",
            stratagem_name=stratagem.name,
            phase_name="Movement phase",
        ):
            return
        payload: dict[str, Any] = {
            "event": "phase_end",
            "phase": "Movement phase",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
            "enemy_candidates_by_unit": enemy_map,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
            enemy_candidates = list(enemy_map.get(self._csm_sort_key(candidates[0])) or [])
            if enemy_candidates:
                payload["enemy_candidates"] = enemy_candidates
                if len(enemy_candidates) == 1:
                    payload["enemy_unit"] = enemy_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_dread_talons_unit_destroyed_reactions(self, *, destroyed_unit: Any, destroyed_by_unit: Any) -> None:
        if not self._is_dread_talons_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        source_root = self._csm_root(destroyed_by_unit)
        destroyed_root = self._csm_root(destroyed_unit)
        if source_root is None or destroyed_root is None:
            return
        if not self._csm_owned_by_player(source_root, self.player):
            return
        if self._csm_owned_by_player(destroyed_root, self.player):
            return
        if not self._csm_is_alive(source_root) or not self._csm_is_on_battlefield(source_root):
            return
        if self._unit_cannot_be_target_of_stratagem(source_root):
            return
        if not self._is_heretic_astartes_unit(source_root):
            return
        if not self._csm_has_keyword(destroyed_root, "CHARACTER"):
            return
        visible_enemies = self._dread_talons_enemy_units_in_range_visible(source_root, radius=12.0)
        if not visible_enemies:
            return
        stratagem = self.get_by_name("BLOODY EXAMPLE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem, target_unit=source_root):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._cabal_reaction_already_queued(
            event_name="unit_destroyed",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
            target_unit=source_root,
        ):
            return
        self._queue_reaction(
            {
                "event": "unit_destroyed",
                "phase_name": "Fight phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": source_root,
                "target_unit": source_root,
                "destroyed_unit": destroyed_root,
                "enemy_units": visible_enemies,
                "candidates": [source_root],
            },
            use_timer=False,
        )

    def _queue_dread_talons_reinforcements_step_reactions(self, *, current_player: Any) -> None:
        if not self._is_dread_talons_detachment():
            return
        if current_player is not self.player:
            return
        if str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return
        try:
            battle_round = int(getattr(self.game, "turn", 0) or 0)
        except (TypeError, ValueError):
            battle_round = 0
        if battle_round < 2:
            return
        stratagem = self.get_by_name("SCREAMING DESCENT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._dread_talons_targetable_units(require_jump_pack_reserves=True)
        if not candidates:
            return
        if self._cabal_reaction_already_queued(
            event_name="reinforcements_step_start",
            stratagem_name=stratagem.name,
            phase_name="Movement phase",
        ):
            return
        payload = {
            "event": "reinforcements_step_start",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "current_player_id": str(getattr(current_player, "id", "") or ""),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_nightmare_hunt_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_nightmare_hunt_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()

        def queue_phase_start_stratagem(stratagem_name: str, *, phase_name: str, candidates: list[Any]) -> None:
            if not candidates:
                return
            stratagem = self.get_by_name(stratagem_name)
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
                return
            if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                return
            if self._cabal_reaction_already_queued(
                event_name="phase_start",
                stratagem_name=stratagem.name,
                phase_name=phase_name,
            ):
                return
            payload = {
                "event": "phase_start",
                "phase": phase_name,
                "phase_name": phase_name,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": list(candidates),
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)

        if phase_key == "SHOOTING_PHASE":
            if player is not self.player:
                return
            candidates = self._nightmare_hunt_targetable_units(require_infantry=True, require_not_shot=True)
            queue_phase_start_stratagem(
                "PREY ON THE WEAK",
                phase_name="Shooting phase",
                candidates=candidates,
            )
            queue_phase_start_stratagem(
                "TALONS SUNK DEEP",
                phase_name="Shooting phase",
                candidates=candidates,
            )
            return

        if phase_key == "FIGHT_PHASE":
            candidates = self._nightmare_hunt_targetable_units(require_infantry=True, require_not_fought=True)
            queue_phase_start_stratagem(
                "PREY ON THE WEAK",
                phase_name="Fight phase",
                candidates=candidates,
            )
            queue_phase_start_stratagem(
                "TALONS SUNK DEEP",
                phase_name="Fight phase",
                candidates=candidates,
            )
            return

        if phase_key != "CHARGE_PHASE" or player is not self.player:
            return
        stratagem = self.get_by_name("MALICIOUS SURGE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._nightmare_hunt_targetable_units(require_infantry=True)
        if not candidates:
            return
        if self._cabal_reaction_already_queued(
            event_name="phase_start",
            stratagem_name=stratagem.name,
            phase_name="Charge phase",
        ):
            return
        payload = {
            "event": "phase_start",
            "phase": "Charge phase",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_nightmare_hunt_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_nightmare_hunt_detachment():
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        action_key = str(action or "").strip().lower().replace(" ", "_")
        if phase_name != "movement phase" or action_key not in {"fall_back", "fallback"}:
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return
        moving_root = self._csm_root(unit)
        if moving_root is None or not self._csm_owned_by_player(moving_root, self.player):
            return
        stratagem = self.get_by_name("RELENTLESS TERROR")
        if stratagem is None:
            return
        if str(getattr(stratagem, "id", "") or "") != "000010642006":
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem, target_unit=moving_root):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._nightmare_hunt_targetable_units(require_infantry=True, require_fell_back=True)
        if moving_root not in candidates:
            return
        if self._cabal_reaction_already_queued(
            event_name="unit_move_ended",
            stratagem_name=stratagem.name,
            phase_name="Movement phase",
            target_unit=moving_root,
        ):
            return
        self._queue_reaction(
            {
                "event": "unit_move_ended",
                "phase_name": "Movement phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": moving_root,
                "target_unit": moving_root,
                "action": str(action or ""),
                "candidates": [moving_root],
            },
            use_timer=False,
        )

    def _queue_nightmare_hunt_unit_set_up_reactions(
        self,
        *,
        unit: Any,
        set_up_as_reinforcements: bool = False,
        **_kwargs: Any,
    ) -> None:
        if not self._is_nightmare_hunt_detachment():
            return
        if unit is None or not bool(set_up_as_reinforcements):
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return
        root = self._csm_root(unit)
        if root is None:
            return
        if not self._csm_owned_by_player(root, self.player):
            return
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return
        if self._unit_cannot_be_target_of_stratagem(root):
            return
        if not self._is_heretic_astartes_unit(root):
            return
        if not bool(getattr(root, "arrived_from_reserves_this_turn", False)):
            return
        enemy_candidates = self._nightmare_hunt_enemy_units_in_range_visible(
            root,
            radius=12.0,
            exclude_monster_vehicle=True,
        )
        if not enemy_candidates:
            return
        stratagem = self.get_by_name("HORRIFIC INCURSION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem, target_unit=root):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._cabal_reaction_already_queued(
            event_name="unit_set_up",
            stratagem_name=stratagem.name,
            phase_name="Movement phase",
            target_unit=root,
        ):
            return
        payload = {
            "event": "unit_set_up",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "set_up_as_reinforcements": True,
            "candidates": [root],
            "enemy_candidates": enemy_candidates,
        }
        if len(enemy_candidates) == 1:
            payload["enemy_unit"] = enemy_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_nightmare_hunt_unit_destroyed_reactions(self, *, destroyed_unit: Any, destroyed_by_unit: Any) -> None:
        if not self._is_nightmare_hunt_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        source_root = self._csm_root(destroyed_by_unit)
        destroyed_root = self._csm_root(destroyed_unit)
        if source_root is None or destroyed_root is None:
            return
        if not self._csm_owned_by_player(source_root, self.player):
            return
        if self._csm_owned_by_player(destroyed_root, self.player):
            return
        if not self._csm_is_alive(source_root) or not self._csm_is_on_battlefield(source_root):
            return
        if self._unit_cannot_be_target_of_stratagem(source_root):
            return
        if not self._is_heretic_astartes_unit(source_root):
            return
        visible_enemies = self._nightmare_hunt_enemy_units_in_range_visible(
            source_root,
            radius=6.0,
            exclude_monster_vehicle=True,
        )
        if not visible_enemies:
            return
        stratagem = self.get_by_name("SADISTIC DISPLAY")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem, target_unit=source_root):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._cabal_reaction_already_queued(
            event_name="unit_destroyed",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
            target_unit=source_root,
        ):
            return
        self._queue_reaction(
            {
                "event": "unit_destroyed",
                "phase_name": "Fight phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": source_root,
                "target_unit": source_root,
                "destroyed_unit": destroyed_root,
                "enemy_units": visible_enemies,
                "candidates": [source_root],
            },
            use_timer=False,
        )

    def _queue_soulforged_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_soulforged_warpack_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()

        def queue_phase_start_stratagem(stratagem_name: str, *, phase_name: str, candidates: list[Any]) -> None:
            if not candidates:
                return
            stratagem = self.get_by_name(stratagem_name)
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
                return
            if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                return
            if self._cabal_reaction_already_queued(
                event_name="phase_start",
                stratagem_name=stratagem.name,
                phase_name=phase_name,
            ):
                return
            payload = {
                "event": "phase_start",
                "phase": phase_name,
                "phase_name": phase_name,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": list(candidates),
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)

        if phase_key == "COMMAND_PHASE":
            if player is not self.player:
                return
            queue_phase_start_stratagem(
                "DAEMONIC POSSESION",
                phase_name="Command phase",
                candidates=self._soulforged_targetable_units(
                    require_vehicle=True,
                    exclude_daemon=True,
                ),
            )
            return

        if phase_key == "MOVEMENT_PHASE":
            if player is not self.player:
                return
            queue_phase_start_stratagem(
                "UNSTOPPABLE RAMPAGE",
                phase_name="Movement phase",
                candidates=self._soulforged_targetable_units(
                    require_vehicle=True,
                    allow_vashtorr=True,
                    require_not_moved=True,
                ),
            )
            return

        if phase_key == "SHOOTING_PHASE":
            if player is not self.player:
                return
            queue_phase_start_stratagem(
                "DESPERATE PLEDGE",
                phase_name="Shooting phase",
                candidates=self._soulforged_targetable_units(
                    require_daemon_vehicle=True,
                    require_not_shot=True,
                ),
            )
            return

        if phase_key == "CHARGE_PHASE":
            if player is not self.player:
                return
            queue_phase_start_stratagem(
                "UNSTOPPABLE RAMPAGE",
                phase_name="Charge phase",
                candidates=self._soulforged_targetable_units(
                    require_vehicle=True,
                    allow_vashtorr=True,
                    require_not_attempted_charge=True,
                ),
            )
            return

        if phase_key != "FIGHT_PHASE":
            return
        queue_phase_start_stratagem(
            "DESPERATE PLEDGE",
            phase_name="Fight phase",
            candidates=self._soulforged_targetable_units(
                require_daemon_vehicle=True,
                require_not_fought=True,
            ),
        )
        queue_phase_start_stratagem(
            "GLUT OF SOULS",
            phase_name="Fight phase",
            candidates=self._soulforged_targetable_units(
                require_daemon_vehicle=True,
                exclude_titanic=True,
                require_not_fought=True,
            ),
        )

    def _queue_soulforged_move_start_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_soulforged_warpack_detachment():
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        action_key = str(action or "").strip().lower().replace(" ", "_")
        if phase_name != "movement phase" or action_key not in {"fall_back", "fallback"}:
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return
        moving_root = self._csm_root(unit)
        if moving_root is None or self._csm_owned_by_player(moving_root, self.player):
            return
        if not self._csm_is_alive(moving_root) or not self._csm_is_on_battlefield(moving_root):
            return
        if self._csm_has_keyword(moving_root, "MONSTER") or self._csm_has_keyword(moving_root, "VEHICLE"):
            return

        stratagem = self.get_by_name("FEEDING FRENZY")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._soulforged_feeding_frenzy_candidates(enemy_unit=moving_root)
        if not candidates:
            return
        moving_id = str(get_entity_id(moving_root) or "")
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_move_started":
                continue
            if self._normalize_stratagem_name(reaction.get("stratagem", "") or "") != self._normalize_stratagem_name("FEEDING FRENZY"):
                continue
            if str(get_entity_id(self._csm_root(reaction.get("moving_unit") or reaction.get("enemy_unit"))) or "") == moving_id:
                return
        payload = {
            "event": "unit_move_started",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "moving_unit": moving_root,
            "enemy_unit": moving_root,
            "action": str(action or ""),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_soulforged_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_soulforged_warpack_detachment():
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        action_key = str(action or "").strip().lower().replace(" ", "_")
        if phase_name != "movement phase" or action_key not in {"move", "normal", "normal_move", "advance", "fall_back", "fallback"}:
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return
        moving_root = self._csm_root(unit)
        if moving_root is None or self._csm_owned_by_player(moving_root, self.player):
            return
        if not self._csm_is_alive(moving_root) or not self._csm_is_on_battlefield(moving_root):
            return

        stratagem = self.get_by_name("PREDATORY PURSUIT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._soulforged_predatory_pursuit_candidates(enemy_unit=moving_root)
        if not candidates:
            return
        moving_id = str(get_entity_id(moving_root) or "")
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_move_ended":
                continue
            if self._normalize_stratagem_name(reaction.get("stratagem", "") or "") != self._normalize_stratagem_name("PREDATORY PURSUIT"):
                continue
            if str(get_entity_id(self._csm_root(reaction.get("moving_unit") or reaction.get("enemy_unit"))) or "") == moving_id:
                return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "moving_unit": moving_root,
            "enemy_unit": moving_root,
            "action": str(action or ""),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _resolve_soulforged_glut_of_souls_fight_attacks_resolved(
        self,
        *,
        unit: Any,
        killing_models_by_target: Any,
    ) -> None:
        if not self._is_soulforged_warpack_detachment():
            return
        root = self._csm_root(unit)
        if root is None or not self._csm_owned_by_player(root, self.player):
            return
        mgr = self._get_chaos_space_marines_mgr()
        resolve_fn = getattr(mgr, "resolve_soulforged_warpack_glut_of_souls", None) if mgr is not None else None
        if not callable(resolve_fn):
            return
        outcome = resolve_fn(root, killing_models_by_target=killing_models_by_target, game=self.game) or {}
        if not bool(outcome.get("triggered", False)):
            return
        healed = int(outcome.get("healed", 0) or 0)
        if healed <= 0:
            return
        logger.info(
            "INFO: GLUT OF SOULS: %s regains %d lost wound%s after destroying enemy models.",
            getattr(root, "name", "Unit"),
            int(healed),
            "" if int(healed) == 1 else "s",
        )

    def _queue_pactbound_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_pactbound_zealots_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()

        def queue_phase_start_stratagem(stratagem_name: str, *, phase_name: str, candidates: list[Any]) -> None:
            if not candidates:
                return
            stratagem = self.get_by_name(stratagem_name)
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
                return
            if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                return
            if self._cabal_reaction_already_queued(
                event_name="phase_start",
                stratagem_name=stratagem.name,
                phase_name=phase_name,
            ):
                return
            payload = {
                "event": "phase_start",
                "phase": phase_name,
                "phase_name": phase_name,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": list(candidates),
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)

        if phase_key == "COMMAND_PHASE":
            if player is not self.player:
                return
            queue_phase_start_stratagem(
                "SKINSHIFT",
                phase_name="Command phase",
                candidates=self._pactbound_skinshift_candidates(),
            )
            return

        if phase_key == "MOVEMENT_PHASE":
            if player is not self.player:
                return
            queue_phase_start_stratagem(
                "TORPEFYING REFRAIN",
                phase_name="Movement phase",
                candidates=self._pactbound_targetable_units(),
            )
            return

        if phase_key == "SHOOTING_PHASE":
            if player is not self.player:
                return
            queue_phase_start_stratagem(
                "PROFANE ZEAL",
                phase_name="Shooting phase",
                candidates=self._pactbound_targetable_units(
                    required_mark="CHAOS UNDIVIDED",
                    require_not_shot=True,
                ),
            )
            return

        if phase_key != "FIGHT_PHASE":
            return
        queue_phase_start_stratagem(
            "PROFANE ZEAL",
            phase_name="Fight phase",
            candidates=self._pactbound_targetable_units(
                required_mark="CHAOS UNDIVIDED",
                require_not_fought=True,
            ),
        )

    def _queue_pactbound_shooting_target_reactions(self, *, attacking_unit: Any, target_units: list[Any]) -> None:
        if not self._is_pactbound_zealots_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        attacker_root = self._csm_root(attacking_unit)
        if attacker_root is None or self._csm_owned_by_player(attacker_root, self.player):
            return
        stratagem = self.get_by_name("FESTERING MIASMA")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._pactbound_targeted_units(target_units=list(target_units or []))
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "shooting_targets_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "FESTERING MIASMA":
                continue
            if self._csm_root(reaction.get("attacking_unit")) is attacker_root:
                return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_pactbound_fight_target_reactions(self, *, attacking_unit: Any, target_units: list[Any]) -> None:
        if not self._is_pactbound_zealots_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        attacker_root = self._csm_root(attacking_unit)
        if attacker_root is None or self._csm_owned_by_player(attacker_root, self.player):
            return
        stratagem = self.get_by_name("ETERNAL HATE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._pactbound_targeted_units(target_units=list(target_units or []))
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "fight_targets_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "ETERNAL HATE":
                continue
            if self._csm_root(reaction.get("attacking_unit")) is attacker_root:
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_pactbound_unit_destroyed_reactions(self, *, destroyed_unit: Any, destroyed_by_unit: Any) -> None:
        if not self._is_pactbound_zealots_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        source_root = self._csm_root(destroyed_by_unit)
        destroyed_root = self._csm_root(destroyed_unit)
        if source_root is None or destroyed_root is None:
            return
        if not self._csm_owned_by_player(source_root, self.player):
            return
        if self._csm_owned_by_player(destroyed_root, self.player):
            return
        if not self._csm_is_alive(source_root) or not self._csm_is_on_battlefield(source_root):
            return
        if self._unit_cannot_be_target_of_stratagem(source_root):
            return
        if not self._is_heretic_astartes_unit(source_root):
            return
        character_models = self._pactbound_eye_of_the_gods_character_models(source_root)
        if not character_models:
            return
        stratagem = self.get_by_name("EYE OF THE GODS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem, target_unit=source_root):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._cabal_reaction_already_queued(
            event_name="unit_destroyed",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
            target_unit=source_root,
        ):
            return
        payload = {
            "event": "unit_destroyed",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": source_root,
            "target_unit": source_root,
            "destroyed_unit": destroyed_root,
            "character_models": character_models,
            "candidates": [source_root],
        }
        if len(character_models) == 1:
            payload["model"] = character_models[0]
            payload["target_model"] = character_models[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_renegade_warband_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_renegade_warband_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "MOVEMENT_PHASE" or player is not self.player:
            return

        stratagem = self.get_by_name("RENEGADE CLAIM")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._cabal_reaction_already_queued(
            event_name="phase_start",
            stratagem_name=stratagem.name,
            phase_name="Movement phase",
        ):
            return

        candidates: list[Any] = []
        objective_map: dict[str, list[Any]] = {}
        for root in list(self._renegade_warband_targetable_units() or []):
            objectives = self._renegade_warband_controlled_objective_candidates(root)
            if not objectives:
                continue
            candidates.append(root)
            objective_map[self._csm_sort_key(root)] = list(objectives)
        if not candidates:
            return

        payload: dict[str, Any] = {
            "event": "phase_start",
            "phase": "Movement phase",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": list(candidates),
            "objective_candidates_by_unit": objective_map,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
            objective_candidates = list(objective_map.get(self._csm_sort_key(candidates[0])) or [])
            if objective_candidates:
                payload["objective_candidates"] = objective_candidates
                if len(objective_candidates) == 1:
                    payload["objective"] = objective_candidates[0]
                    payload["objective_marker"] = objective_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_renegade_warband_shooting_target_reactions(self, *, attacking_unit: Any, target_units: list[Any]) -> None:
        if not self._is_renegade_warband_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return
        attacker_root = self._csm_root(attacking_unit)
        if attacker_root is None or not self._csm_owned_by_player(attacker_root, self.player):
            return
        if not self._csm_is_alive(attacker_root) or not self._csm_is_on_battlefield(attacker_root):
            return
        if self._unit_cannot_be_target_of_stratagem(attacker_root):
            return
        if not self._is_heretic_astartes_unit(attacker_root):
            return

        def queue_selected_stratagem(stratagem_name: str) -> None:
            stratagem = self.get_by_name(stratagem_name)
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
                return
            if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                return
            for reaction in list(getattr(self, "_pending_reactions", []) or []):
                if str(reaction.get("event", "") or "") != "shooting_targets_selected":
                    continue
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem.name or "").strip().upper():
                    continue
                if self._csm_root(reaction.get("attacking_unit")) is attacker_root:
                    return
            self._queue_reaction(
                {
                    "event": "shooting_targets_selected",
                    "phase_name": "Shooting phase",
                    "stratagem": stratagem.name,
                    "cp_cost": stratagem.cp_cost,
                    "attacking_unit": attacker_root,
                    "unit": attacker_root,
                    "target_unit": attacker_root,
                    "target_units": list(target_units or []),
                    "candidates": [attacker_root],
                },
                use_timer=False,
            )

        queue_selected_stratagem("CORRUPTED MUNITIONS")
        queue_selected_stratagem("NEVER OUTGUNNED")
        if (
            (self._is_heretic_astartes_infantry(attacker_root) or self._is_heretic_astartes_mounted(attacker_root))
            and not self._is_damned_unit(attacker_root)
            and self._renegade_warband_selected_targets_include_vendetta(target_units=list(target_units or []))
        ):
            queue_selected_stratagem("VENGEFUL DESTRUCTION")

    def _queue_renegade_warband_shooting_resolved_reactions(
        self,
        *,
        attacker_unit: Any,
        hits_by_target: Optional[dict[Any, Any]] = None,
    ) -> None:
        if not self._is_renegade_warband_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return
        attacker_root = self._csm_root(attacker_unit)
        if attacker_root is None or self._csm_owned_by_player(attacker_root, self.player):
            return

        stratagem = self.get_by_name("REAVERS' REACTION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_shooting_resolved":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "REAVERS' REACTION":
                continue
            if self._csm_root(reaction.get("attacking_unit")) is attacker_root:
                return

        candidates: list[Any] = []
        seen: set[str] = set()
        if isinstance(hits_by_target, dict):
            for raw_target, hits in list(hits_by_target.items()):
                try:
                    hit_count = int(hits or 0)
                except (TypeError, ValueError):
                    hit_count = 0
                if hit_count <= 0:
                    continue
                root = self._csm_root(raw_target)
                if root is None:
                    continue
                uid = self._csm_sort_key(root)
                if uid and uid in seen:
                    continue
                if uid:
                    seen.add(uid)
                if not self._csm_owned_by_player(root, self.player):
                    continue
                if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                    continue
                if self._unit_cannot_be_target_of_stratagem(root):
                    continue
                if not self._is_heretic_astartes_unit(root):
                    continue
                if self._csm_has_keyword(root, "MONSTER") or self._csm_has_keyword(root, "VEHICLE"):
                    continue
                candidates.append(root)
        candidates = sorted(candidates, key=self._csm_sort_key)
        if not candidates:
            return

        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "enemy_unit": attacker_root,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_renegade_warband_fight_target_reactions(self, *, attacking_unit: Any, target_units: list[Any]) -> None:
        if not self._is_renegade_warband_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        attacker_root = self._csm_root(attacking_unit)
        if attacker_root is None:
            return

        if self._csm_owned_by_player(attacker_root, self.player):
            if not self._csm_is_alive(attacker_root) or not self._csm_is_on_battlefield(attacker_root):
                return
            if self._unit_cannot_be_target_of_stratagem(attacker_root):
                return
            if not self._is_heretic_astartes_unit(attacker_root):
                return

            def queue_selected_stratagem(stratagem_name: str) -> None:
                stratagem = self.get_by_name(stratagem_name)
                if stratagem is None:
                    return
                if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
                    return
                if str(stratagem.name or "").strip().upper() in set(
                    getattr(self, "_used_stratagems_this_phase", set()) or set()
                ):
                    return
                for reaction in list(getattr(self, "_pending_reactions", []) or []):
                    if str(reaction.get("event", "") or "") != "fight_targets_selected":
                        continue
                    if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem.name or "").strip().upper():
                        continue
                    if self._csm_root(reaction.get("attacking_unit")) is attacker_root:
                        return
                self._queue_reaction(
                    {
                        "event": "fight_targets_selected",
                        "phase_name": "Fight phase",
                        "stratagem": stratagem.name,
                        "cp_cost": stratagem.cp_cost,
                        "attacking_unit": attacker_root,
                        "unit": attacker_root,
                        "target_unit": attacker_root,
                        "target_units": list(target_units or []),
                        "candidates": [attacker_root],
                    },
                    use_timer=False,
                )

            queue_selected_stratagem("NEVER OUTGUNNED")
            if (
                (self._is_heretic_astartes_infantry(attacker_root) or self._is_heretic_astartes_mounted(attacker_root))
                and not self._is_damned_unit(attacker_root)
                and self._renegade_warband_selected_targets_include_vendetta(target_units=list(target_units or []))
            ):
                queue_selected_stratagem("VENGEFUL DESTRUCTION")
            return

        stratagem = self.get_by_name("UNDYING HATRED")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        candidates: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._csm_root(target)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_heretic_astartes_unit(root):
                continue
            candidates.append(root)
        candidates = sorted(candidates, key=self._csm_sort_key)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "fight_targets_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "UNDYING HATRED":
                continue
            if self._csm_root(reaction.get("attacking_unit")) is attacker_root:
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_renegade_raiders_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_renegade_raiders_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()

        def queue_phase_start_stratagem(stratagem_name: str, *, phase_name: str, candidates: list[Any]) -> None:
            if not candidates:
                return
            stratagem = self.get_by_name(stratagem_name)
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
                return
            if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                return
            if self._cabal_reaction_already_queued(
                event_name="phase_start",
                stratagem_name=stratagem.name,
                phase_name=phase_name,
            ):
                return
            payload = {
                "event": "phase_start",
                "phase": phase_name,
                "phase_name": phase_name,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": list(candidates),
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)

        if phase_key == "MOVEMENT_PHASE":
            if player is not self.player:
                return
            queue_phase_start_stratagem(
                "WARPCHARGED ENGINES",
                phase_name="Movement phase",
                candidates=self._renegade_raiders_targetable_units(
                    require_transport_or_mounted=True,
                    require_not_moved=True,
                ),
            )
            return

        if phase_key == "CHARGE_PHASE":
            if player is not self.player:
                return
            queue_phase_start_stratagem(
                "REAVERS' HASTE",
                phase_name="Charge phase",
                candidates=self._renegade_raiders_targetable_units(
                    require_infantry_or_mounted=True,
                    require_not_attempted_charge=True,
                ),
            )
            return

        if phase_key == "SHOOTING_PHASE":
            if player is not self.player:
                return
            queue_phase_start_stratagem(
                "RUINOUS RAID",
                phase_name="Shooting phase",
                candidates=self._renegade_raiders_targetable_units(
                    require_disembarked_this_round=True,
                    require_not_shot=True,
                ),
            )
            return

        if phase_key != "FIGHT_PHASE":
            return
        if player is self.player:
            queue_phase_start_stratagem(
                "RUINOUS RAID",
                phase_name="Fight phase",
                candidates=self._renegade_raiders_targetable_units(
                    require_disembarked_this_round=True,
                    require_not_fought=True,
                ),
            )
        queue_phase_start_stratagem(
            "SCOUR AND SEIZE",
            phase_name="Fight phase",
            candidates=self._renegade_raiders_targetable_units(require_not_fought=True),
        )

    def _queue_renegade_raiders_shooting_target_reactions(self, *, attacking_unit: Any, target_units: list[Any]) -> None:
        if not self._is_renegade_raiders_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        attacker_root = self._csm_root(attacking_unit)
        if attacker_root is None or self._csm_owned_by_player(attacker_root, self.player):
            return
        stratagem = self.get_by_name("UNFAILINGLY OBDURATE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._renegade_raiders_targeted_units(
            target_units=list(target_units or []),
            exclude_damned=True,
        )
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "shooting_targets_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "UNFAILINGLY OBDURATE":
                continue
            if self._csm_root(reaction.get("attacking_unit")) is attacker_root:
                return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_renegade_raiders_fight_target_reactions(self, *, attacking_unit: Any, target_units: list[Any]) -> None:
        if not self._is_renegade_raiders_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        attacker_root = self._csm_root(attacking_unit)
        if attacker_root is None or self._csm_owned_by_player(attacker_root, self.player):
            return
        stratagem = self.get_by_name("UNFAILINGLY OBDURATE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._renegade_raiders_targeted_units(
            target_units=list(target_units or []),
            exclude_damned=True,
        )
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "fight_targets_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "UNFAILINGLY OBDURATE":
                continue
            if self._csm_root(reaction.get("attacking_unit")) is attacker_root:
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_renegade_raiders_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        _ = player
        if not self._is_renegade_raiders_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return
        stratagem = self.get_by_name("OPPORTUNISTIC RAIDERS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._renegade_raiders_targetable_units(require_eligible_to_fight=True)
        if not candidates:
            return
        if self._cabal_reaction_already_queued(
            event_name="phase_end",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
        ):
            return
        payload = {
            "event": "phase_end",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_veterans_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_veterans_of_the_long_war_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()

        def queue_phase_start_stratagem(stratagem_name: str, *, phase_name: str, candidates: list[Any]) -> None:
            if not candidates:
                return
            stratagem = self.get_by_name(stratagem_name)
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
                return
            if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                return
            if self._cabal_reaction_already_queued(
                event_name="phase_start",
                stratagem_name=stratagem.name,
                phase_name=phase_name,
            ):
                return
            payload = {
                "event": "phase_start",
                "phase": phase_name,
                "phase_name": phase_name,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": list(candidates),
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)

        if phase_key == "MOVEMENT_PHASE":
            if player is not self.player:
                return
            queue_phase_start_stratagem(
                "BLACK CRUSADE",
                phase_name="Movement phase",
                candidates=self._veterans_targetable_units(
                    require_infantry_or_mounted=True,
                    exclude_damned=True,
                ),
            )
            return

        if phase_key == "SHOOTING_PHASE":
            if player is not self.player:
                return
            queue_phase_start_stratagem(
                "LET THE GALAXY BURN",
                phase_name="Shooting phase",
                candidates=self._veterans_targetable_units(
                    exclude_tzeentch=True,
                    require_not_shot=True,
                ),
            )
            return

        if phase_key != "FIGHT_PHASE":
            return
        queue_phase_start_stratagem(
            "BRINGERS OF DESPAIR",
            phase_name="Fight phase",
            candidates=self._veterans_bringers_of_despair_candidates(),
        )

    def _queue_veterans_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_veterans_of_the_long_war_detachment():
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        action_key = str(action or "").strip().lower().replace(" ", "_")
        if phase_name != "movement phase" or action_key not in {"move", "normal", "normal_move", "advance", "fall_back", "fallback"}:
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return
        moving_root = self._csm_root(unit)
        if moving_root is None or self._csm_owned_by_player(moving_root, self.player):
            return
        if not self._csm_is_alive(moving_root) or not self._csm_is_on_battlefield(moving_root):
            return

        stratagem = self.get_by_name("MILLENNIA OF EXPERIENCE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._veterans_millennia_of_experience_candidates(enemy_unit=moving_root)
        if not candidates:
            return
        moving_id = str(get_entity_id(moving_root) or "")
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_move_ended":
                continue
            if self._normalize_stratagem_name(reaction.get("stratagem", "") or "") != self._normalize_stratagem_name("MILLENNIA OF EXPERIENCE"):
                continue
            if str(get_entity_id(self._csm_root(reaction.get("moving_unit") or reaction.get("enemy_unit"))) or "") == moving_id:
                return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "moving_unit": moving_root,
            "enemy_unit": moving_root,
            "action": str(action or ""),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_veterans_unit_destroyed_reactions(self, *, destroyed_unit: Any, destroyed_by_unit: Any) -> None:
        if not self._is_veterans_of_the_long_war_detachment():
            return
        mgr = self._get_chaos_space_marines_mgr()
        focus_target_id = str(getattr(mgr, "veterans_focus_of_hatred_target_unit_id", "") or "").strip()
        if not focus_target_id:
            return
        destroyed_root = self._csm_root(destroyed_unit)
        if destroyed_root is None:
            return
        if str(get_entity_id(destroyed_root) or "").strip() != focus_target_id:
            return
        if self._csm_owned_by_player(destroyed_root, self.player):
            return

        stratagem = self.get_by_name("ENDLESS IRE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        candidates: list[Any] = []
        enemy_candidates_by_unit: dict[str, list[Any]] = {}
        for root in self._veterans_targetable_units(require_character=True, exclude_damned=True):
            root_id = str(get_entity_id(root) or "")
            if not root_id:
                continue
            enemy_candidates = list(
                getattr(mgr, "veterans_endless_ire_candidate_enemy_units", lambda *_a, **_k: [])(
                    root_id,
                    game=self.game,
                    player=self.player,
                )
                or []
            )
            if not enemy_candidates:
                continue
            candidates.append(root)
            enemy_candidates_by_unit[root_id] = list(enemy_candidates)
        if not candidates:
            return

        destroyed_id = str(get_entity_id(destroyed_root) or "")
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_destroyed":
                continue
            if self._normalize_stratagem_name(reaction.get("stratagem", "") or "") != self._normalize_stratagem_name("ENDLESS IRE"):
                continue
            if str(get_entity_id(self._csm_root(reaction.get("destroyed_unit"))) or "") == destroyed_id:
                return
        payload = {
            "event": "unit_destroyed",
            "phase_name": str(getattr(self, "_current_phase_name", "") or "").strip() or "Any phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "destroyed_unit": destroyed_root,
            "destroyed_by_unit": self._csm_root(destroyed_by_unit),
            "candidates": sorted(candidates, key=self._csm_sort_key),
            "enemy_candidates_by_unit": dict(enemy_candidates_by_unit),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_veterans_shooting_target_reactions(self, *, attacking_unit: Any, target_units: list[Any]) -> None:
        if not self._is_veterans_of_the_long_war_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        attacker_root = self._csm_root(attacking_unit)
        if attacker_root is None or self._csm_owned_by_player(attacker_root, self.player):
            return
        stratagem = self.get_by_name("CONTEMPTUOUS DISREGARD")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._veterans_targeted_units(
            target_units=list(target_units or []),
            exclude_damned=True,
        )
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "shooting_targets_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "CONTEMPTUOUS DISREGARD":
                continue
            if self._csm_root(reaction.get("attacking_unit")) is attacker_root:
                return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_veterans_fight_target_reactions(self, *, attacking_unit: Any, target_units: list[Any]) -> None:
        if not self._is_veterans_of_the_long_war_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        attacker_root = self._csm_root(attacking_unit)
        if attacker_root is None or self._csm_owned_by_player(attacker_root, self.player):
            return
        stratagem = self.get_by_name("CONTEMPTUOUS DISREGARD")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._veterans_targeted_units(
            target_units=list(target_units or []),
            exclude_damned=True,
        )
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "fight_targets_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "CONTEMPTUOUS DISREGARD":
                continue
            if self._csm_root(reaction.get("attacking_unit")) is attacker_root:
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_fellhammer_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_fellhammer_siege_host_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()

        if phase_key == "SHOOTING_PHASE":
            if player is not self.player:
                return

            stratagem = self.get_by_name("PITILESS CANNONADE")
            if stratagem is not None:
                if int(getattr(self.player, "command_points", 0) or 0) >= self._cabal_effective_cp_cost(stratagem):
                    if str(stratagem.name or "").strip().upper() not in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                        candidates = self._fellhammer_targetable_units(require_not_shot=True)
                        if candidates and not self._cabal_reaction_already_queued(
                            event_name="phase_start",
                            stratagem_name=stratagem.name,
                            phase_name="Shooting phase",
                        ):
                            payload = {
                                "event": "phase_start",
                                "phase": "Shooting phase",
                                "phase_name": "Shooting phase",
                                "stratagem": stratagem.name,
                                "cp_cost": stratagem.cp_cost,
                                "candidates": candidates,
                            }
                            if len(candidates) == 1:
                                payload["unit"] = candidates[0]
                                payload["target_unit"] = candidates[0]
                            self._queue_reaction(payload, use_timer=False)

            stratagem = self.get_by_name("POINT-BLANK DESTRUCTION")
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
                return
            if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                return
            candidates = self._fellhammer_targetable_units(require_not_shot=True, require_engaged=True)
            if not candidates:
                return
            if self._cabal_reaction_already_queued(
                event_name="phase_start",
                stratagem_name=stratagem.name,
                phase_name="Shooting phase",
            ):
                return
            payload = {
                "event": "phase_start",
                "phase": "Shooting phase",
                "phase_name": "Shooting phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)
            return

        if phase_key != "CHARGE_PHASE" or player is self.player:
            return
        stratagem = self.get_by_name("SIEGECRAFT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._fellhammer_targetable_units()
        if not candidates:
            return
        if self._cabal_reaction_already_queued(
            event_name="phase_start",
            stratagem_name=stratagem.name,
            phase_name="Charge phase",
        ):
            return
        payload = {
            "event": "phase_start",
            "phase": "Charge phase",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_hurons_marauders_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_hurons_marauders_detachment():
            return
        if player is not self.player:
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()

        if phase_key == "COMMAND_PHASE":
            stratagem = self.get_by_name("HARDENED KILLERS")
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
                return
            if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                return
            candidates = self._hurons_marauders_targetable_units(require_damned=True)
            if not candidates:
                return
            if self._cabal_reaction_already_queued(
                event_name="phase_start",
                stratagem_name=stratagem.name,
                phase_name="Command phase",
            ):
                return
            payload = {
                "event": "phase_start",
                "phase": "Command phase",
                "phase_name": "Command phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)
            return

        if phase_key == "MOVEMENT_PHASE":
            stratagem = self.get_by_name("AT THE TYRANT'S COMMAND")
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
                return
            if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                return
            candidates = self._hurons_marauders_targetable_units(require_non_monster_non_vehicle=True)
            if not candidates:
                return
            if self._cabal_reaction_already_queued(
                event_name="phase_start",
                stratagem_name=stratagem.name,
                phase_name="Movement phase",
            ):
                return
            payload = {
                "event": "phase_start",
                "phase": "Movement phase",
                "phase_name": "Movement phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)
            return

        if phase_key != "FIGHT_PHASE":
            return
        stratagem = self.get_by_name("REAVERS' FLURRY")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._hurons_marauders_targetable_units(require_not_fought=True, require_charged=True)
        if not candidates:
            return
        if self._cabal_reaction_already_queued(
            event_name="phase_start",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
        ):
            return
        payload = {
            "event": "phase_start",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_fellhammer_shooting_target_reactions(self, *, attacking_unit: Any, target_units: list[Any]) -> None:
        if not self._is_fellhammer_siege_host_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        attacker_root = self._csm_root(attacking_unit)
        if attacker_root is None or self._csm_owned_by_player(attacker_root, self.player):
            return
        stratagem = self.get_by_name("STEADFAST DETERMINATION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._fellhammer_targeted_units(
            target_units=list(target_units or []),
            exclude_damned=True,
        )
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "shooting_targets_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "STEADFAST DETERMINATION":
                continue
            if self._csm_root(reaction.get("attacking_unit")) is attacker_root:
                return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_fellhammer_fight_target_reactions(self, *, attacking_unit: Any, target_units: list[Any]) -> None:
        if not self._is_fellhammer_siege_host_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        attacker_root = self._csm_root(attacking_unit)
        if attacker_root is None or self._csm_owned_by_player(attacker_root, self.player):
            return

        stratagem = self.get_by_name("BRUTAL ATTRITION")
        if stratagem is not None:
            if int(getattr(self.player, "command_points", 0) or 0) >= self._cabal_effective_cp_cost(stratagem):
                if str(stratagem.name or "").strip().upper() not in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                    candidates = self._fellhammer_targeted_units(
                        target_units=list(target_units or []),
                        require_infantry=True,
                        exclude_damned=True,
                    )
                    if candidates:
                        queued = False
                        for reaction in list(getattr(self, "_pending_reactions", []) or []):
                            if str(reaction.get("event", "") or "") != "fight_targets_selected":
                                continue
                            if str(reaction.get("stratagem", "") or "").strip().upper() != "BRUTAL ATTRITION":
                                continue
                            if self._csm_root(reaction.get("attacking_unit")) is attacker_root:
                                queued = True
                                break
                        if not queued:
                            payload = {
                                "event": "fight_targets_selected",
                                "phase_name": "Fight phase",
                                "stratagem": stratagem.name,
                                "cp_cost": stratagem.cp_cost,
                                "attacking_unit": attacker_root,
                                "target_units": list(target_units or []),
                                "candidates": candidates,
                            }
                            if len(candidates) == 1:
                                payload["unit"] = candidates[0]
                                payload["target_unit"] = candidates[0]
                            self._queue_reaction(payload, use_timer=False)

        stratagem = self.get_by_name("PERSISTENT ASSAILANTS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._fellhammer_targeted_units(
            target_units=list(target_units or []),
            require_not_fought=True,
        )
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "fight_targets_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "PERSISTENT ASSAILANTS":
                continue
            if self._csm_root(reaction.get("attacking_unit")) is attacker_root:
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_hurons_marauders_move_started_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_hurons_marauders_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "movement phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return
        action_key = str(action or "").strip().lower().replace(" ", "_")
        if action_key not in {"advance", "advancing", "advance_move"}:
            return
        root = self._csm_root(unit)
        if root is None or not self._csm_owned_by_player(root, self.player):
            return

        stratagem = self.get_by_name("SEIZE THE PRIZE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._hurons_marauders_targetable_units(require_non_monster_non_vehicle=True)
        if not self._hurons_marauders_unit_in_candidates(root, candidates):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_move_started":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "SEIZE THE PRIZE":
                continue
            if self._csm_root(reaction.get("unit") or reaction.get("target_unit")) is root:
                return
        self._queue_reaction(
            {
                "event": "unit_move_started",
                "phase_name": "Movement phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "action": action,
                "unit": root,
                "target_unit": root,
                "candidates": [root],
            },
            use_timer=False,
        )

    def _capture_hurons_marauders_shooting_targets_selected(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        if not self._is_hurons_marauders_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        stratagem = self.get_by_name("TO THE FAVOURED THE SPOILS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        self._record_hurons_marauders_favoured_spoils_snapshot(
            attacking_unit=attacking_unit,
            target_units=list(target_units or []),
        )

    def _queue_hurons_marauders_shooting_resolved_reactions(
        self,
        *,
        attacker_unit: Any,
        hits_by_target: Optional[dict[Any, Any]] = None,
    ) -> None:
        _ = hits_by_target
        if not self._is_hurons_marauders_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return
        attacker_root = self._csm_root(attacker_unit)
        attacker_key = str(self._attacker_unit_key(attacker_root) or "").strip()
        if attacker_root is None or not attacker_key or self._csm_owned_by_player(attacker_root, self.player):
            return

        before_by_unit = dict(self._hurons_marauders_shooting_wounds_before().pop(attacker_key, {}) or {})
        if not before_by_unit:
            return

        stratagem = self.get_by_name("TO THE FAVOURED THE SPOILS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        candidates: list[Any] = []
        seen: set[str] = set()
        for snapshot in list(before_by_unit.values()):
            unit_id = str((snapshot or {}).get("unit_id", "") or "").strip()
            if not unit_id or unit_id in seen:
                continue
            seen.add(unit_id)
            root = self._hurons_marauders_resolve_unit_by_id(unit_id)
            if root is None:
                continue
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_heretic_astartes_unit(root):
                continue
            try:
                wounds_before = int((snapshot or {}).get("wounds_before", 0) or 0)
            except (TypeError, ValueError):
                wounds_before = 0
            wounds_after = int(self._hurons_marauders_total_current_wounds(root) or 0)
            if wounds_after >= wounds_before:
                continue
            candidates.append(root)
        candidates = sorted(candidates, key=self._csm_sort_key)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_shooting_resolved":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "TO THE FAVOURED THE SPOILS":
                continue
            if self._csm_root(reaction.get("attacking_unit")) is attacker_root:
                return
        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "enemy_unit": attacker_root,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_hurons_marauders_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_hurons_marauders_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE" or player is self.player:
            return
        stratagem = self.get_by_name("ENCIRCLING SURGE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._cabal_effective_cp_cost(stratagem):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = [
            root
            for root in self._hurons_marauders_targetable_units(
                require_non_monster_non_vehicle=True,
                require_not_engaged=True,
            )
            if self._unit_wholly_within_battlefield_edge_distance(root, 6.0)
        ]
        if not candidates:
            return
        if self._cabal_reaction_already_queued(
            event_name="phase_end",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
        ):
            return
        payload = {
            "event": "phase_end",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": sorted(candidates, key=self._csm_sort_key),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _cleanup_dread_talons_phase_end_effects(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_name:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        mgr = self._get_chaos_space_marines_mgr()
        if army is None or mgr is None:
            return

        prefix_by_phase = {
            "MOVEMENT_PHASE": (mgr._DREAD_TALONS_SCREAMING_DESCENT_PREFIX,),
            "SHOOTING_PHASE": (mgr._DREAD_TALONS_PITILESS_HUNTERS_PREFIX,),
            "FIGHT_PHASE": (
                mgr._DREAD_TALONS_DEPTHLESS_CRUELTY_PREFIX,
                mgr._DREAD_TALONS_RELENTLESS_TERROR_PREFIX,
            ),
        }
        prefixes = prefix_by_phase.get(phase_name, ())
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            for prefix in prefixes:
                mgr._remove_special_rule_prefix(root, prefix)
            if phase_name != "FIGHT_PHASE":
                continue
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            for key in (
                "dread_talons_screaming_descent_no_charge_turn_owner",
                "dread_talons_screaming_descent_no_charge_turn",
                "dread_talons_screaming_descent_no_charge_source",
            ):
                sr.pop(key, None)
            root.special_rules = sr

    def _cleanup_nightmare_hunt_phase_end_effects(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_name:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        mgr = self._get_chaos_space_marines_mgr()
        if army is None or mgr is None:
            return

        prefix_by_phase = {
            "SHOOTING_PHASE": (
                mgr._NIGHTMARE_HUNT_PREY_ON_THE_WEAK_PREFIX,
                mgr._NIGHTMARE_HUNT_TALONS_SUNK_DEEP_PREFIX,
            ),
            "CHARGE_PHASE": (mgr._NIGHTMARE_HUNT_MALICIOUS_SURGE_PREFIX,),
            "FIGHT_PHASE": (
                mgr._NIGHTMARE_HUNT_PREY_ON_THE_WEAK_PREFIX,
                mgr._NIGHTMARE_HUNT_TALONS_SUNK_DEEP_PREFIX,
                mgr._NIGHTMARE_HUNT_RELENTLESS_TERROR_PREFIX,
            ),
        }
        prefixes = prefix_by_phase.get(phase_name, ())
        if not prefixes:
            return
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            for prefix in prefixes:
                mgr._remove_special_rule_prefix(root, prefix)

    def _cleanup_pactbound_phase_end_effects(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_name:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        mgr = self._get_chaos_space_marines_mgr()
        if army is None or mgr is None:
            return

        prefix_by_phase = {
            "SHOOTING_PHASE": (
                mgr._PACTBOUND_FESTERING_MIASMA_PREFIX,
                mgr._PACTBOUND_PROFANE_ZEAL_PREFIX,
            ),
            "FIGHT_PHASE": (
                mgr._PACTBOUND_ETERNAL_HATE_PREFIX,
                mgr._PACTBOUND_PROFANE_ZEAL_PREFIX,
                mgr._PACTBOUND_TORPEFYING_REFRAIN_PREFIX,
            ),
        }
        prefixes = prefix_by_phase.get(phase_name, ())
        if not prefixes:
            return
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            for prefix in prefixes:
                mgr._remove_special_rule_prefix(root, prefix)

    def _cleanup_renegade_raiders_phase_end_effects(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_name:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        mgr = self._get_chaos_space_marines_mgr()
        if army is None or mgr is None:
            return

        prefix_by_phase = {
            "CHARGE_PHASE": (mgr._RENEGADE_RAIDERS_REAVERS_HASTE_PREFIX,),
            "SHOOTING_PHASE": (mgr._RENEGADE_RAIDERS_RUINOUS_RAID_PREFIX,),
            "FIGHT_PHASE": (
                mgr._RENEGADE_RAIDERS_RUINOUS_RAID_PREFIX,
                mgr._RENEGADE_RAIDERS_SCOUR_AND_SEIZE_PREFIX,
            ),
        }
        prefixes = prefix_by_phase.get(phase_name, ())
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            if phase_name == "MOVEMENT_PHASE":
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                effects = list(sr.get("advance_no_roll_effects", []) or [])
                kept = [
                    entry
                    for entry in effects
                    if not (
                        isinstance(entry, dict)
                        and str(entry.get("tag", "") or "") == "stratagem:renegade_raiders_warpcharged_engines"
                    )
                ]
                if kept:
                    sr["advance_no_roll_effects"] = kept
                else:
                    sr.pop("advance_no_roll_effects", None)
                root.special_rules = sr
                continue
            for prefix in prefixes:
                mgr._remove_special_rule_prefix(root, prefix)

    def _cleanup_veterans_phase_end_effects(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_name:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        mgr = self._get_chaos_space_marines_mgr()
        if army is None or mgr is None:
            return

        prefixes: tuple[str, ...] = ()
        if phase_name == "SHOOTING_PHASE":
            prefixes = (mgr._VETERANS_LET_THE_GALAXY_BURN_PREFIX,)
        elif phase_name == "FIGHT_PHASE":
            current_owner = str(mgr._current_turn_owner_id(game=self.game) or "")
            player_id = str(getattr(self.player, "id", "") or "")
            if not current_owner or current_owner == player_id:
                prefixes = (
                    mgr._VETERANS_BLACK_CRUSADE_PREFIX,
                    mgr._VETERANS_BRINGERS_OF_DESPAIR_PREFIX,
                )
            else:
                prefixes = (mgr._VETERANS_BRINGERS_OF_DESPAIR_PREFIX,)
        if not prefixes:
            return
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            for prefix in prefixes:
                mgr._remove_special_rule_prefix(root, prefix)

    def _cleanup_fellhammer_phase_end_effects(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_name:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        mgr = self._get_chaos_space_marines_mgr()
        if army is None or mgr is None:
            return

        prefix_by_phase = {
            "SHOOTING_PHASE": (
                mgr._FELLHAMMER_PITILESS_CANNONADE_PREFIX,
                mgr._FELLHAMMER_POINT_BLANK_DESTRUCTION_PREFIX,
                mgr._FELLHAMMER_STEADFAST_DETERMINATION_PREFIX,
            ),
            "CHARGE_PHASE": (mgr._FELLHAMMER_SIEGECRAFT_PREFIX,),
            "FIGHT_PHASE": (
                mgr._FELLHAMMER_BRUTAL_ATTRITION_PREFIX,
                mgr._FELLHAMMER_PERSISTENT_ASSAILANTS_PREFIX,
            ),
        }
        prefixes = prefix_by_phase.get(phase_name, ())
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            for prefix in prefixes:
                mgr._remove_special_rule_prefix(root, prefix)
            if phase_name != "SHOOTING_PHASE":
                continue
            get_models = getattr(root, "get_attached_unit_models", None)
            models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
            for model in list(models or []):
                effects = getattr(model, "_temporary_effects", None)
                if not isinstance(effects, dict) or not effects:
                    continue
                for key in [
                    effect_key
                    for effect_key in list(effects.keys())
                    if str(effect_key or "").startswith("fellhammer_point_blank_destruction:")
                ]:
                    effects.pop(key, None)

    def _cleanup_hurons_marauders_phase_end_effects(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_name:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        mgr = self._get_chaos_space_marines_mgr()
        if army is None or mgr is None:
            return

        if phase_name == "SHOOTING_PHASE":
            self._hurons_marauders_favoured_spoils_snapshots = {}

        current_turn_owner = str(mgr._current_turn_owner_id(game=self.game) or "")
        current_turn = int(mgr._current_turn(game=self.game) or 0)
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            root_id = self._csm_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)

            if phase_name == "MOVEMENT_PHASE":
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                effects = list(sr.get("advance_no_roll_effects", []) or [])
                kept = [
                    entry
                    for entry in effects
                    if not (
                        isinstance(entry, dict)
                        and str(entry.get("tag", "") or "") == "stratagem:hurons_marauders_seize_the_prize"
                    )
                ]
                if kept:
                    sr["advance_no_roll_effects"] = kept
                else:
                    sr.pop("advance_no_roll_effects", None)
                root.special_rules = sr
                continue

            if phase_name != "FIGHT_PHASE":
                continue
            mgr._remove_special_rule_prefix(root, mgr._HURONS_MARAUDERS_REAVERS_FLURRY_PREFIX)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            effect_owner = str(sr.get(f"{mgr._HURONS_MARAUDERS_AT_THE_TYRANTS_COMMAND_PREFIX}_turn_owner", "") or "")
            try:
                effect_turn = int(sr.get(f"{mgr._HURONS_MARAUDERS_AT_THE_TYRANTS_COMMAND_PREFIX}_turn", 0) or 0)
            except (TypeError, ValueError):
                effect_turn = 0
            if effect_owner and current_turn_owner and effect_owner == current_turn_owner and effect_turn == current_turn:
                mgr._remove_special_rule_prefix(root, mgr._HURONS_MARAUDERS_AT_THE_TYRANTS_COMMAND_PREFIX)

    def _use_deceptors_coils_of_deception(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        action = kwargs.get("action")
        pending = self._csm_find_pending_reaction("COILS OF DECEPTION", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if action is None:
                action = pending.get("action")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: COILS OF DECEPTION: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_deceptors_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: COILS OF DECEPTION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: COILS OF DECEPTION: not your Movement phase")
            return False
        action_key = str(action or "").strip().lower().replace(" ", "_")
        if action_key not in {"fall_back", "fallback"}:
            logger.error("ERROR: COILS OF DECEPTION: target did not Fall Back")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: COILS OF DECEPTION: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: COILS OF DECEPTION: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: COILS OF DECEPTION: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: COILS OF DECEPTION: target must be HERETIC ASTARTES")
            return False
        if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
            logger.error("ERROR: COILS OF DECEPTION: target has not Fell Back this round")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_deceptors_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: COILS OF DECEPTION: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._DECEPTORS_COILS_OF_DECEPTION_PREFIX,
            source=stratagem.name or "COILS OF DECEPTION",
            player=self.player,
            game=self.game,
            track_phase=False,
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: COILS OF DECEPTION: %s can shoot after Falling Back this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_deceptors_detonator(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        destroyed_model = kwargs.get("destroyed_model")
        destroyed_unit = kwargs.get("destroyed_unit")
        pending = None
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "DETONATOR":
                continue
            pending = reaction
            break
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if destroyed_model is None:
                destroyed_model = pending.get("destroyed_model")
            if destroyed_unit is None:
                destroyed_unit = pending.get("destroyed_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: DETONATOR: no target unit provided")
            return False

        root = self._csm_root(unit)
        destroyed_root = self._csm_root(destroyed_unit)
        if root is None or destroyed_root is None or destroyed_model is None or not self._is_deceptors_detachment():
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: DETONATOR: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: DETONATOR: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: DETONATOR: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root) or not self._csm_has_keyword(root, "CHARACTER"):
            logger.error("ERROR: DETONATOR: target must be a HERETIC ASTARTES CHARACTER unit")
            return False
        if self._csm_owned_by_player(destroyed_root, self.player):
            logger.error("ERROR: DETONATOR: destroyed unit must be an enemy unit")
            return False
        if self._csm_has_keyword(destroyed_root, "TITANIC"):
            logger.error("ERROR: DETONATOR: TITANIC units are not eligible")
            return False
        has_deadly_demise = getattr(destroyed_root, "has_deadly_demise", None)
        deadly_demise = has_deadly_demise() if callable(has_deadly_demise) else (False, None)
        if not bool(deadly_demise[0]):
            logger.error("ERROR: DETONATOR: destroyed unit does not have Deadly Demise")
            return False
        model_alive_attr = getattr(destroyed_model, "is_alive", None)
        model_alive = bool(model_alive_attr() if callable(model_alive_attr) else model_alive_attr)
        if model_alive:
            logger.error("ERROR: DETONATOR: destroyed model is not destroyed")
            return False
        eligible = candidates or self._deceptors_detonator_candidates(destroyed_model=destroyed_model)
        if eligible and root not in eligible:
            logger.error("ERROR: DETONATOR: target unit is not within 18\" of the destroyed model")
            return False
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            logger.error("ERROR: DETONATOR: map context unavailable")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        setattr(destroyed_model, "_deceptors_detonator_auto_trigger_once", True)
        setattr(destroyed_model, "_skip_deadly_demise_once", True)
        trigger_fn = getattr(destroyed_root, "trigger_deadly_demise_manually", None)
        if callable(trigger_fn):
            trigger_fn(destroyed_model, game_map)

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DETONATOR: %s automatically triggers Deadly Demise via %s.",
            getattr(destroyed_root, "name", "Unit"),
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_deceptors_from_all_sides(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("FROM ALL SIDES", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: FROM ALL SIDES: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_deceptors_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: FROM ALL SIDES: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: FROM ALL SIDES: not your Charge phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: FROM ALL SIDES: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: FROM ALL SIDES: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: FROM ALL SIDES: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: FROM ALL SIDES: target must be HERETIC ASTARTES")
            return False
        if bool(getattr(getattr(root, "round_state", None), "attempted_charge_this_round", False)):
            logger.error("ERROR: FROM ALL SIDES: target has already attempted a charge")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_deceptors_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: FROM ALL SIDES: detachment effect state helper is unavailable")
            return False
        baseline_charged_ids: list[str] = []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        seen_ids: set[str] = set()
        for candidate in list(getattr(army, "units", []) or []):
            candidate_root = self._csm_root(candidate)
            if candidate_root is None or not self._is_heretic_astartes_unit(candidate_root):
                continue
            candidate_id = str(get_entity_id(candidate_root) or "")
            if candidate_id and candidate_id in seen_ids:
                continue
            if candidate_id:
                seen_ids.add(candidate_id)
            if bool(getattr(getattr(candidate_root, "round_state", None), "charged_this_round", False)):
                baseline_charged_ids.append(candidate_id)
        set_state(
            root,
            prefix=mgr._DECEPTORS_FROM_ALL_SIDES_PREFIX,
            source=stratagem.name or "FROM ALL SIDES",
            player=self.player,
            game=self.game,
            extra_state={
                f"{mgr._DECEPTORS_FROM_ALL_SIDES_PREFIX}_baseline_charged_unit_ids": baseline_charged_ids,
            },
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: FROM ALL SIDES: %s gains charge-roll bonuses from other friendly chargers this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_deceptors_pick_them_off(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("PICK THEM OFF", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PICK THEM OFF: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_deceptors_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: PICK THEM OFF: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: PICK THEM OFF: not your Shooting phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: PICK THEM OFF: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: PICK THEM OFF: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: PICK THEM OFF: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: PICK THEM OFF: target must be HERETIC ASTARTES")
            return False
        if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: PICK THEM OFF: target has already shot this round")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_deceptors_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: PICK THEM OFF: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._DECEPTORS_PICK_THEM_OFF_PREFIX,
            source=stratagem.name or "PICK THEM OFF",
            player=self.player,
            game=self.game,
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PICK THEM OFF: %s gains ranged hit/wound re-roll support against weakened targets this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_deceptors_relentless_pursuit(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        enemy_unit = kwargs.get("moving_unit") or kwargs.get("enemy_unit")
        action = kwargs.get("action")
        pending = None
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "RELENTLESS PURSUIT":
                continue
            pending = reaction
            break
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if enemy_unit is None:
                enemy_unit = pending.get("moving_unit") or pending.get("enemy_unit")
            if action is None:
                action = pending.get("action")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: RELENTLESS PURSUIT: no target unit provided")
            return False

        root = self._csm_root(unit)
        enemy_root = self._csm_root(enemy_unit)
        if root is None or enemy_root is None or not self._is_deceptors_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: RELENTLESS PURSUIT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: RELENTLESS PURSUIT: not opponent's Movement phase")
            return False
        action_key = str(action or "").strip().lower().replace(" ", "_")
        if action_key not in {"move", "normal", "normal_move", "advance", "fall_back", "fallback"}:
            logger.error("ERROR: RELENTLESS PURSUIT: invalid trigger action")
            return False
        if self._csm_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: RELENTLESS PURSUIT: trigger unit must be an enemy unit")
            return False
        if not self._csm_is_alive(enemy_root) or not bool(getattr(enemy_root, "deployed", False)):
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: RELENTLESS PURSUIT: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: RELENTLESS PURSUIT: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: RELENTLESS PURSUIT: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: RELENTLESS PURSUIT: target must be HERETIC ASTARTES")
            return False
        if not (self._is_heretic_astartes_infantry(root) or self._is_heretic_astartes_mounted(root)):
            logger.error("ERROR: RELENTLESS PURSUIT: target must be INFANTRY or MOUNTED")
            return False
        if self._csm_unit_is_engaged(root):
            logger.error("ERROR: RELENTLESS PURSUIT: target must not be within Engagement Range")
            return False
        eligible = candidates or self._deceptors_relentless_pursuit_candidates(enemy_unit=enemy_root)
        if eligible and root not in eligible:
            logger.error("ERROR: RELENTLESS PURSUIT: target must be within 9\" of the enemy unit")
            return False
        queue_move = getattr(getattr(self, "game", None), "_queue_reactive_move_movement_decision", None)
        if not callable(queue_move):
            logger.error("ERROR: RELENTLESS PURSUIT: reactive move queue unavailable")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=6,
            kind="relentless_pursuit",
            movement_type="reactive",
            reactive_movement_type="move",
            source=str(getattr(stratagem, "name", "") or "RELENTLESS PURSUIT"),
            moving_unit=enemy_root,
            attacker_unit=enemy_root,
            allow_skip=True,
        )
        if request is None:
            logger.error("ERROR: RELENTLESS PURSUIT: failed to queue reactive move")
            return False

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: RELENTLESS PURSUIT: %s can make a reactive Normal move up to 6\".",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_deceptors_scrambled_coordinates(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("SCRAMBLED COORDINATES", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SCRAMBLED COORDINATES: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_deceptors_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: SCRAMBLED COORDINATES: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: SCRAMBLED COORDINATES: not opponent's Movement phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: SCRAMBLED COORDINATES: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: SCRAMBLED COORDINATES: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: SCRAMBLED COORDINATES: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: SCRAMBLED COORDINATES: target must be HERETIC ASTARTES")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_deceptors_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: SCRAMBLED COORDINATES: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._DECEPTORS_SCRAMBLED_COORDINATES_PREFIX,
            source=stratagem.name or "SCRAMBLED COORDINATES",
            player=self.player,
            game=self.game,
            extra_state={
                f"{mgr._DECEPTORS_SCRAMBLED_COORDINATES_PREFIX}_range": 12.0,
                f"{mgr._DECEPTORS_SCRAMBLED_COORDINATES_PREFIX}_horizontal_only": True,
            },
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SCRAMBLED COORDINATES: enemy Reinforcements must remain outside 12\" of %s this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_dread_talons_depthless_cruelty(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("DEPTHLESS CRUELTY", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: DEPTHLESS CRUELTY: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_dread_talons_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: DEPTHLESS CRUELTY: wrong phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: DEPTHLESS CRUELTY: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: DEPTHLESS CRUELTY: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: DEPTHLESS CRUELTY: target cannot be selected")
            return False
        if not self._is_heretic_astartes_infantry(root):
            logger.error("ERROR: DEPTHLESS CRUELTY: target must be HERETIC ASTARTES INFANTRY")
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: DEPTHLESS CRUELTY: target has already fought this phase")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_dread_talons_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: DEPTHLESS CRUELTY: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._DREAD_TALONS_DEPTHLESS_CRUELTY_PREFIX,
            source=stratagem.name or "DEPTHLESS CRUELTY",
            player=self.player,
            game=self.game,
            extra_state={
                f"{mgr._DREAD_TALONS_DEPTHLESS_CRUELTY_PREFIX}_ap_bonus": 1,
            },
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DEPTHLESS CRUELTY: %s gains melee AP against Battle-shocked or weakened targets this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_dread_talons_pitiless_hunters(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("PITILESS HUNTERS", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PITILESS HUNTERS: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_dread_talons_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: PITILESS HUNTERS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: PITILESS HUNTERS: not your Shooting phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: PITILESS HUNTERS: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: PITILESS HUNTERS: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: PITILESS HUNTERS: target cannot be selected")
            return False
        if not self._is_heretic_astartes_infantry(root):
            logger.error("ERROR: PITILESS HUNTERS: target must be HERETIC ASTARTES INFANTRY")
            return False
        if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: PITILESS HUNTERS: target has already shot this phase")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_dread_talons_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: PITILESS HUNTERS: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._DREAD_TALONS_PITILESS_HUNTERS_PREFIX,
            source=stratagem.name or "PITILESS HUNTERS",
            player=self.player,
            game=self.game,
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PITILESS HUNTERS: %s gains ranged hit and wound re-rolls against broken or weakened targets this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_dread_talons_relentless_terror(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        action = kwargs.get("action")
        pending = self._csm_find_pending_reaction("RELENTLESS TERROR", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if action is None:
                action = pending.get("action")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: RELENTLESS TERROR: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_dread_talons_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: RELENTLESS TERROR: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: RELENTLESS TERROR: not your Movement phase")
            return False
        action_key = str(action or "").strip().lower().replace(" ", "_")
        if action_key not in {"fall_back", "fallback"}:
            logger.error("ERROR: RELENTLESS TERROR: target did not Fall Back")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: RELENTLESS TERROR: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: RELENTLESS TERROR: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: RELENTLESS TERROR: target cannot be selected")
            return False
        if not self._is_heretic_astartes_infantry(root):
            logger.error("ERROR: RELENTLESS TERROR: target must be HERETIC ASTARTES INFANTRY")
            return False
        if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
            logger.error("ERROR: RELENTLESS TERROR: target has not Fallen Back this round")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_dread_talons_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: RELENTLESS TERROR: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._DREAD_TALONS_RELENTLESS_TERROR_PREFIX,
            source=stratagem.name or "RELENTLESS TERROR",
            player=self.player,
            game=self.game,
            track_phase=False,
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: RELENTLESS TERROR: %s can charge after Falling Back this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_nightmare_hunt_prey_on_the_weak(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("PREY ON THE WEAK", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if unit is None and not candidates:
            if phase_name == "shooting phase":
                candidates = self._nightmare_hunt_targetable_units(require_infantry=True, require_not_shot=True)
            elif phase_name == "fight phase":
                candidates = self._nightmare_hunt_targetable_units(require_infantry=True, require_not_fought=True)
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PREY ON THE WEAK: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_nightmare_hunt_detachment():
            return False
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: PREY ON THE WEAK: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: PREY ON THE WEAK: not your Shooting phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: PREY ON THE WEAK: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: PREY ON THE WEAK: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: PREY ON THE WEAK: target cannot be selected")
            return False
        if not self._is_heretic_astartes_infantry(root):
            logger.error("ERROR: PREY ON THE WEAK: target must be HERETIC ASTARTES INFANTRY")
            return False
        round_state = getattr(root, "round_state", None)
        if phase_name == "shooting phase" and bool(getattr(round_state, "shot_this_round", False)):
            logger.error("ERROR: PREY ON THE WEAK: target has already been selected to shoot")
            return False
        if phase_name == "fight phase" and bool(getattr(round_state, "fought_this_phase", False)):
            logger.error("ERROR: PREY ON THE WEAK: target has already been selected to fight")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_nightmare_hunt_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: PREY ON THE WEAK: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._NIGHTMARE_HUNT_PREY_ON_THE_WEAK_PREFIX,
            source=stratagem.name or "PREY ON THE WEAK",
            player=active_player if active_player is not None else self.player,
            game=self.game,
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PREY ON THE WEAK: %s gains Hit re-rolls against Battle-shocked or Below Half-strength targets this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_nightmare_hunt_talons_sunk_deep(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("TALONS SUNK DEEP", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if unit is None and not candidates:
            if phase_name == "shooting phase":
                candidates = self._nightmare_hunt_targetable_units(require_infantry=True, require_not_shot=True)
            elif phase_name == "fight phase":
                candidates = self._nightmare_hunt_targetable_units(require_infantry=True, require_not_fought=True)
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: TALONS SUNK DEEP: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_nightmare_hunt_detachment():
            return False
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: TALONS SUNK DEEP: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: TALONS SUNK DEEP: not your Shooting phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: TALONS SUNK DEEP: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: TALONS SUNK DEEP: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: TALONS SUNK DEEP: target cannot be selected")
            return False
        if not self._is_heretic_astartes_infantry(root):
            logger.error("ERROR: TALONS SUNK DEEP: target must be HERETIC ASTARTES INFANTRY")
            return False
        round_state = getattr(root, "round_state", None)
        if phase_name == "shooting phase" and bool(getattr(round_state, "shot_this_round", False)):
            logger.error("ERROR: TALONS SUNK DEEP: target has already been selected to shoot")
            return False
        if phase_name == "fight phase" and bool(getattr(round_state, "fought_this_phase", False)):
            logger.error("ERROR: TALONS SUNK DEEP: target has already been selected to fight")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_nightmare_hunt_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: TALONS SUNK DEEP: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._NIGHTMARE_HUNT_TALONS_SUNK_DEEP_PREFIX,
            source=stratagem.name or "TALONS SUNK DEEP",
            player=active_player if active_player is not None else self.player,
            game=self.game,
            extra_state={f"{mgr._NIGHTMARE_HUNT_TALONS_SUNK_DEEP_PREFIX}_ap_bonus": 1},
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TALONS SUNK DEEP: %s improves AP against Battle-shocked or Below Half-strength targets this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_nightmare_hunt_relentless_terror(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        action = kwargs.get("action")
        pending = self._csm_find_pending_reaction("RELENTLESS TERROR", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if action is None:
                action = pending.get("action")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: RELENTLESS TERROR: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_nightmare_hunt_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: RELENTLESS TERROR: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: RELENTLESS TERROR: not your Movement phase")
            return False
        action_key = str(action or "").strip().lower().replace(" ", "_")
        if action_key not in {"fall_back", "fallback"}:
            logger.error("ERROR: RELENTLESS TERROR: target did not Fall Back")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: RELENTLESS TERROR: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: RELENTLESS TERROR: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: RELENTLESS TERROR: target cannot be selected")
            return False
        if not self._is_heretic_astartes_infantry(root):
            logger.error("ERROR: RELENTLESS TERROR: target must be HERETIC ASTARTES INFANTRY")
            return False
        if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
            logger.error("ERROR: RELENTLESS TERROR: target has not Fallen Back this round")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_nightmare_hunt_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: RELENTLESS TERROR: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._NIGHTMARE_HUNT_RELENTLESS_TERROR_PREFIX,
            source=stratagem.name or "RELENTLESS TERROR",
            player=self.player,
            game=self.game,
            track_phase=False,
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: RELENTLESS TERROR: %s can shoot and charge after Falling Back this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_nightmare_hunt_malicious_surge(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("MALICIOUS SURGE", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and not candidates:
            candidates = self._nightmare_hunt_targetable_units(require_infantry=True)
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: MALICIOUS SURGE: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_nightmare_hunt_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: MALICIOUS SURGE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: MALICIOUS SURGE: not your Charge phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: MALICIOUS SURGE: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: MALICIOUS SURGE: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: MALICIOUS SURGE: target cannot be selected")
            return False
        if not self._is_heretic_astartes_infantry(root):
            logger.error("ERROR: MALICIOUS SURGE: target must be HERETIC ASTARTES INFANTRY")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_nightmare_hunt_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: MALICIOUS SURGE: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._NIGHTMARE_HUNT_MALICIOUS_SURGE_PREFIX,
            source=stratagem.name or "MALICIOUS SURGE",
            player=self.player,
            game=self.game,
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MALICIOUS SURGE: %s can charge after Advancing this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_nightmare_hunt_horrific_incursion(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit")
        enemy_candidates = list(kwargs.get("enemy_candidates") or [])
        pending = self._csm_find_pending_reaction("HORRIFIC INCURSION", unit=unit)
        if pending is not None:
            if unit is None:
                unit = pending.get("unit") or pending.get("target_unit")
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if enemy_unit is None:
                enemy_unit = pending.get("enemy_unit") or pending.get("target_enemy_unit")
            if not enemy_candidates:
                enemy_candidates = list(pending.get("enemy_candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: HORRIFIC INCURSION: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_nightmare_hunt_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: HORRIFIC INCURSION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: HORRIFIC INCURSION: not your Movement phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: HORRIFIC INCURSION: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: HORRIFIC INCURSION: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: HORRIFIC INCURSION: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: HORRIFIC INCURSION: target must be HERETIC ASTARTES")
            return False
        if not bool(getattr(root, "arrived_from_reserves_this_turn", False)):
            logger.error("ERROR: HORRIFIC INCURSION: target must have arrived from Reserves this turn")
            return False
        if not enemy_candidates:
            enemy_candidates = self._nightmare_hunt_enemy_units_in_range_visible(
                root,
                radius=12.0,
                exclude_monster_vehicle=True,
            )
        if enemy_unit is None and len(enemy_candidates) == 1:
            enemy_unit = enemy_candidates[0]
        if enemy_unit is None:
            logger.error("ERROR: HORRIFIC INCURSION: no enemy unit provided")
            return False
        enemy_root = self._csm_root(enemy_unit)
        if enemy_root is None:
            logger.error("ERROR: HORRIFIC INCURSION: invalid enemy unit")
            return False
        if enemy_candidates and enemy_root not in enemy_candidates:
            logger.error("ERROR: HORRIFIC INCURSION: enemy target is not currently eligible")
            return False
        if self._csm_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: HORRIFIC INCURSION: enemy target must be controlled by your opponent")
            return False
        if not self._csm_is_alive(enemy_root) or not self._csm_is_on_battlefield(enemy_root):
            logger.error("ERROR: HORRIFIC INCURSION: enemy target must be on the battlefield")
            return False
        if self._csm_has_keyword(enemy_root, "MONSTER") or self._csm_has_keyword(enemy_root, "VEHICLE"):
            logger.error("ERROR: HORRIFIC INCURSION: enemy target cannot be a MONSTER or VEHICLE")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        force_test = getattr(enemy_root, "force_battle_shock_test", None)
        if not callable(force_test):
            logger.error("ERROR: HORRIFIC INCURSION: target unit cannot take a forced Battle-shock test")
            return False
        force_test(
            int(getattr(self.game, "turn", 0) or 1) if self.game is not None else 1,
            modifier=-1,
            source=str(stratagem.name or "HORRIFIC INCURSION"),
        )

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: HORRIFIC INCURSION: %s forces %s to take a Battle-shock test at -1.",
            getattr(root, "name", "Unit"),
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_nightmare_hunt_sadistic_display(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        enemy_units = list(kwargs.get("enemy_units") or [])
        pending = self._csm_find_pending_reaction("SADISTIC DISPLAY", unit=unit)
        if pending is not None:
            if unit is None:
                unit = pending.get("unit") or pending.get("target_unit")
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if not enemy_units:
                enemy_units = list(pending.get("enemy_units") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SADISTIC DISPLAY: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_nightmare_hunt_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: SADISTIC DISPLAY: wrong phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: SADISTIC DISPLAY: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: SADISTIC DISPLAY: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: SADISTIC DISPLAY: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: SADISTIC DISPLAY: target must be HERETIC ASTARTES")
            return False
        if not enemy_units:
            enemy_units = self._nightmare_hunt_enemy_units_in_range_visible(
                root,
                radius=6.0,
                exclude_monster_vehicle=True,
            )
        if not enemy_units:
            logger.error("ERROR: SADISTIC DISPLAY: no eligible enemy units are in range and visible")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        current_turn = int(getattr(self.game, "turn", 0) or 1) if self.game is not None else 1
        for enemy_root in list(enemy_units or []):
            take_test = getattr(enemy_root, "take_battle_shock_test", None)
            if callable(take_test):
                take_test(current_turn)

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SADISTIC DISPLAY: %s forces Battle-shock tests on nearby visible enemies.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_dread_talons_merciless_pursuit(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit")
        enemy_candidates = list(kwargs.get("enemy_candidates") or [])
        enemy_candidates_by_unit = kwargs.get("enemy_candidates_by_unit")
        pending = None
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "MERCILESS PURSUIT":
                continue
            pending = reaction
            break
        if pending is not None:
            if unit is None:
                unit = pending.get("unit") or pending.get("target_unit")
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if enemy_unit is None:
                enemy_unit = pending.get("enemy_unit") or pending.get("target_enemy_unit")
            if not enemy_candidates:
                enemy_candidates = list(pending.get("enemy_candidates") or [])
            if enemy_candidates_by_unit is None:
                enemy_candidates_by_unit = pending.get("enemy_candidates_by_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: MERCILESS PURSUIT: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_dread_talons_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: MERCILESS PURSUIT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: MERCILESS PURSUIT: not opponent's Movement phase")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: MERCILESS PURSUIT: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: MERCILESS PURSUIT: target cannot be selected")
            return False
        if not self._is_heretic_astartes_infantry(root):
            logger.error("ERROR: MERCILESS PURSUIT: target must be HERETIC ASTARTES INFANTRY")
            return False
        if self._csm_unit_is_engaged(root):
            logger.error("ERROR: MERCILESS PURSUIT: target must not be within Engagement Range")
            return False

        valid_candidates, enemy_map = self._dread_talons_merciless_pursuit_candidates()
        if candidates:
            valid_candidates = list(candidates)
        if valid_candidates and root not in valid_candidates:
            logger.error("ERROR: MERCILESS PURSUIT: target is not currently eligible")
            return False

        valid_enemy_candidates = list(enemy_candidates or [])
        if not valid_enemy_candidates and hasattr(enemy_candidates_by_unit, "get"):
            valid_enemy_candidates = list(enemy_candidates_by_unit.get(self._csm_sort_key(root)) or [])
        if not valid_enemy_candidates:
            valid_enemy_candidates = list(enemy_map.get(self._csm_sort_key(root)) or [])
        if enemy_unit is None and len(valid_enemy_candidates) == 1:
            enemy_unit = valid_enemy_candidates[0]
        elif enemy_unit is None and valid_enemy_candidates:
            enemy_unit = valid_enemy_candidates[0]
        enemy_root = self._csm_root(enemy_unit)
        if enemy_root is None:
            logger.error("ERROR: MERCILESS PURSUIT: no eligible enemy unit selected")
            return False
        if self._csm_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: MERCILESS PURSUIT: selected enemy unit is not enemy")
            return False
        if not self._csm_is_alive(enemy_root) or not self._csm_is_on_battlefield(enemy_root):
            logger.error("ERROR: MERCILESS PURSUIT: selected enemy unit must be on the battlefield")
            return False
        if valid_enemy_candidates and enemy_root not in valid_enemy_candidates:
            logger.error("ERROR: MERCILESS PURSUIT: selected enemy unit is not currently eligible")
            return False
        if not bool(getattr(getattr(enemy_root, "round_state", None), "fell_back_this_round", False)):
            logger.error("ERROR: MERCILESS PURSUIT: selected enemy unit did not Fall Back this turn")
            return False
        can_charge = getattr(root, "can_declare_charge_against", None)
        if not callable(can_charge) or not bool(can_charge(enemy_root, self.game, out_of_turn=True)):
            logger.error("ERROR: MERCILESS PURSUIT: target cannot declare a charge against the selected enemy")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        ok = bool(self.game.attempt_charge(root, enemy_root, out_of_turn=True, count_as_charged=False)) if self.game is not None else False
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        if not ok:
            logger.error("ERROR: MERCILESS PURSUIT: charge failed")
        else:
            logger.info(
                "INFO: MERCILESS PURSUIT: %s declares an out-of-turn charge against %s (no charge bonus).",
                getattr(root, "name", "Unit"),
                getattr(enemy_root, "name", "Enemy"),
            )
        return True

    def _use_dread_talons_bloody_example(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        enemy_units = list(kwargs.get("enemy_units") or [])
        pending = self._csm_find_pending_reaction("BLOODY EXAMPLE", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if not enemy_units:
                enemy_units = list(pending.get("enemy_units") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: BLOODY EXAMPLE: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_dread_talons_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: BLOODY EXAMPLE: wrong phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: BLOODY EXAMPLE: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: BLOODY EXAMPLE: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: BLOODY EXAMPLE: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: BLOODY EXAMPLE: target must be HERETIC ASTARTES")
            return False

        valid_enemies = list(enemy_units or self._dread_talons_enemy_units_in_range_visible(root, radius=12.0))
        if not valid_enemies:
            logger.error("ERROR: BLOODY EXAMPLE: no visible enemy units within 12\"")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        for enemy_root in list(valid_enemies):
            take_test = getattr(enemy_root, "take_battle_shock_test", None)
            if callable(take_test):
                take_test(current_turn)

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: BLOODY EXAMPLE: %s forces Battle-shock tests on nearby visible enemies.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_dread_talons_screaming_descent(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("SCREAMING DESCENT", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SCREAMING DESCENT: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_dread_talons_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: SCREAMING DESCENT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SCREAMING DESCENT: not your Movement phase")
            return False
        try:
            battle_round = int(getattr(self.game, "turn", 0) or 0)
        except (TypeError, ValueError):
            battle_round = 0
        if battle_round < 2:
            logger.error("ERROR: SCREAMING DESCENT: can only be used from the second battle round onwards")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: SCREAMING DESCENT: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: SCREAMING DESCENT: target unit is not yours")
            return False
        if not self._csm_is_alive(root):
            return False
        if not self._csm_is_in_reserves(root):
            logger.error("ERROR: SCREAMING DESCENT: target must be in Reserves")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: SCREAMING DESCENT: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root) or not self._csm_has_keyword(root, "JUMP PACK"):
            logger.error("ERROR: SCREAMING DESCENT: target must be a HERETIC ASTARTES JUMP PACK unit")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_dread_talons_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: SCREAMING DESCENT: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._DREAD_TALONS_SCREAMING_DESCENT_PREFIX,
            source=stratagem.name or "SCREAMING DESCENT",
            player=self.player,
            game=self.game,
            extra_state={
                f"{mgr._DREAD_TALONS_SCREAMING_DESCENT_PREFIX}_deep_strike_min_distance": 6.0,
                f"{mgr._DREAD_TALONS_SCREAMING_DESCENT_PREFIX}_temp_deep_strike": True,
                f"{mgr._DREAD_TALONS_SCREAMING_DESCENT_PREFIX}_post_setup_battleshock_pending": True,
                "dread_talons_screaming_descent_no_charge_turn_owner": str(getattr(self.player, "id", "") or ""),
                "dread_talons_screaming_descent_no_charge_turn": int(battle_round),
                "dread_talons_screaming_descent_no_charge_source": str(stratagem.name or "SCREAMING DESCENT"),
            },
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SCREAMING DESCENT: %s can arrive more than 6\" from enemies this phase and cannot charge this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_fellhammer_persistent_assailants(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        attacking_unit = kwargs.get("attacking_unit")
        pending = self._csm_find_pending_reaction("PERSISTENT ASSAILANTS", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if attacking_unit is None:
                attacking_unit = pending.get("attacking_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PERSISTENT ASSAILANTS: no target unit provided")
            return False

        root = self._csm_root(unit)
        attacker_root = self._csm_root(attacking_unit)
        if root is None or attacker_root is None or not self._is_fellhammer_siege_host_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: PERSISTENT ASSAILANTS: wrong phase")
            return False
        if self._csm_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: PERSISTENT ASSAILANTS: attacking unit must be an enemy unit")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: PERSISTENT ASSAILANTS: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: PERSISTENT ASSAILANTS: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: PERSISTENT ASSAILANTS: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: PERSISTENT ASSAILANTS: target must be HERETIC ASTARTES")
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: PERSISTENT ASSAILANTS: target has already fought this phase")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_fellhammer_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: PERSISTENT ASSAILANTS: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._FELLHAMMER_PERSISTENT_ASSAILANTS_PREFIX,
            source=stratagem.name or "PERSISTENT ASSAILANTS",
            player=self.player,
            game=self.game,
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PERSISTENT ASSAILANTS: %s gains melee hit re-rolls, and wound re-rolls while Below Half-strength, this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_fellhammer_brutal_attrition(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        attacking_unit = kwargs.get("attacking_unit")
        pending = self._csm_find_pending_reaction("BRUTAL ATTRITION", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if attacking_unit is None:
                attacking_unit = pending.get("attacking_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: BRUTAL ATTRITION: no target unit provided")
            return False

        root = self._csm_root(unit)
        attacker_root = self._csm_root(attacking_unit)
        if root is None or attacker_root is None or not self._is_fellhammer_siege_host_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: BRUTAL ATTRITION: wrong phase")
            return False
        if self._csm_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: BRUTAL ATTRITION: attacking unit must be an enemy unit")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: BRUTAL ATTRITION: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: BRUTAL ATTRITION: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: BRUTAL ATTRITION: target cannot be selected")
            return False
        if not self._is_heretic_astartes_infantry(root) or self._is_damned_unit(root):
            logger.error("ERROR: BRUTAL ATTRITION: target must be HERETIC ASTARTES INFANTRY and not DAMNED")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_fellhammer_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: BRUTAL ATTRITION: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._FELLHAMMER_BRUTAL_ATTRITION_PREFIX,
            source=stratagem.name or "BRUTAL ATTRITION",
            player=self.player,
            game=self.game,
            extra_state={
                f"{mgr._FELLHAMMER_BRUTAL_ATTRITION_PREFIX}_attacker_unit_id": mgr._unit_entity_key(attacker_root),
                f"{mgr._FELLHAMMER_BRUTAL_ATTRITION_PREFIX}_max_rolls_per_attacker_unit": 6,
                f"{mgr._FELLHAMMER_BRUTAL_ATTRITION_PREFIX}_threshold": 4,
                f"{mgr._FELLHAMMER_BRUTAL_ATTRITION_PREFIX}_mortal_wounds": 1,
            },
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: BRUTAL ATTRITION: %s inflicts post-attack melee mortal retaliation against %s this phase.",
            getattr(root, "name", "Unit"),
            getattr(attacker_root, "name", "enemy"),
        )
        return True

    def _use_fellhammer_pitiless_cannonade(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("PITILESS CANNONADE", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and not candidates:
            candidates = self._fellhammer_targetable_units(require_not_shot=True)
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PITILESS CANNONADE: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_fellhammer_siege_host_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: PITILESS CANNONADE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: PITILESS CANNONADE: not your Shooting phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: PITILESS CANNONADE: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: PITILESS CANNONADE: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: PITILESS CANNONADE: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: PITILESS CANNONADE: target must be HERETIC ASTARTES")
            return False
        if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: PITILESS CANNONADE: target has already shot this phase")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_fellhammer_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: PITILESS CANNONADE: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._FELLHAMMER_PITILESS_CANNONADE_PREFIX,
            source=stratagem.name or "PITILESS CANNONADE",
            player=self.player,
            game=self.game,
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PITILESS CANNONADE: %s scores ranged critical hits on 5+ against Below Half-strength targets this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_fellhammer_point_blank_destruction(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("POINT-BLANK DESTRUCTION", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and not candidates:
            candidates = self._fellhammer_targetable_units(require_not_shot=True, require_engaged=True)
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: POINT-BLANK DESTRUCTION: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_fellhammer_siege_host_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: POINT-BLANK DESTRUCTION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: POINT-BLANK DESTRUCTION: not your Shooting phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: POINT-BLANK DESTRUCTION: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: POINT-BLANK DESTRUCTION: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: POINT-BLANK DESTRUCTION: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: POINT-BLANK DESTRUCTION: target must be HERETIC ASTARTES")
            return False
        if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: POINT-BLANK DESTRUCTION: target has already shot this phase")
            return False
        if not self._csm_unit_is_engaged(root):
            logger.error("ERROR: POINT-BLANK DESTRUCTION: target must be within Engagement Range of one or more enemy units")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_fellhammer_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: POINT-BLANK DESTRUCTION: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._FELLHAMMER_POINT_BLANK_DESTRUCTION_PREFIX,
            source=stratagem.name or "POINT-BLANK DESTRUCTION",
            player=self.player,
            game=self.game,
        )

        source = str(getattr(stratagem, "name", "POINT-BLANK DESTRUCTION") or "POINT-BLANK DESTRUCTION")
        phase_key = "SHOOTING_PHASE"
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        for model_index, model in enumerate(list(models or [])):
            alive_attr = getattr(model, "is_alive", True)
            is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if not is_alive:
                continue
            model_id = str(get_entity_id(model) or model_index)
            for wargear_index, wargear in enumerate(list(getattr(model, "wargear", []) or [])):
                if wargear is None:
                    continue
                is_ranged = getattr(wargear, "is_ranged", None)
                if not callable(is_ranged) or not bool(is_ranged()):
                    continue
                has_blast = False
                profiles = getattr(wargear, "profiles", None)
                if isinstance(profiles, dict) and profiles:
                    for profile in list(profiles.values()):
                        is_blast = getattr(profile, "is_blast", None)
                        if callable(is_blast) and bool(is_blast()):
                            has_blast = True
                            break
                else:
                    is_blast = getattr(wargear, "is_blast", None)
                    if callable(is_blast) and bool(is_blast()):
                        has_blast = True
                if has_blast:
                    continue
                weapon_name = str(getattr(wargear, "name", "") or "").strip()
                if not weapon_name:
                    continue
                key_base = f"fellhammer_point_blank_destruction:{model_id}:{wargear_index}:{weapon_name}".lower()
                set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                if callable(set_keywords):
                    set_keywords(
                        key=key_base,
                        weapon_name=weapon_name,
                        keywords=["PISTOL"],
                        source=source,
                        expires_phase=phase_key,
                        attack_type="ranged",
                    )
                    continue
                effects = getattr(model, "_temporary_effects", None)
                if not isinstance(effects, dict):
                    effects = {}
                    model._temporary_effects = effects
                effects[key_base] = {
                    "expires_phase": phase_key,
                    "weapon_keyword_bonuses": {weapon_name: ["PISTOL"]},
                    "weapon_keyword_bonuses_source": source,
                    "weapon_keyword_bonuses_attack_type": "ranged",
                }

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: POINT-BLANK DESTRUCTION: %s gains [PISTOL] on non-Blast ranged weapons this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_fellhammer_steadfast_determination(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        attacking_unit = kwargs.get("attacking_unit")
        pending = self._csm_find_pending_reaction("STEADFAST DETERMINATION", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if attacking_unit is None:
                attacking_unit = pending.get("attacking_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: STEADFAST DETERMINATION: no target unit provided")
            return False

        root = self._csm_root(unit)
        attacker_root = self._csm_root(attacking_unit)
        if root is None or attacker_root is None or not self._is_fellhammer_siege_host_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: STEADFAST DETERMINATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: STEADFAST DETERMINATION: not opponent's Shooting phase")
            return False
        if self._csm_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: STEADFAST DETERMINATION: attacking unit must be an enemy unit")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: STEADFAST DETERMINATION: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: STEADFAST DETERMINATION: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: STEADFAST DETERMINATION: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root) or self._is_damned_unit(root):
            logger.error("ERROR: STEADFAST DETERMINATION: target must be HERETIC ASTARTES and not DAMNED")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_fellhammer_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: STEADFAST DETERMINATION: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._FELLHAMMER_STEADFAST_DETERMINATION_PREFIX,
            source=stratagem.name or "STEADFAST DETERMINATION",
            player=self.player,
            game=self.game,
            extra_state={
                f"{mgr._FELLHAMMER_STEADFAST_DETERMINATION_PREFIX}_fnp": 5,
            },
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: STEADFAST DETERMINATION: %s gains Feel No Pain 5+ this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_fellhammer_siegecraft(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("SIEGECRAFT", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and not candidates:
            candidates = self._fellhammer_targetable_units()
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SIEGECRAFT: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_fellhammer_siege_host_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: SIEGECRAFT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: SIEGECRAFT: not opponent's Charge phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: SIEGECRAFT: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: SIEGECRAFT: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: SIEGECRAFT: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: SIEGECRAFT: target must be HERETIC ASTARTES")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_fellhammer_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: SIEGECRAFT: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._FELLHAMMER_SIEGECRAFT_PREFIX,
            source=stratagem.name or "SIEGECRAFT",
            player=self.player,
            game=self.game,
            extra_state={
                f"{mgr._FELLHAMMER_SIEGECRAFT_PREFIX}_charge_penalty": 2,
            },
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SIEGECRAFT: enemy units suffer -2 to Charge rolls when charging %s this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_hurons_marauders_hardened_killers(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("HARDENED KILLERS", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and not candidates:
            candidates = self._hurons_marauders_targetable_units(require_damned=True)
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: HARDENED KILLERS: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_hurons_marauders_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: HARDENED KILLERS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: HARDENED KILLERS: not your Command phase")
            return False
        if candidates and not self._hurons_marauders_unit_in_candidates(root, candidates):
            logger.error("ERROR: HARDENED KILLERS: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: HARDENED KILLERS: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: HARDENED KILLERS: target cannot be selected")
            return False
        if not self._is_damned_unit(root):
            logger.error("ERROR: HARDENED KILLERS: target must be a DAMNED unit")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        choice_key = str(kwargs.get("choice_key") or kwargs.get("key") or "").strip().upper()
        if choice_key:
            activate = getattr(mgr, "activate_hurons_marauders_hardened_killers", None) if mgr is not None else None
            outcome = (
                activate(
                    root,
                    choice_key=choice_key,
                    game=self.game,
                    player=self.player,
                    source=stratagem.name or "HARDENED KILLERS",
                )
                if callable(activate)
                else {"ok": False}
            )
            if not isinstance(outcome, dict) or not bool(outcome.get("ok", False)):
                logger.error("ERROR: HARDENED KILLERS: invalid choice")
                return False
            self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(
                "INFO: HARDENED KILLERS: %s gains %s until the start of your next turn.",
                getattr(root, "name", "Unit"),
                str(outcome.get("choice_name", choice_key) or choice_key),
            )
            return True

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        queue = getattr(self.game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for request in list(queue.list() or []):
                if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(request, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "hurons_marauders_hardened_killers_choice":
                    continue
                if str(ctx.get("unit_id", "") or "") == str(get_entity_id(root) or ""):
                    return True

        choice_keys = [
            str(getattr(mgr, "_HARDENED_KILLERS_CHOICE_BALLISTIC_SKILL", "BALLISTIC_SKILL") or "BALLISTIC_SKILL"),
            str(getattr(mgr, "_HARDENED_KILLERS_CHOICE_RAPID_FIRE", "RAPID_FIRE") or "RAPID_FIRE"),
            str(getattr(mgr, "_HARDENED_KILLERS_CHOICE_SAVE", "SAVE") or "SAVE"),
        ]
        label_fn = getattr(mgr, "_hardened_killers_choice_label", None) if mgr is not None else None
        options = [
            DecisionOption.create(
                str(label_fn(choice) if callable(label_fn) else choice).strip() or choice,
                payload={"choice_key": choice},
            )
            for choice in choice_keys
        ]
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Hardened Killers: select an effect.",
            player_id=getattr(self.player, "id", None),
            options=options,
            context={
                "ability": "hurons_marauders_hardened_killers_choice",
                "ability_name": str(stratagem.name or "Hardened Killers"),
                "unit_id": get_entity_id(root),
                "army_id": get_entity_id(getattr(self.player, "army", None)),
                "turn": int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0,
                "turn_owner_id": str(getattr(self.player, "id", "") or ""),
                "available_choice_keys": list(choice_keys),
                "optional": False,
            },
        )
        self.game.request_decision(request)
        logger.info(
            "INFO: HARDENED KILLERS: %s must select its temporary benefit.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_hurons_marauders_at_the_tyrants_command(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("AT THE TYRANT'S COMMAND", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and not candidates:
            candidates = self._hurons_marauders_targetable_units(require_non_monster_non_vehicle=True)
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: AT THE TYRANT'S COMMAND: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_hurons_marauders_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: AT THE TYRANT'S COMMAND: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: AT THE TYRANT'S COMMAND: not your Movement phase")
            return False
        if candidates and not self._hurons_marauders_unit_in_candidates(root, candidates):
            logger.error("ERROR: AT THE TYRANT'S COMMAND: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: AT THE TYRANT'S COMMAND: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: AT THE TYRANT'S COMMAND: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: AT THE TYRANT'S COMMAND: target must be HERETIC ASTARTES")
            return False
        if self._csm_has_keyword(root, "MONSTER") or self._csm_has_keyword(root, "VEHICLE"):
            logger.error("ERROR: AT THE TYRANT'S COMMAND: target cannot be a MONSTER or VEHICLE")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_hurons_marauders_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: AT THE TYRANT'S COMMAND: detachment effect helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._HURONS_MARAUDERS_AT_THE_TYRANTS_COMMAND_PREFIX,
            source=stratagem.name or "AT THE TYRANT'S COMMAND",
            player=self.player,
            game=self.game,
            track_phase=False,
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: AT THE TYRANT'S COMMAND: %s can shoot and charge after Advancing this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_hurons_marauders_seize_the_prize(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        action = kwargs.get("action")
        pending = self._csm_find_pending_reaction("SEIZE THE PRIZE", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if action is None:
                action = pending.get("action")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SEIZE THE PRIZE: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_hurons_marauders_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: SEIZE THE PRIZE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SEIZE THE PRIZE: not your Movement phase")
            return False
        action_key = str(action or "").strip().lower().replace(" ", "_")
        if action_key not in {"advance", "advancing", "advance_move"}:
            logger.error("ERROR: SEIZE THE PRIZE: target was not just selected to Advance")
            return False
        if candidates and not self._hurons_marauders_unit_in_candidates(root, candidates):
            logger.error("ERROR: SEIZE THE PRIZE: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: SEIZE THE PRIZE: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: SEIZE THE PRIZE: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: SEIZE THE PRIZE: target must be HERETIC ASTARTES")
            return False
        if self._csm_has_keyword(root, "MONSTER") or self._csm_has_keyword(root, "VEHICLE"):
            logger.error("ERROR: SEIZE THE PRIZE: target cannot be a MONSTER or VEHICLE")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        effect_tag = "stratagem:hurons_marauders_seize_the_prize"
        effects = [
            entry
            for entry in list(sr.get("advance_no_roll_effects", []) or [])
            if not (isinstance(entry, dict) and str(entry.get("tag", "") or "") == effect_tag)
        ]
        effects.append(
            {
                "distance": 6,
                "source": str(stratagem.name or "SEIZE THE PRIZE"),
                "tag": effect_tag,
                "expires_phase": "MOVEMENT_PHASE",
            }
        )
        sr["advance_no_roll_effects"] = effects
        root.special_rules = sr

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SEIZE THE PRIZE: %s uses a fixed 6\" Advance this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_hurons_marauders_reavers_flurry(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("REAVERS' FLURRY", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and not candidates:
            candidates = self._hurons_marauders_targetable_units(require_not_fought=True, require_charged=True)
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: REAVERS' FLURRY: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_hurons_marauders_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: REAVERS' FLURRY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: REAVERS' FLURRY: not your Fight phase")
            return False
        if candidates and not self._hurons_marauders_unit_in_candidates(root, candidates):
            logger.error("ERROR: REAVERS' FLURRY: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: REAVERS' FLURRY: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: REAVERS' FLURRY: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: REAVERS' FLURRY: target must be HERETIC ASTARTES")
            return False
        round_state = getattr(root, "round_state", None)
        if not bool(getattr(round_state, "charged_this_round", False)):
            logger.error("ERROR: REAVERS' FLURRY: target must have charged this turn")
            return False
        if bool(getattr(round_state, "fought_this_phase", False)):
            logger.error("ERROR: REAVERS' FLURRY: target has already fought this phase")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_hurons_marauders_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: REAVERS' FLURRY: detachment effect helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._HURONS_MARAUDERS_REAVERS_FLURRY_PREFIX,
            source=stratagem.name or "REAVERS' FLURRY",
            player=self.player,
            game=self.game,
            extra_state={f"{mgr._HURONS_MARAUDERS_REAVERS_FLURRY_PREFIX}_attacks_bonus": 1},
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: REAVERS' FLURRY: %s gains +1 melee Attack this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_hurons_marauders_to_the_favoured_the_spoils(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("enemy_unit")
        pending = self._csm_find_pending_reaction("TO THE FAVOURED THE SPOILS", unit=unit)
        from_pending = pending is not None
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if attacking_unit is None:
                attacking_unit = pending.get("attacking_unit") or pending.get("enemy_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: TO THE FAVOURED THE SPOILS: no target unit provided")
            return False

        root = self._csm_root(unit)
        attacker_root = self._csm_root(attacking_unit)
        if root is None or attacker_root is None or not self._is_hurons_marauders_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: TO THE FAVOURED THE SPOILS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: TO THE FAVOURED THE SPOILS: not opponent's Shooting phase")
            return False
        if self._csm_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: TO THE FAVOURED THE SPOILS: attacking unit must be an enemy unit")
            return False
        if candidates and not self._hurons_marauders_unit_in_candidates(root, candidates):
            logger.error("ERROR: TO THE FAVOURED THE SPOILS: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: TO THE FAVOURED THE SPOILS: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: TO THE FAVOURED THE SPOILS: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: TO THE FAVOURED THE SPOILS: target must be HERETIC ASTARTES")
            return False
        if (not from_pending) and candidates:
            logger.error("ERROR: TO THE FAVOURED THE SPOILS: target must have lost wounds from the triggering attacks")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        max_distance = kwargs.get("max_distance")
        if max_distance is None:
            max_distance = int(dice_module.get_roll("D6") or 0)
        try:
            max_distance = int(max_distance or 0)
        except (TypeError, ValueError):
            max_distance = 0
        if max_distance <= 0:
            logger.error("ERROR: TO THE FAVOURED THE SPOILS: movement distance roll failed")
            return False

        closest_enemy = self._hurons_marauders_closest_non_aircraft_enemy(root)
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if not callable(queue_move):
            logger.error("ERROR: TO THE FAVOURED THE SPOILS: reactive move queue unavailable")
            return False
        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=int(max_distance),
            kind="to_the_favoured_the_spoils",
            movement_type="reactive",
            source=stratagem.name,
            attacker_unit=closest_enemy or attacker_root,
            allow_engagement_range=True,
        )
        if request is None:
            logger.error("ERROR: TO THE FAVOURED THE SPOILS: failed to queue reactive move")
            return False

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TO THE FAVOURED THE SPOILS: %s can make a Surge move up to %d\" toward the closest non-AIRCRAFT enemy.",
            getattr(root, "name", "Unit"),
            int(max_distance),
        )
        return True

    def _use_hurons_marauders_encircling_surge(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("ENCIRCLING SURGE", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and not candidates:
            candidates = [
                root
                for root in self._hurons_marauders_targetable_units(
                    require_non_monster_non_vehicle=True,
                    require_not_engaged=True,
                )
                if self._unit_wholly_within_battlefield_edge_distance(root, 6.0)
            ]
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: ENCIRCLING SURGE: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_hurons_marauders_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: ENCIRCLING SURGE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: ENCIRCLING SURGE: not opponent's Fight phase")
            return False
        if candidates and not self._hurons_marauders_unit_in_candidates(root, candidates):
            logger.error("ERROR: ENCIRCLING SURGE: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: ENCIRCLING SURGE: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: ENCIRCLING SURGE: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: ENCIRCLING SURGE: target must be HERETIC ASTARTES")
            return False
        if self._csm_has_keyword(root, "MONSTER") or self._csm_has_keyword(root, "VEHICLE"):
            logger.error("ERROR: ENCIRCLING SURGE: target cannot be a MONSTER or VEHICLE")
            return False
        if self._csm_unit_is_engaged(root):
            logger.error("ERROR: ENCIRCLING SURGE: target must not be within Engagement Range")
            return False
        if not self._unit_wholly_within_battlefield_edge_distance(root, 6.0):
            logger.error("ERROR: ENCIRCLING SURGE: target must be wholly within 6\" of a battlefield edge")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        place_fn = getattr(root, "enter_strategic_reserves_midgame", None)
        if not callable(place_fn) or not bool(
            place_fn(
                game=self.game,
                game_map=getattr(self.game, "map", None),
                reason=str(stratagem.name or "ENCIRCLING SURGE"),
            )
        ):
            logger.error("ERROR: ENCIRCLING SURGE: failed to place target into Strategic Reserves")
            return False

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ENCIRCLING SURGE: %s enters Strategic Reserves.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_cabal_baleful_blessing(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        from_pending = False
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "BALEFUL BLESSING":
                    continue
                from_pending = True
                unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                kwargs.setdefault("mortal_wound_allocated", reaction.get("mortal_wound_allocated"))
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: BALEFUL BLESSING: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None:
            return False
        if not from_pending:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "BALEFUL BLESSING":
                    continue
                pending_root = self._csm_root(reaction.get("unit") or reaction.get("target_unit"))
                if pending_root is not root:
                    continue
                from_pending = True
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                kwargs.setdefault("mortal_wound_allocated", reaction.get("mortal_wound_allocated"))
                break
        if not self._is_cabal_of_chaos_detachment():
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: BALEFUL BLESSING: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: BALEFUL BLESSING: target is not currently eligible")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: BALEFUL BLESSING: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: BALEFUL BLESSING: target must be HERETIC ASTARTES")
            return False

        trigger_flag = bool(kwargs.get("mortal_wound_allocated", False))
        trigger_name = str(kwargs.get("trigger", "") or "").strip().lower()
        if not from_pending and not trigger_flag and trigger_name not in {"mortal_wound_allocated", "mortal_wound"}:
            logger.error("ERROR: BALEFUL BLESSING: missing mortal-wound trigger context")
            return False

        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "")
        phase_key = self._phase_key_from_name(phase_name) if phase_name else ""
        models = []
        get_models = getattr(root, "get_attached_unit_models", None)
        if callable(get_models):
            models = list(get_models() or [])
        if not models:
            models = list(getattr(root, "models", []) or [])
        for index, model in enumerate(models):
            is_alive_attr = getattr(model, "is_alive", True)
            is_alive = bool(is_alive_attr() if callable(is_alive_attr) else is_alive_attr)
            if not is_alive:
                continue
            key = f"baleful_blessing:{get_entity_id(model) or index}"
            set_temporary_fnp = getattr(model, "set_temporary_fnp", None)
            if callable(set_temporary_fnp):
                set_temporary_fnp(
                    key=key,
                    value=5,
                    source=stratagem.name,
                    condition="against mortal wounds",
                    expires_phase=phase_key,
                )
                continue
            effects = getattr(model, "_temporary_effects", None)
            if not isinstance(effects, dict):
                effects = {}
                model._temporary_effects = effects
            effects[key] = {
                "expires_phase": str(phase_key or "").strip().upper(),
                "temporary_fnp_value": 5,
                "temporary_fnp_source": str(stratagem.name or "BALEFUL BLESSING"),
                "temporary_fnp_condition": "against mortal wounds",
            }

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: BALEFUL BLESSING: {getattr(root, 'name', 'Unit')} gains FNP 5+ vs mortal wounds this phase.")
        return True

    def _use_cabal_shroud_of_chaos(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "SHROUD OF CHAOS":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SHROUD OF CHAOS: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None:
            return False
        if not self._is_cabal_of_chaos_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: SHROUD OF CHAOS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: SHROUD OF CHAOS: not opponent's Shooting phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: SHROUD OF CHAOS: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: SHROUD OF CHAOS: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: SHROUD OF CHAOS: target cannot be selected")
            return False
        if not self._is_cabal_shroud_source_unit(root):
            logger.error("ERROR: SHROUD OF CHAOS: target must be HERETIC ASTARTES PSYKER or DAEMON PRINCE source")
            return False

        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["shroud_of_chaos_aura_active"] = True
        sr["shroud_of_chaos_expires_phase"] = "SHOOTING_PHASE"
        sr["shroud_of_chaos_owner"] = str(getattr(self.player, "id", "") or "")
        sr["shroud_of_chaos_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["shroud_of_chaos_source"] = str(stratagem.name or "SHROUD OF CHAOS")
        root.special_rules = sr

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: SHROUD OF CHAOS: {getattr(root, 'name', 'Unit')} projects a 6\" Stealth aura this phase.")
        return True

    def _use_cabal_soulseekers(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SOULSEEKERS: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None:
            return False
        if not self._is_cabal_of_chaos_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: SOULSEEKERS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SOULSEEKERS: not your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: SOULSEEKERS: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: SOULSEEKERS: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: SOULSEEKERS: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: SOULSEEKERS: target must be HERETIC ASTARTES")
            return False
        if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: SOULSEEKERS: target has already been selected to shoot")
            return False

        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["warp_vision_ignores_cover_active"] = True
        sr["warp_vision_expires_phase"] = "SHOOTING_PHASE"
        sr["warp_vision_owner"] = str(getattr(self.player, "id", "") or "")
        sr["warp_vision_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["warp_vision_source"] = str(stratagem.name or "SOULSEEKERS")
        root.special_rules = sr

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: SOULSEEKERS: {getattr(root, 'name', 'Unit')} gains [IGNORES COVER] on ranged weapons this phase.")
        return True

    def _use_cabal_unholy_haste(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: UNHOLY HASTE: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None:
            return False
        if not self._is_cabal_of_chaos_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: UNHOLY HASTE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: UNHOLY HASTE: not your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: UNHOLY HASTE: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: UNHOLY HASTE: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: UNHOLY HASTE: target cannot be selected")
            return False
        if not self._is_heretic_astartes_infantry(root):
            logger.error("ERROR: UNHOLY HASTE: target must be HERETIC ASTARTES INFANTRY")
            return False
        if bool(getattr(getattr(root, "round_state", None), "attempted_charge_this_round", False)):
            logger.error("ERROR: UNHOLY HASTE: target has already attempted a charge this phase")
            return False

        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["warp_surge_charge_after_advance"] = True
        sr["warp_surge_expires_phase"] = "CHARGE_PHASE"
        sr["warp_surge_source"] = str(stratagem.name or "UNHOLY HASTE")
        root.special_rules = sr

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: UNHOLY HASTE: {getattr(root, 'name', 'Unit')} can charge after Advancing this phase.")
        return True

    def _use_cabal_no_rest_in_death(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: NO REST IN DEATH: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None:
            return False
        if not self._is_cabal_of_chaos_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: NO REST IN DEATH: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: NO REST IN DEATH: not your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: NO REST IN DEATH: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: NO REST IN DEATH: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: NO REST IN DEATH: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: NO REST IN DEATH: target must be HERETIC ASTARTES")
            return False
        if not self._cabal_within_empyric_support(root, radius=9.0):
            logger.error("ERROR: NO REST IN DEATH: target must be within 9\" of a friendly Psyker/Daemon Prince source")
            return False

        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        is_battleline = self._csm_has_keyword(root, "BATTLELINE")
        mode = kwargs.get("mode") or kwargs.get("no_rest_in_death_mode") or kwargs.get("choice")
        if isinstance(mode, dict):
            mode = mode.get("mode") or mode.get("choice")
        mode = str(mode or "").strip().lower()
        if mode and mode not in {"heal", "return", "return_models", "return model", "return models"}:
            logger.error("ERROR: NO REST IN DEATH: invalid mode")
            return False

        models = []
        get_models = getattr(root, "get_attached_unit_models", None)
        if callable(get_models):
            models = list(get_models() or [])
        if not models:
            models = list(getattr(root, "models", []) or [])

        def _is_alive_model(model: Any) -> bool:
            alive_attr = getattr(model, "is_alive", True)
            return bool(alive_attr() if callable(alive_attr) else alive_attr)

        def _missing_wounds(model: Any) -> int:
            base_wounds = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)) or 0)
            current_wounds = int(getattr(model, "wounds", 0) or 0)
            return max(0, int(base_wounds - current_wounds))

        wounded_models = [m for m in models if _is_alive_model(m) and _missing_wounds(m) > 0]
        wounded_models = sorted(wounded_models, key=lambda m: str(get_entity_id(m) or ""))

        destroyed_pool = list(getattr(root, "models_lost", []) or [])

        def _model_is_character(model: Any) -> bool:
            char_attr = getattr(model, "is_character", None)
            if bool(char_attr() if callable(char_attr) else char_attr):
                return True
            if self._csm_has_keyword(model, "CHARACTER"):
                return True
            parent = getattr(model, "parent_unit", None)
            return bool(parent is not None and self._csm_has_keyword(parent, "CHARACTER"))

        destroyed_candidates = []
        can_return = getattr(root, "_horrors_can_return_model", None)
        for model in list(destroyed_pool):
            if model is None:
                continue
            if _model_is_character(model):
                continue
            if callable(can_return) and not bool(can_return(model)):
                continue
            destroyed_candidates.append(model)
        destroyed_candidates = sorted(destroyed_candidates, key=lambda m: str(get_entity_id(m) or ""))

        if not mode:
            if is_battleline and destroyed_candidates and not wounded_models:
                mode = "return"
            else:
                mode = "heal"

        returned = 0
        healed = 0

        if mode.startswith("return"):
            if not is_battleline:
                logger.error("ERROR: NO REST IN DEATH: return-models mode requires a BATTLELINE unit")
                return False
            return_roll = int(dice_module.get_roll("D3") or 0)
            max_return = max(0, int(return_roll))
            chosen = kwargs.get("return_models") or kwargs.get("chosen_models")
            if chosen is not None:
                selected = set()
                filtered = []
                for entry in list(chosen or []):
                    candidate_id = str(get_entity_id(entry) or entry or "")
                    if not candidate_id or candidate_id in selected:
                        continue
                    for model in destroyed_candidates:
                        if str(get_entity_id(model) or "") == candidate_id:
                            filtered.append(model)
                            selected.add(candidate_id)
                            break
                destroyed_candidates = filtered
            returned = int(
                root.return_destroyed_bodyguard_models(
                    max_return,
                    game_map=getattr(self.game, "map", None),
                    chosen_models=destroyed_candidates,
                    wounds=None,
                    placement_source=stratagem.name,
                )
                or 0
            )
        else:
            heal_roll = int(dice_module.get_roll("D3") or 0)
            heal_amount = max(0, int(heal_roll)) + 1
            heal_model = kwargs.get("model") or kwargs.get("target_model")
            if heal_model is None and wounded_models:
                heal_model = wounded_models[0]
            if heal_model is not None:
                if heal_model not in models:
                    logger.error("ERROR: NO REST IN DEATH: heal model does not belong to target unit")
                    return False
                missing = _missing_wounds(heal_model)
                if missing > 0 and heal_amount > 0:
                    healed = min(int(heal_amount), int(missing))
                    heal_fn = getattr(heal_model, "heal", None)
                    if callable(heal_fn):
                        heal_fn(int(heal_amount))
                    else:
                        base_wounds = int(getattr(heal_model, "_base_wounds", getattr(heal_model, "base_wounds", 0)) or 0)
                        current_wounds = int(getattr(heal_model, "wounds", 0) or 0)
                        heal_model.wounds = min(base_wounds, current_wounds + int(heal_amount))

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: NO REST IN DEATH: %s healed=%d returned=%d.",
            getattr(root, "name", "Unit"),
            int(healed),
            int(returned),
        )
        return True

    def _use_cabal_mutations_curse(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: MUTATION'S CURSE: no source unit provided")
            return False

        root = self._csm_root(unit)
        if root is None:
            return False
        if not self._is_cabal_of_chaos_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: MUTATION'S CURSE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: MUTATION'S CURSE: not your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: MUTATION'S CURSE: source unit is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: MUTATION'S CURSE: source unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: MUTATION'S CURSE: source unit cannot be selected")
            return False
        if not self._is_cabal_psyker_source_unit(root):
            logger.error("ERROR: MUTATION'S CURSE: source unit must be HERETIC ASTARTES PSYKER")
            return False

        enemy_candidates = self._cabal_mutations_curse_enemy_candidates(root, radius=12.0)
        if not enemy_candidates:
            logger.error("ERROR: MUTATION'S CURSE: no visible enemy unit within 12\"")
            return False
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit")
        if enemy_unit is None and len(enemy_candidates) == 1:
            enemy_unit = enemy_candidates[0]
        enemy_root = self._csm_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            logger.error("ERROR: MUTATION'S CURSE: missing enemy target selection")
            return False
        if enemy_root not in enemy_candidates:
            logger.error("ERROR: MUTATION'S CURSE: selected enemy target is not eligible")
            return False

        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        roll = int(dice_module.get_roll("D6") or 0)
        mortal_wounds = 0
        if roll <= 1:
            mortal_wounds = 1
        elif roll <= 4:
            mortal_wounds = int(dice_module.get_roll("D3") or 0)
        else:
            mortal_wounds = int(dice_module.get_roll("D3") or 0) + int(dice_module.get_roll("D3") or 0)

        if mortal_wounds > 0:
            apply_mortals = getattr(root, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortals):
                apply_mortals(enemy_root, int(mortal_wounds), game_map=getattr(self.game, "map", None))

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MUTATION'S CURSE: %s dealt %d mortal wound(s) to %s (roll=%d).",
            getattr(root, "name", "Unit"),
            int(mortal_wounds),
            getattr(enemy_root, "name", "enemy"),
            int(roll),
        )
        return True

    def _use_chaos_cult_chosen_for_glory(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: CHOSEN FOR GLORY: no target unit provided")
            return False
        root = self._csm_root(unit)
        if root is None or not self._is_chaos_cult_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: CHOSEN FOR GLORY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: CHOSEN FOR GLORY: shooting phase use requires your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: CHOSEN FOR GLORY: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: CHOSEN FOR GLORY: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: CHOSEN FOR GLORY: target cannot be selected")
            return False
        if not self._is_damned_unit(root):
            logger.error("ERROR: CHOSEN FOR GLORY: target must be DAMNED")
            return False
        mgr = self._get_chaos_space_marines_mgr()
        has_dark_pacts = getattr(mgr, "_unit_has_dark_pacts", None) if mgr is not None else None
        if not callable(has_dark_pacts) or not bool(has_dark_pacts(root)):
            logger.error("ERROR: CHOSEN FOR GLORY: target must be able to make a Desperate Pact")
            return False
        round_state = getattr(root, "round_state", None)
        if phase_name == "shooting phase" and bool(getattr(round_state, "shot_this_round", False)):
            logger.error("ERROR: CHOSEN FOR GLORY: target has already been selected to shoot")
            return False
        if phase_name == "fight phase" and bool(getattr(round_state, "fought_this_phase", False)):
            logger.error("ERROR: CHOSEN FOR GLORY: target has already been selected to fight")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False
        pact_result = mgr.resolve_chaos_cult_desperate_pact(root, game=self.game)
        mgr._set_chaos_cult_effect_state(
            root,
            prefix=mgr._CHAOS_CULT_CHOSEN_FOR_GLORY_PREFIX,
            source=stratagem.name or "CHOSEN FOR GLORY",
            player=self.player,
            game=self.game,
            extra_state={
                f"{mgr._CHAOS_CULT_CHOSEN_FOR_GLORY_PREFIX}_leadership_passed": bool(
                    pact_result.get("leadership_passed", False)
                )
            },
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CHOSEN FOR GLORY: %s gains Hit re-rolls%s until end of phase.",
            getattr(root, "name", "Unit"),
            " and Wound re-rolls" if bool(pact_result.get("leadership_passed", False)) else "",
        )
        return True

    def _use_chaos_cult_crazed_focus(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: CRAZED FOCUS: no target unit provided")
            return False
        root = self._csm_root(unit)
        if root is None or not self._is_chaos_cult_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: CRAZED FOCUS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: CRAZED FOCUS: not your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: CRAZED FOCUS: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: CRAZED FOCUS: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: CRAZED FOCUS: target cannot be selected")
            return False
        if not self._is_damned_unit(root):
            logger.error("ERROR: CRAZED FOCUS: target must be DAMNED")
            return False
        mgr = self._get_chaos_space_marines_mgr()
        has_dark_pacts = getattr(mgr, "_unit_has_dark_pacts", None) if mgr is not None else None
        if not callable(has_dark_pacts) or not bool(has_dark_pacts(root)):
            logger.error("ERROR: CRAZED FOCUS: target must be able to make a Desperate Pact")
            return False
        if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: CRAZED FOCUS: target has already been selected to shoot")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False
        pact_result = mgr.resolve_chaos_cult_desperate_pact(root, game=self.game)
        mgr._set_chaos_cult_effect_state(
            root,
            prefix=mgr._CHAOS_CULT_CRAZED_FOCUS_PREFIX,
            source=stratagem.name or "CRAZED FOCUS",
            player=self.player,
            game=self.game,
            extra_state={
                f"{mgr._CHAOS_CULT_CRAZED_FOCUS_PREFIX}_leadership_passed": bool(
                    pact_result.get("leadership_passed", False)
                )
            },
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CRAZED FOCUS: %s gains +1 AP%s on ranged attacks until end of phase.",
            getattr(root, "name", "Unit"),
            " and +1 Strength" if bool(pact_result.get("leadership_passed", False)) else "",
        )
        return True

    def _use_chaos_cult_infernal_sacrifice(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: INFERNAL SACRIFICE: no target unit provided")
            return False
        root = self._csm_root(unit)
        if root is None or not self._is_chaos_cult_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: INFERNAL SACRIFICE: wrong phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: INFERNAL SACRIFICE: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: INFERNAL SACRIFICE: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: INFERNAL SACRIFICE: target cannot be selected")
            return False
        if not self._is_damned_unit(root):
            logger.error("ERROR: INFERNAL SACRIFICE: target must be DAMNED")
            return False
        mgr = self._get_chaos_space_marines_mgr()
        has_dark_pacts = getattr(mgr, "_unit_has_dark_pacts", None) if mgr is not None else None
        if not callable(has_dark_pacts) or not bool(has_dark_pacts(root)):
            logger.error("ERROR: INFERNAL SACRIFICE: target must be able to make a Desperate Pact")
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: INFERNAL SACRIFICE: target has already been selected to fight")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False
        pact_result = mgr.resolve_chaos_cult_desperate_pact(root, game=self.game)
        extra_mortals = mgr._apply_chaos_cult_self_mortals(root, roll_spec="D3", game=self.game)
        mgr._set_chaos_cult_effect_state(
            root,
            prefix=mgr._CHAOS_CULT_INFERNAL_SACRIFICE_PREFIX,
            source=stratagem.name or "INFERNAL SACRIFICE",
            player=self.player,
            game=self.game,
            extra_state={
                f"{mgr._CHAOS_CULT_INFERNAL_SACRIFICE_PREFIX}_leadership_passed": bool(
                    pact_result.get("leadership_passed", False)
                )
            },
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: INFERNAL SACRIFICE: %s gains +1 Attacks%s and suffers %d mortal wound(s).",
            getattr(root, "name", "Unit"),
            " and +1 Strength" if bool(pact_result.get("leadership_passed", False)) else "",
            int(extra_mortals) + int(pact_result.get("mortal_wounds", 0) or 0),
        )
        return True

    def _use_chaos_cult_reckless_haste(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: RECKLESS HASTE: no target unit provided")
            return False
        root = self._csm_root(unit)
        if root is None or not self._is_chaos_cult_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: RECKLESS HASTE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: RECKLESS HASTE: not your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: RECKLESS HASTE: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: RECKLESS HASTE: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: RECKLESS HASTE: target cannot be selected")
            return False
        if not self._is_damned_unit(root):
            logger.error("ERROR: RECKLESS HASTE: target must be DAMNED")
            return False
        if bool(getattr(getattr(root, "round_state", None), "attempted_charge_this_round", False)):
            logger.error("ERROR: RECKLESS HASTE: target has already attempted a charge this phase")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["warp_surge_charge_after_advance"] = True
        sr["warp_surge_expires_phase"] = "CHARGE_PHASE"
        sr["warp_surge_source"] = str(stratagem.name or "RECKLESS HASTE")
        root.special_rules = sr
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: RECKLESS HASTE: %s can charge after Advancing this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_chaos_cult_mortal_thralls(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        support_unit = kwargs.get("support_unit")
        candidates = list(kwargs.get("candidates") or [])
        support_by_unit = dict(kwargs.get("support_candidates_by_unit") or {})
        attacking_unit = kwargs.get("attacking_unit")
        pending = self._csm_find_pending_reaction("MORTAL THRALLS", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if not support_by_unit:
                support_by_unit = dict(pending.get("support_candidates_by_unit") or {})
            if attacking_unit is None:
                attacking_unit = pending.get("attacking_unit")
            if support_unit is None:
                support_unit = pending.get("support_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: MORTAL THRALLS: no protected unit provided")
            return False
        root = self._csm_root(unit)
        attacker_root = self._csm_root(attacking_unit)
        if root is None or attacker_root is None or not self._is_chaos_cult_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: MORTAL THRALLS: wrong phase")
            return False
        if self._csm_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: MORTAL THRALLS: attacking unit must be an enemy unit")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: MORTAL THRALLS: protected unit is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: MORTAL THRALLS: protected unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: MORTAL THRALLS: protected unit cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: MORTAL THRALLS: protected unit must be HERETIC ASTARTES")
            return False
        protected_key = self._csm_sort_key(root)
        support_candidates = list(support_by_unit.get(protected_key, []) or [])
        if support_unit is None and len(support_candidates) == 1:
            support_unit = support_candidates[0]
        support_root = self._csm_root(support_unit)
        if support_root is None:
            logger.error("ERROR: MORTAL THRALLS: no support DAMNED unit provided")
            return False
        if support_candidates and support_root not in support_candidates:
            logger.error("ERROR: MORTAL THRALLS: support unit is not currently eligible")
            return False
        if not self._csm_owned_by_player(support_root, self.player):
            logger.error("ERROR: MORTAL THRALLS: support unit is not yours")
            return False
        if not self._csm_is_alive(support_root) or not self._csm_is_on_battlefield(support_root):
            return False
        if self._unit_cannot_be_target_of_stratagem(support_root):
            logger.error("ERROR: MORTAL THRALLS: support unit cannot be selected")
            return False
        if not self._is_damned_unit(support_root):
            logger.error("ERROR: MORTAL THRALLS: support unit must be DAMNED")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False
        mgr = self._get_chaos_space_marines_mgr()
        mgr._set_chaos_cult_effect_state(
            root,
            prefix=mgr._CHAOS_CULT_MORTAL_THRALLS_PREFIX,
            source=stratagem.name or "MORTAL THRALLS",
            player=self.player,
            game=self.game,
            extra_state={
                f"{mgr._CHAOS_CULT_MORTAL_THRALLS_PREFIX}_attacker_unit_id": mgr._unit_entity_key(attacker_root),
                f"{mgr._CHAOS_CULT_MORTAL_THRALLS_PREFIX}_support_unit_id": mgr._unit_entity_key(support_root),
            },
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MORTAL THRALLS: %s redirects eligible wound rolls to %s this phase.",
            getattr(root, "name", "Unit"),
            getattr(support_root, "name", "Unit"),
        )
        return True

    def _use_chaos_cult_selfless_demise(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        attacking_unit = kwargs.get("attacking_unit")
        pending = self._csm_find_pending_reaction("SELFLESS DEMISE", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if attacking_unit is None:
                attacking_unit = pending.get("attacking_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SELFLESS DEMISE: no target unit provided")
            return False
        root = self._csm_root(unit)
        attacker_root = self._csm_root(attacking_unit)
        if root is None or attacker_root is None or not self._is_chaos_cult_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: SELFLESS DEMISE: wrong phase")
            return False
        if self._csm_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: SELFLESS DEMISE: attacking unit must be an enemy unit")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: SELFLESS DEMISE: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: SELFLESS DEMISE: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: SELFLESS DEMISE: target cannot be selected")
            return False
        if not self._is_damned_unit(root):
            logger.error("ERROR: SELFLESS DEMISE: target must be DAMNED")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False
        mgr = self._get_chaos_space_marines_mgr()
        mgr._set_chaos_cult_effect_state(
            root,
            prefix=mgr._CHAOS_CULT_SELFLESS_DEMISE_PREFIX,
            source=stratagem.name or "SELFLESS DEMISE",
            player=self.player,
            game=self.game,
            extra_state={
                f"{mgr._CHAOS_CULT_SELFLESS_DEMISE_PREFIX}_attacker_unit_id": mgr._unit_entity_key(attacker_root),
            },
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SELFLESS DEMISE: %s rolls for post-attack mortal retaliation against %s this phase.",
            getattr(root, "name", "Unit"),
            getattr(attacker_root, "name", "enemy"),
        )
        return True

    def _use_creations_of_bile_autostimulants(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            if len(candidates) == 1:
                unit = candidates[0]
            else:
                candidates = self._creations_of_bile_autostimulants_candidates()
                if len(candidates) == 1:
                    unit = candidates[0]
        if unit is None:
            logger.error("ERROR: AUTOSTIMULANTS: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_creations_of_bile_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: AUTOSTIMULANTS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: AUTOSTIMULANTS: not your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: AUTOSTIMULANTS: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: AUTOSTIMULANTS: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: AUTOSTIMULANTS: target cannot be selected")
            return False
        if not self._is_heretic_astartes_infantry(root):
            logger.error("ERROR: AUTOSTIMULANTS: target must be HERETIC ASTARTES INFANTRY")
            return False
        if bool(getattr(getattr(root, "round_state", None), "attempted_charge_this_round", False)):
            logger.error("ERROR: AUTOSTIMULANTS: target has already attempted a charge")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["warp_surge_charge_after_advance"] = True
        sr["warp_surge_expires_phase"] = "CHARGE_PHASE"
        sr["warp_surge_source"] = str(stratagem.name or "AUTOSTIMULANTS")
        root.special_rules = sr

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: AUTOSTIMULANTS: %s can charge after Advancing this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_creations_of_bile_delayed_mutations(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            if len(candidates) == 1:
                unit = candidates[0]
            else:
                candidates = self._creations_of_bile_delayed_mutations_candidates()
                if len(candidates) == 1:
                    unit = candidates[0]
        if unit is None:
            logger.error("ERROR: DELAYED MUTATIONS: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_creations_of_bile_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: DELAYED MUTATIONS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: DELAYED MUTATIONS: not your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: DELAYED MUTATIONS: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: DELAYED MUTATIONS: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: DELAYED MUTATIONS: target cannot be selected")
            return False
        if not self._is_creations_eligible_unit(root):
            logger.error("ERROR: DELAYED MUTATIONS: target must be eligible HERETIC ASTARTES INFANTRY excluding DAMNED")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        apply_self_mortals = getattr(mgr, "_apply_chaos_cult_self_mortals", None) if mgr is not None else None
        mortal_wounds = int(apply_self_mortals(root, roll_spec="D3", game=self.game) or 0) if callable(apply_self_mortals) else 0
        still_alive = self._csm_is_alive(root) and self._csm_is_on_battlefield(root)
        choice_key = str(kwargs.get("choice_key") or kwargs.get("augmentation_key") or "").strip().upper()

        if still_alive and choice_key:
            activate = getattr(mgr, "activate_creations_of_bile_delayed_mutations", None) if mgr is not None else None
            outcome = (
                activate(
                    root,
                    choice_key=choice_key,
                    game=self.game,
                    player=self.player,
                    source=stratagem.name or "DELAYED MUTATIONS",
                )
                if callable(activate)
                else {"ok": False}
            )
            if not isinstance(outcome, dict) or not bool(outcome.get("ok", False)):
                logger.error("ERROR: DELAYED MUTATIONS: invalid augmentation choice")
                return False
            self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(
                "INFO: DELAYED MUTATIONS: %s suffers %d mortal wound(s) and gains %s until next Command phase.",
                getattr(root, "name", "Unit"),
                int(mortal_wounds),
                str(outcome.get("choice_name", choice_key) or choice_key),
            )
            return True

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        if not still_alive:
            logger.info(
                "INFO: DELAYED MUTATIONS: %s was destroyed by the self-inflicted mortal wounds.",
                getattr(root, "name", "Unit"),
            )
            return True

        queue = getattr(self.game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for pending in list(queue.list() or []):
                if str(getattr(pending, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                pending_ctx = dict(getattr(pending, "context", {}) or {})
                if str(pending_ctx.get("ability", "") or "") != "csm_creations_delayed_mutations_choice":
                    continue
                if str(pending_ctx.get("unit_id", "") or "") == str(get_entity_id(root) or ""):
                    return True

        options = []
        available_choice_keys = []
        catalog_fn = getattr(mgr, "experimental_augmentations_catalog", None) if mgr is not None else None
        catalog = list(catalog_fn() or []) if callable(catalog_fn) else []
        for augmentation in list(catalog or []):
            choice = str(getattr(augmentation, "key", "") or "").strip().upper()
            if not choice:
                continue
            label = str(getattr(augmentation, "name", "") or choice).strip() or choice
            options.append(DecisionOption.create(label, payload={"choice_key": choice}))
            available_choice_keys.append(choice)
        if not options:
            logger.error("ERROR: DELAYED MUTATIONS: no augmentation options available")
            return False

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Delayed Mutations: select an augmentation.",
            player_id=getattr(self.player, "id", None),
            options=options,
            context={
                "ability": "csm_creations_delayed_mutations_choice",
                "ability_name": str(stratagem.name or "Delayed Mutations"),
                "unit_id": get_entity_id(root),
                "army_id": get_entity_id(getattr(self.player, "army", None)),
                "battle_round": int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0,
                "turn": int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0,
                "turn_owner_id": str(getattr(self.player, "id", "") or ""),
                "available_choice_keys": list(available_choice_keys),
                "optional": False,
            },
        )
        self.game.request_decision(request)
        logger.info(
            "INFO: DELAYED MUTATIONS: %s suffers %d mortal wound(s); choose an augmentation.",
            getattr(root, "name", "Unit"),
            int(mortal_wounds),
        )
        return True

    def _use_creations_of_bile_diabolic_regeneration(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            if len(candidates) == 1:
                unit = candidates[0]
            else:
                candidates = self._creations_of_bile_diabolic_regeneration_candidates()
                if len(candidates) == 1:
                    unit = candidates[0]
        if unit is None:
            logger.error("ERROR: DIABOLIC REGENERATION: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_creations_of_bile_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: DIABOLIC REGENERATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: DIABOLIC REGENERATION: not your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: DIABOLIC REGENERATION: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: DIABOLIC REGENERATION: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: DIABOLIC REGENERATION: target cannot be selected")
            return False
        if not self._is_creations_eligible_unit(root):
            logger.error("ERROR: DIABOLIC REGENERATION: target must be eligible HERETIC ASTARTES INFANTRY excluding DAMNED")
            return False

        destroyed_candidates = [
            model
            for model in list(getattr(root, "models_lost", []) or [])
            if not self._csm_model_is_character(model)
        ]
        if not destroyed_candidates:
            logger.error("ERROR: DIABOLIC REGENERATION: no destroyed non-CHARACTER models can be returned")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        return_amount = 1
        if self._csm_has_keyword(root, "BATTLELINE"):
            return_amount = max(0, int(dice_module.get_roll("D3") or 0))
        queue_return = getattr(self.game, "_queue_bodyguard_return_decision", None) if self.game is not None else None
        if not callable(queue_return):
            logger.error("ERROR: DIABOLIC REGENERATION: bodyguard return queue is unavailable")
            return False
        allowed_ids = [
            str(get_entity_id(model) or "")
            for model in list(destroyed_candidates or [])
            if str(get_entity_id(model) or "")
        ]
        request = queue_return(
            player=self.player,
            leader_unit=root,
            bodyguard_unit=root,
            ability={"name": str(stratagem.name or "DIABOLIC REGENERATION")},
            remaining=int(max(1, return_amount)),
            allowed_model_ids=list(allowed_ids),
            allow_skip=False,
        )
        if request is None:
            logger.error("ERROR: DIABOLIC REGENERATION: no eligible return decision could be queued")
            return False

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DIABOLIC REGENERATION: %s will return up to %d destroyed non-CHARACTER model(s).",
            getattr(root, "name", "Unit"),
            int(max(1, return_amount)),
        )
        return True

    def _use_creations_of_bile_masters_are_watching(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        attacking_unit = kwargs.get("attacking_unit")
        pending = self._csm_find_pending_reaction("MASTERS ARE WATCHING", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if attacking_unit is None:
                attacking_unit = pending.get("attacking_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: MASTERS ARE WATCHING: no target unit provided")
            return False

        root = self._csm_root(unit)
        attacker_root = self._csm_root(attacking_unit)
        if root is None or attacker_root is None or not self._is_creations_of_bile_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: MASTERS ARE WATCHING: wrong phase")
            return False
        if self._csm_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: MASTERS ARE WATCHING: attacking unit must be an enemy unit")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: MASTERS ARE WATCHING: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: MASTERS ARE WATCHING: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: MASTERS ARE WATCHING: target cannot be selected")
            return False
        if not self._is_heretic_astartes_infantry(root):
            logger.error("ERROR: MASTERS ARE WATCHING: target must be HERETIC ASTARTES INFANTRY")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_creations_of_bile_phase_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: MASTERS ARE WATCHING: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._CREATIONS_OF_BILE_MASTERS_ARE_WATCHING_PREFIX,
            source=stratagem.name or "MASTERS ARE WATCHING",
            player=self.player,
            game=self.game,
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MASTERS ARE WATCHING: %s gains melee fight-on-death until end of phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_creations_of_bile_specimens_for_the_spider(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            if len(candidates) == 1:
                unit = candidates[0]
            else:
                candidates = self._creations_of_bile_specimens_for_the_spider_candidates()
                if len(candidates) == 1:
                    unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SPECIMENS FOR THE SPIDER: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_creations_of_bile_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: SPECIMENS FOR THE SPIDER: wrong phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: SPECIMENS FOR THE SPIDER: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: SPECIMENS FOR THE SPIDER: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: SPECIMENS FOR THE SPIDER: target cannot be selected")
            return False
        if not self._is_heretic_astartes_infantry(root):
            logger.error("ERROR: SPECIMENS FOR THE SPIDER: target must be HERETIC ASTARTES INFANTRY")
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: SPECIMENS FOR THE SPIDER: target has already fought this phase")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_creations_of_bile_phase_effect_state", None) if mgr is not None else None
        collect_destroyed = getattr(mgr, "_collect_destroyed_enemy_character_model_ids", None) if mgr is not None else None
        if not callable(set_state) or not callable(collect_destroyed):
            logger.error("ERROR: SPECIMENS FOR THE SPIDER: detachment effect helpers are unavailable")
            return False
        set_state(
            root,
            prefix=mgr._CREATIONS_OF_BILE_SPECIMENS_FOR_THE_SPIDER_PREFIX,
            source=stratagem.name or "SPECIMENS FOR THE SPIDER",
            player=self.player,
            game=self.game,
            extra_state={
                f"{mgr._CREATIONS_OF_BILE_SPECIMENS_FOR_THE_SPIDER_PREFIX}_enemy_character_model_ids": list(
                    collect_destroyed(root, game=self.game)
                ),
                f"{mgr._CREATIONS_OF_BILE_SPECIMENS_FOR_THE_SPIDER_PREFIX}_enemy_warlord_model_ids": list(
                    collect_destroyed(root, warlord_only=True, game=self.game)
                ),
                f"{mgr._CREATIONS_OF_BILE_SPECIMENS_FOR_THE_SPIDER_PREFIX}_resolved": False,
            },
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SPECIMENS FOR THE SPIDER: %s gains melee wound re-rolls vs CHARACTER targets this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_soulforged_daemonic_possesion(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("DAEMONIC POSSESION", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: DAEMONIC POSSESION: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_soulforged_warpack_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: DAEMONIC POSSESION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: DAEMONIC POSSESION: not your turn")
            return False
        if candidates and not self._is_soulforged_unit_in_candidates(root, candidates):
            logger.error("ERROR: DAEMONIC POSSESION: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: DAEMONIC POSSESION: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: DAEMONIC POSSESION: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root) or not self._csm_has_keyword(root, "VEHICLE"):
            logger.error("ERROR: DAEMONIC POSSESION: target must be a HERETIC ASTARTES VEHICLE")
            return False
        if self._csm_has_keyword(root, "DAEMON"):
            logger.error("ERROR: DAEMONIC POSSESION: target cannot already be a DAEMON unit")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        extra_keywords = list(sr.get("ability_added_keywords", []) or [])
        lowered = {str(keyword or "").strip().lower() for keyword in extra_keywords}
        if "daemon" not in lowered:
            extra_keywords.append("DAEMON")
            sr["ability_added_keywords"] = extra_keywords
        sr["soulforged_warpack_daemonic_possesion_active"] = True
        sr["soulforged_warpack_daemonic_possesion_source"] = (
            str(getattr(stratagem, "name", "") or mgr._SOULFORGED_WARPACK_DAEMONIC_POSSESION_SOURCE).strip()
            or mgr._SOULFORGED_WARPACK_DAEMONIC_POSSESION_SOURCE
        )
        root.special_rules = sr
        if mgr is not None:
            mgr._clear_unit_ability_cache(root)

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DAEMONIC POSSESION: %s gains the DAEMON keyword for the rest of the battle.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_soulforged_desperate_pledge(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("DESPERATE PLEDGE", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: DESPERATE PLEDGE: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_soulforged_warpack_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: DESPERATE PLEDGE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: DESPERATE PLEDGE: shooting-phase use is only available in your turn")
            return False
        if candidates and not self._is_soulforged_unit_in_candidates(root, candidates):
            logger.error("ERROR: DESPERATE PLEDGE: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: DESPERATE PLEDGE: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: DESPERATE PLEDGE: target cannot be selected")
            return False
        if not (self._is_heretic_astartes_unit(root) and self._csm_has_keyword(root, "DAEMON") and self._csm_has_keyword(root, "VEHICLE")):
            logger.error("ERROR: DESPERATE PLEDGE: target must be a HERETIC ASTARTES DAEMON VEHICLE")
            return False
        round_state = getattr(root, "round_state", None)
        if phase_name == "shooting phase" and bool(getattr(round_state, "shot_this_round", False)):
            logger.error("ERROR: DESPERATE PLEDGE: target has already been selected to shoot")
            return False
        if phase_name == "fight phase" and bool(getattr(round_state, "fought_this_phase", False)):
            logger.error("ERROR: DESPERATE PLEDGE: target has already been selected to fight")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_soulforged_warpack_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: DESPERATE PLEDGE: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._SOULFORGED_WARPACK_DESPERATE_PLEDGE_PREFIX,
            source=stratagem.name or "DESPERATE PLEDGE",
            player=self.player,
            game=self.game,
            extra_state={f"{mgr._SOULFORGED_WARPACK_DESPERATE_PLEDGE_PREFIX}_ap_bonus": 1},
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DESPERATE PLEDGE: %s gains contract-gated AP improvement until end of phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_soulforged_feeding_frenzy(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        enemy_unit = kwargs.get("moving_unit") or kwargs.get("enemy_unit")
        action = kwargs.get("action")
        pending = self._csm_find_pending_reaction("FEEDING FRENZY", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if enemy_unit is None:
                enemy_unit = pending.get("moving_unit") or pending.get("enemy_unit")
            if action is None:
                action = pending.get("action")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: FEEDING FRENZY: no target unit provided")
            return False

        root = self._csm_root(unit)
        enemy_root = self._csm_root(enemy_unit)
        if root is None or enemy_root is None or not self._is_soulforged_warpack_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: FEEDING FRENZY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: FEEDING FRENZY: not opponent's Movement phase")
            return False
        action_key = str(action or "").strip().lower().replace(" ", "_")
        if action_key not in {"fall_back", "fallback"}:
            logger.error("ERROR: FEEDING FRENZY: invalid trigger action")
            return False
        if self._csm_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: FEEDING FRENZY: trigger unit must be an enemy unit")
            return False
        if self._csm_has_keyword(enemy_root, "MONSTER") or self._csm_has_keyword(enemy_root, "VEHICLE"):
            logger.error("ERROR: FEEDING FRENZY: trigger unit cannot be a MONSTER or VEHICLE")
            return False
        if candidates and not self._is_soulforged_unit_in_candidates(root, candidates):
            logger.error("ERROR: FEEDING FRENZY: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: FEEDING FRENZY: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: FEEDING FRENZY: target cannot be selected")
            return False
        if not (
            (self._csm_has_keyword(root, "VEHICLE") and self._csm_has_keyword(root, "DAEMON") and self._is_heretic_astartes_unit(root))
            or self._is_vashtorr_unit(root)
        ):
            logger.error("ERROR: FEEDING FRENZY: target must be a HERETIC ASTARTES DAEMON VEHICLE or Vashtorr")
            return False
        eligible = candidates or self._soulforged_feeding_frenzy_candidates(enemy_unit=enemy_root)
        if eligible and not self._is_soulforged_unit_in_candidates(root, eligible):
            logger.error("ERROR: FEEDING FRENZY: target must be within Engagement Range of the triggering enemy unit")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["enemy_fallback_desperate_escape"] = True
        sr["enemy_fallback_desperate_escape_exclude_monster_vehicle"] = True
        sr["enemy_fallback_desperate_escape_bs_penalty"] = 1
        sr["enemy_fallback_desperate_escape_penalty"] = 0
        sr.pop("enemy_fallback_desperate_escape_target_enemy_id", None)
        sr["enemy_fallback_desperate_escape_expires_phase"] = "MOVEMENT_PHASE"
        sr["enemy_fallback_desperate_escape_turn_owner"] = str(getattr(active_player, "id", "") or "")
        sr["enemy_fallback_desperate_escape_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["enemy_fallback_desperate_escape_source"] = str(getattr(stratagem, "name", "") or "FEEDING FRENZY")
        root.special_rules = sr

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: FEEDING FRENZY: enemy non-MONSTER/non-VEHICLE units falling back from your lines must take Desperate Escape tests this phase.",
        )
        return True

    def _use_soulforged_glut_of_souls(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("GLUT OF SOULS", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: GLUT OF SOULS: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_soulforged_warpack_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: GLUT OF SOULS: wrong phase")
            return False
        if candidates and not self._is_soulforged_unit_in_candidates(root, candidates):
            logger.error("ERROR: GLUT OF SOULS: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: GLUT OF SOULS: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: GLUT OF SOULS: target cannot be selected")
            return False
        if not (self._is_heretic_astartes_unit(root) and self._csm_has_keyword(root, "DAEMON") and self._csm_has_keyword(root, "VEHICLE")):
            logger.error("ERROR: GLUT OF SOULS: target must be a HERETIC ASTARTES DAEMON VEHICLE")
            return False
        if self._csm_has_keyword(root, "TITANIC"):
            logger.error("ERROR: GLUT OF SOULS: target cannot be TITANIC")
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: GLUT OF SOULS: target has already been selected to fight")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_soulforged_warpack_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: GLUT OF SOULS: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._SOULFORGED_WARPACK_GLUT_OF_SOULS_PREFIX,
            source=stratagem.name or "GLUT OF SOULS",
            player=self.player,
            game=self.game,
            extra_state={
                f"{mgr._SOULFORGED_WARPACK_GLUT_OF_SOULS_PREFIX}_threshold": 5,
                f"{mgr._SOULFORGED_WARPACK_GLUT_OF_SOULS_PREFIX}_heal_cap": 6,
                f"{mgr._SOULFORGED_WARPACK_GLUT_OF_SOULS_PREFIX}_healed_wounds": 0,
            },
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: GLUT OF SOULS: %s can regain lost wounds from contract-fuelled kills this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_soulforged_predatory_pursuit(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        enemy_unit = kwargs.get("moving_unit") or kwargs.get("enemy_unit")
        action = kwargs.get("action")
        pending = self._csm_find_pending_reaction("PREDATORY PURSUIT", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if enemy_unit is None:
                enemy_unit = pending.get("moving_unit") or pending.get("enemy_unit")
            if action is None:
                action = pending.get("action")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PREDATORY PURSUIT: no target unit provided")
            return False

        root = self._csm_root(unit)
        enemy_root = self._csm_root(enemy_unit)
        if root is None or enemy_root is None or not self._is_soulforged_warpack_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: PREDATORY PURSUIT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: PREDATORY PURSUIT: not opponent's Movement phase")
            return False
        action_key = str(action or "").strip().lower().replace(" ", "_")
        if action_key not in {"move", "normal", "normal_move", "advance", "fall_back", "fallback"}:
            logger.error("ERROR: PREDATORY PURSUIT: invalid trigger action")
            return False
        if self._csm_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: PREDATORY PURSUIT: trigger unit must be an enemy unit")
            return False
        if candidates and not self._is_soulforged_unit_in_candidates(root, candidates):
            logger.error("ERROR: PREDATORY PURSUIT: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: PREDATORY PURSUIT: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: PREDATORY PURSUIT: target cannot be selected")
            return False
        if not ((self._is_heretic_astartes_unit(root) and self._csm_has_keyword(root, "VEHICLE")) or self._is_vashtorr_unit(root)):
            logger.error("ERROR: PREDATORY PURSUIT: target must be a HERETIC ASTARTES VEHICLE or Vashtorr")
            return False
        if self._csm_unit_is_engaged(root):
            logger.error("ERROR: PREDATORY PURSUIT: target must not be within Engagement Range")
            return False
        eligible = candidates or self._soulforged_predatory_pursuit_candidates(enemy_unit=enemy_root)
        if eligible and not self._is_soulforged_unit_in_candidates(root, eligible):
            logger.error("ERROR: PREDATORY PURSUIT: target must be within 9\" of the enemy unit")
            return False
        queue_move = getattr(getattr(self, "game", None), "_queue_reactive_move_movement_decision", None)
        if not callable(queue_move):
            logger.error("ERROR: PREDATORY PURSUIT: reactive move queue unavailable")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=6,
            kind="predatory_pursuit",
            movement_type="reactive",
            reactive_movement_type="move",
            source=str(getattr(stratagem, "name", "") or "PREDATORY PURSUIT"),
            moving_unit=enemy_root,
            attacker_unit=enemy_root,
            allow_skip=True,
            extra_context={"predatory_pursuit_target_unit_id": str(get_entity_id(enemy_root) or "")},
        )
        if request is None:
            logger.error("ERROR: PREDATORY PURSUIT: failed to queue reactive move")
            return False

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PREDATORY PURSUIT: %s can make a reactive Normal move up to 6\" toward %s.",
            getattr(root, "name", "Unit"),
            getattr(enemy_root, "name", "Unit"),
        )
        return True

    def _use_soulforged_unstoppable_rampage(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("UNSTOPPABLE RAMPAGE", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: UNSTOPPABLE RAMPAGE: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_soulforged_warpack_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"movement phase", "charge phase"}:
            logger.error("ERROR: UNSTOPPABLE RAMPAGE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: UNSTOPPABLE RAMPAGE: not your turn")
            return False
        if candidates and not self._is_soulforged_unit_in_candidates(root, candidates):
            logger.error("ERROR: UNSTOPPABLE RAMPAGE: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: UNSTOPPABLE RAMPAGE: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: UNSTOPPABLE RAMPAGE: target cannot be selected")
            return False
        if not ((self._is_heretic_astartes_unit(root) and self._csm_has_keyword(root, "VEHICLE")) or self._is_vashtorr_unit(root)):
            logger.error("ERROR: UNSTOPPABLE RAMPAGE: target must be a HERETIC ASTARTES VEHICLE or Vashtorr")
            return False
        round_state = getattr(root, "round_state", None)
        if phase_name == "movement phase" and bool(getattr(round_state, "moved_this_round", False)):
            logger.error("ERROR: UNSTOPPABLE RAMPAGE: target has already been selected to move")
            return False
        if phase_name == "charge phase" and bool(getattr(round_state, "attempted_charge_this_round", False)):
            logger.error("ERROR: UNSTOPPABLE RAMPAGE: target has already been selected to charge")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        move_types = {"charge"} if phase_name == "charge phase" else {"move", "advance"}
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        current = set(sr.get("bearer_unit_phase_move_terrain_only_types") or [])
        added = set()
        for move_type in move_types:
            if move_type not in current:
                current.add(move_type)
                added.add(move_type)
        if current:
            sr["bearer_unit_phase_move_terrain_only_types"] = sorted(current)
        if added:
            sr["soulforged_warpack_unstoppable_rampage_added_phase_move_terrain_only_types"] = sorted(added)
        sr["soulforged_warpack_unstoppable_rampage_active"] = True
        sr["soulforged_warpack_unstoppable_rampage_expires_phase"] = (
            "CHARGE_PHASE" if phase_name == "charge phase" else "MOVEMENT_PHASE"
        )
        sr["soulforged_warpack_unstoppable_rampage_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["soulforged_warpack_unstoppable_rampage_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["soulforged_warpack_unstoppable_rampage_source"] = str(getattr(stratagem, "name", "") or "UNSTOPPABLE RAMPAGE")
        root.special_rules = sr

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: UNSTOPPABLE RAMPAGE: %s can move horizontally through terrain this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_pactbound_profane_zeal(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("PROFANE ZEAL", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PROFANE ZEAL: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_pactbound_zealots_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: PROFANE ZEAL: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: PROFANE ZEAL: shooting-phase use is only available in your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: PROFANE ZEAL: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: PROFANE ZEAL: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: PROFANE ZEAL: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: PROFANE ZEAL: target must be HERETIC ASTARTES")
            return False
        if self._pactbound_mark_for_unit(root) != "CHAOS UNDIVIDED":
            logger.error("ERROR: PROFANE ZEAL: target must be CHAOS UNDIVIDED")
            return False
        round_state = getattr(root, "round_state", None)
        if phase_name == "shooting phase" and bool(getattr(round_state, "shot_this_round", False)):
            logger.error("ERROR: PROFANE ZEAL: target has already been selected to shoot")
            return False
        if phase_name == "fight phase" and bool(getattr(round_state, "fought_this_phase", False)):
            logger.error("ERROR: PROFANE ZEAL: target has already been selected to fight")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_pactbound_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: PROFANE ZEAL: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._PACTBOUND_PROFANE_ZEAL_PREFIX,
            source=stratagem.name or "PROFANE ZEAL",
            player=self.player,
            game=self.game,
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PROFANE ZEAL: %s re-rolls Wound rolls until end of phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_pactbound_skinshift(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("SKINSHIFT", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SKINSHIFT: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_pactbound_zealots_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: SKINSHIFT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SKINSHIFT: not your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: SKINSHIFT: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: SKINSHIFT: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: SKINSHIFT: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: SKINSHIFT: target must be HERETIC ASTARTES")
            return False

        models = self._pactbound_attached_models(root)
        wounded_models = self._pactbound_wounded_models(root)
        heal_model = kwargs.get("model") or kwargs.get("target_model")
        if heal_model is None and wounded_models:
            heal_model = wounded_models[0]
        if heal_model is not None and heal_model not in models:
            logger.error("ERROR: SKINSHIFT: heal model does not belong to target unit")
            return False
        if heal_model is not None and heal_model not in wounded_models:
            logger.error("ERROR: SKINSHIFT: selected heal model has no lost wounds")
            return False

        mark = self._pactbound_mark_for_unit(root)
        below_starting_strength = bool(getattr(root, "is_below_starting_strength", lambda: False)())
        destroyed_candidates = self._pactbound_destroyed_non_character_models(root)
        can_return = bool(mark == "TZEENTCH" and below_starting_strength and destroyed_candidates)
        if heal_model is None and not can_return:
            logger.error("ERROR: SKINSHIFT: target has no eligible model to heal or return")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        healed = 0
        if heal_model is not None:
            try:
                base_wounds = int(getattr(heal_model, "_base_wounds", getattr(heal_model, "base_wounds", 0)) or 0)
                current_wounds = int(getattr(heal_model, "wounds", 0) or 0)
            except (TypeError, ValueError):
                base_wounds = 0
                current_wounds = 0
            missing = max(0, int(base_wounds - current_wounds))
            if missing > 0:
                healed = min(3, int(missing))
                heal_fn = getattr(heal_model, "heal", None)
                if callable(heal_fn):
                    heal_fn(3)
                else:
                    heal_model.wounds = min(base_wounds, current_wounds + 3)

        returned = 0
        if can_return:
            chosen_models = kwargs.get("return_models") or kwargs.get("chosen_models")
            if chosen_models is not None:
                selected: list[Any] = []
                seen_ids: set[str] = set()
                for entry in list(chosen_models or []):
                    candidate_id = str(get_entity_id(entry) or entry or "")
                    if not candidate_id or candidate_id in seen_ids:
                        continue
                    for model in destroyed_candidates:
                        if str(get_entity_id(model) or "") == candidate_id:
                            selected.append(model)
                            seen_ids.add(candidate_id)
                            break
                destroyed_candidates = selected
            returned = int(
                root.return_destroyed_bodyguard_models(
                    1,
                    game_map=getattr(self.game, "map", None),
                    chosen_models=destroyed_candidates or None,
                    wounds=None,
                    placement_source=stratagem.name,
                )
                or 0
            )

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SKINSHIFT: %s healed=%d returned=%d.",
            getattr(root, "name", "Unit"),
            int(healed),
            int(returned),
        )
        return True

    def _use_pactbound_eye_of_the_gods(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        character_models = list(kwargs.get("character_models") or [])
        pending = self._csm_find_pending_reaction("EYE OF THE GODS", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if not character_models:
                character_models = list(pending.get("character_models") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: EYE OF THE GODS: no source unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_pactbound_zealots_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: EYE OF THE GODS: wrong phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: EYE OF THE GODS: source unit is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: EYE OF THE GODS: source unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: EYE OF THE GODS: source unit cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: EYE OF THE GODS: source unit must be HERETIC ASTARTES")
            return False

        if not character_models:
            character_models = self._pactbound_eye_of_the_gods_character_models(root)
        model = kwargs.get("model") or kwargs.get("target_model")
        if model is None:
            if len(character_models) == 1:
                model = character_models[0]
            elif character_models:
                model = sorted(character_models, key=lambda entry: str(get_entity_id(entry) or ""))[0]
        if model is None:
            logger.error("ERROR: EYE OF THE GODS: no eligible CHARACTER model provided")
            return False
        if character_models and model not in character_models:
            logger.error("ERROR: EYE OF THE GODS: selected model is not currently eligible")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        apply_bonus = getattr(mgr, "apply_pactbound_eye_of_the_gods_to_model", None) if mgr is not None else None
        if not callable(apply_bonus):
            logger.error("ERROR: EYE OF THE GODS: detachment helper is unavailable")
            return False
        result = apply_bonus(model, source=stratagem.name or "EYE OF THE GODS")
        if not bool((result or {}).get("ok", False)):
            logger.error("ERROR: EYE OF THE GODS: %s", str((result or {}).get("reason", "failed to apply buff")))
            return False

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: EYE OF THE GODS: %s gains permanent characteristic bonuses.",
            getattr(model, "name", "Model"),
        )
        return True

    def _use_pactbound_festering_miasma(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        attacking_unit = kwargs.get("attacking_unit")
        pending = self._csm_find_pending_reaction("FESTERING MIASMA", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if attacking_unit is None:
                attacking_unit = pending.get("attacking_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: FESTERING MIASMA: no target unit provided")
            return False

        root = self._csm_root(unit)
        attacker_root = self._csm_root(attacking_unit)
        if root is None or attacker_root is None or not self._is_pactbound_zealots_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: FESTERING MIASMA: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: FESTERING MIASMA: can only be used in your opponent's Shooting phase")
            return False
        if self._csm_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: FESTERING MIASMA: attacking unit must be an enemy unit")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: FESTERING MIASMA: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: FESTERING MIASMA: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: FESTERING MIASMA: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: FESTERING MIASMA: target must be HERETIC ASTARTES")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        owner_id = str(getattr(active_player, "id", "") or "")
        effect_owner_id = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        mark = self._pactbound_mark_for_unit(root)
        try:
            members = list(root.get_attached_unit_members() or [])
        except (AttributeError, TypeError, ValueError):
            members = [root]
        if root not in members:
            members.append(root)
        for member in members:
            if member is None:
                continue
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["opponent_shooting_phase_stealth_active"] = True
            sr["opponent_shooting_phase_stealth_owner"] = owner_id
            sr["opponent_shooting_phase_stealth_turn"] = int(turn or 0)
            sr["opponent_shooting_phase_stealth_source"] = str(getattr(stratagem, "name", "FESTERING MIASMA") or "FESTERING MIASMA")
            sr["opponent_shooting_phase_stealth_expires_phase"] = "SHOOTING_PHASE"
            sr["pactbound_festering_miasma_active"] = True
            sr["pactbound_festering_miasma_phase"] = "SHOOTING_PHASE"
            sr["pactbound_festering_miasma_turn_owner"] = effect_owner_id
            sr["pactbound_festering_miasma_turn"] = int(turn or 0)
            sr["pactbound_festering_miasma_source"] = str(getattr(stratagem, "name", "FESTERING MIASMA") or "FESTERING MIASMA")
            if mark == "NURGLE":
                sr["pactbound_festering_miasma_targeting_range"] = 18
            else:
                sr.pop("pactbound_festering_miasma_targeting_range", None)
            member.special_rules = sr

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: FESTERING MIASMA: %s gains Stealth%s until end of phase.",
            getattr(root, "name", "Unit"),
            " and an 18\" ranged targeting cap" if mark == "NURGLE" else "",
        )
        return True

    def _use_pactbound_torpefying_refrain(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("TORPEFYING REFRAIN", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: TORPEFYING REFRAIN: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_pactbound_zealots_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: TORPEFYING REFRAIN: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: TORPEFYING REFRAIN: not your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: TORPEFYING REFRAIN: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: TORPEFYING REFRAIN: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: TORPEFYING REFRAIN: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: TORPEFYING REFRAIN: target must be HERETIC ASTARTES")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_pactbound_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: TORPEFYING REFRAIN: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._PACTBOUND_TORPEFYING_REFRAIN_PREFIX,
            source=stratagem.name or "TORPEFYING REFRAIN",
            player=self.player,
            game=self.game,
            track_phase=False,
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TORPEFYING REFRAIN: %s can charge after Falling Back this turn%s.",
            getattr(root, "name", "Unit"),
            " and can shoot/charge after Advancing or Falling Back" if self._pactbound_mark_for_unit(root) == "SLAANESH" else "",
        )
        return True

    def _use_pactbound_eternal_hate(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        attacking_unit = kwargs.get("attacking_unit")
        pending = self._csm_find_pending_reaction("ETERNAL HATE", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if attacking_unit is None:
                attacking_unit = pending.get("attacking_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: ETERNAL HATE: no target unit provided")
            return False

        root = self._csm_root(unit)
        attacker_root = self._csm_root(attacking_unit)
        if root is None or attacker_root is None or not self._is_pactbound_zealots_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: ETERNAL HATE: wrong phase")
            return False
        if self._csm_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: ETERNAL HATE: attacking unit must be an enemy unit")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: ETERNAL HATE: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: ETERNAL HATE: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: ETERNAL HATE: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: ETERNAL HATE: target must be HERETIC ASTARTES")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_pactbound_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: ETERNAL HATE: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._PACTBOUND_ETERNAL_HATE_PREFIX,
            source=stratagem.name or "ETERNAL HATE",
            player=self.player,
            game=self.game,
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ETERNAL HATE: %s gains melee fight-on-death until end of phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_renegade_warband_corrupted_munitions(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("CORRUPTED MUNITIONS", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: CORRUPTED MUNITIONS: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_renegade_warband_detachment():
            return False
        phase_name = str(
            kwargs.get("phase_name")
            or (pending.get("phase_name") if isinstance(pending, dict) else "")
            or self._current_phase_name
            or ""
        ).strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: CORRUPTED MUNITIONS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: CORRUPTED MUNITIONS: not your Shooting phase")
            return False
        if candidates and not self._renegade_warband_unit_in_candidates(root, candidates):
            logger.error("ERROR: CORRUPTED MUNITIONS: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: CORRUPTED MUNITIONS: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: CORRUPTED MUNITIONS: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: CORRUPTED MUNITIONS: target must be HERETIC ASTARTES")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_renegade_warband_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: CORRUPTED MUNITIONS: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._RENEGADE_WARBAND_CORRUPTED_MUNITIONS_PREFIX,
            source=stratagem.name or "CORRUPTED MUNITIONS",
            player=self.player,
            game=self.game,
            extra_state={f"{mgr._RENEGADE_WARBAND_CORRUPTED_MUNITIONS_PREFIX}_ap_bonus": 1},
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CORRUPTED MUNITIONS: %s improves the AP of ranged attacks by 1 this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_renegade_warband_never_outgunned(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("NEVER OUTGUNNED", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: NEVER OUTGUNNED: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_renegade_warband_detachment():
            return False
        phase_name = str(
            kwargs.get("phase_name")
            or (pending.get("phase_name") if isinstance(pending, dict) else "")
            or self._current_phase_name
            or ""
        ).strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: NEVER OUTGUNNED: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: NEVER OUTGUNNED: not your Shooting phase")
            return False
        if candidates and not self._renegade_warband_unit_in_candidates(root, candidates):
            logger.error("ERROR: NEVER OUTGUNNED: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: NEVER OUTGUNNED: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: NEVER OUTGUNNED: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: NEVER OUTGUNNED: target must be HERETIC ASTARTES")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        choice_key = self._renegade_warband_never_outgunned_choice_key(
            kwargs.get("choice_key") or kwargs.get("key") or kwargs.get("choice") or kwargs.get("selection")
        )
        if choice_key:
            outcome = self.apply_renegade_warband_never_outgunned(
                root,
                choice_key=choice_key,
                phase_name=phase_name,
                source=stratagem.name or "NEVER OUTGUNNED",
            )
            if not isinstance(outcome, dict) or not bool(outcome.get("ok", False)):
                logger.error("ERROR: NEVER OUTGUNNED: invalid choice")
                return False
            self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(
                "INFO: NEVER OUTGUNNED: %s gains [%s] on %s weapons this phase.",
                getattr(root, "name", "Unit"),
                str(outcome.get("keyword", choice_key) or choice_key),
                str(outcome.get("attack_type", "") or "selected"),
            )
            return True

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        queue = getattr(self.game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for request in list(queue.list() or []):
                if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(request, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "renegade_warband_never_outgunned_choice":
                    continue
                if str(ctx.get("unit_id", "") or "") == str(get_entity_id(root) or ""):
                    return True

        choice_keys = ["LETHAL_HITS", "SUSTAINED_HITS_1"]
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Never Outgunned: select a weapon keyword.",
            player_id=getattr(self.player, "id", None),
            options=[
                DecisionOption.create(
                    self._renegade_warband_never_outgunned_choice_label(choice) or choice,
                    payload={
                        "choice_key": choice,
                        "unit_id": get_entity_id(root),
                    },
                )
                for choice in choice_keys
            ],
            context={
                "ability": "renegade_warband_never_outgunned_choice",
                "ability_name": str(stratagem.name or "Never Outgunned"),
                "unit_id": get_entity_id(root),
                "army_id": get_entity_id(getattr(self.player, "army", None)),
                "phase_name": "Shooting phase" if phase_name == "shooting phase" else "Fight phase",
                "turn": int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0,
                "turn_owner_id": str(getattr(active_player, "id", "") or getattr(self.player, "id", "") or ""),
                "allowed_choice_keys": list(choice_keys),
                "optional": False,
            },
        )
        self.game.request_decision(request)
        logger.info(
            "INFO: NEVER OUTGUNNED: %s must select Lethal Hits or Sustained Hits 1.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_renegade_warband_vengeful_destruction(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("VENGEFUL DESTRUCTION", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: VENGEFUL DESTRUCTION: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_renegade_warband_detachment():
            return False
        phase_name = str(
            kwargs.get("phase_name")
            or (pending.get("phase_name") if isinstance(pending, dict) else "")
            or self._current_phase_name
            or ""
        ).strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: VENGEFUL DESTRUCTION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: VENGEFUL DESTRUCTION: not your Shooting phase")
            return False
        if candidates and not self._renegade_warband_unit_in_candidates(root, candidates):
            logger.error("ERROR: VENGEFUL DESTRUCTION: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: VENGEFUL DESTRUCTION: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: VENGEFUL DESTRUCTION: target cannot be selected")
            return False
        if not (self._is_heretic_astartes_infantry(root) or self._is_heretic_astartes_mounted(root)):
            logger.error("ERROR: VENGEFUL DESTRUCTION: target must be HERETIC ASTARTES INFANTRY or MOUNTED")
            return False
        if self._is_damned_unit(root):
            logger.error("ERROR: VENGEFUL DESTRUCTION: DAMNED units cannot be targeted")
            return False
        mgr = self._get_chaos_space_marines_mgr()
        if not str(getattr(mgr, "renegade_warband_vendetta_target_unit_id", "") or "").strip():
            logger.error("ERROR: VENGEFUL DESTRUCTION: there is no active Vendetta target")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        set_state = getattr(mgr, "_set_renegade_warband_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: VENGEFUL DESTRUCTION: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._RENEGADE_WARBAND_VENGEFUL_DESTRUCTION_PREFIX,
            source=stratagem.name or "VENGEFUL DESTRUCTION",
            player=self.player,
            game=self.game,
            extra_state={f"{mgr._RENEGADE_WARBAND_VENGEFUL_DESTRUCTION_PREFIX}_wound_bonus": 1},
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: VENGEFUL DESTRUCTION: %s gains +1 to wound against the Vendetta target this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_renegade_warband_reavers_reaction(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
        pending = self._csm_find_pending_reaction("REAVERS' REACTION", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if attacking_unit is None:
                attacking_unit = pending.get("attacking_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: REAVERS' REACTION: no target unit provided")
            return False

        root = self._csm_root(unit)
        attacker_root = self._csm_root(attacking_unit)
        if root is None or attacker_root is None or not self._is_renegade_warband_detachment():
            return False
        phase_name = str(
            kwargs.get("phase_name")
            or (pending.get("phase_name") if isinstance(pending, dict) else "")
            or self._current_phase_name
            or ""
        ).strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: REAVERS' REACTION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: REAVERS' REACTION: not opponent's Shooting phase")
            return False
        if self._csm_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: REAVERS' REACTION: attacking unit must be enemy")
            return False
        if candidates and not self._renegade_warband_unit_in_candidates(root, candidates):
            logger.error("ERROR: REAVERS' REACTION: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: REAVERS' REACTION: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: REAVERS' REACTION: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: REAVERS' REACTION: target must be HERETIC ASTARTES")
            return False
        if self._csm_has_keyword(root, "MONSTER") or self._csm_has_keyword(root, "VEHICLE"):
            logger.error("ERROR: REAVERS' REACTION: target cannot be a MONSTER or VEHICLE")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        try:
            move_max = int(dice_module.get_roll("D6") or 0)
        except Exception:
            move_max = 0
        if move_max <= 0:
            logger.error("ERROR: REAVERS' REACTION: invalid movement distance")
            return False
        req = None
        if self.game is not None:
            req = self.game._queue_reactive_move_movement_decision(
                player=self.player,
                unit=root,
                max_distance=int(move_max),
                kind="renegade_warband_reavers_reaction",
                movement_type="reactive",
                source=stratagem.name,
                attacker_unit=attacker_root,
            )
        if req is None:
            logger.error("ERROR: REAVERS' REACTION: failed to queue movement decision")
            return False

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: REAVERS' REACTION: %s can make a Normal move of up to %d\".",
            getattr(root, "name", "Unit"),
            int(move_max),
        )
        return True

    def _use_renegade_warband_renegade_claim(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        objective = kwargs.get("objective") or kwargs.get("objective_marker")
        objective_candidates = list(kwargs.get("objective_candidates") or [])
        objective_candidates_by_unit = dict(kwargs.get("objective_candidates_by_unit") or {})
        pending = self._csm_find_pending_reaction("RENEGADE CLAIM", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if not objective_candidates_by_unit:
                objective_candidates_by_unit = dict(pending.get("objective_candidates_by_unit") or {})
            if not objective_candidates:
                objective_candidates = list(pending.get("objective_candidates") or [])
            if objective is None:
                objective = pending.get("objective") or pending.get("objective_marker")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: RENEGADE CLAIM: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_renegade_warband_detachment():
            return False
        phase_name = str(
            kwargs.get("phase_name")
            or (pending.get("phase_name") if isinstance(pending, dict) else "")
            or self._current_phase_name
            or ""
        ).strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: RENEGADE CLAIM: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: RENEGADE CLAIM: not your Movement phase")
            return False
        if candidates and not self._renegade_warband_unit_in_candidates(root, candidates):
            logger.error("ERROR: RENEGADE CLAIM: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: RENEGADE CLAIM: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: RENEGADE CLAIM: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: RENEGADE CLAIM: target must be HERETIC ASTARTES")
            return False

        if len(candidates) == 1 and not objective_candidates and objective_candidates_by_unit:
            objective_candidates = list(objective_candidates_by_unit.get(self._csm_sort_key(root)) or [])
        if not objective_candidates:
            objective_candidates = self._renegade_warband_controlled_objective_candidates(root)
        if objective is None and len(objective_candidates) == 1:
            objective = objective_candidates[0]
        if objective is None:
            logger.error("ERROR: RENEGADE CLAIM: no objective marker selected")
            return False

        selected_objective = None
        selected_id = str(getattr(objective, "id", "") or get_entity_id(objective) or "")
        selected_location = getattr(objective, "location", None)
        selected_location_id = str(get_entity_id(selected_location) or "") if selected_location is not None else ""
        for candidate in list(objective_candidates or []):
            candidate_id = str(getattr(candidate, "id", "") or get_entity_id(candidate) or "")
            candidate_location = getattr(candidate, "location", None)
            candidate_location_id = str(get_entity_id(candidate_location) or "") if candidate_location is not None else ""
            if objective is candidate:
                selected_objective = candidate
                break
            if selected_id and candidate_id and selected_id == candidate_id:
                selected_objective = candidate
                break
            if selected_location_id and candidate_location_id and selected_location_id == candidate_location_id:
                selected_objective = candidate
                break
        if selected_objective is None:
            logger.error("ERROR: RENEGADE CLAIM: selected objective marker is not eligible")
            return False
        objective_location = getattr(selected_objective, "location", None)
        if objective_location is None:
            logger.error("ERROR: RENEGADE CLAIM: objective marker location unavailable")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        if hasattr(objective_location, "set_sticky_control"):
            objective_location.set_sticky_control(self.player, source="renegade_warband_renegade_claim")
        else:
            objective_location.sticky_controller = self.player
            objective_location.sticky_source = "renegade_warband_renegade_claim"
            objective_location.controlling_player = self.player

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: RENEGADE CLAIM: selected objective remains under your control until broken.")
        return True

    def _use_renegade_warband_undying_hatred(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
        pending = self._csm_find_pending_reaction("UNDYING HATRED", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if attacking_unit is None:
                attacking_unit = pending.get("attacking_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: UNDYING HATRED: no target unit provided")
            return False

        root = self._csm_root(unit)
        attacker_root = self._csm_root(attacking_unit)
        if root is None or attacker_root is None or not self._is_renegade_warband_detachment():
            return False
        phase_name = str(
            kwargs.get("phase_name")
            or (pending.get("phase_name") if isinstance(pending, dict) else "")
            or self._current_phase_name
            or ""
        ).strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: UNDYING HATRED: wrong phase")
            return False
        if self._csm_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: UNDYING HATRED: attacking unit must be enemy")
            return False
        if candidates and not self._renegade_warband_unit_in_candidates(root, candidates):
            logger.error("ERROR: UNDYING HATRED: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: UNDYING HATRED: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: UNDYING HATRED: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: UNDYING HATRED: target must be HERETIC ASTARTES")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr = dict(sr)
        sr["renegade_warband_undying_hatred_active"] = True
        sr["renegade_warband_undying_hatred_threshold"] = 4
        sr["renegade_warband_undying_hatred_expires_phase"] = "FIGHT_PHASE"
        sr["renegade_warband_undying_hatred_source"] = str(stratagem.name or "UNDYING HATRED")
        sr["renegade_warband_undying_hatred_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        current_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        sr["renegade_warband_undying_hatred_turn_owner"] = str(
            getattr(current_player, "id", "") or getattr(self.player, "id", "") or ""
        )
        root.special_rules = sr
        invalidate = getattr(root, "_invalidate_ability_cache", None)
        if callable(invalidate):
            invalidate()

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: UNDYING HATRED: %s gains melee fight-on-death on 4+ this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_renegade_raiders_warpcharged_engines(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("WARPCHARGED ENGINES", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: WARPCHARGED ENGINES: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_renegade_raiders_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: WARPCHARGED ENGINES: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: WARPCHARGED ENGINES: not your turn")
            return False
        if candidates and not self._renegade_raiders_unit_in_candidates(root, candidates):
            logger.error("ERROR: WARPCHARGED ENGINES: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: WARPCHARGED ENGINES: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: WARPCHARGED ENGINES: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: WARPCHARGED ENGINES: target must be HERETIC ASTARTES")
            return False
        if not (self._csm_has_keyword(root, "TRANSPORT") or self._is_heretic_astartes_mounted(root)):
            logger.error("ERROR: WARPCHARGED ENGINES: target must be a TRANSPORT or MOUNTED unit")
            return False
        if bool(getattr(getattr(root, "round_state", None), "moved_this_round", False)):
            logger.error("ERROR: WARPCHARGED ENGINES: target has already been selected to move")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        effects = list(sr.get("advance_no_roll_effects", []) or [])
        effects = [
            entry
            for entry in effects
            if not (
                isinstance(entry, dict)
                and str(entry.get("tag", "") or "") == "stratagem:renegade_raiders_warpcharged_engines"
            )
        ]
        effects.append(
            {
                "distance": 6,
                "source": str(getattr(stratagem, "name", "WARPCHARGED ENGINES") or "WARPCHARGED ENGINES"),
                "tag": "stratagem:renegade_raiders_warpcharged_engines",
                "expires_phase": "MOVEMENT_PHASE",
            }
        )
        sr["advance_no_roll_effects"] = effects
        root.special_rules = sr

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: WARPCHARGED ENGINES: %s adds 6\" to its Move instead of rolling to Advance this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_renegade_raiders_reavers_haste(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("REAVERS' HASTE", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: REAVERS' HASTE: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_renegade_raiders_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: REAVERS' HASTE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: REAVERS' HASTE: not your turn")
            return False
        if candidates and not self._renegade_raiders_unit_in_candidates(root, candidates):
            logger.error("ERROR: REAVERS' HASTE: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: REAVERS' HASTE: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: REAVERS' HASTE: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: REAVERS' HASTE: target must be HERETIC ASTARTES")
            return False
        if not (self._is_heretic_astartes_infantry(root) or self._is_heretic_astartes_mounted(root)):
            logger.error("ERROR: REAVERS' HASTE: target must be INFANTRY or MOUNTED")
            return False
        if bool(getattr(getattr(root, "round_state", None), "attempted_charge_this_round", False)):
            logger.error("ERROR: REAVERS' HASTE: target has already attempted a charge this turn")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_renegade_raiders_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: REAVERS' HASTE: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._RENEGADE_RAIDERS_REAVERS_HASTE_PREFIX,
            source=stratagem.name or "REAVERS' HASTE",
            player=self.player,
            game=self.game,
            extra_state={f"{mgr._RENEGADE_RAIDERS_REAVERS_HASTE_PREFIX}_charge_roll_bonus": 1},
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: REAVERS' HASTE: %s can charge after Advancing this phase and gains +1 to Charge rolls against objective targets.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_renegade_raiders_ruinous_raid(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("RUINOUS RAID", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: RUINOUS RAID: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_renegade_raiders_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: RUINOUS RAID: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: RUINOUS RAID: not your turn")
            return False
        if candidates and not self._renegade_raiders_unit_in_candidates(root, candidates):
            logger.error("ERROR: RUINOUS RAID: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: RUINOUS RAID: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: RUINOUS RAID: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: RUINOUS RAID: target must be HERETIC ASTARTES")
            return False
        round_state = getattr(root, "round_state", None)
        if not bool(getattr(round_state, "disembarked_this_round", False)):
            logger.error("ERROR: RUINOUS RAID: target must have disembarked from a TRANSPORT this turn")
            return False
        if phase_name == "shooting phase" and bool(getattr(round_state, "shot_this_round", False)):
            logger.error("ERROR: RUINOUS RAID: target has already been selected to shoot")
            return False
        if phase_name == "fight phase" and bool(getattr(round_state, "fought_this_phase", False)):
            logger.error("ERROR: RUINOUS RAID: target has already been selected to fight")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_renegade_raiders_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: RUINOUS RAID: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._RENEGADE_RAIDERS_RUINOUS_RAID_PREFIX,
            source=stratagem.name or "RUINOUS RAID",
            player=self.player,
            game=self.game,
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: RUINOUS RAID: %s re-rolls Hit and Wound rolls against objective targets until end of phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_renegade_raiders_scour_and_seize(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("SCOUR AND SEIZE", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SCOUR AND SEIZE: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_renegade_raiders_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: SCOUR AND SEIZE: wrong phase")
            return False
        if candidates and not self._renegade_raiders_unit_in_candidates(root, candidates):
            logger.error("ERROR: SCOUR AND SEIZE: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: SCOUR AND SEIZE: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: SCOUR AND SEIZE: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: SCOUR AND SEIZE: target must be HERETIC ASTARTES")
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: SCOUR AND SEIZE: target has already been selected to fight")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_renegade_raiders_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: SCOUR AND SEIZE: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._RENEGADE_RAIDERS_SCOUR_AND_SEIZE_PREFIX,
            source=stratagem.name or "SCOUR AND SEIZE",
            player=self.player,
            game=self.game,
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SCOUR AND SEIZE: %s gains Precision against objective targets until end of phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_renegade_raiders_unfailingly_obdurate(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        attacking_unit = kwargs.get("attacking_unit")
        pending = self._csm_find_pending_reaction("UNFAILINGLY OBDURATE", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if attacking_unit is None:
                attacking_unit = pending.get("attacking_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: UNFAILINGLY OBDURATE: no target unit provided")
            return False

        root = self._csm_root(unit)
        attacker_root = self._csm_root(attacking_unit)
        if root is None or attacker_root is None or not self._is_renegade_raiders_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: UNFAILINGLY OBDURATE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: UNFAILINGLY OBDURATE: only available in your opponent's phase")
            return False
        if self._csm_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: UNFAILINGLY OBDURATE: attacking unit must be an enemy unit")
            return False
        if candidates and not self._renegade_raiders_unit_in_candidates(root, candidates):
            logger.error("ERROR: UNFAILINGLY OBDURATE: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: UNFAILINGLY OBDURATE: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: UNFAILINGLY OBDURATE: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: UNFAILINGLY OBDURATE: target must be HERETIC ASTARTES")
            return False
        if self._is_damned_unit(root):
            logger.error("ERROR: UNFAILINGLY OBDURATE: DAMNED units cannot be targeted")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        if not self._apply_armour_of_contempt(root, attacker_root, amount=1):
            logger.error("ERROR: UNFAILINGLY OBDURATE: failed to apply AP reduction")
            return False

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: UNFAILINGLY OBDURATE: attacks from %s worsen AP by 1 against %s for the rest of this attack sequence.",
            getattr(attacker_root, "name", "Enemy Unit"),
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_renegade_raiders_opportunistic_raiders(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("OPPORTUNISTIC RAIDERS", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: OPPORTUNISTIC RAIDERS: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_renegade_raiders_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: OPPORTUNISTIC RAIDERS: wrong phase")
            return False
        if candidates and not self._renegade_raiders_unit_in_candidates(root, candidates):
            logger.error("ERROR: OPPORTUNISTIC RAIDERS: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: OPPORTUNISTIC RAIDERS: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: OPPORTUNISTIC RAIDERS: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: OPPORTUNISTIC RAIDERS: target must be HERETIC ASTARTES")
            return False
        round_state = getattr(root, "round_state", None)
        was_eligible = bool(getattr(round_state, "eligible_to_fight_this_phase", False))
        if not was_eligible and bool(getattr(round_state, "fought_this_phase", False)):
            was_eligible = True
        if not was_eligible:
            logger.error("ERROR: OPPORTUNISTIC RAIDERS: target must have been eligible to fight this phase")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        engaged = self._csm_unit_is_engaged(root)
        movement_type = "fall_back" if engaged else "move"
        max_distance = self._renegade_raiders_normal_move_distance(root)
        if not engaged:
            max_distance = 12 if self._is_heretic_astartes_mounted(root) else 6
        if int(max_distance or 0) <= 0:
            logger.error("ERROR: OPPORTUNISTIC RAIDERS: movement distance is invalid")
            return False

        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if not callable(queue_move):
            logger.error("ERROR: OPPORTUNISTIC RAIDERS: reactive move queue unavailable")
            return False
        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=int(max_distance),
            kind="opportunistic_raiders",
            movement_type=movement_type,
            source=stratagem.name,
            allow_skip=True,
        )
        if request is None:
            logger.error("ERROR: OPPORTUNISTIC RAIDERS: failed to queue movement decision")
            return False

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: OPPORTUNISTIC RAIDERS: %s can make a %s move up to %d\".",
            getattr(root, "name", "Unit"),
            "Fall Back" if engaged else "Normal",
            int(max_distance),
        )
        return True

    def _use_veterans_black_crusade(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("BLACK CRUSADE", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: BLACK CRUSADE: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_veterans_of_the_long_war_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: BLACK CRUSADE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: BLACK CRUSADE: not your turn")
            return False
        if candidates and not self._veterans_unit_in_candidates(root, candidates):
            logger.error("ERROR: BLACK CRUSADE: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: BLACK CRUSADE: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: BLACK CRUSADE: target cannot be selected")
            return False
        if not (
            self._is_heretic_astartes_infantry(root)
            or self._is_heretic_astartes_mounted(root)
        ):
            logger.error("ERROR: BLACK CRUSADE: target must be HERETIC ASTARTES INFANTRY or MOUNTED")
            return False
        if self._is_damned_unit(root):
            logger.error("ERROR: BLACK CRUSADE: DAMNED units cannot be targeted")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_veterans_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: BLACK CRUSADE: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._VETERANS_BLACK_CRUSADE_PREFIX,
            source=stratagem.name or "BLACK CRUSADE",
            player=self.player,
            game=self.game,
            track_phase=False,
            extra_state={
                mgr._VETERANS_BLACK_CRUSADE_DAMAGE_KEY: 0,
                mgr._VETERANS_BLACK_CRUSADE_DAMAGE_CAP_KEY: 6,
            },
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: BLACK CRUSADE: %s can shoot after Advancing or Falling Back this turn and gains conditional bolt Devastating Wounds.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_veterans_bringers_of_despair(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("BRINGERS OF DESPAIR", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: BRINGERS OF DESPAIR: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_veterans_of_the_long_war_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: BRINGERS OF DESPAIR: wrong phase")
            return False
        eligible = candidates or self._veterans_bringers_of_despair_candidates()
        if eligible and not self._veterans_unit_in_candidates(root, eligible):
            logger.error("ERROR: BRINGERS OF DESPAIR: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: BRINGERS OF DESPAIR: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: BRINGERS OF DESPAIR: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: BRINGERS OF DESPAIR: target must be HERETIC ASTARTES")
            return False
        if self._is_damned_unit(root):
            logger.error("ERROR: BRINGERS OF DESPAIR: DAMNED units cannot be targeted")
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: BRINGERS OF DESPAIR: target has already fought this phase")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_veterans_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: BRINGERS OF DESPAIR: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._VETERANS_BRINGERS_OF_DESPAIR_PREFIX,
            source=stratagem.name or "BRINGERS OF DESPAIR",
            player=self.player,
            game=self.game,
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: BRINGERS OF DESPAIR: %s gains Fights First until end of phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_veterans_contemptuous_disregard(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        attacking_unit = kwargs.get("attacking_unit")
        pending = self._csm_find_pending_reaction("CONTEMPTUOUS DISREGARD", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if attacking_unit is None:
                attacking_unit = pending.get("attacking_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: CONTEMPTUOUS DISREGARD: no target unit provided")
            return False

        root = self._csm_root(unit)
        attacker_root = self._csm_root(attacking_unit)
        if root is None or attacker_root is None or not self._is_veterans_of_the_long_war_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: CONTEMPTUOUS DISREGARD: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is self.player:
            logger.error("ERROR: CONTEMPTUOUS DISREGARD: only available in your opponent's Shooting phase")
            return False
        if self._csm_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: CONTEMPTUOUS DISREGARD: attacking unit must be an enemy unit")
            return False
        if candidates and not self._veterans_unit_in_candidates(root, candidates):
            logger.error("ERROR: CONTEMPTUOUS DISREGARD: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: CONTEMPTUOUS DISREGARD: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: CONTEMPTUOUS DISREGARD: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: CONTEMPTUOUS DISREGARD: target must be HERETIC ASTARTES")
            return False
        if self._is_damned_unit(root):
            logger.error("ERROR: CONTEMPTUOUS DISREGARD: DAMNED units cannot be targeted")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        if not self._apply_armour_of_contempt(root, attacker_root, amount=1):
            logger.error("ERROR: CONTEMPTUOUS DISREGARD: failed to apply AP reduction")
            return False

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CONTEMPTUOUS DISREGARD: attacks from %s worsen AP by 1 against %s for the rest of this attack sequence.",
            getattr(attacker_root, "name", "Enemy Unit"),
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_veterans_endless_ire(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit") or kwargs.get("focus_target")
        destroyed_unit = kwargs.get("destroyed_unit")
        pending = self._csm_find_pending_reaction("ENDLESS IRE", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if enemy_unit is None:
                enemy_unit = pending.get("enemy_unit") or pending.get("target_enemy_unit") or pending.get("focus_target")
            if destroyed_unit is None:
                destroyed_unit = pending.get("destroyed_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: ENDLESS IRE: no source unit provided")
            return False

        root = self._csm_root(unit)
        destroyed_root = self._csm_root(destroyed_unit)
        if root is None or not self._is_veterans_of_the_long_war_detachment():
            return False
        if candidates and not self._veterans_unit_in_candidates(root, candidates):
            logger.error("ERROR: ENDLESS IRE: source unit is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: ENDLESS IRE: source unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: ENDLESS IRE: source unit cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root) or not self._csm_has_keyword(root, "CHARACTER"):
            logger.error("ERROR: ENDLESS IRE: source unit must be a HERETIC ASTARTES CHARACTER")
            return False
        if self._is_damned_unit(root):
            logger.error("ERROR: ENDLESS IRE: DAMNED units cannot be targeted")
            return False

        mgr = self._get_chaos_space_marines_mgr()
        focus_target_id = str(getattr(mgr, "veterans_focus_of_hatred_target_unit_id", "") or "").strip()
        if destroyed_root is None:
            logger.error("ERROR: ENDLESS IRE: destroyed focus target was not provided")
            return False
        if str(get_entity_id(destroyed_root) or "").strip() != focus_target_id:
            logger.error("ERROR: ENDLESS IRE: trigger unit is not your current Focus of Hatred")
            return False
        if self._csm_owned_by_player(destroyed_root, self.player):
            logger.error("ERROR: ENDLESS IRE: destroyed unit must be an enemy unit")
            return False

        source_unit_id = str(get_entity_id(root) or "")
        candidate_enemy_units = list(
            getattr(mgr, "veterans_endless_ire_candidate_enemy_units", lambda *_a, **_k: [])(
                source_unit_id,
                game=self.game,
                player=self.player,
            )
            or []
        )
        if not candidate_enemy_units:
            logger.error("ERROR: ENDLESS IRE: no visible enemy units within 12\" of the source unit")
            return False
        enemy_root = self._csm_root(enemy_unit)
        if enemy_root is not None:
            validate_target = getattr(mgr, "veterans_endless_ire_target_is_valid", None) if mgr is not None else None
            if not callable(validate_target) or not bool(
                validate_target(
                    source_unit_id,
                    str(get_entity_id(enemy_root) or ""),
                    game=self.game,
                    player=self.player,
                )
            ):
                logger.error("ERROR: ENDLESS IRE: selected enemy unit is invalid")
                return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        select_target = getattr(mgr, "select_veterans_endless_ire_target", None) if mgr is not None else None
        if enemy_root is not None:
            if not callable(select_target):
                logger.error("ERROR: ENDLESS IRE: detachment target selection helper is unavailable")
                return False
            outcome = select_target(
                source_unit_id,
                str(get_entity_id(enemy_root) or ""),
                game=self.game,
                player=self.player,
            )
            if not isinstance(outcome, dict) or not bool(outcome.get("ok", False)):
                logger.error("ERROR: ENDLESS IRE: failed to select a new focus target")
                return False
            self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(
                "INFO: ENDLESS IRE: %s designates %s as the new Focus of Hatred.",
                getattr(root, "name", "Unit"),
                str(outcome.get("target_name", "Enemy Unit") or "Enemy Unit"),
            )
            return True

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        queue = getattr(self.game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for request in list(queue.list() or []):
                if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(request, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "veterans_endless_ire_focus_target":
                    continue
                if str(ctx.get("source_unit_id", "") or "") == source_unit_id:
                    return True

        options = [
            DecisionOption.create(
                str(getattr(candidate, "name", "Enemy Unit") or "Enemy Unit"),
                payload={
                    "source_unit_id": source_unit_id,
                    "target_unit_id": str(get_entity_id(candidate) or ""),
                    "army_id": get_entity_id(getattr(self.player, "army", None)),
                },
            )
            for candidate in list(candidate_enemy_units or [])
            if str(get_entity_id(candidate) or "")
        ]
        if not options:
            logger.error("ERROR: ENDLESS IRE: no valid enemy choices were generated")
            return False

        current_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip() or "Any phase"
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Endless Ire: select a new focus of hatred.",
            player_id=getattr(self.player, "id", None),
            options=options,
            context={
                "ability": "veterans_endless_ire_focus_target",
                "ability_name": str(stratagem.name or "Endless Ire"),
                "source_unit_id": source_unit_id,
                "army_id": get_entity_id(getattr(self.player, "army", None)),
                "candidate_unit_ids": [str(get_entity_id(candidate) or "") for candidate in list(candidate_enemy_units or [])],
                "phase_name": phase_name.upper().replace(" ", "_"),
                "turn": int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0,
                "turn_owner_id": str(getattr(current_player, "id", "") or getattr(self.player, "id", "") or ""),
                "optional": False,
            },
        )
        self.game.request_decision(request)
        logger.info(
            "INFO: ENDLESS IRE: %s must select a new Focus of Hatred.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_veterans_let_the_galaxy_burn(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._csm_find_pending_reaction("LET THE GALAXY BURN", unit=unit)
        if pending is not None and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: LET THE GALAXY BURN: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None or not self._is_veterans_of_the_long_war_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: LET THE GALAXY BURN: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: LET THE GALAXY BURN: not your turn")
            return False
        if candidates and not self._veterans_unit_in_candidates(root, candidates):
            logger.error("ERROR: LET THE GALAXY BURN: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: LET THE GALAXY BURN: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: LET THE GALAXY BURN: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: LET THE GALAXY BURN: target must be HERETIC ASTARTES")
            return False
        if self._csm_has_keyword(root, "TZEENTCH"):
            logger.error("ERROR: LET THE GALAXY BURN: TZEENTCH units cannot be targeted")
            return False
        if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: LET THE GALAXY BURN: target has already been selected to shoot")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._get_chaos_space_marines_mgr()
        set_state = getattr(mgr, "_set_veterans_effect_state", None) if mgr is not None else None
        if not callable(set_state):
            logger.error("ERROR: LET THE GALAXY BURN: detachment effect state helper is unavailable")
            return False
        set_state(
            root,
            prefix=mgr._VETERANS_LET_THE_GALAXY_BURN_PREFIX,
            source=stratagem.name or "LET THE GALAXY BURN",
            player=self.player,
            game=self.game,
            extra_state={f"{mgr._VETERANS_LET_THE_GALAXY_BURN_PREFIX}_torrent_attacks": 6},
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: LET THE GALAXY BURN: %s gains Ignores Cover on ranged weapons and Torrent attacks become 6 this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_veterans_millennia_of_experience(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        enemy_unit = kwargs.get("moving_unit") or kwargs.get("enemy_unit")
        action = kwargs.get("action")
        pending = self._csm_find_pending_reaction("MILLENNIA OF EXPERIENCE", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if enemy_unit is None:
                enemy_unit = pending.get("moving_unit") or pending.get("enemy_unit")
            if action is None:
                action = pending.get("action")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: MILLENNIA OF EXPERIENCE: no target unit provided")
            return False

        root = self._csm_root(unit)
        enemy_root = self._csm_root(enemy_unit)
        if root is None or enemy_root is None or not self._is_veterans_of_the_long_war_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: MILLENNIA OF EXPERIENCE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: MILLENNIA OF EXPERIENCE: not opponent's Movement phase")
            return False
        action_key = str(action or "").strip().lower().replace(" ", "_")
        if action_key not in {"move", "normal", "normal_move", "advance", "fall_back", "fallback"}:
            logger.error("ERROR: MILLENNIA OF EXPERIENCE: invalid trigger action")
            return False
        if self._csm_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: MILLENNIA OF EXPERIENCE: trigger unit must be an enemy unit")
            return False
        eligible = candidates or self._veterans_millennia_of_experience_candidates(enemy_unit=enemy_root)
        if eligible and not self._veterans_unit_in_candidates(root, eligible):
            logger.error("ERROR: MILLENNIA OF EXPERIENCE: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: MILLENNIA OF EXPERIENCE: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: MILLENNIA OF EXPERIENCE: target cannot be selected")
            return False
        if not (
            self._is_heretic_astartes_infantry(root)
            or self._is_heretic_astartes_mounted(root)
        ):
            logger.error("ERROR: MILLENNIA OF EXPERIENCE: target must be HERETIC ASTARTES INFANTRY or MOUNTED")
            return False
        if self._is_damned_unit(root):
            logger.error("ERROR: MILLENNIA OF EXPERIENCE: DAMNED units cannot be targeted")
            return False
        if self._csm_unit_is_engaged(root):
            logger.error("ERROR: MILLENNIA OF EXPERIENCE: target must not be within Engagement Range")
            return False
        queue_move = getattr(getattr(self, "game", None), "_queue_reactive_move_movement_decision", None)
        if not callable(queue_move):
            logger.error("ERROR: MILLENNIA OF EXPERIENCE: reactive move queue unavailable")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=6,
            kind="veterans_millennia_of_experience",
            movement_type="reactive",
            reactive_movement_type="move",
            source=str(getattr(stratagem, "name", "") or "MILLENNIA OF EXPERIENCE"),
            moving_unit=enemy_root,
            attacker_unit=enemy_root,
            allow_skip=True,
            extra_context={"veterans_millennia_of_experience_trigger_unit_id": str(get_entity_id(enemy_root) or "")},
        )
        if request is None:
            logger.error("ERROR: MILLENNIA OF EXPERIENCE: failed to queue reactive move")
            return False

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MILLENNIA OF EXPERIENCE: %s can make a reactive Normal move up to 6\" after %s finishes moving.",
            getattr(root, "name", "Unit"),
            getattr(enemy_root, "name", "Enemy Unit"),
        )
        return True

    def _use_chaos_space_marines_cabal_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        name_u = self._normalize_stratagem_name(getattr(stratagem, "name", "") or "")
        if name_u == "CHOSEN FOR GLORY":
            return self._use_chaos_cult_chosen_for_glory(stratagem, **kwargs)
        if name_u == "CRAZED FOCUS":
            return self._use_chaos_cult_crazed_focus(stratagem, **kwargs)
        if name_u == "INFERNAL SACRIFICE":
            return self._use_chaos_cult_infernal_sacrifice(stratagem, **kwargs)
        if name_u == "MORTAL THRALLS":
            return self._use_chaos_cult_mortal_thralls(stratagem, **kwargs)
        if name_u == "RECKLESS HASTE":
            return self._use_chaos_cult_reckless_haste(stratagem, **kwargs)
        if name_u == "SELFLESS DEMISE":
            return self._use_chaos_cult_selfless_demise(stratagem, **kwargs)
        if name_u == "BALEFUL BLESSING":
            return self._use_cabal_baleful_blessing(stratagem, **kwargs)
        if name_u == "MUTATION'S CURSE":
            return self._use_cabal_mutations_curse(stratagem, **kwargs)
        if name_u == "NO REST IN DEATH":
            return self._use_cabal_no_rest_in_death(stratagem, **kwargs)
        if name_u == "SHROUD OF CHAOS":
            return self._use_cabal_shroud_of_chaos(stratagem, **kwargs)
        if name_u == "SOULSEEKERS":
            return self._use_cabal_soulseekers(stratagem, **kwargs)
        if name_u == "UNHOLY HASTE":
            return self._use_cabal_unholy_haste(stratagem, **kwargs)
        if name_u == "AUTOSTIMULANTS":
            return self._use_creations_of_bile_autostimulants(stratagem, **kwargs)
        if name_u == "BLACK CRUSADE":
            return self._use_veterans_black_crusade(stratagem, **kwargs)
        if name_u == "BLOODY EXAMPLE":
            return self._use_dread_talons_bloody_example(stratagem, **kwargs)
        if name_u == "BRINGERS OF DESPAIR":
            return self._use_veterans_bringers_of_despair(stratagem, **kwargs)
        if name_u == "BRUTAL ATTRITION":
            return self._use_fellhammer_brutal_attrition(stratagem, **kwargs)
        if name_u == "COILS OF DECEPTION":
            return self._use_deceptors_coils_of_deception(stratagem, **kwargs)
        if name_u == "CONTEMPTUOUS DISREGARD":
            if self._is_veterans_of_the_long_war_detachment():
                return self._use_veterans_contemptuous_disregard(stratagem, **kwargs)
            return None
        if name_u == "CORRUPTED MUNITIONS":
            return self._use_renegade_warband_corrupted_munitions(stratagem, **kwargs)
        if name_u == "DAEMONIC POSSESION":
            return self._use_soulforged_daemonic_possesion(stratagem, **kwargs)
        if name_u == "DEPTHLESS CRUELTY":
            return self._use_dread_talons_depthless_cruelty(stratagem, **kwargs)
        if name_u == "DESPERATE PLEDGE":
            return self._use_soulforged_desperate_pledge(stratagem, **kwargs)
        if name_u == "DETONATOR":
            return self._use_deceptors_detonator(stratagem, **kwargs)
        if name_u == "DELAYED MUTATIONS":
            return self._use_creations_of_bile_delayed_mutations(stratagem, **kwargs)
        if name_u == "DIABOLIC REGENERATION":
            return self._use_creations_of_bile_diabolic_regeneration(stratagem, **kwargs)
        if name_u == "ENDLESS IRE":
            return self._use_veterans_endless_ire(stratagem, **kwargs)
        if name_u == "FEEDING FRENZY":
            return self._use_soulforged_feeding_frenzy(stratagem, **kwargs)
        if name_u == "FROM ALL SIDES":
            return self._use_deceptors_from_all_sides(stratagem, **kwargs)
        if name_u == "GLUT OF SOULS":
            return self._use_soulforged_glut_of_souls(stratagem, **kwargs)
        if name_u == "HARDENED KILLERS":
            return self._use_hurons_marauders_hardened_killers(stratagem, **kwargs)
        if name_u == "LET THE GALAXY BURN":
            return self._use_veterans_let_the_galaxy_burn(stratagem, **kwargs)
        if name_u == "MASTERS ARE WATCHING":
            return self._use_creations_of_bile_masters_are_watching(stratagem, **kwargs)
        if name_u == "MILLENNIA OF EXPERIENCE":
            return self._use_veterans_millennia_of_experience(stratagem, **kwargs)
        if name_u == "AT THE TYRANT'S COMMAND":
            return self._use_hurons_marauders_at_the_tyrants_command(stratagem, **kwargs)
        if name_u == "ENCIRCLING SURGE":
            return self._use_hurons_marauders_encircling_surge(stratagem, **kwargs)
        if name_u == "ETERNAL HATE":
            return self._use_pactbound_eternal_hate(stratagem, **kwargs)
        if name_u == "EYE OF THE GODS":
            return self._use_pactbound_eye_of_the_gods(stratagem, **kwargs)
        if name_u == "FESTERING MIASMA":
            return self._use_pactbound_festering_miasma(stratagem, **kwargs)
        if name_u == "HORRIFIC INCURSION":
            return self._use_nightmare_hunt_horrific_incursion(stratagem, **kwargs)
        if name_u == "MALICIOUS SURGE":
            return self._use_nightmare_hunt_malicious_surge(stratagem, **kwargs)
        if name_u == "NEVER OUTGUNNED":
            return self._use_renegade_warband_never_outgunned(stratagem, **kwargs)
        if name_u == "PERSISTENT ASSAILANTS":
            return self._use_fellhammer_persistent_assailants(stratagem, **kwargs)
        if name_u == "PICK THEM OFF":
            return self._use_deceptors_pick_them_off(stratagem, **kwargs)
        if name_u == "PITILESS CANNONADE":
            return self._use_fellhammer_pitiless_cannonade(stratagem, **kwargs)
        if name_u == "PITILESS HUNTERS":
            return self._use_dread_talons_pitiless_hunters(stratagem, **kwargs)
        if name_u == "POINT-BLANK DESTRUCTION":
            return self._use_fellhammer_point_blank_destruction(stratagem, **kwargs)
        if name_u == "OPPORTUNISTIC RAIDERS":
            return self._use_renegade_raiders_opportunistic_raiders(stratagem, **kwargs)
        if name_u == "PREDATORY PURSUIT":
            return self._use_soulforged_predatory_pursuit(stratagem, **kwargs)
        if name_u == "PREY ON THE WEAK":
            return self._use_nightmare_hunt_prey_on_the_weak(stratagem, **kwargs)
        if name_u == "PROFANE ZEAL":
            return self._use_pactbound_profane_zeal(stratagem, **kwargs)
        if name_u == "REAVERS' REACTION":
            return self._use_renegade_warband_reavers_reaction(stratagem, **kwargs)
        if name_u == "RENEGADE CLAIM":
            return self._use_renegade_warband_renegade_claim(stratagem, **kwargs)
        if name_u == "REAVERS' HASTE":
            return self._use_renegade_raiders_reavers_haste(stratagem, **kwargs)
        if name_u == "REAVERS' FLURRY":
            return self._use_hurons_marauders_reavers_flurry(stratagem, **kwargs)
        if name_u == "RELENTLESS TERROR":
            if str(getattr(stratagem, "id", "") or "") == "000010642006":
                return self._use_nightmare_hunt_relentless_terror(stratagem, **kwargs)
            return self._use_dread_talons_relentless_terror(stratagem, **kwargs)
        if name_u == "MERCILESS PURSUIT":
            return self._use_dread_talons_merciless_pursuit(stratagem, **kwargs)
        if name_u == "RELENTLESS PURSUIT":
            return self._use_deceptors_relentless_pursuit(stratagem, **kwargs)
        if name_u == "RUINOUS RAID":
            return self._use_renegade_raiders_ruinous_raid(stratagem, **kwargs)
        if name_u == "SADISTIC DISPLAY":
            return self._use_nightmare_hunt_sadistic_display(stratagem, **kwargs)
        if name_u == "SCRAMBLED COORDINATES":
            return self._use_deceptors_scrambled_coordinates(stratagem, **kwargs)
        if name_u == "SCOUR AND SEIZE":
            return self._use_renegade_raiders_scour_and_seize(stratagem, **kwargs)
        if name_u == "SCREAMING DESCENT":
            return self._use_dread_talons_screaming_descent(stratagem, **kwargs)
        if name_u == "SEIZE THE PRIZE":
            return self._use_hurons_marauders_seize_the_prize(stratagem, **kwargs)
        if name_u == "SIEGECRAFT":
            return self._use_fellhammer_siegecraft(stratagem, **kwargs)
        if name_u == "SKINSHIFT":
            return self._use_pactbound_skinshift(stratagem, **kwargs)
        if name_u == "SPECIMENS FOR THE SPIDER":
            return self._use_creations_of_bile_specimens_for_the_spider(stratagem, **kwargs)
        if name_u == "STEADFAST DETERMINATION":
            return self._use_fellhammer_steadfast_determination(stratagem, **kwargs)
        if name_u == "TALONS SUNK DEEP":
            return self._use_nightmare_hunt_talons_sunk_deep(stratagem, **kwargs)
        if name_u == "TO THE FAVOURED THE SPOILS":
            return self._use_hurons_marauders_to_the_favoured_the_spoils(stratagem, **kwargs)
        if name_u == "TORPEFYING REFRAIN":
            return self._use_pactbound_torpefying_refrain(stratagem, **kwargs)
        if name_u == "UNDYING HATRED":
            return self._use_renegade_warband_undying_hatred(stratagem, **kwargs)
        if name_u == "UNFAILINGLY OBDURATE":
            return self._use_renegade_raiders_unfailingly_obdurate(stratagem, **kwargs)
        if name_u == "UNSTOPPABLE RAMPAGE":
            return self._use_soulforged_unstoppable_rampage(stratagem, **kwargs)
        if name_u == "VENGEFUL DESTRUCTION":
            return self._use_renegade_warband_vengeful_destruction(stratagem, **kwargs)
        if name_u == "WARPCHARGED ENGINES":
            return self._use_renegade_raiders_warpcharged_engines(stratagem, **kwargs)
        return None
