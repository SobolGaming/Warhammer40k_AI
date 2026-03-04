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
    def _tau_selected_to_move_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(
            getattr(round_state, "moved_this_round", False)
            or getattr(round_state, "advanced_this_round", False)
            or getattr(round_state, "fell_back_this_round", False)
        )

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
        if name_u == "INTERLOCKING MANOUEVRES":
            return self._use_tau_interlocking_manoeuvres(stratagem, **kwargs)
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
        if name_u == "WALL OF MIRRORS":
            return self._use_tau_wall_of_mirrors(stratagem, **kwargs)
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
