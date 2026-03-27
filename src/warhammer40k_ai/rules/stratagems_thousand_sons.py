from __future__ import annotations

import copy
import logging
import math
from typing import Any, Optional

from .thousand_sons_detachments import GRAND_COVEN_BY_KEY
from ..utility import dice as dice_module
from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class ThousandSonsStratagemMixin:
    @staticmethod
    def _ts_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _ts_sort_key(entity: Any) -> str:
        return str(get_entity_id(entity) or "")

    def _ts_detachment_mgr(self) -> Any:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "thousand_sons_detachments", None)

    def _is_thousand_sons_rubricae_phalanx_detachment(self) -> bool:
        mgr = self._ts_detachment_mgr()
        checker = getattr(mgr, "is_rubricae_phalanx", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_thousand_sons_changehost_of_deceit_detachment(self) -> bool:
        mgr = self._ts_detachment_mgr()
        checker = getattr(mgr, "is_changehost_of_deceit", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_thousand_sons_grand_coven_detachment(self) -> bool:
        mgr = self._ts_detachment_mgr()
        checker = getattr(mgr, "is_grand_coven", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_thousand_sons_hexwarp_thrallband_detachment(self) -> bool:
        mgr = self._ts_detachment_mgr()
        checker = getattr(mgr, "is_hexwarp_thrallband", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_thousand_sons_warpforged_cabal_detachment(self) -> bool:
        mgr = self._ts_detachment_mgr()
        checker = getattr(mgr, "is_warpforged_cabal", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_thousand_sons_warpmeld_pact_detachment(self) -> bool:
        mgr = self._ts_detachment_mgr()
        checker = getattr(mgr, "is_warpmeld_pact", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _ts_phase_key_for_game(self) -> str:
        mgr = self._ts_detachment_mgr()
        phase_key_fn = getattr(mgr, "_phase_key_for_game", None) if mgr is not None else None
        if callable(phase_key_fn):
            return str(phase_key_fn(getattr(self, "game", None)) or "")
        return ""

    @staticmethod
    def _ts_has_any_keyword(entity: Any, keyword: str) -> bool:
        if entity is None:
            return False
        has_any = getattr(entity, "has_any_keyword", None)
        if callable(has_any) and has_any(keyword):
            return True
        has_kw = getattr(entity, "has_keyword", None)
        if callable(has_kw) and has_kw(keyword):
            return True
        return False

    def _is_thousand_sons_unit(self, unit: Any) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        mgr = self._ts_detachment_mgr()
        checker = getattr(mgr, "_unit_has_keyword_or_faction", None) if mgr is not None else None
        if callable(checker):
            try:
                if bool(checker(root, "THOUSAND SONS", faction_id="TS")):
                    return True
            except TypeError:
                pass
        faction_id = str(getattr(root, "faction_id", "") or "").strip().upper()
        if faction_id == "TS":
            return True
        return self._ts_has_any_keyword(root, "THOUSAND SONS")

    def _is_rubricae_unit(self, unit: Any) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        if not self._is_thousand_sons_unit(root):
            return False
        if self._ts_has_any_keyword(root, "RUBRICAE"):
            return True
        return "RUBRIC" in str(getattr(root, "name", "") or "").strip().upper()

    def _is_scintillating_legions_unit(self, unit: Any) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        if self._ts_has_any_keyword(root, "SCINTILLATING LEGIONS"):
            return True
        faction_id = str(getattr(root, "faction_id", "") or "").strip().upper()
        if faction_id in {"SL", "SCINTILLATING LEGIONS", "SCINTILLATING_LEGIONS"}:
            return True
        for keyword in list(getattr(root, "faction_keywords", []) or []):
            if str(keyword or "").strip().upper() == "SCINTILLATING LEGIONS":
                return True
        return False

    def _is_monster_unit(self, unit: Any) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        return self._ts_has_any_keyword(root, "MONSTER")

    def _is_rubric_marines_unit(self, unit: Any) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        if not self._is_rubricae_unit(root):
            return False
        if self._ts_has_any_keyword(root, "RUBRIC MARINES"):
            return True
        return "RUBRIC MARINES" in str(getattr(root, "name", "") or "").strip().upper()

    @staticmethod
    def _ts_model_has_keyword(model: Any, keyword: str) -> bool:
        if model is None:
            return False
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any):
            try:
                if bool(has_any(keyword)):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass
        has_kw = getattr(model, "has_keyword", None)
        if callable(has_kw):
            try:
                if bool(has_kw(keyword)):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass
        return False

    @staticmethod
    def _ts_model_is_alive(model: Any) -> bool:
        if model is None:
            return False
        alive = getattr(model, "is_alive", None)
        if callable(alive):
            try:
                return bool(alive())
            except (AttributeError, TypeError, ValueError):
                return False
        return bool(alive)

    def _is_psyker_unit(self, unit: Any) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        if self._ts_has_any_keyword(root, "PSYKER"):
            return True
        for model in list(getattr(root, "models", []) or []):
            if not self._ts_model_is_alive(model):
                continue
            if self._ts_model_has_keyword(model, "PSYKER"):
                return True
        return False

    def _is_thousand_sons_vehicle_unit(self, unit: Any) -> bool:
        root = self._ts_root(unit)
        if root is None or not self._is_thousand_sons_unit(root):
            return False
        mgr = self._ts_detachment_mgr()
        checker = getattr(mgr, "_unit_is_thousand_sons_vehicle", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        return self._ts_has_any_keyword(root, "VEHICLE")

    def _is_character_unit(self, unit: Any) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        return self._ts_has_any_keyword(root, "CHARACTER") or bool(getattr(root, "is_character", False))

    def _is_tzaangors_unit(self, unit: Any) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        mgr = self._ts_detachment_mgr()
        checker = getattr(mgr, "_unit_is_tzaangors", None) if mgr is not None else None
        return bool(checker(root)) if callable(checker) else False

    def _is_tzeentch_mutant_infantry_or_mounted_unit(self, unit: Any) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        mgr = self._ts_detachment_mgr()
        checker = getattr(mgr, "_unit_is_tzeentch_mutant_infantry_or_mounted", None) if mgr is not None else None
        return bool(checker(root)) if callable(checker) else False

    def _is_tzeentch_mutant_unit(self, unit: Any) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        has_tzeentch = self._ts_has_any_keyword(root, "TZEENTCH") or self._ts_has_any_keyword(root, "TZEENTCH MUTANT")
        has_mutant = self._ts_has_any_keyword(root, "MUTANT") or self._ts_has_any_keyword(root, "TZEENTCH MUTANT")
        return bool(has_tzeentch and has_mutant)

    def _ts_model_is_psyker(self, model: Any, *, unit: Any = None) -> bool:
        if model is None:
            return False
        if self._ts_model_has_keyword(model, "PSYKER"):
            return True
        root = self._ts_root(unit) if unit is not None else self._ts_root(getattr(model, "parent_unit", None))
        if root is None:
            return False
        return self._ts_has_any_keyword(root, "PSYKER")

    def _ts_model_is_character(self, model: Any) -> bool:
        if model is None:
            return False
        is_character = getattr(model, "is_character", None)
        if callable(is_character):
            try:
                if bool(is_character()):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass
        elif bool(is_character):
            return True
        if self._ts_model_has_keyword(model, "CHARACTER"):
            return True
        parent = getattr(model, "parent_unit", None)
        if parent is None:
            return False
        if bool(getattr(parent, "is_character", False)):
            return True
        return self._ts_has_any_keyword(parent, "CHARACTER")

    @staticmethod
    def _ts_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(unit, "is_alive", True))

    def _ts_owned_by_player(self, unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(army, "player", None) is player

    def _ts_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        if not self._ts_is_alive(root):
            return False
        if bool(getattr(root, "is_embarked", False)):
            return False
        if getattr(root, "embarked_in", None) is not None:
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        is_in_reserves = getattr(root, "is_in_reserves", None)
        if callable(is_in_reserves) and bool(is_in_reserves()):
            return False
        if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
            return False
        return True

    def _ts_unit_in_candidates(self, root: Any, candidates: list[Any]) -> bool:
        if root is None:
            return False
        rid = self._ts_sort_key(root)
        for candidate in list(candidates or []):
            candidate_root = self._ts_root(candidate)
            if candidate_root is None:
                continue
            if candidate_root is root:
                return True
            if rid and self._ts_sort_key(candidate_root) == rid:
                return True
        return False

    @staticmethod
    def _ts_has_shot_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(getattr(round_state, "shot_this_round", False))

    def _ts_model_distance_inches(self, source_model: Any, target_model: Any) -> Optional[float]:
        if source_model is None or target_model is None:
            return None
        source_base = getattr(source_model, "model_base", None)
        target_base = getattr(target_model, "model_base", None)
        if source_base is not None and target_base is not None and hasattr(source_base, "edge_to_edge_distance"):
            try:
                return float(source_base.edge_to_edge_distance(target_base))
            except (AttributeError, TypeError, ValueError):
                pass
        get_source = getattr(source_model, "get_location", None)
        get_target = getattr(target_model, "get_location", None)
        if callable(get_source) and callable(get_target):
            try:
                sx, sy, sz = get_source()
                tx, ty, tz = get_target()
                return float(math.dist((float(sx), float(sy), float(sz)), (float(tx), float(ty), float(tz))))
            except (AttributeError, TypeError, ValueError):
                return None
        return None

    def _ts_model_horizontal_distance_inches(self, source_model: Any, target_model: Any) -> Optional[float]:
        if source_model is None or target_model is None:
            return None
        source_base = getattr(source_model, "model_base", None)
        target_base = getattr(target_model, "model_base", None)
        if source_base is not None and target_base is not None:
            try:
                from ..utility.aura_utils import horizontal_distance_between_bases_2d

                return float(horizontal_distance_between_bases_2d(source_base, target_base))
            except (AttributeError, TypeError, ValueError):
                pass
        get_source = getattr(source_model, "get_location", None)
        get_target = getattr(target_model, "get_location", None)
        if callable(get_source) and callable(get_target):
            try:
                sx, sy, _sz, *_rest_s = get_source()
                tx, ty, _tz, *_rest_t = get_target()
                return float(math.hypot(float(sx) - float(tx), float(sy) - float(ty)))
            except (AttributeError, TypeError, ValueError):
                return None
        return None

    def _ts_unit_within_distance_of_model(self, unit: Any, model: Any, *, distance: float) -> bool:
        root = self._ts_root(unit)
        if root is None or model is None:
            return False
        max_distance = float(distance)
        for candidate in list(getattr(root, "models", []) or []):
            if not self._ts_model_is_alive(candidate):
                continue
            dist = self._ts_model_distance_inches(model, candidate)
            if dist is not None and dist <= max_distance + 1e-6:
                return True
        return False

    def _ts_unit_within_horizontal_distance_of_unit(
        self,
        unit: Any,
        other_unit: Any,
        *,
        distance: float,
    ) -> bool:
        root = self._ts_root(unit)
        other_root = self._ts_root(other_unit)
        if root is None or other_root is None:
            return False
        max_distance = float(distance)
        source_models = [m for m in list(getattr(root, "models", []) or []) if self._ts_model_is_alive(m)]
        target_models = [m for m in list(getattr(other_root, "models", []) or []) if self._ts_model_is_alive(m)]
        if not source_models or not target_models:
            return False
        for source_model in source_models:
            for target_model in target_models:
                dist = self._ts_model_horizontal_distance_inches(source_model, target_model)
                if dist is not None and dist <= max_distance + 1e-6:
                    return True
        return False

    def _ts_has_enemy_within_horizontal_distance(self, unit: Any, *, distance: float) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        game_map = getattr(getattr(self, "game", None), "map", None)
        if game_map is None:
            return False
        enemies: list[Any] = []
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        if callable(get_enemy_units):
            enemies = list(get_enemy_units(root) or [])
        elif isinstance(getattr(game_map, "units", None), list):
            enemies = list(getattr(game_map, "units", []) or [])
        for enemy in enemies:
            enemy_root = self._ts_root(enemy)
            if enemy_root is None:
                continue
            if self._ts_owned_by_player(enemy_root, self.player):
                continue
            if not self._ts_on_battlefield(enemy_root, require_targetable=False):
                continue
            if self._ts_unit_within_horizontal_distance_of_unit(root, enemy_root, distance=distance):
                return True
        return False

    def _ts_reaction_exists(
        self,
        event_name: str,
        stratagem_name: str,
        *,
        enemy_unit: Any = None,
    ) -> bool:
        event_u = str(event_name or "").strip().lower()
        strat_u = str(stratagem_name or "").strip().upper()
        enemy_root = self._ts_root(enemy_unit)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "").strip().lower() != event_u:
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != strat_u:
                continue
            if enemy_root is not None:
                existing_enemy = self._ts_root(
                    reaction.get("enemy_unit")
                    or reaction.get("attacking_unit")
                )
                if existing_enemy is not enemy_root:
                    continue
            return True
        return False

    def _ts_revenge_pending_entries(self) -> list[dict[str, Any]]:
        pending = getattr(self, "_thousand_sons_revenge_pending", None)
        if isinstance(pending, list):
            return pending
        pending = []
        setattr(self, "_thousand_sons_revenge_pending", pending)
        return pending

    @staticmethod
    def _ts_normalize_move_action(action: Any) -> str:
        action_key = str(action or "").strip().lower().replace(" ", "_")
        if action_key == "normal":
            return "normal_move"
        if action_key == "fallback":
            return "fall_back"
        return action_key

    def _ts_army_roots(self) -> list[Any]:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ts_root(unit)
            if root is None:
                continue
            uid = self._ts_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_game_map(self) -> Any:
        return getattr(getattr(self, "game", None), "map", None)

    def _ts_unit_is_engaged(self, unit: Any) -> bool:
        root = self._ts_root(unit)
        game_map = self._ts_game_map()
        if root is None or game_map is None:
            return False
        for enemy in list(getattr(game_map, "get_enemy_units", lambda _u: [])(root) or []):
            enemy_root = self._ts_root(enemy)
            if enemy_root is None or not self._ts_on_battlefield(enemy_root, require_targetable=False):
                continue
            try:
                if bool(game_map.is_within_engagement_range(root, enemy_root)):
                    return True
            except (AttributeError, TypeError, ValueError):
                continue
        return False

    def _ts_engaged_enemy_units(self, unit: Any) -> list[Any]:
        root = self._ts_root(unit)
        game_map = self._ts_game_map()
        if root is None or game_map is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for enemy in list(getattr(game_map, "get_enemy_units", lambda _u: [])(root) or []):
            enemy_root = self._ts_root(enemy)
            if enemy_root is None:
                continue
            uid = self._ts_sort_key(enemy_root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ts_on_battlefield(enemy_root, require_targetable=False):
                continue
            try:
                if bool(game_map.is_within_engagement_range(root, enemy_root)):
                    out.append(enemy_root)
            except (AttributeError, TypeError, ValueError):
                continue
        return sorted(out, key=self._ts_sort_key)

    def _ts_unit_within_distance_of_unit(self, unit: Any, other_unit: Any, *, distance: float) -> bool:
        root = self._ts_root(unit)
        other_root = self._ts_root(other_unit)
        if root is None or other_root is None:
            return False
        try:
            from ..utility.aura_utils import unit_within_range_of_unit

            return bool(unit_within_range_of_unit(root, other_root, float(distance), use_attached_aggregate=True))
        except (AttributeError, ImportError, TypeError, ValueError):
            return False

    def _ts_unit_wholly_within_distance_of_friendly_thousand_sons_units(
        self,
        unit: Any,
        *,
        distance: float,
    ) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        active_models = [model for model in list(getattr(root, "models", []) or []) if self._ts_model_is_alive(model)]
        if not active_models:
            return False
        anchors = [
            candidate
            for candidate in self._ts_army_roots()
            if candidate is not root
            and self._ts_on_battlefield(candidate, require_targetable=False)
            and self._is_thousand_sons_unit(candidate)
        ]
        if not anchors:
            return False
        for model in active_models:
            if any(self._ts_unit_within_distance_of_model(anchor, model, distance=distance) for anchor in anchors):
                continue
            return False
        return True

    def _ts_prune_revenge_pending(self) -> None:
        game = getattr(self, "game", None)
        current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
        keep: list[dict[str, Any]] = []
        for entry in list(self._ts_revenge_pending_entries()):
            if not isinstance(entry, dict):
                continue
            if current_turn and int(entry.get("turn", 0) or 0) != current_turn:
                continue
            entry_phase = str(entry.get("phase_key", "") or "").strip().upper()
            if entry_phase and phase_key and entry_phase != phase_key:
                continue
            keep.append(entry)
        setattr(self, "_thousand_sons_revenge_pending", keep)

    def _ts_rubricae_battlefield_candidates(self, *, require_fell_back: bool) -> list[Any]:
        if not self._is_thousand_sons_rubricae_phalanx_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ts_root(unit)
            if root is None:
                continue
            uid = self._ts_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ts_owned_by_player(root, self.player):
                continue
            if not self._ts_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_rubricae_unit(root):
                continue
            if require_fell_back and not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_ardent_automata_candidates(self) -> list[Any]:
        return self._ts_rubricae_battlefield_candidates(require_fell_back=True)

    def _ts_inexorable_advance_candidates(self) -> list[Any]:
        return self._ts_rubricae_battlefield_candidates(require_fell_back=False)

    def _ts_infernal_fusillade_candidates(self) -> list[Any]:
        if not self._is_thousand_sons_rubricae_phalanx_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ts_root(unit)
            if root is None:
                continue
            uid = self._ts_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ts_owned_by_player(root, self.player):
                continue
            if not self._ts_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_thousand_sons_unit(root):
                continue
            if not self._is_psyker_unit(root):
                continue
            if self._ts_has_shot_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_implacable_guardians_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_thousand_sons_rubricae_phalanx_detachment():
            return []
        if attacking_unit is not None:
            attacker_root = self._ts_root(attacking_unit)
            if attacker_root is None:
                return []
            if self._ts_owned_by_player(attacker_root, self.player):
                return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._ts_root(unit)
            if root is None:
                continue
            uid = self._ts_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ts_owned_by_player(root, self.player):
                continue
            if not self._ts_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_rubric_marines_unit(root):
                continue
            if not self._is_psyker_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_unwavering_phalanx_candidates(
        self,
        *,
        attacking_unit: Any = None,
    ) -> list[Any]:
        if not self._is_thousand_sons_rubricae_phalanx_detachment():
            return []
        attacker_root = self._ts_root(attacking_unit)
        if attacker_root is None:
            return []
        if self._ts_owned_by_player(attacker_root, self.player):
            return []
        if not self._ts_on_battlefield(attacker_root, require_targetable=False):
            return []
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None or not hasattr(game_map, "is_within_engagement_range"):
            return []

        out: list[Any] = []
        for root in self._ts_rubricae_battlefield_candidates(require_fell_back=False):
            if not self._is_rubric_marines_unit(root):
                continue
            try:
                if not bool(game_map.is_within_engagement_range(root, attacker_root)):
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_revenge_of_the_rubricae_candidates(
        self,
        *,
        attacker_unit: Any = None,
        destroyed_model: Any = None,
    ) -> list[Any]:
        if not self._is_thousand_sons_rubricae_phalanx_detachment():
            return []
        if attacker_unit is not None:
            attacker_root = self._ts_root(attacker_unit)
            if attacker_root is None:
                return []
            if self._ts_owned_by_player(attacker_root, self.player):
                return []
        if destroyed_model is None:
            return []
        out: list[Any] = []
        for root in self._ts_rubricae_battlefield_candidates(require_fell_back=False):
            if not self._ts_unit_within_distance_of_model(root, destroyed_model, distance=6.0):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_grand_coven_psyker_candidates(self, *, require_not_shot: bool = False) -> list[Any]:
        if not self._is_thousand_sons_grand_coven_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ts_root(unit)
            if root is None:
                continue
            uid = self._ts_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ts_owned_by_player(root, self.player):
                continue
            if not self._ts_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_thousand_sons_unit(root):
                continue
            if not self._is_psyker_unit(root):
                continue
            if require_not_shot and self._ts_has_shot_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_grand_coven_desecration_objective_candidates(self, unit: Any) -> list[Any]:
        if not self._is_thousand_sons_grand_coven_detachment():
            return []
        root = self._ts_root(unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
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

    def _ts_grand_coven_psychic_dominion_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_thousand_sons_grand_coven_detachment():
            return []
        attacker_root = self._ts_root(attacking_unit)
        if attacker_root is None or self._ts_owned_by_player(attacker_root, self.player):
            return []
        if not self._ts_on_battlefield(attacker_root, require_targetable=False):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._ts_root(unit)
            if root is None:
                continue
            uid = self._ts_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ts_owned_by_player(root, self.player):
                continue
            if not self._ts_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_thousand_sons_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_glimmershift_portal_candidates(self) -> list[Any]:
        if not self._is_thousand_sons_changehost_of_deceit_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ts_root(unit)
            if root is None:
                continue
            uid = self._ts_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ts_owned_by_player(root, self.player):
                continue
            if not self._ts_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_scintillating_legions_unit(root):
                continue
            if self._ts_has_enemy_within_horizontal_distance(root, distance=6.0):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_changehost_chronosorcerous_bleed_candidates(
        self,
        *,
        charging_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_thousand_sons_changehost_of_deceit_detachment():
            return []
        attacker_root = self._ts_root(charging_unit)
        if attacker_root is None or self._ts_owned_by_player(attacker_root, self.player):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._ts_root(unit)
            if root is None:
                continue
            uid = self._ts_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ts_owned_by_player(root, self.player):
                continue
            if not self._ts_on_battlefield(root, require_targetable=True):
                continue
            if not (self._is_scintillating_legions_unit(root) or (self._is_thousand_sons_unit(root) and self._is_psyker_unit(root))):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_changehost_deceptive_glamour_candidates(self) -> list[Any]:
        if not self._is_thousand_sons_changehost_of_deceit_detachment():
            return []
        if not any(
            self._is_scintillating_legions_unit(root) and self._ts_on_battlefield(root, require_targetable=False)
            for root in self._ts_army_roots()
        ):
            return []
        out: list[Any] = []
        for root in self._ts_army_roots():
            if not self._ts_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_thousand_sons_unit(root):
                continue
            if self._is_scintillating_legions_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_changehost_ethereal_phantasm_candidates(
        self,
        *,
        enemy_unit: Any = None,
        action: str = "",
    ) -> list[Any]:
        if not self._is_thousand_sons_changehost_of_deceit_detachment():
            return []
        action_key = self._ts_normalize_move_action(action)
        if action_key not in {"normal_move", "advance", "fall_back"}:
            return []
        enemy_root = self._ts_root(enemy_unit)
        if enemy_root is None or self._ts_owned_by_player(enemy_root, self.player):
            return []
        if not self._ts_on_battlefield(enemy_root, require_targetable=False):
            return []
        out: list[Any] = []
        for root in self._ts_army_roots():
            if not self._ts_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_scintillating_legions_unit(root):
                continue
            if self._ts_unit_is_engaged(root):
                continue
            if not self._ts_unit_within_distance_of_unit(root, enemy_root, distance=9.0):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_changehost_fractal_disjunction_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_thousand_sons_changehost_of_deceit_detachment():
            return []
        attacker_root = self._ts_root(attacking_unit)
        if attacker_root is None or self._ts_owned_by_player(attacker_root, self.player):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._ts_root(unit)
            if root is None:
                continue
            uid = self._ts_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ts_owned_by_player(root, self.player):
                continue
            if not self._ts_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_scintillating_legions_unit(root):
                continue
            if self._is_monster_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    @staticmethod
    def _ts_hexwarp_strands_choice_options() -> list[dict[str, str]]:
        return [
            {"choice_key": "SHOOT", "label": "Shoot"},
            {"choice_key": "CHARGE", "label": "Charge"},
        ]

    @staticmethod
    def _ts_choice_key(choice: Any) -> str:
        value = choice
        if isinstance(choice, dict):
            value = (
                choice.get("choice_key")
                or choice.get("key")
                or choice.get("choice")
                or choice.get("label")
            )
        return str(value or "").strip().upper().replace(" ", "_")

    @staticmethod
    def _ts_clear_ability_cache(root: Any, *prefixes: str) -> None:
        cache = getattr(root, "_ability_cache", None)
        if not isinstance(cache, dict):
            return
        normalized = tuple(str(prefix or "") for prefix in prefixes if str(prefix or ""))
        if not normalized:
            return
        for key in list(cache.keys()):
            key_str = str(key or "")
            if any(key_str.startswith(prefix) for prefix in normalized):
                cache.pop(key, None)

    def _is_scarab_occult_terminators_unit(self, unit: Any) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        if not self._is_thousand_sons_unit(root):
            return False
        if self._ts_has_any_keyword(root, "SCARAB OCCULT TERMINATORS"):
            return True
        return "SCARAB OCCULT TERMINATORS" in str(getattr(root, "name", "") or "").strip().upper()

    def _ts_hexwarp_unit_wholly_within_flow(self, unit: Any) -> bool:
        if not self._is_thousand_sons_hexwarp_thrallband_detachment():
            return False
        root = self._ts_root(unit)
        mgr = self._ts_detachment_mgr()
        checker = getattr(mgr, "_unit_wholly_within_hexwarp_flow", None) if mgr is not None else None
        return bool(checker(root, game=getattr(self, "game", None))) if callable(checker) and root is not None else False

    def _ts_hexwarp_model_wholly_within_flow(self, model: Any) -> bool:
        if not self._is_thousand_sons_hexwarp_thrallband_detachment():
            return False
        mgr = self._ts_detachment_mgr()
        checker = getattr(mgr, "_model_wholly_within_hexwarp_flow", None) if mgr is not None else None
        return bool(checker(model, game=getattr(self, "game", None))) if callable(checker) and model is not None else False

    def _ts_hexwarp_objective_wholly_within_flow(self, objective: Any) -> bool:
        if not self._is_thousand_sons_hexwarp_thrallband_detachment():
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        location = getattr(objective, "location", None)
        if location is None or bool(getattr(location, "removed", False)):
            return False
        mgr = self._ts_detachment_mgr()
        zones_fn = getattr(mgr, "_active_hexwarp_flow_zones", None) if mgr is not None else None
        zones = set(zones_fn(game=game) or {"own"}) if callable(zones_fn) else {"own"}
        if not zones:
            zones = {"own"}
        players = list(getattr(game, "players", []) or [])
        opponent = next((candidate for candidate in players if candidate is not self.player), None)
        try:
            x = float(getattr(location, "x", 0.0) or 0.0)
            y = float(getattr(location, "y", 0.0) or 0.0)
            radius = float(getattr(location, "control_radius", 0.0) or 0.0)
        except (TypeError, ValueError):
            return False
        if radius < 0.0:
            radius = 0.0

        class _ObjectiveBase:
            radius = 0.0
            facing = 0.0
            base_type = type("_ObjectiveBaseType", (), {"name": "CIRCULAR"})()

            def get_radius(self) -> float:
                return 0.0

        sample_points = [(x, y)]
        if radius > 0.0:
            diag = float(radius / math.sqrt(2.0))
            sample_points.extend(
                [
                    (x + radius, y),
                    (x - radius, y),
                    (x, y + radius),
                    (x, y - radius),
                    (x + diag, y + diag),
                    (x + diag, y - diag),
                    (x - diag, y + diag),
                    (x - diag, y - diag),
                ]
            )
        base = _ObjectiveBase()
        for px, py in sample_points:
            try:
                in_own = bool(game.is_position_wholly_in_deployment_zone(float(px), float(py), base, self.player.id))
            except (AttributeError, TypeError, ValueError):
                return False
            try:
                in_enemy = bool(
                    opponent is not None
                    and game.is_position_wholly_in_deployment_zone(float(px), float(py), base, opponent.id)
                )
            except (AttributeError, TypeError, ValueError):
                return False
            zone = "nml"
            if in_own:
                zone = "own"
            elif in_enemy:
                zone = "enemy"
            if zone not in zones:
                return False
        return True

    def _ts_hexwarp_psyker_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_fell_back: bool = False,
    ) -> list[Any]:
        if not self._is_thousand_sons_hexwarp_thrallband_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ts_root(unit)
            if root is None:
                continue
            uid = self._ts_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ts_owned_by_player(root, self.player):
                continue
            if not self._ts_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_thousand_sons_unit(root):
                continue
            if not self._is_psyker_unit(root):
                continue
            if require_not_shot and self._ts_has_shot_this_phase(root):
                continue
            if require_fell_back and not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_hexwarp_warding_hex_objective_candidates(self, unit: Any) -> list[Any]:
        if not self._is_thousand_sons_hexwarp_thrallband_detachment():
            return []
        root = self._ts_root(unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
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
            if not self._ts_hexwarp_objective_wholly_within_flow(objective):
                continue
            objective_id = str(getattr(objective, "id", "") or get_entity_id(objective) or "")
            if objective_id and objective_id in seen:
                continue
            if objective_id:
                seen.add(objective_id)
            out.append(objective)
        out.sort(key=lambda objective: str(getattr(objective, "id", "") or get_entity_id(objective) or ""))
        return out

    def _ts_hexwarp_warding_hex_candidates(self) -> list[Any]:
        out: list[Any] = []
        for root in self._ts_hexwarp_psyker_candidates():
            if self._ts_hexwarp_warding_hex_objective_candidates(root):
                out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_hexwarp_wrath_of_the_doomed_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_thousand_sons_hexwarp_thrallband_detachment():
            return []
        attacker_root = self._ts_root(attacking_unit)
        if attacker_root is None or self._ts_owned_by_player(attacker_root, self.player):
            return []
        if not self._ts_on_battlefield(attacker_root, require_targetable=False):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._ts_root(unit)
            if root is None:
                continue
            uid = self._ts_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ts_owned_by_player(root, self.player):
                continue
            if not self._ts_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_thousand_sons_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_hexwarp_kaleidoscopic_tempest_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_thousand_sons_hexwarp_thrallband_detachment():
            return []
        attacker_root = self._ts_root(attacking_unit)
        if attacker_root is None or self._ts_owned_by_player(attacker_root, self.player):
            return []
        if not self._ts_on_battlefield(attacker_root, require_targetable=False):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._ts_root(unit)
            if root is None:
                continue
            uid = self._ts_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ts_owned_by_player(root, self.player):
                continue
            if not self._ts_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_thousand_sons_unit(root):
                continue
            if not self._is_psyker_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_hexwarp_through_the_veil_candidates(self) -> list[Any]:
        if not self._is_thousand_sons_hexwarp_thrallband_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ts_root(unit)
            if root is None:
                continue
            uid = self._ts_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ts_owned_by_player(root, self.player):
                continue
            if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
                continue
            reserve_status = str(getattr(root, "reserve_status", "") or "").strip().lower()
            if reserve_status != "strategic_reserves":
                continue
            if not (self._is_rubric_marines_unit(root) or self._is_scarab_occult_terminators_unit(root)):
                continue
            if self._is_scarab_occult_terminators_unit(root):
                has_deep_strike = getattr(root, "has_deep_strike", None)
                if callable(has_deep_strike) and not bool(has_deep_strike()):
                    continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_hexwarp_scouring_warpflame_candidates(self) -> list[Any]:
        return [
            root
            for root in self._ts_hexwarp_psyker_candidates(require_not_shot=True)
            if self._ts_hexwarp_unit_wholly_within_flow(root)
        ]

    def _ts_warpforged_vehicle_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_fell_back: bool = False,
    ) -> list[Any]:
        if not self._is_thousand_sons_warpforged_cabal_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ts_root(unit)
            if root is None:
                continue
            uid = self._ts_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ts_owned_by_player(root, self.player):
                continue
            if not self._ts_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_thousand_sons_vehicle_unit(root):
                continue
            if require_not_shot and self._ts_has_shot_this_phase(root):
                continue
            if require_fell_back and not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_warpforged_supporting_psyker_candidates(self, unit: Any, *, distance: float = 6.0) -> list[Any]:
        root = self._ts_root(unit)
        if root is None:
            return []
        out: list[Any] = []
        for candidate in self._ts_army_roots():
            if candidate is None or candidate is root:
                continue
            if not self._ts_on_battlefield(candidate, require_targetable=False):
                continue
            if not self._is_thousand_sons_unit(candidate) or not self._is_psyker_unit(candidate):
                continue
            if not self._ts_owned_by_player(candidate, self.player):
                continue
            if not self._ts_unit_within_distance_of_unit(root, candidate, distance=float(distance)):
                continue
            out.append(candidate)
        return sorted(out, key=self._ts_sort_key)

    def _ts_warpforged_malevolent_animus_candidates(self) -> list[Any]:
        return [
            root
            for root in self._ts_warpforged_vehicle_candidates()
            if self._ts_warpforged_supporting_psyker_candidates(root, distance=6.0)
        ]

    def _ts_warpforged_ensorcelled_infusion_candidates(self) -> list[Any]:
        return [
            root
            for root in self._ts_warpforged_vehicle_candidates(require_not_shot=True)
            if self._ts_warpforged_supporting_psyker_candidates(root, distance=6.0)
        ]

    def _ts_warpforged_cyberspirit_machinations_candidates(self) -> list[Any]:
        return [
            root
            for root in self._ts_warpforged_vehicle_candidates(require_fell_back=True)
            if self._ts_warpforged_supporting_psyker_candidates(root, distance=6.0)
        ]

    def _ts_warpforged_mutate_landscape_objective_candidates(self, unit: Any) -> list[Any]:
        root = self._ts_root(unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
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

    def _ts_warpforged_mutate_landscape_candidates(self) -> list[Any]:
        if not self._is_thousand_sons_warpforged_cabal_detachment():
            return []
        out: list[Any] = []
        for root in self._ts_army_roots():
            if not self._ts_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_thousand_sons_unit(root) or not self._is_psyker_unit(root):
                continue
            if not self._ts_owned_by_player(root, self.player):
                continue
            if not self._ts_warpforged_mutate_landscape_objective_candidates(root):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_warpforged_warpflame_gargoyles_candidates(self, *, charging_unit: Any = None) -> list[Any]:
        if not self._is_thousand_sons_warpforged_cabal_detachment():
            return []
        enemy_root = self._ts_root(charging_unit)
        if enemy_root is None or self._ts_owned_by_player(enemy_root, self.player):
            return []
        if not self._ts_on_battlefield(enemy_root, require_targetable=False):
            return []
        out: list[Any] = []
        game_map = self._ts_game_map()
        for root in self._ts_warpforged_vehicle_candidates():
            if game_map is None:
                continue
            try:
                engaged = bool(game_map.is_within_engagement_range(root, enemy_root))
            except (AttributeError, TypeError, ValueError):
                engaged = False
            if not engaged:
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    @staticmethod
    def _ts_is_below_starting_strength(unit: Any) -> bool:
        if unit is None:
            return False
        below_fn = getattr(unit, "is_below_starting_strength", None)
        if callable(below_fn):
            try:
                if bool(below_fn()):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass
        return bool(list(getattr(unit, "models_lost", []) or []))

    def _ts_returnable_destroyed_non_character_models(self, unit: Any) -> list[Any]:
        root = self._ts_root(unit)
        if root is None:
            return []
        destroyed_pool = list(getattr(root, "models_lost", []) or [])
        can_return = getattr(root, "_horrors_can_return_model", None)
        candidates: list[Any] = []
        for model in destroyed_pool:
            if model is None:
                continue
            if self._ts_model_is_character(model):
                continue
            if callable(can_return) and not bool(can_return(model)):
                continue
            candidates.append(model)
        return sorted(candidates, key=self._ts_sort_key)

    def _ts_warpmeld_supporting_psyker_candidates(self, unit: Any, *, distance: float = 12.0) -> list[Any]:
        root = self._ts_root(unit)
        if root is None:
            return []
        out: list[Any] = []
        for candidate in self._ts_army_roots():
            if candidate is None:
                continue
            if not self._ts_owned_by_player(candidate, self.player):
                continue
            if not self._ts_on_battlefield(candidate, require_targetable=False):
                continue
            if not self._is_thousand_sons_unit(candidate) or not self._is_psyker_unit(candidate):
                continue
            if not self._ts_unit_within_distance_of_unit(root, candidate, distance=float(distance)):
                continue
            out.append(candidate)
        return sorted(out, key=self._ts_sort_key)

    def _ts_warpmeld_blessed_transmutations_candidates(self) -> list[Any]:
        if not self._is_thousand_sons_warpmeld_pact_detachment():
            return []
        out: list[Any] = []
        for root in self._ts_army_roots():
            if not self._ts_owned_by_player(root, self.player):
                continue
            if not self._ts_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tzaangors_unit(root):
                continue
            if not self._ts_is_below_starting_strength(root):
                continue
            if not self._ts_returnable_destroyed_non_character_models(root):
                continue
            if not self._ts_warpmeld_supporting_psyker_candidates(root, distance=12.0):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_warpmeld_deranged_ferocity_candidates(self, *, selected_unit: Any = None) -> list[Any]:
        if not self._is_thousand_sons_warpmeld_pact_detachment():
            return []
        root = self._ts_root(selected_unit)
        if root is None:
            return []
        if not self._ts_owned_by_player(root, self.player):
            return []
        if not self._ts_on_battlefield(root, require_targetable=True):
            return []
        if not self._is_tzeentch_mutant_unit(root):
            return []
        round_state = getattr(root, "round_state", None)
        if bool(getattr(round_state, "fought_this_phase", False)):
            return []
        return [root]

    def _ts_warpmeld_touched_by_tzeentch_candidates(self) -> list[Any]:
        if not self._is_thousand_sons_warpmeld_pact_detachment():
            return []
        out: list[Any] = []
        for root in self._ts_army_roots():
            if not self._ts_owned_by_player(root, self.player):
                continue
            if not self._ts_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tzeentch_mutant_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_warpmeld_twisted_mirage_candidates(self) -> list[Any]:
        if not self._is_thousand_sons_warpmeld_pact_detachment():
            return []
        out: list[Any] = []
        for root in self._ts_army_roots():
            if not self._ts_owned_by_player(root, self.player):
                continue
            if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
                continue
            if not self._is_tzeentch_mutant_unit(root):
                continue
            reserve_status = str(getattr(root, "reserve_status", "") or "").strip().lower()
            if reserve_status != "strategic_reserves":
                continue
            can_arrive = getattr(root, "can_arrive_from_reserves", None)
            if callable(can_arrive):
                try:
                    if not bool(can_arrive(int(getattr(self.game, "turn", 0) or 0))):
                        continue
                except (AttributeError, TypeError, ValueError):
                    continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_warpmeld_gift_of_change_model_valid(self, model: Any) -> bool:
        if model is None:
            return False
        parent_unit = getattr(model, "parent_unit", None)
        if parent_unit is None:
            return False
        root = self._ts_root(parent_unit)
        if root is None or not self._ts_owned_by_player(root, self.player):
            return False
        if not self._is_thousand_sons_unit(parent_unit) and not self._is_thousand_sons_unit(root):
            return False
        if not self._ts_model_is_character(model):
            return False
        if self._is_monster_unit(parent_unit) or self._is_monster_unit(root):
            return False
        return True

    def _ts_warpmeld_gift_of_change_pending_entries(self) -> list[dict[str, Any]]:
        pending = getattr(self, "_thousand_sons_warpmeld_gift_of_change_pending", None)
        if isinstance(pending, list):
            return pending
        pending = []
        setattr(self, "_thousand_sons_warpmeld_gift_of_change_pending", pending)
        return pending

    def _ts_warpmeld_chaos_spawn_datasheet(self) -> Any:
        cached = getattr(self, "_thousand_sons_warpmeld_chaos_spawn_datasheet", None)
        if cached is not None:
            return cached
        datasheet = self._waha.get_full_datasheet_info_by_name(
            "Chaos Spawn",
            datasheet_id="000001023",
            faction_id="TS",
        )
        if datasheet is None:
            datasheet = self._waha.get_datasheet(
                "Chaos Spawn",
                datasheet_id="000001023",
                faction_id="TS",
            )
        if datasheet is not None:
            setattr(self, "_thousand_sons_warpmeld_chaos_spawn_datasheet", datasheet)
        return datasheet

    def _ts_warpmeld_create_chaos_spawn_unit(self) -> Any:
        datasheet = self._ts_warpmeld_chaos_spawn_datasheet()
        if datasheet is None:
            return None
        from ..units.unit import Unit as UnitClass

        try:
            unit = UnitClass(datasheet, quantity=1)
        except TypeError:
            unit = UnitClass(datasheet)
        unit.spawned_in_battle = True
        unit.starting_model_count = 1
        unit.deployed = True
        unit.reserve_status = "deployed"
        unit.reserve_turn_deployed = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        unit.arrived_from_reserves_this_turn = False
        return unit

    def _ts_warpmeld_place_spawn_unit(self, unit: Any, *, destroyed_base: Any) -> bool:
        if unit is None or destroyed_base is None:
            return False
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        models = [model for model in list(getattr(unit, "models", []) or []) if self._ts_model_is_alive(model)]
        if not models:
            return False
        if game_map is None:
            try:
                models[0].set_location(
                    float(getattr(destroyed_base, "x", 0.0) or 0.0),
                    float(getattr(destroyed_base, "y", 0.0) or 0.0),
                    float(getattr(destroyed_base, "z", 0.0) or 0.0),
                    0.0,
                )
            except (AttributeError, TypeError, ValueError):
                return False
            return True

        try:
            anchor_x = float(getattr(destroyed_base, "x", 0.0) or 0.0)
            anchor_y = float(getattr(destroyed_base, "y", 0.0) or 0.0)
        except (AttributeError, TypeError, ValueError):
            return False

        try:
            max_radius = max(float(getattr(game_map, "width", 72) or 72), float(getattr(game_map, "height", 48) or 48))
        except (AttributeError, TypeError, ValueError):
            max_radius = 72.0

        boundary_repulsors = []
        get_repulsors = getattr(game_map, "get_battlefield_edge_repulsors", None)
        if callable(get_repulsors):
            boundary_repulsors = list(get_repulsors() or [])

        radius = 0.0
        while radius <= max_radius + 1e-6:
            angles = [0.0] if radius <= 1e-6 else [float(angle) for angle in range(0, 360, 15)]
            for angle_deg in angles:
                radians = math.radians(angle_deg)
                x = float(anchor_x + math.cos(radians) * radius)
                y = float(anchor_y + math.sin(radians) * radius)
                try:
                    prospective = unit.calculate_model_positions(
                        x,
                        y,
                        game_map,
                        avoid_friendly_units=True,
                        boundary_repulsors=boundary_repulsors,
                    )
                except (AttributeError, TypeError, ValueError):
                    prospective = None
                if not prospective:
                    continue
                if not bool(game_map.place_unit(unit)):
                    continue
                engaged = False
                for enemy in list(getattr(game_map, "get_enemy_units", lambda _u: [])(unit) or []):
                    enemy_root = self._ts_root(enemy)
                    if enemy_root is None or not self._ts_on_battlefield(enemy_root, require_targetable=False):
                        continue
                    try:
                        if bool(game_map.is_within_engagement_range(unit, enemy_root)):
                            engaged = True
                            break
                    except (AttributeError, TypeError, ValueError):
                        continue
                if engaged:
                    if isinstance(getattr(game_map, "units", None), list) and unit in game_map.units:
                        game_map.units.remove(unit)
                    continue
                return True
            radius += 0.5
        return False

    def _ts_warpmeld_resolve_gift_of_change_entry(self, entry: dict[str, Any]) -> bool:
        if not isinstance(entry, dict):
            return False
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return False
        destroyed_base = entry.get("destroyed_model_base")
        spawn_unit = self._ts_warpmeld_create_chaos_spawn_unit()
        if spawn_unit is None:
            logger.error("ERROR: GIFT OF CHANGE: Chaos Spawn datasheet could not be loaded")
            return False
        set_parent = getattr(spawn_unit, "set_parent_army", None)
        if callable(set_parent):
            set_parent(army)
        else:
            spawn_unit.parent_army = army
        if not self._ts_warpmeld_place_spawn_unit(spawn_unit, destroyed_base=destroyed_base):
            logger.error("ERROR: GIFT OF CHANGE: no valid setup location for Chaos Spawn")
            return False
        army.add_unit(spawn_unit)
        rebuild_registry = getattr(self.game, "rebuild_entity_registry", None) if self.game is not None else None
        if callable(rebuild_registry):
            rebuild_registry()
        refresh_rules = getattr(self.game, "refresh_rule_subscribers", None) if self.game is not None else None
        if callable(refresh_rules):
            refresh_rules()
        logger.info(
            "INFO: GIFT OF CHANGE: spawned %s at the end of the phase.",
            getattr(spawn_unit, "name", "Chaos Spawn"),
        )
        return True

    def _ts_place_unit_into_strategic_reserves(self, unit: Any, *, reason: str = "") -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        place_fn = getattr(root, "enter_strategic_reserves_midgame", None)
        if callable(place_fn):
            return bool(place_fn(game=game, game_map=game_map, reason=reason))

        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        for member in members:
            if member is None:
                continue
            set_status = getattr(member, "set_reserve_status", None)
            if callable(set_status):
                set_status("strategic_reserves")
            else:
                member.reserve_status = "strategic_reserves"
            mark_midgame = getattr(member, "mark_entered_reserves_midgame", None)
            if callable(mark_midgame):
                mark_midgame(game=game)
            if bool(getattr(member, "is_aircraft", False)) and not bool(getattr(member, "hover_mode", False)):
                member._aircraft_return_turn = int(getattr(game, "turn", 0) or 0) + 1 if game is not None else 0
            member.deployed = True
            member.reserve_turn_deployed = None
            member.arrived_from_reserves_this_turn = False
            if game_map is not None and isinstance(getattr(game_map, "units", None), list) and member in game_map.units:
                game_map.units.remove(member)
        return True

    def _ts_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        effective_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        preview_fn = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(preview_fn):
            preview = preview_fn(stratagem, target_unit=target_unit) or {}
            effective_cost = int(preview.get("cost", effective_cost))
        return bool(
            self.player.spend_command_points(
                int(effective_cost),
                reason=f"Stratagem: {getattr(stratagem, 'name', 'Unknown')}",
                source="stratagem",
            )
        )

    def _ts_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue and hasattr(self, "_dequeue_reaction_by_name"):
            self._dequeue_reaction_by_name(getattr(stratagem, "name", ""))
        used = getattr(self, "_used_stratagems_this_phase", None)
        if isinstance(used, set):
            name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
            if name_u:
                used.add(name_u)

    def _queue_thousand_sons_rubricae_phalanx_fall_back_reactions(self, *, unit: Any, action: str) -> None:
        if str(action or "").strip().lower() != "fall_back":
            return
        if not self._is_thousand_sons_rubricae_phalanx_detachment():
            return
        root = self._ts_root(unit)
        if root is None:
            return
        if not self._ts_owned_by_player(root, self.player):
            return
        if not self._ts_on_battlefield(root, require_targetable=True):
            return
        if not self._is_rubricae_unit(root):
            return
        if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
            return

        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("ARDENT AUTOMATA")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Movement phase"):
            return

        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if reaction.get("event") != "unit_move_ended":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if reaction.get("unit") is root:
                return

        queue_reaction = getattr(self, "_queue_reaction", None)
        if not callable(queue_reaction):
            return
        queue_reaction(
            {
                "event": "unit_move_ended",
                "phase_name": "Movement phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": root,
                "target_unit": root,
                "action": "fall_back",
                "candidates": [root],
            }
        )

    def _queue_thousand_sons_rubricae_phalanx_charge_reactions(
        self,
        *,
        charging_unit: Any = None,
        action: str = "",
    ) -> None:
        if str(action or "").strip().lower() != "charge":
            return
        if not self._is_thousand_sons_rubricae_phalanx_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "CHARGE_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return

        attacker_root = self._ts_root(charging_unit)
        if attacker_root is None or self._ts_owned_by_player(attacker_root, self.player):
            return
        if not self._ts_on_battlefield(attacker_root, require_targetable=False):
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("UNWAVERING PHALANX")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._ts_unwavering_phalanx_candidates(attacking_unit=attacker_root)
        if not candidates:
            return
        if self._ts_reaction_exists(
            "unit_move_ended",
            stratagem.name,
            enemy_unit=attacker_root,
        ):
            return
        if not stratagem.can_use(
            self.player,
            self.game,
            phase_name="Charge phase",
            attacking_unit=attacker_root,
            enemy_unit=attacker_root,
        ):
            return

        payload = {
            "event": "unit_move_ended",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_root,
            "attacking_unit": attacker_root,
            "action": "charge",
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
            payload["unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_thousand_sons_rubricae_phalanx_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> None:
        if not self._is_thousand_sons_rubricae_phalanx_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._ts_root(attacking_unit)
        if attacker_root is None or self._ts_owned_by_player(attacker_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("IMPLACABLE GUARDIANS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._ts_implacable_guardians_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not candidates:
            return
        if self._ts_reaction_exists(
            "shooting_targets_selected",
            stratagem.name,
            enemy_unit=attacker_root,
        ):
            return
        if not stratagem.can_use(
            self.player,
            self.game,
            phase_name="Shooting phase",
            attacking_unit=attacker_root,
            target_units=list(target_units or []),
        ):
            return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_root,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_thousand_sons_rubricae_revenge_on_model_destroyed(
        self,
        *,
        attacker_unit: Any = None,
        target_model: Any = None,
        target_unit: Any = None,
        weapon_profile: Any = None,
    ) -> None:
        if not self._is_thousand_sons_rubricae_phalanx_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._ts_root(attacker_unit)
        if attacker_root is None or self._ts_owned_by_player(attacker_root, self.player):
            return
        if not self._ts_is_alive(attacker_root):
            return
        if target_model is None:
            return
        target_root = self._ts_root(target_unit)
        if target_root is None:
            return
        if not self._ts_owned_by_player(target_root, self.player):
            return
        if not self._is_thousand_sons_unit(target_root):
            return
        if not self._ts_model_is_psyker(target_model, unit=target_root):
            return
        parent_wargear = getattr(weapon_profile, "parent_wargear", None)
        if parent_wargear is not None:
            is_ranged = getattr(parent_wargear, "is_ranged", None)
            if callable(is_ranged):
                try:
                    if not bool(is_ranged()):
                        return
                except (AttributeError, TypeError, ValueError):
                    return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("REVENGE OF THE RUBRICAE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._ts_revenge_of_the_rubricae_candidates(
            attacker_unit=attacker_root,
            destroyed_model=target_model,
        )
        if not candidates:
            return
        if not stratagem.can_use(self.player, self.game, phase_name="Shooting phase"):
            return
        attacker_key = self._ts_sort_key(attacker_root)
        if not attacker_key:
            return
        self._ts_prune_revenge_pending()
        current_turn = int(getattr(game, "turn", 0) or 0)
        phase_key = "SHOOTING_PHASE"
        merged = False
        pending = list(self._ts_revenge_pending_entries())
        for entry in pending:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("attacker_key", "") or "") != attacker_key:
                continue
            if int(entry.get("turn", 0) or 0) != current_turn:
                continue
            entry_phase = str(entry.get("phase_key", "") or "").strip().upper()
            if entry_phase and entry_phase != phase_key:
                continue
            existing: list[Any] = []
            seen_ids: set[str] = set()
            for cand in list(entry.get("candidates", []) or []):
                cand_root = self._ts_root(cand)
                if cand_root is None:
                    continue
                cid = self._ts_sort_key(cand_root)
                if cid and cid in seen_ids:
                    continue
                if cid:
                    seen_ids.add(cid)
                existing.append(cand_root)
            for cand in list(candidates or []):
                cand_root = self._ts_root(cand)
                if cand_root is None:
                    continue
                cid = self._ts_sort_key(cand_root)
                if cid and cid in seen_ids:
                    continue
                if cid:
                    seen_ids.add(cid)
                existing.append(cand_root)
            entry["candidates"] = sorted(existing, key=self._ts_sort_key)
            merged = True
            break
        if not merged:
            pending.append(
                {
                    "attacker_key": attacker_key,
                    "attacker_unit": attacker_root,
                    "candidates": sorted(list(candidates or []), key=self._ts_sort_key),
                    "turn": int(current_turn),
                    "phase_key": phase_key,
                    "stratagem": stratagem.name,
                }
            )
        setattr(self, "_thousand_sons_revenge_pending", pending)

    def _queue_thousand_sons_rubricae_revenge_after_shooting_resolved(
        self,
        *,
        attacker_unit: Any = None,
        hits_by_target: Any = None,
    ) -> None:
        del hits_by_target  # Not needed for this trigger; we queue from destroy-time snapshots.
        if not self._is_thousand_sons_rubricae_phalanx_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._ts_root(attacker_unit)
        if attacker_root is None or self._ts_owned_by_player(attacker_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("REVENGE OF THE RUBRICAE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        self._ts_prune_revenge_pending()
        attacker_key = self._ts_sort_key(attacker_root)
        current_turn = int(getattr(game, "turn", 0) or 0)
        keep: list[dict[str, Any]] = []
        queued = False
        for entry in list(self._ts_revenge_pending_entries()):
            if not isinstance(entry, dict):
                continue
            if str(entry.get("attacker_key", "") or "") != attacker_key:
                keep.append(entry)
                continue
            if int(entry.get("turn", 0) or 0) != current_turn:
                continue
            candidates: list[Any] = []
            seen_ids: set[str] = set()
            for unit in list(entry.get("candidates", []) or []):
                root = self._ts_root(unit)
                if root is None:
                    continue
                uid = self._ts_sort_key(root)
                if uid and uid in seen_ids:
                    continue
                if uid:
                    seen_ids.add(uid)
                if not self._ts_owned_by_player(root, self.player):
                    continue
                if not self._ts_on_battlefield(root, require_targetable=True):
                    continue
                if not self._is_rubricae_unit(root):
                    continue
                candidates.append(root)
            if not candidates:
                continue
            if self._ts_reaction_exists(
                "unit_shooting_resolved",
                stratagem.name,
                enemy_unit=attacker_root,
            ):
                queued = True
                continue
            payload = {
                "event": "unit_shooting_resolved",
                "phase_name": "Shooting phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "enemy_unit": attacker_root,
                "attacking_unit": attacker_root,
                "candidates": sorted(candidates, key=self._ts_sort_key),
            }
            if len(candidates) == 1:
                payload["target_unit"] = candidates[0]
            queue_reaction = getattr(self, "_queue_reaction", None)
            if callable(queue_reaction):
                queue_reaction(payload)
                queued = True
        setattr(self, "_thousand_sons_revenge_pending", keep)
        if queued:
            return

    def _queue_thousand_sons_changehost_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        _ = player
        game = getattr(self, "game", None)
        if game is None:
            return
        if not self._is_thousand_sons_changehost_of_deceit_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("DECEPTIVE GLAMOUR")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        candidates = self._ts_changehost_deceptive_glamour_candidates()
        if not candidates:
            return
        if self._ts_reaction_exists("phase_start", stratagem.name):
            return
        if not stratagem.can_use(self.player, self.game, unit=candidates[0], phase_name="Fight phase"):
            return

        payload: dict[str, Any] = {
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
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_thousand_sons_changehost_charge_reactions(
        self,
        *,
        charging_unit: Any = None,
        target_units: Any = None,
    ) -> None:
        if not self._is_thousand_sons_changehost_of_deceit_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "CHARGE_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return

        charging_root = self._ts_root(charging_unit)
        if charging_root is None or self._ts_owned_by_player(charging_root, self.player):
            return
        if not self._ts_on_battlefield(charging_root, require_targetable=False):
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("CHRONOSORCEROUS BLEED")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        candidates = self._ts_changehost_chronosorcerous_bleed_candidates(
            charging_unit=charging_root,
            target_units=target_units,
        )
        if not candidates:
            return
        if self._ts_reaction_exists("charge_declared", stratagem.name, enemy_unit=charging_root):
            return
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=candidates[0],
            enemy_unit=charging_root,
            phase_name="Charge phase",
        ):
            return

        payload: dict[str, Any] = {
            "event": "charge_declared",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": charging_root,
            "attacking_unit": charging_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
            payload["unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_thousand_sons_changehost_move_end_reactions(self, *, unit: Any = None, action: str = "") -> None:
        if not self._is_thousand_sons_changehost_of_deceit_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return

        enemy_root = self._ts_root(unit)
        if enemy_root is None or self._ts_owned_by_player(enemy_root, self.player):
            return
        if not self._ts_on_battlefield(enemy_root, require_targetable=False):
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("ETHEREAL PHANTASM")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        action_key = self._ts_normalize_move_action(action)
        candidates = self._ts_changehost_ethereal_phantasm_candidates(enemy_unit=enemy_root, action=action_key)
        if not candidates:
            return
        if self._ts_reaction_exists("unit_move_ended", stratagem.name, enemy_unit=enemy_root):
            return
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=candidates[0],
            moving_unit=enemy_root,
            phase_name="Movement phase",
        ):
            return

        payload: dict[str, Any] = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "moving_unit": enemy_root,
            "action": action_key,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
            payload["unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_thousand_sons_changehost_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> None:
        if not self._is_thousand_sons_changehost_of_deceit_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._ts_root(attacking_unit)
        if attacker_root is None or self._ts_owned_by_player(attacker_root, self.player):
            return
        if not self._ts_on_battlefield(attacker_root, require_targetable=False):
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("FRACTAL DISJUNCTION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        candidates = self._ts_changehost_fractal_disjunction_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not candidates:
            return
        if self._ts_reaction_exists("shooting_targets_selected", stratagem.name, enemy_unit=attacker_root):
            return
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=candidates[0],
            attacking_unit=attacker_root,
            phase_name="Shooting phase",
        ):
            return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_root,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
            payload["unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_thousand_sons_grand_coven_target_reactions(
        self,
        *,
        event_name: str,
        phase_name: str,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> None:
        if not self._is_thousand_sons_grand_coven_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        current_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if current_phase != str(phase_name or "").strip().upper().replace(" ", "_"):
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._ts_root(attacking_unit)
        if attacker_root is None or self._ts_owned_by_player(attacker_root, self.player):
            return
        if not self._ts_on_battlefield(attacker_root, require_targetable=False):
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("PSYCHIC DOMINION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        candidates = self._ts_grand_coven_psychic_dominion_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not candidates:
            return
        if self._ts_reaction_exists(event_name, stratagem.name, enemy_unit=attacker_root):
            return
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=candidates[0],
            attacking_unit=attacker_root,
            phase_name=str(phase_name or "").replace("_", " ").title(),
        ):
            return
        payload = {
            "event": event_name,
            "phase_name": str(phase_name or "").replace("_", " ").title(),
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_root,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
            payload["unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_thousand_sons_hexwarp_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        _ = player
        if not self._is_thousand_sons_hexwarp_thrallband_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "COMMAND_PHASE":
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("WARDING HEX")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._ts_hexwarp_warding_hex_candidates()
        if not candidates:
            return
        if self._ts_reaction_exists("phase_start", stratagem.name):
            return
        if not stratagem.can_use(self.player, self.game, unit=candidates[0], phase_name="Command phase"):
            return
        payload: dict[str, Any] = {
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
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_thousand_sons_hexwarp_fall_back_reactions(self, *, unit: Any, action: str) -> None:
        if str(action or "").strip().lower().replace(" ", "_") not in {"fall_back", "fallback"}:
            return
        if not self._is_thousand_sons_hexwarp_thrallband_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return
        if getattr(game, "get_current_player", lambda: None)() is not self.player:
            return
        root = self._ts_root(unit)
        if root is None:
            return
        if not self._ts_owned_by_player(root, self.player):
            return
        if not self._ts_on_battlefield(root, require_targetable=True):
            return
        if not self._is_thousand_sons_unit(root) or not self._is_psyker_unit(root):
            return
        if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("STRANDS OF TIME")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Movement phase"):
            return
        if self._ts_reaction_exists("unit_move_ended", stratagem.name):
            return
        payload: dict[str, Any] = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "action": "fall_back",
            "candidates": [root],
            "flow_of_magic": bool(self._ts_hexwarp_unit_wholly_within_flow(root)),
        }
        if not bool(payload["flow_of_magic"]):
            payload["choice_options"] = self._ts_hexwarp_strands_choice_options()
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_thousand_sons_hexwarp_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> None:
        if not self._is_thousand_sons_hexwarp_thrallband_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        if getattr(game, "get_current_player", lambda: None)() is self.player:
            return
        attacker_root = self._ts_root(attacking_unit)
        if attacker_root is None or self._ts_owned_by_player(attacker_root, self.player):
            return
        if not self._ts_on_battlefield(attacker_root, require_targetable=False):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("KALEIDOSCOPIC TEMPEST")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._ts_hexwarp_kaleidoscopic_tempest_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not candidates:
            return
        if self._ts_reaction_exists("shooting_targets_selected", stratagem.name, enemy_unit=attacker_root):
            return
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=candidates[0],
            attacking_unit=attacker_root,
            phase_name="Shooting phase",
        ):
            return
        payload: dict[str, Any] = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_root,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_thousand_sons_hexwarp_fight_target_reactions(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> None:
        if not self._is_thousand_sons_hexwarp_thrallband_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        attacker_root = self._ts_root(attacking_unit)
        if attacker_root is None or self._ts_owned_by_player(attacker_root, self.player):
            return
        if not self._ts_on_battlefield(attacker_root, require_targetable=False):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("WRATH OF THE DOOMED")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._ts_hexwarp_wrath_of_the_doomed_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not candidates:
            return
        if self._ts_reaction_exists("fight_targets_selected", stratagem.name, enemy_unit=attacker_root):
            return
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=candidates[0],
            attacking_unit=attacker_root,
            phase_name="Fight phase",
        ):
            return
        payload: dict[str, Any] = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_root,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_thousand_sons_hexwarp_reinforcements_step_reactions(self, *, current_player: Any) -> None:
        if not self._is_thousand_sons_hexwarp_thrallband_detachment():
            return
        if current_player is not self.player:
            return
        if str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("THROUGH THE VEIL")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._ts_hexwarp_through_the_veil_candidates()
        if not candidates:
            return
        if self._ts_reaction_exists("reinforcements_step_start", stratagem.name):
            return
        if not stratagem.can_use(self.player, self.game, unit=candidates[0], phase_name="Movement phase"):
            return
        payload: dict[str, Any] = {
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
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _cleanup_thousand_sons_hexwarp_phase_end_effects(self, *, phase: Any) -> None:
        if not self._is_thousand_sons_hexwarp_thrallband_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        cleanup_keys_by_phase = {
            "MOVEMENT_PHASE": (
                "thousand_sons_through_the_veil_active",
                "thousand_sons_through_the_veil_temp_deep_strike",
                "thousand_sons_through_the_veil_turn_owner",
                "thousand_sons_through_the_veil_turn",
                "thousand_sons_through_the_veil_expires_phase",
                "thousand_sons_through_the_veil_source",
                "thousand_sons_through_the_veil_deep_strike_min_distance",
            ),
            "SHOOTING_PHASE": (
                "thousand_sons_scouring_warpflame_active",
                "thousand_sons_scouring_warpflame_turn_owner",
                "thousand_sons_scouring_warpflame_turn",
                "thousand_sons_scouring_warpflame_expires_phase",
                "thousand_sons_scouring_warpflame_source",
            ),
            "FIGHT_PHASE": (
                "thousand_sons_wrath_of_the_doomed_active",
                "thousand_sons_wrath_of_the_doomed_turn_owner",
                "thousand_sons_wrath_of_the_doomed_turn",
                "thousand_sons_wrath_of_the_doomed_source",
                "thousand_sons_wrath_of_the_doomed_expires_phase",
                "thousand_sons_strands_of_time_shoot_active",
                "thousand_sons_strands_of_time_charge_active",
                "thousand_sons_strands_of_time_turn_owner",
                "thousand_sons_strands_of_time_turn",
                "thousand_sons_strands_of_time_source",
                "thousand_sons_strands_of_time_choice",
            ),
        }
        cleanup_keys = cleanup_keys_by_phase.get(phase_key)
        if cleanup_keys is None:
            return
        for root in self._ts_army_roots():
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            for key in cleanup_keys:
                if key in sr:
                    sr.pop(key, None)
                    changed = True
            if not changed:
                continue
            root.special_rules = sr
            if phase_key == "MOVEMENT_PHASE":
                self._ts_clear_ability_cache(root, "deep_strike")
            elif phase_key == "SHOOTING_PHASE":
                self._ts_clear_ability_cache(root, "unit_post_shoot_no_cover_specs")
            elif phase_key == "FIGHT_PHASE":
                self._ts_clear_ability_cache(root, "fell_back_and_shoot", "melee_fight_on_death_after_attacks:")

    def _cleanup_thousand_sons_warpforged_phase_start_effects(self, *, player: Any, phase: Any) -> None:
        if not self._is_thousand_sons_warpforged_cabal_detachment():
            return
        if player is not self.player:
            return
        if str(getattr(phase, "name", "") or "").strip().upper() != "COMMAND_PHASE":
            return
        mgr = self._ts_detachment_mgr()
        clear_fn = getattr(mgr, "clear_warpforged_malevolent_animus", None) if mgr is not None else None
        if not callable(clear_fn):
            return
        for root in self._ts_army_roots():
            if clear_fn(root):
                self._ts_clear_ability_cache(root, "move_advance_charge_modifier_ignore_rule")

    def _queue_thousand_sons_warpforged_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_thousand_sons_warpforged_cabal_detachment():
            return
        if player is not self.player:
            return
        if str(getattr(phase, "name", "") or "").strip().upper() != "COMMAND_PHASE":
            return

        def _queue(name: str, candidates: list[Any]) -> None:
            stratagem = getattr(self, "get_by_name", lambda _name: None)(name)
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
            if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                return
            if not candidates or self._ts_reaction_exists("phase_start", stratagem.name):
                return
            if not stratagem.can_use(self.player, self.game, unit=candidates[0], phase_name="Command phase"):
                return
            payload: dict[str, Any] = {
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
            queue_reaction = getattr(self, "_queue_reaction", None)
            if callable(queue_reaction):
                queue_reaction(payload, use_timer=False)

        _queue("MUTATE LANDSCAPE", self._ts_warpforged_mutate_landscape_candidates())
        _queue("MALEVOLENT ANIMUS", self._ts_warpforged_malevolent_animus_candidates())

    def _queue_thousand_sons_warpforged_fall_back_reactions(self, *, unit: Any, action: str) -> None:
        if str(action or "").strip().lower().replace(" ", "_") not in {"fall_back", "fallback"}:
            return
        if not self._is_thousand_sons_warpforged_cabal_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return
        if getattr(game, "get_current_player", lambda: None)() is not self.player:
            return
        root = self._ts_root(unit)
        if root is None or not self._ts_owned_by_player(root, self.player):
            return
        if not self._ts_on_battlefield(root, require_targetable=True):
            return
        if not self._ts_unit_in_candidates(root, self._ts_warpforged_cyberspirit_machinations_candidates()):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("CYBERSPIRIT MACHINATIONS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ts_reaction_exists("unit_move_ended", stratagem.name):
            return
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Movement phase"):
            return
        payload: dict[str, Any] = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "action": "fall_back",
            "candidates": [root],
        }
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_thousand_sons_warpforged_charge_reactions(self, *, charging_unit: Any, action: str) -> None:
        action_key = str(action or "").strip().lower().replace(" ", "_")
        if action_key not in {"charge", "charge_move"}:
            return
        if not self._is_thousand_sons_warpforged_cabal_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "CHARGE_PHASE":
            return
        if getattr(game, "get_current_player", lambda: None)() is self.player:
            return
        enemy_root = self._ts_root(charging_unit)
        if enemy_root is None or self._ts_owned_by_player(enemy_root, self.player):
            return
        if not self._ts_on_battlefield(enemy_root, require_targetable=False):
            return
        candidates = self._ts_warpforged_warpflame_gargoyles_candidates(charging_unit=enemy_root)
        if not candidates:
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("WARPFLAME GARGOYLES")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ts_reaction_exists("unit_move_ended", stratagem.name, enemy_unit=enemy_root):
            return
        if not stratagem.can_use(self.player, self.game, unit=candidates[0], phase_name="Charge phase"):
            return
        payload: dict[str, Any] = {
            "event": "unit_move_ended",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "attacking_unit": enemy_root,
            "action": "charge",
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _process_thousand_sons_warpforged_mutate_landscape_move_end(self, *, unit: Any, action: Any) -> None:
        if not self._is_thousand_sons_warpforged_cabal_detachment():
            return
        enemy_root = self._ts_root(unit)
        if enemy_root is None or self._ts_owned_by_player(enemy_root, self.player):
            return
        if not self._ts_on_battlefield(enemy_root, require_targetable=False):
            return
        action_key = self._ts_normalize_move_action(action)
        if action_key not in {"normal_move", "advance", "fall_back", "charge"}:
            return
        owner_id = str(getattr(self.player, "id", "") or "")
        if not owner_id:
            return
        game_map = self._ts_game_map()
        apply_mortal_wounds = getattr(enemy_root, "_apply_mortal_wounds_to_unit", None)
        is_within = getattr(enemy_root, "is_within_objective_range", None)
        if game_map is None or not callable(apply_mortal_wounds) or not callable(is_within):
            return

        for objective in list(getattr(game_map, "objectives", []) or []):
            location = getattr(objective, "location", None)
            if location is None or bool(getattr(location, "removed", False)):
                continue
            mutate_sources = getattr(location, "thousand_sons_warpforged_mutate_landscape_sources", None)
            if not isinstance(mutate_sources, dict) or owner_id not in mutate_sources:
                continue
            if (
                getattr(location, "controlling_player", None) is not self.player
                and getattr(location, "sticky_controller", None) is not self.player
            ):
                continue
            if not bool(is_within(location)):
                continue
            trigger_roll = int(dice_module.get_roll("D6") or 0)
            if trigger_roll < 4:
                continue
            mortal_wounds = int(dice_module.get_roll("D3") or 0)
            if mortal_wounds <= 0:
                continue
            apply_mortal_wounds(enemy_root, int(mortal_wounds), game_map=game_map)
            logger.info(
                "INFO: MUTATE LANDSCAPE: %s triggered on %s and dealt %d mortal wound(s).",
                getattr(objective, "name", getattr(objective, "id", "Objective")),
                getattr(enemy_root, "name", "Enemy"),
                int(mortal_wounds),
            )

    def _cleanup_thousand_sons_warpforged_phase_end_effects(self, *, phase: Any) -> None:
        if not self._is_thousand_sons_warpforged_cabal_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        cleanup_keys_by_phase = {
            "SHOOTING_PHASE": (
                "thousand_sons_ensorcelled_infusion_active",
                "thousand_sons_ensorcelled_infusion_owner",
                "thousand_sons_ensorcelled_infusion_turn",
                "thousand_sons_ensorcelled_infusion_expires_phase",
                "thousand_sons_ensorcelled_infusion_source",
            ),
            "FIGHT_PHASE": (
                "thousand_sons_cyberspirit_machinations_shoot_active",
                "thousand_sons_cyberspirit_machinations_charge_active",
                "thousand_sons_cyberspirit_machinations_turn_owner",
                "thousand_sons_cyberspirit_machinations_turn",
                "thousand_sons_cyberspirit_machinations_source",
            ),
        }
        cleanup_keys = cleanup_keys_by_phase.get(phase_key)
        if cleanup_keys is None:
            return
        for root in self._ts_army_roots():
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            for key in cleanup_keys:
                if key in sr:
                    sr.pop(key, None)
                    changed = True
            if not changed:
                continue
            root.special_rules = sr
            if phase_key == "FIGHT_PHASE":
                self._ts_clear_ability_cache(root, "fell_back_and_shoot")

    def _queue_thousand_sons_warpmeld_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_thousand_sons_warpmeld_pact_detachment():
            return
        if player is not self.player:
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()

        def _queue(name: str, phase_name: str, candidates: list[Any]) -> None:
            stratagem = getattr(self, "get_by_name", lambda _name: None)(name)
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
            if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                return
            if not candidates or self._ts_reaction_exists("phase_start", stratagem.name):
                return
            if not stratagem.can_use(self.player, self.game, unit=candidates[0], phase_name=phase_name):
                return
            payload: dict[str, Any] = {
                "event": "phase_start",
                "phase": phase_name,
                "phase_name": phase_name,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            queue_reaction = getattr(self, "_queue_reaction", None)
            if callable(queue_reaction):
                queue_reaction(payload, use_timer=False)

        if phase_key == "COMMAND_PHASE":
            _queue("BLESSED TRANSMUTATIONS", "Command phase", self._ts_warpmeld_blessed_transmutations_candidates())
        elif phase_key == "MOVEMENT_PHASE":
            _queue("TOUCHED BY TZEENTCH", "Movement phase", self._ts_warpmeld_touched_by_tzeentch_candidates())

    def _queue_thousand_sons_warpmeld_reinforcements_step_reactions(self, *, current_player: Any) -> None:
        if not self._is_thousand_sons_warpmeld_pact_detachment():
            return
        if current_player is not self.player:
            return
        if str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("TWISTED MIRAGE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._ts_warpmeld_twisted_mirage_candidates()
        if not candidates:
            return
        if self._ts_reaction_exists("reinforcements_step_start", stratagem.name):
            return
        if not stratagem.can_use(self.player, self.game, unit=candidates[0], phase_name="Movement phase"):
            return
        payload: dict[str, Any] = {
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
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_thousand_sons_warpmeld_fight_unit_selected_reactions(self, *, unit: Any, selecting_player: Any) -> None:
        if not self._is_thousand_sons_warpmeld_pact_detachment():
            return
        if selecting_player is not self.player:
            return
        if str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        candidates = self._ts_warpmeld_deranged_ferocity_candidates(selected_unit=unit)
        if not candidates:
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("DERANGED FEROCITY")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        root = candidates[0]
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "").strip().lower() != "fight_unit_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if self._ts_root(reaction.get("unit") or reaction.get("target_unit")) is root:
                return
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Fight phase"):
            return
        payload: dict[str, Any] = {
            "event": "fight_unit_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "candidates": [root],
        }
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_thousand_sons_warpmeld_model_destroyed_reactions(self, *, unit: Any, model: Any) -> None:
        if not self._is_thousand_sons_warpmeld_pact_detachment():
            return
        if not self._ts_warpmeld_gift_of_change_model_valid(model):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("GIFT OF CHANGE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        try:
            battle_round = int(getattr(self.game, "turn", 0) or 0)
        except (AttributeError, TypeError, ValueError):
            battle_round = 0
        if battle_round and int(getattr(self, "_used_battle_round", {}).get(name_u, 0) or 0) == battle_round:
            return
        model_id = self._ts_sort_key(model)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "").strip().lower() != "model_destroyed_before_removal":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if model_id and str(reaction.get("destroyed_model_id", "") or "") == model_id:
                return
        destroyed_member = getattr(model, "parent_unit", None)
        destroyed_root = self._ts_root(unit)
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().replace("_", " ").title() or "Any phase"
        if not stratagem.can_use(self.player, self.game, unit=destroyed_member or destroyed_root, phase_name=phase_name):
            return
        try:
            destroyed_base = copy.deepcopy(getattr(model, "model_base", None))
        except Exception:
            destroyed_base = None
        payload: dict[str, Any] = {
            "event": "model_destroyed_before_removal",
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": destroyed_member or destroyed_root,
            "target_unit": destroyed_member or destroyed_root,
            "destroyed_unit": destroyed_root,
            "destroyed_model": model,
            "destroyed_model_id": model_id,
            "destroyed_model_base": destroyed_base,
        }
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _resolve_thousand_sons_warpmeld_phase_end_effects(self, *, phase: Any) -> None:
        if not self._is_thousand_sons_warpmeld_pact_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_key:
            return
        pending = self._ts_warpmeld_gift_of_change_pending_entries()
        if not pending:
            return
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        keep: list[dict[str, Any]] = []
        for entry in list(pending):
            if not isinstance(entry, dict):
                continue
            entry_phase = str(entry.get("phase_key", "") or "").strip().upper()
            try:
                entry_turn = int(entry.get("turn", 0) or 0)
            except (TypeError, ValueError):
                entry_turn = 0
            if entry_phase == phase_key and (not current_turn or not entry_turn or entry_turn == current_turn):
                self._ts_warpmeld_resolve_gift_of_change_entry(entry)
                continue
            if current_turn and entry_turn and entry_turn < current_turn:
                continue
            keep.append(entry)
        setattr(self, "_thousand_sons_warpmeld_gift_of_change_pending", keep)

    def _cleanup_thousand_sons_warpmeld_phase_end_effects(self, *, phase: Any) -> None:
        if not self._is_thousand_sons_warpmeld_pact_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        for root in self._ts_army_roots():
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            if phase_key == "MOVEMENT_PHASE":
                for key in (
                    "thousand_sons_twisted_mirage_active",
                    "thousand_sons_twisted_mirage_temp_deep_strike",
                    "thousand_sons_twisted_mirage_turn_owner",
                    "thousand_sons_twisted_mirage_turn",
                    "thousand_sons_twisted_mirage_expires_phase",
                    "thousand_sons_twisted_mirage_source",
                    "thousand_sons_twisted_mirage_deep_strike_min_distance",
                    "thousand_sons_twisted_mirage_no_charge_on_arrival",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
                if changed:
                    root.special_rules = sr
                    self._ts_clear_ability_cache(root, "deep_strike")
                continue
            if phase_key == "FIGHT_PHASE":
                if bool(sr.get("thousand_sons_deranged_ferocity_added_fight_within_3")) and "fight_within_3" in sr:
                    sr.pop("fight_within_3", None)
                    changed = True
                active_source = str(sr.get("fight_within_3_active_source", "") or "").strip().upper()
                if active_source == "DERANGED FEROCITY":
                    sr.pop("fight_within_3_active", None)
                    sr.pop("fight_within_3_active_source", None)
                    changed = True
                for key in (
                    "thousand_sons_touched_by_tzeentch_active",
                    "thousand_sons_touched_by_tzeentch_turn_owner",
                    "thousand_sons_touched_by_tzeentch_turn",
                    "thousand_sons_touched_by_tzeentch_source",
                    "thousand_sons_deranged_ferocity_active",
                    "thousand_sons_deranged_ferocity_turn_owner",
                    "thousand_sons_deranged_ferocity_turn",
                    "thousand_sons_deranged_ferocity_expires_phase",
                    "thousand_sons_deranged_ferocity_source",
                    "thousand_sons_deranged_ferocity_added_fight_within_3",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
                if changed:
                    root.special_rules = sr

    def _queue_thousand_sons_changehost_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        _ = player
        game = getattr(self, "game", None)
        if game is None:
            return
        if not self._is_thousand_sons_changehost_of_deceit_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key == "FIGHT_PHASE":
            active_player = getattr(game, "get_current_player", lambda: None)()
            if active_player is not self.player:
                stratagem = getattr(self, "get_by_name", lambda _name: None)("GLIMMERSHIFT PORTAL")
                if stratagem is not None:
                    if int(getattr(self.player, "command_points", 0) or 0) >= int(getattr(stratagem, "cp_cost", 0) or 0):
                        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
                        if name_u not in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                            candidates = self._ts_glimmershift_portal_candidates()
                            if candidates and not self._ts_reaction_exists("phase_end", stratagem.name):
                                if stratagem.can_use(self.player, self.game, phase_name="Fight phase"):
                                    non_monster_candidates = [unit for unit in candidates if not self._is_monster_unit(unit)]
                                    max_units = 2 if non_monster_candidates else 1
                                    payload: dict[str, Any] = {
                                        "event": "phase_end",
                                        "phase": "Fight phase",
                                        "phase_name": "Fight phase",
                                        "stratagem": stratagem.name,
                                        "cp_cost": stratagem.cp_cost,
                                        "candidates": candidates,
                                        "max_units": int(max_units),
                                    }
                                    if len(candidates) == 1:
                                        payload["unit"] = candidates[0]
                                        payload["target_unit"] = candidates[0]
                                    queue_reaction = getattr(self, "_queue_reaction", None)
                                    if callable(queue_reaction):
                                        queue_reaction(payload, use_timer=False)

        cleanup_keys_by_phase = {
            "CHARGE_PHASE": (
                "thousand_sons_chronosorcerous_bleed_active",
                "thousand_sons_chronosorcerous_bleed_turn_owner",
                "thousand_sons_chronosorcerous_bleed_turn",
                "thousand_sons_chronosorcerous_bleed_source",
                "thousand_sons_chronosorcerous_bleed_expires_phase",
                "thousand_sons_chronosorcerous_bleed_charge_modifier",
            ),
            "SHOOTING_PHASE": (
                "thousand_sons_fractal_disjunction_active",
                "thousand_sons_fractal_disjunction_turn_owner",
                "thousand_sons_fractal_disjunction_turn",
                "thousand_sons_fractal_disjunction_source",
                "thousand_sons_fractal_disjunction_expires_phase",
                "thousand_sons_fractal_disjunction_targeting_range",
            ),
            "FIGHT_PHASE": (
                "thousand_sons_deceptive_glamour_active",
                "thousand_sons_deceptive_glamour_turn_owner",
                "thousand_sons_deceptive_glamour_turn",
                "thousand_sons_deceptive_glamour_source",
                "thousand_sons_deceptive_glamour_expires_phase",
            ),
        }
        cleanup_keys = cleanup_keys_by_phase.get(phase_key)
        if cleanup_keys is None:
            return
        for root in self._ts_army_roots():
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            for key in cleanup_keys:
                if key in sr:
                    sr.pop(key, None)
                    changed = True
            if changed:
                root.special_rules = sr

    def _cleanup_thousand_sons_grand_coven_phase_start_effects(self, *, player: Any, phase: Any) -> None:
        if not self._is_thousand_sons_grand_coven_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "COMMAND_PHASE":
            return
        if player is not self.player:
            return
        mgr = self._ts_detachment_mgr()
        clear_fn = getattr(mgr, "clear_all_grand_coven_overrides", None) if mgr is not None else None
        if callable(clear_fn):
            clear_fn()

    def _cleanup_thousand_sons_grand_coven_phase_end_effects(self, *, phase: Any) -> None:
        if not self._is_thousand_sons_grand_coven_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        cleanup_keys_by_phase = {
            "SHOOTING_PHASE": (
                "thousand_sons_devastating_sorcery_active",
                "thousand_sons_devastating_sorcery_phase_key",
                "thousand_sons_devastating_sorcery_owner",
                "thousand_sons_devastating_sorcery_turn",
                "thousand_sons_devastating_sorcery_source",
                "thousand_sons_psychic_dominion_active",
                "thousand_sons_psychic_dominion_phase_key",
                "thousand_sons_psychic_dominion_owner",
                "thousand_sons_psychic_dominion_turn",
                "thousand_sons_psychic_dominion_source",
                "thousand_sons_psychic_dominion_attacker_unit_id",
            ),
            "FIGHT_PHASE": (
                "thousand_sons_psychic_dominion_active",
                "thousand_sons_psychic_dominion_phase_key",
                "thousand_sons_psychic_dominion_owner",
                "thousand_sons_psychic_dominion_turn",
                "thousand_sons_psychic_dominion_source",
                "thousand_sons_psychic_dominion_attacker_unit_id",
            ),
        }
        cleanup_keys = cleanup_keys_by_phase.get(phase_key)
        if cleanup_keys is None:
            return
        for root in self._ts_army_roots():
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            for key in cleanup_keys:
                if key in sr:
                    sr.pop(key, None)
                    changed = True
            if changed:
                root.special_rules = sr

    def _use_thousand_sons_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if self._is_thousand_sons_rubricae_phalanx_detachment():
            if name_u == "ARDENT AUTOMATA":
                return self._use_thousand_sons_ardent_automata(stratagem, **kwargs)
            if name_u == "INEXORABLE ADVANCE":
                return self._use_thousand_sons_inexorable_advance(stratagem, **kwargs)
            if name_u == "INFERNAL FUSILLADE":
                return self._use_thousand_sons_infernal_fusillade(stratagem, **kwargs)
            if name_u == "IMPLACABLE GUARDIANS":
                return self._use_thousand_sons_implacable_guardians(stratagem, **kwargs)
            if name_u == "UNWAVERING PHALANX":
                return self._use_thousand_sons_unwavering_phalanx(stratagem, **kwargs)
            if name_u == "REVENGE OF THE RUBRICAE":
                return self._use_thousand_sons_revenge_of_the_rubricae(stratagem, **kwargs)
        if self._is_thousand_sons_changehost_of_deceit_detachment():
            if name_u == "CHRONOSORCEROUS BLEED":
                return self._use_thousand_sons_chronosorcerous_bleed(stratagem, **kwargs)
            if name_u == "DECEPTIVE GLAMOUR":
                return self._use_thousand_sons_deceptive_glamour(stratagem, **kwargs)
            if name_u == "ETHEREAL PHANTASM":
                return self._use_thousand_sons_ethereal_phantasm(stratagem, **kwargs)
            if name_u == "FRACTAL DISJUNCTION":
                return self._use_thousand_sons_fractal_disjunction(stratagem, **kwargs)
            if name_u == "GLIMMERSHIFT PORTAL":
                return self._use_thousand_sons_glimmershift_portal(stratagem, **kwargs)
        if self._is_thousand_sons_grand_coven_detachment():
            if name_u == "ARCANE FOCUS":
                return self._use_thousand_sons_arcane_focus(stratagem, **kwargs)
            if name_u == "DESECRATION OF WORLDS":
                return self._use_thousand_sons_desecration_of_worlds(stratagem, **kwargs)
            if name_u == "DESTINED BY FATE":
                return self._use_thousand_sons_destined_by_fate(stratagem, **kwargs)
            if name_u == "DEVASTATING SORCERY":
                return self._use_thousand_sons_devastating_sorcery(stratagem, **kwargs)
            if name_u == "EGOTISTICAL POWER":
                return self._use_thousand_sons_egotistical_power(stratagem, **kwargs)
            if name_u == "PSYCHIC DOMINION":
                return self._use_thousand_sons_psychic_dominion(stratagem, **kwargs)
        if self._is_thousand_sons_warpforged_cabal_detachment():
            if name_u == "MUTATE LANDSCAPE":
                return self._use_thousand_sons_mutate_landscape(stratagem, **kwargs)
            if name_u == "MALEVOLENT ANIMUS":
                return self._use_thousand_sons_malevolent_animus(stratagem, **kwargs)
            if name_u == "CYBERSPIRIT MACHINATIONS":
                return self._use_thousand_sons_cyberspirit_machinations(stratagem, **kwargs)
            if name_u == "ENSORCELLED INFUSION":
                return self._use_thousand_sons_ensorcelled_infusion(stratagem, **kwargs)
            if name_u == "WARPFLAME GARGOYLES":
                return self._use_thousand_sons_warpflame_gargoyles(stratagem, **kwargs)
        if self._is_thousand_sons_hexwarp_thrallband_detachment():
            if name_u == "WARDING HEX":
                return self._use_thousand_sons_warding_hex(stratagem, **kwargs)
            if name_u == "WRATH OF THE DOOMED":
                return self._use_thousand_sons_wrath_of_the_doomed(stratagem, **kwargs)
            if name_u == "STRANDS OF TIME":
                return self._use_thousand_sons_strands_of_time(stratagem, **kwargs)
            if name_u == "THROUGH THE VEIL":
                return self._use_thousand_sons_through_the_veil(stratagem, **kwargs)
            if name_u == "SCOURING WARPFLAME":
                return self._use_thousand_sons_scouring_warpflame(stratagem, **kwargs)
            if name_u == "KALEIDOSCOPIC TEMPEST":
                return self._use_thousand_sons_kaleidoscopic_tempest(stratagem, **kwargs)
        if self._is_thousand_sons_warpmeld_pact_detachment():
            if name_u == "GIFT OF CHANGE":
                return self._use_thousand_sons_gift_of_change(stratagem, **kwargs)
            if name_u == "DERANGED FEROCITY":
                return self._use_thousand_sons_deranged_ferocity(stratagem, **kwargs)
            if name_u == "BLESSED TRANSMUTATIONS":
                return self._use_thousand_sons_blessed_transmutations(stratagem, **kwargs)
            if name_u == "TOUCHED BY TZEENTCH":
                return self._use_thousand_sons_touched_by_tzeentch(stratagem, **kwargs)
            if name_u == "TWISTED MIRAGE":
                return self._use_thousand_sons_twisted_mirage(stratagem, **kwargs)
        return None

    def _use_thousand_sons_mutate_landscape(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        objective = kwargs.get("objective") or kwargs.get("objective_marker")
        objective_candidates = list(kwargs.get("objective_candidates") or [])
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None or (objective is None and not objective_candidates):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: MUTATE LANDSCAPE: no target unit provided")
            return False
        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: MUTATE LANDSCAPE: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_thousand_sons_unit(root) or not self._is_psyker_unit(root):
            logger.error("ERROR: MUTATE LANDSCAPE: target must be a THOUSAND SONS PSYKER unit")
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "command phase":
            logger.error("ERROR: MUTATE LANDSCAPE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: MUTATE LANDSCAPE: not your turn")
            return False
        eligible = candidates or self._ts_warpforged_mutate_landscape_candidates()
        if eligible and not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: MUTATE LANDSCAPE: selected unit is not currently eligible")
            return False
        if not objective_candidates:
            objective_candidates = self._ts_warpforged_mutate_landscape_objective_candidates(root)
        if objective is None and objective_candidates:
            objective = objective_candidates[0]
        if objective is None:
            logger.error("ERROR: MUTATE LANDSCAPE: no controlled objective marker is in range")
            return False
        if objective_candidates and objective not in list(objective_candidates or []):
            logger.error("ERROR: MUTATE LANDSCAPE: selected objective is not eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Command phase"):
            logger.error("ERROR: MUTATE LANDSCAPE: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        location = getattr(objective, "location", None)
        if location is None:
            logger.error("ERROR: MUTATE LANDSCAPE: objective marker is missing its location")
            return False
        set_sticky_control = getattr(location, "set_sticky_control", None)
        if callable(set_sticky_control):
            set_sticky_control(self.player, source="mutate_landscape")
        else:
            location.sticky_controller = self.player
            location.controlling_player = self.player
            location.sticky_source = "mutate_landscape"
        owner_id = str(getattr(self.player, "id", "") or "")
        mutation_sources = getattr(location, "thousand_sons_warpforged_mutate_landscape_sources", None)
        if not isinstance(mutation_sources, dict):
            mutation_sources = {}
        mutation_sources[owner_id] = str(getattr(stratagem, "name", "") or "MUTATE LANDSCAPE")
        location.thousand_sons_warpforged_mutate_landscape_sources = mutation_sources

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MUTATE LANDSCAPE: %s mutated objective %s.",
            getattr(root, "name", "Unit"),
            getattr(objective, "id", getattr(objective, "name", "objective")),
        )
        return True

    def _use_thousand_sons_malevolent_animus(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                target_unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: MALEVOLENT ANIMUS: no target unit provided")
            return False
        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: MALEVOLENT ANIMUS: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_thousand_sons_vehicle_unit(root):
            logger.error("ERROR: MALEVOLENT ANIMUS: target must be a THOUSAND SONS VEHICLE unit")
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "command phase":
            logger.error("ERROR: MALEVOLENT ANIMUS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: MALEVOLENT ANIMUS: not your turn")
            return False
        eligible = candidates or self._ts_warpforged_malevolent_animus_candidates()
        if eligible and not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: MALEVOLENT ANIMUS: target is not eligible")
            return False
        if not self._ts_warpforged_supporting_psyker_candidates(root, distance=6.0):
            logger.error("ERROR: MALEVOLENT ANIMUS: requires a friendly THOUSAND SONS PSYKER within 6\"")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Command phase"):
            logger.error("ERROR: MALEVOLENT ANIMUS: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["thousand_sons_malevolent_animus_active"] = True
        sr["thousand_sons_malevolent_animus_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["thousand_sons_malevolent_animus_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["thousand_sons_malevolent_animus_source"] = str(getattr(stratagem, "name", "") or "MALEVOLENT ANIMUS")
        root.special_rules = sr
        self._ts_clear_ability_cache(root, "move_advance_charge_modifier_ignore_rule")

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MALEVOLENT ANIMUS: %s ignores modifiers until your next Command phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_cyberspirit_machinations(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                target_unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: CYBERSPIRIT MACHINATIONS: no target unit provided")
            return False
        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: CYBERSPIRIT MACHINATIONS: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_thousand_sons_vehicle_unit(root):
            logger.error("ERROR: CYBERSPIRIT MACHINATIONS: target must be a THOUSAND SONS VEHICLE unit")
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "movement phase":
            logger.error("ERROR: CYBERSPIRIT MACHINATIONS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: CYBERSPIRIT MACHINATIONS: not your turn")
            return False
        if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
            logger.error("ERROR: CYBERSPIRIT MACHINATIONS: target must have Fallen Back")
            return False
        eligible = candidates or self._ts_warpforged_cyberspirit_machinations_candidates()
        if eligible and not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: CYBERSPIRIT MACHINATIONS: target is not eligible")
            return False
        if not self._ts_warpforged_supporting_psyker_candidates(root, distance=6.0):
            logger.error("ERROR: CYBERSPIRIT MACHINATIONS: requires a friendly THOUSAND SONS PSYKER within 6\"")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: CYBERSPIRIT MACHINATIONS: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["thousand_sons_cyberspirit_machinations_shoot_active"] = True
        sr["thousand_sons_cyberspirit_machinations_charge_active"] = True
        sr["thousand_sons_cyberspirit_machinations_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["thousand_sons_cyberspirit_machinations_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["thousand_sons_cyberspirit_machinations_source"] = str(getattr(stratagem, "name", "") or "CYBERSPIRIT MACHINATIONS")
        root.special_rules = sr
        self._ts_clear_ability_cache(root, "fell_back_and_shoot")

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CYBERSPIRIT MACHINATIONS: %s can shoot and charge after Falling Back this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_ensorcelled_infusion(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: ENSORCELLED INFUSION: no target unit provided")
            return False
        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: ENSORCELLED INFUSION: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_thousand_sons_vehicle_unit(root):
            logger.error("ERROR: ENSORCELLED INFUSION: target must be a THOUSAND SONS VEHICLE unit")
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: ENSORCELLED INFUSION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: ENSORCELLED INFUSION: not your turn")
            return False
        if self._ts_has_shot_this_phase(root):
            logger.error("ERROR: ENSORCELLED INFUSION: target has already shot this phase")
            return False
        eligible = candidates or self._ts_warpforged_ensorcelled_infusion_candidates()
        if eligible and not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: ENSORCELLED INFUSION: target is not eligible")
            return False
        if not self._ts_warpforged_supporting_psyker_candidates(root, distance=6.0):
            logger.error("ERROR: ENSORCELLED INFUSION: requires a friendly THOUSAND SONS PSYKER within 6\"")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: ENSORCELLED INFUSION: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["thousand_sons_ensorcelled_infusion_active"] = True
        sr["thousand_sons_ensorcelled_infusion_owner"] = str(getattr(self.player, "id", "") or "")
        sr["thousand_sons_ensorcelled_infusion_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["thousand_sons_ensorcelled_infusion_expires_phase"] = "SHOOTING_PHASE"
        sr["thousand_sons_ensorcelled_infusion_source"] = str(getattr(stratagem, "name", "") or "ENSORCELLED INFUSION")
        root.special_rules = sr

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ENSORCELLED INFUSION: %s gains [PSYCHIC] and +1 to wound on ranged attacks this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_warpflame_gargoyles(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None or attacking_unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None or attacking_unit is None:
            logger.error("ERROR: WARPFLAME GARGOYLES: missing target or enemy unit")
            return False
        root = self._ts_root(target_unit)
        enemy_root = self._ts_root(attacking_unit)
        if root is None or enemy_root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: WARPFLAME GARGOYLES: target unit is not yours")
            return False
        if self._ts_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: WARPFLAME GARGOYLES: enemy unit is invalid")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._ts_on_battlefield(enemy_root, require_targetable=False):
            return False
        if not self._is_thousand_sons_vehicle_unit(root):
            logger.error("ERROR: WARPFLAME GARGOYLES: target must be a THOUSAND SONS VEHICLE unit")
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "charge phase":
            logger.error("ERROR: WARPFLAME GARGOYLES: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: WARPFLAME GARGOYLES: only usable in your opponent's turn")
            return False
        eligible = candidates or self._ts_warpforged_warpflame_gargoyles_candidates(charging_unit=enemy_root)
        if eligible and not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: WARPFLAME GARGOYLES: target is not eligible")
            return False
        game_map = self._ts_game_map()
        if game_map is None or not bool(getattr(game_map, "is_within_engagement_range", lambda _a, _b: False)(root, enemy_root)):
            logger.error("ERROR: WARPFLAME GARGOYLES: enemy unit must be within Engagement Range")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Charge phase"):
            logger.error("ERROR: WARPFLAME GARGOYLES: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        rolls = [int(dice_module.get_roll("D6") or 0) for _ in range(6)]
        mortal_wounds = sum(1 for roll in rolls if int(roll) >= 5)
        apply_mortal_wounds = getattr(root, "_apply_mortal_wounds_to_unit", None)
        if callable(apply_mortal_wounds) and mortal_wounds > 0:
            apply_mortal_wounds(enemy_root, int(mortal_wounds), game_map=game_map)
        take_battle_shock = getattr(enemy_root, "take_battle_shock_test", None)
        if callable(take_battle_shock):
            take_battle_shock(int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0)

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: WARPFLAME GARGOYLES: %s rolled %s and dealt %d mortal wound(s) to %s before a Battle-shock test.",
            getattr(root, "name", "Unit"),
            rolls,
            int(mortal_wounds),
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_thousand_sons_gift_of_change(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("destroyed_unit")
        destroyed_model = kwargs.get("destroyed_model") or kwargs.get("model") or kwargs.get("target_model")
        destroyed_base = kwargs.get("destroyed_model_base")
        candidates = list(kwargs.get("candidates") or [])
        if destroyed_model is None or target_unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit") or reaction.get("destroyed_unit")
                if destroyed_model is None:
                    destroyed_model = reaction.get("destroyed_model") or reaction.get("model") or reaction.get("target_model")
                if destroyed_base is None:
                    destroyed_base = reaction.get("destroyed_model_base")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        destroyed_member = getattr(destroyed_model, "parent_unit", None) if destroyed_model is not None else None
        root = self._ts_root(target_unit) if target_unit is not None else self._ts_root(destroyed_member)
        if root is None or destroyed_model is None:
            logger.error("ERROR: GIFT OF CHANGE: missing destroyed model context")
            return False
        if not self._ts_warpmeld_gift_of_change_model_valid(destroyed_model):
            logger.error("ERROR: GIFT OF CHANGE: target must be a just-destroyed non-MONSTER THOUSAND SONS CHARACTER model")
            return False
        if candidates and not self._ts_unit_in_candidates(destroyed_member or root, candidates):
            logger.error("ERROR: GIFT OF CHANGE: selected target is not currently eligible")
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().replace("_", " ").title() or "Any phase"
        if not stratagem.can_use(self.player, self.game, unit=destroyed_member or root, phase_name=phase_name):
            logger.error("ERROR: GIFT OF CHANGE: cannot be used in current state")
            return False
        try:
            battle_round = int(getattr(self.game, "turn", 0) or 0)
        except (AttributeError, TypeError, ValueError):
            battle_round = 0
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if battle_round and int(getattr(self, "_used_battle_round", {}).get(name_u, 0) or 0) == battle_round:
            logger.error("ERROR: GIFT OF CHANGE: already used this battle round")
            return False
        if destroyed_base is None:
            try:
                destroyed_base = copy.deepcopy(getattr(destroyed_model, "model_base", None))
            except (AttributeError, TypeError, ValueError):
                destroyed_base = None
        if destroyed_base is None:
            logger.error("ERROR: GIFT OF CHANGE: missing destroyed model position")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=destroyed_member or root):
            return False

        phase_key = str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper()
        if not phase_key and phase_name:
            phase_key = str(phase_name).strip().upper().replace(" ", "_")
        self._ts_warpmeld_gift_of_change_pending_entries().append(
            {
                "phase_key": phase_key,
                "turn": battle_round,
                "destroyed_model_id": self._ts_sort_key(destroyed_model),
                "destroyed_model_name": str(getattr(destroyed_model, "name", "") or "Character"),
                "destroyed_model_base": destroyed_base,
                "source": str(getattr(stratagem, "name", "") or "GIFT OF CHANGE"),
            }
        )
        if battle_round:
            self._used_battle_round[name_u] = int(battle_round)

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: GIFT OF CHANGE: %s will spawn a Chaos Spawn at the end of the phase.",
            getattr(destroyed_model, "name", "Character"),
        )
        return True

    def _use_thousand_sons_deranged_ferocity(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: DERANGED FEROCITY: no target unit provided")
            return False
        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: DERANGED FEROCITY: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tzeentch_mutant_unit(root):
            logger.error("ERROR: DERANGED FEROCITY: target must be a TZEENTCH MUTANT unit")
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "fight phase":
            logger.error("ERROR: DERANGED FEROCITY: wrong phase")
            return False
        round_state = getattr(root, "round_state", None)
        if bool(getattr(round_state, "fought_this_phase", False)):
            logger.error("ERROR: DERANGED FEROCITY: target already fought this phase")
            return False
        eligible = candidates or self._ts_warpmeld_deranged_ferocity_candidates(selected_unit=root)
        if eligible and not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: DERANGED FEROCITY: target is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: DERANGED FEROCITY: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "DERANGED FEROCITY").strip() or "DERANGED FEROCITY"
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if not sr.get("fight_within_3"):
            sr["fight_within_3"] = [{"name": source_name}]
            sr["thousand_sons_deranged_ferocity_added_fight_within_3"] = True
        set_active = getattr(root, "set_fight_within_3_active", None)
        if callable(set_active):
            root.special_rules = sr
            set_active(True, source=source_name)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
        else:
            sr["fight_within_3_active"] = True
            sr["fight_within_3_active_source"] = source_name
        sr["stratagem_pile_in_distance_override"] = max(6.0, float(sr.get("stratagem_pile_in_distance_override", 0.0) or 0.0))
        sr["stratagem_pile_in_expires_phase"] = "FIGHT_PHASE"
        sr["stratagem_pile_in_source"] = source_name
        sr["stratagem_consolidate_distance_override"] = max(
            6.0,
            float(sr.get("stratagem_consolidate_distance_override", 0.0) or 0.0),
        )
        sr["stratagem_consolidate_expires_phase"] = "FIGHT_PHASE"
        sr["stratagem_consolidate_source"] = source_name
        sr["thousand_sons_deranged_ferocity_active"] = True
        sr["thousand_sons_deranged_ferocity_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["thousand_sons_deranged_ferocity_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["thousand_sons_deranged_ferocity_expires_phase"] = "FIGHT_PHASE"
        sr["thousand_sons_deranged_ferocity_source"] = source_name
        root.special_rules = sr

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DERANGED FEROCITY: %s can pile in/consolidate 6\" and fight with models within 3\" this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_blessed_transmutations(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        psyker_model = kwargs.get("psyker_model") or kwargs.get("model") or kwargs.get("source_model")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: BLESSED TRANSMUTATIONS: no target unit provided")
            return False
        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: BLESSED TRANSMUTATIONS: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tzaangors_unit(root):
            logger.error("ERROR: BLESSED TRANSMUTATIONS: target must be a TZAANGORS unit")
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "command phase":
            logger.error("ERROR: BLESSED TRANSMUTATIONS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: BLESSED TRANSMUTATIONS: not your turn")
            return False
        eligible = candidates or self._ts_warpmeld_blessed_transmutations_candidates()
        if eligible and not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: BLESSED TRANSMUTATIONS: target is not currently eligible")
            return False
        if not self._ts_is_below_starting_strength(root):
            logger.error("ERROR: BLESSED TRANSMUTATIONS: target must be below Starting Strength")
            return False
        destroyed_candidates = self._ts_returnable_destroyed_non_character_models(root)
        if not destroyed_candidates:
            logger.error("ERROR: BLESSED TRANSMUTATIONS: target has no eligible destroyed models to return")
            return False
        supporting_psykers = self._ts_warpmeld_supporting_psyker_candidates(root, distance=12.0)
        if not supporting_psykers:
            logger.error("ERROR: BLESSED TRANSMUTATIONS: requires a friendly THOUSAND SONS PSYKER within 12\"")
            return False
        if psyker_model is not None:
            psyker_root = self._ts_root(getattr(psyker_model, "parent_unit", None) or psyker_model)
            if psyker_root not in supporting_psykers or not self._ts_model_is_psyker(psyker_model, unit=psyker_root):
                logger.error("ERROR: BLESSED TRANSMUTATIONS: selected PSYKER model is not eligible")
                return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Command phase"):
            logger.error("ERROR: BLESSED TRANSMUTATIONS: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        return_full = getattr(self, "_return_destroyed_models_full", None)
        if not callable(return_full):
            logger.error("ERROR: BLESSED TRANSMUTATIONS: destroyed-model return helper is unavailable")
            return False
        amount = int(dice_module.get_roll("D3") or 0) + 1
        returned = int(
            return_full(
                root,
                amount=amount,
                game_map=self._ts_game_map(),
                skip_character=True,
            )
            or 0
        )

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: BLESSED TRANSMUTATIONS: %s returned %d model(s).",
            getattr(root, "name", "Unit"),
            int(returned),
        )
        return True

    def _use_thousand_sons_touched_by_tzeentch(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: TOUCHED BY TZEENTCH: no target unit provided")
            return False
        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: TOUCHED BY TZEENTCH: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tzeentch_mutant_unit(root):
            logger.error("ERROR: TOUCHED BY TZEENTCH: target must be a TZEENTCH MUTANT unit")
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "movement phase":
            logger.error("ERROR: TOUCHED BY TZEENTCH: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: TOUCHED BY TZEENTCH: not your turn")
            return False
        eligible = candidates or self._ts_warpmeld_touched_by_tzeentch_candidates()
        if eligible and not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: TOUCHED BY TZEENTCH: target is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: TOUCHED BY TZEENTCH: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["thousand_sons_touched_by_tzeentch_active"] = True
        sr["thousand_sons_touched_by_tzeentch_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["thousand_sons_touched_by_tzeentch_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["thousand_sons_touched_by_tzeentch_source"] = str(getattr(stratagem, "name", "") or "TOUCHED BY TZEENTCH")
        root.special_rules = sr

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TOUCHED BY TZEENTCH: %s can shoot and charge after Advancing this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_twisted_mirage(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: TWISTED MIRAGE: no target unit provided")
            return False
        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: TWISTED MIRAGE: target unit is not yours")
            return False
        reserve_status = str(getattr(root, "reserve_status", "") or "").strip().lower()
        if reserve_status != "strategic_reserves":
            logger.error("ERROR: TWISTED MIRAGE: target must be in Strategic Reserves")
            return False
        if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
            logger.error("ERROR: TWISTED MIRAGE: embarked units are not eligible")
            return False
        if not self._is_tzeentch_mutant_unit(root):
            logger.error("ERROR: TWISTED MIRAGE: target must be a TZEENTCH MUTANT unit")
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "movement phase":
            logger.error("ERROR: TWISTED MIRAGE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: TWISTED MIRAGE: not your turn")
            return False
        eligible = candidates or self._ts_warpmeld_twisted_mirage_candidates()
        if eligible and not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: TWISTED MIRAGE: target is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: TWISTED MIRAGE: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        min_distance = 9.0 if self._is_monster_unit(root) else 6.0
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["thousand_sons_twisted_mirage_active"] = True
        sr["thousand_sons_twisted_mirage_temp_deep_strike"] = True
        sr["thousand_sons_twisted_mirage_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["thousand_sons_twisted_mirage_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["thousand_sons_twisted_mirage_expires_phase"] = "MOVEMENT_PHASE"
        sr["thousand_sons_twisted_mirage_source"] = str(getattr(stratagem, "name", "") or "TWISTED MIRAGE")
        sr["thousand_sons_twisted_mirage_deep_strike_min_distance"] = float(min_distance)
        sr["thousand_sons_twisted_mirage_no_charge_on_arrival"] = True
        root.special_rules = sr
        self._ts_clear_ability_cache(root, "deep_strike")

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TWISTED MIRAGE: %s can arrive more than %.0f\" horizontally from enemy units and cannot charge this turn.",
            getattr(root, "name", "Unit"),
            float(min_distance),
        )
        return True

    def _use_thousand_sons_warding_hex(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        objective = kwargs.get("objective") or kwargs.get("objective_marker")
        objective_candidates = list(kwargs.get("objective_candidates") or [])
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None or (objective is None and not objective_candidates):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: WARDING HEX: no target unit provided")
            return False
        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: WARDING HEX: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_thousand_sons_unit(root) or not self._is_psyker_unit(root):
            logger.error("ERROR: WARDING HEX: target must be a THOUSAND SONS PSYKER unit")
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "command phase":
            logger.error("ERROR: WARDING HEX: wrong phase")
            return False
        eligible = candidates or self._ts_hexwarp_warding_hex_candidates()
        if eligible and not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: WARDING HEX: selected unit is not currently eligible")
            return False
        if not objective_candidates:
            objective_candidates = self._ts_hexwarp_warding_hex_objective_candidates(root)
        if objective is None and objective_candidates:
            objective = objective_candidates[0]
        if objective is None:
            logger.error("ERROR: WARDING HEX: no controlled objective wholly within Flow of Magic is in range")
            return False
        if objective_candidates and objective not in list(objective_candidates or []):
            logger.error("ERROR: WARDING HEX: selected objective is not eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Command phase"):
            logger.error("ERROR: WARDING HEX: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False
        location = getattr(objective, "location", None)
        if location is None:
            logger.error("ERROR: WARDING HEX: objective marker is missing its location")
            return False
        set_sticky_control = getattr(location, "set_sticky_control", None)
        if callable(set_sticky_control):
            set_sticky_control(self.player, source="warding_hex")
        else:
            location.sticky_controller = self.player
            location.controlling_player = self.player
            location.sticky_source = "warding_hex"
        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: WARDING HEX: %s made objective %s sticky while it remains wholly within Flow of Magic.",
            getattr(root, "name", "Unit"),
            getattr(objective, "id", getattr(objective, "name", "objective")),
        )
        return True

    def _use_thousand_sons_wrath_of_the_doomed(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or [])
        if target_unit is None or attacking_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: WRATH OF THE DOOMED: no target unit provided")
            return False
        root = self._ts_root(target_unit)
        attacker_root = self._ts_root(attacking_unit)
        if root is None or attacker_root is None:
            logger.error("ERROR: WRATH OF THE DOOMED: missing attacker context")
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: WRATH OF THE DOOMED: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_thousand_sons_unit(root):
            logger.error("ERROR: WRATH OF THE DOOMED: target must be a THOUSAND SONS unit")
            return False
        if self._ts_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: WRATH OF THE DOOMED: attacker is not an enemy unit")
            return False
        if not self._ts_on_battlefield(attacker_root, require_targetable=False):
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "fight phase":
            logger.error("ERROR: WRATH OF THE DOOMED: wrong phase")
            return False
        eligible = candidates or self._ts_hexwarp_wrath_of_the_doomed_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if eligible and not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: WRATH OF THE DOOMED: target must have been selected by the attacking enemy unit")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=root,
            attacking_unit=attacker_root,
            phase_name="Fight phase",
        ):
            logger.error("ERROR: WRATH OF THE DOOMED: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["thousand_sons_wrath_of_the_doomed_active"] = True
        sr["thousand_sons_wrath_of_the_doomed_turn_owner"] = str(getattr(active_player, "id", "") or "")
        sr["thousand_sons_wrath_of_the_doomed_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["thousand_sons_wrath_of_the_doomed_source"] = str(getattr(stratagem, "name", "") or "WRATH OF THE DOOMED")
        sr["thousand_sons_wrath_of_the_doomed_expires_phase"] = "FIGHT_PHASE"
        root.special_rules = sr
        self._ts_clear_ability_cache(root, "melee_fight_on_death_after_attacks:")
        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: WRATH OF THE DOOMED: %s gains melee fight-on-death until end of phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_strands_of_time(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        action = kwargs.get("action")
        choice_key = self._ts_choice_key(kwargs.get("choice"))
        if target_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if action is None:
                    action = reaction.get("action")
                if not choice_key:
                    choice_key = self._ts_choice_key(reaction.get("choice"))
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: STRANDS OF TIME: no target unit provided")
            return False
        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: STRANDS OF TIME: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_thousand_sons_unit(root) or not self._is_psyker_unit(root):
            logger.error("ERROR: STRANDS OF TIME: target must be a THOUSAND SONS PSYKER unit")
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "movement phase":
            logger.error("ERROR: STRANDS OF TIME: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: STRANDS OF TIME: not your Movement phase")
            return False
        action_key = str(action or "").strip().lower().replace(" ", "_")
        if action_key and action_key not in {"fall_back", "fallback"}:
            logger.error("ERROR: STRANDS OF TIME: wrong trigger")
            return False
        if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
            logger.error("ERROR: STRANDS OF TIME: target must have Fallen Back this phase")
            return False
        eligible = candidates or self._ts_hexwarp_psyker_candidates(require_fell_back=True)
        if eligible and not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: STRANDS OF TIME: selected unit is not currently eligible")
            return False
        in_flow = self._ts_hexwarp_unit_wholly_within_flow(root)
        if not in_flow and choice_key not in {"SHOOT", "CHARGE"}:
            logger.error("ERROR: STRANDS OF TIME: choice must be SHOOT or CHARGE when outside Flow of Magic")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: STRANDS OF TIME: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False
        grant_shoot = bool(in_flow or choice_key == "SHOOT")
        grant_charge = bool(in_flow or choice_key == "CHARGE")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["thousand_sons_strands_of_time_shoot_active"] = grant_shoot
        sr["thousand_sons_strands_of_time_charge_active"] = grant_charge
        sr["thousand_sons_strands_of_time_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["thousand_sons_strands_of_time_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["thousand_sons_strands_of_time_source"] = str(getattr(stratagem, "name", "") or "STRANDS OF TIME")
        sr["thousand_sons_strands_of_time_choice"] = "BOTH" if in_flow else str(choice_key or "")
        root.special_rules = sr
        self._ts_clear_ability_cache(root, "fell_back_and_shoot")
        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: STRANDS OF TIME: %s can %s after Falling Back this turn.",
            getattr(root, "name", "Unit"),
            "shoot and charge" if in_flow else str(choice_key or "").strip().lower(),
        )
        return True

    def _use_thousand_sons_through_the_veil(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: THROUGH THE VEIL: no target unit provided")
            return False
        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: THROUGH THE VEIL: target unit is not yours")
            return False
        reserve_status = str(getattr(root, "reserve_status", "") or "").strip().lower()
        if reserve_status != "strategic_reserves":
            logger.error("ERROR: THROUGH THE VEIL: target must be in Strategic Reserves")
            return False
        if not (self._is_rubric_marines_unit(root) or self._is_scarab_occult_terminators_unit(root)):
            logger.error("ERROR: THROUGH THE VEIL: target must be RUBRIC MARINES or SCARAB OCCULT TERMINATORS")
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "movement phase":
            logger.error("ERROR: THROUGH THE VEIL: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: THROUGH THE VEIL: not your Movement phase")
            return False
        eligible = candidates or self._ts_hexwarp_through_the_veil_candidates()
        if eligible and not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: THROUGH THE VEIL: selected unit is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: THROUGH THE VEIL: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["thousand_sons_through_the_veil_active"] = True
        sr["thousand_sons_through_the_veil_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["thousand_sons_through_the_veil_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["thousand_sons_through_the_veil_expires_phase"] = "MOVEMENT_PHASE"
        sr["thousand_sons_through_the_veil_source"] = str(getattr(stratagem, "name", "") or "THROUGH THE VEIL")
        if self._is_rubric_marines_unit(root):
            sr["thousand_sons_through_the_veil_temp_deep_strike"] = True
        if self._is_scarab_occult_terminators_unit(root):
            sr["thousand_sons_through_the_veil_deep_strike_min_distance"] = 6.0
        root.special_rules = sr
        self._ts_clear_ability_cache(root, "deep_strike")
        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: THROUGH THE VEIL: %s can arrive using Hexwarp Deep Strike permissions this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_scouring_warpflame(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: SCOURING WARPFLAME: no target unit provided")
            return False
        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: SCOURING WARPFLAME: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_thousand_sons_unit(root) or not self._is_psyker_unit(root):
            logger.error("ERROR: SCOURING WARPFLAME: target must be a THOUSAND SONS PSYKER unit")
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: SCOURING WARPFLAME: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SCOURING WARPFLAME: not your Shooting phase")
            return False
        eligible = candidates or self._ts_hexwarp_scouring_warpflame_candidates()
        if eligible and not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: SCOURING WARPFLAME: target must be wholly within Flow of Magic and not yet selected to shoot")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: SCOURING WARPFLAME: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["thousand_sons_scouring_warpflame_active"] = True
        sr["thousand_sons_scouring_warpflame_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["thousand_sons_scouring_warpflame_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["thousand_sons_scouring_warpflame_expires_phase"] = "SHOOTING_PHASE"
        sr["thousand_sons_scouring_warpflame_source"] = str(getattr(stratagem, "name", "") or "SCOURING WARPFLAME")
        root.special_rules = sr
        self._ts_clear_ability_cache(root, "unit_post_shoot_no_cover_specs")
        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SCOURING WARPFLAME: %s gains Ignores Cover and post-shoot no-cover selection this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_kaleidoscopic_tempest(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or [])
        if target_unit is None or attacking_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: KALEIDOSCOPIC TEMPEST: no target unit provided")
            return False
        root = self._ts_root(target_unit)
        attacker_root = self._ts_root(attacking_unit)
        if root is None or attacker_root is None:
            logger.error("ERROR: KALEIDOSCOPIC TEMPEST: missing attacker context")
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: KALEIDOSCOPIC TEMPEST: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_thousand_sons_unit(root) or not self._is_psyker_unit(root):
            logger.error("ERROR: KALEIDOSCOPIC TEMPEST: target must be a THOUSAND SONS PSYKER unit")
            return False
        if self._ts_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: KALEIDOSCOPIC TEMPEST: attacker is not an enemy unit")
            return False
        if not self._ts_on_battlefield(attacker_root, require_targetable=False):
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: KALEIDOSCOPIC TEMPEST: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: KALEIDOSCOPIC TEMPEST: not opponent's Shooting phase")
            return False
        eligible = candidates or self._ts_hexwarp_kaleidoscopic_tempest_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if eligible and not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: KALEIDOSCOPIC TEMPEST: target must have been selected by the attacking enemy unit")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=root,
            attacking_unit=attacker_root,
            phase_name="Shooting phase",
        ):
            logger.error("ERROR: KALEIDOSCOPIC TEMPEST: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["opponent_shooting_phase_stealth_active"] = True
        sr["opponent_shooting_phase_stealth_owner"] = str(getattr(active_player, "id", "") or "")
        sr["opponent_shooting_phase_stealth_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["opponent_shooting_phase_stealth_source"] = str(getattr(stratagem, "name", "") or "KALEIDOSCOPIC TEMPEST")
        sr["opponent_shooting_phase_stealth_expires_phase"] = "SHOOTING_PHASE"
        root.special_rules = sr
        if self._ts_hexwarp_unit_wholly_within_flow(root):
            self._append_defensive_effect(
                root,
                "defensive_cover_bonuses",
                {
                    "attack_type": "ranged",
                    "expires_phase": "SHOOTING_PHASE",
                    "source": str(getattr(stratagem, "name", "") or "KALEIDOSCOPIC TEMPEST"),
                },
            )
        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: KALEIDOSCOPIC TEMPEST: %s gains Stealth%s until end of phase.",
            getattr(root, "name", "Unit"),
            " and Benefit of Cover" if self._ts_hexwarp_unit_wholly_within_flow(root) else "",
        )
        return True

    def _use_thousand_sons_arcane_focus(self, stratagem: Any, **kwargs) -> bool:
        caster_model = kwargs.get("caster_model") or kwargs.get("target_model") or kwargs.get("model")
        rolls_state = kwargs.get("rolls_state")
        current_rolls = list(kwargs.get("current_rolls") or [])
        if not current_rolls and isinstance(rolls_state, dict):
            current_rolls = list(rolls_state.get("rolls") or [])
        if caster_model is None or not current_rolls:
            logger.error("ERROR: ARCANE FOCUS: missing caster model or psychic test rolls")
            return False
        mgr = self._ts_detachment_mgr()
        eligible_fn = getattr(mgr, "grand_coven_model_is_thousand_sons_psyker", None) if mgr is not None else None
        if not callable(eligible_fn) or not bool(eligible_fn(caster_model, game=self.game)):
            logger.error("ERROR: ARCANE FOCUS: target model must be a THOUSAND SONS PSYKER model from your army")
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: ARCANE FOCUS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: ARCANE FOCUS: not your turn")
            return False
        if kwargs.get("channeled") is False:
            logger.error("ERROR: ARCANE FOCUS: trigger requires Channel the Warp")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=getattr(caster_model, "parent_unit", None)):
            return False

        from ..utility.dice import get_roll

        reroll_values = list(kwargs.get("reroll_values") or kwargs.get("rerolls") or [])
        rerolled = []
        for idx in range(len(current_rolls)):
            if idx < len(reroll_values):
                rerolled.append(int(reroll_values[idx]))
            else:
                rerolled.append(int(get_roll("D6") or 0))
        if isinstance(rolls_state, dict):
            rolls_state["rolls"] = list(rerolled)

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ARCANE FOCUS: re-rolled %d psychic test dice for %s.",
            len(rerolled),
            getattr(caster_model, "name", "Model"),
        )
        return True

    def _use_thousand_sons_desecration_of_worlds(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        objective = kwargs.get("objective") or kwargs.get("objective_marker")
        objective_candidates = list(kwargs.get("objective_candidates") or [])
        if target_unit is None:
            logger.error("ERROR: DESECRATION OF WORLDS: no target unit provided")
            return False
        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: DESECRATION OF WORLDS: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_thousand_sons_unit(root) or not self._is_psyker_unit(root):
            logger.error("ERROR: DESECRATION OF WORLDS: target must be a THOUSAND SONS PSYKER unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "command phase":
            logger.error("ERROR: DESECRATION OF WORLDS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: DESECRATION OF WORLDS: not your turn")
            return False

        if not objective_candidates:
            objective_candidates = self._ts_grand_coven_desecration_objective_candidates(root)
        if objective is None and objective_candidates:
            objective = objective_candidates[0]
        if objective is None:
            logger.error("ERROR: DESECRATION OF WORLDS: no controlled objective marker within range")
            return False
        if objective_candidates and objective not in list(objective_candidates or []):
            logger.error("ERROR: DESECRATION OF WORLDS: objective is not eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Command phase"):
            logger.error("ERROR: DESECRATION OF WORLDS: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        location = getattr(objective, "location", None)
        if location is None:
            logger.error("ERROR: DESECRATION OF WORLDS: objective marker is missing its location")
            return False
        set_sticky_control = getattr(location, "set_sticky_control", None)
        if callable(set_sticky_control):
            set_sticky_control(self.player, source="desecration_of_worlds")
        else:
            location.sticky_controller = self.player
            location.sticky_source = "desecration_of_worlds"
            location.controlling_player = self.player

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DESECRATION OF WORLDS: %s makes %s sticky.",
            getattr(root, "name", "Unit"),
            getattr(objective, "name", "Objective"),
        )
        return True

    def _use_thousand_sons_destined_by_fate(self, stratagem: Any, **kwargs) -> bool:
        target_model = kwargs.get("target_model") or kwargs.get("model")
        attack_instance = kwargs.get("attack_instance")
        if target_model is None or not isinstance(attack_instance, dict):
            logger.error("ERROR: DESTINED BY FATE: missing target model or attack context")
            return False
        mgr = self._ts_detachment_mgr()
        eligible_fn = getattr(mgr, "grand_coven_model_is_thousand_sons_psyker", None) if mgr is not None else None
        if not callable(eligible_fn) or not bool(eligible_fn(target_model, game=self.game)):
            logger.error("ERROR: DESTINED BY FATE: target must be a THOUSAND SONS PSYKER model from your army")
            return False
        if bool(attack_instance.get("force_damage_zero", False)):
            logger.error("ERROR: DESTINED BY FATE: damage is already set to 0 for this attack")
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if not phase_name:
            logger.error("ERROR: DESTINED BY FATE: phase context is missing")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=getattr(target_model, "parent_unit", None)):
            return False

        attack_instance["force_damage_zero"] = True
        attack_instance["force_damage_zero_source"] = str(getattr(stratagem, "name", "") or "DESTINED BY FATE")

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DESTINED BY FATE: %s changes the attack's Damage characteristic to 0.",
            getattr(target_model, "name", "Model"),
        )
        return True

    def _use_thousand_sons_devastating_sorcery(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: DEVASTATING SORCERY: no target unit provided")
            return False
        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: DEVASTATING SORCERY: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_thousand_sons_unit(root) or not self._is_psyker_unit(root):
            logger.error("ERROR: DEVASTATING SORCERY: target must be a THOUSAND SONS PSYKER unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: DEVASTATING SORCERY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: DEVASTATING SORCERY: not your turn")
            return False
        if self._ts_has_shot_this_phase(root):
            logger.error("ERROR: DEVASTATING SORCERY: target has already shot this phase")
            return False

        eligible = candidates or self._ts_grand_coven_psyker_candidates(require_not_shot=True)
        if not eligible or not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: DEVASTATING SORCERY: target is not eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: DEVASTATING SORCERY: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["thousand_sons_devastating_sorcery_active"] = True
        sr["thousand_sons_devastating_sorcery_phase_key"] = self._ts_phase_key_for_game()
        sr["thousand_sons_devastating_sorcery_owner"] = str(getattr(self.player, "id", "") or "")
        sr["thousand_sons_devastating_sorcery_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["thousand_sons_devastating_sorcery_source"] = str(getattr(stratagem, "name", "") or "DEVASTATING SORCERY")
        root.special_rules = sr

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DEVASTATING SORCERY: %s gains +9\" Psychic range and full Hit/Wound re-rolls with Psychic weapons this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_egotistical_power(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: EGOTISTICAL POWER: no target unit provided")
            return False
        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: EGOTISTICAL POWER: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_thousand_sons_unit(root) or not self._is_psyker_unit(root):
            logger.error("ERROR: EGOTISTICAL POWER: target must be a THOUSAND SONS PSYKER unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "command phase":
            logger.error("ERROR: EGOTISTICAL POWER: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: EGOTISTICAL POWER: not your turn")
            return False

        eligible = candidates or self._ts_grand_coven_psyker_candidates(require_not_shot=False)
        if not eligible or not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: EGOTISTICAL POWER: target is not eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Command phase"):
            logger.error("ERROR: EGOTISTICAL POWER: cannot be used in current state")
            return False

        choice_key = str(kwargs.get("choice_key") or kwargs.get("key") or kwargs.get("choice") or "").strip().upper()
        if choice_key and choice_key not in GRAND_COVEN_BY_KEY:
            logger.error("ERROR: EGOTISTICAL POWER: invalid Kindred Sorcery choice")
            return False
        mgr = self._ts_detachment_mgr()
        apply_override = getattr(mgr, "apply_grand_coven_override", None) if mgr is not None else None
        if not callable(apply_override):
            logger.error("ERROR: EGOTISTICAL POWER: Grand Coven detachment manager is unavailable")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False
        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)

        if choice_key:
            if not bool(apply_override(root, choice_key, game=self.game, source=stratagem.name)):
                logger.error("ERROR: EGOTISTICAL POWER: failed to apply the selected Kindred Sorcery override")
                return False
            logger.info(
                "INFO: EGOTISTICAL POWER: %s now uses %s until your next Command phase.",
                getattr(root, "name", "Unit"),
                getattr(GRAND_COVEN_BY_KEY.get(choice_key), "name", choice_key),
            )
            return True

        from ..engine.decision_kinds import DECISION_CHOOSE_GRAND_COVEN
        from ..engine.decisions import DecisionOption, DecisionRequest

        options = [
            DecisionOption.create(
                str(desc.name or choice).strip() or choice,
                payload={
                    "choice_key": choice,
                    "unit_id": self._ts_sort_key(root),
                },
            )
            for choice, desc in GRAND_COVEN_BY_KEY.items()
        ]
        request = DecisionRequest.create(
            DECISION_CHOOSE_GRAND_COVEN,
            "Choose Kindred Sorcery override",
            player_id=getattr(self.player, "id", None),
            options=options,
            context={
                "ability": "egotistical_power",
                "ability_name": str(getattr(stratagem, "name", "") or "Egotistical Power"),
                "unit_id": self._ts_sort_key(root),
                "army_id": self._ts_sort_key(getattr(root, "get_parent_army", lambda: None)()),
                "allowed_choice_keys": list(GRAND_COVEN_BY_KEY.keys()),
            },
        )
        if hasattr(self.game, "request_decision"):
            self.game.request_decision(request)
        logger.info(
            "INFO: EGOTISTICAL POWER: queued Kindred Sorcery override choice for %s.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_psychic_dominion(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or kwargs.get("targets") or [])
        if target_unit is None or attacking_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None or attacking_unit is None:
            logger.error("ERROR: PSYCHIC DOMINION: missing target or attacking unit context")
            return False

        root = self._ts_root(target_unit)
        attacker_root = self._ts_root(attacking_unit)
        if root is None or attacker_root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: PSYCHIC DOMINION: target unit is not yours")
            return False
        if self._ts_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: PSYCHIC DOMINION: attacking unit must be an enemy unit")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._ts_on_battlefield(attacker_root, require_targetable=False):
            return False
        if not self._is_thousand_sons_unit(root):
            logger.error("ERROR: PSYCHIC DOMINION: target must be a THOUSAND SONS unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: PSYCHIC DOMINION: trigger only occurs in the Shooting or Fight phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: PSYCHIC DOMINION: not an opponent trigger")
            return False

        eligible = candidates or self._ts_grand_coven_psychic_dominion_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not eligible or not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: PSYCHIC DOMINION: target is not eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, attacking_unit=attacker_root, phase_name=phase_name.title()):
            logger.error("ERROR: PSYCHIC DOMINION: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["thousand_sons_psychic_dominion_active"] = True
        sr["thousand_sons_psychic_dominion_phase_key"] = self._ts_phase_key_for_game()
        sr["thousand_sons_psychic_dominion_owner"] = str(getattr(self.player, "id", "") or "")
        sr["thousand_sons_psychic_dominion_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["thousand_sons_psychic_dominion_source"] = str(getattr(stratagem, "name", "") or "PSYCHIC DOMINION")
        sr["thousand_sons_psychic_dominion_attacker_unit_id"] = self._ts_sort_key(attacker_root)
        root.special_rules = sr

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PSYCHIC DOMINION: %s gains Feel No Pain 4+ against Psychic attacks and %s's Psychic weapons become Hazardous this phase.",
            getattr(root, "name", "Unit"),
            getattr(attacker_root, "name", "Attacking unit"),
        )
        return True

    def _use_thousand_sons_ardent_automata(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("action"):
                    kwargs["action"] = reaction.get("action")
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: ARDENT AUTOMATA: no target unit provided")
            return False

        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: ARDENT AUTOMATA: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_rubricae_unit(root):
            logger.error("ERROR: ARDENT AUTOMATA: target must be a RUBRICAE unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "movement phase":
            logger.error("ERROR: ARDENT AUTOMATA: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: ARDENT AUTOMATA: not your turn")
            return False
        if str(kwargs.get("action", "") or "").strip().lower() not in {"", "fall_back"}:
            logger.error("ERROR: ARDENT AUTOMATA: invalid trigger")
            return False
        if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
            logger.error("ERROR: ARDENT AUTOMATA: target unit has not Fallen Back this phase")
            return False

        eligible = candidates or self._ts_ardent_automata_candidates()
        if not eligible or not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: ARDENT AUTOMATA: target is not eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: ARDENT AUTOMATA: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["thousand_sons_ardent_automata_active"] = True
        sr["thousand_sons_ardent_automata_turn_owner"] = owner_id
        sr["thousand_sons_ardent_automata_turn"] = int(current_turn)
        sr["thousand_sons_ardent_automata_source"] = stratagem.name
        root.special_rules = sr

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ARDENT AUTOMATA: %s can shoot and charge this turn after Falling Back.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_inexorable_advance(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: INEXORABLE ADVANCE: no target unit provided")
            return False

        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: INEXORABLE ADVANCE: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_rubricae_unit(root):
            logger.error("ERROR: INEXORABLE ADVANCE: target must be a RUBRICAE unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "movement phase":
            logger.error("ERROR: INEXORABLE ADVANCE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: INEXORABLE ADVANCE: not your turn")
            return False

        eligible = candidates or self._ts_inexorable_advance_candidates()
        if not eligible or not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: INEXORABLE ADVANCE: target is not eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: INEXORABLE ADVANCE: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["thousand_sons_inexorable_advance_ignore_modifiers_active"] = True
        sr["thousand_sons_inexorable_advance_ignore_modifiers_expires_phase"] = "MOVEMENT_PHASE"
        sr["thousand_sons_inexorable_advance_assault_active"] = True
        sr["thousand_sons_inexorable_advance_assault_expires_phase"] = "SHOOTING_PHASE"
        sr["thousand_sons_inexorable_advance_turn_owner"] = owner_id
        sr["thousand_sons_inexorable_advance_turn"] = int(current_turn)
        sr["thousand_sons_inexorable_advance_source"] = stratagem.name
        # Reuse existing movement/advance modifier-choice plumbing.
        sr["preternatural_agility_ignore_modifiers_active"] = True
        sr["preternatural_agility_ignore_modifiers_expires_phase"] = "MOVEMENT_PHASE"
        sr["preternatural_agility_turn_owner"] = owner_id
        sr["preternatural_agility_turn"] = int(current_turn)
        root.special_rules = sr

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: INEXORABLE ADVANCE: %s can ignore Move/Advance modifiers and gains ranged [ASSAULT] this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_infernal_fusillade(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: INFERNAL FUSILLADE: no target unit provided")
            return False

        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: INFERNAL FUSILLADE: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_thousand_sons_unit(root):
            logger.error("ERROR: INFERNAL FUSILLADE: target must be a THOUSAND SONS unit")
            return False
        if not self._is_psyker_unit(root):
            logger.error("ERROR: INFERNAL FUSILLADE: target must be a PSYKER unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: INFERNAL FUSILLADE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: INFERNAL FUSILLADE: not your turn")
            return False
        if self._ts_has_shot_this_phase(root):
            logger.error("ERROR: INFERNAL FUSILLADE: target has already shot this phase")
            return False

        eligible = candidates or self._ts_infernal_fusillade_candidates()
        if not eligible or not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: INFERNAL FUSILLADE: target is not eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: INFERNAL FUSILLADE: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["thousand_sons_infernal_fusillade_active"] = True
        sr["thousand_sons_infernal_fusillade_expires_phase"] = "SHOOTING_PHASE"
        sr["thousand_sons_infernal_fusillade_owner"] = owner_id
        sr["thousand_sons_infernal_fusillade_turn"] = int(current_turn)
        sr["thousand_sons_infernal_fusillade_source"] = str(getattr(stratagem, "name", "") or "INFERNAL FUSILLADE")
        root.special_rules = sr

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: INFERNAL FUSILLADE: %s inferno ranged weapons gain [PSYCHIC] and Strength 5 this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_implacable_guardians(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or kwargs.get("targets") or [])

        if target_unit is None or attacking_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: IMPLACABLE GUARDIANS: no target unit provided")
            return False

        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: IMPLACABLE GUARDIANS: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_rubric_marines_unit(root):
            logger.error("ERROR: IMPLACABLE GUARDIANS: target must be a RUBRIC MARINES unit")
            return False
        if not self._is_psyker_unit(root):
            logger.error("ERROR: IMPLACABLE GUARDIANS: target must be a PSYKER unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: IMPLACABLE GUARDIANS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: IMPLACABLE GUARDIANS: not opponent's Shooting phase")
            return False

        attacker_root = self._ts_root(attacking_unit)
        if attacker_root is None:
            logger.error("ERROR: IMPLACABLE GUARDIANS: missing attacking unit context")
            return False
        if self._ts_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: IMPLACABLE GUARDIANS: attacker is not an enemy unit")
            return False

        eligible = candidates or self._ts_implacable_guardians_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not eligible or not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: IMPLACABLE GUARDIANS: target was not selected by the attacking unit")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=root,
            phase_name="Shooting phase",
            attacking_unit=attacker_root,
            target_units=list(target_units or []),
        ):
            logger.error("ERROR: IMPLACABLE GUARDIANS: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        entry = {
            "value": 1,
            "attack_type": "any",
            "expires_phase": "SHOOTING_PHASE",
            "source": str(getattr(stratagem, "name", "") or "IMPLACABLE GUARDIANS"),
            "exclude_allocated_model_keyword": "PSYKER",
        }
        append_defensive_effect = getattr(self, "_append_defensive_effect", None)
        if callable(append_defensive_effect):
            append_defensive_effect(root, "defensive_damage_reductions", entry)
        else:
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            items = list(sr.get("defensive_damage_reductions", []) or [])
            items.append(entry)
            sr["defensive_damage_reductions"] = items
            root.special_rules = sr

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: IMPLACABLE GUARDIANS: %s reduces incoming Damage by 1 this phase (excluding attacks allocated to PSYKER models).",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_unwavering_phalanx(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])

        if target_unit is None or attacking_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: UNWAVERING PHALANX: no target unit provided")
            return False

        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: UNWAVERING PHALANX: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_rubric_marines_unit(root):
            logger.error("ERROR: UNWAVERING PHALANX: target must be a RUBRIC MARINES unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "charge phase":
            logger.error("ERROR: UNWAVERING PHALANX: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: UNWAVERING PHALANX: not opponent's Charge phase")
            return False

        attacker_root = self._ts_root(attacking_unit)
        if attacker_root is None:
            logger.error("ERROR: UNWAVERING PHALANX: missing attacking unit context")
            return False
        if self._ts_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: UNWAVERING PHALANX: attacker is not an enemy unit")
            return False

        eligible = candidates or self._ts_unwavering_phalanx_candidates(attacking_unit=attacker_root)
        if not eligible or not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: UNWAVERING PHALANX: target must be within Engagement Range of the charging unit")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=root,
            phase_name="Charge phase",
            attacking_unit=attacker_root,
            enemy_unit=attacker_root,
        ):
            logger.error("ERROR: UNWAVERING PHALANX: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        entry = {
            "value": 1,
            "attack_type": "any",
            "expires_phase": "FIGHT_PHASE",
            "source": str(getattr(stratagem, "name", "") or "UNWAVERING PHALANX"),
        }
        append_defensive_effect = getattr(self, "_append_defensive_effect", None)
        if callable(append_defensive_effect):
            append_defensive_effect(root, "defensive_wound_mods", entry)
        else:
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            items = list(sr.get("defensive_wound_mods", []) or [])
            items.append(entry)
            sr["defensive_wound_mods"] = items
            root.special_rules = sr

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: UNWAVERING PHALANX: %s imposes -1 to wound against incoming attacks in the Fight phase this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_revenge_of_the_rubricae(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
        candidates = list(kwargs.get("candidates") or [])

        if target_unit is None or enemy_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if enemy_unit is None:
                    enemy_unit = reaction.get("enemy_unit") or reaction.get("attacking_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: REVENGE OF THE RUBRICAE: no target unit provided")
            return False

        root = self._ts_root(target_unit)
        enemy_root = self._ts_root(enemy_unit)
        if root is None or enemy_root is None:
            logger.error("ERROR: REVENGE OF THE RUBRICAE: missing attacker context")
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: REVENGE OF THE RUBRICAE: target unit is not yours")
            return False
        if not self._is_rubricae_unit(root):
            logger.error("ERROR: REVENGE OF THE RUBRICAE: target must be a RUBRICAE unit")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if self._ts_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: REVENGE OF THE RUBRICAE: attacker is not an enemy unit")
            return False
        if not self._ts_is_alive(enemy_root):
            logger.error("ERROR: REVENGE OF THE RUBRICAE: attacker is not alive")
            return False
        if candidates and not self._ts_unit_in_candidates(root, candidates):
            logger.error("ERROR: REVENGE OF THE RUBRICAE: target was not selected by the trigger")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: REVENGE OF THE RUBRICAE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: REVENGE OF THE RUBRICAE: not opponent's Shooting phase")
            return False

        queue_fn = getattr(self.game, "_queue_setup_reactive_shooting_decision", None) if self.game is not None else None
        if not callable(queue_fn):
            logger.error("ERROR: REVENGE OF THE RUBRICAE: reactive shooting decision queue unavailable")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=root,
            enemy_unit=enemy_root,
            phase_name="Shooting phase",
        ):
            logger.error("ERROR: REVENGE OF THE RUBRICAE: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False
        request = queue_fn(
            player=self.player,
            unit=root,
            target_unit=enemy_root,
            source=stratagem.name,
        )
        if request is None:
            logger.error("ERROR: REVENGE OF THE RUBRICAE: failed to queue reactive shooting decision")
            return False
        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: REVENGE OF THE RUBRICAE: %s can shoot reactively into %s.",
            getattr(root, "name", "Unit"),
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_thousand_sons_chronosorcerous_bleed(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
        candidates = list(kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or [])

        if target_unit is None or enemy_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if enemy_unit is None:
                    enemy_unit = reaction.get("enemy_unit") or reaction.get("attacking_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: CHRONOSORCEROUS BLEED: no target unit provided")
            return False

        root = self._ts_root(target_unit)
        enemy_root = self._ts_root(enemy_unit)
        if root is None or enemy_root is None:
            logger.error("ERROR: CHRONOSORCEROUS BLEED: missing charge context")
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: CHRONOSORCEROUS BLEED: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not (self._is_scintillating_legions_unit(root) or (self._is_thousand_sons_unit(root) and self._is_psyker_unit(root))):
            logger.error("ERROR: CHRONOSORCEROUS BLEED: target must be a THOUSAND SONS PSYKER or SCINTILLATING LEGIONS unit")
            return False
        if self._ts_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: CHRONOSORCEROUS BLEED: charging unit is not an enemy")
            return False
        if not self._ts_is_alive(enemy_root):
            logger.error("ERROR: CHRONOSORCEROUS BLEED: charging unit is not alive")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "charge phase":
            logger.error("ERROR: CHRONOSORCEROUS BLEED: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: CHRONOSORCEROUS BLEED: not opponent's Charge phase")
            return False

        eligible = candidates or self._ts_changehost_chronosorcerous_bleed_candidates(
            charging_unit=enemy_root,
            target_units=target_units,
        )
        if not eligible or not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: CHRONOSORCEROUS BLEED: target must have been selected as a charge target")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=root,
            enemy_unit=enemy_root,
            phase_name="Charge phase",
        ):
            logger.error("ERROR: CHRONOSORCEROUS BLEED: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["thousand_sons_chronosorcerous_bleed_active"] = True
        sr["thousand_sons_chronosorcerous_bleed_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["thousand_sons_chronosorcerous_bleed_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["thousand_sons_chronosorcerous_bleed_source"] = str(getattr(stratagem, "name", "") or "CHRONOSORCEROUS BLEED")
        sr["thousand_sons_chronosorcerous_bleed_expires_phase"] = "CHARGE_PHASE"
        sr["thousand_sons_chronosorcerous_bleed_charge_modifier"] = -2
        root.special_rules = sr

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CHRONOSORCEROUS BLEED: %s imposes -2 to %s's Charge roll this phase.",
            getattr(root, "name", "Unit"),
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_thousand_sons_deceptive_glamour(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])

        if target_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: DECEPTIVE GLAMOUR: no target unit provided")
            return False

        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: DECEPTIVE GLAMOUR: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_thousand_sons_unit(root):
            logger.error("ERROR: DECEPTIVE GLAMOUR: target must be a THOUSAND SONS unit")
            return False
        if self._is_scintillating_legions_unit(root):
            logger.error("ERROR: DECEPTIVE GLAMOUR: target cannot be a SCINTILLATING LEGIONS unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "fight phase":
            logger.error("ERROR: DECEPTIVE GLAMOUR: wrong phase")
            return False

        eligible = candidates or self._ts_changehost_deceptive_glamour_candidates()
        if not eligible or not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: DECEPTIVE GLAMOUR: target is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: DECEPTIVE GLAMOUR: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["thousand_sons_deceptive_glamour_active"] = True
        sr["thousand_sons_deceptive_glamour_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["thousand_sons_deceptive_glamour_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["thousand_sons_deceptive_glamour_source"] = str(getattr(stratagem, "name", "") or "DECEPTIVE GLAMOUR")
        sr["thousand_sons_deceptive_glamour_expires_phase"] = "FIGHT_PHASE"
        root.special_rules = sr

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DECEPTIVE GLAMOUR: enemy melee attacks prefer SCINTILLATING LEGIONS targets over %s this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_ethereal_phantasm(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("moving_unit") or kwargs.get("attacking_unit")
        candidates = list(kwargs.get("candidates") or [])
        action = kwargs.get("action")

        if target_unit is None or enemy_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if enemy_unit is None:
                    enemy_unit = reaction.get("enemy_unit") or reaction.get("moving_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if action is None:
                    action = reaction.get("action")
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: ETHEREAL PHANTASM: no target unit provided")
            return False

        root = self._ts_root(target_unit)
        enemy_root = self._ts_root(enemy_unit)
        if root is None or enemy_root is None:
            logger.error("ERROR: ETHEREAL PHANTASM: missing move context")
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: ETHEREAL PHANTASM: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_scintillating_legions_unit(root):
            logger.error("ERROR: ETHEREAL PHANTASM: target must be a SCINTILLATING LEGIONS unit")
            return False
        if self._ts_unit_is_engaged(root):
            logger.error("ERROR: ETHEREAL PHANTASM: target must not be in Engagement Range")
            return False
        if self._ts_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: ETHEREAL PHANTASM: moving unit is not an enemy unit")
            return False
        if not self._ts_on_battlefield(enemy_root, require_targetable=False):
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "movement phase":
            logger.error("ERROR: ETHEREAL PHANTASM: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: ETHEREAL PHANTASM: not opponent's Movement phase")
            return False

        action_key = self._ts_normalize_move_action(action)
        eligible = candidates or self._ts_changehost_ethereal_phantasm_candidates(
            enemy_unit=enemy_root,
            action=action_key,
        )
        if not eligible or not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: ETHEREAL PHANTASM: target must be within 9\" of the enemy unit and not engaged")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=root,
            moving_unit=enemy_root,
            phase_name="Movement phase",
        ):
            logger.error("ERROR: ETHEREAL PHANTASM: cannot be used in current state")
            return False
        queue_move = getattr(getattr(self, "game", None), "_queue_reactive_move_movement_decision", None)
        if not callable(queue_move):
            logger.error("ERROR: ETHEREAL PHANTASM: reactive move queue is unavailable")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        fixed_six = self._ts_unit_wholly_within_distance_of_friendly_thousand_sons_units(root, distance=6.0)
        max_distance = 6
        if not fixed_six:
            from ..utility.dice import get_roll

            max_distance = int(get_roll("D6") or 0)
        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=int(max_distance),
            kind="ethereal_phantasm",
            movement_type="reactive",
            reactive_movement_type="move",
            source=str(getattr(stratagem, "name", "") or "ETHEREAL PHANTASM"),
            moving_unit=enemy_root,
            range_value=9,
            extra_context={"ethereal_phantasm_fixed_six": bool(fixed_six)},
        )
        if request is None:
            logger.error("ERROR: ETHEREAL PHANTASM: failed to queue reactive move")
            return False

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ETHEREAL PHANTASM: %s can make a reactive Normal move up to %d\".",
            getattr(root, "name", "Unit"),
            int(max_distance),
        )
        return True

    def _use_thousand_sons_fractal_disjunction(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or [])

        if target_unit is None or attacking_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: FRACTAL DISJUNCTION: no target unit provided")
            return False

        root = self._ts_root(target_unit)
        attacker_root = self._ts_root(attacking_unit)
        if root is None or attacker_root is None:
            logger.error("ERROR: FRACTAL DISJUNCTION: missing attacker context")
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: FRACTAL DISJUNCTION: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_scintillating_legions_unit(root):
            logger.error("ERROR: FRACTAL DISJUNCTION: target must be a SCINTILLATING LEGIONS unit")
            return False
        if self._is_monster_unit(root):
            logger.error("ERROR: FRACTAL DISJUNCTION: target cannot be a MONSTER")
            return False
        if self._ts_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: FRACTAL DISJUNCTION: attacker is not an enemy unit")
            return False
        if not self._ts_is_alive(attacker_root):
            logger.error("ERROR: FRACTAL DISJUNCTION: attacker is not alive")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: FRACTAL DISJUNCTION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: FRACTAL DISJUNCTION: not opponent's Shooting phase")
            return False

        eligible = candidates or self._ts_changehost_fractal_disjunction_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not eligible or not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: FRACTAL DISJUNCTION: target must have been selected by the attacking unit")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=root,
            attacking_unit=attacker_root,
            phase_name="Shooting phase",
        ):
            logger.error("ERROR: FRACTAL DISJUNCTION: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["thousand_sons_fractal_disjunction_active"] = True
        sr["thousand_sons_fractal_disjunction_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["thousand_sons_fractal_disjunction_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["thousand_sons_fractal_disjunction_source"] = str(getattr(stratagem, "name", "") or "FRACTAL DISJUNCTION")
        sr["thousand_sons_fractal_disjunction_expires_phase"] = "SHOOTING_PHASE"
        sr["thousand_sons_fractal_disjunction_targeting_range"] = 18
        root.special_rules = sr

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: FRACTAL DISJUNCTION: %s can only be targeted by ranged attacks from within 18\" this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_glimmershift_portal(self, stratagem: Any, **kwargs) -> bool:
        selected = (
            kwargs.get("units")
            or kwargs.get("target_units")
            or kwargs.get("selected_units")
            or kwargs.get("unit")
            or kwargs.get("target_unit")
        )
        candidates = list(kwargs.get("candidates") or [])
        max_units = int(kwargs.get("max_units", 2) or 2)
        if selected is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if selected is None:
                    selected = (
                        reaction.get("units")
                        or reaction.get("target_units")
                        or reaction.get("selected_units")
                        or reaction.get("unit")
                        or reaction.get("target_unit")
                    )
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if "max_units" not in kwargs:
                    max_units = int(reaction.get("max_units", max_units) or max_units)
                break

        if selected is None and len(candidates) == 1:
            selected = [candidates[0]]
        if selected is None:
            logger.error("ERROR: GLIMMERSHIFT PORTAL: no target units provided")
            return False

        selected_entries = list(selected) if isinstance(selected, (list, tuple)) else [selected]
        resolved: list[Any] = []
        seen_ids: set[str] = set()
        resolve_by_id = getattr(self.game, "_resolve_unit_by_id", None) if self.game is not None else None
        for entry in selected_entries:
            if entry is None:
                continue
            unit = entry
            if isinstance(entry, str):
                unit = resolve_by_id(entry) if callable(resolve_by_id) else None
            root = self._ts_root(unit)
            if root is None:
                continue
            uid = self._ts_sort_key(root)
            if uid and uid in seen_ids:
                continue
            if uid:
                seen_ids.add(uid)
            resolved.append(root)
        if not resolved:
            logger.error("ERROR: GLIMMERSHIFT PORTAL: no valid target units selected")
            return False
        if len(resolved) > max(1, int(max_units)):
            logger.error("ERROR: GLIMMERSHIFT PORTAL: selected too many units")
            return False
        if len(resolved) > 2:
            logger.error("ERROR: GLIMMERSHIFT PORTAL: cannot select more than two units")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "fight phase":
            logger.error("ERROR: GLIMMERSHIFT PORTAL: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: GLIMMERSHIFT PORTAL: not opponent's Fight phase")
            return False

        eligible = candidates or self._ts_glimmershift_portal_candidates()
        if not eligible:
            logger.error("ERROR: GLIMMERSHIFT PORTAL: no eligible units")
            return False
        for root in resolved:
            if not self._ts_unit_in_candidates(root, eligible):
                logger.error("ERROR: GLIMMERSHIFT PORTAL: selected unit is not currently eligible")
                return False
            if not self._ts_owned_by_player(root, self.player):
                logger.error("ERROR: GLIMMERSHIFT PORTAL: selected unit is not yours")
                return False
            if not self._ts_on_battlefield(root, require_targetable=True):
                logger.error("ERROR: GLIMMERSHIFT PORTAL: selected unit must be on the battlefield and targetable")
                return False
            if not self._is_scintillating_legions_unit(root):
                logger.error("ERROR: GLIMMERSHIFT PORTAL: selected unit must be SCINTILLATING LEGIONS")
                return False
            if self._ts_has_enemy_within_horizontal_distance(root, distance=6.0):
                logger.error("ERROR: GLIMMERSHIFT PORTAL: selected unit must be more than 6\" horizontally from all enemies")
                return False

        selected_monsters = [root for root in resolved if self._is_monster_unit(root)]
        if selected_monsters and len(resolved) != 1:
            logger.error("ERROR: GLIMMERSHIFT PORTAL: if selecting a MONSTER unit, exactly one unit must be selected")
            return False

        can_use = False
        try:
            can_use = bool(
                stratagem.can_use(
                    self.player,
                    self.game,
                    phase_name="Fight phase",
                    unit=resolved[0],
                    units=list(resolved),
                )
            )
        except TypeError:
            can_use = bool(stratagem.can_use(self.player, self.game, phase_name="Fight phase", unit=resolved[0]))
        if not can_use:
            logger.error("ERROR: GLIMMERSHIFT PORTAL: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=resolved[0]):
            return False

        for root in resolved:
            if not self._ts_place_unit_into_strategic_reserves(
                root,
                reason=str(getattr(stratagem, "name", "GLIMMERSHIFT PORTAL") or "GLIMMERSHIFT PORTAL"),
            ):
                logger.error("ERROR: GLIMMERSHIFT PORTAL: failed to place %s into Strategic Reserves", getattr(root, "name", "Unit"))
                return False

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        moved_units = ", ".join(getattr(root, "name", "Unit") for root in resolved)
        logger.info("INFO: GLIMMERSHIFT PORTAL: %s entered Strategic Reserves.", moved_units)
        return True
