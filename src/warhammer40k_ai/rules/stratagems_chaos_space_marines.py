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
        name_u = str(stratagem_name or "").strip().upper()
        expected_root = self._csm_root(unit)
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
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
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != str(event_name):
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem_name or "").strip().upper():
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

    def _use_chaos_space_marines_cabal_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
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
        if name_u == "BLOODY EXAMPLE":
            return self._use_dread_talons_bloody_example(stratagem, **kwargs)
        if name_u == "BRUTAL ATTRITION":
            return self._use_fellhammer_brutal_attrition(stratagem, **kwargs)
        if name_u == "COILS OF DECEPTION":
            return self._use_deceptors_coils_of_deception(stratagem, **kwargs)
        if name_u == "DEPTHLESS CRUELTY":
            return self._use_dread_talons_depthless_cruelty(stratagem, **kwargs)
        if name_u == "DETONATOR":
            return self._use_deceptors_detonator(stratagem, **kwargs)
        if name_u == "DELAYED MUTATIONS":
            return self._use_creations_of_bile_delayed_mutations(stratagem, **kwargs)
        if name_u == "DIABOLIC REGENERATION":
            return self._use_creations_of_bile_diabolic_regeneration(stratagem, **kwargs)
        if name_u == "FROM ALL SIDES":
            return self._use_deceptors_from_all_sides(stratagem, **kwargs)
        if name_u == "MASTERS ARE WATCHING":
            return self._use_creations_of_bile_masters_are_watching(stratagem, **kwargs)
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
        if name_u == "RELENTLESS TERROR":
            return self._use_dread_talons_relentless_terror(stratagem, **kwargs)
        if name_u == "MERCILESS PURSUIT":
            return self._use_dread_talons_merciless_pursuit(stratagem, **kwargs)
        if name_u == "RELENTLESS PURSUIT":
            return self._use_deceptors_relentless_pursuit(stratagem, **kwargs)
        if name_u == "SCRAMBLED COORDINATES":
            return self._use_deceptors_scrambled_coordinates(stratagem, **kwargs)
        if name_u == "SCREAMING DESCENT":
            return self._use_dread_talons_screaming_descent(stratagem, **kwargs)
        if name_u == "SIEGECRAFT":
            return self._use_fellhammer_siegecraft(stratagem, **kwargs)
        if name_u == "SPECIMENS FOR THE SPIDER":
            return self._use_creations_of_bile_specimens_for_the_spider(stratagem, **kwargs)
        if name_u == "STEADFAST DETERMINATION":
            return self._use_fellhammer_steadfast_determination(stratagem, **kwargs)
        return None
