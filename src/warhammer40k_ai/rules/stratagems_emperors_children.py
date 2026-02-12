from __future__ import annotations

import logging
from typing import Any, Optional

from ..utility.aura_utils import horizontal_distance_between_bases_2d
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

    def _is_emperors_children_unit(self, unit: Any) -> bool:
        root = self._ec_root(unit)
        if root is None:
            return False
        mgr = self._get_emperors_children_mgr()
        checker = getattr(mgr, "is_emperors_children_unit", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        return self._ec_has_keyword(root, "EMPEROR'S CHILDREN")

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
