from __future__ import annotations

import logging
from typing import Any, Optional

from ..utility.aura_utils import horizontal_distance_between_bases_2d, unit_wholly_within_range_of_unit
from ..utility import dice as dice_module
from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class EmperorsChildrenStratagemMixin:
    @staticmethod
    def _ec_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _ec_sort_key(unit: Any) -> str:
        return str(get_entity_id(unit) or "")

    @staticmethod
    def _ec_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(unit, "is_alive", True))

    @staticmethod
    def _ec_is_on_battlefield(unit: Any) -> bool:
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
    def _ec_owned_by_player(unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(parent_army, "player", None) is player

    @staticmethod
    def _ec_has_keyword(entity: Any, keyword: str) -> bool:
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

    def _get_emperors_children_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        mgr = getattr(army, "emperors_children", None)
        if mgr is not None:
            return mgr
        return getattr(army, "emperors_children_detachments", None)

    def _is_court_of_the_phoenician_detachment(self) -> bool:
        mgr = self._get_emperors_children_mgr()
        checker = getattr(mgr, "is_court_of_the_phoenician", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_coterie_of_the_conceited_detachment(self) -> bool:
        mgr = self._get_emperors_children_mgr()
        checker = getattr(mgr, "is_coterie_of_conceited", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_mercurial_host_detachment(self) -> bool:
        mgr = self._get_emperors_children_mgr()
        checker = getattr(mgr, "is_mercurial_host", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_slaaneshs_chosen_detachment(self) -> bool:
        mgr = self._get_emperors_children_mgr()
        checker = getattr(mgr, "is_slaaneshs_chosen", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_rapid_evisceration_detachment(self) -> bool:
        mgr = self._get_emperors_children_mgr()
        checker = getattr(mgr, "is_rapid_evisceration", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_carnival_of_excess_detachment(self) -> bool:
        mgr = self._get_emperors_children_mgr()
        checker = getattr(mgr, "is_carnival_of_excess", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_emperors_children_unit(self, unit: Any) -> bool:
        root = self._ec_root(unit)
        if root is None:
            return False
        mgr = self._get_emperors_children_mgr()
        checker = getattr(mgr, "is_emperors_children_unit", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        return self._ec_has_keyword(root, "EMPEROR'S CHILDREN")

    def _is_legions_of_excess_unit(self, unit: Any) -> bool:
        root = self._ec_root(unit)
        if root is None:
            return False
        mgr = self._get_emperors_children_mgr()
        checker = getattr(mgr, "is_legions_of_excess_unit", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        return self._ec_has_keyword(root, "LEGIONS OF EXCESS")

    def _is_slaanesh_unit(self, unit: Any) -> bool:
        root = self._ec_root(unit)
        if root is None:
            return False
        return self._ec_has_keyword(root, "SLAANESH")

    def _is_emperors_children_daemon_unit(self, unit: Any) -> bool:
        root = self._ec_root(unit)
        if root is None:
            return False
        if not self._is_emperors_children_unit(root):
            return False
        return self._ec_has_keyword(root, "DAEMON")

    def _is_emperors_children_infantry_unit(self, unit: Any) -> bool:
        root = self._ec_root(unit)
        if root is None:
            return False
        return self._is_emperors_children_unit(root) and self._ec_has_keyword(root, "INFANTRY")

    def _ec_targetable_units(
        self,
        *,
        detachment: str = "court",
        require_daemon: bool = False,
        require_infantry: bool = False,
        require_not_beast_vehicle: bool = False,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
    ) -> list[Any]:
        det = str(detachment or "court").strip().lower()
        if det == "court":
            if not self._is_court_of_the_phoenician_detachment():
                return []
        elif det == "coterie":
            if not self._is_coterie_of_the_conceited_detachment():
                return []
        elif det == "mercurial":
            if not self._is_mercurial_host_detachment():
                return []
        elif det == "slaanesh":
            if not self._is_slaaneshs_chosen_detachment():
                return []
        elif det == "carnival":
            if not self._is_carnival_of_excess_detachment():
                return []
        else:
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ec_root(unit)
            if root is None:
                continue
            uid = self._ec_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ec_owned_by_player(root, self.player):
                continue
            if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_emperors_children_unit(root):
                continue
            if require_daemon and not self._is_emperors_children_daemon_unit(root):
                continue
            if require_infantry and not self._is_emperors_children_infantry_unit(root):
                continue
            if require_not_beast_vehicle and (
                self._ec_has_keyword(root, "BEAST")
                or self._ec_has_keyword(root, "BEASTS")
                or self._ec_has_keyword(root, "VEHICLE")
            ):
                continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._ec_sort_key)

    def _ec_friendly_battlefield_units(self) -> list[Any]:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ec_root(unit)
            if root is None:
                continue
            uid = self._ec_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ec_owned_by_player(root, self.player):
                continue
            if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
                continue
            out.append(root)
        return sorted(out, key=self._ec_sort_key)

    def _ec_is_within_engagement_range_of_enemy(self, unit: Any) -> bool:
        root = self._ec_root(unit)
        if root is None or self.game is None:
            return False
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return False
        enemies = getattr(game_map, "get_enemy_units", None)
        if not callable(enemies):
            return False
        for enemy in list(enemies(root) or []):
            enemy_root = self._ec_root(enemy)
            if enemy_root is None:
                continue
            if not self._ec_is_alive(enemy_root) or not self._ec_is_on_battlefield(enemy_root):
                continue
            try:
                if bool(game_map.is_within_engagement_range(root, enemy_root)):
                    return True
            except (AttributeError, TypeError, ValueError):
                continue
        return False

    @staticmethod
    def _ec_model_missing_wounds(model: Any) -> int:
        if model is None:
            return 0
        base_wounds = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)) or 0)
        current_wounds = int(getattr(model, "wounds", 0) or 0)
        return max(0, int(base_wounds - current_wounds))

    def _ec_wounded_models(self, unit: Any) -> list[Any]:
        root = self._ec_root(unit)
        if root is None:
            return []
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else []
        if not models:
            models = list(getattr(root, "models", []) or [])

        out: list[Any] = []
        for model in list(models or []):
            if model is None:
                continue
            alive_attr = getattr(model, "is_alive", True)
            is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if not is_alive:
                continue
            if self._ec_model_missing_wounds(model) <= 0:
                continue
            out.append(model)
        return sorted(out, key=lambda m: str(get_entity_id(m) or ""))

    def _ec_destroyed_non_character_models(self, unit: Any) -> list[Any]:
        root = self._ec_root(unit)
        if root is None:
            return []
        destroyed = list(getattr(root, "models_lost", []) or [])
        out: list[Any] = []
        for model in list(destroyed or []):
            if model is None:
                continue
            is_character = getattr(model, "is_character", None)
            if bool(is_character() if callable(is_character) else is_character):
                continue
            out.append(model)
        return sorted(out, key=lambda m: str(get_entity_id(m) or ""))

    def _ec_carnival_sycophantic_surge_enemy_candidates(self, unit: Any) -> list[Any]:
        root = self._ec_root(unit)
        if root is None or self.game is None:
            return []
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return []
        get_enemies = getattr(game_map, "get_enemy_units", None)
        if not callable(get_enemies):
            return []

        original_sr = dict(getattr(root, "special_rules", {}) or {})
        sr = dict(original_sr)
        sr["carnival_sycophantic_surge_active"] = True
        sr["carnival_sycophantic_surge_charge_after_advance"] = True
        sr["carnival_sycophantic_surge_charge_after_fall_back"] = True
        sr["carnival_sycophantic_surge_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["carnival_sycophantic_surge_turn"] = int(getattr(self.game, "turn", 0) or 0)
        sr["carnival_sycophantic_surge_expires_phase"] = "CHARGE_PHASE"
        root.special_rules = sr
        try:
            enemy_candidates: list[Any] = []
            seen: set[str] = set()
            for enemy in list(get_enemies(root) or []):
                enemy_root = self._ec_root(enemy)
                if enemy_root is None:
                    continue
                eid = self._ec_sort_key(enemy_root)
                if eid and eid in seen:
                    continue
                if eid:
                    seen.add(eid)
                if not self._ec_is_alive(enemy_root) or not self._ec_is_on_battlefield(enemy_root):
                    continue
                if not self._ec_enemy_within_engagement_of_friendly(enemy_root):
                    continue
                can_charge = getattr(root, "can_declare_charge_against", None)
                if not callable(can_charge):
                    continue
                try:
                    if not bool(can_charge(enemy_root, self.game, out_of_turn=False)):
                        continue
                except (AttributeError, TypeError, ValueError):
                    continue
                enemy_candidates.append(enemy_root)
            return sorted(enemy_candidates, key=self._ec_sort_key)
        finally:
            root.special_rules = original_sr

    def _ec_carnival_sycophantic_surge_tool_action_context(self) -> dict[str, Any]:
        if not self._is_carnival_of_excess_detachment():
            return {}
        candidates: list[Any] = []
        enemy_by_unit: dict[str, list[Any]] = {}
        enemy_union: list[Any] = []
        seen_enemy: set[str] = set()
        for unit in self._ec_friendly_battlefield_units():
            root = self._ec_root(unit)
            if root is None:
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_legions_of_excess_unit(root):
                continue
            enemies = self._ec_carnival_sycophantic_surge_enemy_candidates(root)
            if not enemies:
                continue
            candidates.append(root)
            uid = self._ec_sort_key(root)
            if uid:
                enemy_by_unit[uid] = list(enemies)
            for enemy in enemies:
                eid = self._ec_sort_key(enemy)
                if eid and eid in seen_enemy:
                    continue
                if eid:
                    seen_enemy.add(eid)
                enemy_union.append(enemy)
        candidates = sorted(candidates, key=self._ec_sort_key)
        if not candidates:
            return {}
        return {
            "candidates": candidates,
            "enemy_candidates_by_unit": enemy_by_unit,
            "enemy_candidates": sorted(enemy_union, key=self._ec_sort_key),
        }

    def _ec_can_use_carnival_sycophantic_surge_tool_action(self, kwargs: dict[str, Any]) -> bool:
        if not self._is_carnival_of_excess_detachment():
            return False
        phase_name = str((kwargs or {}).get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "charge phase":
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return False
        unit = (kwargs or {}).get("unit") or (kwargs or {}).get("target_unit")
        if unit is None:
            context = self._ec_carnival_sycophantic_surge_tool_action_context()
            return bool(context.get("candidates"))
        root = self._ec_resolve_unit_entry(unit)
        if root is None:
            return False
        if not self._ec_owned_by_player(root, self.player):
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            return False
        if not self._is_legions_of_excess_unit(root):
            return False
        enemy_candidates = self._ec_carnival_sycophantic_surge_enemy_candidates(root)
        if not enemy_candidates:
            return False
        selected_enemy = (kwargs or {}).get("enemy_unit") or (kwargs or {}).get("target_enemy_unit")
        if selected_enemy is None:
            return True
        selected_root = self._ec_resolve_unit_entry(selected_enemy)
        return self._ec_unit_in_candidates(selected_root, enemy_candidates)

    def _ec_carnival_violent_crescendo_candidates(self) -> list[Any]:
        if not self._is_carnival_of_excess_detachment():
            return []
        candidates: list[Any] = []
        for unit in self._ec_friendly_battlefield_units():
            root = self._ec_root(unit)
            if root is None:
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_slaanesh_unit(root):
                continue
            if not (
                self._ec_has_keyword(root, "BEAST")
                or self._ec_has_keyword(root, "BEASTS")
                or self._ec_has_keyword(root, "INFANTRY")
                or self._ec_has_keyword(root, "MOUNTED")
            ):
                continue
            if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._ec_sort_key)

    def _ec_carnival_violent_crescendo_tool_action_context(self) -> dict[str, Any]:
        candidates = self._ec_carnival_violent_crescendo_candidates()
        if not candidates:
            return {}
        return {"candidates": candidates}

    def _ec_can_use_carnival_violent_crescendo_tool_action(self, kwargs: dict[str, Any]) -> bool:
        if not self._is_carnival_of_excess_detachment():
            return False
        phase_name = str((kwargs or {}).get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            return False
        unit = (kwargs or {}).get("unit") or (kwargs or {}).get("target_unit")
        if unit is None:
            return bool(self._ec_carnival_violent_crescendo_candidates())
        root = self._ec_resolve_unit_entry(unit)
        if root is None:
            return False
        root_id = self._ec_sort_key(root)
        return any(self._ec_sort_key(candidate) == root_id for candidate in self._ec_carnival_violent_crescendo_candidates())

    @staticmethod
    def _ec_total_current_wounds(unit: Any) -> int:
        root = unit
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
        if root is None:
            return 0
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else []
        if not models:
            models = list(getattr(root, "models", []) or [])
        total = 0
        for model in models:
            if model is None:
                continue
            alive_attr = getattr(model, "is_alive", True)
            is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if not is_alive:
                continue
            total += int(getattr(model, "wounds", 0) or 0)
        return int(total)

    @staticmethod
    def _ec_unit_in_candidates(root: Any, candidates: list[Any]) -> bool:
        if root is None:
            return False
        rid = str(get_entity_id(root) or "")
        for cand in list(candidates or []):
            cid = str(get_entity_id(cand) or "")
            if rid and cid and rid == cid:
                return True
            if cand is root:
                return True
        return False

    def _ec_reaction_already_queued(
        self,
        *,
        event_name: str,
        stratagem_name: str,
        phase_name: str,
        enemy_unit: Any = None,
        target_unit: Any = None,
    ) -> bool:
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != str(event_name):
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem_name or "").strip().upper():
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() != str(phase_name or "").strip().lower():
                continue
            if enemy_unit is not None and reaction.get("enemy_unit") is not enemy_unit:
                continue
            if target_unit is not None:
                reaction_target = self._ec_root(reaction.get("target_unit") or reaction.get("unit"))
                if reaction_target is not self._ec_root(target_unit):
                    continue
            return True
        return False

    def _ec_distance_between_units(self, source_unit: Any, target_unit: Any) -> Optional[float]:
        if self.game is None:
            return None
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return None
        get_dist = getattr(game_map, "get_distance_between_units", None)
        if not callable(get_dist):
            return None
        source_root = self._ec_root(source_unit)
        target_root = self._ec_root(target_unit)
        if source_root is None or target_root is None:
            return None
        try:
            return float(get_dist(source_root, target_root))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _ec_horizontal_distance_between_units(source_unit: Any, target_unit: Any) -> Optional[float]:
        source = source_unit
        get_root = getattr(source_unit, "get_attached_unit_root", None)
        if callable(get_root):
            source = get_root()
        target = target_unit
        get_root = getattr(target_unit, "get_attached_unit_root", None)
        if callable(get_root):
            target = get_root()
        if source is None or target is None:
            return None

        get_source_models = getattr(source, "get_attached_unit_models", None)
        source_models = list(get_source_models() or []) if callable(get_source_models) else list(getattr(source, "models", []) or [])
        get_target_models = getattr(target, "get_attached_unit_models", None)
        target_models = list(get_target_models() or []) if callable(get_target_models) else list(getattr(target, "models", []) or [])
        if not source_models or not target_models:
            return None

        best: Optional[float] = None
        for src_model in source_models:
            if src_model is None or not bool(getattr(src_model, "is_alive", True)):
                continue
            src_base = getattr(src_model, "model_base", None)
            if src_base is None:
                continue
            for tgt_model in target_models:
                if tgt_model is None or not bool(getattr(tgt_model, "is_alive", True)):
                    continue
                tgt_base = getattr(tgt_model, "model_base", None)
                if tgt_base is None:
                    continue
                try:
                    dist = float(horizontal_distance_between_bases_2d(src_base, tgt_base))
                except (TypeError, ValueError):
                    continue
                if best is None or dist < best:
                    best = dist
        return best

    def _ec_has_enemy_within_horizontal_distance(self, unit: Any, max_distance: float) -> bool:
        root = self._ec_root(unit)
        if root is None or self.game is None:
            return False
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return False
        try:
            threshold = float(max_distance)
        except (TypeError, ValueError):
            return False
        if threshold < 0.0:
            return False

        seen: set[str] = set()
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._ec_root(enemy)
            if enemy_root is None:
                continue
            eid = self._ec_sort_key(enemy_root)
            if eid and eid in seen:
                continue
            if eid:
                seen.add(eid)
            if not self._ec_is_alive(enemy_root) or not self._ec_is_on_battlefield(enemy_root):
                continue
            dist = self._ec_horizontal_distance_between_units(root, enemy_root)
            if dist is not None and float(dist) <= threshold + 1e-6:
                return True
        return False

    def _ec_place_unit_into_strategic_reserves(self, unit: Any) -> bool:
        root = self._ec_root(unit)
        if root is None:
            return False
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]

        for member in members:
            if member is None:
                continue
            set_reserve_status = getattr(member, "set_reserve_status", None)
            if callable(set_reserve_status):
                set_reserve_status("strategic_reserves")
            else:
                setattr(member, "reserve_status", "strategic_reserves")
            mark_midgame = getattr(member, "mark_entered_reserves_midgame", None)
            if callable(mark_midgame):
                mark_midgame(game=self.game)
            if bool(getattr(member, "is_aircraft", False)) and not bool(getattr(member, "hover_mode", False)):
                setattr(member, "_aircraft_return_turn", int(getattr(self.game, "turn", 0) or 0) + 1 if self.game is not None else 0)
            member.deployed = True
            member.reserve_turn_deployed = None
            member.arrived_from_reserves_this_turn = False
            if game_map is not None and isinstance(getattr(game_map, "units", None), list) and member in game_map.units:
                game_map.units.remove(member)
        return True

    def _ec_catalytic_wounds_before(self) -> dict[str, dict[str, int]]:
        raw = getattr(self, "_ec_court_catalytic_wounds_before", None)
        if isinstance(raw, dict):
            return raw
        raw = {}
        self._ec_court_catalytic_wounds_before = raw
        return raw

    def _record_ec_catalytic_snapshot(self, *, attacking_unit: Any, target_units: list[Any]) -> None:
        stratagem = self.get_by_name("CATALYTIC STIMULUS")
        if stratagem is None:
            return
        atk_key = self._attacker_unit_key(attacking_unit)
        if not atk_key:
            return
        snapshots = self._ec_catalytic_wounds_before()
        by_target: dict[str, int] = {}
        for target in list(target_units or []):
            root = self._ec_root(target)
            if root is None:
                continue
            tid = self._ec_sort_key(root)
            if not tid:
                continue
            by_target[tid] = self._ec_total_current_wounds(root)
        snapshots[atk_key] = by_target

    def _resolve_unit_by_id(self, unit_id: str) -> Any:
        uid = str(unit_id or "")
        if not uid:
            return None
        resolver = getattr(self.game, "_resolve_unit_by_id", None) if self.game is not None else None
        if callable(resolver):
            resolved = resolver(uid)
            if resolved is not None:
                return resolved
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        for unit in list(getattr(game_map, "units", []) or []):
            root = self._ec_root(unit)
            if root is None:
                continue
            if str(get_entity_id(root) or "") == uid:
                return root
        return None

    @staticmethod
    def _ec_is_battle_shocked(unit: Any) -> bool:
        if unit is None:
            return False
        checker = getattr(unit, "is_battle_shocked", None)
        if callable(checker):
            try:
                return bool(checker())
            except (AttributeError, TypeError, ValueError):
                return False
        return False

    def _ec_attached_has_character(self, unit: Any) -> bool:
        root = self._ec_root(unit)
        if root is None:
            return False
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        for member in members:
            if member is None:
                continue
            is_character = getattr(member, "is_character", False)
            if callable(is_character):
                is_character = is_character()
            if bool(is_character):
                return True
            if self._ec_has_keyword(member, "CHARACTER"):
                return True
        return False

    def _ec_is_favoured_champions(self, unit: Any) -> bool:
        root = self._ec_root(unit)
        if root is None:
            return False
        mgr = self._get_emperors_children_mgr()
        checker = getattr(mgr, "is_favoured_champions", None) if mgr is not None else None
        return bool(checker(root)) if callable(checker) else False

    def _ec_slaanesh_character_candidates(self, *, require_not_fought: bool = False) -> list[Any]:
        candidates = self._ec_targetable_units(
            detachment="slaanesh",
            require_not_fought=require_not_fought,
        )
        out: list[Any] = []
        for root in list(candidates or []):
            if self._ec_attached_has_character(root):
                out.append(root)
        return sorted(out, key=self._ec_sort_key)

    def _ec_embarked_units(self, transport_unit: Any, *, require_emperors_children: bool = True) -> list[Any]:
        root_transport = self._ec_root(transport_unit)
        if root_transport is None:
            return []
        passengers = list(getattr(root_transport, "transport_passengers", []) or [])
        out: list[Any] = []
        seen: set[str] = set()
        for passenger in passengers:
            root = self._ec_root(passenger)
            if root is None:
                continue
            uid = self._ec_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ec_is_alive(root):
                continue
            if require_emperors_children and not self._is_emperors_children_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._ec_sort_key)

    def _ec_rapid_destroyed_enemy_this_phase(self) -> set[str]:
        raw = getattr(self, "_ec_rapid_units_destroyed_enemy_this_phase", None)
        if isinstance(raw, set):
            return raw
        raw = set()
        self._ec_rapid_units_destroyed_enemy_this_phase = raw
        return raw

    def _track_emperors_children_rapid_destroyed_enemy(self, *, destroyed_by_unit: Any) -> None:
        if destroyed_by_unit is None or self.game is None:
            return
        if not self._is_rapid_evisceration_detachment():
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            return
        try:
            if destroyed_by_unit.get_parent_army().player is not self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        root = self._ec_root(destroyed_by_unit)
        if root is None:
            return
        if not self._is_emperors_children_unit(root):
            return
        rid = self._ec_sort_key(root)
        if rid:
            self._ec_rapid_destroyed_enemy_this_phase().add(rid)

    def _ec_rapid_transport_candidates(
        self,
        *,
        require_dedicated: bool = False,
        require_not_battleshocked: bool = False,
        require_tormentors_passenger: bool = False,
    ) -> list[Any]:
        if not self._is_rapid_evisceration_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ec_root(unit)
            if root is None:
                continue
            uid = self._ec_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ec_owned_by_player(root, self.player):
                continue
            if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_emperors_children_unit(root):
                continue
            if not self._ec_has_keyword(root, "TRANSPORT"):
                continue
            if require_dedicated and not self._ec_has_keyword(root, "DEDICATED TRANSPORT"):
                continue
            if require_not_battleshocked and self._ec_is_battle_shocked(root):
                continue
            passengers = self._ec_embarked_units(root, require_emperors_children=True)
            if require_tormentors_passenger:
                has_tormentors = False
                for passenger in passengers:
                    if self._ec_is_battle_shocked(passenger):
                        continue
                    if self._ec_has_keyword(passenger, "TORMENTORS"):
                        has_tormentors = True
                        break
                if not has_tormentors:
                    continue
            out.append(root)
        return sorted(out, key=self._ec_sort_key)

    def _ec_rapid_advance_and_claim_objective_candidates(self, transport_unit: Any) -> list[Any]:
        root = self._ec_root(transport_unit)
        if root is None:
            return []
        helper = getattr(self, "_corrupting_taint_objective_candidates", None)
        if callable(helper):
            try:
                candidates = list(helper(root) or [])
            except (AttributeError, TypeError, ValueError):
                candidates = []
            if candidates:
                return sorted(candidates, key=self._ec_sort_key)
        if self.game is None:
            return []
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return []
        out = []
        for obj in list(getattr(game_map, "objectives", []) or []):
            loc = getattr(obj, "location", None)
            if loc is None or bool(getattr(loc, "removed", False)):
                continue
            if getattr(loc, "controlling_player", None) is not self.player:
                continue
            checker = getattr(root, "is_within_objective_range", None)
            if not callable(checker):
                continue
            try:
                if not bool(checker(loc)):
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            out.append(obj)
        return sorted(out, key=self._ec_sort_key)

    def _ec_rapid_onto_next_transport_candidates(self, unit: Any) -> list[Any]:
        root = self._ec_root(unit)
        if root is None:
            return []
        candidates = self._ec_rapid_transport_candidates()
        out: list[Any] = []
        for transport in list(candidates or []):
            can_transport = getattr(transport, "can_transport", None)
            if not callable(can_transport) or not bool(can_transport(root)):
                continue
            try:
                if not unit_wholly_within_range_of_unit(
                    transport,
                    root,
                    6.0,
                    use_attached_aggregate=True,
                ):
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            out.append(transport)
        return sorted(out, key=self._ec_sort_key)

    def _queue_emperors_children_court_shooting_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Optional[list[Any]],
    ) -> None:
        if not self._is_court_of_the_phoenician_detachment():
            return
        if attacking_unit is None or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        if self._ec_owned_by_player(attacking_unit, self.player):
            return

        self._record_ec_catalytic_snapshot(attacking_unit=attacking_unit, target_units=list(target_units or []))

        stratagem = self.get_by_name("CONTEMPTUOUS DISREGARD")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ec_reaction_already_queued(
            event_name="shooting_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
        ):
            return

        candidates = self._ec_targetable_units()
        if not candidates:
            return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_emperors_children_court_fight_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Optional[list[Any]],
    ) -> None:
        if not self._is_court_of_the_phoenician_detachment():
            return
        if attacking_unit is None or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        if self._ec_owned_by_player(attacking_unit, self.player):
            return

        stratagem = self.get_by_name("CONTEMPTUOUS DISREGARD")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ec_reaction_already_queued(
            event_name="fight_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
        ):
            return

        candidates = self._ec_targetable_units()
        if not candidates:
            return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_emperors_children_court_shooting_resolved_reactions(
        self,
        *,
        attacker_unit: Any,
        hits_by_target: Optional[dict[Any, int]] = None,
    ) -> None:
        if not self._is_court_of_the_phoenician_detachment():
            return
        if attacker_unit is None or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return

        stratagem = self.get_by_name("CATALYTIC STIMULUS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        atk_key = self._attacker_unit_key(attacker_unit)
        snapshots = self._ec_catalytic_wounds_before()
        before_by_target = dict(snapshots.pop(atk_key, {}) if atk_key else {})

        candidates: list[Any] = []
        seen: set[str] = set()
        for target_id, before_wounds in list(before_by_target.items()):
            root = self._ec_root(self._resolve_unit_by_id(target_id))
            if root is None:
                continue
            uid = self._ec_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ec_owned_by_player(root, self.player):
                continue
            if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_emperors_children_unit(root):
                continue
            if int(self._ec_total_current_wounds(root)) >= int(before_wounds or 0):
                continue
            candidates.append(root)

        candidates = sorted(candidates, key=self._ec_sort_key)
        if not candidates:
            return

        if self._ec_reaction_already_queued(
            event_name="unit_shooting_resolved",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            enemy_unit=attacker_unit,
        ):
            return

        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_unit,
            "candidates": candidates,
            "lost_wounds": True,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_emperors_children_coterie_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_coterie_of_the_conceited_detachment():
            return
        if str(getattr(phase, "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        stratagem = self.get_by_name("EMBRACE THE PAIN")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ec_reaction_already_queued(
            event_name="phase_start",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
        ):
            return
        candidates = self._ec_targetable_units(detachment="coterie", require_infantry=True)
        if not candidates:
            return
        payload = {
            "event": "phase_start",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
            payload["unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_emperors_children_coterie_fight_unit_selected_reaction(
        self,
        *,
        unit: Any,
        selecting_player: Any,
    ) -> None:
        if not self._is_coterie_of_the_conceited_detachment():
            return
        if selecting_player is not self.player:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        root = self._ec_root(unit)
        if root is None:
            return
        if not self._ec_owned_by_player(root, self.player):
            return
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return
        if self._unit_cannot_be_target_of_stratagem(root):
            return
        if not self._is_emperors_children_unit(root):
            return
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            return
        stratagem = self.get_by_name("MARTIAL PERFECTION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ec_reaction_already_queued(
            event_name="fight_unit_selected",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
            target_unit=root,
        ):
            return
        self._queue_reaction(
            {
                "event": "fight_unit_selected",
                "phase_name": "Fight phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "target_unit": root,
                "unit": root,
                "candidates": [root],
                "fight_unit_selected": True,
            },
            use_timer=False,
        )

    def _queue_emperors_children_coterie_protection_reaction(
        self,
        *,
        target_unit: Any,
        attacker_unit: Any = None,
        target_model: Any = None,
        phase_name: str = "",
        trigger_event: str = "",
    ) -> None:
        if not self._is_coterie_of_the_conceited_detachment():
            return
        root = self._ec_root(target_unit)
        if root is None:
            return
        if not self._ec_owned_by_player(root, self.player):
            return
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return
        if self._unit_cannot_be_target_of_stratagem(root):
            return
        if not self._is_emperors_children_unit(root):
            return
        stratagem = self.get_by_name("PROTECTION OF THE DARK PRINCE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        event_name = str(trigger_event or "attack_allocated").strip().lower() or "attack_allocated"
        if event_name not in {"attack_allocated", "mortal_wound_allocated"}:
            event_name = "attack_allocated"
        if not phase_name:
            phase_name = str(getattr(self, "_current_phase_name", "") or "")
        if not phase_name:
            phase_key = str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper()
            phase_name = {
                "COMMAND_PHASE": "Command phase",
                "MOVEMENT_PHASE": "Movement phase",
                "SHOOTING_PHASE": "Shooting phase",
                "CHARGE_PHASE": "Charge phase",
                "FIGHT_PHASE": "Fight phase",
            }.get(phase_key, phase_key.title().replace("_", " ")) if phase_key else ""
        if not phase_name:
            phase_name = "Any phase"
        if self._ec_reaction_already_queued(
            event_name=event_name,
            stratagem_name=stratagem.name,
            phase_name=phase_name,
            target_unit=root,
        ):
            return
        payload = {
            "event": event_name,
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "target_unit": root,
            "unit": root,
            "attacking_unit": attacker_unit,
            "target_model": target_model,
            "candidates": [root],
            "attack_allocated": bool(event_name == "attack_allocated"),
            "mortal_wound_allocated": bool(event_name == "mortal_wound_allocated"),
        }
        self._queue_reaction(payload, use_timer=False)

    def _queue_emperors_children_mercurial_shooting_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Optional[list[Any]],
    ) -> None:
        if not self._is_mercurial_host_detachment():
            return
        if attacking_unit is None or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        if self._ec_owned_by_player(attacking_unit, self.player):
            return
        stratagem = self.get_by_name("CAPRICIOUS REACTIONS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ec_reaction_already_queued(
            event_name="shooting_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            enemy_unit=attacking_unit,
        ):
            return

        candidates: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._ec_root(target)
            if root is None:
                continue
            uid = self._ec_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ec_owned_by_player(root, self.player):
                continue
            if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_emperors_children_unit(root):
                continue
            candidates.append(root)
        candidates = sorted(candidates, key=self._ec_sort_key)
        if not candidates:
            return

        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_emperors_children_mercurial_fight_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Optional[list[Any]],
    ) -> None:
        if not self._is_mercurial_host_detachment():
            return
        if attacking_unit is None or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        if self._ec_owned_by_player(attacking_unit, self.player):
            return
        stratagem = self.get_by_name("COMBAT STIMMS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ec_reaction_already_queued(
            event_name="fight_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
            enemy_unit=attacking_unit,
        ):
            return

        candidates: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._ec_root(target)
            if root is None:
                continue
            uid = self._ec_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ec_owned_by_player(root, self.player):
                continue
            if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_emperors_children_infantry_unit(root):
                continue
            candidates.append(root)
        candidates = sorted(candidates, key=self._ec_sort_key)
        if not candidates:
            return

        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_emperors_children_mercurial_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_mercurial_host_detachment():
            return
        if unit is None or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "movement phase":
            return
        action_key = str(action or "").strip().lower()
        if action_key not in {"move", "advance", "fall_back"}:
            return
        enemy_root = self._ec_root(unit)
        if enemy_root is None:
            return
        if self._ec_owned_by_player(enemy_root, self.player):
            return
        if not self._ec_is_alive(enemy_root) or not self._ec_is_on_battlefield(enemy_root):
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return

        stratagem = self.get_by_name("DARK VIGOUR")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ec_reaction_already_queued(
            event_name="unit_move_ended",
            stratagem_name=stratagem.name,
            phase_name="Movement phase",
            enemy_unit=enemy_root,
        ):
            return

        candidates = self._ec_targetable_units(
            detachment="mercurial",
            require_not_beast_vehicle=True,
        )
        filtered: list[Any] = []
        for root in list(candidates or []):
            dist = self._ec_distance_between_units(root, enemy_root)
            if dist is None:
                continue
            if float(dist) > 9.0 + 1e-6:
                continue
            filtered.append(root)
        filtered = sorted(filtered, key=self._ec_sort_key)
        if not filtered:
            return

        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "action": action_key,
            "candidates": filtered,
        }
        if len(filtered) == 1:
            payload["target_unit"] = filtered[0]
        self._queue_reaction(payload)

    def _queue_emperors_children_mercurial_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_mercurial_host_detachment():
            return
        if player is self.player:
            return
        if str(getattr(phase, "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        stratagem = self.get_by_name("CRUEL RAIDERS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ec_reaction_already_queued(
            event_name="phase_end",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
        ):
            return

        candidates = self._ec_targetable_units(detachment="mercurial")
        filtered: list[Any] = []
        for root in list(candidates or []):
            if not self._unit_wholly_within_battlefield_edge_distance(root, 9.0):
                continue
            if self._ec_has_enemy_within_horizontal_distance(root, 3.0):
                continue
            filtered.append(root)
        filtered = sorted(filtered, key=self._ec_sort_key)
        if not filtered:
            return

        payload = {
            "event": "phase_end",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": filtered,
        }
        if len(filtered) == 1:
            payload["target_unit"] = filtered[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_emperors_children_rapid_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_rapid_evisceration_detachment():
            return
        if player is not self.player:
            return
        if str(getattr(phase, "name", "") or "").strip().upper() != "COMMAND_PHASE":
            return
        stratagem = self.get_by_name("ADVANCE AND CLAIM")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ec_reaction_already_queued(
            event_name="phase_start",
            stratagem_name=stratagem.name,
            phase_name="Command phase",
        ):
            return

        candidates = self._ec_rapid_transport_candidates(
            require_not_battleshocked=True,
            require_tormentors_passenger=True,
        )
        filtered: list[Any] = []
        objective_candidates_by_unit: dict[Any, list[Any]] = {}
        for root in list(candidates or []):
            objectives = self._ec_rapid_advance_and_claim_objective_candidates(root)
            if not objectives:
                continue
            filtered.append(root)
            objective_candidates_by_unit[root] = list(objectives)
        filtered = sorted(filtered, key=self._ec_sort_key)
        if not filtered:
            return

        payload = {
            "event": "phase_start",
            "phase": "Command phase",
            "phase_name": "Command phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": filtered,
            "objective_candidates_by_unit": objective_candidates_by_unit,
        }
        if len(filtered) == 1:
            payload["target_unit"] = filtered[0]
            payload["unit"] = filtered[0]
            options = list(objective_candidates_by_unit.get(filtered[0], []) or [])
            if len(options) == 1:
                payload["objective"] = options[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_emperors_children_rapid_shooting_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Optional[list[Any]],
    ) -> None:
        if not self._is_rapid_evisceration_detachment():
            return
        if attacking_unit is None or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        if self._ec_owned_by_player(attacking_unit, self.player):
            return
        stratagem = self.get_by_name("REACTIVE DISEMBARKATION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        candidates: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._ec_root(target)
            if root is None:
                continue
            uid = self._ec_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ec_owned_by_player(root, self.player):
                continue
            if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_emperors_children_unit(root):
                continue
            if not self._ec_has_keyword(root, "TRANSPORT"):
                continue
            if not self._ec_embarked_units(root, require_emperors_children=True):
                continue
            candidates.append(root)
        candidates = sorted(candidates, key=self._ec_sort_key)
        if not candidates:
            return

        if self._ec_reaction_already_queued(
            event_name="shooting_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
        ):
            return

        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_emperors_children_rapid_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_rapid_evisceration_detachment():
            return
        if str(getattr(phase, "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return

        onto = self.get_by_name("ONTO THE NEXT")
        if onto is not None:
            if int(getattr(self.player, "command_points", 0) or 0) >= int(getattr(onto, "cp_cost", 0) or 0):
                if str(onto.name or "").strip().upper() not in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                    if not self._ec_reaction_already_queued(
                        event_name="phase_end",
                        stratagem_name=onto.name,
                        phase_name="Fight phase",
                    ):
                        candidates: list[Any] = []
                        transport_candidates_by_unit: dict[Any, list[Any]] = {}
                        for unit_id in sorted(self._ec_rapid_destroyed_enemy_this_phase()):
                            root = self._ec_root(self._resolve_unit_by_id(unit_id))
                            if root is None:
                                continue
                            if not self._ec_owned_by_player(root, self.player):
                                continue
                            if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
                                continue
                            if self._unit_cannot_be_target_of_stratagem(root):
                                continue
                            if not self._is_emperors_children_unit(root):
                                continue
                            transports = self._ec_rapid_onto_next_transport_candidates(root)
                            if not transports:
                                continue
                            candidates.append(root)
                            transport_candidates_by_unit[root] = transports
                        candidates = sorted(candidates, key=self._ec_sort_key)
                        if candidates:
                            payload = {
                                "event": "phase_end",
                                "phase": "Fight phase",
                                "phase_name": "Fight phase",
                                "stratagem": onto.name,
                                "cp_cost": onto.cp_cost,
                                "candidates": candidates,
                                "transport_candidates_by_unit": transport_candidates_by_unit,
                            }
                            if len(candidates) == 1:
                                payload["target_unit"] = candidates[0]
                            self._queue_reaction(payload, use_timer=False)

        if player is self.player:
            return
        outflank = self.get_by_name("OUTFLANKING STRIKE")
        if outflank is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(outflank, "cp_cost", 0) or 0):
            return
        if str(outflank.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ec_reaction_already_queued(
            event_name="phase_end",
            stratagem_name=outflank.name,
            phase_name="Fight phase",
        ):
            return
        candidates = self._ec_rapid_transport_candidates()
        filtered = [root for root in list(candidates or []) if self._unit_wholly_within_battlefield_edge_distance(root, 9.0)]
        filtered = sorted(filtered, key=self._ec_sort_key)
        if not filtered:
            return
        dedicated = [root for root in filtered if self._ec_has_keyword(root, "DEDICATED TRANSPORT")]
        payload = {
            "event": "phase_end",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": outflank.name,
            "cp_cost": outflank.cp_cost,
            "candidates": filtered,
            "dedicated_candidates": sorted(dedicated, key=self._ec_sort_key),
        }
        if len(filtered) == 1:
            payload["target_unit"] = filtered[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_emperors_children_carnival_shooting_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Optional[list[Any]],
    ) -> None:
        if not self._is_carnival_of_excess_detachment():
            return
        if attacking_unit is None or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        if self._ec_owned_by_player(attacking_unit, self.player):
            return

        stratagem = self.get_by_name("UNCANNY REACTIONS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ec_reaction_already_queued(
            event_name="shooting_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            enemy_unit=attacking_unit,
        ):
            return

        candidates: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._ec_root(target)
            if root is None:
                continue
            uid = self._ec_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ec_owned_by_player(root, self.player):
                continue
            if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_slaanesh_unit(root):
                continue
            candidates.append(root)
        candidates = sorted(candidates, key=self._ec_sort_key)
        if not candidates:
            return

        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_emperors_children_carnival_unit_destroyed_reactions(
        self,
        *,
        destroyed_unit: Any,
        destroyed_by_unit: Any,
    ) -> None:
        if not self._is_carnival_of_excess_detachment():
            return
        if self.game is None or destroyed_by_unit is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        source_root = self._ec_root(destroyed_by_unit)
        if source_root is None:
            return
        if not self._ec_owned_by_player(source_root, self.player):
            return
        if not self._ec_is_alive(source_root) or not self._ec_is_on_battlefield(source_root):
            return

        destroyed_root = self._ec_root(destroyed_unit)

        sustained = self.get_by_name("SUSTAINED BY AGONY")
        if sustained is not None:
            if int(getattr(self.player, "command_points", 0) or 0) >= int(getattr(sustained, "cp_cost", 0) or 0):
                if str(sustained.name or "").strip().upper() not in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                    if self._is_emperors_children_unit(source_root) and not self._unit_cannot_be_target_of_stratagem(source_root):
                        already = False
                        for reaction in list(getattr(self, "_pending_reactions", []) or []):
                            if str(reaction.get("event", "") or "") != "unit_destroyed":
                                continue
                            if str(reaction.get("stratagem", "") or "").strip().upper() != "SUSTAINED BY AGONY":
                                continue
                            if reaction.get("source_unit") is source_root and reaction.get("destroyed_enemy_unit") is destroyed_root:
                                already = True
                                break
                        if not already:
                            candidates: list[Any] = []
                            for friendly in self._ec_friendly_battlefield_units():
                                if not self._is_legions_of_excess_unit(friendly):
                                    continue
                                if self._unit_cannot_be_target_of_stratagem(friendly):
                                    continue
                                dist = self._ec_distance_between_units(source_root, friendly)
                                if dist is None or float(dist) > 6.0 + 1e-6:
                                    continue
                                if self._ec_has_keyword(friendly, "DAEMONETTES"):
                                    if not self._ec_destroyed_non_character_models(friendly):
                                        continue
                                elif not self._ec_wounded_models(friendly):
                                    continue
                                candidates.append(friendly)
                            candidates = sorted(candidates, key=self._ec_sort_key)
                            if candidates:
                                payload = {
                                    "event": "unit_destroyed",
                                    "phase_name": "Fight phase",
                                    "stratagem": sustained.name,
                                    "cp_cost": sustained.cp_cost,
                                    "source_unit": source_root,
                                    "destroyed_enemy_unit": destroyed_root,
                                    "candidates": candidates,
                                }
                                if len(candidates) == 1:
                                    payload["target_unit"] = candidates[0]
                                self._queue_reaction(payload)

        ecstatic = self.get_by_name("ECSTATIC SLAUGHTER")
        if ecstatic is not None:
            if int(getattr(self.player, "command_points", 0) or 0) >= int(getattr(ecstatic, "cp_cost", 0) or 0):
                if str(ecstatic.name or "").strip().upper() not in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                    if self._is_legions_of_excess_unit(source_root) and not self._unit_cannot_be_target_of_stratagem(source_root):
                        already = False
                        for reaction in list(getattr(self, "_pending_reactions", []) or []):
                            if str(reaction.get("event", "") or "") != "unit_destroyed":
                                continue
                            if str(reaction.get("stratagem", "") or "").strip().upper() != "ECSTATIC SLAUGHTER":
                                continue
                            if reaction.get("source_unit") is source_root and reaction.get("destroyed_enemy_unit") is destroyed_root:
                                already = True
                                break
                        if not already:
                            candidates: list[Any] = []
                            for friendly in self._ec_friendly_battlefield_units():
                                if not self._is_emperors_children_unit(friendly):
                                    continue
                                if self._unit_cannot_be_target_of_stratagem(friendly):
                                    continue
                                if self._ec_is_within_engagement_range_of_enemy(friendly):
                                    continue
                                dist = self._ec_distance_between_units(source_root, friendly)
                                if dist is None or float(dist) > 6.0 + 1e-6:
                                    continue
                                candidates.append(friendly)
                            candidates = sorted(candidates, key=self._ec_sort_key)
                            if candidates:
                                payload = {
                                    "event": "unit_destroyed",
                                    "phase_name": "Fight phase",
                                    "stratagem": ecstatic.name,
                                    "cp_cost": ecstatic.cp_cost,
                                    "source_unit": source_root,
                                    "destroyed_enemy_unit": destroyed_root,
                                    "candidates": candidates,
                                }
                                if len(candidates) == 1:
                                    payload["target_unit"] = candidates[0]
                                self._queue_reaction(payload)

    def _queue_emperors_children_carnival_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_carnival_of_excess_detachment():
            return
        if player is self.player:
            return
        if str(getattr(phase, "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        stratagem = self.get_by_name("DARK APPARITIONS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ec_reaction_already_queued(
            event_name="phase_end",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
        ):
            return

        candidates: list[Any] = []
        for friendly in self._ec_friendly_battlefield_units():
            if not self._ec_has_keyword(friendly, "DAEMONETTES"):
                continue
            if self._unit_cannot_be_target_of_stratagem(friendly):
                continue
            if self._ec_is_within_engagement_range_of_enemy(friendly):
                continue
            candidates.append(friendly)
        candidates = sorted(candidates, key=self._ec_sort_key)
        if not candidates:
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
        self._queue_reaction(payload, use_timer=False)

    def _queue_emperors_children_slaanesh_shooting_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Optional[list[Any]],
    ) -> None:
        if not self._is_slaaneshs_chosen_detachment():
            return
        if attacking_unit is None or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        if self._ec_owned_by_player(attacking_unit, self.player):
            return

        stratagem = self.get_by_name("VENGEFUL SURGE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ec_reaction_already_queued(
            event_name="shooting_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            enemy_unit=attacking_unit,
        ):
            return

        candidates: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._ec_root(target)
            if root is None:
                continue
            uid = self._ec_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ec_owned_by_player(root, self.player):
                continue
            if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_emperors_children_unit(root):
                continue
            if not self._ec_attached_has_character(root):
                continue
            candidates.append(root)
        candidates = sorted(candidates, key=self._ec_sort_key)
        if not candidates:
            return

        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_emperors_children_slaanesh_fight_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Optional[list[Any]],
    ) -> None:
        if not self._is_slaaneshs_chosen_detachment():
            return
        if attacking_unit is None or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        if self._ec_owned_by_player(attacking_unit, self.player):
            return

        stratagem = self.get_by_name("BEAUTIFUL DEATH")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ec_reaction_already_queued(
            event_name="fight_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
            enemy_unit=attacking_unit,
        ):
            return

        candidates: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._ec_root(target)
            if root is None:
                continue
            uid = self._ec_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ec_owned_by_player(root, self.player):
                continue
            if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_emperors_children_unit(root):
                continue
            if not self._ec_attached_has_character(root):
                continue
            candidates.append(root)
        candidates = sorted(candidates, key=self._ec_sort_key)
        if not candidates:
            return

        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_emperors_children_slaanesh_favoured_updated_reactions(
        self,
        *,
        unit: Any,
        manager: Any = None,
    ) -> None:
        if not self._is_slaaneshs_chosen_detachment():
            return
        if self.game is None:
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is not self.player:
            return

        root = self._ec_root(unit)
        if root is None:
            return
        if not self._ec_owned_by_player(root, self.player):
            return
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return
        if self._unit_cannot_be_target_of_stratagem(root):
            return
        if not self._is_emperors_children_unit(root):
            return
        if not self._ec_attached_has_character(root):
            return

        mgr = manager if manager is not None else self._get_emperors_children_mgr()
        is_favoured = self._ec_is_favoured_champions(root)
        checker = getattr(mgr, "is_favoured_champions", None) if mgr is not None else None
        if callable(checker):
            is_favoured = bool(checker(root))
        if not is_favoured:
            return

        current_round = int(getattr(self.game, "turn", 0) or 0)

        diabolic = self.get_by_name("DIABOLIC MAJESTY")
        if diabolic is not None:
            if int(getattr(self.player, "command_points", 0) or 0) >= int(getattr(diabolic, "cp_cost", 0) or 0):
                if str(diabolic.name or "").strip().upper() not in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                    if int(getattr(self, "_ec_slaanesh_diabolic_majesty_used_round", 0) or 0) != int(current_round or 0):
                        if not self._ec_reaction_already_queued(
                            event_name="emperors_children_favoured_champions_updated",
                            stratagem_name=diabolic.name,
                            phase_name=phase_name,
                            target_unit=root,
                        ):
                            self._queue_reaction(
                                {
                                    "event": "emperors_children_favoured_champions_updated",
                                    "phase_name": phase_name,
                                    "stratagem": diabolic.name,
                                    "cp_cost": diabolic.cp_cost,
                                    "target_unit": root,
                                    "unit": root,
                                    "candidates": [root],
                                },
                                use_timer=False,
                            )

        jealousy = self.get_by_name("HEIGHTENED JEALOUSY")
        if jealousy is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(jealousy, "cp_cost", 0) or 0):
            return
        if str(jealousy.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ec_reaction_already_queued(
            event_name="emperors_children_favoured_champions_updated",
            stratagem_name=jealousy.name,
            phase_name=phase_name,
            target_unit=root,
        ):
            return
        self._queue_reaction(
            {
                "event": "emperors_children_favoured_champions_updated",
                "phase_name": phase_name,
                "stratagem": jealousy.name,
                "cp_cost": jealousy.cp_cost,
                "target_unit": root,
                "unit": root,
                "candidates": [root],
            },
            use_timer=False,
        )

    def _queue_emperors_children_slaanesh_favoured_destroyed_enemy_reaction(
        self,
        *,
        destroyed_unit: Any,
        destroyed_by_unit: Any,
    ) -> None:
        if not self._is_slaaneshs_chosen_detachment():
            return
        if self.game is None:
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is not self.player:
            return
        if destroyed_by_unit is None or destroyed_unit is None:
            return

        attacker_root = self._ec_root(destroyed_by_unit)
        target_root = self._ec_root(destroyed_unit)
        if attacker_root is None or target_root is None:
            return
        if not self._ec_owned_by_player(attacker_root, self.player):
            return
        if self._ec_owned_by_player(target_root, self.player):
            return
        if not self._ec_is_alive(attacker_root) or not self._ec_is_on_battlefield(attacker_root):
            return
        if self._unit_cannot_be_target_of_stratagem(attacker_root):
            return
        if not self._is_emperors_children_unit(attacker_root):
            return
        if not self._ec_attached_has_character(attacker_root):
            return
        if not self._ec_is_favoured_champions(attacker_root):
            return

        jealousy = self.get_by_name("HEIGHTENED JEALOUSY")
        if jealousy is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(jealousy, "cp_cost", 0) or 0):
            return
        if str(jealousy.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ec_reaction_already_queued(
            event_name="unit_destroyed",
            stratagem_name=jealousy.name,
            phase_name=phase_name,
            target_unit=attacker_root,
        ):
            return
        self._queue_reaction(
            {
                "event": "unit_destroyed",
                "phase_name": phase_name,
                "stratagem": jealousy.name,
                "cp_cost": jealousy.cp_cost,
                "target_unit": attacker_root,
                "unit": attacker_root,
                "enemy_unit": target_root,
                "candidates": [attacker_root],
            },
            use_timer=False,
        )

    def _roll_slaanesh_vengeful_surge_distance(self, unit: Any, *, can_reroll: bool) -> int:
        base_roll = int(dice_module.get_roll("D6") or 0)
        reroll_used = False
        player = getattr(unit.get_parent_army(), "player", None) if unit is not None else None
        if can_reroll:
            provider = getattr(getattr(self.game, "map", None), "roll_reroll_provider", None) if self.game is not None else None
            if callable(provider):
                want = bool(
                    provider(
                        player=player,
                        unit=unit,
                        roll_type="vengeful_surge",
                        value=int(base_roll or 0),
                        dice=[int(base_roll or 0)],
                        allow_reroll=True,
                        fallback_choice=int(base_roll or 0) <= 3,
                    )
                )
                if want:
                    base_roll = int(dice_module.get_roll("D6") or 0)
                    reroll_used = True
            else:
                if int(base_roll or 0) <= 3:
                    base_roll = int(dice_module.get_roll("D6") or 0)
                    reroll_used = True

        if player is not None:
            from ..utility.event_bus import append_dice

            label = "Vengeful Surge reroll" if reroll_used else "Vengeful Surge roll"
            append_dice(player, f"{label}: {int(base_roll or 0)}\" for {getattr(unit, 'name', 'Unit')}")
        return int(base_roll or 0)

    def _resolve_emperors_children_slaanesh_vengeful_surge_after_shooting(
        self,
        *,
        attacker_unit: Any,
    ) -> None:
        if not self._is_slaaneshs_chosen_detachment():
            return
        if attacker_unit is None or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return

        attacker_root = self._ec_root(attacker_unit)
        attacker_id = self._ec_sort_key(attacker_root)
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return

        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ec_root(unit)
            if root is None:
                continue
            uid = self._ec_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("slaanesh_vengeful_surge_pending")):
                continue
            expected_attacker_id = str(sr.get("slaanesh_vengeful_surge_attacker_id", "") or "")
            if expected_attacker_id and attacker_id and expected_attacker_id != attacker_id:
                continue
            for key in (
                "slaanesh_vengeful_surge_pending",
                "slaanesh_vengeful_surge_attacker_id",
                "slaanesh_vengeful_surge_allow_reroll",
                "slaanesh_vengeful_surge_source",
                "slaanesh_vengeful_surge_owner",
                "slaanesh_vengeful_surge_turn",
                "slaanesh_vengeful_surge_expires_phase",
            ):
                sr.pop(key, None)
            root.special_rules = sr

            if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
                continue
            can_reroll = bool(sr.get("slaanesh_vengeful_surge_allow_reroll", False))
            source_name = str(sr.get("slaanesh_vengeful_surge_source", "") or "VENGEFUL SURGE").strip() or "VENGEFUL SURGE"
            max_distance = self._roll_slaanesh_vengeful_surge_distance(root, can_reroll=can_reroll)
            if max_distance <= 0:
                continue
            closest_enemy = self._court_closest_non_aircraft_enemy(root)
            queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None)
            if callable(queue_move):
                queue_move(
                    player=self.player,
                    unit=root,
                    max_distance=int(max_distance),
                    kind="vengeful_surge",
                    movement_type="reactive",
                    source=source_name,
                    attacker_unit=closest_enemy or attacker_root,
                    allow_engagement_range=True,
                )

    def _ec_resolve_unit_entry(self, entry: Any) -> Any:
        if isinstance(entry, str):
            return self._ec_root(self._resolve_unit_by_id(entry))
        return self._ec_root(entry)

    def _ec_enemy_units_on_battlefield(self) -> list[Any]:
        if self.game is None:
            return []
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(game_map, "units", []) or []):
            root = self._ec_root(unit)
            if root is None:
                continue
            uid = self._ec_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if self._ec_owned_by_player(root, self.player):
                continue
            if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
                continue
            out.append(root)
        return sorted(out, key=self._ec_sort_key)

    def _ec_enemy_within_engagement_of_friendly(self, enemy_unit: Any) -> bool:
        if self.game is None or enemy_unit is None:
            return False
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return False
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return False
        enemy_root = self._ec_root(enemy_unit)
        if enemy_root is None:
            return False
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ec_root(unit)
            if root is None:
                continue
            uid = self._ec_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ec_owned_by_player(root, self.player):
                continue
            if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
                continue
            try:
                if bool(game_map.is_within_engagement_range(root, enemy_root)):
                    return True
            except (AttributeError, TypeError, ValueError):
                continue
        return False

    def _use_slaanesh_devoted_duellists(self, stratagem: Any, **kwargs) -> bool:
        selected = (
            kwargs.get("units")
            or kwargs.get("target_units")
            or kwargs.get("selected_units")
            or kwargs.get("unit")
            or kwargs.get("target_unit")
        )
        if selected is None:
            selected = []
        if not isinstance(selected, (list, tuple)):
            selected = [selected]
        resolved: list[Any] = []
        seen: set[str] = set()
        for entry in list(selected or []):
            root = self._ec_resolve_unit_entry(entry)
            if root is None:
                continue
            uid = self._ec_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            resolved.append(root)

        eligible = self._ec_slaanesh_character_candidates(require_not_fought=True)
        if not resolved and len(eligible) == 1:
            resolved = [eligible[0]]
        if not resolved:
            logger.error("ERROR: DEVOTED DUELLISTS: no target unit provided")
            return False

        enemy_unit = (
            kwargs.get("enemy_unit")
            or kwargs.get("attacker_unit")
            or kwargs.get("target_enemy_unit")
            or kwargs.get("enemy_target")
        )
        enemy_root = self._ec_resolve_unit_entry(enemy_unit)
        enemy_candidates = self._ec_enemy_units_on_battlefield()
        if enemy_root is None and len(enemy_candidates) == 1:
            enemy_root = enemy_candidates[0]
        if enemy_root is None:
            logger.error("ERROR: DEVOTED DUELLISTS: no enemy unit provided")
            return False
        if not self._ec_unit_in_candidates(enemy_root, enemy_candidates):
            logger.error("ERROR: DEVOTED DUELLISTS: selected enemy is not a valid target")
            return False

        if not self._is_slaaneshs_chosen_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: DEVOTED DUELLISTS: wrong phase")
            return False
        for root in list(resolved):
            if not self._ec_unit_in_candidates(root, eligible):
                logger.error("ERROR: DEVOTED DUELLISTS: one or more selected units are not eligible")
                return False
        if not self._court_spend_cp(stratagem, target_unit=resolved[0], enemy_unit=enemy_root):
            return False

        enemy_id = self._ec_sort_key(enemy_root)
        for root in list(resolved):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["devoted_duellists_active"] = True
            sr["devoted_duellists_expires_phase"] = "FIGHT_PHASE"
            sr["devoted_duellists_owner"] = str(getattr(self.player, "id", "") or "")
            sr["devoted_duellists_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
            sr["devoted_duellists_source"] = str(stratagem.name or "DEVOTED DUELLISTS")
            sr["devoted_duellists_target_unit_id"] = str(enemy_id or "")
            sr["devoted_duellists_sustained_hits_value"] = 1
            root.special_rules = sr

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DEVOTED DUELLISTS: %d unit(s) gain Sustained Hits 1 vs %s this phase.",
            int(len(resolved)),
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_slaanesh_beautiful_death(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("attacking_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "BEAUTIFUL DEATH":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                enemy_unit = enemy_unit or reaction.get("attacking_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: BEAUTIFUL DEATH: no target unit provided")
            return False

        root = self._ec_resolve_unit_entry(unit)
        enemy_root = self._ec_resolve_unit_entry(enemy_unit)
        if root is None:
            return False
        if not self._is_slaaneshs_chosen_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: BEAUTIFUL DEATH: wrong phase")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: BEAUTIFUL DEATH: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: BEAUTIFUL DEATH: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: BEAUTIFUL DEATH: target cannot be selected")
            return False
        if not self._is_emperors_children_unit(root) or not self._ec_attached_has_character(root):
            logger.error("ERROR: BEAUTIFUL DEATH: target must be an EMPEROR'S CHILDREN CHARACTER unit")
            return False
        if enemy_root is not None and self._ec_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: BEAUTIFUL DEATH: attacker is not enemy")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root, enemy_unit=enemy_root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["beautiful_death_active"] = True
        sr["beautiful_death_expires_phase"] = "FIGHT_PHASE"
        sr["beautiful_death_owner"] = str(getattr(self.player, "id", "") or "")
        sr["beautiful_death_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["beautiful_death_source"] = str(stratagem.name or "BEAUTIFUL DEATH")
        root.special_rules = sr

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: BEAUTIFUL DEATH: %s can fight on death on a 4+ this phase (+1 if Favoured Champions).",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_slaanesh_diabolic_majesty(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "DIABOLIC MAJESTY":
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
            logger.error("ERROR: DIABOLIC MAJESTY: no target unit provided")
            return False

        root = self._ec_resolve_unit_entry(unit)
        if root is None:
            return False
        if not self._is_slaaneshs_chosen_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in ("shooting phase", "fight phase"):
            logger.error("ERROR: DIABOLIC MAJESTY: wrong phase")
            return False
        if phase_name == "shooting phase":
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
            if active_player is not self.player:
                logger.error("ERROR: DIABOLIC MAJESTY: not your Shooting phase")
                return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: DIABOLIC MAJESTY: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: DIABOLIC MAJESTY: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: DIABOLIC MAJESTY: target cannot be selected")
            return False
        if not self._is_emperors_children_unit(root) or not self._ec_attached_has_character(root):
            logger.error("ERROR: DIABOLIC MAJESTY: target must be an EMPEROR'S CHILDREN CHARACTER unit")
            return False
        if not self._ec_is_favoured_champions(root):
            logger.error("ERROR: DIABOLIC MAJESTY: target must be your Favoured Champions")
            return False
        current_round = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        if int(getattr(self, "_ec_slaanesh_diabolic_majesty_used_round", 0) or 0) == int(current_round or 0):
            logger.error("ERROR: DIABOLIC MAJESTY: already used this battle round")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root):
            return False

        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        affected = 0
        for enemy_root in list(self._ec_enemy_units_on_battlefield() or []):
            distance = self._ec_distance_between_units(root, enemy_root)
            if distance is None or float(distance) > 6.0 + 1e-6:
                continue
            sr = getattr(enemy_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["battle_shock_test_modifier"] = int(sr.get("battle_shock_test_modifier", 0) or 0) - 1
            reasons = list(sr.get("battle_shock_test_modifier_reasons", []) or [])
            reasons.append("Diabolic Majesty")
            sr["battle_shock_test_modifier_reasons"] = reasons
            enemy_root.special_rules = sr
            take_test = getattr(enemy_root, "take_battle_shock_test", None)
            if callable(take_test):
                take_test(turn)
            affected += 1

        self._ec_slaanesh_diabolic_majesty_used_round = int(current_round or 0)
        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DIABOLIC MAJESTY: %d enemy unit(s) took Battle-shock tests at -1.",
            int(affected),
        )
        return True

    def _use_slaanesh_heightened_jealousy(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "HEIGHTENED JEALOUSY":
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
            logger.error("ERROR: HEIGHTENED JEALOUSY: no target unit provided")
            return False

        root = self._ec_resolve_unit_entry(unit)
        if root is None:
            return False
        if not self._is_slaaneshs_chosen_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in ("shooting phase", "fight phase"):
            logger.error("ERROR: HEIGHTENED JEALOUSY: wrong phase")
            return False
        if phase_name == "shooting phase":
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
            if active_player is not self.player:
                logger.error("ERROR: HEIGHTENED JEALOUSY: not your Shooting phase")
                return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: HEIGHTENED JEALOUSY: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: HEIGHTENED JEALOUSY: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: HEIGHTENED JEALOUSY: target cannot be selected")
            return False
        if not self._is_emperors_children_unit(root) or not self._ec_attached_has_character(root):
            logger.error("ERROR: HEIGHTENED JEALOUSY: target must be an EMPEROR'S CHILDREN CHARACTER unit")
            return False
        if not self._ec_is_favoured_champions(root):
            logger.error("ERROR: HEIGHTENED JEALOUSY: target must be your Favoured Champions")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root):
            return False

        applied = 0
        favoured_id = self._ec_sort_key(root)
        phase_key = self._phase_key_from_name(phase_name)
        for other in list(self._ec_slaanesh_character_candidates(require_not_fought=False) or []):
            other_root = self._ec_root(other)
            if other_root is None:
                continue
            if self._ec_is_favoured_champions(other_root):
                continue
            other_id = self._ec_sort_key(other_root)
            if favoured_id and other_id and favoured_id == other_id:
                continue
            sr = getattr(other_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["heightened_jealousy_active"] = True
            sr["heightened_jealousy_expires_phase"] = str(phase_key)
            sr["heightened_jealousy_owner"] = str(getattr(self.player, "id", "") or "")
            sr["heightened_jealousy_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
            sr["heightened_jealousy_source"] = str(stratagem.name or "HEIGHTENED JEALOUSY")
            sr["heightened_jealousy_favoured_unit_id"] = str(favoured_id or "")
            sr["heightened_jealousy_strength_bonus"] = 1
            other_root.special_rules = sr
            applied += 1

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: HEIGHTENED JEALOUSY: %d non-favoured CHARACTER unit(s) gain +1 Strength on attacks this phase.",
            int(applied),
        )
        return True

    def _use_slaanesh_refusal_to_be_outdone(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: REFUSAL TO BE OUTDONE: no target unit provided")
            return False

        root = self._ec_resolve_unit_entry(unit)
        if root is None:
            return False
        if not self._is_slaaneshs_chosen_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: REFUSAL TO BE OUTDONE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: REFUSAL TO BE OUTDONE: not your turn")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: REFUSAL TO BE OUTDONE: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: REFUSAL TO BE OUTDONE: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: REFUSAL TO BE OUTDONE: target cannot be selected")
            return False
        if not self._is_emperors_children_unit(root) or not self._ec_attached_has_character(root):
            logger.error("ERROR: REFUSAL TO BE OUTDONE: target must be an EMPEROR'S CHILDREN CHARACTER unit")
            return False

        enemy_unit = (
            kwargs.get("enemy_unit")
            or kwargs.get("attacker_unit")
            or kwargs.get("target_enemy_unit")
            or kwargs.get("enemy_target")
        )
        enemy_root = self._ec_resolve_unit_entry(enemy_unit)
        enemy_candidates = [
            cand for cand in self._ec_enemy_units_on_battlefield()
            if self._ec_enemy_within_engagement_of_friendly(cand)
        ]
        if enemy_root is None and len(enemy_candidates) == 1:
            enemy_root = enemy_candidates[0]
        if enemy_root is None:
            logger.error("ERROR: REFUSAL TO BE OUTDONE: no enemy unit provided")
            return False
        if not self._ec_unit_in_candidates(enemy_root, enemy_candidates):
            logger.error("ERROR: REFUSAL TO BE OUTDONE: selected enemy is not within Engagement Range of your units")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root, enemy_unit=enemy_root):
            return False

        enemy_id = self._ec_sort_key(enemy_root)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        mods = list(sr.get("charge_roll_modifiers", []) or [])
        mods = [
            m
            for m in mods
            if not (isinstance(m, dict) and str(m.get("tag", "") or "") == "stratagem:refusal_to_be_outdone")
        ]
        mods.append(
            {
                "value": 2,
                "source": str(stratagem.name or "REFUSAL TO BE OUTDONE"),
                "tag": "stratagem:refusal_to_be_outdone",
                "expires_phase": "CHARGE_PHASE",
                "owner": str(getattr(self.player, "id", "") or ""),
                "turn": int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0,
                "target_unit_ids": [str(enemy_id or "")] if enemy_id else [],
            }
        )
        sr["charge_roll_modifiers"] = mods
        sr["slaanesh_refusal_to_be_outdone_active"] = True
        sr["slaanesh_refusal_to_be_outdone_owner"] = str(getattr(self.player, "id", "") or "")
        sr["slaanesh_refusal_to_be_outdone_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["slaanesh_refusal_to_be_outdone_expires_phase"] = "CHARGE_PHASE"
        sr["slaanesh_refusal_to_be_outdone_target_unit_id"] = str(enemy_id or "")
        sr["slaanesh_refusal_to_be_outdone_source"] = str(stratagem.name or "REFUSAL TO BE OUTDONE")
        root.special_rules = sr

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: REFUSAL TO BE OUTDONE: %s gains +2 to charge against %s this phase.",
            getattr(root, "name", "Unit"),
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_slaanesh_vengeful_surge(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("attacking_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "VENGEFUL SURGE":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                enemy_unit = enemy_unit or reaction.get("attacking_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: VENGEFUL SURGE: no target unit provided")
            return False

        root = self._ec_resolve_unit_entry(unit)
        enemy_root = self._ec_resolve_unit_entry(enemy_unit)
        if root is None:
            return False
        if not self._is_slaaneshs_chosen_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: VENGEFUL SURGE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: VENGEFUL SURGE: not opponent's Shooting phase")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: VENGEFUL SURGE: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: VENGEFUL SURGE: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: VENGEFUL SURGE: target cannot be selected")
            return False
        if not self._is_emperors_children_unit(root) or not self._ec_attached_has_character(root):
            logger.error("ERROR: VENGEFUL SURGE: target must be an EMPEROR'S CHILDREN CHARACTER unit")
            return False
        if enemy_root is not None and self._ec_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: VENGEFUL SURGE: attacker is not enemy")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root, enemy_unit=enemy_root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["slaanesh_vengeful_surge_pending"] = True
        sr["slaanesh_vengeful_surge_attacker_id"] = str(self._ec_sort_key(enemy_root) or "")
        sr["slaanesh_vengeful_surge_allow_reroll"] = not self._ec_is_favoured_champions(root)
        sr["slaanesh_vengeful_surge_source"] = str(stratagem.name or "VENGEFUL SURGE")
        sr["slaanesh_vengeful_surge_owner"] = str(getattr(self.player, "id", "") or "")
        sr["slaanesh_vengeful_surge_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["slaanesh_vengeful_surge_expires_phase"] = "SHOOTING_PHASE"
        root.special_rules = sr

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: VENGEFUL SURGE: %s will make a Surge move after the attacker resolves shooting.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_emperors_children_slaanesh_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "DEVOTED DUELLISTS":
            return self._use_slaanesh_devoted_duellists(stratagem, **kwargs)
        if name_u == "BEAUTIFUL DEATH":
            return self._use_slaanesh_beautiful_death(stratagem, **kwargs)
        if name_u == "HEIGHTENED JEALOUSY":
            return self._use_slaanesh_heightened_jealousy(stratagem, **kwargs)
        if name_u == "DIABOLIC MAJESTY":
            return self._use_slaanesh_diabolic_majesty(stratagem, **kwargs)
        if name_u == "REFUSAL TO BE OUTDONE":
            return self._use_slaanesh_refusal_to_be_outdone(stratagem, **kwargs)
        if name_u == "VENGEFUL SURGE":
            return self._use_slaanesh_vengeful_surge(stratagem, **kwargs)
        return None

    def _use_carnival_sustained_by_agony(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        source_unit = kwargs.get("source_unit") or kwargs.get("destroyed_by_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "SUSTAINED BY AGONY":
                    continue
                target_unit = reaction.get("target_unit") or reaction.get("unit")
                source_unit = source_unit or reaction.get("source_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: SUSTAINED BY AGONY: no LEGIONS OF EXCESS target provided")
            return False

        source_root = self._ec_resolve_unit_entry(source_unit)
        target_root = self._ec_resolve_unit_entry(target_unit)
        if source_root is None:
            logger.error("ERROR: SUSTAINED BY AGONY: missing source EMPEROR'S CHILDREN unit")
            return False
        if target_root is None:
            return False
        if not self._is_carnival_of_excess_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: SUSTAINED BY AGONY: wrong phase")
            return False
        if not self._ec_owned_by_player(source_root, self.player):
            logger.error("ERROR: SUSTAINED BY AGONY: source unit is not yours")
            return False
        if not self._ec_is_alive(source_root) or not self._ec_is_on_battlefield(source_root):
            return False
        if self._unit_cannot_be_target_of_stratagem(source_root):
            logger.error("ERROR: SUSTAINED BY AGONY: source unit cannot be selected")
            return False
        if not self._is_emperors_children_unit(source_root):
            logger.error("ERROR: SUSTAINED BY AGONY: source must be an EMPEROR'S CHILDREN unit")
            return False
        if candidates and not self._ec_unit_in_candidates(target_root, candidates):
            logger.error("ERROR: SUSTAINED BY AGONY: selected target is not currently eligible")
            return False
        if not self._ec_owned_by_player(target_root, self.player):
            logger.error("ERROR: SUSTAINED BY AGONY: selected target unit is not yours")
            return False
        if not self._ec_is_alive(target_root) or not self._ec_is_on_battlefield(target_root):
            return False
        if self._unit_cannot_be_target_of_stratagem(target_root):
            logger.error("ERROR: SUSTAINED BY AGONY: selected target cannot be selected")
            return False
        if not self._is_legions_of_excess_unit(target_root):
            logger.error("ERROR: SUSTAINED BY AGONY: selected target must be LEGIONS OF EXCESS")
            return False
        dist = self._ec_distance_between_units(source_root, target_root)
        if dist is None or float(dist) > 6.0 + 1e-6:
            logger.error("ERROR: SUSTAINED BY AGONY: selected target must be within 6\" of source unit")
            return False

        is_daemonettes = self._ec_has_keyword(target_root, "DAEMONETTES")
        wounded_models = self._ec_wounded_models(target_root)
        destroyed_models = self._ec_destroyed_non_character_models(target_root)
        if is_daemonettes:
            if not destroyed_models:
                logger.error("ERROR: SUSTAINED BY AGONY: DAEMONETTES target has no destroyed models to return")
                return False
        elif not wounded_models:
            logger.error("ERROR: SUSTAINED BY AGONY: selected target has no lost wounds to recover")
            return False

        if not self._court_spend_cp(stratagem, target_unit=source_root, enemy_unit=target_root):
            return False

        healed = 0
        returned = 0
        if is_daemonettes:
            amount = max(0, int(dice_module.get_roll("D3") or 0)) + 3
            chosen = kwargs.get("return_models") or kwargs.get("chosen_models")
            selected_models = list(destroyed_models)
            if chosen is not None:
                selected_ids: set[str] = set()
                filtered: list[Any] = []
                for entry in list(chosen or []):
                    entry_id = str(get_entity_id(entry) or entry or "")
                    if not entry_id or entry_id in selected_ids:
                        continue
                    for model in destroyed_models:
                        if str(get_entity_id(model) or "") == entry_id:
                            filtered.append(model)
                            selected_ids.add(entry_id)
                            break
                selected_models = filtered
            returned = int(
                target_root.return_destroyed_bodyguard_models(
                    int(amount),
                    game_map=getattr(self.game, "map", None),
                    chosen_models=selected_models,
                    wounds=None,
                    placement_source=str(stratagem.name or "SUSTAINED BY AGONY"),
                )
                or 0
            )
        else:
            heal_amount = 3
            heal_model = kwargs.get("model") or kwargs.get("target_model")
            if heal_model is None and wounded_models:
                heal_model = wounded_models[0]
            if heal_model is not None:
                if heal_model not in list(getattr(target_root, "models", []) or []):
                    logger.error("ERROR: SUSTAINED BY AGONY: selected heal model does not belong to target unit")
                    return False
                missing = self._ec_model_missing_wounds(heal_model)
                if missing > 0:
                    healed = min(int(heal_amount), int(missing))
                    heal_fn = getattr(heal_model, "heal", None)
                    if callable(heal_fn):
                        heal_fn(int(heal_amount))
                    else:
                        base_wounds = int(
                            getattr(heal_model, "_base_wounds", getattr(heal_model, "base_wounds", 0)) or 0
                        )
                        current_wounds = int(getattr(heal_model, "wounds", 0) or 0)
                        heal_model.wounds = min(base_wounds, current_wounds + int(heal_amount))

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SUSTAINED BY AGONY: %s healed=%d returned=%d.",
            getattr(target_root, "name", "Unit"),
            int(healed),
            int(returned),
        )
        return True

    def _use_carnival_sycophantic_surge(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SYCOPHANTIC SURGE: no target unit provided")
            return False

        root = self._ec_resolve_unit_entry(unit)
        if root is None:
            return False
        if not self._is_carnival_of_excess_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: SYCOPHANTIC SURGE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SYCOPHANTIC SURGE: not your turn")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: SYCOPHANTIC SURGE: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: SYCOPHANTIC SURGE: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: SYCOPHANTIC SURGE: target cannot be selected")
            return False
        if not self._is_legions_of_excess_unit(root):
            logger.error("ERROR: SYCOPHANTIC SURGE: target must be LEGIONS OF EXCESS")
            return False

        original_sr = dict(getattr(root, "special_rules", {}) or {})
        sr = dict(original_sr)
        sr["carnival_sycophantic_surge_active"] = True
        sr["carnival_sycophantic_surge_charge_after_advance"] = True
        sr["carnival_sycophantic_surge_charge_after_fall_back"] = True
        sr["carnival_sycophantic_surge_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["carnival_sycophantic_surge_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["carnival_sycophantic_surge_expires_phase"] = "CHARGE_PHASE"
        sr["carnival_sycophantic_surge_source"] = str(stratagem.name or "SYCOPHANTIC SURGE")
        root.special_rules = sr

        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None:
            root.special_rules = original_sr
            return False

        enemy_candidates: list[Any] = []
        seen: set[str] = set()
        for enemy in list(game_map.get_enemy_units(root) or []):
            enemy_root = self._ec_root(enemy)
            if enemy_root is None:
                continue
            eid = self._ec_sort_key(enemy_root)
            if eid and eid in seen:
                continue
            if eid:
                seen.add(eid)
            if not self._ec_is_alive(enemy_root) or not self._ec_is_on_battlefield(enemy_root):
                continue
            if not self._ec_enemy_within_engagement_of_friendly(enemy_root):
                continue
            try:
                if not root.can_declare_charge_against(enemy_root, self.game, out_of_turn=False):
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            enemy_candidates.append(enemy_root)
        enemy_candidates = sorted(enemy_candidates, key=self._ec_sort_key)
        if not enemy_candidates:
            root.special_rules = original_sr
            logger.error(
                "ERROR: SYCOPHANTIC SURGE: no eligible charge target is within Engagement Range of a friendly EMPEROR'S CHILDREN unit"
            )
            return False

        selected_enemy = kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit")
        if selected_enemy is not None:
            selected_root = self._ec_resolve_unit_entry(selected_enemy)
            if selected_root is None or not self._ec_unit_in_candidates(selected_root, enemy_candidates):
                root.special_rules = original_sr
                logger.error("ERROR: SYCOPHANTIC SURGE: selected enemy does not satisfy target condition")
                return False

        if not self._court_spend_cp(stratagem, target_unit=root):
            root.special_rules = original_sr
            return False

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SYCOPHANTIC SURGE: %s can charge after Advancing/Falling Back this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_carnival_uncanny_reactions(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("attacking_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "UNCANNY REACTIONS":
                    continue
                unit = reaction.get("target_unit") or reaction.get("unit")
                enemy_unit = enemy_unit or reaction.get("attacking_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: UNCANNY REACTIONS: no target unit provided")
            return False

        root = self._ec_resolve_unit_entry(unit)
        enemy_root = self._ec_resolve_unit_entry(enemy_unit)
        if root is None:
            return False
        if not self._is_carnival_of_excess_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: UNCANNY REACTIONS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: UNCANNY REACTIONS: not opponent's Shooting phase")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: UNCANNY REACTIONS: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: UNCANNY REACTIONS: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: UNCANNY REACTIONS: target cannot be selected")
            return False
        if not self._is_slaanesh_unit(root):
            logger.error("ERROR: UNCANNY REACTIONS: target must have the SLAANESH keyword")
            return False
        if enemy_root is not None and self._ec_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: UNCANNY REACTIONS: attacker is not enemy")
            return False

        if not self._court_spend_cp(stratagem, target_unit=root, enemy_unit=enemy_root):
            return False

        entry = {
            "value": 1,
            "attack_type": "any",
            "expires_phase": "SHOOTING_PHASE",
            "source": str(stratagem.name or "UNCANNY REACTIONS"),
        }
        self._append_defensive_effect(root, "defensive_hit_mods", entry)
        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: UNCANNY REACTIONS: %s gains -1 to be hit until end of phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_carnival_ecstatic_slaughter(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        source_unit = kwargs.get("source_unit") or kwargs.get("destroyed_by_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "ECSTATIC SLAUGHTER":
                    continue
                unit = reaction.get("target_unit") or reaction.get("unit")
                source_unit = source_unit or reaction.get("source_unit")
                enemy_unit = enemy_unit or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: ECSTATIC SLAUGHTER: no EMPEROR'S CHILDREN charge unit provided")
            return False

        source_root = self._ec_resolve_unit_entry(source_unit)
        target_root = self._ec_resolve_unit_entry(unit)
        enemy_root = self._ec_resolve_unit_entry(enemy_unit)
        if source_root is None:
            logger.error("ERROR: ECSTATIC SLAUGHTER: missing LEGIONS OF EXCESS source unit")
            return False
        if target_root is None:
            return False
        if not self._is_carnival_of_excess_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: ECSTATIC SLAUGHTER: wrong phase")
            return False
        if not self._ec_owned_by_player(source_root, self.player):
            logger.error("ERROR: ECSTATIC SLAUGHTER: source unit is not yours")
            return False
        if not self._ec_is_alive(source_root) or not self._ec_is_on_battlefield(source_root):
            return False
        if self._unit_cannot_be_target_of_stratagem(source_root):
            logger.error("ERROR: ECSTATIC SLAUGHTER: source unit cannot be selected")
            return False
        if not self._is_legions_of_excess_unit(source_root):
            logger.error("ERROR: ECSTATIC SLAUGHTER: source must be LEGIONS OF EXCESS")
            return False
        if candidates and not self._ec_unit_in_candidates(target_root, candidates):
            logger.error("ERROR: ECSTATIC SLAUGHTER: selected charge unit is not currently eligible")
            return False
        if not self._ec_owned_by_player(target_root, self.player):
            logger.error("ERROR: ECSTATIC SLAUGHTER: selected charge unit is not yours")
            return False
        if not self._ec_is_alive(target_root) or not self._ec_is_on_battlefield(target_root):
            return False
        if self._unit_cannot_be_target_of_stratagem(target_root):
            logger.error("ERROR: ECSTATIC SLAUGHTER: selected charge unit cannot be selected")
            return False
        if not self._is_emperors_children_unit(target_root):
            logger.error("ERROR: ECSTATIC SLAUGHTER: selected charge unit must be EMPEROR'S CHILDREN")
            return False
        if self._ec_is_within_engagement_range_of_enemy(target_root):
            logger.error("ERROR: ECSTATIC SLAUGHTER: selected charge unit must not be within Engagement Range")
            return False
        dist = self._ec_distance_between_units(source_root, target_root)
        if dist is None or float(dist) > 6.0 + 1e-6:
            logger.error("ERROR: ECSTATIC SLAUGHTER: selected charge unit must be within 6\" of source unit")
            return False

        if self.game is None:
            return False
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return False

        enemy_candidates: list[Any] = []
        seen: set[str] = set()
        for enemy in list(game_map.get_enemy_units(target_root) or []):
            enemy_candidate = self._ec_root(enemy)
            if enemy_candidate is None:
                continue
            eid = self._ec_sort_key(enemy_candidate)
            if eid and eid in seen:
                continue
            if eid:
                seen.add(eid)
            if not self._ec_is_alive(enemy_candidate) or not self._ec_is_on_battlefield(enemy_candidate):
                continue
            try:
                if not target_root.can_declare_charge_against(enemy_candidate, self.game, out_of_turn=True):
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            enemy_candidates.append(enemy_candidate)
        enemy_candidates = sorted(enemy_candidates, key=self._ec_sort_key)
        if not enemy_candidates:
            logger.error("ERROR: ECSTATIC SLAUGHTER: no eligible enemy charge target")
            return False
        if enemy_root is None and len(enemy_candidates) == 1:
            enemy_root = enemy_candidates[0]
        if enemy_root is None:
            logger.error("ERROR: ECSTATIC SLAUGHTER: missing enemy charge target")
            return False
        if not self._ec_unit_in_candidates(enemy_root, enemy_candidates):
            logger.error("ERROR: ECSTATIC SLAUGHTER: selected enemy charge target is not eligible")
            return False

        if not self._court_spend_cp(stratagem, target_unit=source_root, enemy_unit=enemy_root):
            return False

        ok = False
        try:
            ok = bool(self.game.attempt_charge(target_root, enemy_root, out_of_turn=True))
        except (AttributeError, TypeError, ValueError):
            ok = False

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        if not ok:
            logger.error("ERROR: ECSTATIC SLAUGHTER: charge failed")
        return True

    def _use_carnival_violent_crescendo(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: VIOLENT CRESCENDO: no target unit provided")
            return False

        root = self._ec_resolve_unit_entry(unit)
        if root is None:
            return False
        if not self._is_carnival_of_excess_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: VIOLENT CRESCENDO: wrong phase")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: VIOLENT CRESCENDO: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: VIOLENT CRESCENDO: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: VIOLENT CRESCENDO: target cannot be selected")
            return False
        if not self._is_slaanesh_unit(root):
            logger.error("ERROR: VIOLENT CRESCENDO: target must have the SLAANESH keyword")
            return False
        if not (
            self._ec_has_keyword(root, "BEAST")
            or self._ec_has_keyword(root, "BEASTS")
            or self._ec_has_keyword(root, "INFANTRY")
            or self._ec_has_keyword(root, "MOUNTED")
        ):
            logger.error("ERROR: VIOLENT CRESCENDO: target must be BEASTS, INFANTRY, or MOUNTED")
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: VIOLENT CRESCENDO: target has already been selected to fight this phase")
            return False

        if not self._court_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        current_pile = float(sr.get("bearer_unit_pile_in_distance_override", 0.0) or 0.0)
        current_cons = float(sr.get("stratagem_consolidate_distance_override", 0.0) or 0.0)
        sr["bearer_unit_pile_in_distance_override"] = max(current_pile, 6.0)
        sr["stratagem_consolidate_distance_override"] = max(current_cons, 6.0)
        sr["stratagem_choreographer_of_war_source"] = str(stratagem.name or "VIOLENT CRESCENDO")
        sr["carnival_violent_crescendo_active"] = True
        sr["carnival_violent_crescendo_expires_phase"] = "FIGHT_PHASE"
        sr["carnival_violent_crescendo_owner"] = str(getattr(self.player, "id", "") or "")
        sr["carnival_violent_crescendo_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["carnival_violent_crescendo_source"] = str(stratagem.name or "VIOLENT CRESCENDO")
        root.special_rules = sr
        ability_cache = getattr(root, "_ability_cache", None)
        if isinstance(ability_cache, dict):
            ability_cache.pop("choreographer_of_war_source", None)

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: VIOLENT CRESCENDO: %s gets 6\" pile-in/consolidate with closest-enemy-unit movement rules this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_carnival_dark_apparitions(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "DARK APPARITIONS":
                    continue
                unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: DARK APPARITIONS: no target unit provided")
            return False

        root = self._ec_resolve_unit_entry(unit)
        if root is None:
            return False
        if not self._is_carnival_of_excess_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: DARK APPARITIONS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: DARK APPARITIONS: not opponent's Fight phase")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: DARK APPARITIONS: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: DARK APPARITIONS: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: DARK APPARITIONS: target cannot be selected")
            return False
        if not self._ec_has_keyword(root, "DAEMONETTES"):
            logger.error("ERROR: DARK APPARITIONS: target must be a DAEMONETTES unit")
            return False
        if self._ec_is_within_engagement_range_of_enemy(root):
            logger.error("ERROR: DARK APPARITIONS: target must not be within Engagement Range of enemy units")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root):
            return False
        if not self._ec_place_unit_into_strategic_reserves(root):
            logger.error("ERROR: DARK APPARITIONS: failed to place target into Strategic Reserves")
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["dark_apparitions_temp_deep_strike"] = True
        sr["dark_apparitions_deep_strike_min_distance"] = 6.0
        sr["dark_apparitions_requires_emperors_children_within"] = 9.0
        sr["dark_apparitions_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["dark_apparitions_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["dark_apparitions_expires_phase"] = "MOVEMENT_PHASE"
        sr["dark_apparitions_source"] = str(stratagem.name or "DARK APPARITIONS")
        root.special_rules = sr
        ability_cache = getattr(root, "_ability_cache", None)
        if isinstance(ability_cache, dict):
            ability_cache.pop("deep_strike", None)

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DARK APPARITIONS: %s entered Strategic Reserves and may Deep Strike at >6\" in your next Movement phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_emperors_children_carnival_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "SUSTAINED BY AGONY":
            return self._use_carnival_sustained_by_agony(stratagem, **kwargs)
        if name_u == "SYCOPHANTIC SURGE":
            return self._use_carnival_sycophantic_surge(stratagem, **kwargs)
        if name_u == "UNCANNY REACTIONS":
            return self._use_carnival_uncanny_reactions(stratagem, **kwargs)
        if name_u == "ECSTATIC SLAUGHTER":
            return self._use_carnival_ecstatic_slaughter(stratagem, **kwargs)
        if name_u == "VIOLENT CRESCENDO":
            return self._use_carnival_violent_crescendo(stratagem, **kwargs)
        if name_u == "DARK APPARITIONS":
            return self._use_carnival_dark_apparitions(stratagem, **kwargs)
        return None

    def _court_effective_cp_cost(self, stratagem: Any, *, target_unit: Any = None, enemy_unit: Any = None) -> int:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_cost = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_cost):
            preview = apply_cost(stratagem, target_unit=target_unit, enemy_unit=enemy_unit) or {}
            cp_cost = int(preview.get("cost", cp_cost))
        return cp_cost

    def _court_spend_cp(self, stratagem: Any, *, target_unit: Any = None, enemy_unit: Any = None) -> bool:
        cp_cost = self._court_effective_cp_cost(stratagem, target_unit=target_unit, enemy_unit=enemy_unit)
        return bool(
            self.player.spend_command_points(
                cp_cost,
                reason=f"Stratagem: {stratagem.name}",
                source="stratagem",
            )
        )

    def _court_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())

    def _use_court_close_quarters_excruciation(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: CLOSE-QUARTERS EXCRUCIATION: no target unit provided")
            return False

        root = self._ec_root(unit)
        if root is None:
            return False
        if not self._is_court_of_the_phoenician_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: CLOSE-QUARTERS EXCRUCIATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: CLOSE-QUARTERS EXCRUCIATION: not your turn")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: CLOSE-QUARTERS EXCRUCIATION: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: CLOSE-QUARTERS EXCRUCIATION: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: CLOSE-QUARTERS EXCRUCIATION: target cannot be selected")
            return False
        if not self._is_emperors_children_unit(root):
            logger.error("ERROR: CLOSE-QUARTERS EXCRUCIATION: target must be an EMPEROR'S CHILDREN unit")
            return False
        if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: CLOSE-QUARTERS EXCRUCIATION: target has already been selected to shoot")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["court_close_quarters_excruciation_active"] = True
        sr["court_close_quarters_excruciation_expires_phase"] = "SHOOTING_PHASE"
        sr["court_close_quarters_excruciation_owner"] = str(getattr(self.player, "id", "") or "")
        sr["court_close_quarters_excruciation_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["court_close_quarters_excruciation_source"] = str(stratagem.name or "CLOSE-QUARTERS EXCRUCIATION")
        root.special_rules = sr

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CLOSE-QUARTERS EXCRUCIATION: %s gains +1S/+1AP on ranged attacks within 12\" this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_court_contemptuous_disregard(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "CONTEMPTUOUS DISREGARD":
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
            logger.error("ERROR: CONTEMPTUOUS DISREGARD: no target unit provided")
            return False

        root = self._ec_root(unit)
        if root is None:
            return False
        if not self._is_court_of_the_phoenician_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in ("shooting phase", "fight phase"):
            logger.error("ERROR: CONTEMPTUOUS DISREGARD: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: CONTEMPTUOUS DISREGARD: not opponent's phase")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: CONTEMPTUOUS DISREGARD: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: CONTEMPTUOUS DISREGARD: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: CONTEMPTUOUS DISREGARD: target cannot be selected")
            return False
        if not self._is_emperors_children_unit(root):
            logger.error("ERROR: CONTEMPTUOUS DISREGARD: target must be an EMPEROR'S CHILDREN unit")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root):
            return False

        entry = {
            "value": 1,
            "attack_type": "any",
            "expires_phase": self._phase_key_from_name(phase_name),
            "source": str(stratagem.name or "CONTEMPTUOUS DISREGARD"),
            "requires_strength_gt_toughness": True,
        }
        self._append_defensive_effect(root, "defensive_wound_mods", entry)

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CONTEMPTUOUS DISREGARD: %s gains conditional -1 to wound this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_court_euphoric_inspiration(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: EUPHORIC INSPIRATION: no target unit provided")
            return False

        root = self._ec_root(unit)
        if root is None:
            return False
        if not self._is_court_of_the_phoenician_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: EUPHORIC INSPIRATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: EUPHORIC INSPIRATION: not your turn")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: EUPHORIC INSPIRATION: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: EUPHORIC INSPIRATION: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: EUPHORIC INSPIRATION: target cannot be selected")
            return False
        if not self._is_emperors_children_daemon_unit(root):
            logger.error("ERROR: EUPHORIC INSPIRATION: target must be an EMPEROR'S CHILDREN DAEMON unit")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["court_euphoric_inspiration_aura_active"] = True
        sr["court_euphoric_inspiration_expires_phase"] = "CHARGE_PHASE"
        sr["court_euphoric_inspiration_owner"] = str(getattr(self.player, "id", "") or "")
        sr["court_euphoric_inspiration_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["court_euphoric_inspiration_source"] = str(stratagem.name or "EUPHORIC INSPIRATION")
        root.special_rules = sr

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: EUPHORIC INSPIRATION: %s grants a 6\" charge re-roll aura this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_court_prideful_superiority(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PRIDEFUL SUPERIORITY: no target unit provided")
            return False

        root = self._ec_root(unit)
        if root is None:
            return False
        if not self._is_court_of_the_phoenician_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: PRIDEFUL SUPERIORITY: wrong phase")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: PRIDEFUL SUPERIORITY: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: PRIDEFUL SUPERIORITY: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: PRIDEFUL SUPERIORITY: target cannot be selected")
            return False
        if not self._is_emperors_children_unit(root):
            logger.error("ERROR: PRIDEFUL SUPERIORITY: target must be an EMPEROR'S CHILDREN unit")
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: PRIDEFUL SUPERIORITY: target has already fought this phase")
            return False
        fight_mgr = getattr(self.game, "fight_phase_manager", None) if self.game is not None else None
        fought_units = list(getattr(fight_mgr, "fought_units", []) or []) if fight_mgr is not None else []
        if root in fought_units:
            logger.error("ERROR: PRIDEFUL SUPERIORITY: target has already fought this phase")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["court_prideful_superiority_active"] = True
        sr["court_prideful_superiority_expires_phase"] = "FIGHT_PHASE"
        sr["court_prideful_superiority_owner"] = str(getattr(self.player, "id", "") or "")
        sr["court_prideful_superiority_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["court_prideful_superiority_source"] = str(stratagem.name or "PRIDEFUL SUPERIORITY")
        root.special_rules = sr

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PRIDEFUL SUPERIORITY: %s can re-roll Hit and Wound rolls vs CHARACTER targets this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_court_sinuous_breach(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SINUOUS BREACH: no target unit provided")
            return False

        root = self._ec_root(unit)
        if root is None:
            return False
        if not self._is_court_of_the_phoenician_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in ("movement phase", "charge phase"):
            logger.error("ERROR: SINUOUS BREACH: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SINUOUS BREACH: not your turn")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: SINUOUS BREACH: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: SINUOUS BREACH: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: SINUOUS BREACH: target cannot be selected")
            return False
        if not self._is_emperors_children_daemon_unit(root):
            logger.error("ERROR: SINUOUS BREACH: target must be an EMPEROR'S CHILDREN DAEMON unit")
            return False
        if phase_name == "movement phase" and bool(getattr(getattr(root, "round_state", None), "moved_this_round", False)):
            logger.error("ERROR: SINUOUS BREACH: target has already been selected to move this phase")
            return False
        if phase_name == "charge phase" and bool(getattr(getattr(root, "round_state", None), "attempted_charge_this_round", False)):
            logger.error("ERROR: SINUOUS BREACH: target has already been selected to charge this phase")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root):
            return False

        move_types = {"move", "advance"} if phase_name == "movement phase" else {"charge"}
        expires_phase = "MOVEMENT_PHASE" if phase_name == "movement phase" else "CHARGE_PHASE"

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
            sr["court_sinuous_breach_added_phase_move_terrain_only_types"] = sorted(added)
        sr["court_sinuous_breach_active"] = True
        sr["court_sinuous_breach_expires_phase"] = str(expires_phase)
        sr["court_sinuous_breach_owner"] = str(getattr(self.player, "id", "") or "")
        sr["court_sinuous_breach_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["court_sinuous_breach_source"] = str(stratagem.name or "SINUOUS BREACH")
        root.special_rules = sr

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SINUOUS BREACH: %s can move through terrain this phase (%s).",
            getattr(root, "name", "Unit"),
            "Normal/Advance" if phase_name == "movement phase" else "Charge",
        )
        return True

    def _court_closest_non_aircraft_enemy(self, unit: Any) -> Any:
        root = self._ec_root(unit)
        if root is None or self.game is None:
            return None
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return None

        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return None

        closest = None
        closest_dist = None
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._ec_root(enemy)
            if enemy_root is None:
                continue
            if not self._ec_is_alive(enemy_root):
                continue
            if not bool(getattr(enemy_root, "deployed", False)):
                continue
            if self._ec_has_keyword(enemy_root, "AIRCRAFT"):
                continue
            get_dist = getattr(game_map, "get_distance_between_units", None)
            if not callable(get_dist):
                continue
            try:
                distance = float(get_dist(root, enemy_root))
            except (TypeError, ValueError):
                continue
            if closest_dist is None or distance < closest_dist:
                closest_dist = distance
                closest = enemy_root
        return closest

    def _use_court_catalytic_stimulus(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("attacker_unit")
        candidates = list(kwargs.get("candidates") or [])
        from_pending = False
        lost_wounds = bool(kwargs.get("lost_wounds", False))
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "CATALYTIC STIMULUS":
                    continue
                from_pending = True
                unit = reaction.get("unit") or reaction.get("target_unit")
                enemy_unit = enemy_unit or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                lost_wounds = bool(reaction.get("lost_wounds", False)) or lost_wounds
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: CATALYTIC STIMULUS: no target unit provided")
            return False

        root = self._ec_root(unit)
        enemy_root = self._ec_root(enemy_unit)
        if root is None:
            return False
        if not self._is_court_of_the_phoenician_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: CATALYTIC STIMULUS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: CATALYTIC STIMULUS: not opponent's Shooting phase")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: CATALYTIC STIMULUS: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: CATALYTIC STIMULUS: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: CATALYTIC STIMULUS: target cannot be selected")
            return False
        if not self._is_emperors_children_unit(root):
            logger.error("ERROR: CATALYTIC STIMULUS: target must be an EMPEROR'S CHILDREN unit")
            return False
        if enemy_root is not None and self._ec_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: CATALYTIC STIMULUS: attacker is not enemy")
            return False
        if not from_pending and not lost_wounds:
            logger.error("ERROR: CATALYTIC STIMULUS: missing "
                         "lost-wounds trigger context")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root, enemy_unit=enemy_root):
            return False

        max_distance = kwargs.get("max_distance")
        if max_distance is None:
            max_distance = int(dice_module.get_roll("D6") or 0)
        try:
            max_distance = int(max_distance or 0)
        except (TypeError, ValueError):
            max_distance = 0
        if max_distance <= 0:
            logger.error("ERROR: CATALYTIC STIMULUS: movement distance roll failed")
            return False

        closest_enemy = self._court_closest_non_aircraft_enemy(root)
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if callable(queue_move):
            queue_move(
                player=self.player,
                unit=root,
                max_distance=int(max_distance),
                kind="catalytic_stimulus",
                movement_type="reactive",
                source=stratagem.name,
                attacker_unit=closest_enemy or enemy_root,
                allow_engagement_range=True,
            )

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CATALYTIC STIMULUS: %s can make a Stimulus move up to %d\".",
            getattr(root, "name", "Unit"),
            int(max_distance),
        )
        return True

    def _use_coterie_martial_perfection(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        from_pending = False
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "MARTIAL PERFECTION":
                    continue
                from_pending = True
                unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                kwargs.setdefault("fight_unit_selected", reaction.get("fight_unit_selected"))
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: MARTIAL PERFECTION: no target unit provided")
            return False

        root = self._ec_root(unit)
        if root is None:
            return False
        if not self._is_coterie_of_the_conceited_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: MARTIAL PERFECTION: wrong phase")
            return False
        trigger_name = str(kwargs.get("trigger", "") or "").strip().lower()
        trigger_flag = bool(kwargs.get("fight_unit_selected", False))
        if not from_pending and not trigger_flag and trigger_name not in {"fight_unit_selected", "fight_unit"}:
            logger.error("ERROR: MARTIAL PERFECTION: missing fight-unit-selected trigger context")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: MARTIAL PERFECTION: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: MARTIAL PERFECTION: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: MARTIAL PERFECTION: target cannot be selected")
            return False
        if not self._is_emperors_children_unit(root):
            logger.error("ERROR: MARTIAL PERFECTION: target must be an EMPEROR'S CHILDREN unit")
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: MARTIAL PERFECTION: target has already fought this phase")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["coterie_martial_perfection_active"] = True
        sr["coterie_martial_perfection_expires_phase"] = "FIGHT_PHASE"
        sr["coterie_martial_perfection_owner"] = str(getattr(self.player, "id", "") or "")
        sr["coterie_martial_perfection_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["coterie_martial_perfection_source"] = str(stratagem.name or "MARTIAL PERFECTION")
        root.special_rules = sr

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MARTIAL PERFECTION: %s can re-roll Hit rolls this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_coterie_unshakeable_opponents(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: UNSHAKEABLE OPPONENTS: no target unit provided")
            return False

        root = self._ec_root(unit)
        if root is None:
            return False
        if not self._is_coterie_of_the_conceited_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: UNSHAKEABLE OPPONENTS: wrong phase")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: UNSHAKEABLE OPPONENTS: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: UNSHAKEABLE OPPONENTS: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: UNSHAKEABLE OPPONENTS: target cannot be selected")
            return False
        if not self._is_emperors_children_unit(root):
            logger.error("ERROR: UNSHAKEABLE OPPONENTS: target must be an EMPEROR'S CHILDREN unit")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root):
            return False

        current_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["coterie_unshakeable_opponents_active"] = True
        sr["coterie_unshakeable_opponents_expires_phase"] = "FIGHT_PHASE"
        sr["coterie_unshakeable_opponents_turn_owner"] = str(getattr(current_player, "id", "") or "")
        sr["coterie_unshakeable_opponents_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["coterie_unshakeable_opponents_source"] = str(stratagem.name or "UNSHAKEABLE OPPONENTS")
        root.special_rules = sr

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: UNSHAKEABLE OPPONENTS: %s can ignore BS/WS/Hit/Wound modifiers until end of turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_coterie_protection_of_the_dark_prince(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        from_pending = False
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "PROTECTION OF THE DARK PRINCE":
                    continue
                from_pending = True
                unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                kwargs.setdefault("attack_allocated", reaction.get("attack_allocated"))
                kwargs.setdefault("mortal_wound_allocated", reaction.get("mortal_wound_allocated"))
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PROTECTION OF THE DARK PRINCE: no target unit provided")
            return False

        root = self._ec_root(unit)
        if root is None:
            return False
        if not self._is_coterie_of_the_conceited_detachment():
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: PROTECTION OF THE DARK PRINCE: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: PROTECTION OF THE DARK PRINCE: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: PROTECTION OF THE DARK PRINCE: target cannot be selected")
            return False
        if not self._is_emperors_children_unit(root):
            logger.error("ERROR: PROTECTION OF THE DARK PRINCE: target must be an EMPEROR'S CHILDREN unit")
            return False
        trigger_name = str(kwargs.get("trigger", "") or "").strip().lower()
        has_attack_trigger = bool(kwargs.get("attack_allocated", False))
        has_mortal_trigger = bool(kwargs.get("mortal_wound_allocated", False))
        if (
            not from_pending
            and not has_attack_trigger
            and not has_mortal_trigger
            and trigger_name not in {"attack_allocated", "mortal_wound_allocated"}
        ):
            logger.error("ERROR: PROTECTION OF THE DARK PRINCE: missing allocation trigger context")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root):
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "")
        phase_key = str(self._phase_key_from_name(phase_name) or "").strip().upper()

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        entries = list(sr.get("bearer_unit_fnp") or [])
        keep: list[Any] = []
        for entry in entries:
            if not isinstance(entry, dict):
                keep.append(entry)
                continue
            if str(entry.get("source_key", "") or "") == "coterie_protection_dark_prince":
                continue
            keep.append(entry)
        base_entry = {
            "value": 6,
            "condition": None,
            "source": str(stratagem.name or "PROTECTION OF THE DARK PRINCE"),
            "source_key": "coterie_protection_dark_prince",
            "expires_phase": phase_key,
        }
        mortal_entry = {
            "value": 4,
            "condition": "against mortal wounds",
            "source": str(stratagem.name or "PROTECTION OF THE DARK PRINCE"),
            "source_key": "coterie_protection_dark_prince",
            "expires_phase": phase_key,
        }
        keep.append(base_entry)
        keep.append(mortal_entry)
        sr["bearer_unit_fnp"] = keep
        sr["coterie_protection_dark_prince_active"] = True
        sr["coterie_protection_dark_prince_expires_phase"] = phase_key
        sr["coterie_protection_dark_prince_source"] = str(stratagem.name or "PROTECTION OF THE DARK PRINCE")
        root.special_rules = sr

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PROTECTION OF THE DARK PRINCE: %s gains Feel No Pain 6+ (4+ vs mortal wounds) this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_coterie_embrace_the_pain(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "EMBRACE THE PAIN":
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
            logger.error("ERROR: EMBRACE THE PAIN: no target unit provided")
            return False

        root = self._ec_root(unit)
        if root is None:
            return False
        if not self._is_coterie_of_the_conceited_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: EMBRACE THE PAIN: wrong phase")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: EMBRACE THE PAIN: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: EMBRACE THE PAIN: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: EMBRACE THE PAIN: target cannot be selected")
            return False
        if not self._is_emperors_children_infantry_unit(root):
            logger.error("ERROR: EMBRACE THE PAIN: target must be an EMPEROR'S CHILDREN INFANTRY unit")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["suffering_and_sacrifice_active"] = True
        sr["suffering_and_sacrifice_expires_phase"] = "FIGHT_PHASE"
        sr["suffering_and_sacrifice_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["suffering_and_sacrifice_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["suffering_and_sacrifice_source"] = str(stratagem.name or "EMBRACE THE PAIN")
        root.special_rules = sr

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: EMBRACE THE PAIN: enemy units in Engagement Range must target %s this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_mercurial_capricious_reactions(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "CAPRICIOUS REACTIONS":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                attacking_unit = attacking_unit or reaction.get("attacking_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: CAPRICIOUS REACTIONS: no target unit provided")
            return False

        root = self._ec_root(unit)
        attacker_root = self._ec_root(attacking_unit)
        if root is None:
            return False
        if not self._is_mercurial_host_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: CAPRICIOUS REACTIONS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: CAPRICIOUS REACTIONS: not opponent's Shooting phase")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: CAPRICIOUS REACTIONS: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: CAPRICIOUS REACTIONS: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: CAPRICIOUS REACTIONS: target cannot be selected")
            return False
        if not self._is_emperors_children_unit(root):
            logger.error("ERROR: CAPRICIOUS REACTIONS: target must be an EMPEROR'S CHILDREN unit")
            return False
        if attacker_root is not None and self._ec_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: CAPRICIOUS REACTIONS: attacker is not enemy")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root, enemy_unit=attacker_root):
            return False

        entry = {
            "value": 1,
            "attack_type": "any",
            "expires_phase": "SHOOTING_PHASE",
            "source": str(stratagem.name or "CAPRICIOUS REACTIONS"),
        }
        self._append_defensive_effect(root, "defensive_hit_mods", entry)

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CAPRICIOUS REACTIONS: %s gains -1 to be hit this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_mercurial_combat_stimms(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "COMBAT STIMMS":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                attacking_unit = attacking_unit or reaction.get("attacking_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: COMBAT STIMMS: no target unit provided")
            return False

        root = self._ec_root(unit)
        attacker_root = self._ec_root(attacking_unit)
        if root is None:
            return False
        if not self._is_mercurial_host_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: COMBAT STIMMS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: COMBAT STIMMS: not opponent's Fight phase")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: COMBAT STIMMS: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: COMBAT STIMMS: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: COMBAT STIMMS: target cannot be selected")
            return False
        if not self._is_emperors_children_infantry_unit(root):
            logger.error("ERROR: COMBAT STIMMS: target must be an EMPEROR'S CHILDREN INFANTRY unit")
            return False
        if attacker_root is not None and self._ec_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: COMBAT STIMMS: attacker is not enemy")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root, enemy_unit=attacker_root):
            return False

        entry = {
            "value": 1,
            "attack_type": "any",
            "expires_phase": "FIGHT_PHASE",
            "source": str(stratagem.name or "COMBAT STIMMS"),
        }
        self._append_defensive_effect(root, "defensive_wound_mods", entry)

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: COMBAT STIMMS: %s gains -1 to be wounded this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_mercurial_violent_excess(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: VIOLENT EXCESS: no target unit provided")
            return False

        root = self._ec_root(unit)
        if root is None:
            return False
        if not self._is_mercurial_host_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: VIOLENT EXCESS: wrong phase")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: VIOLENT EXCESS: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: VIOLENT EXCESS: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: VIOLENT EXCESS: target cannot be selected")
            return False
        if not self._is_emperors_children_unit(root):
            logger.error("ERROR: VIOLENT EXCESS: target must be an EMPEROR'S CHILDREN unit")
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: VIOLENT EXCESS: target has already fought this phase")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        current_val = int(sr.get("bearer_unit_sustained_hits_value_melee", 0) or 0)
        added = current_val < 1
        if added:
            sr["bearer_unit_sustained_hits_value_melee"] = 1
        sr["mercurial_violent_excess_active"] = True
        sr["mercurial_violent_excess_expires_phase"] = "FIGHT_PHASE"
        sr["mercurial_violent_excess_owner"] = str(getattr(self.player, "id", "") or "")
        sr["mercurial_violent_excess_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["mercurial_violent_excess_source"] = str(stratagem.name or "VIOLENT EXCESS")
        sr["mercurial_violent_excess_added_sustained_melee"] = bool(added)
        sr["mercurial_violent_excess_prev_sustained_melee"] = int(current_val)
        root.special_rules = sr

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: VIOLENT EXCESS: %s gains Sustained Hits 1 for melee weapons this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_mercurial_honour_the_prince(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: HONOUR THE PRINCE: no target unit provided")
            return False

        root = self._ec_root(unit)
        if root is None:
            return False
        if not self._is_mercurial_host_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: HONOUR THE PRINCE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: HONOUR THE PRINCE: not your turn")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: HONOUR THE PRINCE: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: HONOUR THE PRINCE: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: HONOUR THE PRINCE: target cannot be selected")
            return False
        if not self._is_emperors_children_infantry_unit(root):
            logger.error("ERROR: HONOUR THE PRINCE: target must be an EMPEROR'S CHILDREN INFANTRY unit")
            return False
        if bool(getattr(getattr(root, "round_state", None), "moved_this_round", False)):
            logger.error("ERROR: HONOUR THE PRINCE: target has already been selected to move this phase")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        effect_tag = "stratagem:honour_the_prince"
        effects = list(sr.get("advance_no_roll_effects", []) or [])
        effects = [
            entry
            for entry in effects
            if not (isinstance(entry, dict) and str(entry.get("tag", "") or "") == effect_tag)
        ]
        effects.append(
            {
                "distance": 6,
                "source": str(stratagem.name or "HONOUR THE PRINCE"),
                "tag": effect_tag,
                "expires_phase": "MOVEMENT_PHASE",
            }
        )
        sr["advance_no_roll_effects"] = effects
        sr["mercurial_honour_the_prince_active"] = True
        sr["mercurial_honour_the_prince_expires_phase"] = "MOVEMENT_PHASE"
        sr["mercurial_honour_the_prince_owner"] = str(getattr(self.player, "id", "") or "")
        sr["mercurial_honour_the_prince_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["mercurial_honour_the_prince_source"] = str(stratagem.name or "HONOUR THE PRINCE")
        root.special_rules = sr

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: HONOUR THE PRINCE: %s adds 6\" to Move when it Advances this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_mercurial_dark_vigour(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("moving_unit")
        candidates = list(kwargs.get("candidates") or [])
        from_pending = False
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "DARK VIGOUR":
                    continue
                from_pending = True
                unit = reaction.get("unit") or reaction.get("target_unit")
                enemy_unit = enemy_unit or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                kwargs.setdefault("action", reaction.get("action"))
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: DARK VIGOUR: no target unit provided")
            return False

        root = self._ec_root(unit)
        enemy_root = self._ec_root(enemy_unit)
        if root is None:
            return False
        if not self._is_mercurial_host_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: DARK VIGOUR: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: DARK VIGOUR: not opponent's Movement phase")
            return False
        action_key = str(kwargs.get("action") or kwargs.get("trigger") or "").strip().lower()
        if action_key and action_key not in {"move", "advance", "fall_back"}:
            logger.error("ERROR: DARK VIGOUR: invalid trigger action")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: DARK VIGOUR: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: DARK VIGOUR: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: DARK VIGOUR: target cannot be selected")
            return False
        if not self._is_emperors_children_unit(root):
            logger.error("ERROR: DARK VIGOUR: target must be an EMPEROR'S CHILDREN unit")
            return False
        if self._ec_has_keyword(root, "BEAST") or self._ec_has_keyword(root, "BEASTS") or self._ec_has_keyword(root, "VEHICLE"):
            logger.error("ERROR: DARK VIGOUR: target cannot be a BEAST/BEASTS/VEHICLE unit")
            return False
        if enemy_root is None:
            logger.error("ERROR: DARK VIGOUR: missing enemy trigger unit")
            return False
        if self._ec_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: DARK VIGOUR: trigger unit is not enemy")
            return False
        if not self._ec_is_alive(enemy_root) or not self._ec_is_on_battlefield(enemy_root):
            return False
        dist = self._ec_distance_between_units(root, enemy_root)
        if dist is None or float(dist) > 9.0 + 1e-6:
            logger.error("ERROR: DARK VIGOUR: target must be within 9\" of the enemy unit")
            return False
        if not from_pending and not action_key:
            logger.error("ERROR: DARK VIGOUR: missing movement trigger context")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root, enemy_unit=enemy_root):
            return False

        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if callable(queue_move):
            queue_move(
                player=self.player,
                unit=root,
                max_distance=6,
                kind="dark_vigour",
                movement_type="reactive",
                source=stratagem.name,
                moving_unit=enemy_root,
            )

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DARK VIGOUR: %s can make a Normal move up to 6\".",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_mercurial_cruel_raiders(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "CRUEL RAIDERS":
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
            logger.error("ERROR: CRUEL RAIDERS: no target unit provided")
            return False

        root = self._ec_root(unit)
        if root is None:
            return False
        if not self._is_mercurial_host_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: CRUEL RAIDERS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: CRUEL RAIDERS: not opponent's Fight phase")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: CRUEL RAIDERS: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: CRUEL RAIDERS: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: CRUEL RAIDERS: target cannot be selected")
            return False
        if not self._is_emperors_children_unit(root):
            logger.error("ERROR: CRUEL RAIDERS: target must be an EMPEROR'S CHILDREN unit")
            return False
        if not self._unit_wholly_within_battlefield_edge_distance(root, 9.0):
            logger.error("ERROR: CRUEL RAIDERS: target must be wholly within 9\" of a battlefield edge")
            return False
        if self._ec_has_enemy_within_horizontal_distance(root, 3.0):
            logger.error("ERROR: CRUEL RAIDERS: target must not be within 3\" horizontally of enemy units")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root):
            return False
        if not self._ec_place_unit_into_strategic_reserves(root):
            return False

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CRUEL RAIDERS: %s placed into Strategic Reserves.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_rapid_dynamic_breakthrough(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: DYNAMIC BREAKTHROUGH: no target unit provided")
            return False
        root = self._ec_root(unit)
        if root is None:
            return False
        if not self._is_rapid_evisceration_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: DYNAMIC BREAKTHROUGH: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: DYNAMIC BREAKTHROUGH: not your Movement phase")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: DYNAMIC BREAKTHROUGH: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: DYNAMIC BREAKTHROUGH: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: DYNAMIC BREAKTHROUGH: target cannot be selected")
            return False
        if not self._is_emperors_children_unit(root) or not self._ec_has_keyword(root, "VEHICLE"):
            logger.error("ERROR: DYNAMIC BREAKTHROUGH: target must be an EMPEROR'S CHILDREN VEHICLE")
            return False
        if bool(getattr(getattr(root, "round_state", None), "moved_this_round", False)):
            logger.error("ERROR: DYNAMIC BREAKTHROUGH: target has already moved this phase")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        move_types = {"move", "advance", "fall_back"}
        engagement_types = {"move", "advance", "fall_back"}
        block_types = {"move", "advance", "fall_back"}

        current_move_types = set(sr.get("bearer_unit_phase_move_types") or [])
        added_move_types = sorted([t for t in sorted(move_types) if t not in current_move_types])
        if added_move_types:
            current_move_types.update(added_move_types)
            sr["bearer_unit_phase_move_types"] = sorted(current_move_types)
            sr["rapid_dynamic_breakthrough_added_phase_move_types"] = added_move_types

        current_engagement_types = set(sr.get("bearer_unit_phase_move_engagement_types") or [])
        added_engagement_types = sorted([t for t in sorted(engagement_types) if t not in current_engagement_types])
        if added_engagement_types:
            current_engagement_types.update(added_engagement_types)
            sr["bearer_unit_phase_move_engagement_types"] = sorted(current_engagement_types)
            sr["rapid_dynamic_breakthrough_added_phase_move_engagement_types"] = added_engagement_types

        current_block_types = set(sr.get("bearer_unit_phase_move_block_monster_vehicle_types") or [])
        added_block_types = sorted([t for t in sorted(block_types) if t not in current_block_types])
        if added_block_types:
            current_block_types.update(added_block_types)
            sr["bearer_unit_phase_move_block_monster_vehicle_types"] = sorted(current_block_types)
            sr["rapid_dynamic_breakthrough_added_phase_move_block_monster_vehicle_types"] = added_block_types

        if not bool(sr.get("bearer_unit_auto_pass_desperate_escape", False)):
            sr["rapid_dynamic_breakthrough_added_auto_pass_desperate_escape"] = True
        sr["bearer_unit_auto_pass_desperate_escape"] = True
        sr["rapid_dynamic_breakthrough_active"] = True
        sr["rapid_dynamic_breakthrough_expires_phase"] = "MOVEMENT_PHASE"
        sr["rapid_dynamic_breakthrough_owner"] = str(getattr(self.player, "id", "") or "")
        sr["rapid_dynamic_breakthrough_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["rapid_dynamic_breakthrough_source"] = str(stratagem.name or "DYNAMIC BREAKTHROUGH")
        root.special_rules = sr

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DYNAMIC BREAKTHROUGH: %s can move through enemy models and auto-pass Desperate Escape tests this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_rapid_ceaseless_onslaught(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: CEASELESS ONSLAUGHT: no target unit provided")
            return False
        root = self._ec_root(unit)
        if root is None:
            return False
        if not self._is_rapid_evisceration_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: CEASELESS ONSLAUGHT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: CEASELESS ONSLAUGHT: not your Charge phase")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: CEASELESS ONSLAUGHT: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: CEASELESS ONSLAUGHT: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: CEASELESS ONSLAUGHT: target cannot be selected")
            return False
        if not self._is_emperors_children_unit(root):
            logger.error("ERROR: CEASELESS ONSLAUGHT: target must be an EMPEROR'S CHILDREN unit")
            return False
        if bool(getattr(getattr(root, "round_state", None), "attempted_charge_this_round", False)):
            logger.error("ERROR: CEASELESS ONSLAUGHT: target has already attempted a charge this phase")
            return False

        round_state = getattr(root, "round_state", None)
        if not bool(getattr(round_state, "disembarked_this_round", False)):
            logger.error("ERROR: CEASELESS ONSLAUGHT: target did not disembark this turn")
            return False
        transport_id = str(getattr(round_state, "disembarked_from_transport_id", "") or "")
        if not transport_id:
            logger.error("ERROR: CEASELESS ONSLAUGHT: missing disembark transport context")
            return False
        transport_root = self._ec_root(self._resolve_unit_by_id(transport_id))
        if transport_root is None:
            logger.error("ERROR: CEASELESS ONSLAUGHT: transport context no longer available")
            return False
        if not self._ec_owned_by_player(transport_root, self.player):
            logger.error("ERROR: CEASELESS ONSLAUGHT: disembark transport is not friendly")
            return False
        if not self._ec_has_keyword(transport_root, "TRANSPORT"):
            logger.error("ERROR: CEASELESS ONSLAUGHT: disembark source is not a TRANSPORT")
            return False
        transport_state = getattr(transport_root, "round_state", None)
        moved = bool(getattr(transport_state, "moved_this_round", False))
        remained = bool(getattr(transport_state, "remained_stationary_this_round", False))
        advanced = bool(getattr(transport_state, "advanced_this_round", False))
        fell_back = bool(getattr(transport_state, "fell_back_this_round", False))
        if not moved or remained or advanced or fell_back:
            logger.error("ERROR: CEASELESS ONSLAUGHT: transport must have made a Normal move this turn")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root):
            return False

        setattr(round_state, "disembarked_cannot_charge", False)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["rapid_ceaseless_onslaught_active"] = True
        sr["rapid_ceaseless_onslaught_expires_phase"] = "CHARGE_PHASE"
        sr["rapid_ceaseless_onslaught_owner"] = str(getattr(self.player, "id", "") or "")
        sr["rapid_ceaseless_onslaught_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["rapid_ceaseless_onslaught_source"] = str(stratagem.name or "CEASELESS ONSLAUGHT")
        root.special_rules = sr

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CEASELESS ONSLAUGHT: %s can declare a charge this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_rapid_reactive_disembarkation(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("transport_unit") or kwargs.get("transport")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "REACTIVE DISEMBARKATION":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                attacking_unit = attacking_unit or reaction.get("attacking_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: REACTIVE DISEMBARKATION: no target transport provided")
            return False
        root = self._ec_root(unit)
        attacker_root = self._ec_root(attacking_unit)
        if root is None:
            return False
        if not self._is_rapid_evisceration_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: REACTIVE DISEMBARKATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: REACTIVE DISEMBARKATION: not opponent's Shooting phase")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: REACTIVE DISEMBARKATION: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: REACTIVE DISEMBARKATION: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: REACTIVE DISEMBARKATION: target cannot be selected")
            return False
        if not self._is_emperors_children_unit(root) or not self._ec_has_keyword(root, "TRANSPORT"):
            logger.error("ERROR: REACTIVE DISEMBARKATION: target must be an EMPEROR'S CHILDREN TRANSPORT")
            return False
        if attacker_root is not None and self._ec_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: REACTIVE DISEMBARKATION: attacker is not enemy")
            return False
        embarked_units = self._ec_embarked_units(root, require_emperors_children=True)
        if not embarked_units:
            logger.error("ERROR: REACTIVE DISEMBARKATION: no embarked EMPEROR'S CHILDREN units")
            return False

        queue_fn = getattr(self.game, "_queue_transport_reactive_disembark_decisions", None) if self.game is not None else None
        if not callable(queue_fn):
            logger.error("ERROR: REACTIVE DISEMBARKATION: reactive disembark decision queue unavailable")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root, enemy_unit=attacker_root):
            return False
        requests = list(
            queue_fn(
                player=self.player,
                transport=root,
                enemy_unit=attacker_root,
                ability={"name": str(stratagem.name or "REACTIVE DISEMBARKATION"), "range": 6},
                trigger="shooting_targets_selected",
                max_units=1,
            )
            or []
        )
        if not requests:
            logger.error("ERROR: REACTIVE DISEMBARKATION: no disembark decision was queued")
            return False

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: REACTIVE DISEMBARKATION: queued disembark decision for one embarked unit in %s.",
            getattr(root, "name", "Transport"),
        )
        return True

    def _use_rapid_advance_and_claim(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("transport_unit") or kwargs.get("transport")
        objective = kwargs.get("objective") or kwargs.get("objective_marker")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "ADVANCE AND CLAIM":
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
            logger.error("ERROR: ADVANCE AND CLAIM: no target transport provided")
            return False
        root = self._ec_root(unit)
        if root is None:
            return False
        if not self._is_rapid_evisceration_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: ADVANCE AND CLAIM: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: ADVANCE AND CLAIM: not your Command phase")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: ADVANCE AND CLAIM: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: ADVANCE AND CLAIM: target transport is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: ADVANCE AND CLAIM: target cannot be selected")
            return False
        if not self._is_emperors_children_unit(root) or not self._ec_has_keyword(root, "TRANSPORT"):
            logger.error("ERROR: ADVANCE AND CLAIM: target must be an EMPEROR'S CHILDREN TRANSPORT")
            return False
        if self._ec_is_battle_shocked(root):
            logger.error("ERROR: ADVANCE AND CLAIM: target transport is Battle-shocked")
            return False
        embarked = self._ec_embarked_units(root, require_emperors_children=True)
        has_tormentors = any(
            self._ec_has_keyword(passenger, "TORMENTORS") and not self._ec_is_battle_shocked(passenger)
            for passenger in embarked
        )
        if not has_tormentors:
            logger.error("ERROR: ADVANCE AND CLAIM: no eligible embarked TORMENTORS unit")
            return False

        objective_candidates = list(kwargs.get("objective_candidates") or [])
        mapping = kwargs.get("objective_candidates_by_unit")
        if not objective_candidates and hasattr(mapping, "get"):
            objective_candidates = list(mapping.get(root) or [])
        if not objective_candidates:
            objective_candidates = self._ec_rapid_advance_and_claim_objective_candidates(root)
        if objective is None and len(objective_candidates) == 1:
            objective = objective_candidates[0]
        if objective is None:
            logger.error("ERROR: ADVANCE AND CLAIM: no objective marker selected")
            return False
        if objective_candidates and objective not in objective_candidates:
            logger.error("ERROR: ADVANCE AND CLAIM: selected objective marker is not eligible")
            return False
        loc = getattr(objective, "location", None)
        if loc is None:
            logger.error("ERROR: ADVANCE AND CLAIM: objective has no location")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root):
            return False
        set_sticky = getattr(loc, "set_sticky_control", None)
        if callable(set_sticky):
            set_sticky(self.player, source="advance_and_claim")
        else:
            loc.sticky_controller = self.player
            loc.sticky_source = "advance_and_claim"
            loc.controlling_player = self.player

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: ADVANCE AND CLAIM: objective remains under your control until sticky control is broken.")
        return True

    def _use_rapid_onto_the_next(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        transport_unit = kwargs.get("transport_unit") or kwargs.get("transport")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "ONTO THE NEXT":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if transport_unit is None:
                    transport_unit = reaction.get("transport_unit") or reaction.get("transport")
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: ONTO THE NEXT: no target unit provided")
            return False
        root = self._ec_root(unit)
        if root is None:
            return False
        if not self._is_rapid_evisceration_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: ONTO THE NEXT: wrong phase")
            return False
        if candidates and not self._ec_unit_in_candidates(root, candidates):
            logger.error("ERROR: ONTO THE NEXT: target is not currently eligible")
            return False
        if not self._ec_owned_by_player(root, self.player):
            logger.error("ERROR: ONTO THE NEXT: target unit is not yours")
            return False
        if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: ONTO THE NEXT: target cannot be selected")
            return False
        if not self._is_emperors_children_unit(root):
            logger.error("ERROR: ONTO THE NEXT: target must be an EMPEROR'S CHILDREN unit")
            return False

        destroyed_ids = self._ec_rapid_destroyed_enemy_this_phase()
        if candidates:
            eligible = True
        else:
            eligible = self._ec_sort_key(root) in destroyed_ids
        if not eligible:
            logger.error("ERROR: ONTO THE NEXT: target has not destroyed an enemy unit this phase")
            return False

        transport_candidates = []
        mapping = kwargs.get("transport_candidates_by_unit")
        if hasattr(mapping, "get"):
            transport_candidates = [self._ec_root(t) for t in list(mapping.get(root) or []) if self._ec_root(t) is not None]
        if not transport_candidates:
            transport_candidates = self._ec_rapid_onto_next_transport_candidates(root)
        if transport_unit is None and len(transport_candidates) == 1:
            transport_unit = transport_candidates[0]
        if transport_unit is None:
            logger.error("ERROR: ONTO THE NEXT: no target transport provided")
            return False
        transport_root = self._ec_root(transport_unit)
        if transport_root is None:
            return False
        if transport_candidates and not self._ec_unit_in_candidates(transport_root, transport_candidates):
            logger.error("ERROR: ONTO THE NEXT: selected transport is not eligible")
            return False
        if not self._ec_owned_by_player(transport_root, self.player):
            logger.error("ERROR: ONTO THE NEXT: transport is not yours")
            return False
        if not self._ec_is_alive(transport_root) or not self._ec_is_on_battlefield(transport_root):
            return False
        if not self._ec_has_keyword(transport_root, "TRANSPORT"):
            logger.error("ERROR: ONTO THE NEXT: selected unit is not a TRANSPORT")
            return False
        can_transport = getattr(transport_root, "can_transport", None)
        if not callable(can_transport) or not bool(can_transport(root)):
            logger.error("ERROR: ONTO THE NEXT: selected transport cannot embark the unit")
            return False
        if not unit_wholly_within_range_of_unit(
            transport_root,
            root,
            6.0,
            use_attached_aggregate=True,
        ):
            logger.error("ERROR: ONTO THE NEXT: target unit must be wholly within 6\" of the transport")
            return False
        if not self._court_spend_cp(stratagem, target_unit=root, enemy_unit=transport_root):
            return False
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if not bool(transport_root.add_passenger(root, game_map=game_map)):
            logger.error("ERROR: ONTO THE NEXT: embark failed")
            return False

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ONTO THE NEXT: %s embarked within %s.",
            getattr(root, "name", "Unit"),
            getattr(transport_root, "name", "Transport"),
        )
        return True

    def _use_rapid_outflanking_strike(self, stratagem: Any, **kwargs) -> bool:
        selected = (
            kwargs.get("units")
            or kwargs.get("target_units")
            or kwargs.get("selected_units")
            or kwargs.get("unit")
            or kwargs.get("target_unit")
        )
        candidates = list(kwargs.get("candidates") or [])
        if selected is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "OUTFLANKING STRIKE":
                    continue
                selected = (
                    reaction.get("units")
                    or reaction.get("target_units")
                    or reaction.get("selected_units")
                    or reaction.get("unit")
                    or reaction.get("target_unit")
                )
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if selected is None and len(candidates) == 1:
            selected = [candidates[0]]
        if selected is None:
            logger.error("ERROR: OUTFLANKING STRIKE: no target transport provided")
            return False
        if not isinstance(selected, (list, tuple)):
            selected = [selected]

        resolved: list[Any] = []
        seen: set[str] = set()
        for entry in list(selected or []):
            root = self._ec_root(self._resolve_unit_by_id(entry) if isinstance(entry, str) else entry)
            if root is None:
                continue
            uid = self._ec_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            resolved.append(root)
        if not resolved:
            logger.error("ERROR: OUTFLANKING STRIKE: no valid target transports")
            return False
        if len(resolved) > 2:
            logger.error("ERROR: OUTFLANKING STRIKE: cannot target more than two transports")
            return False

        if not self._is_rapid_evisceration_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: OUTFLANKING STRIKE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: OUTFLANKING STRIKE: not opponent's Fight phase")
            return False
        if candidates and not all(self._ec_unit_in_candidates(root, candidates) for root in resolved):
            logger.error("ERROR: OUTFLANKING STRIKE: one or more targets are not currently eligible")
            return False
        if len(resolved) > 1:
            if not all(self._ec_has_keyword(root, "DEDICATED TRANSPORT") for root in resolved):
                logger.error("ERROR: OUTFLANKING STRIKE: selecting two targets requires DEDICATED TRANSPORT units")
                return False

        for root in list(resolved):
            if not self._ec_owned_by_player(root, self.player):
                logger.error("ERROR: OUTFLANKING STRIKE: one or more targets are not yours")
                return False
            if not self._ec_is_alive(root) or not self._ec_is_on_battlefield(root):
                return False
            if self._unit_cannot_be_target_of_stratagem(root):
                logger.error("ERROR: OUTFLANKING STRIKE: one or more targets cannot be selected")
                return False
            if not self._is_emperors_children_unit(root) or not self._ec_has_keyword(root, "TRANSPORT"):
                logger.error("ERROR: OUTFLANKING STRIKE: targets must be EMPEROR'S CHILDREN TRANSPORT units")
                return False
            if not self._unit_wholly_within_battlefield_edge_distance(root, 9.0):
                logger.error("ERROR: OUTFLANKING STRIKE: each target must be wholly within 9\" of a battlefield edge")
                return False
        if not self._court_spend_cp(stratagem, target_unit=resolved[0]):
            return False
        for root in list(resolved):
            if not self._ec_place_unit_into_strategic_reserves(root):
                logger.error("ERROR: OUTFLANKING STRIKE: failed to place target into Strategic Reserves")
                return False

        self._court_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: OUTFLANKING STRIKE: selected transport units were placed into Strategic Reserves.")
        return True

    def _cleanup_emperors_children_court_phase_end_effects(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_name:
            return
        if phase_name == "SHOOTING_PHASE":
            self._ec_catalytic_wounds_before().clear()

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return

        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ec_root(unit)
            if root is None:
                continue
            uid = self._ec_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)

            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue

            if phase_name == "SHOOTING_PHASE" and bool(sr.get("court_close_quarters_excruciation_active")):
                exp = str(sr.get("court_close_quarters_excruciation_expires_phase", "") or "").strip().upper()
                if not exp or exp == "SHOOTING_PHASE":
                    for key in (
                        "court_close_quarters_excruciation_active",
                        "court_close_quarters_excruciation_expires_phase",
                        "court_close_quarters_excruciation_owner",
                        "court_close_quarters_excruciation_turn",
                        "court_close_quarters_excruciation_source",
                    ):
                        sr.pop(key, None)

            if phase_name == "FIGHT_PHASE" and bool(sr.get("court_prideful_superiority_active")):
                exp = str(sr.get("court_prideful_superiority_expires_phase", "") or "").strip().upper()
                if not exp or exp == "FIGHT_PHASE":
                    for key in (
                        "court_prideful_superiority_active",
                        "court_prideful_superiority_expires_phase",
                        "court_prideful_superiority_owner",
                        "court_prideful_superiority_turn",
                        "court_prideful_superiority_source",
                    ):
                        sr.pop(key, None)

            if phase_name == "CHARGE_PHASE" and bool(sr.get("court_euphoric_inspiration_aura_active")):
                exp = str(sr.get("court_euphoric_inspiration_expires_phase", "") or "").strip().upper()
                if not exp or exp == "CHARGE_PHASE":
                    for key in (
                        "court_euphoric_inspiration_aura_active",
                        "court_euphoric_inspiration_expires_phase",
                        "court_euphoric_inspiration_owner",
                        "court_euphoric_inspiration_turn",
                        "court_euphoric_inspiration_source",
                    ):
                        sr.pop(key, None)

            if phase_name in ("MOVEMENT_PHASE", "CHARGE_PHASE") and bool(sr.get("court_sinuous_breach_active")):
                exp = str(sr.get("court_sinuous_breach_expires_phase", "") or "").strip().upper()
                if not exp or exp == phase_name:
                    added = set(sr.get("court_sinuous_breach_added_phase_move_terrain_only_types") or [])
                    if added:
                        current = list(sr.get("bearer_unit_phase_move_terrain_only_types") or [])
                        kept = [move_type for move_type in current if move_type not in added]
                        if kept:
                            sr["bearer_unit_phase_move_terrain_only_types"] = kept
                        else:
                            sr.pop("bearer_unit_phase_move_terrain_only_types", None)
                    for key in (
                        "court_sinuous_breach_active",
                        "court_sinuous_breach_expires_phase",
                        "court_sinuous_breach_owner",
                        "court_sinuous_breach_turn",
                        "court_sinuous_breach_source",
                        "court_sinuous_breach_added_phase_move_terrain_only_types",
                    ):
                        sr.pop(key, None)

            if phase_name == "FIGHT_PHASE" and bool(sr.get("coterie_martial_perfection_active")):
                exp = str(sr.get("coterie_martial_perfection_expires_phase", "") or "").strip().upper()
                if not exp or exp == "FIGHT_PHASE":
                    for key in (
                        "coterie_martial_perfection_active",
                        "coterie_martial_perfection_expires_phase",
                        "coterie_martial_perfection_owner",
                        "coterie_martial_perfection_turn",
                        "coterie_martial_perfection_source",
                    ):
                        sr.pop(key, None)

            if bool(sr.get("coterie_protection_dark_prince_active")):
                exp = str(sr.get("coterie_protection_dark_prince_expires_phase", "") or "").strip().upper()
                if not exp or exp == phase_name:
                    entries = list(sr.get("bearer_unit_fnp") or [])
                    kept: list[Any] = []
                    for entry in entries:
                        if isinstance(entry, dict) and str(entry.get("source_key", "") or "") == "coterie_protection_dark_prince":
                            continue
                        kept.append(entry)
                    if kept:
                        sr["bearer_unit_fnp"] = kept
                    else:
                        sr.pop("bearer_unit_fnp", None)
                    for key in (
                        "coterie_protection_dark_prince_active",
                        "coterie_protection_dark_prince_expires_phase",
                        "coterie_protection_dark_prince_source",
                    ):
                        sr.pop(key, None)

            if phase_name == "FIGHT_PHASE" and bool(sr.get("coterie_unshakeable_opponents_active")):
                owner_id = str(sr.get("coterie_unshakeable_opponents_turn_owner", "") or "")
                if owner_id:
                    current_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
                    if str(getattr(current_player, "id", "") or "") != owner_id:
                        root.special_rules = sr
                        continue
                try:
                    effect_turn = int(sr.get("coterie_unshakeable_opponents_turn", 0) or 0)
                except Exception:
                    effect_turn = 0
                try:
                    current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
                except Exception:
                    current_turn = 0
                if effect_turn and current_turn and effect_turn != current_turn:
                    root.special_rules = sr
                    continue
                for key in (
                    "coterie_unshakeable_opponents_active",
                    "coterie_unshakeable_opponents_expires_phase",
                    "coterie_unshakeable_opponents_turn_owner",
                    "coterie_unshakeable_opponents_turn",
                    "coterie_unshakeable_opponents_source",
                ):
                    sr.pop(key, None)

            if phase_name == "FIGHT_PHASE" and bool(sr.get("suffering_and_sacrifice_active")):
                source = str(sr.get("suffering_and_sacrifice_source", "") or "").strip().upper()
                exp = str(sr.get("suffering_and_sacrifice_expires_phase", "") or "").strip().upper()
                if source == "EMBRACE THE PAIN" and (not exp or exp == "FIGHT_PHASE"):
                    for key in (
                        "suffering_and_sacrifice_active",
                        "suffering_and_sacrifice_expires_phase",
                        "suffering_and_sacrifice_turn_owner",
                        "suffering_and_sacrifice_turn",
                        "suffering_and_sacrifice_source",
                    ):
                        sr.pop(key, None)

            if phase_name == "MOVEMENT_PHASE" and bool(sr.get("mercurial_honour_the_prince_active")):
                exp = str(sr.get("mercurial_honour_the_prince_expires_phase", "") or "").strip().upper()
                if not exp or exp == "MOVEMENT_PHASE":
                    effects = list(sr.get("advance_no_roll_effects", []) or [])
                    kept = [
                        entry
                        for entry in effects
                        if not (
                            isinstance(entry, dict)
                            and str(entry.get("tag", "") or "") == "stratagem:honour_the_prince"
                        )
                    ]
                    if kept:
                        sr["advance_no_roll_effects"] = kept
                    else:
                        sr.pop("advance_no_roll_effects", None)
                    for key in (
                        "mercurial_honour_the_prince_active",
                        "mercurial_honour_the_prince_expires_phase",
                        "mercurial_honour_the_prince_owner",
                        "mercurial_honour_the_prince_turn",
                        "mercurial_honour_the_prince_source",
                    ):
                        sr.pop(key, None)

            if phase_name == "FIGHT_PHASE" and bool(sr.get("mercurial_violent_excess_active")):
                exp = str(sr.get("mercurial_violent_excess_expires_phase", "") or "").strip().upper()
                if not exp or exp == "FIGHT_PHASE":
                    if bool(sr.get("mercurial_violent_excess_added_sustained_melee")):
                        prev = int(sr.get("mercurial_violent_excess_prev_sustained_melee", 0) or 0)
                        if prev > 0:
                            sr["bearer_unit_sustained_hits_value_melee"] = int(prev)
                        else:
                            sr.pop("bearer_unit_sustained_hits_value_melee", None)
                    for key in (
                        "mercurial_violent_excess_active",
                        "mercurial_violent_excess_expires_phase",
                        "mercurial_violent_excess_owner",
                        "mercurial_violent_excess_turn",
                        "mercurial_violent_excess_source",
                        "mercurial_violent_excess_added_sustained_melee",
                        "mercurial_violent_excess_prev_sustained_melee",
                    ):
                        sr.pop(key, None)

            if phase_name == "MOVEMENT_PHASE" and bool(sr.get("rapid_dynamic_breakthrough_active")):
                exp = str(sr.get("rapid_dynamic_breakthrough_expires_phase", "") or "").strip().upper()
                if not exp or exp == "MOVEMENT_PHASE":
                    added = set(sr.get("rapid_dynamic_breakthrough_added_phase_move_types") or [])
                    if added:
                        current = list(sr.get("bearer_unit_phase_move_types") or [])
                        kept = [move_type for move_type in current if move_type not in added]
                        if kept:
                            sr["bearer_unit_phase_move_types"] = kept
                        else:
                            sr.pop("bearer_unit_phase_move_types", None)
                    added = set(sr.get("rapid_dynamic_breakthrough_added_phase_move_engagement_types") or [])
                    if added:
                        current = list(sr.get("bearer_unit_phase_move_engagement_types") or [])
                        kept = [move_type for move_type in current if move_type not in added]
                        if kept:
                            sr["bearer_unit_phase_move_engagement_types"] = kept
                        else:
                            sr.pop("bearer_unit_phase_move_engagement_types", None)
                    added = set(sr.get("rapid_dynamic_breakthrough_added_phase_move_block_monster_vehicle_types") or [])
                    if added:
                        current = list(sr.get("bearer_unit_phase_move_block_monster_vehicle_types") or [])
                        kept = [move_type for move_type in current if move_type not in added]
                        if kept:
                            sr["bearer_unit_phase_move_block_monster_vehicle_types"] = kept
                        else:
                            sr.pop("bearer_unit_phase_move_block_monster_vehicle_types", None)
                    if bool(sr.get("rapid_dynamic_breakthrough_added_auto_pass_desperate_escape")):
                        sr.pop("bearer_unit_auto_pass_desperate_escape", None)
                    for key in (
                        "rapid_dynamic_breakthrough_active",
                        "rapid_dynamic_breakthrough_expires_phase",
                        "rapid_dynamic_breakthrough_owner",
                        "rapid_dynamic_breakthrough_turn",
                        "rapid_dynamic_breakthrough_source",
                        "rapid_dynamic_breakthrough_added_phase_move_types",
                        "rapid_dynamic_breakthrough_added_phase_move_engagement_types",
                        "rapid_dynamic_breakthrough_added_phase_move_block_monster_vehicle_types",
                        "rapid_dynamic_breakthrough_added_auto_pass_desperate_escape",
                    ):
                        sr.pop(key, None)

            if phase_name == "CHARGE_PHASE" and bool(sr.get("rapid_ceaseless_onslaught_active")):
                exp = str(sr.get("rapid_ceaseless_onslaught_expires_phase", "") or "").strip().upper()
                if not exp or exp == "CHARGE_PHASE":
                    for key in (
                        "rapid_ceaseless_onslaught_active",
                        "rapid_ceaseless_onslaught_expires_phase",
                        "rapid_ceaseless_onslaught_owner",
                        "rapid_ceaseless_onslaught_turn",
                        "rapid_ceaseless_onslaught_source",
                    ):
                        sr.pop(key, None)

            if phase_name == "CHARGE_PHASE" and bool(sr.get("carnival_sycophantic_surge_active")):
                exp = str(sr.get("carnival_sycophantic_surge_expires_phase", "") or "").strip().upper()
                if not exp or exp == "CHARGE_PHASE":
                    owner_id = str(sr.get("carnival_sycophantic_surge_turn_owner", "") or "")
                    current_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
                    current_owner = str(getattr(current_player, "id", "") or "")
                    if not owner_id or not current_owner or owner_id == current_owner:
                        for key in (
                            "carnival_sycophantic_surge_active",
                            "carnival_sycophantic_surge_charge_after_advance",
                            "carnival_sycophantic_surge_charge_after_fall_back",
                            "carnival_sycophantic_surge_turn_owner",
                            "carnival_sycophantic_surge_turn",
                            "carnival_sycophantic_surge_expires_phase",
                            "carnival_sycophantic_surge_source",
                        ):
                            sr.pop(key, None)

            if phase_name == "FIGHT_PHASE" and bool(sr.get("carnival_violent_crescendo_active")):
                exp = str(sr.get("carnival_violent_crescendo_expires_phase", "") or "").strip().upper()
                if not exp or exp == "FIGHT_PHASE":
                    for key in (
                        "carnival_violent_crescendo_active",
                        "carnival_violent_crescendo_expires_phase",
                        "carnival_violent_crescendo_owner",
                        "carnival_violent_crescendo_turn",
                        "carnival_violent_crescendo_source",
                    ):
                        sr.pop(key, None)
                    source_name = str(sr.get("stratagem_choreographer_of_war_source", "") or "").strip().upper()
                    if source_name == "VIOLENT CRESCENDO":
                        sr.pop("stratagem_choreographer_of_war_source", None)
                        sr.pop("bearer_unit_pile_in_distance_override", None)
                        sr.pop("stratagem_consolidate_distance_override", None)
                        ability_cache = getattr(root, "_ability_cache", None)
                        if isinstance(ability_cache, dict):
                            ability_cache.pop("choreographer_of_war_source", None)

            if phase_name == "MOVEMENT_PHASE" and bool(sr.get("dark_apparitions_temp_deep_strike")):
                exp = str(sr.get("dark_apparitions_expires_phase", "") or "").strip().upper()
                if not exp or exp == "MOVEMENT_PHASE":
                    owner_id = str(sr.get("dark_apparitions_turn_owner", "") or "")
                    current_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
                    current_owner = str(getattr(current_player, "id", "") or "")
                    if not owner_id or (current_owner and owner_id == current_owner):
                        for key in (
                            "dark_apparitions_temp_deep_strike",
                            "dark_apparitions_deep_strike_min_distance",
                            "dark_apparitions_requires_emperors_children_within",
                            "dark_apparitions_turn_owner",
                            "dark_apparitions_turn",
                            "dark_apparitions_expires_phase",
                            "dark_apparitions_source",
                        ):
                            sr.pop(key, None)
                        ability_cache = getattr(root, "_ability_cache", None)
                        if isinstance(ability_cache, dict):
                            ability_cache.pop("deep_strike", None)

            if phase_name == "FIGHT_PHASE" and bool(sr.get("devoted_duellists_active")):
                exp = str(sr.get("devoted_duellists_expires_phase", "") or "").strip().upper()
                if not exp or exp == "FIGHT_PHASE":
                    for key in (
                        "devoted_duellists_active",
                        "devoted_duellists_expires_phase",
                        "devoted_duellists_owner",
                        "devoted_duellists_turn",
                        "devoted_duellists_source",
                        "devoted_duellists_target_unit_id",
                        "devoted_duellists_sustained_hits_value",
                    ):
                        sr.pop(key, None)

            if phase_name == "FIGHT_PHASE" and bool(sr.get("beautiful_death_active")):
                exp = str(sr.get("beautiful_death_expires_phase", "") or "").strip().upper()
                if not exp or exp == "FIGHT_PHASE":
                    for key in (
                        "beautiful_death_active",
                        "beautiful_death_expires_phase",
                        "beautiful_death_owner",
                        "beautiful_death_turn",
                        "beautiful_death_source",
                    ):
                        sr.pop(key, None)

            if phase_name in ("SHOOTING_PHASE", "FIGHT_PHASE") and bool(sr.get("heightened_jealousy_active")):
                exp = str(sr.get("heightened_jealousy_expires_phase", "") or "").strip().upper()
                if not exp or exp == phase_name:
                    for key in (
                        "heightened_jealousy_active",
                        "heightened_jealousy_expires_phase",
                        "heightened_jealousy_owner",
                        "heightened_jealousy_turn",
                        "heightened_jealousy_source",
                        "heightened_jealousy_favoured_unit_id",
                        "heightened_jealousy_strength_bonus",
                    ):
                        sr.pop(key, None)

            if phase_name == "SHOOTING_PHASE" and bool(sr.get("slaanesh_vengeful_surge_pending")):
                exp = str(sr.get("slaanesh_vengeful_surge_expires_phase", "") or "").strip().upper()
                if not exp or exp == "SHOOTING_PHASE":
                    for key in (
                        "slaanesh_vengeful_surge_pending",
                        "slaanesh_vengeful_surge_attacker_id",
                        "slaanesh_vengeful_surge_allow_reroll",
                        "slaanesh_vengeful_surge_source",
                        "slaanesh_vengeful_surge_owner",
                        "slaanesh_vengeful_surge_turn",
                        "slaanesh_vengeful_surge_expires_phase",
                    ):
                        sr.pop(key, None)

            if phase_name == "CHARGE_PHASE":
                exp = str(sr.get("slaanesh_refusal_to_be_outdone_expires_phase", "") or "").strip().upper()
                if (not exp or exp == "CHARGE_PHASE") and (
                    bool(sr.get("slaanesh_refusal_to_be_outdone_active"))
                    or isinstance(sr.get("charge_roll_modifiers"), list)
                ):
                    mods = list(sr.get("charge_roll_modifiers", []) or [])
                    kept = [
                        m
                        for m in mods
                        if not (
                            isinstance(m, dict)
                            and str(m.get("tag", "") or "") == "stratagem:refusal_to_be_outdone"
                        )
                    ]
                    if kept:
                        sr["charge_roll_modifiers"] = kept
                    else:
                        sr.pop("charge_roll_modifiers", None)
                    for key in (
                        "slaanesh_refusal_to_be_outdone_active",
                        "slaanesh_refusal_to_be_outdone_owner",
                        "slaanesh_refusal_to_be_outdone_turn",
                        "slaanesh_refusal_to_be_outdone_expires_phase",
                        "slaanesh_refusal_to_be_outdone_target_unit_id",
                        "slaanesh_refusal_to_be_outdone_source",
                    ):
                        sr.pop(key, None)

            root.special_rules = sr

    def _use_emperors_children_court_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "CLOSE-QUARTERS EXCRUCIATION":
            return self._use_court_close_quarters_excruciation(stratagem, **kwargs)
        if name_u == "CONTEMPTUOUS DISREGARD":
            return self._use_court_contemptuous_disregard(stratagem, **kwargs)
        if name_u == "EUPHORIC INSPIRATION":
            return self._use_court_euphoric_inspiration(stratagem, **kwargs)
        if name_u == "PRIDEFUL SUPERIORITY":
            return self._use_court_prideful_superiority(stratagem, **kwargs)
        if name_u == "SINUOUS BREACH":
            return self._use_court_sinuous_breach(stratagem, **kwargs)
        if name_u == "CATALYTIC STIMULUS":
            return self._use_court_catalytic_stimulus(stratagem, **kwargs)
        return None

    def _use_emperors_children_rapid_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "ADVANCE AND CLAIM":
            return self._use_rapid_advance_and_claim(stratagem, **kwargs)
        if name_u == "CEASELESS ONSLAUGHT":
            return self._use_rapid_ceaseless_onslaught(stratagem, **kwargs)
        if name_u == "DYNAMIC BREAKTHROUGH":
            return self._use_rapid_dynamic_breakthrough(stratagem, **kwargs)
        if name_u == "ONTO THE NEXT":
            return self._use_rapid_onto_the_next(stratagem, **kwargs)
        if name_u == "OUTFLANKING STRIKE":
            return self._use_rapid_outflanking_strike(stratagem, **kwargs)
        if name_u == "REACTIVE DISEMBARKATION":
            return self._use_rapid_reactive_disembarkation(stratagem, **kwargs)
        return None

    def _use_emperors_children_coterie_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "MARTIAL PERFECTION":
            return self._use_coterie_martial_perfection(stratagem, **kwargs)
        if name_u == "UNSHAKEABLE OPPONENTS":
            return self._use_coterie_unshakeable_opponents(stratagem, **kwargs)
        if name_u == "PROTECTION OF THE DARK PRINCE":
            return self._use_coterie_protection_of_the_dark_prince(stratagem, **kwargs)
        if name_u == "EMBRACE THE PAIN":
            return self._use_coterie_embrace_the_pain(stratagem, **kwargs)
        return None

    def _use_emperors_children_mercurial_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "CAPRICIOUS REACTIONS":
            return self._use_mercurial_capricious_reactions(stratagem, **kwargs)
        if name_u == "COMBAT STIMMS":
            return self._use_mercurial_combat_stimms(stratagem, **kwargs)
        if name_u == "VIOLENT EXCESS":
            return self._use_mercurial_violent_excess(stratagem, **kwargs)
        if name_u == "HONOUR THE PRINCE":
            return self._use_mercurial_honour_the_prince(stratagem, **kwargs)
        if name_u == "DARK VIGOUR":
            return self._use_mercurial_dark_vigour(stratagem, **kwargs)
        if name_u == "CRUEL RAIDERS":
            return self._use_mercurial_cruel_raiders(stratagem, **kwargs)
        return None
