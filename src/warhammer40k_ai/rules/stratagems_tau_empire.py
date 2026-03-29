from __future__ import annotations

import logging
from typing import Any, Optional

from ..utility import dice as dice_module
from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class TauEmpireStratagemMixin:
    @staticmethod
    def _tau_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _tau_sort_key(entity: Any) -> str:
        return str(get_entity_id(entity) or "")

    def _tau_detachment_mgr(self) -> Any:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "tau_empire_detachments", None)

    def _is_tau_experimental_prototype_cadre_detachment(self) -> bool:
        mgr = self._tau_detachment_mgr()
        checker = getattr(mgr, "is_experimental_prototype_cadre", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_tau_montka_detachment(self) -> bool:
        mgr = self._tau_detachment_mgr()
        checker = getattr(mgr, "is_montka", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_tau_auxiliary_cadre_detachment(self) -> bool:
        mgr = self._tau_detachment_mgr()
        checker = getattr(mgr, "is_auxiliary_cadre", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_tau_kauyon_detachment(self) -> bool:
        mgr = self._tau_detachment_mgr()
        checker = getattr(mgr, "is_kauyon", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    @staticmethod
    def _tau_has_any_keyword(entity: Any, keyword: str) -> bool:
        if entity is None:
            return False
        has_any = getattr(entity, "has_any_keyword", None)
        if callable(has_any) and has_any(keyword):
            return True
        has_kw = getattr(entity, "has_keyword", None)
        if callable(has_kw) and has_kw(keyword):
            return True
        return False

    def _is_tau_empire_unit(self, unit: Any) -> bool:
        root = self._tau_root(unit)
        if root is None:
            return False
        mgr = self._tau_detachment_mgr()
        checker = getattr(mgr, "_unit_is_tau_empire", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        faction_id = str(getattr(root, "faction_id", "") or "").strip().upper()
        if faction_id == "TAU":
            return True
        if self._tau_has_any_keyword(root, "T'AU EMPIRE"):
            return True
        if self._tau_has_any_keyword(root, "T\u2019AU EMPIRE"):
            return True
        if self._tau_has_any_keyword(root, "TAU EMPIRE"):
            return True
        return False

    def _is_tau_kroot_unit(self, unit: Any) -> bool:
        root = self._tau_root(unit)
        if root is None:
            return False
        if self._tau_has_any_keyword(root, "KROOT"):
            return True
        return "KROOT" in str(getattr(root, "name", "") or "").strip().upper()

    def _is_tau_vespid_unit(self, unit: Any) -> bool:
        root = self._tau_root(unit)
        if root is None:
            return False
        if self._tau_has_any_keyword(root, "VESPID STINGWINGS"):
            return True
        name_u = str(getattr(root, "name", "") or "").strip().upper()
        return "VESPID" in name_u

    def _is_tau_kroot_or_vespid_unit(self, unit: Any) -> bool:
        return bool(self._is_tau_kroot_unit(unit) or self._is_tau_vespid_unit(unit))

    def _is_tau_battlesuit_unit(self, unit: Any) -> bool:
        root = self._tau_root(unit)
        if root is None:
            return False
        if not self._is_tau_empire_unit(root):
            return False
        return self._tau_has_any_keyword(root, "BATTLESUIT")

    def _is_tau_crisis_unit(self, unit: Any) -> bool:
        root = self._tau_root(unit)
        if root is None:
            return False
        if not self._is_tau_empire_unit(root):
            return False
        if self._tau_has_any_keyword(root, "CRISIS"):
            return True
        return "CRISIS" in str(getattr(root, "name", "") or "").strip().upper()

    @staticmethod
    def _tau_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(unit, "is_alive", True))

    def _tau_owned_by_player(self, unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(army, "player", None) is player

    def _tau_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._tau_root(unit)
        if root is None:
            return False
        if not self._tau_is_alive(root):
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

    def _tau_unit_models(self, unit: Any) -> list[Any]:
        root = self._tau_root(unit)
        if root is None:
            return []
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else []
        if not models:
            models = list(getattr(root, "models", []) or [])
        return sorted(models, key=self._tau_sort_key)

    @staticmethod
    def _tau_model_is_alive(model: Any) -> bool:
        if model is None:
            return False
        alive_attr = getattr(model, "is_alive", True)
        return bool(alive_attr() if callable(alive_attr) else alive_attr)

    @staticmethod
    def _tau_model_missing_wounds(model: Any) -> int:
        if model is None:
            return 0
        base = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)) or 0)
        current = int(getattr(model, "wounds", 0) or 0)
        return max(0, int(base - current))

    def _tau_model_is_battlesuit(self, model: Any, *, parent_unit: Any = None) -> bool:
        if model is None:
            return False
        if self._tau_has_any_keyword(model, "BATTLESUIT"):
            return True
        root = self._tau_root(parent_unit) if parent_unit is not None else None
        if root is not None and self._tau_has_any_keyword(root, "BATTLESUIT"):
            return True
        parent = getattr(model, "parent_unit", None)
        return bool(parent is not None and self._tau_has_any_keyword(parent, "BATTLESUIT"))

    def _tau_wounded_battlesuit_models(self, unit: Any) -> list[Any]:
        root = self._tau_root(unit)
        if root is None:
            return []
        out: list[Any] = []
        for model in self._tau_unit_models(root):
            if not self._tau_model_is_alive(model):
                continue
            if not self._tau_model_is_battlesuit(model, parent_unit=root):
                continue
            if self._tau_model_missing_wounds(model) <= 0:
                continue
            out.append(model)
        return sorted(out, key=self._tau_sort_key)

    def _tau_unit_in_candidates(self, root: Any, candidates: list[Any]) -> bool:
        if root is None:
            return False
        rid = self._tau_sort_key(root)
        for candidate in list(candidates or []):
            cand_root = self._tau_root(candidate)
            if cand_root is None:
                continue
            if cand_root is root:
                return True
            if rid and self._tau_sort_key(cand_root) == rid:
                return True
        return False

    def _tau_has_enemy_within_engagement_range(self, unit: Any) -> bool:
        root = self._tau_root(unit)
        if root is None:
            return False
        game_map = getattr(getattr(self, "game", None), "map", None)
        if game_map is None:
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        is_within_engagement_range = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(is_within_engagement_range):
            return False
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._tau_root(enemy)
            if enemy_root is None:
                continue
            if not self._tau_on_battlefield(enemy_root, require_targetable=False):
                continue
            if bool(is_within_engagement_range(root, enemy_root)):
                return True
        return False

    def _tau_wall_of_mirrors_unit_eligible(self, unit: Any) -> bool:
        root = self._tau_root(unit)
        if root is None:
            return False
        if self._tau_has_any_keyword(root, "STEALTH"):
            return True
        if self._tau_has_any_keyword(root, "GHOSTKEEL"):
            return True
        if self._tau_has_any_keyword(root, "COMMANDER SHADOWSUN"):
            return True
        name_u = str(getattr(root, "name", "") or "").strip().upper()
        if "STEALTH" in name_u:
            return True
        if "GHOSTKEEL" in name_u:
            return True
        return "SHADOWSUN" in name_u

    def _tau_wall_of_mirrors_candidates(self) -> list[Any]:
        if not self._is_tau_kauyon_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tau_root(unit)
            if root is None:
                continue
            uid = self._tau_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tau_owned_by_player(root, self.player):
                continue
            if not self._tau_on_battlefield(root, require_targetable=True):
                continue
            if not self._tau_wall_of_mirrors_unit_eligible(root):
                continue
            if self._tau_has_enemy_within_engagement_range(root):
                continue
            out.append(root)
        return sorted(out, key=self._tau_sort_key)

    def _tau_point_blank_ambush_candidates(self) -> list[Any]:
        if not self._is_tau_kauyon_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tau_root(unit)
            if root is None:
                continue
            uid = self._tau_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tau_owned_by_player(root, self.player):
                continue
            if not self._tau_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tau_empire_unit(root):
                continue
            if self._tau_has_shot_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._tau_sort_key)

    def _tau_auxiliary_cadre_interlocking_candidates(self) -> list[Any]:
        if not self._is_tau_auxiliary_cadre_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tau_root(unit)
            if root is None:
                continue
            uid = self._tau_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tau_owned_by_player(root, self.player):
                continue
            if not self._tau_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tau_empire_unit(root):
                continue
            round_state = getattr(root, "round_state", None)
            was_eligible = bool(getattr(round_state, "eligible_to_fight_this_phase", False))
            if not was_eligible and bool(getattr(round_state, "fought_this_phase", False)):
                was_eligible = True
            if not was_eligible:
                continue
            out.append(root)
        return sorted(out, key=self._tau_sort_key)

    @staticmethod
    def _tau_normalized_phase_name(phase_name: Any) -> str:
        return str(phase_name or "").strip().lower().replace("_", " ")

    @staticmethod
    def _tau_selected_to_move_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(
            getattr(round_state, "moved_this_round", False)
            or getattr(round_state, "advanced_this_round", False)
            or getattr(round_state, "fell_back_this_round", False)
        )

    def _tau_auxiliary_phase_candidates(
        self,
        *,
        phase_name: Any,
        require_kroot_or_vespid: bool = False,
        exclude_kroot_or_vespid: bool = False,
    ) -> list[Any]:
        if not self._is_tau_auxiliary_cadre_detachment():
            return []
        phase_key = self._tau_normalized_phase_name(phase_name)
        if phase_key not in {"shooting phase", "fight phase"}:
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tau_root(unit)
            if root is None:
                continue
            uid = self._tau_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tau_owned_by_player(root, self.player):
                continue
            if not self._tau_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tau_empire_unit(root):
                continue
            is_kroot_or_vespid = self._is_tau_kroot_or_vespid_unit(root)
            if require_kroot_or_vespid and not is_kroot_or_vespid:
                continue
            if exclude_kroot_or_vespid and is_kroot_or_vespid:
                continue
            round_state = getattr(root, "round_state", None)
            if phase_key == "shooting phase":
                if bool(getattr(round_state, "shot_this_round", False)):
                    continue
            else:
                if bool(getattr(round_state, "fought_this_phase", False)):
                    continue
            out.append(root)
        return sorted(out, key=self._tau_sort_key)

    def _tau_pheromone_waypoints_candidates(self) -> list[Any]:
        if not self._is_tau_auxiliary_cadre_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tau_root(unit)
            if root is None:
                continue
            uid = self._tau_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tau_owned_by_player(root, self.player):
                continue
            if not self._tau_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tau_kroot_or_vespid_unit(root):
                continue
            if self._tau_selected_to_move_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._tau_sort_key)

    def _tau_guided_fire_candidates(self) -> list[Any]:
        return self._tau_auxiliary_phase_candidates(
            phase_name="shooting phase",
            exclude_kroot_or_vespid=True,
        )

    def _tau_experimental_modifications_candidates(self, *, phase_name: Any) -> list[Any]:
        return self._tau_auxiliary_phase_candidates(
            phase_name=phase_name,
            require_kroot_or_vespid=True,
        )

    def _tau_multisensory_scanning_candidates(self, *, phase_name: Any) -> list[Any]:
        return self._tau_auxiliary_phase_candidates(
            phase_name=phase_name,
        )

    def _tau_guided_fire_strength_bonus(self, unit: Any) -> int:
        root = self._tau_root(unit)
        if root is None:
            return 0
        if not self._is_tau_empire_unit(root):
            return 0
        if self._is_tau_kroot_or_vespid_unit(root):
            return 0
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return 1
        from ..utility.aura_utils import unit_wholly_within_range_of_unit

        seen: set[str] = set()
        for unit_entry in list(getattr(army, "units", []) or []):
            source = self._tau_root(unit_entry)
            if source is None:
                continue
            uid = self._tau_sort_key(source)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tau_owned_by_player(source, self.player):
                continue
            if not self._tau_on_battlefield(source, require_targetable=True):
                continue
            if not self._is_tau_kroot_or_vespid_unit(source):
                continue
            if unit_wholly_within_range_of_unit(source, root, 9.0, use_attached_aggregate=True):
                return 2
        return 1

    def _tau_aggressive_mobility_candidates(self) -> list[Any]:
        if not self._is_tau_montka_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tau_root(unit)
            if root is None:
                continue
            uid = self._tau_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tau_owned_by_player(root, self.player):
                continue
            if not self._tau_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tau_empire_unit(root):
                continue
            if self._tau_selected_to_move_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._tau_sort_key)

    def _tau_counterfire_defence_systems_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_tau_montka_detachment():
            return []
        if attacking_unit is not None:
            attacker_root = self._tau_root(attacking_unit)
            if attacker_root is None:
                return []
            if self._tau_owned_by_player(attacker_root, self.player):
                return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._tau_root(unit)
            if root is None:
                continue
            uid = self._tau_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tau_owned_by_player(root, self.player):
                continue
            if not self._tau_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tau_empire_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._tau_sort_key)

    def _tau_pinpoint_counter_offensive_target_eligible(self, unit: Any) -> bool:
        root = self._tau_root(unit)
        if root is None:
            return False
        if not self._tau_owned_by_player(root, self.player):
            return False
        if not self._is_tau_empire_unit(root):
            return False
        if self._is_tau_kroot_unit(root):
            return False
        if self._tau_is_alive(root):
            return False
        return True

    def _tau_pinpoint_counter_offensive_candidates(self, *, destroyed_unit: Any = None) -> list[Any]:
        if not self._is_tau_montka_detachment():
            return []
        root = self._tau_root(destroyed_unit)
        if root is None:
            return []
        if not self._tau_pinpoint_counter_offensive_target_eligible(root):
            return []
        return [root]

    def tau_montka_pinpoint_counter_offensive_applies(self, attacker_unit: Any, target_unit: Any) -> bool:
        attacker_root = self._tau_root(attacker_unit)
        target_root = self._tau_root(target_unit)
        if attacker_root is None or target_root is None:
            return False
        if not self._is_tau_montka_detachment():
            return False
        if not self._tau_owned_by_player(attacker_root, self.player):
            return False
        if not self._is_tau_empire_unit(attacker_root):
            return False
        if self._is_tau_kroot_unit(attacker_root):
            return False
        enemy_ids = getattr(self, "_tau_montka_pinpoint_counter_offensive_enemy_ids", set())
        if not isinstance(enemy_ids, set):
            return False
        target_id = self._tau_sort_key(target_root)
        return bool(target_id and target_id in enemy_ids)

    @staticmethod
    def _tau_has_disembarked_this_round(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(getattr(round_state, "disembarked_this_round", False))

    @staticmethod
    def _tau_unit_is_monster_or_vehicle(unit: Any) -> bool:
        if unit is None:
            return False
        has_any = getattr(unit, "has_any_keyword", None)
        if callable(has_any):
            if has_any("MONSTER") or has_any("VEHICLE"):
                return True
        has_kw = getattr(unit, "has_keyword", None)
        if callable(has_kw):
            if has_kw("MONSTER") or has_kw("VEHICLE"):
                return True
        return bool(getattr(unit, "is_monster", False) or getattr(unit, "is_vehicle", False))

    def _tau_current_battle_round(self) -> int:
        game = getattr(self, "game", None)
        if game is None:
            return 0
        get_battle_round = getattr(game, "get_battle_round", None)
        if callable(get_battle_round):
            try:
                return int(get_battle_round() or 0)
            except (TypeError, ValueError):
                return 0
        try:
            return int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def _tau_resolve_friendly_transport_for_disembarked_unit(self, unit: Any) -> Any:
        root = self._tau_root(unit)
        if root is None:
            return None
        round_state = getattr(root, "round_state", None)
        transport_id = str(getattr(round_state, "disembarked_from_transport_id", "") or "")
        if not transport_id:
            return None
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        for unit_entry in list(getattr(army, "units", []) or []):
            candidate = self._tau_root(unit_entry)
            if candidate is None:
                continue
            if self._tau_sort_key(candidate) != transport_id:
                continue
            if not self._tau_owned_by_player(candidate, self.player):
                continue
            return candidate
        return None

    def _tau_enemy_units_on_battlefield(self, *, require_targetable: bool = True) -> list[Any]:
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
                root = self._tau_root(enemy_unit)
                if root is None:
                    continue
                uid = self._tau_sort_key(root)
                if uid and uid in seen:
                    continue
                if uid:
                    seen.add(uid)
                if self._tau_owned_by_player(root, self.player):
                    continue
                if not self._tau_on_battlefield(root, require_targetable=require_targetable):
                    continue
                out.append(root)
        return sorted(out, key=self._tau_sort_key)

    def _tau_resolve_unit_list(self, value: Any) -> list[Any]:
        if value is None:
            return []
        raw_items = list(value) if isinstance(value, (list, tuple, set)) else [value]
        out: list[Any] = []
        seen: set[str] = set()
        for item in raw_items:
            root = self._tau_root(item)
            if root is None:
                continue
            uid = self._tau_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            out.append(root)
        return out

    def _tau_pending_choose_quarry_request(self, *, ability: str, **match_context: Any) -> bool:
        game = getattr(self, "game", None)
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != str(DECISION_CHOOSE_QUARRY):
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != str(ability or ""):
                continue
            matches = True
            for key, value in dict(match_context or {}).items():
                if isinstance(value, (list, tuple, set)):
                    expected = [str(item or "").strip() for item in list(value or []) if str(item or "").strip()]
                    current = [
                        str(item or "").strip()
                        for item in list(ctx.get(key, []) or [])
                        if str(item or "").strip()
                    ]
                    if current != expected:
                        matches = False
                        break
                    continue
                if str(ctx.get(key, "") or "").strip() != str(value or "").strip():
                    matches = False
                    break
            if matches:
                return True
        return False

    @staticmethod
    def _tau_objective_sort_key(objective: Any) -> str:
        if objective is None:
            return ""
        if isinstance(objective, str):
            return str(objective).strip()
        objective_id = str(getattr(objective, "id", "") or get_entity_id(objective) or "")
        if objective_id:
            return objective_id
        location = getattr(objective, "location", None)
        return str(getattr(location, "id", "") or get_entity_id(location) or "")

    def _tau_resolve_objective(self, objective_or_id: Any) -> Any:
        if objective_or_id is None:
            return None
        objective_key = self._tau_objective_sort_key(objective_or_id)
        if objective_key and not isinstance(objective_or_id, str):
            return objective_or_id
        objective_key = str(objective_or_id or "").strip()
        if not objective_key:
            return None
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        for objective in list(getattr(game_map, "objectives", []) or []):
            if self._tau_objective_sort_key(objective) == objective_key:
                return objective
            location = getattr(objective, "location", None)
            if str(getattr(location, "id", "") or get_entity_id(location) or "") == objective_key:
                return objective
        registry = getattr(game, "entity_registry", None) if game is not None else None
        if registry is not None:
            objective = registry.get(objective_key, kind="objective")
            if objective is not None:
                return objective
        return None

    def _tau_objective_candidates_not_in_opponent_deployment_zone(self) -> list[Any]:
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return []
        opponent = getattr(game, "get_opponent", lambda: None)() if game is not None else None
        opponent_id = str(getattr(opponent, "id", "") or "")
        in_zone = getattr(game, "is_position_in_deployment_zone", None) if game is not None else None
        out: list[Any] = []
        seen: set[str] = set()
        for objective in list(getattr(game_map, "objectives", []) or []):
            location = getattr(objective, "location", None)
            marker = location if location is not None else objective
            if marker is None or bool(getattr(marker, "removed", False)):
                continue
            objective_id = self._tau_objective_sort_key(objective)
            if not objective_id or objective_id in seen:
                continue
            if opponent_id and callable(in_zone):
                try:
                    if bool(in_zone(float(getattr(marker, "x", 0.0) or 0.0), float(getattr(marker, "y", 0.0) or 0.0), opponent_id)):
                        continue
                except (TypeError, ValueError):
                    continue
            seen.add(objective_id)
            out.append(objective)
        return sorted(out, key=self._tau_objective_sort_key)

    def _tau_current_kauyon_trap_objective_id(self) -> str:
        current = str(getattr(self, "_tau_kauyon_trap_objective_id", "") or "").strip()
        if current:
            return current
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return ""
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tau_root(unit)
            if root is None:
                continue
            uid = self._tau_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            current = str(sr.get("tau_kauyon_trap_objective_id", "") or "").strip()
            if current:
                self._tau_kauyon_trap_objective_id = current
                self._tau_kauyon_trap_objective_name = str(sr.get("tau_kauyon_trap_objective_name", "") or "")
                return current
        return ""

    def tau_kauyon_apply_tempting_trap_selection(self, source_unit: Any, objective: Any, *, source_name: str = "A Tempting Trap") -> bool:
        root = self._tau_root(source_unit)
        objective = self._tau_resolve_objective(objective)
        if root is None or objective is None:
            return False
        objective_id = self._tau_objective_sort_key(objective)
        if not objective_id:
            return False
        objective_name = str(getattr(objective, "name", "") or "Objective").strip() or "Objective"
        self._tau_kauyon_trap_objective_id = objective_id
        self._tau_kauyon_trap_objective_name = objective_name

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is not None:
            seen: set[str] = set()
            for unit in list(getattr(army, "units", []) or []):
                unit_root = self._tau_root(unit)
                if unit_root is None:
                    continue
                uid = self._tau_sort_key(unit_root)
                if uid and uid in seen:
                    continue
                if uid:
                    seen.add(uid)
                sr = getattr(unit_root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["tau_kauyon_trap_objective_id"] = objective_id
                sr["tau_kauyon_trap_objective_name"] = objective_name
                unit_root.special_rules = sr

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        current_turn = int(getattr(getattr(self, "game", None), "turn", 0) or 0)
        sr["tau_a_tempting_trap_active"] = True
        sr["tau_a_tempting_trap_objective_id"] = objective_id
        sr["tau_a_tempting_trap_objective_name"] = objective_name
        sr["tau_a_tempting_trap_expires_phase"] = "SHOOTING_PHASE"
        sr["tau_a_tempting_trap_turn_owner"] = owner_id
        sr["tau_a_tempting_trap_turn"] = current_turn
        sr["tau_a_tempting_trap_source"] = str(source_name or "A Tempting Trap").strip() or "A Tempting Trap"
        root.special_rules = sr
        return True

    def _tau_pending_charge_roll_request(self, charging_unit: Any) -> tuple[Any, Any]:
        game = getattr(self, "game", None)
        queue = getattr(game, "decision_queue", None)
        if charging_unit is None or queue is None or not hasattr(queue, "list"):
            return None, None

        from ..engine.decision_kinds import DECISION_REQUEST_DICE_ROLL

        charging_unit_id = self._tau_sort_key(charging_unit)
        if not charging_unit_id:
            return None, None
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != str(DECISION_REQUEST_DICE_ROLL):
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("roll_type", "") or "").strip().lower() != "charge":
                continue
            roll_spec = dict(ctx.get("roll_spec", {}) or {})
            if str(roll_spec.get("unit_id", "") or "") != charging_unit_id:
                continue
            roll_id = ctx.get("roll_id")
            state = None
            roll_manager = getattr(game, "roll_manager", None)
            if roll_id is not None and roll_manager is not None:
                state = roll_manager.get_roll(int(roll_id))
            return req, state
        return None, None

    def _tau_remove_pending_charge_roll_request(self, charging_unit: Any) -> bool:
        req, state = self._tau_pending_charge_roll_request(charging_unit)
        if req is None:
            return False
        game = getattr(self, "game", None)
        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "pop"):
            queue.pop(getattr(req, "decision_id", None))
        if state is not None:
            roll_manager = getattr(game, "roll_manager", None)
            if roll_manager is not None:
                roll_manager.rolls.pop(int(state.roll_id), None)
        try:
            charging_unit.round_state.charge_roll_id = None
        except AttributeError:
            pass
        return True

    def _tau_apply_pending_charge_roll_modifier(self, charging_unit: Any, *, value: int, source: str) -> None:
        req, state = self._tau_pending_charge_roll_request(charging_unit)
        if req is None or state is None:
            return
        reason = f"{source} ({int(value):+d})"
        spec = dict(getattr(state, "spec", {}) or {})
        breakdown = [
            dict(entry or {})
            for entry in list(spec.get("sum_modifier_breakdown", []) or [])
            if str(dict(entry or {}).get("source", "") or "").strip() != str(source or "").strip()
        ]
        breakdown.append(
            {
                "source": str(source or "Charge roll modifier").strip() or "Charge roll modifier",
                "value": int(value),
                "reason": reason,
                "contributor_type": "ability",
            }
        )
        spec["sum_modifier_breakdown"] = list(breakdown)
        spec["sum_modifier"] = sum(int(entry.get("value", 0) or 0) for entry in breakdown)
        spec["sum_modifier_reasons"] = [str(entry.get("reason", "") or "") for entry in breakdown]
        state.spec = spec

        ctx = dict(getattr(req, "context", {}) or {})
        ctx["roll_spec"] = dict(spec)
        req.context = ctx

    def _tau_combat_debarkation_candidates(self) -> list[Any]:
        if not self._is_tau_montka_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tau_root(unit)
            if root is None:
                continue
            uid = self._tau_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tau_owned_by_player(root, self.player):
                continue
            if not self._tau_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tau_empire_unit(root):
                continue
            if not self._tau_has_any_keyword(root, "INFANTRY"):
                continue
            if not self._tau_has_disembarked_this_round(root):
                continue
            transport = self._tau_resolve_friendly_transport_for_disembarked_unit(root)
            if transport is None:
                continue
            if not self._tau_has_any_keyword(transport, "TRANSPORT"):
                continue
            out.append(root)
        return sorted(out, key=self._tau_sort_key)

    def _tau_focused_fire_friendly_candidates(self) -> list[Any]:
        if not self._is_tau_montka_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tau_root(unit)
            if root is None:
                continue
            uid = self._tau_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tau_owned_by_player(root, self.player):
                continue
            if not self._tau_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tau_empire_unit(root):
                continue
            if self._tau_has_shot_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._tau_sort_key)

    def _tau_focused_fire_enemy_candidates(self) -> list[Any]:
        if not self._is_tau_montka_detachment():
            return []
        return self._tau_enemy_units_on_battlefield(require_targetable=True)

    def _tau_pulse_onslaught_enemy_candidates(
        self,
        *,
        attacker_unit: Any = None,
        hits_by_target: Any = None,
    ) -> list[Any]:
        if not self._is_tau_montka_detachment():
            return []
        attacker_root = self._tau_root(attacker_unit)
        if attacker_root is None or not self._tau_owned_by_player(attacker_root, self.player):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        if isinstance(hits_by_target, dict):
            for unit, hits in list(hits_by_target.items()):
                try:
                    if int(hits or 0) <= 0:
                        continue
                except (TypeError, ValueError):
                    continue
                root = self._tau_root(unit)
                if root is None:
                    continue
                uid = self._tau_sort_key(root)
                if uid and uid in seen:
                    continue
                if uid:
                    seen.add(uid)
                if self._tau_owned_by_player(root, self.player):
                    continue
                if not self._tau_on_battlefield(root, require_targetable=True):
                    continue
                if self._tau_unit_is_monster_or_vehicle(root):
                    continue
                out.append(root)
        return sorted(out, key=self._tau_sort_key)

    def _tau_resolve_selected_model(self, selection: Any, models: list[Any]) -> Any:
        if selection is None:
            return None
        for model in list(models or []):
            if model is selection:
                return model
        selected_id = str(get_entity_id(selection) or selection or "")
        if not selected_id:
            return None
        for model in list(models or []):
            if str(get_entity_id(model) or "") == selected_id:
                return model
        return None

    def _tau_automated_repair_drones_candidates(self) -> list[Any]:
        if not self._is_tau_experimental_prototype_cadre_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tau_root(unit)
            if root is None:
                continue
            uid = self._tau_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tau_owned_by_player(root, self.player):
                continue
            if not self._tau_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tau_battlesuit_unit(root):
                continue
            if not self._tau_wounded_battlesuit_models(root):
                continue
            out.append(root)
        return sorted(out, key=self._tau_sort_key)

    @staticmethod
    def _tau_has_shot_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(getattr(round_state, "shot_this_round", False))

    @staticmethod
    def _tau_has_fought_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(getattr(round_state, "fought_this_phase", False))

    def _tau_phase_effect_active(
        self,
        unit: Any,
        *,
        active_keys: tuple[str, ...],
        owner_keys: tuple[str, ...] = (),
        turn_keys: tuple[str, ...] = (),
        phase_keys: tuple[str, ...] = (),
        default_phase: str = "",
    ) -> bool:
        root = self._tau_root(unit)
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not any(bool(sr.get(key)) for key in tuple(active_keys or ())):
            return False

        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        if owner_id:
            effect_owner = ""
            for key in tuple(owner_keys or ()):
                value = str(sr.get(key, "") or "").strip()
                if value:
                    effect_owner = value
                    break
            if effect_owner and effect_owner != owner_id:
                return False

        game = getattr(self, "game", None)
        current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        effect_turn = 0
        for key in tuple(turn_keys or ()):
            try:
                val = int(sr.get(key, 0) or 0)
            except (TypeError, ValueError):
                val = 0
            if val:
                effect_turn = val
                break
        if effect_turn and current_turn and effect_turn != current_turn:
            return False

        current_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
        effect_phase = ""
        for key in tuple(phase_keys or ()):
            value = str(sr.get(key, "") or "").strip().upper()
            if value:
                effect_phase = value
                break
        if not effect_phase:
            effect_phase = str(default_phase or "").strip().upper()
        if effect_phase and current_phase and effect_phase != current_phase:
            return False
        return True

    def _tau_threat_assessment_analyser_active(self, unit: Any) -> bool:
        return self._tau_phase_effect_active(
            unit,
            active_keys=(
                "tau_threat_assessment_analyser_active",
                "threat_assessment_analyser_active",
                "threat_assessment_analyzer_active",
            ),
            owner_keys=(
                "tau_threat_assessment_analyser_owner",
                "tau_threat_assessment_analyser_turn_owner",
                "threat_assessment_analyser_owner",
                "threat_assessment_analyser_turn_owner",
                "threat_assessment_analyzer_owner",
                "threat_assessment_analyzer_turn_owner",
            ),
            turn_keys=(
                "tau_threat_assessment_analyser_turn",
                "threat_assessment_analyser_turn",
                "threat_assessment_analyzer_turn",
            ),
            phase_keys=(
                "tau_threat_assessment_analyser_phase",
                "tau_threat_assessment_analyser_expires_phase",
                "threat_assessment_analyser_phase",
                "threat_assessment_analyser_expires_phase",
                "threat_assessment_analyzer_phase",
                "threat_assessment_analyzer_expires_phase",
            ),
            default_phase="SHOOTING_PHASE",
        )

    def _tau_experimental_ammunition_phase_active(self, unit: Any) -> bool:
        return self._tau_phase_effect_active(
            unit,
            active_keys=(
                "tau_experimental_ammunition_phase_active",
                "tau_experimental_ammunition_active",
                "experimental_ammunition_phase_active",
                "experimental_ammunition_active",
            ),
            owner_keys=(
                "tau_experimental_ammunition_phase_owner",
                "tau_experimental_ammunition_turn_owner",
                "experimental_ammunition_phase_owner",
                "experimental_ammunition_owner",
            ),
            turn_keys=(
                "tau_experimental_ammunition_phase_turn",
                "tau_experimental_ammunition_turn",
                "experimental_ammunition_phase_turn",
                "experimental_ammunition_turn",
            ),
            phase_keys=(
                "tau_experimental_ammunition_phase",
                "tau_experimental_ammunition_expires_phase",
                "experimental_ammunition_phase",
                "experimental_ammunition_expires_phase",
            ),
            default_phase="SHOOTING_PHASE",
        )

    def _tau_experimental_prototype_shooting_candidates(self) -> list[Any]:
        if not self._is_tau_experimental_prototype_cadre_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tau_root(unit)
            if root is None:
                continue
            uid = self._tau_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tau_owned_by_player(root, self.player):
                continue
            if not self._tau_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tau_empire_unit(root):
                continue
            if self._tau_has_shot_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._tau_sort_key)

    def _tau_experimental_ammunition_candidates(self) -> list[Any]:
        out = []
        for root in self._tau_experimental_prototype_shooting_candidates():
            if self._tau_threat_assessment_analyser_active(root):
                continue
            out.append(root)
        return sorted(out, key=self._tau_sort_key)

    def _tau_experimental_weaponry_candidates(self) -> list[Any]:
        return self._tau_experimental_prototype_shooting_candidates()

    def _tau_threat_assessment_analyser_candidates(self) -> list[Any]:
        out = []
        for root in self._tau_experimental_prototype_shooting_candidates():
            if self._tau_experimental_ammunition_phase_active(root):
                continue
            out.append(root)
        return sorted(out, key=self._tau_sort_key)

    def _tau_neuroweb_system_jammer_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_tau_experimental_prototype_cadre_detachment():
            return []
        if attacking_unit is not None:
            attacker_root = self._tau_root(attacking_unit)
            if attacker_root is None:
                return []
            if self._tau_owned_by_player(attacker_root, self.player):
                return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._tau_root(unit)
            if root is None:
                continue
            uid = self._tau_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tau_owned_by_player(root, self.player):
                continue
            if not self._tau_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tau_crisis_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._tau_sort_key)

    def _tau_reactive_impact_dampeners_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_tau_experimental_prototype_cadre_detachment():
            return []
        if attacking_unit is not None:
            attacker_root = self._tau_root(attacking_unit)
            if attacker_root is None:
                return []
            if self._tau_owned_by_player(attacker_root, self.player):
                return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._tau_root(unit)
            if root is None:
                continue
            uid = self._tau_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tau_owned_by_player(root, self.player):
                continue
            if not self._tau_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tau_battlesuit_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._tau_sort_key)

    def _queue_tau_experimental_prototype_shooting_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Any,
    ) -> None:
        if attacking_unit is None:
            return
        if not self._is_tau_experimental_prototype_cadre_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return

        # NEUROWEB SYSTEM JAMMER
        stratagem = getattr(self, "get_by_name", lambda _name: None)("NEUROWEB SYSTEM JAMMER")
        if stratagem is not None:
            if int(getattr(self.player, "command_points", 0) or 0) >= int(getattr(stratagem, "cp_cost", 0) or 0):
                if str(getattr(stratagem, "name", "") or "").strip().upper() not in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                    candidates = self._tau_neuroweb_system_jammer_candidates(
                        attacking_unit=attacking_unit,
                        target_units=target_units,
                    )
                    if candidates:
                        already = False
                        for reaction in list(getattr(self, "_pending_reactions", []) or []):
                            if (
                                reaction.get("event") == "shooting_targets_selected"
                                and str(reaction.get("stratagem", "") or "").strip().upper() == str(getattr(stratagem, "name", "") or "").strip().upper()
                                and reaction.get("attacking_unit") is attacking_unit
                            ):
                                already = True
                                break
                        if not already:
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
                            queue_reaction = getattr(self, "_queue_reaction", None)
                            if callable(queue_reaction):
                                queue_reaction(payload)

        # REACTIVE IMPACT DAMPENERS
        reactive = getattr(self, "get_by_name", lambda _name: None)("REACTIVE IMPACT DAMPENERS")
        if reactive is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(reactive, "cp_cost", 0) or 0):
            return
        if str(getattr(reactive, "name", "") or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        reactive_candidates = self._tau_reactive_impact_dampeners_candidates(
            attacking_unit=attacking_unit,
            target_units=target_units,
        )
        if not reactive_candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "shooting_targets_selected"
                and str(reaction.get("stratagem", "") or "").strip().upper() == str(getattr(reactive, "name", "") or "").strip().upper()
                and reaction.get("attacking_unit") is attacking_unit
            ):
                return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": reactive.name,
            "cp_cost": reactive.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": reactive_candidates,
        }
        if len(reactive_candidates) == 1:
            payload["target_unit"] = reactive_candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_tau_montka_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_tau_montka_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        if self._tau_current_battle_round() >= 4:
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("FOCUSED FIRE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        friendly_candidates = self._tau_focused_fire_friendly_candidates()
        if len(friendly_candidates) < 2:
            return
        enemy_candidates = self._tau_focused_fire_enemy_candidates()
        if not enemy_candidates:
            return

        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "phase_start":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if str(reaction.get("phase", "") or reaction.get("phase_name", "")).strip().lower() != "shooting phase":
                continue
            return

        payload = {
            "event": "phase_start",
            "phase": "Shooting phase",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "friendly_candidates": list(friendly_candidates),
            "enemy_candidates": list(enemy_candidates),
        }
        if len(friendly_candidates) == 2:
            payload["selected_units"] = list(friendly_candidates)
            if len(enemy_candidates) == 1:
                payload["enemy_unit"] = enemy_candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_tau_montka_shooting_reactions(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> None:
        if not self._is_tau_montka_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._tau_root(attacking_unit)
        if attacker_root is None or self._tau_owned_by_player(attacker_root, self.player):
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("COUNTERFIRE DEFENCE SYSTEMS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._tau_counterfire_defence_systems_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "shooting_targets_selected"
                and str(reaction.get("stratagem", "") or "").strip().upper() == name_u
                and reaction.get("attacking_unit") is attacker_root
            ):
                return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "enemy_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_tau_montka_shooting_resolved_reactions(
        self,
        *,
        attacker_unit: Any = None,
        hits_by_target: Any = None,
    ) -> None:
        if not self._is_tau_montka_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        attacker_root = self._tau_root(attacker_unit)
        if attacker_root is None:
            return
        if not self._tau_owned_by_player(attacker_root, self.player):
            return
        if not self._tau_on_battlefield(attacker_root, require_targetable=True):
            return
        if not self._is_tau_empire_unit(attacker_root):
            return
        if self._is_tau_kroot_unit(attacker_root):
            return
        if not self._tau_has_any_keyword(attacker_root, "INFANTRY"):
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("PULSE ONSLAUGHT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        enemy_candidates = self._tau_pulse_onslaught_enemy_candidates(
            attacker_unit=attacker_root,
            hits_by_target=hits_by_target,
        )
        if not enemy_candidates:
            return

        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_shooting_resolved":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if reaction.get("unit") is attacker_root or reaction.get("attacker_unit") is attacker_root:
                return

        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": attacker_root,
            "attacker_unit": attacker_root,
            "friendly_unit": attacker_root,
            "enemy_candidates": list(enemy_candidates),
            "candidates": list(enemy_candidates),
        }
        if len(enemy_candidates) == 1:
            payload["target_unit"] = enemy_candidates[0]
            payload["enemy_unit"] = enemy_candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_tau_experimental_prototype_fight_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Any,
    ) -> None:
        if attacking_unit is None:
            return
        if not self._is_tau_experimental_prototype_cadre_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        attacker_root = self._tau_root(attacking_unit)
        if attacker_root is None:
            return
        if self._tau_owned_by_player(attacker_root, self.player):
            return

        reactive = getattr(self, "get_by_name", lambda _name: None)("REACTIVE IMPACT DAMPENERS")
        if reactive is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(reactive, "cp_cost", 0) or 0):
            return
        if str(getattr(reactive, "name", "") or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        reactive_candidates = self._tau_reactive_impact_dampeners_candidates(
            attacking_unit=attacking_unit,
            target_units=target_units,
        )
        if not reactive_candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "fight_targets_selected"
                and str(reaction.get("stratagem", "") or "").strip().upper() == str(getattr(reactive, "name", "") or "").strip().upper()
                and reaction.get("attacking_unit") is attacking_unit
            ):
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": reactive.name,
            "cp_cost": reactive.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": reactive_candidates,
        }
        if len(reactive_candidates) == 1:
            payload["target_unit"] = reactive_candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_tau_montka_unit_destroyed_reactions(
        self,
        *,
        unit: Any,
        destroyed_by_unit: Any,
    ) -> None:
        if unit is None or destroyed_by_unit is None:
            return
        if not self._is_tau_montka_detachment():
            return
        root = self._tau_root(unit)
        enemy_root = self._tau_root(destroyed_by_unit)
        if root is None or enemy_root is None:
            return
        if not self._tau_pinpoint_counter_offensive_target_eligible(root):
            return
        if self._tau_owned_by_player(enemy_root, self.player):
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("PINPOINT COUNTER-OFFENSIVE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in set(
            getattr(self, "_used_stratagems_this_phase", set()) or set()
        ):
            return

        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip() or "Any phase"
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_destroyed":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                continue
            if reaction.get("target_unit") is root and reaction.get("enemy_unit") is enemy_root:
                return

        payload = {
            "event": "unit_destroyed",
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "enemy_unit": enemy_root,
            "candidates": [root],
        }
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_tau_kauyon_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_tau_kauyon_detachment():
            return
        if player is self.player:
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "FIGHT_PHASE":
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("WALL OF MIRRORS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._tau_wall_of_mirrors_candidates()
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "phase_end":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() != "fight phase":
                continue
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
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _tau_kauyon_combat_embarkation_candidates(
        self,
        *,
        charging_unit: Any = None,
        target_units: Any = None,
    ) -> list[dict[str, Any]]:
        if not self._is_tau_kauyon_detachment():
            return []
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game is None or game_map is None:
            return []
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "CHARGE_PHASE":
            return []
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return []
        attacker_root = self._tau_root(charging_unit)
        if attacker_root is None or self._tau_owned_by_player(attacker_root, self.player):
            return []
        declared_targets = []
        for target in self._tau_resolve_unit_list(target_units):
            if not self._tau_owned_by_player(target, self.player):
                continue
            if not self._tau_on_battlefield(target, require_targetable=True):
                continue
            if not self._is_tau_empire_unit(target):
                continue
            if not self._tau_has_any_keyword(target, "INFANTRY"):
                continue
            declared_targets.append(target)
        if not declared_targets:
            return []

        from ..utility.aura_utils import unit_wholly_within_range_of_unit

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[dict[str, Any]] = []
        seen_pairs: set[tuple[str, str]] = set()
        seen_transports: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            transport = self._tau_root(unit)
            if transport is None:
                continue
            transport_id = self._tau_sort_key(transport)
            if not transport_id or transport_id in seen_transports:
                continue
            seen_transports.add(transport_id)
            if not self._tau_on_battlefield(transport, require_targetable=False):
                continue
            if not self._tau_has_any_keyword(transport, "TRANSPORT"):
                continue
            for target in list(declared_targets):
                if target is None or target is transport:
                    continue
                if bool(getattr(target.round_state, "disembarked_this_round", False)):
                    continue
                if not bool(unit_wholly_within_range_of_unit(transport, target, 3.0)):
                    continue
                enemies = list(game_map.get_enemy_units(target) or [])
                if any(enemy is not None and game_map.is_within_engagement_range(target, enemy) for enemy in enemies):
                    continue
                sr = getattr(target, "special_rules", None)
                if isinstance(sr, dict) and sr.get("fire_and_fade_no_embark_turn_owner"):
                    owner = str(sr.get("fire_and_fade_no_embark_turn_owner") or "")
                    turn = int(sr.get("fire_and_fade_no_embark_turn", 0) or 0)
                    if owner and owner == str(getattr(self.player, "id", "") or "") and int(getattr(game, "turn", 0) or 0) == turn:
                        continue
                can_transport = getattr(transport, "can_transport", None)
                if not callable(can_transport) or not bool(can_transport(target)):
                    continue
                target_id = self._tau_sort_key(target)
                pair_key = (transport_id, target_id)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                out.append(
                    {
                        "transport_id": transport_id,
                        "transport_unit": transport,
                        "target_unit_id": target_id,
                        "target_unit": target,
                        "label": f"{getattr(transport, 'name', 'Transport')}: {getattr(target, 'name', 'Unit')}",
                        "spec": {
                            "source": "Combat Embarkation",
                            "range": 3.0,
                            "allow_existing_passengers": True,
                        },
                    }
                )
        out.sort(key=lambda item: (str(item.get("transport_id", "") or ""), str(item.get("target_unit_id", "") or "")))
        return out

    def _tau_kauyon_photon_grenades_candidates(self, *, target_units: Any = None) -> list[Any]:
        if not self._is_tau_kauyon_detachment():
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for target in self._tau_resolve_unit_list(target_units):
            target_id = self._tau_sort_key(target)
            if not target_id or target_id in seen:
                continue
            seen.add(target_id)
            if not self._tau_owned_by_player(target, self.player):
                continue
            if not self._tau_on_battlefield(target, require_targetable=True):
                continue
            if not self._is_tau_empire_unit(target):
                continue
            if not self._tau_has_any_keyword(target, "GRENADES"):
                continue
            out.append(target)
        return sorted(out, key=self._tau_sort_key)

    def _queue_tau_kauyon_charge_declared_reactions(
        self,
        *,
        charging_unit: Any = None,
        target_units: Any = None,
    ) -> None:
        if not self._is_tau_kauyon_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "CHARGE_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._tau_root(charging_unit)
        if attacker_root is None or self._tau_owned_by_player(attacker_root, self.player):
            return

        combat_embarkation = getattr(self, "get_by_name", lambda _name: None)("COMBAT EMBARKATION")
        if combat_embarkation is not None:
            if int(getattr(self.player, "command_points", 0) or 0) >= int(getattr(combat_embarkation, "cp_cost", 0) or 0):
                name_u = str(getattr(combat_embarkation, "name", "") or "").strip().upper()
                if name_u not in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                    candidates = self._tau_kauyon_combat_embarkation_candidates(
                        charging_unit=attacker_root,
                        target_units=target_units,
                    )
                    if candidates:
                        already = False
                        for reaction in list(getattr(self, "_pending_reactions", []) or []):
                            if (
                                reaction.get("event") == "charge_declared"
                                and str(reaction.get("stratagem", "") or "").strip().upper() == name_u
                                and reaction.get("attacking_unit") is attacker_root
                            ):
                                already = True
                                break
                        if not already:
                            payload = {
                                "event": "charge_declared",
                                "phase_name": "Charge phase",
                                "stratagem": combat_embarkation.name,
                                "cp_cost": combat_embarkation.cp_cost,
                                "attacking_unit": attacker_root,
                                "enemy_unit": attacker_root,
                                "target_units": list(target_units or []),
                                "candidates": candidates,
                            }
                            if len(candidates) == 1:
                                payload["target_unit"] = candidates[0].get("target_unit")
                                payload["unit"] = candidates[0].get("target_unit")
                                payload["transport_unit"] = candidates[0].get("transport_unit")
                            queue_reaction = getattr(self, "_queue_reaction", None)
                            if callable(queue_reaction):
                                queue_reaction(payload)

        photon_grenades = getattr(self, "get_by_name", lambda _name: None)("PHOTON GRENADES")
        if photon_grenades is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(photon_grenades, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(photon_grenades, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._tau_kauyon_photon_grenades_candidates(target_units=target_units)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "charge_declared"
                and str(reaction.get("stratagem", "") or "").strip().upper() == name_u
                and reaction.get("attacking_unit") is attacker_root
            ):
                return
        payload = {
            "event": "charge_declared",
            "phase_name": "Charge phase",
            "stratagem": photon_grenades.name,
            "cp_cost": photon_grenades.cp_cost,
            "attacking_unit": attacker_root,
            "enemy_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
            payload["unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_tau_kauyon_ftgg_observer_reactions(
        self,
        *,
        observer_unit: Any = None,
        target_unit: Any = None,
        player: Any = None,
    ) -> None:
        if not self._is_tau_kauyon_detachment():
            return
        if player is not None and player is not self.player:
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        observer_root = self._tau_root(observer_unit)
        target_root = self._tau_root(target_unit)
        if observer_root is None or target_root is None:
            return
        if not self._tau_owned_by_player(observer_root, self.player):
            return
        if self._tau_owned_by_player(target_root, self.player):
            return
        if not self._tau_on_battlefield(observer_root, require_targetable=True):
            return

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        ftgg = getattr(army, "for_the_greater_good", None) if army is not None else None
        if ftgg is None or not bool(getattr(ftgg, "observer_targets_unit", lambda *_args, **_kwargs: False)(observer_root, target_root)):
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("COORDINATE TO ENGAGE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "ftgg_observer_selected"
                and str(reaction.get("stratagem", "") or "").strip().upper() == name_u
                and reaction.get("observer_unit") is observer_root
            ):
                return
        payload = {
            "event": "ftgg_observer_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "observer_unit": observer_root,
            "unit": observer_root,
            "target_unit": target_root,
            "enemy_unit": target_root,
            "candidates": [observer_root],
        }
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _cleanup_tau_kauyon_phase_end_effects(self, *, phase: Any = None) -> None:
        if not self._is_tau_kauyon_detachment():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        if phase_name == "SHOOTING_PHASE":
            seen: set[str] = set()
            for unit in list(getattr(army, "units", []) or []):
                root = self._tau_root(unit)
                if root is None:
                    continue
                uid = self._tau_sort_key(root)
                if uid and uid in seen:
                    continue
                if uid:
                    seen.add(uid)
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                cleanup_specs = (
                    (
                        "tau_point_blank_ambush_expires_phase",
                        (
                            "tau_point_blank_ambush_active",
                            "tau_point_blank_ambush_ap_bonus",
                            "tau_point_blank_ambush_range",
                            "tau_point_blank_ambush_expires_phase",
                            "tau_point_blank_ambush_turn_owner",
                            "tau_point_blank_ambush_turn",
                            "tau_point_blank_ambush_source",
                        ),
                    ),
                    (
                        "tau_a_tempting_trap_expires_phase",
                        (
                            "tau_a_tempting_trap_active",
                            "tau_a_tempting_trap_objective_id",
                            "tau_a_tempting_trap_objective_name",
                            "tau_a_tempting_trap_expires_phase",
                            "tau_a_tempting_trap_turn_owner",
                            "tau_a_tempting_trap_turn",
                            "tau_a_tempting_trap_source",
                        ),
                    ),
                    (
                        "tau_coordinate_to_engage_expires_phase",
                        (
                            "tau_coordinate_to_engage_active",
                            "tau_coordinate_to_engage_spotted_unit_id",
                            "tau_coordinate_to_engage_ballistic_skill_bonus",
                            "tau_coordinate_to_engage_ignores_cover",
                            "tau_coordinate_to_engage_expires_phase",
                            "tau_coordinate_to_engage_turn_owner",
                            "tau_coordinate_to_engage_turn",
                            "tau_coordinate_to_engage_source",
                        ),
                    ),
                )
                for expiry_key, keys in cleanup_specs:
                    exp = str(sr.get(expiry_key, "") or "").strip().upper()
                    if sr.get(keys[0]) is True and (not exp or exp == phase_name):
                        for key in keys:
                            sr.pop(key, None)
                root.special_rules = sr
            return

        if phase_name != "CHARGE_PHASE":
            return

        for player_entry in list(getattr(getattr(self, "game", None), "players", []) or []):
            get_player_army = getattr(player_entry, "get_army", None)
            player_army = get_player_army() if callable(get_player_army) else getattr(player_entry, "army", None)
            if player_army is None:
                continue
            seen: set[str] = set()
            for unit in list(getattr(player_army, "units", []) or []):
                root = self._tau_root(unit)
                if root is None:
                    continue
                uid = self._tau_sort_key(root)
                if uid and uid in seen:
                    continue
                if uid:
                    seen.add(uid)
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                modifiers = []
                changed = False
                for entry in list(sr.get("charge_roll_modifiers", []) or []):
                    if isinstance(entry, dict) and str(entry.get("source_key", "") or "") == "tau_photon_grenades":
                        changed = True
                        continue
                    modifiers.append(entry)
                if changed:
                    sr["charge_roll_modifiers"] = modifiers
                sr.pop("tau_photon_grenades_source", None)
                sr.pop("tau_photon_grenades_turn", None)
                sr.pop("tau_photon_grenades_turn_owner", None)
                root.special_rules = sr


    def _queue_tau_auxiliary_cadre_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_tau_auxiliary_cadre_detachment():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "FIGHT_PHASE":
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("INTERLOCKING MANOUEVRES")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._tau_auxiliary_cadre_interlocking_candidates()
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "phase_end":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() != "fight phase":
                continue
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
            payload["target_unit"] = candidates[0]
            payload["unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    @staticmethod
    def _tau_parse_experimental_ammunition_mode(raw_mode: Any) -> Optional[str]:
        mode = raw_mode
        if isinstance(mode, dict):
            mode = (
                mode.get("mode")
                or mode.get("choice")
                or mode.get("selection")
                or mode.get("effect")
                or mode.get("option")
            )
        mode_key = str(mode or "").strip().lower().replace("_", " ").replace("-", " ")
        mode_key = " ".join(mode_key.split())
        if not mode_key:
            return "strength"
        strength_modes = {
            "strength",
            "strength only",
            "s",
            "option 1",
            "1",
            "basic",
        }
        hazardous_modes = {
            "strength ap hazardous",
            "strength and ap hazardous",
            "strength ap",
            "ap hazardous",
            "hazardous",
            "high output",
            "option 2",
            "2",
        }
        if mode_key in strength_modes:
            return "strength"
        if mode_key in hazardous_modes:
            return "hazardous"
        return None

    @staticmethod
    def _tau_parse_threat_assessment_analyser_mode(raw_mode: Any) -> Optional[str]:
        mode = raw_mode
        if isinstance(mode, dict):
            mode = (
                mode.get("mode")
                or mode.get("choice")
                or mode.get("selection")
                or mode.get("effect")
                or mode.get("option")
            )
        mode_key = str(mode or "").strip().lower().replace("_", " ").replace("-", " ")
        mode_key = " ".join(mode_key.split())
        if not mode_key:
            return "sustained"
        sustained_modes = {
            "sustained",
            "sustained hits",
            "sustained hits 1",
            "sustained 1",
            "option 1 sustained",
            "1 sustained",
        }
        lethal_modes = {
            "lethal",
            "lethal hits",
            "option 1 lethal",
            "1 lethal",
        }
        all_modes = {
            "all",
            "both",
            "combined",
            "triple",
            "hazardous",
            "sustained lethal hazardous",
            "sustained hits lethal hits hazardous",
            "option 2",
            "2",
        }
        if mode_key in sustained_modes:
            return "sustained"
        if mode_key in lethal_modes:
            return "lethal"
        if mode_key in all_modes:
            return "all"
        return None

    def _tau_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
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

    def _tau_place_unit_into_strategic_reserves(self, unit: Any, *, reason: str = "") -> bool:
        root = self._tau_root(unit)
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

    def _tau_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue and hasattr(self, "_dequeue_reaction_by_name"):
            self._dequeue_reaction_by_name(getattr(stratagem, "name", ""))
        used = getattr(self, "_used_stratagems_this_phase", None)
        if isinstance(used, set):
            raw_name = str(getattr(stratagem, "name", "") or "").strip().upper()
            if raw_name:
                used.add(raw_name)

    def _use_tau_empire_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        result = self._use_tau_experimental_prototype_cadre_stratagem(stratagem, **kwargs)
        if result is not None:
            return result
        result = self._use_tau_auxiliary_cadre_stratagem(stratagem, **kwargs)
        if result is not None:
            return result
        result = self._use_tau_montka_stratagem(stratagem, **kwargs)
        if result is not None:
            return result
        return self._use_tau_kauyon_stratagem(stratagem, **kwargs)

    def _use_tau_experimental_prototype_cadre_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        if not self._is_tau_experimental_prototype_cadre_detachment():
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "AUTOMATED REPAIR DRONES":
            return self._use_tau_automated_repair_drones(stratagem, **kwargs)
        if name_u == "REACTIVE IMPACT DAMPENERS":
            return self._use_tau_reactive_impact_dampeners(stratagem, **kwargs)
        if name_u == "NEUROWEB SYSTEM JAMMER":
            return self._use_tau_neuroweb_system_jammer(stratagem, **kwargs)
        if name_u == "EXPERIMENTAL WEAPONRY":
            return self._use_tau_experimental_weaponry(stratagem, **kwargs)
        if name_u == "EXPERIMENTAL AMMUNITION":
            return self._use_tau_experimental_ammunition(stratagem, **kwargs)
        if name_u == "THREAT ASSESSMENT ANALYSER":
            return self._use_tau_threat_assessment_analyser(stratagem, **kwargs)
        return None

    def _use_tau_auxiliary_cadre_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        if not self._is_tau_auxiliary_cadre_detachment():
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "ALIEN EXPERTISE":
            return self._use_tau_alien_expertise(stratagem, **kwargs)
        if name_u == "EXPERIMENTAL MODIFICATIONS":
            return self._use_tau_experimental_modifications(stratagem, **kwargs)
        if name_u == "GUIDED FIRE":
            return self._use_tau_guided_fire(stratagem, **kwargs)
        if name_u == "INTERLOCKING MANOUEVRES":
            return self._use_tau_interlocking_manoeuvres(stratagem, **kwargs)
        if name_u == "MULTISENSORY SCANNING":
            return self._use_tau_multisensory_scanning(stratagem, **kwargs)
        if name_u == "PHEROMONE WAYPOINTS":
            return self._use_tau_pheromone_waypoints(stratagem, **kwargs)
        return None

    def _use_tau_montka_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        if not self._is_tau_montka_detachment():
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "AGGRESSIVE MOBILITY":
            return self._use_tau_aggressive_mobility(stratagem, **kwargs)
        if name_u == "COMBAT DEBARKATION":
            return self._use_tau_combat_debarkation(stratagem, **kwargs)
        if name_u == "FOCUSED FIRE":
            return self._use_tau_focused_fire(stratagem, **kwargs)
        if name_u == "COUNTERFIRE DEFENCE SYSTEMS":
            return self._use_tau_counterfire_defence_systems(stratagem, **kwargs)
        if name_u == "PINPOINT COUNTER-OFFENSIVE":
            return self._use_tau_pinpoint_counter_offensive(stratagem, **kwargs)
        if name_u == "PULSE ONSLAUGHT":
            return self._use_tau_pulse_onslaught(stratagem, **kwargs)
        return None

    def _use_tau_kauyon_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        if not self._is_tau_kauyon_detachment():
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "A TEMPTING TRAP":
            return self._use_tau_a_tempting_trap(stratagem, **kwargs)
        if name_u == "COORDINATE TO ENGAGE":
            return self._use_tau_coordinate_to_engage(stratagem, **kwargs)
        if name_u == "COMBAT EMBARKATION":
            return self._use_tau_combat_embarkation(stratagem, **kwargs)
        if name_u == "PHOTON GRENADES":
            return self._use_tau_photon_grenades(stratagem, **kwargs)
        if name_u == "WALL OF MIRRORS":
            return self._use_tau_wall_of_mirrors(stratagem, **kwargs)
        if name_u == "POINT-BLANK AMBUSH":
            return self._use_tau_point_blank_ambush(stratagem, **kwargs)
        return None

    def _use_tau_interlocking_manoeuvres(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if (target_unit is None or not candidates) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "INTERLOCKING MANOUEVRES":
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: INTERLOCKING MANOUEVRES: no target unit provided")
            return False

        root = self._tau_root(target_unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "fight phase":
            logger.error("ERROR: INTERLOCKING MANOUEVRES: wrong phase")
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: INTERLOCKING MANOUEVRES: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tau_empire_unit(root):
            logger.error("ERROR: INTERLOCKING MANOUEVRES: target must be a T'AU EMPIRE unit")
            return False

        eligible = candidates or self._tau_auxiliary_cadre_interlocking_candidates()
        if eligible and not self._tau_unit_in_candidates(root, eligible):
            logger.error("ERROR: INTERLOCKING MANOUEVRES: target is not currently eligible")
            return False
        round_state = getattr(root, "round_state", None)
        was_eligible = bool(getattr(round_state, "eligible_to_fight_this_phase", False))
        if not was_eligible and bool(getattr(round_state, "fought_this_phase", False)):
            was_eligible = True
        if not was_eligible:
            logger.error("ERROR: INTERLOCKING MANOUEVRES: target must have been eligible to fight this phase")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: INTERLOCKING MANOUEVRES: cannot be used in current state")
            return False
        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False

        engaged = self._tau_has_enemy_within_engagement_range(root)
        movement_type = "fall_back" if engaged else "move"
        max_distance = int(getattr(root, "movement", 0) or 0) if engaged else 6
        if max_distance <= 0:
            max_distance = 1
        extra_context = {}
        if bool(getattr(round_state, "disembarked_this_round", False)):
            extra_context["interlocking_manoeuvres_no_embark_after_move"] = True
            extra_context["interlocking_manoeuvres_turn_owner"] = str(getattr(self.player, "id", "") or "")
            extra_context["interlocking_manoeuvres_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0

        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if not callable(queue_move):
            logger.error("ERROR: INTERLOCKING MANOUEVRES: reactive move decision queue unavailable")
            return False
        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=int(max_distance),
            kind="interlocking_manoeuvres",
            movement_type=str(movement_type),
            source=str(getattr(stratagem, "name", "INTERLOCKING MANOUEVRES") or "INTERLOCKING MANOUEVRES"),
            allow_skip=True,
            extra_context=extra_context,
        )
        if request is None:
            logger.error("ERROR: INTERLOCKING MANOUEVRES: failed to queue move decision")
            return False

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: INTERLOCKING MANOUEVRES: %s can make a %s move.",
            getattr(root, "name", "Unit"),
            "Fall Back" if engaged else "Normal",
        )
        return True

    def _use_tau_alien_expertise(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: ALIEN EXPERTISE: no target unit provided")
            return False

        root = self._tau_root(target_unit)
        if root is None:
            return False
        phase_name = self._tau_normalized_phase_name(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "movement phase":
            logger.error("ERROR: ALIEN EXPERTISE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: ALIEN EXPERTISE: not your Movement phase")
            return False
        if candidates and not self._tau_unit_in_candidates(root, candidates):
            logger.error("ERROR: ALIEN EXPERTISE: target is not currently eligible")
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: ALIEN EXPERTISE: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tau_empire_unit(root):
            logger.error("ERROR: ALIEN EXPERTISE: target must be a T'AU EMPIRE unit")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: ALIEN EXPERTISE: cannot be used in current state")
            return False
        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False

        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        source_name = str(getattr(stratagem, "name", "") or "ALIEN EXPERTISE")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tau_alien_expertise_active"] = True
        sr["tau_alien_expertise_shoot_after_advance"] = True
        sr["tau_alien_expertise_charge_after_advance"] = bool(self._is_tau_kroot_or_vespid_unit(root))
        sr["tau_alien_expertise_turn_owner"] = owner_id
        sr["tau_alien_expertise_turn"] = int(current_turn)
        sr["tau_alien_expertise_source"] = source_name
        root.special_rules = sr

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ALIEN EXPERTISE: %s can shoot after Advancing this turn%s.",
            getattr(root, "name", "Unit"),
            " and charge after Advancing" if self._is_tau_kroot_or_vespid_unit(root) else "",
        )
        return True

    def _use_tau_experimental_modifications(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: EXPERIMENTAL MODIFICATIONS: no target unit provided")
            return False

        root = self._tau_root(target_unit)
        if root is None:
            return False
        phase_name = self._tau_normalized_phase_name(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: EXPERIMENTAL MODIFICATIONS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: EXPERIMENTAL MODIFICATIONS: not your Shooting phase")
            return False

        eligible = candidates or self._tau_experimental_modifications_candidates(phase_name=phase_name)
        if eligible and not self._tau_unit_in_candidates(root, eligible):
            logger.error("ERROR: EXPERIMENTAL MODIFICATIONS: target is not currently eligible")
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: EXPERIMENTAL MODIFICATIONS: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tau_kroot_or_vespid_unit(root):
            logger.error("ERROR: EXPERIMENTAL MODIFICATIONS: target must be a Kroot or Vespid unit")
            return False
        if phase_name == "shooting phase" and self._tau_has_shot_this_phase(root):
            logger.error("ERROR: EXPERIMENTAL MODIFICATIONS: target has already been selected to shoot this phase")
            return False
        if phase_name == "fight phase" and self._tau_has_fought_this_phase(root):
            logger.error("ERROR: EXPERIMENTAL MODIFICATIONS: target has already been selected to fight this phase")
            return False
        phase_label = "Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name=phase_label):
            logger.error("ERROR: EXPERIMENTAL MODIFICATIONS: cannot be used in current state")
            return False
        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False

        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        expires_phase = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        attack_type = "ranged" if phase_name == "shooting phase" else "melee"
        source_name = str(getattr(stratagem, "name", "") or "EXPERIMENTAL MODIFICATIONS")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tau_experimental_modifications_active"] = True
        sr["tau_experimental_modifications_ap_bonus"] = 1
        sr["tau_experimental_modifications_attack_type"] = attack_type
        sr["tau_experimental_modifications_expires_phase"] = expires_phase
        sr["tau_experimental_modifications_turn_owner"] = owner_id
        sr["tau_experimental_modifications_turn"] = int(current_turn)
        sr["tau_experimental_modifications_source"] = source_name
        root.special_rules = sr

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: EXPERIMENTAL MODIFICATIONS: %s improves AP by 1 on %s weapons this phase.",
            getattr(root, "name", "Unit"),
            attack_type,
        )
        return True

    def _use_tau_guided_fire(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: GUIDED FIRE: no target unit provided")
            return False

        root = self._tau_root(target_unit)
        if root is None:
            return False
        phase_name = self._tau_normalized_phase_name(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "shooting phase":
            logger.error("ERROR: GUIDED FIRE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: GUIDED FIRE: not your Shooting phase")
            return False

        eligible = candidates or self._tau_guided_fire_candidates()
        if eligible and not self._tau_unit_in_candidates(root, eligible):
            logger.error("ERROR: GUIDED FIRE: target is not currently eligible")
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: GUIDED FIRE: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tau_empire_unit(root):
            logger.error("ERROR: GUIDED FIRE: target must be a T'AU EMPIRE unit")
            return False
        if self._is_tau_kroot_or_vespid_unit(root):
            logger.error("ERROR: GUIDED FIRE: target cannot be a Kroot or Vespid unit")
            return False
        if self._tau_has_shot_this_phase(root):
            logger.error("ERROR: GUIDED FIRE: target has already been selected to shoot this phase")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: GUIDED FIRE: cannot be used in current state")
            return False
        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False

        strength_bonus = self._tau_guided_fire_strength_bonus(root)
        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        source_name = str(getattr(stratagem, "name", "") or "GUIDED FIRE")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tau_guided_fire_active"] = True
        sr["tau_guided_fire_strength_bonus"] = int(strength_bonus)
        sr["tau_guided_fire_expires_phase"] = "SHOOTING_PHASE"
        sr["tau_guided_fire_turn_owner"] = owner_id
        sr["tau_guided_fire_turn"] = int(current_turn)
        sr["tau_guided_fire_source"] = source_name
        root.special_rules = sr

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: GUIDED FIRE: %s gains +%d Strength on ranged weapons this phase.",
            getattr(root, "name", "Unit"),
            int(strength_bonus),
        )
        return True

    def _use_tau_multisensory_scanning(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: MULTISENSORY SCANNING: no target unit provided")
            return False

        root = self._tau_root(target_unit)
        if root is None:
            return False
        phase_name = self._tau_normalized_phase_name(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: MULTISENSORY SCANNING: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: MULTISENSORY SCANNING: not your Shooting phase")
            return False

        eligible = candidates or self._tau_multisensory_scanning_candidates(phase_name=phase_name)
        if eligible and not self._tau_unit_in_candidates(root, eligible):
            logger.error("ERROR: MULTISENSORY SCANNING: target is not currently eligible")
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: MULTISENSORY SCANNING: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tau_empire_unit(root):
            logger.error("ERROR: MULTISENSORY SCANNING: target must be a T'AU EMPIRE unit")
            return False
        if phase_name == "shooting phase" and self._tau_has_shot_this_phase(root):
            logger.error("ERROR: MULTISENSORY SCANNING: target has already been selected to shoot this phase")
            return False
        if phase_name == "fight phase" and self._tau_has_fought_this_phase(root):
            logger.error("ERROR: MULTISENSORY SCANNING: target has already been selected to fight this phase")
            return False
        phase_label = "Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name=phase_label):
            logger.error("ERROR: MULTISENSORY SCANNING: cannot be used in current state")
            return False
        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False

        reroll_mode = "full" if self._is_tau_kroot_or_vespid_unit(root) else "ones"
        attack_type = "ranged" if phase_name == "shooting phase" else "melee"
        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        expires_phase = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        source_name = str(getattr(stratagem, "name", "") or "MULTISENSORY SCANNING")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tau_multisensory_scanning_active"] = True
        sr["tau_multisensory_scanning_attack_type"] = attack_type
        sr["tau_multisensory_scanning_reroll_mode"] = reroll_mode
        sr["tau_multisensory_scanning_expires_phase"] = expires_phase
        sr["tau_multisensory_scanning_turn_owner"] = owner_id
        sr["tau_multisensory_scanning_turn"] = int(current_turn)
        sr["tau_multisensory_scanning_source"] = source_name
        root.special_rules = sr

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MULTISENSORY SCANNING: %s can re-roll %s Wound rolls on %s attacks this phase.",
            getattr(root, "name", "Unit"),
            "all" if reroll_mode == "full" else "Wound rolls of 1",
            attack_type,
        )
        return True

    def _use_tau_pheromone_waypoints(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: PHEROMONE WAYPOINTS: no target unit provided")
            return False

        root = self._tau_root(target_unit)
        if root is None:
            return False
        phase_name = self._tau_normalized_phase_name(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "movement phase":
            logger.error("ERROR: PHEROMONE WAYPOINTS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: PHEROMONE WAYPOINTS: not your Movement phase")
            return False

        eligible = candidates or self._tau_pheromone_waypoints_candidates()
        if eligible and not self._tau_unit_in_candidates(root, eligible):
            logger.error("ERROR: PHEROMONE WAYPOINTS: target is not currently eligible")
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: PHEROMONE WAYPOINTS: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tau_kroot_or_vespid_unit(root):
            logger.error("ERROR: PHEROMONE WAYPOINTS: target must be a Kroot or Vespid unit")
            return False
        if self._tau_selected_to_move_this_phase(root):
            logger.error("ERROR: PHEROMONE WAYPOINTS: target has already been selected to move this phase")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: PHEROMONE WAYPOINTS: cannot be used in current state")
            return False
        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "PHEROMONE WAYPOINTS")
        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        effect_tag = "stratagem:tau_pheromone_waypoints"
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
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
                "turn_owner": owner_id,
                "turn": int(current_turn),
            }
        )
        sr["advance_no_roll_effects"] = effects
        root.special_rules = sr

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PHEROMONE WAYPOINTS: %s treats its Advance this phase as a fixed +6\".",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tau_wall_of_mirrors(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if (target_unit is None or not candidates) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "WALL OF MIRRORS":
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: WALL OF MIRRORS: no target unit provided")
            return False

        root = self._tau_root(target_unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "fight phase":
            logger.error("ERROR: WALL OF MIRRORS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: WALL OF MIRRORS: not opponent's Fight phase")
            return False

        eligible = candidates or self._tau_wall_of_mirrors_candidates()
        if eligible and not self._tau_unit_in_candidates(root, eligible):
            logger.error("ERROR: WALL OF MIRRORS: target is not currently eligible")
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: WALL OF MIRRORS: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._tau_wall_of_mirrors_unit_eligible(root):
            logger.error("ERROR: WALL OF MIRRORS: target must be a Stealth, Ghostkeel, or Commander Shadowsun unit")
            return False
        if self._tau_has_enemy_within_engagement_range(root):
            logger.error("ERROR: WALL OF MIRRORS: target is within Engagement Range")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: WALL OF MIRRORS: cannot be used in current state")
            return False
        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False
        if not self._tau_place_unit_into_strategic_reserves(root, reason=str(getattr(stratagem, "name", "") or "")):
            logger.error("ERROR: WALL OF MIRRORS: failed to place target into Strategic Reserves")
            return False

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: WALL OF MIRRORS: %s entered Strategic Reserves.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tau_point_blank_ambush(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: POINT-BLANK AMBUSH: no target unit provided")
            return False

        root = self._tau_root(target_unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: POINT-BLANK AMBUSH: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: POINT-BLANK AMBUSH: not your Shooting phase")
            return False
        if self._tau_current_battle_round() <= 2:
            logger.error("ERROR: POINT-BLANK AMBUSH: cannot be used in the first or second battle rounds")
            return False

        eligible = candidates or self._tau_point_blank_ambush_candidates()
        if eligible and not self._tau_unit_in_candidates(root, eligible):
            logger.error("ERROR: POINT-BLANK AMBUSH: target is not currently eligible")
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: POINT-BLANK AMBUSH: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tau_empire_unit(root):
            logger.error("ERROR: POINT-BLANK AMBUSH: target must be a T'AU EMPIRE unit")
            return False
        if self._tau_has_shot_this_phase(root):
            logger.error("ERROR: POINT-BLANK AMBUSH: target has already been selected to shoot this phase")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, target_unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: POINT-BLANK AMBUSH: cannot be used in current state")
            return False
        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tau_point_blank_ambush_active"] = True
        sr["tau_point_blank_ambush_ap_bonus"] = 1
        sr["tau_point_blank_ambush_range"] = 9.0
        sr["tau_point_blank_ambush_expires_phase"] = "SHOOTING_PHASE"
        sr["tau_point_blank_ambush_turn_owner"] = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        sr["tau_point_blank_ambush_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["tau_point_blank_ambush_source"] = str(getattr(stratagem, "name", "") or "POINT-BLANK AMBUSH")
        root.special_rules = sr

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: POINT-BLANK AMBUSH: %s improves AP by 1 against enemies within 9\" this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tau_a_tempting_trap(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        objective = kwargs.get("objective") or kwargs.get("objective_marker") or kwargs.get("objective_id")
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: A TEMPTING TRAP: no target unit provided")
            return False

        root = self._tau_root(target_unit)
        if root is None:
            return False
        phase_name = self._tau_normalized_phase_name(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "shooting phase":
            logger.error("ERROR: A TEMPTING TRAP: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: A TEMPTING TRAP: not your Shooting phase")
            return False

        eligible = candidates or self._tau_point_blank_ambush_candidates()
        if eligible and not self._tau_unit_in_candidates(root, eligible):
            logger.error("ERROR: A TEMPTING TRAP: target is not currently eligible")
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: A TEMPTING TRAP: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tau_empire_unit(root):
            logger.error("ERROR: A TEMPTING TRAP: target must be a T'AU EMPIRE unit")
            return False
        if self._tau_has_shot_this_phase(root):
            logger.error("ERROR: A TEMPTING TRAP: target has already been selected to shoot this phase")
            return False

        objective_candidates = self._tau_objective_candidates_not_in_opponent_deployment_zone()
        trap_objective_id = self._tau_current_kauyon_trap_objective_id()
        phase_label = "Shooting phase"
        source_name = str(getattr(stratagem, "name", "") or "A TEMPTING TRAP").strip() or "A TEMPTING TRAP"

        if not trap_objective_id and objective is None:
            request_decision = getattr(self.game, "request_decision", None) if self.game is not None else None
            if not callable(request_decision):
                logger.error("ERROR: A TEMPTING TRAP: decision queue unavailable")
                return False
            if not objective_candidates:
                logger.error("ERROR: A TEMPTING TRAP: no eligible objective markers")
                return False
            from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
            from ..engine.decisions import DecisionOption, DecisionRequest

            unit_id = self._tau_sort_key(root)
            candidate_objective_ids = [
                self._tau_objective_sort_key(candidate)
                for candidate in list(objective_candidates)
                if self._tau_objective_sort_key(candidate)
            ]
            if not unit_id or not candidate_objective_ids:
                logger.error("ERROR: A TEMPTING TRAP: source unit or objective candidates missing stable ids")
                return False
            if self._tau_pending_choose_quarry_request(
                ability="tau_kauyon_tempting_trap_objective",
                source_unit_id=unit_id,
            ):
                logger.error("ERROR: A TEMPTING TRAP: objective selection already queued")
                return False
            if not stratagem.can_use(self.player, self.game, unit=root, target_unit=root, phase_name=phase_label):
                logger.error("ERROR: A TEMPTING TRAP: cannot be used in current state")
                return False
            if not self._tau_spend_cp(stratagem, target_unit=root):
                return False
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{source_name}: select one objective marker that is not in your opponent's deployment zone.",
                player_id=getattr(self.player, "id", None),
                options=[
                    DecisionOption.create(
                        str(getattr(candidate, "name", "Objective") or "Objective"),
                        payload={
                            "unit_id": unit_id,
                            "source_unit_id": unit_id,
                            "objective_id": self._tau_objective_sort_key(candidate),
                        },
                    )
                    for candidate in list(objective_candidates)
                    if self._tau_objective_sort_key(candidate)
                ],
                context={
                    "ability": "tau_kauyon_tempting_trap_objective",
                    "ability_name": source_name,
                    "phase": phase_label,
                    "phase_name": phase_label,
                    "unit_id": unit_id,
                    "source_unit_id": unit_id,
                    "candidate_objective_ids": list(candidate_objective_ids),
                    "optional": False,
                },
            )
            request_decision(request)
            self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info("INFO: A TEMPTING TRAP: queued Trap objective selection for %s.", getattr(root, "name", "Unit"))
            return True

        selected_objective = self._tau_resolve_objective(trap_objective_id or objective)
        if selected_objective is None:
            logger.error("ERROR: A TEMPTING TRAP: Trap objective marker not found")
            return False
        if not trap_objective_id:
            selected_objective_id = self._tau_objective_sort_key(selected_objective)
            if selected_objective_id not in {self._tau_objective_sort_key(candidate) for candidate in list(objective_candidates)}:
                logger.error("ERROR: A TEMPTING TRAP: selected objective is not eligible")
                return False
        if not stratagem.can_use(self.player, self.game, unit=root, target_unit=root, phase_name=phase_label):
            logger.error("ERROR: A TEMPTING TRAP: cannot be used in current state")
            return False
        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False
        if not self.tau_kauyon_apply_tempting_trap_selection(root, selected_objective, source_name=source_name):
            logger.error("ERROR: A TEMPTING TRAP: failed to apply Trap objective")
            return False

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: A TEMPTING TRAP: %s gains +1 to wound with ranged attacks against enemies within range of %s this phase.",
            getattr(root, "name", "Unit"),
            getattr(selected_objective, "name", "Objective"),
        )
        return True

    def _use_tau_coordinate_to_engage(self, stratagem: Any, **kwargs) -> bool:
        observer_unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("observer_unit")
        target_unit = kwargs.get("enemy_unit") or kwargs.get("spotted_unit") or kwargs.get("target_enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        if (observer_unit is None or target_unit is None or not candidates) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "COORDINATE TO ENGAGE":
                    continue
                if observer_unit is None:
                    observer_unit = reaction.get("observer_unit") or reaction.get("unit") or reaction.get("target_unit")
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if observer_unit is None and len(candidates) == 1:
            observer_unit = candidates[0]
        if observer_unit is None:
            logger.error("ERROR: COORDINATE TO ENGAGE: no observer unit provided")
            return False

        root = self._tau_root(observer_unit)
        spotted_root = self._tau_root(target_unit)
        if root is None:
            return False
        phase_name = self._tau_normalized_phase_name(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "shooting phase":
            logger.error("ERROR: COORDINATE TO ENGAGE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: COORDINATE TO ENGAGE: not your Shooting phase")
            return False
        if candidates and not self._tau_unit_in_candidates(root, candidates):
            logger.error("ERROR: COORDINATE TO ENGAGE: target is not currently eligible")
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: COORDINATE TO ENGAGE: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tau_empire_unit(root):
            logger.error("ERROR: COORDINATE TO ENGAGE: target must be a T'AU EMPIRE unit")
            return False
        if self._tau_has_shot_this_phase(root):
            logger.error("ERROR: COORDINATE TO ENGAGE: target has already been selected to shoot this phase")
            return False

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        ftgg = getattr(army, "for_the_greater_good", None) if army is not None else None
        if ftgg is None or not bool(getattr(ftgg, "is_observer", lambda *_args, **_kwargs: False)(root)):
            logger.error("ERROR: COORDINATE TO ENGAGE: target is not currently an Observer unit")
            return False
        spotted_unit_id = str(getattr(ftgg, "get_observer_target_id", lambda *_args, **_kwargs: "")(root) or "")
        if not spotted_unit_id:
            logger.error("ERROR: COORDINATE TO ENGAGE: Observer has no Spotted unit")
            return False
        if spotted_root is not None and self._tau_sort_key(spotted_root) != spotted_unit_id:
            logger.error("ERROR: COORDINATE TO ENGAGE: selected enemy is not the unit's Spotted unit")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, target_unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: COORDINATE TO ENGAGE: cannot be used in current state")
            return False
        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tau_coordinate_to_engage_active"] = True
        sr["tau_coordinate_to_engage_spotted_unit_id"] = spotted_unit_id
        sr["tau_coordinate_to_engage_ballistic_skill_bonus"] = 1
        sr["tau_coordinate_to_engage_ignores_cover"] = bool(self._tau_has_any_keyword(root, "MARKERLIGHT"))
        sr["tau_coordinate_to_engage_expires_phase"] = "SHOOTING_PHASE"
        sr["tau_coordinate_to_engage_turn_owner"] = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        sr["tau_coordinate_to_engage_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["tau_coordinate_to_engage_source"] = str(getattr(stratagem, "name", "") or "COORDINATE TO ENGAGE")
        root.special_rules = sr

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: COORDINATE TO ENGAGE: %s improves BS by 1 against its Spotted unit this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tau_combat_embarkation(self, stratagem: Any, **kwargs) -> bool:
        charging_unit = kwargs.get("charging_unit") or kwargs.get("attacking_unit") or kwargs.get("enemy_unit")
        target_units = list(kwargs.get("target_units") or [])
        candidates = [dict(candidate or {}) for candidate in list(kwargs.get("candidates") or []) if isinstance(candidate, dict)]
        if (charging_unit is None or not target_units or not candidates) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "COMBAT EMBARKATION":
                    continue
                if charging_unit is None:
                    charging_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                if not candidates:
                    candidates = [
                        dict(candidate or {})
                        for candidate in list(reaction.get("candidates") or [])
                        if isinstance(candidate, dict)
                    ]
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if charging_unit is None:
            logger.error("ERROR: COMBAT EMBARKATION: charging unit not provided")
            return False

        attacker_root = self._tau_root(charging_unit)
        if attacker_root is None:
            return False
        phase_name = self._tau_normalized_phase_name(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "charge phase":
            logger.error("ERROR: COMBAT EMBARKATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: COMBAT EMBARKATION: not opponent's Charge phase")
            return False
        if self._tau_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: COMBAT EMBARKATION: charging unit must be enemy")
            return False

        candidate_specs = candidates or self._tau_kauyon_combat_embarkation_candidates(
            charging_unit=attacker_root,
            target_units=target_units,
        )
        if not candidate_specs:
            logger.error("ERROR: COMBAT EMBARKATION: no eligible embarkation targets")
            return False
        if not stratagem.can_use(self.player, self.game, phase_name="Charge phase", attacking_unit=attacker_root, target_units=list(target_units or [])):
            logger.error("ERROR: COMBAT EMBARKATION: cannot be used in current state")
            return False

        request_decision = getattr(self.game, "request_decision", None) if self.game is not None else None
        if not callable(request_decision):
            logger.error("ERROR: COMBAT EMBARKATION: decision queue unavailable")
            return False
        charging_unit_id = self._tau_sort_key(attacker_root)
        target_unit_ids = [
            self._tau_sort_key(unit)
            for unit in self._tau_resolve_unit_list(target_units)
            if self._tau_sort_key(unit)
        ]
        if self._tau_pending_choose_quarry_request(
            ability="emergency_combat_embarkation",
            charging_unit_id=charging_unit_id,
        ):
            logger.error("ERROR: COMBAT EMBARKATION: embarkation decision already queued")
            return False
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        if not self._tau_spend_cp(stratagem, target_unit=None):
            return False
        self._tau_remove_pending_charge_roll_request(attacker_root)
        options = []
        for candidate in list(candidate_specs):
            transport_id = str(candidate.get("transport_id", "") or "")
            target_unit_id = str(candidate.get("target_unit_id", "") or "")
            if not transport_id or not target_unit_id:
                continue
            options.append(
                DecisionOption.create(
                    str(candidate.get("label", "") or "Combat Embarkation"),
                    payload={
                        "transport_id": transport_id,
                        "target_unit_id": target_unit_id,
                        "spec": dict(candidate.get("spec", {}) or {}),
                    },
                )
            )
        if not options:
            logger.error("ERROR: COMBAT EMBARKATION: embarkation options could not be constructed")
            return False
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Combat Embarkation: select one declared charge target to embark.",
            player_id=getattr(self.player, "id", None),
            options=options,
            context={
                "ability": "emergency_combat_embarkation",
                "ability_name": "Combat Embarkation",
                "phase": "Opponent Charge phase",
                "charging_unit_id": charging_unit_id,
                "target_unit_ids": list(target_unit_ids),
                "out_of_turn": False,
                "count_as_charged": True,
                "optional": False,
            },
        )
        request_decision(request)
        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: COMBAT EMBARKATION: queued embarkation choice against %s.", getattr(attacker_root, "name", "Unit"))
        return True

    def _use_tau_photon_grenades(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        charging_unit = kwargs.get("charging_unit") or kwargs.get("attacking_unit") or kwargs.get("enemy_unit")
        target_units = list(kwargs.get("target_units") or [])
        candidates = list(kwargs.get("candidates") or [])
        if (target_unit is None or charging_unit is None or not candidates) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "PHOTON GRENADES":
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if charging_unit is None:
                    charging_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: PHOTON GRENADES: no target unit provided")
            return False
        if charging_unit is None:
            logger.error("ERROR: PHOTON GRENADES: charging unit not provided")
            return False

        root = self._tau_root(target_unit)
        attacker_root = self._tau_root(charging_unit)
        if root is None or attacker_root is None:
            return False
        phase_name = self._tau_normalized_phase_name(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "charge phase":
            logger.error("ERROR: PHOTON GRENADES: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: PHOTON GRENADES: not opponent's Charge phase")
            return False
        if self._tau_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: PHOTON GRENADES: charging unit must be enemy")
            return False

        eligible = candidates or self._tau_kauyon_photon_grenades_candidates(target_units=target_units)
        if eligible and not self._tau_unit_in_candidates(root, eligible):
            logger.error("ERROR: PHOTON GRENADES: target is not currently eligible")
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: PHOTON GRENADES: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._tau_has_any_keyword(root, "GRENADES"):
            logger.error("ERROR: PHOTON GRENADES: target must have the GRENADES keyword")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, target_unit=root, phase_name="Charge phase"):
            logger.error("ERROR: PHOTON GRENADES: cannot be used in current state")
            return False
        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False

        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        source_name = str(getattr(stratagem, "name", "") or "PHOTON GRENADES").strip() or "PHOTON GRENADES"
        force_test = getattr(attacker_root, "force_battle_shock_test", None)
        if callable(force_test):
            force_test(current_turn=current_turn, source=source_name)

        attacker_sr = getattr(attacker_root, "special_rules", None)
        if not isinstance(attacker_sr, dict):
            attacker_sr = {}
        modifiers = [
            entry
            for entry in list(attacker_sr.get("charge_roll_modifiers", []) or [])
            if not (isinstance(entry, dict) and str(entry.get("source_key", "") or "") == "tau_photon_grenades")
        ]
        modifiers.append(
            {
                "value": -2,
                "source": source_name,
                "source_key": "tau_photon_grenades",
                "tag": "stratagem:tau_photon_grenades",
            }
        )
        attacker_sr["charge_roll_modifiers"] = modifiers
        attacker_sr["tau_photon_grenades_source"] = source_name
        attacker_sr["tau_photon_grenades_turn"] = current_turn
        attacker_sr["tau_photon_grenades_turn_owner"] = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        attacker_root.special_rules = attacker_sr
        self._tau_apply_pending_charge_roll_modifier(attacker_root, value=-2, source=source_name)

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PHOTON GRENADES: %s takes a Battle-shock test and suffers -2 to Charge rolls this phase.",
            getattr(attacker_root, "name", "Unit"),
        )
        return True

    def _use_tau_aggressive_mobility(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: AGGRESSIVE MOBILITY: no target unit provided")
            return False

        root = self._tau_root(target_unit)
        if root is None:
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: AGGRESSIVE MOBILITY: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tau_empire_unit(root):
            logger.error("ERROR: AGGRESSIVE MOBILITY: target must be a T'AU EMPIRE unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "movement phase":
            logger.error("ERROR: AGGRESSIVE MOBILITY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: AGGRESSIVE MOBILITY: not your turn")
            return False

        eligible = candidates or self._tau_aggressive_mobility_candidates()
        if eligible and not self._tau_unit_in_candidates(root, eligible):
            logger.error("ERROR: AGGRESSIVE MOBILITY: target is not currently eligible")
            return False
        if self._tau_selected_to_move_this_phase(root):
            logger.error("ERROR: AGGRESSIVE MOBILITY: target has already been selected to move this phase")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: AGGRESSIVE MOBILITY: cannot be used in current state")
            return False
        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "AGGRESSIVE MOBILITY")
        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        effect_tag = "stratagem:tau_aggressive_mobility"
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
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
        sr["tau_aggressive_mobility_active"] = True
        sr["tau_aggressive_mobility_expires_phase"] = "MOVEMENT_PHASE"
        sr["tau_aggressive_mobility_turn_owner"] = owner_id
        sr["tau_aggressive_mobility_turn"] = int(current_turn)
        sr["tau_aggressive_mobility_source"] = source_name
        root.special_rules = sr

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: AGGRESSIVE MOBILITY: %s adds 6\" to Move when it Advances this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tau_combat_debarkation(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: COMBAT DEBARKATION: no target unit provided")
            return False

        root = self._tau_root(target_unit)
        if root is None:
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: COMBAT DEBARKATION: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tau_empire_unit(root):
            logger.error("ERROR: COMBAT DEBARKATION: target must be a T'AU EMPIRE unit")
            return False
        if not self._tau_has_any_keyword(root, "INFANTRY"):
            logger.error("ERROR: COMBAT DEBARKATION: target must be T'AU EMPIRE INFANTRY")
            return False
        if not self._tau_has_disembarked_this_round(root):
            logger.error("ERROR: COMBAT DEBARKATION: target must have disembarked this turn")
            return False
        transport = self._tau_resolve_friendly_transport_for_disembarked_unit(root)
        if transport is None or not self._tau_has_any_keyword(transport, "TRANSPORT"):
            logger.error("ERROR: COMBAT DEBARKATION: target must have disembarked from a friendly TRANSPORT this turn")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: COMBAT DEBARKATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: COMBAT DEBARKATION: not your Shooting phase")
            return False

        eligible = candidates or self._tau_combat_debarkation_candidates()
        if eligible and not self._tau_unit_in_candidates(root, eligible):
            logger.error("ERROR: COMBAT DEBARKATION: target is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: COMBAT DEBARKATION: cannot be used in current state")
            return False
        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False

        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        source_name = str(getattr(stratagem, "name", "") or "COMBAT DEBARKATION")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tau_combat_debarkation_active"] = True
        sr["tau_combat_debarkation_expires_phase"] = "SHOOTING_PHASE"
        sr["tau_combat_debarkation_turn_owner"] = owner_id
        sr["tau_combat_debarkation_turn"] = int(current_turn)
        sr["tau_combat_debarkation_source"] = source_name
        root.special_rules = sr

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: COMBAT DEBARKATION: %s can re-roll Wound rolls when targeting the closest eligible enemy unit this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tau_focused_fire(self, stratagem: Any, **kwargs) -> bool:
        selected_units = (
            kwargs.get("units")
            or kwargs.get("selected_units")
            or kwargs.get("target_units")
            or kwargs.get("unit")
            or kwargs.get("target_unit")
        )
        enemy_unit = (
            kwargs.get("enemy_unit")
            or kwargs.get("attacking_unit")
            or kwargs.get("attacker_unit")
            or kwargs.get("enemy_target")
            or kwargs.get("target_enemy_unit")
        )
        friendly_candidates = list(kwargs.get("friendly_candidates") or [])
        enemy_candidates = list(kwargs.get("enemy_candidates") or [])
        if not friendly_candidates or not enemy_candidates or selected_units is None or enemy_unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if selected_units is None:
                    selected_units = (
                        reaction.get("selected_units")
                        or reaction.get("units")
                        or reaction.get("target_units")
                    )
                if enemy_unit is None:
                    enemy_unit = reaction.get("enemy_unit") or reaction.get("target_unit")
                if not friendly_candidates:
                    friendly_candidates = list(reaction.get("friendly_candidates") or [])
                if not enemy_candidates:
                    enemy_candidates = list(reaction.get("enemy_candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break

        selected_roots = self._tau_resolve_unit_list(selected_units)
        if not selected_roots:
            logger.error("ERROR: FOCUSED FIRE: no friendly target units provided")
            return False
        if len(selected_roots) != 2:
            logger.error("ERROR: FOCUSED FIRE: must select exactly two friendly T'AU EMPIRE units")
            return False
        enemy_root = self._tau_root(enemy_unit)
        if enemy_root is None:
            if len(enemy_candidates) == 1:
                enemy_root = self._tau_root(enemy_candidates[0])
            else:
                logger.error("ERROR: FOCUSED FIRE: no enemy target unit provided")
                return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: FOCUSED FIRE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: FOCUSED FIRE: not your Shooting phase")
            return False
        if self._tau_current_battle_round() >= 4:
            logger.error("ERROR: FOCUSED FIRE: cannot be used in battle rounds 4 or 5")
            return False

        eligible_friendly = friendly_candidates or self._tau_focused_fire_friendly_candidates()
        if len(eligible_friendly) < 2:
            logger.error("ERROR: FOCUSED FIRE: requires two eligible friendly units that have not been selected to shoot")
            return False
        for root in list(selected_roots):
            if not self._tau_unit_in_candidates(root, eligible_friendly):
                logger.error("ERROR: FOCUSED FIRE: one or more selected friendly units are not eligible")
                return False
            if not self._tau_owned_by_player(root, self.player):
                logger.error("ERROR: FOCUSED FIRE: selected friendly unit is not yours")
                return False
            if not self._is_tau_empire_unit(root):
                logger.error("ERROR: FOCUSED FIRE: selected friendly units must be T'AU EMPIRE")
                return False
            if self._tau_has_shot_this_phase(root):
                logger.error("ERROR: FOCUSED FIRE: selected friendly units must not have been selected to shoot")
                return False

        if self._tau_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: FOCUSED FIRE: enemy target is invalid")
            return False
        eligible_enemy = enemy_candidates or self._tau_focused_fire_enemy_candidates()
        if eligible_enemy and not self._tau_unit_in_candidates(enemy_root, eligible_enemy):
            logger.error("ERROR: FOCUSED FIRE: enemy target is not currently eligible")
            return False
        if not self._tau_on_battlefield(enemy_root, require_targetable=True):
            return False

        first = selected_roots[0]
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=first,
            target_unit=enemy_root,
            phase_name="Shooting phase",
        ):
            logger.error("ERROR: FOCUSED FIRE: cannot be used in current state")
            return False
        if not self._tau_spend_cp(stratagem, target_unit=first):
            return False

        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        enemy_id = self._tau_sort_key(enemy_root)
        source_name = str(getattr(stratagem, "name", "") or "FOCUSED FIRE")
        for root in list(selected_roots):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["tau_focused_fire_active"] = True
            sr["tau_focused_fire_target_id"] = enemy_id
            sr["tau_focused_fire_ap_bonus"] = 1
            sr["tau_focused_fire_expires_phase"] = "SHOOTING_PHASE"
            sr["tau_focused_fire_turn_owner"] = owner_id
            sr["tau_focused_fire_turn"] = int(current_turn)
            sr["tau_focused_fire_source"] = source_name
            root.special_rules = sr

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: FOCUSED FIRE: %s and %s can only target %s this phase and improve AP by 1 when doing so.",
            getattr(selected_roots[0], "name", "Unit 1"),
            getattr(selected_roots[1], "name", "Unit 2"),
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_tau_counterfire_defence_systems(self, stratagem: Any, **kwargs) -> bool:
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
            logger.error("ERROR: COUNTERFIRE DEFENCE SYSTEMS: no target unit provided")
            return False

        root = self._tau_root(target_unit)
        if root is None:
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: COUNTERFIRE DEFENCE SYSTEMS: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tau_empire_unit(root):
            logger.error("ERROR: COUNTERFIRE DEFENCE SYSTEMS: target must be a T'AU EMPIRE unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: COUNTERFIRE DEFENCE SYSTEMS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: COUNTERFIRE DEFENCE SYSTEMS: not opponent's Shooting phase")
            return False

        attacker_root = self._tau_root(attacking_unit)
        if attacker_root is None:
            logger.error("ERROR: COUNTERFIRE DEFENCE SYSTEMS: missing attacking unit context")
            return False
        if self._tau_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: COUNTERFIRE DEFENCE SYSTEMS: attacker is not an enemy unit")
            return False

        eligible = candidates or self._tau_counterfire_defence_systems_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not eligible or not self._tau_unit_in_candidates(root, eligible):
            logger.error("ERROR: COUNTERFIRE DEFENCE SYSTEMS: target must be one of the attacking unit's selected targets")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=root,
            phase_name="Shooting phase",
            attacking_unit=attacker_root,
            target_units=list(target_units or []),
        ):
            logger.error("ERROR: COUNTERFIRE DEFENCE SYSTEMS: cannot be used in current state")
            return False
        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False

        entry = {
            "value": 1,
            "attack_type": "any",
            "expires_phase": "SHOOTING_PHASE",
            "source": str(getattr(stratagem, "name", "") or "COUNTERFIRE DEFENCE SYSTEMS"),
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

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: COUNTERFIRE DEFENCE SYSTEMS: %s reduces incoming Damage by 1 this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tau_pinpoint_counter_offensive(self, stratagem: Any, **kwargs) -> bool:
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
                    enemy_unit = reaction.get("enemy_unit") or reaction.get("attacking_unit") or reaction.get("attacker_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: PINPOINT COUNTER-OFFENSIVE: no target unit provided")
            return False
        if enemy_unit is None:
            logger.error("ERROR: PINPOINT COUNTER-OFFENSIVE: missing enemy unit context")
            return False

        root = self._tau_root(target_unit)
        enemy_root = self._tau_root(enemy_unit)
        if root is None or enemy_root is None:
            return False
        if not self._is_tau_montka_detachment():
            return False
        if candidates and not self._tau_unit_in_candidates(root, candidates):
            logger.error("ERROR: PINPOINT COUNTER-OFFENSIVE: target was not selected")
            return False
        if not self._tau_pinpoint_counter_offensive_target_eligible(root):
            logger.error(
                "ERROR: PINPOINT COUNTER-OFFENSIVE: target must be your destroyed non-KROOT T'AU EMPIRE unit"
            )
            return False
        if self._tau_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: PINPOINT COUNTER-OFFENSIVE: enemy context is invalid")
            return False

        enemy_id = self._tau_sort_key(enemy_root)
        if not enemy_id:
            return False
        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False
        if not isinstance(getattr(self, "_tau_montka_pinpoint_counter_offensive_enemy_ids", None), set):
            self._tau_montka_pinpoint_counter_offensive_enemy_ids = set()
        self._tau_montka_pinpoint_counter_offensive_enemy_ids.add(enemy_id)
        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PINPOINT COUNTER-OFFENSIVE: non-KROOT T'AU EMPIRE units can re-roll Hit rolls against %s for the battle.",
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_tau_pulse_onslaught(self, stratagem: Any, **kwargs) -> bool:
        friendly_unit = (
            kwargs.get("unit")
            or kwargs.get("friendly_unit")
            or kwargs.get("attacker_unit")
            or kwargs.get("attacking_unit")
        )
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or kwargs.get("enemy_candidates") or [])
        hits_by_target = kwargs.get("hits_by_target")
        if friendly_unit is None or enemy_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if friendly_unit is None:
                    friendly_unit = reaction.get("friendly_unit") or reaction.get("unit") or reaction.get("attacker_unit")
                if enemy_unit is None:
                    enemy_unit = reaction.get("enemy_unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("enemy_candidates") or reaction.get("candidates") or [])
                if hits_by_target is None:
                    hits_by_target = reaction.get("hits_by_target")
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if enemy_unit is None and len(candidates) == 1:
            enemy_unit = candidates[0]
        if friendly_unit is None:
            logger.error("ERROR: PULSE ONSLAUGHT: no friendly unit provided")
            return False
        if enemy_unit is None:
            logger.error("ERROR: PULSE ONSLAUGHT: no enemy unit provided")
            return False

        friendly_root = self._tau_root(friendly_unit)
        enemy_root = self._tau_root(enemy_unit)
        if friendly_root is None or enemy_root is None:
            return False
        if not self._tau_owned_by_player(friendly_root, self.player):
            logger.error("ERROR: PULSE ONSLAUGHT: friendly unit must be yours")
            return False
        if not self._tau_on_battlefield(friendly_root, require_targetable=True):
            return False
        if not self._is_tau_empire_unit(friendly_root):
            logger.error("ERROR: PULSE ONSLAUGHT: friendly unit must be T'AU EMPIRE")
            return False
        if self._is_tau_kroot_unit(friendly_root):
            logger.error("ERROR: PULSE ONSLAUGHT: friendly unit cannot be KROOT")
            return False
        if not self._tau_has_any_keyword(friendly_root, "INFANTRY"):
            logger.error("ERROR: PULSE ONSLAUGHT: friendly unit must be INFANTRY")
            return False
        if not self._tau_has_shot_this_phase(friendly_root):
            logger.error("ERROR: PULSE ONSLAUGHT: friendly unit must have just shot")
            return False
        if self._tau_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: PULSE ONSLAUGHT: enemy context is invalid")
            return False
        if not self._tau_on_battlefield(enemy_root, require_targetable=True):
            return False
        if self._tau_unit_is_monster_or_vehicle(enemy_root):
            logger.error("ERROR: PULSE ONSLAUGHT: enemy unit cannot be MONSTER or VEHICLE")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: PULSE ONSLAUGHT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: PULSE ONSLAUGHT: not your Shooting phase")
            return False

        eligible_enemy = candidates or self._tau_pulse_onslaught_enemy_candidates(
            attacker_unit=friendly_root,
            hits_by_target=hits_by_target,
        )
        if eligible_enemy and not self._tau_unit_in_candidates(enemy_root, eligible_enemy):
            logger.error("ERROR: PULSE ONSLAUGHT: enemy unit was not hit by that unit's attacks or is not eligible")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=friendly_root,
            target_unit=enemy_root,
            phase_name="Shooting phase",
        ):
            logger.error("ERROR: PULSE ONSLAUGHT: cannot be used in current state")
            return False
        if not self._tau_spend_cp(stratagem, target_unit=friendly_root):
            return False

        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        source_name = str(getattr(stratagem, "name", "") or "PULSE ONSLAUGHT")
        apply_aflame = getattr(enemy_root, "apply_aflame", None)
        if callable(apply_aflame):
            apply_aflame(
                owner_id=owner_id,
                turn=turn,
                source=source_name,
                move_penalty=-2,
                advance_penalty=-2,
                charge_penalty=-2,
            )
        else:
            sr = getattr(enemy_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["aflame_active"] = True
            sr["aflame_owner"] = owner_id
            sr["aflame_turn"] = int(turn)
            sr["aflame_source"] = source_name
            sr["aflame_move_penalty"] = -2
            sr["aflame_advance_penalty"] = -2
            sr["aflame_charge_penalty"] = -2
            enemy_root.special_rules = sr

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PULSE ONSLAUGHT: %s is shaken (-2 Move, -2 Advance, -2 Charge) until end of opponent's next turn.",
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_tau_reactive_impact_dampeners(self, stratagem: Any, **kwargs) -> bool:
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
            logger.error("ERROR: REACTIVE IMPACT DAMPENERS: no target unit provided")
            return False

        root = self._tau_root(target_unit)
        if root is None:
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: REACTIVE IMPACT DAMPENERS: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tau_battlesuit_unit(root):
            logger.error("ERROR: REACTIVE IMPACT DAMPENERS: target must be a T'AU EMPIRE BATTLESUIT unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: REACTIVE IMPACT DAMPENERS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is self.player:
            logger.error("ERROR: REACTIVE IMPACT DAMPENERS: not opponent's Shooting phase")
            return False

        attacker_root = self._tau_root(attacking_unit)
        if attacker_root is None:
            logger.error("ERROR: REACTIVE IMPACT DAMPENERS: missing attacking unit context")
            return False
        if self._tau_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: REACTIVE IMPACT DAMPENERS: attacker is not an enemy unit")
            return False

        eligible = candidates or self._tau_reactive_impact_dampeners_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not eligible or not self._tau_unit_in_candidates(root, eligible):
            logger.error(
                "ERROR: REACTIVE IMPACT DAMPENERS: target must be one of the attacking unit's selected targets"
            )
            return False
        phase_label = "Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name=phase_label):
            logger.error("ERROR: REACTIVE IMPACT DAMPENERS: cannot be used in current state")
            return False
        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False

        phase_key_fn = getattr(self, "_phase_key_from_name", None)
        phase_key = phase_key_fn(phase_name) if callable(phase_key_fn) else ""
        if not phase_key:
            phase_key = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        entry = {
            "value": 1,
            "attack_type": "any",
            "expires_phase": str(phase_key),
            "source": str(getattr(stratagem, "name", "") or "REACTIVE IMPACT DAMPENERS"),
            "requires_strength_gt_toughness": True,
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

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: REACTIVE IMPACT DAMPENERS: %s gains conditional -1 to wound this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tau_neuroweb_system_jammer(self, stratagem: Any, **kwargs) -> bool:
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
            logger.error("ERROR: NEUROWEB SYSTEM JAMMER: no target unit provided")
            return False

        root = self._tau_root(target_unit)
        if root is None:
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: NEUROWEB SYSTEM JAMMER: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tau_crisis_unit(root):
            logger.error("ERROR: NEUROWEB SYSTEM JAMMER: target must be a T'AU EMPIRE CRISIS unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: NEUROWEB SYSTEM JAMMER: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: NEUROWEB SYSTEM JAMMER: not opponent's Shooting phase")
            return False

        attacker_root = self._tau_root(attacking_unit)
        if attacker_root is None:
            logger.error("ERROR: NEUROWEB SYSTEM JAMMER: missing attacking unit context")
            return False
        if self._tau_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: NEUROWEB SYSTEM JAMMER: attacker is not an enemy unit")
            return False

        eligible = candidates or self._tau_neuroweb_system_jammer_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not eligible or not self._tau_unit_in_candidates(root, eligible):
            logger.error("ERROR: NEUROWEB SYSTEM JAMMER: target must be one of the attacking unit's selected targets")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: NEUROWEB SYSTEM JAMMER: cannot be used in current state")
            return False
        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False

        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        source_name = str(getattr(stratagem, "name", "") or "NEUROWEB SYSTEM JAMMER")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tau_neuroweb_system_jammer_active"] = True
        sr["tau_neuroweb_system_jammer_targeting_range"] = 18
        sr["tau_neuroweb_system_jammer_expires_phase"] = "SHOOTING_PHASE"
        sr["tau_neuroweb_system_jammer_turn_owner"] = owner_id
        sr["tau_neuroweb_system_jammer_turn"] = int(current_turn)
        sr["tau_neuroweb_system_jammer_source"] = source_name
        root.special_rules = sr

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: NEUROWEB SYSTEM JAMMER: %s can only be targeted by ranged attacks from within 18\" until end of phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tau_experimental_weaponry(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: EXPERIMENTAL WEAPONRY: no target unit provided")
            return False

        root = self._tau_root(target_unit)
        if root is None:
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: EXPERIMENTAL WEAPONRY: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tau_empire_unit(root):
            logger.error("ERROR: EXPERIMENTAL WEAPONRY: target must be a T'AU EMPIRE unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: EXPERIMENTAL WEAPONRY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: EXPERIMENTAL WEAPONRY: not your Shooting phase")
            return False

        eligible = candidates or self._tau_experimental_weaponry_candidates()
        if eligible and not self._tau_unit_in_candidates(root, eligible):
            logger.error("ERROR: EXPERIMENTAL WEAPONRY: target is not currently eligible")
            return False
        if self._tau_has_shot_this_phase(root):
            logger.error("ERROR: EXPERIMENTAL WEAPONRY: target has already been selected to shoot")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: EXPERIMENTAL WEAPONRY: cannot be used in current state")
            return False
        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False

        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        source_name = str(getattr(stratagem, "name", "") or "EXPERIMENTAL WEAPONRY")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tau_experimental_weaponry_active"] = True
        sr["tau_experimental_weaponry_expires_phase"] = "SHOOTING_PHASE"
        sr["tau_experimental_weaponry_turn_owner"] = owner_id
        sr["tau_experimental_weaponry_turn"] = int(current_turn)
        sr["tau_experimental_weaponry_source"] = source_name
        root.special_rules = sr

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: EXPERIMENTAL WEAPONRY: %s can re-roll attack-count dice for ranged weapons this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tau_experimental_ammunition(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: EXPERIMENTAL AMMUNITION: no target unit provided")
            return False

        root = self._tau_root(target_unit)
        if root is None:
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: EXPERIMENTAL AMMUNITION: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tau_empire_unit(root):
            logger.error("ERROR: EXPERIMENTAL AMMUNITION: target must be a T'AU EMPIRE unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: EXPERIMENTAL AMMUNITION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: EXPERIMENTAL AMMUNITION: not your Shooting phase")
            return False

        eligible = candidates or self._tau_experimental_ammunition_candidates()
        if eligible and not self._tau_unit_in_candidates(root, eligible):
            logger.error("ERROR: EXPERIMENTAL AMMUNITION: target is not currently eligible")
            return False
        if self._tau_has_shot_this_phase(root):
            logger.error("ERROR: EXPERIMENTAL AMMUNITION: target has already been selected to shoot")
            return False
        if self._tau_threat_assessment_analyser_active(root):
            logger.error(
                "ERROR: EXPERIMENTAL AMMUNITION: target unit cannot also be targeted by THREAT ASSESSMENT ANALYSER in this phase"
            )
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: EXPERIMENTAL AMMUNITION: cannot be used in current state")
            return False

        mode = self._tau_parse_experimental_ammunition_mode(
            kwargs.get("mode")
            or kwargs.get("experimental_ammunition_mode")
            or kwargs.get("choice")
            or kwargs.get("selection")
            or kwargs.get("effect")
        )
        if mode is None:
            logger.error("ERROR: EXPERIMENTAL AMMUNITION: invalid mode selection")
            return False

        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False

        hazardous = mode == "hazardous"
        ap_bonus = 1 if hazardous else 0
        source_name = str(getattr(stratagem, "name", "") or "EXPERIMENTAL AMMUNITION")
        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tau_experimental_ammunition_active"] = True
        sr["tau_experimental_ammunition_strength_bonus"] = 1
        sr["tau_experimental_ammunition_ap_bonus"] = int(ap_bonus)
        sr["tau_experimental_ammunition_ranged_hazardous"] = bool(hazardous)
        sr["tau_experimental_ammunition_expires_phase"] = "SHOOTING_PHASE"
        sr["tau_experimental_ammunition_turn_owner"] = owner_id
        sr["tau_experimental_ammunition_turn"] = int(current_turn)
        sr["tau_experimental_ammunition_source"] = source_name
        # Marker used for same-phase incompatibility checks versus THREAT ASSESSMENT ANALYSER.
        sr["tau_experimental_ammunition_phase_active"] = True
        sr["tau_experimental_ammunition_phase_owner"] = owner_id
        sr["tau_experimental_ammunition_phase_turn"] = int(current_turn)
        sr["tau_experimental_ammunition_phase"] = "SHOOTING_PHASE"
        root.special_rules = sr

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        if hazardous:
            logger.info(
                "INFO: EXPERIMENTAL AMMUNITION: %s gains +1 Strength, +1 AP, and [HAZARDOUS] on ranged weapons this phase.",
                getattr(root, "name", "Unit"),
            )
        else:
            logger.info(
                "INFO: EXPERIMENTAL AMMUNITION: %s gains +1 Strength on ranged weapons this phase.",
                getattr(root, "name", "Unit"),
            )
        return True

    def _use_tau_threat_assessment_analyser(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: THREAT ASSESSMENT ANALYSER: no target unit provided")
            return False

        root = self._tau_root(target_unit)
        if root is None:
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: THREAT ASSESSMENT ANALYSER: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tau_empire_unit(root):
            logger.error("ERROR: THREAT ASSESSMENT ANALYSER: target must be a T'AU EMPIRE unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: THREAT ASSESSMENT ANALYSER: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: THREAT ASSESSMENT ANALYSER: not your Shooting phase")
            return False

        eligible = candidates or self._tau_threat_assessment_analyser_candidates()
        if eligible and not self._tau_unit_in_candidates(root, eligible):
            logger.error("ERROR: THREAT ASSESSMENT ANALYSER: target is not currently eligible")
            return False
        if self._tau_has_shot_this_phase(root):
            logger.error("ERROR: THREAT ASSESSMENT ANALYSER: target has already been selected to shoot")
            return False
        if self._tau_experimental_ammunition_phase_active(root):
            logger.error(
                "ERROR: THREAT ASSESSMENT ANALYSER: target unit cannot also be targeted by EXPERIMENTAL AMMUNITION in this phase"
            )
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: THREAT ASSESSMENT ANALYSER: cannot be used in current state")
            return False

        mode = self._tau_parse_threat_assessment_analyser_mode(
            kwargs.get("mode")
            or kwargs.get("threat_assessment_mode")
            or kwargs.get("choice")
            or kwargs.get("selection")
            or kwargs.get("effect")
        )
        if mode is None:
            logger.error("ERROR: THREAT ASSESSMENT ANALYSER: invalid mode selection")
            return False
        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False

        grant_lethal = mode in {"lethal", "all"}
        grant_sustained = mode in {"sustained", "all"}
        grant_hazardous = mode == "all"
        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        source_name = str(getattr(stratagem, "name", "") or "THREAT ASSESSMENT ANALYSER")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tau_threat_assessment_analyser_active"] = True
        sr["tau_threat_assessment_analyser_lethal_hits"] = bool(grant_lethal)
        sr["tau_threat_assessment_analyser_sustained_hits"] = bool(grant_sustained)
        sr["tau_threat_assessment_analyser_sustained_hits_value"] = 1 if grant_sustained else 0
        sr["tau_threat_assessment_analyser_ranged_hazardous"] = bool(grant_hazardous)
        sr["tau_threat_assessment_analyser_mode"] = mode
        sr["tau_threat_assessment_analyser_expires_phase"] = "SHOOTING_PHASE"
        sr["tau_threat_assessment_analyser_turn_owner"] = owner_id
        sr["tau_threat_assessment_analyser_turn"] = int(current_turn)
        sr["tau_threat_assessment_analyser_source"] = source_name
        # Alias keys retained for compatibility with broader stratagem checks.
        sr["threat_assessment_analyser_active"] = True
        sr["threat_assessment_analyser_owner"] = owner_id
        sr["threat_assessment_analyser_turn"] = int(current_turn)
        sr["threat_assessment_analyser_expires_phase"] = "SHOOTING_PHASE"
        root.special_rules = sr

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        if mode == "all":
            logger.info(
                "INFO: THREAT ASSESSMENT ANALYSER: %s gains [SUSTAINED HITS 1], [LETHAL HITS], and [HAZARDOUS] on ranged weapons this phase.",
                getattr(root, "name", "Unit"),
            )
        elif mode == "lethal":
            logger.info(
                "INFO: THREAT ASSESSMENT ANALYSER: %s gains [LETHAL HITS] on ranged weapons this phase.",
                getattr(root, "name", "Unit"),
            )
        else:
            logger.info(
                "INFO: THREAT ASSESSMENT ANALYSER: %s gains [SUSTAINED HITS 1] on ranged weapons this phase.",
                getattr(root, "name", "Unit"),
            )
        return True

    def _use_tau_automated_repair_drones(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: AUTOMATED REPAIR DRONES: no target unit provided")
            return False

        root = self._tau_root(target_unit)
        if root is None:
            return False
        if candidates and not self._tau_unit_in_candidates(root, candidates):
            logger.error("ERROR: AUTOMATED REPAIR DRONES: target is not currently eligible")
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: AUTOMATED REPAIR DRONES: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tau_battlesuit_unit(root):
            logger.error("ERROR: AUTOMATED REPAIR DRONES: target must be a T'AU EMPIRE BATTLESUIT unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "command phase":
            logger.error("ERROR: AUTOMATED REPAIR DRONES: wrong phase")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Command phase"):
            logger.error("ERROR: AUTOMATED REPAIR DRONES: cannot be used in current state")
            return False

        wounded_models = self._tau_wounded_battlesuit_models(root)
        if not wounded_models:
            logger.error("ERROR: AUTOMATED REPAIR DRONES: no wounded BATTLESUIT model in target unit")
            return False

        model_selection = kwargs.get("model") or kwargs.get("target_model")
        heal_model = self._tau_resolve_selected_model(model_selection, self._tau_unit_models(root))
        if heal_model is None:
            heal_model = wounded_models[0]
        if not self._tau_model_is_battlesuit(heal_model, parent_unit=root):
            logger.error("ERROR: AUTOMATED REPAIR DRONES: selected model must have BATTLESUIT keyword")
            return False
        missing = self._tau_model_missing_wounds(heal_model)
        if missing <= 0:
            logger.error("ERROR: AUTOMATED REPAIR DRONES: selected model has no lost wounds")
            return False

        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False

        heal_roll = max(0, int(dice_module.get_roll("D3") or 0))
        heal_amount = int(heal_roll + 1)
        healed = min(int(heal_amount), int(missing))

        heal_fn = getattr(heal_model, "heal", None)
        if callable(heal_fn):
            heal_fn(int(heal_amount))
        else:
            base_wounds = int(getattr(heal_model, "_base_wounds", getattr(heal_model, "base_wounds", 0)) or 0)
            current_wounds = int(getattr(heal_model, "wounds", 0) or 0)
            heal_model.wounds = min(base_wounds, current_wounds + int(heal_amount))

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: AUTOMATED REPAIR DRONES: %s healed %d wound(s).",
            getattr(root, "name", "Unit"),
            int(healed),
        )
        return True
